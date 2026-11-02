"""Faz 10: PDF'den Sunum Oluşturma (Presentation Outline & Slide Generator).

Creates structured presentation outlines from PDFs with source page grounding:
- Supported tones: "kisa", "akademik", "yonetici", "ders".
- LLM generation when a local GGUF model is available via :class:`src.ai.local_llm.LocalLLM`.
- Graceful extractive fallback: page clustering and topic sentence ranking with source page refs.
- Export helpers:
    * `export_pptx(slides, path)`: 16:9 widescreen PowerPoint presentation (optional python-pptx).
    * `export_pdf_slides(slides, path)`: 16:9 landscape PDF slides via PyMuPDF.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.ai.document_loader import (
    PageText,
    check_cancelled,
    extract_pages,
    report_progress,
)
from src.ai.local_llm import LocalLLM
from src.core.task_manager import CancelledError

try:
    import fitz
except ImportError:
    fitz = None

try:
    import pptx
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches, Pt
except ImportError:
    pptx = None

logger = logging.getLogger(__name__)

ProgressCallback = Callable[..., None]
CancelCheck = Callable[[], bool] | None

# Supported tones and aliases
TONES = ("kisa", "akademik", "yonetici", "ders")

TONE_ALIASES: dict[str, str] = {
    "kisa": "kisa",
    "kısa": "kisa",
    "short": "kisa",
    "brief": "kisa",
    "summary": "kisa",
    "akademik": "akademik",
    "academic": "akademik",
    "bilimsel": "akademik",
    "yonetici": "yonetici",
    "yönetici": "yonetici",
    "yonetici ozeti": "yonetici",
    "yönetici özeti": "yonetici",
    "executive": "yonetici",
    "business": "yonetici",
    "ders": "ders",
    "ders anlatimi": "ders",
    "ders anlatımı": "ders",
    "lecture": "ders",
    "ogrenci": "ders",
    "öğrenci": "ders",
    "egitim": "ders",
    "eğitim": "ders",
}

# Stopwords for keyword extraction (Turkish & English)
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
    "has", "have", "having", "he", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "isn't", "it", "its", "itself", "me",
    "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "once",
    "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "we", "were",
    "what", "when", "where", "which", "while", "who", "whom", "why", "with", "would",
    "you", "your", "yours", "yourself", "yourselves",
}

# Tone keywords used to boost salient sentences in extractive ranking
TONE_KEYWORDS: dict[str, list[str]] = {
    "yonetici": [
        "karar", "strateji", "hedef", "gelir", "maliyet", "büyüme", "performans",
        "artış", "azalış", "başarı", "risk", "fırsat", "eylem", "plan", "öneri",
        "kritik", "liderlik", "müşteri", "pazar", "yatırım", "verimlilik", "sonuç",
        "bütçe", "kâr", "zarar", "executive", "target", "result", "growth", "strategy",
    ],
    "akademik": [
        "araştırma", "çalışma", "yöntem", "metodoloji", "bulgu", "teori", "hipotez",
        "analiz", "veri", "literatür", "kaynak", "sonuç", "gözlem", "deney",
        "değişken", "model", "bağlam", "yaklaşım", "istatistik", "katkı", "tartışma",
        "research", "method", "analysis", "finding", "hypothesis", "study", "data",
    ],
    "ders": [
        "tanım", "kavram", "nedir", "örnek", "özellik", "ilke", "kural", "formül",
        "açıklama", "önemli", "not", "dikkat", "ipucu", "özet", "öğrenme", "adım",
        "neden", "sonuç", "temel", "esas", "aşama", "concept", "definition", "example",
        "rule", "lesson", "principle",
    ],
    "kisa": [
        "özet", "temel", "başlıca", "ana", "sonuç", "önemli", "kilit", "özetle",
        "bulgular", "takeaway", "key", "main", "summary", "core",
    ],
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


def normalize_tone(tone: str | None) -> str:
    """Normalize tone input string to canonical tone name."""
    clean = turkish_lower(str(tone or "")).strip()
    return TONE_ALIASES.get(clean, "yonetici")


def tokenize(text: str) -> list[str]:
    """Extract lowercased word tokens."""
    lowered = turkish_lower(text)
    return re.findall(r"[a-z0-9ğüşıöç]+", lowered)


@dataclass
class Slide:
    """Representation of a presentation slide with source page attribution."""

    title: str
    bullet_points: list[str] = field(default_factory=list)
    source_pages: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "bullet_points": list(self.bullet_points),
            "source_pages": list(self.source_pages),
        }

    def __getitem__(self, key: str) -> Any:
        if key == "title":
            return self.title
        if key in ("bullet_points", "bullets", "points"):
            return self.bullet_points
        if key in ("source_pages", "pages", "sources"):
            return self.source_pages
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


def _normalize_slide(slide: Slide | dict[str, Any] | Sequence[Any]) -> Slide:
    """Coerce various slide formats into a standard Slide instance."""
    if isinstance(slide, Slide):
        return slide
    if isinstance(slide, dict):
        title = str(slide.get("title") or "Slayt")
        raw_bullets = (
            slide.get("bullet_points") or
            slide.get("bullets") or
            slide.get("points") or
            []
        )
        bullets = list(raw_bullets)
        raw_pages = (
            slide.get("source_pages") or
            slide.get("pages") or
            slide.get("sources") or
            []
        )
        pages = list(raw_pages)
        return Slide(title=title, bullet_points=bullets, source_pages=pages)
    if isinstance(slide, (list, tuple)):
        title = str(slide[0]) if len(slide) > 0 else "Slayt"
        bullets = list(slide[1]) if len(slide) > 1 else []
        pages = list(slide[2]) if len(slide) > 2 else []
        return Slide(title=title, bullet_points=bullets, source_pages=pages)
    raise TypeError(f"Desteklenmeyen slayt türü: {type(slide)}")


# ── Extractive Outline Generator Helpers ────────────────────────────────────

@dataclass
class _TextUnit:
    page_number: int
    text: str
    is_heading: bool = False


def _split_into_sentences(text: str) -> list[str]:
    """Break text into individual candidate sentences."""
    if not text:
        return []
    # Replace line breaks inside a paragraph with a space
    normalized = re.sub(r"\s+", " ", text).strip()
    # Split on sentence boundaries: period, exclamation or question followed by space or capital
    raw_sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ0-9])", normalized)
    results: list[str] = []
    for s in raw_sentences:
        candidate = s.strip()
        # Clean leading bullet markers or numbers
        candidate = re.sub(r"^[-*•\d+.)\s]+", "", candidate).strip()
        if len(candidate) >= 15:
            results.append(candidate)
    return results


def _extract_text_units(pages: Sequence[PageText]) -> list[_TextUnit]:
    """Extract paragraphs and headings from pages as ordered units."""
    units: list[_TextUnit] = []
    for page in pages:
        p_num = page.page_number
        raw_text = page.text or ""
        # Check text blocks if available
        if page.blocks:
            for block in page.blocks:
                b_text = block.text.strip()
                if not b_text:
                    continue
                lines = [line.strip() for line in b_text.splitlines() if line.strip()]
                for line in lines:
                    # Heading heuristic: short, no terminal period, or starts with section number
                    is_h = (
                        len(line) <= 75 and
                        not line.endswith((".", ":", ";")) and
                        (re.match(r"^(\d+\.?|[A-ZÇĞİÖŞÜ0-9\s-]{4,})", line) is not None)
                    )
                    units.append(_TextUnit(page_number=p_num, text=line, is_heading=is_h))
        else:
            # Fall back to splitting page text by paragraphs
            paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
            for p in paragraphs:
                is_h = len(p) <= 70 and not p.endswith((".", ":"))
                units.append(_TextUnit(page_number=p_num, text=p, is_heading=is_h))

    # Clean out very short, meaningless units
    return [u for u in units if len(u.text) >= 10]


def _score_sentence(sentence: str, word_freq: Counter, tone: str, is_first: bool) -> float:
    """Score a candidate sentence based on term frequencies and tone keywords."""
    tokens = tokenize(sentence)
    if not tokens:
        return 0.0

    content_tokens = [t for t in tokens if t not in STOPWORDS]
    if not content_tokens:
        return 0.1

    # Base TF score
    tf_sum = sum(word_freq[t] for t in content_tokens)
    base_score = tf_sum / (len(content_tokens) ** 0.75)

    # Tone keyword boost
    tone_kws = TONE_KEYWORDS.get(tone, [])
    tone_hits = sum(1 for t in tokens if any(kw in t for kw in tone_kws))
    tone_bonus = 1.0 + (0.45 * tone_hits)

    # Position bonus
    pos_bonus = 1.25 if is_first else 1.0

    # Length penalty / reward: ideal presentation bullet is 35-130 chars
    s_len = len(sentence)
    if 30 <= s_len <= 140:
        len_mult = 1.15
    elif s_len > 220:
        len_mult = 0.7
    else:
        len_mult = 0.95

    return base_score * tone_bonus * pos_bonus * len_mult


def _cluster_units(units: list[_TextUnit], count: int) -> list[list[_TextUnit]]:
    """Partition sequential text units into `count` clusters."""
    if not units or count <= 0:
        return []
    total = len(units)
    if count >= total:
        # One unit per cluster
        return [[u] for u in units]

    clusters: list[list[_TextUnit]] = []
    for i in range(count):
        start = math.floor(i * total / count)
        end = math.floor((i + 1) * total / count)
        cluster = units[start:end]
        if cluster:
            clusters.append(cluster)
    return clusters


def _determine_slide_title(
    cluster: list[_TextUnit],
    index: int,
    total_slides: int,
    tone: str,
    word_freq: Counter,
) -> str:
    """Synthesize a meaningful, clean title for a slide."""
    # 1. Check if the cluster has an explicit heading
    for unit in cluster:
        if unit.is_heading and len(unit.text) >= 4:
            clean_h = re.sub(r"^(\d+[\.\)]|\#+)\s*", "", unit.text).strip()
            if clean_h and len(clean_h) <= 60:
                return clean_h

    # 2. Heuristic titles for first and last slide based on tone
    if index == 0:
        intro_titles = {
            "yonetici": "Yönetici Özeti: Genel Bakış",
            "akademik": "Giriş ve Araştırma Çerçevesi",
            "ders": "Giriş ve Temel Kavramlar",
            "kisa": "Genel Bakış ve Temel Bulgular",
        }
        return intro_titles.get(tone, "Giriş ve Genel Bakış")

    if index == total_slides - 1:
        conclusion_titles = {
            "yonetici": "Stratejik Öneriler ve Eylem Planı",
            "akademik": "Sonuçlar ve Değerlendirme",
            "ders": "Özet ve Ders Notları",
            "kisa": "Sonuç ve Kapanış",
        }
        return conclusion_titles.get(tone, "Sonuç ve Değerlendirme")

    # 3. Extract top salient keywords from the cluster
    cluster_tokens = []
    for unit in cluster:
        for t in tokenize(unit.text):
            if t not in STOPWORDS and len(t) >= 3:
                cluster_tokens.append(t)

    c_freq = Counter(cluster_tokens)
    top_words = [w.capitalize() for w, _ in c_freq.most_common(2)]
    if top_words:
        return f"{' & '.join(top_words)} Analizi"

    return f"Bölüm {index + 1}: Detaylar"


def _generate_extractive_outline(pages: Sequence[PageText], slide_count: int,
                                 tone: str, progress: ProgressCallback | None = None,
                                 cancel: CancelCheck = None) -> list[Slide]:
    """Create slides using page clustering and topic sentence ranking."""
    check_cancelled(cancel)
    units = _extract_text_units(pages)
    if not units:
        # Empty document fallback
        return [Slide(
            title="Belge Özeti",
            bullet_points=["Belgede işlenebilir metin bulunamadı."],
            source_pages=[1] if pages else [],
        )]

    # Compute global word frequency across all text
    all_tokens = [
        t for u in units
        for t in tokenize(u.text)
        if t not in STOPWORDS and len(t) >= 3
    ]
    word_freq = Counter(all_tokens)

    # Determine bullet count range based on tone
    target_bullets_map = {
        "kisa": 3,
        "yonetici": 4,
        "akademik": 4,
        "ders": 4,
    }
    max_bullets = target_bullets_map.get(tone, 4)

    clusters = _cluster_units(units, slide_count)
    slides: list[Slide] = []
    num_clusters = len(clusters)

    for i, cluster in enumerate(clusters):
        check_cancelled(cancel)
        report_progress(progress, i + 1, num_clusters, f"Slayt {i + 1}/{num_clusters} hazirlaniyor...")

        # Gather source pages
        source_pages = sorted({u.page_number for u in cluster})

        # Title
        title = _determine_slide_title(cluster, i, num_clusters, tone, word_freq)

        # Candidate sentences
        candidate_sentences: list[tuple[str, float]] = []
        for u_idx, unit in enumerate(cluster):
            sentences = _split_into_sentences(unit.text)
            for s_idx, s in enumerate(sentences):
                # Avoid sentence if identical to title
                if turkish_lower(s) == turkish_lower(title):
                    continue
                score = _score_sentence(s, word_freq, tone, is_first=(u_idx == 0 and s_idx == 0))
                candidate_sentences.append((s, score))

        # Rank sentences
        candidate_sentences.sort(key=lambda item: item[1], reverse=True)

        # Select diverse top sentences
        selected_bullets: list[str] = []
        selected_tokens_sets: list[set[str]] = []

        for sentence, _ in candidate_sentences:
            s_toks = set(tokenize(sentence))
            # Jaccard diversity check with already selected bullets
            overlap = False
            for prev_toks in selected_tokens_sets:
                if len(s_toks & prev_toks) / max(1, len(s_toks | prev_toks)) > 0.55:
                    overlap = True
                    break
            if overlap:
                continue

            # Format bullet
            bullet_text = sentence.strip()
            # Ensure it starts capitalized
            if bullet_text:
                bullet_text = bullet_text[0].upper() + bullet_text[1:]
            selected_bullets.append(bullet_text)
            selected_tokens_sets.append(s_toks)

            if len(selected_bullets) >= max_bullets:
                break

        # Fallback if no clean sentences qualified
        if not selected_bullets and cluster:
            snippet = cluster[0].text[:120].strip()
            selected_bullets.append(snippet if snippet else "Detaylar inceleniyor.")

        slides.append(Slide(
            title=title,
            bullet_points=selected_bullets,
            source_pages=source_pages,
        ))

    return slides


# ── Local LLM Generation ───────────────────────────────────────────────────

def _format_llm_prompt(pages: Sequence[PageText], slide_count: int, tone: str) -> str:
    """Construct prompt for local LLM to generate structured slides."""
    tone_descriptions = {
        "kisa": "Kısa, öz ve net; slayt başına 2-3 vurucu madde içeren özet tonu.",
        "akademik": "Akademik, bilimsel ve yöntem/bulgu odaklı; terminolojiye uygun resmi ton.",
        "yonetici": "Yönetici özeti; stratejik hedefler, iş etkisi, risk ve aksiyon odaklı ton.",
        "ders": "Ders anlatımı; eğitici, temel kavramlar, açıklamalar ve örnek odaklı pedagojik ton.",
    }
    tone_desc = tone_descriptions.get(tone, tone_descriptions["yonetici"])

    # Sample pages text with page tags (limit to ~4000 chars to fit context window)
    context_parts: list[str] = []
    total_chars = 0
    for page in pages:
        p_text = page.text.strip()
        if not p_text:
            continue
        part = f"--- [Sayfa {page.page_number}] ---\n{p_text[:800]}\n"
        context_parts.append(part)
        total_chars += len(part)
        if total_chars >= 4000:
            break

    doc_context = "\n".join(context_parts)

    return f"""Aşağıdaki PDF belgesini inceleyerek {slide_count} adet slayttan oluşan bir sunum taslağı hazırla.

Sunum Tonu: {tone_desc}
İstenen Slayt Sayısı: {slide_count}

Belge Metni:
{doc_context}

Gereksinimler:
1. Tam olarak {slide_count} slayt oluştur.
2. Her slayt için bir 'title' (başlık), 'bullet_points' (kısa ve etkili maddeler listesi) ve bilgilerin alındığı 'source_pages' (sayfa numaraları listesi) belirle.
3. Çıktıyı SADECE geçerli bir JSON dizisi formatında üret, başka hiçbir açıklama veya markdown ekleme:
[
  {{
    "title": "Giriş ve Genel Bakış",
    "bullet_points": ["Temel amaç ve kapsam...", "Öne çıkan ilk bulgular..."],
    "source_pages": [1, 2]
  }}
]"""


def _parse_llm_response(raw_text: str | None) -> list[Slide] | None:
    """Attempt to parse JSON array of slides from LLM generation."""
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    match = re.search(r"\[\s*\{.*\}\s*\]", cleaned, re.DOTALL)
    if not match:
        return None
    json_str = match.group(0)
    try:
        data = json.loads(json_str)
        if not isinstance(data, list) or not data:
            return None
        slides: list[Slide] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip() or "Slayt"
            raw_bullets = item.get("bullet_points") or item.get("bullets") or []
            bullets = [str(b).strip() for b in raw_bullets if str(b).strip()]
            raw_pages = item.get("source_pages") or item.get("pages") or []
            pages = []
            for p in raw_pages:
                try:
                    pages.append(int(p))
                except (ValueError, TypeError):
                    pass
            slides.append(
                Slide(title=title, bullet_points=bullets, source_pages=sorted(set(pages)))
            )
        return slides if slides else None
    except (json.JSONDecodeError, TypeError, ValueError, KeyError, AttributeError) as exc:
        logger.debug("LLM JSON parsing error: %s", exc)
        return None


# ── Main Presentation Outline Entry Point ───────────────────────────────────

def generate_presentation_outline(
    pdf_path: str | os.PathLike,
    slide_count: int = 8,
    tone: str = "yonetici",
    progress: ProgressCallback | None = None,
    cancel: CancelCheck = None,
    *,
    llm: LocalLLM | None = None,
    use_llm: bool = True,
) -> list[Slide]:
    """Generate a structured presentation outline from *pdf_path*.

    Args:
        pdf_path: Path to the input PDF file.
        slide_count: Target number of slides (default: 8).
        tone: Presentation tone ('kisa', 'akademik', 'yonetici', 'ders').
        progress: Optional callback `(current, total, message)`.
        cancel: Optional cancellation token or callable.
        llm: Optional custom LocalLLM instance.
        use_llm: Whether to attempt local LLM generation when available.

    Returns:
        List of :class:`Slide` objects containing title, bullet_points, source_pages.
    """
    path = Path(pdf_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"PDF bulunamadı: {path}")

    check_cancelled(cancel)
    norm_tone = normalize_tone(tone)
    target_count = max(1, int(slide_count))

    report_progress(progress, 0, target_count, "PDF okunuyor...")
    pages = extract_pages(path, progress=progress, cancel=cancel)
    check_cancelled(cancel)

    # 1. Try local LLM generation if requested and available
    if use_llm:
        local_llm_instance = llm if llm is not None else LocalLLM()
        if local_llm_instance.available:
            try:
                report_progress(progress, 1, target_count, "LLM ile sunum taslagi uretiliyor...")
                prompt = _format_llm_prompt(pages, target_count, norm_tone)
                response = local_llm_instance.generate(
                    prompt,
                    max_tokens=1500,
                    temperature=0.2,
                    progress=progress,
                    cancel=cancel,
                )
                llm_slides = _parse_llm_response(response)
                if llm_slides and len(llm_slides) >= 1:
                    report_progress(progress, target_count, target_count, "Sunum taslagi tamamlandi.")
                    return llm_slides[:target_count]
            except CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("Local LLM sunum üretimi başarısız, metin tabanlı fallback devrede: %s", exc)

    # 2. Extractive fallback (page clustering + topic sentence ranking)
    report_progress(progress, 1, target_count, "Konu analizi ve slayt kumeleri olusturuluyor...")
    slides = _generate_extractive_outline(
        pages,
        slide_count=target_count,
        tone=norm_tone,
        progress=progress,
        cancel=cancel,
    )

    report_progress(progress, target_count, target_count, "Sunum taslagi hazirlandi.")
    return slides


# ── System Font Discovery for PyMuPDF ───────────────────────────────────────

def _find_system_turkish_font() -> str:
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


# ── Export PPTX ─────────────────────────────────────────────────────────────

def is_pptx_available() -> bool:
    """Return whether python-pptx is installed."""
    return pptx is not None


def export_pptx(
    slides: Sequence[Slide | dict[str, Any]],
    path: str | os.PathLike,
    *,
    raise_on_error: bool = False,
) -> str | None:
    """Export slides to a 16:9 widescreen PowerPoint presentation (.pptx).

    Args:
        slides: Sequence of Slide objects or slide dictionaries.
        path: Output file path.
        raise_on_error: If True, raise ImportError when python-pptx is missing.

    Returns:
        The output path string, or None if python-pptx is unavailable and raise_on_error is False.
    """
    if pptx is None:
        logger.warning("python-pptx kurulu değil; PPTX dışa aktarma devre dışı.")
        if raise_on_error:
            raise ImportError("python-pptx kurulu değil; 'pip install python-pptx' gereklidir.")
        return None

    norm_slides = [_normalize_slide(s) for s in slides]
    if not norm_slides:
        raise ValueError("Dışa aktarılacak slayt bulunamadı.")

    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    prs = pptx.Presentation()
    # 16:9 widescreen dimensions
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6]

    for index, slide_data in enumerate(norm_slides, 1):
        slide = prs.slides.add_slide(blank_layout)

        # 1. Top accent bar
        try:
            accent_bar = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Inches(0), Inches(0), Inches(13.333), Inches(0.12),
            )
            accent_bar.fill.solid()
            accent_bar.fill.fore_color.rgb = RGBColor(30, 58, 138)  # Deep blue #1E3A8A
            accent_bar.line.fill.background()
        except (AttributeError, ValueError, TypeError) as exc:
            logger.debug("PPTX accent bar could not be styled: %s", exc)

        # 2. Slide Title
        title_box = slide.shapes.add_textbox(Inches(0.9), Inches(0.6), Inches(11.533), Inches(1.1))
        tf_title = title_box.text_frame
        tf_title.word_wrap = True
        p_title = tf_title.paragraphs[0]
        p_title.text = slide_data.title
        p_title.font.size = Pt(26)
        p_title.font.bold = True
        p_title.font.color.rgb = RGBColor(15, 23, 42)  # Slate-900

        # 3. Content Bullet Points
        content_box = slide.shapes.add_textbox(Inches(0.9), Inches(1.9), Inches(11.533), Inches(4.3))
        tf_content = content_box.text_frame
        tf_content.word_wrap = True

        for b_idx, bullet in enumerate(slide_data.bullet_points):
            p = tf_content.paragraphs[0] if b_idx == 0 else tf_content.add_paragraph()
            p.text = f"•  {bullet}"
            p.font.size = Pt(17)
            p.font.color.rgb = RGBColor(51, 65, 85)  # Slate-700
            p.space_after = Pt(14)

        # 4. Footer: Source pages & slide number
        footer_box = slide.shapes.add_textbox(Inches(0.9), Inches(6.5), Inches(11.533), Inches(0.5))
        tf_footer = footer_box.text_frame
        p_footer = tf_footer.paragraphs[0]
        p_footer.font.size = Pt(10)
        p_footer.font.color.rgb = RGBColor(100, 116, 139)  # Slate-500

        source_text = ""
        if slide_data.source_pages:
            pages_str = ", ".join(str(p) for p in slide_data.source_pages)
            source_text = f"Kaynak Sayfalar: {pages_str}"

        p_footer.text = f"{source_text}{'  |  ' if source_text else ''}PDFAura • Slayt {index} / {len(norm_slides)}"

    prs.save(str(target))
    return str(target)


# ── Export PDF Slides (16:9 Landscape) ──────────────────────────────────────

def export_pdf_slides(
    slides: Sequence[Slide | dict[str, Any]],
    path: str | os.PathLike,
) -> str:
    if "\x00" in str(path):
        raise ValueError("Path contains invalid null character")
    """Export slides to a 16:9 landscape PDF presentation using PyMuPDF.

    Args:
        slides: Sequence of Slide objects or slide dictionaries.
        path: Output PDF file path.

    Returns:
        The output path string.
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) kurulu değil; PDF slayt dışa aktarma devre dışı.")

    norm_slides = [_normalize_slide(s) for s in slides]
    if not norm_slides:
        raise ValueError("Dışa aktarılacak slayt bulunamadı.")

    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    # 16:9 landscape slide dimensions in points (960 x 540)
    slide_width = 960.0
    slide_height = 540.0
    margin_x = 55.0

    font_path = _find_system_turkish_font()
    has_custom_font = bool(font_path)

    doc = fitz.open()
    try:
        total_slides = len(norm_slides)
        for index, slide_data in enumerate(norm_slides, 1):
            page = doc.new_page(width=slide_width, height=slide_height)

            font_name = "f0" if has_custom_font else "helv"
            if has_custom_font:
                page.insert_font(fontname=font_name, fontfile=font_path, set_simple=False)

            # Top accent bar (Navy / Blue)
            page.draw_rect(fitz.Rect(0, 0, slide_width, 8), fill=(0.12, 0.23, 0.54), color=None)

            # Header brand tag
            header_text = "PDFAura • Sunum Taslağı"
            if not has_custom_font:
                header_text = header_text.translate(_ASCII_TRANSLATION)
            page.insert_text(
                (margin_x, 34),
                header_text,
                fontname=font_name,
                fontsize=8.5,
                color=(0.50, 0.55, 0.62),
            )

            # Slide Title
            title_text = slide_data.title
            if not has_custom_font:
                title_text = title_text.translate(_ASCII_TRANSLATION)
            page.insert_text(
                (margin_x, 68),
                title_text,
                fontname=font_name,
                fontsize=21.0,
                color=(0.06, 0.10, 0.22),
            )

            # Title separator line
            page.draw_line(
                fitz.Point(margin_x, 82),
                fitz.Point(slide_width - margin_x, 82),
                color=(0.86, 0.89, 0.93),
                width=0.8,
            )

            # Render bullet points
            current_y = 125.0
            line_height = 19.0
            bullet_max_width = slide_width - (margin_x * 2) - 30.0

            for bullet in slide_data.bullet_points:
                b_text = bullet.strip()
                if not has_custom_font:
                    b_text = b_text.translate(_ASCII_TRANSLATION)

                # Word wrap bullet text
                words = b_text.split()
                lines: list[str] = []
                current_line = ""
                for word in words:
                    cand = f"{current_line} {word}".strip()
                    # Estimate width based on character length * font size * ratio
                    cand_width = len(cand) * 13.5 * 0.50
                    if cand_width <= bullet_max_width:
                        current_line = cand
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                if current_line:
                    lines.append(current_line)

                # Bullet symbol dot
                page.draw_circle(
                    fitz.Point(margin_x + 8, current_y - 4),
                    radius=2.6,
                    fill=(0.15, 0.35, 0.68),
                    color=None,
                )

                for l_idx, line in enumerate(lines):
                    if current_y > slide_height - 60:
                        break
                    page.insert_text(
                        (margin_x + 22, current_y),
                        line,
                        fontname=font_name,
                        fontsize=13.5,
                        color=(0.20, 0.25, 0.32),
                    )
                    current_y += line_height
                current_y += 10.0  # Spacing between bullet points

            # Footer separator line
            page.draw_line(
                fitz.Point(margin_x, slide_height - 38),
                fitz.Point(slide_width - margin_x, slide_height - 38),
                color=(0.88, 0.90, 0.94),
                width=0.6,
            )

            # Footer left: Source pages
            source_pages = slide_data.source_pages
            if source_pages:
                pages_str = ", ".join(str(p) for p in source_pages)
                src_label = f"Kaynak Sayfalar: {pages_str}"
            else:
                src_label = "Genel Belge"
            if not has_custom_font:
                src_label = src_label.translate(_ASCII_TRANSLATION)

            page.insert_text(
                (margin_x, slide_height - 20),
                src_label,
                fontname=font_name,
                fontsize=9.0,
                color=(0.50, 0.55, 0.62),
            )

            # Footer right: Slide number
            slide_no_text = f"Slayt {index} / {total_slides}"
            page.insert_text(
                (slide_width - margin_x - 70, slide_height - 20),
                slide_no_text,
                fontname=font_name,
                fontsize=9.0,
                color=(0.50, 0.55, 0.62),
            )

        doc.save(str(target), deflate=True, garbage=3)
    finally:
        doc.close()

    return str(target)
