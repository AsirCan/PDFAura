"""OCR-based table detection for scanned pages (Faz 7 #2).

The grid detector is exercised on synthetic images; the full Tesseract path
is skipped when the binary is not installed, which is why the per-cell reader
can also be injected.
"""
import numpy as np
import pytest

from conftest import make_pdf
from src.core import tables

cv2 = pytest.importorskip("cv2")


def grid_image(width=600, height=400, second_grid=True):
    """A white page with two black table grids (5x3 and 2x2)."""
    image = np.full((height, width), 255, dtype=np.uint8)
    for x in (50, 200, 350, 550):
        cv2.line(image, (x, 50), (x, 300), 0, 2)
    for y in (50, 100, 150, 200, 250, 300):
        cv2.line(image, (50, y), (550, y), 0, 2)

    if second_grid:
        for x in (60, 160, 260):
            cv2.line(image, (x, 330), (x, 390), 0, 2)
        for y in (330, 390):
            cv2.line(image, (60, y), (260, y), 0, 2)
    return image


def scanned_grid_pdf(path, text=None, second_grid=False):
    """A PDF whose only content is an image, so it has no text layer."""
    image = grid_image(second_grid=second_grid)
    if text:
        for index, value in enumerate(text):
            cv2.putText(image, value, (65, 85 + index * 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 2, cv2.LINE_AA)
    ok, encoded = cv2.imencode(".png", image)
    assert ok

    import fitz
    doc = fitz.open()
    try:
        page = doc.new_page(width=300, height=200)
        page.insert_image(fitz.Rect(0, 0, 300, 200), stream=encoded.tobytes())
        doc.save(str(path))
    finally:
        doc.close()
    return str(path)


# ── Grid detection ────────────────────────────────────────────────────────

def test_detect_table_cells_finds_both_grids():
    grids = tables._detect_table_cells(grid_image())

    assert len(grids) == 2
    first, second = grids
    assert len(first) == 5
    assert all(len(row) == 3 for row in first)
    assert first[0][0] == (50, 50, 200, 100)
    assert first[-1][-1] == (350, 250, 550, 300)

    assert len(second) == 1
    assert len(second[0]) == 2


def test_detect_table_cells_ignores_a_page_without_lines():
    image = np.full((400, 600), 255, dtype=np.uint8)
    cv2.putText(image, "Just some text", (70, 120),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, 0, 2, cv2.LINE_AA)

    assert tables._detect_table_cells(image) == []


def test_detect_table_cells_is_optional_without_opencv(monkeypatch):
    monkeypatch.setattr(tables, "_opencv", lambda: (None, None))
    assert tables._detect_table_cells(grid_image()) == []


# ── Cell OCR ──────────────────────────────────────────────────────────────

def test_ocr_cells_reads_every_cell_with_the_reader():
    image = grid_image()
    cells = tables._detect_table_cells(image)[0]

    def reader(_image, box, _language):
        return f"{box[0]}x{box[1]}"

    rows = tables._ocr_cells(image, cells, "eng", reader=reader)

    assert len(rows) == 5
    assert rows[0][0] == "50x50"
    assert rows[-1][-1] == "350x250"


def test_ocr_cells_keeps_a_row_when_one_cell_fails():
    image = grid_image()
    cells = [[(0, 0, 10, 10), (20, 20, 30, 30)]]

    def reader(_image, box, _language):
        if box[0] == 0:
            raise RuntimeError("Tesseract failed")
        return "ok"

    assert tables._ocr_cells(image, cells, "eng", reader=reader) == [["", "ok"]]


def test_find_ocr_tables_is_skipped_without_tesseract(tmp_path, monkeypatch):
    import fitz

    pdf = scanned_grid_pdf(tmp_path / "scan.pdf")
    doc = fitz.open(pdf)
    try:
        monkeypatch.setattr(tables, "_tesseract_state", False)
        assert tables._find_ocr_tables(doc[0]) == []
    finally:
        doc.close()


# ── extract_tables integration ────────────────────────────────────────────

def test_ocr_fallback_returns_source_ocr_for_a_scanned_page(tmp_path, monkeypatch):
    pdf = make_pdf(tmp_path / "blank.pdf", pages=1)
    monkeypatch.setattr(tables, "_find_ocr_tables",
                        lambda page: [[["Urun", "Fiyat"], ["Kalem", "10"]]])

    found = tables.extract_tables(pdf)

    assert found == [{"page": 1, "rows": [["Urun", "Fiyat"], ["Kalem", "10"]],
                      "source": "ocr"}]


def test_scanned_grid_is_detected_before_cells_are_read(tmp_path, monkeypatch):
    pdf = scanned_grid_pdf(tmp_path / "scan.pdf")
    seen = {}

    def fake_ocr(image, cells, language):
        seen["tables"] = len(cells)
        seen["columns"] = [len(row) for row in cells]
        seen["language"] = language
        return [["Urun", "Adet", "Fiyat"], ["Kalem", "2", "10"]]

    monkeypatch.setattr(tables, "_tesseract_state", True)
    monkeypatch.setattr(tables, "_ocr_language", lambda: "eng")
    monkeypatch.setattr(tables, "_ocr_cells", fake_ocr)

    found = tables.extract_tables(pdf)

    assert seen == {"tables": 5, "columns": [3, 3, 3, 3, 3], "language": "eng"}
    assert found == [{"page": 1,
                      "rows": [["Urun", "Adet", "Fiyat"], ["Kalem", "2", "10"]],
                      "source": "ocr"}]


def test_pages_with_text_do_not_go_through_ocr(tmp_path, monkeypatch):
    import fitz

    pdf = tmp_path / "text.pdf"
    doc = fitz.open()
    try:
        page = doc.new_page()
        page.insert_text((72, 72), "Merhaba dunya", fontsize=11)
        doc.save(str(pdf))
    finally:
        doc.close()

    def fail(*_args, **_kwargs):
        raise AssertionError("OCR must not run on a page with a text layer")

    monkeypatch.setattr(tables, "_find_ocr_tables", fail)
    assert tables.extract_tables(str(pdf)) == []


def test_digital_tables_keep_their_old_structure(tmp_path):
    import fitz

    pdf = tmp_path / "digital.pdf"
    doc = fitz.open()
    try:
        page = doc.new_page()
        page.insert_text((72, 72), "A", fontsize=11)
        page.draw_line((60, 60), (200, 60), width=0.8)
        page.draw_line((60, 90), (200, 90), width=0.8)
        doc.save(str(pdf))
    finally:
        doc.close()

    # Any table found through the digital path must not gain a "source" key.
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(tables, "_find_pymupdf_tables",
                            lambda page: [[["A", "B"], ["1", "2"]]])
        found = tables.extract_tables(str(pdf))
    finally:
        monkeypatch.undo()

    assert found == [{"page": 1, "rows": [["A", "B"], ["1", "2"]]}]


@pytest.mark.skipif(not tables._tesseract_ready(),
                    reason="Tesseract is not installed")
def test_real_tesseract_reads_a_scanned_table(tmp_path):
    pdf = scanned_grid_pdf(tmp_path / "scan-text.pdf", text=["URUN", "KALEM"])

    found = tables.extract_tables(pdf)

    assert found and found[0]["source"] == "ocr"
    text = " ".join(cell for table in found for row in table["rows"] for cell in row)
    assert "URUN" in text.upper()
