"""The theme system: the registry, the preference and the tokens' contrast.

The page only uses the CSS variables generated from these themes
(tests/test_web_page.py checks both), so the contrast checked here is the
contrast on screen.
"""
import re
from dataclasses import replace

import pytest

from src.app import theme as theme_module
from src.app.theme import (DARK_THEME, DEFAULT_THEME, LIGHT_THEME, SYSTEM, available_themes,
                           get_theme, register_theme, resolve_theme_name, theme_preference)
from src.app.theme.night import NIGHT
from src.app.theme.paper import PAPER

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# ── Registry ────────────────────────────────────────────────────────────────

def test_the_default_theme_is_registered():
    assert DEFAULT_THEME in available_themes()
    assert get_theme(DEFAULT_THEME) is PAPER


def test_an_unknown_theme_name_falls_back_to_the_default():
    assert get_theme("no-such-theme") is PAPER


def test_a_new_theme_can_be_registered_by_changing_tokens_only():
    ink = register_theme(replace(PAPER, name="test-ink", label="Ink",
                                 palette=replace(PAPER.palette, accent="#0B6E4F")))
    try:
        assert get_theme("test-ink").palette.accent == "#0B6E4F"
        assert get_theme("test-ink").typography is PAPER.typography
    finally:
        from src.app import theme as registry
        registry._THEMES.pop("test-ink", None)


def test_register_theme_rejects_other_objects():
    with pytest.raises(TypeError):
        register_theme({"name": "x"})


def test_there_is_a_light_and_a_dark_theme():
    assert get_theme(LIGHT_THEME) is PAPER and not PAPER.dark
    assert get_theme(DARK_THEME) is NIGHT and NIGHT.dark
    # Only colours differ: switching themes must not move anything.
    assert NIGHT.typography is PAPER.typography
    assert NIGHT.metrics == PAPER.metrics


# ── Preference: "system" or a theme name ────────────────────────────────────

@pytest.mark.parametrize("windows_dark,expected", [(True, DARK_THEME), (False, LIGHT_THEME)])
def test_system_preference_follows_windows(monkeypatch, windows_dark, expected):
    monkeypatch.setattr(theme_module, "system_prefers_dark", lambda: windows_dark)
    assert resolve_theme_name(SYSTEM) == expected


@pytest.mark.parametrize("name", [LIGHT_THEME, DARK_THEME])
def test_a_named_preference_ignores_windows(monkeypatch, name):
    monkeypatch.setattr(theme_module, "system_prefers_dark", lambda: name == LIGHT_THEME)
    assert resolve_theme_name(name) == name


def test_the_preference_is_read_from_the_config(monkeypatch):
    from src.core.config_manager import cfg
    monkeypatch.setitem(cfg.config, "theme", DARK_THEME)
    assert theme_preference() == DARK_THEME
    monkeypatch.setitem(cfg.config, "theme", "no-such-theme")
    assert theme_preference() == SYSTEM          # a stale name falls back, not crashes


def test_new_installs_follow_windows():
    from src.core.config_manager import cfg
    assert cfg.default_config["theme"] == SYSTEM


def test_windows_dark_mode_is_read_from_the_registry(monkeypatch):
    import winreg

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    for stored, dark in ((0, True), (1, False)):
        monkeypatch.setattr(winreg, "OpenKey", lambda *a, **k: Key())
        monkeypatch.setattr(winreg, "QueryValueEx", lambda key, name, v=stored: (v, winreg.REG_DWORD))
        assert theme_module.system_prefers_dark() is dark

    def missing(*_a, **_k):
        raise FileNotFoundError
    monkeypatch.setattr(winreg, "OpenKey", missing)
    assert theme_module.system_prefers_dark() is False


# ── Tokens ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("theme", list(available_themes().values()), ids=lambda t: t.name)
def test_every_colour_token_is_a_hex_colour(theme):
    bad = {k: v for k, v in theme.color_tokens().items() if not HEX.match(v)}
    assert bad == {}


# Text on the surfaces it is actually drawn on (WCAG AA: 4.5:1 for text).
TEXT_PAIRS = [
    ("text", "surface"), ("text", "canvas"), ("text", "sidebar"), ("text", "surface_subtle"),
    ("text_secondary", "surface"), ("text_secondary", "canvas"), ("text_secondary", "sidebar"),
    ("text_secondary", "sunken"), ("text_secondary", "surface_subtle"),
    ("text_tertiary", "surface"), ("text_tertiary", "canvas"), ("text_tertiary", "sidebar"),
    ("text_tertiary", "sunken"), ("text_tertiary", "field"),
    ("text", "field"), ("text", "accent_subtle"), ("text", "surface_subtle"),
    ("text_on_accent", "accent"), ("text_on_accent", "accent_hover"), ("text_on_accent", "accent_pressed"),
    ("text_on_accent", "danger_fill"), ("text_on_accent", "danger_fill_hover"),
    ("accent_text", "accent_subtle"), ("accent_text", "accent_subtle_hover"), ("accent_text", "surface"),
    ("accent_text", "surface_subtle"),
    ("success", "surface_subtle"), ("warning", "surface_subtle"), ("danger", "surface_subtle"),
    ("danger", "surface"), ("danger", "danger_bg"),
    ("stage_text", "stage"), ("stage_muted", "stage"),
]


@pytest.mark.parametrize("theme", list(available_themes().values()), ids=lambda t: t.name)
@pytest.mark.parametrize("fg,bg", TEXT_PAIRS, ids=lambda p: p if isinstance(p, str) else None)
def test_text_meets_wcag_aa(theme, fg, bg):
    p = theme.palette
    ratio = contrast(getattr(p, fg), getattr(p, bg))
    assert ratio >= 4.5, f"{fg} on {bg}: {ratio:.2f}:1"


@pytest.mark.parametrize("theme", list(available_themes().values()), ids=lambda t: t.name)
def test_focus_ring_and_accent_are_visible_against_the_surface(theme):
    """Non-text contrast (WCAG 1.4.11) for the controls that carry meaning."""
    p = theme.palette
    assert contrast(p.accent, p.surface) >= 3
    assert contrast(p.accent, p.sidebar) >= 3     # selected nav icon
    assert contrast(p.focus_ring, p.surface) >= 2.5
    assert contrast(p.handle, p.stage) >= 3
