"""#25 Faz 3: the scanner's board for the web window (src/app/scanboard.py).

The page only describes what the user did; the board keeps the photos,
runs detection and the restore on threads and tells the page through
"scanner" events. These run it without a window, with a real session
folder and real exports.
"""
import io
import threading

import cv2
import numpy as np
import pytest
from PIL import Image
from pypdf import PdfReader

from src.app import scanner
from src.app.api import Api
from src.app.scanboard import PHOTO_MAX, ScannerBoard
from src.core.lang_manager import _
from src.core.scanner_session import ScannerSessionStore


def photo(w=600, h=800):
    """A dark desk with a light, slightly skewed sheet on it."""
    img = np.full((h, w, 3), (55, 70, 90), np.uint8)
    sheet = np.array([[100, 90], [500, 120], [520, 700], [80, 680]], np.int32)
    cv2.fillPoly(img, [sheet], (225, 232, 235))
    return img


def write_photo(path, w=600, h=800):
    cv2.imencode(".jpg", photo(w, h))[1].tofile(str(path))
    return str(path)


class Events:
    """The board's "scanner" events, in order."""

    def __init__(self):
        self.states = []
        self._changed = threading.Condition()

    def emit(self, name, data=None):
        assert name == "scanner"
        with self._changed:
            self.states.append(data)
            self._changed.notify_all()

    def wait(self, check, timeout=20):
        with self._changed:
            assert self._changed.wait_for(lambda: any(check(s) for s in self.states), timeout), self.states
            return next(s for s in self.states if check(s))


def idle_after(events, key):
    """The first state with nothing running and a notice with ``key``'s title."""
    return events.wait(lambda s: s["busy"] is None and s["notice"] and s["notice"]["message"].startswith(
        _(key).split("{")[0]))


@pytest.fixture
def store(tmp_path):
    return ScannerSessionStore(str(tmp_path / "session"))


@pytest.fixture
def events():
    return Events()


@pytest.fixture
def board(events, store):
    return ScannerBoard(events.emit, store=store)


@pytest.fixture
def photos(tmp_path):
    return [write_photo(tmp_path / f"fiş {i}.jpg") for i in range(3)]


def added(board, events, paths):
    state = board.add(paths)
    idle_after(events, "scanner_detect_done")
    return state


# ── Adding pages ──────────────────────────────────────────────────────────

def test_adding_photos_selects_the_first_and_finds_its_corners(board, events, photos):
    state = board.add(photos)
    assert [p["name"] for p in state["pages"]] == ["fiş 0.jpg", "fiş 1.jpg", "fiş 2.jpg"]
    assert state["current"] == 0 and state["busy"] == "detecting"
    assert state["output"].endswith(".pdf")
    assert state["notice"]["message"] == _("scanner_page_count").format(count=3)

    done = idle_after(events, "scanner_detect_done")
    assert done["notice"]["message"] == _("scanner_detect_done").format(count=3)
    for page in done["pages"]:
        assert page["version"] >= 1          # the thumbnails must be drawn again
        for (x, y), (ex, ey) in zip(page["corners"], [(100, 90), (500, 120), (520, 700), (80, 680)]):
            assert abs(x - ex) < 30 and abs(y - ey) < 30
    progress = [s["progress"] for s in events.states if s["progress"]]
    assert progress[-1] == {"current": 3, "total": 3}


def test_files_that_are_not_photos_are_left_out(board, tmp_path):
    broken = tmp_path / "bozuk.jpg"
    broken.write_bytes(b"not a photo")
    text = tmp_path / "not.txt"
    text.write_text("x")
    state = board.add([str(broken), str(text)])
    assert state["pages"] == [] and state["busy"] is None


def test_nothing_changes_the_pages_while_corners_are_detected(board, events, photos, monkeypatch):
    go_on = threading.Event()
    real = scanner.detect
    monkeypatch.setattr(scanner, "detect", lambda job: (go_on.wait(10), real(job))[1])
    state = board.add(photos[:1])
    uid = state["pages"][0]["uid"]
    refused = board.rotate(uid, 90)
    assert refused["notice"]["message"] == _("scanner_detect_busy")
    assert refused["pages"][0]["rotation"] == 0
    assert board.add(photos[1:])["notice"]["message"] == _("scanner_detect_busy")
    go_on.set()
    idle_after(events, "scanner_detect_done")
    assert board.rotate(uid, 90)["pages"][0]["rotation"] == 90


# ── Editing ───────────────────────────────────────────────────────────────

def test_move_rename_select_and_remove(board, events, photos):
    uids = [p["uid"] for p in added(board, events, photos)["pages"]]

    state = board.move(uids[2], 0)
    assert [p["uid"] for p in state["pages"]] == [uids[2], uids[0], uids[1]] and state["current"] == 0
    state = board.move(uids[2], 99)                      # clamped to the end
    assert [p["uid"] for p in state["pages"]] == [uids[0], uids[1], uids[2]] and state["current"] == 2

    before = state["pages"][1]["version"]
    state = board.rename(uids[1], "  Fatura\nEkim  ")
    assert state["pages"][1]["label"] == "Fatura Ekim"
    assert state["pages"][1]["version"] == before         # a name is not a new picture

    assert board.select(1)["current"] == 1
    assert board.select(7)["current"] == 1

    state = board.remove(uids[2])
    assert [p["uid"] for p in state["pages"]] == uids[:2] and state["current"] == 1
    state = board.remove(uids[1])
    assert state["current"] == 0
    assert board.remove("nope")["pages"][0]["uid"] == uids[0]


def test_rotating_turns_the_page_and_its_corners(board, events, photos):
    page = added(board, events, photos[:1])["pages"][0]
    state = board.rotate(page["uid"], 90)
    turned = state["pages"][0]
    assert (turned["width"], turned["height"], turned["rotation"]) == (800, 600, 90)
    assert turned["version"] > page["version"]
    assert board.rotate(page["uid"], 45)["pages"][0]["rotation"] == 90     # only quarter turns


def test_corners_from_the_page_are_rounded_and_kept_on_the_photo(board, events, photos):
    uid = added(board, events, photos[:1])["pages"][0]["uid"]
    state = board.set_corners(uid, [[-5, 10.4], [700, 0], [599.6, 900], [0, 799]])
    assert state["pages"][0]["corners"] == [[0, 10], [600, 0], [600, 800], [0, 799]]
    # Anything that is not four points is ignored.
    assert board.set_corners(uid, [[1, 1]])["pages"][0]["corners"] == state["pages"][0]["corners"]
    assert board.set_corners(uid, "0,0")["pages"][0]["corners"] == state["pages"][0]["corners"]
    reset = board.reset(uid)["pages"][0]["corners"]
    assert reset == [list(p) for p in scanner.default_corners(800, 600)]


def test_mode_and_output(board):
    assert board.set_mode("bw")["mode"] == "bw"
    assert board.set_mode("magic")["mode"] == "bw"
    assert board.set_output("  C:\\Belgeler\\tarama.pdf ")["output"] == "C:\\Belgeler\\tarama.pdf"


def test_clear_drops_the_pages_and_the_session(board, events, store, photos):
    added(board, events, photos)
    board.save_now()
    store.flush()
    state = board.clear()
    store.flush()
    assert state["pages"] == [] and state["current"] == -1 and state["output"] == ""
    assert store.load_meta() is None


# ── The session survives a restart ────────────────────────────────────────

def test_the_session_comes_back_as_it_was_left(board, events, store, photos):
    uids = [p["uid"] for p in added(board, events, photos)["pages"]]
    board.move(uids[2], 0)
    board.rename(uids[0], "Kapak")
    board.rotate(uids[1], 90)
    board.set_mode("grayscale")
    board.set_output("C:\\Belgeler\\tarama.pdf")
    board.select(1)
    board.save_now()
    assert board.flush()

    later = Events()
    again = ScannerBoard(later.emit, store=store)
    state = again.restore()
    assert state["busy"] == "restoring"
    restored = later.wait(lambda s: s["busy"] is None and s["pages"])
    assert [p["uid"] for p in restored["pages"]] == [uids[2], uids[0], uids[1]]
    assert restored["pages"][1]["label"] == "Kapak"
    assert restored["pages"][2]["rotation"] == 90
    assert (restored["mode"], restored["output"], restored["current"]) == ("grayscale", "C:\\Belgeler\\tarama.pdf", 1)
    assert restored["notice"]["message"] == _("scanner_session_restored").format(count=3)
    # Only once per run.
    assert again.restore()["busy"] is None and len(later.states) == 1


def test_saving_before_the_scanner_was_opened_creates_nothing(events, tmp_path):
    board = ScannerBoard(events.emit)
    board.save_now()
    assert board.flush() is True
    assert board._store is None


# ── Export ────────────────────────────────────────────────────────────────

def run_export(board, api):
    finished = threading.Event()
    result = {}
    callbacks = {
        "on_done": lambda outcome: (result.update(outcome=outcome), finished.set()),
        "on_failed": lambda title, message: (result.update(failed=message), finished.set()),
        "on_cancelled": lambda: (result.update(cancelled=True), finished.set()),
    }
    job = board.export(api.start_work, callbacks)
    if isinstance(job, dict):
        return job
    assert finished.wait(30)
    return result


def test_export_writes_one_page_per_photo_and_forgets_the_session(board, events, store, photos, tmp_path):
    added(board, events, photos)
    output = tmp_path / "çıktı" / "tarama.pdf"
    board.set_output(str(output))
    result = run_export(board, Api())
    assert result["outcome"].output_path == str(output)
    assert len(PdfReader(str(output)).pages) == 3
    final = events.states[-1]
    assert final["busy"] is None and final["output"] == "" and final["pages"]
    store.flush()
    assert store.load_meta() is None


def test_export_needs_pages_and_a_place_to_write(board, events, photos):
    assert run_export(board, Api()) == {"problem": _("scanner_no_image")}
    added(board, events, photos[:1])
    board.set_output("")
    assert run_export(board, Api()) == {"problem": _("err_set_output")}


def test_an_export_is_refused_while_corners_are_detected(board, events, photos, tmp_path, monkeypatch):
    go_on = threading.Event()
    real = scanner.detect
    monkeypatch.setattr(scanner, "detect", lambda job: (go_on.wait(10), real(job))[1])
    board.add(photos)
    board.set_output(str(tmp_path / "x.pdf"))
    assert run_export(board, Api()) == {"problem": _("scanner_detect_busy")}
    go_on.set()
    idle_after(events, "scanner_detect_done")


# ── Pictures for the page ─────────────────────────────────────────────────

def picture(data):
    return Image.open(io.BytesIO(data))


def test_pictures_of_a_page(board, events, tmp_path):
    big = write_photo(tmp_path / "big.jpg", 3000, 4000)
    uid = added(board, events, [big])["pages"][0]["uid"]

    full = picture(board.render(uid, "photo", 9999, 9999))
    assert full.format == "JPEG" and max(full.size) == PHOTO_MAX
    assert picture(board.render(uid, "photo", 400, 400)).size == (300, 400)

    thumb = picture(board.render(uid, "thumb", 180, 255))
    assert thumb.width <= 180 and thumb.height <= 255 and (thumb.width == 180 or thumb.height == 255)
    preview = picture(board.render(uid, "preview", 260, 370))
    assert preview.width <= 260 and preview.height <= 370

    assert board.render("missing", "photo", 100, 100) is None
    assert board.render(uid, "secret", 100, 100) is None
