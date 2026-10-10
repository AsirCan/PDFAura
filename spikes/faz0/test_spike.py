"""Faz 0 checks against the real spike window (Windows, WebView2 installed).

    python -m pytest spikes/faz0 -q

Not part of the main suite (pytest.ini only collects tests/). Each test
starts spikes/faz0/app.py with the DevTools port open and drives it with
Playwright over CDP, the way the E2E layer in #25 would.
"""
import ctypes
import os
import socket
import subprocess
import sys
import threading
import time

import pytest
import win32con
import win32gui
import win32process

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

playwright = pytest.importorskip("playwright.sync_api")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(predicate, timeout=15, step=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    raise TimeoutError(predicate)


def top_windows(pid, cls=None, title=None, visible=True):
    found = []

    def cb(hwnd, _):
        if win32process.GetWindowThreadProcessId(hwnd)[1] != pid:
            return
        if visible and not win32gui.IsWindowVisible(hwnd):
            return
        if cls and win32gui.GetClassName(hwnd) != cls:
            return
        if title is not None and win32gui.GetWindowText(hwnd) != title:
            return
        found.append(hwnd)
    win32gui.EnumWindows(cb, None)
    return found


class Spike:
    def __init__(self, *args):
        self.page = None
        self.port = free_port()
        self.lines = []
        self.proc = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "app.py"), "--debug-port", str(self.port), *args],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", env=dict(os.environ, PYTHONUNBUFFERED="1"))
        threading.Thread(target=self._read, daemon=True).start()
        self._pw = playwright.sync_playwright().start()
        try:
            # A cold runner takes a while to start Python and WebView2, and
            # CDP answers before WebView2 has created the page.
            self.browser = wait_for(self._connect, timeout=120, step=0.2)
            self.page = wait_for(lambda: self.browser.contexts and self.browser.contexts[0].pages
                                 and self.browser.contexts[0].pages[0], timeout=120)
            # Not page.wait_for_function: Playwright evaluates its predicate
            # with eval() in the page, which the CSP blocks until pywebview's
            # bridge is in. page.evaluate goes through CDP and is not affected.
            self.wait_js("!!(window.pywebview && window.pywebview.api && window.pywebview.api.ping)")
        except BaseException:
            # A half-opened window must not leave Playwright running: every
            # later test would fail with "Sync API inside the asyncio loop".
            self.close()
            raise

    def wait_js(self, expression, timeout=15):
        def check():
            try:
                return self.page.evaluate(expression)
            except Exception:       # mid-navigation
                return None
        return wait_for(check, timeout)

    def _read(self):
        for line in self.proc.stdout:
            self.lines.append(line.rstrip())

    def _connect(self):
        try:
            return self._pw.chromium.connect_over_cdp(f"http://127.0.0.1:{self.port}")
        except Exception:
            return None

    @property
    def hwnd(self):
        return wait_for(lambda: top_windows(self.proc.pid, title="PDF Aura", visible=False))[0]

    def close(self):
        try:
            self.page.evaluate("void pywebview.api.quit()")     # do not wait on the promise
        except Exception:
            pass   # also when there was no page yet
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.proc.pid)], capture_output=True)
        self._pw.stop()


@pytest.fixture
def spike(request):
    marker = request.node.get_closest_marker("spike_args")
    s = Spike(*(marker.args if marker else ()))
    yield s
    s.close()



# ── Bridge and engine ──────────────────────────────────────────────────

def test_playwright_drives_the_real_window_over_cdp(spike):
    assert spike.page.evaluate("pywebview.api.ping({n: 7})") == {"n": 7}
    info = spike.page.evaluate("pywebview.api.info()")
    assert info["renderer"] == "edgechromium"
    spike.wait_js("window.__wired === true")      # buttons get their handlers after the first calls
    spike.page.click("#ping-btn")
    spike.wait_js("document.querySelector('#ping-out').textContent.includes('median')")


def test_csp_blocks_inline_scripts(spike):
    blocked = spike.page.evaluate("""async () => {
        const s = document.createElement('script');
        s.textContent = 'window.__inline = 1';
        document.body.append(s);
        await new Promise(r => setTimeout(r, 50));
        return window.__inline !== 1;
    }""")
    assert blocked


def test_eval_is_blocked_only_until_pywebview_injects_its_bridge():
    """A finding, not a wish: WebView2 stops enforcing the CSP's eval ban
    once the host has run pywebview's injected script, so a lint rule, not
    the CSP, has to keep eval/new Function out of our code."""
    s = Spike("--minimal")
    try:
        assert s.page.evaluate("window.__evalEarly") == "blocked"
        assert s.page.evaluate("(() => { try { eval('1'); return 'allowed' } catch (e) { return 'blocked' } })()") \
            == "allowed"
    finally:
        s.close()


def test_pywebview_silently_falls_back_to_internet_explorer_without_webview2():
    """With the WebView2 registry keys hidden, pywebview picks MSHTML and only
    logs a warning; app.webview2_version() reports None so the app can stop."""
    code = r"""
import winreg
real = winreg.OpenKey
def fake(key, sub, *a, **k):
    if "EdgeUpdate" in sub:
        raise OSError("hidden for the test")
    return real(key, sub, *a, **k)
winreg.OpenKey = fake
import sys; sys.argv = ["x"]
sys.path.insert(0, r"%s")
import app
from webview.platforms import winforms
print(winforms.renderer, app.webview2_version())
""" % HERE
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert out.stdout.split()[-2:] == ["mshtml", "None"], out.stdout + out.stderr


# ── Native dialogs ─────────────────────────────────────────────────────

FILE_NAME_BOXES = (1148, 1152, 1001)     # cmb13 (open), edt2 (folder), edt1 (save)


def _file_name_box(dialog):
    """The dialog's file name box: an Edit whose own id is the file name
    control's. Matching an ancestor's id instead picked the breadcrumb bar
    on the CI runner, whose toolbar shares the save dialog's 1001, so the
    typed path went into the address bar and cikti.pdf in Documents
    was saved."""
    found = []

    def cb(hwnd, _):
        if (win32gui.GetClassName(hwnd) == "Edit" and win32gui.IsWindowVisible(hwnd)
                and win32gui.GetDlgCtrlID(hwnd) in FILE_NAME_BOXES):
            found.append(hwnd)
    win32gui.EnumChildWindows(dialog, cb, None)
    return found[0] if found else None


def _box_length(box):
    # WM_GETTEXTLENGTH needs no buffer, so unlike WM_GETTEXT it answers
    # correctly across processes whatever the text's encoding.
    return ctypes.windll.user32.SendMessageW(box, win32con.WM_GETTEXTLENGTH, 0, 0)


def _fill_file_dialog(pid, text, default=""):
    """Type into the dialog's file name box and press its OK button.

    A save dialog fills in its default name a moment after its box
    appears -- on the CI runner, after the test had typed, so it saved to
    Documents. Wait for the default first (by its length), then type until
    the box holds the text."""
    dialog = wait_for(lambda: top_windows(pid, cls="#32770"))[0]
    box = wait_for(lambda: _file_name_box(dialog))     # its controls appear after the window
    if default:
        try:
            wait_for(lambda: _box_length(box) == len(default), timeout=10)
        except TimeoutError:
            pass

    def typed():
        win32gui.SendMessage(box, win32con.WM_SETTEXT, 0, text)
        time.sleep(0.3)
        return _box_length(box) == len(text)
    wait_for(typed, timeout=10, step=0)
    win32gui.SendMessage(win32gui.GetDlgItem(dialog, 1), win32con.BM_CLICK, 0, 0)    # IDOK


def _pick(spike, call, text, default=""):
    # The trailing 0: page.evaluate would otherwise wait on the promise,
    # which only settles once the dialog this test has to fill is closed.
    spike.page.evaluate(f"window.__done = false; pywebview.api.{call}()"
                        ".then(v => { window.__picked = v; window.__done = true; }); 0")
    _fill_file_dialog(spike.proc.pid, text, default)
    spike.wait_js("window.__done")
    return spike.page.evaluate("window.__picked")


def test_open_dialog_returns_full_paths(spike, tmp_path):
    first, second = tmp_path / "bir.pdf", tmp_path / "iki.pdf"
    first.write_bytes(b"%PDF-1.4\n")
    second.write_bytes(b"%PDF-1.4\n")
    picked = _pick(spike, "pick_files", f'"{first}" "{second}"')
    assert sorted(picked) == sorted([str(first), str(second)])


def test_folder_dialog_returns_the_folder(spike, tmp_path):
    picked = _pick(spike, "pick_folder", str(tmp_path))
    assert [os.path.normcase(p) for p in picked] == [os.path.normcase(str(tmp_path))]


def test_save_dialog_returns_the_target(spike, tmp_path):
    target = tmp_path / "çıktı.pdf"
    picked = _pick(spike, "pick_save", str(target), default="cikti.pdf")     # app.py's save_filename
    assert os.path.normcase(picked) == os.path.normcase(str(target))


# ── Tray ───────────────────────────────────────────────────────────────

@pytest.mark.spike_args("--tray")
def test_close_hides_to_the_tray_and_open_brings_it_back(spike):
    hwnd = spike.hwnd
    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    wait_for(lambda: not win32gui.IsWindowVisible(hwnd))
    assert spike.proc.poll() is None, "closing quit the app instead of hiding it"
    wait_for(lambda: "HIDDEN" in spike.lines)
    spike.page.evaluate("pywebview.api.show_from_tray()")
    wait_for(lambda: win32gui.IsWindowVisible(hwnd))
    print("foreground after show:", win32gui.GetForegroundWindow() == hwnd)


# ── Drag and drop from Explorer ────────────────────────────────────────
# Checked by hand (see RAPOR.md): a synthetic OLE drag from pywin32's
# DoDragDrop never got its loop going, so there is no automated test.

def test_the_drop_handler_registers_under_the_csp(spike):
    """pywebview's DOM API (which carries the full paths of dropped files)
    registers its listener through evaluate_js; it must work here."""
    wait_for(lambda: "DROP-HANDLER ok" in spike.lines)
