import builtins
import errno
import io
import os
import sys
import tempfile

# src.core.config_manager creates its singleton at import time and writes
# %APPDATA%\PDFAura\config.json. Point it at a throwaway folder BEFORE any
# src import so tests never touch the real user profile.
_APPDATA = tempfile.mkdtemp(prefix="pdfaura-test-appdata-")
os.environ["APPDATA"] = _APPDATA

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest  # noqa: E402
from pypdf import PdfWriter  # noqa: E402

# The theme follows Windows' light/dark mode by default. Pin the light theme
# so tests do not depend on the machine.
from src.core.config_manager import cfg as _cfg  # noqa: E402
_cfg.config["theme"] = "paper"


def make_pdf(path, pages=3, size=(595, 842), metadata=None):
    """Write a PDF with `pages` blank pages; page i gets width size[0] + i so
    pages can be told apart after split/reorder."""
    writer = PdfWriter()
    for i in range(pages):
        writer.add_blank_page(width=size[0] + i, height=size[1])
    if metadata:
        writer.add_metadata(metadata)
    with open(path, "wb") as f:
        writer.write(f)
    return str(path)


def make_encrypted_pdf(path, user_password, owner_password=None, algorithm="AES-256", pages=3):
    writer = PdfWriter()
    for i in range(pages):
        writer.add_blank_page(width=595 + i, height=842)
    writer.encrypt(user_password=user_password, owner_password=owner_password, algorithm=algorithm)
    with open(path, "wb") as f:
        writer.write(f)
    return str(path)


def page_widths(path, password=None):
    from pypdf import PdfReader
    reader = PdfReader(path)
    if reader.is_encrypted:
        reader.decrypt(password or "")
    return [round(float(p.mediabox.width)) for p in reader.pages]


# What rich_pdf() puts in a document besides its pages.
RICH_TITLE = "Contract"
RICH_OUTLINE = [("Giris", 1), ("Ek", 3)]       # (bookmark, 1-based page) on 3 pages
RICH_FIELD = "isim"                             # a text field on page 1


def rich_pdf(path, pages=3):
    """A PDF with more than pages: bookmarks, a title and a form field.

    Page i is 595 + i wide like make_pdf. Copying pages one by one into a
    new PdfWriter loses all three of these (#32).
    """
    import fitz
    doc = fitz.open()
    try:
        for i in range(pages):
            doc.new_page(width=595 + i, height=842)
        doc.set_toc([[1, title, page] for title, page in RICH_OUTLINE if page <= pages])
        doc.set_metadata({"title": RICH_TITLE})
        widget = fitz.Widget()
        widget.field_name = RICH_FIELD
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect = fitz.Rect(50, 50, 250, 80)
        widget.field_value = "Ayse"
        doc[0].add_widget(widget)
        doc.save(str(path))
    finally:
        doc.close()
    return str(path)


def pdf_structure(path, password=None):
    """What a document holds besides its pages: bookmarks with their 1-based
    page, the title, whether it has a form (/AcroForm) and its field names."""
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        reader.decrypt(password or "")

    def walk(items):
        for item in items:
            if isinstance(item, list):
                yield from walk(item)
            else:
                yield item.title, reader.get_destination_page_number(item) + 1

    return {
        "outline": list(walk(reader.outline)),
        "title": reader.metadata.title if reader.metadata else None,
        "acroform": "/AcroForm" in reader.trailer["/Root"],
        "fields": sorted(reader.get_fields() or {}),
    }


# How far a write gets before the disk "fills up".
DISK_FULL_AFTER = 100


def _disk_full_error():
    return OSError(errno.ENOSPC, "No space left on device")


class _FillingFile:
    """A file that takes DISK_FULL_AFTER bytes or characters, then fails."""

    def __init__(self, handle):
        self._handle = handle
        self._left = DISK_FULL_AFTER

    def write(self, data):
        chunk = data[:self._left]
        self._handle.write(chunk)
        self._left -= len(chunk)
        if len(chunk) < len(data):
            raise _disk_full_error()
        return len(data)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._handle.close()
        return False

    def __getattr__(self, name):
        return getattr(self._handle, name)


class DiskFull:
    """See the disk_full fixture."""

    def __init__(self, monkeypatch):
        self._monkeypatch = monkeypatch

    def open_in(self, module):
        """Files *module* opens for writing with open() fill up the same way."""
        def filling_open(file, mode="r", *args, **kwargs):
            handle = builtins.open(file, mode, *args, **kwargs)
            return _FillingFile(handle) if any(flag in mode for flag in "wax+") else handle
        self._monkeypatch.setattr(module, "open", filling_open, raising=False)


@pytest.fixture
def disk_full(monkeypatch):
    """The disk fills up DISK_FULL_AFTER bytes into a write (ENOSPC).

    PdfWriter.write always fails that way; ``disk_full.open_in(module)`` does
    the same to files that module writes with open(). What is left behind is
    what a real full disk leaves: a truncated file wherever the bytes went.
    """
    real_write = PdfWriter.write

    def filling_write(self, stream):
        buffer = io.BytesIO()
        real_write(self, buffer)
        data = buffer.getvalue()[:DISK_FULL_AFTER]
        if isinstance(stream, (str, os.PathLike)):
            with builtins.open(stream, "wb") as handle:
                handle.write(data)
        else:
            stream.write(data)
        raise _disk_full_error()

    monkeypatch.setattr(PdfWriter, "write", filling_write)
    return DiskFull(monkeypatch)


def leftovers(folder):
    """Temporary files atomic_output left behind in *folder*."""
    return sorted(name for name in os.listdir(folder) if name.startswith(".pdfaura-"))


@pytest.fixture(scope="session", autouse=True)
def _session_language_tr():
    """Module-scoped fixtures build whole windows before the per-test
    fixture below runs; without this they came up in the Windows UI
    language, so the suite only passed on a Turkish Windows."""
    from src.core.config_manager import cfg
    old = cfg.config.get("language")
    cfg.config["language"] = "tr"
    yield
    cfg.config["language"] = old


@pytest.fixture(autouse=True)
def _language_tr():
    """Tests assert on Turkish messages unless they switch language themselves."""
    from src.core.config_manager import cfg
    old = cfg.config.get("language")
    cfg.config["language"] = "tr"
    yield
    cfg.config["language"] = old
