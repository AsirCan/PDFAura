"""Issue #27: a write cut short must not cost the input or an older output.

The pypdf tools opened their destination with open(path, "wb"), which empties
it before the first byte is written. With the disk full 100 bytes in, saving
over the input turned a good PDF into 100 bytes of nothing.
"""
import errno

import pytest
from PIL import Image

from conftest import leftovers, make_encrypted_pdf, make_pdf, page_widths
from src.core import convert, ocr
from src.core.edit import delete_pages_from_pdf, reorder_pages_in_pdf, rotate_pages_in_pdf
from src.core.merge import merge_pdfs
from src.core.metainfo import update_metadata
from src.core.security import add_watermark_to_pdf, decrypt_pdf, encrypt_pdf
from src.core.signature import stamp_visual_signature
from src.core.split import split_pdf


def _signature(src, out):
    image = src.parent / "imza.png"
    Image.new("RGB", (40, 20), "navy").save(image)
    stamp_visual_signature(str(src), str(out), str(image))


# PDF in, PDF out: name -> run(src, out). "decrypt" gets a locked input.
PDF_WRITERS = {
    "delete": lambda src, out: delete_pages_from_pdf(str(src), str(out), [1]),
    "rotate": lambda src, out: rotate_pages_in_pdf(str(src), str(out), [1], 90),
    "reorder": lambda src, out: reorder_pages_in_pdf(str(src), str(out), [3, 1, 2]),
    "merge": lambda src, out: merge_pdfs([str(src), str(src)], str(out)),
    "split": lambda src, out: split_pdf(str(src), str(out), 1, 2),
    "encrypt": lambda src, out: encrypt_pdf(str(src), str(out), "Gizli123"),
    "decrypt": lambda src, out: decrypt_pdf(str(src), str(out), "parola"),
    "watermark": lambda src, out: add_watermark_to_pdf(str(src), str(out), "GIZLI"),
    "metadata": lambda src, out: update_metadata(str(src), str(out), title="Yeni"),
    "metadata-clean": lambda src, out: update_metadata(str(src), str(out), clean=True),
    "signature": _signature,
}


def _input(tmp_path, name):
    path = tmp_path / "girdi.pdf"
    if name == "decrypt":
        make_encrypted_pdf(path, "parola")
    else:
        make_pdf(path)
    return path


@pytest.mark.parametrize("name", PDF_WRITERS)
def test_saving_over_the_input_keeps_it_when_the_disk_fills(tmp_path, disk_full, name):
    src = _input(tmp_path, name)
    before = src.read_bytes()

    with pytest.raises(OSError) as excinfo:
        PDF_WRITERS[name](src, src)

    assert excinfo.value.errno == errno.ENOSPC
    assert src.read_bytes() == before
    assert leftovers(tmp_path) == []


@pytest.mark.parametrize("name", PDF_WRITERS)
def test_an_older_output_survives_a_failed_write(tmp_path, disk_full, name):
    src = _input(tmp_path, name)
    old = tmp_path / "eski.pdf"
    make_pdf(old, pages=5)
    before = old.read_bytes()

    with pytest.raises(OSError):
        PDF_WRITERS[name](src, old)

    assert old.read_bytes() == before
    assert page_widths(old) == [595, 596, 597, 598, 599]
    assert leftovers(tmp_path) == []


@pytest.mark.parametrize("name", ["rotate", "encrypt", "metadata"])
def test_saving_over_the_input_still_works(tmp_path, name):
    src = tmp_path / "girdi.pdf"
    make_pdf(src)

    PDF_WRITERS[name](src, src)

    password = "Gizli123" if name == "encrypt" else None
    assert page_widths(src, password) == [595, 596, 597]
    assert leftovers(tmp_path) == []


# ── Text and Word outputs ─────────────────────────────────────────────────

def _old_file(path, text="eski icerik, kaybolmamali\n" * 20):
    path.write_text(text, encoding="utf-8")
    return path.read_bytes()


def test_pdf_to_text_keeps_an_older_text_file(tmp_path, disk_full, monkeypatch):
    from pypdf import PageObject
    monkeypatch.setattr(PageObject, "extract_text", lambda self, *args, **kwargs: "metin " * 100)
    src = make_pdf(tmp_path / "girdi.pdf")
    disk_full.open_in(convert)
    out = tmp_path / "girdi.txt"
    before = _old_file(out)

    with pytest.raises(OSError):
        convert.pdf_to_txt(src, str(out))

    assert out.read_bytes() == before
    assert leftovers(tmp_path) == []


def test_ocr_keeps_an_older_text_file(tmp_path, disk_full, monkeypatch):
    src = make_pdf(tmp_path / "girdi.pdf", pages=2, size=(100, 100))
    monkeypatch.setattr(ocr, "check_tesseract_availability", lambda: True)
    monkeypatch.setattr(ocr, "resolve_ocr_language", lambda requested=None: "eng")
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", lambda img, lang=None: "okunan metin " * 50)
    disk_full.open_in(ocr)
    out = tmp_path / "girdi_ocr.txt"
    before = _old_file(out)

    with pytest.raises(OSError):
        ocr.perform_ocr_to_text(src, str(out))

    assert out.read_bytes() == before
    assert leftovers(tmp_path) == []


class _HalfConverter:
    """pdf2docx's Converter, failing halfway through writing the .docx."""
    instances = []

    def __init__(self, pdf):
        self.closed = False
        _HalfConverter.instances.append(self)

    def convert(self, docx, start=0, end=None):
        with open(docx, "wb") as handle:
            handle.write(b"PK\x03\x04 yarim")
        raise OSError(errno.ENOSPC, "No space left on device")

    def close(self):
        self.closed = True


def test_pdf_to_word_keeps_an_older_docx_and_releases_the_pdf(tmp_path, monkeypatch):
    import pdf2docx
    monkeypatch.setattr(pdf2docx, "Converter", _HalfConverter)
    _HalfConverter.instances.clear()
    src = make_pdf(tmp_path / "rapor.pdf")
    out = tmp_path / "rapor.docx"
    before = _old_file(out)

    with pytest.raises(OSError):
        convert.pdf_to_word(src, str(out))

    assert out.read_bytes() == before
    assert leftovers(tmp_path) == []
    # Left open, the PDF stayed locked on Windows.
    assert _HalfConverter.instances[0].closed


def test_office_conversion_keeps_an_older_pdf(tmp_path):
    def half_export(input_abs, output_abs):
        with open(output_abs, "wb") as handle:
            handle.write(b"%PDF-1.7 yarim")
        raise RuntimeError("Word stopped")

    src = tmp_path / "rapor.docx"
    src.write_bytes(b"docx")
    out = tmp_path / "rapor.pdf"
    make_pdf(out)
    before = out.read_bytes()

    with pytest.raises(RuntimeError):
        convert._office_to_pdf(half_export, "Word", str(src), str(out), None)

    assert out.read_bytes() == before
    assert leftovers(tmp_path) == []
