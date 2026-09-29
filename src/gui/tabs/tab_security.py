import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from src.core.errors import friendly_error
from src.core.lang_manager import _
from src.core.security import add_watermark_to_pdf, check_new_password, decrypt_pdf, encrypt_pdf
from src.core.task_manager import TaskContext, CancelledError
from src.gui.widgets import SegmentedControl
from src.gui.helpers import InlineFeedback, ProgressFooter, ToolLayout, bind_preview, confirm_overwrite, quick_error


class SecurityTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        self._task_ctx = None

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        # Changing the operation used to overwrite a path the user picked.
        self._output_chosen = False
        self.mode_var = tk.StringVar(value=_("security_encrypt"))
        self.password_var = tk.StringVar()
        self.confirm_var = tk.StringVar()
        self.watermark_text_var = tk.StringVar(value="GIZLI")
        self.status_var = tk.StringVar(value=_("str_ready"))

        bind_preview(self.app_root, self.input_var)
        self.build_ui()

    def build_ui(self):
        self.layout = ToolLayout(self.parent, _("hint_security"))
        left = self.layout.form

        ttk.Label(left, text=_("str_input_pdf"), style="Field.TLabel").pack(anchor="w")
        input_row = ttk.Frame(left, style="Surface.TFrame")
        input_row.pack(fill="x", pady=(8, 0))
        self.input_entry = ttk.Entry(input_row, textvariable=self.input_var, style="Input.TEntry")
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.input_button = ttk.Button(input_row, text=_("str_browse"), command=self.choose_input_pdf, style="Secondary.TButton")
        self.input_button.pack(side="right")

        ttk.Label(left, text=_("security_op_type"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        self.mode_picker = SegmentedControl(
            left, self.mode_var,
            [_("security_encrypt"), _("security_decrypt"), _("security_watermark")],
            command=self.switch_mode)
        self.mode_picker.pack(fill="x", pady=(8, 0))

        self.dynamic_frame = ttk.Frame(left, style="PanelCard.TFrame", padding=16)
        self.dynamic_frame.pack(fill="x", pady=(18, 0))

        self.password_frame = ttk.Frame(self.dynamic_frame, style="Panel.TFrame")
        ttk.Label(self.password_frame, text=_("security_password"), style="Field.TLabel").pack(anchor="w")
        self.password_entry = ttk.Entry(self.password_frame, textvariable=self.password_var, show="*", style="Input.TEntry")
        self.password_entry.pack(fill="x", pady=(8, 0))

        # Only shown when encrypting; removing a password needs no confirmation.
        self.confirm_row = ttk.Frame(self.password_frame, style="Panel.TFrame")
        ttk.Label(self.confirm_row, text=_("security_password_confirm"), style="Field.TLabel").pack(anchor="w", pady=(12, 0))
        self.confirm_entry = ttk.Entry(self.confirm_row, textvariable=self.confirm_var, show="*", style="Input.TEntry")
        self.confirm_entry.pack(fill="x", pady=(8, 0))

        self.watermark_frame = ttk.Frame(self.dynamic_frame, style="Panel.TFrame")
        ttk.Label(self.watermark_frame, text=_("security_watermark_text"), style="Field.TLabel").pack(anchor="w")
        self.watermark_entry = ttk.Entry(self.watermark_frame, textvariable=self.watermark_text_var, style="Input.TEntry")
        self.watermark_entry.pack(fill="x", pady=(8, 0))

        self.frames = {
            _("security_encrypt"): self.password_frame,
            _("security_decrypt"): self.password_frame,
            _("security_watermark"): self.watermark_frame,
        }
        self.switch_mode()

        ttk.Label(left, text=_("str_output_pdf"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        output_row = ttk.Frame(left, style="Surface.TFrame")
        output_row.pack(fill="x", pady=(8, 0))
        self.output_entry = ttk.Entry(output_row, textvariable=self.output_var, style="Input.TEntry")
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.output_button = ttk.Button(output_row, text=_("str_save_as"), command=self.choose_output_pdf, style="Secondary.TButton")
        self.output_button.pack(side="right")

        self.footer = ProgressFooter(left, _("str_apply"), self.start_action)
        self.footer.pack(fill="x", pady=(24, 0))

        self.feedback = InlineFeedback(left)
        self.feedback.pack(fill="x", pady=(16, 0))
        self.feedback.set_info(_("security_op_type"), _("security_watermark_text"))

    def switch_mode(self):
        for frame in self.frames.values():
            frame.pack_forget()
        current = self.mode_var.get()
        if current in self.frames:
            self.frames[current].pack(fill="x", expand=True)
        if current == _("security_encrypt"):
            self.confirm_row.pack(fill="x")
        else:
            self.confirm_row.pack_forget()
        if self.input_var.get().strip():
            self._set_input(self.input_var.get().strip())

    def choose_input_pdf(self):
        selected = filedialog.askopenfilename(title=_("security_dialog_input"), filetypes=[("PDF", "*.pdf")])
        if selected:
            self._set_input(selected)

    def _set_input(self, path):
        self.input_var.set(path)
        if self._output_chosen:
            return
        base, ext = os.path.splitext(path)
        current = self.mode_var.get()
        if current == _("security_encrypt"):
            suffix = _("security_suffix_encrypted")
        elif current == _("security_decrypt"):
            suffix = _("security_suffix_decrypted")
        else:
            suffix = _("security_suffix_watermarked")
        self.output_var.set(f"{base}{suffix}{ext}")

    def choose_output_pdf(self):
        selected = filedialog.asksaveasfilename(title=_("security_dialog_output"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.output_var.set(selected)
            self._output_chosen = True

    def handle_external_drop(self, file_path):
        if file_path.lower().endswith(".pdf"):
            self._set_input(file_path)

    def _cancel_task(self):
        if self._task_ctx:
            self._task_ctx.cancel()

    def start_action(self):
        input_pdf = self.input_var.get().strip()
        output_pdf = self.output_var.get().strip()
        mode = self.mode_var.get()

        if not input_pdf or not os.path.isfile(input_pdf):
            quick_error(_("err_select_valid_file"), self.footer.action_button, None, self.status_var, self.feedback)
            return
        if not output_pdf:
            quick_error(_("err_set_output"), self.footer.action_button, None, self.status_var, self.feedback)
            return

        # Validate on the main thread so the user is told before any work starts.
        if mode == _("security_encrypt"):
            try:
                check_new_password(self.password_var.get(), self.confirm_var.get())
            except ValueError as exc:
                quick_error(str(exc), self.footer.action_button, None, self.status_var, self.feedback)
                return
        elif mode == _("security_decrypt") and not self.password_var.get():
            quick_error(_("err_password_empty"), self.footer.action_button, None, self.status_var, self.feedback)
            return

        if not self._output_chosen and not confirm_overwrite(output_pdf, self.app_root):
            return

        # Read the fields here; a worker must not touch Tk variables.
        password = self.password_var.get()
        watermark_text = self.watermark_text_var.get().strip()

        def _on_progress(current, total, message=""):
            self.app_root.after(0, self.footer.update_progress, current, total, message)

        self._task_ctx = TaskContext(progress_callback=_on_progress)
        busy_text = _("security_running").format(mode=mode)
        self.footer.start_busy(cancel_callback=self._cancel_task)
        self.feedback.set_busy(busy_text)
        self.status_var.set(busy_text)
        threading.Thread(target=self._run_action,
                         args=(input_pdf, output_pdf, mode, password, watermark_text),
                         daemon=True).start()

    def _run_action(self, input_pdf, output_pdf, mode, password, watermark_text):
        try:
            if mode == _("security_encrypt"):
                encrypt_pdf(input_pdf, output_pdf, password, ctx=self._task_ctx)
                message = _("security_result_encrypt").format(output=output_pdf)
            elif mode == _("security_decrypt"):
                decrypt_pdf(input_pdf, output_pdf, password, ctx=self._task_ctx)
                message = _("security_result_decrypt").format(output=output_pdf)
            elif mode == _("security_watermark"):
                text = watermark_text
                if not text:
                    raise ValueError(_("err_watermark_empty"))
                add_watermark_to_pdf(input_pdf, output_pdf, text, ctx=self._task_ctx)
                message = _("security_result_watermark").format(output=output_pdf)
            else:
                raise ValueError(f"{_('err_unknown_op')}{mode}")

            self.app_root.after(0, self._on_done, message, output_pdf)
        except CancelledError:
            self.app_root.after(0, self._on_cancelled)
        except Exception as exc:
            self.app_root.after(0, self._on_error, friendly_error(exc))

    def _on_done(self, message, output_pdf):
        self.footer.finish_success()
        self.status_var.set(_("str_success"))
        self.feedback.set_success(_("str_success"), message, output_pdf)

    def _on_cancelled(self):
        self.footer.stop_busy()
        self.status_var.set(_("perf_cancelled"))
        self.feedback.set_cancelled()

    def _on_error(self, error_msg):
        self.footer.stop_busy()
        self.status_var.set(_("str_failed"))
        self.feedback.set_error(_("str_failed"), error_msg)
