import io
import os

from src.core.common import open_pdf_reader
from src.core.lang_manager import _
from src.core.output_paths import unique_path, write_pdf


def check_new_password(password, confirm=None):
    """Validate a password chosen for encryption. Raises ValueError."""
    if not password:
        raise ValueError(_("err_password_empty"))
    if "\x00" in str(password):
        raise ValueError("Password contains invalid null character")
    if len(str(password)) > 1024:
        raise ValueError("Password is too long (maximum 1024 characters)")
    if confirm is not None and password != confirm:
        raise ValueError(_("err_password_mismatch"))


def encrypt_pdf(input_pdf, output_pdf, password, ctx=None, owner_password=None,
                allow_print=True, allow_modify=True, allow_copy=True,
                allow_annotate=True):
    """Encrypt a PDF with the given password (AES-256).

    The whole document is copied, so bookmarks, document info and form
    fields stay; copying only the pages lost them (#32).

    *owner_password* opens the document without the restrictions below.
    *allow_print*, *allow_modify*, *allow_copy* and *allow_annotate* map to
    the PDF permission bits Acrobat and PyMuPDF read. The defaults keep the
    old behaviour: everything allowed.
    """
    from pypdf import PdfWriter
    if "\x00" in str(input_pdf) or "\x00" in str(output_pdf):
        raise ValueError("Path contains invalid null character")
    check_new_password(password)
    reader = open_pdf_reader(input_pdf)
    writer = None
    try:
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(0, 1, _("progress_starting"))
        writer = PdfWriter(clone_from=reader)
        total = len(writer.pages)

        writer.encrypt(user_password=password, owner_password=owner_password or password,
                       permissions_flag=_permissions(allow_print, allow_modify, allow_copy,
                                                     allow_annotate),
                       algorithm="AES-256")

        write_pdf(writer, output_pdf)

        if ctx:
            ctx.report_progress(total + 1, total + 1, _("progress_finished"))
    finally:
        if hasattr(reader, "close"):
            reader.close()
        if writer is not None and hasattr(writer, "close"):
            writer.close()


def _truthy(value):
    """A permission flag from a UI checkbox, int or string ("false", "0")."""
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no", "off")
    return bool(value)


def _permissions(allow_print, allow_modify, allow_copy, allow_annotate):
    """PDF permission flags for the four restrictions the UI offers."""
    from pypdf.constants import UserAccessPermissions as Access
    permissions = Access.all()
    if not _truthy(allow_print):
        permissions &= ~(Access.PRINT | Access.PRINT_TO_REPRESENTATION)
    if not _truthy(allow_modify):
        permissions &= ~(Access.MODIFY | Access.FILL_FORM_FIELDS | Access.ASSEMBLE_DOC)
    if not _truthy(allow_copy):
        permissions &= ~(Access.EXTRACT | Access.EXTRACT_TEXT_AND_GRAPHICS)
    if not _truthy(allow_annotate):
        permissions &= ~Access.ADD_OR_MODIFY
    return permissions


def decrypt_pdf(input_pdf, output_pdf, password, ctx=None):
    """Decrypt a PDF using the given password, keeping everything else."""
    if "\x00" in str(input_pdf) or "\x00" in str(output_pdf):
        raise ValueError("Path contains invalid null character")
    from pypdf import PdfReader, PdfWriter
    with open(input_pdf, "rb") as fh:
        initial_reader = PdfReader(fh)
        if not initial_reader.is_encrypted:
            raise ValueError(_("err_pdf_not_encrypted"))

    reader = open_pdf_reader(input_pdf, password)
    writer = None
    try:
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(1, 3, _("progress_starting"))

        writer = PdfWriter(clone_from=reader)
        total = len(writer.pages)

        write_pdf(writer, output_pdf)

        if ctx:
            ctx.report_progress(total + 1, total + 1, _("progress_finished"))
    finally:
        if hasattr(reader, "close"):
            reader.close()
        if writer is not None and hasattr(writer, "close"):
            writer.close()


def decrypt_many(paths, password, out_dir, ctx=None):
    """Decrypt every PDF in *paths* into *out_dir*.

    One bad file (a wrong password, an unencrypted PDF) must not stop the
    rest, so every file gets its own result. Returns a list with one dict per
    input: ``{"input", "output", "success", "error"}``; *output* is None and
    *error* is the message when that file failed.
    """
    if isinstance(paths, (str, os.PathLike)):
        paths = [paths]
    else:
        paths = list(paths)
    if "\x00" in str(out_dir):
        raise ValueError("Output directory contains invalid null character")
    out_dir_abs = os.path.abspath(out_dir)
    os.makedirs(out_dir_abs, exist_ok=True)
    report = []
    total = len(paths)
    for index, source in enumerate(paths, 1):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(index, max(total, 1), _("progress_page_of").format(current=index, total=total))
        result = {"input": source, "output": None, "success": False, "error": None}
        try:
            safe_name = os.path.basename(str(source))
            target = unique_path(os.path.join(out_dir_abs, safe_name))
            if not os.path.abspath(target).startswith(out_dir_abs + os.sep):
                raise ValueError("Output escapes directory")
            decrypt_pdf(source, target, password)
            result.update(output=target, success=True)
        except Exception as exc:  # noqa: BLE001 - one file's error is the report
            result["error"] = str(exc)
        report.append(result)
    return report


# Fonts to try for the watermark, best first. Helvetica is WinAnsi-only, so
# İ, Ş, Ğ, ı, ş and ğ came out as black boxes; these are Unicode TTFs.
_WINDOWS_FONTS = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts")
_WATERMARK_FONTS = [
    ("PDFAura-Segoe", os.path.join(_WINDOWS_FONTS, "segoeuib.ttf")),
    ("PDFAura-ArialBold", os.path.join(_WINDOWS_FONTS, "arialbd.ttf")),
    ("PDFAura-Arial", os.path.join(_WINDOWS_FONTS, "arial.ttf")),
    ("PDFAura-DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]

_registered_font = None


def _watermark_font():
    """Register and return a Unicode font name, or None to fall back.

    Falling back to Helvetica-Bold is only safe for WinAnsi text; the caller
    checks that.
    """
    global _registered_font
    if _registered_font is not None:
        return _registered_font or None

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for name, path in _WATERMARK_FONTS:
        if not os.path.exists(path):
            continue
        try:
            pdfmetrics.registerFont(TTFont(name, path))
        except Exception:
            continue
        _registered_font = name
        return name

    _registered_font = ""
    return None


def _needs_unicode(text):
    """True if *text* has characters Helvetica's WinAnsi encoding lacks."""
    try:
        text.encode("cp1252")
        return False
    except UnicodeEncodeError:
        return True


def _page_geometry(page):
    """(width, height, x0, y0, rotation) of a page's crop box.

    The crop box need not start at (0, 0), and /Rotate changes which way is
    up; both were ignored, so stamps landed off-centre and at odd angles.
    """
    box = page.cropbox if page.cropbox is not None else page.mediabox
    x0, y0 = float(box.left), float(box.bottom)
    width, height = float(box.width), float(box.height)
    rotation = int(page.get("/Rotate", 0) or 0) % 360
    return width, height, x0, y0, rotation


WATERMARK_POSITIONS = ("center", "top-left", "top-right", "bottom-left",
                       "bottom-right", "tiled")
_POSITION_ALIASES = {
    "top_left": "top-left", "topleft": "top-left", "top": "top-left",
    "top_right": "top-right", "topright": "top-right",
    "bottom_left": "bottom-left", "bottomleft": "bottom-left", "bottom": "bottom-left",
    "bottom_right": "bottom-right", "bottomright": "bottom-right",
    "tile": "tiled", "repeat": "tiled",
}


def _normalise_position(position):
    """A watermark position from a UI value, with the long spellings allowed."""
    value = str(position or "center").strip().lower().replace(" ", "-")
    value = _POSITION_ALIASES.get(value, _POSITION_ALIASES.get(value.replace("-", "_"), value))
    if value not in WATERMARK_POSITIONS:
        raise ValueError(_("err_watermark_position").format(position=position))
    return value


def _displayed_size(width, height, rotation):
    """The page size as the reader sees it, after /Rotate is applied."""
    return (height, width) if rotation in (90, 270) else (width, height)


def _rotation_matrix(rotation, width, height):
    """Matrix mapping the displayed orientation back to stored coordinates."""
    if rotation == 90:
        return (0, 1, -1, 0, width, 0)
    if rotation == 180:
        return (-1, 0, 0, -1, width, height)
    if rotation == 270:
        return (0, -1, 1, 0, 0, height)
    return (1, 0, 0, 1, 0, 0)


def _image_size(image_path, width, height, scale=0.3):
    """The image's drawn size in points, scaled to the page and kept on it."""
    try:
        from PIL import Image
        with Image.open(image_path) as image:
            image_w, image_h = image.size
    except Exception:
        raise ValueError(_("err_watermark_image"))
    if image_w <= 0 or image_h <= 0:
        raise ValueError(_("err_watermark_image"))
    draw_w = max(1.0, min(width, height) * scale)
    draw_h = draw_w * image_h / image_w
    # A tall logo would otherwise run off the page; fit both directions.
    factor = min(1.0, width * 0.9 / draw_w, height * 0.9 / draw_h)
    return draw_w * factor, draw_h * factor


def _build_watermark_page(text, width, height, rotation, opacity, angle, font_size,
                          image_path=None, position="center"):
    """Render one watermark sized and positioned for these exact page metrics."""
    from pypdf import PdfReader
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import Color, black
    from reportlab.pdfbase import pdfmetrics

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(width, height))

    # Apply coordinate transform for rotation so coordinates are upright
    matrix = _rotation_matrix(rotation, width, height)
    can.transform(*matrix)

    disp_w, disp_h = _displayed_size(width, height, rotation)

    # Determine coordinates in displayed space
    if position == "center":
        points = [(disp_w * 0.5, disp_h * 0.5)]
    elif position == "top-left":
        points = [(disp_w * 0.175, disp_h * 0.825)]
    elif position == "top-right":
        points = [(disp_w * 0.825, disp_h * 0.825)]
    elif position == "bottom-left":
        points = [(disp_w * 0.175, disp_h * 0.175)]
    elif position == "bottom-right":
        points = [(disp_w * 0.825, disp_h * 0.175)]
    elif position == "tiled":
        points = [
            (disp_w * x, disp_h * y)
            for y in (0.1, 0.5, 0.9)
            for x in (0.1, 0.5, 0.9)
        ]
    else:
        points = [(disp_w * 0.5, disp_h * 0.5)]

    if image_path:
        from PIL import Image
        from reportlab.lib.utils import ImageReader
        try:
            with Image.open(image_path) as src_im:
                im = src_im.convert("RGBA")
        except Exception:
            raise ValueError(_("err_watermark_image"))

        # Adjust alpha using opacity
        r, g, b, a = im.split()
        a = a.point(lambda p: int(p * opacity))
        im.putalpha(a)
        img_reader = ImageReader(im)

        img_w, img_h = _image_size(image_path, disp_w, disp_h, scale=0.3 if position != "tiled" else 0.2)

        for cx, cy in points:
            can.saveState()
            can.translate(cx, cy)
            can.rotate(angle)
            can.drawImage(img_reader, -img_w / 2, -img_h / 2, width=img_w, height=img_h, mask="auto")
            can.restoreState()
    else:
        font_name = _watermark_font() or "Helvetica-Bold"
        effective_font_size = font_size

        if position == "center":
            diagonal = (disp_w ** 2 + disp_h ** 2) ** 0.5
            text_width = pdfmetrics.stringWidth(text, font_name, effective_font_size) or 1
            max_width = diagonal * 0.75
            if text_width > max_width:
                effective_font_size = max(6.0, effective_font_size * max_width / text_width)
        elif position == "tiled":
            effective_font_size = min(effective_font_size, 36.0)

        for cx, cy in points:
            can.saveState()
            can.translate(cx, cy)
            can.rotate(angle)
            can.setFillColor(Color(black.red, black.green, black.blue, alpha=opacity))
            can.setFont(font_name, effective_font_size)
            can.drawCentredString(0, -effective_font_size / 3, text)
            can.restoreState()

    can.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]


def add_watermark_to_pdf(input_pdf, output_pdf, text="", opacity=0.3, angle=45,
                         font_size=60, ctx=None, image_path=None, position="center"):
    if "\x00" in str(input_pdf) or "\x00" in str(output_pdf):
        raise ValueError("Path contains invalid null character")
    if image_path and "\x00" in str(image_path):
        raise ValueError(_("err_watermark_image"))
    text = str(text or "").replace("\x00", "")[:1000]
    font_size = max(4.0, min(500.0, float(font_size or 60.0)))
    opacity = max(0.0, min(1.0, float(opacity if opacity is not None else 0.3)))
    angle = float(angle or 0.0) % 360
    """Add a text or image watermark to all pages of a PDF.

    One watermark is built per distinct page geometry (size and rotation),
    so mixed-size documents stay centred.
    """
    from pypdf import PdfWriter
    try:
        import reportlab  # noqa: F401
    except ImportError:
        raise ImportError(_("err_reportlab_missing"))

    if not text and not image_path:
        raise ValueError(_("err_watermark_empty"))

    position = _normalise_position(position)

    if image_path:
        if not os.path.isfile(image_path):
            raise ValueError(_("err_watermark_image"))
    elif _needs_unicode(text) and _watermark_font() is None:
        raise ValueError(_("err_watermark_font_missing"))

    if ctx:
        ctx.report_progress(1, 10, _("progress_starting"))

    reader = open_pdf_reader(input_pdf)
    writer = None
    try:
        writer = PdfWriter(clone_from=reader)
        total = len(writer.pages)
        stamps = {}

        for i, page in enumerate(writer.pages, 1):
            if ctx:
                ctx.check_cancelled()
                ctx.report_progress(i, total, _("progress_page_of").format(current=i, total=total))

            width, height, x0, y0, rotation = _page_geometry(page)
            key = (round(width, 2), round(height, 2), rotation)
            if key not in stamps:
                stamps[key] = _build_watermark_page(text, width, height, rotation,
                                                    opacity, angle, font_size,
                                                    image_path=image_path,
                                                    position=position)

            page.merge_translated_page(stamps[key], x0, y0, expand=False)

        write_pdf(writer, output_pdf)

        if ctx:
            ctx.report_progress(total, total, _("progress_finished"))
    finally:
        if hasattr(reader, "close"):
            reader.close()
        if writer is not None and hasattr(writer, "close"):
            writer.close()
