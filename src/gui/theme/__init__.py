"""Theme registry and the user's theme preference.

Adding a theme:
    1. Copy paper.py to e.g. slate.py and change the tokens.
    2. register_theme(SLATE) below.
    3. Set "theme": "slate" in config.json, or pick it in Settings.

The preference stored in config.json is a theme name or "system", which
follows Windows' light/dark app mode. styles.apply_theme() switches a
running window without a restart.

Every colour, font and radius on screen comes from the active theme; widgets
read it through active_theme() or the constants src/gui/styles.py derives
from it, never from literals.
"""
from src.gui.theme.base import Metrics, Palette, Theme, TypeRole, Typography
from src.gui.theme.night import NIGHT
from src.gui.theme.paper import PAPER

DEFAULT_THEME = PAPER.name
LIGHT_THEME = PAPER.name
DARK_THEME = NIGHT.name
SYSTEM = "system"
DEFAULT_PREFERENCE = SYSTEM

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


def system_prefers_dark():
    """True when Windows is set to dark mode for apps
    (Settings > Personalisation > Colours). False when it is light or
    cannot be read (older Windows, no registry)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            value, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return value == 0
    except (ImportError, OSError):
        return False


def theme_preference():
    """What the user picked in Settings: "system" or a theme name."""
    try:
        from src.core.config_manager import cfg
        preference = cfg.get("theme", DEFAULT_PREFERENCE)
    except Exception:
        preference = DEFAULT_PREFERENCE
    if preference != SYSTEM and preference not in _THEMES:
        preference = DEFAULT_PREFERENCE
    return preference


def resolve_theme_name(preference):
    """The theme a preference means right now."""
    if preference == SYSTEM:
        return DARK_THEME if system_prefers_dark() else LIGHT_THEME
    return get_theme(preference).name


def active_theme():
    """The theme the preference in the config resolves to."""
    global _active
    if _active is None:
        _active = get_theme(resolve_theme_name(theme_preference()))
    return _active


def set_active_theme(name):
    """Make `name` the active theme. Before the UI exists this is all it
    takes; a running window switches with styles.apply_theme()."""
    global _active
    _active = get_theme(name)
    return _active


register_theme(PAPER)
register_theme(NIGHT)

__all__ = [
    "Metrics", "Palette", "Theme", "TypeRole", "Typography",
    "register_theme", "available_themes", "get_theme",
    "active_theme", "set_active_theme", "DEFAULT_THEME",
    "LIGHT_THEME", "DARK_THEME", "SYSTEM", "DEFAULT_PREFERENCE",
    "system_prefers_dark", "theme_preference", "resolve_theme_name",
]
