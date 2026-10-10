"""#25 Faz 2: the web page's sources against the Python side.

- the generated theme and icons match src/app/theme
- no colour literal outside the generated theme
- every string the page shows exists in lang_manager
- the bridge's methods and web/src/lib/types.ts agree (the contract)
"""
import glob
import os
import re

import pytest

from conftest import ROOT
from src.app import webtheme
from src.app.bridge import Bridge
from src.core.lang_manager import _STRINGS

WEB_SRC = os.path.join(ROOT, "web", "src")
GENERATED = os.path.join(WEB_SRC, "lib", "generated")


def sources(*patterns):
    for pattern in patterns:
        for path in glob.glob(os.path.join(WEB_SRC, "**", pattern), recursive=True):
            if not os.path.normpath(path).startswith(os.path.normpath(GENERATED)):
                yield path


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.mark.parametrize("name", sorted(webtheme.FILES))
def test_the_generated_files_match_the_python_theme(name):
    expected = webtheme.FILES[name]()
    assert read(os.path.join(GENERATED, name)) == expected, \
        f"web/src/lib/generated/{name} is out of date: run python -m src.app.webtheme"


def test_both_themes_define_every_colour_token():
    css = webtheme.theme_css()
    from src.app.theme import get_theme
    for token in get_theme("paper").color_tokens():
        assert css.count(f"--{token.replace('_', '-')}:") == 2, token


COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")


@pytest.mark.parametrize("path", sorted(sources("*.svelte", "*.css", "*.ts")))
def test_colours_come_from_the_theme(path):
    """Every colour is a theme variable, so both themes stay complete."""
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", read(path), flags=re.S)
    assert COLOUR.findall(text) == [], f"{os.path.relpath(path, ROOT)}: use a var(--token)"


KEY_CALL = re.compile(r"""\bt\(\s*["']([a-z0-9_]+)["']""")
KEY_LIST = re.compile(r"""label:\s*["']([a-z0-9_]+)["']""")
TEMPLATE_KEY = re.compile(r"""t\(`([a-z0-9_]*)\$\{""")


def used_keys():
    keys = set()
    for path in sources("*.svelte", "*.ts"):
        text = read(path)
        keys |= set(KEY_CALL.findall(text)) | set(KEY_LIST.findall(text))
    return keys


def test_every_string_the_page_shows_exists():
    missing = sorted(key for key in used_keys() if key not in _STRINGS["en"])
    assert missing == [], f"add these to lang_manager (tr, en and the locales): {missing}"


def test_page_titles_exist_for_every_page():
    """The header builds these keys from the page name."""
    pages = re.search(r"PAGES = \[([^\]]*)\]", read(os.path.join(WEB_SRC, "lib", "app.svelte.ts"))).group(1)
    for page in re.findall(r'"(\w+)"', pages):
        for part in ("eyebrow", "title", "body"):
            assert f"page_meta_{page}_{part}" in _STRINGS["en"]


def _typed_methods():
    text = read(os.path.join(WEB_SRC, "lib", "types.ts"))
    body = text[text.index("export interface Api {"):]
    body = body[:body.index("\n}")]
    return set(re.findall(r"^\s+(\w+)\(", body, re.M))


def test_the_page_and_python_agree_on_the_bridge():
    """Layer 8 of #25's test plan: a method on one side only is a bug."""
    python = {name for name in dir(Bridge) if not name.startswith("_") and callable(getattr(Bridge, name))}
    assert _typed_methods() == python


def test_the_fake_bridge_implements_every_method():
    text = read(os.path.join(WEB_SRC, "lib", "fake-bridge.ts"))
    for method in _typed_methods():
        assert re.search(rf"\basync {method}\(", text), f"fake-bridge.ts lacks {method}"


@pytest.mark.parametrize("path", sorted(sources("*.svelte")))
def test_no_static_style_attributes(path):
    """The CSP forbids inline styles; style:prop directives are set from
    script and are allowed, a style="" attribute is not."""
    text = read(path)
    markup = re.sub(r"<script.*?</script>|<style.*?</style>", "", text, flags=re.S)
    assert not re.search(r"\sstyle=", markup), os.path.relpath(path, ROOT)


@pytest.mark.parametrize("path", sorted(sources("*.svelte", "*.ts")))
def test_no_eval_and_no_raw_html(path):
    text = read(path)
    assert not re.search(r"\beval\(|new Function\(|\{@html", text), os.path.relpath(path, ROOT)
