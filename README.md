<div align="center">

<img src="assets/icon.png" width="132" alt="PDF Aura logosu" />

# PDF Aura

### Windows için çevrimdışı, reklamsız ve yapay zekâ destekli PDF stüdyosu

Sıkıştırın, tarayın, kesin, birleştirin, dönüştürün ve şifreleyin.<br />
Belgeleriniz hiçbir sunucuya yüklenmez; her işlem kendi bilgisayarınızda yapılır.

<br />

<a href="#-kurulum"><img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows 10 ve 11" /></a>
<a href="#-kurulum"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+" /></a>
<a href="https://github.com/AsirCan/PDFAura/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/AsirCan/PDFAura/tests.yml?branch=main&style=for-the-badge&label=testler&logo=githubactions&logoColor=white" alt="Testler" /></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/Lisans-MIT-4F6BFF?style=for-the-badge" alt="MIT lisansı" /></a>
<br />
<a href="#-gizlilik"><img src="https://img.shields.io/badge/Belgeler-yerelde%20kal%C4%B1r-059669?style=for-the-badge&logo=shieldsdotio&logoColor=white" alt="Belgeler yerelde kalır" /></a>
<a href="#-gizlilik"><img src="https://img.shields.io/badge/Reklam-yok-DC2626?style=for-the-badge&logo=adblock&logoColor=white" alt="Reklam yok" /></a>
<a href="#-arayüz"><img src="https://img.shields.io/badge/Aray%C3%BCz-14%20dil-8B5CF6?style=for-the-badge&logo=googletranslate&logoColor=white" alt="14 arayüz dili" /></a>
<a href="#-nasıl-çalışır"><img src="https://img.shields.io/badge/Yapay%20zek%C3%A2-U2--Net%20%2B%20Whisper-F59E0B?style=for-the-badge&logo=onnx&logoColor=white" alt="U2-Net ve Whisper" /></a>

<br />

[**Özellikler**](#-özellikler) &nbsp;•&nbsp;
[**Tanıtım videoları**](#-yakından-bakış) &nbsp;•&nbsp;
[**Kurulum**](#-kurulum) &nbsp;•&nbsp;
[**Nasıl çalışır?**](#-nasıl-çalışır) &nbsp;•&nbsp;
[**SSS**](#-sık-sorulan-sorular) &nbsp;•&nbsp;
[**Yol haritası**](#-yol-haritası)

</div>

<br />

https://github.com/user-attachments/assets/d833ff09-a121-4ea8-9124-70190dd4c518

<p align="center"><sub>Yedi araç tek pencerede. Açık, koyu ve sistem teması anında değişir; yeniden başlatma gerekmez.</sub></p>

---

## ✨ Özellikler

Çevrim içi PDF araçlarının çoğu dosyanızı uzak bir sunucuya yükler, reklam gösterir, dosya boyutunu sınırlar ya da abonelik ister. **PDF Aura** bunların hiçbirini yapmaz: masaüstünüzde çalışan, reklamsız ve sınırsız bir araç setidir.

<table>
  <tr>
    <td width="33%" valign="top">
      <h3>🔒 Belgeleriniz sizde kalır</h3>
      Sıkıştırma, dönüştürme, şifreleme ve tarama tamamen yerelde yapılır. Hesap, bulut ya da izleyici yoktur.
    </td>
    <td width="33%" valign="top">
      <h3>📷 Telefonla belge tarama</h3>
      Fotoğraftaki kâğıdın köşelerini bulur, perspektifi düzeltir ve gölgeleri temizleyerek çok sayfalı bir PDF üretir.
    </td>
    <td width="33%" valign="top">
      <h3>🗜️ Gerçek sıkıştırma</h3>
      Ghostscript tabanlı dört profille taranmış bir sözleşme 5,3 MB'tan 0,5 MB'a iner. Önceki ve sonraki boyutu ekranda görürsünüz.
    </td>
  </tr>
  <tr>
    <td width="33%" valign="top">
      <h3>🔄 Tek yerde dönüştürme</h3>
      PDF ↔ Word, Excel, PowerPoint, resim ve düz metin. Office dosyaları için Microsoft Office ya da ücretsiz LibreOffice kullanılır.
    </td>
    <td width="33%" valign="top">
      <h3>🎙️ Konuşarak komut verin</h3>
      <i>"rapor.pdf ilk 3 sayfayı ayır"</i> yazın ya da söyleyin. Ses tanıma yerel Faster-Whisper modeliyle çalışır.
    </td>
    <td width="33%" valign="top">
      <h3>🎨 Modern arayüz</h3>
      Açık, koyu ve sistem teması, 14 arayüz dili, sürükle-bırak, canlı önizleme ve klavye kısayolları.
    </td>
  </tr>
</table>

### Bir bakışta tüm araçlar

| Araç | Neler yapabilirsiniz? |
| :--- | :--- |
| 📷 **Belge Tara** | Fotoğraftan PDF, yapay zekâ destekli 4 köşe tespiti, büyüteçli köşe düzenleme, tam ekran kırpma, sayfa sıralama ve adlandırma, 5 görüntü filtresi, oturumun otomatik kaydı |
| 🗜️ **Sıkıştır** | `screen`, `ebook`, `printer` ve `prepress` profilleri (72–300 dpi), sonuç boyutunun raporu |
| ✂️ **Düzenle** | Sayfa aralığı kesme, sınırsız PDF birleştirme (Yukarı/Aşağı ile sıralama), sayfa silme, 90°/180°/270° döndürme ve yeniden sıralama |
| 🔄 **Dönüştür** | PDF → Resim (PNG/JPG, DPI seçimi), Resim → PDF, PDF → Word, Word / Excel / PowerPoint → PDF, PDF → Metin |
| 🔐 **Güvenlik** | AES-256 parola koruması, parola kaldırma, Türkçe karakter destekli metin filigranı |
| 🧰 **Gelişmiş** | Dahili PDF önizleyici, Tesseract OCR, meta veri düzenleme ve temizleme, sayfa ve koordinat seçerek görsel imza basma |
| 📦 **Toplu İşlemler** | Bir klasördeki tüm PDF'leri sıkıştırma, dönüştürme ya da şablonla yeniden adlandırma, işlem günlüğü |
| 🤖 **Aura Asistan** | Yazılı ve sesli Türkçe/İngilizce komutlar, yanıtın ekranda gösterilmesi ve sesli okunması |

---

## 🎬 Yakından bakış

Aşağıdaki videolar uygulamanın güncel sürümünden kaydedildi. Her işlem gerçekten çalıştırıldı; belgeler kurgusal örneklerdir.

### 1. Akıllı belge tarayıcı

> **Telefonla çektiğiniz fişleri, faturaları ve sözleşmeleri tarayıcı kalitesinde PDF'e dönüştürün.**

Fotoğrafları pencereye sürükleyin. PDF Aura kâğıdın sınırlarını bulur; yanlış yakaladığı köşeyi büyüteçle tutup doğru yere çekebilirsiniz. **Temiz Belge** filtresi arka planı beyazlatır ve gölgeleri siler. Sayfaları sürükleyerek sıralayabilir, çift tıklayarak adlandırabilirsiniz. Çalışmanız otomatik kaydedilir; uygulama kapansa bile kaldığınız yerden devam edersiniz.

https://github.com/user-attachments/assets/be5c3994-be5e-45b8-8060-7a71e89c27cd

### 2. PDF sıkıştırma

> **Görüntü kalitesini koruyarak dosya boyutunu küçültün.**

E-posta için `screen`, günlük kullanım için `ebook`, baskı için `printer` ya da matbaa için `prepress`. Sıkıştırma bitince özgün ve yeni boyut yan yana gösterilir; çıktıyı ya da klasörünü tek tıkla açabilirsiniz.

https://github.com/user-attachments/assets/0690e03b-9bdd-4cb7-97bf-0c48254090bc

### 3. Sayfa yönetimi: kes, birleştir, düzenle

> **Belgelerinizi istediğiniz gibi parçalayın, birleştirin ve yeniden düzenleyin.**

Bir rapordan yalnızca ihtiyacınız olan sayfaları ayırın, birden fazla PDF'i istediğiniz sırada tek dosyada toplayın. Düzenle sekmesinde sayfa silebilir, döndürebilir ve sayfa sırasını değiştirebilirsiniz.

https://github.com/user-attachments/assets/1c75293f-c691-4e5d-91b5-ef3d576b7d12

### 4. Format dönüştürücü

> **Office belgeleri, görseller ve PDF arasında tek panelden geçiş yapın.**

PDF'i düzenlenebilir bir Word belgesine çevirin, Word, Excel ve PowerPoint dosyalarını PDF yapın, sayfaları yüksek çözünürlüklü PNG/JPG olarak dışa aktarın ya da metni `.txt` olarak alın. Microsoft Office kurulu değilse LibreOffice otomatik devreye girer.

https://github.com/user-attachments/assets/a75e6bba-afbb-485d-924c-3fc2a2b549c8

### 5. Güvenlik ve filigran

> **Gizli belgeleri işaretleyin ve parolayla kilitleyin.**

Sayfalara "GİZLİ" gibi bir filigran ekleyin, ardından belgeyi AES-256 ile şifreleyin. Parolasını bildiğiniz bir PDF'in korumasını da aynı yerden kaldırabilirsiniz.

https://github.com/user-attachments/assets/a72b5b86-19ac-427d-a977-80ec6d4f359d

### 6. Gelişmiş araçlar: önizleme, OCR, meta veri, imza

> **Belgeyi inceleyin, metnini çıkarın, künyesini düzenleyin, imzanızı basın.**

Dahili önizleyicide sayfalar arasında gezinin ve yakınlaştırın. Tesseract OCR ile taranmış PDF'lerdeki metni çıkarın (Tesseract'ı uygulama içinden kurabilirsiniz). Başlık, yazar, konu ve oluşturan bilgilerini düzenleyin ya da tamamen temizleyin. İmza görselinizi seçtiğiniz sayfaya ve konuma yerleştirin.

https://github.com/user-attachments/assets/55a8d18c-2a89-4952-8e2e-b026bdafc797

### 7. Toplu işlemler

> **Bir klasör dolusu belgeyi tek seferde işleyin.**

Klasörü pencereye bırakın; içindeki tüm PDF'leri sıkıştırın, resme ya da PDF'e dönüştürün veya `Fatura_[TARIH]_[ORIJINAL_AD]_[SIRA]` gibi bir şablonla yeniden adlandırın. Şablonda `[ORIJINAL_AD]`, `[SAYFA_SAYISI]`, `[BOYUT]`, `[SIRA]` ve `[TARIH]` kullanılabilir. Kaç dosyanın başarıyla işlendiği günlükte görünür.

https://github.com/user-attachments/assets/561fd51f-515a-4f68-a22d-c58d80d3913b

### 8. Aura Asistan: yazılı ve sesli komutlar

> **Menülerde gezinmeden, ne istediğinizi söyleyin.**

Sağ üstteki komut çubuğuna yazın (<kbd>Ctrl</kbd>+<kbd>K</kbd>) ya da mikrofon düğmesine basılı tutup konuşun. Asistan dosyayı Masaüstü, Belgeler ve İndirilenler klasörlerinde bulur, işlemi yapar; yanıtı hem ekranda gösterir hem sesli okur.

https://github.com/user-attachments/assets/c48b10e6-c294-4e4e-af67-bb5b85ee8185

Çalışan örnek komutlar:
- *"rapor.pdf dosyasını sıkıştır"*
- *"rapor.pdf ilk 3 sayfayı ayır"*
- *"a.pdf ve b.pdf dosyalarını birleştir"*
- *"rapor.pdf dosyasını Word'e çevir"*
- *"rapor.pdf dosyasını abc123 ile şifrele"*
- *"Masaüstündeki sözleşmeyi sıkıştır"* (uzantısız ad Masaüstü / Belgeler / İndirilenler klasörlerinde aranır)

Arayüz İngilizceyken İngilizce komutlar da anlaşılır (*"compress report.pdf"*).

> [!NOTE]
> Ses tanıma modeli mikrofon ilk kez kullanıldığında yüklenir ve bu ilk yükleme için (~460 MB) internet bağlantısı gerekir. Model indirildikten sonra tanıma tamamen çevrimdışı çalışır. Yazılı komutlar için hiçbir indirme gerekmez.

---

## 🎨 Arayüz

- **Kenar çubuğunda yedi araç.** <kbd>Ctrl</kbd>+<kbd>1</kbd> … <kbd>Ctrl</kbd>+<kbd>7</kbd> ile araçlar arasında geçersiniz. Son üretilen dosyalar da kenar çubuğunda listelenir.
- **Açık, koyu ve sistem teması.** Sistem seçeneği Windows'un uygulama modunu izler; değişiklik anında uygulanır.
- **14 arayüz dili:** Türkçe, English, 中文, हिन्दी, Español, العربية, Français, বাংলা, Português, Русский, اردو, Bahasa Indonesia, Deutsch, 日本語. İlk açılışta Windows dilinize göre seçilir.
- **Sürükle-bırak her yerde.** PDF'leri, fotoğrafları ve klasörleri doğrudan pencereye bırakın.
- **Canlı önizleme paneli.** Seçtiğiniz PDF'in ilk sayfası, sayfa sayısı ve boyutu hemen görünür.
- **Sistem tepsisi.** İsterseniz pencereyi kapatınca uygulama tepside çalışmaya devam eder.

### Klavye kısayolları

| Kısayol | İşlev |
| :--- | :--- |
| <kbd>Ctrl</kbd>+<kbd>1</kbd> … <kbd>Ctrl</kbd>+<kbd>7</kbd> | Sıkıştır, Düzenle, Belge Tara, Dönüştür, Güvenlik, Gelişmiş, Toplu İşlemler |
| <kbd>Ctrl</kbd>+<kbd>K</kbd> | Aura Asistan komut çubuğuna geç |
| <kbd>Ctrl</kbd>+<kbd>,</kbd> | Ayarlar |
| <kbd>←</kbd> <kbd>→</kbd> · <kbd>PgUp</kbd> <kbd>PgDn</kbd> | Önizleyicide önceki / sonraki sayfa |
| <kbd>Home</kbd> · <kbd>End</kbd> | Önizleyicide ilk / son sayfa |
| <kbd>+</kbd> · <kbd>-</kbd> | Önizleyicide yakınlaştır / uzaklaştır |
| <kbd>Esc</kbd> | Önizleyiciyi ya da Ayarlar penceresini kapat |

---

## 🧠 Nasıl çalışır?

PDF Aura bir Python masaüstü uygulamasıdır. Arayüz Tkinter/ttk üzerine kurulu, token tabanlı bir tema sistemi kullanır. Uzun işlemler arka planda çalışır; bu sırada arayüz donmaz ve çoğu işlemi yarıda iptal edebilirsiniz.

```mermaid
flowchart LR
    UI["Arayüz<br/>Tkinter · ttk · TkinterDnD"] --> Core["Çekirdek araçlar"]
    UI --> AI["Yerel yapay zekâ"]
    Core --> P1["pypdf · PyMuPDF<br/>kes, birleştir, şifrele, önizle"]
    Core --> P2["Ghostscript<br/>sıkıştırma"]
    Core --> P3["MS Office / LibreOffice · pdf2docx<br/>dönüştürme"]
    Core --> P4["Tesseract<br/>OCR"]
    Core --> P5["ReportLab<br/>filigran ve imza"]
    AI --> A1["OpenCV + U2-Net ONNX<br/>belge köşe tespiti"]
    AI --> A2["Faster-Whisper<br/>ses tanıma"]
    AI --> A3["Kural tabanlı ayrıştırıcı<br/>komut → işlem"]
```

### Belge tarayıcının köşe tespiti

Köşe tespitinde **hibrit bir boru hattı** kullanılır. Hızlı klasik yöntemler önce denenir; derin öğrenme modeli yedek olarak devreye girer:

```mermaid
flowchart LR
    A["Girdi Fotoğrafı"] --> B{"Tespit Motorları"}
    B -->|"Öncelik 1"| E["Çizgi Tespiti (Hough)"]
    B -->|"Öncelik 2"| D["Hızlı CV (Canny, Kontur, Morfoloji)"]
    B -->|"Öncelik 3 (yedek)"| C["ONNX U2-Net / U2-Net-P"]
    E --> F["Kalite Değerlendirme & Skorlama"]
    D --> F
    C --> F
    F --> G["En Yüksek Skorlu 4 Köşe"]
    G --> H["Perspektif Düzeltme (Warp) & A4 Normalizasyonu"]
    H --> I["Görüntü Filtresi & Çok Sayfalı PDF Çıktısı"]
```

Bulunan her dörtgen dört ölçüte göre puanlanır:

1. **Kenar skoru (%35):** Köşelerin fotoğraf kenarlarına uzaklığı ve netliği.
2. **Alan skoru (%25):** Belgenin fotoğrafın %15–95'lik mantıklı bir alanını kaplaması.
3. **En-boy oranı (%20):** A4 / Letter oranlarına uygunluk (1:1 ile 3:1 arası).
4. **Açı skoru (%20):** Dört köşenin 90 dereceye yakınlığı.

Tarama filtreleri: **Temiz Belge** (arka plan bölme), **Siyah-Beyaz** (adaptif eşikleme), **Gri Tonlama** (CLAHE), **Keskin Belge** ve **Orijinal** (yalnızca kırpma).

---

## 🔒 Gizlilik

- Belgeleriniz hiçbir sunucuya gönderilmez; tüm PDF işlemleri bilgisayarınızda yapılır.
- Uygulamada reklam, hesap, telemetri ya da üçüncü taraf izleyici yoktur.
- İnternet yalnızca sizin başlattığınız indirmeler için kullanılır: sesli asistanın ilk kullanımında Whisper modeli, `download_models.py` ya da Ayarlar üzerinden indirilen yapay zekâ modelleri ve Gelişmiş sekmesinden başlatılan Tesseract kurulumu.
- Ayarlar ve son dosyalar listesi `%APPDATA%\PDFAura` klasöründe tutulur. Son dosyalar listesini Ayarlar'dan temizleyebilirsiniz.

---

## 📥 Kurulum

### Sistem gereksinimleri

| Bileşen | Minimum | Önerilen |
| :--- | :--- | :--- |
| **İşletim sistemi** | Windows 10 (64-bit) | Windows 11 (64-bit) |
| **İşlemci** | Intel Core i3 / AMD Ryzen 3 | Intel Core i5 / AMD Ryzen 5 veya üzeri |
| **Bellek** | 4 GB | 8 GB veya üzeri |
| **Disk alanı** | ~500 MB (temel kurulum) | ~1 GB (tüm yapay zekâ modelleriyle) |
| **Python** *(kaynak koddan çalıştırmak için)* | Python 3.10 | Python 3.12 (64-bit) |

### Seçenek A: Kurulum dosyası

Hazır kurulum dosyası `PDFAura-Setup.exe`, [Releases](https://github.com/AsirCan/PDFAura/releases) sayfasında yayınlanır. Kurulum sihirbazını çalıştırın, ardından Başlat menüsündeki **PDF Aura** simgesiyle uygulamayı açın. Henüz bir sürüm yayınlanmadıysa Seçenek B ile birkaç komutla çalıştırabilir ya da aşağıdaki **Kurulum dosyasını derleme** adımlarıyla kurulum dosyasını kendiniz üretebilirsiniz.

### Seçenek B: Kaynak koddan çalıştırma

```powershell
# 1. Depoyu klonlayın
git clone https://github.com/AsirCan/PDFAura.git
cd PDFAura

# 2. Sanal ortam oluşturup etkinleştirin
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Bağımlılıkları yükleyin
pip install --upgrade pip
pip install -r requirements.txt

# 4. Belge tarayıcının yapay zekâ modelini indirin (~4.7 MB)
python download_models.py --skip-optional

# 5. Uygulamayı başlatın
python main.py
```

Sonraki açılışlarda proje klasöründeki `baslat.bat` dosyasına çift tıklamanız yeterlidir.

### Harici bileşenler

| Bileşen | Ne için? | Durum |
| :--- | :--- | :--- |
| [Ghostscript](https://www.ghostscript.com/releases/index.html) | PDF sıkıştırma ve toplu sıkıştırma | **Sıkıştırma için gerekli.** Kurulu değilse Sıkıştır sekmesi kurulum bağlantısıyla uyarır. |
| Microsoft Office veya [LibreOffice](https://www.libreoffice.org/download/) | Word, Excel ve PowerPoint → PDF | İkisinden biri yeterli. Office yoksa LibreOffice kullanılır. |
| [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) | Taranmış PDF'lerden metin çıkarma | İsteğe bağlı. Gelişmiş sekmesinden tek tıkla kurulabilir. Kurulu dil paketleri kullanılır; Türkçe yoksa İngilizce ile çalışır. |

### Yapay zekâ modelleri

| Model dosyası | Boyut | Donanım | Açıklama |
| :--- | :--- | :--- | :--- |
| **`u2netp_document.onnx`** | ~4.7 MB | CPU / düşük sistemler | **Önerilen.** Hafif ve hızlı köşe tespiti. |
| **`u2net_document.onnx`** | ~168 MB | GPU / güçlü CPU | Tam ölçekli model (isteğe bağlı, `python download_models.py`). |
| Faster-Whisper | ~460 MB | CPU | Sesli asistan ilk kullanımda indirir. |

Modeller `models/` klasörüne indirilir ([ayrıntılar](models/README.md)). Tarayıcı modeli yoksa uygulama yine çalışır ve klasik bilgisayarlı görü (OpenCV) yöntemlerini kullanır.

<details>
<summary><b>Kurulum dosyasını derleme</b> (PyInstaller + Inno Setup)</summary>

<br />

1. Uygulamayı paketleyin:

   ```powershell
   pip install -r requirements-dev.txt
   pyinstaller --noconfirm PDFAura.spec
   ```

   Çıktı: `dist\PDFAura\PDFAura.exe`

2. [Inno Setup](https://jrsoftware.org/isdl.php) kuruluyken kurulum dosyasını üretin:

   ```powershell
   iscc setup.iss
   ```

   Çıktı: `dist\PDFAura-Setup.exe`

Ghostscript'i kuruluma eklemek isterseniz yükleyicisini `assets\gs10040w64.exe` olarak yerleştirin. Setup onu paketler ve hedef makinede Ghostscript yoksa sessizce kurar. Dosya yoksa kurulum yine sorunsuz derlenir.

</details>

---

## ❓ Sık sorulan sorular

<details>
<summary><b>İnternet bağlantısı gerekiyor mu?</b></summary>

<br />

Hayır. PDF işlemlerinin hepsi çevrimdışı çalışır. İnternet yalnızca isteğe bağlı indirmeler için gerekir: sesli asistanın ses tanıma modeli (ilk kullanımda ~460 MB), tarayıcının yapay zekâ modeli ve Tesseract kurulumu.

</details>

<details>
<summary><b>Sıkıştır'a bastığımda Ghostscript uyarısı alıyorum.</b></summary>

<br />

Sıkıştırma Ghostscript ile yapılır. [Ghostscript'i indirip](https://www.ghostscript.com/releases/index.html) kurun ve PDF Aura'yı yeniden açın; uygulama kurulu Ghostscript'i kendisi bulur.

</details>

<details>
<summary><b>Word, Excel ya da PowerPoint dosyası PDF'e dönüşmüyor.</b></summary>

<br />

Bu dönüşümler için Microsoft Office veya ücretsiz LibreOffice kurulu olmalıdır. PDF → Word dönüşümü ise ikisine de ihtiyaç duymaz.

</details>

<details>
<summary><b>Belge tarayıcı köşeleri yanlış buldu.</b></summary>

<br />

Köşe noktalarını sürükleyerek kâğıdın köşelerine oturtun; sürüklerken açılan büyüteç ince ayarı kolaylaştırır. Daha hassas çalışmak için **Tam Ekran Kırp**'ı kullanabilir, **Otomatik Algıla** ile tespiti yeniden çalıştırabilir ya da **Sıfırla** ile baştan başlayabilirsiniz. Düz, kontrastlı bir zemin üzerinde çekilen fotoğraflar en iyi sonucu verir.

</details>

<details>
<summary><b>Arayüz dilini nasıl değiştiririm?</b></summary>

<br />

Ayarlar (<kbd>Ctrl</kbd>+<kbd>,</kbd>) → **Uygulama Dili**'nden dili seçip kaydedin. Yeni dil uygulama yeniden başlatıldığında uygulanır; PDF Aura bunu sizin için yapmayı önerir.

</details>

<details>
<summary><b>Pencereyi kapattım ama uygulama kapanmadı.</b></summary>

<br />

**"X (Kapat) tuşuna basıldığında Sistem Tepsisine küçült"** ayarı açıksa PDF Aura tepside çalışmaya devam eder. Tepsi simgesine sağ tıklayıp **Aç** ile pencereyi geri getirebilir, **Çıkış** ile uygulamayı tamamen kapatabilirsiniz. Bu davranışı Ayarlar'dan kapatabilirsiniz.

</details>

---

## 🧭 Yol haritası

- [x] Modern ttk / TkinterDnD arayüzü ve canlı PDF önizleme
- [x] Token tabanlı tasarım sistemiyle yenilenen arayüz
- [x] Açık / koyu tema (Windows ayarını izleyen *Sistem* seçeneğiyle)
- [x] 14 arayüz dili
- [x] U2-Net ONNX tabanlı belge tarayıcı ve çok sayfalı oturum kaydı
- [x] Yerel Faster-Whisper sesli komut asistanı
- [x] Windows sistem tepsisi entegrasyonu
- [x] Microsoft Office yoksa LibreOffice ile Office dönüştürme
- [ ] Windows Gezgini sağ tık menüsü (*"PDF Aura ile Sıkıştır / Dönüştür"*)
- [ ] İsteğe bağlı yerel LLM entegrasyonu (Ollama / llama.cpp ile belge özeti)

Bir fikriniz mi var? [Issue açarak](https://github.com/AsirCan/PDFAura/issues/new) önerin.

---

## 🤝 Katkıda bulunma

Hata bildirimleri, öneriler ve pull request'ler memnuniyetle karşılanır.

1. Depoyu fork'layın ve bir dal açın.
2. Geliştirme bağımlılıklarını yükleyin: `pip install -r requirements-dev.txt`
3. Değişikliğinizi yapın ve testleri çalıştırın: `pytest`
4. Pull request açın. Testler her push'ta GitHub Actions üzerinde Windows'ta otomatik çalışır.

---

## 📄 Lisans ve teşekkürler

PDF Aura [MIT lisansı](LICENSE) ile dağıtılır; kişisel ve ticari amaçlarla özgürce kullanılabilir, değiştirilebilir ve dağıtılabilir.

PDF Aura şu açık kaynak projelerin üzerine kuruludur: [pypdf](https://github.com/py-pdf/pypdf), [PyMuPDF](https://github.com/pymupdf/PyMuPDF), [Ghostscript](https://www.ghostscript.com/), [OpenCV](https://opencv.org/), [ONNX Runtime](https://onnxruntime.ai/), [U2-Net](https://github.com/xuebinqin/U-2-Net), [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper), [Tesseract](https://github.com/tesseract-ocr/tesseract), [pdf2docx](https://github.com/ArtifexSoftware/pdf2docx), [ReportLab](https://www.reportlab.com/) ve [tkinterdnd2](https://github.com/Eliav2/tkinterdnd2). Ghostscript, LibreOffice ve Tesseract ayrı programlar olarak çağrılır ve kendi lisanslarıyla dağıtılır.

Tanıtım videolarındaki fiş fotoğrafları Wikimedia Commons'taki CC0 / kamu malı görsellerdir (Sarah Stierch, Mattes, Grandmaster Huon).

<div align="center">

<br />

<img src="assets/icon.png" width="48" alt="" />

**PDF Aura** ile belgeleriniz güvende, kontrol sizde.

Geliştirici: [AsirCan](https://github.com/AsirCan) &nbsp;•&nbsp; Beğendiyseniz bir ⭐ bırakmayı unutmayın!

[↑ Başa dön](#pdf-aura)

</div>
