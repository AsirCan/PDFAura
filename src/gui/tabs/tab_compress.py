import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from src.core.compress import VALID_QUALITIES, compress_pdf
from src.core.lang_manager import _
from src.core.task_manager import TaskContext, CancelledError
from src.gui.helpers import InlineFeedback, ProgressFooter, bind_preview, build_tool_header, quick_error
from src.utils.file_helper import format_size_mb, suggest_output_path


class CompressTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        self._task_ctx = None

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.quality_var = tk.StringVar(value="ebook")
        self.status_var = tk.StringVar(value=_("str_ready"))

        bind_preview(self.app_root, self.input_var)
        self.build_ui()

    def build_ui(self):
        shell = ttk.Frame(self.parent, style="App.TFrame")
        shell.pack(fill="both", expand=True)

        build_tool_header(
            shell,
            _("txt_compress"),
            _("compress_btn"),
            _("compress_quality_hint"),
            badge_text=_("str_drag_drop_hint"),
        )

        body = ttk.Frame(shell, style="App.TFrame")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, style="Surface.TFrame", padding=22)
        left.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text=_("str_file_selection"), style="Section.TLabel").pack(anchor="w")
        ttk.Label(left, text=_("str_input_pdf"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        input_row = ttk.Frame(left, style="Surface.TFrame")
        input_row.pack(fill="x", pady=(8, 0))
        self.input_entry = ttk.Entry(input_row, textvariable=self.input_var, style="Dark.TEntry")
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.input_button = ttk.Button(input_row, text=_("str_browse"), command=self.choose_input_pdf, style="Secondary.TButton")
        self.input_button.pack(side="right")

        ttk.Label(left, text=_("str_output_pdf"), style="Field.TLabel").pack(anchor="w", pady=(16, 0))
        output_row = ttk.Frame(left, style="Surface.TFrame")
        output_row.pack(fill="x", pady=(8, 0))
        self.output_entry = ttk.Entry(output_row, textvariable=self.output_var, style="Dark.TEntry")
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.output_button = ttk.Button(output_row, text=_("str_save_as"), command=self.choose_output_pdf, style="Ghost.TButton")
        self.output_button.pack(side="right")

        settings = ttk.Frame(left, style="Panel.TFrame", padding=16)
        settings.pack(fill="x", pady=(22, 0))
        ttk.Label(settings, text=_("compress_settings"), style="Section.TLabel").pack(anchor="w")
        ttk.Label(settings, text=_("compress_quality"), style="Field.TLabel").pack(anchor="w", pady=(14, 0))
        self.quality_combo = ttk.Combobox(settings, textvariable=self.quality_var, values=VALID_QUALITIES, state="readonly", width=18, style="Dark.TCombobox")
        self.quality_combo.pack(anchor="w", pady=(8, 0))
        ttk.Label(settings, text=_("compress_quality_hint"), style="Hint.TLabel", wraplength=640, justify="left").pack(anchor="w", pady=(10, 0))

        self.footer = ProgressFooter(left, _("compress_btn"), self.start_compression, button_style="Accent.TButton", progress_style="Accent.Horizontal.TProgressbar")
        self.footer.pack(fill="x", pady=(22, 0))

        right = ttk.Frame(body, style="App.TFrame")
        right.pack(side="left", fill="y", padx=(18, 0))
        self.feedback = InlineFeedback(right)
        self.feedback.pack(fill="x")
        self.feedback.set_info(_("compress_settings"), _("compress_quality_hint"))

    def choose_input_pdf(self):
        selected = filedialog.askopenfilename(title=_("compress_dialog_input"), filetypes=[("PDF", "*.pdf")])
        if selected:
            self.input_var.set(selected)
            if not self.output_var.get().strip():
                self.output_var.set(suggest_output_path(selected))

    def choose_output_pdf(self):
        init = ""
        current = self.input_var.get().strip()
        if current:
            init = os.path.basename(suggest_output_path(current))
        selected = filedialog.asksaveasfilename(
            title=_("compress_dialog_output"),
            defaultextension=".pdf",
            initialfile=init,
            filetypes=[("PDF", "*.pdf")],
        )
        if selected:
            self.output_var.set(selected)

    def handle_external_drop(self, file_path):
        if file_path.lower().endswith(".pdf"):
            self.input_var.set(file_path)
            if not self.output_var.get().strip():
                self.output_var.set(suggest_output_path(file_path))

    def _cancel_task(self):
        if self._task_ctx:
            self._task_ctx.cancel()

    def start_compression(self):
        input_pdf = self.input_var.get().strip()
        output_pdf = self.output_var.get().strip()
        quality = self.quality_var.get().strip().lower()

        if quality not in VALID_QUALITIES:
            quick_error(f"{_('err_select_quality')}{', '.join(VALID_QUALITIES)}", self.footer.action_button, None, self.status_var, self.feedback)
            return
        if not input_pdf or not os.path.isfile(input_pdf):
            quick_error(_("err_select_valid_pdf"), self.footer.action_button, None, self.status_var, self.feedback)
            return
        if not output_pdf:
            quick_error(_("err_set_output"), self.footer.action_button, None, self.status_var, self.feedback)
            return

        def _on_progress(current, total, message=""):
            self.app_root.after(0, self.footer.update_progress, current, total, message)

        self._task_ctx = TaskContext(progress_callback=_on_progress)
        self.footer.start_busy(cancel_callback=self._cancel_task)
        self.feedback.set_busy(_("compress_running"))
        self.status_var.set(_("compress_running"))
        threading.Thread(target=self._run_compress, args=(input_pdf, output_pdf, quality), daemon=True).start()

    def _run_compress(self, input_pdf, output_pdf, quality):
        try:
            original_size = format_size_mb(input_pdf)
            compress_pdf(input_pdf, output_pdf, quality, ctx=self._task_ctx)
            if not os.path.isfile(output_pdf):
                raise RuntimeError(_("err_output_not_created"))
            compressed_size = format_size_mb(output_pdf)
            message = (
                f"{_('compress_result_original')}{original_size:.2f} MB\n"
                f"{_('compress_result_compressed')}{compressed_size:.2f} MB\n"
                f"{_('compress_result_quality')}{quality}\n"
                f"{_('compress_result_saved')}{output_pdf}"
            )
            self.app_root.after(0, self._on_done, message, output_pdf)
        except CancelledError:
            self.app_root.after(0, self._on_cancelled)
        except Exception as exc:
            self.app_root.after(0, self._on_error, str(exc))

    def _on_done(self, message, output_pdf):
        self.footer.finish_success()
        self.status_var.set(_("compress_done"))
        self.feedback.set_success(_("compress_done"), message, output_pdf)

    def _on_cancelled(self):
        self.footer.stop_busy()
        self.status_var.set(_("perf_cancelled"))
        self.feedback.set_cancelled()

    def _on_error(self, error_msg):
        self.footer.stop_busy()
        self.status_var.set(_("compress_fail"))
        self.feedback.set_error(_("compress_fail"), error_msg)
