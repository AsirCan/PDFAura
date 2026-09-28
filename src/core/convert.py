import os
from contextlib import contextmanager

from src.core.lang_manager import _

def pdf_to_images(input_pdf, output_folder, dpi=300, img_format="png", ctx=None):
    """Render PDF pages to images with PyMuPDF. Returns number of created files.

    PyMuPDF renders page by page, so progress and cancellation are exact and
    no external Ghostscript install is needed.
    """
    import fitz

    os.makedirs(output_folder, exist_ok=True)
    ext = "png" if img_format.lower() == "png" else "jpg"

    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, 100, "PDF resme dönüştürülüyor...")

    doc = fitz.open(input_pdf)
    try:
        if doc.needs_pass:
            from src.core.common import PdfPasswordError
            raise PdfPasswordError(_("err_pdf_password_protected"))

        total = doc.page_count
        written = 0
        for index in range(total):
            if ctx:
                ctx.check_cancelled()
            pixmap = doc.load_page(index).get_pixmap(dpi=dpi)
            target = os.path.join(output_folder, f"sayfa_{index + 1:03d}.{ext}")
            if ext == "jpg":
                pixmap.save(target, jpg_quality=95)
            else:
                pixmap.save(target)
            written += 1
            if ctx:
                ctx.report_progress(written, total, f"{written}/{total} sayfa dönüştürüldü...")
    finally:
        doc.close()

    if ctx:
        ctx.report_progress(total, total, f"{written} sayfa dönüştürüldü.")

    return written


def images_to_pdf(image_paths, output_pdf, page_size="Orijinal", ctx=None):
    """Convert images to PDF using Pillow."""
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("Pillow kutuphanesi bulunamadi.\nLutfen kurun: pip install Pillow")
    if not image_paths:
        raise ValueError("En az bir resim secilmeli.")
    PAGE_SIZES = {"A4": (595, 842), "Letter": (612, 792)}
    pdf_images = []
    total = len(image_paths)
    
    for idx, img_path in enumerate(image_paths):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(idx + 1, total, f"Resim {idx + 1}/{total} işleniyor...")
        
        img = Image.open(img_path)
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
        if page_size in PAGE_SIZES:
            target_w, target_h = PAGE_SIZES[page_size]
            img_w, img_h = img.size
            ratio = min(target_w / img_w, target_h / img_h)
            new_w, new_h = int(img_w * ratio), int(img_h * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
        pdf_images.append(img)
    
    pdf_images[0].save(output_pdf, "PDF", save_all=True, append_images=pdf_images[1:], resolution=100.0)
    
    if ctx:
        ctx.report_progress(total, total, "PDF oluşturuldu.")

def pdf_to_word(input_pdf, output_docx, ctx=None):
    """Convert PDF to Word using pdf2docx."""
    try:
        from pdf2docx import Converter
    except ImportError:
        raise ImportError("pdf2docx kutuphanesi bulunamadi.\nLutfen kurun: pip install pdf2docx")
    
    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, 100, "PDF Word'e dönüştürülüyor...")
    
    cv = Converter(input_pdf)
    cv.convert(output_docx, start=0, end=None)
    cv.close()
    
    if ctx:
        ctx.report_progress(100, 100, "Dönüştürme tamamlandı.")

# ── Microsoft Office interop ───────────────────────────────────────────────
#
# These run on a worker thread, so every one of them must CoInitialize that
# thread first. They also use DispatchEx rather than Dispatch: Dispatch
# attaches to the user's already-open Office instance, and quitting it would
# close their unsaved documents.

# HRESULTs meaning "this Office application is not installed here".
_COM_NOT_INSTALLED = (-2147221005, -2147221164)  # invalid class string, class not registered

WD_EXPORT_FORMAT_PDF = 17
PP_SAVE_AS_PDF = 32
XL_TYPE_PDF = 0


def _require_win32com():
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        raise ImportError(_("err_pywin32_missing"))
    return pythoncom, win32com.client


def _office_error(exc, app_name):
    """Turn a raw COM error into something a user can act on."""
    code = getattr(exc, "hresult", None)
    if code is None:
        args = getattr(exc, "args", ())
        code = args[0] if args else None
    if code in _COM_NOT_INSTALLED:
        return RuntimeError(_("err_office_not_installed").format(app=app_name))
    return RuntimeError(f"{_('err_office_failed').format(app=app_name)} {exc}")


def _is_already_running(client, prog_id):
    """True if the user already has this Office application open."""
    try:
        client.GetActiveObject(prog_id)
        return True
    except Exception:
        return False


@contextmanager
def _office_app(prog_id, app_name, single_instance=False):
    """Yield an Office COM application, cleaning up without touching the user's.

    CoInitialize is required because we run on a worker thread. DispatchEx
    asks for a private instance; PowerPoint ignores that and hands back the
    running one, so for single-instance apps we only quit what we started.
    """
    pythoncom, client = _require_win32com()
    pythoncom.CoInitialize()
    app = None
    user_had_it_open = False
    try:
        user_had_it_open = single_instance and _is_already_running(client, prog_id)
        try:
            app = client.DispatchEx(prog_id)
        except Exception as exc:
            raise _office_error(exc, app_name)

        try:
            app.DisplayAlerts = False
        except Exception:
            pass  # PowerPoint rejects this in some versions

        yield app
    finally:
        if app is not None and not user_had_it_open:
            try:
                app.Quit()
            except Exception:
                pass
        del app
        pythoncom.CoUninitialize()


def word_to_pdf(input_docx, output_pdf, ctx=None):
    """Convert Word to PDF via COM (requires Microsoft Word). Supports .doc and .docx."""
    input_abs = os.path.abspath(input_docx)
    output_abs = os.path.abspath(output_pdf)

    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, 100, "Word PDF'e dönüştürülüyor...")

    with _office_app("Word.Application", "Word") as word:
        doc = None
        try:
            doc = word.Documents.Open(input_abs, ReadOnly=True, AddToRecentFiles=False,
                                      Visible=False)
            doc.ExportAsFixedFormat(output_abs, WD_EXPORT_FORMAT_PDF)
        except Exception as exc:
            raise _office_error(exc, "Word")
        finally:
            if doc is not None:
                try:
                    doc.Close(False)
                except Exception:
                    pass

    if ctx:
        ctx.report_progress(100, 100, "Dönüştürme tamamlandı.")


def ppt_to_pdf(input_ppt, output_pdf, ctx=None):
    """Convert PowerPoint to PDF via COM (requires Microsoft PowerPoint)."""
    input_abs = os.path.abspath(input_ppt)
    output_abs = os.path.abspath(output_pdf)

    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, 100, "PowerPoint PDF'e dönüştürülüyor...")

    # PowerPoint is single-instance: quitting it would close the user's decks.
    with _office_app("PowerPoint.Application", "PowerPoint", single_instance=True) as powerpoint:
        deck = None
        try:
            deck = powerpoint.Presentations.Open(input_abs, ReadOnly=True, WithWindow=False)
            deck.SaveAs(output_abs, PP_SAVE_AS_PDF)
        except Exception as exc:
            raise _office_error(exc, "PowerPoint")
        finally:
            if deck is not None:
                try:
                    deck.Close()
                except Exception:
                    pass

    if ctx:
        ctx.report_progress(100, 100, "Dönüştürme tamamlandı.")


def excel_to_pdf(input_excel, output_pdf, ctx=None):
    """Convert Excel to PDF via COM (requires Microsoft Excel)."""
    input_abs = os.path.abspath(input_excel)
    output_abs = os.path.abspath(output_pdf)

    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, 100, "Excel PDF'e dönüştürülüyor...")

    with _office_app("Excel.Application", "Excel") as excel:
        workbook = None
        try:
            # Our own instance stays hidden; the user's Excel is untouched.
            excel.Visible = False
            workbook = excel.Workbooks.Open(input_abs, ReadOnly=True, UpdateLinks=0,
                                            AddToMru=False)
            workbook.ExportAsFixedFormat(XL_TYPE_PDF, output_abs)
        except Exception as exc:
            raise _office_error(exc, "Excel")
        finally:
            if workbook is not None:
                try:
                    workbook.Close(False)
                except Exception:
                    pass

    if ctx:
        ctx.report_progress(100, 100, "Dönüştürme tamamlandı.")


def pdf_to_txt(input_pdf, output_txt, ctx=None):
    """Convert PDF to Text natively using pypdf."""
    from src.core.common import open_pdf_reader

    reader = open_pdf_reader(input_pdf)
    text = []
    total = len(reader.pages)
    
    for i, page in enumerate(reader.pages, 1):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(i, total, f"Sayfa {i}/{total} okunuyor...")
        page_text = page.extract_text()
        if page_text:
            text.append(page_text)
            
    with open(output_txt, "w", encoding="utf-8") as f:
        f.write("\n\n--- Sayfa Sonu ---\n\n".join(text))
    
    if ctx:
        ctx.report_progress(total, total, "Metin çıkarma tamamlandı.")
