from tkinter import ttk

# Core palette
APP_BG = "#f4efe8"
SIDEBAR_BG = "#142132"
SIDEBAR_ACTIVE = "#1f334d"
SIDEBAR_HOVER = "#223a58"
SURFACE_COLOR = "#ffffff"
SURFACE_ALT = "#f7f9fc"
FIELD_COLOR = "#fbfdff"
BORDER_COLOR = "#d8e0ea"
TEXT_COLOR = "#18212b"
MUTED_TEXT = "#627285"
PREVIEW_BG = "#ecf2f8"
PROGRESS_TROUGH = "#dde6f0"

# Accents
PRIMARY_ACCENT = "#0f766e"
PRIMARY_HOVER = "#0b5f58"
SPLIT_ACCENT = "#0f766e"
MERGE_ACCENT = "#1570ef"
EDIT_ACCENT = "#c77d1c"
CONVERT_ACCENT = "#c05a0e"
SECURITY_ACCENT = "#c2410c"
SUCCESS_ACCENT = "#15803d"
WARNING_ACCENT = "#b45309"
ERROR_ACCENT = "#b42318"
VOICE_ACCENT = "#8b5cf6"
VOICE_HOVER = "#7c3aed"
VOICE_ACTIVE = "#ef4444"


def _configure_button(style, name, background, hover, foreground="#ffffff", padding=(14, 10), font=None):
    style.configure(
        name,
        background=background,
        foreground=foreground,
        borderwidth=0,
        focusthickness=0,
        padding=padding,
        font=font or ("Segoe UI Semibold", 10),
    )
    style.map(
        name,
        background=[("active", hover), ("disabled", "#c7d0db")],
        foreground=[("disabled", "#7e8b99")],
    )


def setup_styles():
    style = ttk.Style()
    style.theme_use("clam")

    style.configure(".", background=APP_BG, foreground=TEXT_COLOR, font=("Segoe UI", 10))
    style.configure("App.TFrame", background=APP_BG)
    style.configure("Content.TFrame", background=APP_BG)
    style.configure("Sidebar.TFrame", background=SIDEBAR_BG)
    style.configure("Surface.TFrame", background=SURFACE_COLOR, borderwidth=1, relief="solid", bordercolor=BORDER_COLOR)
    style.configure("Panel.TFrame", background=SURFACE_ALT, borderwidth=1, relief="solid", bordercolor=BORDER_COLOR)
    style.configure("Hero.TFrame", background="#eef5f3", borderwidth=1, relief="solid", bordercolor="#cfe3dd")
    style.configure("Preview.TFrame", background=PREVIEW_BG, borderwidth=1, relief="solid", bordercolor="#d3dfeb")

    style.configure("SidebarBrand.TLabel", background=SIDEBAR_BG, foreground="#f8fbff", font=("Bahnschrift SemiBold", 18))
    style.configure("SidebarMeta.TLabel", background=SIDEBAR_BG, foreground="#9ab0c7", font=("Segoe UI", 9))
    style.configure("SidebarSection.TLabel", background=SIDEBAR_BG, foreground="#87a1bb", font=("Segoe UI Semibold", 9))

    style.configure("PageEyebrow.TLabel", background=APP_BG, foreground=PRIMARY_ACCENT, font=("Segoe UI Semibold", 9))
    style.configure("PageTitle.TLabel", background=APP_BG, foreground=TEXT_COLOR, font=("Bahnschrift SemiBold", 22))
    style.configure("PageBody.TLabel", background=APP_BG, foreground=MUTED_TEXT, font=("Segoe UI", 10))
    style.configure("HeroEyebrow.TLabel", background="#eef5f3", foreground=PRIMARY_ACCENT, font=("Segoe UI Semibold", 9))
    style.configure("HeroTitle.TLabel", background="#eef5f3", foreground=TEXT_COLOR, font=("Bahnschrift SemiBold", 18))
    style.configure("HeroBody.TLabel", background="#eef5f3", foreground=MUTED_TEXT, font=("Segoe UI", 10))
    style.configure("CardTitle.TLabel", background=SURFACE_COLOR, foreground=TEXT_COLOR, font=("Segoe UI Semibold", 12))
    style.configure("CardBody.TLabel", background=SURFACE_COLOR, foreground=MUTED_TEXT, font=("Segoe UI", 10))
    style.configure("Section.TLabel", background=SURFACE_COLOR, foreground=TEXT_COLOR, font=("Segoe UI Semibold", 12))
    style.configure("Field.TLabel", background=SURFACE_COLOR, foreground=MUTED_TEXT, font=("Segoe UI Semibold", 9))
    style.configure("Hint.TLabel", background=SURFACE_COLOR, foreground=MUTED_TEXT, font=("Segoe UI", 9))
    style.configure("StatusTitle.TLabel", background=SURFACE_ALT, foreground=TEXT_COLOR, font=("Segoe UI Semibold", 11))
    style.configure("StatusBody.TLabel", background=SURFACE_ALT, foreground=MUTED_TEXT, font=("Segoe UI", 9))
    style.configure("PreviewTitle.TLabel", background=PREVIEW_BG, foreground=TEXT_COLOR, font=("Segoe UI Semibold", 11))
    style.configure("PreviewMeta.TLabel", background=PREVIEW_BG, foreground=MUTED_TEXT, font=("Segoe UI", 9))
    style.configure("Badge.TLabel", background="#e6f2ef", foreground=PRIMARY_ACCENT, font=("Segoe UI Semibold", 9), padding=(10, 4))
    style.configure("PageInfo.TLabel", background=SURFACE_COLOR, foreground=PRIMARY_ACCENT, font=("Segoe UI Semibold", 10))

    style.configure(
        "Dark.TEntry",
        fieldbackground=FIELD_COLOR,
        foreground=TEXT_COLOR,
        bordercolor=BORDER_COLOR,
        lightcolor=BORDER_COLOR,
        darkcolor=BORDER_COLOR,
        insertcolor=TEXT_COLOR,
        padding=9,
    )
    style.map(
        "Dark.TEntry",
        fieldbackground=[("disabled", "#eff3f7"), ("!disabled", FIELD_COLOR)],
        foreground=[("disabled", "#8a96a4"), ("!disabled", TEXT_COLOR)],
    )

    style.configure(
        "Dark.TCombobox",
        fieldbackground=FIELD_COLOR,
        background=FIELD_COLOR,
        foreground=TEXT_COLOR,
        bordercolor=BORDER_COLOR,
        lightcolor=BORDER_COLOR,
        darkcolor=BORDER_COLOR,
        arrowcolor=TEXT_COLOR,
        padding=7,
    )
    style.map(
        "Dark.TCombobox",
        fieldbackground=[("readonly", FIELD_COLOR), ("disabled", "#eff3f7")],
        foreground=[("readonly", TEXT_COLOR), ("disabled", "#8a96a4")],
        arrowcolor=[("readonly", TEXT_COLOR), ("disabled", "#8a96a4")],
    )

    style.configure(
        "Dark.TSpinbox",
        fieldbackground=FIELD_COLOR,
        background=FIELD_COLOR,
        foreground=TEXT_COLOR,
        bordercolor=BORDER_COLOR,
        lightcolor=BORDER_COLOR,
        darkcolor=BORDER_COLOR,
        insertcolor=TEXT_COLOR,
        arrowcolor=TEXT_COLOR,
        padding=7,
    )
    style.map(
        "Dark.TSpinbox",
        fieldbackground=[("disabled", "#eff3f7"), ("!disabled", FIELD_COLOR)],
        foreground=[("disabled", "#8a96a4"), ("!disabled", TEXT_COLOR)],
        arrowcolor=[("disabled", "#8a96a4"), ("!disabled", TEXT_COLOR)],
    )

    _configure_button(style, "Primary.TButton", PRIMARY_ACCENT, PRIMARY_HOVER)
    _configure_button(style, "Accent.TButton", PRIMARY_ACCENT, PRIMARY_HOVER)
    _configure_button(style, "Split.TButton", SPLIT_ACCENT, PRIMARY_HOVER)
    _configure_button(style, "Merge.TButton", MERGE_ACCENT, "#175cd3")
    _configure_button(style, "Edit.TButton", EDIT_ACCENT, "#a86112")
    _configure_button(style, "Convert.TButton", CONVERT_ACCENT, "#9d4d10")
    _configure_button(style, "Security.TButton", SECURITY_ACCENT, "#9f3a0e")
    _configure_button(style, "Danger.TButton", ERROR_ACCENT, "#912018")
    _configure_button(style, "Voice.TButton", VOICE_ACCENT, VOICE_HOVER, padding=(12, 10))
    _configure_button(style, "VoiceActive.TButton", VOICE_ACTIVE, "#cd1f1f", padding=(12, 10))

    _configure_button(style, "Nav.TButton", SIDEBAR_BG, SIDEBAR_HOVER, foreground="#d9e6f2", padding=(16, 11), font=("Segoe UI Semibold", 10))
    _configure_button(style, "NavSelected.TButton", SIDEBAR_ACTIVE, "#28425f", foreground="#ffffff", padding=(16, 11), font=("Segoe UI Semibold", 10))
    _configure_button(style, "Subnav.TButton", "#eaf0f6", "#dde8f2", foreground=TEXT_COLOR, padding=(12, 8), font=("Segoe UI Semibold", 9))
    _configure_button(style, "SubnavSelected.TButton", "#d8ece9", "#cae5e0", foreground=PRIMARY_ACCENT, padding=(12, 8), font=("Segoe UI Semibold", 9))
    _configure_button(style, "Ghost.TButton", SURFACE_ALT, "#e8edf3", foreground=TEXT_COLOR, padding=(12, 9), font=("Segoe UI", 10))
    _configure_button(style, "Secondary.TButton", SURFACE_ALT, "#e8edf3", foreground=TEXT_COLOR, padding=(12, 9), font=("Segoe UI", 10))
    _configure_button(style, "Small.TButton", SURFACE_ALT, "#e8edf3", foreground=TEXT_COLOR, padding=(9, 6), font=("Segoe UI", 9))

    style.configure(
        "Flat.TCheckbutton",
        background=SURFACE_COLOR,
        foreground=TEXT_COLOR,
        font=("Segoe UI", 10),
        indicatorcolor=SURFACE_COLOR,
        indicatormargin=4,
    )
    style.map("Flat.TCheckbutton", background=[("active", SURFACE_COLOR)], foreground=[("active", TEXT_COLOR)])
    style.configure(
        "Flat.TRadiobutton",
        background=SURFACE_COLOR,
        foreground=TEXT_COLOR,
        font=("Segoe UI", 10),
        indicatorcolor=SURFACE_COLOR,
        indicatormargin=4,
    )
    style.map("Flat.TRadiobutton", background=[("active", SURFACE_COLOR)], foreground=[("active", TEXT_COLOR)])

    for name, accent in [
        ("Accent", PRIMARY_ACCENT),
        ("Split", SPLIT_ACCENT),
        ("Merge", MERGE_ACCENT),
        ("Edit", EDIT_ACCENT),
        ("Convert", CONVERT_ACCENT),
        ("Security", SECURITY_ACCENT),
        ("Primary", PRIMARY_ACCENT),
    ]:
        style.configure(
            f"{name}.Horizontal.TProgressbar",
            troughcolor=PROGRESS_TROUGH,
            background=accent,
            bordercolor=PROGRESS_TROUGH,
            lightcolor=accent,
            darkcolor=accent,
            thickness=10,
        )

    style.configure("Dark.TNotebook", background=APP_BG, borderwidth=0)
    style.configure("Dark.TNotebook.Tab", background=SURFACE_ALT, foreground=MUTED_TEXT, padding=(14, 9), font=("Segoe UI Semibold", 10))
    style.map(
        "Dark.TNotebook.Tab",
        background=[("selected", SURFACE_COLOR), ("active", "#edf3f9")],
        foreground=[("selected", TEXT_COLOR), ("active", TEXT_COLOR)],
    )
