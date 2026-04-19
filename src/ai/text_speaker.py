import os
import queue
import tempfile
import threading
import time

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except Exception:
    PYGAME_AVAILABLE = False

# Offline fallback: pyttsx3
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


class TextSpeaker:
    """Text-to-Speech: önce gTTS (online, doğal Türkçe), başarısız olursa pyttsx3 (offline fallback)."""

    def __init__(self):
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        self._offline_engine = None

    def _get_offline_engine(self):
        """pyttsx3 motorunu lazy init eder (COM thread güvenliği için worker içinde)."""
        if self._offline_engine is None and PYTTSX3_AVAILABLE:
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass
            try:
                self._offline_engine = pyttsx3.init()
                self._offline_engine.setProperty("rate", 150)
            except Exception as e:
                print(f"[pyttsx3 Init Error] {e}")
        return self._offline_engine

    def _worker(self):
        while True:
            text = self.queue.get()
            if text is None:
                break

            spoken = False

            # 1. Öncelik: gTTS (doğal Türkçe ses, internet gerekli)
            if GTTS_AVAILABLE and PYGAME_AVAILABLE:
                try:
                    tts = gTTS(text=text, lang="tr")
                    temp_file = tempfile.mktemp(suffix=".mp3")
                    tts.save(temp_file)

                    if pygame.mixer.get_init():
                        pygame.mixer.music.load(temp_file)
                        pygame.mixer.music.play()

                        while pygame.mixer.music.get_busy():
                            pygame.time.Clock().tick(10)

                        try:
                            pygame.mixer.music.unload()
                        except AttributeError:
                            pygame.mixer.music.stop()

                    # Geçici dosyayı sil
                    try:
                        # Kısa bir süre bekle, dosya kilidi kalkabilir
                        time.sleep(0.2)
                        os.remove(temp_file)
                    except Exception:
                        pass

                    spoken = True
                except Exception as e:
                    print(f"[gTTS Error - offline fallback deneniyor] {e}")

            # 2. Fallback: pyttsx3 (internet yoksa veya gTTS başarısız olduysa)
            if not spoken:
                engine = self._get_offline_engine()
                if engine:
                    try:
                        engine.say(text)
                        engine.runAndWait()
                        spoken = True
                    except Exception as e:
                        print(f"[pyttsx3 Error] {e}")

            if not spoken:
                print(f"[TTS] Ses çalınamadı (hem gTTS hem pyttsx3 başarısız): {text}")

            self.queue.task_done()

    def speak(self, text: str):
        """Metni sese dönüştürmek üzere kuyruğa ekler."""
        self.queue.put(text)


# Global instance
speaker = TextSpeaker()


def speak(text: str):
    """
    Belirtilen metni uygulamanın ses motorunu kullanarak okur.
    Online: Google TTS (doğal Türkçe), Offline: pyttsx3 (sistem sesi).
    """
    print(f"[Asistan] {text}")
    speaker.speak(text)
