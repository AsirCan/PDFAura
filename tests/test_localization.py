"""Issue #20: Turkish text in the English UI, and an undefined Hero style."""
import os
import re
import string

import pytest

from src.core.lang_manager import _STRINGS

TURKISH_ONLY = "çğışöüÇĞİŞÖÜ"

SOURCE_DIRS = ("src/core", "src/gui", "src/ai", "src/utils")


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


def test_right_to_left_text_is_embedded_line_by_line():
    """Tk lays out left to right; without an RTL embedding the trailing
    colon of "لغة التطبيق:" is drawn on the wrong side."""
    assert RTL_LANGUAGES <= set(LANGUAGES)
    text = _in_language("ar", "settings_restart_body")
    for line in filter(None, text.split("\n")):
        assert line.startswith("‫") and line.endswith("‬")


@pytest.mark.parametrize("language", sorted(RTL_LANGUAGES))
def test_right_to_left_lines_stay_short(language):
    """Tk on Windows draws about 200 bytes at a time and lays each piece out
    separately, which scrambled the word order of longer Urdu lines."""
    from src.core.lang_manager import _RTL_LINE_BYTES
    for key in _STRINGS[language]:
        for line in _in_language(language, key).split("\n"):
            assert len(line.encode("utf-8")) <= _RTL_LINE_BYTES, key


def test_right_to_left_file_suffixes_stay_plain():
    """English fallbacks are not wrapped: they end up inside file names."""
    assert _in_language("ar", "suffix_merged") == "_merged"


def test_left_to_right_text_is_not_wrapped():
    assert "‫" not in _in_language("ja", "settings_lang")


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


# ── Styles referenced actually exist (#20.1) ──────────────────────────────

def test_every_referenced_ttk_style_is_defined(tk_root):
    """Hero.TFrame was used but never defined, so its labels sat on coloured
    boxes against the wrong background.

    Styles are generated from the theme by helpers, so this asks ttk itself
    (after setup_styles) rather than reading styles.py."""
    from tkinter import ttk
    style = ttk.Style(tk_root)

    used = set()
    for path in source_files():
        with open(path, encoding="utf-8") as f:
            used |= set(re.findall(r'style="([A-Za-z0-9_.]+\.T[A-Za-z]+)"', f.read()))

    # ttk's own built-ins need no definition.
    builtin = {"TFrame", "TLabel", "TButton", "TEntry", "TCombobox", "TCheckbutton",
               "TNotebook", "TProgressbar", "TScrollbar", "TSeparator", "Treeview"}
    missing = {name for name in used - builtin if not style.configure(name)}
    assert missing == set(), f"styles used but never configured: {sorted(missing)}"


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


def test_merge_uses_the_standard_hint_strip():
    """The merge tab showed a fabricated "2 files merged" line in a hero."""
    with open("src/gui/tabs/tab_merge.py", encoding="utf-8") as f:
        source = f.read()
    # ToolLayout builds the standard hint strip for every tool page.
    assert "ToolLayout(self.parent, _(\"hint_merge\"))" in source
    assert "HeroBody.TLabel" not in source


def test_merge_listbox_uses_the_shared_style():
    with open("src/gui/tabs/tab_merge.py", encoding="utf-8") as f:
        source = f.read()
    assert "style_listbox(self.merge_listbox)" in source


def test_preview_panel_uses_a_minimum_width_column():
    """Pack shrank both children proportionally when the window was narrow;
    a grid column with a minsize takes the space from the content instead."""
    with open("src/gui/main_window.py", encoding="utf-8") as f:
        source = f.read()
    assert "columnconfigure(1, weight=0, minsize=PREVIEW_COLUMN_WIDTH)" in source
    assert 'self.preview_host.grid(' in source


def test_viewer_closes_its_document():
    with open("src/gui/pdf_viewer.py", encoding="utf-8") as f:
        source = f.read()
    assert "doc.close()" in source
    assert "def destroy(self):" in source


def test_viewer_has_keyboard_shortcuts():
    with open("src/gui/pdf_viewer.py", encoding="utf-8") as f:
        source = f.read()
    for key in ("<Left>", "<Right>", "<Prior>", "<Next>", "<plus>", "<minus>"):
        assert key in source, f"{key} not bound"


def test_preview_panel_closes_its_document_on_failure():
    with open("src/gui/preview_panel.py", encoding="utf-8") as f:
        source = f.read()
    assert "finally:" in source


def test_mismatched_drop_is_reported():
    with open("src/gui/tabs/tab_convert.py", encoding="utf-8") as f:
        source = f.read()
    assert "convert_drop_mismatch" in source


# ── Layout at the supported window widths (#20.2) ─────────────────────────

@pytest.fixture(scope="module")
def app_window(tk_root):
    """A real MainWindow on the shared Tk root."""
    from src.gui.main_window import MainWindow
    for child in tk_root.winfo_children():
        child.destroy()
    tk_root.deiconify()
    window = MainWindow(tk_root)
    yield tk_root, window
    for child in tk_root.winfo_children():
        child.destroy()
    tk_root.withdraw()


PREVIEW_PAGES = ["compress", "organize", "convert", "security", "advanced", "batch"]


@pytest.mark.parametrize("width", [1100, 1300, 1480, 1920])
def test_preview_panel_keeps_its_width_at_every_size(app_window, width):
    """It was squeezed to "Ön", "Seçi", "bel" at the default window size."""
    from src.gui.main_window import PREVIEW_WIDTH

    root, window = app_window
    root.geometry(f"{width}x920")
    root.update_idletasks()
    root.update()

    for page in PREVIEW_PAGES:
        window.show_page(page)
        root.update_idletasks()
        root.update()
        actual = window.preview_host.winfo_width()
        assert actual >= PREVIEW_WIDTH, f"{page} at {width}px: preview is {actual}px"


def test_scanner_gives_the_preview_column_back(app_window):
    """The scanner has its own preview, so the column should not be reserved."""
    root, window = app_window
    window.show_page("scanner")
    root.update_idletasks()
    root.update()
    assert not window.preview_host.winfo_ismapped()


@pytest.mark.parametrize("width", [1100, 1480])
def test_no_page_is_wider_than_the_window(app_window, width):
    """Content wider than the window pushes buttons off the right edge."""
    root, window = app_window
    root.geometry(f"{width}x920")
    root.update_idletasks()
    root.update()

    for page in PREVIEW_PAGES:
        window.show_page(page)
        root.update_idletasks()
        root.update()
        frame = window.workspaces[page].frame
        assert frame.winfo_width() <= window.content.winfo_width() + 2, \
            f"{page} at {width}px overflows its column"
