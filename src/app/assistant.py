"""The assistant: a typed or spoken command, handled the same way for every UI.

The Tk header used to run this itself with four threads and a dozen
root.after calls. The window now only reports what the user did -- submit a
line, press or release the microphone -- and gets back two things through
``post``, on its own thread:

- ``on_state(state, detail)``: what the microphone button should say. One
  of the constants below; ``detail`` is the recognised text for HEARD.
- ``on_reply(text)``: every assistant reply, to show as text. It is also
  spoken, but speech alone left the user with nothing when the voice
  engine was off or missing.

The voice model loads when the microphone is first pressed, never at
startup (~330 MB and ~4 s that most sessions never use).
"""
import logging
import threading

from src.app.jobs import call_now
from src.core.lang_manager import _

IDLE = "idle"
LOADING = "loading"          # the voice model is loading; the button is disabled
LISTENING = "listening"      # recording while the button is held
PROCESSING = "processing"    # recognising speech or running a command
HEARD = "heard"              # detail: what was recognised; the command runs now
MISSING = "missing"          # the voice model could not be loaded


def run_command(text):
    """Parse a command and carry it out. Replies go through text_speaker."""
    from src.ai.action_runner import execute_intent
    from src.ai.intent_parser import parse_intent
    execute_intent(parse_intent(text))


class Assistant:
    def __init__(self, post=call_now, on_state=None, on_reply=None, recognizer=None, command=run_command):
        from src.ai import text_speaker
        self._post = post
        self._on_state = on_state
        self._on_reply = on_reply
        self._recognizer = recognizer
        self._command = command
        self._loading = False
        self.model_error = None
        self.state = IDLE
        self._listener = text_speaker.add_listener(self._reply)

    @property
    def recognizer(self):
        if self._recognizer is None:
            from src.ai.speech_recognizer import recognizer
            self._recognizer = recognizer
        return self._recognizer

    def close(self):
        """Stop receiving replies (the window is going away)."""
        from src.ai import text_speaker
        text_speaker.remove_listener(self._listener)

    # ── What the user does ────────────────────────────────────────────
    def submit(self, text):
        """Run a typed command in the background. False if there was none."""
        text = (text or "").strip()
        if not text:
            return False
        self._set_state(PROCESSING)
        threading.Thread(target=self._run, args=(text,), daemon=True, name="pdfaura-assistant").start()
        return True

    def press(self):
        """The microphone button went down: record, or load the model first."""
        if self._loading:
            return
        if self.model_error is not None:
            # Explain again rather than sit there looking usable, and retry.
            self._reply(_("voice_model_error_body").format(error=self.model_error))
            self._load_model()
            return
        if not self.recognizer.model_ready:
            self._load_model()
            return
        self._set_state(LISTENING)
        self.recognizer.start_recording()

    def release(self):
        """The microphone button came up: recognise what was said and run it."""
        if not self.recognizer.is_recording:
            return
        self._set_state(PROCESSING)
        self.recognizer.stop_recording_and_recognize(self._heard)

    # ── Behind the scenes ─────────────────────────────────────────────
    def _set_state(self, state, detail=""):
        self.state = state
        if self._on_state:
            self._post(self._on_state, state, detail)

    def _reply(self, text):
        if self._on_reply:
            self._post(self._on_reply, text)

    def _run(self, text):
        try:
            self._command(text)
        except Exception:
            # The runner answers its own errors; this is a bug in it, and the
            # thread must not die without a word.
            logging.getLogger(__name__).exception("Assistant command failed")
            from src.ai.text_speaker import speak
            speak(_("assist_unexpected_error"))
        finally:
            self._set_state(IDLE)

    def _heard(self, text):
        # Called on the recogniser's worker thread.
        if not text:
            from src.ai.text_speaker import speak
            speak(_("assist_not_heard"))
            self._set_state(IDLE)
            return
        self._set_state(HEARD, text)
        self._run(text)

    def _load_model(self):
        self._loading = True

        def started():
            self._set_state(LOADING)

        def ready():
            self._loading = False
            self.model_error = None
            self._set_state(IDLE)

        def failed(exc):
            self._loading = False
            self.model_error = exc
            # Say why: the reason only ever went to the console before.
            self._set_state(MISSING)
            self._reply(_("voice_model_error_body").format(error=exc))

        self.recognizer.load_model_async(on_start=started, on_success=ready, on_error=failed)
