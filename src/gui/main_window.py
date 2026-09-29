import logging
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

import pystray
from PIL import Image, ImageTk

from src.core.config_manager import cfg
from src.core.lang_manager import _
from src.gui import styles
from src.gui.helpers import follow_width
from src.gui.preview_panel import PreviewPanel
from src.gui.styles import P, setup_styles
from src.gui.theme.images import Icons
from src.gui.widgets import FocusVisible, SegmentedControl, Tooltip
from src.gui.tabs.tab_advanced import AdvancedTab
from src.gui.tabs.tab_batch import BatchTab
from src.gui.tabs.tab_compress import CompressTab
from src.gui.tabs.tab_convert import ConvertTab
from src.gui.tabs.tab_edit import EditTab
from src.gui.tabs.tab_merge import MergeTab
from src.gui.tabs.tab_security import SecurityTab
from src.gui.tabs.tab_settings import SettingsDialog
from src.gui.tabs.tab_scanner import ScannerTab
from src.gui.tabs.tab_split import SplitTab
from src.ai.speech_recognizer import recognizer
from src.ai.intent_parser import parse_intent
from src.ai.action_runner import execute_intent
from src.ai import text_speaker
from src.ai.text_speaker import speak

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = "DND_Files"

PREVIEW_WIDTH = 320
# The grid column also has to hold the 20 px gutter before the panel.
PREVIEW_COLUMN_WIDTH = PREVIEW_WIDTH + 20
CONTENT_MIN_WIDTH = 440

PAGE_META_KEYS = {
    "compress": ("page_meta_compress_eyebrow", "page_meta_compress_title", "page_meta_compress_body"),
    "organize": ("page_meta_organize_eyebrow", "page_meta_organize_title", "page_meta_organize_body"),
    "convert": ("page_meta_convert_eyebrow", "page_meta_convert_title", "page_meta_convert_body"),
    "security": ("page_meta_security_eyebrow", "page_meta_security_title", "page_meta_security_body"),
    "advanced": ("page_meta_advanced_eyebrow", "page_meta_advanced_title", "page_meta_advanced_body"),
    "batch": ("page_meta_batch_eyebrow", "page_meta_batch_title", "page_meta_batch_body"),
    "scanner": ("page_meta_scanner_eyebrow", "page_meta_scanner_title", "page_meta_scanner_body"),
}

# Sidebar order; Ctrl+1 … Ctrl+7 follow it.
NAV_ITEMS = [
    ("compress", Icons.COMPRESS, "txt_compress"),
    ("organize", Icons.ORGANIZE, "txt_edit"),
    ("scanner", Icons.SCAN, "txt_scan"),
    ("convert", Icons.CONVERT, "txt_convert"),
    ("security", Icons.SECURITY, "txt_security"),
    ("advanced", Icons.ADVANCED, "txt_advanced"),
    ("batch", Icons.BATCH, "txt_batch"),
]


class ToolWorkspace:
    def __init__(self, parent, tab_class, root, show_preview=True):
        self.frame = ttk.Frame(parent, style="App.TFrame")
        self.instance = tab_class(self.frame, root)
        # Tools that have their own preview (scanner) hide the shared PDF preview.
        self.show_preview = show_preview

    def get_active_tab(self):
        return self.instance


class GroupWorkspace:
    """Several tools behind one sidebar entry, switched with a segmented
    control above them."""

    def __init__(self, parent, root, groups):
        self.root = root
        self.frame = ttk.Frame(parent, style="App.TFrame")
        self.groups = {}
        self.current_key = None
        self.show_preview = True
        self._key_by_title = {title: key for key, title, _cls in groups}

        self.selected_title = tk.StringVar()
        self.nav = SegmentedControl(self.frame, self.selected_title, [title for _k, title, _c in groups],
                                    command=lambda: self.show(self._key_by_title[self.selected_title.get()]),
                                    on_canvas=True)
        self.nav.pack(anchor="w", pady=(0, 12))
        self.buttons = {key: self.nav.buttons[title] for key, title, _cls in groups}
        self.body = ttk.Frame(self.frame, style="App.TFrame")
        self.body.pack(fill="both", expand=True)

        for key, _title, tab_class in groups:
            self.groups[key] = ToolWorkspace(self.body, tab_class, root)

        if groups:
            self.show(groups[0][0])

    def show(self, key):
        if self.current_key == key:
            return
        if self.current_key:
            self.groups[self.current_key].frame.pack_forget()
        self.current_key = key
        self.groups[key].frame.pack(fill="both", expand=True)
        title = next(t for t, k in self._key_by_title.items() if k == key)
        self.nav.select(title, notify=False)

    def get_active_tab(self):
        return self.groups[self.current_key].get_active_tab()


class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Aura")
        self.root.configure(bg=P.canvas)
        self.root.pdf_aura_set_preview = self.set_preview_file
        self.root.pdf_aura_refresh_recent = self.refresh_recent_files
        self.root.pdf_aura_restart = self.restart

        try:
            if getattr(sys, "frozen", False):
                base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
                if not os.path.exists(os.path.join(base_dir, "assets", "app_icon.ico")):
                    base_dir = os.path.join(os.path.dirname(sys.executable), "_internal")
            else:
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            self.base_dir = base_dir

            self.icon_path = os.path.join(base_dir, "assets", "app_icon.ico")
            if os.path.exists(self.icon_path):
                # default=: dialogs and the viewer get the app icon too.
                self.root.iconbitmap(default=self.icon_path)
            else:
                self.icon_path = None
        except Exception:
            self.icon_path = None
            self.base_dir = None

        self.nav_buttons = {}
        self.workspaces = {}
        self.current_page = None
        self.page_title_var = tk.StringVar()
        self.page_body_var = tk.StringVar()
        self.page_badge_var = tk.StringVar()

        setup_styles(self.root)
        self.focus_visible = FocusVisible(self.root)
        self.build_ui()
        self.setup_ux_features()
        self.show_page("compress")
        self.fit_window_to_content()

        # The voice model is loaded on first use, not here: preloading cost
        # ~330 MB of RAM and ~4 s of CPU on every launch, and a ~460 MB
        # download on the first one, even if the assistant was never used.
        self._model_loading = False
        self._model_error = None
        text_speaker.add_listener(self._show_assistant_reply)

    # ── Layout ────────────────────────────────────────────────────────────

    def build_ui(self):
        shell = ttk.Frame(self.root, style="App.TFrame")
        shell.pack(fill="both", expand=True)

        self._build_sidebar(shell)
        ttk.Frame(shell, style="Divider.TFrame", width=1).pack(side="left", fill="y")

        main = ttk.Frame(shell, style="App.TFrame", padding=(28, 22, 28, 24))
        main.pack(side="left", fill="both", expand=True)
        self.main = main
        self._build_header(main)

        # Every assistant reply is shown here as text: speech alone left the
        # user with nothing when the voice engine was off or unavailable.
        self.assistant_reply_var = tk.StringVar()
        self.assistant_reply = ttk.Frame(main, style="Callout.TFrame", padding=(12, 8, 6, 8))
        reply_icon = styles.icon(Icons.SPARK, 13, P.accent_text)
        ttk.Label(self.assistant_reply, image=reply_icon, style="CalloutIcon.TLabel").pack(side="left", anchor="n", pady=(2, 0))
        reply_label = ttk.Label(self.assistant_reply, textvariable=self.assistant_reply_var,
                                style="CalloutText.TLabel", wraplength=600, justify="left")
        reply_label.pack(side="left", fill="x", expand=True, padx=(8, 8))
        follow_width(reply_label, self.assistant_reply, 80)
        close_icon = styles.icon(Icons.CLOSE, 10, P.accent_text)
        close = ttk.Button(self.assistant_reply, style="CalloutClose.TButton", command=self.hide_assistant_reply,
                           image=close_icon or "", text="" if close_icon else "×")
        close.pack(side="right", anchor="n")
        Tooltip(close, _("str_close"))

        body = ttk.Frame(main, style="App.TFrame")
        body.pack(fill="both", expand=True, pady=(18, 0))
        self.body = body

        # grid, not pack: pack shrinks both children proportionally when the
        # window is narrow, which squeezed the preview down to "Ön", "Seçi",
        # "bel". A grid column with a minsize keeps the preview intact and
        # takes the space out of the content column instead.
        body.columnconfigure(0, weight=1, minsize=CONTENT_MIN_WIDTH)
        body.columnconfigure(1, weight=0, minsize=PREVIEW_COLUMN_WIDTH)
        body.rowconfigure(0, weight=1)

        self.content = ttk.Frame(body, style="App.TFrame")
        self.content.grid(row=0, column=0, sticky="nsew")

        self.preview_host = ttk.Frame(body, width=PREVIEW_WIDTH, style="App.TFrame")
        self.preview_host.grid(row=0, column=1, sticky="ns", padx=(20, 0))
        # The panel inside is pack-managed, so pack_propagate is the one that
        # stops it from resizing the host; grid_propagate covers the rest.
        self.preview_host.pack_propagate(False)
        self.preview_host.grid_propagate(False)

        self.preview_panel = PreviewPanel(self.preview_host, self.root)
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
        self.workspaces["scanner"] = ToolWorkspace(self.content, ScannerTab, self.root, show_preview=False)
        self.workspaces["convert"] = ToolWorkspace(self.content, ConvertTab, self.root)
        self.workspaces["security"] = ToolWorkspace(self.content, SecurityTab, self.root)
        self.workspaces["advanced"] = ToolWorkspace(self.content, AdvancedTab, self.root)
        self.workspaces["batch"] = ToolWorkspace(self.content, BatchTab, self.root)

    def _brand_image(self):
        path = os.path.join(self.base_dir or "", "assets", "appicon.png")
        try:
            image = Image.open(path).convert("RGBA").resize((26, 26), Image.LANCZOS)
            return ImageTk.PhotoImage(image, master=self.root)
        except Exception:
            return None

    def _nav_images(self, glyph):
        """Icon per state: accent when selected, full ink on hover."""
        normal = styles.icon(glyph, 16, P.text_tertiary)
        if normal is None:
            return ""
        return (normal,
                "selected", styles.icon(glyph, 16, P.accent),
                "active", styles.icon(glyph, 16, P.text))

    def _build_sidebar(self, shell):
        sidebar = ttk.Frame(shell, width=styles.M.sidebar_width, style="Sidebar.TFrame", padding=(12, 18, 12, 14))
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self.sidebar = sidebar

        brand = ttk.Frame(sidebar, style="Sidebar.TFrame")
        brand.pack(fill="x", padx=(8, 0))
        self._brand_photo = self._brand_image()
        ttk.Label(brand, text="PDF Aura", image=self._brand_photo or "", compound="left",
                  style="SidebarBrand.TLabel").pack(side="left")

        ttk.Label(sidebar, text=_("sidebar_workspace"), style="SidebarSection.TLabel").pack(anchor="w", padx=(10, 0), pady=(26, 6))
        for index, (key, glyph, label_key) in enumerate(NAV_ITEMS, start=1):
            button = ttk.Button(sidebar, text=_(label_key), style="Nav.TButton",
                                image=self._nav_images(glyph), compound="left",
                                command=lambda current=key: self.show_page(current))
            button.pack(fill="x", pady=1)
            Tooltip(button, f"Ctrl+{index}")
            self.nav_buttons[key] = button

        # Bottom block first, so the recent list takes whatever is left.
        bottom = ttk.Frame(sidebar, style="Sidebar.TFrame")
        bottom.pack(side="bottom", fill="x")
        ttk.Frame(bottom, style="SidebarDivider.TFrame", height=1).pack(fill="x", pady=(0, 8))
        self.settings_button = ttk.Button(bottom, text=_("txt_settings"), style="Nav.TButton",
                                          image=self._nav_images(Icons.SETTINGS), compound="left",
                                          command=self.open_settings)
        self.settings_button.pack(fill="x")
        Tooltip(self.settings_button, "Ctrl+,")
        offline = ttk.Label(bottom, text=_("sidebar_offline"), style="SidebarMeta.TLabel",
                            image=styles.icon(Icons.SHIELD, 12, P.text_tertiary) or "", compound="left",
                            wraplength=180, justify="left")
        offline.pack(anchor="w", padx=(10, 0), pady=(10, 0))

        # Recent files were recorded nowhere, so "Clear recent files" in
        # Settings cleared a list that could never fill up.
        ttk.Label(sidebar, text=_("sidebar_recent"), style="SidebarSection.TLabel").pack(anchor="w", padx=(10, 0), pady=(24, 6))
        self.recent_frame = ttk.Frame(sidebar, style="Sidebar.TFrame")
        self.recent_frame.pack(fill="x")
        self.refresh_recent_files()

    def _build_header(self, main):
        header = ttk.Frame(main, style="App.TFrame")
        header.pack(fill="x")
        header.columnconfigure(0, weight=1)

        title_stack = ttk.Frame(header, style="App.TFrame")
        title_stack.grid(row=0, column=0, sticky="new", padx=(0, 24))
        ttk.Label(title_stack, textvariable=self.page_badge_var, style="PageEyebrow.TLabel").pack(anchor="w")
        ttk.Label(title_stack, textvariable=self.page_title_var, style="PageTitle.TLabel").pack(anchor="w", pady=(2, 0))
        page_body = ttk.Label(title_stack, textvariable=self.page_body_var, style="PageBody.TLabel",
                              wraplength=520, justify="left")
        page_body.pack(anchor="w", fill="x", pady=(4, 0))
        follow_width(page_body, title_stack, 0, minimum=240)

        # Assistant: type a command or hold the mic button and speak.
        self.command_bar = ttk.Frame(header, style="Command.TFrame", padding=(4, 3))
        self.command_bar.grid(row=0, column=1, sticky="ne", pady=(6, 0))
        self.chat_placeholder = _("chat_placeholder")
        self.txt_chat = ttk.Entry(self.command_bar, width=30, style="CommandHint.TEntry")
        self.txt_chat.pack(side="left", fill="y")
        self.txt_chat.insert(0, self.chat_placeholder)

        self.btn_mic = ttk.Button(self.command_bar, text=_("voice_idle"), style="Voice.TButton",
                                  image=styles.icon(Icons.MIC, 13, P.text_secondary) or "", compound="left")
        self.btn_mic.pack(side="left", padx=(2, 0))
        self.btn_mic.bind("<ButtonPress-1>", self.on_mic_press)
        self.btn_mic.bind("<ButtonRelease-1>", self.on_mic_release)
        Tooltip(self.btn_mic, _("voice_hold_hint"))

        def on_focus_in(_event):
            self.command_bar.configure(style="CommandFocus.TFrame")
            if self.txt_chat.get() == self.chat_placeholder:
                self.txt_chat.delete(0, "end")
            self.txt_chat.configure(style="Command.TEntry")

        def on_focus_out(_event):
            self.command_bar.configure(style="Command.TFrame")
            if not self.txt_chat.get():
                self.txt_chat.insert(0, self.chat_placeholder)
                self.txt_chat.configure(style="CommandHint.TEntry")

        self.txt_chat.bind("<FocusIn>", on_focus_in)
        self.txt_chat.bind("<FocusOut>", on_focus_out)
        self.txt_chat.bind("<Return>", self.on_text_chat_submit)
        self.txt_chat.bind("<Escape>", lambda _e: self.root.focus_set())

    def setup_ux_features(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self.handle_drop)
        except AttributeError:
            pass

        # Keyboard: Ctrl+1…7 switch tools, Ctrl+, opens settings, Ctrl+K
        # jumps to the assistant.
        for index, (key, _glyph, _label) in enumerate(NAV_ITEMS, start=1):
            self.root.bind_all(f"<Control-Key-{index}>", lambda _e, k=key: self.show_page(k))
        self.root.bind_all("<Control-comma>", lambda _e: self.open_settings())
        self.root.bind_all("<Control-k>", lambda _e: self.focus_assistant())

        self.tray_icon = None
        if cfg.get("close_to_tray", True):
            self._ensure_tray_icon()

    def _ensure_tray_icon(self):
        """Start the tray icon if it is not running. True if one is available.

        The icon is only created at startup when the setting is already on,
        so turning the setting on later left no icon; closing then hid the
        window with no way to get it back. on_closing() calls this first.
        """
        if getattr(self, "tray_icon", None):
            return True
        icon_path = getattr(self, "icon_path", None)
        if not icon_path or not os.path.exists(icon_path):
            return False
        try:
            image = Image.open(icon_path)
            menu = pystray.Menu(
                pystray.MenuItem(_("tray_open"), self.show_window),
                pystray.MenuItem(_("tray_quit"), self.quit_window),
            )
            self.tray_icon = pystray.Icon("pdfaura", image, "PDF Aura", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
            return True
        except Exception as exc:
            print(f"[Tray] icon could not be started: {exc}")
            self.tray_icon = None
            return False

    def show_page(self, key):
        if key == self.current_page:
            return
        if self.current_page:
            self.workspaces[self.current_page].frame.pack_forget()
            self.nav_buttons[self.current_page].state(["!selected"])

        self.current_page = key
        workspace = self.workspaces[key]
        if workspace.show_preview:
            self.preview_host.grid(row=0, column=1, sticky="ns", padx=(20, 0))
            self.preview_host.master.columnconfigure(1, minsize=PREVIEW_COLUMN_WIDTH)
        else:
            # The scanner has its own preview; give the column back.
            self.preview_host.grid_remove()
            self.preview_host.master.columnconfigure(1, minsize=0)
        workspace.frame.pack(fill="both", expand=True)
        self.nav_buttons[key].state(["selected"])

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

        active_tab = self.get_active_tab()
        if hasattr(active_tab, "handle_external_drop_many"):
            active_tab.handle_external_drop_many(list(files))
        elif hasattr(active_tab, "handle_external_drop"):
            for file_path in files:
                active_tab.handle_external_drop(file_path)

    def set_preview_file(self, path):
        self.preview_panel.set_path(path)

    def open_settings(self):
        SettingsDialog(self.root)

    def focus_assistant(self):
        self.txt_chat.focus_set()
        return "break"

    def _scanner_tab(self):
        workspace = self.workspaces.get("scanner")
        return workspace.instance if workspace else None

    def on_closing(self):
        # Hide only if there really is a tray icon to get the window back
        # from; otherwise quit, rather than run on invisibly.
        if cfg.get("close_to_tray", True) and self._ensure_tray_icon():
            scanner = self._scanner_tab()
            if scanner:
                scanner.save_session_now()
            self.root.withdraw()
            self._notify_running_in_tray()
        else:
            self.quit_window(None, None)

    def _notify_running_in_tray(self):
        # Closing only hides the window; say so once, otherwise it looks like
        # the app quit while it keeps running next to the clock.
        if getattr(self, "_tray_notice_shown", False) or not getattr(self, "tray_icon", None):
            return
        self._tray_notice_shown = True
        try:
            self.tray_icon.notify(_("tray_background_body"), _("tray_background_title"))
        except Exception:
            pass

    def show_window(self, icon, _item):
        self.root.after(0, self.root.deiconify)

    def quit_window(self, icon, _item):
        if getattr(self, "tray_icon", None):
            self.tray_icon.stop()
        # May be called from the tray thread: hop to the Tk thread first.
        self.root.after(0, self._quit_mainloop)

    def _quit_mainloop(self):
        scanner = self._scanner_tab()
        if scanner:
            try:
                self.root.config(cursor="watch")
                self.root.update_idletasks()
                scanner.flush_session(timeout=10.0)
            except Exception:
                logging.exception("Scanner session could not be flushed on exit")
        self.root.quit()

    def restart(self):
        """Start a fresh copy of the app, then close this one. Used to apply a
        new language, since every label is built once at start-up.

        Returns None on success, or the error text if no new copy started.
        """
        if getattr(sys, "frozen", False):
            command = [sys.executable]
            folder = os.path.dirname(sys.executable)
        else:
            folder = self.base_dir or os.getcwd()
            command = [sys.executable, os.path.join(folder, "main.py")]

        # The new copy restores the scanner pages from disk, so write them now.
        scanner = self._scanner_tab()
        if scanner:
            try:
                scanner.flush_session(timeout=10.0)
            except Exception:
                logging.exception("Scanner session could not be flushed before restart")

        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            subprocess.Popen(command, cwd=folder, creationflags=flags, close_fds=True)
        except OSError as exc:
            return str(exc)
        self.quit_window(None, None)
        return None

    def fit_window_to_content(self):
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        w = min(1480, max(1100, screen_w - 60))
        h = min(920, max(720, screen_h - 80))
        x = max(0, (screen_w - w) // 2)
        y = max(0, (screen_h - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(min(1100, screen_w - 40), min(720, screen_h - 60))
        self.root.resizable(True, True)

    def refresh_recent_files(self):
        """Redraw the sidebar's recent-files list from the config."""
        for child in self.recent_frame.winfo_children():
            child.destroy()

        recent = cfg.get_recent_files()[:5]
        if not recent:
            ttk.Label(self.recent_frame, text=_("sidebar_recent_empty"),
                      style="SidebarMeta.TLabel", wraplength=180,
                      justify="left").pack(anchor="w", padx=(10, 0))
            return

        doc_icon = styles.icon(Icons.DOCUMENT, 13, P.text_tertiary) or ""
        for path in recent:
            name = os.path.basename(path)
            label = name if len(name) <= 26 else name[:23] + "…"
            button = ttk.Button(self.recent_frame, text=label, style="NavFile.TButton",
                                image=doc_icon, compound="left",
                                command=lambda p=path: self._open_recent(p))
            button.pack(fill="x", pady=1)
            Tooltip(button, path)

    def _open_recent(self, path):
        from src.gui.helpers import open_path
        if os.path.isfile(path):
            open_path(path)
        else:
            self.refresh_recent_files()   # it has since been deleted

    # ── Assistant ─────────────────────────────────────────────────────────

    def _show_assistant_reply(self, text):
        """Show an assistant reply on screen (called from worker threads)."""
        def _update():
            self.assistant_reply_var.set(text)
            if not self.assistant_reply.winfo_manager():
                self.assistant_reply.pack(fill="x", pady=(14, 0), before=self.body)
        try:
            self.root.after(0, _update)
        except Exception:
            pass   # window already gone

    def hide_assistant_reply(self):
        self.assistant_reply.pack_forget()

    def _set_mic_state(self, text, enabled=True, style="Voice.TButton"):
        self.btn_mic.configure(text=text, style=style,
                               state="normal" if enabled else "disabled")

    def _start_model_load(self, on_ready=None):
        """Load the voice model on demand, keeping the button honest."""
        if self._model_loading:
            return

        self._model_loading = True

        def _started():
            self.root.after(0, lambda: self._set_mic_state(_("voice_loading"), enabled=False))

        def _ready():
            self._model_loading = False
            self._model_error = None
            self.root.after(0, lambda: self._set_mic_state(_("voice_idle")))
            if on_ready:
                self.root.after(0, on_ready)

        def _failed(exc):
            self._model_loading = False
            self._model_error = exc
            # Say why, rather than leaving a live-looking button that does
            # nothing; the reason only ever went to the console before.
            self.root.after(0, lambda: self._set_mic_state(_("voice_model_missing")))
            self.root.after(0, lambda: self._show_assistant_reply(
                _("voice_model_error_body").format(error=exc)))

        recognizer.load_model_async(on_start=_started, on_success=_ready, on_error=_failed)

    def on_text_chat_submit(self, event=None):
        text = self.txt_chat.get().strip()
        if not text or text == self.chat_placeholder:
            return

        self.txt_chat.delete(0, "end")
        self.btn_mic.configure(style="Voice.TButton", text=_("voice_processing"))
        self.root.update_idletasks()

        def _run():
            intent = parse_intent(text)
            execute_intent(intent)
            self.root.after(0, lambda: self.btn_mic.configure(
                style="Voice.TButton",
                text=_("voice_idle")
            ))

        threading.Thread(target=_run, daemon=True).start()

    def on_mic_press(self, event):
        if str(self.btn_mic.cget("state")) == "disabled":
            return

        if self._model_error is not None:
            # Explain rather than sit there looking usable.
            self._show_assistant_reply(
                _("voice_model_error_body").format(error=self._model_error))
            self._start_model_load()
            return

        if not recognizer.model_ready:
            # First use: load now and tell the user it is happening.
            self._start_model_load()
            return

        self.btn_mic.configure(style="VoiceActive.TButton", text=_("voice_listening"))
        recognizer.start_recording()

    def on_mic_release(self, event):
        if not recognizer.is_recording:
            return
        self.btn_mic.configure(style="Voice.TButton", text=_("voice_processing"))
        self.root.update_idletasks()

        def _handle_speech(text):
            def _update_ui():
                if text:
                    self.btn_mic.configure(text=f"\"{text[:40]}...\"" if len(text) > 40 else f"\"{text}\"")
                    self.root.update_idletasks()

                    intent = parse_intent(text)

                    # Run the action off the Tk thread so the window stays responsive.
                    def _run():
                        execute_intent(intent)
                        self.root.after(0, lambda: self.btn_mic.configure(
                            style="Voice.TButton",
                            text=_("voice_idle")
                        ))
                    threading.Thread(target=_run, daemon=True).start()
                else:
                    speak(_("assist_not_heard"))
                    self.btn_mic.configure(
                        style="Voice.TButton",
                        text=_("voice_idle")
                    )

            # UI updates happen on the Tk thread.
            self.root.after(0, _update_ui)

        recognizer.stop_recording_and_recognize(_handle_speech)
