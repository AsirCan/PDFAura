"""#25 layer 4: the real web window (python main.py --web), driven over CDP.

    python -m pytest -m e2e

Not part of the default run (pytest.ini): each test opens a WebView2
window. Needs web/dist (cd web && npm ci && npm run build) and Playwright
(no browser download: it attaches to WebView2 over CDP).

Drag and drop itself cannot be automated (synthetic mouse input never
drives Windows' DoDragDrop, see spikes/faz0/RAPOR.md); the tests hand the
page the same "drop" event Python sends after a real drop.
"""
import json
import os
import site
import socket
import subprocess
import sys
import time

import pytest

from conftest import ROOT, make_pdf

pytestmark = pytest.mark.e2e
playwright = pytest.importorskip("playwright.sync_api")

if not os.path.isfile(os.path.join(ROOT, "web", "dist", "index.html")):
    pytest.skip("web/dist is not built (cd web && npm ci && npm run build)", allow_module_level=True)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Window:
    def __init__(self, appdata, language="tr", theme="paper", tray=False):
        folder = os.path.join(appdata, "PDFAura")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"language": language, "theme": theme, "close_to_tray": tray, "sound_enabled": False}, f)
        self.port = free_port()
        # APPDATA moved, so pip's --user packages must be pointed at again.
        env = dict(os.environ, APPDATA=appdata, PYTHONUSERBASE=site.getuserbase(), PYTHONUNBUFFERED="1")
        self.proc = subprocess.Popen([sys.executable, "main.py", "--web", "--debug-port", str(self.port)],
                                     cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._pw = playwright.sync_playwright().start()
        self.requests = []
        browser = self._wait(self._connect, 40)
        self.page = browser.contexts[0].pages[0]
        self.page.on("request", lambda request: self.requests.append(request.url))
        self.wait("!!document.querySelector('.shell')")

    def _connect(self):
        try:
            return self._pw.chromium.connect_over_cdp(f"http://127.0.0.1:{self.port}")
        except Exception:
            return None

    @staticmethod
    def _wait(check, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            value = check()
            if value:
                return value
            time.sleep(0.1)
        raise TimeoutError(check)

    def wait(self, expression, timeout=15):
        """Poll with page.evaluate: Playwright's wait_for_function uses eval(),
        which the page's CSP blocks."""
        def check():
            try:
                return self.page.evaluate(expression)
            except Exception:
                return None
        return self._wait(check, timeout)

    def drop(self, *paths):
        files = [{"path": p, "name": os.path.basename(p), "folder": os.path.dirname(p), "ext": ".pdf",
                  "kind": "pdf", "size": os.path.getsize(p), "exists": True, "is_dir": False} for p in paths]
        self.page.evaluate("files => window.__aura.emit('drop', {files})", files)

    def close(self):
        try:
            self.page.evaluate("void window.pywebview.api.quit()")
        except Exception:
            pass
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.proc.pid)], capture_output=True)
        self._pw.stop()


@pytest.fixture
def window(tmp_path):
    opened = Window(str(tmp_path / "appdata"))
    yield opened
    opened.close()


def test_the_window_opens_with_every_tool(window):
    labels = window.page.evaluate("[...document.querySelectorAll('.nav .nav-item span')].map(s => s.textContent)")
    assert labels == ["Sıkıştır", "Düzenle", "Belge Tara", "Dönüştür", "Güvenlik", "Gelişmiş", "Toplu İşlemler"]
    assert window.page.evaluate("document.documentElement.dataset.theme") == "paper"


def test_keyboard_switches_tools(window):
    window.page.keyboard.press("Control+4")
    window.wait("document.querySelector('h1').textContent.length > 0")
    assert window.page.evaluate("document.querySelector('.nav-item.selected span').textContent") == "Dönüştür"


def test_compress_runs_end_to_end(window, tmp_path):
    source = make_pdf(tmp_path / "rapor.pdf", pages=3)
    window.drop(source)
    window.wait("document.querySelector('#compress-output').value.endsWith('rapor_sikistirilmis.pdf')")
    window.page.evaluate("document.querySelector('.footer .btn-primary').click()")
    window.wait("!!document.querySelector('.feedback.tone-success')", 30)
    assert os.path.isfile(tmp_path / "rapor_sikistirilmis.pdf")
    # The preview drew the page through the app's own server.
    window.wait("document.querySelector('.preview img')?.complete")


def test_language_changes_without_a_restart(window):
    window.page.keyboard.press("Control+,")
    window.wait("!!document.querySelector('#settings-language')")
    window.page.select_option("#settings-language", "en")
    window.wait("document.querySelector('.nav .nav-item span').textContent === 'Compress'")
    window.page.select_option("#settings-language", "ar")
    window.wait("document.documentElement.dir === 'rtl'")


def test_theme_cards_switch_the_theme_at_once(window):
    window.page.keyboard.press("Control+,")
    window.wait("document.querySelectorAll('.theme-card').length === 3")
    window.page.evaluate("document.querySelectorAll('.theme-card')[1].click()")
    window.wait("document.documentElement.dataset.theme === 'night'")


def test_nothing_leaves_the_computer(window, tmp_path):
    """README: documents are never uploaded anywhere. Every request the page
    makes goes to the app's own server on 127.0.0.1."""
    window.drop(make_pdf(tmp_path / "a.pdf"))
    window.wait("document.querySelector('.preview img')?.complete")
    outside = [url for url in window.requests if not url.startswith("http://127.0.0.1:")]
    assert window.requests and outside == []


def _top_window(pid):
    import win32gui
    import win32process
    found = []

    def visit(hwnd, _):
        if win32gui.GetWindowText(hwnd) == "PDF Aura" and win32process.GetWindowThreadProcessId(hwnd)[1] == pid:
            found.append(hwnd)
    win32gui.EnumWindows(visit, None)
    return found[0] if found else None


def test_closing_hides_to_the_tray_and_quit_really_quits(tmp_path):
    import win32con
    import win32gui
    window = Window(str(tmp_path / "appdata"), tray=True)
    try:
        hwnd = window._wait(lambda: _top_window(window.proc.pid))
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        window._wait(lambda: not win32gui.IsWindowVisible(hwnd))
        assert window.proc.poll() is None, "closing must only hide the window"
    finally:
        window.close()
    assert window.proc.poll() is not None
