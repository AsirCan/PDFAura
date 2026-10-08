"""Issue #10: batch runs overwrote each other's outputs and lied about it."""
import os

import pytest

from conftest import make_pdf
from src.core import batch
from src.core.batch import (RENAME_TOKENS, _apply_rename_tokens, batch_convert_dir,
                            batch_rename_dir, get_files_in_dir)
from src.core.output_paths import unique_path


@pytest.fixture
def copy_instead_of_compress(monkeypatch):
    """These tests are about output names, not compression: copy instead."""
    def fake_compress(src, dst, quality, ctx=None):
        with open(src, "rb") as fin, open(dst, "wb") as fout:
            fout.write(fin.read())
    monkeypatch.setattr(batch, "compress_pdf", fake_compress)


def pdf_names(folder):
    found = []
    for root, _dirs, files in os.walk(folder):
        for name in files:
            if name.lower().endswith(".pdf"):
                found.append(os.path.relpath(os.path.join(root, name), folder))
    return sorted(found)


# ── Rename ────────────────────────────────────────────────────────────────

def test_rule_without_order_token_keeps_every_file(tmp_path):
    """'Fatura' copied all three files onto one name: 3 successes, 1 file."""
    src = tmp_path / "in"
    src.mkdir()
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        make_pdf(src / name)
    out = tmp_path / "out"

    success, errors = batch_rename_dir(str(src), str(out), "Fatura")

    assert success == 3 and errors == []
    assert len(pdf_names(out)) == 3


def test_turkish_dotted_i_tokens_are_applied(tmp_path):
    """The Turkish hint shows [ORİJİNAL_AD] and [TARİH]; the code expected
    the dotless spellings, so the hint's tokens landed in the filename."""
    src = tmp_path / "in"
    src.mkdir()
    make_pdf(src / "rapor.pdf")
    out = tmp_path / "out"

    batch_rename_dir(str(src), str(out), "[TARİH]_[ORİJİNAL_AD]_[SIRA]")

    name = pdf_names(out)[0]
    assert "[" not in name and "]" not in name
    assert "rapor" in name and "001" in name


def test_english_tokens_are_applied(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    make_pdf(src / "report.pdf")
    out = tmp_path / "out"

    batch_rename_dir(str(src), str(out), "[DATE]_[ORIGINAL_NAME]_[ORDER]")

    name = pdf_names(out)[0]
    assert "[" not in name
    assert "report" in name and "001" in name


@pytest.mark.parametrize("alias", [a for aliases in RENAME_TOKENS.values() for a in aliases])
def test_every_documented_token_is_substituted(alias):
    values = {"original_name": "N", "page_count": "3pp", "size": "1.0MB",
              "order": "001", "date": "2026-09-28"}
    assert "[" not in _apply_rename_tokens(f"[{alias}]", values)


def test_tokens_are_case_insensitive():
    values = {"original_name": "N", "page_count": "3pp", "size": "1.0MB",
              "order": "001", "date": "2026-09-28"}
    assert _apply_rename_tokens("[original_name]", values) == "N"


# ── Compress ──────────────────────────────────────────────────────────────

def test_same_name_in_subfolders_keeps_both(tmp_path, copy_instead_of_compress):
    """'rapor.pdf' and 'alt/rapor.pdf' both wrote compressed_rapor.pdf."""
    src = tmp_path / "in"
    (src / "alt").mkdir(parents=True)
    make_pdf(src / "rapor.pdf")
    make_pdf(src / "alt" / "rapor.pdf")
    out = tmp_path / "out"

    success, errors = batch.batch_compress_dir(str(src), str(out), "ebook")

    assert success == 2 and errors == []
    assert len(pdf_names(out)) == 2


def test_output_inside_input_is_not_reprocessed(tmp_path, copy_instead_of_compress):
    """A second run used to produce compressed_compressed_rapor.pdf."""
    src = tmp_path / "in"
    src.mkdir()
    make_pdf(src / "rapor.pdf")
    out = src / "out"

    batch.batch_compress_dir(str(src), str(out), "ebook")
    first = pdf_names(out)
    batch.batch_compress_dir(str(src), str(out), "ebook")

    assert pdf_names(out) == first
    assert not any("compressed_compressed" in n for n in pdf_names(out))


# ── Convert ───────────────────────────────────────────────────────────────

def test_png_and_jpg_with_the_same_stem_both_survive(tmp_path):
    """foto.png and foto.jpg both wrote foto.pdf, in parallel."""
    from PIL import Image
    src = tmp_path / "in"
    src.mkdir()
    for name in ("foto.png", "foto.jpg"):
        Image.new("RGB", (40, 40), (200, 30, 30)).save(src / name)
    out = tmp_path / "out"

    success, errors = batch_convert_dir(str(src), str(out), "img2pdf")

    assert success == 2 and errors == []
    assert len(pdf_names(out)) == 2


def test_empty_folder_is_reported(tmp_path):
    """0/0 used to be reported as a completed run."""
    src = tmp_path / "in"
    src.mkdir()
    out = tmp_path / "out"

    success, errors = batch_convert_dir(str(src), str(out), "img2pdf")

    assert success == 0
    assert errors
    assert "bulunamadi" in errors[0].lower() or "found" in errors[0].lower()


# ── Scanning ──────────────────────────────────────────────────────────────

def test_get_files_in_dir_excludes_the_output_folder(tmp_path):
    src = tmp_path / "in"
    (src / "out").mkdir(parents=True)
    make_pdf(src / "a.pdf")
    make_pdf(src / "out" / "old.pdf")

    found = get_files_in_dir(str(src), [".pdf"], exclude_dir=str(src / "out"))

    assert [os.path.basename(f) for f in found] == ["a.pdf"]


# ── unique_path ───────────────────────────────────────────────────────────

def test_unique_path_avoids_an_existing_file(tmp_path):
    existing = tmp_path / "a.pdf"
    existing.write_bytes(b"x")
    assert unique_path(str(existing)) == str(tmp_path / "a (2).pdf")


def test_unique_path_reserves_planned_names(tmp_path):
    """Names planned before anything is written must not collide."""
    taken = set()
    first = unique_path(str(tmp_path / "a.pdf"), taken)
    second = unique_path(str(tmp_path / "a.pdf"), taken)
    assert first != second
