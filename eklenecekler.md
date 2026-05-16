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
- [x] Büyük dosyalar için bellek optimizasyonu
- [x] Çoklu çekirdek kullanımı
- [x] İlerleme yüzdesi gösterimi
- [x] İşlem iptal etme butonu

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

### AI Doküman Zekası ve Akıllı PDF İş Akışları
PDF Aura'nın klasik PDF araç setinden daha yenilikçi bir doküman asistanına dönüşmesi hedeflenmektedir. Bu paketteki özellikler, PDF içeriğini OCR/metin çıkarımı ile anlayan, kullanıcıya kaynak göstererek cevap veren ve mevcut PDF işlem modülleriyle birlikte çalışan bir AI katmanı olarak tasarlanacaktır.

**Genel mimari yaklaşım:**
- [x] `src/ai/` altında ortak AI altyapısı kurulacak: belge metni çıkarma, sayfa bazlı parçalara ayırma, embedding/indexleme, kaynak gösterme ve model çağırma katmanları ayrılacak.
- [ ] AI özelliklerinde varsayılan yaklaşım **local-first** olacak; ürün çalışmak için OpenAI, Gemini, Claude veya benzeri ücretli API'lere mecbur kalmayacak.
- [ ] Belge içeriği varsayılan olarak internet servisine gönderilmeyecek; yalnızca kullanıcının açıkça seçtiği opsiyonel online özelliklerde hangi verinin dışarı çıkacağı net gösterilecek.
- [ ] AI cevapları mutlaka sayfa numarası ve kaynak metin parçası ile birlikte gösterilecek; kaynak bulunamayan cevaplar "emin değilim" davranışına düşecek.
- [ ] Büyük PDF'lerde UI donmaması için tüm AI işlemleri arka plan thread/task sistemiyle çalışacak, progress/iptal desteği olacak.
- [ ] Gizlilik modu eklenecek: kullanıcıya her işlem için "local çalışır", "internet gerekir" veya "opsiyonel online kalite modu" bilgisi net gösterilecek.

**Local-first model stratejisi:**
- [x] Ayarlar bölümüne **Local AI Model Yönetimi** ekranı eklenecek: model indirme, model yolu seçme, disk boyutu, RAM/VRAM ihtiyacı ve test çalıştırma kontrolleri bulunacak.
- [x] İlk kurulum küçük tutulacak; büyük LLM/OCR modelleri isteğe bağlı indirilecek.
- [x] Model paketleri `models/` altında türüne göre ayrılacak: `models/llm/`, `models/embeddings/`, `models/ocr/`, `models/speech/`, `models/vision/`.
- [x] Her model için lisans notu tutulacak; ticari kullanıma uygun olmayan model varsayılan pakete alınmayacak.
- [ ] Düşük sistemlerde "Hafif Mod", güçlü sistemlerde "Kaliteli Mod" seçeneği sunulacak.
- [x] Model bulunamazsa özellik kırılmayacak; kullanıcıya hangi modelin eksik olduğu ve nasıl indirileceği gösterilecek.
- [ ] Offline kalitesi yetersiz kalan ses, gelişmiş özet veya sunum gibi özelliklerde kullanıcı onaylı online sağlayıcı desteği opsiyonel olarak eklenebilecek; bu mod varsayılan olmayacak.

**Önerilen local-first teknoloji yığını:**
- [x] PDF metin çıkarma: `PyMuPDF` / mevcut PDF okuma altyapısı; taranmış sayfalarda OCR fallback.
- [x] OCR: temiz baskı belgelerde `Tesseract` fallback hazır; daha zor belge ve tablo işleri için `PaddleOCR` Faz 7 kalite katmanında değerlendirilecek.
- [x] Embedding / arama: küçük ve hızlı bir local embedding fallback; FAISS veya benzeri yerel vektör indeksleme.
- [ ] Yerel LLM: Türkçe ve İngilizce için küçük/orta boy `Qwen`, `Mistral` veya benzeri GGUF modeller; `llama.cpp`/`ctransformers` tarzı CPU çalışabilen runtime.
- [ ] Gizli bilgi algılama: `Microsoft Presidio` + Türkiye'ye özel regex kuralları (TC kimlik, IBAN, telefon, vergi no, e-posta).
- [ ] Tablo çıkarma: `PaddleOCR` + `pdfplumber`/`camelot` benzeri klasik tablo çıkarma yöntemleri birlikte kullanılacak.
- [ ] Sesli asistan: öncelik `faster-whisper` ve `Piper` ile offline çalışma; doğruluk veya ses kalitesi yetmezse kullanıcı seçimiyle online ASR/TTS sağlayıcıları bağlanabilecek.
- [ ] Tarama kalite kontrolü: mevcut ONNX kenar modeli + OpenCV bulanıklık/parlama/gölge ölçümleri.

**Donanım profilleri:**
- [ ] Hafif Mod: 8 GB RAM, CPU ağırlıklı kullanım, küçük LLM ve Tesseract ağırlıklı OCR.
- [ ] Standart Mod: 16 GB RAM, 4-8 GB VRAM varsa daha hızlı LLM/OCR.
- [ ] Kaliteli Mod: 32 GB RAM veya GPU olan sistemlerde daha büyük LLM, daha iyi OCR ve daha uzun belge bağlamı.

#### 1. AI PDF Sohbeti
- [ ] Kullanıcı PDF seçip belge hakkında doğal dille soru sorabilecek.
- [ ] Cevaplarda ilgili sayfa numarası, kısa kaynak alıntısı ve "sayfaya git" aksiyonu gösterilecek.
- [ ] Çok sayfalı belgelerde önce OCR/metin çıkarımı yapılacak, sonra sayfa bazlı indeks oluşturulacak.
- [ ] Örnek sorular: "Bu belge ne anlatıyor?", "2. sayfadaki ödeme şartı ne?", "Riskli madde var mı?", "Son tarih nerede yazıyor?"
- [ ] Cevap kalitesi için hallucination önlemi: kaynak bulunamazsa tahmin üretmek yerine kullanıcıya net uyarı verilecek.
- [ ] Kabul kriteri: En az 50 sayfalık PDF'te soru-cevap UI donmadan çalışmalı ve cevapların yanında doğru sayfa referansı görünmeli.

#### 2. Akıllı Özet Modları
- [ ] Tek tıkla farklı özet türleri üretilecek: kısa özet, detaylı özet, öğrenci özeti, toplantı özeti, hukuki/kontrat özeti.
- [ ] Özet sonucu kopyalanabilir, `.txt` olarak kaydedilebilir ve yeni PDF raporu olarak dışa aktarılabilir olacak.
- [ ] Uzun belgelerde bölüm/sayfa bazlı özet çıkarılıp final özet birleştirilecek.
- [ ] Kullanıcı özet dilini seçebilecek: Türkçe, İngilizce.
- [ ] Kabul kriteri: 20+ sayfalık bir PDF'te özet üretimi arka planda ilerleme göstergesiyle tamamlanmalı.

#### 3. AI Tarama Asistanı
- [ ] Mevcut belge tarayıcıdaki kenar algılama, kalite kontrol katmanıyla desteklenecek.
- [ ] Fotoğraf bulanık, çok karanlık, çok parlak, gölgeli veya belge eksik kadrajdaysa kullanıcıya uyarı verilecek.
- [ ] Kenar algılama sonrası AI kalite puanı gösterilecek: "iyi", "orta", "tekrar çekilmesi önerilir".
- [ ] Belge eğikliği, perspektif bozulması ve sayfa sınırı otomatik düzeltilecek; kullanıcı yine köşeleri elle düzenleyebilecek.
- [ ] Kabul kriteri: Kullanıcının `Downloads\1.jpeg`, `2.jpeg`, `3.jpeg` test görsellerinde algılama UI'ı kilitlemeden çalışmalı ve köşeler görsel olarak doğruya yakın çıkmalı.

#### 4. Otomatik Gizli Bilgi Sansürleme
- [ ] PDF içinde TC kimlik, telefon, e-posta, IBAN, adres, imza alanı ve kredi kartı benzeri hassas veriler algılanacak.
- [ ] Kullanıcı bulunan alanları uygulamadan önce önizleyip tek tek onaylayabilecek.
- [ ] Sansürleme gerçek PDF redaction mantığıyla yapılacak; sadece üstüne siyah kutu çizmekle kalmayacak, metin içeriği de çıkarılacak.
- [ ] OCR tabanlı taranmış belgelerde görsel alan karartma uygulanacak.
- [ ] Kabul kriteri: Sansürlenen bilgi PDF metninde arama/kopyalama ile geri getirilememeli.

#### 5. PDF Karşılaştırma ve Değişiklik Açıklama
- [ ] İki PDF seçilerek metin, sayfa, başlık, tablo ve görsel farkları çıkarılacak.
- [ ] AI, farkları "önemsiz biçim değişikliği", "anlam değişikliği", "riskli değişiklik" gibi sınıflandıracak.
- [ ] Sözleşme/rapor senaryosu için "ne değişti?" raporu üretilecek.
- [ ] Farklar sayfa bazlı gösterilecek ve dışa aktarılabilir özet PDF oluşturulacak.
- [ ] Kabul kriteri: Aynı belgenin iki versiyonunda eklenen/silinen maddeler doğru sayfa referansıyla listelenmeli.

#### 6. PDF'den Tablo ve Excel Çıkarma
- [ ] Fatura, dekont, not çizelgesi, rapor tablosu gibi belgelerden tablo yapısı algılanacak.
- [ ] Çıktı formatları: `.xlsx`, `.csv`, kopyalanabilir markdown tablo.
- [ ] OCR ile taranmış tablolarda hücre sınırları ve satır/sütun ilişkisi korunmaya çalışılacak.
- [ ] Kullanıcı çıktı önizlemesinde hücreleri düzenleyebilecek.
- [ ] Kabul kriteri: En az 3 farklı tablo düzeninde satır/sütun yapısı bozulmadan Excel çıktısı alınmalı.

#### 7. Akıllı Dosya Adlandırma ve Klasörleme
- [ ] PDF içeriği okunarak otomatik dosya adı önerilecek.
- [ ] Örnekler: `Matematik_Odev_2026-05-16.pdf`, `Elektrik_Faturasi_Nisan_2026.pdf`, `Kira_Sozlesmesi_Ahmet_Yilmaz.pdf`.
- [ ] Toplu işlemde klasör içindeki PDF'ler belge türüne göre otomatik alt klasörlere ayrılabilecek.
- [ ] Kullanıcı adlandırma şablonu belirleyebilecek: `{belge_turu}_{tarih}_{konu}`.
- [ ] Kabul kriteri: Toplu yeniden adlandırma öncesi kullanıcıya eski/yeni ad tablosu gösterilmeli ve onay alınmalı.

#### 8. AI Komut Çubuğu
- [ ] Uygulama içinde tek satırlık komut alanı olacak: "Bu PDF'i küçült, ilk 3 sayfayı ayır, imza alanını kırp" gibi komutları anlayacak.
- [ ] Komut, mevcut PDF Aura araçlarına işlem zinciri olarak çevrilecek.
- [ ] Çalıştırmadan önce kullanıcıya plan gösterilecek: giriş dosyası, yapılacak adımlar, çıktı konumu.
- [ ] Sesli asistan altyapısıyla aynı `intent_parser` ve `action_runner` modüllerini paylaşacak.
- [ ] Kabul kriteri: En az sıkıştırma, kesme, birleştirme, filigran, OCR ve çıktı klasörü komutları desteklenmeli.

#### 9. Öğrenci Modu
- [ ] Ders notu/ödev PDF'i için konu özeti, önemli noktalar, test soruları ve flashcard üretilecek.
- [ ] "Bu PDF'ten 10 soru hazırla", "boşluk doldurma yap", "sınav notu çıkar" aksiyonları eklenecek.
- [ ] Çıktılar PDF, TXT veya yazdırılabilir çalışma kağıdı olarak kaydedilebilecek.
- [ ] Kabul kriteri: Öğrenci modu çıktısında her önemli bilgi için kaynak sayfa gösterilmeli.

#### 10. PDF'den Sunum Oluşturma
- [ ] Rapor, ders notu veya makale PDF'i seçilip otomatik sunum taslağı üretilecek.
- [ ] Her slayt için başlık, kısa madde listesi ve kaynak sayfa bilgisi üretilecek.
- [ ] Çıktı formatı ilk etapta `.pptx`, alternatif olarak PDF sunum çıktısı olacak.
- [ ] Kullanıcı slayt sayısı ve sunum tonu seçebilecek: kısa, akademik, yönetici özeti, ders anlatımı.
- [ ] Kabul kriteri: En az 10 sayfalık bir PDF'ten 6-10 slaytlık düzenli bir sunum taslağı oluşturulmalı.

**Özellik bazlı local uygulama önerileri:**
- [ ] AI PDF Sohbeti: PDF metni sayfa sayfa çıkarılacak, embedding ile yerel indeks kurulacak, küçük/orta yerel LLM sadece ilgili sayfa parçalarıyla cevap üretecek.
- [ ] Akıllı Özet: Uzun belgelerde map-reduce yaklaşımı kullanılacak; önce sayfa/bölüm özetleri, sonra final özet üretilecek.
- [ ] AI Tarama Asistanı: Kenar tespitinde mevcut hızlı algoritma korunacak; bulanıklık için Laplacian variance, parlama/gölge için histogram ve yerel kontrast ölçümleri eklenecek.
- [ ] Gizli Bilgi Sansürleme: Önce regex + Presidio ile metin tespiti yapılacak, sonra PDF koordinatları üzerinden gerçek redaction uygulanacak.
- [ ] PDF Karşılaştırma: Klasik text diff ana kaynak olacak; yerel LLM sadece farkları kullanıcı dilinde açıklamak için kullanılacak.
- [ ] Tablo/Excel Çıkarma: Dijital PDF'te `pdfplumber`/tablo çizgileri, taranmış PDF'te PaddleOCR tabanlı hücre çıkarımı kullanılacak.
- [ ] Akıllı Dosya Adlandırma: Belgeden tarih, kişi/kurum, belge türü ve konu çıkarılıp şablon tabanlı isim önerilecek; LLM sadece belirsiz durumlarda kullanılacak.
- [ ] AI Komut Çubuğu: İlk katman kural tabanlı parser olacak; yerel LLM yalnızca komut belirsizse plan üretmeye yardım edecek.
- [ ] Öğrenci Modu: Kaynak sayfa zorunlu olacak; soru/flashcard çıktıları belge dışı bilgi eklemeden üretilecek.
- [ ] PDF'den Sunum: Önce kaynaklı bölüm özeti çıkarılacak, sonra slayt planı üretilecek; `.pptx` üretimi mevcut Office/presentation altyapısıyla yapılacak.

**Maliyet ve ürün kararı:**
- [ ] Varsayılan AI özellikleri için kullanıcıdan API anahtarı istenmeyecek.
- [ ] Local modda token maliyeti olmayacak; maliyet kullanıcının disk alanı ve bilgisayar performansı olacak.
- [ ] Opsiyonel online kalite modu eklenirse açıkça ayrı ayar olarak sunulacak; kullanıcı onayı olmadan API, bulut veya ücretli servis kullanılmayacak.
- [ ] Ücretli sürüm düşünülürse ana fark gelişmiş local model paketi, otomasyon, batch AI, profesyonel workflow ve isteğe bağlı online kalite paketleri üzerinden kurgulanacak.
- [ ] İnternet varsayılan belge işleme için gerekmeyecek; model indirme/güncelleme, bulut entegrasyonu ve kullanıcı onaylı online AI özellikleri ayrı şekilde işaretlenecek.

**Önerilen geliştirme sırası:**
1. [x] Local AI Model Yönetimi + model indirme/yol seçme ekranı
2. [x] Yerel OCR + belge metni çıkarma + sayfa bazlı indeksleme altyapısı
3. [ ] Yerel RAG sistemi: embedding, vektör indeks, kaynak gösterme, güvenli cevap üretme
4. [ ] AI PDF Sohbeti + kaynak gösterme
5. [ ] Akıllı Özet Modları
6. [ ] Otomatik Gizli Bilgi Sansürleme
7. [ ] PDF'den Tablo/Excel Çıkarma
8. [ ] AI Tarama Asistanı kalite kontrolü
9. [ ] AI Komut Çubuğu
10. [ ] PDF Karşılaştırma ve Değişiklik Açıklama
11. [ ] Akıllı Dosya Adlandırma ve Klasörleme
12. [ ] Öğrenci Modu
13. [ ] PDF'den Sunum Oluşturma

**Net uygulama önceliği ve faz planı:**

#### Faz 1 — Local AI Temeli (İlk Yapılacak)
Bu faz bitmeden PDF sohbeti, özet, öğrenci modu veya sunum üretimi yapılmayacak. Önce altyapı sağlam kurulacak.

1. [x] `src/ai/` klasörü ve temel modül yapısı oluşturulacak.
   - `src/ai/model_manager.py`
   - `src/ai/document_loader.py`
   - `src/ai/ocr_engine.py`
   - `src/ai/vector_index.py`
   - `src/ai/local_llm.py`
   - `src/ai/rag_engine.py`
2. [x] Ayarlar içine **Local AI Model Yönetimi** ekranı eklenecek.
   - model var mı kontrolü
   - model yolu seçme
   - model indirme butonu
   - RAM/disk gereksinimi gösterimi
   - test çalıştırma butonu
3. [x] İlk hedef model paketi belirlenecek.
   - küçük local LLM
   - embedding modeli
   - OCR modeli
   - gerekli lisans notları
4. [x] Model yoksa uygulama hata vermeyecek; kullanıcıya eksik model uyarısı gösterecek.

**Faz 1 çıktısı:** Kullanıcı AI modellerini local olarak yönetebilir. Henüz PDF sohbeti şart değil; amaç sağlam temel.

#### Faz 2 — Belge Okuma, OCR ve İndeksleme
AI'nin belgeyi anlayabilmesi için önce PDF içeriği güvenilir şekilde çıkarılacak.

1. [x] Dijital PDF'lerden sayfa bazlı metin çıkarılacak.
2. [x] Taranmış PDF veya fotoğraf tabanlı PDF için OCR fallback çalışacak.
3. [x] Her sayfa için metin, sayfa numarası ve koordinat bilgisi tutulacak.
4. [x] Uzun belgeler küçük parçalara bölünecek.
5. [x] Embedding üretilip yerel vektör indeksi oluşturulacak.
6. [x] İndeks cache sistemi kurulacak; aynı PDF her seferinde baştan işlenmeyecek.

**Faz 2 çıktısı:** PDF Aura bir PDF'i local olarak okuyup sayfa sayfa aranabilir hale getirecek. İlk sürümde hızlı local hashing embedding fallback çalışır; daha kaliteli neural embedding modeli Faz 3 RAG kalitesi için ayrıca bağlanacak.

#### Faz 3 — Kaynak Gösteren Yerel RAG
Bu faz, AI cevaplarının belgeye bağlı kalmasını sağlar.

1. [ ] Kullanıcı sorusu embedding ile aranacak.
2. [ ] En alakalı sayfa parçaları bulunacak.
3. [ ] Yerel LLM sadece bulunan kaynak parçalarıyla cevap verecek.
4. [ ] Cevabın altında kaynak sayfa ve kısa alıntı gösterilecek.
5. [ ] Kaynak bulunamazsa cevap üretmek yerine "belgede bulamadım" davranışı olacak.

**Faz 3 çıktısı:** Komut satırı veya basit test UI üzerinden PDF'e soru sorulabilir ve kaynaklı cevap alınabilir.

#### Faz 4 — AI PDF Sohbeti UI
İlk kullanıcıya gösterilecek gerçek AI özelliği bu olacak.

1. [ ] PDF önizleme paneline veya ayrı sekmeye **AI Sohbet** paneli eklenecek.
2. [ ] Kullanıcı soru yazacak, cevap kaynak sayfalarıyla gösterilecek.
3. [ ] Kaynağa tıklayınca ilgili PDF sayfasına gidilecek.
4. [ ] İşlem sırasında dönen progress/animasyon gösterilecek.
5. [ ] Uzun cevaplarda iptal butonu olacak.

**Faz 4 çıktısı:** PDFAura içinde çalışan ilk gerçek local AI özelliği: kaynak gösteren PDF sohbeti.

#### Faz 5 — Akıllı Özet Modları
Sohbet altyapısı hazır olduğu için özet artık daha kolay eklenecek.

1. [ ] Kısa özet.
2. [ ] Detaylı özet.
3. [ ] Öğrenci özeti.
4. [ ] Toplantı/yönetici özeti.
5. [ ] Hukuki/kontrat özeti.
6. [ ] Özet çıktısını TXT/PDF olarak kaydetme.

**Faz 5 çıktısı:** Kullanıcı PDF'i tek tıkla local AI ile özetleyebilir.

#### Faz 6 — Gizli Bilgi Sansürleme
Bu özellik ticari olarak güçlü ve PDF Aura'ya net değer katar.

1. [ ] TC kimlik, IBAN, telefon, e-posta, vergi no için regex kuralları.
2. [ ] Presidio veya benzeri local PII tespit katmanı.
3. [ ] Bulunan alanları PDF üzerinde önizleme.
4. [ ] Kullanıcı onayıyla gerçek redaction.
5. [ ] Taranmış belgelerde OCR koordinatı ile görsel karartma.

**Faz 6 çıktısı:** Hassas bilgileri local olarak bulup kalıcı şekilde sansürleyen güvenlik aracı.

#### Faz 7 — Tablo ve Excel Çıkarma
PDF araç setine pratik bir iş özelliği ekler.

1. [ ] Dijital PDF tablolarını çıkarma.
2. [ ] OCR tabanlı tablo algılama.
3. [ ] Önizleme ve elle düzeltme.
4. [ ] XLSX/CSV dışa aktarma.

**Faz 7 çıktısı:** Fatura, liste, not çizelgesi gibi belgeler Excel'e aktarılabilir.

#### Faz 8 — Scanner AI Kalite Kontrol
Mevcut belge tarayıcı zaten güçlü olduğu için bu faz onu profesyonelleştirir.

1. [ ] Bulanıklık ölçümü.
2. [ ] Parlama/gölge ölçümü.
3. [ ] Eksik kadraj uyarısı.
4. [ ] Kenar algılama kalite puanı.
5. [ ] "Tekrar çekilmesi önerilir" uyarısı.

**Faz 8 çıktısı:** Tarama ekranı sadece kenar bulmaz, fotoğraf kalitesini de değerlendirir.

#### Faz 9 — AI Komut Çubuğu
Bu faz mevcut PDF araçlarını doğal dille kontrol etmeyi sağlar.

1. [ ] Kural tabanlı komut parser.
2. [ ] Yerel LLM fallback.
3. [ ] Çalıştırmadan önce işlem planı gösterimi.
4. [ ] Mevcut core modülleriyle işlem zinciri.

**Faz 9 çıktısı:** Kullanıcı "bu PDF'i sıkıştır, ilk 3 sayfayı ayır" gibi komutlarla işlem yapabilir.

#### Faz 10 — Sonraki Akıllı Özellikler
Temel AI sistemi oturduktan sonra eklenecek özellikler.

1. [ ] PDF karşılaştırma ve değişiklik açıklama.
2. [ ] Akıllı dosya adlandırma ve klasörleme.
3. [ ] Öğrenci modu.
4. [ ] PDF'den sunum oluşturma.

**Faz 10 çıktısı:** PDFAura klasik PDF aracından local-first doküman asistanına dönüşür.

### Sesli Komut ve Geri Bildirim (Local-First / Opsiyonel Online)
Kullanıcının uygulamaya doğal dilde sesli komutlar vererek PDF işlemlerini otomatikleştirmesi hedeflenmektedir. İlk hedef, butona bas-konuş mantığıyla local çalışan bir MVP'dir; ses tanıma, komut çözümleme ve sesli geri bildirim mümkün olduğunca kullanıcının bilgisayarında yürütülecektir. Donanım, dil doğruluğu veya doğal ses kalitesi yeterli olmazsa online ASR/TTS sağlayıcıları opsiyonel olarak eklenebilir; bu mod açık kullanıcı onayı, net gizlilik uyarısı ve kapatma seçeneği olmadan çalışmayacaktır.

**Senaryo Örneği:**
1. Kullanıcı: *"Masaüstündeki `finansal_rapor.pdf` dosyasını al, ilk 5 sayfasını kes, `GİZLİ` yazılı bir filigran ekle ve Belgelerim'e kaydet. gibi her türlü özellik için bu işlemler yapılabilir"*
2. Sistem: Sesi metne dönüştürür, komutu analiz eder ve gerekli işlemleri sırasıyla arka planda çalıştırır.
3. Sistem yanıtı: *"Dosyanız başarıyla kesildi, filigran eklendi ve Belgelerim klasörüne kaydedildi. gibi her türlü özellik için bu işlemler yapılabilir nereye kaydetmek istiyorsun seçeneği sunulabilir sesli olarak ve cevabı da aynı şekilde sesli verince kaydeder örn: masaüstüne kaydetmek istiyorum dediğimizde kaydeder"*

### Detaylı Sistem Mimarisi ve Veri Akışı

**A. Ses Yakalama ve Metne Dönüştürme Katmanı (Audio-to-Text / ASR)**
- **Modül:** `src/ai/speech_recognizer.py`
- **Teknoloji:** `faster-whisper`
- **Opsiyonel online alternatif:** Yerel doğruluk yetersizse kullanıcı seçimiyle online ASR sağlayıcısı bağlanabilir.
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
- **Alternatif:** `pyttsx3`; kalite yetmezse kullanıcı seçimiyle online TTS sağlayıcısı
- **Tercih nedeni:**
  - `Piper` local çalışır ve varsayılan gizlilik hedefiyle uyumludur.
  - `pyttsx3` kurulum gerektirmeyen temel geri bildirim için yedek olarak kullanılabilir.
  - Online TTS yalnızca local ses kalitesi yetersizse, kullanıcı açıkça seçerse ve hangi metnin gönderileceği gösterilirse kullanılacaktır.
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

### Önerilen Local-First Teknoloji Yığını

**MVP (İlk sürüm için en mantıklı yapı)**
- ASR: `faster-whisper small`
- Intent parsing: `regex + kural tabanlı parser`
- TTS: `Piper` veya sistemde hazırsa `pyttsx3`
- Wake word: ilk sürümde opsiyonel, butona bas-konuş modeli yeterli

**Gelişmiş sürüm**
- ASR: `faster-whisper medium`
- Intent parsing: `kural tabanlı parser + yerel LLM fallback`
- Yerel LLM: `Qwen2.5-7B-Instruct` GGUF
- Runtime: `llama.cpp`
- Wake word: `openWakeWord`
- Opsiyonel online kalite modu: yerel ASR/TTS yetersizse seçilebilir, varsayılan kapalı gelir.

### Mimari Karar

Bu özellik için en doğru yaklaşım:
- önce local çalışan, kural tabanlı bir MVP geliştirmek
- sadece karmaşık doğal dil komutlarında yerel LLM fallback eklemek
- offline kalitesi yetersiz kalan ses veya doğal dil adımlarında online sağlayıcıyı opsiyonel ve kullanıcı kontrollü tutmak
- bulut tabanlı hiçbir servisi zorunlu bağımlılık haline getirmemek

Bu sayede sistem:
- hızlı açılır
- gizlilik dostu olur
- temel işlerde internet olmadan çalışır
- online kalite modu açılırsa kullanıcı hangi verinin dışarı çıkacağını bilir
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

### 🎙️ Local-First Doğal TTS (Piper + Opsiyonel Online Ses)
* **Durum:** ⏳ Beklemede
* **Açıklama:** Varsayılan sesli geri bildirim için internet gerektirmeyen `piper-tts` (ONNX ses modelleri) kullanılacak. Yerel SAPI5/pyttsx3 yeterli kalmazsa Piper ana kalite hedefi olacak; çok daha doğal ses gerektiğinde online TTS sağlayıcıları opsiyonel ve kullanıcı onaylı kalite modu olarak eklenebilecek.
* **Detaylar:**
  - İnternette bulunan açık kaynaklı ONNX formatındaki dil modelleri indirilecek (Örn: `tr_TR-fahrettin-medium.onnx` veya benzeri).
  - Tercihen daha profesyonel ve etkileşimi sıcak kılacak bir **kadın sesi modeli** entegre edilecek.
  - Uygulama Ayarları (Settings) sekmesine "Asistan Sesi" için bir dropdown / seçim menüsü konulacak ki kullanıcılar farklı modeller (kadın/erkek vb.) arasında geçiş yapabilsinler.
  - Varsayılan Piper çıkarımı local çalışacak; online ses seçilirse gönderilecek metin ve servis bilgisi kullanıcıya açıkça gösterilecek.
