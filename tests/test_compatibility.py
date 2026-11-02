"""Compatibility tests for various PDF formats and Windows 10/11 path edge cases.

Covers:
(1) Various PDF versions and specifications:
    - PDF 1.3, 1.4, 1.5, 1.6, 1.7
    - Linearized PDF (Fast Web View / Annex F parameter dictionary)
    - PDF with form fields / AcroForm
    - PDF with annotations (highlight, text note, rectangle)
    - PDF with mixed portrait/landscape and rotated pages
    - PDF with embedded fonts vs pure vector paths
(2) Windows 10/11 path edge cases:
    - MAX_PATH (> 260 characters)
    - Spaces in folder and file names
    - Non-ASCII / Unicode paths (Turkish, Cyrillic, Arabic, Chinese characters)
    - Read-only destination directory permissions
    - Locking file handles during processing
(3) Cross-feature compatibility pipeline:
    - compress -> split -> watermark -> redact -> smart_rename sequentially
"""

import errno
import io
import os
import shutil
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import fitz
import pypdf
import pytest

from conftest import leftovers
from src.core.compress import compress_pdf
from src.core.output_paths import atomic_output
from src.core.redact import apply_redactions, find_sensitive
from src.core.security import add_watermark_to_pdf
from src.core.smart_namer import (
    apply_batch_rename,
    plan_batch_rename,
    suggest_filename,
)
from src.core.split import split_pdf

# ─────────────────────────────────────────────────────────────────────────────
# Helper PDF Generators for Diverse Formats
# ─────────────────────────────────────────────────────────────────────────────


def _create_versioned_pdf(path: Path | str, version: str, text: str = "Versioned PDF") -> str:
    """Create a valid PDF with an explicit PDF version header (1.3 to 1.7)."""
    writer = pypdf.PdfWriter()
    writer.pdf_header = f"%PDF-{version}".encode("ascii")
    page = writer.add_blank_page(width=595, height=842)
    
    # Also add text content using PyMuPDF to test mixed reader compatibility
    temp_buf = io.BytesIO()
    writer.write(temp_buf)
    temp_buf.seek(0)
    
    doc = fitz.open(stream=temp_buf.getvalue(), filetype="pdf")
    doc[0].insert_text((72, 100), f"Document PDF {version}: {text}", fontsize=12)
    # Ensure header byte preservation
    out_bytes = doc.tobytes()
    target_header = f"%PDF-{version}".encode("ascii")
    if not out_bytes.startswith(target_header):
        out_bytes = target_header + out_bytes[8:]
    
    with open(path, "wb") as f:
        f.write(out_bytes)
    return str(path)


def _create_linearized_pdf(path: Path | str, text: str = "Linearized Document") -> str:
    """Synthesize a conforming Linearized PDF with calculated xref and parameters."""
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    obj1_tmpl = b"1 0 obj\n<< /Linearized 1.0 /L %d /H [ %d %d ] /O 4 /E %d /N 1 /T %d >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Catalog /Pages 3 0 R >>\nendobj\n"
    obj3 = b"3 0 obj\n<< /Type /Pages /Kids [4 0 R] /Count 1 >>\nendobj\n"
    stream_content = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET".encode("utf-8")
    obj5 = b"5 0 obj\n<< /Length " + str(len(stream_content)).encode() + b" >>\nstream\n" + stream_content + b"\nendstream\nendobj\n"
    obj6 = b"6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    obj4 = b"4 0 obj\n<< /Type /Page /Parent 3 0 R /MediaBox [0 0 612 792] /Contents 5 0 R /Resources << /Font << /F1 6 0 R >> >> >>\nendobj\n"

    # Compute byte offsets iteratively
    L, H0, H1, E, T = 1200, 100, 100, 500, 800
    objs = []
    xref = b""
    trailer = b""
    for _ in range(6):
        o1 = obj1_tmpl % (L, H0, H1, E, T)
        objs = [o1, obj2, obj3, obj4, obj5, obj6]
        offsets = [0]
        cur = len(header)
        for o in objs:
            offsets.append(cur)
            cur += len(o)
        startxref = cur
        xref_lines = [b"xref\n0 7\n0000000000 65535 f \n"]
        for off in offsets[1:]:
            xref_lines.append(f"{off:010d} 00000 n \n".encode("ascii"))
        xref = b"".join(xref_lines)
        trailer = b"trailer\n<< /Size 7 /Root 2 0 R >>\nstartxref\n" + str(startxref).encode("ascii") + b"\n%%EOF\n"
        L = cur + len(xref) + len(trailer)
        H0 = offsets[2]
        H1 = len(obj2)
        E = offsets[4] + len(obj4)
        T = startxref

    content = header + b"".join(objs) + xref + trailer
    with open(path, "wb") as f:
        f.write(content)
    return str(path)


def _create_acroform_pdf(path: Path | str, field_name: str = "customer_name", field_val: str = "Ahmet Yilmaz") -> str:
    """Create a PDF with interactive AcroForm fields."""
    doc = fitz.open()
    try:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), "FATURA FORMU", fontsize=14)
        
        # Add text field widget
        widget = fitz.Widget()
        widget.field_name = field_name
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect = fitz.Rect(72, 100, 300, 130)
        widget.field_value = field_val
        page.add_widget(widget)
        
        # Add checkbox widget
        chk = fitz.Widget()
        chk.field_name = "approved_flag"
        chk.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
        chk.rect = fitz.Rect(72, 140, 92, 160)
        chk.field_value = "Yes"
        page.add_widget(chk)
        
        doc.save(str(path))
    finally:
        doc.close()
    return str(path)


def _create_annotated_pdf(path: Path | str) -> str:
    """Create a PDF containing diverse annotation types (highlight, sticky note, rect)."""
    doc = fitz.open()
    try:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), "RAPOR: Gizli finansal veriler icerir.", fontsize=12)
        
        # Highlight annotation
        page.add_highlight_annot(fitz.Rect(70, 68, 250, 88))
        # Text popup note annotation
        page.add_text_annot(fitz.Point(300, 72), "Muhasebe departmani incelemeli.")
        # Rectangle annotation
        page.add_rect_annot(fitz.Rect(50, 50, 500, 200))
        
        doc.save(str(path))
    finally:
        doc.close()
    return str(path)


def _create_mixed_orientations_pdf(path: Path | str) -> str:
    """Create a document mixing A4 portrait, A4 landscape, Letter portrait, and rotated page."""
    doc = fitz.open()
    try:
        # Page 1: Portrait A4 (595 x 842)
        p1 = doc.new_page(width=595, height=842)
        p1.insert_text((72, 100), "Sayfa 1 - A4 Dikey", fontsize=14)
        
        # Page 2: Landscape A4 (842 x 595)
        p2 = doc.new_page(width=842, height=595)
        p2.insert_text((72, 100), "Sayfa 2 - A4 Yatay", fontsize=14)
        
        # Page 3: Letter Portrait (612 x 792)
        p3 = doc.new_page(width=612, height=792)
        p3.insert_text((72, 100), "Sayfa 3 - Letter Dikey", fontsize=14)
        
        # Page 4: Rotated 90 degrees
        p4 = doc.new_page(width=595, height=842)
        p4.insert_text((72, 100), "Sayfa 4 - Rotated 90", fontsize=14)
        p4.set_rotation(90)
        
        doc.save(str(path))
    finally:
        doc.close()
    return str(path)


def _create_embedded_font_pdf(path: Path | str, text: str = "Embedded Font Text") -> str:
    """Create a PDF with text rendered using standard embedded Type1/TrueType fonts."""
    doc = fitz.open()
    try:
        page = doc.new_page(width=595, height=842)
        font_path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf")
        if os.path.isfile(font_path):
            page.insert_font(fontname="f0", fontfile=font_path, set_simple=False)
            page.insert_textbox(fitz.Rect(72, 72, 500, 150), text, fontname="f0", fontsize=14)
        else:
            page.insert_text((72, 100), text, fontname="helv", fontsize=16)
        page.insert_text((72, 180), "Metin Satiri: TR33 0006 1005 1978 6457 8413 26", fontname="courier", fontsize=12)
        doc.save(str(path))
    finally:
        doc.close()
    return str(path)


def _create_vector_paths_pdf(path: Path | str) -> str:
    """Create a PDF containing only vector graphics paths (rectangles, bezier curves, circles)."""
    doc = fitz.open()
    try:
        page = doc.new_page(width=595, height=842)
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(50, 50, 200, 200))
        shape.draw_circle(fitz.Point(350, 150), 60)
        shape.draw_bezier(fitz.Point(50, 300), fitz.Point(150, 450), fitz.Point(300, 200), fitz.Point(450, 350))
        shape.finish(color=(0.2, 0.4, 0.8), fill=(0.9, 0.9, 0.9), width=2)
        shape.commit()
        doc.save(str(path))
    finally:
        doc.close()
    return str(path)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Various PDF Versions and Specifications Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("version", ["1.3", "1.4", "1.5", "1.6", "1.7"])
def test_pdf_versions_specification_compatibility(tmp_path, version):
    """Verify that PDFAura correctly parses, splits, and compresses PDF versions 1.3 through 1.7."""
    pdf_in = tmp_path / f"test_v{version.replace('.', '_')}.pdf"
    _create_versioned_pdf(pdf_in, version, f"Compatibility check for v{version}")
    
    # PyMuPDF and pypdf load tests
    reader = pypdf.PdfReader(str(pdf_in))
    assert reader.pdf_header.startswith(f"%PDF-{version}")
    assert len(reader.pages) == 1
    
    doc = fitz.open(str(pdf_in))
    assert doc.page_count == 1
    assert "Document PDF" in doc[0].get_text()
    doc.close()
    
    # Split operation
    pdf_split = tmp_path / f"split_v{version.replace('.', '_')}.pdf"
    split_pdf(str(pdf_in), str(pdf_split), 1, 1)
    assert pdf_split.exists()
    assert pdf_split.stat().st_size > 0
    
    # Compression operation
    pdf_comp = tmp_path / f"comp_v{version.replace('.', '_')}.pdf"
    compress_pdf(str(pdf_split), str(pdf_comp), "screen")
    assert pdf_comp.exists()
    assert pdf_comp.stat().st_size > 0


def test_linearized_fast_web_view_pdf(tmp_path):
    """Verify compatibility with Linearized PDFs having Annex F parameter dictionaries."""
    lin_pdf = tmp_path / "linearized_sample.pdf"
    _create_linearized_pdf(lin_pdf, "Linearized Fast Web View Test Document")
    
    # Check reading
    doc = fitz.open(str(lin_pdf))
    assert doc.page_count == 1
    text = doc[0].get_text()
    assert "Linearized Fast Web View" in text
    doc.close()
    
    # Watermarking on linearized input
    wm_pdf = tmp_path / "linearized_watermarked.pdf"
    add_watermark_to_pdf(str(lin_pdf), str(wm_pdf), "LINEARIZED")
    assert wm_pdf.exists()
    
    # Verify resulting document is valid and readable
    doc_wm = fitz.open(str(wm_pdf))
    assert doc_wm.page_count == 1
    doc_wm.close()


def test_acroform_form_fields_preservation(tmp_path):
    """Verify that AcroForm and interactive form widgets survive split and watermark."""
    form_pdf = tmp_path / "acroform_doc.pdf"
    _create_acroform_pdf(form_pdf, "musteri_adi", "Fatma Demir")
    
    # Check initial form fields
    r_init = pypdf.PdfReader(str(form_pdf))
    assert "/AcroForm" in r_init.trailer["/Root"]
    
    # Split
    split_out = tmp_path / "form_split.pdf"
    split_pdf(str(form_pdf), str(split_out), 1, 1)
    r_split = pypdf.PdfReader(str(split_out))
    assert "/AcroForm" in r_split.trailer["/Root"]
    
    # Watermark
    wm_out = tmp_path / "form_watermarked.pdf"
    add_watermark_to_pdf(str(split_out), str(wm_out), "TASLAK")
    r_wm = pypdf.PdfReader(str(wm_out))
    assert "/AcroForm" in r_wm.trailer["/Root"]


def test_annotations_compatibility(tmp_path):
    """Verify that PDF annotations (highlight, notes, shapes) are handled cleanly."""
    annot_pdf = tmp_path / "annotated_doc.pdf"
    _create_annotated_pdf(annot_pdf)
    
    # Check initial annotations
    doc = fitz.open(str(annot_pdf))
    annots = list(doc[0].annots())
    assert len(annots) >= 2
    doc.close()
    
    # Split preserving page
    split_out = tmp_path / "annot_split.pdf"
    split_pdf(str(annot_pdf), str(split_out), 1, 1)
    
    doc_split = fitz.open(str(split_out))
    assert doc_split.page_count == 1
    doc_split.close()
    
    # Watermark annotated page
    wm_out = tmp_path / "annot_watermarked.pdf"
    add_watermark_to_pdf(str(split_out), str(wm_out), "KONTROL")
    assert wm_out.exists()


def test_mixed_portrait_landscape_and_rotated_pages(tmp_path):
    """Verify handling of documents with heterogeneous page geometries and rotations."""
    mixed_pdf = tmp_path / "mixed_geometries.pdf"
    _create_mixed_orientations_pdf(mixed_pdf)
    
    # Verify dimensions
    doc = fitz.open(str(mixed_pdf))
    assert doc.page_count == 4
    assert round(doc[0].rect.width) == 595
    assert round(doc[1].rect.width) == 842
    assert round(doc[2].rect.width) == 612
    doc.close()
    
    # Watermark mixed pages: watermark geometry is computed dynamically per page
    wm_out = tmp_path / "mixed_watermarked.pdf"
    add_watermark_to_pdf(str(mixed_pdf), str(wm_out), "GEOMETRY TEST")
    
    doc_wm = fitz.open(str(wm_out))
    assert doc_wm.page_count == 4
    assert round(doc_wm[0].rect.width) == 595
    assert round(doc_wm[1].rect.width) == 842
    doc_wm.close()
    
    # Split a landscape page out
    landscape_split = tmp_path / "landscape_only.pdf"
    split_pdf(str(wm_out), str(landscape_split), 2, 2)
    doc_ls = fitz.open(str(landscape_split))
    assert doc_ls.page_count == 1
    assert round(doc_ls[0].rect.width) == 842
    doc_ls.close()


def test_embedded_fonts_vs_vector_paths(tmp_path):
    """Verify processing of documents with embedded fonts vs pure vector graphics."""
    # 1. Embedded fonts document
    font_pdf = tmp_path / "font_sample.pdf"
    _create_embedded_font_pdf(font_pdf, "Embedded Fonts Test Heading")
    
    # Compress font PDF (subsets fonts)
    font_comp = tmp_path / "font_compressed.pdf"
    compress_pdf(str(font_pdf), str(font_comp), "screen")
    doc_font = fitz.open(str(font_comp))
    extracted = doc_font[0].get_text().replace("\xa0", " ")
    assert "Embedded Fonts Test Heading" in extracted
    doc_font.close()
    
    # 2. Vector paths document (no text layer)
    vec_pdf = tmp_path / "vector_sample.pdf"
    _create_vector_paths_pdf(vec_pdf)
    
    # Compress pure vector paths
    vec_comp = tmp_path / "vector_compressed.pdf"
    compress_pdf(str(vec_pdf), str(vec_comp), "screen")
    doc_vec = fitz.open(str(vec_comp))
    assert doc_vec[0].get_text() == ""  # Zero text glyphs
    doc_vec.close()
    
    # Redaction on vector-only PDF (no text to detect, should complete gracefully)
    matches = find_sensitive(str(vec_pdf))
    assert matches == []
    vec_redact = tmp_path / "vector_redacted.pdf"
    apply_redactions(str(vec_pdf), matches, str(vec_redact))
    assert vec_redact.exists()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Windows 10/11 Path Edge Cases Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_windows_max_path_length_support(tmp_path):
    """Verify that file operations succeed on paths exceeding MAX_PATH (260 characters)."""
    # Build a directory structure where path length exceeds 280 characters
    chunk = "subdir_long_windows_path_component_"
    deep_dir = tmp_path / f"{chunk}1" / f"{chunk}2" / f"{chunk}3" / f"{chunk}4"
    deep_dir.mkdir(parents=True, exist_ok=True)
    
    long_pdf = deep_dir / "sozlesme_belgesi_uzun_dosya_adi_test.pdf"
    assert len(str(long_pdf)) > 260
    
    # Create PDF in long path
    _create_versioned_pdf(long_pdf, "1.5", "MAX_PATH Test Document Content")
    assert long_pdf.exists()
    
    # Test reading via PyMuPDF and pypdf
    doc = fitz.open(str(long_pdf))
    assert doc.page_count == 1
    doc.close()
    
    r = pypdf.PdfReader(str(long_pdf))
    assert len(r.pages) == 1
    
    # Compress to another long path
    comp_long = deep_dir / "sozlesme_compressed_uzun_dosya_adi.pdf"
    compress_pdf(str(long_pdf), str(comp_long), "screen")
    assert comp_long.exists()
    
    # Watermark to long path
    wm_long = deep_dir / "sozlesme_watermarked_uzun_dosya_adi.pdf"
    add_watermark_to_pdf(str(comp_long), str(wm_long), "MAX_PATH")
    assert wm_long.exists()
    
    # Split
    split_long = deep_dir / "sozlesme_split_uzun_dosya_adi.pdf"
    split_pdf(str(wm_long), str(split_long), 1, 1)
    assert split_long.exists()


def test_windows_spaces_in_paths(tmp_path):
    """Verify operations on paths containing multiple spaces and special brackets."""
    spaced_dir = tmp_path / "My Folder With Many Spaces" / "Sub Level Folder (v2.0) [Final]"
    spaced_dir.mkdir(parents=True, exist_ok=True)
    
    spaced_pdf = spaced_dir / "My Document With Spaces (Final Version) [2026].pdf"
    _create_versioned_pdf(spaced_pdf, "1.4", "Spaces in Path Test")
    
    # Compress
    out_comp = spaced_dir / "Compressed File With Spaces.pdf"
    compress_pdf(str(spaced_pdf), str(out_comp), "screen")
    assert out_comp.exists()
    
    # Watermark
    out_wm = spaced_dir / "Watermarked File With Spaces.pdf"
    add_watermark_to_pdf(str(out_comp), str(out_wm), "STAMP SPACES")
    assert out_wm.exists()
    
    # Split
    out_split = spaced_dir / "Split File With Spaces.pdf"
    split_pdf(str(out_wm), str(out_split), 1, 1)
    assert out_split.exists()


@pytest.mark.parametrize(
    "folder_name, file_name",
    [
        ("türkçe_dizin_çşığöü", "fatura_şirketi_özel_çalışma.pdf"),
        ("русский_каталог", "документ_отчетность_финансы.pdf"),
        ("دليل_المستندات", "تقرير_سنوي_معتمد.pdf"),
        ("中文测试目录", "财务审计报告_最终版.pdf"),
    ],
)
def test_windows_non_ascii_unicode_paths(tmp_path, folder_name, file_name):
    """Verify full PDF pipeline across diverse non-ASCII Unicode paths (Turkish, Cyrillic, Arabic, Chinese)."""
    unicode_dir = tmp_path / folder_name
    unicode_dir.mkdir(parents=True, exist_ok=True)
    
    target_pdf = unicode_dir / file_name
    _create_versioned_pdf(target_pdf, "1.5", "Unicode Path Compatibility Test")
    assert target_pdf.exists()
    
    # 1. Compress
    out_comp = unicode_dir / f"compressed_{file_name}"
    compress_pdf(str(target_pdf), str(out_comp), "screen")
    assert out_comp.exists()
    
    # 2. Split
    out_split = unicode_dir / f"split_{file_name}"
    split_pdf(str(out_comp), str(out_split), 1, 1)
    assert out_split.exists()
    
    # 3. Watermark
    out_wm = unicode_dir / f"watermarked_{file_name}"
    add_watermark_to_pdf(str(out_split), str(out_wm), "UNICODE")
    assert out_wm.exists()
    
    # 4. Smart rename suggestion
    suggested = suggest_filename(str(out_wm))
    assert isinstance(suggested, str)
    assert suggested.endswith(".pdf")


def test_windows_readonly_destination_directory(tmp_path):
    """Verify that writing to a read-only directory raises PermissionError without corrupting files."""
    src_pdf = tmp_path / "source_document.pdf"
    _create_versioned_pdf(src_pdf, "1.4", "Source Content")
    
    ro_dir = tmp_path / "readonly_destination"
    ro_dir.mkdir(parents=True, exist_ok=True)
    
    # Simulate directory write denial via patch on tempfile.mkstemp or os.replace
    with patch("tempfile.mkstemp", side_effect=PermissionError(errno.EACCES, "Access is denied")):
        out_pdf = ro_dir / "target.pdf"
        
        # Compress should raise PermissionError
        with pytest.raises(PermissionError):
            compress_pdf(str(src_pdf), str(out_pdf), "screen")
            
        # Split should raise PermissionError
        with pytest.raises(PermissionError):
            split_pdf(str(src_pdf), str(out_pdf), 1, 1)
            
        # Watermark should raise PermissionError
        with pytest.raises(PermissionError):
            add_watermark_to_pdf(str(src_pdf), str(out_pdf), "WM")

    # Confirm no orphan temporary files were left behind
    assert leftovers(str(ro_dir)) == []


def test_windows_locked_file_handles(tmp_path):
    """Verify handling when destination file is locked by an external Windows process handle."""
    import msvcrt

    src_pdf = tmp_path / "valid_input.pdf"
    _create_versioned_pdf(src_pdf, "1.4", "Input Content")
    
    locked_pdf = tmp_path / "locked_target.pdf"
    _create_versioned_pdf(locked_pdf, "1.4", "Initial Target Content")
    
    initial_bytes = locked_pdf.read_bytes()
    
    # Lock the destination file using Windows Win32 file locking
    with open(locked_pdf, "r+b") as lock_handle:
        msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, os.path.getsize(str(locked_pdf)))
        try:
            # Attempting to overwrite locked file must raise PermissionError / OSError
            with pytest.raises((PermissionError, OSError)):
                compress_pdf(str(src_pdf), str(locked_pdf), "screen")
                
            with pytest.raises((PermissionError, OSError)):
                split_pdf(str(src_pdf), str(locked_pdf), 1, 1)
                
            with pytest.raises((PermissionError, OSError)):
                add_watermark_to_pdf(str(src_pdf), str(locked_pdf), "LOCKED")
        finally:
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, os.path.getsize(str(locked_pdf)))
            
    # Destination must remain untouched and uncorrupted
    assert locked_pdf.read_bytes() == initial_bytes
    # No temporary files left behind
    assert leftovers(str(tmp_path)) == []


def test_closed_file_handles_allow_immediate_post_processing(tmp_path):
    """Verify that PDFAura tools cleanly close file handles so files can be modified immediately."""
    src_pdf = tmp_path / "step_input.pdf"
    _create_versioned_pdf(src_pdf, "1.4", "Immediate Processing Test")
    
    out_pdf = tmp_path / "step_output.pdf"
    compress_pdf(str(src_pdf), str(out_pdf), "screen")
    
    # On Windows, if any handle remained open, os.replace or os.remove would fail with WinError 32
    renamed_pdf = tmp_path / "immediately_renamed.pdf"
    os.replace(out_pdf, renamed_pdf)
    assert renamed_pdf.exists()
    assert not out_pdf.exists()
    
    # Delete immediately
    os.remove(renamed_pdf)
    assert not renamed_pdf.exists()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Cross-Feature Compatibility Pipeline
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "fixture_type",
    [
        "linearized",
        "acroform",
        "annotated",
        "mixed",
        "font",
        "vector",
        "max_path",
        "unicode_turkish",
        "unicode_arabic",
        "spaces",
    ],
)
def test_cross_feature_compatibility_pipeline(tmp_path, fixture_type):
    """Execute compress -> split -> watermark -> redact -> smart_rename sequentially on edge case PDFs."""
    work_dir = tmp_path
    if fixture_type == "max_path":
        chunk = "component_long_path_"
        work_dir = tmp_path / f"{chunk}1" / f"{chunk}2" / f"{chunk}3" / f"{chunk}4"
        work_dir.mkdir(parents=True, exist_ok=True)
    elif fixture_type == "unicode_turkish":
        work_dir = tmp_path / "türkçe_klasör_çşığöü"
        work_dir.mkdir(parents=True, exist_ok=True)
    elif fixture_type == "unicode_arabic":
        work_dir = tmp_path / "مجلد_المستندات"
        work_dir.mkdir(parents=True, exist_ok=True)
    elif fixture_type == "spaces":
        work_dir = tmp_path / "Folder With Spaces And (Tags) [2026]"
        work_dir.mkdir(parents=True, exist_ok=True)

    input_pdf = work_dir / f"input_{fixture_type}.pdf"
    
    # Create the specific edge case document
    if fixture_type in ("linearized", "max_path", "unicode_turkish", "unicode_arabic", "spaces"):
        _create_linearized_pdf(input_pdf, "FATURA BELGESI\nTarih: 15.06.2026\nTC: 10000000146\nFirma: ABC A.S.")
    elif fixture_type == "acroform":
        _create_acroform_pdf(input_pdf, "fatura_no", "FATURA BELGESI\nTarih: 15.06.2026\nTC: 10000000146")
    elif fixture_type == "annotated":
        _create_annotated_pdf(input_pdf)
    elif fixture_type == "mixed":
        _create_mixed_orientations_pdf(input_pdf)
    elif fixture_type == "font":
        _create_embedded_font_pdf(input_pdf, "FATURA BELGESI 15.06.2026 TC: 10000000146 ABC Ltd")
    elif fixture_type == "vector":
        _create_vector_paths_pdf(input_pdf)

    # 1. Step: Compress
    step1_compressed = work_dir / f"step1_{fixture_type}_comp.pdf"
    compress_pdf(str(input_pdf), str(step1_compressed), "screen")
    assert step1_compressed.exists()
    assert step1_compressed.stat().st_size > 0
    
    # 2. Step: Split
    step2_split = work_dir / f"step2_{fixture_type}_split.pdf"
    split_pdf(str(step1_compressed), str(step2_split), 1, 1)
    assert step2_split.exists()
    assert step2_split.stat().st_size > 0
    
    # 3. Step: Watermark
    step3_watermarked = work_dir / f"step3_{fixture_type}_wm.pdf"
    add_watermark_to_pdf(str(step2_split), str(step3_watermarked), "PIPELINE TEST")
    assert step3_watermarked.exists()
    assert step3_watermarked.stat().st_size > 0
    
    # 4. Step: Redact (find and redact any sensitive items or dummy area)
    step4_redacted = work_dir / f"step4_{fixture_type}_redacted.pdf"
    sensitive_matches = find_sensitive(str(step3_watermarked))
    if not sensitive_matches:
        # If document had no text or no detected items, specify a target rectangle on page 1
        sensitive_matches = [{"page": 1, "rect": [50, 50, 150, 80]}]
    apply_redactions(str(step3_watermarked), sensitive_matches, str(step4_redacted))
    assert step4_redacted.exists()
    assert step4_redacted.stat().st_size > 0
    
    # 5. Step: Smart Rename
    rename_plan = plan_batch_rename([str(step4_redacted)])
    assert len(rename_plan) == 1
    rename_results = apply_batch_rename(rename_plan)
    assert len(rename_results) == 1
    final_path = Path(rename_results[0]["applied_path"])
    assert final_path.exists()
    assert final_path.stat().st_size > 0
    
    # Final verification: result must be a readable PDF
    final_doc = fitz.open(str(final_path))
    assert final_doc.page_count == 1
    final_doc.close()
    
    # Verify no dangling temp files
    assert leftovers(str(work_dir)) == []
