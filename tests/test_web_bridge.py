"""#25 Faz 2: what the web page can call (src/app/bridge.py), without a window.

The shell is a stand-in that records events; tools really run.
"""
import os
import threading

import pytest

from conftest import make_pdf
from src.app import bridge as bridge_module
from src.app.bridge import Bridge, JobEvents, file_info
from src.app.images import ImageCache, PdfPages
from src.core.config_manager import cfg
from src.core.lang_manager import _


class Shell:
    """What Bridge needs from window.py."""

    def __init__(self):
        self.token = "tok"
        self.version = "2.1"
        self.images = ImageCache()
        self.pages = PdfPages()
        self.events = self
        self.sent = []
        self.ready_called = False
        self.title_bars = []
        self.languages = 0
        self.quit_called = False
        self._done = threading.Event()

    # EventBus
    def emit(self, name, data=None):
        self.sent.append((name, data))
        if name == "job" and data["type"] in ("done", "failed", "cancelled"):
            self._done.set()

    def ready(self):
        self.ready_called = True

    def wait_job(self):
        assert self._done.wait(10), "the job never finished"
        return [data for name, data in self.sent if name == "job"]

    # window
    def style_title_bar(self, name):
        self.title_bars.append(name)

    def language_changed(self):
        self.languages += 1

    def quit(self):
        self.quit_called = True


@pytest.fixture
def shell():
    return Shell()


@pytest.fixture
def bridge(shell):
    return Bridge(shell)


@pytest.fixture(autouse=True)
def keep_config():
    keys = ("language", "theme", "close_to_tray", "sound_enabled", "default_output_dir", "recent_files")
    saved = {key: cfg.config.get(key) for key in keys}
    cfg.config["sound_enabled"] = False
    yield
    cfg.config.update(saved)


# ── Start-up, language, theme ─────────────────────────────────────────────

def test_boot_has_everything_the_page_draws_with(bridge, shell):
    boot = bridge.boot()
    assert shell.ready_called, "events must flow once the page has booted"
    assert boot["language"] == "tr" and boot["rtl"] is False
    assert boot["strings"]["txt_compress"] == "Sıkıştır"
    assert ["en", "English"] in boot["languages"]
    assert boot["theme"] in ("system", "paper", "night")
    assert set(boot["settings"]) == {"close_to_tray", "sound_enabled", "default_output_dir"}
    assert boot["token"] == "tok"


def test_language_changes_at_once_without_tk_direction_marks(bridge, shell):
    payload = bridge.set_language("ar")
    assert payload["rtl"] is True and cfg.get("language") == "ar"
    assert shell.languages == 1, "the tray menu follows the language"
    assert not any("‫" in text or "‬" in text for text in payload["strings"].values())
    # A key Arabic lacks still comes, in English.
    assert payload["strings"]["suffix_compressed"] == "_compressed"


def test_unknown_language_or_theme_is_refused(bridge):
    with pytest.raises(ValueError):
        bridge.set_language("xx")
    with pytest.raises(ValueError):
        bridge.set_theme("neon")


def test_theme_is_saved_and_the_title_bar_follows_what_is_shown(bridge, shell):
    assert bridge.set_theme("night") == "night" and cfg.get("theme") == "night"
    bridge.theme_shown("night")
    bridge.theme_shown("system")         # not a theme the page can show
    assert shell.title_bars == ["night"]


def test_settings_are_saved_and_a_missing_folder_is_refused(bridge, tmp_path):
    saved = bridge.save_settings({"close_to_tray": False, "sound_enabled": True,
                                  "default_output_dir": str(tmp_path)})
    assert saved == {"close_to_tray": False, "sound_enabled": True, "default_output_dir": str(tmp_path)}
    with pytest.raises(ValueError):
        bridge.save_settings({"default_output_dir": str(tmp_path / "nope")})


# ── Files ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name, kind", [("a.pdf", "pdf"), ("b.JPG", "image"), ("c.docx", "word"),
                                         ("d.pptx", "powerpoint"), ("e.xlsx", "excel"), ("f.zip", "other")])
def test_file_info_names_the_kind(tmp_path, name, kind):
    path = tmp_path / name
    path.write_bytes(b"x")
    info = file_info(str(path))
    assert info["kind"] == kind and info["exists"] and info["size"] == 1 and info["name"] == name


def test_a_folder_is_a_folder(tmp_path):
    assert file_info(str(tmp_path))["kind"] == "folder"


def test_paths_that_do_not_exist_are_not_opened(bridge, tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(os, "startfile", opened.append, raising=False)
    assert bridge.open_path(str(tmp_path / "gone.pdf")) is False
    assert bridge.reveal_path("") is False
    assert opened == []


# ── Tools ─────────────────────────────────────────────────────────────────

def test_a_bad_input_comes_back_as_a_problem_not_a_job(bridge, shell):
    started = bridge.start("compress", {"input": "", "output": "x.pdf", "quality": "ebook"})
    assert started == {"problem": _("err_select_valid_pdf")}
    assert [name for name, _data in shell.sent if name == "job"] == []


def test_a_tool_runs_and_reports_through_events(bridge, shell, tmp_path):
    source = make_pdf(tmp_path / "a.pdf", pages=4)
    target = str(tmp_path / "b.pdf")
    started = bridge.start("split", {"input": source, "output": target, "start": "2", "end": "3"})
    assert started["cancellable"] is True and started["busy"]
    events = shell.wait_job()
    assert all(event["id"] == started["job"] for event in events)
    done = events[-1]
    assert done["type"] == "done" and done["outcome"]["output"] == target and os.path.isfile(target)
    assert done["outcome"]["tone"] == "success"


def test_a_failing_tool_reports_failed(bridge, shell, tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf")
    bridge.start("split", {"input": str(broken), "output": str(tmp_path / "o.pdf"), "start": "1", "end": "1"})
    event = shell.wait_job()[-1]
    assert event["type"] == "failed" and event["title"] == _("split_fail") and event["message"]


def test_suggestions_and_existing_targets_come_from_the_app_layer(bridge, tmp_path):
    source = make_pdf(tmp_path / "rapor.pdf")
    assert bridge.suggest_output("compress", source).endswith("rapor_sikistirilmis.pdf")
    existing = make_pdf(tmp_path / "var.pdf")
    assert bridge.existing_target("compress", {"input": source, "output": existing, "quality": "ebook"}) == existing


def test_job_events_wait_for_the_job_id():
    """A fast job can report before start() returns its Job."""
    sent = []
    events = JobEvents(lambda name, data: sent.append(data), sounds=False)
    reporter = threading.Thread(target=events.callbacks()["on_cancelled"])
    reporter.start()

    class Job:
        id = 7
    events.bind(Job())
    reporter.join(5)
    assert sent == [{"id": 7, "type": "cancelled"}]


# ── Preview ───────────────────────────────────────────────────────────────

def test_a_pdf_document_gets_an_id_and_page_urls(bridge, tmp_path):
    source = make_pdf(tmp_path / "a.pdf", pages=3)
    doc = bridge.document(source)
    assert doc["pages"] == 3 and doc["width"] == 595 and not doc["encrypted"]
    assert doc["base"] == f"/pdf/tok/{doc['id']}/"
    assert source not in doc["base"]


def test_not_a_pdf_is_said_plainly(bridge, tmp_path):
    other = tmp_path / "a.txt"
    other.write_text("x")
    assert bridge.document(str(other))["error"] == "not-a-pdf"
    assert bridge.document(str(tmp_path / "gone.pdf"))["error"] == "not-a-pdf"


def test_an_unreadable_pdf_reports_why(bridge, tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4 not really")
    doc = bridge.document(str(broken))
    assert doc["error"] and doc["error"] != "not-a-pdf"


# ── Assistant and models ──────────────────────────────────────────────────

def test_assistant_replies_become_events(bridge, shell, monkeypatch):
    from src.ai import text_speaker
    from src.app import assistant
    monkeypatch.setattr(text_speaker.speaker, "speak", lambda text: None)
    monkeypatch.setattr(assistant, "run_command", lambda text: text_speaker.speak(f"ok {text}"))
    helper = bridge._helper()
    helper._command = assistant.run_command
    try:
        assert bridge.assistant_submit("rapor.pdf sıkıştır")
        for _ in range(100):
            if ("assistant", {"state": "idle", "detail": ""}) in shell.sent:
                break
            threading.Event().wait(0.05)
    finally:
        helper.close()
    assert ("assistant-reply", {"text": "ok rapor.pdf sıkıştır"}) in shell.sent
    assert ("assistant", {"state": "processing", "detail": ""}) in shell.sent


def test_a_model_without_a_download_opens_its_page_instead(bridge, monkeypatch):
    opened = []
    import webbrowser
    monkeypatch.setattr(webbrowser, "open", opened.append)
    result = bridge.models_download("ocr_engine")
    assert "job" not in result and opened == [result["source_url"]]


def test_the_page_can_quit(bridge, shell):
    bridge.quit()
    assert shell.quit_called


# ── What pywebview exposes ────────────────────────────────────────────────

def test_only_plain_methods_are_exposed():
    """pywebview also exposes the methods of public attributes; the bridge
    keeps every attribute private."""
    instance = Bridge(Shell())
    public = [name for name in vars(instance) if not name.startswith("_")]
    assert public == []


def test_bridge_has_no_way_to_run_code_or_commands():
    names = {name for name in dir(Bridge) if not name.startswith("_")}
    assert not names & {"eval", "exec", "run", "shell", "command", "system", "evaluate"}
    assert bridge_module.subprocess.Popen  # used only for "explorer /select"


def test_the_web_window_does_not_load_tk_or_heavy_libraries():
    """--web must not pay for Tk, and like the Tk window it loads tool
    libraries only when a tool runs."""
    import site
    import subprocess
    import sys
    from conftest import ROOT
    heavy = ("tkinter", "cv2", "numpy", "pypdf", "fitz", "pytesseract", "sounddevice", "faster_whisper", "pystray")
    code = ("import sys; import src.app.window; "
            f"print(' '.join(m for m in {heavy!r} if m in sys.modules))")
    env = dict(os.environ, PYTHONUSERBASE=site.getuserbase())
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, env=env,
                         timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == []
