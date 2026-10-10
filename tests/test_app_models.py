"""#25: Settings' local AI models through src/app/models.py, without a window."""
import io
import threading
import urllib.request

import pytest

from src.ai import model_manager
from src.app.models import Models
from src.core.task_manager import CancelledError


@pytest.fixture(autouse=True)
def no_bundled_models(tmp_path_factory, monkeypatch):
    """Look only in the test's folder, not in this checkout's models/."""
    empty = tmp_path_factory.mktemp("app")
    monkeypatch.setattr(model_manager.ModelManager, "app_root", staticmethod(lambda: empty))


class Done:
    def __init__(self):
        self.event = threading.Event()
        self.result = None
        self.progress = []

    def __call__(self, *args):
        self.result = args
        self.event.set()

    def wait(self):
        assert self.event.wait(5), "the job never reported back"
        return self.result


def test_rows_describe_every_model(tmp_path):
    rows = {row.id: row for row in Models(root=str(tmp_path)).rows()}
    assert set(rows) == {"scanner_u2netp", "ocr_engine", "speech_whisper"}
    vision = rows["scanner_u2netp"]
    assert vision.downloadable and vision.size == "~5 MB"


def test_an_installed_model_shows_its_real_size(tmp_path):
    (tmp_path / "vision").mkdir()
    (tmp_path / "vision" / "u2netp_document.onnx").write_bytes(b"x" * 1024 * 1024 * 2)
    row = Models(root=str(tmp_path)).row("scanner_u2netp")
    assert row.installed and row.size == "2.0 MB"


def test_a_model_without_a_direct_download_is_not_started(tmp_path):
    assert Models(root=str(tmp_path)).download("ocr_engine") is None


def test_a_download_reports_progress_then_the_file(tmp_path, monkeypatch):
    def fake_download(self, model_id, progress=None):
        for done in (1, 2, 4):
            progress(done, 4)
        path = tmp_path / "vision" / "u2netp_document.onnx"
        path.write_bytes(b"onnx")
        return path
    monkeypatch.setattr(model_manager.ModelManager, "download_model", fake_download)
    done, progress = Done(), []
    Models(root=str(tmp_path)).download("scanner_u2netp", on_progress=lambda *a: progress.append(a),
                                        on_done=done)
    (outcome,) = done.wait()
    assert outcome.output_path.endswith("u2netp_document.onnx")
    assert progress[-1] == (4, 4, "")


def test_a_failed_download_says_why(tmp_path, monkeypatch):
    def fake_download(self, model_id, progress=None):
        raise model_manager.ModelDownloadError("HTTP 404")
    monkeypatch.setattr(model_manager.ModelManager, "download_model", fake_download)
    failed = Done()
    Models(root=str(tmp_path)).download("scanner_u2netp", on_failed=failed)
    title, message = failed.wait()
    assert "HTTP 404" in message


def test_a_cancelled_download_is_a_cancel_and_leaves_no_part_file(tmp_path, monkeypatch):
    """The manager wrapped every error, a cancel too, as a failed download."""
    class Response(io.BytesIO):
        headers = {"Content-Length": str(1024 * 512)}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Response(b"x" * 1024 * 512))
    manager = model_manager.ModelManager(str(tmp_path))

    def cancel(done, total):
        raise CancelledError()
    with pytest.raises(CancelledError):
        manager.download_model("scanner_u2netp", progress=cancel)
    assert list((tmp_path / "vision").glob("*.part")) == []


def test_testing_a_model_answers_ok_and_why(tmp_path):
    (tmp_path / "vision").mkdir()
    (tmp_path / "vision" / "u2netp_document.onnx").write_bytes(b"onnx")
    done = Done()
    Models(root=str(tmp_path)).test("scanner_u2netp", on_done=done)
    ok, message = done.wait()
    assert ok and "u2netp_document.onnx" in message


def test_testing_a_missing_model_says_it_is_missing(tmp_path):
    done = Done()
    Models(root=str(tmp_path)).test("scanner_u2netp", on_done=done)
    ok, _message = done.wait()
    assert ok is False


def test_a_new_root_is_used_without_being_saved(tmp_path):
    from src.core.config_manager import cfg
    before = cfg.get("ai_model_root", "")
    models = Models(root=str(tmp_path / "a"))
    models.use_root(str(tmp_path / "b"))
    assert models.root.endswith("b") and cfg.get("ai_model_root", "") == before
