"""Issue #17: the model loaded at every startup and failures were silent."""
import re
import subprocess
import sys
import threading

import pytest

from src.ai import text_speaker
from src.ai.speech_recognizer import SpeechRecognizer
from src.core.config_manager import cfg


# ── Lazy loading (#17.4) ──────────────────────────────────────────────────

def test_importing_the_recognizer_does_not_import_whisper():
    """faster_whisper alone costs time and memory at every launch."""
    code = (
        "import os, sys, tempfile;"
        "os.environ['APPDATA'] = tempfile.mkdtemp();"
        "sys.path.insert(0, r'.');"
        "import src.ai.speech_recognizer;"
        "print('faster_whisper' in sys.modules)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    # Newer PyMuPDF prints a deprecation notice for `import fitz` first.
    assert result.stdout.strip().splitlines()[-1:] == ["False"], result.stdout + result.stderr


def test_recognizer_starts_with_no_model():
    recognizer = SpeechRecognizer()
    assert recognizer.model is None
    assert recognizer.model_ready is False


def test_there_is_no_startup_preload_hook():
    """preload_model_async() was called from MainWindow.__init__."""
    assert not hasattr(SpeechRecognizer, "preload_model_async")
    with open("src/gui/main_window.py", encoding="utf-8") as f:
        assert "preload_model_async" not in f.read()


# ── Load failures are reported (#17.1) ────────────────────────────────────

def test_load_failure_is_recorded_and_reported(monkeypatch):
    """The error only ever reached the console."""
    recognizer = SpeechRecognizer()

    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("offline")

    fake = type(sys)("faster_whisper")
    fake.WhisperModel = Boom
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)

    with pytest.raises(RuntimeError):
        recognizer.load_model()

    assert recognizer.model_ready is False
    assert "offline" in str(recognizer.load_error)


def test_async_load_calls_the_error_callback(monkeypatch):
    recognizer = SpeechRecognizer()

    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("offline")

    fake = type(sys)("faster_whisper")
    fake.WhisperModel = Boom
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)

    seen = {}
    done = threading.Event()

    def on_error(exc):
        seen["error"] = exc
        done.set()

    recognizer.load_model_async(on_error=on_error, on_success=lambda: done.set())
    assert done.wait(5), "callback never fired"
    assert "offline" in str(seen.get("error"))


def test_async_load_calls_the_success_callback(monkeypatch):
    recognizer = SpeechRecognizer()

    class Fine:
        def __init__(self, *a, **k):
            pass

    fake = type(sys)("faster_whisper")
    fake.WhisperModel = Fine
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)

    done = threading.Event()
    recognizer.load_model_async(on_success=done.set, on_error=lambda e: done.set())
    assert done.wait(5)
    assert recognizer.model_ready is True


# ── Replies are visible, not only spoken (#17.2) ──────────────────────────

def test_speak_notifies_listeners():
    """Text-chat results were only spoken; nothing appeared on screen."""
    seen = []
    listener = text_speaker.add_listener(seen.append)
    try:
        text_speaker.speak("islem tamamlandi")
    finally:
        text_speaker.remove_listener(listener)
    assert seen == ["islem tamamlandi"]


def test_a_failing_listener_does_not_break_speaking():
    def boom(_text):
        raise RuntimeError("listener bug")

    seen = []
    text_speaker.add_listener(boom)
    good = text_speaker.add_listener(seen.append)
    try:
        text_speaker.speak("hello")
    finally:
        text_speaker.remove_listener(boom)
        text_speaker.remove_listener(good)
    assert seen == ["hello"]


# ── Language (#17.3) ──────────────────────────────────────────────────────

def test_recognition_language_follows_the_ui():
    recognizer = SpeechRecognizer()
    cfg.config["language"] = "en"
    assert recognizer.language == "en"
    cfg.config["language"] = "tr"
    assert recognizer.language == "tr"


def test_assistant_replies_are_translated():
    from src.core.lang_manager import _
    cfg.config["language"] = "tr"
    turkish = _("assist_not_understood")
    cfg.config["language"] = "en"
    english = _("assist_not_understood")
    cfg.config["language"] = "tr"
    assert turkish != english
    assert english != "assist_not_understood"   # key actually exists


def test_action_names_are_translated():
    from src.ai.action_runner import _get_action_name
    cfg.config["language"] = "tr"
    turkish = _get_action_name("compress")
    cfg.config["language"] = "en"
    english = _get_action_name("compress")
    cfg.config["language"] = "tr"
    assert turkish == "Sikistirma" and english == "Compress"


# ── Temp files (#17.5) ────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["src/ai/speech_recognizer.py", "src/ai/action_runner.py"])
def test_no_insecure_mktemp(path):
    """tempfile.mktemp is insecure and deprecated."""
    with open(path, encoding="utf-8") as f:
        source = f.read()
    assert not re.search(r"tempfile\.mktemp\s*\(", source)
