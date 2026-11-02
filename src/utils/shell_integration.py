"""Per-user Windows Explorer entries for PDF files.

Explorer reads file-type verbs from

    HKCU\\Software\\Classes\\SystemFileAssociations\\.pdf\\shell

so the three actions below are registered for the current user only and never
need administrator rights. Each verb runs the same ``src.cli`` commands the
terminal uses, which keeps the context menu and the command line on one code
path:

    PDF Aura ile Sıkıştır   -> pdfaura compress "%1" -q ebook
    PDF Aura ile Kes        -> pdfaura split "%1" --pages 1-1
    PDF Aura ile Birleştir  -> pdfaura merge %*

``%*`` hands every selected file to one process, which is what makes
"Birleştir" work on a multi-selection. A context menu cannot ask for a page
range, so "Kes" extracts the first page by default; pass ``split_pages`` to
register another range (for example ``"1-10"``).

Frozen builds have no argument dispatcher yet. The one-line change main.py
needs is::

    if len(sys.argv) > 1:
        from src.cli import main as cli_main; sys.exit(cli_main())

The source checkout builds commands with ``python -m src.cli``, so nothing
else is required while developing or running from source.

``winreg`` is imported lazily: this module still imports on non-Windows
machines, where every function simply reports that nothing was registered.
"""
import re
import sys
from dataclasses import dataclass

SHELL_KEY = r"Software\Classes\SystemFileAssociations\.pdf\shell"

# A context menu has nowhere to type a page range. The first page is a safe,
# predictable default; callers that know a better range pass split_pages.
DEFAULT_SPLIT_PAGES = "1-1"

_PAGES = re.compile(r"^\s*\d+\s*-\s*\d+\s*$")


@dataclass(frozen=True)
class MenuEntry:
    """One Explorer verb: its registry key, label and CLI arguments."""

    key: str
    label: str
    arguments: str          # %1 is the clicked file, %* every selected file
    multi_select: bool = False


MENU_ENTRIES = (
    MenuEntry("PDFAura.Compress", "PDF Aura ile Sıkıştır",
              'compress "%1" -q ebook'),
    MenuEntry("PDFAura.Split", "PDF Aura ile Kes",
              'split "%1" --pages {pages}'),
    MenuEntry("PDFAura.Merge", "PDF Aura ile Birleştir",
              "merge %*", multi_select=True),
)


def _winreg_module():
    """The winreg module, or None on a platform without a registry."""
    try:
        import winreg
    except ImportError:
        return None
    return winreg


def _quote(value):
    """Quote one Windows command line argument."""
    return '"' + str(value).replace('"', r'\"') + '"'


def _command_prefix(exe=None):
    """What runs the CLI: the app itself when frozen, else this interpreter.

    A caller may pass the installed PDFAura.exe explicitly (the Settings
    toggle and the installer do); running from source without one uses
    ``python -m src.cli`` so the menu works in a developer checkout too.
    """
    if exe:
        clean_exe = str(exe).replace("\r", "").replace("\n", "").strip()
        return _quote(clean_exe)
    if getattr(sys, "frozen", False):
        return _quote(sys.executable)
    return f"{_quote(sys.executable)} -m src.cli"


def build_command(entry, exe=None, split_pages=DEFAULT_SPLIT_PAGES):
    """The full command line Explorer runs for ``entry``."""
    arguments = entry.arguments
    if "{pages}" in arguments:
        pages = split_pages if _PAGES.match(str(split_pages)) else DEFAULT_SPLIT_PAGES
        arguments = arguments.format(pages=pages.strip())
    return f"{_command_prefix(exe)} {arguments}"


def _verb_path(entry):
    return rf"{SHELL_KEY}\{entry.key}"


def _icon(exe):
    return f"{exe or sys.executable},0"


def register_context_menu(exe=None, split_pages=DEFAULT_SPLIT_PAGES):
    """Add/refresh the three verbs for the current user.

    Returns True when the entries were written, False when the platform has
    no registry or Windows refused the write (a locked-down profile). The
    caller may show that as a warning; it is never an error worth crashing
    the window over.
    """
    winreg = _winreg_module()
    if winreg is None:
        return False

    try:
        for entry in MENU_ENTRIES:
            path = _verb_path(entry)
            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0,
                                     winreg.KEY_WRITE)
            try:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, entry.label)
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, _icon(exe))
                if entry.multi_select:
                    # Without this Explorer only offers the verb to one file.
                    winreg.SetValueEx(key, "MultiSelectModel", 0, winreg.REG_SZ,
                                      "Player")
                command = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                                             rf"{path}\command", 0,
                                             winreg.KEY_WRITE)
                try:
                    winreg.SetValueEx(command, "", 0, winreg.REG_SZ,
                                      build_command(entry, exe, split_pages))
                finally:
                    winreg.CloseKey(command)
            finally:
                winreg.CloseKey(key)
        return True
    except OSError:
        return False


def unregister_context_menu():
    """Remove the three verbs (and their commands) for the current user.

    Idempotent: a verb that is already gone is not an error, so uninstalling
    or toggling the setting twice is harmless.
    """
    winreg = _winreg_module()
    if winreg is None:
        return False

    removed = True
    for entry in MENU_ENTRIES:
        try:
            _delete_tree(winreg, _verb_path(entry))
        except OSError:
            removed = False

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, SHELL_KEY, 0,
                             winreg.KEY_READ)
        try:
            has_subkeys = True
            try:
                winreg.EnumKey(key, 0)
            except OSError:
                has_subkeys = False
        finally:
            winreg.CloseKey(key)

        if not has_subkeys:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, SHELL_KEY)
    except OSError:
        pass

    return removed


def _delete_tree(winreg, path):
    """Delete ``path`` and everything below it; a missing key is fine."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ)
    except FileNotFoundError:
        return
    except OSError:
        raise

    try:
        children = []
        index = 0
        while True:
            try:
                children.append(winreg.EnumKey(key, index))
            except OSError:
                break                 # no more subkeys
            index += 1
    finally:
        winreg.CloseKey(key)

    for child in children:
        _delete_tree(winreg, rf"{path}\{child}")
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)


def context_menu_registered():
    """True when all three verbs are present (used by the Settings toggle)."""
    winreg = _winreg_module()
    if winreg is None:
        return False

    try:
        for entry in MENU_ENTRIES:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _verb_path(entry), 0,
                                 winreg.KEY_READ)
            winreg.CloseKey(key)
        return True
    except OSError:
        return False
