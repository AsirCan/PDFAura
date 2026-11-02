"""Faz 10: PDF comparison and change explanation tests."""
import os
from unittest.mock import patch

import fitz
import pytest

from src.core.compare import (
    CATEGORY_FORMAT,
    CATEGORY_MEANING,
    CATEGORY_RISKY,
    compare_pdfs,
    explain_changes,
    export_report_pdf,
)
from src.core.task_manager import CancelledError


def make_pdf(path, pages_text, metadata: dict | None = None) -> str:
    """Create a test PDF with given pages of text and optional metadata."""
    doc = fitz.open()
    try:
        if metadata:
            doc.set_metadata(metadata)
        for page_idx, text in enumerate(pages_text):
            page = doc.new_page()
            # Insert each paragraph separated vertically
            y = 72
            for para in text.split("\n\n"):
                if para.strip():
                    page.insert_text((72, y), para.strip(), fontsize=11)
                    y += 36 + len(para.splitlines()) * 14
        doc.save(str(path))
    finally:
        doc.close()
    return str(path)


# ── Contract Diff with Page References ───────────────────────────────────────

def test_contract_two_versions_added_removed_clauses(tmp_path):
    """Two versions of a generated contract with added/removed clauses

    listed with correct page refs.
    """
    v1_pages = [
        # Page 1
        "Madde 1: Taraflar ve Kapsam\nİşbu sözleşme Şirket A ile Şirket B arasında akdedilmiştir.\n\n"
        "Madde 2: Hizmet Bedeli ve Ödeme\nAylık hizmet bedeli 10.000 TL dir.",
        # Page 2
        "Madde 3: Sözleşme Süresi\nSözleşme süresi 1 yıldır.\n\n"
        "Madde 4: Cezai Şart\nSözleşmenin ihlali halinde 50.000 TL ceza ödenir.\n\n"
        "Madde 5: Fesih Koşulları\nTaraflar 30 gün önceden yazılı bildirim ile feshedebilir.",
    ]

    v2_pages = [
        # Page 1
        "Madde 1: Taraflar ve Kapsam\nİşbu sözleşme Şirket A ile Şirket B arasında akdedilmiştir.\n\n"
        "Madde 2: Hizmet Bedeli ve Ödeme\nAylık hizmet bedeli 20.000 TL dir.",  # Bedel changed
        # Page 2
        "Madde 3: Sözleşme Süresi\nSözleşme süresi 2 yıldır.\n\n"  # Süre changed
        # Madde 4 (Cezai Şart) is REMOVED from Page 2
        "Madde 5: Fesih Koşulları\nTaraflar 60 gün önceden yazılı bildirim ile feshedebilir.\n\n"  # 30 -> 60 changed
        "Madde 6: Gizlilik ve Bilgi Güvenliği\nTaraflar gizli bilgileri korumayı taahhüt eder.",  # ADDED on Page 2
    ]

    pdf1 = make_pdf(tmp_path / "sozlesme_v1.pdf", v1_pages)
    pdf2 = make_pdf(tmp_path / "sozlesme_v2.pdf", v2_pages)

    report = compare_pdfs(pdf1, pdf2)
    assert report["has_changes"] is True
    assert report["page_count"]["a"] == 2
    assert report["page_count"]["b"] == 2
    assert report["page_count"]["delta"] == 0

    changes = report["changes"]

    # Verify removed clause (Madde 4) was detected on Page 2 of doc A
    removed_items = [c for c in changes if c["type"] == "removed"]
    assert len(removed_items) >= 1
    removed_ceza = next(c for c in removed_items if "Cezai Şart" in c["a_text"] or "ceza" in c["a_text"].lower())
    assert removed_ceza["a_page"] == 2
    assert removed_ceza["category"] == CATEGORY_RISKY

    # Verify added clause (Madde 6) was detected on Page 2 of doc B
    added_items = [c for c in changes if c["type"] == "added"]
    assert len(added_items) >= 1
    added_gizlilik = next(c for c in added_items if "Gizlilik" in c["b_text"])
    assert added_gizlilik["b_page"] == 2

    # Verify changed clauses with correct page references
    changed_items = [c for c in changes if c["type"] == "changed"]
    # Bedel on page 1
    bedel_change = next(c for c in changed_items if "20.000 TL" in c["b_text"])
    assert bedel_change["a_page"] == 1
    assert bedel_change["b_page"] == 1
    assert bedel_change["category"] == CATEGORY_RISKY

    # Fesih on page 2
    fesih_change = next(c for c in changed_items if "60 gün" in c["b_text"])
    assert fesih_change["a_page"] == 2
    assert fesih_change["b_page"] == 2
    assert fesih_change["category"] == CATEGORY_RISKY

    # Check pages structure
    pages = report["pages"]
    assert len(pages) == 2
    p1 = pages[0]
    p2 = pages[1]
    assert p1["a_page"] == 1 and p1["b_page"] == 1
    assert p2["a_page"] == 2 and p2["b_page"] == 2
    assert any("20.000 TL" in c.get("b_text", "") for c in p1["text_changes"])
    assert any("Gizlilik" in c.get("b_text", "") for c in p2["text_changes"])
    assert any("Cezai Şart" in c.get("a_text", "") or "ceza" in c.get("a_text", "").lower()
               for c in p2["text_changes"])


# ── Change Classification (biçim, anlam, riskli) ────────────────────────────

def test_classify_format_change(tmp_path):
    """Whitespace, punctuation and case changes are classified as 'biçim'."""
    v1 = ["Madde 1: Genel İlkeler\nTaraflar iyi niyet çerçevesinde hareket eder."]
    v2 = ["MADDE 1: GENEL İLKELER\nTaraflar,   iyi niyet çerçevesinde hareket eder."]

    pdf1 = make_pdf(tmp_path / "v1.pdf", v1)
    pdf2 = make_pdf(tmp_path / "v2.pdf", v2)

    report = compare_pdfs(pdf1, pdf2)
    changes = [c for c in report["changes"] if c["type"] != "image"]
    assert len(changes) > 0
    for c in changes:
        assert c["category"] == CATEGORY_FORMAT


def test_classify_meaning_change(tmp_path):
    """Wording change without numbers, dates, amounts, percentages, or keywords is 'anlam'."""
    v1 = ["Madde 1: Taraflar işbu protokolü karşılıklı iyi niyetle yürütmeyi taahhüt eder."]
    v2 = ["Madde 1: Taraflar işbu protokolü karşılıklı dürüstlükle yürütmeyi taahhüt eder."]

    pdf1 = make_pdf(tmp_path / "v1.pdf", v1)
    pdf2 = make_pdf(tmp_path / "v2.pdf", v2)

    report = compare_pdfs(pdf1, pdf2)
    changes = [c for c in report["changes"] if c["type"] != "image"]
    assert len(changes) == 1
    assert changes[0]["category"] == CATEGORY_MEANING


def test_classify_risk_numbers_and_dates(tmp_path):
    """Changes in numbers, dates, amounts or percentages are 'riskli'."""
    v1 = [
        "Teslim tarihi 15 Mayıs 2024 olarak belirlenmiştir.\n\n"
        "Gecikme zammı %5 oranında tahsil edilir."
    ]
    v2 = [
        "Teslim tarihi 15 Haziran 2024 olarak belirlenmiştir.\n\n"  # Month changed
        "Gecikme zammı %15 oranında tahsil edilir."  # %5 -> %15 changed
    ]

    pdf1 = make_pdf(tmp_path / "v1.pdf", v1)
    pdf2 = make_pdf(tmp_path / "v2.pdf", v2)

    report = compare_pdfs(pdf1, pdf2)
    changes = [c for c in report["changes"] if c["type"] != "image"]
    assert len(changes) >= 2
    for c in changes:
        assert c["category"] == CATEGORY_RISKY


def test_classify_risk_keywords(tmp_path):
    """Changes involving keywords ceza, tazminat, fesih, süre, ödeme are 'riskli'."""
    v1 = [
        "Sözleşmeye aykırılık halinde ceza uygulanmaz.\n\n"
        "İşbu belgenin feshi yazılı bildirimle mümkündür."
    ]
    v2 = [
        "Sözleşmeye aykırılık halinde ceza uygulanacaktır.\n\n"
        "İşbu belgenin feshi noter kanalıyla yapılacaktır."
    ]

    pdf1 = make_pdf(tmp_path / "v1.pdf", v1)
    pdf2 = make_pdf(tmp_path / "v2.pdf", v2)

    report = compare_pdfs(pdf1, pdf2)
    changes = [c for c in report["changes"] if c["type"] != "image"]
    assert len(changes) >= 2
    for c in changes:
        assert c["category"] == CATEGORY_RISKY


# ── Metadata Differences ─────────────────────────────────────────────────────

def test_metadata_diffs(tmp_path):
    """Metadata differences are detected and reported."""
    v1 = ["İçerik metni."]
    v2 = ["İçerik metni."]

    pdf1 = make_pdf(tmp_path / "v1.pdf", v1, metadata={"title": "Eski Başlık", "author": "Ahmet"})
    pdf2 = make_pdf(tmp_path / "v2.pdf", v2, metadata={"title": "Yeni Başlık", "author": "Ahmet"})

    report = compare_pdfs(pdf1, pdf2)
    meta_changes = report["metadata_changes"]
    assert len(meta_changes) == 1
    assert meta_changes[0]["field"] == "title"
    assert meta_changes[0]["a_text"] == "Eski Başlık"
    assert meta_changes[0]["b_text"] == "Yeni Başlık"


# ── Image Diff Ratio per Page ───────────────────────────────────────────────

def test_image_diff_ratio(tmp_path):
    """Rendered-pixmap image diff ratio is computed per page."""
    # Create identical pages
    pdf1 = make_pdf(tmp_path / "p1.pdf", ["Sayfa 1 metni.", "Sayfa 2 metni."])
    pdf2 = make_pdf(tmp_path / "p2.pdf", ["Sayfa 1 metni.", "Sayfa 2 metni."])

    report_same = compare_pdfs(pdf1, pdf2)
    for p in report_same["pages"]:
        ratio = p["image_diff"]["ratio"]
        assert ratio is not None
        assert ratio == 0.0

    # Create modified page 2
    pdf3 = make_pdf(tmp_path / "p3.pdf", [
        "Sayfa 1 metni.",
        "Sayfa 2 tamamen değiştirilmiş ve bambaşka uzun bir metin ile doldurulmuştur.",
    ])
    report_diff = compare_pdfs(pdf1, pdf3)
    p2 = report_diff["pages"][1]
    assert p2["image_diff"]["ratio"] > 0.0
    assert p2["image_diff_ratio"] == p2["image_diff"]["ratio"]


# ── Page Count Changes ───────────────────────────────────────────────────────

def test_page_count_addition_and_removal(tmp_path):
    """Adding or removing pages is correctly identified."""
    pdf1 = make_pdf(tmp_path / "doc1.pdf", ["Sayfa 1", "Sayfa 2", "Sayfa 3"])
    pdf2 = make_pdf(tmp_path / "doc2.pdf", ["Sayfa 1"])

    report = compare_pdfs(pdf1, pdf2)
    assert report["page_count"]["a"] == 3
    assert report["page_count"]["b"] == 1
    assert report["page_count"]["delta"] == -2
    assert report["summary"]["pages_removed"] == [2, 3]


# ── Explanation (LLM & Turkish Template) ────────────────────────────────────

def test_explain_changes_template():
    """Deterministic Turkish template explanation when local LLM is absent."""
    report = {
        "a": {"path": "sozlesme_v1.pdf"},
        "b": {"path": "sozlesme_v2.pdf"},
        "page_count": {"a": 2, "b": 2, "delta": 0},
        "summary": {
            "total_changes": 2,
            "by_category": {CATEGORY_RISKY: 1, CATEGORY_MEANING: 1, CATEGORY_FORMAT: 0},
        },
        "changes": [
            {
                "type": "changed",
                "category": CATEGORY_RISKY,
                "a_page": 1,
                "b_page": 1,
                "b_text": "Aylık kira 15.000 TL.",
            },
            {
                "type": "added",
                "category": CATEGORY_MEANING,
                "a_page": None,
                "b_page": 2,
                "b_text": "Yeni ek madde.",
            },
        ],
    }

    text = explain_changes(report)
    assert "toplam 2 fark bulundu" in text
    assert "1 tanesi riskli" in text
    assert "Riskli değişiklikler:" in text
    assert "Sayfa 1" in text
    assert "15.000 TL" in text


def test_explain_changes_via_mock_llm():
    """Explanation delegates to local_llm.generate when available."""
    report = {
        "a": {"path": "v1.pdf"},
        "b": {"path": "v2.pdf"},
        "page_count": {"a": 1, "b": 1, "delta": 0},
        "changes": [{"type": "changed", "category": "riskli", "a_page": 1, "b_page": 1, "b_text": "Değişiklik"}],
        "summary": {"total_changes": 1, "by_category": {"riskli": 1}},
    }

    with patch("src.ai.local_llm.generate", return_value="Yapay zeka açıklaması: Sözleşme bedeli değişti."):
        result = explain_changes(report)
        assert result == "Yapay zeka açıklaması: Sözleşme bedeli değişti."


# ── Report PDF Export ────────────────────────────────────────────────────────

def test_export_report_pdf(tmp_path):
    """export_report_pdf writes a readable PDF with Turkish characters."""
    v1 = ["Madde 1: Eski Hizmet Şartları\nAylık 5000 TL ödeme."]
    v2 = ["Madde 1: Yeni Hizmet Şartları\nAylık 7500 TL ödeme ve 1000 TL ceza."]

    pdf1 = make_pdf(tmp_path / "v1.pdf", v1, metadata={"title": "Protokol v1"})
    pdf2 = make_pdf(tmp_path / "v2.pdf", v2, metadata={"title": "Protokol v2"})

    report = compare_pdfs(pdf1, pdf2)
    out_pdf = tmp_path / "rapor.pdf"

    ret_path = export_report_pdf(report, out_pdf)
    assert os.path.isfile(ret_path)
    assert ret_path == str(out_pdf)

    # Verify PDF content and Turkish characters with fitz
    doc = fitz.open(str(out_pdf))
    assert len(doc) >= 1
    content = doc[0].get_text()
    doc.close()

    assert "PDF" in content
    assert "Karşılaştırma" in content or "Karsilastirma" in content
    assert "Raporu" in content
    assert "7500" in content or "ceza" in content.lower()


# ── Progress and Cancellation ───────────────────────────────────────────────

def test_compare_progress_and_cancel(tmp_path):
    """Progress callbacks are called and cancellation stops the process."""
    pdf1 = make_pdf(tmp_path / "v1.pdf", ["Sayfa 1 metni.", "Sayfa 2 metni."])
    pdf2 = make_pdf(tmp_path / "v2.pdf", ["Sayfa 1 metni.", "Sayfa 2 güncel metin."])

    progress_events = []

    def on_progress(cur, tot, msg=""):
        progress_events.append((cur, tot, msg))

    report = compare_pdfs(pdf1, pdf2, progress=on_progress)
    assert len(progress_events) > 0

    # Test cancellation
    with pytest.raises(CancelledError):
        compare_pdfs(pdf1, pdf2, cancel=lambda: True)


def test_compare_missing_file():
    """Missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        compare_pdfs("non_existent_1.pdf", "non_existent_2.pdf")


def test_compare_identical_pdfs(tmp_path):
    """Identical PDFs produce has_changes=False and 0 changes."""
    pdf1 = make_pdf(tmp_path / "same1.pdf", ["Aynı metin sayfası 1.", "Aynı metin sayfası 2."])
    pdf2 = make_pdf(tmp_path / "same2.pdf", ["Aynı metin sayfası 1.", "Aynı metin sayfası 2."])

    report = compare_pdfs(pdf1, pdf2)
    assert report["has_changes"] is False
    assert report["summary"]["total_changes"] == 0
    assert len(report["changes"]) == 0
    assert report["page_count"]["delta"] == 0


def test_compare_password_protected(tmp_path):
    """Password-protected PDF raises PdfPasswordError."""
    from src.core.common import PdfPasswordError

    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((72, 72), "Gizli metin")
    enc_path = tmp_path / "encrypted.pdf"
    doc.save(str(enc_path), encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret")
    doc.close()

    normal = make_pdf(tmp_path / "normal.pdf", ["Normal metin"])

    with pytest.raises(PdfPasswordError):
        compare_pdfs(enc_path, normal)
