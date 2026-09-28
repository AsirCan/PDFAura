"""Issue #5: Ghostscript deadlock, lost error text, discovery outside PATH."""
import os
import shutil
import subprocess
import sys
import textwrap

import pytest

from conftest import make_pdf
from src.core import compress
from src.core.task_manager import CancelledError, TaskContext
from src.utils import ghostscript_helper
from src.utils.ghostscript_helper import escape_gs_path, find_ghostscript, run_ghostscript


def write_fake_gs(folder, body):
    """Install a fake gswin64c on PATH that runs *body* as a Python script."""
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "fake_gs.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")

    if sys.platform == "win32":
        launcher = folder / "gswin64c.bat"
        launcher.write_text(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        launcher = folder / "gswin64c"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    return str(launcher)


@pytest.fixture
def fake_gs_path(tmp_path, monkeypatch):
    """Put a fake-Ghostscript folder first on PATH and clear the path cache."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setattr(ghostscript_helper, "_cached_path", None)
    yield bin_dir
    monkeypatch.setattr(ghostscript_helper, "_cached_path", None)


# A fake Ghostscript that writes far more than a pipe buffer holds (~64 KB on
# Windows) before exiting. The old code never read the pipe, so both processes
# blocked forever; this must now finish.
CHATTY_GS = """
    import sys, os
    out = None
    for arg in sys.argv[1:]:
        if arg.startswith("-sOutputFile="):
            out = arg.split("=", 1)[1]
    for i in range(8000):
        sys.stderr.write("**** Warning: chatty ghostscript line %d\\n" % i)
    sys.stderr.flush()
    if out:
        with open(out, "wb") as f:
            f.write(b"%PDF-1.4 fake compressed output\\n" * 100)
    sys.exit(0)
"""


def test_chatty_ghostscript_does_not_deadlock(tmp_path, fake_gs_path):
    write_fake_gs(fake_gs_path, CHATTY_GS)
    src = make_pdf(tmp_path / "in.pdf")
    out = tmp_path / "out.pdf"

    # Without draining stderr this call never returns.
    compress.compress_pdf(src, str(out), "ebook")

    assert out.exists() and out.stat().st_size > 0


def test_chatty_ghostscript_with_progress_context(tmp_path, fake_gs_path):
    write_fake_gs(fake_gs_path, CHATTY_GS)
    src = make_pdf(tmp_path / "in.pdf")
    out = tmp_path / "out.pdf"

    seen = []
    ctx = TaskContext(progress_callback=lambda c, t, m="": seen.append(c))
    compress.compress_pdf(src, str(out), "ebook", ctx=ctx)

    assert out.exists()
    assert seen and seen[-1] == 100


def test_cp1254_error_is_readable(tmp_path, fake_gs_path):
    """Turkish Windows Ghostscript writes cp1254, not UTF-8."""
    write_fake_gs(fake_gs_path, """
        import sys
        sys.stderr.buffer.write("Dosya açılamadı: geçersiz çıktı".encode("cp1254"))
        sys.exit(1)
    """)
    src = make_pdf(tmp_path / "in.pdf")

    with pytest.raises(RuntimeError) as excinfo:
        compress.compress_pdf(src, str(tmp_path / "out.pdf"), "ebook")

    # The point is a readable message instead of a UnicodeDecodeError.
    assert "UnicodeDecodeError" not in str(excinfo.value)
    assert "lamad" in str(excinfo.value)


def test_failed_run_leaves_no_partial_output(tmp_path, fake_gs_path):
    write_fake_gs(fake_gs_path, """
        import sys
        out = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("-sOutputFile=")][0]
        open(out, "wb").write(b"half written")
        sys.stderr.write("boom")
        sys.exit(1)
    """)
    src = make_pdf(tmp_path / "in.pdf")
    out = tmp_path / "out.pdf"

    with pytest.raises(RuntimeError):
        compress.compress_pdf(src, str(out), "ebook")

    assert not out.exists()
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".pdfaura-")] == []


def test_input_equal_to_output_is_not_destroyed(tmp_path, fake_gs_path):
    """Ghostscript truncates its input if it is also the output; we must not."""
    write_fake_gs(fake_gs_path, CHATTY_GS)
    src = make_pdf(tmp_path / "same.pdf")
    original = open(src, "rb").read()

    compress.compress_pdf(src, src, "ebook")

    content = open(src, "rb").read()
    assert content != original          # it really was replaced
    assert content.startswith(b"%PDF")  # and it is the fake's output, not a truncated file


def test_cancel_kills_the_process(tmp_path, fake_gs_path):
    write_fake_gs(fake_gs_path, """
        import time
        time.sleep(60)
    """)
    src = make_pdf(tmp_path / "in.pdf")
    out = tmp_path / "out.pdf"

    ctx = TaskContext()
    ctx.cancel()

    with pytest.raises(CancelledError):
        compress.compress_pdf(src, str(out), "ebook", ctx=ctx)

    assert not out.exists()


def test_missing_ghostscript_gives_install_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(ghostscript_helper, "_cached_path", None)
    monkeypatch.setattr(ghostscript_helper, "find_ghostscript", lambda *a, **k: None)
    monkeypatch.setattr(compress, "run_ghostscript", ghostscript_helper.run_ghostscript)
    monkeypatch.setattr(shutil, "which", lambda *a, **k: None)
    monkeypatch.setattr(ghostscript_helper, "_from_registry", lambda: None)
    monkeypatch.setattr(ghostscript_helper, "_from_program_files", lambda: None)

    src = make_pdf(tmp_path / "in.pdf")
    with pytest.raises(FileNotFoundError, match="Ghostscript"):
        compress.compress_pdf(src, str(tmp_path / "out.pdf"), "ebook")


def test_find_ghostscript_uses_program_files_when_not_on_path(tmp_path, monkeypatch):
    """The Windows installer does not touch PATH, so discovery must not rely on it."""
    program_files = tmp_path / "ProgramFiles"
    installed = program_files / "gs" / "gs10.03.1" / "bin" / "gswin64c.exe"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b"")
    older = program_files / "gs" / "gs9.56" / "bin" / "gswin64c.exe"
    older.parent.mkdir(parents=True)
    older.write_bytes(b"")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(shutil, "which", lambda *a, **k: None)
    monkeypatch.setattr(ghostscript_helper, "_from_registry", lambda: None)
    monkeypatch.setenv("ProgramFiles", str(program_files))
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    monkeypatch.delenv("ProgramW6432", raising=False)

    found = find_ghostscript(refresh=True)
    assert found == str(installed)  # newest version wins


def test_escape_gs_path_doubles_percent():
    assert escape_gs_path(r"C:\\100% done\\out.pdf") == r"C:\\100%% done\\out.pdf"


def test_no_console_window_flag_on_windows():
    if sys.platform == "win32":
        assert ghostscript_helper.CREATE_NO_WINDOW == subprocess.CREATE_NO_WINDOW
