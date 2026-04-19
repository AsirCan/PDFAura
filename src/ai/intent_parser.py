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


def _normalize_text(text: str) -> str:
    """Whisper çıktısındaki yaygın hataları düzeltir."""
    # "nokta pdf" veya "nokta PDF" -> ".pdf"
    text = re.sub(r'\s*nokta\s*(pdf|PDF)\s*', '.pdf', text)
    # "alt çizgi" -> "_"
    text = re.sub(r'\s*alt\s*çizgi\s*', '_', text)
    return text


def _turkish_word_to_number(text: str) -> str:
    """Metin içindeki Türkçe yazılmış rakamları sayıya çevirir. Örn: 'ilk beş' -> 'ilk 5'"""
    for word, num in TURKISH_NUMBERS.items():
        # Kelime sınırlarına dikkat ederek değiştir
        text = re.sub(rf'\b{word}\b', str(num), text, flags=re.IGNORECASE)
    return text


def parse_target_folder(text: str) -> str:
    """Metin içindeki hedef klasörü (Masaüstü, Belgelerim) saptayıp tam yolunu döner."""
    text_lower = text.lower()
    user_home = os.path.expanduser("~")

    # Whisper bazen "masaüstü"yü "masa üstü" olarak ayırıyor
    if "masaüstü" in text_lower or "masa üstü" in text_lower or "desktop" in text_lower:
        return os.path.join(user_home, "Desktop")

    # "belge" kelimesi dosya adında geçiyorsa (ör: belge.pdf) false positive olmasın
    # Sadece "belgelerime kaydet", "belgelere kaydet" gibi kalıplarda hedef olsun
    if re.search(r'belge(ler)?(?:im)?(?:e|ye|\'?e)\s+(?:kaydet|yükle|at|koy)', text_lower):
        return os.path.join(user_home, "Documents")

    if "indir" in text_lower and ("klasör" in text_lower or "kaydet" in text_lower):
        return os.path.join(user_home, "Downloads")

    return None


def parse_input_file(text: str) -> str:
    """Metinde geçen .pdf uzantılı dosyayı veya 'X dosyası' kalıbını bulur."""
    result = ""

    # 1. "finansal_rapor.pdf" gibi açık uzantılar
    match = re.search(r'([\w_-]+\.pdf)', text, re.IGNORECASE)
    if match:
        result = match.group(1).strip()

    # 2. "test dosyasını", "rapor dosyasını" vb.
    if not result:
        match = re.search(r'([a-zA-ZçğıöşüÇĞİÖŞÜ0-9_-]+)\s+dosya', text, re.IGNORECASE)
        if match:
            result = match.group(1).strip() + ".pdf"

    # 3. "sunum p d f ini" vb.
    if not result:
        match = re.search(r'([a-zA-ZçğıöşüÇĞİÖŞÜ0-9_-]+)\s+p\s*d\s*f', text, re.IGNORECASE)
        if match:
            result = match.group(1).strip() + ".pdf"

    if not result:
        return ""

    # Whisper bazen konumları da dosya adının parçası olarak verir
    # "Masa üstündeki test.pdf" -> "test.pdf"
    location_prefixes = [
        r'masa\s*üstündeki\s*', r'masaüstündeki\s*',
        r'belgelerim(?:deki)?\s*', r'belgelerdeki\s*',
        r'indirilenler(?:deki)?\s*', r'desktop(?:teki)?\s*',
    ]
    for prefix in location_prefixes:
        result = re.sub(prefix, '', result, flags=re.IGNORECASE).strip()

    return result


def parse_actions(text: str) -> list:
    """Komutta hangi PDF işlemlerinin istendiğini belirleyip zincir olarak döner."""
    text_lower = text.lower()
    actions = []

    # 1. Kesme / Bölme
    if "kes" in text_lower or "böl" in text_lower:
        match = re.search(r'ilk\s+(\d+)', text_lower)
        if match:
            end = int(match.group(1))
            actions.append({"action": "split", "kwargs": {"start": 1, "end": end}})
        else:
            # "3 ile 7 arası", "3-7", "3 ve 7 arası" kalıpları
            match = re.search(r'(\d+)\s*(?:ile|ve|[-–])\s*(\d+)', text_lower)
            if match:
                actions.append({"action": "split", "kwargs": {"start": int(match.group(1)), "end": int(match.group(2))}})
            else:
                # Tek sayfa: "5. sayfayı kes"
                match = re.search(r'(\d+)\.?\s*sayfa', text_lower)
                if match:
                    page = int(match.group(1))
                    actions.append({"action": "split", "kwargs": {"start": page, "end": page}})
                else:
                    actions.append({"action": "split", "kwargs": {"start": 1, "end": 1}})

    # 2. Filigran
    if "filigran" in text_lower:
        match = re.search(r'([a-zA-ZçğıöşüÇĞİÖŞÜ0-9]+)\s+yazılı', text, re.IGNORECASE)
        w_text = match.group(1).upper() if match else "GİZLİ"
        actions.append({"action": "watermark", "kwargs": {"text": w_text}})

    # 3. Sıkıştırma
    if "sıkıştır" in text_lower or "küçült" in text_lower or "kompres" in text_lower:
        actions.append({"action": "compress", "kwargs": {"quality": "ebook"}})

    # 4. Şifreleme
    if "şifrele" in text_lower or "parola" in text_lower or "şifre ekle" in text_lower:
        match = re.search(r'([a-zA-Z0-9]+)\s+(ile|şifresiyle|diye)\s+şifre', text_lower)
        pwd = match.group(1) if match else "123456"
        actions.append({"action": "encrypt", "kwargs": {"password": pwd}})

    # 5. Sayfa Silme
    if "sil" in text_lower and "sayfa" in text_lower:
        pages = [int(x) for x in re.findall(r'(\d+)', text_lower) if 0 < int(x) < 10000]
        if pages:
            actions.append({"action": "delete_pages", "kwargs": {"pages": pages}})

    # 6. Sayfa Döndürme
    if "döndür" in text_lower or ("çevir" in text_lower and "dönüştür" not in text_lower):
        match = re.search(r'(\d+)\s*derece', text_lower)
        angle = int(match.group(1)) if match else 90
        # Geçerli açılarla sınırla
        if angle not in (90, 180, 270):
            angle = 90
        actions.append({"action": "rotate", "kwargs": {"angle": angle}})

    # 7. OCR (Whisper bazen OCR'ı OJR, OSR, OGR gibi yanlış duyabiliyor)
    ocr_keywords = ["ocr", "ojr", "osr", "ogr", "o.c.r", "metin tanı", "karakter tanı", "yazı çıkar"]
    if any(kw in text_lower for kw in ocr_keywords):
        actions.append({"action": "ocr", "kwargs": {}})

    # 8. PDF'den resme dönüştürme
    img_keywords = ["resim", "resme", "görsel", "görsele", "png", "jpg", "fotoğraf"]
    if any(kw in text_lower for kw in img_keywords) and "dönüştür" in text_lower:
        fmt = "jpg" if "jpg" in text_lower or "jpeg" in text_lower else "png"
        actions.append({"action": "pdf_to_image", "kwargs": {"format": fmt}})

    # 9. PDF'den Word'e dönüştürme
    if ("word" in text_lower or "docx" in text_lower or "kelime" in text_lower) and "dönüştür" in text_lower:
        actions.append({"action": "pdf_to_word", "kwargs": {}})

    # 10. PDF'den metin çıkarma
    if "metin" in text_lower and ("çıkar" in text_lower or "dönüştür" in text_lower):
        # OCR zaten eklenmişse tekrar ekleme
        if not any(a["action"] == "ocr" for a in actions):
            actions.append({"action": "pdf_to_text", "kwargs": {}})

    return actions


def parse_intent(text: str) -> dict:
    """
    Sesten dönüşen metni alıp ActionRunner için anlamlı JSON (sözlük) formatına çevirir.
    """
    if not text:
        return {}

    # Ön işleme: Whisper hatalarını düzelt ve yazılı rakamları çevir
    text = _normalize_text(text)
    text = _turkish_word_to_number(text)

    intent = {
        "input_file": parse_input_file(text),
        "output_target": parse_target_folder(text),
        "action_chain": parse_actions(text),
        "raw_text": text
    }
    return intent
