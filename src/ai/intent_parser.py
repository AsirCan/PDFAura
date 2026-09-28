"""Turn a spoken or typed command into an action chain for the ActionRunner.

The order of work matters and is the fix for most of issue #9: file names are
extracted *first* and then removed from the text, so keyword and number
matching never sees them. Otherwise "herkes.pdf" matched "kes" (split),
"rapor_5.pdf" contributed page 5 to a delete, and "bir.pdf" was rewritten to
"1.pdf" by the Turkish number normaliser.
"""
import os
import re

# Whisper Türkçe yazı-rakam dönüşüm tablosu
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
    "split":        [r"\bkes", r"\bböl", r"\bayır", r"\bayir", r"\bsplit\b", r"\bextract\b"],
    "merge":        [r"\bbirleştir", r"\bbirlestir", r"\bmerge\b", r"\bcombine\b"],
    "compress":     [r"\bsıkıştır", r"\bsikistir", r"\bküçült", r"\bkucult", r"\bkompres",
                     r"\bcompress\b", r"\bshrink\b"],
    "encrypt":      [r"\bşifrele", r"\bsifrele", r"\bparola", r"\bşifre ekle",
                     r"\bencrypt\b", r"\bpassword\b", r"\bprotect\b"],
    "watermark":    [r"\bfiligran", r"\bwatermark\b"],
    "delete_pages": [r"\bsil\b", r"\bsilme\b", r"\bsil[a-zçğıöşü]*", r"\bdelete\b", r"\bremove\b"],
    "rotate":       [r"\bdöndür", r"\bdondur", r"\bçevir.*\bderece", r"\brotate\b"],
    "ocr":          [r"\bocr\b", r"\bojr\b", r"\bosr\b", r"\bogr\b", r"\bo\.c\.r\b",
                     r"\bmetin tanı", r"\bkarakter tanı", r"\byazı çıkar"],
}

# A conversion is "convert/çevir/dönüştür" plus a target format.
CONVERT_TARGETS = {
    "pdf_to_word":  [r"\bword\b", r"\bdocx?\b", r"\bkelime\b"],
    "pdf_to_image": [r"\bresim", r"\bresme\b", r"\bgörsel", r"\bgorsel", r"\bfotoğraf",
                     r"\bfotograf", r"\bpng\b", r"\bjpe?g\b", r"\bimage\b", r"\bpicture\b"],
    "pdf_to_text":  [r"\bmetin", r"\bmetne\b", r"\btxt\b", r"\byazıya\b", r"\btext\b"],
}

CONVERT_VERBS = [r"\bçevir", r"\bcevir", r"\bdönüştür", r"\bdonustur", r"\bconvert\b",
                 r"\bturn into\b", r"\bexport\b"]

# Rotation direction words that make a bare "çevir" a rotation rather than a
# conversion.
ROTATE_HINTS = [r"\bderece\b", r"\bsağa\b", r"\bsaga\b", r"\bsola\b", r"\bsaat yönü",
                r"\bdegree", r"\bclockwise\b", r"\bright\b", r"\bleft\b"]


def _matches(patterns, text):
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _normalize_text(text: str) -> str:
    """Whisper çıktısındaki yaygın hataları düzeltir."""
    text = re.sub(r'\s*nokta\s*(pdf|PDF)\s*', '.pdf', text)
    text = re.sub(r'\s*alt\s*çizgi\s*', '_', text)
    return text


def _turkish_word_to_number(text: str) -> str:
    """Metin içindeki Türkçe yazılmış rakamları sayıya çevirir. Örn: 'ilk beş' -> 'ilk 5'

    Only ever applied to the text with file names already removed -- otherwise
    "bir.pdf" becomes "1.pdf".
    """
    for word, num in TURKISH_NUMBERS.items():
        text = re.sub(rf'\b{word}\b', str(num), text, flags=re.IGNORECASE)
    return text


def parse_target_folder(text: str) -> str:
    """Metin içindeki hedef klasörü (Masaüstü, Belgelerim) saptayıp tam yolunu döner."""
    text_lower = text.lower()
    user_home = os.path.expanduser("~")

    if re.search(r'masa\s*üstü(?:ne|ndeki|nde)?\s+(?:kaydet|yükle|at|koy)', text_lower) or \
       re.search(r'\bdesktop\b.*\bsave\b', text_lower):
        return os.path.join(user_home, "Desktop")

    if re.search(r'belge(ler)?(?:im)?(?:e|ye|\'?e)\s+(?:kaydet|yükle|at|koy)', text_lower):
        return os.path.join(user_home, "Documents")

    if "indir" in text_lower and ("klasör" in text_lower or "kaydet" in text_lower):
        return os.path.join(user_home, "Downloads")

    return None


def _candidate_paths(stem):
    """Files in the search folders whose stem matches *stem* case-insensitively."""
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


def _parse_pages(text):
    """Page numbers mentioned in *text* (which must already be name-free)."""
    pages = []
    # "3-5 arası", "3 ile 7 arası"
    for match in re.finditer(r'(\d+)\s*(?:ile|ve|-|–|to)\s*(\d+)', text, re.IGNORECASE):
        start, end = int(match.group(1)), int(match.group(2))
        step = 1 if end >= start else -1
        pages.extend(range(start, end + step, step))
    if pages:
        return sorted(set(pages))
    return [int(x) for x in re.findall(r'\d+', text) if 0 < int(x) < 10000]


def _parse_split_range(text):
    match = re.search(r'(?:ilk|first)\s+(\d+)', text, re.IGNORECASE)
    if match:
        return {"start": 1, "end": int(match.group(1))}

    match = re.search(r'(?:son|last)\s+(\d+)', text, re.IGNORECASE)
    if match:
        return {"last": int(match.group(1))}

    match = re.search(r'(\d+)\s*(?:ile|ve|-|–|to)\s*(\d+)', text, re.IGNORECASE)
    if match:
        start, end = int(match.group(1)), int(match.group(2))
        return {"start": min(start, end), "end": max(start, end)}

    match = re.search(r'(\d+)\.?\s*(?:sayfa|page)', text, re.IGNORECASE)
    if match:
        page = int(match.group(1))
        return {"start": page, "end": page}

    return None


def parse_actions(text: str, clean_text: str = None) -> list:
    """Work out which operations were asked for.

    *clean_text* is the command with file names removed; when it is not given
    the text is used as-is (callers inside this module always pass it).
    """
    haystack = clean_text if clean_text is not None else text
    lowered = haystack.lower()
    actions = []

    # ── Conversions: a convert verb plus an explicit target format ──
    converted = False
    if _matches(CONVERT_VERBS, lowered):
        for action, patterns in CONVERT_TARGETS.items():
            if _matches(patterns, lowered):
                kwargs = {}
                if action == "pdf_to_image":
                    kwargs["format"] = "jpg" if re.search(r'\bjpe?g\b', lowered) else "png"
                actions.append({"action": action, "kwargs": kwargs})
                converted = True
                break

    # ── Split ──
    if _matches(KEYWORDS["split"], lowered):
        span = _parse_split_range(lowered)
        actions.append({"action": "split", "kwargs": span if span else {"start": 1, "end": 1}})

    # ── Merge ──
    if _matches(KEYWORDS["merge"], lowered):
        actions.append({"action": "merge", "kwargs": {}})

    # ── Watermark ──
    if _matches(KEYWORDS["watermark"], lowered):
        match = re.search(rf'([{_TR_CHARS}0-9]+)\s+yazılı', haystack, re.IGNORECASE)
        actions.append({"action": "watermark",
                        "kwargs": {"text": match.group(1).upper() if match else "GİZLİ"}})

    # ── Compress ──
    if _matches(KEYWORDS["compress"], lowered):
        actions.append({"action": "compress", "kwargs": {"quality": "ebook"}})

    # ── Encrypt ──
    if _matches(KEYWORDS["encrypt"], lowered):
        match = re.search(r'([a-zA-Z0-9]+)\s+(?:ile|şifresiyle|diye|with)\s+şifre', lowered) or \
                re.search(r'(?:şifre|parola|password)\s*[:=]?\s*([a-zA-Z0-9]{3,})', lowered)
        password = match.group(1) if match else None
        # No default password, ever: "123456" silently encrypted people's
        # files with a password they were never told.
        actions.append({"action": "encrypt",
                        "kwargs": {"password": password} if password
                        else {"needs_password": True}})

    # ── Delete pages ──
    if _matches(KEYWORDS["delete_pages"], lowered) and re.search(r'sayfa|page', lowered):
        pages = _parse_pages(lowered)
        if pages:
            actions.append({"action": "delete_pages", "kwargs": {"pages": pages}})

    # ── Rotate: only on an explicit rotate word, or "çevir" with a direction ──
    rotate = _matches([r"\bdöndür", r"\bdondur", r"\brotate\b"], lowered)
    if not rotate and not converted and _matches(CONVERT_VERBS, lowered) and _matches(ROTATE_HINTS, lowered):
        rotate = True
    if rotate:
        match = re.search(r'(\d+)\s*(?:derece|degree)', lowered)
        angle = int(match.group(1)) if match else 90
        if angle not in (90, 180, 270):
            angle = 90
        if re.search(r'\bsola\b|\bleft\b|\bsaat yönünün tersi', lowered):
            angle = 360 - angle if angle != 180 else 180
        actions.append({"action": "rotate", "kwargs": {"angle": angle}})

    # ── OCR ──
    if _matches(KEYWORDS["ocr"], lowered):
        actions.append({"action": "ocr", "kwargs": {}})

    # ── Bare "metni çıkar" without a convert verb ──
    if not converted and re.search(r'metin|metni|text', lowered) and \
            re.search(r'çıkar|cikar|extract', lowered) and \
            not any(a["action"] == "ocr" for a in actions):
        actions.append({"action": "pdf_to_text", "kwargs": {}})

    return actions


def parse_intent(text: str) -> dict:
    """Turn recognised speech (or typed text) into an ActionRunner intent."""
    if not text:
        return {}

    text = _normalize_text(text)

    # File names first, then keyword matching on what is left of the command.
    mentions = _file_mentions(text)
    input_files = [name for name, _mention in mentions]
    command_text = _turkish_word_to_number(_strip_file_names(text, mentions))

    return {
        "input_file": input_files[0] if input_files else "",
        "input_files": input_files,
        "output_target": parse_target_folder(command_text),
        "action_chain": parse_actions(text, command_text),
        "raw_text": text,
    }
