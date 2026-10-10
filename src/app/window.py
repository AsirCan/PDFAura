"""The web window: pywebview on Edge WebView2, the tray and drag and drop.

    python main.py --web [--debug-port N]

The page (web/, built into web/dist) is served by server.py and talks to
Python only through bridge.py; what comes back unasked travels as events
(events.py). This module owns everything about the native window itself.
Decisions behind it are measured in spikes/faz0/RAPOR.md.
"""
import logging
import os
import secrets
import sys
import threading

from src.app import native
from src.app.bridge import Bridge, file_info
from src.app.events import EventBus
from src.app.images import ImageCache, PdfPages
from src.core.config_manager import cfg
from src.core.lang_manager import _

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _asset(name):
    base = getattr(sys, "_MEIPASS", None) or APP_ROOT
    path = os.path.join(base, "assets", name)
    return path if os.path.isfile(path) else None


def _theme_palette(name):
    from src.gui.theme import get_theme
    return get_theme(name)


def _starting_theme():
    """The theme the window opens in, so its first frame is not white."""
    from src.gui.theme import resolve_theme_name, theme_preference
    return resolve_theme_name(theme_preference())


def _window_size():
    """The Tk window's rule: large, but never past the screen."""
    try:
        import webview
        screen = webview.screens[0]
        screen_w, screen_h = screen.width, screen.height
    except Exception:
        screen_w, screen_h = 1600, 1000
    width = min(1480, max(1100, screen_w - 60))
    height = min(920, max(720, screen_h - 80))
    return min(width, screen_w), min(height, screen_h)


class Shell:
    """The native side of the web window."""

    def __init__(self, debug_port=None):
        self.debug_port = debug_port
        self.token = secrets.token_urlsafe(16)
        self.images = ImageCache()
        self.pages = PdfPages()
        self.events = EventBus()
        self.version = _app_version()
        self.window = None
        self.bridge = Bridge(self)
        self._tray = None
        self._tray_notice_shown = False
        self._quitting = False

    # ── Life cycle ────────────────────────────────────────────────────
    def run(self):
        if not native.webview2_version():
            native.show_error("PDF Aura", _("webview2_missing").format(url=native.WEBVIEW2_DOWNLOAD))
            return 1

        import webview
        from src.app.server import make_app, web_root

        if not os.path.isfile(os.path.join(web_root(), "index.html")):
            native.show_error("PDF Aura", _("web_build_missing"))
            return 1

        webview.settings["ALLOW_FILE_URLS"] = False
        webview.settings["SHOW_DEFAULT_MENUS"] = False
        webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
        if self.debug_port:
            # Only for tests and --debug-port; never in a normal start.
            webview.settings["REMOTE_DEBUGGING_PORT"] = self.debug_port

        theme = _theme_palette(_starting_theme())
        width, height = _window_size()
        # A WSGI app as the url: pywebview serves it on 127.0.0.1 and a
        # random port, and adds none of its own routes.
        self.window = webview.create_window(
            "PDF Aura", url=make_app(self.token, self.images, self.pages), js_api=self.bridge,
            width=width, height=height, min_size=(960, 640), background_color=theme.palette.canvas)
        self.events.attach(self.window.run_js)
        self.window.events.closing += self._on_closing
        self.window.events.loaded += self._on_loaded
        self.window.events.shown += lambda: self.style_title_bar(_starting_theme())

        # A fixed profile folder: the default is a new %TEMP%\tmpXXXX per run,
        # left behind (~8 MB) by every crash. private_mode still keeps
        # cookies and storage out of it.
        storage = os.path.join(os.getenv("LOCALAPPDATA") or cfg.config_dir, "PDFAura", "WebView2")
        if cfg.get("close_to_tray", True):
            self._ensure_tray()
        webview.start(gui="edgechromium", private_mode=True, storage_path=storage, icon=_asset("app_icon.ico"),
                      debug=bool(self.debug_port))
        self._stop_tray()
        self.pages.close()
        return 0

    def quit(self):
        """Really quit: the tray's Quit and the page's own quit."""
        self._quitting = True
        self._stop_tray()
        if self.window is not None:
            self.window.destroy()

    def _on_closing(self):
        # Hide only if there is a tray icon to get the window back from;
        # otherwise quit rather than run on invisibly.
        if self._quitting or not cfg.get("close_to_tray", True) or not self._ensure_tray():
            self._stop_tray()
            return True
        self.window.hide()
        self._notify_running_in_tray()
        return False

    def _on_loaded(self):
        self._listen_for_drops()

    # ── Title bar ─────────────────────────────────────────────────────
    def style_title_bar(self, name):
        try:
            hwnd = int(self.window.native.Handle.ToInt64())
        except Exception:
            return
        theme = _theme_palette(name)
        native.style_title_bar(hwnd, theme.dark, theme.palette.canvas, theme.palette.text)

    # ── Drag and drop ─────────────────────────────────────────────────
    def _listen_for_drops(self):
        """Browsers do not tell a page where a dropped file lives; pywebview's
        DOM events carry the full path (pywebviewFullPath)."""
        from webview.dom import DOMEventHandler
        try:
            document = self.window.dom.document
            document.events.drop += DOMEventHandler(self._on_drop, prevent_default=True)
            document.events.dragover += DOMEventHandler(lambda _e: None, prevent_default=True, debounce=500)
        except Exception:
            logging.getLogger(__name__).exception("Drag and drop is not available")

    def _on_drop(self, event):
        files = (event.get("dataTransfer") or {}).get("files") or []
        paths = [item.get("pywebviewFullPath") for item in files if item.get("pywebviewFullPath")]
        if paths:
            self.events.emit("drop", {"files": [file_info(path) for path in paths]})

    # ── Tray ──────────────────────────────────────────────────────────
    def _tray_menu(self):
        import pystray
        return pystray.Menu(
            # default=True: clicking the icon opens the window too.
            pystray.MenuItem(_("tray_open"), lambda *_a: self.show(), default=True),
            pystray.MenuItem(_("tray_quit"), lambda *_a: self.quit()))

    def _ensure_tray(self):
        """Start the tray icon if needed. True if there is one."""
        if self._tray is not None:
            return True
        icon_path = _asset("app_icon.ico")
        if icon_path is None:
            return False
        try:
            import pystray
            from PIL import Image
            self._tray = pystray.Icon("pdfaura", Image.open(icon_path), "PDF Aura", self._tray_menu())
            threading.Thread(target=self._tray.run, daemon=True, name="pdfaura-tray").start()
            return True
        except Exception:
            logging.getLogger(__name__).exception("Tray icon could not be started")
            self._tray = None
            return False

    def _stop_tray(self):
        tray, self._tray = self._tray, None
        if tray is not None:
            try:
                tray.stop()
            except Exception:
                pass

    def _notify_running_in_tray(self):
        # Closing only hides the window; say so once, or it looks as if the
        # app quit while it keeps running next to the clock.
        if self._tray_notice_shown or self._tray is None:
            return
        self._tray_notice_shown = True
        try:
            self._tray.notify(_("tray_background_body"), _("tray_background_title"))
        except Exception:
            pass

    def show(self):
        if self.window is not None:
            self.window.show()
            self.window.restore()

    def language_changed(self):
        """The tray menu speaks the new language too."""
        if self._tray is not None:
            try:
                self._tray.menu = self._tray_menu()
                self._tray.update_menu()
            except Exception:
                pass


def _app_version():
    """AppVersion from setup.iss, the one place the version is written."""
    try:
        with open(os.path.join(APP_ROOT, "setup.iss"), encoding="utf-8") as f:
            for line in f:
                if line.startswith("AppVersion="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def run(debug_port=None):
    return Shell(debug_port).run()
