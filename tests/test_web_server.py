"""#25 Faz 2: the web window's local HTTP app (src/app/server.py) and its
event path (src/app/events.py)."""
import io
import json
from wsgiref.util import setup_testing_defaults

import pytest

from conftest import make_pdf
from src.app.events import EventBus
from src.app.images import ImageCache, PdfPages
from src.app.server import CSP, make_app


def get(app, path, query=""):
    environ = {}
    setup_testing_defaults(environ)
    environ.update(PATH_INFO=path, QUERY_STRING=query, REQUEST_METHOD="GET")
    seen = {}

    def start_response(status, headers, exc_info=None):
        seen["status"] = int(status.split()[0])
        seen["headers"] = dict(headers)

    body = b"".join(app(environ, start_response))
    return seen["status"], seen["headers"], body


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>x</title>", encoding="utf-8")
    (root / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    images, pages = ImageCache(), PdfPages()
    return make_app("secret", images, pages, root=str(root)), images, pages


def test_every_response_carries_the_strict_csp(site):
    app, _images, _pages = site
    for path in ("/", "/assets/app.js", "/missing", "/img/wrong/key"):
        _status, headers, _body = get(app, path)
        assert headers["Content-Security-Policy"] == CSP
        assert headers["X-Content-Type-Options"] == "nosniff"


def test_the_csp_allows_nothing_inline_or_remote():
    assert "'unsafe-inline'" not in CSP and "'unsafe-eval'" not in CSP
    assert "http" not in CSP and "*" not in CSP
    assert "script-src 'self'" in CSP and "frame-ancestors 'none'" in CSP


def test_the_page_is_served_fresh(site):
    status, headers, body = get(site[0], "/")
    assert status == 200 and b"<title>" in body and headers["Cache-Control"] == "no-store"


def test_files_outside_the_build_are_not_served(site):
    status, _headers, _body = get(site[0], "/../../secret.txt")
    assert status in (403, 404)


def test_images_need_the_token(site):
    app, images, _pages = site
    key = images.put(b"\xff\xd8jpeg")
    assert get(app, f"/img/secret/{key}")[0] == 200
    assert get(app, f"/img/guess/{key}")[0] == 404
    assert get(app, "/img/secret/unknown")[0] == 404


def test_pdf_pages_are_drawn_on_request(site, tmp_path):
    app, _images, pages = site
    doc_id = pages.register(make_pdf(tmp_path / "a.pdf", pages=2))
    status, headers, body = get(app, f"/pdf/secret/{doc_id}/1", "w=200")
    assert status == 200 and headers["Content-Type"] == "image/jpeg" and body[:2] == b"\xff\xd8"
    from PIL import Image
    assert Image.open(io.BytesIO(body)).width == 200
    assert get(app, f"/pdf/secret/{doc_id}/5")[0] == 404
    assert get(app, f"/pdf/other/{doc_id}/0")[0] == 404
    assert get(app, "/pdf/secret/nope/0")[0] == 404


def test_a_previewed_pdf_can_still_be_replaced(tmp_path):
    """A document opened from the file keeps it open, and Windows then
    refuses to write over it."""
    path = make_pdf(tmp_path / "a.pdf")
    pages = PdfPages()
    pages.render(pages.register(path), 0, 100)
    make_pdf(tmp_path / "b.pdf", pages=5)
    import os
    os.replace(tmp_path / "b.pdf", path)
    assert pages.info(path)["pages"] == 5, "a changed file is read again"
    pages.close()


def test_the_image_cache_drops_the_oldest_past_its_limit():
    cache = ImageCache(limit_bytes=10)
    first = cache.put(b"123456")
    second = cache.put(b"123456")
    assert cache.get(first) is None and cache.get(second) == (b"123456", "image/jpeg")


# ── Events ────────────────────────────────────────────────────────────────

def test_events_wait_for_the_page_then_go_in_order():
    sent = []
    bus = EventBus(sent.append)
    bus.emit("job", {"id": 1})
    bus.emit("drop", {"files": []})
    assert sent == []
    bus.ready()
    bus.emit("assistant", {"state": "idle"})
    assert len(sent) == 3
    assert sent[0] == 'window.__aura&&window.__aura.emit("job",{"id": 1})'


def test_event_data_cannot_break_out_of_the_script():
    sent = []
    bus = EventBus(sent.append)
    bus.ready()
    bus.emit("assistant-reply", {"text": "\");alert(1);//</script>"})
    payload = sent[0][len('window.__aura&&window.__aura.emit("assistant-reply",'):-1]
    assert json.loads(payload) == {"text": "\");alert(1);//</script>"}


def test_a_closing_window_does_not_break_the_sender():
    def broken(_script):
        raise RuntimeError("window gone")
    bus = EventBus(broken)
    bus.ready()
    bus.emit("job", {"id": 1})
