"""#25 Faz 1: the scanner's model in src/app/scanner.py, without the Tk tab.

Rotation, default corners, detection fallback, the saved session and the
export were all inside a 1,900-line tab; these pin their behaviour down so
the web window can reuse them.
"""
import os
import site
import subprocess
import sys

import cv2
import numpy as np
import pytest

from conftest import ROOT
from src.app import scanner
from src.core import document_scanner


def photo(w=600, h=800):
    """A dark desk with a light, slightly skewed sheet on it."""
    img = np.full((h, w, 3), (55, 70, 90), np.uint8)
    sheet = np.array([[100, 90], [500, 120], [520, 700], [80, 680]], np.int32)
    cv2.fillPoly(img, [sheet], (225, 232, 235))
    return img


def page_for(img, path="p.jpg"):
    h, w = img.shape[:2]
    return scanner.ScanPage(path, img, scanner.default_corners(h, w))


# ── Small pieces ──────────────────────────────────────────────────────────

def test_mode_ids_match_the_core():
    """src.app.scanner repeats them so the window can open without OpenCV."""
    assert [m for m, _k in scanner.MODES] == [
        document_scanner.MODE_ORIGINAL, document_scanner.MODE_CLEAN_DOC, document_scanner.MODE_BW,
        document_scanner.MODE_GRAYSCALE, document_scanner.MODE_SHARP]


def test_default_corners_sit_inside_the_photo():
    assert scanner.default_corners(800, 600) == [(20, 20), (579, 20), (579, 779), (20, 779)]
    assert scanner.default_corners(10, 10) == [(0, 0), (9, 0), (9, 9), (0, 9)]


def test_page_labels_are_one_clean_line():
    assert scanner.clean_label("  Fatura\n\tEkim\x00 ") == "Fatura Ekim"
    assert len(scanner.clean_label("x" * 500)) == scanner.PAGE_LABEL_MAX


@pytest.mark.parametrize("corners, ok", [
    ([[0, 0], [1, 0], [1, 1], [0, 1]], True),
    ([[0, 0], [1, 0], [1, 1]], False),
    ([[0, 0], [1, 0], [1, 1], [0, float("nan")]], False),
    ([[0, 0], [1, 0], [1, 1], [True, 1]], False),
    ("0,0,1,1", False),
])
def test_corner_lists_are_validated(corners, ok):
    assert scanner.valid_corners(corners) is ok


# ── Rotation ──────────────────────────────────────────────────────────────

def test_rotating_turns_the_photo_and_its_corners():
    page = page_for(photo())
    page.corners = [(100, 90), (500, 120), (520, 700), (80, 680)]
    scanner.rotate(page, 90)
    assert page.rotation == 90 and page.display_shape == (600, 800)
    # The old bottom-left becomes the new top-left (corners[0] must stay top-left).
    assert page.corners[0] == (800 - 680, 80)
    scanner.rotate(page, -90)
    assert page.rotation == 0 and page.display_shape == (800, 600)
    assert page.corners == [(100, 90), (500, 120), (520, 700), (80, 680)]


def test_four_quarter_turns_change_nothing():
    page = page_for(photo())
    before = list(page.corners)
    for _i in range(4):
        scanner.rotate(page, 90)
    assert page.rotation == 0 and page.corners == before
    assert np.array_equal(page.display_image, page.cv_image)


def test_the_original_pixels_are_never_changed():
    """Pages are saved by uid; changed pixels would need a new uid."""
    img = photo()
    page = page_for(img)
    original = img.copy()
    scanner.rotate(page, 90)
    page.reset_corners()
    assert np.array_equal(page.cv_image, original)


# ── Loading and detection ─────────────────────────────────────────────────

def test_a_photo_with_a_unicode_path_loads(tmp_path):
    path = tmp_path / "fiş ğüşıöç.jpg"
    ok, buf = cv2.imencode(".jpg", photo())
    buf.tofile(str(path))
    page = scanner.load_photo(str(path))
    assert page is not None and page.display_shape == (800, 600)
    assert page.corners == scanner.default_corners(800, 600)


def test_an_unreadable_file_is_skipped(tmp_path):
    bad = tmp_path / "not a photo.jpg"
    bad.write_bytes(b"nope")
    assert scanner.load_photo(str(bad)) is None


def test_detection_finds_the_sheet(tmp_path):
    path = tmp_path / "sheet.png"
    cv2.imencode(".png", photo())[1].tofile(str(path))
    page = scanner.load_photo(str(path))
    corners, found = scanner.detect(scanner.detection_job(page, str(path)))
    assert found
    for (x, y), (ex, ey) in zip(corners, [(100, 90), (500, 120), (520, 700), (80, 680)]):
        assert abs(x - ex) < 30 and abs(y - ey) < 30


def test_a_rotated_page_is_detected_from_its_rotated_pixels(tmp_path):
    page = page_for(photo())
    scanner.rotate(page, 90)
    job = scanner.detection_job(page, "unused-because-rotated.png")
    assert job["path"] is None and job["image"].shape[:2] == (600, 800)
    corners, found = scanner.detect(job)
    assert found and len(corners) == 4


def test_a_failed_detection_still_gives_handles():
    job = {"page": None, "path": "missing-file.png", "image": None, "shape": (100, 200)}
    corners, found = scanner.detect(job)
    assert not found and corners == scanner.default_corners(100, 200)


# ── Session ───────────────────────────────────────────────────────────────

class FakeStore:
    def __init__(self, images):
        self.images = images

    def read_image(self, uid):
        return self.images.get(uid)

    def image_path(self, uid):
        return f"session/{uid}.png"


def test_a_session_round_trips():
    pages = [page_for(photo(), "a.jpg"), page_for(photo(400, 300), "b.jpg")]
    scanner.rotate(pages[1], 90)
    pages[1].label = "Arka yüz"
    meta = scanner.session_meta(pages, scanner.MODE_BW, "C:/out.pdf", 1)
    assert meta["scan_mode"] == "bw" and meta["current_index"] == 1 and meta["corner_order"] == "display"

    store = FakeStore({p.uid: p.cv_image for p in pages})
    restored, skipped = scanner.restore_pages(store, meta)
    assert skipped == 0 and [p.uid for p in restored] == [p.uid for p in pages]
    assert restored[1].rotation == 90 and restored[1].label == "Arka yüz"
    assert restored[1].corners == [tuple(c) for c in pages[1].corners]
    assert restored[1].display_shape == pages[1].display_shape


def test_pages_whose_image_no_longer_matches_are_skipped():
    page = page_for(photo())
    meta = scanner.session_meta([page], scanner.MODE_ORIGINAL, "", 0)
    store = FakeStore({page.uid: photo(300, 300)})        # different size
    assert scanner.restore_pages(store, meta) == ([], 1)


def test_old_sessions_get_their_corners_started_at_the_top_left():
    page = page_for(photo())
    meta = scanner.session_meta([page], scanner.MODE_ORIGINAL, "", 0)
    del meta["corner_order"]
    meta["pages"][0]["corners"] = [[500, 120], [520, 700], [80, 680], [100, 90]]
    restored, _skipped = scanner.restore_pages(FakeStore({page.uid: page.cv_image}), meta)
    assert restored[0].corners[0] == (100, 90)


# ── Export and pictures ───────────────────────────────────────────────────

def test_export_writes_one_page_per_snapshot_entry(tmp_path):
    import fitz
    pages = [page_for(photo()), page_for(photo())]
    shots = scanner.snapshot(pages)
    pages.clear()                     # the live list may change; the export must not care
    out = str(tmp_path / "sub" / "taranan.pdf")
    outcome = scanner.export_pdf(None, shots, out, scanner.MODE_CLEAN_DOC)
    assert outcome.output_path == out and outcome.tone == "success"
    with fitz.open(out) as doc:
        assert len(doc) == 2


def test_pictures_have_the_requested_sizes():
    page = page_for(photo())
    fitted = scanner.fitted(page, 180, 255)
    assert fitted.width <= 180 and fitted.height <= 255 and (fitted.width == 180 or fitted.height == 255)
    assert max(scanner.preview(page, scanner.MODE_BW, 260, 370).size) <= 370
    assert scanner.to_pil(page.display_image, (60, 80)).size == (60, 80)


# ── Startup cost ──────────────────────────────────────────────────────────

HEAVY = ("cv2", "numpy", "pypdf", "fitz", "pymupdf", "pytesseract", "sounddevice", "soundfile",
         "pystray", "onnxruntime", "faster_whisper", "reportlab", "pdf2docx")


def test_opening_the_window_loads_no_heavy_library():
    """Each of these used to be imported at startup (#25: 0.56 s of the
    window's import time). They load when a tool first needs them."""
    code = ("import sys; import src.app.window; "
            f"print(' '.join(m for m in {HEAVY!r} if m in sys.modules))")
    # conftest moved APPDATA, which is also where pip's --user packages live.
    env = dict(os.environ, PYTHONUSERBASE=site.getuserbase())
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                         env=env, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == []
