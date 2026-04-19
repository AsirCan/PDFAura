"""
Kapsamli AI Pipeline Testi
Her bir ozellik icin gTTS ile ses olusturur, Whisper'dan gecirip Intent Parser ile cozumler.
"""
import os
import sys
import tempfile

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))

from gtts import gTTS
from faster_whisper import WhisperModel
from src.ai.intent_parser import parse_intent

# Model yukle (tek seferlik)
print("=" * 70)
print("PDF Aura - KAPSAMLI AI Pipeline Testi")
print("=" * 70)
print("\nWhisper modeli yukleniyor...")
model = WhisperModel("small", device="cpu", compute_type="int8")
print("Model hazir!\n")

# Test komutlari - tum ozellikler
test_commands = [
    # --- TEMEL ---
    ("SIKISTIRMA", "Masaüstündeki rapor.pdf dosyasını sıkıştır"),
    ("KESME (ilk N)", "Masaüstündeki sunum.pdf dosyasının ilk 3 sayfasını kes"),
    ("KESME (aralik)", "test.pdf dosyasını 2 ile 5 arası kes"),
    ("FILIGRAN", "rapor.pdf dosyasına GİZLİ yazılı filigran ekle"),
    ("SIFRELEME", "belge.pdf dosyasını abc123 ile şifrele"),
    
    # --- DUZENLEME ---
    ("SAYFA SILME", "rapor.pdf dosyasının 3. sayfasını sil"),
    ("DONDURME", "sunum.pdf dosyasını 90 derece döndür"),
    
    # --- DONUSTURME ---
    ("PDF->RESIM", "rapor.pdf dosyasını resme dönüştür"),
    ("PDF->WORD", "belge.pdf dosyasını word formatına dönüştür"),
    ("OCR", "tarama.pdf dosyasına OCR yap"),
    
    # --- ZINCIRLEME ---
    ("ZINCIR: KES+FILIGRAN", "Masaüstündeki finansal_rapor.pdf dosyasının ilk 5 sayfasını kes ve GİZLİ yazılı filigran ekle"),
    ("ZINCIR: SIKISTIR+SIFRELE", "rapor.pdf dosyasını sıkıştır ve test123 ile şifrele"),
]

passed = 0
failed = 0
results = []

for label, command in test_commands:
    print(f"\n{'─' * 70}")
    print(f"  TEST: {label}")
    print(f"  Komut: \"{command}\"")
    
    try:
        # 1. gTTS ile ses dosyasi olustur
        tts = gTTS(text=command, lang="tr")
        temp_mp3 = tempfile.mktemp(suffix=".mp3")
        tts.save(temp_mp3)
        
        # 2. Whisper ile metne cevir
        segments, info = model.transcribe(temp_mp3, language="tr")
        recognized = " ".join([s.text for s in segments]).strip()
        
        # 3. Intent parser ile cozumle
        intent = parse_intent(recognized)
        
        # 4. Sonuclari goster
        print(f"  Whisper: \"{recognized}\"")
        print(f"  Dosya:   {intent.get('input_file', '???')}")
        print(f"  Hedef:   {intent.get('output_target', 'Belirtilmedi')}")
        actions = intent.get("action_chain", [])
        if actions:
            for a in actions:
                print(f"  Islem:   {a['action']} -> {a.get('kwargs', {})}")
            passed += 1
            status = "BASARILI"
        else:
            failed += 1
            status = "BASARISIZ (islem bulunamadi)"
            
        results.append((label, status, recognized))
        print(f"  Durum:   {status}")
        
        # Temizle
        os.remove(temp_mp3)
        
    except Exception as e:
        failed += 1
        status = f"HATA: {e}"
        results.append((label, status, ""))
        print(f"  Durum:   {status}")

# OZET
print(f"\n{'=' * 70}")
print(f"SONUC TABLOSU")
print(f"{'=' * 70}")
print(f"{'Test':<25} {'Durum':<15}")
print(f"{'─' * 40}")
for label, status, _ in results:
    mark = "[OK]" if "BASARILI" in status else "[X]"
    print(f"  {mark} {label:<25}")
    
print(f"\n  Toplam: {passed + failed} | Basarili: {passed} | Basarisiz: {failed}")
print(f"{'=' * 70}")
