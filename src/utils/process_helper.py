"""Small helpers for running external programs (LibreOffice, the Tesseract
installer) from a windowed build."""
import sys

# Suppress the console window that would otherwise flash up for every call in
# a windowed (PyInstaller --noconsole) build.
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def decode_output(raw):
    """Decode a program's output: UTF-8 first, then the ANSI code page
    (Turkish Windows tools write cp1254)."""
    if not raw:
        return ""
    for encoding in ("utf-8", "mbcs" if sys.platform == "win32" else "latin-1"):
        try:
            return raw.decode(encoding).strip()
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace").strip()
