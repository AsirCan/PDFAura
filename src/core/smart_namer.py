"""Smart document naming and folder organization for PDF Aura.

Extracts key metadata (document_type, date, subject/entity) from the first page
of a PDF using robust regex and date heuristics with an optional local LLM fallback,
generates sanitized filename suggestions based on customizable templates,
and provides batch rename planning with collision resolution and folder organization.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Canonical document types
DOCUMENT_TYPES = ("fatura", "dekont", "sozlesme", "rapor", "odev", "diger")

# Reserved filenames on Windows
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
    *(f"COM{n}" for n in range(0, 10)),
    *(f"LPT{n}" for n in range(0, 10)),
}

# Illegal characters in Windows filenames
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Month names mapping for Turkish and English
_MONTH_NAMES: dict[str, int] = {
    # Turkish
    "ocak": 1, "subat": 2, "mart": 3, "nisan": 4, "mayis": 5, "haziran": 6,
    "temmuz": 7, "agustos": 8, "eylul": 9, "ekim": 10, "kasim": 11, "aralik": 12,
    # English
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6,
    "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

# Known subject keywords by category for entity/subject heuristics
_KNOWN_SUBJECTS = (
    # Academic / Courses
    "Matematik", "Fizik", "Kimya", "Biyoloji", "Geometri", "Tarih", "Cografya",
    "Coğrafya", "Edebiyat", "Turkce", "Türkçe", "Ingilizce", "İngilizce",
    "Almanca", "Fransizca", "Fransızca", "Felsefe", "Bilgisayar", "Algoritma",
    "Yazilim", "Yazılım", "Programlama", "Veritabani", "Veritabanı",
    "Istatistik", "İstatistik", "Ekonomi", "Iktisat", "İktisat", "Isletme",
    "İşletme", "Muhasebe", "Hukuk", "Tip", "Tıp", "Anatomi", "Psikoloji",
    "Sosyoloji",
    # Utilities & Bills
    "Elektrik", "Dogalgaz", "Doğalgaz", "Su", "Internet", "İnternet", "Telefon",
    "Aidat", "Kira", "Sigorta", "Kasko",
    # Service providers & Banks
    "Enerjisa", "Bedas", "BEDAŞ", "Igdas", "İGDAŞ", "Iski", "İSKİ",
    "Turkcell", "Vodafone", "Turk Telekom", "Türk Telekom",
    "Garanti", "Garanti BBVA", "Ziraat", "Ziraat Bankasi", "Yapi Kredi", "Yapı Kredi",
    "Is Bankasi", "İş Bankası", "Akbank", "QNB", "Enpara", "Vakifbank", "Vakıfbank",
    "Amazon", "Trendyol", "Hepsiburada", "Google", "Apple", "Microsoft",
    # Report Topics
    "Finansal", "Faaliyet", "Denetim", "Pazarlama", "Satis", "Satış", "Ar-Ge",
    "Yillik", "Yıllık", "Aylik", "Aylık", "Surdurulebilirlik", "Sürdürülebilirlik",
)


def _normalize_text(text: str) -> str:
    """Normalize whitespace, soft hyphens, and Unicode characters."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xa0", " ").replace("\u202f", " ")
    text = text.replace("\xad", "-")
    for dash in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        text = text.replace(dash, "-")
    return text.strip()


def _to_ascii_lower(text: str) -> str:
    """Normalize text to lowercase ASCII, handling Turkish dotted/dotless I."""
    if not text:
        return ""
    text = _normalize_text(text)
    text = text.replace("İ", "i").replace("I", "i").lower()
    tr_map = str.maketrans({
        "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
    })
    return text.translate(tr_map)


def extract_first_page_text(pdf_path: str | os.PathLike) -> str:
    """Extract plain text from the first page of *pdf_path*.
    if "\x00" in str(pdf_path):
        return ""

    Tries PyMuPDF (fitz) first, falls back to pypdf, and degrades gracefully
    to an OCR extraction or empty string if no digital text is found.
    """
    path_str = str(pdf_path)

    # 1. Try PyMuPDF (fitz)
    try:
        import fitz
        doc = fitz.open(path_str)
        try:
            if doc.page_count > 0:
                raw_text = doc[0].get_text() or ""
                normalized = _normalize_text(raw_text)
                if normalized:
                    return normalized
        finally:
            doc.close()
    except Exception as exc:
        logger.debug("fitz text extraction failed on %s: %s", path_str, exc)

    # 2. Try pypdf
    try:
        from pypdf import PdfReader
        with open(path_str, "rb") as fh:
            reader = PdfReader(fh)
            if len(reader.pages) > 0:
                raw_text = reader.pages[0].extract_text() or ""
                normalized = _normalize_text(raw_text)
                if normalized:
                    return normalized
    except Exception as exc:
        logger.debug("pypdf text extraction failed on %s: %s", path_str, exc)

    # 3. Try document_loader OCR fallback
    try:
        from src.ai.document_loader import extract_pages
        pages = extract_pages(path_str, use_ocr=True)
        if pages and pages[0].text.strip():
            return _normalize_text(pages[0].text)
    except Exception as exc:
        logger.debug("OCR text extraction fallback failed on %s: %s", path_str, exc)

    return ""


def _classify_document_type(text: str) -> str:
    """Classify the document into one of DOCUMENT_TYPES based on text heuristics."""
    if not text:
        return "diger"

    norm = _to_ascii_lower(text)

    # Weighted keywords for each category
    scores: dict[str, int] = {k: 0 for k in DOCUMENT_TYPES}

    # Fatura patterns
    fatura_rules = [
        (r"\b(e-fatura|efatura|e-arsiv|earsiv)\b", 8),
        (r"\bfatura\s+tarihi\b", 7),
        (r"\bfatura\s+no\b", 7),
        (r"\bvergi\s+(kimlik|dairesi|no)\b|\bvkn\b", 5),
        (r"\bodenecek\s+tutar\b|\btoplam\s+tutar\b", 4),
        (r"\bkdv\b", 3),
        (r"\bfatura\w*\b", 5),
        (r"\btax\s+invoice\b", 7),
        (r"\binvoice\b", 5),
        (r"\bbill\s+to\b", 4),
        (r"\birsaliye\b", 3),
    ]
    for pattern, weight in fatura_rules:
        if re.search(pattern, norm):
            scores["fatura"] += weight

    # Dekont patterns
    dekont_rules = [
        (r"\b(islem|odeme|transfer)\s+dekont\w*\b", 8),
        (r"\bdekont\w*\b", 6),
        (r"\b(tahsilat|tediye)\s+makbuz\w*\b", 7),
        (r"\bmakbuz\w*\b", 5),
        (r"\bhesap\s+ozeti\b", 5),
        (r"\bpara\s+transferi\b|\beft\b|\bhavale\b|\bfast\s+islemi\b", 5),
        (r"\b(gonderen|alici)\s+iban\b", 5),
        (r"\bdekont\s+no\b|\bislem\s+no\b", 5),
        (r"\btransfer\s+receipt\b|\bbank\s+statement\b", 7),
        (r"\breceipt\b", 3),
    ]
    for pattern, weight in dekont_rules:
        if re.search(pattern, norm):
            scores["dekont"] += weight

    # Sozlesme patterns
    sozlesme_rules = [
        (r"\b(kira|hizmet|is|gizlilik|satis|alimsatim)\s+sozlesme\w*\b", 8),
        (r"\bsozlesme\w*\b|\bmukavele\b", 6),
        (r"\bsozlesme\s+tarihi\b", 6),
        (r"\bakdedilmistir\b|\btaraflar\b", 4),
        (r"\bmadde\s+[0-9]+\b", 3),
        (r"\bimza\s+sirkuleri\b|\btaahhutname\b", 5),
        (r"\b(lease|service|employment|non-disclosure)\s+agreement\b", 8),
        (r"\bcontract\b|\bagreement\b|\bnda\b", 5),
    ]
    for pattern, weight in sozlesme_rules:
        if re.search(pattern, norm):
            scores["sozlesme"] += weight

    # Rapor patterns
    rapor_rules = [
        (r"\b(faaliyet|denetim|finansal|analiz|durum|aylik|yillik|arastirma|ekspertiz|degerlendirme)\s+rapor\w*\b", 8),
        (r"\brapor\w*\b", 5),
        (r"\brapor\s+tarihi\b", 6),
        (r"\b(annual|financial|audit|status|progress|analysis)\s+report\b", 8),
        (r"\breport\b", 5),
    ]
    for pattern, weight in rapor_rules:
        if re.search(pattern, norm):
            scores["rapor"] += weight

    # Odev patterns
    odev_rules = [
        (r"\b(proje|ders|donem|ev)\s+odev\w*\b", 8),
        (r"\bodev\w*\b", 6),
        (r"\bhomework\b|\bassignment\b", 6),
        (r"\bogrenci\s+no\b|\bogrenci\s+numarasi\b", 5),
        (r"\bders\s+notu\b|\balistirma\b|\bsoru\s+[0-9]+\b", 4),
        (r"\bvize\b|\bfinal\s+sinavi\b", 4),
        (r"\bcoursework\b|\bsyllabus\b", 5),
    ]
    for pattern, weight in odev_rules:
        if re.search(pattern, norm):
            scores["odev"] += weight

    best_type = max(scores, key=lambda k: scores[k])
    if scores[best_type] > 0:
        return best_type
    return "diger"


def _parse_date_components(year: int, month: int, day: int) -> str:
    """Format validated year, month, day as YYYY-MM-DD or empty string."""
    try:
        if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
    except (TypeError, ValueError):
        pass
    return ""


def _extract_date_from_text(text: str) -> str:
    """Extract a date formatted as YYYY-MM-DD from the text using heuristics."""
    if not text:
        return ""

    clean_text = _normalize_text(text)

    # Priority 1: Labeled date lines
    labeled_patterns = [
        r"(?i)(?:[a-zçğıöşü]+\s+)?(?:tarih(?:i)?|date)\s*[:\-]?\s*([^\n\r]+)",
    ]
    for pattern in labeled_patterns:
        match = re.search(pattern, clean_text)
        if match:
            candidate = match.group(1).strip()
            date_found = _parse_single_date_candidate(candidate)
            if date_found:
                return date_found

    # Priority 2: Standard ISO dates YYYY-MM-DD anywhere in text
    iso_match = re.search(r"\b(19\d\d|20\d\d)[.\-\/](0?[1-9]|1[0-2])[.\-\/](0?[1-9]|[12]\d|3[01])\b", clean_text)
    if iso_match:
        y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        res = _parse_date_components(y, m, d)
        if res:
            return res

    # Priority 3: DD.MM.YYYY dates
    dmy_match = re.search(r"\b(0?[1-9]|[12]\d|3[01])[.\-\/](0?[1-9]|1[0-2])[.\-\/](19\d\d|20\d\d)\b", clean_text)
    if dmy_match:
        d, m, y = int(dmy_match.group(1)), int(dmy_match.group(2)), int(dmy_match.group(3))
        res = _parse_date_components(y, m, d)
        if res:
            return res

    # Priority 4: Textual dates e.g. "16 Mayıs 2026", "16 May 2026"
    norm_text = _to_ascii_lower(clean_text)
    text_date_match = re.search(r"\b(0?[1-9]|[12]\d|3[01])\s+([a-z]+)\s+(19\d\d|20\d\d)\b", norm_text)
    if text_date_match:
        d = int(text_date_match.group(1))
        month_str = text_date_match.group(2)
        y = int(text_date_match.group(3))
        if month_str in _MONTH_NAMES:
            m = _MONTH_NAMES[month_str]
            res = _parse_date_components(y, m, d)
            if res:
                return res

    # Priority 5: Month-Year without day e.g. "Nisan 2026" -> defaults to 1st of month
    my_match = re.search(r"\b([a-z]+)\s+(19\d\d|20\d\d)\b", norm_text)
    if my_match:
        month_str = my_match.group(1)
        y = int(my_match.group(2))
        if month_str in _MONTH_NAMES:
            m = _MONTH_NAMES[month_str]
            res = _parse_date_components(y, m, 1)
            if res:
                return res

    return ""


def _parse_single_date_candidate(candidate: str) -> str:
    """Attempt to parse a specific candidate date string."""
    if not candidate:
        return ""

    clean_cand = _normalize_text(candidate)

    # Check numeric YYYY-MM-DD
    iso = re.search(r"\b(19\d\d|20\d\d)[.\-\/](0?[1-9]|1[0-2])[.\-\/](0?[1-9]|[12]\d|3[01])\b", clean_cand)
    if iso:
        return _parse_date_components(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))

    # Check numeric DD.MM.YYYY
    dmy = re.search(r"\b(0?[1-9]|[12]\d|3[01])[.\-\/](0?[1-9]|1[0-2])[.\-\/](19\d\d|20\d\d)\b", clean_cand)
    if dmy:
        return _parse_date_components(int(dmy.group(3)), int(dmy.group(2)), int(dmy.group(1)))

    # Check textual date
    cand_norm = _to_ascii_lower(clean_cand)
    tm = re.search(r"\b(0?[1-9]|[12]\d|3[01])\s+([a-z]+)\s+(19\d\d|20\d\d)\b", cand_norm)
    if tm and tm.group(2) in _MONTH_NAMES:
        return _parse_date_components(int(tm.group(3)), _MONTH_NAMES[tm.group(2)], int(tm.group(1)))

    # Optional dateutil fallback
    try:
        from dateutil import parser
        parsed = parser.parse(clean_cand, dayfirst=False if re.search(r"[a-zA-Z]", clean_cand) else True, fuzzy=True)
        return _parse_date_components(parsed.year, parsed.month, parsed.day)
    except Exception:
        pass

    return ""


def _clean_subject_candidate(val: str) -> str:
    """Clean and strip punctuation from a subject candidate string."""
    if not val:
        return ""
    val = re.sub(r'[\r\n\t]+', ' ', val)
    val = val.strip(" :-\t\r\n.,;\"'()[]{}")
    words = val.split()
    if len(words) > 4:
        val = " ".join(words[:4])
    return val[:40].strip()


def _extract_subject_from_text(text: str, doc_type: str = "diger") -> str:
    """Extract subject or entity name from first page text using high-confidence heuristics."""
    if not text:
        return ""

    norm = _to_ascii_lower(text)

    # 1. Primary labeled topic patterns (e.g. Konu: ..., Ders: ..., Açıklama: ...)
    primary_topic_patterns = [
        r'(?i)(?:konu(?:su)?|ders(?:in\s+adı)?|subject|topic)\s*[:\-]\s*([^\n\r,;]+)',
        r'(?i)(?:açıklama|aciklama|description)\s*[:\-]\s*([^\n\r,;]+)',
    ]
    for pattern in primary_topic_patterns:
        match = re.search(pattern, text)
        if match:
            cleaned = _clean_subject_candidate(match.group(1))
            cleaned_norm = _to_ascii_lower(cleaned)
            if cleaned and len(cleaned) > 1 and not cleaned.isdigit() and cleaned_norm not in ("tarih", "date"):
                return cleaned

    # 2. Known domain subjects (courses for odev, utilities for fatura)
    # Exclude "tarih" if followed by colon (date label)
    for kw in _KNOWN_SUBJECTS:
        kw_norm = _to_ascii_lower(kw)
        pattern = rf"\b{re.escape(kw_norm)}\b(?!\s*[:\-])"
        if re.search(pattern, norm):
            return kw

    # 3. Check entity / person labels
    entity_patterns = [
        # Person / Student
        r'(?i)(?:öğrenci(?:nin\s+adı)?|ogrenci(?:nin\s+adi)?|student)\s*[:\-]\s*([^\n\r,;]+)',
        # Tenant / Landlord (contracts)
        r'(?i)(?:kiracı|kiraci|kiraya\s+veren|tenant|landlord)\s*[:\-]\s*([^\n\r,;]+)',
        # Recipient / Customer
        r'(?i)(?:alıcı|alici|müşteri|musteri|sayın|sayin|recipient|customer|buyer)\s*[:\-]\s*([^\n\r,;]+)',
        # Sender / Vendor
        r'(?i)(?:gönderen|gonderen|satıcı|satici|seller|vendor|sender)\s*[:\-]\s*([^\n\r,;]+)',
        # Name Surname
        r'(?i)(?:adı\s+soyadı|adi\s+soyadi|ad\s+soyad|full\s*name)\s*[:\-]\s*([^\n\r,;]+)',
        # Company / Institution
        r'(?i)(?:kurum|firma|şirket|sirket|unvan(?:ı)?|company)\s*[:\-]\s*([^\n\r,;]+)',
    ]
    for pattern in entity_patterns:
        match = re.search(pattern, text)
        if match:
            cleaned = _clean_subject_candidate(match.group(1))
            cleaned_norm = _to_ascii_lower(cleaned)
            if cleaned and len(cleaned) > 1 and not cleaned.isdigit() and cleaned_norm not in ("tarih", "date"):
                return cleaned

    return ""


def _extract_header_fallback(text: str) -> str:
    """Document header fallback: look for first substantive line of text."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    skip_exact = {
        "fatura", "dekont", "sozlesme", "sözleşme", "rapor", "odev", "ödev",
        "invoice", "receipt", "contract", "report", "homework", "pdf",
        "tarih", "date",
    }
    for line in lines[:5]:
        cleaned = _clean_subject_candidate(line)
        cleaned_norm = _to_ascii_lower(cleaned)
        if cleaned and len(cleaned) > 2 and cleaned_norm not in skip_exact and not cleaned.isdigit():
            if not re.search(r"^\d{1,4}[.\-\/]\d{1,2}", cleaned):
                return cleaned
    return ""


def _extract_with_local_llm(text: str) -> dict[str, str] | None:
    """Optional local LLM fallback to extract metadata when heuristics are uncertain."""
    try:
        from src.ai.local_llm import LocalLLM
        llm = LocalLLM()
        if not llm.available or not llm.runtime_available:
            return None

        prompt = (
            "Aşağıdaki belge metninden belge türünü (fatura, dekont, sozlesme, rapor, odev, diger), "
            "tarihi (YYYY-MM-DD) ve konu/kişi/kurum adını (subject) JSON formatında çıkar.\n"
            "Sadece JSON nesnesi döndür:\n"
            '{"document_type": "...", "date": "...", "subject": "..."}\n\n'
            f"Metin:\n{text[:1200]}\n\nJSON:"
        )
        response = llm.generate(prompt, max_tokens=100, temperature=0.0)
        if not response:
            return None

        import json
        match = re.search(r"\{[^{}]*\}", response)
        if match:
            data = json.loads(match.group(0))
            return {
                "document_type": str(data.get("document_type", "")).strip().lower(),
                "date": str(data.get("date", "")).strip(),
                "subject": str(data.get("subject", "")).strip(),
            }
    except Exception as exc:
        logger.debug("Local LLM metadata fallback failed: %s", exc)

    return None


def extract_metadata_fields(pdf_path: str | os.PathLike) -> dict[str, Any]:
    """Extract document_type, date, and entity/subject from the first page of *pdf_path*.

    Returns a dict with:
      - ``document_type``: one of 'fatura', 'dekont', 'sozlesme', 'rapor', 'odev', 'diger'
      - ``type``: alias for document_type
      - ``date``: YYYY-MM-DD or empty string
      - ``subject``: entity or topic string
      - ``entity``: alias for subject
    """
    text = extract_first_page_text(pdf_path)

    # Heuristic extraction
    doc_type = _classify_document_type(text)
    date_str = _extract_date_from_text(text)
    subject_str = _extract_subject_from_text(text, doc_type)

    # Optional Local LLM fallback if any field is missing or unclassified
    if (doc_type == "diger" or not date_str or not subject_str) and text:
        llm_data = _extract_with_local_llm(text)
        if llm_data:
            if doc_type == "diger" and llm_data.get("document_type") in DOCUMENT_TYPES:
                doc_type = llm_data["document_type"]
            if not date_str and llm_data.get("date"):
                parsed_d = _parse_single_date_candidate(llm_data["date"])
                if parsed_d:
                    date_str = parsed_d
            if llm_data.get("subject"):
                subject_str = _clean_subject_candidate(llm_data["subject"])

    # Fallback for subject: header line
    if not subject_str and text:
        subject_str = _extract_header_fallback(text)

    # Ensure doc_type is valid
    if doc_type not in DOCUMENT_TYPES:
        doc_type = "diger"

    return {
        "document_type": doc_type,
        "type": doc_type,
        "date": date_str,
        "subject": subject_str,
        "entity": subject_str,
    }


def sanitize_filename(name: str, fallback: str = "belge.pdf") -> str:
    """Sanitize a filename for filesystem safety on Windows and cross-platform."""
    if name.lower().endswith(".pdf"):
        stem = name[:-4]
    else:
        stem = name

    # Replace invalid chars with underscore
    stem = _INVALID_CHARS.sub("_", stem)

    # Collapse multiple consecutive underscores, dashes, spaces
    stem = re.sub(r"_{2,}", "_", stem)
    stem = re.sub(r"-{2,}", "-", stem)
    stem = re.sub(r"\s+", " ", stem)
    stem = re.sub(r"[-_]*[-_]", lambda m: "_" if "_" in m.group(0) else "-", stem)

    # Strip leading and trailing punctuation and spaces
    stem = stem.strip(" .-_")

    # Prevent directory traversal dots
    stem = re.sub(r"\.{2,}", ".", stem).strip(" .-_")

    # Limit filename length to prevent OS filesystem limits
    if len(stem) > 200:
        stem = stem[:200].rstrip(" .-_")

    # Guard against empty names and Windows reserved names
    check_stem = stem.split(".")[0].rstrip().upper()
    if not stem or check_stem in _RESERVED_NAMES:
        fallback_stem = fallback[:-4] if fallback.lower().endswith(".pdf") else fallback
        stem = fallback_stem

    return f"{stem}.pdf"


def suggest_filename(
    pdf_path: str | os.PathLike,
    template: str = "{belge_turu}_{tarih}_{konu}",
    *,
    metadata: dict[str, Any] | None = None,
    ascii_only: bool = False,
) -> str:
    """Suggest a sanitized filename using the specified *template*.

    Recognized template placeholders (case-insensitive):
      - ``{belge_turu}`` / ``{document_type}`` / ``{type}``
      - ``{tarih}`` / ``{date}``
      - ``{konu}`` / ``{subject}`` / ``{entity}``
      - ``{orijinal_ad}`` / ``{original_name}`` / ``{stem}``
    """
    if metadata is None:
        metadata = extract_metadata_fields(pdf_path)

    doc_type = metadata.get("document_type") or metadata.get("type") or "diger"
    date_val = metadata.get("date") or ""
    subject_val = metadata.get("subject") or metadata.get("entity") or ""

    orig_stem = ""
    if pdf_path:
        orig_stem = Path(pdf_path).stem

    # Prepare subject: replace spaces with underscores for clean formatting
    clean_subj = subject_val.replace(" ", "_").strip(" .-_")

    if ascii_only:
        clean_subj = _to_ascii_lower(clean_subj)
        orig_stem = _to_ascii_lower(orig_stem)

    # Token mapper supporting case variations (Upper, Title, Lower)
    def replace_token(match: re.Match) -> str:
        token_name = match.group(1).strip()
        norm_token = _to_ascii_lower(token_name)

        if norm_token in ("belge_turu", "belgeturu", "document_type", "type", "tur", "tür"):
            val = doc_type
        elif norm_token in ("tarih", "date"):
            val = date_val
        elif norm_token in ("konu", "subject", "entity", "kisi", "kurum"):
            val = clean_subj
        elif norm_token in ("orijinal_ad", "orijinalad", "original_name", "stem"):
            val = orig_stem
        else:
            return match.group(0)

        # Apply casing
        if token_name.isupper():
            val = val.upper()
        elif token_name.istitle() or (token_name and token_name[0].isupper()):
            val = val.capitalize()
        return val

    result = re.sub(r"\{([^{}]+)\}", replace_token, template)

    # Sanitize and finalize extension
    fallback_name = f"{doc_type}.pdf" if doc_type != "diger" else (f"{orig_stem}.pdf" if orig_stem else "belge.pdf")
    return sanitize_filename(result, fallback=fallback_name)


def plan_batch_rename(
    folder_or_files: str | os.PathLike | Iterable[str | os.PathLike],
    template: str = "{belge_turu}_{tarih}_{konu}",
    *,
    organize_folders: bool = False,
    output_folder: str | os.PathLike | None = None,
    recursive: bool = False,
) -> list[dict[str, Any]]:
    if output_folder and "\x00" in str(output_folder):
        raise ValueError("output_folder contains invalid null character")
    if isinstance(folder_or_files, (str, os.PathLike, Path)) and "\x00" in str(folder_or_files):
        return []
    """Generate a batch rename plan with collision resolution and optional subfolder organization.

    Returns a list of dicts:
      ``{old_path, new_path, type, date, subject, collision_resolved}``
    """
    file_list: list[str] = []

    # Check if folder_or_files is a directory
    if isinstance(folder_or_files, (str, os.PathLike, Path)):
        p = Path(folder_or_files)
        if p.is_dir():
            if recursive:
                for root, _, files in os.walk(p):
                    for f in sorted(files):
                        if f.lower().endswith(".pdf"):
                            file_list.append(os.path.abspath(os.path.join(root, f)))
            else:
                for entry in sorted(os.listdir(p)):
                    full_p = p / entry
                    if full_p.is_file() and entry.lower().endswith(".pdf"):
                        file_list.append(os.path.abspath(str(full_p)))
        elif p.is_file():
            file_list.append(os.path.abspath(str(p)))
    else:
        for item in folder_or_files:
            file_list.append(os.path.abspath(str(item)))

    plan: list[dict[str, Any]] = []
    taken_paths: set[str] = set()

    for old_path in file_list:
        meta = extract_metadata_fields(old_path)
        doc_type = meta.get("document_type") or meta.get("type") or "diger"
        date_str = meta.get("date") or ""
        subject_str = meta.get("subject") or meta.get("entity") or ""

        # Determine target directory
        if output_folder:
            base_dir = os.path.abspath(str(output_folder))
        else:
            base_dir = os.path.dirname(old_path)

        if organize_folders:
            target_dir = os.path.join(base_dir, doc_type)
        else:
            target_dir = base_dir

        suggested_name = suggest_filename(old_path, template=template, metadata=meta)
        target_path = os.path.join(target_dir, suggested_name)

        # Collision resolution:
        # A collision occurs if target_path was already claimed in this batch (taken_paths),
        # or if target_path already exists on disk and is a DIFFERENT file from old_path.
        norm_target = os.path.normcase(os.path.abspath(target_path))
        norm_old = os.path.normcase(os.path.abspath(old_path))

        collision = (norm_target in taken_paths) or (os.path.exists(target_path) and norm_target != norm_old)
        collision_resolved = False

        if collision:
            stem, ext = os.path.splitext(suggested_name)
            counter = 2
            while True:
                candidate_name = f"{stem} ({counter}){ext}"
                candidate_path = os.path.join(target_dir, candidate_name)
                norm_cand = os.path.normcase(os.path.abspath(candidate_path))
                if norm_cand not in taken_paths and (not os.path.exists(candidate_path) or norm_cand == norm_old):
                    target_path = candidate_path
                    collision_resolved = True
                    break
                counter += 1

        taken_paths.add(os.path.normcase(os.path.abspath(target_path)))

        plan.append({
            "old_path": old_path,
            "new_path": target_path,
            "type": doc_type,
            "document_type": doc_type,
            "date": date_str,
            "subject": subject_str,
            "entity": subject_str,
            "collision_resolved": collision_resolved,
        })

    return plan


def apply_batch_rename(
    plan: list[dict[str, Any]],
    organize_folders: bool = False,
    output_folder: str | os.PathLike | None = None,
) -> list[dict[str, Any]]:
    """Apply the batch rename plan, creating subfolders as needed.

    Returns the list of applied plan items with execution status.
    """
    results: list[dict[str, Any]] = []

    for item in plan:
        res = dict(item)
        try:
            if "\x00" in str(item.get("old_path", "")) or "\x00" in str(item.get("new_path", "")):
                raise ValueError("Path contains invalid null character")
            old_path = os.path.abspath(str(item["old_path"]))
            new_path = os.path.abspath(str(item["new_path"]))
            raw_doc_type = str(item.get("type") or item.get("document_type") or "diger")
            doc_type = raw_doc_type if raw_doc_type in DOCUMENT_TYPES else "diger"

            # If override output_folder or organize_folders was requested at apply time
            if output_folder:
                dest_dir = os.path.abspath(str(output_folder))
                if organize_folders:
                    dest_dir = os.path.join(dest_dir, doc_type)
                safe_basename = sanitize_filename(os.path.basename(new_path))
                new_path = os.path.join(dest_dir, safe_basename)
                norm_dest = os.path.normcase(dest_dir)
                norm_new = os.path.normcase(new_path)
                if not norm_new.startswith(norm_dest + os.sep) and norm_new != norm_dest:
                    res["success"] = False
                    res["error"] = "Path traversal detected"
                    results.append(res)
                    continue
            elif organize_folders:
                curr_dir = os.path.dirname(new_path)
                if os.path.basename(curr_dir) != doc_type:
                    dest_dir = os.path.join(curr_dir, doc_type)
                    safe_basename = sanitize_filename(os.path.basename(new_path))
                    new_path = os.path.join(dest_dir, safe_basename)

            res["applied_path"] = new_path

            if not os.path.isfile(old_path):
                raise FileNotFoundError(f"Source file not found: {old_path}")
            norm_old = os.path.normcase(old_path)
            norm_new = os.path.normcase(new_path)

            if norm_old != norm_new:
                target_dir = os.path.dirname(new_path)
                if target_dir:
                    os.makedirs(target_dir, exist_ok=True)
                shutil.move(old_path, new_path)

            res["success"] = True
            res["error"] = None
        except Exception as exc:
            logger.error("Failed to rename %s to %s: %s", item.get("old_path"), item.get("new_path"), exc)
            res["success"] = False
            res["error"] = str(exc)

        results.append(res)

    return results
