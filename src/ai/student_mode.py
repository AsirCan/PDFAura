"""Faz 10 / Section 9: Öğrenci Modu (Student Study Pack Generator).

Creates comprehensive, curriculum-aligned study packs from PDF documents:
- Key points & exam notes (Önemli Noktalar / Sınav Notları) with source page grounding.
- Multiple-choice and open-ended practice questions (Test ve Çalışma Soruları) with page references.
- Realistic cloze deletion / fill-in-the-blank exercises (Boşluk Doldurma Alıştırmaları) with hints.
- Concept flashcards (Bilgi Kartları: Ön/Arka) with source pages.
- Graceful extractive / rule-based heuristics fallback when local LLM is absent.
- Optional prompt-based enhancement when LocalLLM is available.
- Export helpers to UTF-8 TXT and formatted PDF via PyMuPDF with full Turkish character support.
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from src.ai.document_loader import (
    DocumentChunk,
    LoadedDocument,
    PageText,
    check_cancelled,
    load_document,
    report_progress,
)
from src.ai.local_llm import LocalLLM
from src.core.task_manager import CancelledError

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)

ProgressCallback = Callable[..., None]
CancelCheck = Callable[[], bool] | None

# ── Character & Normalization Utilities ────────────────────────────────────

_ASCII_TRANSLATION = str.maketrans({
    "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ı": "i", "İ": "I",
    "ö": "o", "Ö": "O", "ş": "s", "Ş": "S", "ü": "u", "Ü": "U",
})


def turkish_lower(text: str) -> str:
    """Lowercase text with correct Turkish I/ı and İ/i handling."""
    if not text:
        return ""
    return str(text).replace("İ", "i").replace("I", "ı").lower()


def tokenize(text: str) -> list[str]:
    """Extract lowercased alphanumeric word tokens."""
    lowered = turkish_lower(text)
    return re.findall(r"[a-z0-9ğüşıöç]+", lowered)


# Stopwords for Turkish and English
STOPWORDS: set[str] = {
    # Turkish
    "acaba", "altı", "ama", "ancak", "arada", "artık", "asla", "aslında",
    "ayrıca", "az", "bana", "bazen", "bazı", "bazıları", "belki", "ben",
    "benden", "beni", "benim", "beri", "beş", "bile", "bin", "bir", "biri",
    "birkaç", "birkez", "birşey", "birşeyi", "biz", "bizden", "bize", "bizi",
    "bizim", "böyle", "böylece", "bu", "buna", "bunda", "bundan", "bunlar",
    "bunları", "bunların", "bunu", "bunun", "burada", "bütün", "çoğu", "çoğuna",
    "çoğunu", "çok", "çünkü", "da", "daha", "dahi", "de", "defa", "değil",
    "demek", "diğer", "diğeri", "diğerleri", "diye", "dokuz", "dolayı", "dört",
    "edecek", "eden", "ederek", "edilecek", "ediliyor", "edilmesi", "ediyor",
    "eğer", "elli", "en", "etmesi", "etti", "ettiği", "ettiğini", "fakat",
    "falan", "filan", "gene", "gibi", "göre", "halen", "hangi", "hangisi",
    "hani", "hatta", "hem", "henüz", "hep", "hepsi", "hepsine", "hepsini",
    "her", "herhangi", "herkes", "herkese", "herkesi", "herkesin", "hiç",
    "hiçbir", "hiçbiri", "hakkında", "için", "ilk", "ile", "ilgili", "ise",
    "işte", "itibaren", "itibariyle", "kadar", "karşın", "katrilyon", "kendi",
    "kendine", "kendini", "kendisi", "kendisine", "kendisini", "kez", "ki",
    "kim", "kime", "kimi", "kimin", "kimisi", "kimse", "kırk", "madem", "mı",
    "mi", "milyar", "milyon", "mu", "mü", "nasıl", "ne", "neden", "nedenle",
    "nerde", "nerede", "nereye", "netekim", "neye", "neyi", "neyse", "niçin",
    "nin", "nın", "niye", "nun", "nün", "o", "öbür", "öbürü", "olacak", "olan",
    "olarak", "oldu", "olduğu", "olduğunu", "oldukça", "olduklarını", "olmadığı",
    "olmak", "olması", "olmayan", "olmaz", "olsa", "olsun", "olup", "olur",
    "olursa", "oluyor", "on", "ona", "ondan", "onlar", "onlara", "onlardan",
    "onların", "onlarca", "onları", "onu", "onun", "orada", "öte", "ötürü",
    "öyle", "oysa", "oysaki", "pek", "rağmen", "sadece", "sanki", "sekiz",
    "seksen", "sen", "senden", "sana", "seni", "senin", "siz", "sizden",
    "size", "sizi", "sizin", "sonra", "şayet", "şekilde", "şey", "şeyden",
    "şeye", "şeyi", "şeyler", "şimdi", "şöyle", "şu", "şuna", "şunda", "şundan",
    "şunlar", "şunları", "şunu", "şunun", "tabi", "tamam", "tarafından", "trilyon",
    "tüm", "tümü", "üç", "üzerine", "üzerinde", "üzere", "var", "vardı", "ve",
    "veya", "veyahut", "ya", "yaşında", "yahut", "yalnız", "yani", "yapacak",
    "yapılan", "yapılması", "yapıyor", "yedi", "yerine", "yetmiş", "yine",
    "yirmi", "yok", "yoksa", "yüz", "zaten", "zaman",
    # English
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from", "further", "had",
    "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "isn't", "it", "its", "itself", "me",
    "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once",
    "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "with", "would", "you",
    "your", "yours", "yourself", "yourselves",
}

# Educational concept markers that indicate key learning objectives
_EXAM_INDICATORS_TR = (
    "tanımlanır", "adı verilir", "denir", "demektir", "anlamına gelir",
    "sürecidir", "birimidir", "organelidir", "özelliği", "kuralı", "prensibi",
    "kanunu", "yasası", "temel", "esas", "önemlidir", "önem taşır", "sonucunda",
    "sayesinde", "amaçlanır", "sağlar", "oluşur", "ayrılır", "farkı", "örneğin",
    "özetle", "dikkat", "gerekir", "kapsamında", "göre", "formülü",
)

_EXAM_INDICATORS_EN = (
    "defined as", "refers to", "called", "known as", "is a process", "crucial",
    "fundamental", "essential", "important", "principle", "consists of",
    "results in", "therefore", "function of", "characterized by", "difference",
    "formula", "law", "rule", "example",
)


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, honoring Turkish and academic abbreviations."""
    normalized = unicodedata.normalize("NFC", str(text or "")).strip()
    if not normalized:
        return []

    abbrevs = [
        (r"\bDr\.", "Dr__DOT__"),
        (r"\bProf\.", "Prof__DOT__"),
        (r"\bDoç\.", "Doç__DOT__"),
        (r"\bAv\.", "Av__DOT__"),
        (r"\bvb\.", "vb__DOT__"),
        (r"\bvs\.", "vs__DOT__"),
        (r"\bvd\.", "vd__DOT__"),
        (r"\bsf\.", "sf__DOT__"),
        (r"\bs\.", "s__DOT__"),
        (r"\bm\.", "m__DOT__"),
        (r"\bNo\.", "No__DOT__"),
        (r"\bbkz\.", "bkz__DOT__"),
        (r"\bMadde\s+(\d+)\.", r"Madde \1__DOT__"),
        (r"\b(\d+)\.", r"\1__DOT__"),
        (r"\bi\.e\.", "i__DOT__e__DOT__"),
        (r"\be\.g\.", "e__DOT__g__DOT__"),
        (r"\betc\.", "etc__DOT__"),
        (r"\bvs\.", "vs__DOT__"),
        (r"\bal\.", "al__DOT__"),
    ]
    protected = normalized
    for pattern, repl in abbrevs:
        protected = re.sub(pattern, repl, protected, flags=re.IGNORECASE)

    raw_sentences = re.split(r"(?<=[.!?…])\s+|\n{2,}|\r\n{2,}", protected)
    results = []
    for s in raw_sentences:
        restored = s.replace("__DOT__", ".")
        clean = re.sub(r"\s+", " ", restored).strip()
        clean = re.sub(r"^[-*•–—\d.)]+\s*", "", clean).strip()
        if len(clean) >= 15 and len(clean.split()) >= 3:
            results.append(clean)
    return results


def _find_turkish_font() -> str:
    """Locate a system TrueType font with full Turkish Unicode glyphs."""
    windows = os.environ.get("WINDIR") or os.environ.get("SystemRoot") or r"C:\Windows"
    candidates = [
        os.path.join(windows, "Fonts", name)
        for name in ("arial.ttf", "segoeui.ttf", "calibri.ttf", "tahoma.ttf", "verdana.ttf")
    ]
    candidates.extend([
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ])
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return ""


# ── Domain Data Classes (Subclasses of dict for 100% dictionary compatibility) ─

class KeyPoint(dict):
    """An essential study concept or exam note grounded on a source page."""

    def __init__(self, text: str, page: int = 1, pages: list[int] | None = None,
                 score: float = 0.0, **kwargs):
        pg = int(page) if page else 1
        pg_list = [int(p) for p in (pages or [pg])]
        super().__init__(
            text=str(text).strip(),
            point=str(text).strip(),
            page=pg,
            pages=pg_list,
            score=round(float(score), 4),
            **kwargs,
        )

    @property
    def text(self) -> str:
        return self["text"]

    @property
    def point(self) -> str:
        return self["point"]

    @property
    def page(self) -> int:
        return self["page"]

    @property
    def pages(self) -> list[int]:
        return self["pages"]

    def __str__(self) -> str:
        return f"{self['text']} [Sayfa {self['page']}]"


class Question(dict):
    """A practice question (multiple choice or open) with answer and page ref."""

    def __init__(self, question: str, type: str = "multiple_choice",
                 options: list[str] | None = None, answer: str = "",
                 page: int = 1, pages: list[int] | None = None,
                 explanation: str = "", **kwargs):
        pg = int(page) if page else 1
        pg_list = [int(p) for p in (pages or [pg])]
        super().__init__(
            question=str(question).strip(),
            type=str(type),
            options=list(options or []),
            answer=str(answer).strip(),
            correct_answer=str(answer).strip(),
            page=pg,
            pages=pg_list,
            explanation=str(explanation).strip(),
            **kwargs,
        )

    @property
    def question(self) -> str:
        return self["question"]

    @property
    def type(self) -> str:
        return self["type"]

    @property
    def options(self) -> list[str]:
        return self["options"]

    @property
    def answer(self) -> str:
        return self["answer"]

    @property
    def correct_answer(self) -> str:
        return self["correct_answer"]

    @property
    def page(self) -> int:
        return self["page"]

    @property
    def pages(self) -> list[int]:
        return self["pages"]

    @property
    def explanation(self) -> str:
        return self["explanation"]

    def __str__(self) -> str:
        lines = [f"{self['question']} [Sayfa {self['page']}]"]
        if self["type"] == "multiple_choice" and self["options"]:
            for opt in self["options"]:
                lines.append(f"  {opt}")
        lines.append(f"  Cevap: {self['answer']}")
        return "\n".join(lines)


class FillInBlank(dict):
    """A cloze deletion sentence with the target word replaced by a blank."""

    def __init__(self, blank_sentence: str, answer: str, sentence: str = "",
                 page: int = 1, pages: list[int] | None = None,
                 hint: str = "", **kwargs):
        pg = int(page) if page else 1
        pg_list = [int(p) for p in (pages or [pg])]
        clean_blank = str(blank_sentence).strip()
        super().__init__(
            blank_sentence=clean_blank,
            sentence=str(sentence or clean_blank).strip(),
            text=clean_blank,
            question=clean_blank,
            answer=str(answer).strip(),
            blank=str(answer).strip(),
            page=pg,
            pages=pg_list,
            hint=str(hint).strip(),
            **kwargs,
        )

    @property
    def blank_sentence(self) -> str:
        return self["blank_sentence"]

    @property
    def sentence(self) -> str:
        return self["sentence"]

    @property
    def answer(self) -> str:
        return self["answer"]

    @property
    def page(self) -> int:
        return self["page"]

    @property
    def pages(self) -> list[int]:
        return self["pages"]

    @property
    def hint(self) -> str:
        return self["hint"]

    def __str__(self) -> str:
        hint_str = f" ({self['hint']})" if self['hint'] else ""
        return f"{self['blank_sentence']}{hint_str} [Sayfa {self['page']}]"


class Flashcard(dict):
    """A study flashcard with front concept/prompt, back definition, and page ref."""

    def __init__(self, front: str, back: str, page: int = 1,
                 pages: list[int] | None = None, category: str = "", **kwargs):
        pg = int(page) if page else 1
        pg_list = [int(p) for p in (pages or [pg])]
        super().__init__(
            front=str(front).strip(),
            back=str(back).strip(),
            page=pg,
            pages=pg_list,
            category=str(category).strip(),
            **kwargs,
        )

    @property
    def front(self) -> str:
        return self["front"]

    @property
    def back(self) -> str:
        return self["back"]

    @property
    def page(self) -> int:
        return self["page"]

    @property
    def pages(self) -> list[int]:
        return self["pages"]

    @property
    def category(self) -> str:
        return self["category"]

    def __str__(self) -> str:
        return f"Ön: {self['front']} | Arka: {self['back']} [Sayfa {self['page']}]"


class StudyPack(dict):
    """A complete study pack holding exam notes, questions, cloze, and cards."""

    def __init__(self, key_points: list[KeyPoint] | None = None,
                 questions: list[Question] | None = None,
                 fill_in_blanks: list[FillInBlank] | None = None,
                 flashcards: list[Flashcard] | None = None,
                 title: str = "", summary: str = "", page_count: int = 0,
                 source_path: str = "", metadata: dict[str, Any] | None = None,
                 **kwargs):
        super().__init__(
            key_points=list(key_points or []),
            questions=list(questions or []),
            fill_in_blanks=list(fill_in_blanks or []),
            flashcards=list(flashcards or []),
            title=str(title).strip(),
            summary=str(summary).strip(),
            page_count=int(page_count),
            source_path=str(source_path),
            metadata=dict(metadata or {}),
            **kwargs,
        )

    @property
    def key_points(self) -> list[KeyPoint]:
        return self["key_points"]

    @property
    def questions(self) -> list[Question]:
        return self["questions"]

    @property
    def fill_in_blanks(self) -> list[FillInBlank]:
        return self["fill_in_blanks"]

    @property
    def flashcards(self) -> list[Flashcard]:
        return self["flashcards"]

    @property
    def title(self) -> str:
        return self["title"]

    @property
    def summary(self) -> str:
        return self["summary"]

    @property
    def page_count(self) -> int:
        return self["page_count"]

    @property
    def source_path(self) -> str:
        return self["source_path"]

    @property
    def metadata(self) -> dict[str, Any]:
        return self.get("metadata", {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self["title"],
            "summary": self["summary"],
            "page_count": self["page_count"],
            "source_path": self["source_path"],
            "key_points": [dict(p) for p in self["key_points"]],
            "questions": [dict(q) for q in self["questions"]],
            "fill_in_blanks": [dict(f) for f in self["fill_in_blanks"]],
            "flashcards": [dict(c) for c in self["flashcards"]],
            "metadata": dict(self.get("metadata", {})),
        }


# ── Extractive & Rule-based Heuristics ──────────────────────────────────────

@dataclass
class _SentenceItem:
    raw_text: str
    clean_text: str
    page_number: int
    tokens: list[str] = field(default_factory=list)
    score: float = 0.0


def _extract_sentence_pool(pages: Sequence[PageText]) -> list[_SentenceItem]:
    """Split pages into sentence items, calculate token sets and basic stats."""
    items: list[_SentenceItem] = []
    for page in pages:
        sentences = _split_into_sentences(page.text)
        for s in sentences:
            tokens = [t for t in tokenize(s) if t not in STOPWORDS and len(t) >= 3]
            items.append(_SentenceItem(
                raw_text=s,
                clean_text=s,
                page_number=page.page_number,
                tokens=tokens,
            ))
    return items


def _jaccard_similarity(tokens_a: Sequence[str], tokens_b: Sequence[str]) -> float:
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _score_sentences_for_key_points(items: list[_SentenceItem],
                                    word_frequencies: Counter[str]) -> None:
    """Score sentences based on information density, exam indicators, and definitions."""
    indicators = _EXAM_INDICATORS_TR + _EXAM_INDICATORS_EN
    for item in items:
        if not item.tokens:
            item.score = 0.0
            continue

        tf_sum = sum(word_frequencies.get(tok, 1) for tok in item.tokens)
        base_score = tf_sum / (len(item.tokens) + 2)

        lowered = turkish_lower(item.clean_text)
        indicator_count = sum(1 for ind in indicators if ind in lowered)
        if indicator_count > 0:
            base_score *= (1.0 + min(indicator_count * 0.35, 1.2))

        # Boost definition patterns: "X, Y'dir", "X ... olarak adlandırılır", "X: Y"
        if re.search(r"[:–—]\s+|,\s+[a-zçğıöşüA-ZÇĞİÖŞÜ0-9\s]{2,40}\s*(?:dir|dır|dur|dür|tanımlanır|denir)\b", item.clean_text):
            base_score *= 1.3

        # Length normalization: prefer concise sentences (40-200 chars)
        char_len = len(item.clean_text)
        if 45 <= char_len <= 190:
            base_score *= 1.15
        elif char_len > 280:
            base_score *= 0.8

        # Deprioritize structural titles (Bölüm 1, Chapter 2, etc.)
        if re.match(r"^(?:bölüm|ünite|kısım|chapter|section)\s+\d+", item.clean_text, re.IGNORECASE):
            base_score *= 0.15

        item.score = base_score


def _generate_extractive_key_points(items: list[_SentenceItem],
                                     max_points: int = 10) -> list[KeyPoint]:
    """Select the top distinct key points distributed across pages."""
    sorted_items = sorted(items, key=lambda it: it.score, reverse=True)
    selected: list[_SentenceItem] = []

    # First pass: ensure representation from each page
    pages_seen: set[int] = set()
    for it in sorted_items:
        if it.page_number not in pages_seen and it.score > 0.1:
            selected.append(it)
            pages_seen.add(it.page_number)
            if len(selected) >= max_points:
                break

    # Second pass: fill remaining with highest-scoring diverse sentences
    for it in sorted_items:
        if len(selected) >= max_points:
            break
        if it in selected:
            continue
        # Avoid redundancy with Jaccard check
        if any(_jaccard_similarity(it.tokens, s.tokens) > 0.5 for s in selected):
            continue
        selected.append(it)

    # Sort selected points by page number then occurrence
    selected.sort(key=lambda it: it.page_number)
    return [
        KeyPoint(text=it.clean_text, page=it.page_number, score=it.score)
        for it in selected
    ]


def _find_best_cloze_target(sentence: str, word_freq: Counter[str]) -> tuple[str, str] | None:
    """Identify the optimal concept or term to blank out in a sentence.

    Returns (target_word, hint) or None.
    """
    clean_words = re.findall(r"\b[A-Za-zçğıöşüÇĞİÖŞÜ0-9\-]{4,}\b", sentence)
    candidates = [
        w for w in clean_words
        if turkish_lower(w) not in STOPWORDS and not w.isdigit()
    ]
    if not candidates:
        return None

    # Priority 1: Check if sentence defines a term before colon or dash
    colon_match = re.match(r"^([A-ZÇĞİÖŞÜ][a-zçğıöşüA-ZÇĞİÖŞÜ\s]{2,30})\s*[:–—]", sentence)
    if colon_match:
        term = colon_match.group(1).strip()
        first_word = term.split()[0]
        if first_word in candidates:
            return first_word, f"İlk harf: '{first_word[0].upper()}', {len(first_word)} harf"

    # Priority 2: Capitalized technical terms / proper nouns not at sentence start
    for w in candidates[1:]:
        if w[0].isupper() and len(w) >= 4:
            return w, f"İlk harf: '{w[0].upper()}', {len(w)} harf"

    # Priority 3: Technical/concept words before "denir", "tanımlanır", "sürecidir"
    def_match = re.search(r"(\b[A-Za-zçğıöşüÇĞİÖŞÜ]{4,}\b)\s+(?:olarak\s+)?(?:tanımlanır|adlandırılır|denir)\b", sentence)
    if def_match:
        term = def_match.group(1)
        if term in candidates:
            return term, f"İlk harf: '{term[0].upper()}', {len(term)} harf"

    # Priority 4: Suffix matches for concepts (-izm, -loji, -tik, -tion, -ing)
    for w in candidates:
        low = turkish_lower(w)
        if any(low.endswith(sfx) for sfx in ("izm", "loji", "lojik", "tik", "leşme", "laşma", "tion", "ment", "ing")):
            return w, f"İlk harf: '{w[0].upper()}', {len(w)} harf"

    # Priority 5: Candidate with highest document frequency / weight
    candidates.sort(key=lambda w: (word_freq.get(turkish_lower(w), 1), len(w)), reverse=True)
    best = candidates[0]
    return best, f"İlk harf: '{best[0].upper()}', {len(best)} harf"


def _generate_extractive_fill_in_blanks(items: list[_SentenceItem],
                                        word_freq: Counter[str],
                                        max_count: int = 10) -> list[FillInBlank]:
    """Generate realistic cloze deletion exercises with hints."""
    results: list[FillInBlank] = []
    seen_answers: set[str] = set()

    for item in items:
        if len(results) >= max_count:
            break
        sentence = item.clean_text
        if len(sentence) < 30 or len(sentence) > 220:
            continue

        target_info = _find_best_cloze_target(sentence, word_freq)
        if not target_info:
            continue

        target_word, hint = target_info
        low_target = turkish_lower(target_word)
        if low_target in seen_answers:
            continue

        # Replace only the exact whole word with _______
        pattern = r"\b" + re.escape(target_word) + r"\b"
        blank_sentence, count = re.subn(pattern, "_______", sentence, count=1)
        if count == 0:
            continue

        seen_answers.add(low_target)
        results.append(FillInBlank(
            blank_sentence=blank_sentence,
            answer=target_word,
            sentence=sentence,
            page=item.page_number,
            hint=hint,
        ))

    return results


def _generate_extractive_flashcards(items: list[_SentenceItem],
                                    max_count: int = 10) -> list[Flashcard]:
    """Generate front/back concept flashcards from definition patterns and sentences."""
    cards: list[Flashcard] = []
    seen_fronts: set[str] = set()

    # Pattern A: "Concept : Definition" or "Concept - Definition"
    colon_pattern = re.compile(r"^([A-ZÇĞİÖŞÜ][a-zçğıöşüA-ZÇĞİÖŞÜ0-9\s]{2,35})\s*[:–—]\s*(.{15,})$")

    # Pattern B: "X ... olarak adlandırılır / denir / tanımlanır"
    naming_pattern = re.compile(r"^(.*?)\s+(?:olarak\s+)?(?:adı verilir|olarak adlandırılır|olarak tanımlanır|denir)\b", re.IGNORECASE)

    # Pattern C: "Concept, explanation..."
    comma_pattern = re.compile(r"^([A-ZÇĞİÖŞÜ][a-zçğıöşüA-ZÇĞİÖŞÜ\s]{2,30}),\s*(.{20,})$")

    for item in items:
        if len(cards) >= max_count:
            break
        sentence = item.clean_text

        # Test Pattern A
        mA = colon_pattern.match(sentence)
        if mA:
            front = mA.group(1).strip()
            back = mA.group(2).strip()
            low_f = turkish_lower(front)
            if any(low_f.startswith(pfx) for pfx in ("bölüm", "ünite", "kısım", "chapter", "section", "sayfa", "page")):
                continue
            if low_f not in seen_fronts and len(back) >= 15:
                seen_fronts.add(low_f)
                cards.append(Flashcard(front=front, back=back, page=item.page_number, category="Tanım"))
                continue

        # Test Pattern B
        mB = naming_pattern.match(sentence)
        if mB:
            clause = mB.group(1).strip()
            words = clause.split()
            if words:
                front = f"Tanım: {words[0]}..." if len(words) <= 2 else f"{' '.join(words[:4])}... nedir?"
                back = sentence
                low_f = turkish_lower(front)
                if any(low_f.startswith(pfx) for pfx in ("bölüm", "ünite", "kısım", "chapter", "section", "sayfa", "page")):
                    continue
                if low_f not in seen_fronts:
                    seen_fronts.add(low_f)
                    cards.append(Flashcard(front=front, back=back, page=item.page_number, category="Kavram"))
                    continue

        # Test Pattern C
        mC = comma_pattern.match(sentence)
        if mC:
            front = mC.group(1).strip()
            back = mC.group(2).strip()
            low_f = turkish_lower(front)
            if any(low_f.startswith(pfx) for pfx in ("bölüm", "ünite", "kısım", "chapter", "section", "sayfa", "page")):
                continue
            if low_f not in seen_fronts and len(front.split()) <= 4:
                seen_fronts.add(low_f)
                cards.append(Flashcard(front=front, back=back, page=item.page_number, category="Özellik"))
                continue

    # If we need more cards, derive from high-scoring sentences
    for item in items:
        if len(cards) >= max_count:
            break
        sentence = item.clean_text
        words = sentence.split()
        if len(words) >= 5:
            # Concept candidate from head of sentence
            lead_concept = " ".join(words[:2]).rstrip(",.:;")
            low_lead = turkish_lower(lead_concept)
            if low_lead not in seen_fronts and len(lead_concept) >= 4:
                seen_fronts.add(low_lead)
                cards.append(Flashcard(
                    front=f"{lead_concept} hakkında bilgi",
                    back=sentence,
                    page=item.page_number,
                    category="Önemli Bilgi",
                ))

    return cards


def _generate_extractive_questions(items: list[_SentenceItem],
                                   cloze_list: list[FillInBlank],
                                   word_freq: Counter[str],
                                   question_count: int = 10) -> list[Question]:
    """Generate balanced multiple-choice and open-ended study questions with distractors."""
    questions: list[Question] = []
    distractor_pool: list[str] = [
        w for w, count in word_freq.most_common(120)
        if w not in STOPWORDS and len(w) >= 4 and not w.isdigit()
    ]
    # Default fallbacks when corpus has few words
    default_distractors = ["Glikoz", "Enzim", "Fotosentez", "Mitokondri", "Ribozom", "Çekirdek", "Sitoplazma", "DNA"]

    # 1. Multiple-choice questions built on cloze sentences or definitions
    for cloze in cloze_list:
        if len(questions) >= question_count:
            break
        correct = cloze.answer
        correct_low = turkish_lower(correct)

        # Pick 3 plausible distractors
        available_distractors = [
            w for w in distractor_pool
            if w != correct_low and abs(len(w) - len(correct)) <= 6
        ]
        if len(available_distractors) < 3:
            available_distractors.extend([
                d for d in default_distractors
                if turkish_lower(d) != correct_low
            ])

        # Sample 3 distractors
        rng = random.Random(hash(correct) + cloze.page)
        chosen_distractors = rng.sample(available_distractors, min(3, len(available_distractors)))
        while len(chosen_distractors) < 3:
            chosen_distractors.append(f"Seçenek {len(chosen_distractors) + 1}")

        # Capitalize consistently
        options_raw = [correct] + [
            d.capitalize() if correct[0].isupper() else d.lower()
            for d in chosen_distractors
        ]
        rng.shuffle(options_raw)

        labels = ["A", "B", "C", "D"]
        formatted_options = [f"{lbl}) {opt}" for lbl, opt in zip(labels, options_raw)]

        correct_label = "A"
        for lbl, opt in zip(labels, options_raw):
            if opt.strip() == correct.strip():
                correct_label = lbl
                break

        full_answer = f"{correct_label}) {correct}"
        stem = f"Aşağıdaki cümlede boş bırakılan yere hangisi gelmelidir?\n\"{cloze.blank_sentence}\""

        questions.append(Question(
            question=stem,
            type="multiple_choice",
            options=formatted_options,
            answer=full_answer,
            page=cloze.page,
            explanation=f"Kaynak: {cloze.sentence}",
        ))

    # 2. Open-ended concept questions for remaining items
    for item in items:
        if len(questions) >= question_count:
            break
        sentence = item.clean_text
        words = sentence.split()
        if len(words) < 5:
            continue

        subject = " ".join(words[:2]).rstrip(",.:;")
        stem = f"Sayfa {item.page_number}'deki bilgilere göre; \"{subject}\" konusunu ve önemini açıklayınız."

        questions.append(Question(
            question=stem,
            type="open",
            options=[],
            answer=sentence,
            page=item.page_number,
            explanation="Metindeki ilgili açıklamaya başvurunuz.",
        ))

    return questions[:question_count]


# ── LLM Prompting & Enhancement ─────────────────────────────────────────────

def _build_llm_prompt(pages: Sequence[PageText], question_count: int,
                      include_flashcards: bool, include_fill_blanks: bool) -> str:
    """Construct structured instruction prompt for LocalLLM."""
    page_blocks = []
    for p in pages:
        page_blocks.append(f"=== SAYFA {p.page_number} ===\n{p.text[:1800]}")
    document_content = "\n\n".join(page_blocks)

    schema = {
        "key_points": [{"text": "Önemli sınav notu veya temel kavram", "page": 1}],
        "questions": [
            {
                "question": "Soru metni?",
                "type": "multiple_choice",
                "options": ["A) Şık 1", "B) Şık 2", "C) Şık 3", "D) Şık 4"],
                "answer": "A) Şık 1",
                "page": 1,
                "explanation": "Açıklama"
            }
        ],
        "fill_in_blanks": [{"blank_sentence": "Cümle _______ şeklinde boşluk içerir.", "answer": "kelime", "hint": "K... (6 harf)", "page": 1}] if include_fill_blanks else [],
        "flashcards": [{"front": "Kavram adı", "back": "Açıklaması veya tanımı", "page": 1}] if include_flashcards else [],
    }

    return (
        "Sen uzman bir öğretmen ve eğitim materyali hazırlayıcısısın. "
        "Aşağıdaki sayfa bazlı ders notlarını incele ve öğrenci için kapsamlı bir çalışma paketi oluştur.\n"
        f"Hedef soru sayısı: {question_count}.\n"
        "Her soruda, önemli noktada, boşluk doldurmada ve bilgi kartında 'page' alanında doğru sayfa numarasını belirt.\n"
        "Yanıtını SADECE ve kesinlikle aşağıdaki geçerli JSON şemasına uygun olarak üret:\n"
        f"```json\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n```\n\n"
        f"DERS METNİ:\n{document_content}\n"
    )


def _parse_llm_json(raw_text: str) -> dict[str, Any] | None:
    """Safely extract and parse JSON object from LLM response text."""
    if not raw_text:
        return None

    cleaned = raw_text.strip()
    # Strip markdown code fences if present
    code_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if code_match:
        cleaned = code_match.group(1).strip()

    # Search for outermost JSON object brackets
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return None


def _prompt_llm_study_pack(llm: LocalLLM, pages: Sequence[PageText],
                           question_count: int, include_flashcards: bool,
                           include_fill_blanks: bool,
                           cancel: CancelCheck = None) -> tuple[list[KeyPoint], list[Question], list[FillInBlank], list[Flashcard]] | None:
    """Prompt LocalLLM and parse structured items, or None on failure."""
    prompt = _build_llm_prompt(pages, question_count, include_flashcards, include_fill_blanks)
    try:
        check_cancelled(cancel)
        output = llm.generate(prompt, max_tokens=1500, temperature=0.2, cancel=cancel)
        if not output:
            return None

        parsed = _parse_llm_json(output)
        if not isinstance(parsed, dict):
            return None

        key_points = [
            KeyPoint(text=item.get("text", ""), page=item.get("page", 1))
            for item in parsed.get("key_points", [])
            if item.get("text")
        ]
        questions = [
            Question(
                question=item.get("question", ""),
                type=item.get("type", "multiple_choice"),
                options=item.get("options", []),
                answer=item.get("answer", ""),
                page=item.get("page", 1),
                explanation=item.get("explanation", ""),
            )
            for item in parsed.get("questions", [])
            if item.get("question")
        ]
        fill_in_blanks = [
            FillInBlank(
                blank_sentence=item.get("blank_sentence", ""),
                answer=item.get("answer", ""),
                page=item.get("page", 1),
                hint=item.get("hint", ""),
            )
            for item in parsed.get("fill_in_blanks", [])
            if item.get("blank_sentence")
        ] if include_fill_blanks else []

        flashcards = [
            Flashcard(
                front=item.get("front", ""),
                back=item.get("back", ""),
                page=item.get("page", 1),
            )
            for item in parsed.get("flashcards", [])
            if item.get("front") and item.get("back")
        ] if include_flashcards else []

        return key_points, questions, fill_in_blanks, flashcards
    except CancelledError:
        raise
    except Exception as exc:
        logger.warning("LocalLLM student pack generation failed, falling back to heuristics: %s", exc)
        return None


# ── Top-Level Generation Functions ──────────────────────────────────────────

def generate_study_pack(pdf_path: str | os.PathLike | LoadedDocument,
                        question_count: int = 10,
                        include_flashcards: bool = True,
                        include_fill_blanks: bool = True,
                        progress: ProgressCallback | None = None,
                        cancel: CancelCheck = None,
                        *,
                        use_llm: bool = True,
                        llm: LocalLLM | None = None,
                        title: str | None = None) -> StudyPack:
    """Generate a comprehensive study pack from a PDF document.

    Args:
        pdf_path: Path to the PDF file, or an already LoadedDocument instance.
        question_count: Target number of practice questions (default 10).
        include_flashcards: Whether to generate front/back concept flashcards.
        include_fill_blanks: Whether to generate cloze deletion exercises.
        progress: Progress update callback accepting (current, total, message).
        cancel: Cancellation check callable or context.
        use_llm: Whether to attempt LocalLLM generation if available.
        llm: Optional explicit LocalLLM instance.
        title: Optional custom title for the study pack.

    Returns:
        StudyPack dict carrying key_points, questions, fill_in_blanks, flashcards.
    """
    check_cancelled(cancel)
    report_progress(progress, 5, 100, "Belge yukleniyor...")

    # 1. Load document pages
    if isinstance(pdf_path, LoadedDocument):
        doc = pdf_path
        source_name = Path(doc.path).name if doc.path else "Belge"
    else:
        doc = load_document(pdf_path, progress=progress, cancel=cancel)
        source_name = Path(pdf_path).name

    check_cancelled(cancel)
    report_progress(progress, 25, 100, "Icerik analiz ediliyor...")

    pages = doc.pages
    if not pages or all(not p.text.strip() for p in pages):
        return StudyPack(
            key_points=[],
            questions=[],
            fill_in_blanks=[],
            flashcards=[],
            title=title or f"{source_name} • Çalışma Paketi",
            summary="Belgede analiz edilecek metin bulunamadı.",
            page_count=len(pages),
            source_path=str(doc.path) if hasattr(doc, "path") else str(pdf_path),
        )

    # 2. Extract sentence candidates and word statistics
    sentence_items = _extract_sentence_pool(pages)
    word_freq: Counter[str] = Counter()
    for item in sentence_items:
        word_freq.update(item.tokens)

    _score_sentences_for_key_points(sentence_items, word_freq)
    check_cancelled(cancel)

    # 3. Attempt LLM generation if available
    llm_result = None
    if use_llm:
        model = llm if llm is not None else LocalLLM()
        if model.available and model.runtime_available:
            report_progress(progress, 40, 100, "Calisma paketi uretiliyor...")
            llm_result = _prompt_llm_study_pack(
                model, pages, question_count=question_count,
                include_flashcards=include_flashcards,
                include_fill_blanks=include_fill_blanks,
                cancel=cancel,
            )

    check_cancelled(cancel)
    report_progress(progress, 65, 100, "Onemli noktalar ve alistirmalar derleniyor...")

    # 4. Extractive heuristics fallback / top-up
    extractive_points = _generate_extractive_key_points(sentence_items, max_points=max(5, question_count))
    extractive_blanks = _generate_extractive_fill_in_blanks(sentence_items, word_freq, max_count=question_count) if include_fill_blanks else []
    extractive_cards = _generate_extractive_flashcards(sentence_items, max_count=question_count) if include_flashcards else []
    extractive_questions = _generate_extractive_questions(sentence_items, extractive_blanks, word_freq, question_count=question_count)

    # 5. Merge LLM results or use heuristics
    if llm_result:
        k_pts, qs, blanks, cards = llm_result
        final_points = k_pts if k_pts else extractive_points
        final_questions = qs if qs else extractive_questions
        # If LLM returned fewer questions than requested, top up
        if len(final_questions) < question_count:
            existing_stems = {q.question for q in final_questions}
            for eq in extractive_questions:
                if len(final_questions) >= question_count:
                    break
                if eq.question not in existing_stems:
                    final_questions.append(eq)

        final_blanks = blanks if (include_fill_blanks and blanks) else extractive_blanks
        final_cards = cards if (include_flashcards and cards) else extractive_cards
    else:
        final_points = extractive_points
        final_questions = extractive_questions
        final_blanks = extractive_blanks
        final_cards = extractive_cards

    check_cancelled(cancel)
    report_progress(progress, 95, 100, "Calisma paketi tamamlaniyor...")

    doc_title = title or f"{source_name} • Öğrenci Çalışma Paketi"
    pack = StudyPack(
        key_points=final_points,
        questions=final_questions,
        fill_in_blanks=final_blanks,
        flashcards=final_cards,
        title=doc_title,
        summary=f"{len(pages)} sayfalık belgeden {len(final_points)} önemli nokta, {len(final_questions)} soru çıkarıldı.",
        page_count=len(pages),
        source_path=str(doc.path) if hasattr(doc, "path") else str(pdf_path),
        metadata={"used_llm": bool(llm_result)},
    )

    report_progress(progress, 100, 100, "Calisma paketi hazirlandi.")
    return pack


def generate_questions(pdf_path: str | os.PathLike | LoadedDocument,
                       question_count: int = 10,
                       progress: ProgressCallback | None = None,
                       cancel: CancelCheck = None,
                       **kwargs) -> list[Question]:
    """Convenience helper for 'Bu PDF'ten X soru hazırla' action."""
    pack = generate_study_pack(
        pdf_path, question_count=question_count,
        include_flashcards=False, include_fill_blanks=False,
        progress=progress, cancel=cancel, **kwargs
    )
    return pack.questions


def generate_fill_in_blanks(pdf_path: str | os.PathLike | LoadedDocument,
                            count: int = 10,
                            progress: ProgressCallback | None = None,
                            cancel: CancelCheck = None,
                            **kwargs) -> list[FillInBlank]:
    """Convenience helper for 'boşluk doldurma yap' action."""
    pack = generate_study_pack(
        pdf_path, question_count=count,
        include_flashcards=False, include_fill_blanks=True,
        progress=progress, cancel=cancel, **kwargs
    )
    return pack.fill_in_blanks


def generate_flashcards(pdf_path: str | os.PathLike | LoadedDocument,
                        count: int = 10,
                        progress: ProgressCallback | None = None,
                        cancel: CancelCheck = None,
                        **kwargs) -> list[Flashcard]:
    """Convenience helper for 'flashcard üret' action."""
    pack = generate_study_pack(
        pdf_path, question_count=count,
        include_flashcards=True, include_fill_blanks=False,
        progress=progress, cancel=cancel, **kwargs
    )
    return pack.flashcards


def generate_exam_notes(pdf_path: str | os.PathLike | LoadedDocument,
                        count: int = 10,
                        progress: ProgressCallback | None = None,
                        cancel: CancelCheck = None,
                        **kwargs) -> list[KeyPoint]:
    """Convenience helper for 'sınav notu çıkar' action."""
    pack = generate_study_pack(
        pdf_path, question_count=count,
        include_flashcards=False, include_fill_blanks=False,
        progress=progress, cancel=cancel, **kwargs
    )
    return pack.key_points


# ── Export Helpers: TXT and Formatted PDF ───────────────────────────────────

def export_study_txt(pack: dict[str, Any] | StudyPack, path: str | os.PathLike) -> str:
    if "\x00" in str(path):
        raise ValueError("Path contains invalid null character")
    """Export a study pack to a clean UTF-8 text worksheet."""
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    title = pack.get("title") or "Öğrenci Çalışma Paketi"
    source = pack.get("source_path") or ""
    page_count = pack.get("page_count", 0)

    lines: list[str] = [
        "=" * 80,
        "PDFAURA • ÖĞRENCİ ÇALIŞMA PAKETİ",
        f"{title.upper()}",
        "=" * 80,
    ]
    if source:
        lines.append(f"Kaynak Belge : {source}")
    if page_count:
        lines.append(f"Toplam Sayfa : {page_count}")
    lines.append("")

    # Section 1: Key Points
    key_points = pack.get("key_points") or []
    if key_points:
        lines.extend([
            "-" * 80,
            "1. ÖNEMLİ NOKTALAR VE SINAV ÖZETİ",
            "-" * 80,
        ])
        for idx, pt in enumerate(key_points, 1):
            text = pt.get("text", "")
            pg = pt.get("page", 1)
            lines.append(f"{idx}. [Sayfa {pg}] {text}")
        lines.append("")

    # Section 2: Questions
    questions = pack.get("questions") or []
    if questions:
        lines.extend([
            "-" * 80,
            "2. TEST VE ÇALIŞMA SORULARI",
            "-" * 80,
        ])
        for idx, q in enumerate(questions, 1):
            q_text = q.get("question", "")
            pg = q.get("page", 1)
            lines.append(f"Soru {idx} [Sayfa {pg}]:")
            lines.append(f"  {q_text}")
            opts = q.get("options") or []
            if opts:
                for opt in opts:
                    lines.append(f"    {opt}")
            lines.append("")

    # Section 3: Fill in the Blanks
    fill_blanks = pack.get("fill_in_blanks") or []
    if fill_blanks:
        lines.extend([
            "-" * 80,
            "3. BOŞLUK DOLDURMA ALIŞTIRMALARI",
            "-" * 80,
        ])
        for idx, fb in enumerate(fill_blanks, 1):
            b_sent = fb.get("blank_sentence", "")
            pg = fb.get("page", 1)
            hint = fb.get("hint", "")
            hint_str = f" ({hint})" if hint else ""
            lines.append(f"{idx}. [Sayfa {pg}] {b_sent}{hint_str}")
        lines.append("")

    # Section 4: Flashcards
    flashcards = pack.get("flashcards") or []
    if flashcards:
        lines.extend([
            "-" * 80,
            "4. BİLGİ KARTLARI (FLASHCARDS)",
            "-" * 80,
        ])
        for idx, card in enumerate(flashcards, 1):
            front = card.get("front", "")
            back = card.get("back", "")
            pg = card.get("page", 1)
            lines.append(f"[Kart {idx}] [Sayfa {pg}]")
            lines.append(f"  Ön  : {front}")
            lines.append(f"  Arka: {back}")
            lines.append("")

    # Section 5: Answer Key
    lines.extend([
        "=" * 80,
        "5. CEVAP ANAHTARI",
        "=" * 80,
    ])
    if questions:
        lines.append("[Test Soruları Cevapları]")
        for idx, q in enumerate(questions, 1):
            ans = q.get("answer", "")
            pg = q.get("page", 1)
            lines.append(f"  {idx}. {ans} (Sayfa {pg})")
        lines.append("")

    if fill_blanks:
        lines.append("[Boşluk Doldurma Cevapları]")
        for idx, fb in enumerate(fill_blanks, 1):
            ans = fb.get("answer", "")
            pg = fb.get("page", 1)
            lines.append(f"  {idx}. {ans} (Sayfa {pg})")
        lines.append("")

    lines.append("=" * 80)

    with open(target, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    return str(target)


class _StudyPdfWriter:
    """Formatted PDF layout engine with multi-page handling and Turkish glyph support."""

    PAGE_WIDTH = 595.32   # A4
    PAGE_HEIGHT = 841.92  # A4
    MARGIN = 45.0

    def __init__(self, doc, title: str = ""):
        self.doc = doc
        self.title = title
        self.font_path = _find_turkish_font()
        if self.font_path and fitz is not None:
            self.font_name = "f0"
            self._font = fitz.Font(fontfile=self.font_path)
            self._ascii = False
        else:
            self.font_name = "helv"
            self._font = None
            self._ascii = True

        self.current_page = None
        self.y = self.MARGIN
        self.page_number = 0
        self._new_page()

    def _new_page(self) -> None:
        self.page_number += 1
        self.current_page = self.doc.new_page(width=self.PAGE_WIDTH, height=self.PAGE_HEIGHT)
        if self.font_path:
            self.current_page.insert_font(fontname=self.font_name, fontfile=self.font_path,
                                         set_simple=False)

        header_text = f"PDFAura • Öğrenci Çalışma Paketi {f'— {self.title}' if self.title else ''}"
        if self._ascii:
            header_text = header_text.translate(_ASCII_TRANSLATION)
        self.current_page.insert_text(
            (self.MARGIN, self.MARGIN * 0.65),
            header_text,
            fontname=self.font_name,
            fontsize=8.5,
            color=(0.4, 0.4, 0.4),
        )
        self.current_page.draw_line(
            fitz.Point(self.MARGIN, self.MARGIN * 0.75),
            fitz.Point(self.PAGE_WIDTH - self.MARGIN, self.MARGIN * 0.75),
            color=(0.82, 0.82, 0.82),
            width=0.6,
        )

        self.y = self.MARGIN + 12.0

    def _measure(self, text: str, size: float) -> float:
        if self._font is not None:
            try:
                return float(self._font.text_length(text, fontsize=size))
            except Exception:
                pass
        return len(text) * size * 0.52

    def _wrap(self, text: str, max_width: float, size: float) -> list[str]:
        lines: list[str] = []
        for raw_line in str(text).splitlines() or [""]:
            words = raw_line.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                candidate = f"{current} {word}"
                if self._measure(candidate, size) <= max_width:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines

    def _ensure_space(self, height: float) -> None:
        if self.y + height > self.PAGE_HEIGHT - self.MARGIN:
            self._new_page()

    def add_line(self, text: str, *, size: float = 9.5,
                 color: tuple[float, float, float] = (0.12, 0.12, 0.12),
                 indent: float = 0.0, space_after: float = 3.0) -> None:
        if self._ascii:
            text = str(text).translate(_ASCII_TRANSLATION)

        width = self.PAGE_WIDTH - 2 * self.MARGIN - indent
        line_height = size * 1.35

        for wrapped in self._wrap(text, width, size):
            self._ensure_space(line_height)
            if wrapped:
                self.current_page.insert_text(
                    (self.MARGIN + indent, self.y + size),
                    wrapped,
                    fontname=self.font_name,
                    fontsize=size,
                    color=color,
                )
            self.y += line_height
        self.y += space_after

    def add_heading(self, text: str, *, level: int = 1) -> None:
        if level == 1:
            size = 14.0
            color = (0.10, 0.20, 0.50)
            space_before = 12.0
            space_after = 6.0
        elif level == 2:
            size = 11.5
            color = (0.15, 0.25, 0.45)
            space_before = 9.0
            space_after = 4.0
        else:
            size = 10.0
            color = (0.20, 0.30, 0.40)
            space_before = 6.0
            space_after = 3.0

        self._ensure_space(space_before + size * 1.5)
        self.y += space_before
        self.add_line(text, size=size, color=color, space_after=space_after)

    def add_bullet(self, text: str, *, indent: float = 12.0) -> None:
        bullet_char = "-" if self._ascii else "•"
        full_text = f"{bullet_char}  {text}"
        self.add_line(full_text, size=9.5, color=(0.15, 0.15, 0.15),
                      indent=indent, space_after=3.5)


def export_study_pdf(pack: dict[str, Any] | StudyPack,
                     path: str | os.PathLike,
                     title: str | None = None) -> str:
    if "\x00" in str(path):
        raise ValueError("Path contains invalid null character")
    """Export a study pack to a styled multi-page PDF document."""
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) kurulu değil; PDF kaydetme devre dışı.")

    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    doc_title = title or pack.get("title") or "Öğrenci Çalışma Paketi"
    pdf_doc = fitz.open()

    try:
        writer = _StudyPdfWriter(pdf_doc, title=doc_title)

        # Document Header
        writer.add_heading(doc_title, level=1)
        meta_info = f"Kaynak: {Path(pack.get('source_path', '')).name or 'Belge'} • Toplam {pack.get('page_count', 1)} Sayfa"
        writer.add_line(meta_info, size=9.0, color=(0.45, 0.45, 0.45), space_after=8.0)

        # 1. Key Points
        key_points = pack.get("key_points") or []
        if key_points:
            writer.add_heading("1. Önemli Noktalar & Sınav Notları", level=2)
            for idx, pt in enumerate(key_points, 1):
                text = pt.get("text", "")
                pg = pt.get("page", 1)
                writer.add_bullet(f"[Sayfa {pg}] {text}")

        # 2. Questions
        questions = pack.get("questions") or []
        if questions:
            writer.add_heading("2. Test ve Çalışma Soruları", level=2)
            for idx, q in enumerate(questions, 1):
                q_text = q.get("question", "")
                pg = q.get("page", 1)
                writer.add_line(f"Soru {idx} [Sayfa {pg}]:", size=10.0,
                                color=(0.10, 0.18, 0.42), indent=4.0, space_after=2.0)
                writer.add_line(f"{q_text}", size=9.5, indent=8.0, space_after=3.0)
                opts = q.get("options") or []
                if opts:
                    for opt in opts:
                        writer.add_line(f"  {opt}", size=9.0, color=(0.25, 0.25, 0.25),
                                        indent=12.0, space_after=1.5)
                writer.y += 3.0

        # 3. Fill in Blanks
        fill_blanks = pack.get("fill_in_blanks") or []
        if fill_blanks:
            writer.add_heading("3. Boşluk Doldurma Alıştırmaları", level=2)
            for idx, fb in enumerate(fill_blanks, 1):
                b_sent = fb.get("blank_sentence", "")
                pg = fb.get("page", 1)
                hint = fb.get("hint", "")
                hint_str = f" ({hint})" if hint else ""
                writer.add_bullet(f"[Sayfa {pg}] {b_sent}{hint_str}")

        # 4. Flashcards
        flashcards = pack.get("flashcards") or []
        if flashcards:
            writer.add_heading("4. Bilgi Kartları (Flashcards)", level=2)
            for idx, card in enumerate(flashcards, 1):
                front = card.get("front", "")
                back = card.get("back", "")
                pg = card.get("page", 1)
                writer.add_line(f"[Kart {idx}] [Sayfa {pg}] Ön: {front}", size=9.5,
                                color=(0.12, 0.25, 0.50), indent=6.0, space_after=2.0)
                writer.add_line(f"  ↳ Arka: {back}", size=9.0, color=(0.20, 0.20, 0.20),
                                indent=12.0, space_after=4.0)

        # 5. Answer Key
        if questions or fill_blanks:
            writer.add_heading("5. Cevap Anahtarı", level=2)
            if questions:
                writer.add_line("Test Soruları Cevapları:", size=9.5,
                                color=(0.15, 0.20, 0.35), indent=4.0)
                for idx, q in enumerate(questions, 1):
                    ans = q.get("answer", "")
                    pg = q.get("page", 1)
                    writer.add_line(f"  {idx}. {ans} [s. {pg}]", size=9.0,
                                    indent=10.0, space_after=1.5)

            if fill_blanks:
                writer.y += 3.0
                writer.add_line("Boşluk Doldurma Cevapları:", size=9.5,
                                color=(0.15, 0.20, 0.35), indent=4.0)
                for idx, fb in enumerate(fill_blanks, 1):
                    ans = fb.get("answer", "")
                    pg = fb.get("page", 1)
                    writer.add_line(f"  {idx}. {ans} [s. {pg}]", size=9.0,
                                    indent=10.0, space_after=1.5)

        # Add page numbering footer to all generated pages
        total_pages = pdf_doc.page_count
        for i in range(total_pages):
            page = pdf_doc[i]
            footer_text = f"Sayfa {i + 1} / {total_pages}"
            page.insert_text(
                (writer.PAGE_WIDTH / 2.0 - 25.0, writer.PAGE_HEIGHT - writer.MARGIN * 0.55),
                footer_text,
                fontname=writer.font_name,
                fontsize=8.0,
                color=(0.55, 0.55, 0.55),
            )

        pdf_doc.save(str(target), deflate=True, garbage=3)
    finally:
        pdf_doc.close()

    return str(target)
