import io

from pypdf import PdfReader, PdfWriter

from src.core.common import open_pdf_reader
from src.core.lang_manager import _
from src.core.security import _page_geometry

# Points per image pixel when no explicit width is given: 96 dpi artwork
# placed at its natural size in a 72 dpi PDF.
PT_PER_PIXEL = 72.0 / 96.0


def _to_number(value, name):
    """Parse a coordinate, accepting a comma decimal separator.

    The GUI used int(), so "100.5" -- and the "100,5" a Turkish keyboard
    produces -- raised a raw ValueError.
    """
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError(_("err_invalid_coordinate").format(name=name, value=value))


def stamp_visual_signature(input_pdf, output_pdf, image_path, page_num=1,
                           x_pos=100, y_pos=100, scale=1.0, width_pt=None):
    """Stamp a signature image onto one page.

    page_num is 1-indexed. x_pos/y_pos are in points from the bottom-left of
    the page's visible area, and are honoured on pages whose crop box does
    not start at (0, 0) and on rotated pages.

    *width_pt* sets the stamp width in points directly; otherwise the image
    is placed at its natural size scaled by *scale*.
    """
    from PIL import Image
    try:
        from reportlab.pdfgen import canvas
    except ImportError:
        raise ImportError(_("err_reportlab_missing"))

    x_pos = _to_number(x_pos, "X")
    y_pos = _to_number(y_pos, "Y")
    scale = _to_number(scale, "scale")

    reader = open_pdf_reader(input_pdf)
    writer = PdfWriter()

    total_pages = len(reader.pages)
    if page_num < 1 or page_num > total_pages:
        raise ValueError(_("err_signature_page").format(page=page_num, total=total_pages))

    try:
        with Image.open(image_path) as img:
            img_w, img_h = img.size
    except Exception:
        raise FileNotFoundError(_("err_signature_image"))

    if width_pt:
        stamp_w = _to_number(width_pt, "width")
        stamp_h = stamp_w * img_h / img_w
    else:
        stamp_w = img_w * PT_PER_PIXEL * scale
        stamp_h = img_h * PT_PER_PIXEL * scale

    target_page = reader.pages[page_num - 1]
    width, height, x0, y0, rotation = _page_geometry(target_page)

    # The canvas is laid out in the page's visible orientation, so on a
    # rotated page the stamp box is the page turned the same way.
    if rotation in (90, 270):
        canvas_w, canvas_h = height, width
    else:
        canvas_w, canvas_h = width, height

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(canvas_w, canvas_h))
    can.drawImage(image_path, x_pos, y_pos, width=stamp_w, height=stamp_h, mask="auto")
    can.save()
    packet.seek(0)

    stamp_page = PdfReader(packet).pages[0]

    # Turn the stamp back into the page's stored (unrotated) coordinates and
    # offset it by the crop box origin, which need not be (0, 0).
    a, b, c, d, e, f = _rotation_matrix(rotation, width, height)
    matrix = (a, b, c, d, e + x0, f + y0)

    for i, page in enumerate(reader.pages):
        new_page = writer.add_page(page)
        if i == page_num - 1:
            new_page.merge_transformed_page(stamp_page, matrix, expand=False)

    with open(output_pdf, "wb") as f:
        writer.write(f)


def _rotation_matrix(rotation, width, height):
    """Matrix mapping the displayed orientation back to stored coordinates."""
    if rotation == 90:
        return (0, 1, -1, 0, width, 0)
    if rotation == 180:
        return (-1, 0, 0, -1, width, height)
    if rotation == 270:
        return (0, -1, 1, 0, 0, height)
    return (1, 0, 0, 1, 0, 0)
