import queue
import threading

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


class TextSpeaker:
    """Offline Text-to-Speech wrapper. No text is sent to an external service."""

    def __init__(self):
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        self._offline_engine = None

    def _get_offline_engine(self):
        if self._offline_engine is None and PYTTSX3_AVAILABLE:
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass
            try:
                self._offline_engine = pyttsx3.init()
                self._offline_engine.setProperty("rate", 150)
            except Exception as exc:
                print(f"[pyttsx3 Init Error] {exc}")
        return self._offline_engine

    def _worker(self):
        while True:
            text = self.queue.get()
            if text is None:
                break

            spoken = False
            engine = self._get_offline_engine()
            if engine:
                try:
                    engine.say(text)
                    engine.runAndWait()
                    spoken = True
                except Exception as exc:
                    print(f"[pyttsx3 Error] {exc}")

            if not spoken:
                print(f"[TTS] Offline ses motoru kullanılamadı: {text}")

            self.queue.task_done()

    def speak(self, text: str):
        self.queue.put(text)


speaker = TextSpeaker()


def speak(text: str):
    """Read text aloud using the local offline voice engine."""
    print(f"[Asistan] {text}")
    speaker.speak(text)
