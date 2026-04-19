import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import queue
import tempfile
import threading

import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel


class SpeechRecognizer:
    def __init__(self, model_size="small"):
        self.model_size = model_size
        self.model = None
        self.is_recording = False
        self.model_ready = False
        self.audio_queue = queue.Queue()
        self.samplerate = 16000
        self.audio_data = []
        self.stream = None
        self._lock = threading.Lock()

    def load_model(self):
        """Modeli ilk ihtiyaç anında yükler (Lazy load)."""
        if self.model is None:
            self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            self.model_ready = True

    def preload_model_async(self, on_start=None, on_complete=None):
        """Arayüz yüklenirken arka planda modeli yüklemek için çağrılabilir."""
        def _worker():
            if self.model is None:
                if on_start:
                    on_start()
                try:
                    self.load_model()
                except Exception as e:
                    print(f"[Model Load Error] {e}")
                if on_complete:
                    on_complete()
            else:
                self.model_ready = True
                if on_complete:
                    on_complete()

        threading.Thread(target=_worker, daemon=True).start()

    def _audio_callback(self, indata, frames, time, status):
        """sounddevice tarafından çağrılan callback."""
        if self.is_recording:
            self.audio_queue.put(indata.copy())

    def start_recording(self):
        with self._lock:
            if self.is_recording:
                return

            self.is_recording = True
            self.audio_data = []

            # Eski queue'u temizle
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break

            try:
                self.stream = sd.InputStream(
                    samplerate=self.samplerate,
                    channels=1,
                    dtype="float32",
                    callback=self._audio_callback,
                )
                self.stream.start()
            except sd.PortAudioError as e:
                print(f"[Mikrofon Hatası] Mikrofon bulunamadı veya erişim reddedildi: {e}")
                self.is_recording = False
            except Exception as e:
                print(f"[Record Start Error] {e}")
                self.is_recording = False

    def stop_recording_and_recognize(self, callback):
        """Kayıt durur ve başka bir thread'de whisper tanıma yapar."""
        with self._lock:
            if not self.is_recording:
                callback("")
                return

            self.is_recording = False

            # Stream'i güvenli şekilde kapat
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception as e:
                    print(f"[Stream Close Warning] {e}")
                finally:
                    self.stream = None

        # Kuyruktaki tüm veriyi al
        while not self.audio_queue.empty():
            try:
                self.audio_data.append(self.audio_queue.get_nowait())
            except queue.Empty:
                break

        if not self.audio_data:
            callback("")
            return

        # Çok kısa kayıtları reddet (< 0.5 saniye)
        audio_concat = np.concatenate(self.audio_data, axis=0)
        duration = len(audio_concat) / self.samplerate
        if duration < 0.5:
            print(f"[Kayıt çok kısa: {duration:.1f}s] Atlanıyor.")
            callback("")
            return

        # Geçici dosyaya kaydet
        temp_wav = tempfile.mktemp(suffix=".wav")
        try:
            sf.write(temp_wav, audio_concat, self.samplerate)
        except Exception as e:
            print(f"[Record Save Error] {e}")
            callback("")
            return

        def _recognize_worker():
            try:
                self.load_model()
                segments, info = self.model.transcribe(temp_wav, language="tr")
                text = " ".join([segment.text for segment in segments])
                callback(text.strip())
            except Exception as e:
                print(f"[Whisper Error] {e}")
                callback("")
            finally:
                # Geçici dosyayı her durumda sil
                try:
                    if os.path.exists(temp_wav):
                        os.remove(temp_wav)
                except Exception:
                    pass

        threading.Thread(target=_recognize_worker, daemon=True).start()


# Sisteme global tekil örnek
recognizer = SpeechRecognizer()
