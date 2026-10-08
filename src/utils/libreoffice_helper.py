"""Converting Office documents to PDF with LibreOffice.

Word/PowerPoint/Excel to PDF used to need Microsoft Office and simply failed
without it, even on machines with LibreOffice installed. This is the
fallback: soffice --headless --convert-to pdf.

Each run gets its own throwaway LibreOffice profile. Without that, a
LibreOffice window the user already has open receives the job instead, and
soffice returns at once without having written anything.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from src.core.lang_manager import _
from src.utils.process_helper import CREATE_NO_WINDOW, decode_output

# A deck with hundreds of slides takes a minute or two; a hang takes forever.
LIBREOFFICE_TIMEOUT_S = 600

_REGISTRY_KEY = r"SOFTWARE\LibreOffice\UNO\InstallPath"


def _from_registry():
    """Read the program folder from HKLM\\SOFTWARE\\LibreOffice\\UNO\\InstallPath."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None

    for root_key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(root_key, _REGISTRY_KEY, 0, winreg.KEY_READ | view) as key:
                    folder = winreg.QueryValueEx(key, "")[0]
            except OSError:
                continue
            exe = os.path.join(folder, "soffice.exe")
            if os.path.isfile(exe):
                return exe
    return None


def _from_program_files():
    if sys.platform != "win32":
        return None
    roots = (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"),
             os.environ.get("ProgramFiles(x86)"))
    for root in roots:
        if not root:
            continue
        exe = os.path.join(root, "LibreOffice", "program", "soffice.exe")
        if os.path.isfile(exe):
            return exe
    return None


def find_libreoffice():
    """Return the full path to LibreOffice's soffice, or None."""
    for finder in (_from_registry, _from_program_files):
        try:
            path = finder()
        except Exception:
            path = None
        if path:
            return path
    return shutil.which("soffice")


def _kill_tree(process):
    """soffice.exe is a launcher; the work happens in its soffice.bin child."""
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=CREATE_NO_WINDOW)
    if process.poll() is None:
        process.kill()
    process.communicate()


def libreoffice_to_pdf(soffice, input_path, output_pdf, ctx=None):
    """Convert *input_path* to *output_pdf* with LibreOffice and wait for it.

    The input is copied into a private folder first: LibreOffice names its
    output after the input, leaves a lock file next to what it opens, and
    this way neither touches the user's folder. The result reaches
    *output_pdf* through atomic_output, so a failure leaves any previous
    file there intact.

    Raises RuntimeError if LibreOffice fails or times out, CancelledError if
    ctx was cancelled.
    """
    import time

    from src.core.output_paths import atomic_output
    from src.core.task_manager import CancelledError

    with tempfile.TemporaryDirectory(prefix="pdfaura-lo-", ignore_cleanup_errors=True) as work:
        source = os.path.join(work, "input" + os.path.splitext(input_path)[1].lower())
        shutil.copyfile(input_path, source)
        out_dir = os.path.join(work, "out")
        os.makedirs(out_dir)

        command = [
            soffice,
            "-env:UserInstallation=" + Path(work, "profile").as_uri(),
            "--headless", "--norestore", "--nolockcheck", "--nodefault",
            "--convert-to", "pdf", "--outdir", out_dir, source,
        ]
        # Our PYTHONHOME would point LibreOffice's bundled Python at ours.
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONHOME", "PYTHONPATH")}
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, env=env,
                                   creationflags=CREATE_NO_WINDOW)

        deadline = time.monotonic() + LIBREOFFICE_TIMEOUT_S
        output = b""
        try:
            while True:
                try:
                    chunk, _stderr = process.communicate(timeout=0.3)
                    output += chunk or b""
                    break
                except subprocess.TimeoutExpired:
                    if ctx is not None and ctx.is_cancelled:
                        raise CancelledError("cancelled")
                    if time.monotonic() > deadline:
                        raise RuntimeError(_("err_libreoffice_timeout").format(
                            seconds=LIBREOFFICE_TIMEOUT_S))
        except BaseException:
            _kill_tree(process)
            raise

        produced = os.path.join(out_dir, "input.pdf")
        if process.returncode != 0 or not os.path.isfile(produced) \
                or os.path.getsize(produced) == 0:
            detail = decode_output(output) or f"exit code {process.returncode}"
            raise RuntimeError(f"{_('err_libreoffice_failed')} {detail}")

        with atomic_output(output_pdf) as temp_path:
            shutil.copyfile(produced, temp_path)
