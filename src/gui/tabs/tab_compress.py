import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from src.core.compress import compress_pdf, VALID_QUALITIES
from src.utils.file_helper import suggest_output_path, format_size_mb
from src.gui.helpers import set_busy, operation_done
from src.core.lang_manager import _

class CompressTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.quality_var = tk.StringVar(value="ebook")
        self.status_var = tk.StringVar(value=_("str_ready"))
        
        self.build_ui()

    def build_ui(self):
        c = ttk.Frame(self.parent, padding=20, style="Card.TFrame")
        c.pack(fill="both", expand=True, pady=(12, 0))

        ttk.Label(c, text=_("str_file_selection"), style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(c, text=_("str_input_pdf"), style="Field.TLabel").grid(row=1, column=0, sticky="w", pady=(18, 8))
        self.input_entry = ttk.Entry(c, textvariable=self.input_var, width=64, style="Dark.TEntry")
        self.input_entry.grid(row=2, column=0, sticky="ew", padx=(0, 10))
        self.input_button = ttk.Button(c, text=_("str_browse"), command=self.choose_input_pdf, style="Secondary.TButton")
        self.input_button.grid(row=2, column=1, sticky="ew")

        ttk.Label(c, text=_("str_output_pdf"), style="Field.TLabel").grid(row=3, column=0, sticky="w", pady=(16, 8))
        self.output_entry = ttk.Entry(c, textvariable=self.output_var, width=64, style="Dark.TEntry")
        self.output_entry.grid(row=4, column=0, sticky="ew", padx=(0, 10))
        self.output_button = ttk.Button(c, text=_("str_save_as"), command=self.choose_output_pdf, style="Secondary.TButton")
        self.output_button.grid(row=4, column=1, sticky="ew")

        ttk.Label(c, text=_("compress_settings"), style="Section.TLabel").grid(row=5, column=0, sticky="w", pady=(22, 0))
        ttk.Label(c, text=_("compress_quality"), style="Field.TLabel").grid(row=6, column=0, sticky="w", pady=(16, 8))
        self.quality_combo = ttk.Combobox(c, textvariable=self.quality_var, values=VALID_QUALITIES,
                                          state="readonly", width=24, style="Dark.TCombobox")
        self.quality_combo.grid(row=7, column=0, sticky="w")
        ttk.Label(c, text=_("compress_quality_hint"),
                  style="Hint.TLabel").grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.compress_button = ttk.Button(c, text=_("compress_btn"), command=self.start_compression, style="Accent.TButton")
        self.compress_button.grid(row=9, column=0, sticky="w", pady=(22, 12))
        self.progress_bar = ttk.Progressbar(c, mode="indeterminate", length=520, style="Accent.Horizontal.TProgressbar")
        self.progress_bar.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(2, 12))
        self.status_label = ttk.Label(c, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.grid(row=11, column=0, columnspan=2, sticky="w")
        c.columnconfigure(0, weight=1)

    def choose_input_pdf(self):
        f = filedialog.askopenfilename(title=_("compress_dialog_input"), filetypes=[("PDF", "*.pdf")])
        if f:
            self.input_var.set(f)
            if not self.output_var.get().strip():
                self.output_var.set(suggest_output_path(f))

    def choose_output_pdf(self):
        init = ""
        inp = self.input_var.get().strip()
        if inp:
            init = os.path.basename(suggest_output_path(inp))
        f = filedialog.asksaveasfilename(title=_("compress_dialog_output"), defaultextension=".pdf",
                                          initialfile=init, filetypes=[("PDF", "*.pdf")])
        if f:
            self.output_var.set(f)

    def start_compression(self):
        input_pdf = self.input_var.get().strip()
        output_pdf = self.output_var.get().strip()
        quality = self.quality_var.get().strip().lower()
        if quality not in VALID_QUALITIES:
            from tkinter import messagebox
            messagebox.showerror(_("str_error"), f"{_('err_select_quality')}{', '.join(VALID_QUALITIES)}")
            return
        if not input_pdf or not os.path.isfile(input_pdf):
            from tkinter import messagebox
            messagebox.showerror(_("str_error"), _("err_select_valid_pdf"))
            return
        if not output_pdf:
            from tkinter import messagebox
            messagebox.showerror(_("str_error"), _("err_set_output"))
            return
            
        set_busy(self.compress_button, self.progress_bar, True)
        self.status_var.set(_("compress_running"))
        threading.Thread(target=self._run_compress, args=(input_pdf, output_pdf, quality), daemon=True).start()

    def _run_compress(self, input_pdf, output_pdf, quality):
        try:
            orig = format_size_mb(input_pdf)
            compress_pdf(input_pdf, output_pdf, quality)
            if not os.path.isfile(output_pdf):
                raise RuntimeError(_("err_output_not_created"))
            comp = format_size_mb(output_pdf)
            msg = (f"{_('compress_result_original')}{orig:.2f} MB\n{_('compress_result_compressed')}{comp:.2f} MB\n"
                   f"{_('compress_result_quality')}{quality}\n{_('compress_result_saved')}{output_pdf}")
            self.app_root.after(0, operation_done, self.app_root, self.compress_button, self.progress_bar,
                            self.status_var, _("compress_done"), msg, None)
        except Exception as exc:
            self.app_root.after(0, operation_done, self.app_root, self.compress_button, self.progress_bar,
                            self.status_var, _("compress_fail"), None, str(exc))
