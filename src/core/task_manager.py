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

    def child(self):
        """A context sharing this one's cancellation but reporting no progress.

        Handed to parallel workers: they must notice a cancel (and kill their
        Ghostscript), but four workers fighting over one progress bar would
        just make it jump around.
        """
        child = TaskContext()
        child._cancel_event = self._cancel_event
        return child

    def report_progress(self, current, total, message=""):
        """
        İlerlemeyi UI'a raporlar.
        current / total oranı yüzde hesabı için kullanılır.
        """
        self.check_cancelled()
        if self._progress_callback:
            self._progress_callback(current, total, message)


def memory_optimize():
    """Bellek optimizasyonu: Garbage collector'ı zorla çalıştır."""
    gc.collect()


# Büyük dosya eşiği (50 MB)
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024


