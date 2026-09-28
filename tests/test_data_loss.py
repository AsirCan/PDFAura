"""Issue #8: metadata save wiped existing fields, reorder silently dropped pages."""
import pytest
from pypdf import PdfReader

from conftest import make_encrypted_pdf, make_pdf, page_widths
from src.core.common import PdfPasswordError, parse_page_order
from src.core.edit import reorder_pages_in_pdf
from src.core.metainfo import read_metadata, update_metadata

META = {"/Title": "Test Belgesi", "/Author": "Deneme Yazar",
        "/Subject": "Konu", "/Creator": "Olusturan"}


# ── Metadata ──────────────────────────────────────────────────────────────

def test_saving_without_reading_keeps_existing_metadata(tmp_path):
    """The GUI sends None for fields it never loaded; nothing may be erased."""
    src = make_pdf(tmp_path / "in.pdf", metadata=META)
    out = tmp_path / "out.pdf"

    update_metadata(src, str(out))

    meta = read_metadata(str(out))
    assert meta["title"] == "Test Belgesi"
    assert meta["author"] == "Deneme Yazar"
    assert meta["subject"] == "Konu"
    assert meta["creator"] == "Olusturan"


def test_only_supplied_fields_change(tmp_path):
    src = make_pdf(tmp_path / "in.pdf", metadata=META)
    out = tmp_path / "out.pdf"

    update_metadata(src, str(out), title="Yeni Baslik")

    meta = read_metadata(str(out))
    assert meta["title"] == "Yeni Baslik"
    assert meta["author"] == "Deneme Yazar"  # untouched


def test_empty_string_clears_just_that_field(tmp_path):
    src = make_pdf(tmp_path / "in.pdf", metadata=META)
    out = tmp_path / "out.pdf"

    update_metadata(src, str(out), author="")

    meta = read_metadata(str(out))
    assert meta["author"] == ""
    assert meta["title"] == "Test Belgesi"


def test_clean_leaves_no_info_fields_at_all(tmp_path):
    """'Clear all' used to leave /Producer behind."""
    src = make_pdf(tmp_path / "in.pdf", metadata=META)
    out = tmp_path / "out.pdf"

    update_metadata(src, str(out), clean=True)

    reader = PdfReader(str(out))
    assert reader.metadata is None or dict(reader.metadata) == {}
    assert reader.xmp_metadata is None


def test_reading_encrypted_pdf_raises_a_clear_error(tmp_path):
    """The Read button swallowed this and showed nothing at all."""
    src = make_encrypted_pdf(tmp_path / "locked.pdf", "secret")

    with pytest.raises(PdfPasswordError, match="parola korumalı"):
        read_metadata(src)


# ── Page order parsing ────────────────────────────────────────────────────

def test_partial_order_is_rejected_with_the_missing_pages():
    """'2, 1' on a 5-page document used to produce a 2-page file and say OK."""
    with pytest.raises(ValueError) as excinfo:
        parse_page_order("2, 1", 5)

    message = str(excinfo.value)
    assert "3" in message and "4" in message and "5" in message


def test_duplicate_pages_are_rejected():
    with pytest.raises(ValueError, match="2"):
        parse_page_order("1, 2, 2", 3)


def test_trailing_comma_is_tolerated():
    """Used to surface as: invalid literal for int() with base 10: ''"""
    assert parse_page_order("3, 1, 2,", 3) == [3, 1, 2]


def test_whitespace_and_blank_chunks_are_tolerated():
    assert parse_page_order("  3 ,, 1,2  ", 3) == [3, 1, 2]


def test_forward_range():
    assert parse_page_order("1-3", 3) == [1, 2, 3]


def test_reverse_range_reverses_the_document():
    assert parse_page_order("5-1", 5) == [5, 4, 3, 2, 1]


def test_mixed_ranges_and_singles():
    assert parse_page_order("4, 1-3, 5", 5) == [4, 1, 2, 3, 5]


def test_page_outside_the_document_is_named():
    with pytest.raises(ValueError, match="9"):
        parse_page_order("1, 2, 9", 3)


def test_garbage_token_is_named():
    with pytest.raises(ValueError, match="abc"):
        parse_page_order("1, abc, 2", 3)


def test_empty_order_is_rejected():
    with pytest.raises(ValueError):
        parse_page_order("  ,, ", 3)


# ── Reorder core ──────────────────────────────────────────────────────────

def test_reorder_refuses_to_drop_pages(tmp_path):
    """Defence in depth: the core must refuse even if a caller asks for it."""
    src = make_pdf(tmp_path / "in.pdf", pages=5)
    out = tmp_path / "out.pdf"

    with pytest.raises(ValueError):
        reorder_pages_in_pdf(src, str(out), [2, 1])


def test_reorder_accepts_a_full_permutation(tmp_path):
    src = make_pdf(tmp_path / "in.pdf", pages=3)
    out = tmp_path / "out.pdf"

    reorder_pages_in_pdf(src, str(out), [3, 1, 2])

    # make_pdf gives page i width 595 + i, so order is visible in the widths.
    assert page_widths(out) == [597, 595, 596]
