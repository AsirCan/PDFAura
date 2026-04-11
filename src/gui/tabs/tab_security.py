import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from src.gui.helpers import set_busy, operation_done, quick_error
from src.core.security import encrypt_pdf, decrypt_pdf, add_watermark_to_pdf
from src.core.lang_manager import _

class SecurityTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.mode_var = tk.StringVar(value=_("security_encrypt"))
        self.password_var = tk.StringVar()
        self.watermark_text_var = tk.StringVar(value="GIZLI")
        self.status_var = tk.StringVar(value=_("str_ready"))
        
        self.build_ui()

    def build_ui(self):
        c = ttk.Frame(self.parent, padding=20, style="Card.TFrame")
        c.pack(fill="both", expand=True, pady=(12, 0))

        ttk.Label(c, text=_("str_input_pdf"), style="Field.TLabel").grid(row=0, column=0, sticky="w", pady=(8, 8))
        ef = ttk.Frame(c, style="Card.TFrame")
        ef.grid(row=1, column=0, sticky="ew")
        self.input_entry = ttk.Entry(ef, textvariable=self.input_var, width=58, style="Dark.TEntry")
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.input_button = ttk.Button(ef, text=_("str_browse"), command=self.choose_input_pdf, style="Secondary.TButton")
        self.input_button.pack(side="right")

        ttk.Label(c, text=_("security_op_type"), style="Section.TLabel").grid(row=2, column=0, sticky="w", pady=(18, 0))
        self.mode_combo = ttk.Combobox(c, textvariable=self.mode_var,
                                       values=[_("security_encrypt"), _("security_decrypt"), _("security_watermark")],
                                       state="readonly", width=24, style="Dark.TCombobox")
        self.mode_combo.grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.mode_combo.bind("<<ComboboxSelected>>", lambda e: self.switch_mode())

        # Dynamic frames container
        self.dynamic_frame = ttk.Frame(c, style="Card.TFrame")
        self.dynamic_frame.grid(row=4, column=0, sticky="ew", pady=(12, 0))

        # Password frame
        self.password_frame = ttk.Frame(self.dynamic_frame, style="Card.TFrame")
        ttk.Label(self.password_frame, text=_("security_password"), style="Field.TLabel").pack(side="left", padx=(0, 10))
        self.password_entry = ttk.Entry(self.password_frame, textvariable=self.password_var, show="*", width=30, style="Dark.TEntry")
        self.password_entry.pack(side="left")

        # Watermark frame
        self.watermark_frame = ttk.Frame(self.dynamic_frame, style="Card.TFrame")
        ttk.Label(self.watermark_frame, text=_("security_watermark_text"), style="Field.TLabel").pack(side="left", padx=(0, 10))
        self.watermark_entry = ttk.Entry(self.watermark_frame, textvariable=self.watermark_text_var, width=30, style="Dark.TEntry")
        self.watermark_entry.pack(side="left")

        self.frames = {
            _("security_encrypt"): self.password_frame,
            _("security_decrypt"): self.password_frame,
            _("security_watermark"): self.watermark_frame,
        }
        self.switch_mode()

        # Output
        ttk.Label(c, text=_("str_output_pdf"), style="Field.TLabel").grid(row=5, column=0, sticky="w", pady=(16, 8))
        of = ttk.Frame(c, style="Card.TFrame")
        of.grid(row=6, column=0, sticky="ew")
        self.output_entry = ttk.Entry(of, textvariable=self.output_var, width=58, style="Dark.TEntry")
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.output_button = ttk.Button(of, text=_("str_save_as"), command=self.choose_output_pdf, style="Secondary.TButton")
        self.output_button.pack(side="right")

        self.action_button = ttk.Button(c, text=_("str_apply"), command=self.start_action, style="Security.TButton")
        self.action_button.grid(row=7, column=0, sticky="w", pady=(22, 12))
        self.progress_bar = ttk.Progressbar(c, mode="indeterminate", length=520, style="Security.Horizontal.TProgressbar")
        self.progress_bar.grid(row=8, column=0, sticky="ew", pady=(2, 12))
        self.status_label = ttk.Label(c, textvariable=self.status_var, style="SecurityStatus.TLabel")
        self.status_label.grid(row=9, column=0, sticky="w")
        c.columnconfigure(0, weight=1)

    def switch_mode(self):
        for frame in self.frames.values():
            frame.pack_forget()
        mode = self.mode_var.get()
        if mode in self.frames:
            self.frames[mode].pack(fill="x", expand=True)

    def choose_input_pdf(self):
        f = filedialog.askopenfilename(title=_("security_dialog_input"), filetypes=[("PDF", "*.pdf")])
        if f:
            self.input_var.set(f)
            base, ext = os.path.splitext(f)
            mode = self.mode_var.get()
            suffix = "_sifreli" if mode == _("security_encrypt") else "_sifresiz" if mode == _("security_decrypt") else "_filigranli"
            self.output_var.set(f"{base}{suffix}{ext}")

    def choose_output_pdf(self):
        f = filedialog.asksaveasfilename(title=_("security_dialog_output"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if f:
            self.output_var.set(f)

    def start_action(self):
        input_pdf = self.input_var.get().strip()
        output_pdf = self.output_var.get().strip()
        mode = self.mode_var.get()
        
        if not input_pdf or not os.path.isfile(input_pdf):
            quick_error(_("err_select_valid_file"), self.action_button, self.progress_bar, self.status_var)
            return
        if not output_pdf:
            quick_error(_("err_set_output"), self.action_button, self.progress_bar, self.status_var)
            return
            
        set_busy(self.action_button, self.progress_bar, True)
        self.status_var.set(_("security_running").format(mode=mode))
        threading.Thread(target=self._run_action, args=(input_pdf, output_pdf, mode), daemon=True).start()

    def _run_action(self, input_pdf, output_pdf, mode):
        try:
            if mode == _("security_encrypt"):
                pwd = self.password_var.get()
                encrypt_pdf(input_pdf, output_pdf, pwd)
                msg = _("security_result_encrypt").format(output=output_pdf)
            elif mode == _("security_decrypt"):
                pwd = self.password_var.get()
                decrypt_pdf(input_pdf, output_pdf, pwd)
                msg = _("security_result_decrypt").format(output=output_pdf)
            elif mode == _("security_watermark"):
                text = self.watermark_text_var.get().strip()
                if not text:
                    raise ValueError(_("err_watermark_empty"))
                add_watermark_to_pdf(input_pdf, output_pdf, text)
                msg = _("security_result_watermark").format(output=output_pdf)
            else:
                raise ValueError(f"{_('err_unknown_op')}{mode}")

            self.app_root.after(0, operation_done, self.app_root, self.action_button, self.progress_bar,
                            self.status_var, _("str_success"), msg, None)
        except Exception as exc:
            self.app_root.after(0, operation_done, self.app_root, self.action_button, self.progress_bar,
                            self.status_var, _("str_failed"), None, str(exc))
