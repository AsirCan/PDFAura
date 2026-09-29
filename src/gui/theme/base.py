"""The shape of a theme.

A theme is plain data: colour tokens, type roles and metrics. Nothing here
touches Tk, so a theme can be defined, registered and tested without a
display. src/gui/styles.py turns the active theme into ttk styles.

Colour tokens are semantic ("text_secondary", "accent_subtle"), never
literal ("grey_600"), so a new theme only has to answer "what colour is a
secondary label?" and every screen follows.
"""
from dataclasses import dataclass, field, fields


@dataclass(frozen=True)
class Palette:
    # ── Neutral surfaces, back to front ──
    canvas: str             # window background behind everything
    sidebar: str            # navigation rail; recedes behind the content
    surface: str            # cards, the main working surface
    surface_subtle: str     # quiet panels inside a card (status, groups)
    sunken: str             # wells: preview stage, hint strip, segment track
    field: str              # text inputs
    hover: str              # neutral hover wash on transparent controls
    pressed: str            # neutral pressed wash

    # ── Lines ──
    border_subtle: str      # card outlines, dividers
    border: str             # input outlines
    border_strong: str      # input hover

    # ── Text ──
    text: str
    text_secondary: str
    text_tertiary: str      # meta only; never for text the user must read
    text_disabled: str
    text_on_accent: str

    # ── Brand accent: used sparingly, for "act here" and "you are here" ──
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_subtle: str
    accent_subtle_hover: str
    accent_border: str
    accent_text: str
    focus_ring: str

    # ── Status ──
    success: str
    success_bg: str
    success_border: str
    warning: str
    warning_bg: str
    warning_border: str
    danger: str             # danger text and icons
    danger_fill: str        # destructive button face (carries text_on_accent)
    danger_fill_hover: str
    danger_bg: str
    danger_border: str

    # ── Dark stage the scanner and PDF viewer put photos and pages on ──
    stage: str
    stage_text: str
    stage_muted: str
    handle: str             # crop corner handle
    handle_active: str
    handle_line: str        # crop outline
    handle_ring: str        # outline that lifts a handle off the photo
    magnifier_cross: str


@dataclass(frozen=True)
class TypeRole:
    families: tuple         # tried in order; first installed one wins
    size: int               # points
    fallback: str = "Segoe UI"


@dataclass(frozen=True)
class Typography:
    display: TypeRole       # page title
    title: TypeRole         # card title
    heading: TypeRole       # section inside a card
    body: TypeRole
    body_strong: TypeRole
    label: TypeRole         # field labels, buttons
    small: TypeRole         # hints, meta
    small_strong: TypeRole
    micro: TypeRole         # overlines, badges
    mono: TypeRole
    icon_families: tuple = ("Segoe Fluent Icons", "Segoe MDL2 Assets")
    icon_files: tuple = ("SegoeIcons.ttf", "segmdl2.ttf")


@dataclass(frozen=True)
class Metrics:
    radius_sm: int = 4      # checkbox, badge
    radius: int = 6         # buttons, inputs
    radius_lg: int = 8      # cards
    unit: int = 4           # spacing grid
    sidebar_width: int = 232
    control_pad_y: int = 7  # vertical button padding; sets the control height

    def space(self, steps):
        """Spacing on the 4 px grid: space(4) == 16."""
        return self.unit * steps


@dataclass(frozen=True)
class Theme:
    name: str
    label: str
    palette: Palette
    typography: Typography
    metrics: Metrics = field(default_factory=Metrics)
    dark: bool = False

    def color_tokens(self):
        return {f.name: getattr(self.palette, f.name) for f in fields(self.palette)}
