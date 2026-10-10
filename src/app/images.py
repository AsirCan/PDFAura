"""Pictures for the web window: PDF pages and other images, served over HTTP.

The page shows images from the app's own local server (see server.py),
not as data: URLs through the bridge: for a large image that is 2.3 times
faster (spikes/faz0/RAPOR.md). Documents are registered under a random id,
so a file path never appears in a URL.

PyMuPDF must not run on two threads at once, and requests for pages come
in on server threads of their own, so every PyMuPDF call holds one lock.
"""
import os
import secrets
import threading
from collections import OrderedDict

JPEG_QUALITY = 88
MAX_RENDER_WIDTH = 4096       # px; a page zoomed to 500 % in the viewer
_OPEN_DOCUMENTS = 4


class ImageCache:
    """Encoded images by unguessable key, dropped oldest first past a size."""

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
                _old, (old_data, _mime) = self._items.popitem(last=False)
                self._size -= len(old_data)
        return key

    def get(self, key):
        """(data, mime) or None."""
        with self._lock:
            item = self._items.get(key)
            if item is not None:
                self._items.move_to_end(key)
            return item


class PdfPages:
    """The PDFs the page shows, by id, and their pages as JPEG."""

    def __init__(self):
        self._lock = threading.Lock()
        self._paths = {}                  # id -> path
        self._ids = {}                    # path -> id
        self._open = OrderedDict()        # path -> (mtime, fitz.Document)

    def register(self, path):
        """The id the page uses for ``path`` (the same one every time)."""
        path = os.path.abspath(path)
        with self._lock:
            doc_id = self._ids.get(path)
            if doc_id is None:
                doc_id = secrets.token_urlsafe(9)
                self._ids[path] = doc_id
                self._paths[doc_id] = path
            return doc_id

    def path(self, doc_id):
        with self._lock:
            return self._paths.get(doc_id)

    def _document(self, path):
        """An open document for ``path``, reopened if the file changed.
        Call with the lock held.

        Opened from a copy in memory: a document opened from the file keeps
        it open, and Windows then refuses to replace it -- a tool writing
        over the PDF on screen would fail.
        """
        import fitz
        mtime = os.path.getmtime(path)
        cached = self._open.get(path)
        if cached is not None and cached[0] == mtime:
            self._open.move_to_end(path)
            return cached[1]
        if cached is not None:
            cached[1].close()
        with open(path, "rb") as handle:
            doc = fitz.open(stream=handle.read(), filetype="pdf")
        self._open[path] = (mtime, doc)
        while len(self._open) > _OPEN_DOCUMENTS:
            _old, (_mtime, old_doc) = self._open.popitem(last=False)
            old_doc.close()
        return doc

    def info(self, path):
        """What the preview panel shows about a PDF. Raises if it cannot be read."""
        with self._lock:
            doc = self._document(path)
            first = doc.load_page(0) if len(doc) else None
            return {
                "pages": len(doc),
                "width": first.rect.width if first else 0,
                "height": first.rect.height if first else 0,
                "encrypted": bool(doc.needs_pass),
            }

    def render(self, doc_id, index, width):
        """Page ``index`` of a registered document, ``width`` px wide, as JPEG
        bytes; None if there is no such document or page."""
        import fitz
        path = self.path(doc_id)
        if path is None or not os.path.isfile(path):
            return None
        width = max(16, min(int(width), MAX_RENDER_WIDTH))
        with self._lock:
            doc = self._document(path)
            if doc.needs_pass or not 0 <= index < len(doc):
                return None
            page = doc.load_page(index)
            zoom = width / max(1.0, page.rect.width)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            return pixmap.tobytes("jpeg", jpg_quality=JPEG_QUALITY)

    def close(self):
        with self._lock:
            for _mtime, doc in self._open.values():
                doc.close()
            self._open.clear()
