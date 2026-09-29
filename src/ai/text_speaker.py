import queue
import threading

from src.core.config_manager import cfg

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

# Substrings that identify a voice for a language, in the names SAPI reports.
_VOICE_HINTS = {
    "tr": ("turkish", "türk", "tolga", "-tr", "_tr", "tr-tr"),
    "en": ("english", "zira", "david", "hazel", "-en", "_en", "en-us", "en-gb"),
    "zh": ("chinese", "huihui", "yaoyao", "kangkang", "zh-cn", "zh-tw"),
    "hi": ("hindi", "hemant", "kalpana", "hi-in"),
    "es": ("spanish", "español", "helena", "laura", "pablo", "sabina", "es-es", "es-mx"),
    "ar": ("arabic", "hoda", "naayf", "ar-sa", "ar-eg"),
    "fr": ("french", "français", "hortense", "julie", "paul", "fr-fr", "fr-ca"),
    "bn": ("bengali", "bangla", "bn-in", "bn-bd"),
    "pt": ("portuguese", "português", "maria", "daniel", "helia", "pt-br", "pt-pt"),
    "ru": ("russian", "irina", "pavel", "ru-ru"),
    "ur": ("urdu", "ur-pk", "ur-in"),
    "id": ("indonesian", "andika", "id-id"),
    "de": ("german", "deutsch", "hedda", "katja", "stefan", "de-de"),
    "ja": ("japanese", "haruka", "ayumi", "ichiro", "sayaka", "ja-jp"),
}

# Direction marks lang_manager wraps Arabic and Urdu lines in; they mean
# nothing to a voice.
_BIDI_MARKS = str.maketrans("", "", "\u202b\u202c")


class TextSpeaker:
    """Offline Text-to-Speech wrapper. No text is sent to an external service."""

    def __init__(self):
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        self._offline_engine = None
        self._voice_language = None

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

    def _select_voice(self, engine):
        """Pick a voice matching the UI language.

        Turkish text read by the system default (usually an English voice)
        is close to unintelligible.
        """
        language = cfg.get("language", "tr")
        if language == self._voice_language:
            return
        hints = _VOICE_HINTS.get(language, ())
        try:
            for voice in engine.getProperty("voices"):
                haystack = f"{voice.id} {getattr(voice, 'name', '')}".lower()
                languages = [
                    bytes(item).decode("utf-8", "ignore").lower() if isinstance(item, bytes)
                    else str(item).lower()
                    for item in (getattr(voice, "languages", None) or [])
                ]
                haystack = " ".join([haystack] + languages)
                if any(hint in haystack for hint in hints):
                    engine.setProperty("voice", voice.id)
                    break
        except Exception as exc:
            print(f"[pyttsx3 Voice Error] {exc}")
        self._voice_language = language

    def _worker(self):
        while True:
            text = self.queue.get()
            if text is None:
                break

            spoken = False
            engine = self._get_offline_engine()
            if engine:
                try:
                    self._select_voice(engine)
                    engine.say(text)
                    engine.runAndWait()
                    spoken = True
                except Exception as exc:
                    print(f"[pyttsx3 Error] {exc}")

            if not spoken:
                print(f"[TTS] Offline ses motoru kullanılamadı: {text}")

            self.queue.task_done()

    def speak(self, text: str):
        self.queue.put(text.translate(_BIDI_MARKS))


speaker = TextSpeaker()

# Called with every assistant reply so the UI can show it as text. Speech
# alone left users with no feedback at all when the voice engine was off or
# unavailable.
_listeners = []


def add_listener(callback):
    """Register callback(text) to receive every assistant reply."""
    _listeners.append(callback)
    return callback


def remove_listener(callback):
    if callback in _listeners:
        _listeners.remove(callback)


def speak(text: str):
    """Read text aloud, and hand it to every listener so it can be shown."""
    print(f"[Asistan] {text}")
    for callback in list(_listeners):
        try:
            callback(text)
        except Exception as exc:
            print(f"[Assistant Listener Error] {exc}")
    speaker.speak(text)
