"""Command line interface: every subcommand drives the same core functions."""
import os
import subprocess
import sys

from pypdf import PdfReader

from conftest import ROOT, make_encrypted_pdf, make_pdf, page_widths


def run_cli(*args):
    """Run 'python -m src.cli ...' the way a script would."""
    return subprocess.run(
        [sys.executable, "-m", "src.cli", *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_compress_subcommand(tmp_path):
    src = make_pdf(tmp_path / "input.pdf", pages=1)
    out = tmp_path / "out.pdf"

    result = run_cli("compress", src, "-q", "ebook", "-o", out)

    assert result.returncode == 0, result.stderr
    assert out.exists()
    assert len(PdfReader(str(out)).pages) == 1


def test_split_subcommand_extracts_the_page_range(tmp_path):
    src = make_pdf(tmp_path / "input.pdf", pages=5)   # page i is 595+i wide
    out = tmp_path / "out.pdf"

    result = run_cli("split", src, "--pages", "2-4", "-o", out)

    assert result.returncode == 0, result.stderr
    assert page_widths(str(out)) == [596, 597, 598]


def test_merge_subcommand_keeps_the_given_order(tmp_path):
    first = make_pdf(tmp_path / "a.pdf", pages=2)
    second = make_pdf(tmp_path / "b.pdf", pages=1)
    out = tmp_path / "merged.pdf"

    result = run_cli("merge", first, second, "-o", out)

    assert result.returncode == 0, result.stderr
    assert page_widths(str(out)) == [595, 596, 595]


def test_rotate_subcommand_only_turns_the_named_pages(tmp_path):
    src = make_pdf(tmp_path / "input.pdf", pages=3)
    out = tmp_path / "rotated.pdf"

    result = run_cli("rotate", src, "--pages", "1,3", "--angle", "90", "-o", out)

    assert result.returncode == 0, result.stderr
    rotations = [int(page.get("/Rotate", 0)) for page in PdfReader(str(out)).pages]
    assert rotations == [90, 0, 90]


def test_encrypt_then_decrypt_subcommands(tmp_path):
    src = make_pdf(tmp_path / "input.pdf", pages=2)
    encrypted = tmp_path / "encrypted.pdf"
    decrypted = tmp_path / "decrypted.pdf"

    result = run_cli("encrypt", src, "-p", "gizli", "-o", encrypted)
    assert result.returncode == 0, result.stderr
    assert PdfReader(str(encrypted)).is_encrypted

    result = run_cli("decrypt", encrypted, "-p", "gizli", "-o", decrypted)
    assert result.returncode == 0, result.stderr
    reader = PdfReader(str(decrypted))
    assert not reader.is_encrypted
    assert len(reader.pages) == 2


def test_watermark_subcommand_stamps_every_page(tmp_path):
    src = make_pdf(tmp_path / "input.pdf", pages=2)
    out = tmp_path / "watermarked.pdf"

    result = run_cli("watermark", src, "-t", "DRAFT", "-o", out)

    assert result.returncode == 0, result.stderr
    import fitz
    with fitz.open(str(out)) as doc:
        assert all("DRAFT" in page.get_text() for page in doc)


def test_to_images_subcommand_writes_one_file_per_page(tmp_path):
    src = make_pdf(tmp_path / "input.pdf", pages=2)
    folder = tmp_path / "pages"

    result = run_cli("to-images", src, "-o", folder, "--dpi", "72")

    assert result.returncode == 0, result.stderr
    assert sorted(os.listdir(folder)) == ["input_001.png", "input_002.png"]


def test_missing_input_reports_the_file_and_exits_non_zero(tmp_path):
    result = run_cli("compress", tmp_path / "nope.pdf")

    assert result.returncode == 1
    assert "Input file not found" in result.stderr
    assert "nope.pdf" in result.stderr


def test_invalid_quality_is_a_usage_error(tmp_path):
    src = make_pdf(tmp_path / "input.pdf")
    result = run_cli("compress", src, "-q", "ultra")

    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_invalid_page_range_is_reported(tmp_path):
    src = make_pdf(tmp_path / "input.pdf", pages=3)
    result = run_cli("split", src, "--pages", "3-1")

    assert result.returncode == 1
    assert "Invalid page range" in result.stderr
    assert not (tmp_path / "input_split.pdf").exists()


def test_merge_with_one_input_is_a_usage_error(tmp_path):
    src = make_pdf(tmp_path / "input.pdf")
    result = run_cli("merge", src)

    assert result.returncode == 2
    assert "at least two" in result.stderr


def test_decrypt_with_the_wrong_password_exits_non_zero(tmp_path):
    src = make_encrypted_pdf(tmp_path / "input.pdf", "dogru")
    out = tmp_path / "out.pdf"

    result = run_cli("decrypt", src, "-p", "yanlis", "-o", out)

    assert result.returncode == 1
    assert "error:" in result.stderr
    assert not out.exists()
