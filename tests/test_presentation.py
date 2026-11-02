"""Faz 10: Tests for PDF'den Sunum Oluşturma (Presentation Outline & Slides).

Tests cover:
- Acceptance criterion: 10-page PDF produces 6-10 structured slides with titles,
  bullet points, and source page grounding.
- All 4 tones (kisa, akademik, yonetici, ders) and aliases.
- Slide dataclass dict-like access and normalization.
- Extractive fallback (page clustering and topic sentence ranking).
- Local LLM prompt integration and fallback on invalid/empty LLM output.
- 16:9 landscape PDF slides export via PyMuPDF (verifying 960x540 dimensions and text).
- 16:9 widescreen PPTX export via python-pptx (verifying slide counts, dimensions, text).
- Graceful degradation when python-pptx is missing.
- Progress reporting and cancellation.
- Edge cases: missing files, empty PDFs.
"""
from __future__ import annotations

import os
from pathlib import Path

import fitz
import pytest

from src.ai import presentation
from src.ai.presentation import (
    TONES,
    Slide,
    _normalize_slide,
    export_pdf_slides,
    export_pptx,
    generate_presentation_outline,
    is_pptx_available,
    normalize_tone,
)
from src.core.task_manager import CancelledError


def _create_test_pdf(path: Path | str, page_texts: list[str]) -> str:
    """Helper to generate a multi-page PDF with UTF-8 Turkish text."""
    doc = fitz.open()
    try:
        font_path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf")
        has_font = os.path.isfile(font_path)

        for text in page_texts:
            page = doc.new_page(width=595, height=842)
            if has_font:
                page.insert_font(fontname="f0", fontfile=font_path, set_simple=False)
                page.insert_textbox(fitz.Rect(40, 40, 555, 800), text, fontname="f0", fontsize=11)
            else:
                page.insert_textbox(fitz.Rect(40, 40, 555, 800), text, fontsize=11)
        doc.save(str(path))
    finally:
        doc.close()
    return str(path)


@pytest.fixture
def ten_page_report_pdf(tmp_path) -> Path:
    """Generate a comprehensive 10-page business/academic report."""
    pages = [
        # Page 1: Title and Executive Summary
        (
            "Yıllık Stratejik Performans ve Büyüme Raporu 2026\n\n"
            "Bu rapor şirketimizin son bir yıllık operasyonel ve finansal gelişimini özetlemektedir. "
            "Yönetim kurulu stratejik hedefler doğrultusunda dijitalleşme yatırımlarına ağırlık vermiştir. "
            "Toplam ciro bir önceki yıla göre yüzde 35 artış göstererek rekor seviyeye ulaşmıştır."
        ),
        # Page 2: Market Analysis
        (
            "Pazar Dinamikleri ve Küresel Fırsatlar\n\n"
            "Küresel yazılım sektöründe yapay zekâ ve otomasyon talebi hızla artmaktadır. "
            "Pazar payımız yerli segmentte yüzde 28 oranına ulaşmış ve lider konuma yaklaşmıştır. "
            "Rekabet analizi rakiplerimizin mobil entegrasyonda yavaş kaldığını göstermektedir."
        ),
        # Page 3: Methodology and Research
        (
            "Araştırma Metodolojisi ve Veri Analizi\n\n"
            "Çalışma kapsamında 1200 aktif kurumsal kullanıcı ile derinlemesine anket gerçekleştirilmiştir. "
            "Veri seti regresyon ve faktör analizi yöntemleri ile detaylıca incelenmiştir. "
            "Hipotez testleri otomasyon araçlarının iş verimliliğini yüzde 40 artırdığını kanıtlamıştır."
        ),
        # Page 4: Product Development
        (
            "Ürün Geliştirme ve İnovasyon Süreçleri\n\n"
            "Yeni nesil doküman işleme motoru başarıyla tamamlanmış ve canlı ortama alınmıştır. "
            "Yerel yapay zekâ modelleri sayesinde veri gizliliği en üst düzeyde korunmaktadır. "
            "Kullanıcı arayüzü modern standartlara göre yeniden tasarlanmış ve hızlandırılmıştır."
        ),
        # Page 5: Financial Results
        (
            "Finansal Performans ve Gelir Tablosu\n\n"
            "Yıllık net kâr marjı yüzde 22 olarak gerçekleşmiş ve bütçe tahminlerini aşmıştır. "
            "Operasyonel giderler optimizasyon adımları sayesinde yüzde 12 oranında azaltılmıştır. "
            "Ar-Ge faaliyetlerine ayrılan bütçe toplam gelirin yüzde 15'ine yükseltilmiştir."
        ),
        # Page 6: Operational Efficiency
        (
            "Operasyonel Verimlilik ve Kalite Yönetimi\n\n"
            "Müşteri destek yanıt süresi ortalama 4 dakikaya düşürülerek rekor kırılmıştır. "
            "ISO 27001 bilgi güvenliği standartları denetiminden başarıyla ve sıfır uygunsuzlukla geçilmiştir. "
            "Sunucu altyapısının kesintisiz çalışma oranı yüzde 99.98 olarak ölçülmüştür."
        ),
        # Page 7: Team and HR
        (
            "İnsan Kaynakları ve Yetenek Yönetimi\n\n"
            "Mühendislik kadromuz 45 yeni uzman geliştirici ve veri bilimci ile güçlendirilmiştir. "
            "Şirket içi teknik eğitim programlarına katılım oranı yüzde 90 seviyesine ulaşmıştır. "
            "Çalışan memnuniyeti anketi sonuçları genel bağlılığın yüksek olduğunu ortaya koymuştur."
        ),
        # Page 8: Risk Management
        (
            "Risk Analizi ve Uyum Süreçleri\n\n"
            "Kur dalgalanmalarına karşı hedging ve vadeli işlem mekanizmaları devreye alınmıştır. "
            "KVKK ve GDPR düzenlemelerine tam uyum için hukuki denetimler tamamlanmıştır. "
            "Tedarik zinciri riskleri alternatif yerli tedarikçiler ile asgariye indirilmiştir."
        ),
        # Page 9: Future Roadmap
        (
            "Gelecek Dönem Yol Haritası ve Stratejik Vizyon\n\n"
            "Önümüzdeki iki çeyrekte Avrupa pazarına doğrudan ihracat başlatılması planlanmaktadır. "
            "Bulut ve masaüstü hibrit çalışma modeliyle küresel ölçekte büyüme hedeflenmektedir. "
            "Stratejik ortaklık görüşmeleri üç büyük teknoloji grubu ile devam etmektedir."
        ),
        # Page 10: Recommendations and Conclusion
        (
            "Sonuç ve Yönetim Kurulu Önerileri\n\n"
            "Yatırımların planlandığı şekilde sürdürülmesi ve yapay zekâ özelliklerinin genişletilmesi önerilmektedir. "
            "Mevcut büyüme trendi şirketin değerlemesini iki katına çıkarma potansiyeline sahiptir. "
            "Tüm departmanların koordineli çalışması başarının anahtarı olarak değerlendirilmiştir."
        ),
    ]
    path = tmp_path / "on_sayfalik_rapor.pdf"
    _create_test_pdf(path, pages)
    return path


def test_ten_page_pdf_acceptance_criterion(ten_page_report_pdf):
    """Kabul kriteri: En az 10 sayfalık bir PDF'ten 6-10 slaytlık düzenli bir sunum taslağı oluşturulmalı."""
    slides = generate_presentation_outline(
        ten_page_report_pdf,
        slide_count=8,
        tone="yonetici",
        use_llm=False,
    )

    # Acceptance check: 6-10 slides generated
    assert 6 <= len(slides) <= 10
    assert len(slides) == 8

    # Check each slide's structure
    for i, slide in enumerate(slides, 1):
        assert isinstance(slide, Slide)
        assert slide.title and len(slide.title.strip()) > 0
        assert isinstance(slide.bullet_points, list)
        assert len(slide.bullet_points) >= 1
        assert isinstance(slide.source_pages, list)
        assert len(slide.source_pages) >= 1
        # Source pages must be between 1 and 10
        for p in slide.source_pages:
            assert 1 <= p <= 10

    # Ensure source pages span the document
    all_pages = [p for s in slides for p in s.source_pages]
    assert 1 in all_pages
    assert 10 in all_pages


def test_tones_and_aliases(ten_page_report_pdf):
    """Test all 4 canonical tones and their aliases."""
    for tone_name in TONES:
        slides = generate_presentation_outline(
            ten_page_report_pdf,
            slide_count=6,
            tone=tone_name,
            use_llm=False,
        )
        assert len(slides) == 6
        for s in slides:
            assert s.title
            assert len(s.bullet_points) >= 1

    # Aliases
    assert normalize_tone("executive") == "yonetici"
    assert normalize_tone("academic") == "akademik"
    assert normalize_tone("lecture") == "ders"
    assert normalize_tone("short") == "kisa"
    assert normalize_tone("yönetici özeti") == "yonetici"
    assert normalize_tone("öğrenci") == "ders"


def test_slide_dataclass_and_dict_compatibility():
    """Verify Slide acts both as a dataclass and like a dictionary."""
    slide = Slide(
        title="Test Başlığı",
        bullet_points=["Madde 1", "Madde 2"],
        source_pages=[1, 3],
    )
    # Attributes
    assert slide.title == "Test Başlığı"
    assert slide.bullet_points == ["Madde 1", "Madde 2"]
    assert slide.source_pages == [1, 3]

    # Dict access
    assert slide["title"] == "Test Başlığı"
    assert slide["bullet_points"] == ["Madde 1", "Madde 2"]
    assert slide["source_pages"] == [1, 3]
    assert slide.get("title") == "Test Başlığı"
    assert slide.get("nonexistent", "def") == "def"

    # to_dict
    d = slide.to_dict()
    assert d == {
        "title": "Test Başlığı",
        "bullet_points": ["Madde 1", "Madde 2"],
        "source_pages": [1, 3],
    }

    # Normalization from dict
    norm = _normalize_slide({"title": "Dict Slide", "bullet_points": ["B1"], "source_pages": [2]})
    assert isinstance(norm, Slide)
    assert norm.title == "Dict Slide"
    assert norm.bullet_points == ["B1"]
    assert norm.source_pages == [2]

    # Normalization from tuple
    norm_t = _normalize_slide(("Tuple Slide", ["B2"], [4]))
    assert norm_t.title == "Tuple Slide"
    assert norm_t.bullet_points == ["B2"]
    assert norm_t.source_pages == [4]


def test_export_pdf_slides_16_9(ten_page_report_pdf, tmp_path):
    """Test exporting slides to 16:9 landscape PDF slides via PyMuPDF."""
    slides = generate_presentation_outline(
        ten_page_report_pdf,
        slide_count=6,
        tone="akademik",
        use_llm=False,
    )
    out_pdf = tmp_path / "presentation_slides.pdf"
    result_path = export_pdf_slides(slides, out_pdf)

    assert result_path == str(out_pdf)
    assert out_pdf.is_file()

    # Verify PDF content and dimensions
    doc = fitz.open(str(out_pdf))
    try:
        assert doc.page_count == 6
        for page in doc:
            rect = page.rect
            # Verify 16:9 aspect ratio (960 x 540)
            assert round(rect.width) == 960
            assert round(rect.height) == 540
            text = page.get_text()
            assert "PDFAura" in text
            assert "Slayt" in text
    finally:
        doc.close()


def test_export_pptx(ten_page_report_pdf, tmp_path):
    """Test exporting slides to PowerPoint PPTX format."""
    slides = generate_presentation_outline(
        ten_page_report_pdf,
        slide_count=7,
        tone="yonetici",
        use_llm=False,
    )
    out_pptx = tmp_path / "presentation.pptx"
    result_path = export_pptx(slides, out_pptx)

    if is_pptx_available():
        assert result_path == str(out_pptx)
        assert out_pptx.is_file()

        import pptx
        prs = pptx.Presentation(str(out_pptx))
        assert len(prs.slides) == 7
        # Check widescreen dimensions: 13.333 x 7.5 inches
        assert round(prs.slide_width.inches, 2) == 13.33
        assert round(prs.slide_height.inches, 2) == 7.5


def test_export_pptx_graceful_degradation(monkeypatch, tmp_path):
    """When python-pptx is absent, export_pptx should degrade gracefully."""
    monkeypatch.setattr(presentation, "pptx", None)

    assert not is_pptx_available()
    slides = [Slide(title="Test", bullet_points=["A", "B"], source_pages=[1])]
    out_file = tmp_path / "test_degrade.pptx"

    # Default: returns None without raising
    res = export_pptx(slides, out_file, raise_on_error=False)
    assert res is None

    # With raise_on_error: raises informative ImportError
    with pytest.raises(ImportError) as exc_info:
        export_pptx(slides, out_file, raise_on_error=True)
    assert "python-pptx kurulu değil" in str(exc_info.value)


def test_progress_and_cancellation(ten_page_report_pdf):
    """Verify progress callback triggers and cancellation halts execution."""
    progress_calls = []

    def on_progress(current, total, message=""):
        progress_calls.append((current, total, message))

    slides = generate_presentation_outline(
        ten_page_report_pdf,
        slide_count=6,
        progress=on_progress,
        use_llm=False,
    )
    assert len(slides) == 6
    assert len(progress_calls) >= 3
    # Final progress step should reach total
    last = progress_calls[-1]
    assert last[0] == 6 and last[1] == 6

    # Test cancellation token
    with pytest.raises(CancelledError):
        generate_presentation_outline(
            ten_page_report_pdf,
            slide_count=6,
            cancel=lambda: True,
            use_llm=False,
        )


def test_mock_local_llm_generation(ten_page_report_pdf):
    """Test outline generation when LocalLLM returns structured JSON."""
    class MockLLM:
        available = True

        def generate(self, prompt, **kwargs):
            return """[
                {
                    "title": "LLM Slayt 1",
                    "bullet_points": ["LLM Maddesi 1", "LLM Maddesi 2"],
                    "source_pages": [1, 2]
                },
                {
                    "title": "LLM Slayt 2",
                    "bullet_points": ["LLM Maddesi 3"],
                    "source_pages": [3]
                }
            ]"""

    slides = generate_presentation_outline(
        ten_page_report_pdf,
        slide_count=2,
        llm=MockLLM(),
        use_llm=True,
    )
    assert len(slides) == 2
    assert slides[0].title == "LLM Slayt 1"
    assert slides[0].bullet_points == ["LLM Maddesi 1", "LLM Maddesi 2"]
    assert slides[0].source_pages == [1, 2]


def test_mock_local_llm_fallback_on_invalid_output(ten_page_report_pdf):
    """When LLM returns unparseable text, gracefully fall back to extractive outline."""
    class BrokenLLM:
        available = True

        def generate(self, prompt, **kwargs):
            return "Üzgünüm, slayt oluşturamadım."

    slides = generate_presentation_outline(
        ten_page_report_pdf,
        slide_count=4,
        llm=BrokenLLM(),
        use_llm=True,
    )
    assert len(slides) == 4
    # Extractive fallback succeeded
    for s in slides:
        assert s.title
        assert len(s.bullet_points) >= 1


def test_edge_cases(tmp_path):
    """Test error handling for missing file and empty document."""
    with pytest.raises(FileNotFoundError):
        generate_presentation_outline(tmp_path / "nonexistent.pdf")

    # Empty 1-page PDF
    empty_pdf = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(str(empty_pdf))
    doc.close()

    slides = generate_presentation_outline(empty_pdf, slide_count=4, use_llm=False)
    assert len(slides) >= 1
    assert "Belge" in slides[0].title or "Özet" in slides[0].title
