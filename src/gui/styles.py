"""ttk styles, built from the active theme (src/gui/theme).

setup_styles(root) must run once, after the Tk root exists and before any
widget is built. It resolves the theme's fonts against what is installed,
draws the rounded control images, and configures every named style the app
uses. Nothing in here holds a literal colour: change the theme, not this file.

Naming: a style's name says what it is for ("Primary.TButton",
"Field.TLabel"). Rounded image elements show the style's `background` in
their corners, so styles meant for a different surface get their own name
("Nav.TButton" sits on the sidebar, "Voice.TButton" inside the command
field). tests/test_ui_interactions.py checks that every button's corners
match the surface it is placed on.
"""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from PIL import Image, ImageDraw

from src.gui.theme import active_theme
from src.gui.theme.images import (ImageBank, Icons, check_box, chevron, icon_image,
                                  radio_dot, rounded_box)

THEME = active_theme()
P = THEME.palette
M = THEME.metrics

# Status tones of the result panel: (text colour, icon glyph). The colour
# is never the only signal; the badge always names the state too.
TONES = {
    "neutral": (P.text_secondary, Icons.INFO),
    "info": (P.accent_text, Icons.INFO),
    "busy": (P.accent_text, Icons.SYNC),
    "success": (P.success, Icons.SUCCESS),
    "warning": (P.warning, Icons.WARNING),
    "danger": (P.danger, Icons.ERROR),
}

_fonts = {}
_bank = None
# Colour inside each rounded-image frame style (its `background` is the
# colour *around* it); widgets placed in the frame must match this one.
INTERIOR = {}
_icon_family = None


# ── Public accessors ────────────────────────────────────────────────────────

def font(role):
    """A Tk font tuple for a type role ("body", "title", ...)."""
    if role in _fonts:
        return _fonts[role]
    type_role = getattr(THEME.typography, role)
    return (type_role.fallback, type_role.size)


def icon_font(size=12):
    """Tk font tuple for glyphs from Icons, or None without an icon font."""
    return (_icon_family, size) if _icon_family else None


def icon(glyph, size=16, color=None, box=None):
    """A PhotoImage of an Icons glyph (None when no icon font is installed)."""
    if _bank is None:
        return None
    color = color or P.text_secondary
    box = box or size + 4
    key = ("icon", glyph, size, color, box)
    return _bank.photo(key, lambda: icon_image(glyph, size, color, THEME.typography.icon_files, box))


def icon_states(glyph, size=16, color=None):
    """An icon for a button that can be disabled: dimmed with its label."""
    normal = icon(glyph, size, color)
    if normal is None:
        return ""
    return (normal, "disabled", icon(glyph, size, P.text_disabled))


def surface_of(widget):
    """The colour a widget shows behind its children."""
    try:
        name = str(widget.cget("style")) or widget.winfo_class()
    except tk.TclError:
        return str(widget.cget("background"))
    return INTERIOR.get(name) or ttk.Style(widget).lookup(name, "background")


def image_bank():
    return _bank


# ── Setup ───────────────────────────────────────────────────────────────────

def _resolve_fonts(root):
    global _icon_family
    installed = set(tkfont.families(root))
    typo = THEME.typography
    for role in ("display", "title", "heading", "body", "body_strong", "label",
                 "small", "small_strong", "micro", "mono"):
        type_role = getattr(typo, role)
        family = next((f for f in type_role.families if f in installed), type_role.fallback)
        _fonts[role] = (family, type_role.size)
    _icon_family = next((f for f in typo.icon_families if f in installed), None)


def _set_named_fonts(root):
    """Tk's own defaults, so plain tk widgets and dialogs match."""
    for name, role in (("TkDefaultFont", "body"), ("TkTextFont", "body"),
                       ("TkMenuFont", "body"), ("TkHeadingFont", "label"),
                       ("TkCaptionFont", "heading"), ("TkSmallCaptionFont", "small"),
                       ("TkTooltipFont", "small"), ("TkFixedFont", "mono")):
        try:
            family, size = font(role)
            tkfont.nametofont(name, root=root).configure(family=family, size=size)
        except tk.TclError:
            pass


def _option_database(root):
    """Defaults for classic tk widgets (combobox drop-downs, listboxes, menus)."""
    body = font("body")
    root.option_add("*TCombobox*Listbox.background", P.surface)
    root.option_add("*TCombobox*Listbox.foreground", P.text)
    root.option_add("*TCombobox*Listbox.selectBackground", P.accent_subtle_hover)
    root.option_add("*TCombobox*Listbox.selectForeground", P.text)
    root.option_add("*TCombobox*Listbox.font", body)
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
    root.option_add("*TCombobox*Listbox.relief", "flat")
    root.option_add("*Menu.background", P.surface)
    root.option_add("*Menu.foreground", P.text)
    root.option_add("*Menu.activeBackground", P.accent_subtle_hover)
    root.option_add("*Menu.activeForeground", P.text)
    root.option_add("*Menu.font", body)
    root.option_add("*Menu.relief", "flat")


def _img(key, factory):
    return _bank.photo(key, factory)


RING = 2  # focus-ring width; every control image reserves this margin
# ttk *tiles* (does not stretch) the middle of an image element, one alpha
# blit per tile. A tiny middle turned a large card into tens of thousands of
# blits per redraw and froze the window, so the middles are generous.
STRETCH = 64


def _box(fill, border=None, radius=None, ring=None):
    """A rounded control image. It always carries a RING-px margin, drawn as
    the focus ring when `ring` is given and left transparent otherwise, so
    all states of a control have the same size and nothing shifts on focus."""
    radius = M.radius if radius is None else radius
    inner = radius * 2 + 4 + STRETCH
    total = inner + RING * 2
    if ring:
        return _img(("box", fill, border, radius, ring),
                    lambda: rounded_box(total, total, radius, fill, border=border,
                                        ring=ring, ring_width=RING))
    return _img(("box", fill, border, radius, None),
                lambda: _pad_img(rounded_box(inner, inner, radius, fill, border=border), RING))


def _panel(fill, border=None, radius=None):
    """A rounded surface image without the focus margin (cards, wells)."""
    radius = M.radius_lg if radius is None else radius
    size = radius * 2 + 4 + STRETCH * 2
    return _img(("panel", fill, border, radius),
                lambda: rounded_box(size, size, radius, fill, border=border))


def _control_element(style, element, normal, *states, radius=None):
    """Image element for a focusable control: fixed rounded edges, a RING-px
    margin for the focus ring, and a small minimum size (the image itself is
    large only so ttk has few tiles to draw)."""
    radius = M.radius if radius is None else radius
    edge = radius + 2 + RING
    style.element_create(element, "image", normal, *states, border=edge, padding=RING + 1,
                         width=edge * 2, height=edge * 2, sticky="nsew")


def _frame_style(style, name, fill, parent_bg, border=None, radius=None):
    """A frame drawn as a rounded box (card, group, well)."""
    radius = M.radius_lg if radius is None else radius
    element = f"{name}.box"
    edge = radius + 2
    style.element_create(element, "image", _panel(fill, border, radius),
                         border=edge, padding=1, width=edge * 2, height=edge * 2, sticky="nsew")
    style.layout(name, [(element, {"sticky": "nsew"})])
    style.configure(name, background=parent_bg)
    INTERIOR[name] = fill


def _configure_button(style, name, parent_bg, fill, hover, pressed, foreground,
                      border=None, border_hover=None, fg_hover=None,
                      disabled_fill=None, disabled_fg=None, disabled_border=None,
                      padding=None, font_role="body_strong", anchor=None, radius=None,
                      selected=None, selected_border=None, selected_fg=None):
    """A rounded push button with hover, pressed, disabled, keyboard-focus
    (and optionally selected) states."""
    radius = M.radius if radius is None else radius
    specs = [
        ("disabled", _box(disabled_fill or fill, disabled_border or border, radius)),
        ("pressed !disabled", _box(pressed, border_hover or border, radius)),
    ]
    if selected:
        specs.append(("selected", _box(selected, selected_border or border, radius)))
    specs += [
        # user1 = focus arrived from the keyboard (see widgets.FocusVisible).
        ("user1 focus !disabled", _box(fill, border, radius, ring=P.focus_ring)),
        ("active !disabled", _box(hover, border_hover or border, radius)),
    ]
    element = f"{name}.box"
    _control_element(style, element, _box(fill, border, radius), *specs, radius=radius)
    style.layout(name, [(element, {"sticky": "nsew", "children": [
        ("Button.padding", {"sticky": "nsew", "children": [
            ("Button.label", {"sticky": "nsew"})]})]})])
    style.configure(name, background=parent_bg, foreground=foreground, font=font(font_role),
                    padding=padding or (14, M.control_pad_y), anchor=anchor or "center",
                    focuscolor=parent_bg)
    fg_map = [("disabled", disabled_fg or P.text_disabled)]
    if selected_fg:
        fg_map.append(("selected", selected_fg))
    fg_map.append(("active", fg_hover or foreground))
    style.map(name, foreground=fg_map)


def setup_styles(root=None):
    """Build every ttk style from the active theme. Returns the ttk.Style."""
    global _bank
    root = root or tk._default_root
    style = ttk.Style(root)
    if _bank is not None and _bank.master is root:
        return style                     # already built for this window
    style.theme_use("clam")
    _bank = ImageBank(root)
    _resolve_fonts(root)
    _set_named_fonts(root)
    _option_database(root)

    body, label = font("body"), font("label")

    style.configure(".", background=P.canvas, foreground=P.text, font=body,
                    bordercolor=P.border, lightcolor=P.surface, darkcolor=P.border,
                    troughcolor=P.sunken, selectbackground=P.accent_subtle_hover,
                    selectforeground=P.text, insertcolor=P.text, focuscolor=P.focus_ring)

    # ── Frames ──
    style.configure("App.TFrame", background=P.canvas)
    style.configure("Sidebar.TFrame", background=P.sidebar)
    style.configure("Surface.TFrame", background=P.surface)
    style.configure("Panel.TFrame", background=P.surface)
    style.configure("FeedbackRow.TFrame", background=P.surface_subtle)
    style.configure("Divider.TFrame", background=P.border_subtle)
    style.configure("SidebarDivider.TFrame", background=P.border_subtle)
    style.configure("Stage.TFrame", background=P.stage)
    _frame_style(style, "Card.TFrame", P.surface, P.canvas, border=P.border_subtle)
    _frame_style(style, "Preview.TFrame", P.surface, P.canvas, border=P.border_subtle)
    _frame_style(style, "PanelCard.TFrame", P.surface, P.surface, border=P.border_subtle, radius=M.radius)
    _frame_style(style, "Feedback.TFrame", P.surface_subtle, P.surface, border=P.border_subtle, radius=M.radius)
    _frame_style(style, "Hint.TFrame", P.sunken, P.canvas, radius=M.radius)
    _frame_style(style, "Callout.TFrame", P.accent_subtle, P.canvas, border=P.accent_border, radius=M.radius)
    _frame_style(style, "Segmented.TFrame", P.sunken, P.surface, radius=M.radius + 1)
    _frame_style(style, "CanvasSegmented.TFrame", P.hover, P.canvas, radius=M.radius + 1)
    _control_element(style, "Command.TFrame.box", _box(P.field, P.border),
                     ("hover", _box(P.field, P.border_strong)))
    style.layout("Command.TFrame", [("Command.TFrame.box", {"sticky": "nsew"})])
    style.configure("Command.TFrame", background=P.canvas)
    INTERIOR["Command.TFrame"] = P.field
    _control_element(style, "CommandFocus.TFrame.box", _box(P.field, P.accent, ring=P.focus_ring))
    style.layout("CommandFocus.TFrame", [("CommandFocus.TFrame.box", {"sticky": "nsew"})])
    style.configure("CommandFocus.TFrame", background=P.canvas)
    INTERIOR["CommandFocus.TFrame"] = P.field

    # ── Text ──
    def text(name, bg, fg, role, **extra):
        style.configure(name, background=bg, foreground=fg, font=font(role), **extra)

    text("SidebarBrand.TLabel", P.sidebar, P.text, "heading", space=10)
    text("SidebarMeta.TLabel", P.sidebar, P.text_tertiary, "small", space=6)
    text("SidebarSection.TLabel", P.sidebar, P.text_tertiary, "micro")
    text("PageEyebrow.TLabel", P.canvas, P.text_tertiary, "micro")
    text("PageTitle.TLabel", P.canvas, P.text, "display")
    text("PageBody.TLabel", P.canvas, P.text_secondary, "body")
    text("HintIcon.TLabel", P.sunken, P.text_tertiary, "body")
    text("HintStrip.TLabel", P.sunken, P.text_secondary, "small")
    text("CalloutText.TLabel", P.accent_subtle, P.text, "body")
    text("CalloutIcon.TLabel", P.accent_subtle, P.accent_text, "body")
    text("CardTitle.TLabel", P.surface, P.text, "title")
    text("Section.TLabel", P.surface, P.text, "heading")
    text("Field.TLabel", P.surface, P.text_secondary, "label")
    text("Hint.TLabel", P.surface, P.text_tertiary, "small")
    text("Body.TLabel", P.surface, P.text, "body")
    text("PageInfo.TLabel", P.surface, P.accent_text, "small_strong")
    text("StatusTitle.TLabel", P.surface_subtle, P.text, "body_strong")
    text("StatusBody.TLabel", P.surface_subtle, P.text_secondary, "small")
    text("PreviewTitle.TLabel", P.surface, P.text, "heading")
    text("PreviewName.TLabel", P.surface, P.text, "body_strong")
    text("PreviewMeta.TLabel", P.surface, P.text_secondary, "small")
    text("PreviewPath.TLabel", P.surface, P.text_tertiary, "small")

    # ── Inputs ──
    _control_element(style, "Input.field", _box(P.field, P.border),
                     ("disabled", _box(P.sunken, P.border_subtle)),
                     ("focus", _box(P.field, P.accent, ring=P.focus_ring)),
                     ("hover", _box(P.field, P.border_strong)))
    style.element_create("Plain.field", "image", _panel(P.field, None, 0), border=3, padding=0,
                         width=6, height=6, sticky="nsew")
    for name, field in (("Input.TEntry", "Input.field"), ("Command.TEntry", "Plain.field")):
        style.layout(name, [(field, {"sticky": "nsew", "children": [
            ("Entry.padding", {"sticky": "nsew", "children": [
                ("Entry.textarea", {"sticky": "nsew"})]})]})])
    style.configure("Input.TEntry", background=P.surface, foreground=P.text,
                    fieldbackground=P.field, insertcolor=P.text, padding=(10, 6),
                    selectbackground=P.accent_subtle_hover, selectforeground=P.text)
    style.map("Input.TEntry", foreground=[("disabled", P.text_disabled)])
    # Borderless entry that sits inside the Command frame.
    style.configure("Command.TEntry", background=P.field, fieldbackground=P.field,
                    foreground=P.text, insertcolor=P.text, padding=(10, 5),
                    borderwidth=0, bordercolor=P.field, lightcolor=P.field, darkcolor=P.field,
                    selectbackground=P.accent_subtle_hover, selectforeground=P.text)
    style.map("Command.TEntry", foreground=[("disabled", P.text_disabled)])
    # The same entry while it shows its placeholder.
    style.layout("CommandHint.TEntry", style.layout("Command.TEntry"))
    style.configure("CommandHint.TEntry", **{k: style.lookup("Command.TEntry", k) for k in (
        "background", "fieldbackground", "insertcolor", "padding", "borderwidth")})
    style.configure("CommandHint.TEntry", foreground=P.text_tertiary)

    arrow = _img(("chev", "down", P.text_secondary), lambda: chevron(20, 14, P.text_secondary, "down"))
    arrow_off = _img(("chev", "down", P.text_disabled), lambda: chevron(20, 14, P.text_disabled, "down"))
    up = _img(("chev", "up", P.text_secondary), lambda: chevron(18, 11, P.text_secondary, "up"))
    down = _img(("chev", "down-s", P.text_secondary), lambda: chevron(18, 11, P.text_secondary, "down"))
    style.element_create("Input.arrow", "image", arrow, ("disabled", arrow_off), sticky="", padding=(0, 0, 6, 0))
    style.element_create("Input.uparrow", "image", up, sticky="", padding=(0, 2, 6, 0))
    style.element_create("Input.downarrow", "image", down, sticky="", padding=(0, 0, 6, 2))

    style.layout("Input.TCombobox", [("Input.field", {"sticky": "nsew", "children": [
        ("Input.arrow", {"side": "right", "sticky": "ns"}),
        ("Combobox.padding", {"sticky": "nsew", "children": [
            ("Combobox.textarea", {"sticky": "nsew"})]})]})])
    style.configure("Input.TCombobox", background=P.surface, foreground=P.text,
                    fieldbackground=P.field, padding=(10, 6), arrowsize=0,
                    selectbackground=P.field, selectforeground=P.text, insertcolor=P.text)
    style.map("Input.TCombobox",
              fieldbackground=[("readonly", P.field)],
              selectbackground=[("readonly", P.field)],
              selectforeground=[("readonly", P.text)],
              foreground=[("disabled", P.text_disabled)])

    style.layout("Input.TSpinbox", [("Input.field", {"sticky": "nsew", "children": [
        ("null", {"side": "right", "sticky": "ns", "children": [
            ("Input.uparrow", {"side": "top", "sticky": "e"}),
            ("Input.downarrow", {"side": "bottom", "sticky": "e"})]}),
        ("Spinbox.padding", {"sticky": "nsew", "children": [
            ("Spinbox.textarea", {"sticky": "nsew"})]})]})])
    style.configure("Input.TSpinbox", background=P.surface, foreground=P.text,
                    fieldbackground=P.field, padding=(10, 6), insertcolor=P.text,
                    selectbackground=P.accent_subtle_hover, selectforeground=P.text)
    style.map("Input.TSpinbox", foreground=[("disabled", P.text_disabled)])

    # ── Buttons ──
    _configure_button(style, "Primary.TButton", P.surface, P.accent, P.accent_hover,
                      P.accent_pressed, P.text_on_accent, disabled_fill=P.sunken,
                      disabled_border=P.sunken, padding=(18, M.control_pad_y + 1))
    _configure_button(style, "Danger.TButton", P.surface, P.danger, P.danger_hover,
                      P.danger_hover, P.text_on_accent, disabled_fill=P.sunken)
    _configure_button(style, "Secondary.TButton", P.surface, P.surface, P.surface_subtle,
                      P.sunken, P.text, border=P.border, border_hover=P.border_strong,
                      disabled_fill=P.surface, disabled_border=P.border_subtle)
    _configure_button(style, "Ghost.TButton", P.surface, P.surface, P.hover, P.pressed,
                      P.text_secondary, fg_hover=P.text, disabled_fill=P.surface)
    _configure_button(style, "Small.TButton", P.surface, P.surface, P.surface_subtle,
                      P.sunken, P.text, border=P.border, border_hover=P.border_strong,
                      disabled_fill=P.surface, disabled_border=P.border_subtle,
                      padding=(10, 4), font_role="small")
    # Same roles on the subtle status panel.
    _configure_button(style, "Feedback.Secondary.TButton", P.surface_subtle, P.surface, P.surface,
                      P.sunken, P.text, border=P.border, border_hover=P.border_strong,
                      disabled_fill=P.surface_subtle, disabled_border=P.border_subtle,
                      padding=(12, 5), font_role="small_strong")
    _configure_button(style, "Feedback.Ghost.TButton", P.surface_subtle, P.surface_subtle, P.hover,
                      P.pressed, P.text_secondary, fg_hover=P.text,
                      padding=(12, 5), font_role="small_strong")
    # Window chrome on the canvas.
    _configure_button(style, "Canvas.Secondary.TButton", P.canvas, P.surface, P.surface_subtle,
                      P.sunken, P.text, border=P.border, border_hover=P.border_strong)
    _configure_button(style, "CalloutClose.TButton", P.accent_subtle, P.accent_subtle,
                      P.accent_subtle_hover, P.accent_border, P.accent_text, padding=(4, 2),
                      font_role="small")
    # Voice button lives inside the command field.
    _configure_button(style, "Voice.TButton", P.field, P.field, P.hover, P.pressed,
                      P.text_secondary, fg_hover=P.text, padding=(10, 4), font_role="small_strong",
                      disabled_fill=P.field)
    _configure_button(style, "VoiceActive.TButton", P.field, P.danger_bg, P.danger_bg,
                      P.danger_bg, P.danger, border=P.danger_border, padding=(10, 4),
                      font_role="small_strong")

    # Sidebar navigation.
    _configure_button(style, "Nav.TButton", P.sidebar, P.sidebar, P.hover, P.pressed,
                      P.text_secondary, fg_hover=P.text, selected=P.surface,
                      selected_border=P.border_subtle, selected_fg=P.text,
                      padding=(10, 7), font_role="body", anchor="w")
    style.configure("Nav.TButton", compound="left", space=10)
    _configure_button(style, "NavFile.TButton", P.sidebar, P.sidebar, P.hover, P.pressed,
                      P.text_secondary, fg_hover=P.text, padding=(10, 4), font_role="small",
                      anchor="w")
    style.configure("NavFile.TButton", compound="left", space=8)
    for name in ("Feedback.Secondary.TButton", "Feedback.Ghost.TButton", "Voice.TButton",
                 "VoiceActive.TButton", "Secondary.TButton", "Ghost.TButton", "Small.TButton",
                 "Primary.TButton"):
        style.configure(name, space=6)

    # Segmented controls: the group switch on the canvas and mode pickers in cards.
    for prefix, track in (("", P.sunken), ("Canvas", P.hover)):
        _configure_button(style, f"{prefix}Segment.TButton", track, track, P.pressed if prefix else P.hover,
                          P.pressed, P.text_secondary, fg_hover=P.text, selected=P.surface,
                          selected_border=P.border_subtle, selected_fg=P.text,
                          padding=(12, 5), font_role="label", radius=M.radius - 1)

    # ── Check & radio ──
    size = 18
    cb = lambda fill, border, mark=None: _img(  # noqa: E731
        ("cb", fill, border, mark), lambda: _pad_img(check_box(size, M.radius_sm, fill, border, mark)))
    rb = lambda fill, border, dot=None: _img(  # noqa: E731
        ("rb", fill, border, dot), lambda: _pad_img(radio_dot(size, fill, border, dot)))
    style.element_create("Check.indicator", "image", cb(P.field, P.border_strong),
                         ("disabled selected", cb(P.sunken, P.border, P.text_disabled)),
                         ("disabled", cb(P.sunken, P.border)),
                         ("pressed selected", cb(P.accent_pressed, P.accent_pressed, P.text_on_accent)),
                         ("active selected", cb(P.accent_hover, P.accent_hover, P.text_on_accent)),
                         ("selected", cb(P.accent, P.accent, P.text_on_accent)),
                         ("active", cb(P.surface_subtle, P.text_tertiary)),
                         sticky="", padding=(0, 0, 8, 0))
    style.element_create("Radio.indicator", "image", rb(P.field, P.border_strong),
                         ("disabled selected", rb(P.sunken, P.border, P.text_disabled)),
                         ("disabled", rb(P.sunken, P.border)),
                         ("active selected", rb(P.accent_hover, P.accent_hover, P.text_on_accent)),
                         ("selected", rb(P.accent, P.accent, P.text_on_accent)),
                         ("active", rb(P.surface_subtle, P.text_tertiary)),
                         sticky="", padding=(0, 0, 8, 0))
    for name, indicator in (("Flat.TCheckbutton", "Check.indicator"),
                            ("Flat.TRadiobutton", "Radio.indicator")):
        style.layout(name, [("Checkbutton.padding", {"sticky": "nsew", "children": [
            (indicator, {"side": "left", "sticky": ""}),
            ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
                ("Checkbutton.label", {"sticky": "nsew"})]})]})])
        style.configure(name, background=P.surface, foreground=P.text, font=body,
                        padding=(0, 4), focuscolor=P.surface)
        style.map(name, background=[("active", P.surface)],
                  foreground=[("disabled", P.text_disabled)])

    # ── Progress ──
    trough = _img(("pill", P.sunken), lambda: rounded_box(STRETCH, 6, 3, P.sunken))
    bar = _img(("pill", P.accent), lambda: rounded_box(STRETCH, 6, 3, P.accent))
    bar_done = _img(("pill", P.success), lambda: rounded_box(STRETCH, 6, 3, P.success))
    pill = dict(border=(3, 0), padding=0, width=6, height=6)
    style.element_create("Aura.trough", "image", trough, sticky="ew", **pill)
    style.element_create("Aura.pbar", "image", bar, sticky="nsew", **pill)
    style.element_create("Done.pbar", "image", bar_done, sticky="nsew", **pill)
    for name, pbar in (("Accent.Horizontal.TProgressbar", "Aura.pbar"),
                       ("Done.Horizontal.TProgressbar", "Done.pbar")):
        style.layout(name, [("Aura.trough", {"sticky": "nsew", "children": [
            (pbar, {"side": "left", "sticky": "ns"})]})])
        style.configure(name, background=P.surface, thickness=6)

    # ── Scrollbars: a slim pill thumb on a plain trough ──
    for prefix, bg, rest, hot in (("", P.surface, P.border, P.border_strong),
                                  ("Canvas.", P.canvas, P.border, P.border_strong),
                                  ("Stage.", P.stage, P.text_secondary, P.text_tertiary)):
        thumb = _img(("thumb", rest), lambda rest=rest: _pad_img(rounded_box(8, STRETCH, 4, rest), 2))
        thumb_hover = _img(("thumb", hot), lambda hot=hot: _pad_img(rounded_box(8, STRETCH, 4, hot), 2))
        el = f"{prefix}Aura.vthumb"
        style.element_create(el, "image", thumb, ("active", thumb_hover), ("pressed", thumb_hover),
                             border=(0, 6), padding=0, width=12, height=20, sticky="ns")
        style.layout(f"{prefix}Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {
            "sticky": "ns", "children": [(el, {"expand": "1", "sticky": "nswe"})]})])
        style.configure(f"{prefix}Vertical.TScrollbar", troughcolor=bg, background=bg,
                        bordercolor=bg, lightcolor=bg, darkcolor=bg, arrowsize=0, width=12)
        hthumb = _img(("hthumb", rest), lambda rest=rest: _pad_img(rounded_box(STRETCH, 8, 4, rest), 2))
        hthumb_hover = _img(("hthumb", hot), lambda hot=hot: _pad_img(rounded_box(STRETCH, 8, 4, hot), 2))
        el = f"{prefix}Aura.hthumb"
        style.element_create(el, "image", hthumb, ("active", hthumb_hover), ("pressed", hthumb_hover),
                             border=(6, 0), padding=0, width=20, height=12, sticky="ew")
        style.layout(f"{prefix}Horizontal.TScrollbar", [("Horizontal.Scrollbar.trough", {
            "sticky": "ew", "children": [(el, {"expand": "1", "sticky": "nswe"})]})])
        style.configure(f"{prefix}Horizontal.TScrollbar", troughcolor=bg, background=bg,
                        bordercolor=bg, lightcolor=bg, darkcolor=bg, arrowsize=0, width=12)

    # ── Notebook, treeview ──
    tab_off = _img(("tab", "off"), lambda: _tab_image(P.canvas, P.border_subtle, 1))
    tab_on = _img(("tab", "on"), lambda: _tab_image(P.canvas, P.accent, 2))
    tab_hover = _img(("tab", "hover"), lambda: _tab_image(P.canvas, P.border_strong, 1))
    style.element_create("Aura.tab", "image", tab_off, ("selected", tab_on), ("active", tab_hover),
                         border=(2, 2, 2, 3), padding=0, width=8, height=4, sticky="nsew")
    style.layout("Tabs.TNotebook.Tab", [("Aura.tab", {"sticky": "nsew", "children": [
        ("Notebook.padding", {"sticky": "nsew", "children": [
            ("Notebook.label", {"sticky": ""})]})]})])
    style.configure("Tabs.TNotebook", background=P.canvas, borderwidth=0, tabmargins=(0, 0, 0, 12),
                    bordercolor=P.canvas, lightcolor=P.canvas, darkcolor=P.canvas)
    style.configure("Tabs.TNotebook.Tab", background=P.canvas, foreground=P.text_secondary,
                    padding=(4, 8, 4, 8), font=font("body_strong"))
    style.map("Tabs.TNotebook.Tab",
              foreground=[("selected", P.text), ("active", P.text)],
              expand=[("selected", (0, 0, 0, 0))])
    style.layout("Tabs.TNotebook", [("Notebook.client", {"sticky": "nsew"})])

    style.configure("Treeview", background=P.surface, fieldbackground=P.surface,
                    foreground=P.text, rowheight=32, font=body, borderwidth=0,
                    bordercolor=P.border_subtle, lightcolor=P.surface, darkcolor=P.surface)
    style.map("Treeview", background=[("selected", P.accent_subtle_hover)],
              foreground=[("selected", P.text)])
    style.configure("Treeview.Heading", background=P.surface_subtle, foreground=P.text_secondary,
                    font=label, relief="flat", padding=(8, 7), bordercolor=P.border_subtle,
                    lightcolor=P.surface_subtle, darkcolor=P.border_subtle)
    style.map("Treeview.Heading", background=[("active", P.sunken)])
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    return style


def _pad_img(img, margin=2):
    """Add a transparent margin so small images keep a hit area and line up
    with the ring-padded buttons."""
    w, h = img.size
    out = Image.new("RGBA", (w + margin * 2, h + margin * 2), (0, 0, 0, 0))
    out.paste(img, (margin, margin))
    return out


def _tab_image(bg, line, thickness):
    img = Image.new("RGBA", (STRETCH, 8), bg)
    ImageDraw.Draw(img).rectangle((0, 8 - thickness, STRETCH - 1, 7), fill=line)
    return img
