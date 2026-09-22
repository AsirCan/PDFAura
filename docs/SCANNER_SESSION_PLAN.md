# Belge Tarayıcı: Oturum Kalıcılığı (Scanner Session Persistence) Uygulama Planı

> **Bu doküman kimin için?** Bu projeyi hiç görmemiş bir geliştirici ya da AI asistanı için yazıldı. Hiçbir ek bağlam gerekmeden baştan sona uygulanabilir.
>
> **Güvenilirlik:** Buradaki kodun tamamı `b7ce3b1` commit'inin bir kopyasına uygulandı. Gerçek Tk penceresiyle uçtan uca test edildi: ekleme, döndürme, sıralama, kapatma, orijinal dosyaları silme, yeniden açma, geri yükleme, PDF alma, bozuk/eksik/kurcalanmış oturum ve ikinci instance kilidi (bkz. Ek A). Satır numaraları `b7ce3b1` içindir. Kod kaydıysa metot adıyla bul.

---

## 0. Kodlamaya başlamadan önce bilinmesi gerekenler

Aşağıdakiler kodda doğrulandı. Tasarımın neredeyse tamamı bunlardan çıkıyor. Birini atlamak sessiz bir bug demek.

| # | Gerçek | Nerede | Sonucu |
|---|---|---|---|
| F1 | **Tüm sekmeler uygulama açılışında oluşturulur**, sekmeye geçildiğinde değil. `ScannerTab.__init__` uygulama başlarken çalışır. | `main_window.py:222-236` | Resimleri `__init__` içinde yüklemek, kullanıcı tarayıcıyı hiç açmasa bile açılışı yavaşlatır ve sayfa başına ~75 MB RAM harcar. **Çözüm:** `__init__` sadece küçük JSON'u okur. Resimler sekme ilk gösterildiğinde (`<Map>` olayı) arka planda çözülür. |
| F2 | `pg.cv_image` **hiç değişmez** (orijinal, döndürülmemiş). `pg.display_image = rotate_image(cv_image, rotation)`. `pg.corners` **döndürülmüş görüntünün koordinatlarındadır.** | `_apply_rotation` (`tab_scanner.py:530`) | PNG olarak **`cv_image`** kaydedilir (bir kez). Geri yüklerken `display_image = rotate_image(cv_image, rotation)` yapılır ve köşeler **olduğu gibi** atanır. `_apply_rotation` çağrılırsa köşeler iki kez döner. |
| F3 | `scan_mode_var` **çevrilmiş etiketi** tutar ("Temiz Belge" / "Clean Document"). | `tab_scanner.py:96, 686` | Etiket saklanırsa dil değişince mod kaybolur. İç sabit saklanır (`_get_selected_mode()` → `"clean_doc"`), yüklerken `tr(key)` ile etikete çevrilir. |
| F4 | `self._detecting_corners`, sekmenin fiilî **"meşgul" kilididir**. Ekleme, döndürme, tespit, tarama ve tam ekran bunu kontrol eder. `_set_corner_detection_busy()` toolbar'ı devre dışı bırakır. | 7 yerde | Geri yükleme sırasında bu kilit **yeniden kullanılır**. Yeni bayrak eklenirse 7 kontrol noktasına dokunmak gerekir. |
| F5 | Worker thread'ler UI'ye `self.app_root.after(0, fn, ...)` ile döner. | `_run_corner_detection` | Aynı kalıp kullanılır. Worker thread içinde **başka hiçbir Tk çağrısı yapılmaz.** Not: bu kalıp çalışan bir `mainloop()` ister. Testte `root.update()` döngüsü yetmez (Ek A bunu doğru yapıyor). |
| F6 | `close_to_tray` varsayılan **True**. X'e basmak pencereyi gizler, process yaşamaya devam eder. Gerçek çıkış tray menüsündeki "Çıkış"tır. `quit_window` **pystray thread'inden** çağrılır. | `main_window.py:299-323` | Son kayıt gerçek çıkışta ana thread'de flush edilir. Gizlemede sadece bekleyen kayıt hemen kuyruğa atılır. |
| F7 | **Tek instance koruması yok.** Tray'de çalışırken Başlat menüsünden tekrar açmak ikinci bir process başlatır. | `main.py` | İki process aynı klasöre yazarsa birinin öksüz-dosya temizliği diğerinin resimlerini siler. **Çözüm:** kilit dosyası. İkinci instance oturuma dokunmaz. |
| F8 | `imwrite_unicode(path, img)` formatı **dosya uzantısından** çıkarır. | `document_scanner.py:29` | `x.png.tmp` yoluna yazamaz. Atomik yazma için `cv2.imencode(".png", ...)` + `buf.tofile(tmp)` kullanılır. |
| F9 | Köşeler kodun her yerinde **Python `int`**: sürükleme `int(ix)`, dedektör `_apply_smart_inset` → `int`, varsayılanlar `int`. | `document_scanner.py:763` | JSON'a `int(round(float(v)))` yazılır. Bu numpy skalerlerine karşı da güvenli. Geri yüklerken yine `int` olur, tipler birebir aynı kalır. |
| F10 | `auto_detect()`, `rotation == 0` iken **`pg.path` dosyasını diskten yeniden okur.** | `tab_scanner.py:558` | Orijinal silinmiş, taşınmış ya da düzenlenmişse tespit bozulur. **Çözüm:** önce oturumdaki PNG kullanılır (piksel olarak `cv_image`'in aynısı). |
| F11 | Yeni i18n anahtarı **hem `"tr"` hem `"en"`** sözlüğüne eklenmeli. Eksik anahtar ekranda ham anahtar adı olarak görünür. | `lang_manager.py` | Bkz. §7. |

---

## 1. Mimari özet

```
┌─────────────────────────── Ana (Tk) thread ────────────────────────────┐
│  kullanıcı değişikliği ─► _schedule_session_save()  (400 ms debounce)  │
│                                   │                                    │
│                                   ▼                                    │
│                           _save_session()                              │
│        meta (sadece Python tipleri) + {uid: cv_image referansı}        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ queue.put (bloklamaz, kopya yok)
┌───────────────────────────────────▼────────────────────────────────────┐
│  ScannerSessionStore yazıcı thread'i (TEK thread, FIFO)                │
│   1. diskte olmayan her uid için PNG yaz (.tmp → os.replace)           │
│   2. session.json yaz (.tmp → fsync → os.replace)                      │
│   3. images/ altındaki referanssız PNG'leri sil                        │
└────────────────────────────────────────────────────────────────────────┘

Açılış:  __init__ → load_meta() (küçük JSON, senkron)
         → sekme ilk kez görünür (<Map>) → worker thread PNG'leri çözer
         → after(0) → ana thread sayfaları kurar ve InlineFeedback gösterir
Export:  PDF başarılı + o sırada değişiklik yapılmadıysa → clear()
Çıkış:   tray "Çıkış" → ana thread'e geç → flush_session() → root.quit()
```

**Tasarım kararları ve gerekçeleri**

1. **Yeni modül `src/core/scanner_session.py`.** Disk, thread ve kilit işi Tk bilmeyen, tek başına test edilebilen bir sınıfta durur. `tab_scanner.py` sadece durumu JSON'a çevirir ve hook'ları çağırır.
2. **Tek yazıcı thread + FIFO kuyruk.** Sıralama garantisi verir: bir resim, onu referans eden `session.json`'dan önce diske yazılır. `clear` ile `save` karışmaz.
3. **Her kayıtta tüm sayfaların `cv_image` referansı gönderilir, worker sadece diskte olmayanı yazar.** Böylece "resim sadece ilk eklendiğinde yazılır" şartı ek durum tutmadan sağlanır ve sistem kendini onarır. Bir yazım başarısız olursa sonraki kayıt tekrar dener. PDF sonrası `clear` edilmiş bir oturumda değişiklik yapılırsa resimler otomatik yeniden yazılır. Referans göndermek ücretsizdir çünkü `cv_image` asla yerinde değiştirilmez (F2).
4. **400 ms debounce.** Köşe sürükleme bırakma, döndürme ve çıktı yolu kutusuna harf harf yazma tek bir kayda iner. Sürükleme **sırasında** kayıt yapılmaz, sadece bırakınca.
5. **Tembel geri yükleme (`<Map>`).** "Belge Tara sekmesine geçince oturum yüklensin" isteğini birebir karşılar (F1). Yükleme çağrısı yine `__init__` içindedir (kısıt 5).
6. **PDF sonrası temizlik + revizyon kontrolü.** Kullanıcı PDF yazılırken bir şey değiştirdiyse o değişiklik PDF'te yoktur. Bu durumda oturum silinmez.
7. **PDF sonrası UI boşaltılmaz.** Sayfalar ekranda kalır (mevcut davranış). Sadece diskteki oturum silinir. Kullanıcı sonra bir şey değiştirirse oturum baştan oluşur, yani "export edilmemiş değişiklik" varsa kalıcıdır.

---

## 2. Oturum veri formatı

### 2.1 Klasör yapısı

```
%APPDATA%\PDFAura\
├── config.json                      (mevcut)
└── scanner_session\
    ├── .lock                        sahibi process açık tuttuğu sürece kilitli (0 byte)
    ├── session.json                 metadata
    ├── session.json.tmp             (sadece yazma anında; atomik değiştirme için)
    ├── session.json.corrupt         (bozuk JSON bulunursa buraya taşınır; teşhis için)
    └── images\
        ├── 3f2a9c0e…(32 hex).png    her sayfanın ORİJİNAL (döndürülmemiş) pikselleri
        └── …png.tmp                 (sadece yazma anında)
```

### 2.2 `session.json` şeması (versiyon 1)

| Alan | Tip | Anlam / kural |
|---|---|---|
| `version` | int | Şu an `1`. Daha büyükse (yeni sürümün yazdığı): **dokunma**, bu çalıştırmada kalıcılığı kapat. Eksik ya da farklıysa: bozuk kabul et. |
| `corner_order` | str | *(Sonradan eklendi)* `"display"` ise `corners[0]` döndürülmüş görüntünün sol-üst köşesidir. Bu alan yoksa oturum, döndürmede köşe sırasını güncellemeyen eski kodla yazılmıştır. Yüklerken her sayfanın listesi `x+y` değeri en küçük noktadan başlatılır; saat yönündeki sıra korunur. |
| `saved_at` | str | `YYYY-MM-DDTHH:MM:SS` yerel saat. Sadece bilgi amaçlı. |
| `scan_mode` | str | İç sabit: `original` · `clean_doc` · `bw` · `grayscale` · `sharp`. **Çevrilmiş etiket DEĞİL** (F3). Bilinmeyen değer gelirse mevcut seçim korunur. |
| `output_path` | str | Çıkış PDF yolu. Boş olabilir. |
| `current_index` | int | Seçili sayfa. Aralık dışıysa 0 kullanılır. |
| `pages` | list | **Dizideki sıra = PDF sayfa sırası.** |
| `pages[].uid` | str | `^[0-9a-f]{32}$` (uuid4 hex). PNG adı `images/<uid>.png`. Regex dışı değer **reddedilir** (path traversal koruması). |
| `pages[].source_path` | str | Kullanıcının eklediği orijinal dosya yolu. **Artık var olmayabilir.** Sadece varsayılan çıktı adı için kullanılır. |
| `pages[].width`, `height` | int | **Döndürülmemiş** PNG'nin boyutu. Yüklenen PNG ile eşleşmezse sayfa atlanır (köşeler yanlış olurdu). |
| `pages[].rotation` | int | `0`/`90`/`180`/`270` (saat yönü). Başka değer gelirse 0 kabul edilir. |
| `pages[].label` | str | *(Sonradan eklendi, opsiyonel)* Kullanıcının sayfaya verdiği ad ("Kapak" gibi). Eksikse `""`. Yüklerken tek satıra indirilir ve 60 karakterle sınırlanır (`_clean_label`). Şema versiyonu 1'de kaldı, çünkü eski oturumlar bu alan olmadan da açılıyor. |
| `pages[].corners` | `[[x,y]×4]` int | **Döndürülmüş görüntü koordinatında**, sıra: sol-üst, sağ-üst, sağ-alt, sol-alt. Yüklerken `[0, w]×[0, h]` aralığına kırpılır. Geçersizse varsayılan köşeler kullanılır. |

Örnek:

```json
{
  "version": 1,
  "saved_at": "2026-09-22T14:03:11",
  "scan_mode": "clean_doc",
  "output_path": "C:\\Users\\ali\\Desktop\\fatura_tarandi.pdf",
  "current_index": 1,
  "pages": [
    {
      "uid": "3f2a9c0e5b7d4e1f9a8b7c6d5e4f3a2b",
      "source_path": "C:\\Users\\ali\\Desktop\\IMG_1234.jpg",
      "width": 3024,
      "height": 4032,
      "rotation": 90,
      "corners": [[120, 88], [3900, 101], [3890, 2950], [130, 2940]]
    }
  ]
}
```

(`rotation: 90` olduğu için görüntülenen boyut 4032×3024'tür. x değerleri 4032'ye kadar gidebilir.)

### 2.3 Değişmezler (invariant'lar)

- `images/<uid>.png` içeriği her zaman o sayfanın `cv_image`'i ile **piksel piksel aynıdır**. PNG kayıpsızdır, `imread_unicode` her zaman 3 kanallı BGR döndürür.
- Bir `uid`'in pikselleri **asla değişmez**. İleride bir özellik `cv_image`'i değiştirirse (ör. kalıcı kırpma), o sayfaya **yeni uid** verilmelidir.
- `session.json` hiçbir zaman yarım yazılmış olamaz (`.tmp` + `fsync` + `os.replace`).
- JSON'da referans verilen her PNG, JSON'dan **önce** diske yazılmıştır (tek FIFO thread).

---

## 3. `src/core/config_manager.py` değişiklikleri

İki ekleme var. Geriye dönük uyumludurlar: `load()` dosyadaki anahtarları varsayılanların üzerine yazdığı için eski `config.json`'larda yeni anahtar otomatik olarak varsayılan değeri alır.

```diff
         self.default_config = {
             "language": "en",
             "sound_enabled": True,
             "default_output_dir": "",
             "recent_files": [],
             "close_to_tray": True,
             "ai_model_root": "",
             "ai_model_paths": {},
+            "scanner_session_enabled": True,
         }
```

`save()` metodundan sonra, `get()` metodundan önce:

```python
    @property
    def scanner_session_dir(self):
        """%APPDATA%\\PDFAura\\scanner_session – Belge Tarayıcı'nın yarım kalan işi."""
        return os.path.join(self.config_dir, "scanner_session")
```

`scanner_session_enabled`, özelliği kapatmak için bir "kill switch". Ayarlar penceresine bağlamak bu işin kapsamında değil.

---

## 4. YENİ DOSYA: `src/core/scanner_session.py` (tam kod)

Aynen oluştur:

```python
"""
Scanner session persistence
───────────────────────────
Keeps the Belge Tarayıcı work (photos, corners, rotation, order, scan mode,
output path) on disk so it survives an app restart.

Layout (under %APPDATA%\\PDFAura\\scanner_session\\):
    .lock               held for the lifetime of the owning PDF Aura process
    session.json        metadata, written atomically (.tmp + os.replace)
    images/<uid>.png    lossless copy of each page's ORIGINAL (unrotated) pixels

All writes happen on ONE background thread, in the order they were queued, so
an image is always on disk before the session.json that references it.
"""

import atexit
import json
import logging
import os
import queue
import re
import shutil
import threading
import time

import cv2

from src.core.document_scanner import imread_unicode

SESSION_VERSION = 1
SESSION_FILE = "session.json"
IMAGES_DIR = "images"
LOCK_FILE = ".lock"
# Level 1 = fastest zlib setting; PNG stays lossless at any level.
PNG_PARAMS = [cv2.IMWRITE_PNG_COMPRESSION, 1]
UID_RE = re.compile(r"^[0-9a-f]{32}$")


def _replace_with_retry(src, dst, attempts=5):
    # Antivirus / search indexer can hold a file for a few ms on Windows.
    for i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(0.05 * (i + 1))


def _try_lock(path):
    """Return an open handle holding an exclusive lock, or None if another process owns it."""
    try:
        fh = open(path, "a+b")
    except OSError:
        return None
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError:
        fh.close()
        return None


class ScannerSessionStore:
    """Disk side of the scanner session. Thread-safe; never touches Tk."""

    def __init__(self, session_dir, enabled=True, on_error=None):
        self.session_dir = session_dir
        self.images_dir = os.path.join(session_dir, IMAGES_DIR)
        self.meta_path = os.path.join(session_dir, SESSION_FILE)
        self.on_error = on_error          # called from the WORKER thread with a message
        self.enabled = False
        self.locked_by_other = False
        self._lock_fh = None
        self._queue = queue.Queue()

        if not enabled:
            return
        try:
            os.makedirs(session_dir, exist_ok=True)
        except OSError as exc:
            logging.error("Scanner session dir could not be created: %s", exc)
            return

        self._lock_fh = _try_lock(os.path.join(session_dir, LOCK_FILE))
        if self._lock_fh is None:
            # A second PDF Aura instance: never write, or the two would delete
            # each other's images during orphan cleanup.
            self.locked_by_other = True
            return

        self.enabled = True
        threading.Thread(target=self._run, name="ScannerSessionWriter", daemon=True).start()
        atexit.register(self.flush, 3.0)

    # ── paths ────────────────────────────────────────────────────────────

    def image_path(self, uid):
        return os.path.join(self.images_dir, f"{uid}.png")

    # ── read side (synchronous) ──────────────────────────────────────────

    def load_meta(self):
        """Return the stored metadata dict, or None when there is nothing usable."""
        if not self.enabled or not os.path.isfile(self.meta_path):
            return None

        raw = None
        for attempt in range(3):
            try:
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    raw = f.read()
                break
            except OSError as exc:
                if attempt == 2:
                    # Probably locked, not broken: keep the files and stop
                    # persisting for this run so nothing overwrites them.
                    logging.error("Scanner session could not be read, persistence off for this run: %s", exc)
                    self.enabled = False
                    return None
                time.sleep(0.1)

        try:
            meta = json.loads(raw)
        except ValueError as exc:
            logging.warning("Scanner session is corrupt, discarding: %s", exc)
            self._quarantine()
            return None

        if not isinstance(meta, dict) or not isinstance(meta.get("pages"), list):
            logging.warning("Scanner session has an unexpected shape, discarding")
            self._quarantine()
            return None

        version = meta.get("version")
        if isinstance(version, int) and version > SESSION_VERSION:
            # Written by a newer PDF Aura: don't touch it.
            logging.warning("Scanner session version %s is newer than supported %s", version, SESSION_VERSION)
            self.enabled = False
            return None
        if version != SESSION_VERSION:
            self._quarantine()
            return None
        return meta

    def read_image(self, uid):
        """Decode one stored page image (safe to call from a worker thread)."""
        if not isinstance(uid, str) or not UID_RE.fullmatch(uid):
            return None
        path = self.image_path(uid)
        if not os.path.isfile(path):
            return None
        return imread_unicode(path)

    def _quarantine(self):
        # Only called from load_meta, before any write is queued.
        try:
            _replace_with_retry(self.meta_path, self.meta_path + ".corrupt")
        except OSError:
            pass
        shutil.rmtree(self.images_dir, ignore_errors=True)

    # ── write side (asynchronous) ────────────────────────────────────────

    def save(self, meta, images):
        """Queue a full snapshot.

        meta   – JSON-ready dict (plain Python types only).
        images – {uid: ndarray} for EVERY page; only files missing on disk are
                 encoded, so passing all of them is cheap and self-healing.
        """
        if self.enabled:
            self._queue.put(("save", meta, images))

    def clear(self):
        if self.enabled:
            self._queue.put(("clear", None, None))

    def flush(self, timeout=10.0):
        """Block until everything queued so far is on disk. Returns False on timeout."""
        if not self.enabled:
            return True
        done = threading.Event()
        self._queue.put(("flush", done, None))
        return done.wait(timeout)

    def _run(self):
        while True:
            op, a, b = self._queue.get()
            try:
                if op == "save":
                    self._do_save(a, b)
                elif op == "clear":
                    self._do_clear()
                elif op == "flush":
                    a.set()
            except Exception as exc:
                logging.exception("Scanner session write failed")
                if self.on_error:
                    try:
                        self.on_error(str(exc))
                    except Exception:
                        pass

    def _do_save(self, meta, images):
        os.makedirs(self.images_dir, exist_ok=True)
        for uid, img in images.items():
            path = self.image_path(uid)
            if os.path.isfile(path):
                continue                       # written once, never rewritten
            ok, buf = cv2.imencode(".png", img, PNG_PARAMS)
            if not ok:
                raise IOError(f"PNG encode failed for page {uid}")
            tmp = path + ".tmp"
            buf.tofile(tmp)
            _replace_with_retry(tmp, path)

        tmp = self.meta_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        _replace_with_retry(tmp, self.meta_path)

        self._remove_orphans({p["uid"] for p in meta["pages"]})

    def _remove_orphans(self, keep):
        try:
            names = os.listdir(self.images_dir)
        except FileNotFoundError:
            return
        for name in names:
            if name.endswith(".tmp") or name.split(".", 1)[0] not in keep:
                try:
                    os.remove(os.path.join(self.images_dir, name))
                except OSError:
                    pass

    def _do_clear(self):
        # session.json first: a crash halfway must not leave metadata that
        # points at deleted images.
        for name in (SESSION_FILE, SESSION_FILE + ".tmp"):
            try:
                os.remove(os.path.join(self.session_dir, name))
            except FileNotFoundError:
                pass
        shutil.rmtree(self.images_dir, ignore_errors=True)
```

**Önemli ayrıntılar**

- Yazıcı thread `daemon=True`. Daemon olmasaydı `queue.get()` üzerinde sonsuza kadar bekler ve process kapanmazdı. Veri kaybını önlemek için çıkışta açıkça `flush()` çağrılır (§6). `atexit` ise ek bir güvenlik ağıdır: Python, atexit callback'lerini daemon thread'ler hâlâ çalışırken çağırır.
- Kilit, process ölünce işletim sistemi tarafından otomatik bırakılır. Çöken bir uygulama kilidi takılı bırakmaz.
- `load_meta` ve `_quarantine` senkron çalışır ve **sadece `__init__` sırasında** çağrılır. O anda kuyrukta iş olmadığı için yazıcı thread ile yarışmazlar.

---

## 5. `src/gui/tabs/tab_scanner.py` değişiklikleri

### 5.1 Import'lar (dosyanın başı, satır 11-37)

```diff
+import logging
+import math
 import os
 import threading
 import tempfile
+import time
+import uuid
 import tkinter as tk
-from tkinter import ttk, filedialog
+from tkinter import ttk, filedialog, messagebox      # messagebox: sadece §5.9 için
 ...
+from src.core.config_manager import cfg
 from src.core.lang_manager import _ as tr   # rename to avoid shadowing
+from src.core.scanner_session import ScannerSessionStore, SESSION_VERSION
 from src.core.task_manager import TaskContext, CancelledError
```

### 5.2 Modül seviyesi (`_MODE_MAP` tanımından hemen sonra)

```python
SESSION_SAVE_DELAY_MS = 400


def _valid_corners(corners):
    if not isinstance(corners, list) or len(corners) != 4:
        return False
    for pt in corners:
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            return False
        for v in pt:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                return False
    return True
```

### 5.3 `_PageData`: `uid` alanı (geriye uyumlu, eski 3 argümanlı çağrılar çalışmaya devam eder)

```diff
 class _PageData:
     """Per-page state for one photo in the scan list."""
-    __slots__ = ("path", "cv_image", "display_image", "rotation", "corners")
+    __slots__ = ("path", "cv_image", "display_image", "rotation", "corners", "uid")

-    def __init__(self, path, cv_image, corners):
+    def __init__(self, path, cv_image, corners, uid=None):
         self.path = path
         self.cv_image = cv_image
         self.display_image = cv_image.copy()
         self.rotation = 0
         self.corners = list(corners)
+        # Names this page's PNG in the session folder. cv_image must never be
+        # changed in place; a page with different pixels needs a new uid.
+        self.uid = uid or uuid.uuid4().hex
```

### 5.4 `ScannerTab.__init__`

```diff
         self._thumb_cache = {}   # id(page) -> ((rotation, corners), PhotoImage)

+        # ── session persistence ──
+        self._session_save_job = None     # after() id of the pending debounced save
+        self._session_restoring = False   # True from "session found" until it is applied
+        self._session_meta = None         # read in __init__, applied on first show
+        self._session_rev = 0             # bumped on every change; guards the post-export clear
+        self._scan_start_rev = None
+        self._session_error_shown = False
+        self._session_store = ScannerSessionStore(
+            cfg.scanner_session_dir,
+            enabled=cfg.get("scanner_session_enabled", True),
+            on_error=lambda msg: self.app_root.after(0, self._on_session_error, msg),
+        )
+
         self.build_ui()
+        self.output_var.trace_add("write", lambda *_args: self._schedule_session_save())
+        self._load_session()
```

Sıralama önemli. `trace_add` ve `_load_session`, `build_ui()`'dan **sonra** gelir, çünkü `self.feedback` ve footer'a ihtiyaç duyarlar. `output_var` üzerindeki trace; `choose_output()`, elle yazma ve `_add_image_pages` içindeki otomatik isim atamasının hepsini tek yerden yakalar. Bu yüzden `choose_output()` içine ayrıca hook **eklenmez**.

### 5.5 Kayıt hook'ları (tam liste)

Her hook tek satırdır: `self._schedule_session_save()`. Hepsi ana thread'de çalışır.

| Değişiklik | Metot (satır) | Hook nereye |
|---|---|---|
| Fotoğraf ekleme (dosya seçici **ve** sürükle-bırak) | `_add_image_pages` (247) | `self._start_corner_detection(jobs)` satırından **hemen önce** |
| AI köşe tespiti sonucu (hem ekleme sonrası hem "Otomatik Algıla") | `_apply_corner_detection_result` (364) | `page.corners = list(corners)` satırından hemen sonra. Sayfa başına tetiklenir, böylece tespit yarıda kalırsa bitmiş olanlar korunur. Debounce sayesinde maliyeti yok. |
| Sayfa silme | `remove_current` (401) | metodun sonu (`self._show_current_page()` sonrası) |
| Sıra değiştirme | `move_page` (424) | metodun sonu |
| Döndürme (sağa ve sola) | `_apply_rotation` (530) | metodun sonu. `rotate_cw` ve `rotate_ccw` ikisi de buradan geçer. |
| Köşe sıfırlama | `reset_corners` (567) | metodun sonu |
| Köşe sürükleme bitti | `_on_canvas_release` (675) | `if` bloğunun içi, `self.update_preview()` sonrası |
| Tam ekran köşe sürükleme bitti | `_fs_on_release` (924) | `if` bloğunun içi, `self._fs_redraw()` sonrası |
| Tarama stili | combobox bind (191) | `lambda evt: self.update_preview()` → `self._on_mode_changed` (bkz. 5.7) |
| Çıkış yolu | `output_var` trace | §5.4 |

**Bilerek hook eklenmeyen yerler:** `_on_canvas_drag` ve `_fs_on_drag` (her fare hareketinde tetiklenirdi, bırakınca kaydediliyor zaten). `prev_page`, `next_page`, `_on_strip_click` (sadece gezinme; `current_index` bir sonraki gerçek kayıtla birlikte yazılır). Gezinmeye hook eklenirse PDF sonrası temizlik, kullanıcı küçük resme tıkladı diye iptal olur.

Örnek diff:

```diff
@@ _add_image_pages
             tr("scanner_page_count").format(count=len(self.pages))
         )
+        self._schedule_session_save()
         self._start_corner_detection(jobs)
         return len(jobs)

@@ _apply_corner_detection_result
         page.corners = list(corners)
+        self._schedule_session_save()
         if page is self.current_page:

@@ _on_canvas_release
             self._redraw_canvas() # remove magnifier
             self.update_preview()
+            self._schedule_session_save()

@@ _fs_on_release
             self._fs_redraw() # remove magnifier
+            self._schedule_session_save()

@@ build_ui
-        self.mode_combo.bind("<<ComboboxSelected>>", lambda evt: self.update_preview())
+        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_changed)
```

### 5.6 `auto_detect`: orijinal dosya silinmiş olabilir (F10)

```diff
-        image = pg.display_image.copy() if pg.rotation != 0 else None
-        path = None if image is not None else pg.path
+        path = self._detection_source_path(pg) if pg.rotation == 0 else None
+        image = pg.display_image.copy() if path is None else None
         self._start_corner_detection([{
```

`path` ya da `image`'den tam olarak biri dolu olur. `_run_corner_detection` bu iki durumu zaten destekliyor.

### 5.7 Yeni metotlar (tam kod)

`update_preview()` metodundan sonra, `#  Scan & export (multi-page)` başlığından önce ekle:

```python
    def _on_mode_changed(self, _event=None):
        self.update_preview()
        self._schedule_session_save()

    # ─────────────────────────────────────────────────────────────────────
    #  Session persistence (survives app restart)
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _mode_label(mode):
        for m, key in _MODE_MAP:
            if m == mode:
                return tr(key)
        return None

    def _detection_source_path(self, pg):
        """A file whose pixels equal pg.cv_image. The session PNG wins: the
        original may have been moved, deleted or edited since it was added."""
        stored = self._session_store.image_path(pg.uid)
        if os.path.isfile(stored):
            return stored
        if pg.path and os.path.isfile(pg.path):
            return pg.path
        return None

    def _schedule_session_save(self):
        """Debounced autosave. Call after ANY change to pages, corners, rotation,
        order, scan mode or output path. Main thread only."""
        if self._session_restoring or not self._session_store.enabled:
            return
        self._session_rev += 1
        if self._session_save_job is not None:
            self.app_root.after_cancel(self._session_save_job)
        self._session_save_job = self.app_root.after(SESSION_SAVE_DELAY_MS, self._save_session)

    def _save_session(self):
        """Snapshot the state (cheap, main thread) and hand it to the writer thread."""
        self._session_save_job = None
        if self._session_restoring or not self._session_store.enabled:
            return
        if not self.pages:
            self._session_store.clear()
            return

        meta = {
            "version": SESSION_VERSION,
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "scan_mode": self._get_selected_mode(),   # internal id, not the translated label
            "output_path": self.output_var.get().strip(),
            "current_index": max(0, self.current_index),
            "pages": [
                {
                    "uid": pg.uid,
                    "source_path": pg.path,
                    "width": int(pg.cv_image.shape[1]),
                    "height": int(pg.cv_image.shape[0]),
                    "rotation": int(pg.rotation) % 360,
                    # Corners are integer pixels everywhere in this tab; int() also
                    # turns any numpy scalar into something json can encode.
                    "corners": [[int(round(float(x))), int(round(float(y)))] for x, y in pg.corners],
                }
                for pg in self.pages
            ],
        }
        # References only, no copies: cv_image is never modified in place.
        self._session_store.save(meta, {pg.uid: pg.cv_image for pg in self.pages})

    def save_session_now(self):
        """Run a pending debounced save immediately (e.g. window hidden to tray)."""
        if self._session_save_job is not None:
            self.app_root.after_cancel(self._session_save_job)
            self._save_session()

    def flush_session(self, timeout=10.0):
        """Save pending changes and wait until they are on disk. Used on app exit."""
        self.save_session_now()
        return self._session_store.flush(timeout)

    def _clear_session(self):
        if self._session_save_job is not None:
            self.app_root.after_cancel(self._session_save_job)
            self._session_save_job = None
        self._session_store.clear()

    def _on_session_error(self, message):
        # Once per run is enough; the next save retries whatever is missing.
        if self._session_error_shown:
            return
        self._session_error_shown = True
        self.feedback.set_error(tr("scanner_session_title"),
                                tr("scanner_session_save_failed").format(error=message))

    def _load_session(self):
        """Called once from __init__. Reads session.json now (small, fast);
        the images are decoded the first time the tab is shown."""
        if self._session_store.locked_by_other:
            self.feedback.set_info(tr("scanner_session_title"), tr("scanner_session_locked"))
            return
        meta = self._session_store.load_meta()
        if not meta or not meta.get("pages"):
            return
        self._session_meta = meta
        self._session_restoring = True        # nothing may overwrite it before it is applied
        self.parent.bind("<Map>", self._on_tab_mapped, add="+")
        if self.parent.winfo_ismapped():
            self._begin_session_restore()

    def _on_tab_mapped(self, event):
        if event.widget is self.parent and self._session_meta is not None:
            self._begin_session_restore()

    def _begin_session_restore(self):
        meta, self._session_meta = self._session_meta, None   # one-shot
        if meta is None:
            return
        # Reuse the tab's busy lock: add/rotate/detect/scan already refuse to
        # run while it is set, and the toolbar gets disabled.
        self._detecting_corners = True
        self._set_corner_detection_busy(True, tr("scanner_session_restoring"))
        threading.Thread(target=self._restore_session_worker, args=(meta,), daemon=True).start()

    def _restore_session_worker(self, meta):
        # Worker thread: disk + numpy only, no Tk calls.
        restored, skipped = [], 0
        for entry in meta["pages"]:
            try:
                page = self._page_from_session_entry(entry)
            except Exception:
                logging.exception("Scanner session page could not be restored")
                page = None
            if page is None:
                skipped += 1
            else:
                restored.append(page)
        self.app_root.after(0, self._apply_restored_session, meta, restored, skipped)

    def _page_from_session_entry(self, entry):
        if not isinstance(entry, dict):
            return None
        uid = entry.get("uid")
        img = self._session_store.read_image(uid)    # also validates the uid
        if img is None:
            return None
        h, w = img.shape[:2]
        if entry.get("width") != w or entry.get("height") != h:
            return None    # pixels don't match the metadata, corners would be wrong

        source = entry.get("source_path")
        if not isinstance(source, str) or not source:
            source = self._session_store.image_path(uid)
        page = _PageData(source, img, [], uid=uid)

        rotation = entry.get("rotation", 0)
        if rotation in (90, 180, 270):
            page.rotation = int(rotation)
            page.display_image = rotate_image(img, page.rotation)

        dh, dw = page.display_image.shape[:2]
        corners = entry.get("corners")
        if _valid_corners(corners):
            # Already in display (rotated) coordinates: do NOT call _apply_rotation.
            page.corners = [(min(max(int(round(x)), 0), dw), min(max(int(round(y)), 0), dh))
                            for x, y in corners]
        else:
            page.corners = self._default_corners_for_shape(dh, dw)
        return page

    def _apply_restored_session(self, meta, restored, skipped):
        if restored:
            # self.pages is empty: every way to add a page was locked meanwhile.
            self.pages = restored + self.pages
            idx = meta.get("current_index", 0)
            self.current_index = idx if isinstance(idx, int) and 0 <= idx < len(self.pages) else 0
            label = self._mode_label(meta.get("scan_mode"))
            if label:
                self.scan_mode_var.set(label)
            out = meta.get("output_path")
            if isinstance(out, str) and out and not self.output_var.get().strip():
                self.output_var.set(out)      # trace fires, saves are still suppressed

        self._session_restoring = False
        self._detecting_corners = False
        self._set_corner_detection_busy(False)
        self.status_var.set(tr("str_ready"))

        if not restored:
            self._session_store.clear()
            self.feedback.set_info(tr("scanner_session_title"), tr("scanner_session_failed"))
            return

        self._show_current_page()
        if skipped:
            self.feedback.set_info(
                tr("scanner_session_title"),
                tr("scanner_session_restored_partial").format(count=len(restored), skipped=skipped),
            )
            self._schedule_session_save()    # rewrite session.json without the broken pages
        else:
            self.feedback.set_info(
                tr("scanner_session_title"),
                tr("scanner_session_restored").format(count=len(restored)),
            )
```

**Durum makinesi (neden iki bayrak var)**

| Durum | `_session_restoring` | `_detecting_corners` | Anlamı |
|---|---|---|---|
| Oturum yok | False | False | Normal çalışma, kayıtlar açık. |
| Oturum bulundu, sekme henüz açılmadı | **True** | False | Hiçbir kayıt diskteki oturumun üzerine yazamaz. Tray'e gizlenip çıkılsa bile oturum korunur. Sekme görünmediği için kullanıcı etkileşimi yok. |
| Resimler çözülüyor | **True** | **True** | UI kilitli, InlineFeedback "yükleniyor" gösterir. |
| Uygulandı | False | False | Normal çalışma. |

### 5.8 `start_scan` ve `_run_scan`: başarılı PDF sonrası temizlik

```diff
@@ start_scan
         self._task_ctx = TaskContext(progress_callback=_on_progress)
+        self._scan_start_rev = self._session_rev
         self.footer.start_busy(cancel_callback=self._cancel_task)

@@ _run_scan → iç fonksiyon _done()   (ana thread'de çalışır)
             def _done():
                 self.footer.finish_success()
                 self.status_var.set(tr("scanner_done"))
                 self.feedback.set_success(tr("scanner_done"), msg, output_pdf)
+                # Only forget the session if nothing changed while the PDF was
+                # being written; otherwise those edits are not in the PDF yet.
+                if self._session_rev == self._scan_start_rev:
+                    self._clear_session()
             self.app_root.after(0, _done)
```

`CancelledError` ve `Exception` dallarına **hiçbir şey eklenmez**. İptal edilen ya da hata veren bir tarama oturumu silmemelidir.

### 5.9 (Önerilir) "Tümünü Temizle" butonu

Oturum artık kendiliğinden geri geldiği için, kullanıcının sıfırdan başlamak istediğinde 20 sayfayı tek tek silmesi gerekmemeli. Test edilmiş kod:

```diff
@@ build_ui, toolbar1
         self.remove_photo_button.pack(side="left", padx=(0, 6))
+        ttk.Button(toolbar1, text=tr("scanner_clear_all"), command=self.clear_all_pages, style="Ghost.TButton").pack(side="left", padx=(0, 6))
```

`remove_current`'ın hemen altına:

```python
    def clear_all_pages(self):
        """Drop every page and the saved session to start a new document."""
        if not self.pages or self._detecting_corners:
            return
        if not messagebox.askyesno(tr("scanner_clear_all"), tr("scanner_clear_all_confirm"), parent=self.app_root):
            return
        self.pages.clear()
        self._thumb_cache.clear()
        self.current_index = -1
        self.canvas.delete("all")
        self.preview_canvas.delete("all")
        self._show_current_page()
        self._clear_session()
        self.feedback.set_info(tr("scanner_crop_area"), tr("scanner_select_hint"))
```

Buton `toolbar1` içinde olduğu için `_detect_controls` listesine otomatik girer ve meşgulken devre dışı kalır.

---

## 6. `src/gui/main_window.py` değişiklikleri

```diff
+import logging
 import os
 import sys
 import threading
```

```diff
+    def _scanner_tab(self):
+        workspace = self.workspaces.get("scanner")
+        return workspace.instance if workspace else None
+
     def on_closing(self):
         if cfg.get("close_to_tray", True) and self.icon_path:
+            scanner = self._scanner_tab()
+            if scanner:
+                scanner.save_session_now()
             self.root.withdraw()
             self._notify_running_in_tray()
         else:
             self.quit_window(None, None)
```

```diff
     def quit_window(self, icon, _item):
         if getattr(self, "tray_icon", None):
             self.tray_icon.stop()
-        self.root.after(0, self.root.quit)
+        # May be called from the tray thread: hop to the Tk thread first.
+        self.root.after(0, self._quit_mainloop)
+
+    def _quit_mainloop(self):
+        scanner = self._scanner_tab()
+        if scanner:
+            try:
+                self.root.config(cursor="watch")
+                self.root.update_idletasks()
+                scanner.flush_session(timeout=10.0)
+            except Exception:
+                logging.exception("Scanner session could not be flushed on exit")
+        self.root.quit()
```

**Neden böyle?**
- `quit_window` pystray thread'inden çağrılır (F6). `flush_session` ise `after_cancel` ve `after` kullanır, bu yüzden **ana thread'de** çalışmalıdır. `_quit_mainloop` bunu `after(0)` ile sağlar.
- `on_closing` (tray'e gizleme) sadece kaydı kuyruğa atar, beklemez. Process yaşadığı için yazıcı thread işi bitirir.
- `flush` en fazla 10 sn bekler. Kullanıcı 20 fotoğraf ekleyip hemen çıkarsa PNG yazımı birkaç saniye sürebilir (§9). Süre dolarsa uygulama yine kapanır. Atomik yazma sayesinde dosyalar bozulmaz, en fazla bir önceki tutarlı oturum açılır.
- Görev yöneticisinden öldürme ya da elektrik kesintisinde en fazla son ~400 ms + o anki yazım kaybolur. Diskte her zaman tutarlı bir önceki durum vardır.

---

## 7. `src/core/lang_manager.py`: yeni anahtarlar

`"tr"` sözlüğünde `"scanner_detect_busy"` satırından sonra:

```python
        "scanner_session_title":            "Kaldığınız Yerden Devam",
        "scanner_session_restoring":        "Önceki tarama oturumu yükleniyor...",
        "scanner_session_restored":         "{count} sayfa geri yüklendi. PDF oluşturulunca oturum temizlenir.",
        "scanner_session_restored_partial": "{count} sayfa geri yüklendi, {skipped} sayfa okunamadığı için atlandı.",
        "scanner_session_failed":           "Önceki oturum bulundu ama sayfaları okunamadı; oturum temizlendi.",
        "scanner_session_save_failed":      "Tarama oturumu diske kaydedilemedi: {error}",
        "scanner_session_locked":           "Tarayıcı oturumu başka bir PDF Aura penceresinde açık. Bu penceredeki değişiklikler kaydedilmeyecek.",
        "scanner_clear_all":                "Tümünü Temizle",
        "scanner_clear_all_confirm":        "Tüm sayfalar ve kayıtlı oturum silinsin mi?",
```

`"en"` sözlüğünde `"scanner_detect_busy"` satırından sonra:

```python
        "scanner_session_title":            "Pick Up Where You Left Off",
        "scanner_session_restoring":        "Restoring your previous scan session...",
        "scanner_session_restored":         "{count} page(s) restored. The session is cleared once the PDF is created.",
        "scanner_session_restored_partial": "{count} page(s) restored, {skipped} could not be read and were skipped.",
        "scanner_session_failed":           "A previous session was found but its pages could not be read; it was cleared.",
        "scanner_session_save_failed":      "The scan session could not be saved to disk: {error}",
        "scanner_session_locked":           "The scanner session is open in another PDF Aura window. Changes made here will not be saved.",
        "scanner_clear_all":                "Clear All",
        "scanner_clear_all_confirm":        "Remove all pages and the saved session?",
```

---

## 8. Edge case'ler

| Durum | Davranış | Nerede ele alınıyor |
|---|---|---|
| **Orijinal fotoğraf silindi, taşındı ya da düzenlendi** | Oturum PNG'den açılır. "Otomatik Algıla" PNG'yi kullanır. | PNG kopyası + `_detection_source_path` |
| **`session.json` bozuk (JSON değil)** | `session.json.corrupt` olarak taşınır, resimler silinir, boş başlar. Çökme olmaz. | `load_meta` → `_quarantine` |
| **Şekil yanlış** (`pages` liste değil, `version` yok ya da farklı) | Bozuk gibi davranılır. | `load_meta` |
| **`version` daha büyük** (kullanıcı eski sürüme döndü) | Dosyalara **dokunulmaz**, bu çalıştırmada kalıcılık kapalıdır. Yeni sürüme dönünce oturum geri gelir. | `load_meta` → `enabled=False` |
| **`session.json` okunamıyor** (antivirüs kilidi vb.) | 3 deneme yapılır. Olmazsa kalıcılık bu çalıştırmada kapatılır, **dosyalar silinmez**. | `load_meta` |
| **Bir PNG eksik veya okunamıyor** | O sayfa atlanır, diğerleri açılır. "N sayfa atlandı" mesajı gösterilir. JSON hemen temiz hâliyle yeniden yazılır. | `_page_from_session_entry` → `_apply_restored_session` |
| **Hiçbir PNG okunamadı** | Oturum temizlenir, bilgi mesajı gösterilir. | `_apply_restored_session` |
| **PNG boyutu JSON'daki `width`/`height` ile uyuşmuyor** | Sayfa atlanır (köşeler anlamsız olurdu). | `_page_from_session_entry` |
| **Köşeler geçersiz** (4 değil, NaN, string, bool) | O sayfa varsayılan köşelerle açılır. | `_valid_corners` |
| **Köşeler görüntü dışında** | `[0,w]×[0,h]` aralığına kırpılır (sürükleme ile aynı kural). | `_page_from_session_entry` |
| **Kurcalanmış `uid`** (`"../../x"`) | Regex ile reddedilir, dosya sistemine hiç gidilmez. | `read_image` / `UID_RE` |
| **İkinci PDF Aura instance'ı** | Kilit alınamaz. Oturum okunmaz ve yazılmaz, sekmede uyarı görünür. İlk instance'ın verisi güvende kalır. | `_try_lock`, `locked_by_other` |
| **Uygulama köşe tespiti sırasında kapandı** | Tespiti biten sayfalar kaydedilmiştir (sonuç başına hook). Bitmeyenler varsayılan köşelerle açılır, kullanıcı "Otomatik Algıla"ya basabilir. | §5.5 |
| **PDF yazılırken kullanıcı bir şey değiştirdi** | PDF başarılı olsa bile oturum **silinmez**. | `_session_rev` / `_scan_start_rev` |
| **PDF iptal edildi ya da hata verdi** | Oturum aynen kalır. | §5.8 |
| **PDF sonrası kullanıcı düzenlemeye devam etti** | Oturum yeniden oluşur, resimler tekrar yazılır (kendini onaran kayıt). | `_do_save` isfile kontrolü |
| **Son sayfa silindi** | Oturum diskte temizlenir. | `_save_session` → `if not self.pages` |
| **Disk dolu, izin hatası** | Yazıcı thread çökmez. Hata loglanır ve InlineFeedback'te **bir kez** gösterilir. Önceki tutarlı oturum diskte kalır. Sonraki kayıt eksik resmi tekrar dener. | `_run` → `on_error` → `_on_session_error` |
| **Yazım ortasında çökme** | Geride sadece `.tmp` dosyaları kalır. Bir sonraki kayıt bunları öksüz olarak siler. `session.json` hep tutarlıdır. | atomik yazma + `_remove_orphans` |
| **Dil değişti** | Mod iç sabitle saklandığı için doğru etikete çevrilir. | `_mode_label` |
| **Kullanıcı tarayıcı sekmesini hiç açmadı** | Resimler hiç çözülmez (sıfır RAM ve CPU). Oturum bir sonraki açılışa aynen kalır. | `<Map>` + `_session_restoring` |
| **Pencere tray'e gizlenip tekrar gösterildi** | `<Map>` tekrar tetiklenir ama tek seferlik korumadan geçemez. | `_begin_session_restore` |
| **Büyük resimler (12 MP ve üstü)** | PNG ~25 MB/sayfa. Yazma ve okuma UI thread'inde **yapılmaz**. Resim küçültülmez: köşe koordinatları ve PDF kalitesi orijinal piksele bağlıdır. | §9 |

---

## 9. Performans notları

Ölçüm (bu makine, OpenCV 5.0, 4032×3024 fotoğraf benzeri görüntü):

| İşlem | Süre | Boyut |
|---|---|---|
| PNG yazma, sıkıştırma 1 | ~780 ms | ~25 MB |
| PNG yazma, sıkıştırma 6 | ~1110 ms | ~24 MB |
| PNG okuma | ~200 ms | |
| `cv2.rotate` 90° | ~16 ms | |
| Karşılaştırma: JPEG q92 | | ~3 MB |

Sonuçlar:

1. **PNG yazma asla ana thread'de yapılmaz.** Sayfa başına ~0,8 sn UI donması kabul edilemez. Tek yazıcı thread bunu üstlenir.
2. **Resim yalnızca bir kez yazılır.** `_do_save` önce `os.path.isfile` kontrolü yapar (stat, mikrosaniyeler). Döndürme ya da köşe değişikliği sadece ~1-5 KB'lık JSON'u yeniden yazar.
3. **Sıkıştırma seviyesi 1** seçildi. Seviye 6, %40 daha yavaş ama sadece %3 daha küçük.
4. **400 ms debounce.** Art arda gelen değişiklikler tek kayda iner. `_save_session`'ın ana thread maliyeti sadece metadata dict'ini kurmaktır (<1 ms). `cv_image` kopyalanmaz, referansı gönderilir.
5. **Geri yükleme tembel ve arka planda.** Açılışta sadece JSON okunur. 20 sayfalık bir oturumun ~4 sn'lik çözme süresi, sekme açıldığında worker thread'de geçer. UI bu sırada "yükleniyor" gösterir ve kilitlidir.
6. **Kuyruk birleştirme (coalescing) yok.** Debounce sonrası kuyrukta nadiren 1-2'den fazla iş olur ve JSON yazımı ucuzdur. Karmaşıklığa değmez.
7. **Disk kullanımı** yaklaşık sayfa × 25 MB'tır (12 MP için). PDF başarılı olunca silinir.
   - *Neden orijinal JPEG baytları kopyalanmıyor (~3 MB)?* JPEG'in pikselleri, EXIF yönlendirmesini nasıl uyguladığına bağlı olarak OpenCV sürümleri arasında değişebilir. Değişirse genişlik ve yükseklik yer değiştirir ve kaydedilen köşeler yanlış yere düşer. PNG'deki çözülmüş pikseller sürümden bağımsızdır. Disk önemli hâle gelirse ileride `"image_format"` alanıyla şema versiyon 2'de değerlendirilebilir.
8. **RAM (mevcut durum, bu işin kapsamı dışında):** `_PageData` her sayfa için `cv_image` + `display_image = cv_image.copy()` tutar (12 MP'de ~75 MB). Oturum geri yüklemesi bunu artırmaz, ekleme ile aynıdır. İleride `rotation == 0` iken kopya yerine aynı dizi paylaşılabilir.

---

## 10. YAPMA listesi (en olası hatalar)

1. ❌ Geri yüklerken `_apply_rotation` / `rotate_cw` çağırmak. Köşeler zaten döndürülmüş koordinatta, iki kez döner (F2).
2. ❌ `scan_mode_var.get()` değerini (çevrilmiş etiketi) kaydetmek (F3).
3. ❌ `json.dump`'a numpy tipleri vermek. Her değeri `int()` / `float()` / `str()` ile düz Python tipine çevir.
4. ❌ `session.json`'u ya da PNG'yi ana thread'de yazmak. `_save_session` sadece kuyruğa atar.
5. ❌ `imwrite_unicode` ile `.tmp` uzantılı dosyaya yazmak (F8).
6. ❌ Worker thread'den `self.feedback`, `self.canvas`, `StringVar` vb. Tk nesnelerine dokunmak. Tek izinli çağrı `self.app_root.after(0, ...)`.
7. ❌ `after()` / `after_cancel()`'ı ana thread dışından çağırmak. `_schedule_session_save`, `flush_session` ve `save_session_now` sadece ana thread'den çağrılır. Tray thread'i önce `after(0)` ile ana thread'e geçer.
8. ❌ Yazıcı thread'i `daemon=False` yapmak. Process kapanmaz.
9. ❌ Oturum bulunmuşken, uygulanmadan önce kayda izin vermek. Boş `pages` ile yapılan tek bir kayıt diskteki oturumu **siler** (`_session_restoring` bunu engeller).
10. ❌ `_on_canvas_drag` / `_fs_on_drag` içine kayıt eklemek. Kayıt sadece bırakmada yapılır.
11. ❌ İptal edilen ya da hata veren taramada oturumu temizlemek.
12. ❌ Resimleri küçültüp kaydetmek. Köşeler ve PDF kalitesi orijinal piksele bağlıdır.
13. ❌ `cv_image`'i yerinde (in-place) değiştiren kod yazmak. Değişmesi gerekirse yeni `uid` ver (§2.3).
14. ❌ i18n anahtarını sadece `"tr"` sözlüğüne eklemek (F11).

---

## 11. Uygulama sırası (checklist)

- [ ] 1. `config_manager.py`: `scanner_session_enabled` varsayılanı + `scanner_session_dir` property'si (§3)
- [ ] 2. `src/core/scanner_session.py` dosyasını oluştur (§4)
- [ ] 3. `lang_manager.py`: 9 anahtar × 2 dil (§7)
- [ ] 4. `tab_scanner.py`: import'lar, `SESSION_SAVE_DELAY_MS`, `_valid_corners` (§5.1-5.2)
- [ ] 5. `tab_scanner.py`: `_PageData.uid` (§5.3)
- [ ] 6. `tab_scanner.py`: `__init__` alanları + trace + `_load_session()` (§5.4)
- [ ] 7. `tab_scanner.py`: yeni metot bloğu (§5.7)
- [ ] 8. `tab_scanner.py`: 9 hook + combobox bind (§5.5)
- [ ] 9. `tab_scanner.py`: `auto_detect` değişikliği (§5.6)
- [ ] 10. `tab_scanner.py`: `start_scan` / `_done` temizliği (§5.8)
- [ ] 11. (Önerilir) "Tümünü Temizle" (§5.9)
- [ ] 12. `main_window.py`: `_scanner_tab`, `on_closing`, `quit_window`, `_quit_mainloop` (§6)
- [ ] 13. `python -m py_compile` ile tüm değişen dosyaları derle
- [ ] 14. Ek A testini çalıştır, `ALL OK` görmeden bitmiş sayma
- [ ] 15. §12'deki manuel senaryoları uygulamada dene

---

## 12. Manuel test senaryoları

Uygulamayı `baslat.bat` ile aç. "Çıkış" = tray simgesine sağ tık → Çıkış (X sadece gizler).

1. **Temel akış:** 3 fotoğraf ekle, birini döndür, birinin köşesini sürükle, sırayı değiştir, stili "Siyah-Beyaz" yap, çıkış yolu seç → Çıkış → tekrar aç → Belge Tara. Her şey aynı olmalı. Feedback'te "3 sayfa geri yüklendi" görünmeli.
2. **Orijinal silindi:** 1. senaryodan sonra fotoğrafları diskten sil → aç. Oturum yine gelmeli. "Otomatik Algıla" çalışmalı.
3. **PDF temizler:** PDF Oluştur → başarılı → Çıkış → aç. Tarayıcı boş olmalı, `%APPDATA%\PDFAura\scanner_session\session.json` bulunmamalı.
4. **PDF sonrası düzenleme:** PDF'ten sonra bir sayfayı döndür → Çıkış → aç. Oturum geri gelmeli.
5. **Hızlı çıkış:** Köşe sürükle ve hemen (400 ms dolmadan) tray'den Çıkış yap → aç. Son köşe konumu korunmuş olmalı.
6. **Tespit sırasında çıkış:** 10 fotoğraf ekle, köşe tespiti sürerken Çıkış → aç. Bitmiş sayfalar tespit edilmiş köşelerle, diğerleri varsayılan köşelerle açılmalı. Çökme olmamalı.
7. **İkinci instance:** Uygulama tray'deyken Başlat menüsünden tekrar aç → Belge Tara. "Başka pencerede açık" uyarısı görünmeli. İlk instance'ın oturumu bozulmamalı.
8. **Dil değişimi:** Oturum varken dili değiştir, yeniden başlat. Tarama stili doğru dilde ve doğru seçili olmalı.
9. **Bozuk dosya:** `session.json` içine rastgele metin yaz → aç. Boş tarayıcı açılmalı, `session.json.corrupt` oluşmalı, çökme olmamalı.
10. **Sekmeyi açmadan çıkış:** Oturum varken uygulamayı aç, Belge Tara'ya **girmeden** Çıkış → aç → Belge Tara. Oturum hâlâ gelmeli.
11. **Unicode:** `Masaüstü\fotoğraf_şçö.jpg` gibi Türkçe karakterli yollarla 1. senaryoyu tekrarla.

---

## 13. Kapsam dışı / Faz 2 fikirleri

- **Yarım kalan tespiti otomatik sürdürmek:** sayfa başına `"detect_pending": true` sakla, geri yüklemede bu sayfalar için `_start_corner_detection` başlat.
- **Ayarlar penceresinde** `scanner_session_enabled` anahtarı ve "Oturum boyutu: 312 MB, [Temizle]" satırı.
- **Birden fazla isimli oturum** ("Faturalar", "Kimlik") ve oturum listesi.
- **RAM optimizasyonu:** `rotation == 0` iken `display_image` için kopya yerine `cv_image` paylaşımı.

---

## Ek A: Uçtan uca kabul testi

Repo köküne `session_e2e_test.py` adıyla kaydet ve uygulamanın Python'uyla çalıştır:

```bash
"C:\Users\<kullanıcı>\AppData\Local\Programs\Python\Python312\python.exe" session_e2e_test.py
```

Beklenen son satır `ALL OK`. Test gerçek `%APPDATA%`'ya dokunmaz, repo altında `_appdata_test/` ve `_photos_test/` klasörlerini kullanır. İş bitince bu iki klasörü ve test dosyasını sil. **Commit'leme.**

Önemli: Worker thread'ler `app_root.after()` kullandığı için testte `root.update()` döngüsü **çalışmaz** ("main thread is not in main loop" hatası verir). `pump()` bu yüzden gerçek `mainloop()` + `quit()` kullanır.

```python
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APPDATA = os.path.join(HERE, "_appdata_test")
shutil.rmtree(APPDATA, ignore_errors=True)
os.makedirs(APPDATA)
os.environ["APPDATA"] = APPDATA          # before cfg is imported
sys.path.insert(0, HERE)

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk

from src.core.config_manager import cfg
from src.core.document_scanner import imwrite_unicode
from src.core.scanner_session import ScannerSessionStore
from src.gui.styles import setup_styles
import src.gui.tabs.tab_scanner as ts

SESSION_DIR = cfg.scanner_session_dir
assert SESSION_DIR.startswith(APPDATA), SESSION_DIR
META = os.path.join(SESSION_DIR, "session.json")
IMGS = os.path.join(SESSION_DIR, "images")


def pump(root, cond, timeout=60, what=""):
    # Worker threads use app_root.after(), which needs a running mainloop.
    end = time.time() + timeout
    ok = []

    def check():
        if cond():
            ok.append(True)
            root.quit()
        elif time.time() > end:
            root.quit()
        else:
            root.after(10, check)

    root.after(0, check)
    root.mainloop()
    if not ok:
        raise AssertionError(f"timeout waiting for {what}")


def wait_ms(root, ms):
    end = time.time() + ms / 1000
    pump(root, lambda: time.time() >= end, timeout=ms / 1000 + 5)


def make_photo(path, w, h, seed):
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), 60, np.uint8)
    img += rng.integers(0, 20, img.shape, dtype=np.uint8)
    cv2.rectangle(img, (w // 6, h // 8), (w - w // 5, h - h // 7), (235, 235, 235), -1)
    for i in range(8):
        y = h // 8 + 40 + i * 30
        cv2.line(img, (w // 6 + 30, y), (w - w // 5 - 30, y), (40, 40, 40), 3)
    assert imwrite_unicode(path, img)


def new_tab(pack):
    root = tk.Tk()
    root.geometry("1300x850")
    setup_styles()
    frame = ttk.Frame(root)
    tab = ts.ScannerTab(frame, root)
    if pack:
        frame.pack(fill="both", expand=True)
    root.update()
    return root, frame, tab


def snapshot(tab):
    return {
        "pages": [(p.uid, p.path, p.rotation, [(x, y) for x, y in p.corners],
                   p.cv_image.shape, p.display_image.shape) for p in tab.pages],
        "mode": tab._get_selected_mode(),
        "output": tab.output_var.get(),
        "index": tab.current_index,
    }


def close(root, tab):
    tab._session_store._lock_fh.close()     # release so the next "process" can own it
    root.destroy()


# ── photos with unicode names ──
src_dir = os.path.join(HERE, "_photos_test")
shutil.rmtree(src_dir, ignore_errors=True)
os.makedirs(src_dir)
photos = []
for i, (w, h) in enumerate([(1200, 900), (900, 1300), (1000, 1000)]):
    p = os.path.join(src_dir, f"fotoğraf_şçö_{i}.jpg")
    make_photo(p, w, h, i)
    photos.append(p)

# ═════ RUN 1: build a session ═════
root, frame, tab = new_tab(pack=True)
assert not tab._session_restoring and tab.pages == []
tab._add_image_pages(photos)
pump(root, lambda: not tab._detecting_corners, what="detection")

tab.current_index = 0
tab.rotate_cw()                                       # page0 rotation 90
tab.current_index = 1
tab.rotate_ccw(); tab.rotate_ccw()                    # page1 rotation 180
tab.pages[2].corners = [(10, 12), (900, 15), (905, 950), (8, 940)]
tab.current_index = 2
tab.move_page(-1)                                     # order: p0, p2, p1 ; index 1
tab.scan_mode_var.set(ts.tr("scanner_mode_bw"))
tab._on_mode_changed()
out_pdf = os.path.join(src_dir, "çıktı_tarandı.pdf")
tab.output_var.set(out_pdf)

# debounce: nothing written yet right after the change
assert tab._session_save_job is not None
wait_ms(root, 700)
assert tab._session_store.flush(10)
assert os.path.isfile(META), "session.json missing after debounce"
meta = json.load(open(META, encoding="utf-8"))
assert meta["version"] == 1 and meta["scan_mode"] == "bw" and meta["output_path"] == out_pdf
assert len(os.listdir(IMGS)) == 3
mtimes = {n: os.path.getmtime(os.path.join(IMGS, n)) for n in os.listdir(IMGS)}

# second instance must not get the lock
other = ScannerSessionStore(SESSION_DIR)
assert other.locked_by_other and not other.enabled
print("lock OK")

# more edits: images must NOT be rewritten
time.sleep(1.1)
tab.current_index = 0
tab.reset_corners()
wait_ms(root, 600)
tab._session_store.flush(10)
assert {n: os.path.getmtime(os.path.join(IMGS, n)) for n in os.listdir(IMGS)} == mtimes, "images rewritten"
print("images written once OK")

# remove a page → its PNG is garbage collected
removed_uid = tab.pages[2].uid
tab.current_index = 2
tab.remove_current()
tab.flush_session()
assert not os.path.exists(os.path.join(IMGS, removed_uid + ".png"))
assert len(json.load(open(META, encoding="utf-8"))["pages"]) == 2
print("remove + orphan cleanup OK")

# pending change + quit flush (no waiting for debounce)
tab.current_index = 1
tab.rotate_cw()
assert tab._session_save_job is not None
tab.flush_session()
before = snapshot(tab)
close(root, tab)

# originals deleted → must still restore
for p in photos:
    os.remove(p)

# ═════ RUN 2: restore lazily on first show ═════
root, frame, tab = new_tab(pack=False)
assert tab._session_restoring and tab.pages == [], "should wait for first show"
tab._save_session()                                   # must not clobber pending session
tab._session_store.flush(5)
assert os.path.isfile(META)
frame.pack(fill="both", expand=True)
pump(root, lambda: not tab._session_restoring, what="restore")
after = snapshot(tab)
assert after == before, f"\n{before}\n!=\n{after}"
assert all(type(v) is int for pg in tab.pages for pt in pg.corners for v in pt), "corner types"
print("restore equals saved state OK:", tab.feedback.message_var.get())

# auto-detect uses the session PNG (original is gone)
src = tab._detection_source_path(tab.pages[0])
assert src.startswith(IMGS), src
print("detection source OK")

# ═════ export clears session ═════
tab.start_scan()
pump(root, lambda: not os.path.isfile(META), timeout=120, what="clear after export")
assert os.path.isfile(out_pdf)
tab._session_store.flush(5)
assert not os.path.exists(IMGS) or not os.listdir(IMGS)
print("export clears session OK")

# edit after export → session recreated incl. images
tab.rotate_cw()
tab.flush_session()
assert os.path.isfile(META) and len(os.listdir(IMGS)) == 2
print("edit after export re-creates session OK")
close(root, tab)

# ═════ RUN 3: one PNG missing → partial restore ═════
missing = os.listdir(IMGS)[0]
os.remove(os.path.join(IMGS, missing))
root, frame, tab = new_tab(pack=True)
pump(root, lambda: not tab._session_restoring, what="partial restore")
assert len(tab.pages) == 1, len(tab.pages)
print("partial:", tab.feedback.message_var.get())
tab._session_store.flush(5)
wait_ms(root, 600)
tab._session_store.flush(5)
assert len(json.load(open(META, encoding="utf-8"))["pages"]) == 1
close(root, tab)

# ═════ corrupt json ═════
open(META, "w", encoding="utf-8").write("{not json")
root, frame, tab = new_tab(pack=True)
assert tab.pages == [] and not tab._session_restoring
assert os.path.isfile(META + ".corrupt") and not os.path.isfile(META)
print("corrupt json quarantined OK")
close(root, tab)

# ═════ newer version is left alone ═════
json.dump({"version": 99, "pages": [{"uid": "x"}]}, open(META, "w", encoding="utf-8"))
root, frame, tab = new_tab(pack=True)
assert not tab._session_store.enabled and os.path.isfile(META)
tab._schedule_session_save()
assert tab._session_save_job is None
print("newer version untouched OK")
close(root, tab)

# ═════ tampered uid (path traversal) ═════
json.dump({"version": 1, "pages": [{"uid": "../../evil", "width": 1, "height": 1, "rotation": 0,
                                     "corners": [[0, 0], [1, 0], [1, 1], [0, 1]]}]},
          open(META, "w", encoding="utf-8"))
root, frame, tab = new_tab(pack=True)
pump(root, lambda: not tab._session_restoring, what="tampered restore")
assert tab.pages == [] and not os.path.isfile(META)
print("tampered uid rejected OK:", tab.feedback.message_var.get())
close(root, tab)

print("\nALL OK")
```
