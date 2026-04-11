import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from src.gui.helpers import set_busy
from src.core.batch import batch_compress_dir, batch_convert_dir, batch_rename_dir
from src.core.lang_manager import _

class BatchTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        
        self.input_dir_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        
        self.action_var = tk.StringVar(value=_("batch_compress"))
        self.status_var = tk.StringVar(value=_("str_ready"))
        
        # Options
        self.compress_qual_var = tk.StringVar(value="screen")
        self.convert_mode_var = tk.StringVar(value="pdf2img")
        self.rename_rule_var = tk.StringVar(value="[TARIH]_[ORIJINAL_AD]_Sayfa[SAYFA_SAYISI]")
        
        self.build_ui()

    def build_ui(self):
        c = ttk.Frame(self.parent, padding=15, style="Card.TFrame")
        c.pack(fill="both", expand=True, pady=(10, 0))

        ttk.Label(c, text=_("str_input_folder"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        ef = ttk.Frame(c, style="Card.TFrame")
        ef.grid(row=1, column=0, sticky="ew", pady=(5,0))
        ttk.Entry(ef, textvariable=self.input_dir_var, width=58, style="Dark.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(ef, text=_("str_select_dir"), command=self.choose_input_dir, style="Secondary.TButton").pack(side="right")

        ttk.Label(c, text=_("batch_main_type"), style="Section.TLabel").grid(row=2, column=0, sticky="w", pady=(15, 0))
        self.mode_combo = ttk.Combobox(c, textvariable=self.action_var,
                                       values=[_("batch_compress"), _("batch_convert"), _("batch_rename")],
                                       state="readonly", width=30, style="Dark.TCombobox")
        self.mode_combo.grid(row=3, column=0, sticky="w", pady=(5, 0))
        self.mode_combo.bind("<<ComboboxSelected>>", lambda e: self.switch_mode())

        # Dynamic Frames Container
        self.dyn_frame = ttk.Frame(c, style="Card.TFrame")
        self.dyn_frame.grid(row=4, column=0, sticky="nsew", pady=(10, 0))

        # 1. Compress Options
        self.f_compress = ttk.Frame(self.dyn_frame, style="Card.TFrame")
        ttk.Label(self.f_compress, text=_("batch_compress_quality")).grid(row=0, column=0, sticky="w")
        ttk.Combobox(self.f_compress, textvariable=self.compress_qual_var, 
                     values=["screen", "ebook", "printer", "prepress"], state="readonly", style="Dark.TCombobox").grid(row=0, column=1, padx=10)

        # 2. Convert Options
        self.f_convert = ttk.Frame(self.dyn_frame, style="Card.TFrame")
        ttk.Radiobutton(self.f_convert, text=_("batch_radio_pdf2img"), variable=self.convert_mode_var, value="pdf2img").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Radiobutton(self.f_convert, text=_("batch_radio_img2pdf"), variable=self.convert_mode_var, value="img2pdf").grid(row=1, column=0, sticky="w", pady=2)

        # 3. Rename Options
        self.f_rename = ttk.Frame(self.dyn_frame, style="Card.TFrame")
        ttk.Label(self.f_rename, text=_("batch_rename_rule")).grid(row=0, column=0, sticky="w")
        ttk.Entry(self.f_rename, textvariable=self.rename_rule_var, width=40, style="Dark.TEntry").grid(row=0, column=1, padx=10)
        ttk.Label(self.f_rename, text=_("batch_rename_hint"), foreground="#9ca3af").grid(row=1, column=0, columnspan=2, sticky="w", pady=5)

        self.frames = {
            _("batch_compress"): self.f_compress,
            _("batch_convert"): self.f_convert,
            _("batch_rename"): self.f_rename
        }
        self.switch_mode()

        ttk.Label(c, text=_("str_output_folder_label"), style="Field.TLabel").grid(row=5, column=0, sticky="w", pady=(10, 5))
        of = ttk.Frame(c, style="Card.TFrame")
        of.grid(row=6, column=0, sticky="ew")
        ttk.Entry(of, textvariable=self.output_dir_var, width=58, style="Dark.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(of, text=_("str_select_dir"), command=self.choose_output_dir, style="Secondary.TButton").pack(side="right")

        self.action_button = ttk.Button(c, text=_("batch_start_btn"), command=self.start_action, style="Accent.TButton")
        self.action_button.grid(row=7, column=0, sticky="w", pady=(15, 10))
        
        self.progress_bar = ttk.Progressbar(c, mode="determinate", length=400, style="Horizontal.TProgressbar")
        self.progress_bar.grid(row=8, column=0, sticky="ew", pady=(0, 5))
        
        self.status_label = ttk.Label(c, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.grid(row=9, column=0, sticky="w")
        
        # Log Text Box
        self.log_text = tk.Text(c, height=6, bg="#1e1e1e", fg="#e2e8f0", bd=0, state="disabled", font=("Consolas", 9))
        self.log_text.grid(row=10, column=0, sticky="nsew", pady=(10, 0))
        c.rowconfigure(10, weight=1)
        c.columnconfigure(0, weight=1)

    def switch_mode(self):
        for f in self.frames.values():
            f.grid_remove()
        mode = self.action_var.get()
        if mode in self.frames:
            self.frames[mode].grid(row=0, column=0, sticky="nsew")

    def choose_input_dir(self):
        d = filedialog.askdirectory(title=_("batch_dialog_input"))
        if d: self.input_dir_var.set(d)

    def choose_output_dir(self):
        d = filedialog.askdirectory(title=_("batch_dialog_output"))
        if d: self.output_dir_var.set(d)

    def _append_log(self, text):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _update_progress(self, current, total, log_message):
        """Thread-safe call to update UI during batch work"""
        def ui_update():
            self.progress_bar["value"] = current
            self.progress_bar["maximum"] = total
            pct = int((current/total)*100)
            self.status_var.set(_("batch_progress").format(pct=pct, cur=current, total=total))
            if log_message:
                self._append_log(log_message)
        self.app_root.after(0, ui_update)

    def start_action(self):
        inp = self.input_dir_var.get()
        out = self.output_dir_var.get()
        
        if not inp or not os.path.isdir(inp):
            messagebox.showerror(_("str_error"), _("err_select_valid_input_dir"))
            return
        if not out or not os.path.isdir(out):
            messagebox.showerror(_("str_error"), _("err_select_valid_output_dir"))
            return
            
        set_busy(self.action_button, None, True)
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        
        self._append_log(_("batch_log_started").format(path=inp))
        self.progress_bar["value"] = 0
        
        mode = self.action_var.get()
        threading.Thread(target=self._run_job, args=(mode, inp, out), daemon=True).start()

    def _run_job(self, mode, inp, out):
        try:
            succ = 0
            errs = []
            
            if mode == _("batch_compress"):
                succ, errs = batch_compress_dir(inp, out, self.compress_qual_var.get(), self._update_progress)
            elif mode == _("batch_convert"):
                succ, errs = batch_convert_dir(inp, out, self.convert_mode_var.get(), self._update_progress)
            elif mode == _("batch_rename"):
                succ, errs = batch_rename_dir(inp, out, self.rename_rule_var.get(), self._update_progress)
            
            # Reset UI state safely
            self.app_root.after(0, self._finalize_job, succ, errs, out)
        except Exception as e:
            def throw():
                set_busy(self.action_button, None, False)
                self.status_var.set(_("err_critical"))
                messagebox.showerror(_("err_critical"), str(e))
            self.app_root.after(0, throw)
            
    def _finalize_job(self, succ, errs, out):
        set_busy(self.action_button, None, False)
        self.progress_bar["value"] = self.progress_bar["maximum"]
        self.status_var.set(_("batch_done"))
        self._append_log(_("batch_log_ended"))
        self._append_log(_("batch_success_count").format(succ=succ, errs=len(errs)))
        
        msg = _("batch_result").format(succ=succ, errs=len(errs))
        if errs:
            msg += _("batch_result_errors").format(dir=out)
        messagebox.showinfo(_("batch_result_title"), msg)
