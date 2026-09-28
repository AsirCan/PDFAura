"""Issues #12 and #13: export raced the page list; every page was forced to A4."""
import cv2
import fitz
import numpy as np
import pytest

from src.core.document_scanner import (A4_HEIGHT_PX, A4_WIDTH_PX, MODE_BW, MODE_ORIGINAL,
                                       PAGE_SIZE_A4_LANDSCAPE, PAGE_SIZE_A4_PORTRAIT,
                                       apply_scan_mode, perspective_warp,
                                       scanned_images_to_pdf, target_size_from_corners)


def corners(width, height):
    """TL, TR, BR, BL of an axis-aligned rectangle."""
    return [(0, 0), (width, 0), (width, height), (0, height)]


# ── Output size (#13.1) ───────────────────────────────────────────────────

def test_a4_portrait_snaps_to_a4():
    assert target_size_from_corners(corners(210, 297)) == (A4_WIDTH_PX, A4_HEIGHT_PX)


def test_a4_landscape_snaps_to_landscape_a4():
    assert target_size_from_corners(corners(297, 210)) == (A4_HEIGHT_PX, A4_WIDTH_PX)


def test_slightly_off_a4_still_snaps():
    assert target_size_from_corners(corners(210, 297 * 1.03)) == (A4_WIDTH_PX, A4_HEIGHT_PX)


def test_receipt_keeps_its_own_proportions():
    w, h = target_size_from_corners(corners(100, 300))
    assert h > w
    assert abs((h / w) - 3.0) < 0.02


def test_business_card_keeps_its_own_proportions():
    w, h = target_size_from_corners(corners(85, 54))
    assert w > h
    assert abs((w / h) - (85 / 54)) < 0.02


@pytest.mark.parametrize("page_size, expected", [
    (PAGE_SIZE_A4_PORTRAIT, (A4_WIDTH_PX, A4_HEIGHT_PX)),
    (PAGE_SIZE_A4_LANDSCAPE, (A4_HEIGHT_PX, A4_WIDTH_PX)),
])
def test_explicit_page_size_overrides_measurement(page_size, expected):
    assert target_size_from_corners(corners(100, 300), page_size) == expected


def test_a_circle_stays_a_circle_on_a_landscape_document():
    """The reported symptom: a circle came out as a 1 : 2.63 ellipse."""
    doc_w, doc_h = 900, 340
    image = np.full((doc_h, doc_w, 3), 255, np.uint8)
    cv2.circle(image, (doc_w // 2, doc_h // 2), 120, (0, 0, 0), -1)

    warped = perspective_warp(image, corners(doc_w - 1, doc_h - 1))

    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    ys, xs = np.where(gray < 128)
    width = xs.max() - xs.min()
    height = ys.max() - ys.min()
    assert abs(width / height - 1.0) < 0.05, f"circle became {width}x{height}"


def test_forcing_a4_would_distort_the_same_circle():
    """Guards the test above: the old fixed-A4 behaviour really was wrong."""
    doc_w, doc_h = 900, 340
    image = np.full((doc_h, doc_w, 3), 255, np.uint8)
    cv2.circle(image, (doc_w // 2, doc_h // 2), 120, (0, 0, 0), -1)

    warped = perspective_warp(image, corners(doc_w - 1, doc_h - 1),
                              A4_WIDTH_PX, A4_HEIGHT_PX)

    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    ys, xs = np.where(gray < 128)
    ratio = (xs.max() - xs.min()) / (ys.max() - ys.min())
    assert ratio < 0.5  # badly squashed, as reported


# ── PDF writing (#13.2, #13.3) ────────────────────────────────────────────

def page(width, height, colour=(30, 30, 200)):
    return np.full((height, width, 3), colour, np.uint8)


def test_pdf_page_keeps_the_image_aspect(tmp_path):
    out = tmp_path / "out.pdf"
    scanned_images_to_pdf([page(1200, 600)], str(out))

    doc = fitz.open(str(out))
    try:
        rect = doc.load_page(0).rect
        assert abs(rect.width / rect.height - 2.0) < 0.01
    finally:
        doc.close()


def test_mixed_orientations_each_keep_their_own_size(tmp_path):
    out = tmp_path / "out.pdf"
    scanned_images_to_pdf([page(1200, 600), page(600, 1200)], str(out))

    doc = fitz.open(str(out))
    try:
        assert doc.page_count == 2
        first, second = doc.load_page(0).rect, doc.load_page(1).rect
        assert first.width > first.height
        assert second.height > second.width
    finally:
        doc.close()


def test_pages_are_consumed_lazily(tmp_path):
    """Memory used to grow ~50 MB per page because every page was kept."""
    live = []

    def pages():
        for i in range(5):
            image = page(400, 600)
            live.append(i)
            yield image
            # By the time the next page is requested, the writer has embedded
            # and released the previous one.
            assert len(live) == i + 1

    out = tmp_path / "out.pdf"
    count = scanned_images_to_pdf(pages(), str(out))
    assert count == 5
    assert fitz.open(str(out)).page_count == 5


def test_black_and_white_pages_are_stored_as_png(tmp_path):
    """B&W was saved as JPEG: blurry and larger at the same time."""
    image = np.full((600, 400, 3), 255, np.uint8)
    image[100:300, 100:300] = 0
    bw = apply_scan_mode(image, MODE_BW)

    out = tmp_path / "bw.pdf"
    scanned_images_to_pdf([bw], str(out), mode=MODE_BW)

    doc = fitz.open(str(out))
    try:
        images = doc.get_page_images(0)
        assert images, "no image embedded"
        info = doc.extract_image(images[0][0])
        assert info["ext"] == "png"
    finally:
        doc.close()


def test_colour_pages_are_stored_as_jpeg(tmp_path):
    out = tmp_path / "colour.pdf"
    scanned_images_to_pdf([page(400, 600)], str(out), mode=MODE_ORIGINAL)

    doc = fitz.open(str(out))
    try:
        info = doc.extract_image(doc.get_page_images(0)[0][0])
        assert info["ext"] in ("jpeg", "jpg")
    finally:
        doc.close()


def test_no_pages_is_an_error(tmp_path):
    with pytest.raises(ValueError):
        scanned_images_to_pdf([], str(tmp_path / "out.pdf"))


def test_failure_leaves_no_partial_pdf(tmp_path):
    out = tmp_path / "out.pdf"

    def pages():
        yield page(400, 600)
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        scanned_images_to_pdf(pages(), str(out))

    assert not out.exists()


# ── Export snapshot (#12) ─────────────────────────────────────────────────

def test_export_uses_the_snapshot_not_the_live_list(tmp_path):
    """Removing a page mid-export changed which pages reached the PDF.

    This models the fix: the worker is handed a snapshot taken on the main
    thread, so later edits to the live list cannot reach it.
    """
    live_pages = [page(400, 600, c) for c in ((0, 0, 255), (0, 255, 0), (255, 0, 0))]
    snapshot = list(live_pages)          # what start_scan() hands the worker

    live_pages.pop(0)                    # the user removes a page mid-export

    out = tmp_path / "out.pdf"
    count = scanned_images_to_pdf(iter(snapshot), str(out))

    assert count == 3
    assert fitz.open(str(out)).page_count == 3
