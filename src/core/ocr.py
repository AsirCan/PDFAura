import os
import shutil

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

    from src.core.output_paths import atomic_output
    with atomic_output(output_txt) as temp_path, open(temp_path, "w", encoding="utf-8") as f:
        f.write("\n".join(full_text))

    if ctx:
        ctx.report_progress(len(full_text), len(full_text), _("str_done"))

    return len(full_text)


def _tessdata_dir():
    """Tesseract's tessdata folder, or None when it cannot be located.

    PyMuPDF's OCR needs the folder itself, not just tesseract.exe, and its
    own lookup only checks PATH. Here tesseract.exe may have been found in
    one of the standard install folders, so use that folder's tessdata.
    """
    env = os.environ.get("TESSDATA_PREFIX")
    if env and os.path.isdir(env):
        return env

    candidates = []
    try:
        import pytesseract
        candidates.append(getattr(pytesseract.pytesseract, "tesseract_cmd", ""))
    except Exception:
        pass
    candidates.extend(_STANDARD_PATHS)
    candidates.append(shutil.which("tesseract") or "")

    for executable in candidates:
        if not executable or not os.path.exists(executable):
            continue
        tessdata = os.path.join(os.path.dirname(executable), "tessdata")
        if os.path.isdir(tessdata):
            return tessdata
    return None


def _page_has_text(page):
    """True when the page already has a text layer worth keeping."""
    return bool(page.get_text("text").strip())


def _pytesseract_page_pdf(pix, language):
    """One-page PDF (image + hidden text) from pytesseract, as bytes.

    Used when PyMuPDF's own OCR output is unavailable. The PDF has the same
    page geometry as the pixmap at 72 dpi, so the caller can scale it onto
    the original page.
    """
    import pytesseract
    from PIL import Image

    mode = "RGBA" if pix.alpha else "RGB"
    image = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
    try:
        return pytesseract.image_to_pdf_or_hocr(image, extension="pdf", lang=language)
    except pytesseract.TesseractError as exc:
        raise RuntimeError(_("err_ocr_failed").format(error=exc)) from exc
    finally:
        del image


def _ocr_page_pdf(page, language, dpi):
    """Render *page* and return a one-page searchable PDF as bytes."""
    pix = page.get_pixmap(dpi=dpi)
    if hasattr(pix, "pdfocr_tobytes"):
        try:
            data = pix.pdfocr_tobytes(language=language, tessdata=_tessdata_dir())
        except Exception:
            data = None
        if data:
            return data
    return _pytesseract_page_pdf(pix, language)


def _append_ocr_page(output, page, pdf_bytes):
    """Add *pdf_bytes* as a new page with the original page's size."""
    import fitz

    ocr_doc = fitz.open("pdf", pdf_bytes)
    try:
        if ocr_doc.page_count < 1:
            raise RuntimeError(_("err_ocr_failed").format(error="empty OCR result"))
        rect = page.rect
        out_page = output.new_page(width=rect.width, height=rect.height)
        out_page.show_pdf_page(out_page.rect, ocr_doc, 0)
    finally:
        ocr_doc.close()


def _cancel_requested(cancel):
    if cancel is None:
        return False
    if callable(cancel):
        return bool(cancel())
    if hasattr(cancel, "is_set"):        # threading.Event
        return bool(cancel.is_set())
    return bool(getattr(cancel, "is_cancelled", False))


def _check_cancelled(cancel):
    if _cancel_requested(cancel):
        from src.core.task_manager import CancelledError
        raise CancelledError(_("perf_cancelled_msg"))


def _report_progress(progress, current, total, message=""):
    if progress is not None:
        progress(current, total, message)


def make_searchable_pdf(input_pdf, output_pdf, lang="tur+eng", dpi=300,
                        progress=None, cancel=None):
    """Add an invisible OCR text layer to the scanned pages of a PDF.

    Pages that already have text are copied unchanged, so a mixed document
    only pays for OCR where it is needed. OCR runs through PyMuPDF's Tesseract
    integration (``Pixmap.pdfocr_tobytes``); if that is unavailable,
    pytesseract's searchable-PDF output is used per page. The image of an OCRed
    page is kept, only its text becomes selectable and searchable.

    *progress*, when given, is called as ``progress(current, total, message)``
    once per page. *cancel* is a callable returning True to stop; a
    ``CancelledError`` is then raised and no output is written.

    Returns the number of pages that received a text layer. Raises
    ``EnvironmentError`` with a readable message when Tesseract is missing.
    """
    import fitz

    try:
        available = check_tesseract_availability()
    except Exception:
        available = False
    if not available:
        raise EnvironmentError(_("err_tesseract_missing"))

    language = resolve_ocr_language(lang)
    input_pdf = os.path.abspath(input_pdf)
    output_pdf = os.path.abspath(output_pdf)

    source = fitz.open(input_pdf)
    output = fitz.open()
    try:
        total = source.page_count
        ocr_pages = 0
        for index in range(total):
            _check_cancelled(cancel)
            _report_progress(progress, index, total, _("ocr_page_progress").format(
                current=index + 1, total=total))

            page = source.load_page(index)
            if _page_has_text(page):
                # Keep the original page, with its links and annotations.
                output.insert_pdf(source, from_page=index, to_page=index)
                continue

            try:
                pdf_bytes = _ocr_page_pdf(page, language, dpi)
                _append_ocr_page(output, page, pdf_bytes)
            except RuntimeError:
                raise
            except Exception as exc:
                raise RuntimeError(_("err_ocr_failed").format(error=exc)) from exc
            ocr_pages += 1

        if source.metadata:
            output.set_metadata(source.metadata)
        try:
            toc = source.get_toc()
            if toc:
                output.set_toc(toc)
        except Exception:
            pass  # a broken outline should not lose the OCR result

        _check_cancelled(cancel)
        # Windows cannot replace the input while PyMuPDF still has it open,
        # which matters when the user picked the input as the output.
        source.close()

        from src.core.output_paths import atomic_output
        with atomic_output(output_pdf) as temp_path:
            output.save(temp_path, garbage=3, deflate=True)

        _report_progress(progress, total, total, _("str_done"))
        return ocr_pages
    finally:
        output.close()
        if not source.is_closed:
            source.close()
