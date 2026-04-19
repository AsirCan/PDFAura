# PDF Aura — Product Ready Yol Haritası

> Bu dosya, PDF Aura'yı tam anlamıyla profesyonel ve satışa hazır bir ürün haline getirmek için eklenmesi gereken tüm özellikleri listeler.

---

## ✅ Mevcut Özellikler (Tamamlandı)

- [x] PDF sıkıştırma (Ghostscript tabanlı, 4 kalite modu)
- [x] PDF kesme (sayfa aralığı seçerek kaydetme)
- [x] Modern masaüstü arayüz
- [x] Sekmeli araç yapısı
- [x] Otomatik çıktı dosya adı oluşturma
- [x] Sayfa sayısı algılama ve gösterme
- [x] Windows installer (Inno Setup + Ghostscript otomatik kurulum)
- [x] PDF birleştirme (çoklu dosya, sıralama, ekleme/kaldırma)
- [x] Sayfa silme (tekli, çoklu, aralık: `3, 5, 12-15`)
- [x] Sayfa döndürme (90/180/270 derece, tekli veya tümü)
- [x] Sayfa sıralama (metin tabanlı yeniden sıralama)
- [x] PDF -> resim dönüştürme (PNG/JPEG, DPI: 72-600)
- [x] Resim -> PDF dönüştürme (çoklu resim, A4/Letter/Orijinal)
- [x] PDF -> Word dönüştürme (`pdf2docx`)
- [x] Word -> PDF dönüştürme (`docx2pdf`)
- [x] Akıllı Belge Tarayıcı (CamScanner tarzı kırpma ve filtreler)
- [x] Unit test altyapısı
- [x] Ortak stil ve durum yönetimi katmanı

---

## ✅ Öncelik 1 — Temel PDF İşlemleri (Tamamlandı)

### PDF Birleştirme (Merge)
- [x] Birden fazla PDF'yi tek bir dosyada birleştirme
- [x] Yukarı/Aşağı butonları ile sıralama değiştirme
- [x] Dosya listesinden seçili olanları kaldırma
- [x] Çıktı dosya adı önerisi: `dosya_birleşik.pdf`
- [ ] Drag & drop ile sıralama değiştirme (Öncelik 6'ya taşındı)

### PDF Sayfa Silme
- [x] Belirli sayfaları silip geri kalanını kaydetme
- [x] Çoklu sayfa seçimi (ör: `3, 5, 12-15`)
- [ ] Önizleme ile silme onayı (Öncelik 4'e taşındı)

### PDF Sayfa Sıralama (Reorder)
- [x] Metin tabanlı yeniden sıralama (ör: `5, 3, 1, 2, 4`)
- [ ] Sayfaları sürükle-bırak ile yeniden sıralama (Öncelik 6'ya taşındı)
- [ ] Sayfa küçük resimleri (thumbnails) gösterme (Öncelik 4'e taşındı)

### PDF Döndürme (Rotate)
- [x] Tek sayfa veya tüm sayfaları 90°/180°/270° döndürme
- [x] Açı seçimi (saat yönü)

---

## ✅ Öncelik 2 — Dönüştürme İşlemleri (Tamamlandı)

### PDF -> Resim (Image Export)
- [x] PDF sayfalarını PNG/JPG olarak dışa aktarma
- [x] DPI ayarı (72, 150, 300, 600)
- [x] Toplu dışa aktarma (tüm sayfalar)
- [x] Çıktı klasörü seçimi

### Resim -> PDF
- [x] JPG/PNG/BMP/TIFF/GIF resimlerden PDF oluşturma
- [x] Birden fazla resmi tek PDF'ye dönüştürme
- [x] Sayfa boyutu seçimi (A4, Letter, Orijinal)
- [x] RGBA resim desteği (otomatik RGB dönüşümü)
- [ ] Resim sıralaması (drag & drop) (Öncelik 6'ya taşındı)

### PDF -> Word (DOCX)
- [x] PDF'yi düzenlenebilir Word formatına dönüştürme (`pdf2docx`)
- [x] Tablo ve metin yapısını koruma
- [x] Türkçe karakter desteği

### Word -> PDF
- [x] DOCX dosyalarını PDF'ye dönüştürme (`docx2pdf`, MS Word gerekli)

---

## ✅ Öncelik 3 — Güvenlik ve Koruma (Tamamlandı)

### PDF Şifreleme (Password Protection)
- [x] PDF'ye açma şifresi ekleme
- [x] 128-bit şifreleme
- [ ] Düzenleme/yazdırma kısıtlaması

### PDF Şifre Kaldırma
- [x] Şifreli PDF'den şifreyi kaldırma (şifre biliniyorsa)
- [ ] Toplu şifre kaldırma (Öncelik 5'te)

### PDF Filigran (Watermark)
- [x] Metin filigranı ekleme
- [ ] Resim filigranı ekleme (logo vb.)
- [ ] Opaklık, açı, konum ayarları
- [x] Tüm sayfalara uygulama

---

## ✅ Öncelik 4 — Gelişmiş Özellikler (Tamamlandı)

### PDF Önizleme
- [x] Uygulama içi PDF görüntüleyici
- [x] Sayfa küçük resimleri
- [x] Zoom in/out kontrolü
- [x] İşlem öncesi / sonrası karşılaştırma

### OCR (Optik Karakter Tanıma)
- [x] Taranmış PDF'lerdeki metni tanıma
- [x] Tesseract OCR entegrasyonu
- [x] Türkçe dil desteği
- [ ] Aranabilir PDF oluşturma

### Akıllı Belge Tarayıcı (Document Scanner)
- [x] Görüntüden otomatik belge kenarı belirleme (Canny/Contours)
- [x] Yamuk fotoğrafları 4 köşeden interaktif manipüle etme (Warp Perspective)
- [x] Dinamik büyüteç (Magnifier) ile noktasal tam ekran kırpma
- [x] Gelişmiş Filtreler: Temiz Belge (Adaptive Thres), Siyah-Beyaz, Keskinleştirme
- [x] Çoklu fotoğraf işleyerek tek PDF yapma

### PDF Meta Veri Düzenleme
- [x] Başlık, yazar, konu, anahtar kelime düzenleme
- [x] Oluşturma/değiştirme tarihi ayarlama
- [x] Meta veri temizleme

### PDF İmza
- [x] Görsel imza ekleme
- [x] Çizim ile el yazısı imza (`png`)
- [x] İmza konumu ve boyutu ayarlama
- [x] Tarih damgası ekleme

---

## ✅ Öncelik 5 — Toplu İşlemler (Batch Processing) (Tamamlandı)

### Toplu Sıkıştırma
- [x] Klasördeki tüm PDF'leri tek seferde sıkıştırma
- [x] İlerleme çubuğu ile dosya bazlı takip
- [x] Başarı/hata raporu

### Toplu Dönüştürme
- [x] Birden fazla PDF -> resim veya tersi
- [x] Klasör bazlı toplu işlem

### Toplu Yeniden Adlandırma
- [x] PDF dosyalarını kurala göre yeniden adlandırma
- [x] Tarih, sayfa sayısı, boyut gibi değişkenler

---

## ✅ Öncelik 6 — Kullanıcı Deneyimi (UX) (Tamamlandı)

### Drag & Drop Desteği
- [x] Dosyaları pencereye sürükleyip bırakma
- [x] Tüm sekmelerde çalışan evrensel drop zone
- [x] Görsel geri bildirim

### Son Kullanılan Dosyalar
- [x] Son işlenen dosyaların listesi
- [x] Hızlı erişim paneli altyapısı
- [x] Geçmiş temizleme seçeneği

### Ayarlar Paneli
- [x] Varsayılan çıktı klasörü
- [x] Dil seçimi (TR/EN)

### Bildirimler ve Sesler
- [x] Opsiyonel ses efektleri
- [x] System tray'e küçültme

### Çoklu Dil Desteği (i18n)
- [x] Türkçe (varsayılan)
- [x] İngilizce
- [ ] Almanca
- [ ] Arapça

---

## 📌 Öncelik 7 — Teknik Altyapı ve Kalite

### Hata Yönetimi ve Loglama
- [ ] Detaylı hata logları (AppData klasöründe)
- [ ] Crash reporter (opsiyonel anonim hata bildirimi)
- [ ] Kullanıcı dostu hata mesajları

### Otomatik Güncelleme
- [ ] Uygulama içi güncelleme kontrolü
- [ ] Sürüm notları gösterimi
- [ ] Sessiz (silent) güncelleme modu

### Performans Optimizasyonu
- [ ] Büyük dosyalar için bellek optimizasyonu
- [ ] Çoklu çekirdek kullanımı
- [ ] İlerleme yüzdesi gösterimi
- [ ] İşlem iptal etme butonu

### Test ve Kalite Kontrolü
- [x] Unit test'ler
- [ ] Farklı PDF formatları ile uyumluluk testleri
- [ ] Windows 10/11 uyumluluk testleri
- [x] Edge case testleri

---

## 📌 Öncelik 8 — Marka ve Pazarlama

### Branding
- [ ] Profesyonel uygulama ikonu
- [ ] Splash screen
- [ ] Hakkında (About) penceresi
- [ ] Uygulama içi yardım / kullanım kılavuzu

### Web Sitesi
- [ ] Ürün tanıtım sayfası
- [ ] İndirme linki
- [ ] Ekran görüntüleri ve demo videosu
- [ ] SSS bölümü

### Installer İyileştirmeleri
- [ ] Kurulum sırasında özellik seçimi
- [ ] Sessiz kurulum desteği
- [ ] Kaldırma sırasında ayarları temizleme seçeneği
- [ ] Dijital imza (code signing)

---

## 📌 Öncelik 9 — Entegrasyonlar

### Windows Sağ Tık Menüsü (Context Menu)
- [ ] PDF'ye sağ tıklayınca "PDF Aura ile Sıkıştır" seçeneği
- [ ] "PDF Aura ile Kes" seçeneği
- [ ] "PDF Aura ile Birleştir" seçeneği

### Komut Satırı (CLI) Desteği
- [ ] Terminal üzerinden sıkıştırma: `pdfaura compress input.pdf -q ebook`
- [ ] Terminal üzerinden kesme: `pdfaura split input.pdf --pages 1-100`
- [ ] Otomasyon ve script entegrasyonu

### Bulut Entegrasyonu (İleri Seviye)
- [ ] Google Drive'dan dosya açma
- [ ] OneDrive entegrasyonu
- [ ] İşlenmiş dosyayı buluta yükleme

---

## 📌 Öncelik 10 — Yapay Zeka ve Sesli Asistan (AI & Voice)

### Sesli Komut ve Geri Bildirim (Tamamen Yerel / Offline)
Kullanıcının uygulamaya doğal dilde sesli komutlar vererek PDF işlemlerini otomatikleştirmesi hedeflenmektedir. Bu sistem tamamen yerel çalışacaktır; ses verisi, komut çözümleme, PDF işlemleri ve sesli geri bildirim hiçbir aşamada internete ihtiyaç duymadan kullanıcının kendi bilgisayarında yürütülecektir.

**Senaryo Örneği:**
1. Kullanıcı: *"Masaüstündeki `finansal_rapor.pdf` dosyasını al, ilk 5 sayfasını kes, `GİZLİ` yazılı bir filigran ekle ve Belgelerim'e kaydet. gibi her türlü özellik için bu işlemler yapılabilir"*
2. Sistem: Sesi metne dönüştürür, komutu analiz eder ve gerekli işlemleri sırasıyla arka planda çalıştırır.
3. Sistem yanıtı: *"Dosyanız başarıyla kesildi, filigran eklendi ve Belgelerim klasörüne kaydedildi. gibi her türlü özellik için bu işlemler yapılabilir nereye kaydetmek istiyorsun seçeneği sunulabilir sesli olarak ve cevabı da aynı şekilde sesli verince kaydeder örn: masaüstüne kaydetmek istiyorum dediğimizde kaydeder"*

### Detaylı Sistem Mimarisi ve Veri Akışı

**A. Ses Yakalama ve Metne Dönüştürme Katmanı (Audio-to-Text / ASR)**
- **Modül:** `src/ai/speech_recognizer.py`
- **Teknoloji:** `faster-whisper`
- **Model tercihi:** ilk sürüm için `small`, daha yüksek doğruluk gerektiğinde `medium`
- **Uyanma kelimesi (wake word):** isteğe bağlı olarak `openWakeWord` veya `Porcupine`
- **İşleyiş:**
  - Sistem düşük güç modunda uyanma kelimesini dinler.
  - Kullanıcı "Hey Aura" veya "Merhaba Aura" dediğinde aktif dinleme başlar.
  - Mikrofon girdisi alınır, temel gürültü azaltma uygulanır.
  - Ses verisi `faster-whisper` ile düz metne dönüştürülür.
  - Elde edilen metin komut çözümleme katmanına iletilir.

**B. Doğal Dil İşleme ve Niyet Çıkarımı Katmanı (Intent Parsing)**
- **Modül:** `src/ai/intent_parser.py`
- **Birincil teknoloji:** `regex + kural tabanlı parser`
- **İsteğe bağlı gelişmiş katman:** yerel LLM (`Qwen2.5-7B-Instruct` GGUF, `llama.cpp` üzerinden)
- **Neden bu yaklaşım:**
  - Uygulamanın komut seti sınırlı ve nettir.
  - `kes`, `böl`, `birleştir`, `sıkıştır`, `şifrele`, `filigran ekle`, `OCR yap` gibi işlemler kural tabanlı olarak daha stabil çözülebilir.
  - İlk sürümde LLM zorunlu değildir; gerekirse sadece fallback olarak eklenir.
- **İşleyiş:**
  - Dönüşen metin normalize edilir.
  - Dosya adı, klasör hedefi, işlem türü ve parametreler ayrıştırılır.
  - Örnek çözümleme çıktısı:

```json
{
  "input_file": "finansal_rapor.pdf",
  "output_target": "Belgelerim",
  "action_chain": [
    {
      "action": "split",
      "kwargs": {
        "start": 1,
        "end": 5
      }
    },
    {
      "action": "watermark",
      "kwargs": {
        "text": "GİZLİ"
      }
    }
  ]
}
```

**C. Orkestrasyon ve Çekirdek İşlem Katmanı (Orchestrator)**
- **Modül:** `src/ai/action_runner.py`
- **İşleyiş:**
  - `intent_parser` tarafından üretilen yapılandırılmış veri alınır.
  - İşlem zinciri sırayla yürütülür.
  - Uygulamanın mevcut `src/core/` modülleri doğrudan kullanılır.
  - Örnek:
    - `from src.core.split import split_pdf`
    - `from src.core.security import add_watermark_to_pdf`
  - Her adımın çıktısı bir sonraki adıma giriş olur.
- **Sorumlulukları:**
  - geçici dosya üretimi
  - çok adımlı komut zincirlerinin yürütülmesi
  - hata yakalama
  - kullanıcıya dönecek final durum mesajının hazırlanması
- **Örnek hata durumları:**
  - dosya bulunamadı
  - sayfa aralığı geçersiz
  - çıktı klasörü yazılabilir değil
  - PDF işlem modülü beklenmeyen hata verdi

**D. Sesli Geri Bildirim ve Sentez Katmanı (Text-to-Speech / TTS)**
- **Modül:** `src/ai/text_speaker.py`
- **Teknoloji:** `Piper`
- **Alternatif:** `pyttsx3`
- **Tercih nedeni:**
  - `Piper` tamamen offline çalışır.
  - Daha doğal ve modern ses üretimi sağlar.
  - Yerel masaüstü uygulaması için gömülebilir yapıdadır.
- **İşleyiş:**
  - İşlem tamamlandığında veya hata oluştuğunda kullanıcıya okunacak metin hazırlanır.
  - Örnek başarılı çıktı: *"Dosyanız başarıyla işlendi ve Belgelerim klasörüne kaydedildi."*
  - Örnek hata çıktısı: *"Üzgünüm, masaüstünde belirttiğiniz dosyayı bulamadım."*

**E. Kullanıcı Deneyimi (GUI Entegrasyonu)**
- Sekmelerin yanında bağımsız bir **AI Asistan** butonu veya ayrı bir panel bulunur.
- Dinleme sırasında ekranda animasyonlu bir **"Dinleniyor..."** göstergesi yer alır.
- Kullanıcının söylediği komut metne çevrildikten sonra küçük bir önizleme balonunda gösterilir.
- İstenirse komut çalıştırılmadan önce kullanıcıdan onay alınır.
- İşlem tamamlandığında:
  - ekranda kısa bir durum özeti gösterilir
  - istenirse sesli yanıt okunur
  - oluşan dosya otomatik olarak ilgili klasörde açılabilir

### Önerilen Yerel Teknoloji Yığını

**MVP (İlk sürüm için en mantıklı yapı)**
- ASR: `faster-whisper small`
- Intent parsing: `regex + kural tabanlı parser`
- TTS: `Piper`
- Wake word: ilk sürümde opsiyonel, butona bas-konuş modeli yeterli

**Gelişmiş sürüm**
- ASR: `faster-whisper medium`
- Intent parsing: `kural tabanlı parser + yerel LLM fallback`
- Yerel LLM: `Qwen2.5-7B-Instruct` GGUF
- Runtime: `llama.cpp`
- Wake word: `openWakeWord`

### Mimari Karar

Bu özellik için en doğru yaklaşım:
- önce tamamen kural tabanlı ve offline bir MVP geliştirmek
- sadece karmaşık doğal dil komutlarında yerel LLM fallback eklemek
- bulut tabanlı hiçbir servise bağımlı olmamak

Bu sayede sistem:
- hızlı açılır
- gizlilik dostu olur
- internet olmadan çalışır
- masaüstü PDF iş akışlarına daha güvenilir şekilde entegre edilir

---

## 📊 Öncelik Sıralaması Özet Tablosu

| Öncelik | Kategori | Zorluk | Etki |
|---------|----------|--------|------|
| 1 | Temel PDF İşlemleri | Orta | 🔥🔥🔥🔥🔥 |
| 2 | Dönüştürme İşlemleri | Yüksek | 🔥🔥🔥🔥 |
| 3 | Güvenlik ve Koruma | Orta | 🔥🔥🔥🔥 |
| 4 | Gelişmiş Özellikler | Yüksek | 🔥🔥🔥 |
| 5 | Toplu İşlemler | Orta | 🔥🔥🔥 |
| 6 | Kullanıcı Deneyimi | Düşük-Orta | 🔥🔥🔥🔥 |
| 7 | Teknik Altyapı | Orta | 🔥🔥🔥🔥 |
| 8 | Marka ve Pazarlama | Düşük | 🔥🔥🔥 |
| 9 | Entegrasyonlar | Yüksek | 🔥🔥 |
| 10 | Yapay Zeka (AI & Voice) | Çok Yüksek | 🔥🔥🔥🔥🔥 |

---

## 🎯 Önerilen İlk Sprint (MVP+)

Hızlıca ürünü güçlendirmek için ilk yapılması gerekenler:

1. **PDF birleştirme** — En çok istenen özellik
2. **Drag & Drop** — UX'i büyük ölçüde iyileştirir
3. **PDF -> resim dönüştürme** — Çok kullanılan bir ihtiyaç
4. **PDF şifreleme** — Güvenlik hissi verir
5. **Sağ tık menü entegrasyonu** — Profesyonel hissettirir
6. **Hakkında penceresi + splash screen** — Marka algısı

---

*Son güncelleme: 17 Nisan 2026*  
*Proje: PDF Aura v2.0*

---

## 📌 İleriye Dönük İstekler (V2+)

### 🎙️ Tamamen Yerel ve Doğal TTS (Offline Piper TTS)
* **Durum:** ⏳ Beklemede
* **Açıklama:** gTTS'in internet ihtiyacını ortadan kaldırıp, yerel SAPI5'in (pyttsx3) mekanik ve yabancı aksanlı sesinden kurtulmak için `piper-tts` (ONNX ses modelleri) kullanılacak.
* **Detaylar:**
  - İnternette bulunan açık kaynaklı ONNX formatındaki dil modelleri indirilecek (Örn: `tr_TR-fahrettin-medium.onnx` veya benzeri).
  - Tercihen daha profesyonel ve etkileşimi sıcak kılacak bir **kadın sesi modeli** entegre edilecek.
  - Uygulama Ayarları (Settings) sekmesine "Asistan Sesi" için bir dropdown / seçim menüsü konulacak ki kullanıcılar farklı modeller (kadın/erkek vb.) arasında geçiş yapabilsinler.
  - Tüm çıkarımlar, tıpkı `faster-whisper` gibi %100 offline (kullanıcının kendi yerel bilgisayarında) çalışacak.