import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from src.core.common import get_pdf_page_count
from src.core.lang_manager import _
from src.core.split import split_pdf
from src.gui.helpers import InlineFeedback, bind_preview, build_tool_header, operation_done, quick_error, set_busy
from src.utils.file_helper import format_size_mb, suggest_split_output_path


class SplitTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root

        self.split_input_var = tk.StringVar()
        self.split_output_var = tk.StringVar()
        self.split_start_var = tk.StringVar(value="1")
        self.split_end_var = tk.StringVar(value="")
        self.split_status_var = tk.StringVar(value=_("str_ready"))
        self.split_page_info_var = tk.StringVar(value="")

        bind_preview(self.app_root, self.split_input_var)
        self.build_ui()

    def build_ui(self):
        shell = ttk.Frame(self.parent, style="App.TFrame")
        shell.pack(fill="both", expand=True)

        build_tool_header(
            shell,
            _("txt_split"),
            _("split_btn"),
            _("split_hint"),
            badge_text=_("split_page_range"),
        )

        body = ttk.Frame(shell, style="App.TFrame")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, style="Surface.TFrame", padding=22)
        left.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text=_("str_input_pdf"), style="Field.TLabel").pack(anchor="w")
        input_row = ttk.Frame(left, style="Surface.TFrame")
        input_row.pack(fill="x", pady=(8, 0))
        self.split_input_entry = ttk.Entry(input_row, textvariable=self.split_input_var, style="Dark.TEntry")
        self.split_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.split_input_button = ttk.Button(input_row, text=_("str_browse"), command=self.choose_split_input_pdf, style="Secondary.TButton")
        self.split_input_button.pack(side="right")

        ttk.Label(left, textvariable=self.split_page_info_var, style="PageInfo.TLabel").pack(anchor="w", pady=(8, 0))

        ttk.Label(left, text=_("str_output_pdf"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        output_row = ttk.Frame(left, style="Surface.TFrame")
        output_row.pack(fill="x", pady=(8, 0))
        self.split_output_entry = ttk.Entry(output_row, textvariable=self.split_output_var, style="Dark.TEntry")
        self.split_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.split_output_button = ttk.Button(output_row, text=_("str_save_as"), command=self.choose_split_output_pdf, style="Ghost.TButton")
        self.split_output_button.pack(side="right")
        ttk.Label(
            left,
            text=_("output_action_hint").format(action=_("split_btn")),
            style="Hint.TLabel",
            wraplength=640,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        range_card = ttk.Frame(left, style="Panel.TFrame", padding=16)
        range_card.pack(fill="x", pady=(22, 0))
        ttk.Label(range_card, text=_("split_page_range"), style="Section.TLabel").pack(anchor="w")
        grid = ttk.Frame(range_card, style="Panel.TFrame")
        grid.pack(anchor="w", pady=(14, 0))
        ttk.Label(grid, text=_("split_start"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(grid, text=_("split_end"), style="Field.TLabel").grid(row=0, column=2, sticky="w", padx=(20, 0))
        self.split_start_spin = ttk.Spinbox(grid, from_=1, to=99999, textvariable=self.split_start_var, width=10, style="Dark.TSpinbox", command=self.update_split_output_name)
        self.split_start_spin.grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(grid, text="-", style="CardTitle.TLabel").grid(row=1, column=1, padx=12, pady=(8, 0))
        self.split_end_spin = ttk.Spinbox(grid, from_=1, to=99999, textvariable=self.split_end_var, width=10, style="Dark.TSpinbox", command=self.update_split_output_name)
        self.split_end_spin.grid(row=1, column=2, sticky="w", padx=(20, 0), pady=(8, 0))
        ttk.Label(range_card, text=_("split_hint"), style="Hint.TLabel", wraplength=640, justify="left").pack(anchor="w", pady=(12, 0))

        footer = ttk.Frame(left, style="Surface.TFrame")
        footer.pack(fill="x", pady=(22, 0))
        self.split_button = ttk.Button(footer, text=_("split_btn"), command=self.start_split, style="Split.TButton")
        self.split_button.pack(side="left")
        self.split_progress_bar = ttk.Progressbar(footer, mode="indeterminate", style="Split.Horizontal.TProgressbar", length=220)
        self.split_progress_bar.pack(side="left", fill="x", expand=True, padx=(16, 0))

        right = ttk.Frame(body, style="App.TFrame")
        right.pack(side="left", fill="y", padx=(18, 0))
        self.feedback = InlineFeedback(right)
        self.feedback.pack(fill="x")
        self.feedback.set_info(_("split_page_range"), _("output_action_hint").format(action=_("split_btn")))

        self.split_start_var.trace_add("write", lambda *_args: self.update_split_output_name())
        self.split_end_var.trace_add("write", lambda *_args: self.update_split_output_name())

    def choose_split_input_pdf(self):
        selected = filedialog.askopenfilename(title=_("split_dialog_input"), filetypes=[("PDF", "*.pdf")])
        if not selected:
            return
        self.split_input_var.set(selected)
        self._refresh_page_info(selected)
        self.update_split_output_name()

    def _refresh_page_info(self, path):
        try:
            total = get_pdf_page_count(path)
            self.split_page_info_var.set(_("split_total_pages").format(count=total))
            self.split_end_var.set(str(total))
            self.split_start_var.set("1")
        except Exception as exc:
            self.split_page_info_var.set(f"{_('split_page_read_err')}{exc}")

    def choose_split_output_pdf(self):
        init = ""
        current = self.split_input_var.get().strip()
        if current:
            try:
                start_page, end_page = int(self.split_start_var.get()), int(self.split_end_var.get())
                init = os.path.basename(suggest_split_output_path(current, start_page, end_page))
            except ValueError:
                init = os.path.basename(current)
        selected = filedialog.asksaveasfilename(
            title=_("split_dialog_output"),
            defaultextension=".pdf",
            initialfile=init,
            filetypes=[("PDF", "*.pdf")],
        )
        if selected:
            self.split_output_var.set(selected)

    def update_split_output_name(self):
        current = self.split_input_var.get().strip()
        if not current:
            return
        try:
            start_page, end_page = int(self.split_start_var.get()), int(self.split_end_var.get())
            self.split_output_var.set(suggest_split_output_path(current, start_page, end_page))
        except ValueError:
            pass

    def handle_external_drop(self, file_path):
        if file_path.lower().endswith(".pdf"):
            self.split_input_var.set(file_path)
            self._refresh_page_info(file_path)
            self.update_split_output_name()

    def start_split(self):
        input_pdf = self.split_input_var.get().strip()
        output_pdf = self.split_output_var.get().strip()
        if not input_pdf or not os.path.isfile(input_pdf):
            quick_error(_("err_select_valid_file"), self.split_button, self.split_progress_bar, self.split_status_var, self.feedback)
            return
        try:
            start_page = int(self.split_start_var.get())
            end_page = int(self.split_end_var.get())
        except ValueError:
            quick_error(_("err_enter_page_numbers"), self.split_button, self.split_progress_bar, self.split_status_var, self.feedback)
            return
        if not output_pdf:
            quick_error(_("err_set_output"), self.split_button, self.split_progress_bar, self.split_status_var, self.feedback)
            return

        busy_text = _("split_running").format(start=start_page, end=end_page)
        set_busy(self.split_button, self.split_progress_bar, True, self.feedback, busy_text)
        self.split_status_var.set(busy_text)
        threading.Thread(target=self._run_split, args=(input_pdf, output_pdf, start_page, end_page), daemon=True).start()

    def _run_split(self, input_pdf, output_pdf, start_page, end_page):
        try:
            original_size = format_size_mb(input_pdf)
            split_pdf(input_pdf, output_pdf, start_page, end_page)
            if not os.path.isfile(output_pdf):
                raise RuntimeError(_("err_output_not_created"))
            result_size = format_size_mb(output_pdf)
            page_count = end_page - start_page + 1
            message = _("split_result").format(orig=original_size, result=result_size, start=start_page, end=end_page, count=page_count, output=output_pdf)
            self.app_root.after(
                0,
                operation_done,
                self.split_button,
                self.split_progress_bar,
                self.split_status_var,
                _("split_done"),
                message,
                None,
                self.feedback,
                output_pdf,
            )
        except Exception as exc:
            self.app_root.after(
                0,
                operation_done,
                self.split_button,
                self.split_progress_bar,
                self.split_status_var,
                _("split_fail"),
                None,
                str(exc),
                self.feedback,
                None,
            )
