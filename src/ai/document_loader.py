from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import fitz
from PIL import Image

from src.ai.ocr_engine import OCREngine, OCREngineUnavailable, OCRWord


BBox = tuple[float, float, float, float]
ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class TextBlock:
    page_number: int
    text: str
    bbox: BBox
    source: str = "text"
    confidence: float | None = None


@dataclass(frozen=True)
class DocumentPage:
    page_number: int
    text: str
    width: float
    height: float
    text_blocks: tuple[TextBlock, ...] = ()
    source: str = "text"
    ocr_used: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentChunk:
    page_number: int
    text: str
    chunk_index: int
    bbox: BBox | None = None
    source: str = "text"
    char_start: int = 0
    char_end: int = 0


@dataclass(frozen=True)
class DocumentLoadResult:
    path: str
    pages: tuple[DocumentPage, ...]
    chunks: tuple[DocumentChunk, ...]
    warnings: tuple[str, ...] = ()
    used_ocr: bool = False


class DocumentLoader:
    """PDF text extraction, OCR fallback and chunking for local AI features."""

    def __init__(
        self,
        chunk_chars: int = 1400,
        overlap_chars: int = 180,
        min_text_chars_for_ocr: int = 24,
        ocr_dpi: int = 180,
    ):
        self.chunk_chars = max(400, chunk_chars)
        self.overlap_chars = max(0, min(overlap_chars, self.chunk_chars // 2))
        self.min_text_chars_for_ocr = max(0, min_text_chars_for_ocr)
        self.ocr_dpi = max(100, min(ocr_dpi, 300))

    def load_pdf(
        self,
        pdf_path: str,
        *,
        use_ocr: bool = True,
        ocr_engine: OCREngine | None = None,
        progress: ProgressCallback | None = None,
    ) -> DocumentLoadResult:
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(pdf_path)

        pages: list[DocumentPage] = []
        chunks: list[DocumentChunk] = []
        warnings: list[str] = []

        with fitz.open(str(path)) as doc:
            total_pages = len(doc)
            for index, page in enumerate(doc, start=1):
                page_data = self._load_page(
                    page,
                    page_number=index,
                    use_ocr=use_ocr,
                    ocr_engine=ocr_engine,
                )
                warnings.extend(page_data.warnings)
                pages.append(page_data)
                chunks.extend(self.chunk_page(page_data))
                if progress:
                    progress(index, total_pages)

        return DocumentLoadResult(
            str(path),
            tuple(pages),
            tuple(chunks),
            warnings=tuple(warnings),
            used_ocr=any(page.ocr_used for page in pages),
        )

    def _load_page(
        self,
        page,
        *,
        page_number: int,
        use_ocr: bool,
        ocr_engine: OCREngine | None,
    ) -> DocumentPage:
        rect = page.rect
        width = float(rect.width)
        height = float(rect.height)
        blocks = self._extract_text_blocks(page, page_number)
        text = self._blocks_to_text(blocks)
        warnings: list[str] = []

        should_try_ocr = use_ocr and len(" ".join(text.split())) < self.min_text_chars_for_ocr
        if should_try_ocr:
            if ocr_engine is None:
                ocr_engine = OCREngine()
            if ocr_engine.is_available():
                try:
                    ocr_blocks, ocr_text = self._extract_ocr_blocks(page, page_number, ocr_engine)
                    if len(" ".join(ocr_text.split())) > len(" ".join(text.split())):
                        return DocumentPage(
                            page_number,
                            ocr_text,
                            width,
                            height,
                            text_blocks=tuple(ocr_blocks),
                            source="ocr",
                            ocr_used=bool(ocr_text.strip()),
                        )
                except (OCREngineUnavailable, RuntimeError, OSError, ValueError) as exc:
                    warnings.append(f"Sayfa {page_number}: OCR çalıştırılamadı: {exc}")
            else:
                warnings.append(f"Sayfa {page_number}: {ocr_engine.status_message()}")

        source = "text" if text.strip() else "empty"
        return DocumentPage(
            page_number,
            text,
            width,
            height,
            text_blocks=tuple(blocks),
            source=source,
            warnings=tuple(warnings),
        )

    def _extract_text_blocks(self, page, page_number: int) -> list[TextBlock]:
        blocks: list[TextBlock] = []
        for raw_block in page.get_text("blocks") or []:
            if len(raw_block) < 5:
                continue

            block_type = int(raw_block[6]) if len(raw_block) > 6 else 0
            if block_type != 0:
                continue

            text = self._normalize_text(str(raw_block[4]))
            if not text:
                continue

            x0, y0, x1, y1 = (float(raw_block[0]), float(raw_block[1]), float(raw_block[2]), float(raw_block[3]))
            blocks.append(TextBlock(page_number, text, self._clean_bbox((x0, y0, x1, y1)), source="text"))
        return blocks

    def _extract_ocr_blocks(
        self,
        page,
        page_number: int,
        ocr_engine: OCREngine,
    ) -> tuple[list[TextBlock], str]:
        image = self._render_page(page)
        words = ocr_engine.pil_to_words(image)
        blocks = self._ocr_words_to_blocks(words, page_number, page.rect, image.size)

        if blocks:
            return blocks, self._blocks_to_text(blocks)

        text = self._normalize_text(ocr_engine.pil_to_text(image))
        if not text:
            return [], ""

        page_bbox = (0.0, 0.0, float(page.rect.width), float(page.rect.height))
        return [TextBlock(page_number, text, page_bbox, source="ocr")], text

    def _render_page(self, page) -> Image.Image:
        scale = self.ocr_dpi / 72.0
        matrix = fitz.Matrix(scale, scale)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

    def _ocr_words_to_blocks(
        self,
        words: list[OCRWord],
        page_number: int,
        page_rect,
        image_size: tuple[int, int],
    ) -> list[TextBlock]:
        image_width, image_height = image_size
        if image_width <= 0 or image_height <= 0:
            return []

        scale_x = float(page_rect.width) / float(image_width)
        scale_y = float(page_rect.height) / float(image_height)
        blocks: list[TextBlock] = []

        for word in words:
            x0, y0, x1, y1 = word.bbox
            blocks.append(
                TextBlock(
                    page_number=page_number,
                    text=self._normalize_text(word.text),
                    bbox=self._clean_bbox((x0 * scale_x, y0 * scale_y, x1 * scale_x, y1 * scale_y)),
                    source="ocr",
                    confidence=word.confidence,
                )
            )
        return [block for block in blocks if block.text]

    def chunk_page(self, page: DocumentPage) -> list[DocumentChunk]:
        text, entries = self._page_text_with_offsets(page)
        if not text:
            return []

        chunks: list[DocumentChunk] = []
        start = 0
        idx = 0
        while start < len(text):
            previous_start = start
            end = min(len(text), start + self.chunk_chars)
            if end < len(text):
                split_at = text.rfind(" ", start, end)
                if split_at > start + self.chunk_chars // 2:
                    end = split_at
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    DocumentChunk(
                        page.page_number,
                        chunk_text,
                        idx,
                        bbox=self._bbox_for_range(entries, start, end),
                        source=self._source_for_range(entries, start, end) or page.source,
                        char_start=start,
                        char_end=end,
                    )
                )
                idx += 1
            if end >= len(text):
                break
            start = max(previous_start + 1, end - self.overlap_chars)
        return chunks

    def _page_text_with_offsets(self, page: DocumentPage) -> tuple[str, list[tuple[int, int, TextBlock]]]:
        entries: list[tuple[int, int, TextBlock]] = []
        parts: list[str] = []
        cursor = 0

        for block in page.text_blocks:
            text = self._normalize_text(block.text)
            if not text:
                continue
            if parts:
                cursor += 1
            start = cursor
            parts.append(text)
            cursor += len(text)
            entries.append((start, cursor, block))

        if parts:
            return " ".join(parts), entries

        text = self._normalize_text(page.text)
        if not text:
            return "", []

        fallback = TextBlock(
            page.page_number,
            text,
            (0.0, 0.0, page.width, page.height),
            source=page.source,
        )
        return text, [(0, len(text), fallback)]

    def _bbox_for_range(self, entries: list[tuple[int, int, TextBlock]], start: int, end: int) -> BBox | None:
        boxes = [block.bbox for block_start, block_end, block in entries if block_end > start and block_start < end]
        if not boxes:
            return None
        return self._union_bbox(boxes)

    def _source_for_range(self, entries: list[tuple[int, int, TextBlock]], start: int, end: int) -> str:
        sources = {block.source for block_start, block_end, block in entries if block_end > start and block_start < end}
        if "ocr" in sources:
            return "ocr"
        if "text" in sources:
            return "text"
        return next(iter(sources), "")

    @staticmethod
    def _blocks_to_text(blocks: list[TextBlock]) -> str:
        return "\n".join(block.text for block in blocks if block.text).strip()

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(text.replace("\x00", " ").split())

    @staticmethod
    def _clean_bbox(bbox: BBox) -> BBox:
        x0, y0, x1, y1 = bbox
        return (float(min(x0, x1)), float(min(y0, y1)), float(max(x0, x1)), float(max(y0, y1)))

    @staticmethod
    def _union_bbox(boxes: list[BBox]) -> BBox:
        return (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
