"""Issue #20: Turkish text in the English UI; every language complete."""
import os
import re
import string

import pytest

from src.core.lang_manager import _STRINGS

TURKISH_ONLY = "çğışöüÇĞİŞÖÜ"

SOURCE_DIRS = ("src/core", "src/app", "src/ai", "src/utils")


def source_files():
    for folder in SOURCE_DIRS:
        for dirpath, _dirs, files in os.walk(folder):
            if "__pycache__" in dirpath:
                continue
            for name in files:
                if name.endswith(".py") and name != "lang_manager.py":
                    yield os.path.join(dirpath, name)


# ── The two dictionaries agree ────────────────────────────────────────────

def test_both_languages_have_the_same_keys():
    turkish = set(_STRINGS["tr"])
    english = set(_STRINGS["en"])
    assert turkish - english == set(), f"missing from en: {sorted(turkish - english)}"
    assert english - turkish == set(), f"missing from tr: {sorted(english - turkish)}"


def test_english_strings_have_no_turkish_letters():
    offenders = {
        key: value for key, value in _STRINGS["en"].items()
        if isinstance(value, str) and any(ch in TURKISH_ONLY for ch in value)
    }
    assert offenders == {}, f"Turkish letters in English strings: {offenders}"


def test_translated_keys_are_not_placeholders():
    """A key whose English value is the key itself was never translated."""
    offenders = [key for key, value in _STRINGS["en"].items() if value == key]
    assert offenders == []


# ── The other languages ───────────────────────────────────────────────────

from src.core.lang_manager import LANGUAGES, RTL_LANGUAGES, get_text  # noqa: E402

EXTRA_LANGUAGES = sorted(set(LANGUAGES) - {"tr", "en"})

# Left to English on purpose (see src/core/locales/__init__.py).
ENGLISH_ONLY = {k for k in _STRINGS["en"] if k.startswith(("suffix_", "security_suffix_"))}
ENGLISH_ONLY.add("batch_rename_default")


def _fields(text):
    return sorted(f[1] for f in string.Formatter().parse(text) if f[1] is not None)


def test_every_listed_language_has_strings():
    assert set(LANGUAGES) == set(_STRINGS)


@pytest.mark.parametrize("language", EXTRA_LANGUAGES)
def test_language_covers_every_key(language):
    strings = _STRINGS[language]
    english = set(_STRINGS["en"])
    assert english - ENGLISH_ONLY - set(strings) == set(), "keys left untranslated"
    assert set(strings) - english == set(), "keys English does not have"
    assert set(strings) & ENGLISH_ONLY == set(), "file-name keys must stay English"


@pytest.mark.parametrize("language", EXTRA_LANGUAGES)
def test_language_keeps_the_placeholders(language):
    """A renamed or dropped {field} raises KeyError when the string is formatted."""
    english = _STRINGS["en"]
    offenders = {
        key: value for key, value in _STRINGS[language].items()
        if _fields(value) != _fields(english[key])
    }
    assert offenders == {}


@pytest.mark.parametrize("language", EXTRA_LANGUAGES)
def test_batch_hint_shows_tokens_the_renamer_understands(language):
    from src.core.batch import RENAME_TOKENS
    known = {alias for aliases in RENAME_TOKENS.values() for alias in aliases}
    shown = re.findall(r"\[([^\]]+)\]", _STRINGS[language]["batch_rename_hint"])
    assert shown and set(shown) <= known


def _in_language(language, key):
    from src.core.config_manager import cfg
    cfg.config["language"] = language
    return get_text(key)


def test_missing_key_falls_back_to_english():
    assert _in_language("de", "suffix_compressed") == "_compressed"


def test_right_to_left_text_is_plain():
    """The page sets dir="rtl" and the browser lays the text out: no
    direction marks, no lines broken for Tk (they came out as real breaks)."""
    assert RTL_LANGUAGES <= set(LANGUAGES)
    for language in sorted(RTL_LANGUAGES):
        text = _in_language(language, "settings_restart_body")
        assert "‫" not in text and "‬" not in text
        assert text == _STRINGS[language]["settings_restart_body"]


# ── No user-visible Turkish outside lang_manager ──────────────────────────

# Progress messages and error text reach the screen, so they must come from
# lang_manager. These calls are the ones that display a string.
# Matching is line-bounded so a match cannot run past the end of one string
# literal and pick up a Turkish character from an unrelated line.
DISPLAY_CALLS = re.compile(
    r"(?:report_progress|set_error|set_info|set_success|set_busy|speak)"
    r"\([^)\n]*\"[^\"\n]*[" + TURKISH_ONLY + r"][^\"\n]*\""
)


@pytest.mark.parametrize("path", sorted(source_files()))
def test_no_hardcoded_turkish_in_displayed_strings(path):
    with open(path, encoding="utf-8") as f:
        source = f.read()
    matches = DISPLAY_CALLS.findall(source)
    assert matches == [], f"{path}: hardcoded Turkish reaches the screen"


# ── Specific fixes from the issue ─────────────────────────────────────────

def test_the_export_typo_is_fixed():
    assert "aktarıldü" not in _STRINGS["tr"]["convert_result_pdf2txt"]
    assert "aktarıldı" in _STRINGS["tr"]["convert_result_pdf2txt"]


def test_zoom_labels_are_translated():
    assert _STRINGS["tr"]["viewer_zoom_in"] != _STRINGS["en"]["viewer_zoom_in"]
    assert _STRINGS["tr"]["viewer_zoom_out"] != _STRINGS["en"]["viewer_zoom_out"]


@pytest.mark.parametrize("quality", ["screen", "ebook", "printer", "prepress"])
def test_compression_qualities_are_explained(quality):
    """Bare "screen/ebook/printer/prepress" said nothing about what they do."""
    for language in ("tr", "en"):
        label = _STRINGS[language][f"quality_{quality}"]
        assert quality in label
        assert "dpi" in label, f"{language}/{quality} has no explanation"
