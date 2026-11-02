"""Extract tables from PDFs and export them as XLSX, CSV or Markdown.

PyMuPDF's ``find_tables`` handles digital PDFs: it first looks for ruled
tables, then for borderless tables whose columns line up. When it finds
nothing, pdfplumber is used if it happens to be installed. Pages without a
text layer (scans and photos) are rendered and their table grid is found
with OpenCV; each cell is then read with Tesseract when it is available.
openpyxl is used for XLSX when available; otherwise a small built-in writer
produces the same Office Open XML format, so exporting never depends on an
extra package.
"""
import csv
import os
import zipfile
from xml.sax.saxutils import escape, quoteattr

from src.core.lang_manager import _
from src.core.output_paths import atomic_output, unique_path

# Tables coming from the OCR path carry this marker so callers can tell them
# apart from digital extraction without breaking the existing structure.
OCR_SOURCE = "ocr"

# Rendering at ~216 dpi keeps small table text readable for Tesseract while
# still fitting an A4 page comfortably in memory.
OCR_RENDER_SCALE = 3.0
OCR_MIN_TABLE_SIZE = 40       # pixels
OCR_LINE_SPAN_RATIO = 0.35    # a line must cover this much of the table width

_tesseract_state = None


def extract_tables(pdf_path, pages=None):
    if "\x00" in str(pdf_path):
        raise ValueError("Path contains invalid null character")
    """Return the tables found in *pdf_path*.

    Each table is ``{"page": 1-based page number, "rows": [[cell, ...], ...]}``.
    *pages* limits the work to those pages: None means every page, an int or
    an iterable of ints is accepted, and a string such as "1, 3-4" is parsed
    with the same rules as the rest of the app. Values are strings; missing
    cells are "" so row/column positions stay intact.

    Encrypted files raise PdfPasswordError through the normal PyMuPDF check.
    """
    import fitz

    from src.core.common import PdfPasswordError

    doc = fitz.open(pdf_path)
    try:
        if doc.needs_pass:
            raise PdfPasswordError(_("err_pdf_password_protected"))

        selected = _selected_pages(pages, doc.page_count)
        tables = []
        for page_number in selected:
            page = doc.load_page(page_number - 1)
            page_tables = _find_pymupdf_tables(page)
            if not page_tables:
                page_tables = _find_pdfplumber_tables(pdf_path, page_number)
            for rows in page_tables:
                tables.append({"page": page_number, "rows": rows})

            # Digital extraction found nothing. Only pages without a text
            # layer are scans/Photoshop output, so run the OCR path there; a
            # page with text but no table should stay empty rather than going
            # through Tesseract again.
            if not page_tables and not _has_text_layer(page):
                for rows in _find_ocr_tables(page):
                    tables.append({"page": page_number, "rows": rows,
                                   "source": OCR_SOURCE})
        return tables
    finally:
        doc.close()


def to_markdown(table):
    """Render one table as a GitHub-flavoured Markdown table.

    *table* is a table dict from extract_tables or a plain list of rows.
    Pipes and line breaks inside cells are escaped so the preview stays a
    valid table when the user copies it elsewhere.
    """
    rows = _table_rows(table)
    if not rows:
        return ""

    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    header = rows[0]
    lines = [
        "| " + " | ".join(_markdown_cell(cell) for cell in header) + " |",
        "| " + " | ".join("---" for _ in range(width)) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(_markdown_cell(cell) for cell in row) + " |")
    return "\n".join(lines)


def export_csv(tables, folder):
    if "\x00" in str(folder):
        raise ValueError("Folder contains invalid null character")
    """Write every table to its own UTF-8 CSV file and return the paths.

    The BOM keeps Turkish characters readable when the file is opened in
    Excel; the file names are made unique so exporting twice does not
    overwrite the first result.
    """
    folder_abs = os.path.abspath(folder)
    os.makedirs(folder_abs, exist_ok=True)
    written = []
    for index, table in enumerate(tables, 1):
        page = _table_page(table, index)
        name = f"page_{page:03d}_table_{index:02d}.csv"
        path = unique_path(os.path.join(folder_abs, name))
        if not os.path.abspath(path).startswith(folder_abs + os.sep):
            raise ValueError("Output escapes directory")
        with atomic_output(path) as temp_path:
            with open(temp_path, "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerows(_table_rows(table))
        written.append(path)
    return written


def export_xlsx(tables, path):
    if "\x00" in str(path):
        raise ValueError("Path contains invalid null character")
    """Write all tables to one XLSX workbook, one worksheet per table.

    openpyxl is used when installed. Without it the workbook is written with
    zipfile and the Office Open XML schema directly, so the feature still
    works on a minimal install. There is no dependency on pandas or Excel.
    """
    tables = list(tables)
    if not tables:
        raise ValueError("No tables to export.")

    try:
        from openpyxl import Workbook
        workbook = Workbook()
    except Exception:  # not installed -- use the built-in writer
        _write_xlsx_without_openpyxl(tables, path)
        return path

    for index, table in enumerate(tables, 1):
        if index == 1:
            sheet = workbook.active
            sheet.title = _sheet_name(table, index)
        else:
            sheet = workbook.create_sheet(_sheet_name(table, index))
        for row in _table_rows(table):
            sheet.append(row)
    try:
        with atomic_output(path) as temp_path:
            workbook.save(temp_path)
    finally:
        try:
            workbook.close()
        except Exception:
            pass
    return path


# ── Extraction helpers ────────────────────────────────────────────────────

def _selected_pages(pages, total):
    """Turn *pages* into sorted 1-based page numbers within 1..total."""
    if pages is None:
        return list(range(1, total + 1))

    if isinstance(pages, str):
        from src.core.common import parse_page_numbers
        return parse_page_numbers(pages, total)

    if isinstance(pages, int):
        wanted = [pages]
    else:
        wanted = list(pages)

    for page in wanted:
        if not isinstance(page, int) or page < 1 or page > total:
            raise ValueError(_("err_invalid_page").format(page=page))
    return sorted(set(wanted))


def _find_pymupdf_tables(page):
    """Rows for every table PyMuPDF sees on *page*.

    Ruled tables are tried first. The "text" strategy is only used when that
    finds nothing, because it also turns ordinary multi-column text into a
    table.
    """
    for strategy in ("lines", "text"):
        try:
            found = page.find_tables(strategy=strategy)
        except TypeError:
            # PyMuPDF before the strategy argument: the default is "lines".
            if strategy != "lines":
                continue
            try:
                found = page.find_tables()
            except Exception:
                return []
        except Exception:
            continue

        tables = []
        for table in getattr(found, "tables", []):
            try:
                rows = _clean_rows(table.extract())
            except Exception:
                continue
            if rows:
                tables.append(rows)
        if tables:
            return tables
    return []


def _find_pdfplumber_tables(pdf_path, page_number):
    """Optional fallback for layouts MuPDF misses. Missing pdfplumber is fine."""
    try:
        import pdfplumber
    except Exception:
        return []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_number > len(pdf.pages):
                return []
            raw_tables = pdf.pages[page_number - 1].extract_tables()
    except Exception:
        return []

    tables = []
    for raw in raw_tables or []:
        rows = _clean_rows(raw)
        if rows:
            tables.append(rows)
    return tables


# ── OCR extraction for scanned pages ─────────────────────────────────────

def _has_text_layer(page):
    """True when the page already contains selectable text."""
    try:
        return bool(page.get_text("text").strip())
    except Exception:
        return False


def _opencv():
    """Return (cv2, numpy) or (None, None); OpenCV stays optional."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None, None
    return cv2, np


def _tesseract_ready():
    """True when pytesseract and a Tesseract binary can actually be used."""
    global _tesseract_state
    if _tesseract_state is None:
        try:
            from src.core.ocr import check_tesseract_availability
            _tesseract_state = bool(check_tesseract_availability())
        except Exception:
            _tesseract_state = False
    return _tesseract_state


def _ocr_language():
    """Best installed Tesseract language string, or "eng" as a last resort."""
    try:
        from src.core.ocr import resolve_ocr_language
        return resolve_ocr_language()
    except Exception:
        return "eng"


def _render_page_gray(page):
    """Render *page* as a grayscale NumPy image, or None when unavailable."""
    _cv2, np = _opencv()
    if np is None:
        return None
    import fitz

    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(OCR_RENDER_SCALE, OCR_RENDER_SCALE),
                              colorspace=fitz.csGRAY, alpha=False)
        stride = getattr(pix, "stride", pix.width)
        samples = np.frombuffer(pix.samples, dtype=np.uint8)
        image = samples.reshape(pix.height, stride)[:, :pix.width]
        return image.copy()
    except Exception:
        return None


def _detect_table_cells(image):
    """Return grids of cell rectangles found in a grayscale page image.

    The result is a list of tables; each table is a list of rows, each row a
    list of ``(x0, y0, x1, y1)`` boxes in image pixels. Long horizontal and
    vertical strokes are isolated with morphology, then their projections
    inside each connected table outline give the row and column positions.
    """
    cv2, np = _opencv()
    if cv2 is None or image is None or not getattr(image, "size", 0):
        return []

    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)

    height, width = image.shape[:2]
    if height < OCR_MIN_TABLE_SIZE or width < OCR_MIN_TABLE_SIZE:
        return []

    _threshold, binary = cv2.threshold(
        image, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    horizontal_kernel = max(15, width // 40)
    vertical_kernel = max(15, height // 40)
    horizontal = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN,
        np.ones((1, horizontal_kernel), dtype=np.uint8))
    vertical = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN,
        np.ones((vertical_kernel, 1), dtype=np.uint8))

    combined = cv2.add(horizontal, vertical)
    # Close one- or two-pixel gaps at intersections before grouping outlines.
    combined = cv2.dilate(combined, np.ones((3, 3), dtype=np.uint8), iterations=1)
    contours, _hierarchy = cv2.findContours(
        combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    tables = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w < OCR_MIN_TABLE_SIZE or h < OCR_MIN_TABLE_SIZE:
            continue
        rows = _line_positions(horizontal, x, y, w, h, axis=1)
        columns = _line_positions(vertical, x, y, w, h, axis=0)
        if len(rows) < 2 or len(columns) < 2:
            continue
        tables.append(_cells_from_grid(rows, columns))
    tables.sort(key=lambda grid: (grid[0][0][1], grid[0][0][0]))
    return tables


def _line_positions(band, x, y, width, height, axis):
    """Centre positions of the thick strokes inside a table outline.

    *axis* 1 projects horizontal strokes onto y (rows), 0 projects vertical
    strokes onto x (columns). Consecutive pixels of one thick line are grouped
    into a single position so the grid is not doubled.
    """
    crop = band[y:y + height, x:x + width]
    if not getattr(crop, "size", 0):
        return []
    counts = (crop > 0).sum(axis=axis)
    span = width if axis == 1 else height
    threshold = max(3, int(span * OCR_LINE_SPAN_RATIO))

    positions = []
    start = None
    for index, count in enumerate(counts):
        if count >= threshold:
            if start is None:
                start = index
        elif start is not None:
            positions.append((start + index - 1) // 2)
            start = None
    if start is not None:
        positions.append((start + len(counts) - 1) // 2)

    offset = y if axis == 1 else x
    return [position + offset for position in positions]


def _cells_from_grid(rows, columns):
    """Turn row/column line positions into a table of cell rectangles."""
    return [
        [(columns[column], rows[row], columns[column + 1], rows[row + 1])
         for column in range(len(columns) - 1)]
        for row in range(len(rows) - 1)
    ]


def _find_ocr_tables(page):
    """Rows for the table grids OCR finds on a scan, or an empty list."""
    if _has_text_layer(page) or not _tesseract_ready():
        return []
    image = _render_page_gray(page)
    if image is None:
        return []

    grids = _detect_table_cells(image)
    if not grids:
        return []
    language = _ocr_language()
    tables = []
    for cells in grids:
        rows = _clean_rows(_ocr_cells(image, cells, language))
        if rows:
            tables.append(rows)
    return tables


def _ocr_cells(image, cells, language, reader=None):
    """Read every cell rectangle with Tesseract, skipping failures per cell."""
    read = reader or _read_cell_text
    rows = []
    for cell_row in cells:
        values = []
        for box in cell_row:
            try:
                values.append(read(image, box, language))
            except Exception:
                values.append("")
        if any(value.strip() for value in values):
            rows.append(values)
    return rows


def _read_cell_text(image, box, language):
    """OCR one cell; returns its text collapsed onto a single line."""
    import pytesseract

    cv2, _np = _opencv()
    if cv2 is None:
        return ""

    x0, y0, x1, y1 = (int(round(value)) for value in box)
    padding = max(2, (y1 - y0) // 20)
    crop = image[y0 + padding:y1 - padding, x0 + padding:x1 - padding]
    if crop.size == 0:
        return ""
    if crop.shape[0] < 20:
        crop = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    kwargs = {"config": "--psm 6"}
    if language:
        kwargs["lang"] = language
    text = pytesseract.image_to_string(crop, **kwargs)
    return " ".join(text.split())


def _clean_rows(raw_rows):
    """Normalise extracted cells and drop empty padding rows/columns."""
    rows = []
    for raw in raw_rows or []:
        row = []
        for cell in raw:
            text = "" if cell is None else str(cell)
            row.append(text.strip())
        if any(row):
            rows.append(row)
    if not rows:
        return []

    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    keep = [column for column in range(width)
            if any(row[column] for row in rows)]
    if len(keep) != width:
        rows = [[row[column] for column in keep] for row in rows]
    return rows


# ── Table/row helpers shared by the exporters ─────────────────────────────

def _table_rows(table):
    """Rows of a table dict or a plain list, padded to equal width."""
    rows = table.get("rows") if isinstance(table, dict) else table
    normalised = []
    for row in rows or []:
        if isinstance(row, (str, bytes)):
            row = [row]
        normalised.append(["" if cell is None else str(cell) for cell in row])
    if not normalised:
        return []
    width = max(len(row) for row in normalised)
    return [row + [""] * (width - len(row)) for row in normalised]


def _table_page(table, index):
    if isinstance(table, dict) and table.get("page") is not None:
        try:
            return int(table["page"])
        except (TypeError, ValueError):
            pass
    return index


def _markdown_cell(value):
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("|", "\\|").replace("\n", "<br>").strip()


def _sheet_name(table, index):
    page = _table_page(table, index)
    name = f"Page {page} Table {index}"
    for char in '[]:*?/\\':
        name = name.replace(char, "_")
    return name[:31]


# ── XLSX without openpyxl ─────────────────────────────────────────────────

_XLSX_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_XLSX_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _write_xlsx_without_openpyxl(tables, path):
    """Write a minimal but valid Office Open XML workbook with the stdlib."""
    sheet_names = [_sheet_name(table, index) for index, table in enumerate(tables, 1)]
    sheet_paths = [f"worksheets/sheet{index}.xml" for index in range(1, len(tables) + 1)]

    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
    ]
    for index in range(1, len(tables) + 1):
        content_types.append(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    content_types.append("</Types>")

    workbook_sheets = []
    workbook_rels = []
    for index, (name, target) in enumerate(zip(sheet_names, sheet_paths), 1):
        workbook_sheets.append(
            f'<sheet name={quoteattr(name)} sheetId="{index}" r:id="rId{index}"/>')
        workbook_rels.append(
            f'<Relationship Id="rId{index}" Type="{_XLSX_REL_NS}/worksheet" '
            f'Target="{target}"/>')
    styles_id = len(tables) + 1
    workbook_rels.append(
        f'<Relationship Id="rId{styles_id}" Type="{_XLSX_REL_NS}/styles" '
        'Target="styles.xml"/>')

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{_XLSX_MAIN_NS}" xmlns:r="{_XLSX_REL_NS}">'
        "<sheets>" + "".join(workbook_sheets) + "</sheets></workbook>")

    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PACKAGE_REL_NS}">'
        + "".join(workbook_rels) + "</Relationships>")

    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PACKAGE_REL_NS}">'
        f'<Relationship Id="rId1" Type="{_XLSX_REL_NS}/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>')

    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<styleSheet xmlns="{_XLSX_MAIN_NS}">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
        '<cellXfs count="1"><xf xfId="0"/></cellXfs>'
        "</styleSheet>")

    with atomic_output(path) as temp_path:
        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", "".join(content_types))
            archive.writestr("_rels/.rels", root_rels_xml)
            archive.writestr("xl/workbook.xml", workbook_xml)
            archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
            archive.writestr("xl/styles.xml", styles_xml)
            for index, table in enumerate(tables, 1):
                archive.writestr(f"xl/worksheets/sheet{index}.xml",
                                 _sheet_xml(_table_rows(table)))


def _sheet_xml(rows):
    """A worksheet where every value is stored as an inline string."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<worksheet xmlns="{_XLSX_MAIN_NS}"><sheetData>',
    ]
    for row_number, row in enumerate(rows, 1):
        parts.append(f'<row r="{row_number}">')
        for column, value in enumerate(row, 1):
            ref = f"{_column_letter(column)}{row_number}"
            parts.append(
                f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">'
                f"{escape(value)}</t></is></c>")
        parts.append("</row>")
    parts.append("</sheetData></worksheet>")
    return "".join(parts)


def _column_letter(number):
    """1 -> A, 26 -> Z, 27 -> AA."""
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters
