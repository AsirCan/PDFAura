# Faz 0 raporu: pywebview + Edge WebView2 (#25)

Bu klasör bir **deneme** (spike). Uygulamanın parçası değildir ve Faz 2'de gerçek web kabuğu yazılınca silinebilir. Amaç, issue'daki kararları tahmine değil ölçüme dayandırmaktı.

**Ortam:** Windows 11 · Python 3.12.4 · pywebview 6.2.1 · pythonnet 3.2.1 · WebView2 154.0.4258.62 · 20 iş parçacıklı CPU · ekran ölçeği %100.

## Özet

| Konu | Sonuç | Karar |
| :--- | :--- | :--- |
| Pencere motoru | ✅ pywebview 6.2.1 + WebView2 sorunsuz çalışıyor; PyInstaller ile paketleniyor | **pywebview kalır** |
| JS → Python köprüsü (`js_api`) | ✅ Gidiş-dönüş ortanca 0,7 ms, p95 1 ms | **`js_api` kalır** |
| Python → JS olayları | ✅ `run_js` ile 1000 olay 0,4–0,6 sn'de iletildi, arayüz 144 fps'te kaldı | Olaylar **`run_js`** ile gönderilir; **`evaluate_js` kullanılmaz** (aşağıya bakın) |
| Görüntü taşıma | ✅ Büyük görüntüde yerel HTTP, `data:` URL'den 2,3 kat hızlı; küçükte fark yok | Görüntüler uygulamanın **kendi yerel sunucusundan**, rastgele belirteçli (token) adreslerle |
| 300 sayfalık PDF küçük resimleri | ✅ İlk ekran 70 ms (HTTP) / 112 ms (`data:`); kaydırma 144 fps, 50 ms'yi aşan kare yok | `<img loading="lazy">` + HTTP |
| Native dosya diyalogları | ✅ Çoklu dosya açma, klasör seçme ve kaydetme tam yol döndürüyor (otomatik test) | `create_file_dialog` |
| Kapat → tepsi → geri aç | ✅ `closing` olayı iptal edilip pencere gizleniyor; tepsiden açınca pencere öne geliyor | **pystray kalır** |
| Sürükle-bırak tam yol | ✅ Elle denendi: Gezgin'den bırakılan birden çok dosyanın tam yolu geliyor, Türkçe karakterler bozulmuyor | DOM `drop` olayı + `CoreWebView2File.Path` |
| WebView2 yoksa | ❌ pywebview **sessizce Internet Explorer motoruna (MSHTML) düşüyor** | Uygulama açılmadan önce kendisi kontrol eder (`webview2_version()`) |
| CSP | ⚠️ Satır içi script engelleniyor, **`eval` engeli ise köprü yüklenince etkisiz kalıyor** | CSP kalır + `eval`/`new Function` lint kuralıyla yasaklanır |
| Playwright ↔ WebView2 (CDP) | ✅ Yerelde çalışıyor (9 test) | CI iş akışı hazır, **henüz koşmadı** (push gerekiyor) |
| 14 dil, sağdan sola yazım, koyu tema | ✅ Hepsi doğru çiziliyor, kutu (tofu) yok | Sistem font yığını yeterli |

## Ölçümler

### Açılış ve bellek
`measure.py`, 5 çalıştırmanın ortancası. Bellek, açıldıktan 4 sn sonra süreç ve tüm alt süreçleri (WebView2'nin 6 süreci) için toplanıyor.

**Sütunlar:**
- **Pencere:** pencerenin ekranda belirdiği an.
- **İçerik hazır:** sayfa yüklenip köprüden geri çağırdığı an (yalnızca web).
- **Bellek (Görev Yöneticisi):** özel çalışma kümesi; Görev Yöneticisi'nin "Bellek" sütununun gösterdiği değer.
- **Ayrılan (commit):** sürecin ayırdığı toplam özel bellek.

| Çeşit | Pencere | İçerik hazır | Bellek (Görev Yöneticisi) | Ayrılan (commit) |
| :--- | ---: | ---: | ---: | ---: |
| Boş Tk penceresi | 0,14 sn | — | 9 MB | 12 MB |
| **Bugünkü uygulama** (kaynak) | 1,29 sn | — | 70 MB | 89 MB |
| Boş WebView2 penceresi | 0,65 sn | 0,96 sn | 131 MB | 205 MB |
| WebView2 + `src/core` ve `src/ai` yüklü (kaynak) | 1,05 sn | 1,38 sn | 168 MB | 258 MB |
| **Bugünkü uygulama** (PyInstaller exe) | 1,20 sn | — | 76 MB | 95 MB |
| **WebView2 + çekirdek** (PyInstaller exe) | 0,96 sn | 1,29 sn | 172 MB | 262 MB |
| *Faz 1 sonrası:* bugünkü uygulama (kaynak) | 1,01 sn | — | 33 MB | 36 MB |
| *Faz 1 sonrası:* WebView2 + çekirdek (kaynak) | 0,79 sn | 1,12 sn | 141 MB | 215 MB |

**Yorum:**
- **Açılış:** Pencere bugünkünden daha erken görünüyor; içerik bugünkü kadar sürede hazır oluyor. Sürenin büyük kısmı WebView2 değil, çekirdek modüllerin importu (boş WebView2: 0,96 sn). Faz 1'deki tembel import bunu doğrudan kısaltır.
- **Bellek:** WebView2 yaklaşık **+100 MB** getiriyor (Görev Yöneticisi değeri). Bu kaçınılmaz bir maliyet. Ayrılan bellek 262 MB; OpenBLAS düzeltmesinden önceki 700 MB'ın çok altında.
- `working_set_mb` toplamı (430–490 MB) yanıltıcı: WebView2 süreçlerinin paylaştığı DLL sayfalarını her süreçte bir kez daha sayıyor. Bu yüzden bütçede kullanılmamalı.

### Görüntü taşıma (12 MP fotoğraf, JPEG; istekten `img.decode()` bitimine, 3 tekrarın ortancası)

| Uzun kenar | JPEG | `data:` URL (köprü) | Yerel HTTP |
| ---: | ---: | ---: | ---: |
| 1600 px | 164 KB | 15–16 ms | 16 ms |
| 2560 px | 490 KB | 40–44 ms | 30–34 ms |
| 4000 px (tam) | 2,7 MB | 163–167 ms | **71–75 ms** |

Python tarafında küçültme ve JPEG kodlama 8–35 ms sürüyor. Hedef (< 300 ms) her durumda karşılanıyor.

### Python → JS olayları
| Yöntem | Olay | Python'da geçen | Arayüz |
| :--- | ---: | ---: | :--- |
| `run_js` | 1000 | 370–620 ms | 142–144 fps, en uzun kare 7 ms |
| `evaluate_js` | 200 | 82–87 ms | 137–146 fps |

Saniyede en fazla 20 ilerleme olayı (issue'daki kısma hedefi) maliyetsiz.

### Paket boyutu (PyInstaller onedir, `build_exe.py`)
| | Toplam | Arayüz katmanının payı |
| :--- | ---: | :--- |
| Bugünkü uygulama | 451,6 MB | Tk + tkinterdnd2 ≈ 9,9 MB |
| Web denemesi (çekirdekle) | 435,5 MB | pywebview 1,2 MB + pythonnet 0,6 MB |

Kurulum boyutu farkı yaklaşık **−8 MB** (hedef: ≤ +25 MB). Yan bulgu: 450 MB'ın büyük kısmı arayüzden bağımsız.

| Paket | Boyut |
| :--- | ---: |
| `cv2` | 112 MB |
| `av.libs` (faster-whisper'ın ses çözücüsü) | 63 MB |
| `ctranslate2` | 59 MB |
| `pymupdf` | 38 MB |
| `onnxruntime` | 36 MB |

Ayrıca makinede `opencv-python` ile `opencv-python-headless` birlikte kurulu. Bunlar ayrı bir boyut optimizasyonu issue'su için iyi adaylar.

## Bulgular ve sürprizler

1. **WebView2 yoksa sessizce IE'ye düşüyor.** pywebview `winforms.py` import edilirken kayıt defterine bakıyor. WebView2'yi bulamazsa yalnızca uyarı loglayıp MSHTML'i (Internet Explorer 11) seçiyor; `gui="edgechromium"` bunu engellemiyor. Uygulama `webview.start()`'tan önce kendisi kontrol etmeli. `app.py` içindeki `webview2_version()` ve `test_pywebview_silently_falls_back_to_internet_explorer_without_webview2` bunu gösteriyor.
2. **CSP'nin `eval` yasağı köprü yüklenince etkisiz kalıyor.** `early.js` sayfa ayrıştırılırken `eval`'in engellendiğini görüyor. pywebview köprüsünü `ExecuteScript` ile enjekte ettikten sonra aynı çağrı çalışıyor. Satır içi `<script>` engeli ise sürüyor. Sonuç: CSP yine yararlı, ama `eval` / `new Function` / `{@html}` yasağını **ESLint kuralı** sağlamalı.
3. **`evaluate_js` içeride `eval()` kullanıyor** (pywebview `window.py`). Olaylar için `run_js` kullanılmalı.
4. **pywebview'in varsayılan yerel sunucusu `/js_api/<uid>` adresini `Access-Control-Allow-Origin: *` ile açıyor.** `url=` olarak kendi WSGI uygulamamızı verince bu uç nokta hiç eklenmiyor. Statik dosyalar ve görüntüler de bizim kontrolümüzde oluyor (CSP başlığı, `nosniff`, belirteçli görüntü adresleri). **Karar: kendi WSGI uygulamamız.**
5. **Geçici WebView2 profilleri birikiyor.** Varsayılan ayarla her açılışta `%TEMP%\tmpXXXX` adında yaklaşık 8 MB'lık bir profil oluşuyor. Normal kapanışta siliniyor, ama çökme ya da `taskkill` sonrasında kalıyor (ölçümler sırasında 32 klasör, 255 MB birikti; temizlendi). **Karar:** `storage_path` sabit bir klasör olur (`%LOCALAPPDATA%\PDFAura\WebView2`) ve `private_mode` açık kalır. Açılış süresi değişmedi, birikme bitti.
6. **Playwright'ın `wait_for_function`'ı CSP'ye takılıyor**, çünkü koşulunu sayfada `eval` ile değerlendiriyor. Testler bunun yerine Python'dan `page.evaluate` ile yokluyor; o CDP üzerinden gidiyor ve CSP'den etkilenmiyor.
7. **Diyalog testleri:** `page.evaluate` bir promise döndürürse sonucunu bekler. Diyaloğu test kendisi doldurduğu için çağrı `...; 0` ile beklemeden başlatılmalı.
8. **Sürükle-bırak otomasyonu:** pywin32'nin `DoDragDrop`'u sentetik fare girdisiyle döngüsünü hiç ilerletmedi. Bu yüzden otomatik test yok. pywebview'in tam yolu WebView2'nin resmî `CoreWebView2File.Path` alanından aldığı kaynakta doğrulandı. Gerçek sürükleme elle denendi: Masaüstünden aynı anda bırakılan üç PDF'in (biri Türkçe karakterli) tam yolları kartta doğru göründü.

## Elle denenecekler (senin için)

```bash
python spikes/faz0/app.py --tray
```

1. **Sürükle-bırak:** Gezgin'den bir ya da birkaç dosyayı (Türkçe karakterli ve boşluklu adlar dahil) "Sürükle-bırak" kartına bırak. Kartta tam yollar görünmeli.
2. **Dosya diyalogları:** "Dosya aç…", "Klasör seç…" ve "Kaydet…" düğmelerini dene.
3. **Tepsi:** Pencereyi X ile kapat; uygulama tepside kalmalı. Tepsi simgesine tıkla; pencere öne gelmeli.
4. **Tema:** Windows'ta açık/koyu modu değiştir; sayfa anında uymalı.
5. **"Tüm ölçümleri çalıştır":** Sonuçlar ekranda görünür.

## Issue'daki bütçeler: ölçüme göre önerilen düzeltmeler

| Metrik | Issue'daki hedef | Ölçülen (exe, çekirdek yüklü) | Öneri |
| :--- | :--- | :--- | :--- |
| Açılış (içerik hazır) | ≤ 1,3 sn | 1,29 sn | Hedef kalsın; Faz 1'deki tembel import ile < 1,0 sn bekleniyor |
| Boştaki toplam bellek | ≤ 260 MB çalışma kümesi | 172 MB (Görev Yöneticisi) | Ölçütü **Görev Yöneticisi değeri ≤ 200 MB** olarak değiştir; çalışma kümesi toplamı yanıltıcı |
| Ayrılan bellek (WebView2 dahil) | < 400 MB | 262 MB | ✅ Kalsın |
| Kurulum boyutu farkı | ≤ +25 MB | −8 MB | ✅ |
| 12 MP önizleme | < 300 ms | 71–75 ms (tam), 16 ms (1600 px) | ✅ |
| İlerleme olayları | ≤ 20/sn | 1000 olay 0,6 sn'de, akıcı | ✅ |

## Sabitlenecek sürümler
| Paket | Sürüm | Nerede |
| :--- | :--- | :--- |
| pywebview | 6.2.1 | `requirements.txt` (Faz 2) |
| pythonnet | 3.2.1 (pywebview getiriyor) | — |
| playwright (Python) | 1.63.0 | `requirements-dev.txt` (Faz 2) |
| svelte | 5.57.2 | `web/package.json` (Faz 2) |
| vite | 8.3.4 | 〃 |
| typescript | 7.0.2 | 〃 |
| vitest | 5.0.3 | 〃 |
| @playwright/test | 1.64.0 | 〃 |

Node 26 / npm 11 ile denendi (yalnızca sürümler sorgulandı; ön yüz Faz 2'de kurulacak).

## Açık kalanlar
- [x] Gerçek sürükle-bırak elle denendi; tam yollar doğru geliyor.
- [ ] `.github/workflows/faz0-spike.yml` push edilince CI'da koşacak. WebView2 yoksa önce kuruyor. Henüz hiç koşmadı.
- [ ] WebView2'siz **gerçek** bir makinede (temiz VM) deneme. Burada kayıt defteri taklit edilerek gösterildi.
- [ ] `setup.iss` için WebView2 önyükleyicisi Faz 4 işi.

## Dosyalar
| Dosya | Ne işe yarar |
| :--- | :--- |
| `app.py` | Deneme penceresi: köprü, diyaloglar, sürükle-bırak, görüntü sunucusu, tepsi, ölçüm modu |
| `web/` | Deneme sayfası (CSP'ye uygun: satır içi script ya da stil yok) |
| `fixtures.py` | 12 MP fotoğraf ve 300 sayfalık PDF'i `%TEMP%`'e üretir; depoya bir şey girmez |
| `measure.py` | Açılış ve bellek ölçümü (süreç ağacı dahil) |
| `build_exe.py` | Denemeyi ve bugünkü uygulamayı `%TEMP%`'e paketleyip boyutları karşılaştırır |
| `test_spike.py` | 9 otomatik kontrol (Playwright + CDP, diyaloglar, tepsi, CSP, IE'ye düşme) |
| `requirements.txt` | Yalnızca deneme için gereken paketler |

```bash
python -m pytest spikes/faz0 -q
```

```bash
python spikes/faz0/measure.py 5 tk-app web-bare web-core
```

```bash
python spikes/faz0/build_exe.py
```
