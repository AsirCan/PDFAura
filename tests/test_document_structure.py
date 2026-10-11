"""Issue #32: the tools kept the pages and dropped the rest of the document.

Copying pages one by one into a new PdfWriter lost the bookmarks, the title
and the fillable form. Whole-document operations now copy the document and
change it in place; operations that pick pages carry over what belongs to
the pages they keep.
"""
import pytest
from PIL import Image

from conftest import RICH_FIELD, RICH_OUTLINE, RICH_TITLE, make_pdf, page_widths, pdf_structure, rich_pdf
from src.core.edit import delete_pages_from_pdf, reorder_pages_in_pdf, rotate_pages_in_pdf
from src.core.merge import merge_pdfs
from src.core.metainfo import update_metadata
from src.core.security import add_watermark_to_pdf, decrypt_pdf, encrypt_pdf
from src.core.signature import stamp_visual_signature
from src.core.split import split_pdf

WHOLE = {"outline": RICH_OUTLINE, "title": RICH_TITLE, "acroform": True, "fields": [RICH_FIELD]}


def _signature(src, out):
    image = src.parent / "imza.png"
    Image.new("RGB", (40, 20), "navy").save(image)
    stamp_visual_signature(str(src), str(out), str(image), page_num=2)


def _decrypt(src, out):
    locked = src.parent / "kilitli.pdf"
    encrypt_pdf(str(src), str(locked), "Gizli123")
    decrypt_pdf(str(locked), str(out), "Gizli123")


# The table in issue #32, and the other whole-document operations.
@pytest.mark.parametrize("name, run, password", [
    ("encrypt", lambda src, out: encrypt_pdf(str(src), str(out), "Gizli123"), "Gizli123"),
    ("decrypt", _decrypt, None),
    ("watermark", lambda src, out: add_watermark_to_pdf(str(src), str(out), "GIZLI"), None),
    ("split-all", lambda src, out: split_pdf(str(src), str(out), 1, 3), None),
    ("rotate", lambda src, out: rotate_pages_in_pdf(str(src), str(out), [1, 2, 3], 90), None),
    ("signature", _signature, None),
])
def test_whole_document_operations_keep_bookmarks_title_and_form(tmp_path, name, run, password):
    src = tmp_path / "sozlesme.pdf"
    rich_pdf(src)
    out = tmp_path / "cikti.pdf"

    run(src, out)

    assert pdf_structure(out, password) == WHOLE
    assert page_widths(out, password) == [595, 596, 597]


def test_metadata_changes_only_the_title(tmp_path):
    src = rich_pdf(tmp_path / "sozlesme.pdf")
    out = tmp_path / "cikti.pdf"

    update_metadata(src, str(out), title="New")

    assert pdf_structure(out) == {**WHOLE, "title": "New"}


def test_clearing_metadata_keeps_bookmarks_and_form(tmp_path):
    src = rich_pdf(tmp_path / "sozlesme.pdf")
    out = tmp_path / "cikti.pdf"

    update_metadata(src, str(out), clean=True)

    assert pdf_structure(out) == {**WHOLE, "title": None}


def test_the_form_keeps_its_value(tmp_path):
    from pypdf import PdfReader
    src = rich_pdf(tmp_path / "sozlesme.pdf")
    out = tmp_path / "cikti.pdf"

    encrypt_pdf(src, str(out), "Gizli123")

    reader = PdfReader(str(out))
    reader.decrypt("Gizli123")
    assert reader.get_fields()[RICH_FIELD].get("/V") == "Ayse"


# ── Operations that pick pages keep what belongs to those pages ──────────

@pytest.mark.parametrize("name, run, expected", [
    # "Giris" is on page 1 with the form field, "Ek" on page 3.
    ("delete-1", lambda src, out: delete_pages_from_pdf(src, out, [1]),
     {"outline": [("Ek", 2)], "fields": [], "widths": [596, 597]}),
    ("delete-2", lambda src, out: delete_pages_from_pdf(src, out, [2]),
     {"outline": [("Giris", 1), ("Ek", 2)], "fields": [RICH_FIELD], "widths": [595, 597]}),
    ("split-2-3", lambda src, out: split_pdf(src, out, 2, 3),
     {"outline": [("Ek", 2)], "fields": [], "widths": [596, 597]}),
    ("split-1-2", lambda src, out: split_pdf(src, out, 1, 2),
     {"outline": [("Giris", 1)], "fields": [RICH_FIELD], "widths": [595, 596]}),
    ("reorder", lambda src, out: reorder_pages_in_pdf(src, out, [3, 1, 2]),
     {"outline": [("Giris", 2), ("Ek", 1)], "fields": [RICH_FIELD], "widths": [597, 595, 596]}),
])
def test_page_picking_keeps_what_is_on_the_kept_pages(tmp_path, name, run, expected):
    src = rich_pdf(tmp_path / "sozlesme.pdf")
    out = str(tmp_path / "cikti.pdf")

    run(src, out)

    structure = pdf_structure(out)
    assert structure["outline"] == expected["outline"]
    assert structure["fields"] == expected["fields"]
    assert structure["title"] == RICH_TITLE
    assert page_widths(out) == expected["widths"]


def test_merge_keeps_every_files_bookmarks_and_the_first_files_info(tmp_path):
    first = rich_pdf(tmp_path / "sozlesme.pdf")
    second = make_pdf(tmp_path / "ek.pdf", pages=2)
    third = rich_pdf(tmp_path / "ikinci.pdf")
    out = str(tmp_path / "birlesik.pdf")

    merge_pdfs([first, second, third], out)

    structure = pdf_structure(out)
    assert structure["outline"] == RICH_OUTLINE + [("Giris", 6), ("Ek", 8)]
    assert structure["title"] == RICH_TITLE
    assert structure["acroform"] and RICH_FIELD in structure["fields"]
    assert len(page_widths(out)) == 8
