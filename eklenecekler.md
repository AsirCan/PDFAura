# PDF Aura — Product Ready Yol Haritası

> Bu dosya, PDF Aura'yı tam anlamıyla profesyonel ve satışa hazır bir ürün haline getirmek için eklenmesi gereken tüm özellikleri listeler.

---

## ✅ Mevcut Özellikler (Tamamlandı)

- [x] PDF Sıkıştırma (Ghostscript tabanlı, 4 kalite modu)
- [x] PDF Kesme (Sayfa aralığı seçerek kaydetme)
- [x] Dark mode modern arayüz
- [x] 5 sekmeli tab yapısı (Sıkıştır / Kes / Birleştir / Düzenle / Dönüştür)
- [x] Otomatik çıktı dosya adı oluşturma
- [x] Sayfa sayısı algılama ve gösterme
- [x] Windows installer (Inno Setup + Ghostscript otomatik kurulum)
- [x] PDF Birleştirme (çoklu dosya, sıralama, ekleme/kaldırma)
- [x] Sayfa Silme (tekli, çoklu, aralık: "3, 5, 12-15")
- [x] Sayfa Döndürme (90/180/270 derece, tekli veya tümü)
- [x] Sayfa Sıralama (metin tabanlı yeniden sıralama)
- [x] PDF -> Resim dönüştürme (PNG/JPEG, DPI: 72-600)
- [x] Resim -> PDF dönüştürme (çoklu resim, A4/Letter/Orijinal)
- [x] PDF -> Word dönüştürme (pdf2docx)
- [x] Word -> PDF dönüştürme (docx2pdf)
- [x] 49 unit test (split, merge, delete, rotate, reorder, convert)
- [x] Her sekme için ayrı accent renk ve progress bar

---

## ✅ Öncelik 1 — Temel PDF İşlemleri (TAMAMLANDI)

### PDF Birleştirme (Merge)
- [x] Birden fazla PDF'yi tek bir dosyada birleştirme
- [x] Yukarı/Aşağı butonları ile sıralama değiştirme
- [x] Dosya listesinden seçili olanları kaldırma
- [x] Çıktı dosya adı önerisi: `dosya_birlesik.pdf`
- [ ] Drag & drop ile sıralama değiştirme (Öncelik 6'ya taşındı)

### PDF Sayfa Silme
- [x] Belirli sayfaları silip geri kalanını kaydetme
- [x] Çoklu sayfa seçimi (ör: 3, 5, 12-15)
- [ ] Önizleme ile silme onayı (Öncelik 4'e taşındı)

### PDF Sayfa Sıralama (Reorder)
- [x] Metin tabanlı yeniden sıralama (ör: "5, 3, 1, 2, 4")
- [ ] Sayfaları sürükle-bırak ile yeniden sıralama (Öncelik 6'ya taşındı)
- [ ] Sayfa küçük resimleri (thumbnails) gösterme (Öncelik 4'e taşındı)

### PDF Döndürme (Rotate)
- [x] Tek sayfa veya tüm sayfaları 90°/180°/270° döndürme
- [x] Açı seçimi (saat yönü)

---

## ✅ Öncelik 2 — Dönüştürme İşlemleri (TAMAMLANDI)

### PDF → Resim (Image Export)
- [x] PDF sayfalarını PNG/JPG olarak dışa aktarma
- [x] DPI ayarı (72, 150, 300, 600)
- [x] Toplu dışa aktarma (tüm sayfalar)
- [x] Çıktı klasörü seçimi

### Resim → PDF
- [x] JPG/PNG/BMP/TIFF/GIF resimlerden PDF oluşturma
- [x] Birden fazla resmi tek PDF'ye dönüştürme
- [x] Sayfa boyutu seçimi (A4, Letter, Orijinal)
- [x] RGBA resim desteği (otomatik RGB dönüşümü)
- [ ] Resim sıralaması (drag & drop) (Öncelik 6'ya taşındı)

### PDF → Word (DOCX)
- [x] PDF'yi düzenlenebilir Word formatına dönüştürme (pdf2docx)
- [x] Tablo ve metin yapısını koruma
- [x] Türkçe karakter desteği

### Word → PDF
- [x] DOCX dosyalarını PDF'ye dönüştürme (docx2pdf, MS Word gerekli)

---

## ✅ Öncelik 3 — Güvenlik ve Koruma (TAMAMLANDI)

### PDF Şifreleme (Password Protection)
- [x] PDF'ye açma şifresi ekleme
- [x] 128-bit şifreleme (PyPDF2)
- [ ] Düzenleme/yazdırma kısıtlaması (Şu an sadece açma şifresi var, genel kısıtlama desteklenmedi)

### PDF Şifre Kaldırma
- [x] Şifreli PDF'den şifreyi kaldırma (şifre biliniyorsa)
- [ ] Toplu şifre kaldırma (Öncelik 5'te)

### PDF Filigran (Watermark)
- [x] Metin filigranı ekleme (ReportLab + PyPDF2)
- [ ] Resim filigranı ekleme (logo vb.)
- [ ] Opaklık, açı, konum ayarları (Varsayılan opacity 0.3 ve açı 45)
- [x] Tüm sayfalara uygulama

---

## ✅ Öncelik 4 — Gelişmiş Özellikler (TAMAMLANDI)

### PDF Önizleme
- [x] Uygulama içi PDF görüntüleyici (PyMuPDF - popup)
- [x] Sayfa küçük resimleri (thumbnail panel) - Entegre kaydırıcı
- [x] Zoom in/out kontrolü
- [x] İşlem öncesi / sonrası karşılaştırma

### OCR (Optik Karakter Tanıma)
- [x] Taranmış PDF'lerdeki metni tanıma
- [x] Tesseract OCR entegrasyonu (pytesseract)
- [x] Türkçe dil desteği (Tesseract Kuruluysa)
- [ ] Aranabilir PDF oluşturma (Şu an sadece metin çıkarımı .txt desteklendi)

### PDF Meta Veri Düzenleme
- [x] Başlık, yazar, konu, anahtar kelime düzenleme
- [x] Oluşturma/değiştirme tarihi ayarlama
- [x] Meta veri temizleme (gizlilik için)

### PDF İmza
- [x] Dijital imza ekleme (Görsel Mühür olarak entegre edildi)
- [x] Çizim ile el yazısı imza (png)
- [x] İmza konumu ve boyutu ayarlama
- [x] Tarih damgası ekleme (Orijinal ModDate ile PDF update edilir)

---

## ✅ Öncelik 5 — Toplu İşlemler (Batch Processing) (TAMAMLANDI)

### Toplu Sıkıştırma
- [x] Klasördeki tüm PDF'leri tek seferde sıkıştırma
- [x] İlerleme çubuğu ile dosya bazlı takip
- [x] Başarı/hata raporu

### Toplu Dönüştürme
- [x] Birden fazla PDF → resim veya tersi
- [x] Klasör bazlı toplu işlem

### Toplu Yeniden Adlandırma
- [x] PDF dosyalarını kurala göre yeniden adlandırma
- [x] Tarih, sayfa sayısı, boyut gibi değişkenler

---

## ✅ Öncelik 6 — Kullanıcı Deneyimi (UX) (TAMAMLANDI)

### Drag & Drop Desteği
- [x] Dosyaları pencereye sürükleyip bırakma
- [x] Tüm sekmelerde çalışan evrensel drop zone
- [x] Görsel geri bildirim (hover efekti - DND Hook ile sağlandı)

### Son Kullanılan Dosyalar
- [x] Son işlenen dosyaların listesi (Config manager içinden tutulur)
- [x] Hızlı erişim paneli (Backend altyapısı kuruldu)
- [x] Geçmiş temizleme seçeneği (Ayarlar paneli)

### Ayarlar Paneli
- [x] Varsayılan çıktı klasörü
- [x] Dil seçimi (TR/EN)

### Bildirimler ve Sesler
- [x] Opsiyonel ses efektleri (Config toggle)
- [x] System tray'e küçültme (pystray ile entegre)

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
- [ ] Çoklu çekirdek kullanımı (multi-threading)
- [ ] İlerleme yüzdesi gösterimi (indeterminate yerine)
- [ ] İşlem iptal etme butonu

### Test ve Kalite Kontrolü
- [x] Unit test'ler (49 test - unittest)
- [ ] Farklı PDF formatları ile uyumluluk testleri
- [ ] Windows 10/11 uyumluluk testleri
- [x] Edge case testleri (geçersiz sayfa, boş liste, tüm sayfa silme)

---

## 📌 Öncelik 8 — Marka ve Pazarlama

### Branding
- [ ] Profesyonel uygulama ikonu (çeşitli boyutlarda)
- [ ] Splash screen (açılış ekranı)
- [ ] Hakkında (About) penceresi — versiyon, lisans, iletişim
- [ ] Uygulama içi yardım / kullanım kılavuzu

### Web Sitesi
- [ ] Ürün tanıtım sayfası
- [ ] İndirme linki
- [ ] Ekran görüntüleri ve demo videosu
- [ ] SSS (Sıkça Sorulan Sorular) bölümü

### İnstaller İyileştirmeleri
- [ ] Kurulum sırasında özellik seçimi (component selection)
- [ ] Sessiz kurulum desteği (enterprise için)
- [ ] Kaldırma sırasında ayarları temizleme seçeneği
- [ ] Dijital imza (code signing) — güvenlik uyarısı olmaması için

---

## 📌 Öncelik 9 — Entegrasyonlar

### Windows Sağ Tık Menüsü (Context Menu)
- [ ] PDF'ye sağ tıklayınca "PDF Aura ile Sıkıştır" seçeneği
- [ ] "PDF Aura ile Kes" seçeneği
- [ ] "PDF Aura ile Birleştir" seçeneği

### Komut Satırı (CLI) Desteği
- [ ] Terminal üzerinden sıkıştırma: `pdfaura compress input.pdf -q ebook`
- [ ] Terminal üzerinden kesme: `pdfaura split input.pdf --pages 1-100`
- [ ] Otomasyon ve script entegrasyonu için

### Bulut Entegrasyonu (İleri Seviye)
- [ ] Google Drive'dan dosya açma
- [ ] OneDrive entegrasyonu
- [ ] İşlenmiş dosyayı buluta yükleme

---

## 📌 Öncelik 10 — Yapay Zeka ve Sesli Asistan (AI & Voice)

### Sesli Komut ve Geri Bildirim (TTS / ASR) Akıllı Asistanı
Kullanıcının uygulamaya doğal dilde sesli komutlar vererek PDF işlemlerini (sıkıştırma, kesme, şifreleme vb.) otomatize etmesi hedeflenmektedir. Bu sistem uygulamayı tamamen eller serbest (hands-free) bir deneyime dönüştürür.

**Senaryo Örneği:**
1. Kullanıcı: *"Masaüstündeki 'finansal_rapor.pdf' dosyasını al, ilk 5 sayfasını kes, GİZLİ yazılı bir filigran ekle ve belgelerime kaydet."*
2. Sistem: (Sesi metne döker, analiz eder, arka planda işlemleri sırasıyla yapar).
3. Sistem Yanıtı: *"Dosyanız başarıyla kesildi, filigran eklendi ve Belgelerim klasörüne kaydedildi."*

### Detaylı Sistem Mimarisi ve Veri Akışı (Data Flow)

**A. Ses Yakalama ve Metne Dönüştürme Katmanı (Audio-to-Text / ASR)**
*   **Modül:** `src/ai/speech_recognizer.py`
*   **Teknoloji:** İnternet erişimi gerektiren durumlar için `SpeechRecognition` (Google Web Speech API). Tamamen yerel (offline) ve yüksek gizlilik gerektiren durumlar için **OpenAI Whisper** (tiny veya base model).
*   **Uyanma Kelimesi (Wake Word Engine):** Sistem tıpkı Siri gibi arka planda sürekli düşük güç modunda dinleme yapacak şekilde tasarlanır (Örn: `Picovoice Porcupine` veya `PocketSphinx` kütüphaneleri ile). Kullanıcı **"Hey Aura"** veya **"Merhaba Aura"** dediğinde sistem aktif(uyanık) dinleme moduna -yani asıl kayıt işlemine- geçer.
*   **İşleyiş:** Uyanma kelimesi algılandığında sistem tetiklenir, `PyAudio` üzerinden ana söylenen komut yakalanır. Gürültü engelleme (noise cancellation) uygulanır ve yakalanan ses paketi ASR modeline paslanıp düz metin (string) olarak NLP katmanına iletilir.

**B. Doğal Dil İşleme ve Niyet Çıkarımı Katmanı (NLP & Intent Parsing)**
*   **Modül:** `src/ai/intent_parser.py`
*   **Teknoloji:** Spacy (Türkçe NLP kütüphanesi) veya yerel / hafif bir LLM (HuggingFace üzerinden). Basit komutlar için karmaşık Regex algoritmaları.
*   **İşleyiş:** Dönüşen metin "Tokenize" edilir. Cümleden şu parametreler çıkarılır:
    1.  **Kaynak Target (Dosya):** Cümledeki dosya adı ve potansiyel path. (Örn: `finansal_rapor.pdf` -> `C:\Users\Username\Desktop\finansal_rapor.pdf` path'inde aranır).
    2.  **Operasyon (Action):** "kes", "böl", "sıkıştır", "şifrele" gibi fiiller tespit edilerek uygulamanın çekirdek metotlarıyla (`split_pdf`, `compress_pdf`, `encrypt_pdf`) eşlenir.
    3.  **Argümanlar (Kwargs):** "ilk 5 sayfası" -> `start=1, end=5`. "GİZLİ filigran" -> `text="GİZLİ"`. "Şifresi 1234" -> `password="1234"`.

**C. Orkestrasyon ve Çekirdek İşlem Katmanı (Orchestrator)**
*   **Modül:** `src/ai/action_runner.py`
*   **İşleyiş:** NLP modülünden gelen JSON formatındaki veri (`{"action": "split", "input": "...", "kwargs": {"start":1, "end":5}}`) alınır.
*   Uygulama zaten MVC (Modüler) yapıda olduğundan (`src/core/`), bu orchestrator doğrudan core fonksiyonları çalıştırır. (Örn: `from src.core.split import split_pdf`).
*   Bu katman, olası hata durumlarını (try-catch) yakalar: "Dosya bulunamadı", "Sayfa sayısı 5'ten küçük", "Sıkıştırma motoru hatası".

**D. Sesli Geri Bildirim ve Sentez Katmanı (Text-to-Speech / TTS)**
*   **Modül:** `src/ai/text_speaker.py`
*   **Teknoloji:** Windows sistemlerde çevrimdışı ve ücretsiz olduğu için `pyttsx3` (SAPI5 altyapısı) veya internet gerektiren `gTTS` (Google).
*   **İşleyiş:** İşlem başarılıysa veya yukarıdaki orkestratörden bir hata dönerse, bu mesaj dinamik bir cümle haline getirilir (Örn: *"Üzgünüm, masaüstünde bahsettiğiniz dosyayı bulamadım"*). `pyttsx3` bu cümleyi sistem hoparlöründen Türkçe olarak okur.

**E. Kullanıcı Deneyimi (GUI Entegrasyonu)**
*   Sekmelerin yanına bağımsız bir "AI Asistan" Floating Action Button'ı veya ayrı bir sekmesi yerleştirilir.
*   Dinleme esnasında ekranda animasyonlu bir "Dinleniyor..." ses dalgası (audio visualizer) gösterilir ve konuşma bittiğinde metne çevrilen hali küçük bir baloncukta (chat bubble) kullanıcıya gösterilerek işlemin onayı istenir veya otomatik gerçekleştirilir.

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

1. **PDF Birleştirme** — En çok istenen özellik
2. **Drag & Drop** — UX'i büyük ölçüde iyileştirir
3. **PDF → Resim dönüştürme** — Çok kullanılan bir ihtiyaç
4. **PDF Şifreleme** — Güvenlik hissi verir
5. **Sağ tık menü entegrasyonu** — Profesyonel hissettirir
6. **Hakkında penceresi + Splash screen** — Marka algısı

---

*Son güncelleme: 11 Nisan 2026*
*Proje: PDF Aura v2.0*
