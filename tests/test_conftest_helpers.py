"""The shared test helpers do what the data-loss and structure tests rely on (#38)."""
import errno

import pytest
from pypdf import PdfWriter

import conftest
from conftest import (DISK_FULL_AFTER, RICH_FIELD, RICH_OUTLINE, RICH_TITLE, make_pdf, pdf_structure,
                      rich_pdf)


def test_rich_pdf_has_bookmarks_a_title_and_a_form(tmp_path):
    structure = pdf_structure(rich_pdf(tmp_path / "rich.pdf"))

    assert structure == {"outline": RICH_OUTLINE, "title": RICH_TITLE, "acroform": True,
                         "fields": [RICH_FIELD]}


def test_a_plain_pdf_has_none_of_that(tmp_path):
    structure = pdf_structure(make_pdf(tmp_path / "plain.pdf"))

    assert structure == {"outline": [], "title": None, "acroform": False, "fields": []}


def test_disk_full_truncates_a_pdf_written_to_a_path(tmp_path, disk_full):
    target = tmp_path / "out.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)

    with pytest.raises(OSError) as excinfo:
        writer.write(str(target))

    assert excinfo.value.errno == errno.ENOSPC
    assert target.stat().st_size == DISK_FULL_AFTER


def test_disk_full_truncates_text_a_module_writes(tmp_path, disk_full):
    target = tmp_path / "out.txt"
    disk_full.open_in(conftest)

    with pytest.raises(OSError):
        with conftest.open(target, "w", encoding="utf-8") as handle:
            handle.write("x" * (DISK_FULL_AFTER * 2))

    assert target.read_text(encoding="utf-8") == "x" * DISK_FULL_AFTER


def test_disk_full_leaves_reading_alone(tmp_path, disk_full):
    source = tmp_path / "in.txt"
    source.write_text("y" * (DISK_FULL_AFTER * 2), encoding="utf-8")
    disk_full.open_in(conftest)

    with conftest.open(source, encoding="utf-8") as handle:
        assert len(handle.read()) == DISK_FULL_AFTER * 2
