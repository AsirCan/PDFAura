"""PDF compression runs on PyMuPDF; Ghostscript is no longer needed."""
import io
import os
import subprocess
import sys

import fitz
import numpy as np
import pytest
from PIL import Image

from conftest import make_pdf
from src.core import compress
from src.core.common import PdfPasswordError
from src.core.task_manager import CancelledError, TaskContext
from src.utils.process_helper import CREATE_NO_WINDOW, decode_output


def make_scan_pdf(path, pages=2, dpi=300, text="Taranmis sozlesme"):
    """A PDF like a scanner makes: a full-page JPEG per page at `dpi`, plus a
    line of real text so we can check text survives."""
    rng = np.random.default_rng(7)
    width, height = int(8.27 * dpi), int(11.69 * dpi)
    doc = fitz.open()
    for _ in range(pages):
        # Paper-like noise compresses badly, like a real scan.
        pixels = rng.normal(225, 18, (height // 4, width // 4, 3)).clip(0, 255).astype("uint8")
        image = Image.fromarray(pixels).resize((width, height))
        buf = io.BytesIO()
        image.save(buf, "JPEG", quality=95)
        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=buf.getvalue())
        page.insert_text((72, 72), text, fontsize=14)
    doc.save(path)
    doc.close()
    return str(path)


def first_image_width(path):
    doc = fitz.open(path)
    try:
        xref = doc[0].get_images()[0][0]
        return doc.extract_image(xref)["width"]
    finally:
        doc.close()


def temp_leftovers(folder):
    return [p.name for p in folder.iterdir() if p.name.startswith(".pdfaura-")]


def test_no_external_program_is_needed(tmp_path, monkeypatch):
    """Compression must work with nothing installed: no subprocess at all."""
    def no_subprocess(*args, **kwargs):
        raise AssertionError(f"compression started a process: {args}")

    monkeypatch.setattr(subprocess, "Popen", no_subprocess)
    monkeypatch.setattr(subprocess, "run", no_subprocess)
    src = make_scan_pdf(tmp_path / "scan.pdf", pages=1)

    compress.compress_pdf(src, str(tmp_path / "out.pdf"), "ebook")

    assert os.path.getsize(tmp_path / "out.pdf") < os.path.getsize(src)


def test_scan_is_downsampled_to_the_profile_resolution(tmp_path):
    src = make_scan_pdf(tmp_path / "scan.pdf", pages=1, dpi=300)
    out = tmp_path / "out.pdf"

    compress.compress_pdf(src, str(out), "ebook")

    # 300 dpi → 150 dpi halves the width (MuPDF's default "average"
    # subsampling left it at 300 dpi).
    assert first_image_width(out) == pytest.approx(first_image_width(src) / 2, abs=2)
    assert os.path.getsize(out) < os.path.getsize(src) / 3


def test_profiles_are_ordered_by_size(tmp_path):
    src = make_scan_pdf(tmp_path / "scan.pdf", pages=1)
    sizes = {}
    for quality in compress.VALID_QUALITIES:
        out = tmp_path / f"{quality}.pdf"
        compress.compress_pdf(src, str(out), quality)
        sizes[quality] = os.path.getsize(out)

    assert sizes["screen"] < sizes["ebook"] < sizes["printer"] <= sizes["prepress"]


def test_text_stays_text(tmp_path):
    """Images are re-encoded; the page content is not rasterised."""
    src = make_scan_pdf(tmp_path / "scan.pdf", pages=1, text="Hizmet Sozlesmesi 2026")
    out = tmp_path / "out.pdf"

    compress.compress_pdf(src, str(out), "screen")

    doc = fitz.open(out)
    try:
        assert "Hizmet Sozlesmesi 2026" in doc[0].get_text()
        assert doc.page_count == 1
    finally:
        doc.close()


def test_result_is_never_larger_than_the_input(tmp_path):
    """Ghostscript's printer profile turned a 2.7 MB photo PDF into 14 MB."""
    src = make_pdf(tmp_path / "tiny.pdf", pages=2)
    out = tmp_path / "out.pdf"

    for quality in compress.VALID_QUALITIES:
        compress.compress_pdf(src, str(out), quality)
        assert os.path.getsize(out) <= os.path.getsize(src)


def test_input_equal_to_output_is_replaced_safely(tmp_path):
    src = make_scan_pdf(tmp_path / "same.pdf", pages=1)
    before = os.path.getsize(src)

    compress.compress_pdf(src, src, "ebook")

    assert os.path.getsize(src) < before
    with fitz.open(src) as doc:
        assert doc.page_count == 1
    assert temp_leftovers(tmp_path) == []


def test_metadata_is_kept(tmp_path):
    src = make_pdf(tmp_path / "meta.pdf", metadata={"/Title": "Faaliyet Raporu", "/Author": "Aura"})
    out = tmp_path / "out.pdf"

    compress.compress_pdf(src, str(out), "ebook")

    with fitz.open(out) as doc:
        assert doc.metadata["title"] == "Faaliyet Raporu"
        assert doc.metadata["author"] == "Aura"


def test_unknown_quality_is_rejected(tmp_path):
    src = make_pdf(tmp_path / "in.pdf")
    with pytest.raises(ValueError):
        compress.compress_pdf(src, str(tmp_path / "out.pdf"), "maximum")


def test_password_protected_input_gives_a_clear_message(tmp_path):
    src = make_scan_pdf(tmp_path / "plain.pdf", pages=1)
    locked = tmp_path / "locked.pdf"
    with fitz.open(src) as doc:
        doc.save(locked, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="gizli", owner_pw="gizli")

    with pytest.raises(PdfPasswordError):
        compress.compress_pdf(str(locked), str(tmp_path / "out.pdf"), "ebook")

    assert not (tmp_path / "out.pdf").exists()
    assert temp_leftovers(tmp_path) == []


def test_broken_input_leaves_no_partial_output(tmp_path):
    src = tmp_path / "broken.pdf"
    src.write_bytes(b"%PDF-1.7 this is not really a PDF")
    out = tmp_path / "out.pdf"

    with pytest.raises(Exception):
        compress.compress_pdf(str(src), str(out), "ebook")

    assert not out.exists()
    assert temp_leftovers(tmp_path) == []


def test_cancel_leaves_no_output(tmp_path):
    src = make_scan_pdf(tmp_path / "in.pdf", pages=1)
    out = tmp_path / "out.pdf"
    ctx = TaskContext()
    ctx.cancel()

    with pytest.raises(CancelledError):
        compress.compress_pdf(src, str(out), "ebook", ctx=ctx)

    assert not out.exists()
    assert temp_leftovers(tmp_path) == []


def test_progress_reaches_100(tmp_path):
    src = make_scan_pdf(tmp_path / "in.pdf", pages=1)
    seen = []
    ctx = TaskContext(progress_callback=lambda current, total, message="": seen.append(current))

    compress.compress_pdf(src, str(tmp_path / "out.pdf"), "ebook", ctx=ctx)

    assert seen[0] == 0 and seen[-1] == 100
    assert seen == sorted(seen)


# ── process helpers (LibreOffice, Tesseract installer) ─────────────────────

def test_cp1254_output_is_readable():
    """Turkish Windows tools write cp1254, not UTF-8."""
    raw = "Dosya açılamadı: geçersiz çıktı".encode("cp1254")
    text = decode_output(raw)
    assert "lamad" in text


def test_no_console_window_flag_on_windows():
    if sys.platform == "win32":
        assert CREATE_NO_WINDOW == subprocess.CREATE_NO_WINDOW
