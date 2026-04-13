import tkinter as tk
from tkinter import ttk, filedialog

from src.core.config_manager import cfg
from src.core.lang_manager import _
from src.gui.helpers import InlineFeedback


class SettingsPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="App.TFrame")
        self.lang_var = tk.StringVar(value=cfg.get("language", "tr"))
        self.tray_var = tk.BooleanVar(value=cfg.get("close_to_tray", True))
        self.sound_var = tk.BooleanVar(value=cfg.get("sound_enabled", True))
        self.out_dir_var = tk.StringVar(value=cfg.get("default_output_dir", ""))
        self.build_ui()

    def build_ui(self):
        hero = ttk.Frame(self, style="Hero.TFrame", padding=22)
        hero.pack(fill="x")
        ttk.Label(hero, text=_("txt_settings"), style="HeroEyebrow.TLabel").pack(anchor="w")
        ttk.Label(hero, text=_("settings_appearance"), style="HeroTitle.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(
            hero,
            text=_("settings_saved"),
            style="HeroBody.TLabel",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        body = ttk.Frame(self, style="App.TFrame")
        body.pack(fill="both", expand=True, pady=(18, 0))

        left = ttk.Frame(body, style="Surface.TFrame", padding=20)
        left.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text=_("settings_appearance"), style="Section.TLabel").pack(anchor="w")
        row = ttk.Frame(left, style="Surface.TFrame")
        row.pack(fill="x", pady=(14, 0))
        ttk.Label(row, text=_("settings_lang"), style="Field.TLabel").pack(side="left")
        ttk.Combobox(row, textvariable=self.lang_var, values=["tr", "en"], state="readonly", width=12, style="Dark.TCombobox").pack(side="left", padx=(14, 0))

        ttk.Checkbutton(left, text=_("settings_tray"), variable=self.tray_var, style="Flat.TCheckbutton").pack(anchor="w", pady=(16, 0))
        ttk.Checkbutton(left, text=_("settings_sound"), variable=self.sound_var, style="Flat.TCheckbutton").pack(anchor="w", pady=(8, 0))

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=18)
        ttk.Label(left, text=_("settings_file_ops"), style="Section.TLabel").pack(anchor="w")
        ttk.Label(left, text=_("settings_default_dir"), style="Field.TLabel").pack(anchor="w", pady=(14, 0))
        folder_row = ttk.Frame(left, style="Surface.TFrame")
        folder_row.pack(fill="x", pady=(8, 0))
        ttk.Entry(folder_row, textvariable=self.out_dir_var, style="Dark.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(folder_row, text=_("str_select"), command=self.pick_dir, style="Secondary.TButton").pack(side="right")
        ttk.Button(folder_row, text=_("str_delete"), command=lambda: self.out_dir_var.set(""), style="Ghost.TButton").pack(side="right", padx=(0, 8))

        actions = ttk.Frame(left, style="Surface.TFrame")
        actions.pack(anchor="w", pady=(18, 0))
        ttk.Button(actions, text=_("settings_save_btn"), command=self.save_settings, style="Primary.TButton").pack(side="left")
        ttk.Button(actions, text=_("settings_clear_history"), command=self.clear_history, style="Secondary.TButton").pack(side="left", padx=(10, 0))

        right = ttk.Frame(body, style="Panel.TFrame", padding=18)
        right.pack(side="left", fill="y", padx=(18, 0))
        self.feedback = InlineFeedback(right)
        self.feedback.pack(fill="x")
        self.feedback.set_info(
            _("txt_settings"),
            _("settings_saved"),
        )

    def pick_dir(self):
        selected = filedialog.askdirectory(title=_("settings_default_dir"))
        if selected:
            self.out_dir_var.set(selected)

    def clear_history(self):
        cfg.clear_recent_files()
        self.feedback.set_success(_("str_success"), _("settings_cleared"))

    def save_settings(self):
        cfg.set("language", self.lang_var.get())
        cfg.set("close_to_tray", self.tray_var.get())
        cfg.set("sound_enabled", self.sound_var.get())
        cfg.set("default_output_dir", self.out_dir_var.get())
        self.feedback.set_success(_("str_success"), _("settings_saved"))


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(_("txt_settings"))
        self.transient(parent)
        self.geometry("920x620")
        self.minsize(820, 560)
        self.configure(bg="#f4efe8")

        shell = ttk.Frame(self, style="App.TFrame", padding=24)
        shell.pack(fill="both", expand=True)

        head = ttk.Frame(shell, style="App.TFrame")
        head.pack(fill="x", pady=(0, 16))
        ttk.Label(head, text=_("txt_settings"), style="PageTitle.TLabel").pack(side="left")
        ttk.Button(head, text=_("str_close"), command=self.destroy, style="Ghost.TButton").pack(side="right")

        panel = SettingsPanel(shell)
        panel.pack(fill="both", expand=True)

        self.grab_set()
