"""Issue #14: enabling the tray setting at runtime left no icon, so X hid the
window with no way to get it back."""
import pytest

from src.core.config_manager import cfg
from src.gui.main_window import MainWindow


class FakeRoot:
    def __init__(self):
        self.withdrawn = False

    def withdraw(self):
        self.withdrawn = True


class App:
    """The two methods under test, on a stand-in with no Tk or pystray."""
    on_closing = MainWindow.on_closing
    _ensure_tray_icon = MainWindow._ensure_tray_icon

    def __init__(self, icon_path=None, tray_icon=None, icon_starts=True):
        self.root = FakeRoot()
        self.icon_path = icon_path
        self.tray_icon = tray_icon
        self.quit_called = False
        self._icon_starts = icon_starts
        self._notified = False

    def quit_window(self, _icon, _item):
        self.quit_called = True

    def show_window(self, _icon, _item):
        pass

    def _scanner_tab(self):
        return None

    def _notify_running_in_tray(self):
        self._notified = True


@pytest.fixture
def tray_on():
    old = cfg.config.get("close_to_tray")
    cfg.config["close_to_tray"] = True
    yield
    cfg.config["close_to_tray"] = old


@pytest.fixture
def tray_off():
    old = cfg.config.get("close_to_tray")
    cfg.config["close_to_tray"] = False
    yield
    cfg.config["close_to_tray"] = old


@pytest.fixture
def icon_file(tmp_path):
    from PIL import Image
    path = tmp_path / "icon.png"
    Image.new("RGB", (16, 16), (10, 10, 10)).save(path)
    return str(path)


class FakeIcon:
    """Stands in for pystray.Icon; run() returns instead of entering a loop."""
    def __init__(self, *args, **kwargs):
        self.ran = False

    def run(self):
        self.ran = True


def test_tray_icon_is_started_on_demand(tray_on, icon_file, monkeypatch):
    """The setting was turned on after launch, so no icon existed yet."""
    monkeypatch.setattr("src.gui.main_window.pystray.Icon", FakeIcon)

    app = App(icon_path=icon_file, tray_icon=None)
    app.on_closing()

    assert isinstance(app.tray_icon, FakeIcon)
    assert app.root.withdrawn is True
    assert app.quit_called is False


def test_quits_instead_of_hiding_when_no_icon_can_be_made(tray_on):
    """Without an icon file the window must not be hidden with no way back."""
    app = App(icon_path=None, tray_icon=None)

    app.on_closing()

    assert app.root.withdrawn is False
    assert app.quit_called is True


def test_quits_when_the_icon_file_is_missing(tray_on, tmp_path):
    app = App(icon_path=str(tmp_path / "gone.png"), tray_icon=None)

    app.on_closing()

    assert app.root.withdrawn is False
    assert app.quit_called is True


def test_quits_when_pystray_fails(tray_on, icon_file, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no tray on this system")
    monkeypatch.setattr("src.gui.main_window.pystray.Icon", boom)

    app = App(icon_path=icon_file, tray_icon=None)
    app.on_closing()

    assert app.root.withdrawn is False
    assert app.quit_called is True


def test_existing_icon_is_reused(tray_on, icon_file):
    sentinel = object()
    app = App(icon_path=icon_file, tray_icon=sentinel)

    app.on_closing()

    assert app.tray_icon is sentinel
    assert app.root.withdrawn is True


def test_setting_off_quits(tray_off, icon_file):
    app = App(icon_path=icon_file, tray_icon=None)

    app.on_closing()

    assert app.root.withdrawn is False
    assert app.quit_called is True
