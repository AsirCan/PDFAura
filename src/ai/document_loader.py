"""Page-based PDF text extraction for the local RAG features.

Digital pages are read with PyMuPDF; pages that hold (almost) no text fall
back to the Tesseract helpers in :mod:`src.core.ocr`. The extracted pages and
their chunks are cached under ``%APPDATA%\\PDFAura\\ai_cache\\documents`` keyed
by the SHA-256 of the file, so asking a second question never reads the PDF
again.

Everything here works without an LLM or an OCR engine: a missing optional
dependency degrades to "no text on that page", not to an exception.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.core.config_manager import cfg
from src.core.lang_manager import _
from src.core.task_manager import CancelledError


logger = logging.getLogger(__name__)

ProgressCallback = Callable[..., None]
CancelCheck = Callable[[], bool] | None

CACHE_VERSION = 1
DEFAULT_CHUNK_SIZE = 900
DEFAULT_CHUNK_OVERLAP = 150
DEFAULT_MIN_PAGE_CHARS = 24
# A page with less text than this is treated as scanned and gets OCR.
_OCR_MATRIX = 2.0


@dataclass(frozen=True)
class TextBlock:
    """A text block on a page and where it sits in PDF coordinates."""

    text: str
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


@dataclass(frozen=True)
class PageText:
    page_number: int          # 1-based, like the page numbers users see
    text: str
    blocks: tuple[TextBlock, ...] = ()
    ocr_used: bool = False


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    page_number: int
    text: str
    start: int = 0
    end: int = 0
    bbox: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class LoadedDocument:
    path: str
    file_hash: str
    pages: tuple[PageText, ...]
    chunks: tuple[DocumentChunk, ...]
    from_cache: bool = False
    cache_path: str = ""

    @property
    def page_count(self) -> int:
        return len(self.pages)


def check_cancelled(cancel: CancelCheck) -> None:
    """Raise CancelledError if *cancel* asks us to stop.

    Accepts a plain ``callable() -> bool`` and a
    :class:`src.core.task_manager.TaskContext`.
    """
    if cancel is None:
        return
    checker = getattr(cancel, "check_cancelled", None)
    if callable(checker):
        checker()
        return
    if callable(cancel):
        if cancel():
            raise CancelledError("İşlem kullanıcı tarafından iptal edildi.")
        return
    if getattr(cancel, "is_cancelled", False):
        raise CancelledError("İşlem kullanıcı tarafından iptal edildi.")


def report_progress(progress: ProgressCallback | None, current: int, total: int,
                    message: str = "") -> None:
    """Call a UI progress callback, tolerating two-argument callbacks."""
    if progress is None:
        return
    try:
        progress(current, total, message)
    except TypeError:
        # Some callers only accept (current, total); do not lose the update.
        progress(current, total)


def default_cache_dir() -> Path:
    return Path(cfg.config_dir).expanduser() / "ai_cache" / "documents"


def file_hash(path: str | os.PathLike, cancel: CancelCheck = None) -> str:
    if "\x00" in str(path):
        raise ValueError("Path contains invalid null character")
    """SHA-256 of the file, read in blocks so large PDFs stay cheap."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            check_cancelled(cancel)
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text or ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _text_blocks(page) -> tuple[TextBlock, ...]:
    """The page's text blocks, in reading order, with their coordinates."""
    blocks = []
    for raw in page.get_text("blocks") or ():
        # (x0, y0, x1, y1, text, block_no, block_type); 0 is text.
        if len(raw) < 5 or (len(raw) > 6 and raw[6] != 0):
            continue
        text = _normalize_text(raw[4])
        if not text:
            continue
        try:
            bbox = tuple(round(float(value), 2) for value in raw[:4])
        except (TypeError, ValueError):
            bbox = (0.0, 0.0, 0.0, 0.0)
        blocks.append(TextBlock(text=text, bbox=bbox))
    return tuple(blocks)


def _ocr_page_text(page, lang: str | None = None, cancel: CancelCheck = None) -> str:
    """OCR one rendered page with Tesseract, or "" when it is unavailable."""
    try:
        from src.core import ocr as ocr_core
        if not ocr_core.check_tesseract_availability():
            return ""
        language = ocr_core.resolve_ocr_language(lang)

        import fitz
        from PIL import Image

        pix = page.get_pixmap(matrix=fitz.Matrix(_OCR_MATRIX, _OCR_MATRIX), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        check_cancelled(cancel)
        text = ocr_core.pytesseract.image_to_string(image, lang=language)
        return _normalize_text(text)
    except CancelledError:
        raise
    except Exception as exc:
        # Missing Tesseract data is not a reason to fail the whole document.
        logger.warning("OCR fallback failed: %s", exc)
        return ""


def _page_bbox(page) -> tuple[float, float, float, float]:
    try:
        rect = page.rect
        return (round(float(rect.x0), 2), round(float(rect.y0), 2),
                round(float(rect.x1), 2), round(float(rect.y1), 2))
    except Exception:
        return (0.0, 0.0, 0.0, 0.0)


def extract_pages(pdf_path: str | os.PathLike, *, use_ocr: bool = True,
                  ocr_lang: str | None = None,
                  min_page_chars: int = DEFAULT_MIN_PAGE_CHARS,
                  progress: ProgressCallback | None = None,
                  cancel: CancelCheck = None) -> tuple[PageText, ...]:
    """Read every page of *pdf_path* as text, with an OCR fallback."""
    import fitz

    document = fitz.open(str(pdf_path))
    pages: list[PageText] = []
    try:
        if getattr(document, "needs_pass", False):
            from src.core.errors import PdfPasswordError
            raise PdfPasswordError(_("err_pdf_password_protected"))
        total = document.page_count
        for index in range(total):
            check_cancelled(cancel)
            report_progress(progress, index, total,
                            f"Sayfa {index + 1}/{total} okunuyor")

            page = document.load_page(index)
            blocks = _text_blocks(page)
            text = _normalize_text("\n".join(block.text for block in blocks))
            ocr_used = False

            if use_ocr and len(text) < max(1, int(min_page_chars)):
                ocr_text = _ocr_page_text(page, ocr_lang, cancel)
                if len(ocr_text) > len(text):
                    text = ocr_text
                    # Tesseract is called with a whole rendered page, so its
                    # coordinates are the page rectangle rather than lines.
                    blocks = (TextBlock(text=ocr_text, bbox=_page_bbox(page)),)
                    ocr_used = True

            pages.append(PageText(page_number=index + 1, text=text,
                                  blocks=blocks, ocr_used=ocr_used))

        report_progress(progress, total, total, "Belge okundu")
    finally:
        if not getattr(document, "is_closed", False):
            document.close()
    return tuple(pages)


def _block_spans(page: PageText) -> list[tuple[int, int, tuple[float, float, float, float]]]:
    """Where each block's text sits inside ``page.text``."""
    spans = []
    cursor = 0
    for block in page.blocks:
        index = page.text.find(block.text, cursor)
        if index < 0:
            continue
        spans.append((index, index + len(block.text), block.bbox))
        cursor = index + len(block.text)
    return spans


def _bbox_for_range(spans, start: int, end: int):
    boxes = [bbox for (block_start, block_end, bbox) in spans
             if block_end > start and block_start < end]
    if not boxes:
        return None
    return (min(box[0] for box in boxes), min(box[1] for box in boxes),
            max(box[2] for box in boxes), max(box[3] for box in boxes))


def _break_point(text: str, start: int, end: int) -> int:
    """Prefer to end a chunk at a paragraph, sentence or word boundary."""
    window = text[start:end]
    tail = max(int(len(window) * 0.55), len(window) - 240)
    for separator in ("\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "):
        position = window.rfind(separator, tail)
        if position > 0:
            return start + position + len(separator)
    return end


def chunk_page(page: PageText, *, chunk_size: int = DEFAULT_CHUNK_SIZE,
               chunk_overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[DocumentChunk]:
    """Split one page into overlapping chunks, never crossing page bounds."""
    if chunk_size <= 0:
        raise ValueError("chunk_size pozitif olmalı.")
    chunk_size = int(chunk_size)
    chunk_overlap = max(0, min(int(chunk_overlap), chunk_size - 1))

    text = page.text
    if not text.strip():
        return []

    spans = _block_spans(page)
    chunks: list[DocumentChunk] = []
    start = 0
    index = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            end = _break_point(text, start, end)

        piece = _normalize_text(text[start:end])
        if piece:
            chunks.append(DocumentChunk(
                chunk_id=f"p{page.page_number}-c{index}",
                page_number=page.page_number,
                text=piece,
                start=start,
                end=end,
                bbox=_bbox_for_range(spans, start, end),
            ))
            index += 1

        if end >= len(text):
            break
        next_start = end - chunk_overlap
        if next_start <= start:
            next_start = end
        start = next_start
    return chunks


def chunk_pages(pages, *, chunk_size: int = DEFAULT_CHUNK_SIZE,
                chunk_overlap: int = DEFAULT_CHUNK_OVERLAP) -> tuple[DocumentChunk, ...]:
    chunks: list[DocumentChunk] = []
    for page in pages:
        chunks.extend(chunk_page(page, chunk_size=chunk_size,
                                 chunk_overlap=chunk_overlap))
    return tuple(chunks)


def _page_to_dict(page: PageText) -> dict:
    return {
        "page_number": page.page_number,
        "text": page.text,
        "ocr_used": page.ocr_used,
        "blocks": [{"text": block.text, "bbox": list(block.bbox)}
                   for block in page.blocks],
    }


def _page_from_dict(data: dict) -> PageText:
    blocks = tuple(
        TextBlock(text=str(block.get("text", "")),
                  bbox=tuple(block.get("bbox") or (0.0, 0.0, 0.0, 0.0)))
        for block in data.get("blocks", [])
    )
    return PageText(page_number=int(data.get("page_number", 0)),
                    text=str(data.get("text", "")),
                    blocks=blocks,
                    ocr_used=bool(data.get("ocr_used", False)))


def _chunk_to_dict(chunk: DocumentChunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "page_number": chunk.page_number,
        "text": chunk.text,
        "start": chunk.start,
        "end": chunk.end,
        "bbox": list(chunk.bbox) if chunk.bbox else None,
    }


def _chunk_from_dict(data: dict) -> DocumentChunk:
    bbox = data.get("bbox")
    return DocumentChunk(
        chunk_id=str(data.get("chunk_id", "")),
        page_number=int(data.get("page_number", 0)),
        text=str(data.get("text", "")),
        start=int(data.get("start", 0)),
        end=int(data.get("end", 0)),
        bbox=tuple(bbox) if bbox else None,
    )


def _read_cache(cache_path: Path) -> dict | None:
    try:
        with open(cache_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict) and data.get("version") == CACHE_VERSION:
            return data
    except (OSError, ValueError, TypeError):
        pass
    return None


def _write_cache(cache_path: Path, document: LoadedDocument, *,
                 chunk_size: int, chunk_overlap: int) -> None:
    payload = {
        "version": CACHE_VERSION,
        "file_hash": document.file_hash,
        "chunk_size": int(chunk_size),
        "chunk_overlap": int(chunk_overlap),
        "pages": [_page_to_dict(page) for page in document.pages],
        "chunks": [_chunk_to_dict(chunk) for chunk in document.chunks],
    }
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_path = tempfile.mkstemp(prefix=".rag-", suffix=".json",
                                             dir=str(cache_path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, cache_path)
        except Exception:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise
    except OSError as exc:
        # An unwritable cache only costs speed; the answer still comes.
        logger.warning("RAG cache not written (%s): %s", cache_path, exc)


def load_document(pdf_path: str | os.PathLike, *, cache_dir: str | os.PathLike | None = None,
                  use_cache: bool = True, use_ocr: bool = True,
                  ocr_lang: str | None = None, chunk_size: int = DEFAULT_CHUNK_SIZE,
                  chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
                  min_page_chars: int = DEFAULT_MIN_PAGE_CHARS,
                  progress: ProgressCallback | None = None,
                  cancel: CancelCheck = None) -> LoadedDocument:
    if "\x00" in str(pdf_path):
        raise ValueError("Path contains invalid null character")
    """Read a PDF into pages and chunks, reusing the on-disk cache."""
    if chunk_size <= 0:
        raise ValueError("chunk_size pozitif olmalı.")

    path = Path(pdf_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"PDF bulunamadı: {path}")

    check_cancelled(cancel)
    digest = file_hash(path, cancel)
    directory = Path(cache_dir).expanduser() if cache_dir else default_cache_dir()
    cache_path = directory / f"{digest}.json"

    cached = _read_cache(cache_path) if use_cache else None
    if cached:
        try:
            pages = tuple(_page_from_dict(item) for item in cached.get("pages", []))
            if (int(cached.get("chunk_size", -1)) == int(chunk_size)
                    and int(cached.get("chunk_overlap", -1)) == int(chunk_overlap)):
                chunks = tuple(_chunk_from_dict(item)
                               for item in cached.get("chunks", []))
            else:
                chunks = chunk_pages(pages, chunk_size=chunk_size,
                                     chunk_overlap=chunk_overlap)
            msg = _("str_loaded_from_cache")
            report_progress(progress, 1, 1, msg)
            return LoadedDocument(path=str(path), file_hash=digest, pages=pages,
                                  chunks=chunks, from_cache=True,
                                  cache_path=str(cache_path))
        except (TypeError, ValueError, KeyError, AttributeError):
            # A damaged cache is not fatal: read the PDF again and replace it.
            logger.warning("RAG cache unreadable, rebuilding: %s", cache_path)

    pages = extract_pages(path, use_ocr=use_ocr, ocr_lang=ocr_lang,
                          min_page_chars=min_page_chars,
                          progress=progress, cancel=cancel)
    check_cancelled(cancel)
    chunks = chunk_pages(pages, chunk_size=chunk_size,
                         chunk_overlap=chunk_overlap)
    document = LoadedDocument(path=str(path), file_hash=digest, pages=pages,
                              chunks=chunks, from_cache=False,
                              cache_path=str(cache_path))
    if use_cache:
        _write_cache(cache_path, document, chunk_size=chunk_size,
                     chunk_overlap=chunk_overlap)
    return document
