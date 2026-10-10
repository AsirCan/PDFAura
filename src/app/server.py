"""The web window's own local HTTP app: the built page and its pictures.

It is handed to pywebview as the window's ``url``. pywebview then serves it
on 127.0.0.1 and a random port and adds none of its own routes; its
default server opens /js_api to any origin (CORS *), see
spikes/faz0/RAPOR.md. Calls into Python go through the js_api bridge, not
over HTTP, so this app only ever serves files and images.

Every response carries a strict Content-Security-Policy: scripts and
styles only from this app, no inline script, no remote anything. Image
routes need the per-run token, so another program on the machine cannot
read the pictures of the user's documents by guessing URLs.
"""
import os
import secrets
import sys

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
       "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
       "form-action 'none'; frame-ancestors 'none'")


def _base():
    # Next to the code from source, inside the bundle in a PyInstaller build.
    return getattr(sys, "_MEIPASS", None) or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def web_root():
    """The built page (web/dist)."""
    return os.path.join(_base(), "web", "dist")


def assets_root():
    return os.path.join(_base(), "assets")


def make_app(token, images, pages, root=None):
    """A WSGI app serving the page from ``root`` and images from the caches."""
    import bottle

    root = root or web_root()
    app = bottle.Bottle()

    @app.hook("after_request")
    def _headers():
        bottle.response.set_header("Content-Security-Policy", CSP)
        bottle.response.set_header("X-Content-Type-Options", "nosniff")
        bottle.response.set_header("Referrer-Policy", "no-referrer")
        bottle.response.set_header("Cross-Origin-Resource-Policy", "same-origin")

    def _authorised(tok):
        return secrets.compare_digest(tok, token)

    def _image(data, mime):
        bottle.response.content_type = mime
        # A key or page URL always shows the same picture (pages carry the
        # file's version), so the page may keep them.
        bottle.response.set_header("Cache-Control", "private, max-age=31536000, immutable")
        return data

    @app.get("/img/<tok>/<key>")
    def image(tok, key):
        item = images.get(key) if _authorised(tok) else None
        if item is None:
            bottle.abort(404)
        return _image(*item)

    @app.get("/pdf/<tok>/<doc_id>/<index:int>")
    def page(tok, doc_id, index):
        if not _authorised(tok):
            bottle.abort(404)
        try:
            width = int(bottle.request.query.get("w", 560))
        except ValueError:
            bottle.abort(400)
        try:
            data = pages.render(doc_id, index, width)
        except Exception:
            data = None
        if data is None:
            bottle.abort(404)
        return _image(data, "image/jpeg")

    @app.get("/app-icon.png")
    def app_icon():
        # The brand mark in the sidebar: the same file as the Tk window's.
        return bottle.static_file("appicon.png", root=assets_root())

    @app.get("/")
    def index():
        response = bottle.static_file("index.html", root=root)
        # The page itself always comes fresh, so a new build shows at once.
        response.set_header("Cache-Control", "no-store")
        return response

    @app.get("/<path:path>")
    def static(path):
        return bottle.static_file(path, root=root)

    return app
