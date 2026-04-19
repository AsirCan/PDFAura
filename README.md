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

# Uygulamayı başlatın
python main.py
```

## Dağıtım (Build)

Uygualama tamamen son kullanıcıya ulaşabilir bir kurulum dosyasına (Setup.exe) dönüştürülebilir yapıdadır. `setup.iss` Inno Setup scripti ve cx_Freeze aracılığı ile direkt paketlenebilir formattadır.
