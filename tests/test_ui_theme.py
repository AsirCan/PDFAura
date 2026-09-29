"""The theme system: tokens, contrast, and that screens really use it."""
import os
import re
from dataclasses import replace

import pytest

from src.gui.theme import DEFAULT_THEME, available_themes, get_theme, register_theme
from src.gui.theme.paper import PAPER

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
        from src.gui import theme as registry
        registry._THEMES.pop("test-ink", None)


def test_register_theme_rejects_other_objects():
    with pytest.raises(TypeError):
        register_theme({"name": "x"})


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
    ("text_tertiary", "sunken"),
    ("text_on_accent", "accent"), ("text_on_accent", "accent_hover"), ("text_on_accent", "danger"),
    ("accent_text", "accent_subtle"), ("accent_text", "surface"), ("accent_text", "surface_subtle"),
    ("success", "surface_subtle"), ("warning", "surface_subtle"), ("danger", "surface_subtle"),
    ("danger", "danger_bg"),
    ("stage_text", "stage"), ("stage_muted", "stage"),
]


@pytest.mark.parametrize("theme", list(available_themes().values()), ids=lambda t: t.name)
@pytest.mark.parametrize("fg,bg", TEXT_PAIRS, ids=lambda p: p if isinstance(p, str) else None)
def test_text_meets_wcag_aa(theme, fg, bg):
    p = theme.palette
    ratio = contrast(getattr(p, fg), getattr(p, bg))
    assert ratio >= 4.5, f"{fg} on {bg}: {ratio:.2f}:1"


def test_focus_ring_and_accent_are_visible_against_the_surface():
    """Non-text contrast (WCAG 1.4.11) for the controls that carry meaning."""
    p = PAPER.palette
    assert contrast(p.accent, p.surface) >= 3
    assert contrast(p.focus_ring, p.surface) >= 2.5
    assert contrast(p.handle, p.stage) >= 3


# ── Screens use the theme, not literals ─────────────────────────────────────

GUI_DIR = "src/gui"


def _gui_sources():
    for dirpath, _dirs, files in os.walk(GUI_DIR):
        if "__pycache__" in dirpath or os.path.normpath(dirpath).startswith(os.path.normpath("src/gui/theme")):
            continue
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


@pytest.mark.parametrize("path", list(_gui_sources()))
def test_no_colour_literals_outside_the_theme(path):
    with open(path, encoding="utf-8") as f:
        source = f.read()
    literals = re.findall(r"[\"']#[0-9A-Fa-f]{3,8}[\"']", source)
    assert literals == [], f"{path}: colours belong in src/gui/theme ({literals})"


@pytest.mark.parametrize("path", list(_gui_sources()))
def test_no_hardcoded_font_families_outside_the_theme(path):
    """Fonts come from styles.font(role) so a theme can change them."""
    with open(path, encoding="utf-8") as f:
        source = f.read()
    families = re.findall(r"(?:font=\(|family=)\s*[\"'](?:Segoe|Consolas|Bahnschrift|Arial)[^\"']*[\"']", source)
    assert families == [], f"{path}: {families}"


# ── Built styles ────────────────────────────────────────────────────────────

def test_setup_styles_is_idempotent_per_window(tk_root):
    from src.gui.styles import image_bank, setup_styles
    bank = image_bank()
    setup_styles(tk_root)            # a second call must not raise "duplicate element"
    assert image_bank() is bank


def test_fonts_resolve_to_installed_families(tk_root):
    from tkinter import font as tkfont
    from src.gui.styles import font
    installed = set(tkfont.families(tk_root))
    for role in ("display", "title", "body", "label", "small", "mono"):
        family, size = font(role)
        assert family in installed or family in ("Segoe UI", "Segoe UI Semibold", "Consolas")
        assert size > 0


def test_control_states_keep_one_size(tk_root):
    """Hover, focus and pressed images of a control must be the same size,
    or the control jumps when the pointer or keyboard reaches it."""
    from src.gui import styles
    sizes = {(photo.width(), photo.height())
             for key, photo in styles.image_bank()._photos.items() if key[0] == "box"
             and key[3] == styles.M.radius}
    assert len(sizes) == 1, sizes
