"""Locating and running Ghostscript safely.

The Windows Ghostscript installer does not put its binaries on PATH, so we
also look in the registry and under Program Files. Running it goes through
run_ghostscript(), which drains stderr while it waits -- reading the pipe is
what keeps a chatty Ghostscript (lots of "**** Warning" lines on damaged
PDFs) from filling the pipe buffer and deadlocking both processes.
"""
import glob
import os
import shutil
import subprocess
import sys

from src.core.lang_manager import _

GHOSTSCRIPT_EXE = "gswin64c"

# Names to try on PATH, best first.
_EXE_NAMES = ("gswin64c", "gswin32c", "gs")

# Suppress the console window that would otherwise flash up for every call in
# a windowed (PyInstaller --noconsole) build.
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

_cached_path = None


def _from_registry():
    """Read the install path from HKLM\\SOFTWARE\\GPL Ghostscript\\<version>."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None

    found = []
    for root_key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for vendor in (r"SOFTWARE\GPL Ghostscript", r"SOFTWARE\Artifex Ghostscript"):
            # Check both the 64-bit and 32-bit registry views.
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    key = winreg.OpenKey(root_key, vendor, 0, winreg.KEY_READ | view)
                except OSError:
                    continue
                with key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            version = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, version, 0, winreg.KEY_READ | view) as sub:
                                dll = winreg.QueryValueEx(sub, "GS_DLL")[0]
                        except OSError:
                            continue
                        bin_dir = os.path.dirname(dll)
                        for name in _EXE_NAMES:
                            exe = os.path.join(bin_dir, name + ".exe")
                            if os.path.isfile(exe):
                                found.append((_version_key(version), exe))
                                break
    if found:
        return max(found)[1]
    return None


def _from_program_files():
    """Fall back to %ProgramFiles%\\gs\\gs<version>\\bin\\gswin64c.exe."""
    if sys.platform != "win32":
        return None
    found = []
    roots = {os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
             os.environ.get("ProgramW6432")}
    for root in roots:
        if not root:
            continue
        for name in _EXE_NAMES:
            for exe in glob.glob(os.path.join(root, "gs", "gs*", "bin", name + ".exe")):
                version = os.path.basename(os.path.dirname(os.path.dirname(exe)))[2:]
                found.append((_version_key(version), exe))
    if found:
        return max(found)[1]
    return None


def _version_key(version):
    """Sort '10.03.1' above '9.56' numerically rather than as text."""
    parts = []
    for chunk in str(version).split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return parts


def find_ghostscript(refresh=False):
    """Return the full path to a Ghostscript console binary, or None.

    Looks on PATH first, then in the registry, then under Program Files.
    The result is cached; pass refresh=True to look again.
    """
    global _cached_path
    if _cached_path is not None and not refresh:
        return _cached_path

    for name in _EXE_NAMES:
        path = shutil.which(name)
        if path:
            _cached_path = path
            return path

    for finder in (_from_registry, _from_program_files):
        try:
            path = finder()
        except Exception:
            path = None
        if path:
            _cached_path = path
            return path

    return None


def escape_gs_path(path):
    """Escape a path for -sOutputFile=, where % is a format specifier."""
    return str(path).replace("%", "%%")


def _decode(raw):
    """Decode Ghostscript output: UTF-8 first, then the ANSI code page."""
    if not raw:
        return ""
    for encoding in ("utf-8", "mbcs" if sys.platform == "win32" else "latin-1"):
        try:
            return raw.decode(encoding).strip()
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace").strip()


def run_ghostscript(args, ctx=None, on_tick=None):
    """Run Ghostscript with *args* (without the executable) and wait for it.

    stderr is drained by communicate() so Ghostscript can never block on a
    full pipe. While waiting, on_tick() is called roughly every 0.3 s for
    progress reporting, and a cancelled ctx kills the process.

    Raises FileNotFoundError if Ghostscript is missing, RuntimeError if it
    exits non-zero, and CancelledError if ctx was cancelled.
    """
    from src.core.task_manager import CancelledError

    gs_path = find_ghostscript()
    if not gs_path:
        raise FileNotFoundError(_("err_ghostscript_missing"))

    process = subprocess.Popen(
        [gs_path] + list(args),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=CREATE_NO_WINDOW,
    )

    stderr = b""
    try:
        while True:
            try:
                # Keeps the stderr pipe drained; the timeout is what lets us
                # poll for cancellation and report progress meanwhile.
                _stdout, chunk = process.communicate(timeout=0.3)
                stderr += chunk or b""
                break
            except subprocess.TimeoutExpired:
                if ctx is not None and ctx.is_cancelled:
                    raise CancelledError("İşlem kullanıcı tarafından iptal edildi.")
                if on_tick is not None:
                    on_tick()
    except BaseException:
        # Never leave Ghostscript running behind a cancel or a callback error.
        if process.poll() is None:
            process.kill()
            process.communicate()
        raise

    if process.returncode != 0:
        message = _decode(stderr) or _("err_ghostscript_unknown")
        raise RuntimeError(f"{_('err_ghostscript_failed')} {message}")

    return _decode(stderr)
