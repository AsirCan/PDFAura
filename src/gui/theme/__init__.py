"""Theme registry.

Adding a theme:
    1. Copy paper.py to e.g. slate.py and change the tokens.
    2. register_theme(SLATE) below.
    3. Set "theme": "slate" in config.json (read once at start-up).

Every colour, font and radius on screen comes from the active theme; widgets
read it through active_theme() or the constants src/gui/styles.py derives
from it, never from literals.
"""
from src.gui.theme.base import Metrics, Palette, Theme, TypeRole, Typography
from src.gui.theme.paper import PAPER

DEFAULT_THEME = PAPER.name

_THEMES = {}
_active = None


def register_theme(theme):
    if not isinstance(theme, Theme):
        raise TypeError("register_theme expects a Theme")
    _THEMES[theme.name] = theme
    return theme


def available_themes():
    return dict(_THEMES)


def get_theme(name):
    return _THEMES.get(name) or _THEMES[DEFAULT_THEME]


def active_theme():
    """The theme chosen in the config, falling back to the default."""
    global _active
    if _active is None:
        try:
            from src.core.config_manager import cfg
            name = cfg.get("theme", DEFAULT_THEME)
        except Exception:
            name = DEFAULT_THEME
        _active = get_theme(name)
    return _active


def set_active_theme(name):
    """Select a theme before the UI is built (styles are built once)."""
    global _active
    _active = get_theme(name)
    return _active


register_theme(PAPER)

__all__ = [
    "Metrics", "Palette", "Theme", "TypeRole", "Typography",
    "register_theme", "available_themes", "get_theme",
    "active_theme", "set_active_theme", "DEFAULT_THEME",
]
