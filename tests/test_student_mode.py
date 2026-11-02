"""Tests for Faz 10 / Section 9: Öğrenci Modu (Student Mode Backend).

Covers:
- Generating comprehensive study packs from multi-page PDFs.
- Source page grounding: every key point, question, cloze, and card carries its source page.
- Extractive/rule-based heuristics fallback when Local LLM is absent.
- Realistic cloze deletions (fill-in-the-blanks) and concept flashcards.
- Multiple-choice questions with plausible distractors and open-ended questions.
- Optional LocalLLM prompting and graceful fallback on LLM errors/empty output.
- Export to TXT and formatted PDF via PyMuPDF with full Turkish character support.
- Cancellation and progress reporting.
- Graceful degradation on empty or minimal documents.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import fitz
from src.ai.student_mode import (
    FillInBlank,
    Flashcard,
    KeyPoint,
    Question,
    StudyPack,
    export_study_pdf,
    export_study_txt,
    generate_exam_notes,
    generate_fill_in_blanks,
    generate_flashcards,
    generate_questions,
    generate_study_pack,
)
from src.core.task_manager import CancelledError


def _make_pdf(path: Path | str, pages: list[str]) -> str:
    """Helper to generate a multi-page PDF with Turkish text."""
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
def multi_page_biology_pdf(tmp_path) -> Path:
    """A 3-page Biology textbook chapter with definitions, mechanisms, and summaries."""
    path = tmp_path / "biyoloji_hucre_bolunmesi.pdf"
    pages = [
        # Page 1: Cell structure and Mitochondria
        (
            "Bölüm 1: Hücre Yapısı ve Organeller.\n"
            "Hücre, yaşayan tüm canlıların temel yapısal ve işlevsel birimidir.\n"
            "Mitokondri: Hücrenin temel enerji santralidir ve oksijenli solunumla ATP üretir.\n"
            "Kloroplast ise sadece bitki hücrelerinde bulunur ve fotosentez sürecini yürütür.\n"
            "Ribozom, protein sentezinden sorumlu zarsız bir organeldir.\n"
            "Çekirdek: Hücrenin genetik materyali olan DNA molekülünü barındırır ve korur."
        ),
        # Page 2: Mitosis and Meiosis
        (
            "Bölüm 2: Hücre Bölünmesi ve Aşamaları.\n"
            "Mitoz bölünme, vücut hücrelerinde gerçekleşir ve iki yeni özdeş hücre üretir.\n"
            "Mitoz bölünmenin temel aşamaları profaz, metafaz, anafaz ve telofaz olarak adlandırılır.\n"
            "Kromozomların hücre ekvatorunda tek sıra halinde dizildiği evreye metafaz denir.\n"
            "Mayoz bölünme sonucunda kromozom sayısı yarıya iner ve genetik çeşitlilik sağlanır.\n"
            "Krossing-over olayı, homolog kromozomlar arasındaki gen alışverişidir."
        ),
        # Page 3: Photosynthesis and Energy
        (
            "Bölüm 3: Enerji Dönüşümleri ve Fotosentez.\n"
            "Fotosentez: Işık enerjisinin klorofiller tarafından soğurularak kimyasal enerjiye çevrilmesidir.\n"
            "Işığa bağımlı reaksiyonlar tilakoit zarda gerçekleşir ve oksijen gazı açığa çıkar.\n"
            "Kalvin döngüsü stromada gerçekleşir ve karbondioksit kullanılarak glikoz üretilir.\n"
            "Hücresel solunum, glikozun parçalanarak hücresel enerjiye dönüştürülmesi sürecidir.\n"
            "ATP molekülü tüm canlı hücrelerde enerji taşıyıcısı olarak görev yapar."
        ),
    ]
    _make_pdf(path, pages)
    return path


@pytest.fixture
def multi_page_english_pdf(tmp_path) -> Path:
    """A 2-page Computer Science study sheet in English."""
    path = tmp_path / "operating_systems.pdf"
    pages = [
        # Page 1
        (
            "Chapter 1: Operating System Fundamentals.\n"
            "The operating system is essential software that manages hardware resources.\n"
            "A process is defined as an executing instance of a program in memory.\n"
            "Virtual memory enables systems to address more memory than physically installed.\n"
            "Deadlock refers to a situation where competing actions wait indefinitely."
        ),
        # Page 2
        (
            "Chapter 2: Concurrency and Scheduling.\n"
            "CPU scheduling algorithms determine which process runs on the CPU core.\n"
            "Round Robin: A preemptive scheduling algorithm using fixed time quantums.\n"
            "Threads share the process memory space while maintaining independent stack frames.\n"
            "Mutual exclusion prevents multiple threads from accessing shared critical sections."
        ),
    ]
    _make_pdf(path, pages)
    return path


# ── Core Generation Tests ───────────────────────────────────────────────────

def test_generate_study_pack_structure(multi_page_biology_pdf):
    """Test that generate_study_pack returns a dict with all expected sections and page grounding."""
    pack = generate_study_pack(multi_page_biology_pdf, question_count=6, use_llm=False)

    assert isinstance(pack, dict)
    assert isinstance(pack, StudyPack)
    assert "key_points" in pack
    assert "questions" in pack
    assert "fill_in_blanks" in pack
    assert "flashcards" in pack
    assert pack.page_count == 3

    # Check key points
    assert len(pack.key_points) > 0
    for kp in pack.key_points:
        assert isinstance(kp, KeyPoint)
        assert isinstance(kp, dict)
        assert kp["text"]
        assert kp["page"] in (1, 2, 3)
        assert 1 in kp["pages"] or 2 in kp["pages"] or 3 in kp["pages"]

    # Check questions
    assert len(pack.questions) > 0
    assert len(pack.questions) <= 6
    for q in pack.questions:
        assert isinstance(q, Question)
        assert q["question"]
        assert q["answer"]
        assert q["page"] in (1, 2, 3)
        if q["type"] == "multiple_choice":
            assert len(q["options"]) == 4

    # Check fill in blanks
    assert len(pack.fill_in_blanks) > 0
    for fb in pack.fill_in_blanks:
        assert isinstance(fb, FillInBlank)
        assert "_______" in fb["blank_sentence"]
        assert fb["answer"]
        assert fb["page"] in (1, 2, 3)

    # Check flashcards
    assert len(pack.flashcards) > 0
    for card in pack.flashcards:
        assert isinstance(card, Flashcard)
        assert card["front"]
        assert card["back"]
        assert card["page"] in (1, 2, 3)


def test_generate_study_pack_flag_toggles(multi_page_biology_pdf):
    """Test that include_flashcards and include_fill_blanks toggles are strictly respected."""
    pack_no_cards = generate_study_pack(
        multi_page_biology_pdf,
        question_count=4,
        include_flashcards=False,
        include_fill_blanks=True,
        use_llm=False,
    )
    assert len(pack_no_cards.flashcards) == 0
    assert len(pack_no_cards.fill_in_blanks) > 0

    pack_no_blanks = generate_study_pack(
        multi_page_biology_pdf,
        question_count=4,
        include_flashcards=True,
        include_fill_blanks=False,
        use_llm=False,
    )
    assert len(pack_no_blanks.flashcards) > 0
    assert len(pack_no_blanks.fill_in_blanks) == 0


def test_question_count_parameter(multi_page_biology_pdf):
    """Test that question_count controls the number of generated questions."""
    pack_small = generate_study_pack(multi_page_biology_pdf, question_count=3, use_llm=False)
    assert len(pack_small.questions) == 3

    pack_large = generate_study_pack(multi_page_biology_pdf, question_count=8, use_llm=False)
    assert len(pack_large.questions) <= 8
    assert len(pack_large.questions) >= 4


def test_page_grounding_accuracy(multi_page_biology_pdf):
    """Verify that facts from specific pages carry the exact source page number."""
    pack = generate_study_pack(multi_page_biology_pdf, question_count=10, use_llm=False)

    # Every item tagged with page 1 must be from page 1 content
    p1_items = [item for item in (pack.key_points + pack.flashcards) if item["page"] == 1]
    assert len(p1_items) > 0
    p1_vocabulary = ("hücre", "mitokondri", "kloroplast", "ribozom", "çekirdek", "dna", "atp", "organel")
    for item in p1_items:
        assert any(w in str(item).lower() for w in p1_vocabulary)

    # Every item tagged with page 2 must be from page 2 content
    p2_items = [item for item in (pack.key_points + pack.flashcards) if item["page"] == 2]
    assert len(p2_items) > 0
    p2_vocabulary = ("mitoz", "metafaz", "mayoz", "kromozom", "krossing-over", "bölünme", "evre")
    for item in p2_items:
        assert any(w in str(item).lower() for w in p2_vocabulary)

    # Every item tagged with page 3 must be from page 3 content
    p3_items = [item for item in (pack.key_points + pack.flashcards) if item["page"] == 3]
    assert len(p3_items) > 0
    p3_vocabulary = ("fotosentez", "solunum", "kalvin", "tilakoit", "glikoz", "ışık", "stroma", "atp", "reaksiyon")
    for item in p3_items:
        assert any(w in str(item).lower() for w in p3_vocabulary)


def test_convenience_functions(multi_page_biology_pdf):
    """Test dedicated action functions: generate_questions, generate_fill_in_blanks, etc."""
    questions = generate_questions(multi_page_biology_pdf, question_count=5, use_llm=False)
    assert isinstance(questions, list)
    assert len(questions) == 5
    assert all(isinstance(q, Question) for q in questions)

    blanks = generate_fill_in_blanks(multi_page_biology_pdf, count=4, use_llm=False)
    assert isinstance(blanks, list)
    assert len(blanks) > 0
    assert all(isinstance(fb, FillInBlank) for fb in blanks)

    cards = generate_flashcards(multi_page_biology_pdf, count=4, use_llm=False)
    assert isinstance(cards, list)
    assert len(cards) > 0
    assert all(isinstance(c, Flashcard) for c in cards)

    notes = generate_exam_notes(multi_page_biology_pdf, count=5, use_llm=False)
    assert isinstance(notes, list)
    assert len(notes) > 0
    assert all(isinstance(n, KeyPoint) for n in notes)


# ── Extractive Heuristics Quality ───────────────────────────────────────────

def test_cloze_deletion_heuristics(multi_page_biology_pdf):
    """Verify that cloze deletions blank out realistic technical words, not stopwords."""
    blanks = generate_fill_in_blanks(multi_page_biology_pdf, count=6, use_llm=False)
    assert len(blanks) > 0
    for fb in blanks:
        ans = fb.answer.lower()
        # Answer must not be a stopword
        assert ans not in ("ve", "bir", "ise", "veya", "da", "de", "bu")
        # Answer must be at least 4 characters
        assert len(ans) >= 4
        # Blank sentence contains _______
        assert "_______" in fb.blank_sentence
        # Hint is present
        assert fb.hint != ""


def test_concept_flashcard_heuristics(multi_page_biology_pdf):
    """Verify concept flashcard extraction from definition and colon patterns."""
    cards = generate_flashcards(multi_page_biology_pdf, count=8, use_llm=False)
    assert len(cards) > 0
    fronts = [c.front.lower() for c in cards]

    # Verify key concepts appear on the front of flashcards
    has_target_concept = any(
        any(k in f for k in ("mitokondri", "çekirdek", "mitoz", "fotosentez", "kloroplast"))
        for f in fronts
    )
    assert has_target_concept


def test_english_study_pack(multi_page_english_pdf):
    """Verify study pack generation works cleanly for English material."""
    pack = generate_study_pack(multi_page_english_pdf, question_count=4, use_llm=False)
    assert pack.page_count == 2
    assert len(pack.key_points) > 0
    assert len(pack.questions) > 0
    assert len(pack.fill_in_blanks) > 0
    assert len(pack.flashcards) > 0


# ── Export Helpers Tests ───────────────────────────────────────────────────

def test_export_study_txt(multi_page_biology_pdf, tmp_path):
    """Verify exporting study pack to a UTF-8 text file."""
    pack = generate_study_pack(multi_page_biology_pdf, question_count=5, use_llm=False)
    out_txt = tmp_path / "calisma_paketi.txt"

    result_path = export_study_txt(pack, out_txt)
    assert Path(result_path).is_file()

    content = Path(result_path).read_text(encoding="utf-8")
    assert "PDFAURA" in content.upper()
    assert "ÖNEMLİ NOKTALAR VE SINAV ÖZETİ" in content
    assert "TEST VE ÇALIŞMA SORULARI" in content
    assert "BOŞLUK DOLDURMA ALIŞTIRMALARI" in content
    assert "BİLGİ KARTLARI (FLASHCARDS)" in content
    assert "CEVAP ANAHTARI" in content
    assert "[Sayfa " in content


def test_export_study_pdf(multi_page_biology_pdf, tmp_path):
    """Verify exporting study pack to a styled multi-page PDF document."""
    pack = generate_study_pack(multi_page_biology_pdf, question_count=6, use_llm=False)
    out_pdf = tmp_path / "calisma_paketi.pdf"

    result_path = export_study_pdf(pack, out_pdf)
    assert Path(result_path).is_file()

    # Verify PyMuPDF can open and read text from the generated PDF
    doc = fitz.open(result_path)
    try:
        assert doc.page_count >= 1
        full_text = "".join(doc[i].get_text() for i in range(doc.page_count)).replace("\xa0", " ")
        assert len(full_text) > 100
        assert "Öğrenci Çalışma Paketi" in full_text or "Ogrenci Calisma Paketi" in full_text
        assert "Sayfa 1" in full_text
    finally:
        doc.close()


# ── LLM Integration & Mocking ──────────────────────────────────────────────

def test_mock_llm_success(multi_page_biology_pdf):
    """Test LocalLLM integration when LLM returns valid structured JSON."""
    mock_llm = MagicMock()
    mock_llm.available = True
    mock_llm.runtime_available = True

    sample_response = json.dumps({
        "key_points": [
            {"text": "Mitoz bölünme vücut hücrelerinde gerçekleşir.", "page": 2}
        ],
        "questions": [
            {
                "question": "Fotosentez nerede gerçekleşir?",
                "type": "multiple_choice",
                "options": ["A) Kloroplast", "B) Ribozom", "C) Çekirdek", "D) Lizozom"],
                "answer": "A) Kloroplast",
                "page": 3,
                "explanation": "Kloroplast fotosentez organelidir."
            }
        ],
        "fill_in_blanks": [
            {
                "blank_sentence": "Hücrenin enerji santrali _______ organelidir.",
                "answer": "mitokondri",
                "hint": "M... (11 harf)",
                "page": 1
            }
        ],
        "flashcards": [
            {
                "front": "Ribozom nedir?",
                "back": "Protein sentezinden sorumlu zarsız organeldir.",
                "page": 1
            }
        ],
    })
    mock_llm.generate.return_value = sample_response

    pack = generate_study_pack(multi_page_biology_pdf, question_count=4, llm=mock_llm, use_llm=True)
    assert pack.metadata.get("used_llm") is True
    assert any("Mitoz bölünme" in pt.text for pt in pack.key_points)
    assert any("Fotosentez nerede" in q.question for q in pack.questions)
    assert any("enerji santrali" in fb.blank_sentence for fb in pack.fill_in_blanks)


def test_mock_llm_failure_graceful_fallback(multi_page_biology_pdf):
    """Test that when LocalLLM raises an error or outputs garbage, heuristics gracefully take over."""
    mock_llm = MagicMock()
    mock_llm.available = True
    mock_llm.runtime_available = True
    # LLM fails with an exception
    mock_llm.generate.side_effect = RuntimeError("GPU out of memory")

    pack = generate_study_pack(multi_page_biology_pdf, question_count=5, llm=mock_llm, use_llm=True)
    # Must not crash; fallback to heuristics
    assert isinstance(pack, StudyPack)
    assert len(pack.key_points) > 0
    assert len(pack.questions) > 0
    assert len(pack.flashcards) > 0


# ── Edge Cases: Cancellation, Progress, and Empty Documents ────────────────

def test_cancellation(multi_page_biology_pdf):
    """Test that cancelling raises CancelledError."""
    with pytest.raises(CancelledError):
        generate_study_pack(multi_page_biology_pdf, cancel=lambda: True)


def test_progress_reporting(multi_page_biology_pdf):
    """Test that progress callback receives progress events."""
    events = []

    def on_progress(cur, total, msg=""):
        events.append((cur, total, msg))

    generate_study_pack(multi_page_biology_pdf, progress=on_progress, use_llm=False)
    assert len(events) >= 3
    assert any(ev[0] == 100 for ev in events)


def test_empty_pdf(tmp_path):
    """Test that empty or blank PDF degrades gracefully without uncaught exceptions."""
    empty_pdf = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)  # blank page
    doc.save(str(empty_pdf))
    doc.close()

    pack = generate_study_pack(empty_pdf, use_llm=False)
    assert isinstance(pack, StudyPack)
    assert pack.key_points == []
    assert pack.questions == []
    assert pack.fill_in_blanks == []
    assert pack.flashcards == []
