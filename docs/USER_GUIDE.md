# PDF Aura — Kullanım Kılavuzu & User Guide

PDF Aura; yerel yapay zeka (Local AI) destekli, gizlilik odaklı (Privacy-First), modern ve çok işlevli masaüstü PDF yönetim aracıdır. Belgeleriniz asla internete veya üçüncü taraf bulut sunucularına aktarılmaz; tüm işlemler tamamen cihazınızda yerel olarak yürütülür.

PDF Aura is a privacy-first, local AI-powered, modern desktop PDF utility suite. All operations run 100% offline on your device, ensuring zero data leakage to cloud servers.

---

## 📑 İçindekiler / Table of Contents

- [Bölüm 1: Türkçe Kullanım Kılavuzu](#bölüm-1-türkçe-kullanım-kılavuzu)
  - [1. Giriş ve Gizlilik İlkeleri](#1-giriş-ve-gizlilik-ilkeleri)
  - [2. Sistem Gereksinimleri ve Kurulum](#2-sistem-gereksinimleri-ve-kurulum)
  - [3. Temel PDF Araçları](#3-temel-pdf-araçları)
    - [3.1. Sıkıştırma (Compress)](#31-sıkıştırma-compress)
    - [3.2. Bölme (Split)](#32-bölme-split)
    - [3.3. Birleştirme (Merge)](#33-birleştirme-merge)
    - [3.4. Sayfa Düzenleme (Rotate, Delete, Reorder)](#34-sayfa-düzenleme-rotate-delete-reorder)
  - [4. Belge Dönüştürme (Convert)](#4-belge-dönüştürme-convert)
    - [4.1. PDF -> Resim ve Resim -> PDF](#41-pdf---resim-ve-resim---pdf)
    - [4.2. PDF -> Word ve Word -> PDF](#42-pdf---word-ve-word---pdf)
    - [4.3. Tablo ve Excel Çıkarma](#43-tablo-ve-excel-çıkarma)
    - [4.4. Metin Çıkarımı (PDF -> TXT)](#44-metin-çıkarımı-pdf---txt)
  - [5. OCR ve Arama Yapılabilir PDF](#5-ocr-ve-arama-yapılabilir-pdf)
  - [6. Güvenlik ve Gizlilik Araçları](#6-güvenlik-ve-gizlilik-araçları)
    - [6.1. Şifreleme (Encrypt) ve Şifre Kaldırma (Decrypt)](#61-şifreleme-encrypt-ve-şifre-kaldırma-decrypt)
    - [6.2. Filigran Ekleme (Watermark)](#62-filigran-ekleme-watermark)
    - [6.3. Otomatik Hassas Bilgi Sansürleme (Redaction)](#63-otomatik-hassas-bilgi-sansürleme-redaction)
  - [7. Akıllı Belge Tarayıcı ve AI Tarama Kalite Kontrolü](#7-akıllı-belge-tarayıcı-ve-ai-tarama-kalite-kontrolü)
  - [8. Yerel Yapay Zeka (Local AI) Doküman Zekası](#8-yerel-yapay-zeka-local-ai-doküman-zekası)
    - [8.1. Yerel Model Yönetimi](#81-yerel-model-yönetimi)
    - [8.2. AI PDF Sohbeti (RAG ve Kaynak Gösterme)](#82-ai-pdf-sohbeti-rag-ve-kaynak-gösterme)
    - [8.3. Akıllı Özet Modları (Summarizer)](#83-akıllı-özet-modları-summarizer)
    - [8.4. PDF Karşılaştırma ve Fark Analizi (Compare)](#84-pdf-karşılaştırma-ve-fark-analizi-compare)
    - [8.5. Akıllı Dosya Adlandırma ve Sıralama (Smart Namer)](#85-akıllı-dosya-adlandırma-ve-sıralama-smart-namer)
    - [8.6. Öğrenci Modu (Student Mode: Sınav, Test, Flashcard)](#86-öğrenci-modu-student-mode-sınav-test-flashcard)
    - [8.7. PDF'ten Sunum Oluşturma (Presentation Mode)](#87-pdften-sunum-oluşturma-presentation-mode)
    - [8.8. AI Komut Çubuğu (Natural Language Command Bar)](#88-ai-komut-çubuğu-natural-language-command-bar)
  - [9. Toplu İşlemler (Batch Processing)](#9-toplu-işlemler-batch-processing)
  - [10. Komut Satırı Arayüzü (CLI Kullanımı)](#10-komut-satırı-arayüzü-cli-kullanımı)
  - [11. Sık Sorulan Sorular ve Sorun Giderme](#11-sık-sorulan-sorular-ve-sorun-giderme)
- [Part 2: English User Guide](#part-2-english-user-guide)
  - [1. Introduction & Privacy-First Architecture](#1-introduction--privacy-first-architecture)
  - [2. System Requirements & Installation](#2-system-requirements--installation)
  - [3. Core PDF Tools (Compress, Split, Merge, Edit)](#3-core-pdf-tools-compress-split-merge-edit)
  - [4. Document Conversion (Convert Suite)](#4-document-conversion-convert-suite)
  - [5. Optical Character Recognition (OCR)](#5-optical-character-recognition-ocr)
  - [6. Security & Privacy Suite (Encrypt, Decrypt, Watermark, Redact)](#6-security--privacy-suite-encrypt-decrypt-watermark-redact)
  - [7. Smart Document Scanner & AI Quality Audit](#7-smart-document-scanner--ai-quality-audit)
  - [8. Local AI Document Intelligence](#8-local-ai-document-intelligence)
  - [9. Batch Processing](#9-batch-processing)
  - [10. Command Line Interface (CLI Guide)](#10-command-line-interface-cli-guide)
  - [11. Frequently Asked Questions (FAQ) & Troubleshooting](#11-frequently-asked-questions-faq--troubleshooting)

---

# Bölüm 1: Türkçe Kullanım Kılavuzu

## 1. Giriş ve Gizlilik İlkeleri

PDF Aura; klasik PDF düzenleme araçları ile modern yerel yapay zeka teknolojisini birleştiren yeni nesil bir masaüstü yazılımıdır.

### Temel Prensipler
- **%100 Yerel Çalışma (Offline-First):** PDF dosyalarınız hiçbir zaman internete yüklenmez. Tüm sıkıştırma, birleştirme, OCR ve yapay zeka analizleri bilgisayarınızın işlemcisi (CPU) ve grafik kartı (GPU) üzerinde çalışır.
- **Sıfır Bulut Bağımlılığı & Aboneliksiz:** OpenAI, Gemini veya Anthropic gibi dış API'lere bağımlı değildir; API anahtarı girmenizi istemez.
- **Kalıcı Güvenlik:** Askeri sınıf AES-256 şifreleme ve gerçek PDF redaction (sansürlenen metnin dosya baytlarından kalıcı olarak silinmesi) sunar.

---

## 2. Sistem Gereksinimleri ve Kurulum

### Sistem Gereksinimleri
| Donanım Profili | Minimum | Önerilen | Kaliteli AI Modu |
| :--- | :--- | :--- | :--- |
| **İşletim Sistemi** | Windows 10/11 (64-bit) | Windows 10/11 (64-bit) | Windows 11 (64-bit) |
| **İşlemci (CPU)** | Intel Core i3 / AMD Ryzen 3 | Intel Core i5/i7 veya Ryzen 5/7 | Intel Core i7/i9 veya Ryzen 7/9 |
| **Bellek (RAM)** | 4 GB (Temel Araçlar) | 8 GB (Hafif AI & OCR) | 16 GB - 32 GB (Yerel LLM) |
| **Ekran Kartı** | Dahili Grafik Kartı | 4 GB VRAM (Opsiyonel) | 8 GB+ VRAM (NVIDIA CUDA) |
| **Depolama** | 500 MB (Uygulama) | 2 GB (OCR & Modeller) | 5-10 GB (GGUF LLM Modelleri) |

### Kurulum Adımları
1. **Windows Installer:** `PDFAura_Setup.exe` dosyasını çalıştırın. İsteğe bağlı olarak özellik seçimi (OCR paketleri, masaüstü kısayolu, Windows Gezgini sağ tık menüsü) yapabilirsiniz.
2. **Sessiz Kurulum:** Sistem yöneticileri için `PDFAura_Setup.exe /VERYSILENT /NORESTART` komutu ile sessiz kurulum desteklenir.
3. **Taşınabilir (Portable) Sürüm:** Kurulum gerektirmeyen `.zip` arşivini klasöre çıkartıp `PDFAura.exe` veya `run_app.py` ile doğrudan başlatabilirsiniz.

---

## 3. Temel PDF Araçları

### 3.1. Sıkıştırma (Compress)
PDF dosyalarının boyutunu görsel kalite kaybını asgari düzeyde tutarak küçültür.
- **Kullanım:** Sol menüden **Sıkıştır** sekmesine tıklayın. Dosyanızı sürükleyip bırakın veya seçin. Hedef kalite profilini belirleyin:
  - `screen`: Düşük çözünürlük (72 DPI) — E-posta ve web paylaşımları için maksimum küçültme.
  - `ebook`: Dengeli profil (150 DPI) — Dijital okuma ve arşivleme için önerilen varsayılan mod.
  - `printer`: Yüksek kalite (300 DPI) — Standart ofis baskıları için ideal.
  - `prepress`: Matbaa kalitesi (300+ DPI) — Orijinal renk profillerini koruyarak kayıpsız sıkıştırma.
- Çıktı dosyası varsayılan olarak `dosyaadi_compressed.pdf` olarak kaydedilir.

### 3.2. Bölme (Split)
Büyük belgelerden belirli sayfaları veya sayfa aralıklarını ayıklar.
- **Kullanım:** **Böl** sekmesine gidin. Giriş PDF'ini seçin.
- Sayfa aralığını girin (örnek: `1-5`, `10-25` veya tek sayfa için `7`).
- **İşlemi Başlat** butonuna basın; ayıklanan sayfalar yeni bir PDF olarak kaydedilir.

### 3.3. Birleştirme (Merge)
Birden fazla PDF dosyasını belirlediğiniz sırayla tek bir belge altında toplar.
- **Kullanım:** **Birleştir** sekmesine tıklayın. Birden fazla dosya ekleyin.
- Dosya listesindeki yukarı/aşağı butonları ile birleşme sırasını özelleştirin.
- Çıktı dosyasını adlandırıp **Birleştir**'e tıklayın.

### 3.4. Sayfa Düzenleme (Rotate, Delete, Reorder)
- **Sayfa Döndürme (Rotate):** Yanlış taranmış yatay veya baş aşağı sayfaları 90°, 180° veya 270° saat yönünde döndürün. Tüm sayfalara veya seçili sayfalara (örn: `1,3,5`) uygulanabilir.
- **Sayfa Silme (Delete):** İstenmeyen sayfaları virgülle belirterek belgeden tamamen çıkarın.
- **Sayfa Sıralama (Reorder):** Sayfa sıralamasını sürükle-bırak veya yeni indeks dizilimi (örn: `3,1,2,4-10`) ile güncelleyin.

---

## 4. Belge Dönüştürme (Convert)

### 4.1. PDF -> Resim ve Resim -> PDF
- **PDF -> Resim:** Sayfaları yüksek çözünürlüklü PNG veya JPG formatına çevirin. 150 DPI (ekran) veya 300 DPI (baskı) çözünürlük seçebilirsiniz.
- **Resim -> PDF:** JPG, PNG, BMP, TIFF formatındaki görselleri tek veya çok sayfalı bir PDF belgesine dönüştürün.

### 4.2. PDF -> Word ve Word -> PDF
- **PDF -> Word (.docx):** Metin tabanlı veya OCR ile işlenmiş PDF'leri düzenlenebilir Microsoft Word formatına dönüştürür. Başlıklar, paragraflar ve temel mizanpaj korunur.
- **Word -> PDF (.pdf):** DOCX dosyalarını mizanpajı bozulmadan PDF standartlarına uygun şekilde derler.

### 4.3. Tablo ve Excel Çıkarma
- PDF belgelerinde (fatura, ekstre, veri tablosu) yer alan tabloları otomatik tespit eder.
- Çıktıyı Microsoft Excel (`.xlsx`), CSV veya Markdown tablo formatında kaydeder.
- Taranmış belgelerde OCR destekli hücre hizalama ve sınır tespiti yapar.

### 4.4. Metin Çıkarımı (PDF -> TXT)
- Belgedeki tüm düz metni sayfa başlıkları ve paragraflar ile temiz bir `.txt` dosyasına aktarır.

---

## 5. OCR ve Arama Yapılabilir PDF

Taranmış belgeler ve fotoğraflar üzerindeki metinleri tanıyarak kopyalanabilir ve aranabilir hale getirir.
- **Tesseract ve PaddleOCR Desteği:** Türkçe, İngilizce, Almanca, Fransızca, Rusça, Arapça ve diğer dillerde yüksek doğruluklu metin tanıma.
- **Arama Yapılabilir PDF (Searchable PDF):** Taranmış sayfanın altına görünmez metin katmanı yerleştirir. Böylece belgenin orijinal görsel görünümü korunurken Ctrl+F ile arama ve metin kopyalama yapılabilir.
- **Toplu OCR:** Yüzlerce sayfadan oluşan arşivleri arka planda sırayla işler.

---

## 6. Güvenlik ve Gizlilik Araçları

### 6.1. Şifreleme (Encrypt) ve Şifre Kaldırma (Decrypt)
- **AES-256 Şifreleme:** Endüstri standardı 256-bit AES şifreleme algoritması ile belgelerinizi yetkisiz erişime karşı koruyun.
- **İzin Yönetimi:** Belgeye erişim parolası haricinde yazdırma, metin kopyalama veya form doldurma izinlerini sınırlandırabilirsiniz.
- **Şifre Kaldırma:** Parolasını bildiğiniz korumalı PDF'lerin şifresini tek tıkla çözün.

### 6.2. Filigran Ekleme (Watermark)
- Belgenin tüm sayfalarına çapraz veya yatay metin damgaları ekleyin (örn: "GİZLİ", "KOPYA", "DRAFT", şirket adı).
- Saydamlık (opacity 0.0 - 1.0), döndürme açısı (0° - 360°) ve yazı tipi boyutunu hassas ayarlayın.

### 6.3. Otomatik Hassas Bilgi Sansürleme (Redaction)
- **Hassas Veri Tespiti:** TC Kimlik Numarası, telefon numarası, e-posta adresi, IBAN, kredi kartı ve vergi numaralarını otomatik yakalar.
- **Kalıcı İmha (True Redaction):** Üzerine sadece siyah kutu çizilmez; ilgili metin ve piksel verisi PDF dosyasının ham bayt yapısından tamamen silinir. Metin arama veya kopyalama ile geri getirilemez.

---

## 7. Akıllı Belge Tarayıcı ve AI Tarama Kalite Kontrolü

Masaüstü veya bağlı tarayıcılardan alınan belge fotoğraflarını profesyonel dijital belgelere dönüştürür.
- **Yapay Zeka Kenar Tespiti:** Belge sınırlarını ve köşelerini milisaniyeler içinde tespit eder; perspektif bozulmasını otomatik düzeltir.
- **Tarama Kalite Denetimi:**
  - *Bulanıklık Analizi:* Laplacian varyans yöntemi ile fotoğrafın netliğini ölçer.
  - *Parlama ve Gölge Tespiti:* Histogram ve yerel kontrast ölçümleri ile aşırı aydınlık veya karanlık gölgeli bölgeleri bildirir.
  - *Kalite Skoru:* "Mükemmel", "İyi", "Orta" veya "Tekrar Çekim Önerilir" durum rozeti gösterir.

---

## 8. Yerel Yapay Zeka (Local AI) Doküman Zekası

PDF Aura'nın en güçlü yönü, bilgisayarınızda yerel çalışan LLM (Büyük Dil Modeli) motorudur.

### 8.1. Yerel Model Yönetimi
- **Ayarlar > Yerel AI Modelleri** ekranından sisteminize uygun modelleri yönetebilirsiniz.
- GGUF formatındaki optimize modelleri (Qwen, Mistral vb.) tek tıkla indirebilir veya bilgisayarınızdaki mevcut modeli seçebilirsiniz.
- Hafif mod (CPU için optimize), Standart mod (8-16 GB RAM) ve Kalite modu (GPU hızlandırmalı) profilleri sunulur.

### 8.2. AI PDF Sohbeti (RAG ve Kaynak Gösterme)
- Belgenizi seçip doğal dille soru sorun: *"Bu sözleşmede fesih süresi kaç gün?", "İkinci sayfadaki garanti şartları neler?"*
- **Sıfır Halüsinasyon Prensibi:** Model yalnızca belge içeriğinden cevap üretir; bilgiyi bulamazsa tahmin yürütmek yerine net olarak belirtir.
- **Kaynak Gösterme:** Her cevabın yanında ilgili sayfa numarası ve doğrudan alıntı metni gösterilir; tıklayarak ilgili sayfaya gidebilirsiniz.

### 8.3. Akıllı Özet Modları (Summarizer)
- **Kısa Özet (Executive Summary):** 3-5 maddede ana fikri çıkartır.
- **Detaylı Özet:** Bölüm bazlı kapsamlı sentez sunar.
- **Hukuki / Kontrat Özeti:** Yükümlülükleri, cezai şartları ve tarihleri listeler.
- **Öğrenci Özeti:** Ana kavramları, tanımları ve formülleri derler.
- Çıktılar `.txt`, Markdown veya yeni bir PDF raporu olarak dışa aktarılabilir.

### 8.4. PDF Karşılaştırma ve Fark Analizi (Compare)
- İki PDF dosyasını yan yana karşılaştırır.
- Metin ekleme, çıkarma ve değiştirme farklarını sayfa sayfa vurgular.
- Yerel AI, farkları semantik olarak sınıflandırır: *"Önemsiz biçim değişikliği", "Anlam değişikliği", "Kritik / Riskli madde değişikliği"*.

### 8.5. Akıllı Dosya Adlandırma ve Sıralama (Smart Namer)
- Belgenin içeriğini, tarihini, kişi/kurum bilgisini analiz eder.
- Şablon bazlı otomatik isim önerir: `{belge_turu}_{tarih}_{kurum_veya_konu}.pdf`.
- Örnek: `Elektrik_Faturasi_Nisan_2026.pdf`, `Kira_Sozlesmesi_Ahmet_Yilmaz.pdf`.
- Toplu işlemlerde dosyaları otomatik olarak mantıksal alt klasörlere ayırabilir.

### 8.6. Öğrenci Modu (Student Mode: Sınav, Test, Flashcard)
- Ders notları veya akademik kitaplardan çalışma materyali üretir:
  - **10 Test Sorusu:** 4 seçenekli çoktan seçmeli sorular ve cevap anahtarı.
  - **Doğru / Yanlış & Boşluk Doldurma:** Bilgiyi pekiştiren alıştırmalar.
  - **Flashcard (Bilgi Kartı):** Ön yüzünde soru/kavram, arka yüzünde açıklama ve kaynak sayfa.
- Yazdırılabilir sınav çalışma kağıdı (Worksheet PDF) çıktısı alınabilir.

### 8.7. PDF'ten Sunum Oluşturma (Presentation Mode)
- Uzun raporları veya makaleleri 6-10 slaytlık düzenli bir sunum taslağına dönüştürür.
- Her slayt için vurucu başlık, 3-4 ana madde ve kaynak sayfa referansı oluşturur.
- Çıktıyı doğrudan Microsoft PowerPoint (`.pptx`) formatında kaydeder.

### 8.8. AI Komut Çubuğu (Natural Language Command Bar)
- Klavyeden `Ctrl+K` ile komut çubuğunu açıp doğrudan yazın:
  - *"Bu dosyayı sıkıştır ve ilk 3 sayfasını ayır"*
  - *"Belgedeki tüm TC kimlik numaralarını sansürle"*
  - *"150 DPI ile resimlere çevir"*
- Planlama motoru komutu doğrular, adımları kullanıcıya onaylatır ve güvenle icra eder.

---

## 9. Toplu İşlemler (Batch Processing)

Yüzlerce dosya üzerinde tek seferde işlem yapın:
- **Toplu Sıkıştırma:** Bir klasör dolusu PDF'i seçilen kalite profilinde küçültür.
- **Toplu Dönüştürme:** Yüzlerce Word veya görsel dosyasını tek seferde PDF'e çevirir.
- **Toplu Yeniden Adlandırma:** Akıllı şablonlar ile dosyaları organize eder.

---

## 10. Komut Satırı Arayüzü (CLI Kullanımı)

PDF Aura, betiklerle otomasyon ve sunucu ortamları için güçlü bir CLI sunar.

Komut yapısı:
```bash
python -m src.cli <KOMUT> [PARAMETRELER]
# Veya sistem yoluna eklendiyse:
pdfaura <KOMUT> [PARAMETRELER]
```

### Başlıca CLI Komutları ve Örnekler:
```bash
# 1. PDF Sıkıştırma (ebook, screen, printer, prepress)
python -m src.cli compress dosya.pdf -q ebook -o dosya_kucuk.pdf

# 2. Sayfa Bölme (Örnek: 1-10 sayfaları)
python -m src.cli split dosya.pdf --pages 1-10 -o bolum1.pdf

# 3. PDF Birleştirme
python -m src.cli merge rapor1.pdf rapor2.pdf rapor3.pdf -o tam_rapor.pdf

# 4. Sayfa Döndürme (90, 180, 270 derece)
python -m src.cli rotate dosya.pdf --pages 1,3-5 --angle 90 -o cevrilmis.pdf

# 5. Şifreleme (AES-256)
python -m src.cli encrypt gizli.pdf -p GizliParola123 -o kilitli.pdf

# 6. Şifre Çözme
python -m src.cli decrypt kilitli.pdf -p GizliParola123 -o acik.pdf

# 7. Filigran Ekleme
python -m src.cli watermark sozlesme.pdf -t "GİZLİDİR" --opacity 0.25 --angle 45 -o filigranli.pdf

# 8. Sayfaları Resme Dönüştürme (DPI: 150 veya 300, Format: png veya jpg)
python -m src.cli to-images sunum.pdf -o resimler_klasoru --dpi 300 --format png
```

---

## 11. Sık Sorulan Sorular ve Sorun Giderme

**S: PDF Aura belgelerimi internete yüklüyor mu?**  
*C:* Kesinlikle hayır. PDF Aura mimari olarak "Offline-First" tasarlanmıştır. AI modelleri ve tüm araçlar yerel bilgisayarınızda çalışır.

**S: Yapay zeka özelliklerini kullanmak için internete veya API anahtarına ihtiyacım var mı?**  
*C:* Hayır. Uygulama yerel GGUF modellerini çalıştırır; OpenAI veya Gemini API anahtarı girmeniz gerekmez.

**S: Büyük PDF dosyalarında donma yaşanır mı?**  
*C:* Hayır. Tüm işlemler arka plan iş parçacıklarında (background worker threads) yürütülür; arayüz akıcı kalır ve işlem istenildiği an iptal edilebilir.

---
---

# Part 2: English User Guide

## 1. Introduction & Privacy-First Architecture

PDF Aura is an all-in-one, privacy-first desktop PDF suite powered by cutting-edge local AI. Designed for professionals, students, researchers, and enterprises, PDF Aura runs 100% offline.

### Key Pillars
- **Zero Cloud Leakage:** Your documents never touch external servers or third-party cloud APIs.
- **Local AI Intelligence:** Chat with documents, generate summaries, quizzes, and slide decks using offline LLMs (GGUF format via llama.cpp/local inference).
- **Military-Grade Security:** True PDF redaction and AES-256 encryption.

---

## 2. System Requirements & Installation

### Hardware Profiles
- **Lightweight Mode (Core tools, basic OCR):** 4 GB RAM, dual-core CPU.
- **Standard Mode (Fast OCR & 3B/7B Local LLM):** 8-16 GB RAM, modern quad-core CPU.
- **Pro Quality Mode (Large LLMs, GPU accelerated):** 16-32 GB RAM, NVIDIA CUDA GPU (optional).

### Setup Methods
- **Windows Installer:** Run `PDFAura_Setup.exe` with optional component selection and context menu integration.
- **Silent Deployment:** Run `PDFAura_Setup.exe /VERYSILENT /NORESTART` for unattended enterprise rollouts.
- **Portable Edition:** Extract the portable archive and execute `PDFAura.exe`.

---

## 3. Core PDF Tools (Compress, Split, Merge, Edit)

### 3.1. Compress
Drastically reduce PDF file sizes while preserving visual readability.
- **Profiles:**
  - `screen`: 72 DPI — maximum shrinkage for email attachments.
  - `ebook`: 150 DPI — balanced default for reading and archiving.
  - `printer`: 300 DPI — crisp output for physical office printing.
  - `prepress`: 300+ DPI — lossless quality preservation for professional press.

### 3.2. Split
Extract individual pages or consecutive page ranges (e.g. `1-5`, `8-20`) into standalone PDF documents.

### 3.3. Merge
Combine multiple PDF files in any custom order. Reorder items with intuitive up/down controls or drag-and-drop.

### 3.4. Edit (Rotate, Delete, Reorder)
- **Rotate:** Adjust upside-down or sideways pages by 90°, 180°, or 270°.
- **Delete:** Remove arbitrary pages safely.
- **Reorder:** Rearrange page sequence visually or via index rules.

---

## 4. Document Conversion (Convert Suite)

- **PDF to Images & Images to PDF:** High-resolution export (PNG/JPG at 150 or 300 DPI) and multi-image compiling into standardized PDFs.
- **PDF to Word & Word to PDF:** Seamless bidirectional document conversion (.docx <-> .pdf) preserving typography and layout.
- **Table Extraction to Excel:** Automatic table boundary detection exporting to Microsoft Excel (`.xlsx`), CSV, or Markdown tables.
- **Plain Text Extraction:** Extract sanitized, cleanly separated text into `.txt`.

---

## 5. Optical Character Recognition (OCR)

Convert non-searchable scanned documents and photos into accessible, fully searchable PDFs.
- **Engines:** Tesseract and PaddleOCR integration.
- **Multilingual Recognition:** Turkish, English, German, French, Spanish, Arabic, and more.
- **Searchable PDF Layer:** Generates an invisible, selectable text layer beneath the original raster image so you can search using `Ctrl+F` and copy text effortlessly.

---

## 6. Security & Privacy Suite (Encrypt, Decrypt, Watermark, Redact)

- **AES-256 Encryption:** Secure confidential files with enterprise passwords and granular permissions (preventing copying, printing, or form modification).
- **Password Removal (Decrypt):** Strip protection with authorized passwords.
- **Custom Watermarks:** Add stamps (e.g. "CONFIDENTIAL", "DRAFT") with adjustable font size, angle, and opacity.
- **Automated Redaction:** Automatically detects sensitive patterns (SSN, national IDs, credit cards, emails, phone numbers, IBANs) and applies destructive redaction—permanently wiping underlying vector and text streams.

---

## 7. Smart Document Scanner & AI Quality Audit

Transform smartphone or flatbed scans into clean digital PDFs.
- **AI Corner & Edge Detection:** Fast, automatic quadrangular boundary detection with perspective keystone correction.
- **Scan Quality Audit:** Real-time analysis for blurriness (Laplacian variance), glare, and harsh shadows. Provides an instant quality badge ("Good", "Medium", "Retake recommended").

---

## 8. Local AI Document Intelligence

### 8.1. Local Model Management
Easily download and manage quantized GGUF models directly within the Settings menu. No external dependencies required.

### 8.2. AI Document Chat & RAG
Engage in contextual Q&A with your documents. Every response includes verifiable page citations and exact text excerpts. Zero hallucination guarantee.

### 8.3. Smart Summarizer
Choose tailored summary modes: Executive, Detailed, Contract/Legal, or Student Study summary. Export as TXT, Markdown, or PDF.

### 8.4. Document Compare
Compare two document revisions side-by-side. Highlights textual, layout, and structural differences with AI-driven semantic impact ratings (minor vs. critical changes).

### 8.5. Smart File Naming & Organization
Analyze document headers and contents to suggest structured filenames (e.g., `{doc_type}_{date}_{topic}.pdf`) and auto-sort into categorized folders.

### 8.6. Student Mode (Study Sheets, Quizzes, Flashcards)
Transform lecture notes and textbooks into:
- 10-Question multiple-choice quizzes with answer keys.
- Fill-in-the-blank and True/False drills.
- Interactive flashcard decks with source page citations.

### 8.7. Presentation Generator
Convert lengthy reports into clean, ready-to-present PowerPoint (`.pptx`) slide decks complete with concise bullet points and citations.

### 8.8. AI Command Bar
Press `Ctrl+K` to execute natural language tasks like: *"Compress this PDF and remove page 4"*.

---

## 9. Batch Processing

Automate mass workflows across hundreds of files:
- Batch Compress with quality thresholds.
- Batch Convert between PDF, DOCX, and images.
- Batch Smart Rename following predefined naming patterns.

---

## 10. Command Line Interface (CLI Guide)

PDF Aura includes a comprehensive CLI for background automation and headless operation.

Syntax:
```bash
python -m src.cli <COMMAND> [OPTIONS]
# Or directly:
pdfaura <COMMAND> [OPTIONS]
```

### CLI Command Reference:
- **Compress:** `python -m src.cli compress doc.pdf -q ebook -o compressed.pdf`
- **Split:** `python -m src.cli split doc.pdf --pages 1-5 -o part1.pdf`
- **Merge:** `python -m src.cli merge a.pdf b.pdf c.pdf -o merged.pdf`
- **Rotate:** `python -m src.cli rotate doc.pdf --pages 1-3 --angle 90 -o rotated.pdf`
- **Encrypt:** `python -m src.cli encrypt doc.pdf -p MyPass -o secure.pdf`
- **Decrypt:** `python -m src.cli decrypt secure.pdf -p MyPass -o open.pdf`
- **Watermark:** `python -m src.cli watermark doc.pdf -t "CONFIDENTIAL" --opacity 0.3 -o stamped.pdf`
- **To Images:** `python -m src.cli to-images doc.pdf -o out_folder --dpi 300 --format png`

---

## 11. Frequently Asked Questions (FAQ) & Troubleshooting

**Q: Are my documents uploaded to any remote server?**  
*A:* No. PDF Aura is strictly local-first. All processing runs entirely on your local machine.

**Q: Do I need an OpenAI API key or paid subscription?**  
*A:* No. PDF Aura includes built-in offline AI runtimes and models. No external API keys or subscriptions are ever required.

**Q: Can I use PDF Aura in commercial environments?**  
*A:* Yes. All included tools and default models are licensed for professional and commercial use.
