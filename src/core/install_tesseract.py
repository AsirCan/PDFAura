import base64
import os
import subprocess
import tempfile
import threading

from src.core.lang_manager import _
from src.utils.process_helper import CREATE_NO_WINDOW

# The Turkish pack from tessdata_fast at a fixed commit, checked against the
# size and git blob id GitHub lists for it there. It came from the main
# branch and went straight to its final place: a cut connection left half a
# file there for good (#35).
TUR_COMMIT = "87416418657359cb625c412a48b6e1d6d41c29bd"
TUR_URL = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{TUR_COMMIT}/tur.traineddata"
TUR_SIZE = 4550554
TUR_GIT_SHA1 = "1f0b331ef29f50ceb7c44da58e38c7ec42314d0a"


def _installed_dir():
    """Where Tesseract ended up, or "" if it is not installed."""
    for candidate in (
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Tesseract-OCR"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Tesseract-OCR"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR"),
    ):
        if candidate and os.path.isdir(candidate):
            return candidate
    return ""


def install_target_tesseract(on_success=None, on_error=None):
    """
    Downloads and installs Tesseract silently via winget,
    then downloads the Turkish language pack.
    """
    t = threading.Thread(target=install_tesseract_now, args=(on_success, on_error), daemon=True)
    t.start()


def install_tesseract_now(on_success=None, on_error=None):
    """install_target_tesseract's work, on the calling thread."""
    try:
        # 1. Install via Winget
        result = subprocess.run(
            ["winget", "install", "-e", "--id", "UB-Mannheim.TesseractOCR",
             "--accept-source-agreements", "--accept-package-agreements", "--silent"],
            capture_output=True, text=True,
            creationflags=CREATE_NO_WINDOW,   # no console window in a packaged build
        )

        tess_path = _installed_dir()
        if not tess_path:
            # winget's exit code and output say far more than "the folder
            # is missing", which was the only thing checked before.
            detail = (result.stderr or result.stdout or "").strip()
            message = _("err_tesseract_install_failed").format(code=result.returncode)
            if detail:
                message = message + "\n" + detail[:400]
            if on_error:
                on_error(message)
            return

        # 2. Download Turkish Language Pack
        install_turkish_pack(os.path.join(tess_path, "tessdata"))

        if on_success:
            on_success()

    except Exception as e:
        if on_error:
            on_error(f"{_('err_tesseract_install_error')}\n{e}")


def _pack_is_usable(path):
    """Our pack, or another one at least as big (tessdata_best is larger):
    a smaller file is what a cut download used to leave behind."""
    from src.utils.download import file_matches
    if file_matches(path, TUR_SIZE, git_sha1=TUR_GIT_SHA1):
        return True
    try:
        return os.path.getsize(path) > TUR_SIZE
    except OSError:
        return False


def install_turkish_pack(tessdata_dir):
    """Put tur.traineddata into *tessdata_dir*, asking for administrator
    rights when that folder needs them. Raises if it is not there after."""
    from src.utils.download import download_verified, file_matches
    destination = os.path.join(tessdata_dir, "tur.traineddata")
    if _pack_is_usable(destination):
        return
    try:
        download_verified(TUR_URL, destination, TUR_SIZE, git_sha1=TUR_GIT_SHA1)
        return
    except PermissionError:
        pass    # Program Files needs administrator rights

    staging = tempfile.mkdtemp(prefix="pdfaura-tessdata-")
    staged = os.path.join(staging, "tur.traineddata")
    try:
        download_verified(TUR_URL, staged, TUR_SIZE, git_sha1=TUR_GIT_SHA1)
        _copy_as_administrator(staged, destination)
    finally:
        try:
            os.remove(staged)
            os.rmdir(staging)
        except OSError:
            pass
    # The UAC prompt may have been refused, or the copy may have failed:
    # this used to report success either way.
    if not file_matches(destination, TUR_SIZE, git_sha1=TUR_GIT_SHA1):
        raise RuntimeError(_("err_tesseract_lang_copy").format(folder=tessdata_dir))


def _ps_literal(text):
    """*text* as a single-quoted PowerShell string. PowerShell also takes
    the curly quotes for quote marks, so they are doubled too."""
    for quote in ("'", "\u2018", "\u2019", "\u201a", "\u201b"):
        text = text.replace(quote, quote * 2)
    return f"'{text}'"


def _copy_as_administrator(source, destination):
    """Copy a file with the UAC prompt. The paths go in a script passed as
    -EncodedCommand, never into a command line, where a quote in a user
    name (O'Brien) broke the command."""
    script = (f"$ErrorActionPreference = 'Stop'; "
              f"Copy-Item -LiteralPath {_ps_literal(source)} -Destination {_ps_literal(destination)} -Force")
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    elevate = ("$p = Start-Process powershell -Verb RunAs -Wait -PassThru -WindowStyle Hidden "
               f"-ArgumentList '-NoProfile','-NonInteractive','-EncodedCommand','{encoded}'; exit $p.ExitCode")
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                           "-Command", elevate],
                          capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
