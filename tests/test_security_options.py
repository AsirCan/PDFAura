"""Öncelik 3: permission restrictions, image watermarks with options, batch decrypt."""
import os

import fitz
import numpy as np
import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter

from conftest import make_encrypted_pdf, make_pdf
from src.core.security import add_watermark_to_pdf, decrypt_many, encrypt_pdf
from src.app import tools

A4 = (595, 842)
PRINT, MODIFY, COPY, ANNOTATE = 4, 8, 16, 32


def make_pdf_with_pages(path, sizes=(A4,), rotation=0):
    writer = PdfWriter()
    for width, height in sizes:
        page = writer.add_blank_page(width=width, height=height)
        if rotation:
            page.rotate(rotation)
    with open(path, "wb") as handle:
        writer.write(handle)
    return str(path)


def make_logo(path, size=(100, 50), colour=(200, 0, 0, 255)):
    image = Image.new("RGBA", size, colour)
    if str(path).lower().endswith((".jpg", ".jpeg")):
        image = image.convert("RGB")
    image.save(path)
    return str(path)


def ink_bounds(path, index=0):
    """Normalised (left, top, right, bottom) of the marks drawn on a page."""
    doc = fitz.open(path)
    try:
        page = doc.load_page(index)
        pixmap = page.get_pixmap(dpi=36)
        data = np.frombuffer(pixmap.samples, dtype=np.uint8)
        data = data.reshape(pixmap.height, pixmap.width, pixmap.n)
        grey = data[:, :, :3].min(axis=2)
        ys, xs = np.where(grey < 240)
        assert len(xs), "nothing was drawn"
        return (xs.min() / pixmap.width, ys.min() / pixmap.height,
                xs.max() / pixmap.width, ys.max() / pixmap.height)
    finally:
        doc.close()


def darkest_pixel(path):
    doc = fitz.open(path)
    try:
        pixmap = doc.load_page(0).get_pixmap(dpi=36)
        data = np.frombuffer(pixmap.samples, dtype=np.uint8)
        return int(data.reshape(pixmap.height, pixmap.width, pixmap.n)[:, :, :3].min())
    finally:
        doc.close()


def image_bbox(path, index=0):
    doc = fitz.open(path)
    try:
        page = doc.load_page(index)
        images = page.get_images(full=True)
        assert images, "no image was stamped"
        return page.get_image_bbox(images[0])
    finally:
        doc.close()


# ── Permissions ───────────────────────────────────────────────────────────

def test_permissions_restrict_print_copy_modify_and_annotate(tmp_path):
    src = make_pdf(tmp_path / "in.pdf")
    out = str(tmp_path / "locked.pdf")

    encrypt_pdf(src, out, "user", owner_password="owner", allow_print=False,
                allow_modify=False, allow_copy=False, allow_annotate=False)

    permissions = PdfReader(out).trailer["/Encrypt"]["/P"]
    for bit in (PRINT, MODIFY, COPY, ANNOTATE):
        assert permissions & bit == 0


@pytest.mark.parametrize("flag, bit", [
    ("allow_print", PRINT), ("allow_modify", MODIFY),
    ("allow_copy", COPY), ("allow_annotate", ANNOTATE),
])
def test_each_permission_can_be_switched_off_alone(tmp_path, flag, bit):
    src = make_pdf(tmp_path / "in.pdf")
    out = str(tmp_path / f"{flag}.pdf")

    encrypt_pdf(src, out, "user", owner_password="owner", **{flag: False})

    permissions = PdfReader(out).trailer["/Encrypt"]["/P"]
    assert permissions & bit == 0
    for other in (PRINT, MODIFY, COPY, ANNOTATE):
        if other != bit:
            assert permissions & other


def test_owner_password_opens_without_the_restrictions(tmp_path):
    src = make_pdf(tmp_path / "in.pdf")
    out = str(tmp_path / "locked.pdf")
    encrypt_pdf(src, out, "user", owner_password="owner", allow_print=False,
                allow_modify=False, allow_copy=False, allow_annotate=False)

    doc = fitz.open(out)
    try:
        assert doc.authenticate("user")
        assert doc.permissions & fitz.PDF_PERM_PRINT == 0
    finally:
        doc.close()

    doc = fitz.open(out)
    try:
        assert doc.authenticate("owner")
        assert doc.permissions & fitz.PDF_PERM_PRINT
        assert doc.permissions & fitz.PDF_PERM_MODIFY
        assert doc.permissions & fitz.PDF_PERM_COPY
        assert doc.permissions & fitz.PDF_PERM_ANNOTATE
    finally:
        doc.close()


def test_default_encryption_still_allows_everything(tmp_path):
    src = make_pdf(tmp_path / "in.pdf")
    out = str(tmp_path / "locked.pdf")
    encrypt_pdf(src, out, "user")

    permissions = PdfReader(out).trailer["/Encrypt"]["/P"]
    for bit in (PRINT, MODIFY, COPY, ANNOTATE):
        assert permissions & bit


def test_ui_strings_say_false_for_permissions(tmp_path):
    src = make_pdf(tmp_path / "in.pdf")
    out = str(tmp_path / "locked.pdf")
    encrypt_pdf(src, out, "user", allow_print="false", allow_copy="0")

    permissions = PdfReader(out).trailer["/Encrypt"]["/P"]
    assert permissions & PRINT == 0
    assert permissions & COPY == 0
    assert permissions & MODIFY


# ── Image watermarks and their options ───────────────────────────────────

@pytest.mark.parametrize("ext", ["png", "jpg"])
def test_image_watermark_is_stamped_on_every_page(tmp_path, ext):
    src = make_pdf_with_pages(tmp_path / "in.pdf", (A4, A4, A4))
    logo = make_logo(tmp_path / f"logo.{ext}")
    out = str(tmp_path / "wm.pdf")

    add_watermark_to_pdf(src, out, "", opacity=0.5, angle=0, image_path=logo)

    doc = fitz.open(out)
    try:
        assert doc.page_count == 3
        for page in doc:
            assert page.get_images(full=True)
    finally:
        doc.close()


def test_image_watermark_can_move_to_a_corner(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf")
    logo = make_logo(tmp_path / "logo.png")
    out = str(tmp_path / "wm.pdf")

    add_watermark_to_pdf(src, out, "", image_path=logo, position="bottom-right", angle=0)

    rect = image_bbox(out)
    assert rect.x0 > A4[0] * 0.5
    assert rect.y0 > A4[1] * 0.5


@pytest.mark.parametrize("position, expected", [
    ("center", (0.3, 0.3, 0.7, 0.7)),
    ("top-left", (0.0, 0.0, 0.35, 0.35)),
    ("top-right", (0.65, 0.0, 1.0, 0.35)),
    ("bottom-left", (0.0, 0.65, 0.35, 1.0)),
    ("bottom-right", (0.65, 0.65, 1.0, 1.0)),
])
def test_text_watermark_position_is_honoured(tmp_path, position, expected):
    src = make_pdf_with_pages(tmp_path / "in.pdf")
    out = str(tmp_path / "wm.pdf")

    add_watermark_to_pdf(src, out, "GIZLI", angle=0, font_size=40, position=position)

    left, top, right, bottom = ink_bounds(out)
    assert expected[0] - 0.05 <= left and expected[1] - 0.05 <= top
    assert right <= expected[2] + 0.05 and bottom <= expected[3] + 0.05


def test_tiled_watermark_covers_the_page(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf")
    out = str(tmp_path / "wm.pdf")

    add_watermark_to_pdf(src, out, "GIZLI", angle=0, font_size=36, position="tiled")

    left, top, right, bottom = ink_bounds(out)
    assert right - left > 0.7
    assert bottom - top > 0.7


def test_opacity_changes_how_dark_the_watermark_is(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf")
    light = str(tmp_path / "light.pdf")
    dark = str(tmp_path / "dark.pdf")

    add_watermark_to_pdf(src, light, "GIZLI", opacity=0.1)
    add_watermark_to_pdf(src, dark, "GIZLI", opacity=0.9)

    assert darkest_pixel(light) > darkest_pixel(dark)


def test_image_watermark_opacity_is_honoured(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf")
    logo = make_logo(tmp_path / "logo.png")
    light = str(tmp_path / "light.pdf")
    dark = str(tmp_path / "dark.pdf")

    add_watermark_to_pdf(src, light, "", image_path=logo, opacity=0.1, angle=0)
    add_watermark_to_pdf(src, dark, "", image_path=logo, opacity=0.9, angle=0)

    assert darkest_pixel(light) > darkest_pixel(dark)


def test_angle_rotates_an_image_watermark(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf")
    logo = make_logo(tmp_path / "logo.png", size=(120, 30))
    flat = str(tmp_path / "flat.pdf")
    turned = str(tmp_path / "turned.pdf")

    add_watermark_to_pdf(src, flat, "", image_path=logo, angle=0, position="center")
    add_watermark_to_pdf(src, turned, "", image_path=logo, angle=90, position="center")

    flat_rect = image_bbox(flat)
    turned_rect = image_bbox(turned)
    assert flat_rect.width > flat_rect.height
    assert turned_rect.height > turned_rect.width


def test_unknown_position_is_reported(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf")
    with pytest.raises(ValueError, match="konum"):
        add_watermark_to_pdf(src, str(tmp_path / "wm.pdf"), "GIZLI", position="middle")


def test_watermark_needs_text_or_an_image(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf")
    with pytest.raises(ValueError, match="boş olamaz"):
        add_watermark_to_pdf(src, str(tmp_path / "wm.pdf"), "")


def test_missing_logo_gives_a_readable_error(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf")
    with pytest.raises(ValueError, match="okunamadı"):
        add_watermark_to_pdf(src, str(tmp_path / "wm.pdf"), "",
                             image_path=str(tmp_path / "yok.png"))


# ── Batch decrypt ────────────────────────────────────────────────────────

def test_decrypt_many_reports_each_file(tmp_path):
    good1 = make_encrypted_pdf(tmp_path / "a.pdf", "pw")
    good2 = make_encrypted_pdf(tmp_path / "b.pdf", "pw")
    wrong = make_encrypted_pdf(tmp_path / "c.pdf", "other")
    plain = make_pdf(tmp_path / "d.pdf")
    out_dir = tmp_path / "out"

    report = decrypt_many([good1, good2, wrong, plain], "pw", str(out_dir))

    assert [item["success"] for item in report] == [True, True, False, False]
    assert [item["input"] for item in report] == [good1, good2, wrong, plain]
    for item in report[:2]:
        assert os.path.isfile(item["output"])
        assert not PdfReader(item["output"]).is_encrypted
    for item in report[2:]:
        assert item["output"] is None
        assert item["error"]


def test_decrypt_many_keeps_duplicate_names_apart(tmp_path):
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    make_encrypted_pdf(first / "rapor.pdf", "pw")
    make_encrypted_pdf(second / "rapor.pdf", "pw")
    out_dir = tmp_path / "out"

    report = decrypt_many([first / "rapor.pdf", second / "rapor.pdf"], "pw", str(out_dir))

    assert all(item["success"] for item in report)
    assert report[0]["output"] != report[1]["output"]
    assert os.path.isfile(report[0]["output"]) and os.path.isfile(report[1]["output"])


def test_decrypt_many_accepts_one_path(tmp_path):
    source = make_encrypted_pdf(tmp_path / "a.pdf", "pw")
    report = decrypt_many(source, "pw", str(tmp_path / "out"))
    assert report[0]["success"] is True


# ── The tool layer passes the options through ─────────────────────────────

def test_security_tool_passes_permission_options(tmp_path):
    src = make_pdf(tmp_path / "in.pdf")
    out = str(tmp_path / "locked.pdf")
    params = {"input": src, "output": out, "mode": "encrypt", "password": "user",
              "confirm": "user", "owner_password": "owner", "allow_print": False,
              "allow_copy": False, "allow_modify": True, "allow_annotate": True}

    assert tools.check("security", params) is None
    tools.get("security").run(None, **params)

    permissions = PdfReader(out).trailer["/Encrypt"]["/P"]
    assert permissions & PRINT == 0 and permissions & COPY == 0
    assert permissions & MODIFY


def test_security_tool_passes_watermark_options(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf")
    logo = make_logo(tmp_path / "logo.png")
    out = str(tmp_path / "wm.pdf")
    params = {"input": src, "output": out, "mode": "watermark", "watermark_text": "",
              "watermark_image": logo, "opacity": 0.4, "angle": 0,
              "position": "bottom-left"}

    assert tools.check("security", params) is None
    tools.get("security").run(None, **params)

    rect = image_bbox(out)
    assert rect.x1 < A4[0] * 0.5
    assert rect.y0 > A4[1] * 0.5


def test_security_tool_checks_the_watermark_image_and_position(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf")
    missing = {"input": src, "output": str(tmp_path / "wm.pdf"), "mode": "watermark",
               "watermark_image": str(tmp_path / "yok.png")}
    assert tools.check("security", missing) == "Geçerli bir resim dosyası seçin."

    bad = {**missing, "watermark_image": make_logo(tmp_path / "logo.png"),
           "position": "middle"}
    assert "konum" in tools.check("security", bad)


def test_image_watermark_on_rotated_page(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf", sizes=(A4,), rotation=90)
    logo = make_logo(tmp_path / "logo.png")
    out = str(tmp_path / "wm_rot.pdf")

    add_watermark_to_pdf(src, out, "", image_path=logo, angle=0)

    doc = fitz.open(out)
    try:
        assert doc.page_count == 1
        page = doc[0]
        assert page.rotation == 90
        assert len(page.get_images(full=True)) >= 1
    finally:
        doc.close()


def test_tiled_image_watermark(tmp_path):
    src = make_pdf_with_pages(tmp_path / "in.pdf")
    logo = make_logo(tmp_path / "logo.png")
    out = str(tmp_path / "wm_tiled.pdf")

    add_watermark_to_pdf(src, out, "", image_path=logo, position="tiled")

    left, top, right, bottom = ink_bounds(out)
    assert right - left > 0.7
    assert bottom - top > 0.7


def test_decrypt_many_reports_progress_and_cancel(tmp_path):
    good = make_encrypted_pdf(tmp_path / "a.pdf", "pw")
    out_dir = tmp_path / "out"

    progress = []

    class MockContext:
        def check_cancelled(self):
            pass

        def report_progress(self, current, total, text=""):
            progress.append((current, total))

    report = decrypt_many([good], "pw", str(out_dir), ctx=MockContext())
    assert report[0]["success"] is True
    assert len(progress) == 1

