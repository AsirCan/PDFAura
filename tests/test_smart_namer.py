"""Tests for src/core/smart_namer.py (Akıllı Dosya Adlandırma ve Klasörleme)."""
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import fitz

from src.core.smart_namer import (
    DOCUMENT_TYPES,
    apply_batch_rename,
    extract_first_page_text,
    extract_metadata_fields,
    plan_batch_rename,
    sanitize_filename,
    suggest_filename,
)


def _create_pdf_with_text(path: Path, text: str) -> str:
    """Helper to create a PDF containing real extractable text."""
    doc = fitz.open()
    try:
        page = doc.new_page(width=595, height=842)
        font_path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf")
        if os.path.isfile(font_path):
            page.insert_font(fontname="f0", fontfile=font_path, set_simple=False)
            page.insert_textbox(fitz.Rect(50, 50, 545, 800), text, fontname="f0", fontsize=12)
        else:
            page.insert_textbox(fitz.Rect(50, 50, 545, 800), text, fontsize=12)
        doc.save(str(path))
    finally:
        doc.close()
    return str(path)


# ── 1. Document Type & Metadata Extraction Tests ─────────────────────────


def test_extract_metadata_fatura(tmp_path):
    pdf = tmp_path / "fatura_test.pdf"
    content = (
        "BEDAŞ ELEKTRİK DAĞITIM A.Ş.\n"
        "ELEKTRİK FATURASI\n"
        "Fatura Tarihi: 15.05.2026\n"
        "Fatura No: GIB2026000012345\n"
        "Ödenecek Tutar: 450,50 TL\n"
        "KDV: 81,09 TL\n"
    )
    _create_pdf_with_text(pdf, content)

    meta = extract_metadata_fields(pdf)
    assert meta["document_type"] == "fatura"
    assert meta["type"] == "fatura"
    assert meta["date"] == "2026-05-15"
    assert "Elektrik" in meta["subject"] or "BEDAS" in meta["subject"].upper()


def test_extract_metadata_dekont(tmp_path):
    pdf = tmp_path / "dekont_test.pdf"
    content = (
        "TÜRKİYE GARANTİ BANKASI\n"
        "EFT / HAVALE İŞLEM DEKONTU\n"
        "İşlem Tarihi: 2026-07-20\n"
        "Açıklama: Ev Kirası\n"
        "Gönderen IBAN: TR120006200000001234567890\n"
        "Alıcı: Fatma Demir\n"
    )
    _create_pdf_with_text(pdf, content)

    meta = extract_metadata_fields(pdf)
    assert meta["document_type"] == "dekont"
    assert meta["date"] == "2026-07-20"
    assert meta["subject"] != ""


def test_extract_metadata_sozlesme(tmp_path):
    pdf = tmp_path / "sozlesme_test.pdf"
    content = (
        "KİRA SÖZLEŞMESİ\n"
        "Taraflar: Mehmet Yılmaz ile Ahmet Kaya\n"
        "Kiracı: Ahmet Kaya\n"
        "Sözleşme Tarihi: 01.06.2026\n"
        "Madde 1: İşbu kira sözleşmesi akdedilmiştir.\n"
    )
    _create_pdf_with_text(pdf, content)

    meta = extract_metadata_fields(pdf)
    assert meta["document_type"] == "sozlesme"
    assert meta["date"] == "2026-06-01"
    assert meta["subject"] != ""


def test_extract_metadata_rapor(tmp_path):
    pdf = tmp_path / "rapor_test.pdf"
    content = (
        "ACME HOLDİNG A.Ş.\n"
        "2026 YILI FİNANSAL RAPORU\n"
        "Yıllık Faaliyet ve Denetim Raporu\n"
        "Rapor Tarihi: 30.04.2026\n"
        "Konu: Finansal Değerlendirme\n"
    )
    _create_pdf_with_text(pdf, content)

    meta = extract_metadata_fields(pdf)
    assert meta["document_type"] == "rapor"
    assert meta["date"] == "2026-04-30"
    assert "Finansal" in meta["subject"]


def test_extract_metadata_odev(tmp_path):
    pdf = tmp_path / "odev_test.pdf"
    content = (
        "FEN BİLİMLERİ ENSTİTÜSÜ\n"
        "Matematik Dersi 1. Ödevi\n"
        "Öğrenci: Can Yılmaz\n"
        "Öğrenci No: 202601001\n"
        "Tarih: 16 Mayıs 2026\n"
    )
    _create_pdf_with_text(pdf, content)

    meta = extract_metadata_fields(pdf)
    assert meta["document_type"] == "odev"
    assert meta["date"] == "2026-05-16"
    assert "Matematik" in meta["subject"]


def test_extract_metadata_english_document(tmp_path):
    pdf = tmp_path / "tax_invoice.pdf"
    content = (
        "GLOBAL CORP LLC\n"
        "TAX INVOICE\n"
        "Invoice Date: 2026-09-15\n"
        "Bill To: John Doe\n"
        "Total Due: $250.00\n"
    )
    _create_pdf_with_text(pdf, content)

    meta = extract_metadata_fields(pdf)
    assert meta["document_type"] == "fatura"
    assert meta["date"] == "2026-09-15"


def test_extract_metadata_diger_unclassified(tmp_path):
    pdf = tmp_path / "diger_test.pdf"
    content = "Haftalık yemek menüsü ve mutfak temizlik kuralları."
    _create_pdf_with_text(pdf, content)

    meta = extract_metadata_fields(pdf)
    assert meta["document_type"] == "diger"
    assert meta["type"] == "diger"


def test_extract_metadata_empty_pdf(tmp_path):
    pdf = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(str(pdf))
    doc.close()

    meta = extract_metadata_fields(pdf)
    assert meta["document_type"] == "diger"
    assert meta["date"] == ""
    assert meta["subject"] == ""


# ── 2. Date Parsing Heuristic Tests ──────────────────────────────────────


def test_extract_date_formats(tmp_path):
    # DD.MM.YYYY
    pdf1 = tmp_path / "d1.pdf"
    _create_pdf_with_text(pdf1, "Fatura Tarihi: 28.02.2026 Fatura No: 123")
    assert extract_metadata_fields(pdf1)["date"] == "2026-02-28"

    # YYYY-MM-DD
    pdf2 = tmp_path / "d2.pdf"
    _create_pdf_with_text(pdf2, "Tarih: 2026-11-05 Dekont")
    assert extract_metadata_fields(pdf2)["date"] == "2026-11-05"

    # Turkish textual: 12 Nisan 2026
    pdf3 = tmp_path / "d3.pdf"
    _create_pdf_with_text(pdf3, "Teslim Tarihi: 12 Nisan 2026 Proje Ödevi")
    assert extract_metadata_fields(pdf3)["date"] == "2026-04-12"

    # Month-Year only: Mart 2026 -> defaults to 1st of month
    pdf4 = tmp_path / "d4.pdf"
    _create_pdf_with_text(pdf4, "Faaliyet Raporu Mart 2026")
    assert extract_metadata_fields(pdf4)["date"] == "2026-03-01"


def test_dateutil_fallback_on_unusual_date(tmp_path):
    pdf = tmp_path / "dateutil_test.pdf"
    # Date in an unusual format supported by dateutil (e.g. October 24th, 2025)
    _create_pdf_with_text(pdf, "Contract Date: October 24th, 2025\nAgreement")
    meta = extract_metadata_fields(pdf)
    assert meta["date"] == "2025-10-24"


# ── 3. Suggest Filename Tests ────────────────────────────────────────────


def test_suggest_filename_default_template(tmp_path):
    pdf = tmp_path / "sample.pdf"
    _create_pdf_with_text(
        pdf,
        "Matematik Dersi Ödevi\nTarih: 16.05.2026\nÖğrenci: Ali Demir"
    )

    suggested = suggest_filename(pdf)
    assert suggested.endswith(".pdf")
    assert "odev" in suggested.lower()
    assert "2026-05-16" in suggested
    assert "matematik" in suggested.lower()


def test_suggest_filename_custom_templates(tmp_path):
    pdf = tmp_path / "sample2.pdf"
    _create_pdf_with_text(
        pdf,
        "ELEKTRİK FATURASI\nFatura Tarihi: 10.04.2026\nKonu: Elektrik"
    )

    # Custom template: {konu}_{belge_turu}_{tarih}
    name1 = suggest_filename(pdf, template="{konu}_{belge_turu}_{tarih}")
    assert name1 == "Elektrik_fatura_2026-04-10.pdf"

    # Uppercase template tokens: {BELGE_TURU}_{KONU}
    name2 = suggest_filename(pdf, template="{BELGE_TURU}_{KONU}")
    assert name2 == "FATURA_ELEKTRIK.pdf" or name2 == "FATURA_Elektrik.pdf"

    # Original name token
    name3 = suggest_filename(pdf, template="{orijinal_ad}_{belge_turu}")
    assert name3 == "sample2_fatura.pdf"


def test_suggest_filename_cleans_empty_tokens(tmp_path):
    # PDF with no date and no subject
    pdf = tmp_path / "empty_meta.pdf"
    _create_pdf_with_text(pdf, "ELEKTRİK FATURASI")

    name = suggest_filename(pdf, template="{belge_turu}_{tarih}_{konu}")
    # Should not produce double underscores or trailing underscores
    assert "__" not in name
    assert not name.startswith("_")
    assert name.endswith(".pdf")


def test_sanitize_filename_handles_illegal_characters():
    dirty = 'fatura: <Elektrik>*|?"2026/05'
    clean = sanitize_filename(dirty)
    for bad in '<>:"/\\|?*':
        assert bad not in clean
    assert clean.endswith(".pdf")


def test_sanitize_filename_reserved_windows_name():
    assert sanitize_filename("CON.pdf") != "CON.pdf"
    assert sanitize_filename("NUL") != "NUL.pdf"


# ── 4. Batch Rename Planning & Collision Resolution ──────────────────────


def test_plan_batch_rename_single_and_list(tmp_path):
    pdf1 = tmp_path / "f1.pdf"
    pdf2 = tmp_path / "f2.pdf"
    _create_pdf_with_text(pdf1, "ELEKTRİK FATURASI\nTarih: 2026-05-01")
    _create_pdf_with_text(pdf2, "KİRA SÖZLEŞMESİ\nTarih: 2026-05-02")

    plan = plan_batch_rename([pdf1, pdf2])
    assert len(plan) == 2

    # Check required keys
    for item in plan:
        assert "old_path" in item
        assert "new_path" in item
        assert "type" in item
        assert "date" in item
        assert "subject" in item
        assert "collision_resolved" in item

    assert plan[0]["type"] == "fatura"
    assert plan[1]["type"] == "sozlesme"


def test_plan_batch_rename_folder_input(tmp_path):
    folder = tmp_path / "input_docs"
    folder.mkdir()
    _create_pdf_with_text(folder / "doc1.pdf", "Elektrik Faturası\nTarih: 2026-01-01")
    _create_pdf_with_text(folder / "doc2.pdf", "Banka Dekontu\nTarih: 2026-01-02")
    # Non-pdf file should be ignored
    (folder / "notes.txt").write_text("not a pdf", encoding="utf-8")

    plan = plan_batch_rename(folder)
    assert len(plan) == 2
    types = {item["type"] for item in plan}
    assert "fatura" in types
    assert "dekont" in types


def test_plan_batch_rename_collision_in_batch(tmp_path):
    # Two identical PDFs in batch that produce identical names
    pdf1 = tmp_path / "source1.pdf"
    pdf2 = tmp_path / "source2.pdf"
    content = "ELEKTRİK FATURASI\nTarih: 2026-05-16\nKonu: Elektrik"
    _create_pdf_with_text(pdf1, content)
    _create_pdf_with_text(pdf2, content)

    plan = plan_batch_rename([pdf1, pdf2])
    assert len(plan) == 2

    assert plan[0]["collision_resolved"] is False
    assert plan[1]["collision_resolved"] is True
    assert "(2)" in plan[1]["new_path"]
    assert plan[0]["new_path"] != plan[1]["new_path"]


def test_plan_batch_rename_collision_with_existing_disk_file(tmp_path):
    # File already exists on disk at target location
    existing_target = tmp_path / "fatura_2026-05-16_Elektrik.pdf"
    _create_pdf_with_text(existing_target, "Already here")

    pdf1 = tmp_path / "source_new.pdf"
    _create_pdf_with_text(pdf1, "ELEKTRİK FATURASI\nTarih: 2026-05-16\nKonu: Elektrik")

    plan = plan_batch_rename([pdf1])
    assert len(plan) == 1
    # Collision with existing disk file should be resolved
    assert plan[0]["collision_resolved"] is True
    assert "(2)" in plan[0]["new_path"]


def test_plan_batch_rename_organize_folders(tmp_path):
    pdf = tmp_path / "doc.pdf"
    _create_pdf_with_text(pdf, "ELEKTRİK FATURASI\nTarih: 2026-05-16")

    plan = plan_batch_rename([pdf], organize_folders=True)
    assert len(plan) == 1
    # Target path should contain the 'fatura' subfolder
    assert os.path.basename(os.path.dirname(plan[0]["new_path"])) == "fatura"


# ── 5. Apply Batch Rename Tests ──────────────────────────────────────────


def test_apply_batch_rename_in_place(tmp_path):
    pdf = tmp_path / "temp_input.pdf"
    _create_pdf_with_text(pdf, "ELEKTRİK FATURASI\nTarih: 2026-05-16\nKonu: Elektrik")

    plan = plan_batch_rename([pdf])
    assert os.path.exists(pdf)

    results = apply_batch_rename(plan)
    assert len(results) == 1
    assert results[0]["success"] is True

    # Old path should be gone, new path should exist
    assert not os.path.exists(pdf)
    assert os.path.exists(results[0]["new_path"])


def test_apply_batch_rename_with_folder_organization(tmp_path):
    pdf1 = tmp_path / "doc_fat.pdf"
    pdf2 = tmp_path / "doc_odev.pdf"
    _create_pdf_with_text(pdf1, "ELEKTRİK FATURASI\nTarih: 2026-05-16")
    _create_pdf_with_text(pdf2, "Matematik Dersi Ödevi\nTarih: 2026-05-17")

    out_folder = tmp_path / "organized_output"
    plan = plan_batch_rename([pdf1, pdf2], output_folder=out_folder, organize_folders=True)

    results = apply_batch_rename(plan)
    assert len(results) == 2
    for r in results:
        assert r["success"] is True
        assert os.path.exists(r["new_path"])

    fatura_dir = out_folder / "fatura"
    odev_dir = out_folder / "odev"
    assert fatura_dir.is_dir()
    assert odev_dir.is_dir()
    assert len(list(fatura_dir.glob("*.pdf"))) == 1
    assert len(list(odev_dir.glob("*.pdf"))) == 1


def test_apply_batch_rename_missing_file_handled_gracefully(tmp_path):
    ghost_plan = [{
        "old_path": str(tmp_path / "non_existent.pdf"),
        "new_path": str(tmp_path / "new_name.pdf"),
        "type": "diger",
        "date": "",
        "subject": "",
        "collision_resolved": False,
    }]
    results = apply_batch_rename(ghost_plan)
    assert len(results) == 1
    assert results[0]["success"] is False
    assert results[0]["error"] is not None


# ── 6. Local LLM Fallback Tests ──────────────────────────────────────────


def test_local_llm_fallback_used_when_available(tmp_path):
    pdf = tmp_path / "unclear.pdf"
    _create_pdf_with_text(pdf, "Bazı özel metinler ve açıklamalar burada.")

    fake_json = '{"document_type": "rapor", "date": "2026-10-15", "subject": "Strateji"}'
    with patch("src.ai.local_llm.LocalLLM") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.available = True
        mock_instance.runtime_available = True
        mock_instance.generate.return_value = fake_json
        mock_cls.return_value = mock_instance

        meta = extract_metadata_fields(pdf)
        assert meta["document_type"] == "rapor"
        assert meta["date"] == "2026-10-15"
        assert meta["subject"] == "Strateji"
