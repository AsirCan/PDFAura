"""Faz 5: Tests for Akıllı Özet Modları (PDF Summarizer).

Tests cover:
- All 5 modes: kisa, detayli, ogrenci, toplanti, hukuki.
- Every point carries source pages.
- Map-reduce processing for long documents.
- Extractive summarizer fallback (term-frequency sentence scoring) without an LLM.
- Export to TXT and PDF (via PyMuPDF) with intact Turkish characters.
- Cancellation and progress reporting.
- Graceful error / empty document handling.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import fitz
from src.ai.local_llm import LocalLLM
from src.ai.summarizer import (
    MODES,
    SummaryPoint,
    SummaryResult,
    Summarizer,
    normalize_mode,
    save_pdf,
    save_txt,
    summarize,
)
from src.core.task_manager import CancelledError


def _make_pdf(path: Path | str, pages: list[str]) -> str:
    """Generate a multi-page PDF containing extractable text with Turkish characters."""
    doc = fitz.open()
    try:
        font_path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf")
        has_font = os.path.isfile(font_path)

        for text in pages:
            page = doc.new_page(width=595, height=842)
            if has_font:
                page.insert_font(fontname="f0", fontfile=font_path, set_simple=False)
                page.insert_textbox(fitz.Rect(50, 50, 545, 790), text, fontname="f0", fontsize=11)
            else:
                page.insert_textbox(fitz.Rect(50, 50, 545, 790), text, fontsize=11)
        doc.save(str(path))
    finally:
        doc.close()
    return str(path)


@pytest.fixture
def multi_page_meeting_pdf(tmp_path) -> Path:
    """A 3-page meeting document with agendas, decisions, and action items."""
    path = tmp_path / "toplanti_belgesi.pdf"
    pages = [
        # Page 1: Agenda and opening
        (
            "Yönetim Kurulu Strateji ve Değerlendirme Toplantısı Tutanağı.\n"
            "Toplantı 15 Ekim tarihinde genel merkez binasında tüm üyelerin katılımıyla gerçekleştirilmiştir.\n"
            "Gündem kapsamında 2024 yılı üçüncü çeyrek bütçe performansı ve büyüme hedefleri görüşüldü.\n"
            "Şirketin toplam geliri geçen yıla kıyasla yüzde 25 artış göstererek 15 milyon TL seviyesine ulaşmıştır.\n"
            "Müşteri memnuniyeti oranının yüzde 94 olarak ölçüldüğü toplantıda değerlendirildi."
        ),
        # Page 2: Decisions
        (
            "Toplantıda Alınan Kararlar ve Kabul Edilen Hususlar.\n"
            "Yeni bulut altyapısına geçiş projesinin derhal başlatılmasına oy birliğiyle karar verildi.\n"
            "Müşteri destek ekibine 5 yeni uzman personel alınması hususunda mutabık kalındı ve bütçe onaylandı.\n"
            "Ar-Ge departmanı için ayrılan yıllık kaynak miktarının 2 milyon TL artırılması kararlaştırıldı.\n"
            "Avrupa pazarına açılma stratejisinin ilk etapta Almanya ve Hollanda üzerinden yürütülmesi uygun görüldü."
        ),
        # Page 3: Action items and deadlines
        (
            "Aksiyon Maddeleri, Sorumlular ve Takip Takvimi.\n"
            "Bilgi İşlem Direktörü Ahmet Bey bulut geçiş planını 30 Kasım tarihine kadar tamamlayacak ve sunacaktır.\n"
            "İnsan Kaynakları ekibi işe alım ilanlarını en geç önümüzdeki Cuma günü yayınlamakla sorumlu tutulmuştur.\n"
            "Mali İşler Direktörlüğü revize edilmiş bütçe raporunu hazırlayacak ve yönetim kuruluna teslim edecektir.\n"
            "Bir sonraki olağan değerlendirme toplantısının 15 Aralık tarihinde yapılması planlandı."
        ),
    ]
    _make_pdf(path, pages)
    return path


@pytest.fixture
def multi_page_legal_pdf(tmp_path) -> Path:
    """A 3-page commercial contract with parties, obligations, and penalties."""
    path = tmp_path / "hizmet_sozlesmesi.pdf"
    pages = [
        # Page 1: Parties and scope
        (
            "Yazılım Geliştirme ve Lisans Hizmet Sözleşmesi.\n"
            "İşbu sözleşme bir tarafta PDFAura Yazılım A.Ş. ile diğer tarafta Müşteri Teknoloji Ltd. Şti. arasında akdedilmiştir.\n"
            "Sözleşmenin konusu, mobil ve masaüstü belge yönetim yazılımlarının geliştirilmesi ve lisanslanmasıdır.\n"
            "İşbu anlaşma imza tarihinde yürürlüğe girer ve 2 yıl süreyle geçerli olacaktır.\n"
            "Taraflar sözleşmede belirtilen tebligat adreslerinin geçerli olduğunu kabul ve taahhüt eder."
        ),
        # Page 2: Rights and obligations
        (
            "Tarafların Temel Hak ve Yükümlülükleri.\n"
            "Yüklenici firma yazılım modüllerini teknik şartnamede belirtilen standartlara uygun olarak teslim etmekle yükümlüdür.\n"
            "Müşteri, her aşama onaylandığında fatura bedeli olan 250.000 TL ödemeyi 14 iş günü içinde yapmayı taahhüt eder.\n"
            "Geliştirilen yazılımın tüm fikri ve sınai mülkiyet hakları ödemelerin tamamlanması şartıyla Müşteri'ye ait olacaktır.\n"
            "Yüklenici teslim tarihinden itibaren 12 ay boyunca ücretsiz hata düzeltme ve bakım desteği sağlayacaktır."
        ),
        # Page 3: Termination, penalties, and jurisdiction
        (
            "Sözleşmenin Feshi, Cezai Şartlar ve Uyuşmazlıkların Çözümü.\n"
            "Taraflardan birinin sözleşme şartlarını ağır şekilde ihlal etmesi halinde 30 gün önceden yazılı bildirimle fesih yapılabilir.\n"
            "Teslimatta haksız gecikme yaşanması durumunda yüklenici her gecikilen gün için 5.000 TL cezai şart ödemekle yükümlüdür.\n"
            "Taraflar işbu sözleşmeden doğan gizli bilgileri üçüncü şahıslarla paylaşamaz; gizlilik ihlalinde tazminat hakkı saklıdır.\n"
            "Uyuşmazlıkların çözümünde İstanbul Çağlayan Mahkemeleri ve İcra Daireleri münhasıran yetkilidir."
        ),
    ]
    _make_pdf(path, pages)
    return path


@pytest.fixture
def multi_page_student_pdf(tmp_path) -> Path:
    """A 3-page academic study text with concepts, notes, and exam tips."""
    path = tmp_path / "yapay_zeka_ders_notu.pdf"
    pages = [
        # Page 1: Concepts and definitions
        (
            "Makine Öğrenmesi ve Doğal Dil İşleme Temel Ders Notları.\n"
            "Doğal Dil İşleme (NLP), bilgisayarların insan dilini anlamasını, yorumlamasını ve üretmesini sağlayan yapay zeka dalıdır.\n"
            "Kavram olarak Terim Frekansı (TF), bir kelimenin belirli bir belgede ne sıklıkla geçtiğini gösteren temel ölçüttür.\n"
            "Ters Belge Frekansı (IDF) ilkesi ise nadir geçen terimlere daha yüksek bilgi ağırlığı atanmasını ifade eder.\n"
            "Vektör uzay modeli, metin belgelerini çok boyutlu sayısal vektörler olarak temsil eden matematiksel modeldir."
        ),
        # Page 2: Principles and important notes
        (
            "Model Eğitimi ve Analiz Aşamalarında Önemli İlkeler.\n"
            "Modelin genelleme yeteneğini ölçmek amacıyla veri kümesi eğitim, doğrulama ve test olarak üç gruba ayrılmalıdır.\n"
            "Aşırı öğrenme (overfitting) durumunda model eğitim verisini ezberler ancak yeni verilerde başarısız sonuç verir.\n"
            "Özellikle etiketli veri eksikliği durumunda denetimsiz veya yarı-denetimli öğrenme yöntemleri tercih edilir.\n"
            "Doğruluk oranı tek başına yeterli bir performans metriği değildir; kesinlik ve duyarlılık da analiz edilmelidir."
        ),
        # Page 3: Exam review notes and takeaways
        (
            "Final Sınavı Hazırlık Hatırlatıcıları ve Çalışma İpuçları.\n"
            "Sınavda TF-IDF matrisi hesaplama soruları kesinlikle çıkacaktır, formül adımlarına dikkat ediniz.\n"
            "Örnek olarak kosinüs benzerliği formülü ile iki metin vektörü arasındaki açının nasıl hesaplandığını biliniz.\n"
            "Çalışma notu: Düzenlileştirme (regularization) teknikleri modelin karmaşıklığını sınırlandırmak için kullanılır.\n"
            "Sonuç olarak derin öğrenme modellerinde kayıp fonksiyonunun minimize edilmesi temel optimizasyon hedefidir."
        ),
    ]
    _make_pdf(path, pages)
    return path


# ── Mode Tests ─────────────────────────────────────────────────────────────

def test_summarize_kisa_mode(multi_page_meeting_pdf):
    result = summarize(multi_page_meeting_pdf, mode="kisa")

    assert isinstance(result, SummaryResult)
    assert result.mode == "kisa"
    assert not result.used_llm
    assert len(result.points) >= 3
    assert len(result.points) <= 6

    # Every point must carry valid page references
    for pt in result.points:
        assert pt.pages, f"Point missing page reference: {pt.text}"
        assert all(isinstance(p, int) and p >= 1 for p in pt.pages)

    # Output text should contain source page citations
    assert "[Sayfa " in result.text
    assert "# Kısa Özet" in result.text
    assert result.sources
    assert set(result.sources).issubset({1, 2, 3})


def test_summarize_detayli_mode(multi_page_meeting_pdf):
    result = summarize(multi_page_meeting_pdf, mode="detayli")

    assert result.mode == "detayli"
    assert not result.used_llm
    assert len(result.points) >= 4

    # Every point must carry page numbers
    for pt in result.points:
        assert pt.pages
        assert any(p in {1, 2, 3} for p in pt.pages)

    # Detaylı mode groups by pages for multi-page document
    assert "Sayfa 1" in result.text
    assert "Sayfa 2" in result.text
    assert "Sayfa 3" in result.text


def test_summarize_ogrenci_mode(multi_page_student_pdf):
    result = summarize(multi_page_student_pdf, mode="ogrenci")

    assert result.mode == "ogrenci"
    assert not result.used_llm
    assert len(result.points) >= 3

    # Every point must carry source page
    for pt in result.points:
        assert pt.pages
        assert 1 <= pt.pages[0] <= 3

    # Sections for student mode
    assert "Temel Tanımlar ve Kavramlar" in result.text
    assert "Önemli Notlar ve Ana Fikirler" in result.text
    assert "Sınav ve Çalışma Hatırlatıcıları" in result.text


def test_summarize_toplanti_mode(multi_page_meeting_pdf):
    result = summarize(multi_page_meeting_pdf, mode="toplanti")

    assert result.mode == "toplanti"
    assert not result.used_llm
    assert len(result.points) >= 3

    for pt in result.points:
        assert pt.pages

    # Sections for meeting mode
    assert "Alınan Kararlar" in result.text
    assert "Aksiyon Maddeleri ve Sorumluluklar" in result.text


def test_summarize_hukuki_mode(multi_page_legal_pdf):
    result = summarize(multi_page_legal_pdf, mode="hukuki")

    assert result.mode == "hukuki"
    assert not result.used_llm
    assert len(result.points) >= 3

    for pt in result.points:
        assert pt.pages

    # Sections for legal mode
    assert "Taraflar ve Sözleşmenin Kapsamı" in result.text
    assert "Temel Hak ve Yükümlülükler" in result.text
    assert "Fesih, Sorumluluk ve Cezai Şartlar" in result.text


def test_all_five_modes_available():
    for mode in MODES:
        norm = normalize_mode(mode)
        assert norm == mode


def test_mode_aliases():
    assert normalize_mode("short") == "kisa"
    assert normalize_mode("detailed") == "detayli"
    assert normalize_mode("student") == "ogrenci"
    assert normalize_mode("meeting") == "toplanti"
    assert normalize_mode("legal") == "hukuki"
    assert normalize_mode("sözleşme") == "hukuki"


# ── Map-Reduce Tests for Long Documents ────────────────────────────────────

def test_map_reduce_long_document(tmp_path):
    path = tmp_path / "uzun_dokuman.pdf"
    pages = [
        f"Sayfa {i} içeriği. Şirket büyüme hedefi yüzde {i * 10} olarak belirlendi. "
        f"Önemli projeler {i}. çeyrekte başarıyla tamamlanmıştır."
        for i in range(1, 6)  # 5 pages, exceeds LONG_DOC_PAGE_THRESHOLD (3)
    ]
    _make_pdf(path, pages)

    result = summarize(path, mode="kisa")

    assert result.metadata.get("is_long") is True
    assert result.metadata.get("method") == "extractive_map_reduce"
    assert len(result.points) >= 3
    # Sources should span multiple pages
    assert len(result.sources) >= 2
    for pt in result.points:
        assert pt.pages


def test_explicit_map_reduce_kwarg(tmp_path):
    path = tmp_path / "kisa_belge.pdf"
    _make_pdf(path, ["Tek sayfalık metin. Şirket kararı onaylandı."])

    # Force map-reduce even on single page
    result = summarize(path, mode="kisa", map_reduce=True)
    assert result.metadata.get("method") == "extractive_map_reduce"


# ── Saving Outputs: TXT and PDF with Turkish Characters ────────────────────

def test_save_txt(multi_page_meeting_pdf, tmp_path):
    result = summarize(multi_page_meeting_pdf, mode="kisa")
    txt_path = tmp_path / "ozet.txt"

    saved = save_txt(result, txt_path)
    assert Path(saved).is_file()

    with open(saved, "r", encoding="utf-8") as handle:
        content = handle.read()

    assert content == result.text
    assert "[Sayfa " in content
    # Also verify save_txt accepts a plain string
    str_path = tmp_path / "duz_yazi.txt"
    save_txt("Örnek Türkçe metin: Şirket, çağdaş.", str_path)
    assert "çağdaş" in str_path.read_text(encoding="utf-8")


def test_save_pdf_with_turkish_characters(tmp_path):
    pt1 = SummaryPoint(
        text="Şirket, sağladığı çağdaş çözümler ışığında %25 büyüme kaydetti.",
        pages=[1],
        section="Temel Noktalar",
    )
    pt2 = SummaryPoint(
        text="Öğrenci sınav notları: Ç, ç, Ğ, ğ, İ, ı, Ö, ö, Ş, ş, Ü, ü harfleri tamamen desteklenir.",
        pages=[2],
        section="Karakter Testi",
    )
    summary = SummaryResult(
        text=(
            "# Türkçe Karakter Test Özeti\n\n"
            "### Temel Noktalar\n"
            f"- {pt1.format_with_citation()}\n\n"
            "### Karakter Testi\n"
            f"- {pt2.format_with_citation()}\n"
        ),
        mode="kisa",
        language="tr",
        points=[pt1, pt2],
        sources=[1, 2],
        used_llm=False,
    )

    pdf_path = tmp_path / "turkce_ozet.pdf"
    saved_pdf = save_pdf(summary, pdf_path)

    assert Path(saved_pdf).is_file()
    assert os.path.getsize(saved_pdf) > 500

    # Read back with PyMuPDF to verify characters are intact
    doc = fitz.open(saved_pdf)
    assert doc.page_count >= 1
    extracted = doc[0].get_text()
    doc.close()

    # Verify Turkish characters exist in extracted text
    assert "Şirket" in extracted
    assert "çağdaş" in extracted
    assert "ışığında" in extracted
    for char in ("Ç", "ç", "Ğ", "ğ", "İ", "ı", "Ö", "ö", "Ş", "ş", "Ü", "ü"):
        assert char in extracted, f"Missing Turkish char {char} in saved PDF"


# ── Cancellation and Progress Reporting ────────────────────────────────────

def test_summarize_cancellation(multi_page_meeting_pdf):
    with pytest.raises(CancelledError):
        summarize(multi_page_meeting_pdf, mode="kisa", cancel=lambda: True)


def test_summarize_progress_callback(multi_page_meeting_pdf):
    progress_records: list[tuple[int, int, str]] = []

    def on_progress(current: int, total: int, message: str = ""):
        progress_records.append((current, total, message))

    result = summarize(multi_page_meeting_pdf, mode="kisa", progress=on_progress)

    assert progress_records
    assert any(cur >= 10 for cur, _, _ in progress_records)
    assert progress_records[-1][0] == 100  # Final completion


# ── Edge Cases & English Language ──────────────────────────────────────────

def test_empty_pdf(tmp_path):
    empty_pdf = tmp_path / "bos.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(str(empty_pdf))
    doc.close()

    result = summarize(empty_pdf, mode="kisa")
    assert result.points == []
    assert result.sources == []
    assert "bulunamadı" in result.text or "metin" in result.text


def test_english_language_support(tmp_path):
    path = tmp_path / "english_doc.pdf"
    pages = [
        "Company Quarterly Report.\n"
        "Revenue increased by 18 percent to 12 million dollars.\n"
        "Customer satisfaction reached 92 percent according to the latest survey.\n"
        "New product launch is scheduled for September.",
        "Strategic Decisions and Action Items.\n"
        "The board approved the expansion into European markets.\n"
        "Engineering team will finalize the migration by October.\n"
        "Next executive review will take place in December.",
    ]
    _make_pdf(path, pages)

    result = summarize(path, mode="kisa", language="en")

    assert result.language == "en"
    assert "# Executive Summary" in result.text
    assert "[Page " in result.text
    for pt in result.points:
        assert pt.pages


# ── LLM Fallback & Fake Model Integration ──────────────────────────────────

def test_llm_fallback_when_unavailable(multi_page_meeting_pdf, tmp_path):
    # Pass an LLM whose model file does not exist
    fake_llm = LocalLLM(model_path=str(tmp_path / "nonexistent.gguf"))
    result = summarize(multi_page_meeting_pdf, mode="kisa", llm=fake_llm, use_llm=True)

    # Should gracefully degrade to extractive without raising RuntimeError
    assert not result.used_llm
    assert len(result.points) >= 3


def test_llm_generation_with_fake_runtime(tmp_path):
    path = tmp_path / "test_doc.pdf"
    _make_pdf(path, ["İlk sayfa içeriği hakkında kısa bir açıklama."])

    gguf_path = tmp_path / "model.gguf"
    gguf_path.write_bytes(b"gguf")

    class FakeLlamaModel:
        def __call__(self, prompt, **kwargs):
            return iter([
                {"choices": [{"text": "# Kısa Özet\n- Önemli bir gelişme sağlandı. [Sayfa 1]\n- İkinci karar onaylandı. [Sayfa 1]"}]},
            ])

    llm = LocalLLM(str(gguf_path), model_factory=lambda **kwargs: FakeLlamaModel())
    result = summarize(path, mode="kisa", llm=llm, use_llm=True)

    assert result.used_llm
    assert len(result.points) >= 1
    assert result.sources == [1]
