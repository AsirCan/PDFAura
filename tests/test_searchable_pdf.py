"""Searchable PDF output: OCR text layer only where a page has no text."""

import pytest

from src.core import ocr
from src.core.task_manager import CancelledError


def _source_pdf(path, text_pages=(), pages=2):
    """A PDF whose *text_pages* have real text and the rest look scanned."""
    import fitz

    doc = fitz.open()
    try:
        for index in range(pages):
            page = doc.new_page(width=400 + index * 10, height=500 + index * 10)
            if index in text_pages:
                page.insert_text((40, 80), f"Original page {index + 1}", fontsize=16)
        doc.save(str(path))
    finally:
        doc.close()
    return str(path)


def _ocr_stub(page, language, dpi):
    """Stand-in for OCR: a one-page PDF with a known sentence."""
    import fitz

    doc = fitz.open()
    try:
        out_page = doc.new_page(width=page.rect.width, height=page.rect.height)
        out_page.insert_text((40, 80), "TARANMIS METIN", fontsize=16)
        return doc.tobytes()
    finally:
        doc.close()


def test_pages_with_text_are_not_ocrd(tmp_path, monkeypatch):
    source = _source_pdf(tmp_path / "mixed.pdf", text_pages=(0, 2), pages=3)
    output = tmp_path / "searchable.pdf"

    monkeypatch.setattr(ocr, "check_tesseract_availability", lambda: True)
    monkeypatch.setattr(ocr, "resolve_ocr_language", lambda requested=None: "eng")
    seen = []

    def fake_ocr(page, language, dpi):
        seen.append(page.number)
        return _ocr_stub(page, language, dpi)

    monkeypatch.setattr(ocr, "_ocr_page_pdf", fake_ocr)

    count = ocr.make_searchable_pdf(source, str(output))

    assert count == 1
    assert seen == [1], "only the page without text should be OCRed"

    import fitz
    result = fitz.open(str(output))
    try:
        assert result.page_count == 3
        assert "Original page 1" in result[0].get_text()
        assert "TARANMIS METIN" in result[1].get_text()
        assert "Original page 3" in result[2].get_text()
        assert [round(page.rect.width) for page in result] == [400, 410, 420]
    finally:
        result.close()


def test_a_text_only_pdf_is_copied_without_ocr(tmp_path, monkeypatch):
    source = _source_pdf(tmp_path / "text.pdf", text_pages=(0, 1), pages=2)
    output = tmp_path / "searchable.pdf"

    monkeypatch.setattr(ocr, "check_tesseract_availability", lambda: True)
    monkeypatch.setattr(ocr, "resolve_ocr_language", lambda requested=None: "eng")

    def fail(*args, **kwargs):
        raise AssertionError("OCR must not run on pages that already have text")

    monkeypatch.setattr(ocr, "_ocr_page_pdf", fail)

    assert ocr.make_searchable_pdf(source, str(output)) == 0

    import fitz
    result = fitz.open(str(output))
    try:
        assert "Original page 1" in result[0].get_text()
        assert "Original page 2" in result[1].get_text()
    finally:
        result.close()


def test_missing_tesseract_gives_a_readable_error(tmp_path, monkeypatch):
    source = _source_pdf(tmp_path / "in.pdf", pages=1)
    output = tmp_path / "out.pdf"
    monkeypatch.setattr(ocr, "check_tesseract_availability", lambda: False)

    with pytest.raises(EnvironmentError) as excinfo:
        ocr.make_searchable_pdf(source, str(output))

    assert "Tesseract" in str(excinfo.value)
    assert not output.exists()


def test_cancel_writes_nothing(tmp_path, monkeypatch):
    source = _source_pdf(tmp_path / "in.pdf", text_pages=(0,), pages=2)
    output = tmp_path / "out.pdf"

    monkeypatch.setattr(ocr, "check_tesseract_availability", lambda: True)
    monkeypatch.setattr(ocr, "resolve_ocr_language", lambda requested=None: "eng")
    monkeypatch.setattr(ocr, "_ocr_page_pdf", _ocr_stub)

    with pytest.raises(CancelledError):
        ocr.make_searchable_pdf(source, str(output), cancel=lambda: True)

    assert not output.exists()


def test_reports_progress_for_every_page(tmp_path, monkeypatch):
    source = _source_pdf(tmp_path / "in.pdf", pages=3)
    output = tmp_path / "out.pdf"

    monkeypatch.setattr(ocr, "check_tesseract_availability", lambda: True)
    monkeypatch.setattr(ocr, "resolve_ocr_language", lambda requested=None: "eng")
    monkeypatch.setattr(ocr, "_ocr_page_pdf", _ocr_stub)

    seen = []
    ocr.make_searchable_pdf(
        source, str(output), dpi=200,
        progress=lambda current, total, message="": seen.append((current, total, message)))

    assert [item[0] for item in seen] == [0, 1, 2, 3]
    assert all(item[1] == 3 for item in seen)
    assert seen[-1][2] == ocr._("str_done")


def test_can_write_over_the_input_file(tmp_path, monkeypatch):
    source = _source_pdf(tmp_path / "same.pdf", text_pages=(0,), pages=1)

    monkeypatch.setattr(ocr, "check_tesseract_availability", lambda: True)
    monkeypatch.setattr(ocr, "resolve_ocr_language", lambda requested=None: "eng")

    assert ocr.make_searchable_pdf(source, source) == 0

    import fitz
    result = fitz.open(source)
    try:
        assert "Original page 1" in result[0].get_text()
    finally:
        result.close()


def test_requested_dpi_reaches_the_ocr_step(tmp_path, monkeypatch):
    source = _source_pdf(tmp_path / "in.pdf", pages=1)
    received = []

    monkeypatch.setattr(ocr, "check_tesseract_availability", lambda: True)
    monkeypatch.setattr(ocr, "resolve_ocr_language", lambda requested=None: "eng")

    def fake_ocr(page, language, dpi):
        received.append(dpi)
        return _ocr_stub(page, language, dpi)

    monkeypatch.setattr(ocr, "_ocr_page_pdf", fake_ocr)

    ocr.make_searchable_pdf(source, str(tmp_path / "out.pdf"), dpi=150)

    assert received == [150]


@pytest.mark.skipif(not ocr.check_tesseract_availability(),
                    reason="Tesseract is not installed")
def test_real_ocr_makes_a_scanned_page_searchable(tmp_path):
    import fitz

    # Render text, then put only the image in a new PDF: no text layer.
    rendered = fitz.open()
    try:
        page = rendered.new_page(width=500, height=200)
        page.insert_text((40, 100), "Hello searchable world", fontsize=36)
        pix = page.get_pixmap(dpi=150)
    finally:
        rendered.close()

    scanned = fitz.open()
    try:
        page = scanned.new_page(width=500, height=200)
        page.insert_image(page.rect, stream=pix.tobytes("png"))
        scanned.save(str(tmp_path / "scanned.pdf"))
    finally:
        scanned.close()

    output = tmp_path / "searchable.pdf"
    count = ocr.make_searchable_pdf(
        str(tmp_path / "scanned.pdf"), str(output), lang="eng", dpi=300)

    assert count == 1
    result = fitz.open(str(output))
    try:
        assert "hello" in result[0].get_text().lower()
    finally:
        result.close()
