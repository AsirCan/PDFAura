"""Turning exceptions into something a user can act on.

Raw Python text reached the screen for perfectly ordinary situations: a
file open in Word showed a WinError 32 traceback message, and a typo in a
page box showed "invalid literal for int() with base 10: 'abc'".
"""
import errno

from src.core.lang_manager import _

# Exception text that means the input is not a readable PDF.
_BROKEN_PDF_MARKERS = (
    "eof marker not found",
    "cannot read an empty file",
    "stream has ended unexpectedly",
    "invalid pdf header",
    "no /root object",
    "startxref not found",
    "cannot open broken document",
    "failed to open file",
)


def friendly_error(exc):
    """A message worth showing the user for *exc*.

    Messages we raised ourselves already read well and are returned as they
    are; the rest are mapped to a localised explanation.
    """
    from src.core.common import PdfPasswordError
    from src.core.task_manager import CancelledError

    if isinstance(exc, CancelledError):
        return _("perf_cancelled_msg")

    if isinstance(exc, PdfPasswordError):
        return str(exc)

    if isinstance(exc, PermissionError):
        return f"{_('err_no_permission')} {getattr(exc, 'filename', '') or ''}".strip()

    if isinstance(exc, FileNotFoundError):
        # Our own FileNotFoundErrors carry a full explanation already.
        if getattr(exc, "filename", None):
            return f"{_('err_file_missing')} {exc.filename}"
        return str(exc) or _("err_file_missing")

    if isinstance(exc, OSError):
        if exc.errno == errno.ENOSPC:
            return _("err_disk_full")
        # WinError 32: the file is in use by another process.
        if getattr(exc, "winerror", None) in (32, 33):
            return f"{_('err_file_in_use')} {getattr(exc, 'filename', '') or ''}".strip()
        if exc.errno == errno.EACCES:
            return f"{_('err_no_permission')} {getattr(exc, 'filename', '') or ''}".strip()

    if isinstance(exc, ImportError):
        return f"{_('err_missing_dependency')} {exc}"

    text = str(exc)
    lowered = text.lower()

    if any(marker in lowered for marker in _BROKEN_PDF_MARKERS):
        return _("err_broken_pdf")

    # Anything that still reads like a Python internal message.
    if "invalid literal for int()" in lowered or "could not convert string to float" in lowered:
        return f"{_('err_unexpected')} {text}"

    if isinstance(exc, (ValueError, RuntimeError)) and text:
        return text   # raised by us, already readable

    return f"{_('err_unexpected')} {text}" if text else _("err_unexpected")
