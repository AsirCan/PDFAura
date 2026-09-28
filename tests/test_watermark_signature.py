"""Issue #15: watermarks lost Turkish characters and were centred for A4 only."""
import fitz
import pytest
from pypdf import PdfReader, PdfWriter

from src.core.security import _needs_unicode, _watermark_font, add_watermark_to_pdf
from src.core.signature import _to_number, stamp_visual_signature

# width, height in points
A4 = (595, 842)
A4_LANDSCAPE = (842, 595)
A3_LANDSCAPE = (1191, 842)
LETTER = (612, 792)


def make_pdf_with_pages(path, sizes, rotation=0, offset=0):
    writer = PdfWriter()
    for width, height in sizes:
        page = writer.add_blank_page(width=width, height=height)
        if rotation:
            page.rotate(rotation)
        if offset:
            # A crop box that does not start at (0, 0).
            page.mediabox.lower_left = (offset, offset)
            page.mediabox.upper_right = (offset + width, offset + height)
    with open(path, "wb") as f:
        writer.write(f)
    return str(path)


def text_on_page(path, index=0):
    doc = fitz.open(path)
    try:
        return doc.load_page(index).get_text()
    finally:
        doc.close()


def ink_centre(path, index=0):
    """Centre of the drawn marks on a page, and the page size, in points."""
    doc = fitz.open(path)
    try:
        page = doc.load_page(index)
        pixmap = page.get_pixmap(dpi=36)
        import numpy as np
        data = np.frombuffer(pixmap.samples, dtype=np.uint8)
        data = data.reshape(pixmap.height, pixmap.width, pixmap.n)
        grey = data[:, :, :3].min(axis=2)
        ys, xs = np.where(grey < 240)
        if len(xs) == 0:
            return None
        cx = (xs.min() + xs.max()) / 2 / pixmap.width
        cy = (ys.min() + ys.max()) / 2 / pixmap.height
        return cx, cy
    finally:
        doc.close()


# ── Turkish characters ────────────────────────────────────────────────────

def test_unicode_detection():
    assert _needs_unicode("GİZLİ") is True
    assert _needs_unicode("GIZLI") is False


@pytest.mark.skipif(_watermark_font() is None, reason="no Unicode TTF on this machine")
def test_turkish_watermark_survives_a_round_trip(tmp_path):
    """'GİZLİ ŞİRKET ğüşıöç' used to render as black boxes."""
    src = make_pdf_with_pages(tmp_path / "in.pdf", [A4])
    out = tmp_path / "out.pdf"

    add_watermark_to_pdf(src, str(out), "GİZLİ ŞİRKET ğüşıöç")

    extracted = text_on_page(str(out))
    for char in "GİZLİŞğüşıöç":
        assert char in extracted, f"{char!r} missing from {extracted!r}"


@pytest.mark.skipif(_watermark_font() is None, reason="no Unicode TTF on this machine")
def test_assistant_default_gizli_works(tmp_path):
    """The assistant sends "GİZLİ" by default."""
    src = make_pdf_with_pages(tmp_path / "in.pdf", [A4])
    out = tmp_path / "out.pdf"
    add_watermark_to_pdf(src, str(out), "GİZLİ")
    assert "GİZLİ" in text_on_page(str(out))


def test_ascii_watermark_still_works(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf", [A4])
    out = tmp_path / "out.pdf"
    add_watermark_to_pdf(src, str(out), "GIZLI")
    assert "GIZLI" in text_on_page(str(out))


# ── Centring on other page sizes ──────────────────────────────────────────

@pytest.mark.parametrize("size, name", [
    (A4, "A4"), (A4_LANDSCAPE, "A4 landscape"),
    (A3_LANDSCAPE, "A3 landscape"), (LETTER, "Letter"),
])
def test_watermark_is_centred_on_every_page_size(tmp_path, size, name):
    """A single A4 stamp was merged onto every page: 314 pt off on A3."""
    src = make_pdf_with_pages(tmp_path / "in.pdf", [size])
    out = tmp_path / "out.pdf"

    add_watermark_to_pdf(src, str(out), "GIZLI")

    centre = ink_centre(str(out))
    assert centre is not None, f"nothing drawn on {name}"
    cx, cy = centre
    assert abs(cx - 0.5) < 0.05, f"{name}: x off by {abs(cx - 0.5):.1%}"
    assert abs(cy - 0.5) < 0.05, f"{name}: y off by {abs(cy - 0.5):.1%}"


def test_mixed_page_sizes_are_each_centred(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf", [A4, A3_LANDSCAPE, LETTER])
    out = tmp_path / "out.pdf"

    add_watermark_to_pdf(src, str(out), "GIZLI")

    for index in range(3):
        cx, cy = ink_centre(str(out), index)
        assert abs(cx - 0.5) < 0.05 and abs(cy - 0.5) < 0.05, f"page {index} off centre"


def test_rotated_page_is_centred(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf", [A4], rotation=90)
    out = tmp_path / "out.pdf"

    add_watermark_to_pdf(src, str(out), "GIZLI")

    cx, cy = ink_centre(str(out))
    assert abs(cx - 0.5) < 0.05 and abs(cy - 0.5) < 0.05


def test_offset_cropbox_is_centred(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf", [A4], offset=50)
    out = tmp_path / "out.pdf"

    add_watermark_to_pdf(src, str(out), "GIZLI")

    cx, cy = ink_centre(str(out))
    assert abs(cx - 0.5) < 0.05 and abs(cy - 0.5) < 0.05


def test_long_text_is_shrunk_to_fit(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf", [A4])
    out = tmp_path / "out.pdf"

    add_watermark_to_pdf(src, str(out), "BU COK UZUN BIR FILIGRAN METNIDIR VE SIGMALIDIR", font_size=60)

    doc = fitz.open(str(out))
    try:
        page = doc.load_page(0)
        # Every drawn mark must stay inside the page.
        for block in page.get_text("blocks"):
            x0, y0, x1, y1 = block[:4]
            assert x0 > -20 and y0 > -20
            assert x1 < page.rect.width + 20 and y1 < page.rect.height + 20
    finally:
        doc.close()


def test_page_count_is_unchanged(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf", [A4, A4, A4])
    out = tmp_path / "out.pdf"
    add_watermark_to_pdf(src, str(out), "GIZLI")
    assert len(PdfReader(str(out)).pages) == 3


# ── Signature coordinates ─────────────────────────────────────────────────

def test_coordinates_accept_decimals():
    assert _to_number("100.5", "X") == 100.5


def test_coordinates_accept_a_comma_separator():
    """A Turkish keyboard produces "100,5"; int() raised a raw ValueError."""
    assert _to_number("100,5", "X") == 100.5


def test_bad_coordinate_gives_a_readable_error():
    with pytest.raises(ValueError, match="X"):
        _to_number("abc", "X")


@pytest.fixture
def signature_image(tmp_path):
    from PIL import Image
    path = tmp_path / "sig.png"
    Image.new("RGB", (120, 60), (0, 0, 0)).save(path)
    return str(path)


def stamp_bbox(path, index=0):
    """Bounding box of the stamped image, in page points from bottom-left."""
    doc = fitz.open(path)
    try:
        page = doc.load_page(index)
        rects = [page.get_image_bbox(info) for info in page.get_images(full=True)]
        if not rects:
            return None
        rect = rects[0]
        # fitz y grows downwards; convert to PDF bottom-left origin.
        return rect.x0, page.rect.height - rect.y1
    finally:
        doc.close()


def test_signature_lands_on_the_requested_coordinate(tmp_path, signature_image):
    src = make_pdf_with_pages(tmp_path / "in.pdf", [A4])
    out = tmp_path / "out.pdf"

    stamp_visual_signature(src, str(out), signature_image, 1, 100, 150)

    x, y = stamp_bbox(str(out))
    assert abs(x - 100) < 3 and abs(y - 150) < 3


def test_signature_on_a_rotated_page(tmp_path, signature_image):
    src = make_pdf_with_pages(tmp_path / "in.pdf", [A4], rotation=90)
    out = tmp_path / "out.pdf"

    stamp_visual_signature(src, str(out), signature_image, 1, 100, 150)

    # The stamp must be on the page, not pushed off it.
    doc = fitz.open(str(out))
    try:
        page = doc.load_page(0)
        rect = page.get_image_bbox(page.get_images(full=True)[0])
        assert page.rect.contains(rect), f"{rect} outside {page.rect}"
    finally:
        doc.close()


def test_signature_with_an_offset_cropbox(tmp_path, signature_image):
    src = make_pdf_with_pages(tmp_path / "in.pdf", [A4], offset=50)
    out = tmp_path / "out.pdf"

    stamp_visual_signature(src, str(out), signature_image, 1, 100, 150)

    doc = fitz.open(str(out))
    try:
        page = doc.load_page(0)
        rect = page.get_image_bbox(page.get_images(full=True)[0])
        assert page.rect.contains(rect), f"{rect} outside {page.rect}"
    finally:
        doc.close()


def test_explicit_width_sets_the_stamp_size(tmp_path, signature_image):
    src = make_pdf_with_pages(tmp_path / "in.pdf", [A4])
    out = tmp_path / "out.pdf"

    stamp_visual_signature(src, str(out), signature_image, 1, 100, 150, width_pt=200)

    doc = fitz.open(str(out))
    try:
        rect = doc.load_page(0).get_image_bbox(doc.load_page(0).get_images(full=True)[0])
        assert abs(rect.width - 200) < 3
        assert abs(rect.height - 100) < 3   # source is 2:1
    finally:
        doc.close()


def test_invalid_page_number_is_reported(tmp_path, signature_image):
    src = make_pdf_with_pages(tmp_path / "in.pdf", [A4])
    with pytest.raises(ValueError, match="9"):
        stamp_visual_signature(src, str(tmp_path / "o.pdf"), signature_image, 9, 10, 10)
