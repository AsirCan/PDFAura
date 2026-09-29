"""Paper: the default PDF Aura theme.

Warm, low-saturation neutrals (paper, not steel) carry the whole interface;
one cobalt "ink" accent, taken from the app icon, marks what can be acted on
and where the user is. Status colours appear only when there is a status to
report. Every text/background pair used on screen meets WCAG AA; see
tests/test_ui_theme.py.
"""
from src.gui.theme.base import Metrics, Palette, Theme, TypeRole, Typography

_UI = ("Segoe UI Variable Text", "Segoe UI")
_UI_STRONG = ("Segoe UI Variable Text Semibold", "Segoe UI Semibold")
_SMALL = ("Segoe UI Variable Small", "Segoe UI")
_SMALL_STRONG = ("Segoe UI Variable Small Semibold", "Segoe UI Semibold")
_DISPLAY = ("Segoe UI Variable Display Semibold", "Segoe UI Semibold")

PAPER = Theme(
    name="paper",
    label="Paper",
    palette=Palette(
        canvas="#F5F4F1",
        sidebar="#ECEAE5",
        surface="#FFFFFF",
        surface_subtle="#FAF9F7",
        sunken="#F0EEEA",
        field="#FFFFFF",
        hover="#E9E6E0",
        pressed="#DFDBD4",

        border_subtle="#E6E3DD",
        border="#CDC8BF",
        border_strong="#AEA89D",

        text="#1E1D1A",
        text_secondary="#57524A",
        text_tertiary="#6B665D",
        text_disabled="#A9A398",
        text_on_accent="#FFFFFF",

        accent="#2F44C2",
        accent_hover="#2739A7",
        accent_pressed="#1F2E8A",
        accent_subtle="#EEF0FB",
        accent_subtle_hover="#E2E6F9",
        accent_border="#C6CDF1",
        accent_text="#2A3CAE",
        focus_ring="#7F8FE4",

        success="#1B6E45",
        success_bg="#EAF5EE",
        success_border="#C3E2CF",
        warning="#8F540A",
        warning_bg="#FCF4E4",
        warning_border="#EDD6A9",
        danger="#B02318",
        danger_hover="#921C13",
        danger_bg="#FCEEEC",
        danger_border="#F0C7C2",

        stage="#2B2A27",
        stage_text="#ECEAE5",
        stage_muted="#A39E94",
        handle="#5A71EE",
        handle_active="#F0A03C",
        handle_line="#6E83F2",
        magnifier_cross="#F0A03C",
    ),
    typography=Typography(
        display=TypeRole(_DISPLAY, 18, "Segoe UI Semibold"),
        title=TypeRole(_UI_STRONG, 12, "Segoe UI Semibold"),
        heading=TypeRole(_UI_STRONG, 11, "Segoe UI Semibold"),
        body=TypeRole(_UI, 10),
        body_strong=TypeRole(_UI_STRONG, 10, "Segoe UI Semibold"),
        label=TypeRole(_UI_STRONG, 9, "Segoe UI Semibold"),
        small=TypeRole(_SMALL, 9),
        small_strong=TypeRole(_SMALL_STRONG, 9, "Segoe UI Semibold"),
        micro=TypeRole(_SMALL_STRONG, 8, "Segoe UI Semibold"),
        mono=TypeRole(("Cascadia Mono", "Consolas"), 9, "Consolas"),
    ),
    metrics=Metrics(),
)
