import io
import os

from pypdf import PdfReader, PdfWriter

from src.core.common import open_pdf_reader
from src.core.lang_manager import _


def check_new_password(password, confirm=None):
    """Validate a password chosen for encryption. Raises ValueError."""
    if not password:
        raise ValueError(_("err_password_empty"))
    if confirm is not None and password != confirm:
        raise ValueError(_("err_password_mismatch"))


def encrypt_pdf(input_pdf, output_pdf, password, ctx=None):
    """Encrypt a PDF with the given password (AES-256)."""
    check_new_password(password)
    reader = open_pdf_reader(input_pdf)
    writer = PdfWriter()
    total = len(reader.pages)

    for i, page in enumerate(reader.pages, 1):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(i, total + 1, f"Sayfa {i}/{total} şifreleniyor...")
        writer.add_page(page)

    writer.encrypt(user_password=password, algorithm="AES-256")

    with open(output_pdf, "wb") as f:
        writer.write(f)

    if ctx:
        ctx.report_progress(total + 1, total + 1, "Şifreleme tamamlandı.")

def decrypt_pdf(input_pdf, output_pdf, password, ctx=None):
    """Decrypt a PDF using the given password."""
    if not PdfReader(input_pdf).is_encrypted:
        raise ValueError(_("err_pdf_not_encrypted"))

    reader = open_pdf_reader(input_pdf, password)

    if ctx:
        ctx.report_progress(1, 3, "Şifre çözülüyor...")

    writer = PdfWriter()
    total = len(reader.pages)
    for i, page in enumerate(reader.pages, 1):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(i, total + 1, f"Sayfa {i}/{total} çözülüyor...")
        writer.add_page(page)

    with open(output_pdf, "wb") as f:
        writer.write(f)

    if ctx:
        ctx.report_progress(total + 1, total + 1, "Şifre çözme tamamlandı.")

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


def _build_watermark_page(text, width, height, rotation, opacity, angle, font_size):
    """Render one watermark sized and centred for these exact page metrics."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import Color, black
    from reportlab.pdfbase import pdfmetrics

    font_name = _watermark_font() or "Helvetica-Bold"

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(width, height))

    # A rotated page is displayed turned, so the text has to turn with it.
    effective_angle = (angle + rotation) % 360

    # Shrink long text to ~80% of the diagonal rather than overflowing.
    diagonal = (width ** 2 + height ** 2) ** 0.5
    text_width = pdfmetrics.stringWidth(text, font_name, font_size) or 1
    max_width = diagonal * 0.8
    if text_width > max_width:
        font_size = max(6.0, font_size * max_width / text_width)

    can.translate(width / 2, height / 2)
    can.rotate(effective_angle)
    can.setFillColor(Color(black.red, black.green, black.blue, alpha=opacity))
    can.setFont(font_name, font_size)
    can.drawCentredString(0, -font_size / 3, text)
    can.save()

    packet.seek(0)
    return PdfReader(packet).pages[0]


def add_watermark_to_pdf(input_pdf, output_pdf, text, opacity=0.3, angle=45, font_size=60, ctx=None):
    """Add a diagonal text watermark to all pages of a PDF.

    One watermark is built per distinct page geometry (size and rotation),
    so mixed-size documents stay centred; a single A4 stamp used to be
    merged onto every page and was off by up to 314 pt on A3 landscape.
    """
    try:
        import reportlab  # noqa: F401
    except ImportError:
        raise ImportError(_("err_reportlab_missing"))

    if _needs_unicode(text) and _watermark_font() is None:
        raise ValueError(_("err_watermark_font_missing"))

    if ctx:
        ctx.report_progress(1, 10, "Filigran oluşturuluyor...")

    reader = open_pdf_reader(input_pdf)
    writer = PdfWriter()
    total = len(reader.pages)
    stamps = {}

    for i, page in enumerate(reader.pages, 1):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(i, total, f"Sayfa {i}/{total} filigranlaniyor...")

        width, height, x0, y0, rotation = _page_geometry(page)
        key = (round(width, 2), round(height, 2), rotation)
        if key not in stamps:
            stamps[key] = _build_watermark_page(text, width, height, rotation,
                                                opacity, angle, font_size)

        # Attach the page to the writer before merging: pypdf needs the page
        # to have a writer to rewrite its content stream reliably.
        new_page = writer.add_page(page)
        # Shift the stamp onto the crop box when it does not start at (0, 0).
        new_page.merge_translated_page(stamps[key], x0, y0, expand=False)

    with open(output_pdf, "wb") as f:
        writer.write(f)

    if ctx:
        ctx.report_progress(total, total, "Filigran ekleme tamamlandı.")
