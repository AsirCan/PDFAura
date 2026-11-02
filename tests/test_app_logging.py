"""Priority 7: rotating logs, crash reports and friendly error messages."""

import errno
import glob
import logging
import os
import sys
import threading

import pytest

from src.core import app_logging
from src.core.common import PdfPasswordError
from src.core.config_manager import cfg
from src.core.errors import friendly_error
from src.core.lang_manager import _


@pytest.fixture(autouse=True)
def isolate_logging():
    """Undo the global hooks and handlers a test installs."""
    old_sys_hook = sys.excepthook
    old_thread_hook = threading.excepthook
    old_level = logging.getLogger().level
    app_logging._configured = False
    app_logging._log_file = None
    app_logging._crash_directory = None
    yield
    app_logging._remove_our_handlers()
    sys.excepthook = old_sys_hook
    threading.excepthook = old_thread_hook
    logging.getLogger().setLevel(old_level)
    app_logging._configured = False
    app_logging._log_file = None
    app_logging._crash_directory = None


@pytest.fixture
def turkish():
    old = cfg.config.get("language", "tr")
    cfg.config["language"] = "tr"
    yield
    cfg.config["language"] = old


# ── Rotating log under %APPDATA% ──────────────────────────────────────────

def test_logs_are_written_under_appdata_and_rotate(tmp_path, monkeypatch):
    appdata = tmp_path / "appdata"
    monkeypatch.setenv("APPDATA", str(appdata))

    path = app_logging.setup_logging(max_bytes=400, backup_count=2, force=True)

    assert path == str(appdata / "PDFAura" / "logs" / app_logging.LOG_FILE_NAME)
    startup_files = [path] + glob.glob(path + ".*")
    assert any("Logging started" in open(name, encoding="utf-8").read()
               for name in startup_files)

    logger = logging.getLogger("pdfaura.test")
    for number in range(60):
        logger.info("message %02d %s", number, "x" * 40)

    assert os.path.isfile(path)
    files = [path] + glob.glob(path + ".*")
    assert len(files) > 1, "the log never rotated"
    assert any("message" in open(name, encoding="utf-8").read() for name in files)


def test_unwritable_appdata_falls_back_to_the_home_directory(tmp_path, monkeypatch):
    blocker = tmp_path / "appdata-is-a-file"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(blocker))

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    path = app_logging.setup_logging(force=True)

    assert path is not None
    assert path.startswith(str(home)), path


# ── Crash hooks ───────────────────────────────────────────────────────────

def test_uncaught_exception_is_logged_and_gets_a_crash_report(tmp_path):
    logs, reports = tmp_path / "logs", tmp_path / "crashes"
    log_path = app_logging.setup_logging(
        log_directory=str(logs), crash_directory=str(reports), force=True)

    def boom():
        raise ValueError("özel hata")

    try:
        boom()
    except ValueError:
        sys.excepthook(*sys.exc_info())

    report_files = list(reports.glob("crash-*.txt"))
    assert len(report_files) == 1
    report = report_files[0].read_text(encoding="utf-8")
    assert "ValueError: özel hata" in report
    assert "Traceback:" in report
    assert "Thread:" in report

    log = open(log_path, encoding="utf-8").read()
    assert "Uncaught exception in thread" in log
    assert "ValueError: özel hata" in log
    assert "Traceback" in log


def test_worker_thread_exception_is_reported(tmp_path):
    logs, reports = tmp_path / "logs", tmp_path / "crashes"
    log_path = app_logging.setup_logging(
        log_directory=str(logs), crash_directory=str(reports), force=True)

    thread = threading.Thread(target=lambda: None, name="worker-1")
    try:
        raise RuntimeError("worker patladı")
    except RuntimeError:
        args = threading.ExceptHookArgs([*sys.exc_info(), thread])

    threading.excepthook(args)

    report_files = list(reports.glob("crash-*.txt"))
    assert len(report_files) == 1
    report = report_files[0].read_text(encoding="utf-8")
    assert "Thread: worker-1" in report
    assert "RuntimeError: worker patladı" in report

    log = open(log_path, encoding="utf-8").read()
    assert "Uncaught exception in thread worker-1" in log


def test_anonymous_reporting_is_off_by_default_and_a_local_stub(tmp_path):
    old = cfg.config.get("anonymous_crash_reporting")
    cfg.config["anonymous_crash_reporting"] = False
    try:
        assert cfg.default_config["anonymous_crash_reporting"] is False
        assert app_logging.anonymous_crash_reporting_enabled() is False
        assert app_logging.submit_anonymous_report(str(tmp_path / "report.txt")) is False
    finally:
        if old is None:
            cfg.config.pop("anonymous_crash_reporting", None)
        else:
            cfg.config["anonymous_crash_reporting"] = old


def test_logging_degrades_gracefully_when_no_folder_is_writable(tmp_path, monkeypatch):
    """A completely locked-down profile still gets hooks, never a crash."""
    blocker = tmp_path / "blocked"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(blocker))
    monkeypatch.setenv("HOME", str(blocker))
    monkeypatch.setenv("USERPROFILE", str(blocker))
    monkeypatch.setattr(app_logging.tempfile, "gettempdir", lambda: str(blocker))

    assert app_logging.setup_logging(force=True) is None
    assert sys.excepthook is app_logging.handle_exception


# ── Friendly error messages ───────────────────────────────────────────────

def test_encrypted_pdf_is_explained(turkish):
    expected = _("err_pdf_password_protected")
    assert friendly_error(PdfPasswordError()) == expected
    assert friendly_error(Exception("File has not been decrypted")) == expected
    assert "parola" in expected.lower()

    assert friendly_error(Exception("incorrect password")) == _("err_wrong_password")


def test_corrupted_pdf_is_explained(turkish):
    expected = _("err_broken_pdf")
    assert friendly_error(Exception("Invalid PDF header")) == expected
    assert friendly_error(Exception("xref table is broken")) == expected
    assert friendly_error(Exception("stream has ended unexpectedly")) == expected


def test_file_not_found_keeps_the_path(turkish):
    exc = FileNotFoundError(2, "No such file or directory", "C:/yok/rapor.pdf")
    message = friendly_error(exc)
    assert message.startswith(_("err_file_missing"))
    assert "rapor.pdf" in message
    assert "No such file" not in message


def test_permission_denied_keeps_the_path(turkish):
    exc = PermissionError(errno.EACCES, "Permission denied", "C:/Windows/out.pdf")
    message = friendly_error(exc)
    assert message.startswith(_("err_no_permission"))
    assert "out.pdf" in message
    assert "Permission denied" not in message


def test_windows_access_denied_without_errno_is_explained(turkish):
    exc = OSError(0, "Access is denied")
    exc.winerror = 5
    exc.filename = "C:/Program Files/PDFAura/out.pdf"
    assert _("err_no_permission") in friendly_error(exc)


def test_disk_full_is_explained(turkish):
    exc = OSError(errno.ENOSPC, "No space left on device")
    assert friendly_error(exc) == _("err_disk_full")

    windows = OSError(0, "There is not enough space on the disk")
    windows.winerror = 112
    assert friendly_error(windows) == _("err_disk_full")


def test_missing_optional_dependency_names_the_pip_package(turkish):
    message = friendly_error(ImportError("No module named 'cv2'"))
    assert _("err_missing_dependency") in message
    assert "opencv-python" in message
    assert "pip install opencv-python" in message
    assert "No module named" not in message

    assert "pywin32" in friendly_error(ImportError("No module named 'win32com'"))
