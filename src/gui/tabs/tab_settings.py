import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from src.core.config_manager import cfg
from src.core.lang_manager import _

class SettingsTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        
        self.lang_var = tk.StringVar(value=cfg.get("language", "tr"))
        self.tray_var = tk.BooleanVar(value=cfg.get("close_to_tray", True))
        self.sound_var = tk.BooleanVar(value=cfg.get("sound_enabled", True))
        self.out_dir_var = tk.StringVar(value=cfg.get("default_output_dir", ""))
        
        self.build_ui()

    def build_ui(self):
        c = ttk.Frame(self.parent, padding=15, style="Card.TFrame")
        c.pack(fill="both", expand=True, pady=(10, 0))

        # Genel Ayarlar
        ttk.Label(c, text=_("settings_appearance"), style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        f1 = ttk.Frame(c, style="Card.TFrame")
        f1.grid(row=1, column=0, sticky="ew")
        
        ttk.Label(f1, text=_("settings_lang")).grid(row=0, column=0, sticky="w", pady=5)
        lang_cb = ttk.Combobox(f1, textvariable=self.lang_var, values=["tr", "en"], state="readonly", width=15)
        lang_cb.grid(row=0, column=1, sticky="w", padx=10, pady=5)
        
        ttk.Checkbutton(f1, text=_("settings_tray"), variable=self.tray_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Checkbutton(f1, text=_("settings_sound"), variable=self.sound_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=5)

        ttk.Separator(c, orient="horizontal").grid(row=2, column=0, sticky="ew", pady=15)

        # Çıktı Ayarları
        ttk.Label(c, text=_("settings_file_ops"), style="Section.TLabel").grid(row=3, column=0, sticky="w", pady=(0, 10))
        
        f2 = ttk.Frame(c, style="Card.TFrame")
        f2.grid(row=4, column=0, sticky="ew")
        
        ttk.Label(f2, text=_("settings_default_dir")).grid(row=0, column=0, sticky="w", pady=5)
        
        of_frame = ttk.Frame(f2, style="Card.TFrame")
        of_frame.grid(row=1, column=0, sticky="ew")
        ttk.Entry(of_frame, textvariable=self.out_dir_var, width=50, style="Dark.TEntry").pack(side="left", fill="x", expand=True, padx=(0,10))
        ttk.Button(of_frame, text=_("str_select"), command=self.pick_dir, style="Secondary.TButton").pack(side="right")
        ttk.Button(of_frame, text=_("str_delete"), command=lambda: self.out_dir_var.set(""), style="Secondary.TButton").pack(side="right", padx=(0,5))
        
        ttk.Separator(c, orient="horizontal").grid(row=5, column=0, sticky="ew", pady=15)

        # Geçmiş Ayarları
        ttk.Label(c, text=_("settings_history"), style="Section.TLabel").grid(row=6, column=0, sticky="w", pady=(0, 10))
        ttk.Button(c, text=_("settings_clear_history"), command=self.clear_history, style="Secondary.TButton").grid(row=7, column=0, sticky="w")
        
        # Kaydet Butonu
        ttk.Button(c, text=_("settings_save_btn"), command=self.save_settings, style="Accent.TButton").grid(row=8, column=0, sticky="w", pady=(25, 0))

    def pick_dir(self):
        d = filedialog.askdirectory(title=_("settings_default_dir"))
        if d:
            self.out_dir_var.set(d)

    def clear_history(self):
        cfg.clear_recent_files()
        messagebox.showinfo(_("str_success"), _("settings_cleared"))

    def save_settings(self):
        cfg.set("language", self.lang_var.get())
        cfg.set("close_to_tray", self.tray_var.get())
        cfg.set("sound_enabled", self.sound_var.get())
        cfg.set("default_output_dir", self.out_dir_var.get())
        
        messagebox.showinfo(_("str_success"), _("settings_saved"))
