import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from src.gui.helpers import set_busy, operation_done, quick_error
from src.core.metainfo import read_metadata, update_metadata
from src.core.ocr import perform_ocr_to_text, check_tesseract_availability
from src.core.signature import stamp_visual_signature
from src.core.lang_manager import _

class AdvancedTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        
        self.action_var = tk.StringVar(value=_("adv_preview"))
        self.status_var = tk.StringVar(value=_("str_ready"))
        
        # Meta Fields
        self.title_var = tk.StringVar()
        self.author_var = tk.StringVar()
        self.subject_var = tk.StringVar()
        self.creator_var = tk.StringVar()
        self.meta_clean_var = tk.BooleanVar(value=False)
        
        # Sig Fields
        self.sig_image_var = tk.StringVar()
        self.sig_page_var = tk.StringVar(value="1")
        self.sig_x_var = tk.StringVar(value="100")
        self.sig_y_var = tk.StringVar(value="100")
        self.sig_scale_var = tk.StringVar(value="1.0")
        
        self.build_ui()

    def build_ui(self):
        c = ttk.Frame(self.parent, padding=15, style="Card.TFrame")
        c.pack(fill="both", expand=True, pady=(10, 0))

        ttk.Label(c, text=_("str_input_pdf"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        ef = ttk.Frame(c, style="Card.TFrame")
        ef.grid(row=1, column=0, sticky="ew", pady=(5,0))
        self.input_entry = ttk.Entry(ef, textvariable=self.input_var, width=58, style="Dark.TEntry")
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(ef, text=_("str_select"), command=self.choose_input, style="Secondary.TButton").pack(side="right")

        ttk.Label(c, text=_("adv_operation"), style="Section.TLabel").grid(row=2, column=0, sticky="w", pady=(15, 0))
        self.mode_combo = ttk.Combobox(c, textvariable=self.action_var,
                                       values=[_("adv_preview"), _("adv_ocr"), _("adv_metadata"), _("adv_signature")],
                                       state="readonly", width=30, style="Dark.TCombobox")
        self.mode_combo.grid(row=3, column=0, sticky="w", pady=(5, 0))
        self.mode_combo.bind("<<ComboboxSelected>>", lambda e: self.switch_mode())

        # Dynamic Frames Container
        self.dyn_frame = ttk.Frame(c, style="Card.TFrame")
        self.dyn_frame.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        c.rowconfigure(4, weight=1)

        # 1. Preview Frame
        self.f_preview = ttk.Frame(self.dyn_frame, style="Card.TFrame")
        ttk.Label(self.f_preview, text=_("adv_preview_hint"),
                  style="Hint.TLabel").pack(pady=20)

        # 2. OCR Frame
        self.f_ocr = ttk.Frame(self.dyn_frame, style="Card.TFrame")
        ttk.Label(self.f_ocr, text=_("adv_ocr_hint"),
                  style="Hint.TLabel").pack(anchor="w", pady=(0,10))
        
        # Check availability
        self.tess_warn_label = ttk.Label(self.f_ocr, text=_("adv_tess_warning"),
                  foreground="#ef4444", background="#252526")
        self.tess_warn_label.pack(anchor="w")
        
        self.tess_install_btn = ttk.Button(self.f_ocr, text=_("adv_tess_install_btn"),
                                           command=self.trigger_tesseract_install, style="Small.TButton")

        # 3. Meta Info Frame
        self.f_meta = ttk.Frame(self.dyn_frame, style="Card.TFrame")
        ttk.Button(self.f_meta, text=_("adv_read_meta_btn"), command=self.load_metadata,
                   style="Small.TButton").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,10))
        
        ttk.Label(self.f_meta, text=_("adv_meta_title")).grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(self.f_meta, textvariable=self.title_var, width=40, style="Dark.TEntry").grid(row=1, column=1)
        
        ttk.Label(self.f_meta, text=_("adv_meta_author")).grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(self.f_meta, textvariable=self.author_var, width=40, style="Dark.TEntry").grid(row=2, column=1)
        
        ttk.Label(self.f_meta, text=_("adv_meta_subject")).grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(self.f_meta, textvariable=self.subject_var, width=40, style="Dark.TEntry").grid(row=3, column=1)
        
        ttk.Label(self.f_meta, text=_("adv_meta_creator")).grid(row=4, column=0, sticky="w", pady=5)
        ttk.Entry(self.f_meta, textvariable=self.creator_var, width=40, style="Dark.TEntry").grid(row=4, column=1)
        
        ttk.Checkbutton(self.f_meta, text=_("adv_meta_clean"), variable=self.meta_clean_var).grid(row=5, column=0, columnspan=2, sticky="w", pady=10)

        # 4. Signature Frame
        self.f_sig = ttk.Frame(self.dyn_frame, style="Card.TFrame")
        ttk.Label(self.f_sig, text=_("adv_sig_image")).grid(row=0, column=0, sticky="w", pady=5)
        sf1 = ttk.Frame(self.f_sig, style="Card.TFrame")
        sf1.grid(row=1, column=0, sticky="ew", columnspan=2)
        ttk.Entry(sf1, textvariable=self.sig_image_var, width=35, style="Dark.TEntry").pack(side="left", fill="x", expand=True)
        ttk.Button(sf1, text=_("adv_sig_choose"), command=self.choose_sig, style="Small.TButton").pack(side="right", padx=(5,0))
        
        ttk.Label(self.f_sig, text=_("adv_sig_page")).grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(self.f_sig, textvariable=self.sig_page_var, width=10, style="Dark.TEntry").grid(row=2, column=1, sticky="w")
        
        ttk.Label(self.f_sig, text=_("adv_sig_x")).grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(self.f_sig, textvariable=self.sig_x_var, width=10, style="Dark.TEntry").grid(row=3, column=1, sticky="w")
        
        ttk.Label(self.f_sig, text=_("adv_sig_y")).grid(row=4, column=0, sticky="w", pady=5)
        ttk.Entry(self.f_sig, textvariable=self.sig_y_var, width=10, style="Dark.TEntry").grid(row=4, column=1, sticky="w")
        
        ttk.Label(self.f_sig, text=_("adv_sig_scale")).grid(row=5, column=0, sticky="w", pady=5)
        ttk.Entry(self.f_sig, textvariable=self.sig_scale_var, width=10, style="Dark.TEntry").grid(row=5, column=1, sticky="w")

        self.frames = {
            _("adv_preview"): self.f_preview,
            _("adv_ocr"): self.f_ocr,
            _("adv_metadata"): self.f_meta,
            _("adv_signature"): self.f_sig
        }
        self.switch_mode()

        # Output & Execution
        ttk.Label(c, text=_("str_output_dir_file"), style="Field.TLabel").grid(row=5, column=0, sticky="w", pady=(10, 5))
        of = ttk.Frame(c, style="Card.TFrame")
        of.grid(row=6, column=0, sticky="ew")
        self.output_entry = ttk.Entry(of, textvariable=self.output_var, width=58, style="Dark.TEntry")
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.output_button = ttk.Button(of, text=_("str_save_as"), command=self.choose_output, style="Secondary.TButton")
        self.output_button.pack(side="right")

        self.action_button = ttk.Button(c, text=_("str_start"), command=self.start_action, style="Accent.TButton")
        self.action_button.grid(row=7, column=0, sticky="w", pady=(15, 10))
        self.progress_bar = ttk.Progressbar(c, mode="indeterminate", length=400, style="Accent.Horizontal.TProgressbar")
        self.progress_bar.grid(row=8, column=0, sticky="ew", pady=(0, 10))
        self.status_label = ttk.Label(c, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.grid(row=9, column=0, sticky="w")
        c.columnconfigure(0, weight=1)

    def switch_mode(self):
        for f in self.frames.values():
            f.grid_remove()
        mode = self.action_var.get()
        if mode in self.frames:
            self.frames[mode].grid(row=0, column=0, sticky="nsew")
            
        if mode == _("adv_ocr"):
            if check_tesseract_availability():
                self.tess_warn_label.config(text=_("adv_tess_installed"), foreground="#10b981")
                self.tess_install_btn.pack_forget()
            else:
                self.tess_warn_label.config(text=_("adv_tess_not_installed"), foreground="#ef4444")
                self.tess_install_btn.pack(anchor="w", pady=5)

    def choose_input(self):
        f = filedialog.askopenfilename(title=_("security_dialog_input"), filetypes=[("PDF", "*.pdf")])
        if f:
            self.input_var.set(f)

    def choose_output(self):
        mode = self.action_var.get()
        if mode == _("adv_ocr"):
            f = filedialog.asksaveasfilename(title=_("adv_dialog_txt_save"), defaultextension=".txt", filetypes=[("Text", "*.txt")])
        else:
            f = filedialog.asksaveasfilename(title=_("adv_dialog_pdf_save"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if f:
            self.output_var.set(f)

    def choose_sig(self):
        f = filedialog.askopenfilename(title=_("adv_dialog_sig_img"), filetypes=[(_("convert_images_label"), "*.png *.jpg *.jpeg")])
        if f:
            self.sig_image_var.set(f)

    def load_metadata(self):
        inp = self.input_var.get()
        if not inp or not os.path.isfile(inp):
            messagebox.showerror(_("str_error"), _("err_select_valid_file"))
            return
        meta = read_metadata(inp)
        self.title_var.set(meta.get("title", ""))
        self.author_var.set(meta.get("author", ""))
        self.subject_var.set(meta.get("subject", ""))
        self.creator_var.set(meta.get("creator", ""))
        messagebox.showinfo(_("str_info"), _("adv_meta_read_ok"))

    def trigger_tesseract_install(self):
        from src.core.install_tesseract import install_target_tesseract
        self.tess_install_btn.config(text=_("adv_tess_installing"), state="disabled")
        
        def success():
            self.app_root.after(0, lambda: messagebox.showinfo(_("adv_tess_install_title"), _("adv_tess_install_ok")))
            self.app_root.after(0, self.switch_mode)
            
        def fail(msg):
            self.app_root.after(0, lambda: messagebox.showerror(_("str_error"), msg))
            self.app_root.after(0, lambda: self.tess_install_btn.config(text=_("adv_tess_install_btn"), state="normal"))
            
        install_target_tesseract(on_success=success, on_error=fail)

    def start_action(self):
        inp = self.input_var.get()
        out = self.output_var.get()
        mode = self.action_var.get()
        
        if not inp or not os.path.isfile(inp):
            quick_error(_("err_select_valid_file"), self.action_button, self.progress_bar, self.status_var)
            return
            
        if mode == _("adv_preview"):
            from src.gui.pdf_viewer import PDFViewerWindow
            PDFViewerWindow(self.app_root, inp)
            return

        if not out:
            quick_error(_("err_set_output_file"), self.action_button, self.progress_bar, self.status_var)
            return
            
        set_busy(self.action_button, self.progress_bar, True)
        self.status_var.set(_("str_processing"))
        
        if mode == _("adv_ocr"):
            threading.Thread(target=self._run_ocr, args=(inp, out), daemon=True).start()
        elif mode == _("adv_metadata"):
            threading.Thread(target=self._run_meta, args=(inp, out), daemon=True).start()
        elif mode == _("adv_signature"):
            threading.Thread(target=self._run_sig, args=(inp, out), daemon=True).start()

    def _run_ocr(self, inp, out):
        try:
            perform_ocr_to_text(inp, out)
            self.app_root.after(0, operation_done, self.app_root, self.action_button, self.progress_bar,
                            self.status_var, _("str_success"), _("adv_result_ocr").format(output=out), None)
        except Exception as e:
            self.app_root.after(0, operation_done, self.app_root, self.action_button, self.progress_bar,
                            self.status_var, _("str_error"), None, str(e))

    def _run_meta(self, inp, out):
        try:
            update_metadata(inp, out, 
                            title=self.title_var.get() if not self.meta_clean_var.get() else None,
                            author=self.author_var.get() if not self.meta_clean_var.get() else None,
                            subject=self.subject_var.get() if not self.meta_clean_var.get() else None,
                            creator=self.creator_var.get() if not self.meta_clean_var.get() else None,
                            clean=self.meta_clean_var.get())
            self.app_root.after(0, operation_done, self.app_root, self.action_button, self.progress_bar,
                            self.status_var, _("str_success"), _("adv_result_meta").format(output=out), None)
        except Exception as e:
            self.app_root.after(0, operation_done, self.app_root, self.action_button, self.progress_bar,
                            self.status_var, _("str_error"), None, str(e))

    def _run_sig(self, inp, out):
        try:
            stamp_visual_signature(inp, out, 
                                   self.sig_image_var.get(), 
                                   int(self.sig_page_var.get()), 
                                   int(self.sig_x_var.get()), 
                                   int(self.sig_y_var.get()), 
                                   float(self.sig_scale_var.get()))
            self.app_root.after(0, operation_done, self.app_root, self.action_button, self.progress_bar,
                            self.status_var, _("str_success"), _("adv_result_sig").format(output=out), None)
        except Exception as e:
            self.app_root.after(0, operation_done, self.app_root, self.action_button, self.progress_bar,
                            self.status_var, _("str_error"), None, str(e))
