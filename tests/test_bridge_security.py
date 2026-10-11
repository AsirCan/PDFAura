"""Issue #37: the bridge answers only the app's page, and opens only safe paths.

pywebview puts the js_api bridge into every page the window loads, without
looking where it came from, and open_path ran os.startfile on any path the
page named.
"""
import inspect
import os

import pytest

from conftest import make_pdf
from src.app.bridge import Bridge, same_origin
from src.core.config_manager import cfg
from test_web_bridge import Shell

APP = "http://127.0.0.1:52811/"


@pytest.fixture
def shell():
    return Shell()


@pytest.fixture
def bridge(shell):
    return Bridge(shell)


@pytest.fixture
def opened(monkeypatch):
    seen = []
    monkeypatch.setattr(os, "startfile", seen.append, raising=False)
    return seen


@pytest.fixture(autouse=True)
def no_recent_files():
    saved = cfg.config.get("recent_files")
    cfg.config["recent_files"] = []
    yield
    cfg.config["recent_files"] = saved


# ── Where a call comes from ───────────────────────────────────────────────

@pytest.mark.parametrize("url, ours", [
    ("http://127.0.0.1:52811/", True),
    ("http://127.0.0.1:52811/index.html#settings", True),
    ("http://127.0.0.1:52812/", False),           # another local server
    ("http://localhost:52811/", False),
    ("https://127.0.0.1:52811/", False),
    ("https://example.com/", False),
    ("file:///C:/Users/me/Downloads/sayfa.html", False),
    ("", False),
    (None, False),
])
def test_only_the_apps_own_server_is_the_apps_page(url, ours):
    assert same_origin(url, APP) is ours


def test_a_foreign_page_gets_no_answer(bridge, shell, tmp_path, opened):
    shell.ours = False
    for call in (lambda: bridge.boot(), lambda: bridge.settings(), lambda: bridge.open_path(str(tmp_path)),
                 lambda: bridge.start("compress", {}), lambda: bridge.quit()):
        with pytest.raises(PermissionError):
            call()
    assert opened == [] and not shell.quit_called


def test_every_call_of_the_page_is_guarded():
    unguarded = [name for name, member in vars(Bridge).items()
                 if not name.startswith("_") and inspect.isfunction(member) and not hasattr(member, "__wrapped__")]
    assert unguarded == []


def test_the_page_still_sees_the_parameter_names():
    """pywebview names the page's functions after getfullargspec."""
    assert inspect.getfullargspec(Bridge(Shell()).start).args == ["self", "tool", "params"]


# ── What the page may open ────────────────────────────────────────────────

def test_a_path_the_app_never_wrote_or_showed_is_not_opened(bridge, tmp_path, opened):
    stranger = make_pdf(tmp_path / "baska.pdf")
    assert bridge.open_path(stranger) is False
    assert bridge.reveal_path(stranger) is False
    assert opened == []


@pytest.mark.parametrize("name", ["kur.exe", "calistir.bat", "komut.cmd", "kisayol.lnk", "sayfa.html",
                                  "betik.ps1", "yardim.chm"])
def test_programs_and_pages_are_never_opened(bridge, tmp_path, opened, name):
    program = tmp_path / name
    program.write_bytes(b"x")
    cfg.config["recent_files"] = [str(program)]       # even if it were listed
    assert bridge.open_path(str(program)) is False
    assert opened == []


def test_what_a_tool_wrote_can_be_opened(bridge, shell, tmp_path, opened):
    source = make_pdf(tmp_path / "rapor.pdf", pages=3)
    output = str(tmp_path / "rapor_kesit.pdf")
    bridge.start("split", {"input": source, "output": output, "start": "1", "end": "2"})
    shell.wait_job()

    assert bridge.open_path(output) is True
    assert opened == [output]


def test_recent_files_and_previewed_documents_can_be_opened(bridge, tmp_path, opened):
    recent = make_pdf(tmp_path / "son.pdf")
    previewed = make_pdf(tmp_path / "onizleme.pdf")
    cfg.config["recent_files"] = [recent]
    bridge.document(previewed)

    assert bridge.open_path(recent) is True
    assert bridge.open_path(previewed) is True
    assert opened == [recent, previewed]


# ── The window never leaves the app's page ────────────────────────────────

class Args:
    def __init__(self, uri):
        self.Uri = uri
        self.Cancel = False


class Window:
    real_url = APP

    def __init__(self, current=APP):
        self.current = current

    def get_current_url(self):
        return self.current


@pytest.mark.parametrize("uri, allowed", [
    (APP, True),
    (APP + "index.html", True),
    ("file:///C:/Users/me/Downloads/birakilan.html", False),     # a dropped file
    ("https://example.com/", False),
    ("http://127.0.0.1:9999/", False),
])
def test_navigation_away_from_the_app_is_cancelled(uri, allowed):
    from src.app.window import Shell as WindowShell
    shell = WindowShell()
    shell.window = Window()
    args = Args(uri)

    shell._on_navigation_starting(None, args)

    assert args.Cancel is (not allowed)


def test_the_window_knows_when_it_shows_another_page():
    from src.app.window import Shell as WindowShell
    shell = WindowShell()
    assert shell.page_is_ours() is False          # no window yet
    shell.window = Window()
    assert shell.page_is_ours() is True
    shell.window = Window("file:///C:/x.html")
    assert shell.page_is_ours() is False
