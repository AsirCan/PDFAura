"""
Merkezi görev yönetimi altyapısı.
İptal desteği, ilerleme takibi ve bellek optimizasyonu sağlar.
"""
import gc
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


class CancelledError(Exception):
    """Kullanıcı tarafından iptal edilen işlemlerde fırlatılır."""
    pass


class TaskContext:
    """
    İşlem fonksiyonlarına geçirilen bağlam nesnesi.
    İlerleme raporlama ve iptal kontrolü sağlar.
    """

    def __init__(self, progress_callback=None):
        self._cancel_event = threading.Event()
        self._progress_callback = progress_callback

    def check_cancelled(self):
        """İptal durumunu kontrol eder. İptal edildiyse CancelledError fırlatır."""
        if self._cancel_event.is_set():
            raise CancelledError("İşlem kullanıcı tarafından iptal edildi.")

    def cancel(self):
        """İşlemi iptal etmek için çağrılır."""
        self._cancel_event.set()

    @property
    def is_cancelled(self):
        return self._cancel_event.is_set()

    def report_progress(self, current, total, message=""):
        """
        İlerlemeyi UI'a raporlar.
        current / total oranı yüzde hesabı için kullanılır.
        """
        self.check_cancelled()
        if self._progress_callback:
            self._progress_callback(current, total, message)


def run_parallel(func, items, max_workers=None, ctx=None):
    """
    Çoklu çekirdek desteği ile paralel çalıştırma.
    func(item) -> result şeklinde bir fonksiyon ve item listesi alır.
    Returns (results, errors)
    """
    import os
    if max_workers is None:
        max_workers = min(os.cpu_count() or 4, len(items), 8)

    results = []
    errors = []
    total = len(items)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {executor.submit(func, item): item for item in items}
        for idx, future in enumerate(as_completed(future_to_item), 1):
            if ctx and ctx.is_cancelled:
                executor.shutdown(wait=False, cancel_futures=True)
                raise CancelledError("İşlem kullanıcı tarafından iptal edildi.")
            item = future_to_item[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                errors.append((item, str(e)))
            if ctx:
                ctx.report_progress(idx, total)

    return results, errors


def memory_optimize():
    """Bellek optimizasyonu: Garbage collector'ı zorla çalıştır."""
    gc.collect()


# Büyük dosya eşiği (50 MB)
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024


def is_large_file(file_path):
    """Dosyanın büyük dosya olarak kabul edilip edilmeyeceğini kontrol eder."""
    import os
    try:
        return os.path.getsize(file_path) > LARGE_FILE_THRESHOLD
    except OSError:
        return False
