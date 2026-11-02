"""Tests for German (de) and Arabic (ar) i18n support in PDFAura.

Ensures:
- 'de' and 'ar' are supported in available_languages and get_translations.
- Arabic carries RTL metadata (rtl=True, is_rtl=True), while German carries LTR metadata.
- All keys present in tr.py/en.py exist in de.py and ar.py for main UI strings.
- Newly added keys (e.g. security permissions, logo watermarks, positions) exist in de and ar.
- No missing translation key falls back to English when language is set to 'de' or 'ar' for all main UI strings.
"""
import string
import pytest

from src.core.config_manager import cfg
from src.core.lang_manager import (
    LANGUAGES,
    RTL_LANGUAGES,
    _STRINGS,
    available_languages,
    get_available_languages,
    get_text,
    get_translations,
    is_rtl,
    strings_for,
)
from src.core.locales import ar, de, en, tr

# File-name suffixes and batch rename token intentionally stay English ASCII
ENGLISH_ONLY = {k for k in _STRINGS["en"] if k.startswith(("suffix_", "security_suffix_"))}
ENGLISH_ONLY.add("batch_rename_default")

MAIN_UI_KEYS = sorted(set(_STRINGS["en"]) - ENGLISH_ONLY)


def _fields(text):
    return sorted(f[1] for f in string.Formatter().parse(text) if f[1] is not None)


# ── Available Languages ───────────────────────────────────────────────────

def test_available_languages_supports_de_and_ar():
    assert "de" in available_languages
    assert "ar" in available_languages
    assert "de" in available_languages()
    assert "ar" in available_languages()
    assert "de" in get_available_languages()
    assert "ar" in get_available_languages()

    assert available_languages["de"]["name"] == "Deutsch"
    assert available_languages["ar"]["name"] == "العربية"
    assert available_languages["de"] == "Deutsch"
    assert available_languages["ar"] == "العربية"


def test_arabic_has_rtl_metadata():
    assert "ar" in RTL_LANGUAGES
    assert is_rtl("ar") is True

    # Checked via available_languages
    meta_ar = available_languages["ar"]
    assert meta_ar["rtl"] is True
    assert meta_ar.rtl is True
    assert meta_ar["is_rtl"] is True
    assert meta_ar.is_rtl is True
    assert meta_ar["direction"] == "rtl"

    # Checked via get_available_languages()
    assert get_available_languages()["ar"].rtl is True


def test_german_has_ltr_metadata():
    assert "de" not in RTL_LANGUAGES
    assert is_rtl("de") is False

    meta_de = available_languages["de"]
    assert meta_de["rtl"] is False
    assert meta_de.rtl is False
    assert meta_de["is_rtl"] is False
    assert meta_de.is_rtl is False
    assert meta_de["direction"] == "ltr"


# ── get_translations ──────────────────────────────────────────────────────

def test_get_translations_de():
    trans = get_translations("de")
    assert trans["rtl"] is False
    assert trans.rtl is False
    assert trans["is_rtl"] is False
    assert trans.is_rtl is False
    assert trans["language"] == "de"
    assert trans.language == "de"
    assert trans["txt_compress"] == "Komprimieren"
    assert "txt_merge" in trans


def test_get_translations_ar():
    trans = get_translations("ar")
    assert trans["rtl"] is True
    assert trans.rtl is True
    assert trans["is_rtl"] is True
    assert trans.is_rtl is True
    assert trans["language"] == "ar"
    assert trans.language == "ar"
    assert trans["txt_compress"] == "ضغط"
    assert "txt_merge" in trans


def test_get_translations_default():
    cfg.config["language"] = "de"
    trans_de = get_translations()
    assert trans_de.language == "de"

    cfg.config["language"] = "ar"
    trans_ar = get_translations()
    assert trans_ar.language == "ar"
    assert trans_ar.rtl is True


# ── Key Parity with tr.py / en.py ─────────────────────────────────────────

def test_locales_tr_and_en_modules():
    assert hasattr(tr, "STRINGS")
    assert hasattr(en, "STRINGS")
    assert set(tr.STRINGS.keys()) == set(en.STRINGS.keys())


def test_all_main_ui_keys_present_in_de_and_ar():
    en_keys = set(en.STRINGS.keys()) - ENGLISH_ONLY
    tr_keys = set(tr.STRINGS.keys()) - ENGLISH_ONLY
    de_keys = set(de.STRINGS.keys())
    ar_keys = set(ar.STRINGS.keys())

    assert en_keys == tr_keys
    missing_de = en_keys - de_keys
    missing_ar = en_keys - ar_keys
    assert missing_de == set(), f"German missing main UI keys: {sorted(missing_de)}"
    assert missing_ar == set(), f"Arabic missing main UI keys: {sorted(missing_ar)}"


def test_security_keys_present_in_de_and_ar():
    security_keys = [
        "security_owner_password",
        "security_permissions",
        "security_allow_print",
        "security_allow_modify",
        "security_allow_copy",
        "security_allow_annotate",
        "security_watermark_image",
        "security_watermark_opacity",
        "security_watermark_angle",
        "security_watermark_position",
        "security_position_center",
        "security_position_top_left",
        "security_position_top_right",
        "security_position_bottom_left",
        "security_position_bottom_right",
        "security_position_tiled",
        "err_watermark_image",
        "err_watermark_position",
        "err_watermark_opacity",
    ]
    for key in security_keys:
        assert key in de.STRINGS, f"Missing key in de: {key}"
        assert key in ar.STRINGS, f"Missing key in ar: {key}"
        assert key in _STRINGS["tr"], f"Missing key in tr: {key}"
        assert key in _STRINGS["en"], f"Missing key in en: {key}"


# ── No Missing Translation Key Falls Back ─────────────────────────────────

@pytest.mark.parametrize("key", MAIN_UI_KEYS)
def test_de_main_ui_strings_do_not_fall_back(key):
    cfg.config["language"] = "de"
    assert key in de.STRINGS, f"Key {key} not found in de.STRINGS"
    translated = get_text(key)
    assert translated == de.STRINGS[key]
    assert translated != "", f"Empty translation for {key} in German"
    assert translated != key, f"Key {key} fell back to raw key string"


@pytest.mark.parametrize("key", MAIN_UI_KEYS)
def test_ar_main_ui_strings_do_not_fall_back(key):
    cfg.config["language"] = "ar"
    assert key in ar.STRINGS, f"Key {key} not found in ar.STRINGS"
    translated = get_text(key)
    assert translated == ar.STRINGS[key]
    assert translated != "", f"Empty translation for {key} in Arabic"
    assert translated != key, f"Key {key} fell back to raw key string"


def test_placeholders_match_english_for_de_and_ar():
    for key in MAIN_UI_KEYS:
        expected_fields = _fields(en.STRINGS[key])
        assert _fields(de.STRINGS[key]) == expected_fields, f"Placeholder mismatch in German for {key}"
        assert _fields(ar.STRINGS[key]) == expected_fields, f"Placeholder mismatch in Arabic for {key}"


def test_file_suffixes_stay_english_ascii():
    # File-name suffixes intentionally stay English ASCII
    cfg.config["language"] = "de"
    assert get_text("suffix_compressed") == "_compressed"
    assert get_text("suffix_merged") == "_merged"

    cfg.config["language"] = "ar"
    assert get_text("suffix_compressed") == "_compressed"
    assert get_text("suffix_merged") == "_merged"
