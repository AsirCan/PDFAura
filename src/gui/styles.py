from tkinter import ttk

# Theme colors
BG_COLOR = "#1e1e1e"
CARD_COLOR = "#252526"
FIELD_COLOR = "#2d2d30"
BORDER_COLOR = "#3c3c3c"
TEXT_COLOR = "#f3f3f3"
MUTED_TEXT = "#9da5b4"
PROGRESS_TROUGH = "#1b1b1c"

# Tab accent colors
COMPRESS_ACCENT = "#0e639c"
COMPRESS_HOVER = "#1177bb"
SPLIT_ACCENT = "#8b5cf6"
SPLIT_HOVER = "#7c3aed"
MERGE_ACCENT = "#10b981"
MERGE_HOVER = "#059669"
EDIT_ACCENT = "#f59e0b"
EDIT_HOVER = "#d97706"
CONVERT_ACCENT = "#ec4899"
CONVERT_HOVER = "#db2777"
SECURITY_ACCENT = "#ef4444" 

def setup_styles():
    style = ttk.Style()
    style.theme_use("clam")

    style.configure(".", background=BG_COLOR, foreground=TEXT_COLOR, font=("Segoe UI", 10))
    style.configure("App.TFrame", background=BG_COLOR)
    style.configure("Card.TFrame", background=CARD_COLOR, borderwidth=1, relief="solid", bordercolor=BORDER_COLOR)

    # Label styles
    style.configure("Title.TLabel", background=BG_COLOR, foreground=TEXT_COLOR, font=("Segoe UI Semibold", 20))
    style.configure("Subtitle.TLabel", background=BG_COLOR, foreground=MUTED_TEXT, font=("Segoe UI", 10))
    style.configure("Section.TLabel", background=CARD_COLOR, foreground=TEXT_COLOR, font=("Segoe UI Semibold", 11))
    style.configure("Field.TLabel", background=CARD_COLOR, foreground=MUTED_TEXT, font=("Segoe UI", 10))
    style.configure("Hint.TLabel", background=CARD_COLOR, foreground=MUTED_TEXT, font=("Segoe UI", 9))
    style.configure("Status.TLabel", background=CARD_COLOR, foreground="#75beff", font=("Segoe UI", 10))
    style.configure("SplitStatus.TLabel", background=CARD_COLOR, foreground="#a78bfa", font=("Segoe UI", 10))
    style.configure("MergeStatus.TLabel", background=CARD_COLOR, foreground="#6ee7b7", font=("Segoe UI", 10))
    style.configure("EditStatus.TLabel", background=CARD_COLOR, foreground="#fcd34d", font=("Segoe UI", 10))
    style.configure("ConvertStatus.TLabel", background=CARD_COLOR, foreground="#f9a8d4", font=("Segoe UI", 10))
    style.configure("SecurityStatus.TLabel", background=CARD_COLOR, foreground="#fca5a5", font=("Segoe UI", 10))
    style.configure("PageInfo.TLabel", background=CARD_COLOR, foreground="#4ade80", font=("Segoe UI Semibold", 10))

    # Entry style
    style.configure("Dark.TEntry", fieldbackground=FIELD_COLOR, foreground=TEXT_COLOR,
                     bordercolor=BORDER_COLOR, lightcolor=BORDER_COLOR, darkcolor=BORDER_COLOR,
                     insertcolor=TEXT_COLOR, padding=8)
    style.map("Dark.TEntry",
               fieldbackground=[("disabled", "#232325"), ("!disabled", FIELD_COLOR)],
               foreground=[("disabled", "#7a7a7a"), ("!disabled", TEXT_COLOR)])

    # Combobox style
    style.configure("Dark.TCombobox", fieldbackground=FIELD_COLOR, background=FIELD_COLOR,
                     foreground=TEXT_COLOR, bordercolor=BORDER_COLOR, lightcolor=BORDER_COLOR,
                     darkcolor=BORDER_COLOR, arrowcolor=TEXT_COLOR, padding=6)
    style.map("Dark.TCombobox",
               fieldbackground=[("readonly", FIELD_COLOR), ("disabled", "#232325")],
               foreground=[("readonly", TEXT_COLOR), ("disabled", "#7a7a7a")],
               arrowcolor=[("readonly", TEXT_COLOR), ("disabled", "#7a7a7a")])

    # Spinbox style
    style.configure("Dark.TSpinbox", fieldbackground=FIELD_COLOR, background=FIELD_COLOR,
                     foreground=TEXT_COLOR, bordercolor=BORDER_COLOR, lightcolor=BORDER_COLOR,
                     darkcolor=BORDER_COLOR, insertcolor=TEXT_COLOR, arrowcolor=TEXT_COLOR, padding=6)
    style.map("Dark.TSpinbox",
               fieldbackground=[("disabled", "#232325"), ("!disabled", FIELD_COLOR)],
               foreground=[("disabled", "#7a7a7a"), ("!disabled", TEXT_COLOR)],
               arrowcolor=[("disabled", "#7a7a7a"), ("!disabled", TEXT_COLOR)])

    # Button styles
    for name, accent, hover in [
        ("Accent", COMPRESS_ACCENT, COMPRESS_HOVER),
        ("Split", SPLIT_ACCENT, SPLIT_HOVER),
        ("Merge", MERGE_ACCENT, MERGE_HOVER),
        ("Edit", EDIT_ACCENT, EDIT_HOVER),
        ("Convert", CONVERT_ACCENT, CONVERT_HOVER),
        ("Security", SECURITY_ACCENT, "#dc2626"),
    ]:
        style.configure(f"{name}.TButton", background=accent, foreground=TEXT_COLOR,
                         borderwidth=0, focusthickness=0, padding=(14, 9),
                         font=("Segoe UI Semibold", 10))
        style.map(f"{name}.TButton",
                   background=[("active", hover), ("disabled", "#3a3d41")],
                   foreground=[("disabled", "#80858d")])

    style.configure("Secondary.TButton", background="#333337", foreground=TEXT_COLOR,
                     borderwidth=0, focusthickness=0, padding=(12, 8), font=("Segoe UI", 10))
    style.map("Secondary.TButton",
               background=[("active", "#3f3f46"), ("disabled", "#2a2a2d")],
               foreground=[("disabled", "#80858d")])

    style.configure("Small.TButton", background="#333337", foreground=TEXT_COLOR,
                     borderwidth=0, focusthickness=0, padding=(8, 5), font=("Segoe UI", 9))
    style.map("Small.TButton",
               background=[("active", "#3f3f46"), ("disabled", "#2a2a2d")],
               foreground=[("disabled", "#80858d")])

    # Progress bar styles
    for name, accent in [
        ("Accent", COMPRESS_ACCENT), ("Split", SPLIT_ACCENT),
        ("Merge", MERGE_ACCENT), ("Edit", EDIT_ACCENT), 
        ("Convert", CONVERT_ACCENT), ("Security", SECURITY_ACCENT)
    ]:
        style.configure(f"{name}.Horizontal.TProgressbar",
                         troughcolor=PROGRESS_TROUGH, background=accent,
                         bordercolor=PROGRESS_TROUGH, lightcolor=accent, darkcolor=accent, thickness=8)

    # Notebook style
    style.configure("Dark.TNotebook", background=BG_COLOR, borderwidth=0)
    style.configure("Dark.TNotebook.Tab", background="#2d2d30", foreground=MUTED_TEXT,
                     padding=(16, 10), font=("Segoe UI Semibold", 10), borderwidth=0)
    style.map("Dark.TNotebook.Tab",
               background=[("selected", CARD_COLOR), ("active", "#383838")],
               foreground=[("selected", TEXT_COLOR), ("active", TEXT_COLOR)],
               expand=[("selected", [0, 0, 0, 2])])
