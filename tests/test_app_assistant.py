"""#25: the assistant in src/app/assistant.py, without a window.

The Tk header ran commands, the voice model and the recogniser with its own
threads; any UI now only reports button presses and gets states and replies.
"""
import threading

import pytest

from src.ai import text_speaker
from src.app import assistant
from src.core.lang_manager import _


@pytest.fixture(autouse=True)
def silent(monkeypatch):
    """Replies still reach listeners, but nothing is read aloud."""
    monkeypatch.setattr(text_speaker.speaker, "speak", lambda text: None)


class FakeRecognizer:
    def __init__(self, fail=None, heard="pdf'i sıkıştır"):
        self.model_ready = False
        self.is_recording = False
        self.fail = fail
        self.heard = heard
        self.loads = 0

    def load_model_async(self, on_start=None, on_success=None, on_error=None):
        self.loads += 1
        on_start()
        if self.fail:
            on_error(RuntimeError(self.fail))
        else:
            self.model_ready = True
            on_success()

    def start_recording(self):
        self.is_recording = True

    def stop_recording_and_recognize(self, callback):
        self.is_recording = False
        threading.Thread(target=callback, args=(self.heard,), daemon=True).start()


class Seen:
    def __init__(self):
        self.states = []
        self.replies = []
        self.commands = []
        self.idle = threading.Event()

    def state(self, state, detail):
        self.states.append((state, detail) if detail else state)
        if state == assistant.IDLE:
            self.idle.set()

    def make(self, recognizer=None, command=None):
        return assistant.Assistant(on_state=self.state, on_reply=self.replies.append,
                                   recognizer=recognizer or FakeRecognizer(),
                                   command=command or self.commands.append)


def test_a_typed_command_runs_in_the_background():
    seen = Seen()
    helper = seen.make()
    try:
        assert helper.submit("  rapor.pdf sıkıştır ")
        assert seen.idle.wait(5)
    finally:
        helper.close()
    assert seen.commands == ["rapor.pdf sıkıştır"]
    assert seen.states == [assistant.PROCESSING, assistant.IDLE]


def test_an_empty_command_does_nothing():
    seen = Seen()
    helper = seen.make()
    helper.close()
    assert not helper.submit("   ")
    assert seen.states == [] and seen.commands == []


def test_a_failing_command_is_answered_and_ends_idle():
    seen = Seen()

    def boom(_text):
        raise RuntimeError("bug")
    helper = seen.make(command=boom)
    try:
        helper.submit("x")
        assert seen.idle.wait(5)
    finally:
        helper.close()
    assert seen.replies == [_("assist_unexpected_error")]


def test_the_first_press_loads_the_model_instead_of_recording():
    seen, recognizer = Seen(), FakeRecognizer()
    helper = seen.make(recognizer)
    helper.close()
    helper.press()
    assert recognizer.loads == 1 and not recognizer.is_recording
    assert seen.states == [assistant.LOADING, assistant.IDLE]


def test_a_model_that_cannot_load_says_why_and_retries_on_the_next_press():
    seen, recognizer = Seen(), FakeRecognizer(fail="no network")
    helper = seen.make(recognizer)
    helper.close()
    helper.press()
    assert seen.states[-1] == assistant.MISSING
    assert len(seen.replies) == 1 and "no network" in seen.replies[0]
    helper.press()
    assert recognizer.loads == 2
    assert len(seen.replies) == 3          # explained again, then the retry failed again


def test_hold_to_talk_records_recognises_and_runs():
    seen, recognizer = Seen(), FakeRecognizer()
    recognizer.model_ready = True
    helper = seen.make(recognizer)
    try:
        helper.press()
        assert recognizer.is_recording and seen.states == [assistant.LISTENING]
        helper.release()
        assert seen.idle.wait(5)
    finally:
        helper.close()
    assert seen.states == [assistant.LISTENING, assistant.PROCESSING,
                           (assistant.HEARD, "pdf'i sıkıştır"), assistant.IDLE]
    assert seen.commands == ["pdf'i sıkıştır"]


def test_silence_is_answered_not_ignored():
    seen, recognizer = Seen(), FakeRecognizer(heard="")
    recognizer.model_ready = True
    helper = seen.make(recognizer)
    try:
        helper.press()
        helper.release()
        assert seen.idle.wait(5)
    finally:
        helper.close()
    assert seen.replies == [_("assist_not_heard")]
    assert seen.commands == []


def test_release_without_a_recording_does_nothing():
    seen = Seen()
    helper = seen.make()
    helper.close()
    helper.release()
    assert seen.states == []


def test_replies_reach_the_ui_until_it_closes():
    seen = Seen()
    helper = seen.make()
    text_speaker.speak("tamam")
    helper.close()
    text_speaker.speak("artık duyulmaz")
    assert seen.replies == ["tamam"]


def test_callbacks_go_through_post():
    posted = []
    helper = assistant.Assistant(post=lambda fn, *args: posted.append(args), on_state=print,
                                 on_reply=print, recognizer=FakeRecognizer(), command=lambda t: None)
    helper.close()
    helper.press()
    assert posted == [(assistant.LOADING, ""), (assistant.IDLE, "")]
