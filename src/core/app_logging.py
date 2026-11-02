"""Detailed logs and crash reports for the installed application.

A crash used to leave only the final traceback in crash.log, which main.py
wrote after the window was already gone. Nothing recorded what the app was
doing before the crash, and a failure in a worker thread vanished entirely.
This module writes a rotating log under %APPDATA%\\PDFAura\\logs and turns
every uncaught exception (main thread or worker) into a crash report.

Everything is local. Anonymous crash reporting is only an opt-in config flag
and a stub: no build of this module sends anything over the network.
"""
import logging
import logging.handlers
import os
import platform
import sys
import tempfile
import threading
import traceback
from datetime import datetime

APP_NAME = "PDFAura"
LOG_FILE_NAME = "pdfaura.log"
CRASH_DIR_NAME = "crash_reports"

MAX_LOG_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 5

_FORMAT = ("%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s "
           "(%(filename)s:%(lineno)d): %(message)s")
_FORMATTER = logging.Formatter(_FORMAT)

_lock = threading.Lock()
_configured = False
_log_file = None
_crash_directory = None
_original_sys_excepthook = None


def _app_data_dir():
    """%APPDATA%\\PDFAura, or the home directory when APPDATA is not set."""
    base = (os.environ.get("APPDATA") or "").strip() or os.path.expanduser("~")
    return os.path.join(base, APP_NAME)


def log_dir():
    """The folder detailed logs are written to."""
    return os.path.join(_app_data_dir(), "logs")


def crash_report_dir():
    """The folder crash reports are written to."""
    return _crash_directory or os.path.join(_app_data_dir(), CRASH_DIR_NAME)


def log_file_path():
    """The log file setup_logging() is writing to, or None."""
    return _log_file


def _ensure_directory(path):
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except OSError:
        return None


def _remove_our_handlers():
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_pdfaura_handler", False):
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass


def setup_logging(level=logging.INFO, log_directory=None, crash_directory=None,
                  max_bytes=MAX_LOG_BYTES, backup_count=BACKUP_COUNT, force=False):
    """Start rotating file logging and the crash hooks.

    Safe to call more than once; the app calls it at start-up. ``force`` is
    for tests and reconfigures the handlers. Returns the log file path, or
    None when no writable folder was found (logging then goes to stderr).
    """
    global _configured, _log_file, _crash_directory

    with _lock:
        if _configured and not force:
            return _log_file

        if crash_directory is not None:
            _crash_directory = crash_directory

        if force:
            _remove_our_handlers()

        target = _ensure_directory(log_directory or log_dir())
        if target is None:
            # An APPDATA that cannot be written to (a locked-down profile, a
            # stale environment variable) falls back to the home directory.
            target = _ensure_directory(os.path.join(os.path.expanduser("~"), APP_NAME, "logs"))

        root = logging.getLogger()
        root.setLevel(level)

        file_handler = None
        if target is not None:
            path = os.path.join(target, LOG_FILE_NAME)
            try:
                file_handler = logging.handlers.RotatingFileHandler(
                    path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
                file_handler.setFormatter(_FORMATTER)
                file_handler._pdfaura_handler = True
                root.addHandler(file_handler)
                _log_file = path
            except OSError:
                file_handler = None

        if file_handler is None:
            # No log file: keep the log visible on stderr instead of losing it.
            stream = logging.StreamHandler()
            stream.setFormatter(_FORMATTER)
            stream._pdfaura_handler = True
            root.addHandler(stream)
            _log_file = None

        _install_excepthooks()
        _configured = True

        logger = logging.getLogger(__name__)
        logger.info("Logging started (%s); Python %s on %s",
                    _log_file or "stderr only", platform.python_version(), platform.platform())
        logger.info("Working directory: %s", os.getcwd())
        return _log_file


def _install_excepthooks():
    global _original_sys_excepthook

    if sys.excepthook is not handle_exception:
        _original_sys_excepthook = sys.excepthook
    sys.excepthook = handle_exception

    if hasattr(threading, "excepthook"):
        threading.excepthook = handle_thread_exception


def handle_exception(exc_type, exc_value, exc_tb):
    """sys.excepthook: log the exception and keep a crash report."""
    try:
        if exc_type not in (SystemExit, KeyboardInterrupt):
            _report_crash(exc_type, exc_value, exc_tb, threading.current_thread().name)
    except Exception:
        pass   # an exception inside the crash handler must not hide the crash

    previous = _original_sys_excepthook
    if previous and previous is not handle_exception:
        try:
            previous(exc_type, exc_value, exc_tb)
        except Exception:
            pass


def handle_thread_exception(args):
    """threading.excepthook: a worker thread's last exception.

    The traceback goes to the log and the crash report folder; it is not
    printed to stderr a second time.
    """
    try:
        exc_type = args.exc_type
        if exc_type not in (SystemExit, KeyboardInterrupt):
            thread = getattr(args, "thread", None)
            thread_name = getattr(thread, "name", None) or "unknown"
            _report_crash(exc_type, args.exc_value, args.exc_traceback, thread_name)
    except Exception:
        pass


def _report_crash(exc_type, exc_value, exc_tb, thread_name):
    logger = logging.getLogger(__name__)
    logger.critical("Uncaught exception in thread %s", thread_name,
                    exc_info=(exc_type, exc_value, exc_tb))

    details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    path = _write_crash_report(exc_type, exc_value, details, thread_name)
    if path:
        logger.info("Crash report written to %s", path)

    if anonymous_crash_reporting_enabled():
        # Opt-in only. submit_anonymous_report() is a stub that never uses
        # the network; the report stays on this computer.
        logger.info("Anonymous crash reporting is enabled, but this build keeps reports locally.")
        submit_anonymous_report(path)
    return path


def _write_crash_report(exc_type, exc_value, details, thread_name):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    name = f"crash-{stamp}-{os.getpid()}.txt"
    text = (
        "PDF Aura crash report\n"
        f"Time: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
        f"Python: {platform.python_version()}\n"
        f"Platform: {platform.platform()}\n"
        f"Thread: {thread_name}\n"
        f"Exception: {getattr(exc_type, '__name__', str(exc_type))}: {exc_value}\n"
        f"Working directory: {os.getcwd()}\n\n"
        "Traceback:\n"
        f"{details}"
    )

    folders = [crash_report_dir(),
               os.path.join(os.path.expanduser("~"), APP_NAME, CRASH_DIR_NAME),
               os.path.join(tempfile.gettempdir(), APP_NAME, CRASH_DIR_NAME)]
    seen = set()
    for folder in folders:
        key = os.path.normcase(os.path.abspath(folder))
        if key in seen:
            continue
        seen.add(key)
        if _ensure_directory(folder) is None:
            continue
        try:
            path = os.path.join(folder, name)
            with open(path, "w", encoding="utf-8") as report:
                report.write(text)
            return path
        except OSError:
            continue
    return None


def anonymous_crash_reporting_enabled():
    """The opt-in flag; False unless the user turned it on in the config."""
    try:
        from src.core.config_manager import cfg
        return bool(cfg.get("anonymous_crash_reporting", False))
    except Exception:
        return False


def submit_anonymous_report(report_path):
    """Stub for a future opt-in crash reporter. Never touches the network.

    A real implementation would read *report_path* and post it to a server
    only after the user opted in. Keeping the function here gives the UI a
    single place to plug into and documents that this build sends nothing.
    """
    return False
