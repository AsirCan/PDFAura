"""Per-user Explorer context menu: registry writes, commands and installer.

``winreg`` is replaced by an in-memory registry so these tests run anywhere
and never touch the machine's real PDF verbs.
"""
import os
import sys

import pytest

from conftest import ROOT
from src.utils import shell_integration as shell

EXE = r"C:\Program Files\PDF Aura\PDFAura.exe"
MERGE_EXE = r"C:\Users\Ayse\AppData\Local\Programs\PDF Aura\PDFAura.exe"


class _Key:
    """A registry key handle; the path is all the fake needs."""

    def __init__(self, registry, path):
        self.registry = registry
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeRegistry:
    """The small part of winreg the module uses, backed by a dict."""

    HKEY_CURRENT_USER = "HKCU"
    KEY_READ = 0x20019
    KEY_WRITE = 0x20006
    REG_SZ = 1

    def __init__(self):
        self.values = {}          # path -> {value name: value}

    def _ensure(self, path):
        parts = path.split("\\")
        for i in range(1, len(parts) + 1):
            self.values.setdefault("\\".join(parts[:i]), {})

    def CreateKeyEx(self, hive, path, reserved, access):
        self._ensure(path)
        return _Key(self, path)

    def OpenKey(self, hive, path, reserved, access):
        if path not in self.values:
            raise FileNotFoundError(path)
        return _Key(self, path)

    def CloseKey(self, key):
        pass

    def SetValueEx(self, key, name, reserved, kind, value):
        self._ensure(key.path)
        self.values[key.path][name] = value

    def EnumKey(self, key, index):
        prefix = key.path + "\\"
        children = sorted(path for path in self.values if path.startswith(prefix)
                          and "\\" not in path[len(prefix):])
        if index >= len(children):
            raise OSError(259, "No more data is available")
        return children[index][len(prefix):]

    def DeleteKey(self, hive, path):
        prefix = path + "\\"
        if any(other.startswith(prefix) for other in self.values):
            raise OSError(5, "Access is denied")     # real winreg refuses
        try:
            del self.values[path]
        except KeyError:
            raise FileNotFoundError(path)


@pytest.fixture
def registry(monkeypatch):
    fake = FakeRegistry()
    monkeypatch.setattr(shell, "_winreg_module", lambda: fake)
    return fake


def verb(registry, entry):
    base = shell.SHELL_KEY + "\\" + entry.key
    data = dict(registry.values.get(base, {}))
    cmd = registry.values.get(base + "\\command")
    if cmd is not None:
        data["command"] = cmd
    return data


def test_register_writes_all_three_verbs(registry):
    assert shell.register_context_menu(exe=EXE) is True

    labels = {entry.key: verb(registry, entry)[""]
              for entry in shell.MENU_ENTRIES}
    assert labels == {
        "PDFAura.Compress": "PDF Aura ile Sıkıştır",
        "PDFAura.Split": "PDF Aura ile Kes",
        "PDFAura.Merge": "PDF Aura ile Birleştir",
    }


def test_commands_run_the_cli_with_the_clicked_file(registry):
    shell.register_context_menu(exe=EXE)

    commands = {entry.key: verb(registry, entry)["command"][""]
                for entry in shell.MENU_ENTRIES}
    assert commands["PDFAura.Compress"] == \
        f'"{EXE}" compress "%1" -q ebook'
    assert commands["PDFAura.Split"] == \
        f'"{EXE}" split "%1" --pages 1-1'
    assert commands["PDFAura.Merge"] == f'"{EXE}" merge %*'


def test_the_commands_parse_as_real_cli_arguments():
    """Whatever Explorer runs is a subcommand src/cli.py already has."""
    from src.cli import build_parser

    parser = build_parser()
    assert parser.parse_args(["compress", "a.pdf", "-q", "ebook"]).command == "compress"
    assert parser.parse_args(["split", "a.pdf", "--pages", "1-1"]).command == "split"
    assert parser.parse_args(["merge", "a.pdf", "b.pdf"]).command == "merge"


def test_merge_is_offered_for_a_multi_selection(registry):
    shell.register_context_menu(exe=EXE)
    merge = verb(registry, next(e for e in shell.MENU_ENTRIES
                                if e.key == "PDFAura.Merge"))
    assert merge["MultiSelectModel"] == "Player"


def test_the_icon_points_at_the_app(registry):
    shell.register_context_menu(exe=EXE)
    for entry in shell.MENU_ENTRIES:
        assert verb(registry, entry)["Icon"] == f"{EXE},0"


def test_a_custom_page_range_is_used_for_cut(registry):
    shell.register_context_menu(exe=EXE, split_pages="3-7")
    split = verb(registry, next(e for e in shell.MENU_ENTRIES
                                if e.key == "PDFAura.Split"))
    assert split["command"][""] == f'"{EXE}" split "%1" --pages 3-7'


def test_an_invalid_page_range_falls_back_to_the_default(registry):
    shell.register_context_menu(exe=EXE, split_pages="all")
    split = verb(registry, next(e for e in shell.MENU_ENTRIES
                                if e.key == "PDFAura.Split"))
    assert "--pages 1-1" in split["command"][""]


def test_unregister_removes_the_verbs_and_their_commands(registry):
    shell.register_context_menu(exe=EXE)
    assert shell.unregister_context_menu() is True
    assert not any(path.startswith(shell.SHELL_KEY + "\\PDFAura") for path in registry.values)


def test_unregister_is_idempotent(registry):
    assert shell.unregister_context_menu() is True
    assert shell.unregister_context_menu() is True


def test_context_menu_registered_reports_presence(registry):
    assert shell.context_menu_registered() is False
    shell.register_context_menu(exe=EXE)
    assert shell.context_menu_registered() is True
    shell.unregister_context_menu()
    assert shell.context_menu_registered() is False


def test_without_a_registry_everything_degrades_quietly(monkeypatch):
    monkeypatch.setattr(shell, "_winreg_module", lambda: None)
    assert shell.register_context_menu(exe=EXE) is False
    assert shell.unregister_context_menu() is False
    assert shell.context_menu_registered() is False


def test_a_refused_write_is_reported_not_raised(registry, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(registry, "CreateKeyEx", denied)
    assert shell.register_context_menu(exe=EXE) is False


def test_source_checkout_runs_the_cli_module(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    entry = shell.MENU_ENTRIES[0]
    assert shell.build_command(entry) == \
        f'"{sys.executable}" -m src.cli compress "%1" -q ebook'


def test_a_frozen_build_runs_the_exe_itself(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", EXE)
    entry = shell.MENU_ENTRIES[2]
    assert shell.build_command(entry) == f'"{EXE}" merge %*'


# ── Installer ─────────────────────────────────────────────────────────────

def read_setup():
    with open(os.path.join(ROOT, "setup.iss"), encoding="utf-8") as f:
        return f.read()


def test_installer_offers_the_context_menu_task():
    setup = read_setup()
    assert "[Registry]" in setup
    assert "Tasks: contextmenu" in setup
    assert setup.count("uninsdeletekey") >= 3


def test_installer_registers_the_same_three_labels_and_commands():
    setup = read_setup()
    for entry in shell.MENU_ENTRIES:
        assert entry.key in setup
        assert entry.label in setup
    assert 'compress ""%1"" -q ebook' in setup
    assert 'split ""%1"" --pages 1-1' in setup
    assert "merge %*" in setup
    assert "MultiSelectModel" in setup


def test_installer_has_optional_desktop_context_menu_and_file_association_tasks():
    setup = read_setup()
    for task in ("desktopicon", "contextmenu", "fileassoc"):
        assert f'Name: "{task}"' in setup
    assert "Tasks: fileassoc" in setup
    assert "OpenWithProgids" in setup


def test_installer_documents_silent_install_and_uninstall():
    setup = read_setup()
    assert "/VERYSILENT" in setup
    assert "/SUPPRESSMSGBOXES" in setup
    assert "/TASKS=" in setup
    assert "/REMOVESETTINGS" in setup


def test_uninstall_asks_before_deleting_user_settings():
    setup = read_setup()
    assert "CurUninstallStepChanged" in setup
    assert "RemoveSettingsPrompt" in setup
    assert r"{userappdata}\PDFAura" in setup
    assert "UninstallSilent" in setup
