"""Turn a spoken or typed command into an action chain for the ActionRunner.

The order of work matters and is the fix for most of issue #9: file names are
extracted *first* and then removed from the text, so keyword and number
matching never sees them. Otherwise "herkes.pdf" matched "kes" (split),
"rapor_5.pdf" contributed page 5 to a delete, and "bir.pdf" was rewritten to
"1.pdf" by the Turkish number normaliser.
"""
import json
import logging
import os
import re

logger = logging.getLogger(__name__)

# Whisper Türkçe yazı-rakam dönüşüm tablosu

ENGLISH_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

TURKISH_NUMBERS = {
    "bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5,
    "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10,
    "yirmi": 20, "otuz": 30, "kırk": 40, "elli": 50,
    "altmış": 60, "yetmiş": 70, "seksen": 80, "doksan": 90,
    "yüz": 100,
}

# Folders we are willing to look in for a name given without an extension.
SEARCH_FOLDERS = ("Desktop", "Documents", "Downloads")

_TR_CHARS = "a-zA-ZçğıöşüÇĞİÖŞÜ"

# Keywords are matched at a word start (\b...) so "herkes" does not contain
# "kes", and "silme" does not fire on an unrelated "sil".
KEYWORDS = {
    "split":        [r"\bkes\b", r"\bkes[a-zçğıöşü]*", r"\bböl\b", r"\bböl[a-zçğıöşü]*",
                     r"\bbol\b", r"\bbol[a-zçğıöşü]*", r"\bayır\b", r"\bayir\b",
                     r"\bayır[a-zçğıöşü]*", r"\bayir[a-zçğıöşü]*", r"\bsplit\b",
                     r"\bextract\b", r"\bdivide\b", r"\bcut\b", r"\bseparate\b"],
    "merge":        [r"\bbirleştir", r"\bbirlestir", r"\bmerge\b", r"\bcombine\b",
                     r"\b(?:bir|1)?\s*araya\s*getir\b", r"\bjoin\b", r"\bconcatenate\b"],
    "compress":     [r"\bsıkıştır", r"\bsikistir", r"\bküçült", r"\bkucult", r"\bkompres",
                     r"\bcompress\b", r"\bshrink\b",
                     r"\bboyutun?u\s*(?:düşür|dusur|azalt|küçült|kucult)",
                     r"\breduce\s+(?:file\s+)?size\b", r"\bmake\s+(?:it\s+)?smaller\b"],
    "encrypt":      [r"\bşifrele", r"\bsifrele", r"\bparola", r"\b[şs]ifre\s*ekle",
                     r"\bparola\s*ekle", r"\b[şs]ifre\s*koy", r"\bparola\s*koy",
                     r"\bkoru\b", r"\bkilitle", r"\bencrypt", r"\bpassword", r"\bprotect",
                     r"\block\b"],
    "watermark":    [r"\bfiligran", r"\bwatermark\b"],
    "delete_pages": [r"\bsil\b", r"\bsilme\b", r"\bsil[a-zçğıöşü]*", r"\bdelete\b", r"\bremove\b"],
    "rotate":       [r"\bdöndür", r"\bdondur", r"\brotate\b", r"\bturn\b",
                     r"\bters\s*[çc]evir", r"\bba[şs]\s*a[şs]a[ğg][ıi]"],
    "ocr":          [r"\bocr\b", r"\bojr\b", r"\bosr\b", r"\bogr\b", r"\bo\.c\.r\b",
                     r"\bmetin\s*tan[ıi]", r"\bmetni\s*tan[ıi]",
                     r"\bkarakter\s*tan[ıi]", r"\byaz[ıi]\s*[çc][ıi]kar",
                     r"\brecognize\s*text\b", r"\btext\s*recognition\b",
                     r"\boptical\s*character\s*recognition\b"],
    "decrypt":      [r"\b[şs]ifre(?:yi|sini|sı|si|lemeyi)?\b.{0,60}?\b(?:kaldır|kaldir|çöz|coz|sil)\b",
                     r"\bparola(?:yı|sını|sı)?\b.{0,60}?\b(?:kaldır|kaldir|çöz|coz|sil)\b",
                     r"\b[şs]ifre\s*korumas[ıi]n[ıi]\s*kald[ıi]r",
                     r"\bkilidi\s*a[çc]\b",
                     r"\bdecrypt\b", r"\bunlock\b",
                     r"\bremove\s+(?:the\s+)?password(?:\s+protection)?\b"],
}

# A conversion is "convert/çevir/dönüştür" plus a target format.
CONVERT_TARGETS = {
    "pdf_to_word":  [r"\bword\b", r"\bdocx?\b", r"\bkelime\b"],
    "pdf_to_image": [r"\bresim", r"\bresme\b", r"\bresimlere\b", r"\bresim\s+olarak\b",
                     r"\bgörsel", r"\bgorsel", r"\bgörsellere\b", r"\bgorsellere\b",
                     r"\bfotoğraf", r"\bfotograf", r"\bpng\b", r"\bjpe?g\b", r"\bimage\b",
                     r"\bimages?\b", r"\bpicture\b"],
    "pdf_to_text":  [r"\bmetin", r"\bmetne\b", r"\btxt\b", r"\byazıya\b", r"\btext\b"],
}

CONVERT_VERBS = [r"\bçevir", r"\bcevir", r"\bdönüştür", r"\bdonustur", r"\bconvert\b",
                 r"\bturn into\b", r"\bexport\b"]

# "Sayfaları resim olarak kaydet" has no convert verb of its own.
IMAGE_EXPORT_HINTS = [r"\bresim(?:ler)?\s+olarak\b", r"\bgörsel(?:ler)?\s+olarak\b",
                      r"\bgorsel(?:ler)?\s+olarak\b", r"\bas\s+images?\b",
                      r"\bto\s+images?\b"]
IMAGE_EXPORT_VERBS = [r"\bkaydet", r"\bçıkar", r"\bcikar", r"\boluştur", r"\bolustur",
                      r"\bexport\b", r"\bsave\b", r"\bwrite\b"]

# Quality profiles, best first so "en yüksek kalite" is not read as printer.
COMPRESS_QUALITY_PATTERNS = [
    ("prepress", [r"\bprepress\b", r"\bmatbaa", r"en\s+yüksek\s+kalite",
                  r"en\s+yuksek\s+kalite", r"maksimum\s+kalite", r"maximum\s+quality",
                  r"\bpress\s+quality\b"]),
    ("printer", [r"\bprinter\b", r"\bbask[ıi]\b", r"\byazd[ıi]r", r"yüksek\s+kalite",
                 r"yuksek\s+kalite", r"\bhigh\s+quality\b", r"\bprint\b"]),
    ("screen", [r"\bscreen\b", r"\bekran\b", r"en\s+küçük", r"en\s+kucuk",
                r"en\s+düşük", r"en\s+dusuk", r"maksimum\s+sıkıştırma",
                r"maksimum\s+sikistir", r"\bmaximum\s+compression\b", r"\bsmallest\b",
                r"\blow\s+quality\b"]),
    ("ebook", [r"\bebook\b", r"\be[-\s]?kitap\b", r"\bdengeli\b", r"\bbalanced\b",
               r"\bnormal\b", r"\bdefault\b"]),
]

VALID_QUALITIES = ("screen", "ebook", "printer", "prepress")

# Everything a command may ask for. Used to validate local-LLM output.
ALLOWED_ACTIONS = {
    "split", "merge", "compress", "watermark", "encrypt", "decrypt",
    "delete_pages", "rotate", "ocr", "pdf_to_image", "pdf_to_word", "pdf_to_text",
}

# The local model may name an action the way a person would.
ACTION_ALIASES = {
    "remove_password": "decrypt", "remove-password": "decrypt", "sifre_kaldir": "decrypt",
    "sifre_coz": "decrypt", "unlock": "decrypt",
    "delete": "delete_pages", "remove_pages": "delete_pages", "sil": "delete_pages",
    "to_images": "pdf_to_image", "to-images": "pdf_to_image", "images": "pdf_to_image",
    "resim": "pdf_to_image", "to_image": "pdf_to_image",
    "to_word": "pdf_to_word", "to-text": "pdf_to_text",
    "to_text": "pdf_to_text", "text": "pdf_to_text",
}

# Rotation direction words that make a bare "çevir" a rotation rather than a
# conversion.
ROTATE_HINTS = [r"\bderece\b", r"\bsağa\b", r"\bsaga\b", r"\bsola\b",
                r"\bsaat\s*yönü", r"\bsaat\s*yonu", r"\bters\b",
                r"\bba[şs]\s*a[şs]a[ğg][ıi]", r"\bupside\s*down\b",
                r"\bdegree", r"\bclockwise\b", r"\bright\b", r"\bleft\b"]


def _matches(patterns, text):
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _lower(text):
    """Lower-case with Turkish İ fixed: "İndirilenler" -> "indirilenler".

    str.lower() turns İ into "i" plus a combining dot, so a plain regex for
    "indirilenler" missed the word when it was capitalised.
    """
    return text.lower().replace("\u0307", "")


def _normalize_text(text: str) -> str:
    """Whisper çıktısındaki yaygın hataları düzeltir."""
    text = re.sub(r'\s*nokta\s*(pdf|PDF)\s*', '.pdf', text)
    text = re.sub(r'\s*alt\s*çizgi\s*', '_', text)
    return text


def _turkish_word_to_number(text: str) -> str:
    """Metin içindeki Türkçe veya İngilizce yazılmış rakamları sayıya çevirir. Örn: 'ilk beş' -> 'ilk 5'

    Only ever applied to the text with file names already removed -- otherwise
    "bir.pdf" becomes "1.pdf".
    """
    for word, num in TURKISH_NUMBERS.items():
        text = re.sub(rf'\b{word}\b', str(num), text, flags=re.IGNORECASE)
    for word, num in ENGLISH_NUMBERS.items():
        text = re.sub(rf'\b{word}\b', str(num), text, flags=re.IGNORECASE)
    return text


# "kaydet" and friends: a folder is a destination when one of these is near it.
_SAVE_CUES = (r"\bkaydet", r"\bkayded", r"\byükle", r"\byukle", r"\bat\b", r"\bkoy\b",
              r"\byaz\b", r"\bçıkar", r"\bcikar", r"\bsave\b", r"\bput\b", r"\bexport\b",
              r"\bwrite\b")
_OUTPUT_HINTS = (r"\bçıktı", r"\bcikti", r"\bhedef", r"\boutput\b", r"\btarget\b",
                 r"\bklasör", r"\bklasor", r"\bfolder\b")


def _has_save_cue(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in _SAVE_CUES)


def _has_output_hint(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in _OUTPUT_HINTS)


def _clean_custom_path(candidate: str) -> str:
    """Trim the words around an unquoted Windows path: 'C:\\x klasörüne kaydet'."""
    candidate = candidate.strip().strip("\"'“”‘’«»").strip()
    candidate = re.split(
        r"\s+(?:klasör|klasor|folder|kaydet|kayded|save|içine|icine|olarak)\w*\b",
        candidate, maxsplit=1, flags=re.IGNORECASE)[0]
    return candidate.rstrip(" .,;:!?") or ""


def _custom_output_path(text: str):
    """A full path written in the command, expanded, or None.

    Only looked for where the sentence talks about saving or an output folder;
    otherwise 'C:\\Belgeler\\rapor.pdf' in an input command would look like a
    destination.
    """
    if not (_has_save_cue(text) or _has_output_hint(text)):
        return None

    candidates = []
    for quote in ('"', "'", "“", "‘"):
        close = {'"': '"', "'": "'", "“": "”", "‘": "’"}[quote]
        candidates.extend(m.group(1) for m in re.finditer(
            rf"{quote}([A-Za-z]:[\\/][^{close}]*|[~%][^{close}]*)", text))

    unquoted = re.search(
        r"((?:[A-Za-z]:[\\/]|~[\\/]|%USERPROFILE%[\\/])[^<>\"'|?*\r\n]*)",
        text, re.IGNORECASE)
    if unquoted:
        candidates.append(unquoted.group(1))

    for candidate in candidates:
        cleaned = _clean_custom_path(candidate)
        if not cleaned:
            continue
        expanded = os.path.expandvars(os.path.expanduser(cleaned))
        if os.path.splitext(expanded)[1].lower() == ".pdf":
            expanded = os.path.dirname(expanded)
        if expanded:
            return os.path.normpath(expanded)
    return None


def parse_target_folder(text: str) -> str:
    """Metin içindeki hedef klasörü
    text = str(text or "")[:4096] (Masaüstü, Belgelerim, İndirilenler, özel yol) saptayıp tam yolunu döner."""
    text_lower = _lower(text)
    user_home = os.path.expanduser("~")
    save_cue = _has_save_cue(text_lower)

    custom = _custom_output_path(text)
    if custom:
        return custom

    desktop_direction = re.search(
        r"masa\s*[uü]st[uü](?:\s+klas[oö]r(?:[uü])?)?(?:'?ne|'?na|'?e|'?a)\b", text_lower)
    desktop_base = re.search(r"\bmasa\s*[uü]st[uü]\b", text_lower)
    if desktop_direction or \
            re.search(r"\b(?:to|into|in|on)\s+(?:the\s+)?desktop\b", text_lower) or \
            (save_cue and (desktop_base or re.search(r"\bdesktop\b", text_lower))):
        return os.path.join(user_home, "Desktop")

    documents_direction = re.search(
        r"belge(?:ler|lerim)?(?:\s+klas[oö]r(?:[uü])?)?(?:'?[ea]|'?ye|'?ya|ime|e)\b", text_lower)
    documents_base = re.search(r"\b(?:belgelerim|belgeler|belge)\b", text_lower)
    if documents_direction or \
            re.search(r"\b(?:to|into|in)\s+(?:my\s+)?documents\b", text_lower) or \
            (save_cue and (documents_base or re.search(r"\bdocuments\b", text_lower))):
        return os.path.join(user_home, "Documents")

    downloads_direction = re.search(
        r"[iı]ndirilenler(?:\s+klas[oö]r(?:[uü])?)?(?:'?[ea]|'?ye|'?ya)?\b", text_lower)
    downloads_base = re.search(r"\b[iı]ndirilenler\b", text_lower)
    if re.search(r"\b(?:to|into|in)\s+(?:the\s+)?downloads\b", text_lower) or \
            (save_cue and (downloads_direction or downloads_base or
                           re.search(r"\bdownloads?\b", text_lower))) or \
            ("indir" in text_lower and ("klas" in text_lower or "kaydet" in text_lower)):
        return os.path.join(user_home, "Downloads")

    return None


def _candidate_paths(stem):
    """Files in the search folders whose stem matches *stem* case-insensitively."""
    if not stem or "\x00" in str(stem):
        return []
    matches = []
    home = os.path.expanduser("~")
    for folder in SEARCH_FOLDERS:
        directory = os.path.join(home, folder)
        if not os.path.isdir(directory):
            continue
        try:
            entries = os.listdir(directory)
        except OSError:
            continue
        for name in entries:
            if not name.lower().endswith(".pdf"):
                continue
            if os.path.splitext(name)[0].lower() == stem.lower():
                matches.append(os.path.join(directory, name))
    return matches


def _strip_turkish_suffix(word):
    """Drop a trailing Turkish case suffix: 'sözleşmeyi' -> 'sözleşme'."""
    for suffix in ("sini", "sını", "yi", "yı", "yu", "yü", "ni", "nı", "nu", "nü",
                   "i", "ı", "u", "ü", "e", "a"):
        if len(word) > len(suffix) + 2 and word.lower().endswith(suffix):
            return word[: -len(suffix)]
    return word


def _file_mentions(text: str):
    r"""Find every file mentioned as (file_name, exact_text_that_named_it).

    Keeping the matched substring is what lets _strip_file_names remove
    precisely what named the file. Stripping the bare stem instead would eat
    real words: "a.pdf ve b.pdf birleştir" has stem "b", and removing "b\w*"
    deletes "birleştir" along with it.
    """
    explicit = [(m.group(1), m.group(1))
                for m in re.finditer(r'([\w_\-çğıöşüÇĞİÖŞÜ]+\.pdf)', text, re.IGNORECASE)]
    if explicit:
        return explicit

    match = re.search(rf'([{_TR_CHARS}0-9_-]+)\s+dosya', text, re.IGNORECASE)
    if match:
        return [(match.group(1).strip() + ".pdf", match.group(1))]

    match = re.search(rf'([{_TR_CHARS}0-9_-]+)\s+p\s*d\s*f', text, re.IGNORECASE)
    if match:
        return [(match.group(1).strip() + ".pdf", match.group(0))]

    # "Masaüstündeki sözleşmeyi sıkıştır" -- no extension, no "dosya".
    skip = {"masaüstündeki", "masaüstünde", "masaüstü", "belgelerimdeki", "belgelerdeki",
            "indirilenlerdeki", "klasöründeki", "klasördeki", "dosyayı", "dosyasını",
            "the", "file", "my", "in", "on", "desktop", "documents", "downloads"}
    for word in re.findall(rf'[{_TR_CHARS}0-9_-]{{3,}}', text):
        if word.lower() in skip:
            continue
        for candidate in (word, _strip_turkish_suffix(word)):
            if _candidate_paths(candidate):
                return [(candidate + ".pdf", word)]
    return []


def parse_input_files(text: str):
    """Return every file name mentioned, in the order they appear."""
    return [name for name, _mention in _file_mentions(text)]


def parse_input_file(text: str) -> str:
    """First file mentioned, or "" -- kept for callers that want a single file."""
    names = parse_input_files(text)
    return names[0] if names else ""


def _strip_file_names(text, mentions):
    """Remove exactly the text that named each file.

    Everything downstream -- keywords, page numbers, the number normaliser --
    then works on a string that cannot contain a file name.
    """
    stripped = text
    for _name, mention in mentions:
        stripped = re.sub(re.escape(mention), " ", stripped, flags=re.IGNORECASE)
    return stripped


# Ranges written as "3-5", "3 ile 5 arası", "3. sayfadan 5. sayfaya"...
_PAGE_RANGE_PATTERNS = [
    r'(\d+)\s*\.?\s*(?:sayfa(?:dan|dan)?|page)?\s*(?:ile|ve|-|–|—|to|through|until)\s*(\d+)',
    r'(\d+)\s*\.?\s*sayfadan\s*(\d+)\s*\.?\s*sayfaya',
    r"(\d+)\s*'?[dt]en\s+(\d+)\s*'?[ae]\s*kadar",
    r'\bpages?\s+(\d+)\s*[-–—]\s*(\d+)',
    r'(\d+)\s*[-–—]\s*(\d+)\s*(?:arası|arasi|aralığı|araligi|aralık|aralik|between)',
    r'(\d+)\s*[-–—]\s*(\d+)',
]


def _range_pair(start, end):
    start, end = int(start), int(end)
    return {"start": min(start, end), "end": max(start, end)}



def _extract_clause_for(text, keywords):
    """Extract the clause or sentence fragment that contains any of *keywords*."""
    delimiters = r'(?:,\s*|;\s*|\s+(?:ve|and|sonra|then|ardından|ayrıca|also)\s+)'
    clauses = re.split(delimiters, text, flags=re.IGNORECASE)
    for clause in clauses:
        if any(re.search(kw, clause, re.IGNORECASE) for kw in keywords):
            return clause
    return text

def _parse_pages(text):
    """Page numbers mentioned in *text* (which must already be name-free)."""
    pages = []
    spans = []
    for pattern in _PAGE_RANGE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start, end = int(match.group(1)), int(match.group(2))
            step = 1 if end >= start else -1
            pages.extend(range(start, end + step, step))
            spans.append(match.span())
    for match in re.finditer(r'\d+', text):
        if any(start <= match.start() < end for start, end in spans):
            continue
        value = int(match.group(0))
        if 0 < value < 10000:
            pages.append(value)
    return sorted(set(pages))


def _parse_delete_pages(text):
    """Delete kwargs: a page list, or {"last": N} for "son 2 sayfa"."""
    clause = _extract_clause_for(text, KEYWORDS["delete_pages"])
    match = re.search(r'(?:son|last)\s+(\d+)', clause, re.IGNORECASE)
    if match:
        return {"last": int(match.group(1))}
    match = re.search(r'(?:ilk|first)\s+(\d+)', clause, re.IGNORECASE)
    if match:
        count = int(match.group(1))
        return {"pages": list(range(1, count + 1))}
    pages = _parse_pages(clause)
    if not pages and clause != text:
        pages = _parse_pages(text)
    return {"pages": pages} if pages else {}


def _parse_split_range(text):
    clause = _extract_clause_for(text, KEYWORDS["split"])
    match = re.search(r'(?:ilk|first)\s+(\d+)', clause, re.IGNORECASE)
    if match:
        return {"start": 1, "end": int(match.group(1))}

    match = re.search(r'(?:son|last)\s+(\d+)', clause, re.IGNORECASE)
    if match:
        return {"last": int(match.group(1))}

    for pattern in _PAGE_RANGE_PATTERNS:
        match = re.search(pattern, clause, re.IGNORECASE)
        if match:
            return _range_pair(match.group(1), match.group(2))

    match = re.search(r'(\d+)\.?\s*(?:sayfa|page)', clause, re.IGNORECASE)
    if match:
        page = int(match.group(1))
        return {"start": page, "end": page}

    if clause != text:
        for pattern in _PAGE_RANGE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return _range_pair(match.group(1), match.group(2))

    return None


def parse_compression_quality(text):
    """The compression profile a command asks for (default: ebook)."""
    lowered = _lower(text)
    for quality, patterns in COMPRESS_QUALITY_PATTERNS:
        if _matches(patterns, lowered):
            return quality
    return "ebook"


# ── Passwords ──
#
# A password is only taken where the command marks it: "şifre: X",
# "parola X", "X ile şifrele", "with X". It is read from the command as
# typed, because PDF passwords are case-sensitive; the lowered text turned
# "Gizli123" into "gizli123", and the suffix of "şifrelemek" or "şifreler
# misin" passed for a password.

_QUOTES = "\"'“”‘’«»"
# A bare password: no spaces or quotes, 3+ characters, Turkish letters too.
_BARE = rf"[^\s{_QUOTES}]{{3,64}}"
_QUOTED = rf"[{_QUOTES}]([^{_QUOTES}]{{1,64}})[{_QUOTES}]"
_TOKEN = rf"(?:{_QUOTED}|({_BARE}))"
_MARKER = r"\b(?:şifre|sifre|parola|password|passcode)(?:si|sı)?"

_PASSWORD_PATTERNS = [
    # decrypt / unlock / remove password with X
    re.compile(rf"\b(?:decrypt|unlock|remove\s+(?:the\s+)?password(?:\s+protection)?)\b.{{0,100}}?\bwith\s+(?:the\s+)?(?:password\s+)?{_TOKEN}",
               re.IGNORECASE),
    # encrypt report.pdf with X, protect it with the password X
    re.compile(rf"\b(?:encrypt|protect|lock)\b.{{0,100}}?\bwith\s+(?:the\s+)?(?:password\s+)?{_TOKEN}",
               re.IGNORECASE),
    # şifresini X ile kaldır, parolayı X ile çöz
    re.compile(rf"(?:[şs]ifre|parola)(?:sini|sı|si|yi|yı)?\s+{_TOKEN}\s+"
               rf"(?:ile|şifresiyle|sifresiyle|parolasıyla|parolasiyla|diye)\s+"
               rf"(?:kaldır|kaldir|çöz|coz|sil)", re.IGNORECASE),
    # X ile şifrele, X şifresiyle şifrele, X parolası ile koru, X diye şifrele
    re.compile(rf"{_TOKEN}\s+(?:(?:[şs]ifre|parola)(?:si|sı)?\s+)?"
               rf"(?:ile|şifresiyle|sifresiyle|parolasıyla|parolasiyla|diye)\s+"
               rf"(?:[şs]ifrele|parola|kilitle|koru)", re.IGNORECASE),
    # X parolasıyla şifresini kaldır, X ile şifreyi çöz
    re.compile(rf"{_TOKEN}\s+(?:(?:[şs]ifre|parola)(?:si|sı)?\s+)?"
               rf"(?:ile|şifresiyle|sifresiyle|parolasıyla|parolasiyla|diye)\s+"
               rf"(?:(?:[şs]ifre)(?:sini|yi)?|(?:parola)(?:yı|sını)?)\s*"
               rf"(?:kaldır|kaldir|çöz|coz|sil)", re.IGNORECASE),
    # şifre: X, parola X, password = X, şifresi X olsun, şifre olarak X
    re.compile(rf"{_MARKER}(?:\s*[:=]\s*|\s+(?:olarak\s+|is\s+|as\s+)?){_TOKEN}", re.IGNORECASE),
]

# Words that stand where a password could and never are one: "parola ile
# şifrele" is not a password of "parola".
_NOT_PASSWORDS = {
    "ile", "ve", "bir", "olarak", "olsun", "ekle", "koy", "koru", "kilitle", "lütfen", "lutfen",
    "şifre", "sifre", "şifresi", "sifresi", "şifreyle", "sifreyle", "şifrele", "sifrele",
    "parola", "parolası", "parolasi", "parolayla", "güçlü", "guclu", "yeni", "bunu", "onu",
    "dosya", "dosyayı", "dosyayi", "dosyasını", "dosyasini", "belgeyi", "pdf'i", "pdf'yi",
    "password", "passcode", "please", "the", "and", "with", "this", "that", "file", "pdf",
    "encrypt", "protect", "lock", "strong", "new", "is", "as", "for", "my", "your",
    "from", "to", "in", "on", "at", "by", "into", "onto", "out", "of", "off", "all",
    "pages", "page", "sayfa", "sayfalar", "den", "dan", "ten", "tan", "için", "icin",
    "kadar", "olan", "olanı", "olani", "dosyadan",
    # Words that mark the *removal* of a password, never the password itself.
    "kaldır", "kaldir", "çöz", "coz", "sil", "remove", "unlock", "decrypt", "aç", "ac",
    "open", "şifresini", "sifresini", "şifreyi", "sifreyi", "şifresi", "sifresi",
    "parolayı", "parolayi", "parolasını", "parolasini", "parolası", "parolasi",
}


def parse_password(text):
    """The password a command names, exactly as written, or None.
    text = str(text or "")[:4096]

    None means "ask for it": a wrong guess locks the user's document with a
    password they do not know.
    """
    for pattern in _PASSWORD_PATTERNS:
        for match in pattern.finditer(text):
            quoted, bare = match.group(1), match.group(2)
            if quoted is not None:
                if quoted.strip():
                    return quoted
                continue
            candidate = bare.rstrip(".,;:!?")
            if len(candidate) < 3 or candidate.lower() in _NOT_PASSWORDS:
                continue
            if candidate.lower().endswith(".pdf"):
                continue        # a file name, not a password
            return candidate
    return None


_WATERMARK_STOPWORDS = {
    "ekle", "ekleyin", "ekleme", "yaz", "yazın", "yazili", "yazılı", "koy", "koyun",
    "bas", "basın", "metin", "metni", "yazı", "yazisi", "yazısı", "filigran", "watermark",
    "text", "add", "put", "write", "the", "a", "an", "with", "as", "please", "olsun",
    "yap", "bir", "olan", "olarak", "uygula",
}

# Ways of naming the watermark text, most specific first.
_WATERMARK_PATTERNS = [
    r'[“"\'‘]([^”"\'’]{1,60})[”"\'’]\s*(?:yaz[ıi]l[ıi]|olarak)?\s*'
    r'(?:bir\s+)?(?:filigran|watermark)',
    r'(?:filigran|watermark)\s*(?:metni|yazısı|yazisi|text)?\s*[:=]\s*'
    r'["“\'‘]?([^"“”\'‘’\n,.;]{1,60})',
    r'(?:filigran|watermark)\s+(?:metni|yazısı|yazisi)\s+'
    r'["“\'‘]?([^\s"“”\'‘’,.;]{1,40})',
    r'(?:filigran|watermark)\s+(?:ekle|yaz|bas|koy|add|put)\s+'
    r'["“\'‘]?([^\s"“”\'‘’,.;]{1,40})',
    r'([^\s,.;]{1,40})\s+(?:filigran|watermark)',
    r'([\wçğıöşüÇĞİÖŞÜ0-9_-]{1,40})\s+yaz[ıi]l[ıi]',
    r'\b(?:add|put|write)\s+["\'“]?([^\s,.;"“”]{1,40})["\'”]?\s+'
    r'(?:as\s+)?(?:a\s+)?watermark',
    r'\bwatermark\s+(?:with|as)\s+["\'“]?([^\s,.;"“”]{1,40})',
    r'(?:üzerine|uzerine)\s+["\'“]?([^\s,.;"“”]{1,40})["\'”]?\s+yaz',
]


def _clean_watermark_text(value):
    value = (value or "").strip().strip(_QUOTES).strip()
    value = re.sub(r'^(?:olarak|metni|yazısı|yazisi|text)\s*[:=]?\s*', "", value,
                   flags=re.IGNORECASE)
    value = value.strip(" .,;:!?\"'“”‘’«»")
    if not value or value.lower() in _WATERMARK_STOPWORDS:
        return None
    return value[:60].strip().upper()


def parse_watermark_text(text):
    """The text a watermark command names, or "GİZLİ" when it names none."""
    text = str(text or "")[:4096]
    for pattern in _WATERMARK_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            cleaned = _clean_watermark_text(match.group(1))
            if cleaned:
                return cleaned
    return "GİZLİ"


def _rotate_angle(lowered):
    if re.search(r'\b(?:ters|ba[şs]\s*a[şs]a[ğg][ıi]|upside\s*down)\b', lowered):
        return 180
    match = re.search(r'(\d+)\s*(?:derece|degree)', lowered)
    angle = int(match.group(1)) if match else 90
    if angle not in (90, 180, 270):
        angle = 90
    if re.search(r'\bsola\b|\bleft\b|\bsaat\s*yönünün\s*tersi|\bsaat\s*yonunun\s*tersi|\bcounter-?clockwise\b|\bccw\b', lowered):
        angle = 360 - angle if angle != 180 else 180
    return angle


def parse_actions(text: str, clean_text: str = None) -> list:
    """Work out which operations were asked for.

    *clean_text* is the command with file names removed; when it is not given
    the text is used as-is (callers inside this module always pass it).

    Actions come out in an order the runner can carry out: decryption first,
    because nothing can read an encrypted PDF; encryption last, because every
    later step would otherwise need the password.
    """
    haystack = clean_text if clean_text is not None else text
    lowered = _lower(haystack)
    decrypt_actions = []
    middle_actions = []  # list of (position, action_dict)
    encrypt_actions = []

    def _pos(patterns):
        positions = []
        for p in patterns:
            m = re.search(p, lowered)
            if m:
                positions.append(m.start())
        return min(positions) if positions else 999999

    # ── Decrypt: must run before anything that reads the PDF ──
    decrypt = _matches(KEYWORDS["decrypt"], lowered)
    if decrypt:
        dec_clause = _extract_clause_for(text, KEYWORDS["decrypt"])
        password = parse_password(dec_clause) or parse_password(text)
        decrypt_actions.append({"action": "decrypt",
                                "kwargs": {"password": password} if password
                                else {"needs_password": True}})

    # ── Conversions: a convert verb plus an explicit target format ──
    converted = False
    converted_to_image = False
    if _matches(CONVERT_VERBS, lowered):
        for action, patterns in CONVERT_TARGETS.items():
            if _matches(patterns, lowered):
                kwargs = {}
                if action == "pdf_to_image":
                    kwargs["format"] = "jpg" if re.search(r'\bjpe?g\b', lowered) else "png"
                    converted_to_image = True
                middle_actions.append((_pos(patterns), {"action": action, "kwargs": kwargs}))
                converted = True
                break

    # "Sayfaları resim olarak kaydet" has no convert verb.
    if not converted and _matches(IMAGE_EXPORT_HINTS, lowered) and \
            _matches(IMAGE_EXPORT_VERBS, lowered):
        middle_actions.append((_pos(IMAGE_EXPORT_HINTS), {"action": "pdf_to_image",
                               "kwargs": {"format": "jpg" if re.search(r'\bjpe?g\b', lowered) else "png"}}))
        converted = True
        converted_to_image = True

    # ── Split ──
    span = _parse_split_range(lowered)
    split = _matches(KEYWORDS["split"], lowered)
    if split and converted_to_image and span is None and \
            not _matches([r"\bkes", r"\bböl", r"\bboll", r"\bsplit\b"], lowered):
        # "sayfaları resimlere ayır" is an image export, not a page split.
        split = False
    if split:
        middle_actions.append((_pos(KEYWORDS["split"]),
                               {"action": "split", "kwargs": span if span else {"start": 1, "end": 1}}))

    # ── Merge ──
    if _matches(KEYWORDS["merge"], lowered):
        middle_actions.append((_pos(KEYWORDS["merge"]), {"action": "merge", "kwargs": {}}))

    # ── Watermark ──
    if _matches(KEYWORDS["watermark"], lowered):
        middle_actions.append((_pos(KEYWORDS["watermark"]),
                               {"action": "watermark",
                                "kwargs": {"text": parse_watermark_text(haystack)}}))

    # ── Compress ──
    if _matches(KEYWORDS["compress"], lowered):
        middle_actions.append((_pos(KEYWORDS["compress"]),
                               {"action": "compress",
                                "kwargs": {"quality": parse_compression_quality(lowered)}}))

    # ── Delete pages ──
    if _matches(KEYWORDS["delete_pages"], lowered) and re.search(r'sayfa|page', lowered):
        kwargs = _parse_delete_pages(lowered)
        if kwargs:
            middle_actions.append((_pos(KEYWORDS["delete_pages"]),
                                   {"action": "delete_pages", "kwargs": kwargs}))

    # ── Rotate: only on an explicit rotate word, or "çevir" with a direction ──
    rotate = _matches(KEYWORDS["rotate"], lowered)
    if not rotate and not converted and _matches(CONVERT_VERBS, lowered) and \
            _matches(ROTATE_HINTS, lowered):
        rotate = True
    if rotate:
        middle_actions.append((_pos(KEYWORDS["rotate"]),
                               {"action": "rotate", "kwargs": {"angle": _rotate_angle(lowered)}}))

    # ── OCR ──
    if _matches(KEYWORDS["ocr"], lowered):
        middle_actions.append((_pos(KEYWORDS["ocr"]), {"action": "ocr", "kwargs": {}}))

    # ── Bare "metni çıkar" without a convert verb ──
    if not converted and re.search(r'metin|metni|text', lowered) and \
            re.search(r'çıkar|cikar|extract', lowered) and \
            not any(a["action"] == "ocr" for _, a in middle_actions):
        middle_actions.append((_pos([r"metin", r"metni", r"text"]),
                               {"action": "pdf_to_text", "kwargs": {}}))

    # ── Encrypt: last, so the steps before it can still read the PDF ──
    has_encrypt_kw = _matches(KEYWORDS["encrypt"], lowered)
    if has_encrypt_kw and decrypt:
        # Only allow encrypt alongside decrypt if there is an explicit encrypt verb
        has_encrypt_kw = bool(re.search(
            r'\b(?:[şs]ifrele|encrypt|protect|kilitle|lock|[şs]ifre\s*ekle|parola\s*ekle|[şs]ifre\s*koy|parola\s*koy)\b',
            lowered
        ))
    if has_encrypt_kw:
        enc_clause = _extract_clause_for(text, [
            r'\b[şs]ifrele', r'\bencrypt', r'\bprotect', r'\bkilitle', r'\block',
            r'\b[şs]ifre\s*ekle', r'\bparola\s*ekle', r'\bparola\s*koy', r'\bparola'
        ])
        password = parse_password(enc_clause) or parse_password(text)
        encrypt_actions.append({"action": "encrypt",
                                "kwargs": {"password": password} if password
                                else {"needs_password": True}})

    # Sort middle actions by position in text to preserve user\'s spoken order
    middle_actions.sort(key=lambda item: item[0])
    ordered_middle = [act for _, act in middle_actions]

    return decrypt_actions + ordered_middle + encrypt_actions


# ── Optional local-LLM fallback ──────────────────────────────────────────
#
# The rule parser is the first layer and the only one that runs for a command
# it understood. When it finds no action at all, a local GGUF model may be
# asked for a structured intent; its answer is validated before use, so a
# confused model cannot ask the runner to do anything the rule parser could
# not. Without llama-cpp-python or a model file this is a no-op.

_LLM_ACTION_SCHEMA = """
{
  "input_file": "rapor.pdf",
  "input_files": ["rapor.pdf"],
  "output_target": "Masaüstü",
  "action_chain": [
    {"action": "compress", "kwargs": {"quality": "ebook"}},
    {"action": "split", "kwargs": {"start": 1, "end": 3}}
  ]
}
""".strip()

_LLM_PROMPT = """Sen PDF Aura adlı PDF aracının komut çözümleyicisisin.
Kullanıcının Türkçe veya İngilizce komutunu aşağıdaki JSON şemasına çevir.
Yalnızca JSON döndür; açıklama, markdown veya kod bloğu yazma.

Şema:
{schema}

İzinli action değerleri: split, merge, compress, watermark, encrypt, decrypt,
delete_pages, rotate, ocr, pdf_to_image, pdf_to_word, pdf_to_text.
compress kalitesi: screen, ebook, printer, prepress.
rotate açısı: 90, 180, 270.
split için {{"start": 1, "end": 5}} veya {{"last": 3}}.
delete_pages için {{"pages": [2, 4]}} veya {{"last": 2}}.
encrypt/decrypt için parola yoksa {{"needs_password": true}}.
output_target: Masaüstü, Belgelerim, İndirilenler veya tam bir klasör yolu.

Komut: {command}
JSON:"""


def _extract_json_object(text):
    """The first JSON object in *text*, ignoring markdown fences and chatter."""
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", str(text), flags=re.IGNORECASE)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(cleaned[start:end + 1])
    except (ValueError, TypeError):
        return None


def _as_int(value, default=None):
    try:
        if isinstance(value, bool):
            return default
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _normalize_llm_target(value):
    if not isinstance(value, str):
        return None
    candidate = value.replace("\r", "").replace("\n", "").strip()
    if not candidate or candidate.lower() in ("same", "same folder", "ayni", "aynı",
                                              "bulundugu klasor", "bulunduğu klasör"):
        return None
    known = parse_target_folder(" " + candidate + " kaydet")
    if known:
        return known
    if re.search(r"[\\/]|[A-Za-z]:", candidate):
        return os.path.normpath(os.path.expandvars(os.path.expanduser(candidate)))
    return None


def _validate_kwargs(action, kwargs, text):
    """Validated kwargs for one action, or None when it cannot be run."""
    if not isinstance(kwargs, dict):
        kwargs = {}

    if action == "split":
        last = _as_int(kwargs.get("last"))
        if last is not None and last > 0:
            return {"last": last}
        start = _as_int(kwargs.get("start"), 1)
        end = _as_int(kwargs.get("end"), start)
        if start is None or end is None or start < 1 or end < 1:
            return None
        return {"start": min(start, end), "end": max(start, end)}

    if action == "merge":
        return {}

    if action == "compress":
        quality = kwargs.get("quality")
        if isinstance(quality, str) and quality.lower() in VALID_QUALITIES:
            return {"quality": quality.lower()}
        if isinstance(quality, str):
            return {"quality": parse_compression_quality(quality)}
        return {"quality": "ebook"}

    if action == "watermark":
        cleaned = _clean_watermark_text(str(kwargs.get("text") or ""))
        return {"text": cleaned or "GİZLİ"}

    if action in ("encrypt", "decrypt"):
        password = kwargs.get("password")
        if isinstance(password, str) and password and len(password) <= 128:
            return {"password": password}
        return {"needs_password": True}

    if action == "delete_pages":
        last = _as_int(kwargs.get("last"))
        if last is not None and last > 0:
            return {"last": last}
        raw_pages = kwargs.get("pages")
        if isinstance(raw_pages, str):
            raw_pages = _parse_pages(raw_pages)
        if isinstance(raw_pages, (list, tuple, set)):
            pages = sorted({page for page in (_as_int(p) for p in raw_pages)
                            if page is not None and 0 < page < 10000})
            return {"pages": pages} if pages else None
        return None

    if action == "rotate":
        angle = _as_int(kwargs.get("angle"), 90)
        return {"angle": angle if angle in (90, 180, 270) else 90}

    if action == "pdf_to_image":
        fmt = str(kwargs.get("format") or kwargs.get("img_format") or "png").lower()
        return {"format": "jpg" if fmt in ("jpg", "jpeg") else "png"}

    if action in ("ocr", "pdf_to_word", "pdf_to_text"):
        return {}

    return None


def _validate_llm_intent(data, fallback):
    """A safe intent from the model's JSON, or None if it cannot be trusted."""
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("intent"), dict):
        data = data["intent"]

    raw_files = data.get("input_files")
    if raw_files is None:
        raw_files = data.get("input_file")
    if isinstance(raw_files, str):
        raw_files = [raw_files]
    if not isinstance(raw_files, (list, tuple)):
        raw_files = []

    files = []
    for item in raw_files:
        if not isinstance(item, str):
            continue
        name = os.path.basename(item.strip().replace("\\", "/"))
        if not name or name in (".", ".."):
            continue
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        files.append(name)
    if not files:
        files = [name for name in fallback.get("input_files", []) if name]
    if not files:
        return None

    raw_actions = data.get("action_chain", data.get("actions"))
    if not isinstance(raw_actions, (list, tuple)) or not raw_actions:
        return None

    actions = []
    for item in raw_actions[:12]:
        if isinstance(item, str):
            action, kwargs = item, {}
        elif isinstance(item, dict):
            action, kwargs = item.get("action"), item.get("kwargs") or {}
        else:
            continue
        action = ACTION_ALIASES.get(str(action).strip().lower(), str(action).strip().lower())
        if action not in ALLOWED_ACTIONS:
            continue
        validated = _validate_kwargs(action, kwargs, fallback.get("raw_text", ""))
        if validated is None:
            continue
        actions.append({"action": action, "kwargs": validated})

    if not actions:
        return None

    if any(a["action"] == "merge" for a in actions) and len(files) < 2:
        return None

    target = data.get("output_target", data.get("output"))
    if target is None:
        target = fallback.get("output_target")
    else:
        target = _normalize_llm_target(target)

    return {
        "input_file": files[0],
        "input_files": files,
        "output_target": target,
        "action_chain": actions,
        "raw_text": fallback.get("raw_text", ""),
        "source": "llm",
    }


def _ask_llm(model, prompt):
    generate = getattr(model, "generate", None)
    if callable(generate):
        try:
            return generate(prompt, max_tokens=512, temperature=0.0)
        except TypeError:
            return generate(prompt)
    if callable(model):
        return model(prompt)
    return None


def _available_local_llm():
    """A local model when one is configured, else None; never an error."""
    try:
        from src.ai import local_llm as local_llm_module
    except Exception as exc:      # optional dependency
        logger.debug("local_llm unavailable: %s", exc)
        return None
    try:
        if not local_llm_module.is_llm_available():
            return None
        return local_llm_module.create_local_llm()
    except Exception as exc:
        logger.debug("local LLM could not be created: %s", exc)
        return None


def parse_intent_with_llm(text, fallback=None, llm=None):
    """Ask a local/optional LLM for a structured intent, validated strictly.

    Returns None when no model is available, the answer is not JSON, or the
    answer fails validation. It never raises for a model failure.
    """
    model = llm if llm is not None else _available_local_llm()
    if model is None:
        return None

    prompt = _LLM_PROMPT.format(schema=_LLM_ACTION_SCHEMA, command=text)
    try:
        response = _ask_llm(model, prompt)
    except Exception as exc:
        logger.warning("Local LLM intent fallback failed: %s", exc)
        return None

    data = _extract_json_object(response)
    if data is None:
        logger.debug("Local LLM did not return a JSON object")
        return None
    return _validate_llm_intent(data, fallback or {})


def parse_intent(text: str, *, llm=None, use_llm: bool = True) -> dict:
    """Turn recognised speech (or typed text) into an ActionRunner intent.

    Rules always run first. The optional local model is only consulted when
    they found no action at all; *llm* can be injected (anything with a
    ``generate`` method or a callable) for tests or another local runtime.
    """
    if not text:
        return {}

    text = _normalize_text(text[:4096])

    # File names first, then keyword matching on what is left of the command.
    mentions = _file_mentions(text)
    input_files = [name for name, _mention in mentions]
    command_text = _turkish_word_to_number(_strip_file_names(text, mentions))

    intent = {
        "input_file": input_files[0] if input_files else "",
        "input_files": input_files,
        "output_target": parse_target_folder(command_text),
        "action_chain": parse_actions(text, command_text),
        "raw_text": text,
        "source": "rules",
    }

    if use_llm and not intent["action_chain"]:
        improved = parse_intent_with_llm(text, intent, llm=llm)
        if improved:
            return improved

    return intent


# ── Human-readable plan ──────────────────────────────────────────────────

_QUALITY_LABELS = {
    "screen": "ekran / en küçük dosya",
    "ebook": "dengeli / e-kitap",
    "printer": "baskı",
    "prepress": "matbaa",
}

_PDF_ACTIONS = {"split", "merge", "watermark", "compress", "encrypt", "decrypt",
                "delete_pages", "rotate"}


def _target_label(target):
    if not target:
        return "girdi dosyasının bulunduğu klasör"
    expanded = os.path.normpath(os.path.expandvars(os.path.expanduser(target)))
    name = os.path.basename(expanded).lower()
    labels = {
        "desktop": "Masaüstü", "masaüstü": "Masaüstü",
        "documents": "Belgelerim", "belgeler": "Belgelerim", "belgelerim": "Belgelerim",
        "downloads": "İndirilenler", "indirilenler": "İndirilenler",
    }
    label = labels.get(name)
    return f"{label} ({expanded})" if label else expanded


def _plan_step(action, kwargs):
    kind = action.get("action") if isinstance(action, dict) else action
    kwargs = kwargs or {}

    if kind == "split":
        if "last" in kwargs:
            return f"Son {kwargs['last']} sayfayı ayır"
        return f"Sayfa {kwargs.get('start', 1)}-{kwargs.get('end', 1)} arasını ayır"
    if kind == "merge":
        return "Diğer PDF dosyalarıyla birleştir"
    if kind == "compress":
        quality = kwargs.get("quality", "ebook")
        return f"Sıkıştır ({_QUALITY_LABELS.get(quality, quality)} kalitesi)"
    if kind == "watermark":
        return f"Filigran ekle: {kwargs.get('text', 'GİZLİ')}"
    if kind == "encrypt":
        note = "parola: belirtildi" if kwargs.get("password") else "parola sorulacak"
        return f"PDF'i şifrele ({note})"
    if kind == "decrypt":
        note = "parola: belirtildi" if kwargs.get("password") else "parola sorulacak"
        return f"Şifre korumasını kaldır ({note})"
    if kind == "delete_pages":
        if "last" in kwargs:
            return f"Son {kwargs['last']} sayfayı sil"
        pages = ", ".join(str(page) for page in kwargs.get("pages", []))
        return f"Sayfaları sil: {pages}"
    if kind == "rotate":
        angle = kwargs.get("angle", 90)
        direction = "saat yönünün tersine" if angle == 270 else "saat yönünde"
        return f"Tüm sayfaları {angle}° {direction} döndür"
    if kind == "ocr":
        return "OCR uygula (metni tanı ve .txt olarak kaydet)"
    if kind == "pdf_to_image":
        return f"Sayfaları {str(kwargs.get('format', 'png')).upper()} resimlere dönüştür"
    if kind == "pdf_to_word":
        return "Word belgesine dönüştür"
    if kind == "pdf_to_text":
        return "Düz metne dönüştür"
    return str(kind)


def _planned_output_names(intent):
    stem = os.path.splitext(os.path.basename(intent.get("input_file") or ""))[0] or "belge"
    names = []
    actions = [a.get("action") for a in intent.get("action_chain", []) if isinstance(a, dict)]
    for action in actions:
        if action == "ocr":
            names.append(f"{stem}_ocr.txt")
        elif action == "pdf_to_image":
            names.append(f"{stem}_resimler/")
        elif action == "pdf_to_word":
            names.append(f"{stem}.docx")
        elif action == "pdf_to_text":
            names.append(f"{stem}.txt")
    if any(action in _PDF_ACTIONS for action in actions):
        names.insert(0, f"{stem}_aura.pdf")
    return names


def build_plan(intent: dict) -> str:
    """A Turkish, human-readable plan to show before running *intent*.

    Lists the input file(s), every step in the order the runner will carry
    them out, and where the result will be written.
    """
    intent = intent or {}
    files = [name for name in intent.get("input_files", []) if name]
    if not files and intent.get("input_file"):
        files = [intent["input_file"]]

    lines = ["İşlem planı:"]
    if files:
        lines.append(f"  Girdi: {', '.join(files)}")
    else:
        lines.append("  Girdi: (dosya belirtilmedi)")

    actions = intent.get("action_chain") or []
    if not actions:
        lines.append("  Adımlar: işlem anlaşılamadı")
    else:
        lines.append("  Adımlar:")
        for index, action in enumerate(actions, 1):
            if isinstance(action, dict):
                step = _plan_step(action, action.get("kwargs"))
            else:
                step = _plan_step(action, {})
            lines.append(f"    {index}. {step}")

    lines.append(f"  Çıktı konumu: {_target_label(intent.get('output_target'))}")
    names = _planned_output_names(intent)
    if names:
        lines.append(f"  Çıktı dosyası: {', '.join(names)}")

    for action in actions:
        if isinstance(action, dict) and action.get("action") in ("encrypt", "decrypt") \
                and action.get("kwargs", {}).get("needs_password"):
            lines.append("  Not: İşlem için parola sorulacak.")
            break

    return "\n".join(lines)
