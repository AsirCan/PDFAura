"""Closing the window and the tray icon (src/app/window.py).

Issue #14: enabling the tray setting at runtime left no icon, so X hid the
window with no way to get it back. The window only hides if there is a
tray icon to bring it back from; otherwise closing quits.
"""
import threading

import pystray
import pytest

from src.app import window as window_module
from src.app.window import Shell
from src.core.config_manager import cfg


class FakeWindow:
    """What Shell uses of a pywebview window."""

    def __init__(self):
        self.calls = []

    def hide(self):
        self.calls.append("hide")

    def show(self):
        self.calls.append("show")

    def restore(self):
        self.calls.append("restore")

    def destroy(self):
        self.calls.append("destroy")


class FakeIcon:
    """Stands in for pystray.Icon; run() returns instead of entering a loop."""
    made = []

    def __init__(self, name, image, title, menu):
        self.menu = menu
        self.ran = threading.Event()
        self.stopped = False
        self.notes = []
        FakeIcon.made.append(self)

    def run(self):
        self.ran.set()

    def stop(self):
        self.stopped = True

    def notify(self, body, title):
        self.notes.append((title, body))

    def update_menu(self):
        pass


@pytest.fixture
def tray(monkeypatch):
    old = cfg.config.get("close_to_tray")
    cfg.config["close_to_tray"] = True
    FakeIcon.made = []
    monkeypatch.setattr(pystray, "Icon", FakeIcon)
    yield
    cfg.config["close_to_tray"] = old


@pytest.fixture
def icon_file(tmp_path, monkeypatch):
    from PIL import Image
    path = tmp_path / "app_icon.ico"
    Image.new("RGB", (16, 16), (10, 10, 10)).save(path)
    monkeypatch.setattr(window_module, "_asset", lambda name: str(path))
    return str(path)


@pytest.fixture
def shell():
    made = Shell()
    made.window = FakeWindow()
    return made


def test_closing_hides_to_a_tray_icon_started_on_demand(tray, icon_file, shell, monkeypatch):
    saved = []
    monkeypatch.setattr(shell.scans, "save_now", lambda: saved.append(True))
    assert shell._on_closing() is False, "closing must be cancelled, the window only hides"
    assert shell.window.calls == ["hide"]
    assert len(FakeIcon.made) == 1 and FakeIcon.made[0].ran.wait(5)
    # The scanner's pages are written now: the app may never be shown again.
    assert saved == [True]


def test_the_first_hide_says_the_app_is_still_running(tray, icon_file, shell):
    shell._on_closing()
    shell._on_closing()
    assert len(FakeIcon.made[0].notes) == 1


def test_quits_instead_of_hiding_when_no_icon_can_be_made(tray, shell, monkeypatch):
    monkeypatch.setattr(window_module, "_asset", lambda name: None)
    assert shell._on_closing() is True
    assert shell.window.calls == []


def test_quits_when_pystray_fails(tray, icon_file, shell, monkeypatch):
    def boom(*_a, **_k):
        raise OSError("no tray here")
    monkeypatch.setattr(pystray, "Icon", boom)
    assert shell._on_closing() is True
    assert shell.window.calls == []


def test_an_existing_icon_is_reused(tray, icon_file, shell):
    shell._on_closing()
    shell._on_closing()
    assert len(FakeIcon.made) == 1


def test_with_the_setting_off_closing_quits(tray, icon_file, shell):
    shell._ensure_tray()
    cfg.config["close_to_tray"] = False
    assert shell._on_closing() is True
    assert FakeIcon.made[0].stopped


def test_quit_really_quits(tray, icon_file, shell):
    shell._ensure_tray()
    shell.quit()
    assert shell.window.calls == ["destroy"] and FakeIcon.made[0].stopped
    assert shell._on_closing() is True


def test_a_click_on_the_icon_brings_the_window_back(tray, icon_file, shell):
    """The Open item is the menu's default, so a click on the icon (not only
    right-click, Open) shows the window, restored and in front."""
    shell._ensure_tray()
    menu = FakeIcon.made[0].menu
    first = list(menu.items)[0]
    assert first.default
    first(FakeIcon.made[0])
    assert shell.window.calls == ["show", "restore"]


def test_the_tray_menu_follows_the_language(tray, icon_file, shell):
    shell._ensure_tray()
    cfg.config["language"] = "en"
    shell.language_changed()
    assert [item.text for item in FakeIcon.made[0].menu.items] == ["Open", "Quit"]
