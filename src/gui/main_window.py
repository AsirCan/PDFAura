import os
import sys
import threading
import tkinter as tk
from tkinter import ttk

import pystray
from PIL import Image

from src.core.config_manager import cfg
from src.core.lang_manager import _
from src.gui.preview_panel import PreviewPanel
from src.gui.styles import APP_BG, setup_styles
from src.gui.tabs.tab_advanced import AdvancedTab
from src.gui.tabs.tab_batch import BatchTab
from src.gui.tabs.tab_compress import CompressTab
from src.gui.tabs.tab_convert import ConvertTab
from src.gui.tabs.tab_edit import EditTab
from src.gui.tabs.tab_merge import MergeTab
from src.gui.tabs.tab_security import SecurityTab
from src.gui.tabs.tab_settings import SettingsDialog
from src.gui.tabs.tab_split import SplitTab
from src.ai.speech_recognizer import recognizer
from src.ai.intent_parser import parse_intent
from src.ai.action_runner import execute_intent
from src.ai.text_speaker import speak

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = "DND_Files"

PAGE_META_KEYS = {
    "compress": ("page_meta_compress_eyebrow", "page_meta_compress_title", "page_meta_compress_body"),
    "organize": ("page_meta_organize_eyebrow", "page_meta_organize_title", "page_meta_organize_body"),
    "convert": ("page_meta_convert_eyebrow", "page_meta_convert_title", "page_meta_convert_body"),
    "security": ("page_meta_security_eyebrow", "page_meta_security_title", "page_meta_security_body"),
    "advanced": ("page_meta_advanced_eyebrow", "page_meta_advanced_title", "page_meta_advanced_body"),
    "batch": ("page_meta_batch_eyebrow", "page_meta_batch_title", "page_meta_batch_body"),
}


class ToolWorkspace:
    def __init__(self, parent, tab_class, root):
        self.frame = ttk.Frame(parent, style="App.TFrame")
        self.instance = tab_class(self.frame, root)

    def get_active_tab(self):
        return self.instance


class GroupWorkspace:
    def __init__(self, parent, root, groups):
        self.root = root
        self.frame = ttk.Frame(parent, style="App.TFrame")
        self.groups = {}
        self.buttons = {}
        self.current_key = None

        self.nav = ttk.Frame(self.frame, style="App.TFrame")
        self.nav.pack(fill="x", pady=(0, 16))
        self.body = ttk.Frame(self.frame, style="App.TFrame")
        self.body.pack(fill="both", expand=True)

        for key, title, tab_class in groups:
            button = ttk.Button(self.nav, text=title, style="Subnav.TButton", command=lambda current=key: self.show(current))
            button.pack(side="left", padx=(0, 10))
            self.buttons[key] = button
            self.groups[key] = ToolWorkspace(self.body, tab_class, root)

        if groups:
            self.show(groups[0][0])

    def show(self, key):
        if self.current_key:
            self.groups[self.current_key].frame.pack_forget()
            self.buttons[self.current_key].configure(style="Subnav.TButton")
        self.current_key = key
        self.groups[key].frame.pack(fill="both", expand=True)
        self.buttons[key].configure(style="SubnavSelected.TButton")

    def get_active_tab(self):
        return self.groups[self.current_key].get_active_tab()


class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Aura")
        self.root.configure(bg=APP_BG)
        self.root.pdf_aura_set_preview = self.set_preview_file

        try:
            if getattr(sys, "frozen", False):
                base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
                if not os.path.exists(os.path.join(base_dir, "assets", "app_icon.ico")):
                     base_dir = os.path.join(os.path.dirname(sys.executable), "_internal")
            else:
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                
            self.icon_path = os.path.join(base_dir, "assets", "app_icon.ico")
            if os.path.exists(self.icon_path):
                self.root.iconbitmap(self.icon_path)
            else:
                self.icon_path = None
        except Exception:
            self.icon_path = None

        self.nav_buttons = {}
        self.workspaces = {}
        self.current_page = None
        self.page_title_var = tk.StringVar()
        self.page_body_var = tk.StringVar()
        self.page_badge_var = tk.StringVar()

        setup_styles()
        self.build_ui()
        self.setup_ux_features()
        self.show_page("compress")
        self.fit_window_to_content()
        
        # Arka planda AI modelini indir veya yükle
        def _on_model_start():
            if hasattr(self, 'btn_mic'):
                self.root.after(0, lambda: self.btn_mic.configure(state="disabled", text="🎙️ AI Modeli İniyor / Yükleniyor..."))
            
        def _on_model_complete():
            if hasattr(self, 'btn_mic'):
                self.root.after(0, lambda: self.btn_mic.configure(state="normal", text="🎙️ Asistan"))

        recognizer.preload_model_async(on_start=_on_model_start, on_complete=_on_model_complete)

    def build_ui(self):
        shell = ttk.Frame(self.root, padding=20, style="App.TFrame")
        shell.pack(fill="both", expand=True)

        sidebar = ttk.Frame(shell, width=236, style="Sidebar.TFrame", padding=18)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        ttk.Label(sidebar, text="PDF Aura", style="SidebarBrand.TLabel").pack(anchor="w")
        ttk.Label(sidebar, text=_("header_subtitle"), style="SidebarMeta.TLabel", wraplength=180, justify="left").pack(anchor="w", pady=(8, 0))

        ttk.Label(sidebar, text=_("sidebar_workspace"), style="SidebarSection.TLabel").pack(anchor="w", pady=(26, 8))
        nav_items = [
            ("compress", _("txt_compress")),
            ("organize", _("txt_edit")),
            ("convert", _("txt_convert")),
            ("security", _("txt_security")),
            ("advanced", _("txt_advanced")),
            ("batch", _("txt_batch")),
        ]
        for key, label in nav_items:
            button = ttk.Button(sidebar, text=label, style="Nav.TButton", command=lambda current=key: self.show_page(current))
            button.pack(fill="x", pady=4)
            self.nav_buttons[key] = button

        ttk.Label(sidebar, text=_("sidebar_drag_drop"), style="SidebarSection.TLabel").pack(anchor="w", pady=(28, 8))
        ttk.Label(
            sidebar,
            text=_("str_drag_drop_hint"),
            style="SidebarMeta.TLabel",
            wraplength=180,
            justify="left",
        ).pack(anchor="w")

        main = ttk.Frame(shell, style="App.TFrame")
        main.pack(side="left", fill="both", expand=True, padx=(18, 0))

        header = ttk.Frame(main, style="App.TFrame")
        header.pack(fill="x")

        title_stack = ttk.Frame(header, style="App.TFrame")
        title_stack.pack(side="left", fill="x", expand=True)
        ttk.Label(title_stack, textvariable=self.page_badge_var, style="PageEyebrow.TLabel").pack(anchor="w")
        ttk.Label(title_stack, textvariable=self.page_title_var, style="PageTitle.TLabel").pack(anchor="w", pady=(4, 0))
        ttk.Label(title_stack, textvariable=self.page_body_var, style="PageBody.TLabel", wraplength=820, justify="left").pack(anchor="w", pady=(8, 0))

        header_actions = ttk.Frame(header, style="App.TFrame")
        header_actions.pack(side="right")
        ttk.Button(header_actions, text=_("txt_settings"), command=self.open_settings, style="Ghost.TButton").pack(side="right")
        
        self.btn_mic = ttk.Button(header_actions, text="🎙️ Asistan", style="Voice.TButton")
        self.btn_mic.pack(side="right", padx=(0, 10))
        self.btn_mic.bind("<ButtonPress-1>", self.on_mic_press)
        self.btn_mic.bind("<ButtonRelease-1>", self.on_mic_release)

        self.txt_chat = ttk.Entry(header_actions, width=25)
        self.txt_chat.pack(side="right", padx=(0, 10))
        self.txt_chat.insert(0, "Aura'ya yazın...")
        
        def on_focus_in(e):
            if self.txt_chat.get() == "Aura'ya yazın...":
                self.txt_chat.delete(0, 'end')
        def on_focus_out(e):
            if not self.txt_chat.get():
                self.txt_chat.insert(0, "Aura'ya yazın...")
                
        self.txt_chat.bind('<FocusIn>', on_focus_in)
        self.txt_chat.bind('<FocusOut>', on_focus_out)
        self.txt_chat.bind("<Return>", self.on_text_chat_submit)

        body = ttk.Frame(main, style="App.TFrame")
        body.pack(fill="both", expand=True, pady=(18, 0))

        self.content = ttk.Frame(body, style="App.TFrame")
        self.content.pack(side="left", fill="both", expand=True)

        preview_host = ttk.Frame(body, width=340, style="App.TFrame")
        preview_host.pack(side="left", fill="y", padx=(18, 0))
        preview_host.pack_propagate(False)
        self.preview_panel = PreviewPanel(preview_host, self.root)
        self.preview_panel.pack(fill="both", expand=True)

        self.workspaces["compress"] = ToolWorkspace(self.content, CompressTab, self.root)
        self.workspaces["organize"] = GroupWorkspace(
            self.content,
            self.root,
            [
                ("split", _("txt_split"), SplitTab),
                ("merge", _("txt_merge"), MergeTab),
                ("edit", _("txt_edit"), EditTab),
            ],
        )
        self.workspaces["convert"] = ToolWorkspace(self.content, ConvertTab, self.root)
        self.workspaces["security"] = ToolWorkspace(self.content, SecurityTab, self.root)
        self.workspaces["advanced"] = ToolWorkspace(self.content, AdvancedTab, self.root)
        self.workspaces["batch"] = ToolWorkspace(self.content, BatchTab, self.root)

    def setup_ux_features(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self.handle_drop)
        except AttributeError:
            pass
            
        self.tray_icon = None
        if cfg.get("close_to_tray", True) and getattr(self, "icon_path", None) and os.path.exists(self.icon_path):
            self._start_tray_icon()

    def _start_tray_icon(self):
        image = Image.open(self.icon_path)
        menu = pystray.Menu(
            pystray.MenuItem(_("tray_open"), self.show_window),
            pystray.MenuItem(_("tray_quit"), self.quit_window),
        )
        self.tray_icon = pystray.Icon("pdfaura", image, "PDF Aura", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_page(self, key):
        if self.current_page:
            self.workspaces[self.current_page].frame.pack_forget()
            self.nav_buttons[self.current_page].configure(style="Nav.TButton")

        self.current_page = key
        self.workspaces[key].frame.pack(fill="both", expand=True)
        self.nav_buttons[key].configure(style="NavSelected.TButton")

        eyebrow_key, title_key, body_key = PAGE_META_KEYS[key]
        self.page_badge_var.set(_(eyebrow_key))
        self.page_title_var.set(_(title_key))
        self.page_body_var.set(_(body_key))

    def get_active_tab(self):
        return self.workspaces[self.current_page].get_active_tab()

    def handle_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        if not files:
            return

        file_path = files[0]
        active_tab = self.get_active_tab()
        if hasattr(active_tab, "handle_external_drop"):
            active_tab.handle_external_drop(file_path)

    def set_preview_file(self, path):
        self.preview_panel.set_path(path)

    def open_settings(self):
        SettingsDialog(self.root)

    def on_closing(self):
        if cfg.get("close_to_tray", True) and self.icon_path:
            self.root.withdraw()
        else:
            self.quit_window(None, None)

    def show_window(self, icon, _item):
        self.root.after(0, self.root.deiconify)

    def quit_window(self, icon, _item):
        if getattr(self, "tray_icon", None):
            self.tray_icon.stop()
        self.root.after(0, self.root.quit)

    def fit_window_to_content(self):
        self.root.update_idletasks()
        self.root.geometry("1480x920")
        self.root.minsize(1200, 760)
        self.root.resizable(True, True)

    def on_text_chat_submit(self, event=None):
        text = self.txt_chat.get().strip()
        if not text or text == "Aura'ya yazın...":
            return
            
        self.txt_chat.delete(0, "end")
        self.btn_mic.configure(style="Voice.TButton", text="🎙️ İşleniyor...")
        self.root.update_idletasks()
        
        def _run():
            from src.ai.intent_parser import parse_intent
            from src.ai.action_runner import execute_intent
            intent = parse_intent(text)
            execute_intent(intent)
            self.root.after(0, lambda: self.btn_mic.configure(
                style="Voice.TButton",
                text="🎙️ Asistan"
            ))
        
        import threading
        threading.Thread(target=_run, daemon=True).start()

    def on_mic_press(self, event):
        # Model yüklenmeden veya buton disabled iken basılmasını engelle
        if not recognizer.model_ready:
            return
        if str(self.btn_mic.cget("state")) == "disabled":
            return
        self.btn_mic.configure(style="VoiceActive.TButton", text="🎙️ Dinleniyor...")
        recognizer.start_recording()
        
    def on_mic_release(self, event):
        if not recognizer.is_recording:
            return
        self.btn_mic.configure(style="Voice.TButton", text="🎙️ İşleniyor...")
        self.root.update_idletasks()
        
        def _handle_speech(text):
            def _update_ui():
                if text:
                    self.btn_mic.configure(text=f"🎙️ \"{text[:40]}...\"" if len(text) > 40 else f"🎙️ \"{text}\"")
                    self.root.update_idletasks()
                    
                    intent = parse_intent(text)
                    # execute_intent arkaplanda çalışsın ki UI donmasın
                    import threading
                    def _run():
                        execute_intent(intent)
                        self.root.after(0, lambda: self.btn_mic.configure(
                            style="Voice.TButton",
                            text="🎙️ Asistan"
                        ))
                    threading.Thread(target=_run, daemon=True).start()
                else:
                    speak("Sizi duyamadım, lütfen tekrar deneyin.")
                    self.btn_mic.configure(
                        style="Voice.TButton",
                        text="🎙️ Asistan"
                    )
            
            # UI güncellemelerini ana thread'de yap
            self.root.after(0, _update_ui)
            
        recognizer.stop_recording_and_recognize(_handle_speech)
