"""Night: the dark PDF Aura theme.

The same warm neutrals as Paper, turned down: charcoal rather than blue-black,
so a page of white paper on the stage does not glare. Depth reads the other
way round from Paper: the sidebar recedes darkest, cards rise lighter than
the canvas, and wells (inputs, the preview stage) sink below the card.

The cobalt accent is lifted just enough to stand off the dark surface while
white labels on it still meet WCAG AA. Status colours are lighter tints for
text, and the destructive button keeps its own deeper red (danger_fill) so
its white label stays readable. tests/test_ui_theme.py checks every pair.
"""
from dataclasses import replace

from src.gui.theme.base import Palette, Theme
from src.gui.theme.paper import PAPER

NIGHT = replace(
    PAPER,
    name="night",
    label="Night",
    dark=True,
    palette=Palette(
        canvas="#1B1A18",
        sidebar="#161513",
        surface="#252421",
        surface_subtle="#2A2926",
        sunken="#1F1E1C",
        field="#1D1C1A",
        hover="#33312E",
        pressed="#3C3A36",

        border_subtle="#36342F",
        border="#4D4A44",
        border_strong="#6A665F",

        text="#EDEBE6",
        text_secondary="#BEB9AF",
        text_tertiary="#A19B90",
        text_disabled="#66625B",
        text_on_accent="#FFFFFF",

        accent="#5066DE",
        accent_hover="#566BE3",
        accent_pressed="#4458CC",
        accent_subtle="#252A42",
        accent_subtle_hover="#2D3350",
        accent_border="#3C4677",
        accent_text="#A3AFF7",
        focus_ring="#7F8FE4",

        success="#63C58F",
        success_bg="#1C2B22",
        success_border="#2E5140",
        warning="#E3AA55",
        warning_bg="#30271A",
        warning_border="#5A4726",
        danger="#F2837A",
        danger_fill="#C9372C",
        danger_fill_hover="#B02F25",
        danger_bg="#35201E",
        danger_border="#63332F",

        stage="#121110",
        stage_text="#ECEAE5",
        stage_muted="#A39E94",
        handle="#6E83F2",
        handle_active="#F0A03C",
        handle_line="#7F91F4",
        handle_ring="#FFFFFF",
        magnifier_cross="#F0A03C",
    ),
)
