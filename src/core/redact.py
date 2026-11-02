"""Find and permanently remove sensitive data from PDFs.

Detection runs locally: regular expressions with checksum validation for
Turkish IDs, IBANs, phone numbers, e-mail addresses, tax numbers, credit
cards and postal addresses, plus Microsoft Presidio when it happens to be
installed. Redaction is done with PyMuPDF's :meth:`Page.add_redact_annot` and
:meth:`Page.apply_redactions`, which removes the text from the content
stream -- drawing a black box over it is not enough, because the text would
still be searchable and copyable.

Scanned pages have no text layer. :func:`find_sensitive_ocr` renders them and
uses Tesseract's word boxes instead, and
:func:`redact_image_regions` removes the underlying image pixels as well as
drawing the visible boxes.

Presidio and Tesseract are optional; without them the regex rules and the
digital-PDF path keep working.
"""
import re
from dataclasses import dataclass

from src.core.lang_manager import _
from src.core.output_paths import atomic_output

# Match type names used in the public result dictionaries.
TC_KIMLIK = "tc_kimlik"
IBAN = "iban"
TELEFON = "telefon"
EPOSTA = "eposta"
VERGI_NO = "vergi_no"
KREDI_KARTI = "kredi_karti"
ADRES = "adres"

# Lower numbers win when two rules find the same span (e.g. the digits inside
# an IBAN can look like a tax number).
_PRIORITY = {
    IBAN: 0,
    TC_KIMLIK: 1,
    VERGI_NO: 2,
    EPOSTA: 3,
    TELEFON: 4,
    KREDI_KARTI: 5,
    ADRES: 6,
}
_PRESIDIO_PRIORITY = 9

# Rendering scale for the OCR finder; 3x (~216 dpi) is enough for printed
# text and keeps a multi-page scan quick.
OCR_RENDER_SCALE = 3.0
OCR_MIN_CONFIDENCE = 30


# ── Checksums and validators ─────────────────────────────────────────────

def _digits(value):
    return re.sub(r"\D", "", value or "")


def is_valid_tc_kimlik(value):
    """True for an 11-digit Turkish national ID with a valid checksum."""
    digits = _digits(value)
    if len(digits) != 11 or digits[0] == "0" or len(set(digits[:10])) == 1:
        return False
    numbers = [int(ch) for ch in digits]
    odd = sum(numbers[0:9:2])
    even = sum(numbers[1:8:2])
    if numbers[9] != (odd * 7 - even) % 10:
        return False
    return numbers[10] == sum(numbers[:10]) % 10


def is_valid_iban(value):
    """True for a Turkish IBAN (TR + 24 digits) that passes the mod-97 test."""
    compact = re.sub(r"[^0-9A-Za-z]", "", value or "").upper()
    if len(compact) != 26 or not compact.startswith("TR"):
        return False
    rearranged = compact[4:] + compact[:4]
    try:
        numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    except ValueError:
        return False
    return int(numeric) % 97 == 1


def normalize_phone(value):
    """Return a Turkish phone number as ``0XXXXXXXXXX``, or None.

    Accepts ``+90``, ``90`` and ``0`` prefixes, spaces, dots, dashes and
    parentheses around the area code. Mobile numbers may be written without
    the leading zero.
    """
    digits = _digits(value)
    if len(digits) == 12 and digits.startswith("90"):
        digits = "0" + digits[2:]
    elif len(digits) == 10:
        digits = "0" + digits
    if len(digits) != 11 or digits[0] != "0":
        return None
    # 2xx/3xx/4xx are landline area codes; 5xx is mobile.
    if digits[1] not in "2345":
        return None
    return digits


def is_valid_tax_number(value):
    """True for a 10-digit Turkish tax number with a valid check digit."""
    digits = _digits(value)
    if len(digits) != 10:
        return False
    total = 0
    for index, char in enumerate(digits[:9]):
        tmp = (int(char) + 9 - index) % 10
        if tmp:
            tmp = (tmp * (2 ** (9 - index))) % 9
            if tmp == 0:
                tmp = 9
        total += tmp
    return (10 - total % 10) % 10 == int(digits[9])


def is_valid_credit_card(value):
    """True for a 13-19 digit card number that passes the Luhn test."""
    digits = _digits(value)
    if not 13 <= len(digits) <= 19 or digits[0] == "0":
        return False
    if len(set(digits)) == 1:
        return False
    total = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        number = int(char)
        if index % 2 == parity:
            number *= 2
            if number > 9:
                number -= 9
        total += number
    return total % 10 == 0


def _is_valid_email(value):
    local, _, domain = (value or "").partition("@")
    if not local or not domain or "." not in domain:
        return False
    if domain.startswith((".", "-")) or domain.endswith((".", "-")):
        return False
    return ".." not in value


# ── Regex rules ──────────────────────────────────────────────────────────

# A token must not be part of a longer word/number: the digits of an IBAN,
# for example, must not also be reported as a tax number.
_LEFT = r"(?<![0-9A-Za-z])"
_RIGHT = r"(?![0-9A-Za-z])"

_RULES = (
    (IBAN, (
        re.compile(_LEFT + r"TR[ \t]*\d{2}(?:[ \t]*\d{4}){5}[ \t]*\d{2}" + _RIGHT,
                   re.IGNORECASE),
    ), is_valid_iban),
    (TC_KIMLIK, (
        re.compile(_LEFT + r"\d{11}" + _RIGHT),
        re.compile(_LEFT + r"\d{3}[ \t]+\d{3}[ \t]+\d{3}[ \t]+\d{2}" + _RIGHT),
    ), is_valid_tc_kimlik),
    (VERGI_NO, (
        re.compile(_LEFT + r"\d{10}" + _RIGHT),
    ), is_valid_tax_number),
    (EPOSTA, (
        re.compile(r"(?<![0-9A-Za-z._%+-])[0-9A-Za-z._%+-]+@"
                   r"[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)+"),
    ), _is_valid_email),
    (TELEFON, (
        re.compile(_LEFT + r"(?:\+?90[ \t.-]?|0[ \t.-]?)"
                   r"\(?[2-5]\d{2}\)?[ \t.-]?\d{3}[ \t.-]?\d{2}[ \t.-]?\d{2}" + _RIGHT),
        re.compile(_LEFT + r"\(?5\d{2}\)?[ \t.-]?\d{3}[ \t.-]?\d{2}[ \t.-]?\d{2}" + _RIGHT),
    ), normalize_phone),
    (KREDI_KARTI, (
        re.compile(_LEFT + r"(?:\d[ \t.-]?){12,18}\d" + _RIGHT),
    ), is_valid_credit_card),
)

# ── Turkish address rules ────────────────────────────────────────────────
#
# An address is a whole line rather than one fixed token, so the rule checks
# for the markers Turkish addresses use and then marks the line. Lower-case
# folding also maps the dotted capital İ to a plain i.

_ADDRESS_STREET = re.compile(
    r"(?<![0-9a-zçğıöşü])(?:mah(?:alle(?:si)?)?|cad(?:de(?:si)?)?|"
    r"sok(?:ak|ağı|agi)?|bulvar(?:ı|i)?|mevki(?:i)?|apartman(?:ı|i)?|"
    r"site(?:si)?|köy(?:ü|u)?)\b")
_ADDRESS_UNIT = re.compile(
    r"(?<![0-9a-zçğıöşü])(?:(?:no|daire|kat|blok)\s*[:.]?\s*\d+[a-z]?|"
    r"d\s*[:.]\s*\d+)")
_ADDRESS_REGION = re.compile(
    r"(?<![0-9a-zçğıöşü])(?:il[çc]e(?:si)?\s*[:.,-]?\s*|il\s*[:.,-]\s*)"
    r"[a-zçğıöşü]{3,}")
_ADDRESS_LABEL = re.compile(r"(?<![0-9a-zçğıöşü])adres(?:i)?\s*[:.]")
_ADDRESS_POSTAL = re.compile(r"(?<!\d)\d{5}(?!\d)")


def _fold_turkish(text):
    """Lower-case *text* for keyword matching, including the dotted İ."""
    return (text or "").casefold().replace("\u0307", "")


def _looks_like_address(text):
    """True when *text* looks like a Turkish postal address."""
    folded = _fold_turkish(text).strip()
    if len(folded) < 8:
        return False

    streets = _ADDRESS_STREET.findall(folded)
    units = _ADDRESS_UNIT.findall(folded)
    region = _ADDRESS_REGION.search(folded)
    label = _ADDRESS_LABEL.search(folded)
    has_digit = any(char.isdigit() for char in folded)
    words = len(folded.split())

    if len(streets) >= 2:
        return True
    if streets and (has_digit or units or region):
        return True
    if len(units) >= 2:
        return True
    if region:
        return True
    if label and (has_digit or words >= 3):
        return True
    if streets and _ADDRESS_POSTAL.search(folded):
        return True
    return False


def _address_candidate(line):
    """A whole-line ADRES candidate for *line*, or None."""
    if not _looks_like_address(line.text):
        return None
    rect = _span_rect(line, 0, len(line.text))
    if rect is None:
        return None
    return _Candidate(ADRES, line.text.strip(), rect, 0, len(line.text),
                      _PRIORITY[ADRES])


_PRESIDIO_TYPES = {
    "EMAIL_ADDRESS": EPOSTA,
    "PHONE_NUMBER": TELEFON,
    "CREDIT_CARD": KREDI_KARTI,
    "IBAN_CODE": IBAN,
    "TR_NATIONAL_ID": TC_KIMLIK,
    "TR_TAX_ID": VERGI_NO,
}

_analyzer = None
_analyzer_loaded = False


@dataclass
class _Line:
    """One extracted line: its text and each word's char and PDF bounds."""
    text: str
    words: list


@dataclass
class _Candidate:
    kind: str
    text: str
    rect: tuple
    start: int
    end: int
    priority: int


# ── Optional dependencies ────────────────────────────────────────────────

def _require_fitz():
    try:
        import fitz
    except ImportError:
        raise ImportError(_("err_missing_dependency") + " PyMuPDF")
    return fitz


def _presidio_analyzer():
    """Return a cached AnalyzerEngine, or None when Presidio is absent/broken."""
    global _analyzer, _analyzer_loaded
    if _analyzer_loaded:
        return _analyzer
    _analyzer_loaded = True
    try:
        from presidio_analyzer import AnalyzerEngine
    except ImportError:
        return None
    try:
        _analyzer = AnalyzerEngine()
    except Exception:
        # A missing spaCy model must not break the regex rules.
        _analyzer = None
    return _analyzer


# ── Text/geometry helpers ────────────────────────────────────────────────

def _page_lines(page):
    """Group PyMuPDF's words into lines, remembering char and PDF positions."""
    grouped = {}

    for x0, y0, x1, y1, word, block_no, line_no, _word_no in page.get_text("words", sort=True):
        key = (block_no, line_no)
        line = grouped.get(key)
        if line is None:
            line = {"text": "", "words": []}
            grouped[key] = line

        if line["text"]:
            line["text"] += " "
        start = len(line["text"])
        line["text"] += word
        line["words"].append((start, start + len(word), (x0, y0, x1, y1)))

    return [_Line(item["text"], item["words"]) for item in grouped.values()]


def _span_rect(line, start, end):
    """Union of the word boxes touched by ``line.text[start:end]``."""
    boxes = [box for word_start, word_end, box in line.words
             if word_start < end and word_end > start]
    if not boxes:
        return None
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _regex_candidates(line):
    found = []
    for kind, patterns, validator in _RULES:
        for pattern in patterns:
            for match in pattern.finditer(line.text):
                text = match.group(0)
                if not validator(text):
                    continue
                rect = _span_rect(line, match.start(), match.end())
                if rect is None:
                    continue
                found.append(_Candidate(kind, text, rect, match.start(), match.end(),
                                        _PRIORITY[kind]))

    address = _address_candidate(line)
    if address is not None:
        found.append(address)
    return found


def _presidio_candidates(line, analyzer):
    if analyzer is None or len(line.text.strip()) < 3:
        return []
    try:
        results = analyzer.analyze(text=line.text, language="en", score_threshold=0.4)
    except Exception:
        return []

    found = []
    for result in results:
        start, end = int(result.start), int(result.end)
        if start < 0 or end > len(line.text) or start >= end:
            continue
        text = line.text[start:end]
        if not text.strip():
            continue
        rect = _span_rect(line, start, end)
        if rect is None:
            continue
        entity = str(result.entity_type).upper()
        kind = _PRESIDIO_TYPES.get(entity, "presidio_" + entity.lower())
        found.append(_Candidate(kind, text, rect, start, end, _PRESIDIO_PRIORITY))
    return found


def _without_overlaps(candidates):
    """Drop lower-priority candidates that overlap a stronger match."""
    ordered = sorted(candidates, key=lambda c: (c.priority, c.start, -(c.end - c.start)))
    kept = []
    for candidate in ordered:
        if any(candidate.start < other.end and candidate.end > other.start
               for other in kept):
            continue
        kept.append(candidate)
    return kept


# ── OCR for scanned pages ────────────────────────────────────────────────

_ocr_state = None


def _tesseract_ready():
    """True when pytesseract and a Tesseract binary are both usable."""
    global _ocr_state
    if _ocr_state is None:
        try:
            from src.core.ocr import check_tesseract_availability
            _ocr_state = bool(check_tesseract_availability())
        except Exception:
            _ocr_state = False
    return _ocr_state


def _ocr_language():
    """Best installed Tesseract language string, or "eng" as a last resort."""
    try:
        from src.core.ocr import resolve_ocr_language
        return resolve_ocr_language()
    except Exception:
        return "eng"


def _page_has_text(page):
    """True when the page already has selectable text (so OCR is skipped)."""
    try:
        return bool(page.get_text("text").strip())
    except Exception:
        return False


def _render_page_for_ocr(page):
    """Return ``(PIL image, scale_x, scale_y)`` for a page, or a None image."""
    try:
        import fitz
        from PIL import Image
    except Exception:
        return None, 1.0, 1.0

    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(OCR_RENDER_SCALE, OCR_RENDER_SCALE),
                              colorspace=fitz.csGRAY, alpha=False)
    except Exception:
        return None, 1.0, 1.0

    try:
        mode = "L" if pix.n == 1 else "RGB"
        image = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
    except Exception:
        return None, 1.0, 1.0

    width = page.rect.width or 1.0
    height = page.rect.height or 1.0
    return image, pix.width / width, pix.height / height


def _words_to_lines(data, scale_x, scale_y, min_confidence=OCR_MIN_CONFIDENCE):
    """Group Tesseract's ``image_to_data`` words into :class:`_Line` objects.

    Word boxes arrive in rendered-image pixels; they are divided by the render
    scale so the rectangles use PDF points, the same as the digital path.
    """
    texts = data.get("text", []) or []
    lines = {}
    for index, raw_text in enumerate(texts):
        text = (raw_text or "").strip()
        if not text:
            continue
        try:
            confidence = float(data.get("conf", [100] * len(texts))[index])
        except (TypeError, ValueError, IndexError):
            confidence = 100.0
        if confidence < min_confidence:
            continue

        key = (data.get("block_num", [0] * len(texts))[index],
               data.get("par_num", [0] * len(texts))[index],
               data.get("line_num", [0] * len(texts))[index])
        line = lines.get(key)
        if line is None:
            line = {"text": "", "words": []}
            lines[key] = line

        if line["text"]:
            line["text"] += " "
        start = len(line["text"])
        line["text"] += text
        left = float(data.get("left", [0] * len(texts))[index])
        top = float(data.get("top", [0] * len(texts))[index])
        width = float(data.get("width", [0] * len(texts))[index])
        height = float(data.get("height", [0] * len(texts))[index])
        box = (left / scale_x, top / scale_y,
               (left + width) / scale_x, (top + height) / scale_y)
        line["words"].append((start, start + len(text), box))

    return [_Line(item["text"], item["words"]) for item in lines.values()]


def _ocr_lines_for_page(page, language):
    """OCR one page and return its word boxes grouped into lines."""
    image, scale_x, scale_y = _render_page_for_ocr(page)
    if image is None:
        return []
    try:
        import pytesseract
        kwargs = {}
        if language:
            kwargs["lang"] = language
        data = pytesseract.image_to_data(
            image, output_type=pytesseract.Output.DICT, **kwargs)
    except Exception:
        return []
    return _words_to_lines(data, scale_x, scale_y)


# ── Public API ───────────────────────────────────────────────────────────

def find_sensitive(pdf_path, use_presidio=True):
    """Find sensitive values in *pdf_path*.

    Returns a list of dictionaries with ``type``, ``text``, ``page`` (1-based)
    and ``rect`` (``x0, y0, x1, y1`` in PDF points). An empty list is returned
    for documents without an extractable text layer (e.g. scans without OCR).
    """
    fitz = _require_fitz()
    analyzer = _presidio_analyzer() if use_presidio else None

    document = fitz.open(pdf_path)
    try:
        if getattr(document, "needs_pass", False):
            from src.core.errors import PdfPasswordError
            raise PdfPasswordError(_("err_pdf_password_protected"))
        matches = []
        for page_index, page in enumerate(document):
            for line in _page_lines(page):
                # Offsets are line-local, so resolve overlaps per line.
                candidates = _regex_candidates(line)
                candidates.extend(_presidio_candidates(line, analyzer))
                for candidate in _without_overlaps(candidates):
                    matches.append({
                        "type": candidate.kind,
                        "text": candidate.text,
                        "page": page_index + 1,
                        "rect": candidate.rect,
                    })
    finally:
        if not getattr(document, "is_closed", False):
            document.close()

    matches.sort(key=lambda item: (item["page"], item["rect"][1], item["rect"][0]))
    return matches


def find_sensitive_ocr(pdf_path, use_presidio=True):
    """Find sensitive values in scanned pages through OCR.

    Pages that already have a text layer are skipped -- :func:`find_sensitive`
    handles them and running both would report every value twice. Each page is
    rendered, Tesseract's word boxes become page coordinates, and the same
    regex/address/Presidio rules run on those lines. Returns the same list of
    dictionaries as :func:`find_sensitive`, or an empty list when Tesseract is
    not installed.
    """
    if not _tesseract_ready():
        return []

    fitz = _require_fitz()
    analyzer = _presidio_analyzer() if use_presidio else None
    language = _ocr_language()

    document = fitz.open(pdf_path)
    try:
        if getattr(document, "needs_pass", False):
            from src.core.errors import PdfPasswordError
            raise PdfPasswordError(_("err_pdf_password_protected"))
        matches = []
        for page_index, page in enumerate(document):
            if _page_has_text(page):
                continue
            for line in _ocr_lines_for_page(page, language):
                candidates = _regex_candidates(line)
                candidates.extend(_presidio_candidates(line, analyzer))
                for candidate in _without_overlaps(candidates):
                    matches.append({
                        "type": candidate.kind,
                        "text": candidate.text,
                        "page": page_index + 1,
                        "rect": candidate.rect,
                    })
    finally:
        if not getattr(document, "is_closed", False):
            document.close()

    matches.sort(key=lambda item: (item["page"], item["rect"][1], item["rect"][0]))
    return matches


def _match_value(match, key):
    if isinstance(match, dict):
        return match[key]
    if isinstance(match, (tuple, list)):
        return match[("type", "text", "page", "rect").index(key)]
    return getattr(match, key)


def _match_rect(match):
    rect = _match_value(match, "rect")
    if hasattr(rect, "x0"):
        return (rect.x0, rect.y0, rect.x1, rect.y1)
    return tuple(rect)


def _clamp_rect(rect, page_rect):
    x0, y0, x1, y1 = (float(value) for value in rect)
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    x0 = max(x0, page_rect.x0)
    y0 = max(y0, page_rect.y0)
    x1 = min(x1, page_rect.x1)
    y1 = min(y1, page_rect.y1)
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def apply_redactions(pdf_path, matches, output_path, fill=(0, 0, 0), ctx=None):
    """Permanently redact *matches* from *pdf_path* into *output_path*.

    Every match's rectangle gets a real PyMuPDF redaction annotation and the
    page is then cleaned with ``apply_redactions``: the glyphs are removed from
    the content stream, so the text can no longer be searched or copied.
    Image pixels under the rectangle are removed as well, which also covers
    rects supplied from an OCR layer. *fill* is the box colour; pass None for
    no visible box.
    """
    fitz = _require_fitz()
    document = fitz.open(pdf_path)
    closed = False
    try:
        by_page = {}
        for match in matches:
            page_number = int(_match_value(match, "page"))
            if not 1 <= page_number <= document.page_count:
                raise ValueError(_("err_invalid_page").format(page=page_number))
            rect = _clamp_rect(_match_rect(match), document[page_number - 1].rect)
            if rect is not None:
                by_page.setdefault(page_number, []).append(rect)

        total = sum(len(rects) for rects in by_page.values()) or 1
        done = 0
        for page_number in sorted(by_page):
            if ctx:
                ctx.check_cancelled()
            page = document[page_number - 1]
            for rect in by_page[page_number]:
                page.add_redact_annot(fitz.Rect(rect), fill=fill)
            if by_page[page_number]:
                page.apply_redactions()
            done += len(by_page[page_number])
            if ctx:
                ctx.report_progress(done, total, _("progress_page_of").format(
                    current=page_number, total=document.page_count))

        with atomic_output(output_path) as temp_path:
            document.save(temp_path, garbage=3, deflate=True)
            # Windows cannot replace the input while PyMuPDF still has it open.
            document.close()
            closed = True

        if ctx:
            ctx.report_progress(total, total, _("progress_finished"))
    finally:
        if not getattr(document, "is_closed", False):
            document.close()


def _region_page_rect(region):
    """Return ``(page, rect)`` from the region shapes we accept."""
    if isinstance(region, dict):
        page = region.get("page", region.get("page_number"))
        rect = region.get("rect", region.get("bbox"))
        if rect is None and all(key in region for key in ("x0", "y0", "x1", "y1")):
            rect = (region["x0"], region["y0"], region["x1"], region["y1"])
        if page is None or rect is None:
            raise ValueError("Redaction region needs a page and a rect.")
        return int(page), _match_rect({"rect": rect})

    if isinstance(region, (tuple, list)):
        if len(region) == 2 and isinstance(region[1], (tuple, list)) \
                and len(region[1]) == 4:
            return int(region[0]), _match_rect({"rect": region[1]})
        if len(region) == 5:
            return int(region[0]), _match_rect({"rect": region[1:]})

    raise ValueError("Redaction region needs a page and a rect.")


def _apply_image_redactions(page, fitz):
    """Apply pending redactions, removing pixels from scanned page images.

    Older PyMuPDF releases do not accept the ``images`` keyword; there the
    default (which also removes image content) is used.
    """
    pixels = getattr(fitz, "PDF_REDACT_IMAGE_PIXELS", None)
    try:
        if pixels is None:
            page.apply_redactions()
        else:
            page.apply_redactions(images=pixels)
    except TypeError:
        page.apply_redactions()


def redact_image_regions(pdf_path, regions, output_path, fill=(0, 0, 0), ctx=None):
    """Redact arbitrary page areas, including the image pixels underneath.

    *regions* is an iterable of ``{"page": 1, "rect": (x0, y0, x1, y1)}``
    dictionaries (the shape returned by :func:`find_sensitive` and
    :func:`find_sensitive_ocr`), ``(page, rect)`` pairs or
    ``(page, x0, y0, x1, y1)`` tuples. Every rectangle gets a filled box and
    ``apply_redactions(images=PDF_REDACT_IMAGE_PIXELS)`` removes the scanned
    image content below it, so the area cannot be recovered by extracting or
    re-rendering the page. Returns *output_path*.
    """
    fitz = _require_fitz()
    document = fitz.open(pdf_path)
    closed = False
    try:
        by_page = {}
        for region in regions:
            page_number, rect = _region_page_rect(region)
            if not 1 <= page_number <= document.page_count:
                raise ValueError(_("err_invalid_page").format(page=page_number))
            clamped = _clamp_rect(rect, document[page_number - 1].rect)
            if clamped is not None:
                by_page.setdefault(page_number, []).append(clamped)

        total = sum(len(rects) for rects in by_page.values()) or 1
        done = 0
        for page_number in sorted(by_page):
            if ctx:
                ctx.check_cancelled()
            page = document[page_number - 1]
            for rect in by_page[page_number]:
                page.add_redact_annot(fitz.Rect(rect), fill=fill)
            _apply_image_redactions(page, fitz)
            done += len(by_page[page_number])
            if ctx:
                ctx.report_progress(done, total, _("progress_page_of").format(
                    current=page_number, total=document.page_count))

        with atomic_output(output_path) as temp_path:
            document.save(temp_path, garbage=3, deflate=True)
            # Windows cannot replace the input while PyMuPDF still has it open.
            document.close()
            closed = True

        if ctx:
            ctx.report_progress(total, total, _("progress_finished"))
    finally:
        if not getattr(document, "is_closed", False):
            document.close()

    return output_path
