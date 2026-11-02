"""Faz 10 — PDF comparison and change explanation.

Two PDFs are compared page by page and paragraph by paragraph. The text diff
is the source of truth: :func:`compare_pdfs` returns a report with the page
count change, metadata differences, added/removed/changed paragraphs (with a
page reference in *both* documents), a simple rendered-image difference per
page, and a heuristic category for every change:

``biçim``   only case, punctuation or whitespace changed
``anlam``   the wording changed without touching risky content
``riskli``  a number, date, amount, percentage or a contract keyword such as
            ``ceza``, ``tazminat``, ``fesih``, ``süre`` or ``ödeme`` changed

The local LLM is optional and only used to *explain* the diff in Turkish;
:func:`explain_changes` falls back to a deterministic template. PyMuPDF is
needed for image comparison and the report PDF, but the text diff still works
through pypdf when it is missing.
"""
from __future__ import annotations

import difflib
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.core.common import PdfPasswordError, open_pdf_reader
from src.core.lang_manager import _
from src.core.task_manager import CancelledError


logger = logging.getLogger(__name__)

ProgressCallback = Callable[..., None]
CancelCheck = Callable[[], bool] | None

CATEGORY_FORMAT = "biçim"
CATEGORY_MEANING = "anlam"
CATEGORY_RISKY = "riskli"
CATEGORIES = (CATEGORY_FORMAT, CATEGORY_MEANING, CATEGORY_RISKY)

# Page similarity needed before two pages are treated as versions of the same
# page. Below it the page is reported as added or removed instead.
MIN_PAGE_SIMILARITY = 0.12
# Paragraph similarity needed before a removed/added pair is reported as one
# "changed" paragraph instead of separate removed + added items.
MIN_PARAGRAPH_SIMILARITY = 0.50
# Share of differing pixels that counts as an image change on a page.
IMAGE_DIFF_THRESHOLD = 0.01
IMAGE_ZOOM = 1.0

# Agreement/contract wording: a change touching one of these is worth a human
# reading the clause again. Stems match suffixed forms ("cezası", "süresi").
_CRITICAL_RE = re.compile(
    r"\b(?:ceza\w*|tazminat\w*|fesih\w*|feshe\w*|fesh\w*|süre\w*|sure\w*|ödeme\w*|öden\w*|odeme\w*|oden\w*)\b",
    re.UNICODE,
)
_RISK_RE = re.compile(
    r"\b(?:ceza\w*|tazminat\w*|fesih\w*|feshe\w*|fesh\w*|süre\w*|sure\w*|"
    r"ödeme\w*|öden\w*|odeme\w*|oden\w*|faiz\w*|temerrüt\w*|temerru\w*|"
    r"cayma\w*|ihbar\w*|kira\w*|ücret\w*|ucret\w*|bedel\w*|vergi\w*|"
    r"yaptırım\w*|yaptirim\w*|artış\w*|artis\w*|indirim\w*|iade\w*|"
    r"borç\w*|borc\w*|zam(?:m?[ıiaueoöü]\w*)?)\b",
    re.UNICODE,
)
_NUMBER_RE = re.compile(r"\b\d+(?:[.,:/\-]\d+)*\b")
_PERCENT_RE = re.compile(r"%\s*\d+(?:[.,]\d+)?|\b\d+(?:[.,]\d+)?\s*%|\byüzde\s*\d+(?:[.,]\d+)?\b")
_CURRENCY_RE = re.compile(r"\b(?:tl|try|usd|eur|euro|dolar|sterlin|gbp|chf)\b|[₺$€£]")
_MONTHS_RE = re.compile(
    r"\b(?:ocak|şubat|subat|mart|nisan|mayıs|mayis|haziran|temmuz|ağustos|agustos|eylül|eylul|ekim|kasım|kasim|aralık|aralik)\b"
)
_WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class _PageText:
    number: int          # 1-based, as the user sees it
    text: str
    paragraphs: tuple[str, ...]


# ── Small shared helpers ────────────────────────────────────────────────────

def check_cancelled(cancel: CancelCheck) -> None:
    """Raise CancelledError if *cancel* asks us to stop."""
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
        progress(current, total)


def _prepare_text(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text or ""))
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_paragraph(text: str) -> str:
    """Collapse line wrapping and repeated spaces inside one paragraph."""
    text = _prepare_text(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", " ", text)
    return text.strip()


def _fold(text: str) -> str:
    """Casefold Turkish text without leaving the combining dot of 'İ'."""
    return _prepare_text(text).casefold().replace("\u0307", "")


def _format_key(text: str) -> str:
    """Text with case, whitespace and punctuation removed."""
    return re.sub(r"[\W_]+", "", _fold(text))


def _similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, _fold(a), _fold(b),
                                   autojunk=False).ratio()


def _token_similarity(a: str, b: str) -> float:
    """Fast word-overlap similarity used to align whole pages."""
    a_words = set(_WORD_RE.findall(_fold(a)))
    b_words = set(_WORD_RE.findall(_fold(b)))
    if not a_words and not b_words:
        return 1.0
    if not a_words or not b_words:
        return 0.0
    return 2.0 * len(a_words & b_words) / (len(a_words) + len(b_words))


def _risky_tokens(text: str) -> set[str]:
    """Numbers, dates, amounts, percentages and risky keywords in *text*."""
    folded = _fold(text)
    tokens = set(_NUMBER_RE.findall(folded))
    tokens.update(_PERCENT_RE.findall(folded))
    tokens.update(f"#month:{m}" for m in _MONTHS_RE.findall(folded))
    tokens.update(f"#curr:{c}" for c in _CURRENCY_RE.findall(folded))
    tokens.update(f"#kw:{w}" for w in _RISK_RE.findall(folded))
    return tokens


def _has_critical_clause(text: str) -> bool:
    """Return True if text contains core contract keywords (ceza, fesih, etc.)."""
    return bool(_CRITICAL_RE.search(_fold(text)))


def _classify(kind: str, a_text: str = "", b_text: str = "") -> tuple[str, str]:
    """Return ``(category, Turkish reason)`` for one change."""
    if kind in ("added", "removed"):
        target = a_text if kind == "removed" else b_text
        if not _format_key(target):
            return CATEGORY_FORMAT, "Yalnızca biçim ve boşluk karakterleri."
        if _risky_tokens(target) or _has_critical_clause(target):
            return CATEGORY_RISKY, (
                "Eklenen veya kaldırılan metin sayı, tarih, tutar, oran veya "
                "riskli bir sözleşme ifadesi içeriyor."
            )
        return CATEGORY_MEANING, (
            "Yeni bir madde eklendi." if kind == "added" else "Bir madde kaldırıldı."
        )

    # For changed text:
    if _format_key(a_text) == _format_key(b_text):
        return CATEGORY_FORMAT, (
            "Yalnızca biçim değişti (büyük/küçük harf, boşluk veya noktalama)."
        )

    if _risky_tokens(a_text) != _risky_tokens(b_text):
        return CATEGORY_RISKY, (
            "Sayı, tarih, tutar, oran veya riskli sözleşme ifadesi değişti."
        )

    if _has_critical_clause(a_text) or _has_critical_clause(b_text):
        return CATEGORY_RISKY, (
            "Kritik sözleşme maddesi (ceza, tazminat, fesih, süre veya ödeme) değiştirildi."
        )

    return CATEGORY_MEANING, "Metnin anlamı değişti."


def _make_change(kind: str, a_text: str = "", b_text: str = "",
                 a_page: int | None = None, b_page: int | None = None) -> dict:
    category, reason = _classify(kind, a_text, b_text)
    return {
        "type": kind,
        "category": category,
        "a_page": a_page,
        "b_page": b_page,
        "page": b_page if b_page is not None else a_page,
        "a_text": a_text,
        "b_text": b_text,
        "reason": reason,
    }


# ── Reading pages and paragraphs ────────────────────────────────────────────

def _split_text_paragraphs(text: str) -> list[str]:
    """Split extracted text on blank lines, falling back to lines."""
    chunks = re.split(r"\n\s*\n", _prepare_text(text))
    paragraphs = []
    for chunk in chunks:
        normalized = _normalize_paragraph(chunk)
        if normalized:
            paragraphs.append(normalized)
    if len(paragraphs) <= 1:
        lines = [_normalize_paragraph(line) for line in _prepare_text(text).splitlines()]
        lines = [line for line in lines if line]
        if len(lines) > 1:
            return lines
    return paragraphs


def _page_paragraphs(page) -> list[str]:
    """The page's text blocks in reading order, each as one paragraph."""
    paragraphs = []
    for block in page.get_text("blocks", sort=True) or ():
        # (x0, y0, x1, y1, text, block_no, block_type); 0 is text.
        if len(block) < 5 or (len(block) > 6 and block[6] != 0):
            continue
        raw = str(block[4])
        chunks = re.split(r"\n\s*\n", _prepare_text(raw))
        for chunk in chunks:
            text = _normalize_paragraph(chunk)
            if text:
                paragraphs.append(text)
    if not paragraphs or len(paragraphs) <= 1:
        fallback = _split_text_paragraphs(page.get_text("text", sort=True))
        if len(fallback) > len(paragraphs):
            return fallback
    return paragraphs


def _read_pages_with_fitz(path: str, cancel: CancelCheck = None) -> tuple[_PageText, ...]:
    import fitz

    document = fitz.open(str(path))
    try:
        if document.needs_pass:
            raise PdfPasswordError(_("err_pdf_password_protected"))
        pages = []
        for index in range(document.page_count):
            check_cancelled(cancel)
            page = document.load_page(index)
            paragraphs = tuple(_page_paragraphs(page))
            pages.append(_PageText(number=index + 1,
                                   text="\n".join(paragraphs),
                                   paragraphs=paragraphs))
        return tuple(pages)
    finally:
        document.close()


def _read_pages_with_pypdf(path: str, cancel: CancelCheck = None) -> tuple[_PageText, ...]:
    """Fallback reader when PyMuPDF is not installed."""
    reader = open_pdf_reader(path)
    try:
        pages = []
        for index, page in enumerate(reader.pages):
            check_cancelled(cancel)
            text = page.extract_text() or ""
            paragraphs = tuple(_split_text_paragraphs(text))
            pages.append(_PageText(number=index + 1,
                                   text="\n".join(paragraphs),
                                   paragraphs=paragraphs))
        return tuple(pages)
    finally:
        if hasattr(reader, "close"):
            reader.close()


def _read_pages(path: str, cancel: CancelCheck = None) -> tuple[_PageText, ...]:
    try:
        import fitz  # noqa: F401
    except Exception as exc:
        logger.debug("PyMuPDF unavailable, using pypdf for comparison: %s", exc)
        return _read_pages_with_pypdf(path, cancel)
    return _read_pages_with_fitz(path, cancel)


def _safe_metadata(path: str) -> dict:
    try:
        from src.core.metainfo import read_metadata
        return read_metadata(path)
    except Exception as exc:
        logger.warning("Metadata could not be read (%s): %s", path, exc)
        return {}


# ── Page alignment ──────────────────────────────────────────────────────────

def _align_pages(a_pages, b_pages) -> list[tuple[int | None, int | None]]:
    """Pair pages by content, allowing inserted and removed pages.

    Returns ``(a_page, b_page)`` pairs in document order; None marks a gap.
    """
    n, m = len(a_pages), len(b_pages)
    if not n:
        return [(None, j + 1) for j in range(m)]
    if not m:
        return [(i + 1, None) for i in range(n)]

    scores = [[0.0] * (m + 1) for _ in range(n + 1)]
    choices = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            similarity = _token_similarity(a_pages[i - 1].text, b_pages[j - 1].text)
            match = similarity if similarity >= MIN_PAGE_SIMILARITY else -1.0

            best = scores[i - 1][j]
            choice = 1  # a page without a partner
            if scores[i][j - 1] > best + 1e-12:
                best = scores[i][j - 1]
                choice = 2  # a new page
            diagonal = scores[i - 1][j - 1] + match
            if diagonal > best + 1e-12:
                best = diagonal
                choice = 3  # the same page in both documents
            scores[i][j] = best
            choices[i][j] = choice

    pairs = []
    i, j = n, m
    while i or j:
        if i and j and choices[i][j] == 3:
            pairs.append((i, j))
            i -= 1
            j -= 1
        elif i and (not j or choices[i][j] == 1):
            pairs.append((i, None))
            i -= 1
        else:
            pairs.append((None, j))
            j -= 1
    pairs.reverse()
    return pairs


# ── Paragraph diff ──────────────────────────────────────────────────────────

def _pair_replacement(a_items, b_items):
    """Pair paragraphs inside a difflib replace block by similarity.

    Returns ``(pairs, removed, added)``: pairs are ``(a_index, b_index)``;
    removed / added hold the unpaired indices.
    """
    n, m = len(a_items), len(b_items)
    if not n:
        return [], [], list(range(m))
    if not m:
        return [], list(range(n)), []

    scores = [[0.0] * (m + 1) for _ in range(n + 1)]
    choices = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            a_text = getattr(a_items[i - 1], "text", a_items[i - 1])
            b_text = getattr(b_items[j - 1], "text", b_items[j - 1])
            similarity = _similarity(a_text, b_text)
            match = similarity if similarity >= MIN_PARAGRAPH_SIMILARITY else -1.0

            best = scores[i - 1][j]
            choice = 1
            if scores[i][j - 1] > best + 1e-12:
                best = scores[i][j - 1]
                choice = 2
            diagonal = scores[i - 1][j - 1] + match
            if diagonal > best + 1e-12:
                best = diagonal
                choice = 3
            scores[i][j] = best
            choices[i][j] = choice

    pairs = []
    removed = []
    added = []
    i, j = n, m
    while i or j:
        if i and j and choices[i][j] == 3:
            pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif i and (not j or choices[i][j] == 1):
            removed.append(i - 1)
            i -= 1
        else:
            added.append(j - 1)
            j -= 1
    pairs.reverse()
    removed.reverse()
    added.reverse()
    return pairs, removed, added


def _paragraph_changes(a_pages, b_pages) -> list[dict]:
    a_items = [(_page.number, paragraph)
               for _page in a_pages for paragraph in _page.paragraphs]
    b_items = [(_page.number, paragraph)
               for _page in b_pages for paragraph in _page.paragraphs]

    matcher = difflib.SequenceMatcher(
        None,
        [text for _page, text in a_items],
        [text for _page, text in b_items],
        autojunk=False,
    )
    changes = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete":
            for page, text in a_items[i1:i2]:
                changes.append(_make_change("removed", a_text=text, a_page=page))
            continue
        if tag == "insert":
            for page, text in b_items[j1:j2]:
                changes.append(_make_change("added", b_text=text, b_page=page))
            continue

        # "replace": pair the closest paragraphs as changed, the rest as
        # removed/added. The pairs keep the page reference of both versions.
        a_slice = [item[1] for item in a_items[i1:i2]]
        b_slice = [item[1] for item in b_items[j1:j2]]
        a_pages_slice = [item[0] for item in a_items[i1:i2]]
        b_pages_slice = [item[0] for item in b_items[j1:j2]]

        pairs, removed, added = _pair_replacement(a_slice, b_slice)
        for a_index, b_index in pairs:
            changes.append(_make_change(
                "changed", a_text=a_slice[a_index], b_text=b_slice[b_index],
                a_page=a_pages_slice[a_index], b_page=b_pages_slice[b_index],
            ))
        for index in removed:
            changes.append(_make_change("removed", a_text=a_slice[index],
                                        a_page=a_pages_slice[index]))
        for index in added:
            changes.append(_make_change("added", b_text=b_slice[index],
                                        b_page=b_pages_slice[index]))
    return changes


# ── Metadata diff ───────────────────────────────────────────────────────────

def _metadata_changes(a_meta: dict, b_meta: dict) -> list[dict]:
    changes = []
    for field in ("title", "author", "subject", "creator", "producer"):
        old = str(a_meta.get(field, "") or "")
        new = str(b_meta.get(field, "") or "")
        if old == new:
            continue
        category, reason = _classify("changed", old, new)
        if category != CATEGORY_RISKY and field in ("creator", "producer"):
            category = CATEGORY_FORMAT
            reason = "Yalnızca belgeyi üreten araç bilgisi değişti."
        changes.append({
            "type": "metadata",
            "category": category,
            "a_page": None,
            "b_page": None,
            "field": field,
            "a_text": old,
            "b_text": new,
            "reason": reason,
        })
    return changes


# ── Rendered image diff ─────────────────────────────────────────────────────

def _byte_diff_ratio(a_bytes: bytes, b_bytes: bytes) -> float:
    if len(a_bytes) != len(b_bytes):
        return 1.0
    if not a_bytes:
        return 0.0
    try:
        import numpy as np
        a = np.frombuffer(a_bytes, dtype=np.uint8)
        b = np.frombuffer(b_bytes, dtype=np.uint8)
        return float(np.count_nonzero(a != b)) / float(a.size)
    except Exception:
        differing = sum(1 for left, right in zip(a_bytes, b_bytes) if left != right)
        return differing / float(len(a_bytes))


def _diff_pixmaps(a_pix, b_pix) -> dict:
    a_width, a_height = a_pix.width, a_pix.height
    b_width, b_height = b_pix.width, b_pix.height
    a_bytes, b_bytes = a_pix.samples, b_pix.samples

    if (a_width, a_height) != (b_width, b_height):
        try:
            from PIL import Image
            image_a = Image.frombytes("L", (a_width, a_height), a_bytes)
            image_b = Image.frombytes("L", (b_width, b_height), b_bytes)
            image_b = image_b.resize(image_a.size)
            a_bytes, b_bytes = image_a.tobytes(), image_b.tobytes()
        except Exception:
            return {"ratio": 1.0, "changed": True, "size_changed": True}

    ratio = _byte_diff_ratio(a_bytes, b_bytes)
    return {
        "ratio": round(ratio, 6),
        "changed": ratio >= IMAGE_DIFF_THRESHOLD,
        "size_changed": (a_width, a_height) != (b_width, b_height),
    }


def _image_diffs(a_path: str, b_path: str,
                 pairs: list[tuple[int, int]],
                 progress: ProgressCallback | None = None,
                 cancel: CancelCheck = None,
                 progress_offset: int = 0,
                 progress_total: int = 0) -> dict:
    if not pairs:
        return {}
    try:
        import fitz
    except Exception as exc:
        logger.debug("PyMuPDF unavailable, skipping image comparison: %s", exc)
        return {}

    results = {}
    a_document = fitz.open(str(a_path))
    b_document = None
    try:
        b_document = fitz.open(str(b_path))
        for index, (a_page, b_page) in enumerate(pairs, 1):
            check_cancelled(cancel)
            report_progress(progress, progress_offset + index, progress_total,
                            f"Sayfa {b_page}/{len(b_document)} görseli karşılaştırılıyor")
            try:
                a_pix = a_document.load_page(a_page - 1).get_pixmap(
                    matrix=fitz.Matrix(IMAGE_ZOOM, IMAGE_ZOOM),
                    colorspace=fitz.csGRAY, alpha=False)
                b_pix = b_document.load_page(b_page - 1).get_pixmap(
                    matrix=fitz.Matrix(IMAGE_ZOOM, IMAGE_ZOOM),
                    colorspace=fitz.csGRAY, alpha=False)
                results[(a_page, b_page)] = _diff_pixmaps(a_pix, b_pix)
            except Exception as exc:
                logger.warning("Page image comparison failed (%s/%s): %s",
                               a_page, b_page, exc)
                results[(a_page, b_page)] = {
                    "ratio": None, "changed": False, "error": str(exc),
                }
    finally:
        if a_document and not getattr(a_document, "is_closed", False):
            a_document.close()
        if b_document and not getattr(b_document, "is_closed", False):
            b_document.close()
    return results


# ── Public API ──────────────────────────────────────────────────────────────

def compare_pdfs(a, b, progress: ProgressCallback | None = None,
                 cancel: CancelCheck = None) -> dict:
    """Compare two PDFs and return a structured change report.

    *progress* receives ``(current, total, message)`` updates; *cancel* may be
    a callable returning True or a :class:`src.core.task_manager.TaskContext`.
    """
    a_path, b_path = str(a), str(b)
    for path in (a_path, b_path):
        if "\x00" in path:
            raise ValueError("Path contains invalid null character")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"PDF bulunamadı: {path}")

    check_cancelled(cancel)
    report_progress(progress, 0, 1, "Belgeler okunuyor")
    a_pages = _read_pages(a_path, cancel)
    b_pages = _read_pages(b_path, cancel)
    check_cancelled(cancel)

    total_steps = max(1, len(a_pages) + len(b_pages) + min(len(a_pages), len(b_pages)))
    report_progress(progress, len(a_pages) + len(b_pages), total_steps,
                    "Metin farkları çıkarılıyor")

    changes = _paragraph_changes(a_pages, b_pages)
    a_meta = _safe_metadata(a_path)
    b_meta = _safe_metadata(b_path)
    metadata_changes = _metadata_changes(a_meta, b_meta)

    alignment = _align_pages(a_pages, b_pages)
    entries = []
    b_entries = {}
    a_to_b = {}
    b_to_a = {}
    for a_page, b_page in alignment:
        if a_page is not None and b_page is not None:
            a_to_b[a_page] = b_page
            b_to_a[b_page] = a_page
        entry = {
            "a_page": a_page,
            "b_page": b_page,
            "status": "added" if a_page is None
                      else "removed" if b_page is None
                      else "unchanged",
            "text_changes": [],
            "image_diff": {"ratio": None, "changed": False},
            "image_diff_ratio": None,
        }
        entries.append(entry)
        if b_page is not None:
            b_entries[b_page] = entry

    # Every text change is attached to the page in the new document when that
    # page exists; removed pages keep the old page reference.
    for change in changes:
        if change.get("a_page") is not None and change.get("b_page") is None:
            change["aligned_b_page"] = a_to_b.get(change["a_page"])
        elif change.get("b_page") is not None and change.get("a_page") is None:
            change["aligned_a_page"] = b_to_a.get(change["b_page"])

        target_b = change.get("b_page") or a_to_b.get(change.get("a_page"))
        entry = b_entries.get(target_b) if target_b is not None else None
        if entry is None:
            entry = next((item for item in entries
                          if item["a_page"] == change.get("a_page")
                          and item["b_page"] is None), None)
        if entry is not None:
            entry["text_changes"].append(change)

    pairs = [(item["a_page"], item["b_page"]) for item in entries
             if item["a_page"] is not None and item["b_page"] is not None]
    image_results = _image_diffs(
        a_path, b_path, pairs, progress=progress, cancel=cancel,
        progress_offset=len(a_pages) + len(b_pages),
        progress_total=total_steps,
    )

    for entry in entries:
        diff = image_results.get((entry["a_page"], entry["b_page"]))
        if diff:
            entry["image_diff"] = diff
            entry["image_diff_ratio"] = diff.get("ratio")

    image_changes = []
    for entry in entries:
        diff = entry.get("image_diff") or {}
        ratio = diff.get("ratio")
        if diff.get("changed") and ratio is not None and not entry["text_changes"]:
            image_changes.append({
                "type": "image",
                "category": CATEGORY_FORMAT,
                "a_page": entry["a_page"],
                "b_page": entry["b_page"],
                "a_text": "",
                "b_text": "",
                "reason": (f"Sayfa görünümü değişti (görsel fark oranı "
                           f"%{ratio * 100:.1f})."),
            })

    for entry in entries:
        if entry["status"] == "added" or entry["status"] == "removed":
            continue
        if entry["text_changes"] or (entry.get("image_diff") or {}).get("changed"):
            entry["status"] = "changed"

    all_changes = metadata_changes + changes + image_changes
    pages_added = [b_page for a_page, b_page in alignment if a_page is None]
    pages_removed = [a_page for a_page, b_page in alignment if b_page is None]
    by_category = {category: sum(1 for change in all_changes
                                 if change["category"] == category)
                   for category in CATEGORIES}
    summary = {
        "total_changes": len(all_changes),
        "text_changes": len(changes),
        "added": sum(1 for change in changes if change["type"] == "added"),
        "removed": sum(1 for change in changes if change["type"] == "removed"),
        "changed": sum(1 for change in changes if change["type"] == "changed"),
        "metadata_changes": len(metadata_changes),
        "image_changes": len(image_changes),
        "by_category": by_category,
        "pages_added": pages_added,
        "pages_removed": pages_removed,
    }

    report_progress(progress, total_steps, total_steps, "Karsilastirma hazir")
    return {
        "a": {"path": a_path, "page_count": len(a_pages), "metadata": a_meta},
        "b": {"path": b_path, "page_count": len(b_pages), "metadata": b_meta},
        "page_count": {
            "a": len(a_pages),
            "b": len(b_pages),
            "delta": len(b_pages) - len(a_pages),
        },
        "metadata_changes": metadata_changes,
        "pages": entries,
        "changes": all_changes,
        "image_diffs": image_results,
        "image_diff_ratio_per_page": {
            (entry["a_page"], entry["b_page"]): (entry.get("image_diff") or {}).get("ratio")
            for entry in entries
        },
        "summary": summary,
        "has_changes": bool(all_changes),
    }


# ── Explanation ─────────────────────────────────────────────────────────────

def _page_ref_text(change: dict) -> str:
    a_page, b_page = change.get("a_page"), change.get("b_page")
    if a_page is not None and b_page is not None:
        if a_page == b_page:
            return f"Sayfa {b_page}"
        return f"Sayfa {a_page} → Sayfa {b_page}"
    if b_page is not None:
        return f"Sayfa {b_page} (yeni)"
    if a_page is not None:
        return f"Sayfa {a_page} (kaldırıldı)"
    return "Belge geneli"


def _type_text(kind: str) -> str:
    return {
        "added": "Eklendi",
        "removed": "Kaldırıldı",
        "changed": "Değişti",
        "image": "Görsel değişiklik",
        "metadata": "Meta veri",
    }.get(kind, str(kind))


def _short(text: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + "…"


def _template_explanation(report: dict) -> str:
    summary = report.get("summary") or {}
    page_count = report.get("page_count") or {}
    total = summary.get("total_changes", len(report.get("changes") or []))
    by_category = summary.get("by_category") or {}

    lines = []
    if not total:
        lines.append("İki belge arasında metin veya meta veri farkı bulunmadı.")
    else:
        lines.append(f"İki belge arasında toplam {total} fark bulundu.")
        lines.append(
            f"Bunlardan {by_category.get(CATEGORY_RISKY, 0)} tanesi riskli, "
            f"{by_category.get(CATEGORY_MEANING, 0)} tanesi anlam, "
            f"{by_category.get(CATEGORY_FORMAT, 0)} tanesi biçim değişikliği."
        )

    delta = page_count.get("delta", 0)
    if delta:
        direction = "arttı" if delta > 0 else "azaldı"
        lines.append(
            f"Sayfa sayısı {page_count.get('a', 0)} → {page_count.get('b', 0)} "
            f"({abs(delta)} sayfa {direction})."
        )

    risky = [change for change in report.get("changes") or []
             if change.get("category") == CATEGORY_RISKY]
    if risky:
        lines.append("Riskli değişiklikler:")
        for change in risky[:10]:
            detail = _short(change.get("b_text") or change.get("a_text"), 120)
            lines.append(f"- {_page_ref_text(change)}: {detail}")
        if len(risky) > 10:
            lines.append(f"- … {len(risky) - 10} riskli fark daha var.")
    elif total:
        lines.append("Riskli bir değişiklik görülmedi.")

    return "\n".join(lines)


def _llm_prompt(report: dict) -> str:
    changes = report.get("changes") or []
    lines = [
        "Sen bir sözleşme ve rapor analistisin. Aşağıdaki iki PDF sürümü "
        "arasındaki farkları Türkçe, kısa ve anlaşılır şekilde açıkla. "
        "Riskli değişiklikleri özellikle belirt; sayfa numaralarını kullan. "
        "Yeni bilgi uydurma.",
        "",
        f"Eski belge: {report.get('a', {}).get('path', '')}",
        f"Yeni belge: {report.get('b', {}).get('path', '')}",
        f"Sayfa sayısı: {report.get('page_count', {}).get('a', 0)} → "
        f"{report.get('page_count', {}).get('b', 0)}",
        "",
        "Farklar:",
    ]
    for change in changes[:40]:
        lines.append(
            f"- {_page_ref_text(change)} | {change.get('category')} | "
            f"{_type_text(change.get('type', ''))} | "
            f"Eski: {_short(change.get('a_text'), 220)} | "
            f"Yeni: {_short(change.get('b_text'), 220)}"
        )
    if len(changes) > 40:
        lines.append(f"- … {len(changes) - 40} fark daha var.")
    return "\n".join(lines)


def explain_changes(report: dict, *, model_path: str | None = None,
                    max_tokens: int = 512) -> str:
    """Explain a report in Turkish, using the local LLM when available.

    The LLM is optional: without a model (or without llama-cpp-python) a
    deterministic Turkish template is returned instead.
    """
    prompt = _llm_prompt(report)
    try:
        from src.ai import local_llm
        kwargs = {"max_tokens": max_tokens, "temperature": 0.1}
        if model_path:
            kwargs["model_path"] = model_path
        text = local_llm.generate(prompt, **kwargs)
        if text and str(text).strip():
            return str(text).strip()
    except Exception as exc:
        logger.debug("Local LLM explanation unavailable: %s", exc)
    return _template_explanation(report)


# ── Report PDF ──────────────────────────────────────────────────────────────

PAGE_WIDTH, PAGE_HEIGHT = 595, 842   # A4 at 72 dpi
MARGIN = 46
_REPORT_FONT_NAME = "PDFAuraTR"
_METADATA_LABELS = {
    "title": "Başlık",
    "author": "Yazar",
    "subject": "Konu",
    "creator": "Oluşturan",
    "producer": "Üretici",
}
_ASCII_TRANSLATION = str.maketrans({
    "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ı": "i", "İ": "I",
    "ö": "o", "Ö": "O", "ş": "s", "Ş": "S", "ü": "u", "Ü": "U",
    "•": "*", "→": "->", "“": '"', "”": '"', "’": "'", "…": "...",
})


def _find_turkish_font() -> str:
    """A system TTF that can render Turkish characters, or ""."""
    windows = os.environ.get("WINDIR") or os.environ.get("SystemRoot") or r"C:\Windows"
    candidates = [
        os.path.join(windows, "Fonts", name)
        for name in ("segoeui.ttf", "arial.ttf", "calibri.ttf",
                     "tahoma.ttf", "verdana.ttf")
    ]
    candidates.extend([
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        str(Path(__file__).resolve().parents[2] / "assets" / "DejaVuSans.ttf"),
    ])
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return ""


class _ReportWriter:
    """Minimal top-down text writer for the comparison report."""

    def __init__(self, document):
        import fitz
        self._fitz = fitz
        self.document = document
        self.font_path = _find_turkish_font()
        if self.font_path:
            self.font_name = _REPORT_FONT_NAME
            self._font = fitz.Font(fontfile=self.font_path)
            self._ascii = False
        else:
            self.font_name = "helv"
            self._font = None
            self._ascii = True
        self.page = None
        self.y = 0.0
        self._new_page()

    def _new_page(self):
        self.page = self.document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        if self.font_path:
            self.page.insert_font(fontname=self.font_name,
                                  fontfile=self.font_path)
        self.y = MARGIN

    def _measure(self, text: str, size: float) -> float:
        if self._font is not None:
            return float(self._font.text_length(text, fontsize=size))
        return float(self._fitz.get_text_length(text, fontname=self.font_name,
                                                fontsize=size))

    def _wrap(self, text: str, width: float, size: float) -> list[str]:
        lines = []
        for raw_line in str(text).splitlines() or [""]:
            words = raw_line.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                candidate = f"{current} {word}"
                if self._measure(candidate, size) <= width:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines

    def _ensure(self, height: float):
        if self.y + height > PAGE_HEIGHT - MARGIN:
            self._new_page()

    def line(self, text: str, *, size: float = 10,
             color: tuple[float, float, float] = (0.1, 0.1, 0.1),
             indent: float = 0, space_after: float = 2) -> None:
        if self._ascii:
            text = str(text).translate(_ASCII_TRANSLATION)
        width = PAGE_WIDTH - 2 * MARGIN - indent
        line_height = size * 1.35
        for wrapped in self._wrap(text, width, size):
            self._ensure(line_height)
            if wrapped:
                self.page.insert_text(
                    (MARGIN + indent, self.y + size),
                    wrapped, fontname=self.font_name, fontsize=size,
                    color=color,
                )
            self.y += line_height
        self.y += space_after

    def heading(self, text: str, size: float = 15,
                color: tuple[float, float, float] = (0.12, 0.16, 0.36)) -> None:
        self._ensure(size * 2)
        self.line(text, size=size, color=color, space_after=6)

    def spacer(self, height: float = 6) -> None:
        self._ensure(height)
        self.y += height


def _change_color(change: dict) -> tuple[float, float, float]:
    if change.get("category") == CATEGORY_RISKY:
        return (0.72, 0.05, 0.05)
    if change.get("category") == CATEGORY_MEANING:
        return (0.10, 0.22, 0.52)
    return (0.38, 0.38, 0.38)


def export_report_pdf(report: dict, path) -> str:
    """Write *report* as a Turkish, printable PDF and return its path."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF (fitz) gerekli ancak yüklü değil.") from exc

    from src.core.output_paths import atomic_output

    target = str(path)
    document = fitz.open()
    try:
        writer = _ReportWriter(document)
        writer.heading("PDF Karşılaştırma Raporu", 19)
        writer.line(f"Eski belge: {report.get('a', {}).get('path', '')}", size=9.5)
        writer.line(f"Yeni belge: {report.get('b', {}).get('path', '')}", size=9.5)

        page_count = report.get("page_count") or {}
        delta = int(page_count.get("delta", 0) or 0)
        writer.line(
            f"Sayfa sayısı: {page_count.get('a', 0)} → "
            f"{page_count.get('b', 0)} ({delta:+d})", size=9.5,
        )

        summary = report.get("summary") or {}
        by_category = summary.get("by_category") or {}
        writer.line(
            f"Toplam fark: {summary.get('total_changes', 0)}  •  "
            f"riskli: {by_category.get(CATEGORY_RISKY, 0)}  •  "
            f"anlam: {by_category.get(CATEGORY_MEANING, 0)}  •  "
            f"biçim: {by_category.get(CATEGORY_FORMAT, 0)}", size=9.5,
        )
        writer.spacer()

        writer.heading("Meta Veri Farkları", 13)
        metadata_changes = report.get("metadata_changes") or []
        if metadata_changes:
            for change in metadata_changes:
                label = _METADATA_LABELS.get(change.get("field"),
                                             change.get("field", ""))
                writer.line(
                    f"{label}: “{_short(change.get('a_text'), 150)}” → "
                    f"“{_short(change.get('b_text'), 150)}” "
                    f"[{change.get('category')}]", size=9.5,
                    color=_change_color(change), indent=8,
                )
        else:
            writer.line("Meta veri farkı yok.", size=9.5, indent=8)

        writer.spacer()
        writer.heading("Sayfa Sayısı Değişimi", 13)
        added_pages = summary.get("pages_added") or []
        removed_pages = summary.get("pages_removed") or []
        writer.line(
            "Eklenen sayfalar: " +
            (", ".join(str(page) for page in added_pages) if added_pages else "yok"),
            size=9.5, indent=8,
        )
        writer.line(
            "Kaldırılan sayfalar: " +
            (", ".join(str(page) for page in removed_pages) if removed_pages else "yok"),
            size=9.5, indent=8,
        )

        writer.spacer()
        writer.heading("Farklar", 13)
        changes = report.get("changes") or []
        if not changes:
            writer.line("Metin veya meta veri farkı bulunmadı.", size=10, indent=8)
        for index, change in enumerate(changes, 1):
            writer.line(
                f"{index}. {_page_ref_text(change)}  •  "
                f"{_type_text(change.get('type', ''))}  •  "
                f"{change.get('category', '')}",
                size=10.5, color=_change_color(change),
            )
            if change.get("a_text"):
                writer.line(f"Eski: {_short(change['a_text'], 1200)}",
                            size=9, indent=14)
            if change.get("b_text"):
                writer.line(f"Yeni: {_short(change['b_text'], 1200)}",
                            size=9, indent=14)
            if change.get("reason"):
                writer.line(f"Neden: {change['reason']}", size=8.5, indent=14,
                            color=(0.4, 0.4, 0.4))
            writer.spacer(4)

        with atomic_output(target) as temp_path:
            document.save(temp_path)
    finally:
        document.close()
    return target
