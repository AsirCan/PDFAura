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
    "not a pdf",
    "invalid pdf",
    "malformed pdf",
    "pdf is damaged",
    "pdf is corrupted",
    "truncated",
    "xref",
    "trailer not found",
    "object not defined",
)

# A password protected PDF, whether we raised it or pypdf/pikepdf did.
_ENCRYPTED_MARKERS = (
    "file has not been decrypted",
    "not been decrypted",
    "password required",
    "password is required",
    "encrypted pdf",
    "closed or encrypted",
    "needs a password",
)

_WRONG_PASSWORD_MARKERS = (
    "incorrect password",
    "invalid password",
    "wrong password",
)

_ENCRYPTED_TYPES = ("PdfPasswordError", "FileNotDecryptedError", "PasswordError")

# Import name -> the pip package a user can install.
_PIP_NAMES = {
    "cv2": "opencv-python",
    "fitz": "PyMuPDF",
    "PIL": "Pillow",
    "docx": "python-docx",
    "pptx": "python-pptx",
    "win32com": "pywin32",
    "win32": "pywin32",
    "pythoncom": "pywin32",
    "pywintypes": "pywin32",
    "webview": "pywebview",
    "speech_recognition": "SpeechRecognition",
}


def _missing_package(exc):
    """The pip package name behind an ImportError, or "" when unknown."""
    text = str(exc)
    marker = "no module named"
    lowered = text.lower()
    if marker not in lowered:
        return ""
    name = text[lowered.index(marker) + len(marker):].strip(" '\"")
    name = name.split("'")[0].split('"')[0].strip()
    top_level = name.split(".")[0]
    return _PIP_NAMES.get(top_level, top_level)


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
        return str(exc) or _("err_pdf_password_protected")

    text = str(exc)
    lowered = text.lower()

    if any(marker in lowered for marker in _WRONG_PASSWORD_MARKERS):
        return _("err_wrong_password")

    if type(exc).__name__ in _ENCRYPTED_TYPES or any(
            marker in lowered for marker in _ENCRYPTED_MARKERS):
        return _("err_pdf_password_protected")

    if isinstance(exc, PermissionError):
        return f"{_('err_no_permission')} {getattr(exc, 'filename', '') or ''}".strip()

    if isinstance(exc, FileNotFoundError):
        # Our own FileNotFoundErrors carry a full explanation already.
        if getattr(exc, "filename", None):
            return f"{_('err_file_missing')} {exc.filename}"
        if text and not lowered.startswith("[errno"):
            return text
        return _("err_file_missing")

    if isinstance(exc, OSError):
        # ERROR_DISK_FULL / ERROR_HANDLE_DISK_FULL on Windows.
        if exc.errno == errno.ENOSPC or getattr(exc, "winerror", None) in (39, 112):
            return _("err_disk_full")
        # WinError 32: the file is in use by another process.
        if getattr(exc, "winerror", None) in (32, 33):
            return f"{_('err_file_in_use')} {getattr(exc, 'filename', '') or ''}".strip()
        if exc.errno == errno.EACCES or getattr(exc, "winerror", None) == 5:
            return f"{_('err_no_permission')} {getattr(exc, 'filename', '') or ''}".strip()

    if isinstance(exc, ImportError):
        package = _missing_package(exc)
        if package:
            return f"{_('err_missing_dependency')} {package} (pip install {package})"
        return f"{_('err_missing_dependency')} {text}"

    if any(marker in lowered for marker in _BROKEN_PDF_MARKERS) or \
            type(exc).__name__ in ("PdfReadError", "PdfStreamError"):
        return _("err_broken_pdf")

    # Anything that still reads like a Python internal message.
    if "invalid literal for int()" in lowered or "could not convert string to float" in lowered:
        return f"{_('err_unexpected')} {text}"

    if isinstance(exc, (ValueError, RuntimeError)) and text:
        return text   # raised by us, already readable

    return f"{_('err_unexpected')} {text}" if text else _("err_unexpected")
