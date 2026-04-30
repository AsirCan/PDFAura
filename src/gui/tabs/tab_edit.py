import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from src.core.common import get_pdf_page_count, parse_page_numbers
from src.core.edit import delete_pages_from_pdf, reorder_pages_in_pdf, rotate_pages_in_pdf
from src.core.lang_manager import _
from src.core.task_manager import TaskContext, CancelledError
from src.gui.helpers import InlineFeedback, ProgressFooter, bind_preview, build_tool_header, quick_error


class EditTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        self._task_ctx = None

        self.edit_input_var = tk.StringVar()
        self.edit_output_var = tk.StringVar()
        self.edit_mode_var = tk.StringVar(value=_("edit_mode_delete"))
        self.edit_pages_var = tk.StringVar()
        self.edit_angle_var = tk.StringVar(value="90")
        self.edit_order_var = tk.StringVar()
        self.edit_page_info_var = tk.StringVar(value="")
        self.edit_status_var = tk.StringVar(value=_("str_ready"))

        bind_preview(self.app_root, self.edit_input_var)
        self.build_ui()

    def build_ui(self):
        shell = ttk.Frame(self.parent, style="App.TFrame")
        shell.pack(fill="both", expand=True)

        build_tool_header(shell, _("txt_edit"), _("str_apply"), _("edit_order_hint"), badge_text=_("edit_operation"))

        body = ttk.Frame(shell, style="App.TFrame")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, style="Surface.TFrame", padding=22)
        left.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text=_("str_input_pdf"), style="Field.TLabel").pack(anchor="w")
        input_row = ttk.Frame(left, style="Surface.TFrame")
        input_row.pack(fill="x", pady=(8, 0))
        self.edit_input_entry = ttk.Entry(input_row, textvariable=self.edit_input_var, style="Dark.TEntry")
        self.edit_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.edit_input_button = ttk.Button(input_row, text=_("str_browse"), command=self.choose_edit_input_pdf, style="Secondary.TButton")
        self.edit_input_button.pack(side="right")
        ttk.Label(left, textvariable=self.edit_page_info_var, style="PageInfo.TLabel").pack(anchor="w", pady=(8, 0))

        ttk.Label(left, text=_("edit_operation"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        self.edit_mode_combo = ttk.Combobox(
            left,
            textvariable=self.edit_mode_var,
            values=[_("edit_mode_delete"), _("edit_mode_rotate"), _("edit_mode_reorder")],
            state="readonly",
            width=26,
            style="Dark.TCombobox",
        )
        self.edit_mode_combo.pack(anchor="w", pady=(8, 0))
        self.edit_mode_combo.bind("<<ComboboxSelected>>", lambda _event: self.switch_edit_mode())

        self.edit_dynamic = ttk.Frame(left, style="Panel.TFrame", padding=16)
        self.edit_dynamic.pack(fill="x", pady=(18, 0))

        self.edit_delete_frame = ttk.Frame(self.edit_dynamic, style="Panel.TFrame")
        ttk.Label(self.edit_delete_frame, text=_("edit_pages_to_delete"), style="Field.TLabel").pack(anchor="w")
        ttk.Entry(self.edit_delete_frame, textvariable=self.edit_pages_var, style="Dark.TEntry").pack(fill="x", pady=(8, 0))
        ttk.Label(self.edit_delete_frame, text=_("edit_delete_hint"), style="Hint.TLabel", wraplength=640, justify="left").pack(anchor="w", pady=(8, 0))

        self.edit_rotate_frame = ttk.Frame(self.edit_dynamic, style="Panel.TFrame")
        ttk.Label(self.edit_rotate_frame, text=_("edit_pages_to_rotate"), style="Field.TLabel").pack(anchor="w")
        ttk.Entry(self.edit_rotate_frame, textvariable=self.edit_pages_var, style="Dark.TEntry").pack(fill="x", pady=(8, 0))
        ttk.Label(self.edit_rotate_frame, text=_("edit_rotate_hint"), style="Hint.TLabel").pack(anchor="w", pady=(8, 0))
        angle_row = ttk.Frame(self.edit_rotate_frame, style="Panel.TFrame")
        angle_row.pack(anchor="w", pady=(10, 0))
        ttk.Label(angle_row, text=_("edit_angle"), style="Field.TLabel").pack(side="left")
        ttk.Combobox(angle_row, textvariable=self.edit_angle_var, values=["90", "180", "270"], state="readonly", width=8, style="Dark.TCombobox").pack(side="left", padx=(12, 0))
        ttk.Label(angle_row, text=_("edit_angle_hint"), style="Hint.TLabel").pack(side="left", padx=(12, 0))

        self.edit_reorder_frame = ttk.Frame(self.edit_dynamic, style="Panel.TFrame")
        ttk.Label(self.edit_reorder_frame, text=_("edit_new_order"), style="Field.TLabel").pack(anchor="w")
        ttk.Entry(self.edit_reorder_frame, textvariable=self.edit_order_var, style="Dark.TEntry").pack(fill="x", pady=(8, 0))
        ttk.Label(self.edit_reorder_frame, text=_("edit_order_hint"), style="Hint.TLabel", wraplength=640, justify="left").pack(anchor="w", pady=(8, 0))

        self.edit_frames = {
            _("edit_mode_delete"): self.edit_delete_frame,
            _("edit_mode_rotate"): self.edit_rotate_frame,
            _("edit_mode_reorder"): self.edit_reorder_frame,
        }
        self.switch_edit_mode()

        ttk.Label(left, text=_("str_output_pdf"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        output_row = ttk.Frame(left, style="Surface.TFrame")
        output_row.pack(fill="x", pady=(8, 0))
        self.edit_output_entry = ttk.Entry(output_row, textvariable=self.edit_output_var, style="Dark.TEntry")
        self.edit_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.edit_output_button = ttk.Button(output_row, text=_("str_save_as"), command=self.choose_edit_output_pdf, style="Ghost.TButton")
        self.edit_output_button.pack(side="right")

        self.footer = ProgressFooter(left, _("str_apply"), self.start_edit, button_style="Edit.TButton", progress_style="Edit.Horizontal.TProgressbar")
        self.footer.pack(fill="x", pady=(22, 0))

        right = ttk.Frame(body, style="App.TFrame")
        right.pack(side="left", fill="y", padx=(18, 0))
        self.feedback = InlineFeedback(right)
        self.feedback.pack(fill="x")
        self.feedback.set_info(_("edit_operation"), _("edit_delete_hint"))

    def switch_edit_mode(self):
        for frame in self.edit_frames.values():
            frame.pack_forget()
        current = self.edit_mode_var.get()
        if current in self.edit_frames:
            self.edit_frames[current].pack(fill="x", expand=True)

    def choose_edit_input_pdf(self):
        selected = filedialog.askopenfilename(title=_("edit_dialog_input"), filetypes=[("PDF", "*.pdf")])
        if not selected:
            return
        self.edit_input_var.set(selected)
        try:
            total = get_pdf_page_count(selected)
            self.edit_page_info_var.set(_("edit_total_pages").format(count=total))
        except Exception as exc:
            self.edit_page_info_var.set(f"{_('str_error')}: {exc}")
        base, ext = os.path.splitext(selected)
        self.edit_output_var.set(f"{base}_düzenlenmiş{ext}")

    def choose_edit_output_pdf(self):
        selected = filedialog.asksaveasfilename(title=_("edit_dialog_output"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.edit_output_var.set(selected)

    def handle_external_drop(self, file_path):
        if file_path.lower().endswith(".pdf"):
            self.edit_input_var.set(file_path)
            try:
                total = get_pdf_page_count(file_path)
                self.edit_page_info_var.set(_("edit_total_pages").format(count=total))
            except Exception as exc:
                self.edit_page_info_var.set(f"{_('str_error')}: {exc}")
            base, ext = os.path.splitext(file_path)
            self.edit_output_var.set(f"{base}_düzenlenmiş{ext}")

    def _cancel_task(self):
        if self._task_ctx:
            self._task_ctx.cancel()

    def start_edit(self):
        input_pdf = self.edit_input_var.get().strip()
        output_pdf = self.edit_output_var.get().strip()
        mode = self.edit_mode_var.get()
        if not input_pdf or not os.path.isfile(input_pdf):
            quick_error(_("err_select_valid_file"), self.footer.action_button, None, self.edit_status_var, self.feedback)
            return
        if not output_pdf:
            quick_error(_("err_set_output"), self.footer.action_button, None, self.edit_status_var, self.feedback)
            return

        def _on_progress(current, total, message=""):
            self.app_root.after(0, self.footer.update_progress, current, total, message)

        self._task_ctx = TaskContext(progress_callback=_on_progress)
        busy_text = _("edit_running").format(mode=mode)
        self.footer.start_busy(cancel_callback=self._cancel_task)
        self.feedback.set_busy(busy_text)
        self.edit_status_var.set(busy_text)
        threading.Thread(target=self._run_edit, args=(input_pdf, output_pdf, mode), daemon=True).start()

    def _run_edit(self, input_pdf, output_pdf, mode):
        try:
            total = get_pdf_page_count(input_pdf)
            if mode == _("edit_mode_delete"):
                pages_text = self.edit_pages_var.get().strip()
                if not pages_text:
                    raise ValueError(_("edit_err_enter_delete"))
                pages = parse_page_numbers(pages_text, total)
                delete_pages_from_pdf(input_pdf, output_pdf, pages, ctx=self._task_ctx)
                remaining = total - len(pages)
                message = _("edit_result_delete").format(count=len(pages), remaining=remaining, output=output_pdf)
            elif mode == _("edit_mode_rotate"):
                pages_text = self.edit_pages_var.get().strip()
                angle = int(self.edit_angle_var.get())
                pages = parse_page_numbers(pages_text, total) if pages_text else list(range(1, total + 1))
                rotate_pages_in_pdf(input_pdf, output_pdf, pages, angle, ctx=self._task_ctx)
                message = _("edit_result_rotate").format(count=len(pages), angle=angle, output=output_pdf)
            elif mode == _("edit_mode_reorder"):
                order_text = self.edit_order_var.get().strip()
                if not order_text:
                    raise ValueError(_("edit_err_enter_order"))
                new_order = [int(chunk.strip()) for chunk in order_text.split(",")]
                reorder_pages_in_pdf(input_pdf, output_pdf, new_order, ctx=self._task_ctx)
                message = _("edit_result_reorder").format(count=len(new_order), output=output_pdf)
            else:
                raise ValueError(f"{_('err_unknown_op')}{mode}")

            self.app_root.after(0, self._on_done, message, output_pdf)
        except CancelledError:
            self.app_root.after(0, self._on_cancelled)
        except Exception as exc:
            self.app_root.after(0, self._on_error, str(exc))

    def _on_done(self, message, output_pdf):
        self.footer.finish_success()
        self.edit_status_var.set(_("edit_done"))
        self.feedback.set_success(_("edit_done"), message, output_pdf)

    def _on_cancelled(self):
        self.footer.stop_busy()
        self.edit_status_var.set(_("perf_cancelled"))
        self.feedback.set_cancelled()

    def _on_error(self, error_msg):
        self.footer.stop_busy()
        self.edit_status_var.set(_("edit_fail"))
        self.feedback.set_error(_("edit_fail"), error_msg)
