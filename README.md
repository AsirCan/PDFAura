# PDF Aura

PDF Aura, Windows 64-bit işletim sistemleri için geliştirilen modern, çevrimdışı ve kapsamlı bir PDF araç setidir. Gündelik doküman işlemlerinden karmaşık ofis otomasyonlarına kadar tüm PDF ihtiyaçlarınıza profesyonel ve güvenli bir çözüm sunmayı hedefler. Tamamen kendi bilgisayarınızda çalışır, böylece hiçbir belgeniz dışarıdaki bir sunucuya yüklenmez ve gizliliğiniz %100 oranında korunur.

## Neler Yapabilirsiniz?

Mevcut sürümde kullanabileceğiniz temel araçlar:

*   **PDF Sıkıştırma:** Dosya boyutlarını görünüm kalitesinden ödün vermeden 4 farklı profil (screen, ebook, printer, prepress) üzerinden optimize ederek küçültün.
*   **Sayfa İşlemleri (Kes, Böl, Düzenle):** İstemediğiniz sayfaları atın, belirli aralıkları (örn. 5-15) kesin, sayfaları dilediğiniz gibi 90/180/270 derece döndürün veya sıralamalarını tamamen değiştirin.
*   **PDF Birleştirme:** Sürükleyip bırakarak sınırsız sayıda PDF dosyasını anında tek bir dosya altında birleştirin.
*   **Format Dönüştürme Merkezi:**
    *   PDF'lerinizi görsellere (PNG/JPG) veya PDF'ten çıkarılabilir formattaki saf metin dosyalarına (TXT) dönüştürün.
    *   Fotoğraflarınızı, Word (.docx), Excel (.xlsx) ve PowerPoint (.pptx) belgelerinizi saniyeler içinde otomatik olarak PDF'e çevirin.
*   **Akıllı Belge Tarayıcı (Kamera/Fotoğraf Okuyucu):**
    *   Cep telefonu ile çektiğiniz kağıt/belge fotoğraflarını, akıllı yapay sinir algoritmalarıyla otomatik algılar ve perspektifini 4 köşeden (CamScanner tarzı) düzelterek A4 boyutuna getirir.
    *   Gölge ve kötü ışık düşen fotoğraflarınızı "Temiz Belge" modundaki **Adaptive Text Thresholding** ile arkaplanı bembeyaz, yazıları simsiyah ve okunaklı yapacak şekilde restore eder. Çoklu fotoğraf yükleme desteğiyle anında dergi/kitap PDF'leri çıkartabilirsiniz.
*   **Güvenlik:** Hassas belgelerinize 128-Bit parola koruması atayın, şifre bildiğiniz dosyaların şifre gereksinimini kaldırın veya tüm sayfalara özel filigran (watermark) ekleyin.
*   **Gelişmiş:** Optik Karakter Tanıma (OCR) sayesinde resim tabanlı PDF'lerden yazıları çekin veya resmi belgelerinize kendi ıslak/görsel imzanızı damgalayın.
*   **Toplu İşlemler:** Klasör dolusu belgeyi tek komutla aynı formata çevirin, sıkıştırın veya akıllı parametrelerle otomatik olarak yeniden isimlendirin.

## Gelecekte Neler Eklenecek? (Yol Haritası)

PDF Aura halihazırda güçlü bir araca dönüşmüş olsa da, onu piyasadaki diğer rakiplerinden üstün kılacak sıradaki özelliklerin entegre edilmesi planlanmaktadır:

1.  **AI Odaklı Sesli Doküman Asistanı:** Kullanıcıların tamamen sesli komutlarla ("Masaüstündeki raporu sıkıştır ve ilk 10 sayfasını kes") işlemi yapmasını sağlayacak Yapay Zeka tabanlı devrim niteliğinde bir hands-free sistem.
2.  **Otomasyon Entegrasyonu:** İşletim sisteminin sağ tık menüsüne eklenerek ("Bunu PDF Aura ile Sıkıştır") hızı maksimum seviyeye çıkarma.
3.  **Bulut Senkronizasyonu:** Yerel işlemin güvenliğini bozmadan, isteğe bağlı Google Drive ve OneDrive çıkış destekleri.

## ⚙️ Gereksinimler

*   **İşletim Sistemi:** Windows 10 veya Windows 11 (64-bit)
*   **Altyapı:** Python 3.10 veya daha yenisi
*   Sıkıştırma motoru için açık kaynaklı *Ghostscript* entegrasyonu kullanır.
*   Ofis belgelerini (Word, PowerPoint, Excel) dönüştürme işlemleri, sisteminizde *Microsoft Office* 'in kurulu olmasını gerektirir.

## 🧰 Geliştiriciler İçin Kurulum

Uygulamayı mevcut kaynak kodlarından çalıştırmak isterseniz:

```powershell
# Gerekli kütüphaneleri sisteminize kurun
pip install -r requirements.txt

# AI modellerini indirin (ilk kurulumda gerekli)
python download_models.py

# Uygulamayı başlatın
python main.py
```

### 🤖 AI Model İndirme

PDF Aura, belge köşe tespiti için gelişmiş yapay zeka modelleri kullanır. İlk kurulumda modelleri indirmeniz gerekir:

```powershell
# Tüm modelleri indir (önerilen)
python download_models.py

# Sadece hafif modeli indir (~5 MB)
python download_models.py --skip-optional
```

**Modeller:**
- **u2netp_document.onnx** (~4.7 MB) - Hafif ve hızlı, CPU'da bile çalışır (Önerilen)
- **u2net_document.onnx** (~168 MB) - Daha yüksek doğruluk, GPU önerilir (Opsiyonel)

Modeller `models/` klasörüne indirilir. Eğer otomatik indirme çalışmazsa, manuel olarak indirebilirsiniz:
- Hafif model: https://huggingface.co/chwshuang/Stable_diffusion_remove_background_model/resolve/main/u2netp.onnx
- Tam model: https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx

**Not:** Modeller olmadan da uygulama çalışır, ancak belge tarayıcı özelliği klasik bilgisayarlı görü yöntemlerini kullanır.

## 🛠️ Kurulum Dosyası (Setup) Oluşturma

Uygulamayı son kullanıcı için tek bir `.exe` kurulum dosyasına dönüştürmek için aşağıdaki adımları izleyebilirsiniz:

### 1. Executable (.exe) Paketleme
Öncelikle kaynak kodları `dist` klasörü altında çalışabilir bir yapıya dönüştürmek için PyInstaller kullanın:

```powershell
pyinstaller --noconfirm PDFAura.spec
```
*(Bu işlem bilgisayar hızına bağlı olarak yaklaşık 3-5 dakika sürebilir.)*

### 2. Kurulum Sihirbazı (Setup.exe) Oluşturma
Oluşturulan dosyaları profesyonel bir Windows yükleyicisine dönüştürmek için **Inno Setup** kullanın:

1.  Bilgisayarınızda [Inno Setup](https://jrsoftware.org/isdl.php) kurulu olduğundan emin olun.
2.  `setup.iss` dosyasına sağ tıklayıp **"Compile"** seçeneğini seçin.
3.  Alternatif olarak terminalden şu komutu çalıştırın:
    ```powershell
    iscc setup.iss
    ```

İşlem tamamlandığında `dist` klasörü içerisinde **PDFAura.exe** adında, yaklaşık **150-200 MB** boyutunda bir kurulum dosyası oluşacaktır.
