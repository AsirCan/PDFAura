"""Issue #16: "A4" produced a 428x571 pt page and downscaled the image."""
import fitz
import pytest
from PIL import Image

from src.core.convert import DEFAULT_IMAGE_DPI, images_to_pdf

A4_PT = (595.276, 841.890)
LETTER_PT = (612.0, 792.0)


def make_image(path, size=(1200, 1600), mode="RGB", colour=(200, 30, 30), dpi=None):
    image = Image.new(mode, size, colour if mode != "L" else 128)
    image.save(path, dpi=dpi) if dpi else image.save(path)
    return str(path)


def page_rect(pdf_path, index=0):
    doc = fitz.open(pdf_path)
    try:
        return doc.load_page(index).rect
    finally:
        doc.close()


def embedded_image(pdf_path, index=0):
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(index)
        xref = page.get_images(full=True)[0][0]
        info = doc.extract_image(xref)
        return info["width"], info["height"]
    finally:
        doc.close()


# ── Page size ─────────────────────────────────────────────────────────────

def test_a4_page_is_really_a4(tmp_path):
    """It used to come out 428 x 571 pt."""
    src = make_image(tmp_path / "p.png", (1200, 1600))
    out = tmp_path / "out.pdf"

    images_to_pdf([src], str(out), "A4")

    rect = page_rect(str(out))
    assert abs(rect.width - A4_PT[0]) < 1
    assert abs(rect.height - A4_PT[1]) < 1


def test_landscape_image_gets_a_landscape_a4(tmp_path):
    src = make_image(tmp_path / "p.png", (1600, 1200))
    out = tmp_path / "out.pdf"

    images_to_pdf([src], str(out), "A4")

    rect = page_rect(str(out))
    assert abs(rect.width - A4_PT[1]) < 1
    assert abs(rect.height - A4_PT[0]) < 1


def test_letter_page_size(tmp_path):
    src = make_image(tmp_path / "p.png", (1200, 1600))
    out = tmp_path / "out.pdf"

    images_to_pdf([src], str(out), "Letter")

    rect = page_rect(str(out))
    assert abs(rect.width - LETTER_PT[0]) < 1
    assert abs(rect.height - LETTER_PT[1]) < 1


def test_original_size_uses_the_image_dpi(tmp_path):
    src = make_image(tmp_path / "p.png", (600, 900), dpi=(300, 300))
    out = tmp_path / "out.pdf"

    images_to_pdf([src], str(out), "Orijinal")

    rect = page_rect(str(out))
    assert abs(rect.width - 600 * 72 / 300) < 1
    assert abs(rect.height - 900 * 72 / 300) < 1


def test_original_size_falls_back_to_96_dpi(tmp_path):
    src = make_image(tmp_path / "p.png", (960, 480))
    out = tmp_path / "out.pdf"

    images_to_pdf([src], str(out), "Orijinal")

    rect = page_rect(str(out))
    assert abs(rect.width - 960 * 72 / DEFAULT_IMAGE_DPI) < 2


# ── Resolution ────────────────────────────────────────────────────────────

def test_image_keeps_its_original_pixels(tmp_path):
    """The image was resized down to the page's point count."""
    src = make_image(tmp_path / "p.png", (2400, 3200))
    out = tmp_path / "out.pdf"

    images_to_pdf([src], str(out), "A4")

    width, height = embedded_image(str(out))
    assert (width, height) == (2400, 3200)


def test_image_is_not_stretched(tmp_path):
    """A 1:1 image on A4 must stay square."""
    src = make_image(tmp_path / "p.png", (1000, 1000))
    out = tmp_path / "out.pdf"

    images_to_pdf([src], str(out), "A4")

    doc = fitz.open(str(out))
    try:
        rect = doc.load_page(0).get_image_bbox(doc.load_page(0).get_images(full=True)[0])
        assert abs(rect.width / rect.height - 1.0) < 0.01
    finally:
        doc.close()


# ── Transparency ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode", ["RGBA", "LA", "P"])
def test_transparent_areas_become_white_not_black(tmp_path, mode):
    """Only RGBA was handled; LA and P transparency came out black."""
    path = tmp_path / f"t_{mode}.png"
    transparent = Image.new("RGBA", (200, 200), (255, 0, 0, 0))  # fully transparent
    if mode == "RGBA":
        transparent.save(path)
    elif mode == "LA":
        transparent.convert("LA").save(path)
    else:
        # A palette image whose colour 0 is declared transparent.
        palette = Image.new("P", (200, 200), 0)
        palette.putpalette([255, 0, 0] * 256)
        palette.save(path, transparency=0)

    out = tmp_path / "out.pdf"
    images_to_pdf([str(path)], str(out), "Orijinal")

    doc = fitz.open(str(out))
    try:
        pixmap = doc.load_page(0).get_pixmap(dpi=36)
        centre = pixmap.pixel(pixmap.width // 2, pixmap.height // 2)
        assert min(centre[:3]) > 200, f"{mode}: transparent area came out {centre}"
    finally:
        doc.close()


# ── EXIF orientation ──────────────────────────────────────────────────────

def test_exif_orientation_is_applied(tmp_path):
    """Phone photos came out sideways."""
    path = tmp_path / "rot.jpg"
    image = Image.new("RGB", (1200, 800), (10, 120, 200))
    exif = image.getexif()
    exif[274] = 6                                     # Orientation: rotate 90 CW
    image.save(path, exif=exif)

    out = tmp_path / "out.pdf"
    images_to_pdf([str(path)], str(out), "Orijinal")

    rect = page_rect(str(out))
    assert rect.height > rect.width, "orientation was not applied"


# ── Multi-page TIFF ───────────────────────────────────────────────────────

def test_every_tiff_frame_becomes_a_page(tmp_path):
    """Only the first frame of a multi-page TIFF was used."""
    path = tmp_path / "multi.tiff"
    frames = [Image.new("RGB", (400, 600), c) for c in
              ((200, 0, 0), (0, 200, 0), (0, 0, 200))]
    frames[0].save(path, save_all=True, append_images=frames[1:])

    out = tmp_path / "out.pdf"
    images_to_pdf([str(path)], str(out), "A4")

    assert fitz.open(str(out)).page_count == 3


# ── General ───────────────────────────────────────────────────────────────

def test_several_images_become_several_pages(tmp_path):
    paths = [make_image(tmp_path / f"p{i}.png") for i in range(3)]
    out = tmp_path / "out.pdf"

    images_to_pdf(paths, str(out), "A4")

    assert fitz.open(str(out)).page_count == 3


def test_no_images_is_an_error(tmp_path):
    with pytest.raises(ValueError):
        images_to_pdf([], str(tmp_path / "out.pdf"))


def test_failure_leaves_no_partial_pdf(tmp_path):
    out = tmp_path / "out.pdf"
    with pytest.raises(Exception):
        images_to_pdf([str(tmp_path / "missing.png")], str(out), "A4")
    assert not out.exists()
