import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from src.core.split import split_pdf
from src.core.common import get_pdf_page_count
from src.utils.file_helper import suggest_split_output_path, format_size_mb
from src.gui.helpers import set_busy, operation_done
from src.core.lang_manager import _

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
        
        self.build_ui()

    def build_ui(self):
        c = ttk.Frame(self.parent, padding=20, style="Card.TFrame")
        c.pack(fill="both", expand=True, pady=(12, 0))

        ttk.Label(c, text=_("str_file_selection"), style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(c, text=_("str_input_pdf"), style="Field.TLabel").grid(row=1, column=0, sticky="w", pady=(18, 8))
        self.split_input_entry = ttk.Entry(c, textvariable=self.split_input_var, width=64, style="Dark.TEntry")
        self.split_input_entry.grid(row=2, column=0, sticky="ew", padx=(0, 10))
        self.split_input_button = ttk.Button(c, text=_("str_browse"), command=self.choose_split_input_pdf, style="Secondary.TButton")
        self.split_input_button.grid(row=2, column=1, sticky="ew")

        self.split_page_info_label = ttk.Label(c, textvariable=self.split_page_info_var, style="PageInfo.TLabel")
        self.split_page_info_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

        ttk.Label(c, text=_("str_output_pdf"), style="Field.TLabel").grid(row=4, column=0, sticky="w", pady=(16, 8))
        self.split_output_entry = ttk.Entry(c, textvariable=self.split_output_var, width=64, style="Dark.TEntry")
        self.split_output_entry.grid(row=5, column=0, sticky="ew", padx=(0, 10))
        self.split_output_button = ttk.Button(c, text=_("str_save_as"), command=self.choose_split_output_pdf, style="Secondary.TButton")
        self.split_output_button.grid(row=5, column=1, sticky="ew")

        ttk.Label(c, text=_("split_page_range"), style="Section.TLabel").grid(row=6, column=0, sticky="w", pady=(22, 0))
        rf = ttk.Frame(c, style="Card.TFrame")
        rf.grid(row=7, column=0, columnspan=2, sticky="w", pady=(16, 0))
        ttk.Label(rf, text=_("split_start"), style="Field.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 16))
        ttk.Label(rf, text=_("split_end"), style="Field.TLabel").grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.split_start_spin = ttk.Spinbox(rf, from_=1, to=99999, textvariable=self.split_start_var,
                                             width=12, style="Dark.TSpinbox", command=self.update_split_output_name)
        self.split_start_spin.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        ttk.Label(rf, text="-", style="Section.TLabel", font=("Segoe UI", 14)).grid(row=1, column=1, padx=8, pady=(8, 0))
        self.split_end_spin = ttk.Spinbox(rf, from_=1, to=99999, textvariable=self.split_end_var,
                                           width=12, style="Dark.TSpinbox", command=self.update_split_output_name)
        self.split_end_spin.grid(row=1, column=2, sticky="w", padx=(8, 0), pady=(8, 0))

        ttk.Label(c, text=_("split_hint"),
                  style="Hint.TLabel").grid(row=8, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self.split_button = ttk.Button(c, text=_("split_btn"), command=self.start_split, style="Split.TButton")
        self.split_button.grid(row=9, column=0, sticky="w", pady=(22, 12))
        self.split_progress_bar = ttk.Progressbar(c, mode="indeterminate", length=520, style="Split.Horizontal.TProgressbar")
        self.split_progress_bar.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(2, 12))
        self.split_status_label = ttk.Label(c, textvariable=self.split_status_var, style="SplitStatus.TLabel")
        self.split_status_label.grid(row=11, column=0, columnspan=2, sticky="w")
        c.columnconfigure(0, weight=1)

        self.split_start_var.trace_add("write", lambda *_args: self.update_split_output_name())
        self.split_end_var.trace_add("write", lambda *_args: self.update_split_output_name())

    def choose_split_input_pdf(self):
        f = filedialog.askopenfilename(title=_("split_dialog_input"), filetypes=[("PDF", "*.pdf")])
        if not f:
            return
        self.split_input_var.set(f)
        try:
            total = get_pdf_page_count(f)
            self.split_page_info_var.set(_("split_total_pages").format(count=total))
            self.split_end_var.set(str(total))
            self.split_start_var.set("1")
        except Exception as exc:
            self.split_page_info_var.set(f"{_('split_page_read_err')}{exc}")
        self.update_split_output_name()

    def choose_split_output_pdf(self):
        init = ""
        inp = self.split_input_var.get().strip()
        if inp:
            try:
                s, e = int(self.split_start_var.get()), int(self.split_end_var.get())
                init = os.path.basename(suggest_split_output_path(inp, s, e))
            except ValueError:
                init = os.path.basename(inp)
        f = filedialog.asksaveasfilename(title=_("split_dialog_output"), defaultextension=".pdf",
                                          initialfile=init, filetypes=[("PDF", "*.pdf")])
        if f:
            self.split_output_var.set(f)

    def update_split_output_name(self):
        inp = self.split_input_var.get().strip()
        if not inp:
            return
        try:
            s, e = int(self.split_start_var.get()), int(self.split_end_var.get())
            self.split_output_var.set(suggest_split_output_path(inp, s, e))
        except ValueError:
            pass

    def start_split(self):
        input_pdf = self.split_input_var.get().strip()
        output_pdf = self.split_output_var.get().strip()
        if not input_pdf or not os.path.isfile(input_pdf):
            messagebox.showerror(_("str_error"), _("err_select_valid_file"))
            return
        try:
            start_page, end_page = int(self.split_start_var.get()), int(self.split_end_var.get())
        except ValueError:
            messagebox.showerror(_("str_error"), _("err_enter_page_numbers"))
            return
        if not output_pdf:
            messagebox.showerror(_("str_error"), _("err_set_output"))
            return
            
        set_busy(self.split_button, self.split_progress_bar, True)
        self.split_status_var.set(_("split_running").format(start=start_page, end=end_page))
        threading.Thread(target=self._run_split, args=(input_pdf, output_pdf, start_page, end_page), daemon=True).start()

    def _run_split(self, input_pdf, output_pdf, start_page, end_page):
        try:
            orig = format_size_mb(input_pdf)
            split_pdf(input_pdf, output_pdf, start_page, end_page)
            if not os.path.isfile(output_pdf):
                raise RuntimeError(_("err_output_not_created"))
            result = format_size_mb(output_pdf)
            count = end_page - start_page + 1
            msg = _("split_result").format(orig=orig, result=result, start=start_page, end=end_page, count=count, output=output_pdf)
            self.app_root.after(0, operation_done, self.app_root, self.split_button, self.split_progress_bar,
                            self.split_status_var, _("split_done"), msg, None)
        except Exception as exc:
            self.app_root.after(0, operation_done, self.app_root, self.split_button, self.split_progress_bar,
                            self.split_status_var, _("split_fail"), None, str(exc))
