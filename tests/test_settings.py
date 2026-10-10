"""Issue #18: settings that did nothing, wrong model states, fragile config."""
import json
import os
from pathlib import Path

from src.ai.model_manager import ModelManager
from src.core.config_manager import ConfigManager, cfg, detect_default_language
from src.core.output_paths import default_output_dir, suggest_output


# ── Config file handling (#18.9) ──────────────────────────────────────────

def test_corrupt_config_is_backed_up_not_silently_replaced(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    config_dir = tmp_path / "PDFAura"
    config_dir.mkdir()
    (config_dir / "config.json").write_text("{ this is not json", encoding="utf-8")

    manager = ConfigManager()

    backup = config_dir / "config.json.corrupt"
    assert backup.exists(), "the broken file was thrown away"
    assert backup.read_text(encoding="utf-8") == "{ this is not json"
    # And we carried on with defaults.
    assert manager.get("sound_enabled") is True


def test_config_is_written_atomically(tmp_path, monkeypatch):
    """A crash mid-write must not truncate the settings."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    manager = ConfigManager()
    manager.set("language", "tr")

    written = json.loads((tmp_path / "PDFAura" / "config.json").read_text(encoding="utf-8"))
    assert written["language"] == "tr"
    # No temp files left behind.
    leftovers = [p.name for p in (tmp_path / "PDFAura").iterdir() if p.name.startswith(".config-")]
    assert leftovers == []


def test_valid_config_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    config_dir = tmp_path / "PDFAura"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps({"language": "tr", "sound_enabled": False}), encoding="utf-8")

    manager = ConfigManager()

    assert manager.get("language") == "tr"
    assert manager.get("sound_enabled") is False


def test_default_language_is_a_supported_one():
    """The stored default was "en" while get_text() fell back to "tr"."""
    from src.core.lang_manager import LANGUAGES
    assert detect_default_language() in LANGUAGES


# ── Recent files (#18.1) ──────────────────────────────────────────────────

def test_recent_files_are_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    manager = ConfigManager()
    target = tmp_path / "out.pdf"
    target.write_bytes(b"%PDF")

    manager.add_recent_file(str(target))

    assert manager.get_recent_files() == [str(target)]


def test_recent_files_do_not_duplicate(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    manager = ConfigManager()
    target = tmp_path / "out.pdf"
    target.write_bytes(b"%PDF")

    manager.add_recent_file(str(target))
    manager.add_recent_file(str(target))

    assert len(manager.get_recent_files()) == 1


def test_recent_files_are_capped(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    manager = ConfigManager()
    for i in range(15):
        target = tmp_path / f"f{i}.pdf"
        target.write_bytes(b"%PDF")
        manager.add_recent_file(str(target))

    assert len(manager.get_recent_files()) == ConfigManager.MAX_RECENT_FILES


def test_deleted_files_drop_out_of_the_list(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    manager = ConfigManager()
    target = tmp_path / "gone.pdf"
    target.write_bytes(b"%PDF")
    manager.add_recent_file(str(target))
    target.unlink()

    assert manager.get_recent_files() == []


def test_a_finished_job_is_added_to_the_recent_files(tmp_path, monkeypatch):
    """Every tool finishes through src.app.api, whichever UI started it."""
    from src.app.api import Api
    from src.app.tools import Outcome
    recorded = []
    monkeypatch.setattr(cfg, "add_recent_file", recorded.append)
    target = tmp_path / "out.pdf"
    target.write_bytes(b"%PDF")

    job = Api().start_work(lambda ctx: Outcome("t", "m", str(target)), fail_title="str_error")
    assert job.finished.wait(5)
    failed = Api().start_work(lambda ctx: Outcome("t", "m", str(target), tone="warning"), fail_title="str_error")
    assert failed.finished.wait(5)
    assert recorded == [str(target)]


# ── Default output folder (#18.1) ─────────────────────────────────────────

def test_default_output_dir_is_used_when_set(tmp_path):
    old = cfg.config.get("default_output_dir")
    cfg.config["default_output_dir"] = str(tmp_path)
    try:
        suggested = suggest_output("C:/elsewhere/rapor.pdf", "compressed")
        assert Path(suggested).parent == tmp_path
    finally:
        cfg.config["default_output_dir"] = old


def test_output_sits_next_to_the_input_when_unset():
    old = cfg.config.get("default_output_dir")
    cfg.config["default_output_dir"] = ""
    try:
        suggested = suggest_output(os.path.join("C:/elsewhere", "rapor.pdf"), "compressed")
        assert os.path.dirname(suggested) == "C:/elsewhere"
    finally:
        cfg.config["default_output_dir"] = old


def test_a_missing_default_folder_is_ignored():
    old = cfg.config.get("default_output_dir")
    cfg.config["default_output_dir"] = "Z:/does/not/exist"
    try:
        assert default_output_dir() == ""
    finally:
        cfg.config["default_output_dir"] = old


# ── Completion sound (#18.1) ──────────────────────────────────────────────

def test_beep_is_silent_when_disabled(monkeypatch):
    import src.core.notify as notify
    beeps = []

    class FakeWinsound:
        MB_ICONASTERISK = 1
        MB_ICONHAND = 2

        @staticmethod
        def MessageBeep(kind):
            beeps.append(kind)

    monkeypatch.setitem(__import__("sys").modules, "winsound", FakeWinsound)
    monkeypatch.setattr(notify.sys, "platform", "win32")

    cfg.config["sound_enabled"] = False
    notify.play_success()
    assert beeps == []

    cfg.config["sound_enabled"] = True
    notify.play_success()
    assert beeps == [FakeWinsound.MB_ICONASTERISK]


# ── Model discovery (#18.2, #18.3, #18.4) ─────────────────────────────────

def test_scanner_looks_where_settings_downloads(tmp_path, monkeypatch):
    """The Download button wrote a model the scanner never looked at."""
    from src.core import document_scanner_onnx

    monkeypatch.setenv("APPDATA", str(tmp_path))
    root = ModelManager().model_root
    dirs = [str(p) for p in document_scanner_onnx._candidate_model_dirs()]

    assert str(Path(root) / "vision") in dirs


def test_the_downloaded_model_is_actually_found(tmp_path, monkeypatch):
    from src.core import document_scanner_onnx

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.delenv("PDFAURA_ONNX_MODEL", raising=False)
    vision = Path(ModelManager().model_root) / "vision"
    vision.mkdir(parents=True, exist_ok=True)
    model = vision / "u2netp_document.onnx"
    model.write_bytes(b"fake onnx")

    assert document_scanner_onnx.get_model_path() == str(model)


def test_tesseract_is_looked_for_beyond_path(monkeypatch, tmp_path):
    """Settings checked only PATH while the Advanced tab also checked
    Program Files, so the two screens could disagree."""
    import src.ai.model_manager as model_manager

    program_files = tmp_path / "PF"
    installed = program_files / "Tesseract-OCR" / "tesseract.exe"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b"")

    monkeypatch.setattr(model_manager.shutil, "which", lambda *a, **k: None)
    monkeypatch.setenv("ProgramFiles", str(program_files))

    assert model_manager._find_tesseract() == str(installed)


def test_whisper_is_found_in_the_hugging_face_cache(tmp_path, monkeypatch):
    """faster-whisper caches there, so a working assistant showed "missing"."""
    import src.ai.model_manager as model_manager

    hub = tmp_path / "hub"
    snapshot = hub / "models--Systran--faster-whisper-small" / "snapshots" / "abc"
    snapshot.mkdir(parents=True)
    (snapshot / "model.bin").write_bytes(b"x")

    monkeypatch.setenv("HF_HOME", str(tmp_path))
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)

    found = model_manager._find_whisper_in_hf_cache()
    assert found is not None and found.name == "model.bin"


# ── Settings screen text (#18.5, #18.6) ───────────────────────────────────

def test_settings_does_not_claim_to_have_saved_on_open():
    with open("src/gui/tabs/tab_settings.py", encoding="utf-8") as f:
        source = f.read()
    build_ui = source.split("def _build_general_settings")[0]
    assert '_("settings_saved")' not in build_ui


def test_model_detail_labels_are_translated():
    from src.core.lang_manager import _
    for key in ("model_detail_status", "model_detail_path",
                "model_detail_license", "model_detail_notes"):
        cfg.config["language"] = "tr"
        turkish = _(key)
        cfg.config["language"] = "en"
        english = _(key)
        cfg.config["language"] = "tr"
        assert turkish != english, f"{key} is not translated"
        assert english != key


def test_no_hardcoded_turkish_left_in_the_model_detail_panel():
    with open("src/gui/tabs/tab_settings.py", encoding="utf-8") as f:
        source = f.read()
    for literal in ('f"Durum:', 'f"Yol:', 'f"Lisans:', 'f"Not:', "İndiriliyor:"):
        assert literal not in source, f"{literal} still hardcoded"
