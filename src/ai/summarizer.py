"""Faz 5: Akıllı Özet Modları (Smart PDF Summarization Engine).

Provides multi-mode PDF summarization with source page grounding:
- Modes: "kisa", "detayli", "ogrenci", "toplanti", "hukuki".
- Map-Reduce summarization for long documents.
- Graceful extractive fallback (term-frequency sentence scoring) when no
  local LLM is available, keeping page references on every point.
- Export to TXT and PDF (via PyMuPDF) with full Turkish character support.
"""
from __future__ import annotations

import math
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

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
    from src.core.config_manager import cfg
except Exception:
    cfg = None

try:
    import fitz
except ImportError:
    fitz = None

ProgressCallback = Callable[..., None]
CancelCheck = Callable[[], bool] | None

# Canonical summarization modes
MODES = ("kisa", "detayli", "ogrenci", "toplanti", "hukuki")

MODE_ALIASES: dict[str, str] = {
    "kısa": "kisa",
    "kisa": "kisa",
    "short": "kisa",
    "brief": "kisa",
    "detaylı": "detayli",
    "detayli": "detayli",
    "detailed": "detayli",
    "detail": "detayli",
    "öğrenci": "ogrenci",
    "ogrenci": "ogrenci",
    "student": "ogrenci",
    "study": "ogrenci",
    "toplantı": "toplanti",
    "toplanti": "toplanti",
    "meeting": "toplanti",
    "executive": "toplanti",
    "hukuki": "hukuki",
    "legal": "hukuki",
    "contract": "hukuki",
    "sozlesme": "hukuki",
    "sözleşme": "hukuki",
}

# Thresholds for map-reduce processing
LONG_DOC_PAGE_THRESHOLD = 3
LONG_DOC_CHAR_THRESHOLD = 3500

# Stopwords for Turkish and English
STOPWORDS: set[str] = {
    # Turkish stopwords
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
    # English stopwords
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
    "through", "to", "too", "under", "until", "up", "very", "was", "we", "were",
    "what", "when", "where", "which", "while", "who", "whom", "why", "with", "would",
    "you", "your", "yours", "yourself", "yourselves",
}

# Mode-specific keywords for extractive filtering & scoring
MODE_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "ogrenci": {
        "definitions": [
            "tanım", "tanımı", "tanımlanır", "nedir", "kavram", "kavramı",
            "demektir", "anlamına", "ilke", "ilkesi", "prensip", "kural", "kuralları",
            "formül", "esas", "terim", "teori", "model", "definition", "concept",
            "principle", "formula", "theory",
        ],
        "notes": [
            "önemli", "özellikle", "amaç", "amacı", "amacıyla", "yöntem", "yöntemi",
            "neden", "sonuç", "sonucu", "faktör", "özellik", "özellikleri",
            "temel", "kapsam", "etki", "analiz", "important", "method", "factor",
            "feature", "objective",
        ],
        "exam": [
            "sınav", "soru", "sorular", "dikkat", "özetle", "örnek", "örneğin",
            "not", "çalışma", "hatırlatma", "ipucu", "sonuç olarak", "exam", "question",
            "note", "example", "takeaway",
        ],
    },
    "toplanti": {
        "decisions": [
            "karar", "kararlaştırıldı", "karar verildi", "onaylandı", "kabul edildi",
            "mutabık", "mutabakat", "seçildi", "belirlendi", "uygun görüldü",
            "neticelendi", "tasdik", "decided", "approved", "agreed", "resolved",
        ],
        "actions": [
            "aksiyon", "görev", "sorumlu", "yapılacak", "tamamlanacak", "hazırlanacak",
            "termin", "teslim", "tarih", "tarihine kadar", "atanan", "sorumlusu",
            "takip", "yürütülecek", "action", "task", "deadline", "responsible",
            "deliverable", "follow-up",
        ],
        "agenda": [
            "gündem", "toplantı", "görüşüldü", "değerlendirildi", "katılımcı",
            "sonraki", "adım", "hedef", "plan", "planlandı", "strateji", "süreç",
            "meeting", "agenda", "discussion", "next steps", "timeline",
        ],
    },
    "hukuki": {
        "parties_scope": [
            "taraf", "taraflar", "sözleşme", "konu", "kapsam", "işbu", "tanımlar",
            "yürürlük", "başlangıç", "tarihinde", "akdedilmiştir", "anlaşma",
            "party", "parties", "agreement", "scope", "whereas", "entered into",
        ],
        "obligations": [
            "yükümlü", "yükümlülük", "taahhüt", "hak", "haklar", "borç", "borçlu",
            "ifası", "ödeme", "bedel", "teslimat", "şart", "koşul", "ifa", "vade",
            "obligation", "duty", "payment", "covenant", "warranty", "deliverable",
        ],
        "termination_risks": [
            "fesih", "feshi", "tazminat", "ceza", "cezai şart", "ihlal", "ihlalinde",
            "mücbir sebep", "yetkili mahkeme", "uyuşmazlık", "hukuk", "sorumluluk",
            "gizlilik", "zarar", "termination", "breach", "penalty", "liability",
            "indemnify", "dispute", "confidentiality",
        ],
    },
}

_ASCII_TRANSLATION = str.maketrans({
    "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ı": "i", "İ": "I",
    "ö": "o", "Ö": "O", "ş": "s", "Ş": "S", "ü": "u", "Ü": "U",
})


def turkish_lower(text: str) -> str:
    """Lowercase text with correct Turkish I/ı and İ/i handling."""
    if not text:
        return ""
    return str(text).replace("İ", "i").replace("I", "ı").lower()


def normalize_mode(mode: str) -> str:
    """Normalize input string to canonical mode name."""
    clean = turkish_lower(str(mode or "")).strip()
    return MODE_ALIASES.get(clean, "kisa")


def tokenize(text: str) -> list[str]:
    """Extract lowercased word tokens."""
    lowered = turkish_lower(text)
    return re.findall(r"[a-z0-9ğüşıöç]+", lowered)


@dataclass
class SummaryPoint:
    """A single summarized takeaway with its source page(s)."""

    text: str
    pages: list[int] = field(default_factory=list)
    section: str = ""
    score: float = 0.0

    def format_with_citation(self, language: str = "tr") -> str:
        tag_label = "Sayfa" if language.lower().startswith("tr") else "Page"
        if not self.pages:
            return self.text
        pages_str = ", ".join(str(p) for p in sorted(set(self.pages)))
        if f"[{tag_label}" in self.text:
            return self.text
        clean = self.text.strip()
        if not clean.endswith((".", "!", "?", "…", ":")):
            clean += "."
        return f"{clean} [{tag_label} {pages_str}]"


@dataclass
class SummaryResult:
    """Complete summarization output carrying structured points and metadata."""

    text: str
    mode: str
    language: str = "tr"
    points: list[SummaryPoint] = field(default_factory=list)
    sources: list[int] = field(default_factory=list)
    used_llm: bool = False
    document_path: str = ""
    page_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.text

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "mode": self.mode,
            "language": self.language,
            "sources": list(self.sources),
            "used_llm": self.used_llm,
            "document_path": self.document_path,
            "page_count": self.page_count,
            "points": [
                {
                    "text": p.text,
                    "pages": list(p.pages),
                    "section": p.section,
                    "score": round(p.score, 4),
                }
                for p in self.points
            ],
            "metadata": dict(self.metadata),
        }


# ── Sentence Candidate & Scoring ───────────────────────────────────────────

@dataclass
class _SentenceCandidate:
    raw_text: str
    clean_text: str
    page_number: int
    index_in_page: int
    tokens: list[str] = field(default_factory=list)
    score: float = 0.0


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, honoring Turkish abbreviations."""
    normalized = unicodedata.normalize("NFC", str(text or "")).strip()
    if not normalized:
        return []

    # Replace common abbreviations temporarily so periods don't trigger splits
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
        (r"\b(\d+)\.", r"\1__DOT__"),  # Decimal or list numbering
        (r"\bi\.e\.", "i__DOT__e__DOT__"),
        (r"\be\.g\.", "e__DOT__g__DOT__"),
        (r"\betc\.", "etc__DOT__"),
    ]
    protected = normalized
    for pattern, repl in abbrevs:
        protected = re.sub(pattern, repl, protected, flags=re.IGNORECASE)

    raw_sentences = re.split(r"(?<=[.!?…])\s+|\n{2,}|\r\n{2,}", protected)
    results = []
    for s in raw_sentences:
        restored = s.replace("__DOT__", ".")
        clean = re.sub(r"\s+", " ", restored).strip()
        # Clean off initial bullet characters or numbering
        clean = re.sub(r"^[-*•–—\d.)]+\s*", "", clean).strip()
        if len(clean) >= 15 and len(clean.split()) >= 3:
            results.append(clean)
    return results


def _extract_candidates(pages: Sequence[PageText]) -> list[_SentenceCandidate]:
    """Extract sentence candidates from pages with their page references."""
    candidates = []
    for page in pages:
        sentences = _split_into_sentences(page.text)
        for idx, sentence in enumerate(sentences):
            tokens = [t for t in tokenize(sentence) if t not in STOPWORDS]
            if tokens:
                candidates.append(_SentenceCandidate(
                    raw_text=sentence,
                    clean_text=sentence,
                    page_number=page.page_number,
                    index_in_page=idx,
                    tokens=tokens,
                ))
    return candidates


def _calculate_tf_scores(candidates: list[_SentenceCandidate]) -> None:
    """Calculate term-frequency sentence scores across all candidates."""
    if not candidates:
        return

    # Count global term frequency
    tf: Counter[str] = Counter()
    for candidate in candidates:
        tf.update(candidate.tokens)

    for candidate in candidates:
        token_count = len(candidate.tokens)
        if token_count == 0:
            candidate.score = 0.0
            continue

        raw_score = sum(math.log(1.0 + tf[t]) for t in candidate.tokens)
        # Length normalization to prevent bias towards unnaturally long sentences
        norm_score = raw_score / (math.pow(token_count, 0.65) + 1.0)

        # Positional boost: opening sentences of a page often state core topics
        if candidate.index_in_page == 0:
            norm_score *= 1.25
        elif candidate.index_in_page == 1:
            norm_score *= 1.15

        # Factual boost: sentences with numbers, percentages, currency, dates
        if re.search(r"\d+|%|TL|USD|EUR|\$", candidate.clean_text):
            norm_score *= 1.12

        candidate.score = norm_score


def _jaccard_similarity(tokens_a: Sequence[str], tokens_b: Sequence[str]) -> float:
    """Calculate token overlap Jaccard similarity."""
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _deduplicate_candidates(candidates: list[_SentenceCandidate],
                            threshold: float = 0.60) -> list[_SentenceCandidate]:
    """Remove redundant sentence candidates, keeping higher-scoring ones."""
    sorted_candidates = sorted(candidates, key=lambda c: -c.score)
    unique: list[_SentenceCandidate] = []
    for cand in sorted_candidates:
        if any(_jaccard_similarity(cand.tokens, u.tokens) >= threshold for u in unique):
            continue
        unique.append(cand)
    return unique


# ── Extractive Summarizer Implementation ───────────────────────────────────

def _summarize_extractive_kisa(candidates: list[_SentenceCandidate],
                              language: str,
                              page_count: int) -> tuple[str, list[SummaryPoint]]:
    """Generate concise executive summary (3-5 key points)."""
    tag = "Sayfa" if language.lower().startswith("tr") else "Page"
    header = "# Kısa Özet" if language.lower().startswith("tr") else "# Executive Summary"

    if not candidates:
        empty_msg = (
            "Belgede özetlenecek metin bulunamadı."
            if language.lower().startswith("tr")
            else "No extractable text found in the document."
        )
        return f"{header}\n\n{empty_msg}", []

    deduped = _deduplicate_candidates(candidates)

    # Distribute selections across pages if multi-page
    selected: list[_SentenceCandidate] = []
    by_page: dict[int, list[_SentenceCandidate]] = defaultdict(list)
    for c in deduped:
        by_page[c.page_number].append(c)

    # Pick the top candidate from each page first (up to 4 pages)
    for page_num in sorted(by_page.keys())[:4]:
        if by_page[page_num]:
            selected.append(by_page[page_num][0])

    # Fill remaining quota up to 5 points from overall highest
    for c in deduped:
        if len(selected) >= 5:
            break
        if c not in selected:
            selected.append(c)

    # Sort selected points in document order (page number, then index)
    selected.sort(key=lambda c: (c.page_number, c.index_in_page))

    points: list[SummaryPoint] = []
    lines = [header, ""]
    for c in selected:
        pt = SummaryPoint(text=c.clean_text, pages=[c.page_number], score=c.score)
        points.append(pt)
        lines.append(f"- {pt.format_with_citation(language)}")

    return "\n".join(lines), points


def _summarize_extractive_detayli(candidates: list[_SentenceCandidate],
                                 language: str,
                                 page_count: int) -> tuple[str, list[SummaryPoint]]:
    """Generate detailed summary organized by page or thematic section."""
    tag = "Sayfa" if language.lower().startswith("tr") else "Page"
    header = "# Detaylı Belge Özeti" if language.lower().startswith("tr") else "# Detailed Document Summary"

    if not candidates:
        empty_msg = (
            "Belgede özetlenecek metin bulunamadı."
            if language.lower().startswith("tr")
            else "No extractable text found in the document."
        )
        return f"{header}\n\n{empty_msg}", []

    deduped = _deduplicate_candidates(candidates)
    by_page: dict[int, list[_SentenceCandidate]] = defaultdict(list)
    for c in deduped:
        by_page[c.page_number].append(c)

    points: list[SummaryPoint] = []
    lines = [header, ""]

    if page_count > 1 or len(by_page) > 1:
        # Multi-page breakdown
        for page_num in sorted(by_page.keys()):
            page_candidates = by_page[page_num][:3]  # top 2-3 per page
            if not page_candidates:
                continue
            section_title = f"{tag} {page_num}"
            lines.append(f"### {section_title}")
            for c in page_candidates:
                pt = SummaryPoint(text=c.clean_text, pages=[c.page_number],
                                  section=section_title, score=c.score)
                points.append(pt)
                lines.append(f"- {pt.format_with_citation(language)}")
            lines.append("")
    else:
        # Single page: take top 6-8 points
        selected = deduped[:8]
        selected.sort(key=lambda c: c.index_in_page)
        lines.append("### Temel Maddeler ve Bulgular" if language.lower().startswith("tr")
                     else "### Key Points & Findings")
        for c in selected:
            pt = SummaryPoint(text=c.clean_text, pages=[c.page_number],
                              section="Bulgular", score=c.score)
            points.append(pt)
            lines.append(f"- {pt.format_with_citation(language)}")

    return "\n".join(lines).strip(), points


def _summarize_extractive_categorized(candidates: list[_SentenceCandidate],
                                     mode: str,
                                     language: str,
                                     sections_spec: list[tuple[str, str, str]]) -> tuple[str, list[SummaryPoint]]:
    """Generate categorized summary (ogrenci, toplanti, hukuki)."""
    is_tr = language.lower().startswith("tr")
    header_mapping = {
        "ogrenci": "# Öğrenci Çalışma Notları ve Özeti" if is_tr else "# Student Study Guide",
        "toplanti": "# Toplantı ve Yönetici Özeti" if is_tr else "# Meeting Summary",
        "hukuki": "# Hukuki ve Sözleşme Özeti" if is_tr else "# Legal & Contract Summary",
    }
    header = header_mapping.get(mode, "# Özet")

    if not candidates:
        empty_msg = (
            "Belgede özetlenecek metin bulunamadı."
            if is_tr
            else "No extractable text found in the document."
        )
        return f"{header}\n\n{empty_msg}", []

    deduped = _deduplicate_candidates(candidates)
    mode_spec = MODE_KEYWORDS.get(mode, {})

    assigned: dict[str, list[_SentenceCandidate]] = {key: [] for key, _, _ in sections_spec}
    used: set[str] = set()

    # Pass 1: Keyword-based matching
    for key, _, _ in sections_spec:
        keywords = set(mode_spec.get(key, []))
        if not keywords:
            continue
        for c in deduped:
            if c.clean_text in used:
                continue
            cand_tokens = set(c.tokens)
            # Boost / match when keywords are present
            if cand_tokens & keywords:
                assigned[key].append(c)
                used.add(c.clean_text)
                if len(assigned[key]) >= 4:
                    break

    # Pass 2: Fallback for empty/sparse sections using remaining highest TF candidates
    remaining = [c for c in deduped if c.clean_text not in used]
    rem_idx = 0
    for key, _, _ in sections_spec:
        while len(assigned[key]) < 2 and rem_idx < len(remaining):
            assigned[key].append(remaining[rem_idx])
            used.add(remaining[rem_idx].clean_text)
            rem_idx += 1

    points: list[SummaryPoint] = []
    lines = [header, ""]

    for key, title_tr, title_en in sections_spec:
        sec_title = title_tr if is_tr else title_en
        items = assigned.get(key, [])
        if not items:
            continue
        lines.append(f"### {sec_title}")
        # Sort items in reading order
        items.sort(key=lambda c: (c.page_number, c.index_in_page))
        for c in items:
            pt = SummaryPoint(text=c.clean_text, pages=[c.page_number],
                              section=sec_title, score=c.score)
            points.append(pt)
            lines.append(f"- {pt.format_with_citation(language)}")
        lines.append("")

    return "\n".join(lines).strip(), points


def _summarize_extractive_map_reduce(pages: Sequence[PageText],
                                     mode: str,
                                     language: str,
                                     progress: ProgressCallback | None = None,
                                     cancel: CancelCheck = None) -> tuple[str, list[SummaryPoint]]:
    """Map-Reduce extractive summarization for long multi-page documents."""
    total_pages = len(pages)
    map_candidates: list[_SentenceCandidate] = []

    # MAP PHASE: Extract top candidate sentences per page
    for idx, page in enumerate(pages):
        check_cancelled(cancel)
        report_progress(progress, 30 + int((idx / max(1, total_pages)) * 35), 100,
                        f"Sayfa {page.page_number}/{total_pages} taranıyor (Map)")
        page_cands = _extract_candidates([page])
        if not page_cands:
            continue
        _calculate_tf_scores(page_cands)
        # Select top candidates for this page (top 3-4 per page)
        top_page = sorted(page_cands, key=lambda c: -c.score)[:4]
        map_candidates.extend(top_page)

    check_cancelled(cancel)
    report_progress(progress, 70, 100, "Sayfa ozetleri birlestiriliyor (Reduce)")

    # REDUCE PHASE: Re-score combined candidates across pages
    _calculate_tf_scores(map_candidates)

    if mode == "kisa":
        return _summarize_extractive_kisa(map_candidates, language, total_pages)
    elif mode == "detayli":
        return _summarize_extractive_detayli(map_candidates, language, total_pages)
    elif mode == "ogrenci":
        spec = [
            ("definitions", "Temel Tanımlar ve Kavramlar", "Key Definitions & Concepts"),
            ("notes", "Önemli Notlar ve Ana Fikirler", "Core Notes & Principles"),
            ("exam", "Sınav ve Çalışma Hatırlatıcıları", "Exam & Review Takeaways"),
        ]
        return _summarize_extractive_categorized(map_candidates, "ogrenci", language, spec)
    elif mode == "toplanti":
        spec = [
            ("decisions", "Alınan Kararlar", "Decisions Taken"),
            ("actions", "Aksiyon Maddeleri ve Sorumluluklar", "Action Items & Responsibilities"),
            ("agenda", "Gündem ve Sonraki Adımlar", "Agenda & Next Steps"),
        ]
        return _summarize_extractive_categorized(map_candidates, "toplanti", language, spec)
    elif mode == "hukuki":
        spec = [
            ("parties_scope", "Taraflar ve Sözleşmenin Kapsamı", "Parties & Scope"),
            ("obligations", "Temel Hak ve Yükümlülükler", "Key Rights & Obligations"),
            ("termination_risks", "Fesih, Sorumluluk ve Cezai Şartlar", "Termination, Liability & Penalties"),
        ]
        return _summarize_extractive_categorized(map_candidates, "hukuki", language, spec)
    else:
        return _summarize_extractive_kisa(map_candidates, language, total_pages)


def _summarize_extractive(pages: Sequence[PageText],
                          mode: str,
                          language: str) -> tuple[str, list[SummaryPoint]]:
    """Run full extractive summarization pipeline."""
    candidates = _extract_candidates(pages)
    _calculate_tf_scores(candidates)
    page_count = len(pages)

    if mode == "kisa":
        return _summarize_extractive_kisa(candidates, language, page_count)
    elif mode == "detayli":
        return _summarize_extractive_detayli(candidates, language, page_count)
    elif mode == "ogrenci":
        spec = [
            ("definitions", "Temel Tanımlar ve Kavramlar", "Key Definitions & Concepts"),
            ("notes", "Önemli Notlar ve Ana Fikirler", "Core Notes & Principles"),
            ("exam", "Sınav ve Çalışma Hatırlatıcıları", "Exam & Review Takeaways"),
        ]
        return _summarize_extractive_categorized(candidates, "ogrenci", language, spec)
    elif mode == "toplanti":
        spec = [
            ("decisions", "Alınan Kararlar", "Decisions Taken"),
            ("actions", "Aksiyon Maddeleri ve Sorumluluklar", "Action Items & Responsibilities"),
            ("agenda", "Gündem ve Sonraki Adımlar", "Agenda & Next Steps"),
        ]
        return _summarize_extractive_categorized(candidates, "toplanti", language, spec)
    elif mode == "hukuki":
        spec = [
            ("parties_scope", "Taraflar ve Sözleşmenin Kapsamı", "Parties & Scope"),
            ("obligations", "Temel Hak ve Yükümlülükler", "Key Rights & Obligations"),
            ("termination_risks", "Fesih, Sorumluluk ve Cezai Şartlar", "Termination, Liability & Penalties"),
        ]
        return _summarize_extractive_categorized(candidates, "hukuki", language, spec)
    else:
        return _summarize_extractive_kisa(candidates, language, page_count)


# ── LLM Summarization & Map-Reduce ─────────────────────────────────────────

def _parse_llm_points(text: str, default_page: int = 1) -> list[SummaryPoint]:
    """Parse bullet points and [Sayfa X] / [Page X] citations from LLM output."""
    points: list[SummaryPoint] = []
    current_section = ""

    for line in text.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        if trimmed.startswith("#"):
            current_section = trimmed.lstrip("#").strip()
            continue

        if trimmed.startswith(("-", "*", "•")) or re.match(r"^\d+\.", trimmed):
            bullet_text = re.sub(r"^[-*•\d.)]+\s*", "", trimmed).strip()
            # Find citation e.g. [Sayfa 1, 2] or [Page 3]
            match = re.search(r"\[(?:Sayfa|Page)\s*([0-9,\s]+)\]", bullet_text, flags=re.IGNORECASE)
            pages: list[int] = []
            if match:
                page_nums = re.findall(r"\d+", match.group(1))
                pages = [int(p) for p in page_nums]
                clean_pt = re.sub(r"\s*\[(?:Sayfa|Page)\s*[0-9,\s]+\]", "", bullet_text).strip()
            else:
                pages = [default_page]
                clean_pt = bullet_text

            if clean_pt:
                points.append(SummaryPoint(text=clean_pt, pages=pages, section=current_section))

    return points


def _summarize_llm_map_reduce(llm: LocalLLM,
                              pages: Sequence[PageText],
                              mode: str,
                              language: str,
                              progress: ProgressCallback | None = None,
                              cancel: CancelCheck = None) -> tuple[str, list[SummaryPoint]] | None:
    """Run Map-Reduce summarization using LocalLLM."""
    is_tr = language.lower().startswith("tr")
    tag = "Sayfa" if is_tr else "Page"

    mode_descriptions = {
        "kisa": "kısa ve öz ana noktalar (3-5 madde)" if is_tr else "short executive summary (3-5 points)",
        "detayli": "tüm bölümleri kapsayan detaylı özet" if is_tr else "comprehensive detailed summary",
        "ogrenci": "öğrenci çalışma rehberi, tanımlar ve sınav notları" if is_tr else "student study guide and key concepts",
        "toplanti": "toplantı kararları, aksiyon maddeleri ve sonraki adımlar" if is_tr else "meeting minutes, decisions, and action items",
        "hukuki": "taraflar, yükümlülükler, fesih ve cezai şartlar" if is_tr else "parties, obligations, termination and liabilities",
    }
    mode_desc = mode_descriptions.get(mode, mode)

    # ── MAP PHASE: Summarize individual pages ──
    page_summaries: list[str] = []
    total_pages = len(pages)

    for idx, page in enumerate(pages):
        check_cancelled(cancel)
        report_progress(progress, 30 + int((idx / max(1, total_pages)) * 35), 100,
                        f"Sayfa {page.page_number}/{total_pages} özetleniyor (Map)")

        text = page.text.strip()
        if not text:
            continue

        # If page is short, use directly; otherwise summarize with LLM
        if len(text) < 400:
            page_summaries.append(f"[{tag} {page.page_number}]\n{text}")
            continue

        prompt = (
            f"Sen bir özetleme asistanısın. Aşağıdaki metin belgenin {page.page_number}. sayfasına aittir.\n"
            f"Bu sayfadaki en önemli 2-4 bilgiyi madde halinde özetle.\n"
            f"KURAL: Her maddenin sonuna mutlaka [{tag} {page.page_number}] yaz.\n\n"
            f"METİN (Sayfa {page.page_number}):\n{text[:2500]}\n\n"
            f"ÖZET:"
        )

        try:
            summary_piece = llm.generate(prompt, max_tokens=256, temperature=0.1, cancel=cancel)
        except Exception:
            summary_piece = None

        if summary_piece:
            page_summaries.append(f"[{tag} {page.page_number} Notları]:\n{summary_piece.strip()}")
        else:
            page_summaries.append(f"[{tag} {page.page_number}]:\n{text[:600]}")

    if not page_summaries:
        return None

    # ── REDUCE PHASE: Synthesize into final mode-specific summary ──
    check_cancelled(cancel)
    report_progress(progress, 75, 100, "Ozetler birlestiriliyor (Reduce)")

    combined_notes = "\n\n".join(page_summaries)
    if len(combined_notes) > 4000:
        combined_notes = combined_notes[:4000]

    reduce_prompt = (
        f"Sen profesyonel bir belge analiz asistanısın.\n"
        f"Aşağıda belgenin sayfa sayfa çıkarılmış özet notları yer almaktadır.\n"
        f"Bu notları kullanarak '{mode_desc}' modunda nihai, tutarlı ve eksiksiz bir özet oluştur.\n\n"
        f"ÖNEMLİ KURALLAR:\n"
        f"1. Her tespit veya maddenin sonuna MUTLAKA kaynak sayfa numarasını [{tag} X] olarak ekle.\n"
        f"2. Bilgi uydurma, yalnızca verilen notları kullan.\n"
        f"3. Başlıklar ve temiz maddeler halinde düzenle.\n\n"
        f"SAYFA NOTLARI:\n{combined_notes}\n\n"
        f"NİHAİ ÖZET:"
    )

    try:
        final_text = llm.generate(reduce_prompt, max_tokens=600, temperature=0.1, cancel=cancel)
    except Exception:
        final_text = None

    if not final_text:
        return None

    points = _parse_llm_points(final_text, default_page=pages[0].page_number if pages else 1)
    return final_text, points


# ── Core Summarizer Engine Class ───────────────────────────────────────────

class Summarizer:
    """PDF summarizer supporting multiple modes, map-reduce, and extractive fallback."""

    def __init__(self, llm: LocalLLM | None = None, *, use_llm: bool = True,
                 cache_dir: str | Path | None = None):
        self.use_llm = bool(use_llm)
        self.cache_dir = cache_dir
        if llm is not None:
            self.llm = llm
        elif self.use_llm:
            try:
                self.llm = LocalLLM()
            except Exception:
                self.llm = None
        else:
            self.llm = None

    def summarize(self, pdf_path: str | os.PathLike,
                  mode: str = "kisa",
                  language: str = "tr",
                  progress: ProgressCallback | None = None,
                  cancel: CancelCheck = None,
                  **kwargs) -> SummaryResult:
        """Summarize *pdf_path* under *mode* ('kisa', 'detayli', 'ogrenci', 'toplanti', 'hukuki')."""
        canon_mode = normalize_mode(mode)
        lang = str(language or "tr").lower()[:2]
        check_cancelled(cancel)

        # 1. Load Document
        report_progress(progress, 10, 100, "Belge yukleniyor")

        def load_progress(current, total, message=""):
            frac = (current / total) if total else 0.0
            report_progress(progress, 10 + int(frac * 20), 100, message)

        doc = load_document(pdf_path, cache_dir=self.cache_dir,
                            progress=load_progress, cancel=cancel)
        check_cancelled(cancel)

        if not doc.pages or not any(p.text.strip() for p in doc.pages):
            empty_msg = (
                "Bu belgede aranabilir veya okunabilir metin bulunamadı."
                if lang.startswith("tr")
                else "No readable text found in this document."
            )
            report_progress(progress, 100, 100, "Metin bulunamadi")
            return SummaryResult(
                text=empty_msg,
                mode=canon_mode,
                language=lang,
                points=[],
                sources=[],
                used_llm=False,
                document_path=str(doc.path),
                page_count=doc.page_count,
            )

        total_chars = sum(len(p.text) for p in doc.pages)
        map_reduce_req = kwargs.get("map_reduce", None)
        if map_reduce_req is not None:
            is_long = bool(map_reduce_req)
        else:
            is_long = (doc.page_count >= LONG_DOC_PAGE_THRESHOLD or total_chars >= LONG_DOC_CHAR_THRESHOLD)

        # 2. Attempt LLM generation if available
        llm_ready = self.use_llm and self.llm is not None and getattr(self.llm, "available", False)
        if llm_ready:
            try:
                report_progress(progress, 35, 100, "Yapay zeka ozeti hazirlaniyor")
                if is_long:
                    llm_out = _summarize_llm_map_reduce(
                        self.llm, doc.pages, canon_mode, lang,
                        progress=progress, cancel=cancel,
                    )
                else:
                    # Single page or short document direct generation
                    combined_text = "\n\n".join(
                        f"[Sayfa {p.page_number}]\n{p.text}" for p in doc.pages if p.text.strip()
                    )
                    prompt = (
                        f"Sen profesyonel bir belge analiz asistanısın. Aşağıdaki metni '{canon_mode}' modunda özetle.\n"
                        f"KURAL: Her maddenin sonuna kaynak sayfa numarasını [Sayfa X] olarak ekle. Bilgi uydurma.\n\n"
                        f"METİN:\n{combined_text}\n\nÖZET:"
                    )
                    text_out = self.llm.generate(prompt, max_tokens=512, cancel=cancel)
                    if text_out:
                        points = _parse_llm_points(text_out, default_page=1)
                        llm_out = (text_out, points)
                    else:
                        llm_out = None

                if llm_out:
                    summary_text, points = llm_out
                    # Gather unique sources from points
                    sources = sorted({p for pt in points for p in pt.pages})
                    report_progress(progress, 100, 100, "Ozet tamamlandi")
                    return SummaryResult(
                        text=summary_text,
                        mode=canon_mode,
                        language=lang,
                        points=points,
                        sources=sources,
                        used_llm=True,
                        document_path=str(doc.path),
                        page_count=doc.page_count,
                        metadata={"method": "llm_map_reduce" if is_long else "llm_direct", "is_long": is_long},
                    )
            except CancelledError:
                raise
            except Exception:
                # LLM failure gracefully degrades to extractive summarizer below
                pass

        # 3. Extractive Summarizer Fallback (term-frequency sentence scoring)
        check_cancelled(cancel)
        report_progress(progress, 60, 100, "Cikarimsal ozet olusturuluyor")
        if is_long:
            summary_text, points = _summarize_extractive_map_reduce(
                doc.pages, canon_mode, lang, progress=progress, cancel=cancel
            )
            method = "extractive_map_reduce"
        else:
            summary_text, points = _summarize_extractive(doc.pages, canon_mode, lang)
            method = "extractive_tf"

        sources = sorted({p for pt in points for p in pt.pages})

        report_progress(progress, 100, 100, "Ozet tamamlandi")
        return SummaryResult(
            text=summary_text,
            mode=canon_mode,
            language=lang,
            points=points,
            sources=sources,
            used_llm=False,
            document_path=str(doc.path),
            page_count=doc.page_count,
            metadata={"method": method, "is_long": is_long},
        )


def summarize(pdf_path: str | os.PathLike,
              mode: str = "kisa",
              language: str = "tr",
              progress: ProgressCallback | None = None,
              cancel: CancelCheck = None,
              llm: LocalLLM | None = None,
              use_llm: bool = True,
              cache_dir: str | Path | None = None,
              **kwargs) -> SummaryResult:
    """Convenience functional wrapper around :class:`Summarizer`."""
    engine = Summarizer(llm=llm, use_llm=use_llm, cache_dir=cache_dir)
    return engine.summarize(pdf_path=pdf_path, mode=mode, language=language,
                            progress=progress, cancel=cancel, **kwargs)


# ── Saving Summaries: TXT and PDF with Turkish Characters ──────────────────

def save_txt(summary: SummaryResult | str | dict[str, Any], path: str | os.PathLike) -> str:
    """Save summary text to a UTF-8 encoded text file."""
    if isinstance(summary, SummaryResult):
        text = summary.text
    elif isinstance(summary, dict):
        text = str(summary.get("text", ""))
    else:
        text = str(summary or "")

    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)
    return str(target)


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


class _SummaryPdfWriter:
    """Renders formatted summary documents to PDF with full Turkish glyph support."""

    PAGE_WIDTH = 595.32   # A4
    PAGE_HEIGHT = 841.92  # A4
    MARGIN = 50.0

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

        # Draw header banner
        header_text = f"PDFAura • Akıllı Özet {f'— {self.title}' if self.title else ''}"
        if self._ascii:
            header_text = header_text.translate(_ASCII_TRANSLATION)
        self.current_page.insert_text(
            (self.MARGIN, self.MARGIN * 0.7),
            header_text,
            fontname=self.font_name,
            fontsize=8.5,
            color=(0.45, 0.45, 0.45),
        )
        self.current_page.draw_line(
            fitz.Point(self.MARGIN, self.MARGIN * 0.8),
            fitz.Point(self.PAGE_WIDTH - self.MARGIN, self.MARGIN * 0.8),
            color=(0.82, 0.82, 0.82),
            width=0.6,
        )

        self.y = self.MARGIN + 15.0

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

    def add_line(self, text: str, *, size: float = 10.0,
                 color: tuple[float, float, float] = (0.1, 0.1, 0.1),
                 indent: float = 0.0, space_after: float = 3.0) -> None:
        if self._ascii:
            text = str(text).translate(_ASCII_TRANSLATION)

        width = self.PAGE_WIDTH - 2 * self.MARGIN - indent
        line_height = size * 1.38

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
            size = 16.0
            color = (0.10, 0.18, 0.40)
            space_before = 8.0
            space_after = 8.0
        elif level == 2:
            size = 13.0
            color = (0.12, 0.22, 0.45)
            space_before = 10.0
            space_after = 5.0
        else:
            size = 11.5
            color = (0.20, 0.28, 0.48)
            space_before = 8.0
            space_after = 4.0

        self._ensure_space(space_before + size * 1.5)
        self.y += space_before
        self.add_line(text, size=size, color=color, space_after=space_after)

    def add_bullet(self, text: str, *, indent: float = 14.0) -> None:
        bullet_char = "-" if self._ascii else "•"
        full_text = f"{bullet_char}  {text}"
        self.add_line(full_text, size=10.0, color=(0.12, 0.12, 0.12),
                     indent=indent, space_after=4.0)


def save_pdf(summary: SummaryResult | str | dict[str, Any],
             path: str | os.PathLike,
             title: str | None = None) -> str:
    if "\x00" in str(path):
        raise ValueError("Path contains invalid null character")
    """Save summary to a formatted PDF with full Turkish character support."""
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) kurulu değil; PDF kaydetme devre dışı.")

    if isinstance(summary, SummaryResult):
        text = summary.text
        doc_title = title or f"{summary.mode.capitalize()} Özet"
    elif isinstance(summary, dict):
        text = str(summary.get("text", ""))
        doc_title = title or str(summary.get("mode", "Özet")).capitalize()
    else:
        text = str(summary or "")
        doc_title = title or "Belge Özeti"

    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    pdf_doc = fitz.open()
    try:
        writer = _SummaryPdfWriter(pdf_doc, title=doc_title)

        for line in text.splitlines():
            trimmed = line.strip()
            if not trimmed:
                writer.y += 4.0
                continue

            if trimmed.startswith("# "):
                writer.add_heading(trimmed[2:].strip(), level=1)
            elif trimmed.startswith("## "):
                writer.add_heading(trimmed[3:].strip(), level=2)
            elif trimmed.startswith("### "):
                writer.add_heading(trimmed[4:].strip(), level=3)
            elif trimmed.startswith(("-", "*", "•")):
                bullet_content = re.sub(r"^[-*•]\s*", "", trimmed).strip()
                writer.add_bullet(bullet_content)
            else:
                writer.add_line(trimmed, size=10.0, color=(0.15, 0.15, 0.15), space_after=3.0)

        # Draw footer page numbers across all pages
        total = pdf_doc.page_count
        for i in range(total):
            page = pdf_doc[i]
            footer = f"Sayfa {i + 1} / {total}"
            page.insert_text(
                (writer.MARGIN, writer.PAGE_HEIGHT - writer.MARGIN * 0.6),
                footer,
                fontname=writer.font_name,
                fontsize=8.0,
                color=(0.55, 0.55, 0.55),
            )

        pdf_doc.save(str(target), deflate=True, garbage=3)
    finally:
        pdf_doc.close()

    return str(target)
