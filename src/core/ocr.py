import os

from src.core.lang_manager import _


def __getattr__(name):
    # pytesseract (and the numpy it pulls in) loads on first use, not when
    # the app starts; ocr.pytesseract still works for callers and tests.
    if name == "pytesseract":
        import pytesseract
        return pytesseract
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# Preferred OCR languages, best first. Only ones actually installed are used:
# the language was hardcoded to "tur", so OCR failed outright without the
# Turkish pack and read English documents with a Turkish model.
PREFERRED_LANGUAGES = ("tur", "eng")

# Standard install locations to fall back on when tesseract is not on PATH.
_STANDARD_PATHS = (
    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                 "Tesseract-OCR", "tesseract.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 "Tesseract-OCR", "tesseract.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs",
                 "Tesseract-OCR", "tesseract.exe"),
)


def check_tesseract_availability():
    """Returns True if Tesseract can be called, else False."""
    import pytesseract
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        for candidate in _STANDARD_PATHS:
            if candidate and os.path.exists(candidate):
                pytesseract.pytesseract.tesseract_cmd = candidate
                try:
                    pytesseract.get_tesseract_version()
                    return True
                except Exception:
                    continue
        return False


def installed_languages():
    """Language codes Tesseract actually has data for."""
    import pytesseract
    try:
        return list(pytesseract.get_languages(config=""))
    except Exception:
        return []


def resolve_ocr_language(requested=None):
    """Pick an OCR language string from what is installed.

    *requested* wins if its packs are present; otherwise the preferred
    languages that are installed are combined ("tur+eng"), and failing that
    any single installed language is used.
    """
    available = installed_languages()
    if not available:
        # get_languages can fail on old builds; trust the caller instead of
        # refusing to run.
        return requested or PREFERRED_LANGUAGES[0]

    if requested:
        wanted = [code for code in requested.split("+") if code in available]
        if wanted:
            return "+".join(wanted)

    preferred = [code for code in PREFERRED_LANGUAGES if code in available]
    if preferred:
        return "+".join(preferred)

    usable = [code for code in available if code != "osd"]
    if usable:
        return usable[0]

    raise RuntimeError(_("err_ocr_no_language"))


def perform_ocr_to_text(input_pdf, output_txt, lang=None, ctx=None):
    """OCR every page of a PDF and save the text.

    Reports per-page progress and honours cancellation: the Cancel button
    used to sit there while the job ran on to a "success" message.
    """
    import fitz  # PyMuPDF
    import pytesseract
    from PIL import Image
    if not check_tesseract_availability():
        raise EnvironmentError(_("err_tesseract_missing"))

    language = resolve_ocr_language(lang)

    doc = fitz.open(input_pdf)
    full_text = []
    try:
        total = doc.page_count
        for page_num in range(total):
            if ctx:
                ctx.check_cancelled()
                ctx.report_progress(page_num, total, _("ocr_page_progress").format(
                    current=page_num + 1, total=total))

            page = doc.load_page(page_num)
            # Render high-res image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))

            mode = "RGBA" if pix.alpha else "RGB"
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)

            try:
                text = pytesseract.image_to_string(img, lang=language)
            except pytesseract.TesseractError as exc:
                raise RuntimeError(_("err_ocr_failed").format(error=exc))
            full_text.append(f"--- Sayfa {page_num + 1} ---\n{text}\n")
            del img, pix   # a rendered page is large; do not hold them all
    finally:
        doc.close()

    with open(output_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(full_text))

    if ctx:
        ctx.report_progress(len(full_text), len(full_text), _("str_done"))

    return len(full_text)
