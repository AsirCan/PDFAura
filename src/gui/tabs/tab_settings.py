import os
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.ai.model_manager import ModelManager
from src.core.config_manager import cfg
from src.core.lang_manager import LANGUAGES, _
from src.gui import styles
from src.gui.helpers import InlineFeedback, follow_width
from src.gui.styles import P
from src.gui.theme import DARK_THEME, LIGHT_THEME, SYSTEM, get_theme, theme_preference
from src.gui.theme.images import Icons, theme_preview
from src.gui.widgets import ScrollArea, Tooltip

# Theme picker: (preference stored in the config, label key).
THEME_CHOICES = (
    (LIGHT_THEME, "settings_theme_light"),
    (DARK_THEME, "settings_theme_dark"),
    (SYSTEM, "settings_theme_system"),
)


class SettingsPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="App.TFrame")
        # The language the running UI was built in; changing it needs a restart.
        self._ui_language = cfg.get("language", "tr")
        self.lang_var = tk.StringVar(value=LANGUAGES.get(self._ui_language, self._ui_language))
        self.tray_var = tk.BooleanVar(value=cfg.get("close_to_tray", True))
        self.sound_var = tk.BooleanVar(value=cfg.get("sound_enabled", True))
        self.out_dir_var = tk.StringVar(value=cfg.get("default_output_dir", ""))
        self.model_manager = ModelManager()
        self.ai_root_var = tk.StringVar(value=str(self.model_manager.model_root))
        self.ai_detail_var = tk.StringVar(value="")
        self._download_running = False
        self.build_ui()

    def build_ui(self):
        intro = ttk.Label(self, text=_("settings_intro"), style="PageBody.TLabel", justify="left")
        intro.pack(anchor="w", fill="x")
        follow_width(intro, self)

        body = ttk.Frame(self, style="App.TFrame")
        body.pack(fill="both", expand=True, pady=(16, 0))

        settings_tabs = ttk.Notebook(body, style="Tabs.TNotebook")
        settings_tabs.pack(side="left", fill="both", expand=True)

        general_tab = ttk.Frame(settings_tabs, style="Card.TFrame", padding=20)
        ai_tab = ttk.Frame(settings_tabs, style="Card.TFrame", padding=20)
        settings_tabs.add(general_tab, text=_("settings_general_tab"))
        settings_tabs.add(ai_tab, text=_("settings_local_ai_tab"))

        # Scrolls when the dialog is too short for the whole form, so the
        # Save button can never end up below the edge of the card.
        general_scroll = ScrollArea(general_tab, style="Surface.TFrame", background=P.surface)
        general_scroll.pack(fill="both", expand=True)
        self.general_scroll = general_scroll
        self._build_general_settings(general_scroll.body)
        self._build_ai_settings(ai_tab)

        # Beside the notebook, level with its cards (below the tab row).
        right = ttk.Frame(body, style="Card.TFrame", padding=16, width=300)
        right.pack(side="right", fill="y", padx=(18, 0), pady=(46, 0))
        right.pack_propagate(False)
        self.feedback = InlineFeedback(right)
        self.feedback.pack(fill="x")
        # set_info, not set_success: nothing has been saved yet, and the
        # success panel offers "Open output" buttons that mean nothing here.
        self.feedback.set_info(
            _("txt_settings"),
            _("settings_intro"),
        )

    def _build_general_settings(self, parent):
        ttk.Label(parent, text=_("settings_appearance"), style="Section.TLabel").pack(anchor="w")
        ttk.Label(parent, text=_("settings_theme"), style="Field.TLabel").pack(anchor="w", pady=(14, 0))
        self._build_theme_picker(parent)
        ttk.Label(parent, text=_("settings_theme_hint"), style="Hint.TLabel").pack(anchor="w", pady=(8, 0))

        row = ttk.Frame(parent, style="Surface.TFrame")
        row.pack(fill="x", pady=(18, 0))
        ttk.Label(row, text=_("settings_lang"), style="Field.TLabel").pack(side="left")
        ttk.Combobox(
            row,
            textvariable=self.lang_var,
            values=list(LANGUAGES.values()),
            state="readonly",
            width=18,
            style="Input.TCombobox",
        ).pack(side="left", padx=(14, 0))

        ttk.Checkbutton(parent, text=_("settings_tray"), variable=self.tray_var, style="Flat.TCheckbutton").pack(anchor="w", pady=(16, 0))
        ttk.Checkbutton(parent, text=_("settings_sound"), variable=self.sound_var, style="Flat.TCheckbutton").pack(anchor="w", pady=(8, 0))

        ttk.Frame(parent, style="Divider.TFrame", height=1).pack(fill="x", pady=18)
        ttk.Label(parent, text=_("settings_file_ops"), style="Section.TLabel").pack(anchor="w")
        ttk.Label(parent, text=_("settings_default_dir"), style="Field.TLabel").pack(anchor="w", pady=(14, 0))
        folder_row = ttk.Frame(parent, style="Surface.TFrame")
        folder_row.pack(fill="x", pady=(8, 0))
        ttk.Entry(folder_row, textvariable=self.out_dir_var, style="Input.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(folder_row, text=_("str_select"), command=self.pick_dir, style="Secondary.TButton").pack(side="right")
        ttk.Button(folder_row, text=_("str_delete"), command=lambda: self.out_dir_var.set(""), style="Ghost.TButton",
                   image=styles.icon(Icons.CLEAR, 12, P.text_secondary) or "", compound="left").pack(side="right", padx=(0, 8))

        actions = ttk.Frame(parent, style="Surface.TFrame")
        actions.pack(anchor="w", pady=(18, 0))
        ttk.Button(actions, text=_("settings_save_btn"), command=self.save_settings, style="Primary.TButton").pack(side="left")
        ttk.Button(actions, text=_("settings_clear_history"), command=self.clear_history, style="Secondary.TButton").pack(side="left", padx=(10, 0))

    def _build_theme_picker(self, parent):
        """Light / Dark / System as cards with a picture of each, applied the
        moment one is clicked (and saved, like Windows' own setting)."""
        row = ttk.Frame(parent, style="Surface.TFrame")
        row.pack(anchor="w", pady=(8, 0))
        light, dark = get_theme(LIGHT_THEME).palette, get_theme(DARK_THEME).palette
        previews = {LIGHT_THEME: (light, None), DARK_THEME: (dark, None), SYSTEM: (light, dark)}
        self.theme_buttons = {}
        for index, (preference, label_key) in enumerate(THEME_CHOICES):
            palette, other = previews[preference]
            image = styles.image_bank().photo(
                ("theme-preview", preference),
                lambda palette=palette, other=other: theme_preview(112, 68, palette, other))
            button = ttk.Button(row, text=_(label_key), image=image or "", compound="top",
                                style="ThemeOption.TButton",
                                command=lambda choice=preference: self.choose_theme(choice))
            button.pack(side="left", padx=(0 if index == 0 else 10, 0))
            self.theme_buttons[preference] = button
        self._sync_theme_buttons()

    def _sync_theme_buttons(self):
        current = theme_preference()
        for preference, button in self.theme_buttons.items():
            button.state(["selected"] if preference == current else ["!selected"])

    def choose_theme(self, preference):
        cfg.set("theme", preference)
        styles.apply_preference(preference)
        self._sync_theme_buttons()

    def _build_ai_settings(self, parent):
        ttk.Label(parent, text=_("settings_local_ai_title"), style="Section.TLabel").pack(anchor="w")
        ttk.Label(
            parent,
            text=_("settings_local_ai_desc"),
            style="Hint.TLabel",
            wraplength=560,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        root_row = ttk.Frame(parent, style="Surface.TFrame")
        root_row.pack(fill="x", pady=(16, 0))
        ttk.Label(root_row, text=_("settings_ai_model_root"), style="Field.TLabel").pack(anchor="w")

        root_picker = ttk.Frame(parent, style="Surface.TFrame")
        root_picker.pack(fill="x", pady=(8, 0))
        ttk.Entry(root_picker, textvariable=self.ai_root_var, style="Input.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(root_picker, text=_("str_select"), command=self.pick_ai_root, style="Secondary.TButton").pack(side="right")
        ttk.Button(root_picker, text=_("settings_ai_open_folder"), command=self.open_ai_root, style="Secondary.TButton").pack(side="right", padx=(0, 8))

        table_frame = ttk.Frame(parent, style="PanelCard.TFrame", padding=2)
        table_frame.pack(fill="both", expand=True, pady=(16, 0))

        columns = ("status", "model", "type", "size", "hardware")
        self.model_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=8)
        self.model_tree.heading("status", text=_("settings_ai_status"))
        self.model_tree.heading("model", text=_("settings_ai_model"))
        self.model_tree.heading("type", text=_("settings_ai_type"))
        self.model_tree.heading("size", text=_("settings_ai_size"))
        self.model_tree.heading("hardware", text=_("settings_ai_hardware"))
        self.model_tree.column("status", width=80, anchor="center", stretch=False)
        self.model_tree.column("model", width=260, anchor="w")
        self.model_tree.column("type", width=95, anchor="center", stretch=False)
        self.model_tree.column("size", width=90, anchor="e", stretch=False)
        self.model_tree.column("hardware", width=110, anchor="center", stretch=False)
        self.model_tree.pack(side="left", fill="both", expand=True)
        self.model_tree.bind("<<TreeviewSelect>>", self.on_model_select)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.model_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.model_tree.configure(yscrollcommand=scrollbar.set)

        action_row = ttk.Frame(parent, style="Surface.TFrame")
        action_row.pack(fill="x", pady=(14, 0))
        self.ai_refresh_btn = ttk.Button(action_row, text=_("settings_ai_refresh"), command=self.refresh_ai_models, style="Secondary.TButton")
        self.ai_refresh_btn.pack(side="left")
        self.ai_pick_btn = ttk.Button(action_row, text=_("settings_ai_pick_model"), command=self.pick_selected_model_path, style="Secondary.TButton")
        self.ai_pick_btn.pack(side="left", padx=(8, 0))
        self.ai_download_btn = ttk.Button(action_row, text=_("settings_ai_download"), command=self.download_selected_model, style="Secondary.TButton")
        self.ai_download_btn.pack(side="left", padx=(8, 0))
        self.ai_test_btn = ttk.Button(action_row, text=_("settings_ai_test"), command=self.test_selected_model, style="Secondary.TButton")
        self.ai_test_btn.pack(side="left", padx=(8, 0))
        ttk.Button(action_row, text=_("settings_save_btn"), command=self.save_settings, style="Primary.TButton").pack(side="right")

        ttk.Label(
            parent,
            textvariable=self.ai_detail_var,
            style="Hint.TLabel",
            wraplength=560,
            justify="left",
        ).pack(anchor="w", pady=(12, 0))

        self.model_manager.ensure_directories()
        self.ai_root_var.set(str(self.model_manager.model_root))
        self.refresh_ai_models()

    def pick_dir(self):
        selected = filedialog.askdirectory(title=_("settings_default_dir"))
        if selected:
            self.out_dir_var.set(selected)

    def pick_ai_root(self):
        selected = filedialog.askdirectory(title=_("settings_ai_model_root"))
        if selected:
            self.ai_root_var.set(selected)
            self.model_manager.set_model_root(selected)
            self.refresh_ai_models()
            self.feedback.set_success(_("str_success"), _("settings_ai_root_saved"))

    def open_ai_root(self):
        try:
            self.model_manager.set_model_root(self.ai_root_var.get())
            os.startfile(str(self.model_manager.model_root))
            self.feedback.set_success(_("str_success"), _("settings_ai_folder_ready"))
        except Exception as exc:
            self.feedback.set_error(_("str_error"), str(exc))

    def refresh_ai_models(self):
        self.model_manager = ModelManager(self.ai_root_var.get())
        self.model_manager.ensure_directories()
        for item in self.model_tree.get_children():
            self.model_tree.delete(item)

        for status in self.model_manager.all_statuses():
            label = _("settings_ai_ready") if status.installed else _("settings_ai_missing")
            size = f"{status.size_mb:.1f} MB" if status.size_mb else f"~{status.spec.size_mb:.0f} MB"
            self.model_tree.insert(
                "",
                "end",
                iid=status.spec.id,
                values=(label, status.spec.name, status.spec.category, size, status.spec.hardware_profile),
            )
        self._update_ai_detail()

    def _selected_model_id(self):
        selection = self.model_tree.selection()
        return selection[0] if selection else ""

    def on_model_select(self, _event=None):
        self._update_ai_detail()

    def _update_ai_detail(self):
        model_id = self._selected_model_id()
        if not model_id:
            self.ai_detail_var.set(_("settings_ai_no_selection"))
            return

        status = self.model_manager.status(model_id)
        spec = status.spec
        detail = "\n".join([
            spec.name,
            spec.description,
            f"{_('model_detail_status')}: {status.message}",
            f"{_('model_detail_path')}: {status.path or '-'}",
            f"{_('model_detail_license')}: {spec.license_name or '-'}",
            f"{_('model_detail_notes')}: {spec.notes or '-'}",
        ])
        self.ai_detail_var.set(detail)

    def pick_selected_model_path(self):
        model_id = self._selected_model_id()
        if not model_id:
            self.feedback.set_info(_("settings_local_ai_title"), _("settings_ai_no_selection"))
            return

        selected = filedialog.askopenfilename(
            title=_("settings_ai_pick_model"),
            filetypes=[
                ("AI model files", "*.gguf *.onnx *.bin *.safetensors *.pdmodel *.traineddata *.ct2"),
                ("All files", "*.*"),
            ],
        )
        if not selected:
            selected = filedialog.askdirectory(title=_("settings_ai_pick_model"))
        if not selected:
            return

        self.model_manager.set_model_path(model_id, selected)
        self.refresh_ai_models()
        self.feedback.set_success(_("str_success"), _("settings_ai_path_saved"))

    def download_selected_model(self):
        model_id = self._selected_model_id()
        if not model_id:
            self.feedback.set_info(_("settings_local_ai_title"), _("settings_ai_no_selection"))
            return
        if self._download_running:
            return

        spec = self.model_manager.get_spec(model_id)
        if not spec:
            return
        if not spec.download_url:
            if spec.source_url:
                webbrowser.open(spec.source_url)
            self.feedback.set_info(_("settings_local_ai_title"), _("settings_ai_download_unavailable"))
            return

        self._download_running = True
        self.ai_download_btn.config(state="disabled")
        self.feedback.set_busy(_("settings_ai_download_started"))

        def _progress(downloaded, total):
            if total:
                pct = int(downloaded * 100 / total)
                self.after(0, self.ai_detail_var.set,
                           f"{spec.name}\n{_('model_detail_downloading')}: {pct}%")

        def _worker():
            try:
                path = self.model_manager.download_model(model_id, progress=_progress)
                self.after(0, self._download_done, str(path), None)
            except Exception as exc:
                # Catch everything: any other error used to escape the thread
                # and leave the Download button disabled for good.
                self.after(0, self._download_done, "", str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    def _download_done(self, path, error):
        self._download_running = False
        self.ai_download_btn.config(state="normal")
        self.refresh_ai_models()
        if error:
            self.feedback.set_error(_("str_error"), error)
        else:
            self.feedback.set_success(_("str_success"), _("settings_ai_download_done").format(path=path))

    def test_selected_model(self):
        model_id = self._selected_model_id()
        if not model_id:
            self.feedback.set_info(_("settings_local_ai_title"), _("settings_ai_no_selection"))
            return

        self.ai_test_btn.config(state="disabled")

        def _worker():
            try:
                ok, message = self.model_manager.test_model(model_id)
            except Exception as exc:
                ok, message = False, str(exc)
            self.after(0, self._test_done, ok, message)

        threading.Thread(target=_worker, daemon=True).start()

    def _test_done(self, ok, message):
        self.ai_test_btn.config(state="normal")
        title = _("settings_ai_test_ok") if ok else _("settings_ai_test_fail")
        if ok:
            self.feedback.set_success(title, message)
        else:
            self.feedback.set_error(title, message)
        self.refresh_ai_models()

    def clear_history(self):
        cfg.clear_recent_files()
        self.feedback.set_success(_("str_success"), _("settings_cleared"))

    def _selected_language(self):
        name = self.lang_var.get()
        return next((code for code, label in LANGUAGES.items() if label == name), name)

    def save_settings(self):
        language = self._selected_language()
        cfg.set("language", language)
        cfg.set("close_to_tray", self.tray_var.get())
        cfg.set("sound_enabled", self.sound_var.get())
        cfg.set("default_output_dir", self.out_dir_var.get())
        if self.ai_root_var.get().strip():
            self.model_manager.set_model_root(self.ai_root_var.get().strip())
        self.refresh_ai_models()
        if language != self._ui_language:
            self._offer_restart()
        else:
            self.feedback.set_success(_("str_success"), _("settings_saved"))

    def _offer_restart(self):
        """Every label is built once at start-up, so a new language only shows
        after a restart. Closing the window just hides it in the tray, so
        offer to do the restart rather than leave the user wondering."""
        restart = getattr(self.nametowidget("."), "pdf_aura_restart", None)
        if restart and messagebox.askyesno(_("settings_restart_title"), _("settings_restart_body"),
                                           parent=self.winfo_toplevel()):
            error = restart()
            if error is None:
                return
            self.feedback.set_error(_("str_error"), _("settings_restart_failed").format(error=error))
            return
        self.feedback.set_success(_("str_success"), _("settings_saved_restart_later"))


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(_("txt_settings"))
        self.transient(parent)
        self.geometry("1060x760")
        self.minsize(920, 660)
        styles.themed(self, bg=P.canvas)

        shell = ttk.Frame(self, style="App.TFrame", padding=24)
        shell.pack(fill="both", expand=True)

        head = ttk.Frame(shell, style="App.TFrame")
        head.pack(fill="x", pady=(0, 16))
        ttk.Label(head, text=_("txt_settings"), style="PageTitle.TLabel").pack(side="left")
        close = ttk.Button(head, text=_("str_close"), command=self.destroy, style="Canvas.Secondary.TButton")
        close.pack(side="right")
        Tooltip(close, "Esc")
        self.bind("<Escape>", lambda _e: self.destroy())

        panel = SettingsPanel(shell)
        panel.pack(fill="both", expand=True)

        self.grab_set()
