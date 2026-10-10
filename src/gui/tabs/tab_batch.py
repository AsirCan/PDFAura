import os
import tkinter as tk
from tkinter import ttk, filedialog

from src.app.tools import mode_from_label
from src.core.lang_manager import _
from src.gui import styles
from src.gui.styles import P
from src.gui.widgets import SegmentedControl
from src.gui.helpers import InlineFeedback, ProgressFooter, ToolLayout, ToolRun, follow_width


class BatchTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root

        self.input_dir_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.action_var = tk.StringVar(value=_("batch_compress"))
        self.status_var = tk.StringVar(value=_("str_ready"))
        self.compress_qual_var = tk.StringVar(value="screen")
        self.convert_mode_var = tk.StringVar(value="pdf2img")
        self.rename_rule_var = tk.StringVar(value=_("batch_rename_default"))
        self.build_ui()

    def build_ui(self):
        self.layout = ToolLayout(self.parent, _("hint_batch"))
        left = self.layout.form

        ttk.Label(left, text=_("str_input_folder"), style="Field.TLabel").pack(anchor="w")
        input_row = ttk.Frame(left, style="Surface.TFrame")
        input_row.pack(fill="x", pady=(8, 0))
        ttk.Entry(input_row, textvariable=self.input_dir_var, style="Input.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(input_row, text=_("str_select_dir"), command=self.choose_input_dir, style="Secondary.TButton").pack(side="right")

        ttk.Label(left, text=_("batch_main_type"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        self.mode_picker = SegmentedControl(
            left, self.action_var,
            [_("batch_compress"), _("batch_convert"), _("batch_rename")],
            command=self.switch_mode)
        self.mode_picker.pack(fill="x", pady=(8, 0))

        self.dyn_frame = ttk.Frame(left, style="PanelCard.TFrame", padding=16)
        self.dyn_frame.pack(fill="x", pady=(18, 0))

        self.f_compress = ttk.Frame(self.dyn_frame, style="Panel.TFrame")
        ttk.Label(self.f_compress, text=_("batch_compress_quality"), style="Field.TLabel").pack(anchor="w")
        ttk.Combobox(self.f_compress, textvariable=self.compress_qual_var, values=["screen", "ebook", "printer", "prepress"], state="readonly", style="Input.TCombobox").pack(anchor="w", pady=(8, 0))

        self.f_convert = ttk.Frame(self.dyn_frame, style="Panel.TFrame")
        ttk.Radiobutton(self.f_convert, text=_("batch_radio_pdf2img"), variable=self.convert_mode_var, value="pdf2img", style="Flat.TRadiobutton").pack(anchor="w")
        ttk.Radiobutton(self.f_convert, text=_("batch_radio_img2pdf"), variable=self.convert_mode_var, value="img2pdf", style="Flat.TRadiobutton").pack(anchor="w", pady=(8, 0))

        self.f_rename = ttk.Frame(self.dyn_frame, style="Panel.TFrame")
        ttk.Label(self.f_rename, text=_("batch_rename_rule"), style="Field.TLabel").pack(anchor="w")
        ttk.Entry(self.f_rename, textvariable=self.rename_rule_var, style="Input.TEntry").pack(fill="x", pady=(8, 0))
        rename_hint = ttk.Label(self.f_rename, text=_("batch_rename_hint"), style="Hint.TLabel", justify="left")
        rename_hint.pack(anchor="w", pady=(10, 0))
        follow_width(rename_hint, self.dyn_frame, 32)

        self.frames = {
            _("batch_compress"): self.f_compress,
            _("batch_convert"): self.f_convert,
            _("batch_rename"): self.f_rename,
        }
        self.switch_mode()

        ttk.Label(left, text=_("str_output_folder_label"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        output_row = ttk.Frame(left, style="Surface.TFrame")
        output_row.pack(fill="x", pady=(8, 0))
        ttk.Entry(output_row, textvariable=self.output_dir_var, style="Input.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(output_row, text=_("str_select_dir"), command=self.choose_output_dir, style="Secondary.TButton").pack(side="right")

        self.footer = ProgressFooter(left, _("batch_start_btn"), self.start_action)
        self.footer.pack(fill="x", pady=(24, 0))

        log_card = ttk.Frame(left, style="PanelCard.TFrame", padding=14)
        log_card.pack(fill="both", expand=True, pady=(18, 0))
        ttk.Label(log_card, text=_("batch_log_title"), style="Section.TLabel").pack(anchor="w")
        # width=1: a Text defaults to 80 columns, which demanded ~560 px and
        # squeezed the preview panel off the right of the window.
        self.log_text = styles.themed(
            tk.Text(log_card, height=10, width=1, bd=0, state="disabled", font=styles.font("mono"),
                    wrap="word", padx=10, pady=8, highlightthickness=1),
            bg=P.surface_subtle, fg=P.text, insertbackground=P.text,
            highlightbackground=P.border_subtle, highlightcolor=P.border_subtle,
            selectbackground=P.accent_subtle_hover, selectforeground=P.text)
        self.log_text.pack(fill="both", expand=True, pady=(10, 0))

        self.feedback = InlineFeedback(left)
        self.feedback.pack(fill="x", pady=(16, 0))
        self.feedback.set_info(_("batch_main_type"), _("batch_rename_hint"))
        self.run = ToolRun(self.app_root, self.footer, self.feedback, self.status_var,
                           on_progress=self._update_progress, on_done=self._finalize_job,
                           on_cancelled=self._cancelled)

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
        self.footer.update_progress(current, total, "")
        pct = int((current / max(total, 1)) * 100)
        self.status_var.set(_("batch_progress").format(pct=pct, cur=current, total=total))
        if log_message:
            self._append_log(log_message)

    def handle_external_drop(self, file_path):
        if os.path.isdir(file_path):
            if not self.input_dir_var.get().strip():
                self.input_dir_var.set(file_path)
            elif not self.output_dir_var.get().strip():
                self.output_dir_var.set(file_path)

    def start_action(self):
        inp = self.input_dir_var.get().strip()
        # Every setting is read here, on the main thread; the job gets values.
        job = self.run.start("batch", {
            "mode": mode_from_label("batch", self.action_var.get()),
            "input_dir": inp,
            "output_dir": self.output_dir_var.get().strip(),
            "quality": self.compress_qual_var.get(),
            "convert_mode": self.convert_mode_var.get(),
            "rename_rule": self.rename_rule_var.get(),
        })
        if job is None:
            return
        # The job's log lines arrive through after(), so they follow this.
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        self._append_log(_("batch_log_started").format(path=inp))

    def _cancelled(self):
        self._append_log("\n--- " + _("perf_cancelled") + " ---")

    def _finalize_job(self, outcome):
        """The panel shows the outcome (ToolRun); the log and the status
        line say how many files made it."""
        counts = outcome.details
        self._append_log(_("batch_log_ended"))
        self._append_log(_("batch_success_count").format(succ=counts["succeeded"], errs=counts["failed"]))
        status = {"error": "str_failed", "info": "str_ready"}.get(outcome.tone, "batch_done")
        self.status_var.set(_(status))
