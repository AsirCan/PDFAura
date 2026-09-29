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
# before anything builds styles, so tests do not depend on the machine.
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


@pytest.fixture(autouse=True)
def _language_tr():
    """Tests assert on Turkish messages unless they switch language themselves."""
    from src.core.config_manager import cfg
    old = cfg.config.get("language")
    cfg.config["language"] = "tr"
    yield
    cfg.config["language"] = old


@pytest.fixture(scope="session")
def tk_root():
    """One Tk interpreter for the whole run.

    Creating a second one after destroying the first made Tcl fail to read
    its own init.tcl on some runs, so UI tests share this root; each test
    cleans up the windows it opens.
    """
    import tkinter as tk
    try:
        root = tk.Tk()
    except Exception as exc:                       # pragma: no cover
        pytest.skip(f"no Tk display: {exc}")
    root.withdraw()
    from src.gui.styles import setup_styles
    setup_styles(root)
    yield root
    try:
        root.destroy()
    except Exception:
        pass
