import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from src.core.batch import batch_compress_dir, batch_convert_dir, batch_rename_dir
from src.core.lang_manager import _
from src.core.task_manager import TaskContext, CancelledError
from src.gui.helpers import InlineFeedback, ProgressFooter, build_tool_header, quick_error


class BatchTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        self._task_ctx = None

        self.input_dir_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.action_var = tk.StringVar(value=_("batch_compress"))
        self.status_var = tk.StringVar(value=_("str_ready"))
        self.compress_qual_var = tk.StringVar(value="screen")
        self.convert_mode_var = tk.StringVar(value="pdf2img")
        self.rename_rule_var = tk.StringVar(value="[TARIH]_[ORIJINAL_AD]_Sayfa[SAYFA_SAYISI]")
        self.build_ui()

    def build_ui(self):
        shell = ttk.Frame(self.parent, style="App.TFrame")
        shell.pack(fill="both", expand=True)

        build_tool_header(shell, _("txt_batch"), _("batch_start_btn"), _("batch_rename_hint"), badge_text=_("batch_main_type"))

        body = ttk.Frame(shell, style="App.TFrame")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, style="Surface.TFrame", padding=22)
        left.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text=_("str_input_folder"), style="Field.TLabel").pack(anchor="w")
        input_row = ttk.Frame(left, style="Surface.TFrame")
        input_row.pack(fill="x", pady=(8, 0))
        ttk.Entry(input_row, textvariable=self.input_dir_var, style="Dark.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(input_row, text=_("str_select_dir"), command=self.choose_input_dir, style="Secondary.TButton").pack(side="right")

        ttk.Label(left, text=_("batch_main_type"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        self.mode_combo = ttk.Combobox(
            left,
            textvariable=self.action_var,
            values=[_("batch_compress"), _("batch_convert"), _("batch_rename")],
            state="readonly",
            width=30,
            style="Dark.TCombobox",
        )
        self.mode_combo.pack(anchor="w", pady=(8, 0))
        self.mode_combo.bind("<<ComboboxSelected>>", lambda _event: self.switch_mode())

        self.dyn_frame = ttk.Frame(left, style="Panel.TFrame", padding=16)
        self.dyn_frame.pack(fill="x", pady=(18, 0))

        self.f_compress = ttk.Frame(self.dyn_frame, style="Panel.TFrame")
        ttk.Label(self.f_compress, text=_("batch_compress_quality"), style="Field.TLabel").pack(anchor="w")
        ttk.Combobox(self.f_compress, textvariable=self.compress_qual_var, values=["screen", "ebook", "printer", "prepress"], state="readonly", style="Dark.TCombobox").pack(anchor="w", pady=(8, 0))

        self.f_convert = ttk.Frame(self.dyn_frame, style="Panel.TFrame")
        ttk.Radiobutton(self.f_convert, text=_("batch_radio_pdf2img"), variable=self.convert_mode_var, value="pdf2img", style="Flat.TRadiobutton").pack(anchor="w")
        ttk.Radiobutton(self.f_convert, text=_("batch_radio_img2pdf"), variable=self.convert_mode_var, value="img2pdf", style="Flat.TRadiobutton").pack(anchor="w", pady=(8, 0))

        self.f_rename = ttk.Frame(self.dyn_frame, style="Panel.TFrame")
        ttk.Label(self.f_rename, text=_("batch_rename_rule"), style="Field.TLabel").pack(anchor="w")
        ttk.Entry(self.f_rename, textvariable=self.rename_rule_var, style="Dark.TEntry").pack(fill="x", pady=(8, 0))
        ttk.Label(self.f_rename, text=_("batch_rename_hint"), style="Hint.TLabel", wraplength=640, justify="left").pack(anchor="w", pady=(10, 0))

        self.frames = {
            _("batch_compress"): self.f_compress,
            _("batch_convert"): self.f_convert,
            _("batch_rename"): self.f_rename,
        }
        self.switch_mode()

        ttk.Label(left, text=_("str_output_folder_label"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        output_row = ttk.Frame(left, style="Surface.TFrame")
        output_row.pack(fill="x", pady=(8, 0))
        ttk.Entry(output_row, textvariable=self.output_dir_var, style="Dark.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(output_row, text=_("str_select_dir"), command=self.choose_output_dir, style="Ghost.TButton").pack(side="right")

        self.footer = ProgressFooter(left, _("batch_start_btn"), self.start_action, button_style="Accent.TButton", progress_style="Accent.Horizontal.TProgressbar")
        self.footer.pack(fill="x", pady=(22, 0))

        log_card = ttk.Frame(left, style="Panel.TFrame", padding=14)
        log_card.pack(fill="both", expand=True, pady=(18, 0))
        ttk.Label(log_card, text=_("batch_log_title"), style="Section.TLabel").pack(anchor="w")
        self.log_text = tk.Text(log_card, height=10, bg="#fbfdff", fg="#18212b", bd=0, state="disabled", font=("Consolas", 9), wrap="word")
        self.log_text.pack(fill="both", expand=True, pady=(10, 0))

        right = ttk.Frame(body, style="App.TFrame")
        right.pack(side="left", fill="y", padx=(18, 0))
        self.feedback = InlineFeedback(right)
        self.feedback.pack(fill="x")
        self.feedback.set_info(_("batch_main_type"), _("batch_rename_hint"))

    def switch_mode(self):
        for frame in self.frames.values():
            frame.pack_forget()
        current = self.action_var.get()
        if current in self.frames:
            self.frames[current].pack(fill="x", expand=True)
        if hasattr(self, "feedback"):
            self.feedback.set_info(_("batch_main_type"), current)

    def choose_input_dir(self):
        selected = filedialog.askdirectory(title=_("batch_dialog_input"))
        if selected:
            self.input_dir_var.set(selected)

    def choose_output_dir(self):
        selected = filedialog.askdirectory(title=_("batch_dialog_output"))
        if selected:
            self.output_dir_var.set(selected)

    def _append_log(self, text):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _update_progress(self, current, total, log_message=""):
        def ui_update():
            self.footer.update_progress(current, total, "")
            pct = int((current / max(total, 1)) * 100)
            self.status_var.set(_("batch_progress").format(pct=pct, cur=current, total=total))
            if log_message:
                self._append_log(log_message)
        self.app_root.after(0, ui_update)

    def handle_external_drop(self, file_path):
        if os.path.isdir(file_path):
            if not self.input_dir_var.get().strip():
                self.input_dir_var.set(file_path)
            elif not self.output_dir_var.get().strip():
                self.output_dir_var.set(file_path)

    def _cancel_task(self):
        if self._task_ctx:
            self._task_ctx.cancel()

    def start_action(self):
        inp = self.input_dir_var.get().strip()
        out = self.output_dir_var.get().strip()

        if not inp or not os.path.isdir(inp):
            quick_error(_("err_select_valid_input_dir"), self.footer.action_button, None, self.status_var, self.feedback)
            return
        if not out or not os.path.isdir(out):
            quick_error(_("err_select_valid_output_dir"), self.footer.action_button, None, self.status_var, self.feedback)
            return

        self._task_ctx = TaskContext(progress_callback=self._update_progress)
        self.footer.start_busy(cancel_callback=self._cancel_task)
        self.feedback.set_busy(_("str_processing"))

        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        self._append_log(_("batch_log_started").format(path=inp))

        mode = self.action_var.get()
        threading.Thread(target=self._run_job, args=(mode, inp, out), daemon=True).start()

    def _run_job(self, mode, inp, out):
        try:
            if mode == _("batch_compress"):
                succ, errs = batch_compress_dir(inp, out, self.compress_qual_var.get(), None, ctx=self._task_ctx)
            elif mode == _("batch_convert"):
                succ, errs = batch_convert_dir(inp, out, self.convert_mode_var.get(), None, ctx=self._task_ctx)
            else:
                succ, errs = batch_rename_dir(inp, out, self.rename_rule_var.get(), None, ctx=self._task_ctx)
            self.app_root.after(0, self._finalize_job, succ, errs, out)
        except CancelledError:
            self.app_root.after(0, self._cancelled)
        except Exception as exc:
            def fail():
                self.footer.stop_busy()
                self.status_var.set(_("err_critical"))
                self.feedback.set_error(_("err_critical"), str(exc))
            self.app_root.after(0, fail)

    def _cancelled(self):
        self.footer.stop_busy()
        self.status_var.set(_("perf_cancelled"))
        self.feedback.set_cancelled()
        self._append_log("\n--- " + _("perf_cancelled") + " ---")

    def _finalize_job(self, succ, errs, out):
        self.footer.finish_success()
        self.status_var.set(_("batch_done"))
        self._append_log(_("batch_log_ended"))
        self._append_log(_("batch_success_count").format(succ=succ, errs=len(errs)))

        message = _("batch_result").format(succ=succ, errs=len(errs))
        if errs:
            message += _("batch_result_errors").format(dir=out)
        self.feedback.set_success(_("batch_result_title"), message, out)
