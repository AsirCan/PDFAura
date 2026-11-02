"""Table extraction and XLSX/CSV/Markdown export (Faz 7)."""
import csv
import os
import zipfile
import xml.etree.ElementTree as ET

import fitz
import pytest

from conftest import make_pdf
from src.core import tables
from src.core.common import PdfPasswordError

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"m": MAIN_NS}

# Three different table layouts: a ruled grid, borderless aligned columns and
# an invoice-like list separated by horizontal rules.
LAYOUT_GRID = [
    ["Urun", "Adet", "Fiyat", "Tutar"],
    ["Kalem", "2", "10", "20"],
    ["Defter", "3", "15", "45"],
    ["Toplam", "", "", "65"],
]
LAYOUT_TEXT = [
    ["Tarih", "Aciklama", "Tutar"],
    ["01.01.2026", "Kira", "5000"],
    ["02.01.2026", "Elektrik", "750"],
]
LAYOUT_LINES = [
    ["Fatura No", "INV-2026-001", "Tarih", "01.02.2026"],
    ["Musteri", "Aura Ltd", "Vade", "15.02.2026"],
    ["Toplam", "1250 TL", "KDV", "225 TL"],
]


def _draw_grid(page, x0, y0, widths, heights, rows, fontsize=10):
    xs = [x0]
    for width in widths:
        xs.append(xs[-1] + width)
    ys = [y0]
    for height in heights:
        ys.append(ys[-1] + height)

    for x in xs:
        page.draw_line((x, ys[0]), (x, ys[-1]), color=(0, 0, 0), width=0.8)
    for y in ys:
        page.draw_line((xs[0], y), (xs[-1], y), color=(0, 0, 0), width=0.8)
    for row_index, row in enumerate(rows):
        for column_index, text in enumerate(row):
            if text:
                page.insert_text((xs[column_index] + 3, ys[row_index] + 15),
                                 text, fontsize=fontsize)


def make_table_pdf(path):
    """Four pages: ruled grid, borderless text, horizontal-rule list, two grids."""
    doc = fitz.open()
    try:
        page = doc.new_page(width=595, height=842)
        _draw_grid(page, 50, 60, [100, 80, 80, 80], [24] * len(LAYOUT_GRID), LAYOUT_GRID)

        page = doc.new_page(width=595, height=842)
        for row_index, row in enumerate(LAYOUT_TEXT):
            for column_index, text in enumerate(row):
                page.insert_text(([60, 200, 440][column_index], 100 + row_index * 26),
                                 text, fontsize=12)

        page = doc.new_page(width=595, height=842)
        x0, y0, row_height, column_width = 50, 80, 30, 110
        for row_index, row in enumerate(LAYOUT_LINES):
            for column_index, text in enumerate(row):
                page.insert_text((x0 + column_index * column_width,
                                  y0 + row_index * row_height + 18), text, fontsize=10)
            page.draw_line((x0, y0 + (row_index + 1) * row_height),
                           (x0 + 4 * column_width, y0 + (row_index + 1) * row_height),
                           color=(0, 0, 0), width=0.8)
        page.draw_line((x0, y0), (x0 + 4 * column_width, y0),
                       color=(0, 0, 0), width=0.8)

        page = doc.new_page(width=595, height=842)
        _draw_grid(page, 40, 60, [60, 60], [22, 22], [["A", "B"], ["1", "2"]], 9)
        _draw_grid(page, 320, 60, [60, 60], [22, 22], [["C", "D"], ["3", "4"]], 9)

        doc.save(str(path))
    finally:
        doc.close()
    return str(path)


# ── Extraction ────────────────────────────────────────────────────────────

def test_three_different_layouts_keep_their_rows_and_columns(tmp_path):
    pdf = make_table_pdf(tmp_path / "tables.pdf")

    found = tables.extract_tables(pdf)

    by_page = {}
    for table in found:
        by_page.setdefault(table["page"], []).append(table["rows"])
    assert by_page[1] == [LAYOUT_GRID]
    assert by_page[2] == [LAYOUT_TEXT]
    assert by_page[3] == [LAYOUT_LINES]
    assert len(found) == 5  # pages 1-3 plus the two grids on page 4


def test_multiple_tables_on_one_page_are_separate(tmp_path):
    pdf = make_table_pdf(tmp_path / "tables.pdf")

    page_four = [table for table in tables.extract_tables(pdf, pages=4)]

    assert [table["rows"] for table in page_four] == [
        [["A", "B"], ["1", "2"]],
        [["C", "D"], ["3", "4"]],
    ]
    assert all(table["page"] == 4 for table in page_four)


def test_pages_accepts_int_list_and_range_string(tmp_path):
    pdf = make_table_pdf(tmp_path / "tables.pdf")

    assert [t["page"] for t in tables.extract_tables(pdf, pages=2)] == [2]
    assert [t["page"] for t in tables.extract_tables(pdf, pages=[1, 3])] == [1, 3]
    # The fourth page holds two tables; both must come back.
    assert [t["page"] for t in tables.extract_tables(pdf, pages="1, 3-4")] == [1, 3, 4, 4]


@pytest.mark.parametrize("pages", [0, 5, -1, "9"])
def test_invalid_page_selection_is_rejected(tmp_path, pages):
    pdf = make_table_pdf(tmp_path / "tables.pdf")
    with pytest.raises(ValueError):
        tables.extract_tables(pdf, pages=pages)


def test_a_pdf_without_tables_gives_an_empty_list(tmp_path):
    pdf = make_pdf(tmp_path / "blank.pdf", pages=2)
    assert tables.extract_tables(pdf) == []


def test_password_protected_pdf_raises_the_common_error(tmp_path):
    source = make_table_pdf(tmp_path / "tables.pdf")
    locked = tmp_path / "locked.pdf"
    with fitz.open(source) as doc:
        doc.save(str(locked), encryption=fitz.PDF_ENCRYPT_AES_256,
                 user_pw="gizli", owner_pw="gizli")

    with pytest.raises(PdfPasswordError):
        tables.extract_tables(str(locked))


def test_pdfplumber_fallback_is_used_when_pymupdf_finds_nothing(tmp_path, monkeypatch):
    pdf = make_table_pdf(tmp_path / "tables.pdf")
    fallback = [[["X", "Y"], ["1", "2"]]]
    monkeypatch.setattr(tables, "_find_pymupdf_tables", lambda page: [])
    monkeypatch.setattr(tables, "_find_pdfplumber_tables",
                        lambda path, page: fallback if page == 1 else [])

    found = tables.extract_tables(pdf, pages=[1])

    assert found == [{"page": 1, "rows": [["X", "Y"], ["1", "2"]]}]


# ── Markdown ──────────────────────────────────────────────────────────────

def test_markdown_table_escapes_pipes_and_newlines():
    markdown = tables.to_markdown({
        "page": 1,
        "rows": [["Ad", "Not"], ["A|B", "line1\nline2"], ["C"]],
    })

    lines = markdown.splitlines()
    assert lines[0] == "| Ad | Not |"
    assert lines[1] == "| --- | --- |"
    assert lines[2] == "| A\\|B | line1<br>line2 |"
    assert lines[3] == "| C |  |"  # short rows are padded, not shifted


def test_markdown_accepts_a_plain_list_of_rows():
    assert tables.to_markdown([["A", "B"], ["1", "2"]]).splitlines()[0] == "| A | B |"


def test_markdown_of_an_empty_table_is_empty():
    assert tables.to_markdown({"page": 1, "rows": []}) == ""


# ── CSV ───────────────────────────────────────────────────────────────────

def test_csv_export_writes_one_utf8_bom_file_per_table(tmp_path):
    pdf = make_table_pdf(tmp_path / "tables.pdf")
    found = tables.extract_tables(pdf)

    written = tables.export_csv(found, str(tmp_path / "csv"))

    assert len(written) == len(found) == 5
    assert all(os.path.isfile(path) for path in written)
    assert open(written[0], "rb").read(3) == b"\xef\xbb\xbf"
    with open(written[0], encoding="utf-8-sig", newline="") as handle:
        assert list(csv.reader(handle)) == LAYOUT_GRID


def test_csv_export_does_not_overwrite_an_earlier_run(tmp_path):
    found = [{"page": 1, "rows": [["A"]]}]
    folder = str(tmp_path / "csv")

    first = tables.export_csv(found, folder)
    second = tables.export_csv(found, folder)

    assert first != second
    assert all(os.path.isfile(path) for path in first + second)


def test_csv_export_keeps_unicode(tmp_path):
    folder = str(tmp_path / "csv")
    written = tables.export_csv(
        [{"page": 1, "rows": [["Ürün", "İstanbul"], ["Ölçü", "Şube"]]}], folder)

    with open(written[0], encoding="utf-8-sig", newline="") as handle:
        assert list(csv.reader(handle)) == [["Ürün", "İstanbul"], ["Ölçü", "Şube"]]


# ── XLSX ──────────────────────────────────────────────────────────────────

def _text_of(element):
    return "".join(node.text or "" for node in element.iter(f"{{{MAIN_NS}}}t"))


def _column_index(ref):
    letters = "".join(char for char in ref if char.isalpha())
    index = 0
    for char in letters:
        index = index * 26 + ord(char.upper()) - ord("A") + 1
    return index


def read_xlsx(path):
    """Read sheet values from either openpyxl or the built-in writer."""
    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [_text_of(item) for item in root.findall("m:si", NS)]

        sheets = []
        names = [name for name in archive.namelist()
                 if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")]
        names.sort(key=lambda name: int(name.rsplit("sheet", 1)[1].split(".")[0]))
        for name in names:
            root = ET.fromstring(archive.read(name))
            rows = []
            for row in root.findall(".//m:sheetData/m:row", NS):
                values = {}
                for cell in row.findall("m:c", NS):
                    column = _column_index(cell.get("r", "A1")) - 1
                    if cell.get("t") == "inlineStr":
                        text = _text_of(cell)
                    else:
                        value = cell.find("m:v", NS)
                        text = "" if value is None else (value.text or "")
                        if cell.get("t") == "s" and text:
                            text = shared[int(text)]
                    values[column] = text
                width = max(values) + 1 if values else 0
                rows.append([values.get(column, "") for column in range(width)])
            sheets.append(rows)
    return sheets


def test_xlsx_export_has_one_sheet_per_table_with_the_same_rows(tmp_path):
    pdf = make_table_pdf(tmp_path / "tables.pdf")
    found = tables.extract_tables(pdf)
    output = tmp_path / "tables.xlsx"

    tables.export_xlsx(found, str(output))

    assert os.path.isfile(output)
    sheets = read_xlsx(output)
    assert len(sheets) == len(found) == 5
    assert sheets[0] == LAYOUT_GRID
    assert sheets[1] == LAYOUT_TEXT
    assert sheets[2] == LAYOUT_LINES
    assert sheets[3] == [["A", "B"], ["1", "2"]]
    assert sheets[4] == [["C", "D"], ["3", "4"]]


def test_xlsx_builtin_writer_works_without_openpyxl(tmp_path):
    output = tmp_path / "fallback.xlsx"
    source = [{"page": 2, "rows": [["Ürün", "Not"], ["Çay", "A|B"]]}]

    tables._write_xlsx_without_openpyxl(source, str(output))

    assert read_xlsx(output) == [[["Ürün", "Not"], ["Çay", "A|B"]]]


def test_xlsx_export_rejects_an_empty_table_list(tmp_path):
    with pytest.raises(ValueError):
        tables.export_xlsx([], str(tmp_path / "empty.xlsx"))
    assert not (tmp_path / "empty.xlsx").exists()
