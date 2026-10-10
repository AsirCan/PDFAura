"""
Merkezi görev yönetimi altyapısı.
İptal desteği, ilerleme takibi ve bellek optimizasyonu sağlar.
"""
import gc
import threading


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
        self.notify(current, total, message)

    def notify(self, current, total, message=""):
        """Report progress without checking for a cancel, for code that
        checks at its own safe points (the batch loops catch every error per
        file, so a cancel raised from inside one would count as a failed
        file)."""
        if self._progress_callback:
            self._progress_callback(current, total, message)


def memory_optimize():
    """Bellek optimizasyonu: Garbage collector'ı zorla çalıştır."""
    gc.collect()


# Büyük dosya eşiği (50 MB)
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024


