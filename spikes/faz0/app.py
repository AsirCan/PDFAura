"""Faz 0 spike window for #25: what pywebview + Edge WebView2 can and cannot do.

    python spikes/faz0/app.py                    interactive: try each part by hand
    python spikes/faz0/app.py --bench OUT.json   run the measurements, write OUT.json, quit
    python spikes/faz0/app.py --minimal          empty page; only for startup/RAM measurements

Options:
    --debug-port N          open the DevTools protocol on 127.0.0.1:N (Playwright)
    --csp strict|eval       strict CSP (no eval) or one that allows 'unsafe-eval'
    --persistent-profile    keep cookies and web storage between runs (off: InPrivate)
    --tray                  closing the window hides it to the tray
    --import-core           load src/core + src/ai first, like the real app would
"""
import argparse
import base64
import json
import os
import secrets
import sys
import threading
import time
import winreg
from collections import OrderedDict

STARTED = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WEB = os.path.join(HERE, "web")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

# Same cap main.py applies; the core imports below load numpy.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import bottle  # noqa: E402  (ships with pywebview)
import webview  # noqa: E402
from webview.dom import DOMEventHandler  # noqa: E402

WEBVIEW2_CLIENT = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

CSP = {
    "strict": ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
               "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"),
    "eval": ("default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self'; "
             "img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; "
             "frame-ancestors 'none'"),
}


def log(*parts):
    print(*parts, flush=True)


def webview2_version():
    """The installed Evergreen WebView2 runtime's version, or None.

    pywebview only logs a warning and falls back to MSHTML (Internet
    Explorer 11) when this is missing, so the app has to check first.
    """
    for hive, prefix in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node"),
                         (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE"),
                         (winreg.HKEY_CURRENT_USER, r"SOFTWARE")):
        try:
            with winreg.OpenKey(hive, rf"{prefix}\{WEBVIEW2_CLIENT}") as key:
                version, _ = winreg.QueryValueEx(key, "pv")
        except OSError:
            continue
        if version and version != "0.0.0.0":
            return version
    return None


def windows_prefers_dark():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


class ImageCache:
    """Encoded images by unguessable key, capped by total size (LRU)."""

    def __init__(self, limit_bytes=96 * 2**20):
        self._items = OrderedDict()
        self._size = 0
        self._limit = limit_bytes
        self._lock = threading.Lock()

    def put(self, data, mime="image/jpeg"):
        key = secrets.token_urlsafe(12)
        with self._lock:
            self._items[key] = (data, mime)
            self._size += len(data)
            while self._size > self._limit and len(self._items) > 1:
                _old, (old_data, _m) = self._items.popitem(last=False)
                self._size -= len(old_data)
        return key

    def get(self, key):
        with self._lock:
            item = self._items.get(key)
            if item:
                self._items.move_to_end(key)
            return item


class Renderer:
    """PyMuPDF and OpenCV work. PyMuPDF must not run on two threads at once,
    and both js_api calls and HTTP requests arrive on threads of their own."""

    def __init__(self):
        self._lock = threading.Lock()
        self._doc = None
        self._photo = None

    def photo_jpeg(self, max_side, quality=85):
        import cv2
        from fixtures import photo_path
        with self._lock:
            if self._photo is None:
                self._photo = cv2.imread(photo_path())
            image = self._photo
            h, w = image.shape[:2]
            scale = min(1.0, max_side / max(h, w))
            if scale < 1.0:
                image = cv2.resize(image, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
            return buf.tobytes()

    def page_count(self):
        import fitz
        from fixtures import pdf_path
        with self._lock:
            if self._doc is None:
                self._doc = fitz.open(pdf_path())
            return len(self._doc)

    def thumb_jpeg(self, index, width):
        import fitz
        self.page_count()
        with self._lock:
            page = self._doc.load_page(index)
            zoom = width / page.rect.width
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            return pix.tobytes("jpeg", jpg_quality=80)


def make_server(token, cache, renderer, csp, start_page):
    app = bottle.Bottle()

    @app.hook("after_request")
    def _headers():
        bottle.response.set_header("Content-Security-Policy", csp)
        bottle.response.set_header("X-Content-Type-Options", "nosniff")
        bottle.response.set_header("Referrer-Policy", "no-referrer")

    def _image(data, mime="image/jpeg"):
        bottle.response.content_type = mime
        # Keys are never reused for different bytes.
        bottle.response.set_header("Cache-Control", "private, max-age=31536000, immutable")
        return data

    @app.get("/img/<tok>/<key>")
    def img(tok, key):
        item = cache.get(key) if secrets.compare_digest(tok, token) else None
        if not item:
            bottle.abort(404)
        return _image(*item)

    @app.get("/thumb/<tok>/<index:int>")
    def thumb(tok, index):
        if not secrets.compare_digest(tok, token):
            bottle.abort(404)
        width = int(bottle.request.query.get("w", 160))
        return _image(renderer.thumb_jpeg(index, width))

    @app.get("/")
    def index():
        return bottle.static_file(start_page, root=WEB)

    @app.get("/<path:path>")
    def static(path):
        return bottle.static_file(path, root=WEB)

    return app


class Api:
    """Everything the page may call. pywebview runs each call on its own thread."""

    def __init__(self, args, token, cache, renderer):
        self._args = args
        self._token = token
        self._cache = cache
        self._renderer = renderer
        self._window = None
        self._tray = None
        self._quitting = False
        self._drops = []

    def attach(self, window):
        self._window = window

    # ── Bridge ─────────────────────────────────────────────────────────
    def config(self):
        return {"bench": bool(self._args.bench)}

    def ready(self):
        log(f"READY {time.time():.4f}")
        return {"since_start_ms": round((time.time() - STARTED) * 1000)}

    def ping(self, payload=None):
        return payload

    def info(self):
        from webview.platforms import winforms
        return {
            "renderer": winforms.renderer,
            "webview2": webview2_version(),
            "pywebview": _pywebview_version(),
            "windows_dark": windows_prefers_dark(),
            "csp": self._args.csp,
            "pid": os.getpid(),
        }

    def samples(self):
        """One real UI string per language, raw (no Tk RTL wrapping)."""
        from src.core.lang_manager import LANGUAGES, RTL_LANGUAGES, _STRINGS
        return [{"code": code, "name": name, "rtl": code in RTL_LANGUAGES,
                 "text": _STRINGS.get(code, {}).get("preview_empty_title", "")}
                for code, name in LANGUAGES.items()]

    def try_evaluate_js(self):
        """pywebview's evaluate_js wraps the script in eval(); see if CSP allows it."""
        try:
            return {"ok": True, "value": self._window.evaluate_js("21 * 2")}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}

    # ── Native dialogs ─────────────────────────────────────────────────
    def pick_files(self):
        result = self._window.create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=True,
            file_types=("PDF (*.pdf)", "Resimler (*.jpg;*.jpeg;*.png)", "Tüm dosyalar (*.*)"))
        return list(result or [])

    def pick_folder(self):
        return list(self._window.create_file_dialog(webview.FileDialog.FOLDER) or [])

    def pick_save(self, directory="", name="cikti.pdf"):
        result = self._window.create_file_dialog(webview.FileDialog.SAVE, directory=directory, save_filename=name,
                                                  file_types=("PDF (*.pdf)",))
        if isinstance(result, (list, tuple)):
            return result[0] if result else None
        return result

    # ── Drag and drop ──────────────────────────────────────────────────
    def on_drop(self, event):
        files = event.get("dataTransfer", {}).get("files", [])
        paths = [f.get("pywebviewFullPath") for f in files]
        self._drops.append(paths)
        log(f"DROP {json.dumps(paths, ensure_ascii=False)}")
        self._window.run_js(f"window.spike && window.spike.dropped({json.dumps(paths)})")

    def drops(self):
        return self._drops

    # ── Image transport ────────────────────────────────────────────────
    def photo(self, mode, max_side):
        t0 = time.perf_counter()
        data = self._renderer.photo_jpeg(max_side)
        py_ms = (time.perf_counter() - t0) * 1000
        if mode == "data":
            src = "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
        else:
            src = f"/img/{self._token}/{self._cache.put(data)}"
        return {"src": src, "bytes": len(data), "py_ms": round(py_ms, 1)}

    def page_count(self):
        return self._renderer.page_count()

    def thumb(self, index, width):
        data = self._renderer.thumb_jpeg(index, width)
        return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")

    def thumb_base(self):
        return f"/thumb/{self._token}/"

    # ── Python -> JS events ────────────────────────────────────────────
    def burst(self, count):
        """Push `count` progress events with run_js, which does not wait."""
        t0 = time.perf_counter()
        for i in range(count):
            self._window.run_js(f"window.spike.progress({i + 1},{count})")
        return round((time.perf_counter() - t0) * 1000, 1)

    def burst_blocking(self, count):
        """Same with evaluate_js, which waits for each result."""
        t0 = time.perf_counter()
        for i in range(count):
            self._window.evaluate_js(f"window.spike.progress({i + 1},{count})")
        return round((time.perf_counter() - t0) * 1000, 1)

    # ── Tray ───────────────────────────────────────────────────────────
    def on_closing(self):
        if not self._args.tray or self._quitting:
            return True
        self._ensure_tray()
        self._window.hide()
        log("HIDDEN")
        return False            # cancels the close

    def _ensure_tray(self):
        if self._tray:
            return
        import pystray
        from PIL import Image
        image = Image.open(os.path.join(ROOT, "assets", "icon.png"))
        menu = pystray.Menu(pystray.MenuItem("Aç", lambda *_: self.show_from_tray(), default=True),
                            pystray.MenuItem("Çık", lambda *_: self.quit()))
        self._tray = pystray.Icon("pdfaura-faz0", image, "PDF Aura (Faz 0)", menu)
        threading.Thread(target=self._tray.run, daemon=True).start()

    def show_from_tray(self):
        self._window.show()
        self._window.restore()
        log("SHOWN-FROM-TRAY")

    def quit(self):
        self._quitting = True
        if self._tray:
            self._tray.stop()
        self._window.destroy()

    # ── Results ────────────────────────────────────────────────────────
    def report(self, results):
        results["info"] = self.info()
        results["evaluate_js"] = self.try_evaluate_js()
        if self._args.bench:
            with open(self._args.bench, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            log(f"REPORT {self._args.bench}")
            threading.Timer(0.2, self.quit).start()
        return True


def _pywebview_version():
    try:
        from importlib.metadata import version
        return version("pywebview")
    except Exception:
        return "?"


def import_core():
    """The modules the real app's screens load at startup today."""
    import src.core.compress, src.core.convert, src.core.edit, src.core.merge  # noqa: E401,F401
    import src.core.metainfo, src.core.ocr, src.core.security, src.core.signature  # noqa: E401,F401
    import src.core.split, src.core.batch, src.core.document_scanner  # noqa: E401,F401
    import src.ai.speech_recognizer, src.ai.intent_parser, src.ai.action_runner  # noqa: E401,F401


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench")
    parser.add_argument("--minimal", action="store_true")
    parser.add_argument("--debug-port", type=int)
    parser.add_argument("--csp", choices=sorted(CSP), default="strict")
    parser.add_argument("--persistent-profile", action="store_true")
    parser.add_argument("--tray", action="store_true")
    parser.add_argument("--import-core", action="store_true")
    args = parser.parse_args()

    version = webview2_version()
    if not version:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None, "Microsoft Edge WebView2 Runtime bulunamadı.\n"
                  "https://go.microsoft.com/fwlink/p/?LinkId=2124703", "PDF Aura", 0x10)
        sys.exit(1)

    if args.import_core:
        import_core()

    if args.debug_port:
        webview.settings["REMOTE_DEBUGGING_PORT"] = args.debug_port
    webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False

    token = secrets.token_urlsafe(16)
    cache = ImageCache()
    renderer = Renderer()
    api = Api(args, token, cache, renderer)
    page = "minimal.html" if args.minimal else "index.html"
    server = make_server(token, cache, renderer, CSP[args.csp], page)

    # A WSGI app as the url: pywebview serves it on 127.0.0.1 and a random
    # port, and adds none of its own routes (no CORS-open /js_api endpoint).
    window = webview.create_window("PDF Aura", url=server, js_api=api, width=1280, height=820,
                                   min_size=(900, 600), background_color="#F6F7F9")
    api.attach(window)
    window.events.closing += api.on_closing
    window.events.shown += lambda: log(f"SHOWN {time.time():.4f}")

    def register_drop():
        # pywebview's DOM API registers listeners through evaluate_js, so this
        # also shows whether that survives the CSP.
        window.events.loaded -= register_drop
        try:
            window.dom.document.events.drop += DOMEventHandler(api.on_drop, prevent_default=True)
            window.dom.document.events.dragover += DOMEventHandler(lambda e: None, prevent_default=True,
                                                                   debounce=500)
            log("DROP-HANDLER ok")
        except Exception as exc:
            log(f"DROP-HANDLER failed: {type(exc).__name__}: {exc}"[:300])

    if not args.minimal:
        window.events.loaded += register_drop

    # A fixed folder: pywebview's default is a new %TEMP%	mpXXXX per run,
    # which a crash or a killed process leaves behind (~8 MB each).
    # private_mode still keeps cookies and storage out of it.
    storage = os.path.join(os.getenv("LOCALAPPDATA", ROOT), "PDFAura-faz0", "WebView2")
    webview.start(gui="edgechromium", private_mode=not args.persistent_profile,
                  storage_path=storage, debug=False)


if __name__ == "__main__":
    main()
