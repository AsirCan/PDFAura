import os
import sys
import tkinter as tk
from tkinter import ttk
from src.gui.styles import setup_styles, BG_COLOR, TEXT_COLOR, MUTED_TEXT

from src.gui.tabs.tab_compress import CompressTab
from src.gui.tabs.tab_split import SplitTab
from src.gui.tabs.tab_merge import MergeTab
from src.gui.tabs.tab_edit import EditTab
from src.gui.tabs.tab_convert import ConvertTab
from src.gui.tabs.tab_security import SecurityTab
from src.gui.tabs.tab_advanced import AdvancedTab
from src.gui.tabs.tab_batch import BatchTab
from src.gui.tabs.tab_settings import SettingsTab
from src.core.config_manager import cfg
from src.core.lang_manager import _
import threading
import pystray
from PIL import Image

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = "DND_Files"

class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Aura")
        self.root.configure(bg=BG_COLOR)

        try:
            base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            self.icon_path = os.path.join(base_dir, "assets", "app_icon.ico")
            if os.path.exists(self.icon_path):
                self.root.iconbitmap(self.icon_path)
        except Exception:
            self.icon_path = None

        self.tab_instances = []
        setup_styles()
        self.build_ui()
        self.setup_ux_features()
        self.fit_window_to_content()

    def build_ui(self):
        main_frame = ttk.Frame(self.root, padding=20, style="App.TFrame")
        main_frame.pack(fill="both", expand=True)

        # Header
        header = ttk.Frame(main_frame, style="App.TFrame")
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="PDF Aura", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text=_("header_subtitle"),
                  style="Subtitle.TLabel").pack(anchor="w", pady=(4, 0))

        # Notebook
        self.notebook = ttk.Notebook(main_frame, style="Dark.TNotebook")
        self.notebook.pack(fill="both", expand=True)

        tabs = [
            (f"  {_('txt_compress')}  ", CompressTab),
            (f"  {_('txt_split')}  ", SplitTab),
            (f"  {_('txt_merge')}  ", MergeTab),
            (f"  {_('txt_edit')}  ", EditTab),
            (f"  {_('txt_convert')}  ", ConvertTab),
            (f"  {_('txt_security')}  ", SecurityTab),
            (f"  {_('txt_advanced')}  ", AdvancedTab),
            (f"  {_('txt_batch')}  ", BatchTab),
            (f"  {_('txt_settings')}  ", SettingsTab),
        ]
        
        for title, TabClass in tabs:
            frame = ttk.Frame(self.notebook, style="App.TFrame")
            self.notebook.add(frame, text=title)
            instance = TabClass(frame, self.root)
            self.tab_instances.append(instance)

    def setup_ux_features(self):
        # 1. System Tray
        self.root.protocol('WM_DELETE_WINDOW', self.on_closing)
        
        # 2. Drag & Drop
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.handle_drop)
        except AttributeError:
            pass # Probably running without tkinterdnd2 root override

    def handle_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        if not files: return
        
        file_path = files[0] # Take first file
        current_idx = self.notebook.index("current")
        active_tab = self.tab_instances[current_idx]
        
        if hasattr(active_tab, "input_var"):
            active_tab.input_var.set(file_path)
            
        elif hasattr(active_tab, "tree"):
            # Mock structure for MergeTab drag insert
            if not file_path.lower().endswith(".pdf"): return
            item_id = active_tab.tree.insert("", "end", values=(os.path.basename(file_path), active_tab.pending_count, "-"))
            active_tab.files_map[item_id] = file_path
            active_tab.pending_count += 1
            if hasattr(active_tab, "status_var"):
                active_tab.status_var.set(f"{active_tab.pending_count}{_('str_files_added_to_list')}")

    def on_closing(self):
        if cfg.get("close_to_tray", True) and self.icon_path:
            self.root.withdraw()
            image = Image.open(self.icon_path)
            menu = pystray.Menu(
                pystray.MenuItem(_('tray_open'), self.show_window),
                pystray.MenuItem(_('tray_quit'), self.quit_window)
            )
            self.tray_icon = pystray.Icon("pdfaura", image, "PDF Aura", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        else:
            self.quit_window(None, None)

    def show_window(self, icon, item):
        icon.stop()
        self.root.after(0, self.root.deiconify)

    def quit_window(self, icon, item):
        if icon:
            icon.stop()
        self.root.quit()
        
    def fit_window_to_content(self):
        self.root.update_idletasks()
        width = max(820, self.root.winfo_reqwidth() + 24)
        height = max(620, self.root.winfo_reqheight() + 24)
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(820, 580)
        self.root.resizable(True, True)
