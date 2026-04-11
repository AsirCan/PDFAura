import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from src.core.convert import pdf_to_images, images_to_pdf, pdf_to_word, word_to_pdf, ppt_to_pdf, excel_to_pdf, pdf_to_txt
from src.utils.file_helper import format_size_mb
from src.gui.helpers import set_busy, operation_done, quick_error
from src.core.lang_manager import _

class ConvertTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        
        self.convert_mode_var = tk.StringVar(value=_("convert_pdf2img"))
        self.convert_status_var = tk.StringVar(value=_("str_ready"))
        
        # PDF -> Image
        self.p2i_input_var = tk.StringVar()
        self.p2i_folder_var = tk.StringVar()
        self.p2i_dpi_var = tk.StringVar(value="300")
        self.p2i_format_var = tk.StringVar(value="PNG")
        
        # Image -> PDF
        self.i2p_file_list = []
        self.i2p_output_var = tk.StringVar()
        self.i2p_size_var = tk.StringVar(value=_("convert_original"))
        
        # PDF -> Word
        self.p2w_input_var = tk.StringVar()
        self.p2w_output_var = tk.StringVar()
        
        # Word -> PDF
        self.w2p_input_var = tk.StringVar()
        self.w2p_output_var = tk.StringVar()
        
        # PPT -> PDF
        self.ppt2p_input_var = tk.StringVar()
        self.ppt2p_output_var = tk.StringVar()

        # Excel -> PDF
        self.excel2p_input_var = tk.StringVar()
        self.excel2p_output_var = tk.StringVar()

        # PDF -> TXT
        self.p2txt_input_var = tk.StringVar()
        self.p2txt_output_var = tk.StringVar()
        
        self.build_ui()

    def build_ui(self):
        c = ttk.Frame(self.parent, padding=20, style="Card.TFrame")
        c.pack(fill="both", expand=True, pady=(12, 0))

        ttk.Label(c, text=_("convert_type"), style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.convert_mode_combo = ttk.Combobox(c, textvariable=self.convert_mode_var,
                                                values=[_("convert_pdf2img"), _("convert_img2pdf"), _("convert_pdf2word"), _("convert_word2pdf"), _("convert_ppt2pdf"), _("convert_excel2pdf"), _("convert_pdf2txt")],
                                                state="readonly", width=24, style="Dark.TCombobox")
        self.convert_mode_combo.grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.convert_mode_combo.bind("<<ComboboxSelected>>", lambda e: self.switch_convert_mode())

        # Dynamic content area
        self.convert_dynamic = ttk.Frame(c, style="Card.TFrame")
        self.convert_dynamic.grid(row=2, column=0, sticky="nsew", pady=(16, 0))

        # ── PDF -> Image frame ──
        f1 = ttk.Frame(self.convert_dynamic, style="Card.TFrame")
        ttk.Label(f1, text=_("str_input_pdf"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        r1 = ttk.Frame(f1, style="Card.TFrame")
        r1.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.p2i_input_entry = ttk.Entry(r1, textvariable=self.p2i_input_var, width=50, style="Dark.TEntry")
        self.p2i_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r1, text=_("str_browse"), command=self.choose_p2i_input, style="Secondary.TButton").pack(side="right")

        ttk.Label(f1, text=_("str_output_folder"), style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(14, 0))
        r2 = ttk.Frame(f1, style="Card.TFrame")
        r2.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.p2i_folder_entry = ttk.Entry(r2, textvariable=self.p2i_folder_var, width=50, style="Dark.TEntry")
        self.p2i_folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r2, text=_("str_browse"), command=self.choose_p2i_folder, style="Secondary.TButton").pack(side="right")

        sf = ttk.Frame(f1, style="Card.TFrame")
        sf.grid(row=4, column=0, sticky="w", pady=(14, 0))
        ttk.Label(sf, text="DPI:", style="Field.TLabel").pack(side="left", padx=(0, 8))
        ttk.Combobox(sf, textvariable=self.p2i_dpi_var, values=["72", "150", "300", "600"],
                     state="readonly", width=6, style="Dark.TCombobox").pack(side="left", padx=(0, 20))
        ttk.Label(sf, text="Format:", style="Field.TLabel").pack(side="left", padx=(0, 8))
        ttk.Combobox(sf, textvariable=self.p2i_format_var, values=["PNG", "JPEG"],
                     state="readonly", width=8, style="Dark.TCombobox").pack(side="left")
        f1.columnconfigure(0, weight=1)

        # ── Image -> PDF frame ──
        f2 = ttk.Frame(self.convert_dynamic, style="Card.TFrame")
        ttk.Label(f2, text=_("convert_image_files"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        
        from src.gui.styles import FIELD_COLOR, TEXT_COLOR, CONVERT_ACCENT
        self.i2p_listbox = tk.Listbox(f2, bg=FIELD_COLOR, fg=TEXT_COLOR, selectbackground=CONVERT_ACCENT,
                                       selectforeground=TEXT_COLOR, font=("Segoe UI", 9), height=5,
                                       borderwidth=1, relief="solid", highlightthickness=0, activestyle="none")
        self.i2p_listbox.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(8, 0))
        ib = ttk.Frame(f2, style="Card.TFrame")
        ib.grid(row=1, column=1, sticky="n", pady=(8, 0))
        ttk.Button(ib, text=_("str_add"), command=self.i2p_add_files, style="Small.TButton").pack(fill="x", pady=(0, 4))
        ttk.Button(ib, text=_("str_remove"), command=self.i2p_remove_selected, style="Small.TButton").pack(fill="x")

        ttk.Label(f2, text=_("str_output_pdf"), style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(12, 0))
        r3 = ttk.Frame(f2, style="Card.TFrame")
        r3.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.i2p_output_entry = ttk.Entry(r3, textvariable=self.i2p_output_var, width=50, style="Dark.TEntry")
        self.i2p_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r3, text=_("str_save"), command=self.choose_i2p_output, style="Secondary.TButton").pack(side="right")

        sz = ttk.Frame(f2, style="Card.TFrame")
        sz.grid(row=4, column=0, sticky="w", pady=(12, 0))
        ttk.Label(sz, text=_("convert_page_size"), style="Field.TLabel").pack(side="left", padx=(0, 8))
        ttk.Combobox(sz, textvariable=self.i2p_size_var, values=[_("convert_original"), "A4", "Letter"],
                     state="readonly", width=10, style="Dark.TCombobox").pack(side="left")
        f2.columnconfigure(0, weight=1)

        # ── PDF -> Word frame ──
        f3 = ttk.Frame(self.convert_dynamic, style="Card.TFrame")
        ttk.Label(f3, text=_("str_input_pdf"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        r4 = ttk.Frame(f3, style="Card.TFrame")
        r4.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.p2w_input_entry = ttk.Entry(r4, textvariable=self.p2w_input_var, width=50, style="Dark.TEntry")
        self.p2w_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r4, text=_("str_browse"), command=self.choose_p2w_input, style="Secondary.TButton").pack(side="right")

        ttk.Label(f3, text=_("convert_output_word"), style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(14, 0))
        r5 = ttk.Frame(f3, style="Card.TFrame")
        r5.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.p2w_output_entry = ttk.Entry(r5, textvariable=self.p2w_output_var, width=50, style="Dark.TEntry")
        self.p2w_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r5, text=_("str_save"), command=self.choose_p2w_output, style="Secondary.TButton").pack(side="right")
        f3.columnconfigure(0, weight=1)

        # ── Word -> PDF frame ──
        f4 = ttk.Frame(self.convert_dynamic, style="Card.TFrame")
        ttk.Label(f4, text=_("convert_input_word"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        r6 = ttk.Frame(f4, style="Card.TFrame")
        r6.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.w2p_input_entry = ttk.Entry(r6, textvariable=self.w2p_input_var, width=50, style="Dark.TEntry")
        self.w2p_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r6, text=_("str_browse"), command=self.choose_w2p_input, style="Secondary.TButton").pack(side="right")

        ttk.Label(f4, text=_("str_output_pdf"), style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(14, 0))
        r7 = ttk.Frame(f4, style="Card.TFrame")
        r7.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.w2p_output_entry = ttk.Entry(r7, textvariable=self.w2p_output_var, width=50, style="Dark.TEntry")
        self.w2p_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r7, text=_("str_save"), command=self.choose_w2p_output, style="Secondary.TButton").pack(side="right")
        f4.columnconfigure(0, weight=1)

        # ── PPT -> PDF frame ──
        f5 = ttk.Frame(self.convert_dynamic, style="Card.TFrame")
        ttk.Label(f5, text=_("convert_input_ppt"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        r8 = ttk.Frame(f5, style="Card.TFrame")
        r8.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.ppt2p_input_entry = ttk.Entry(r8, textvariable=self.ppt2p_input_var, width=50, style="Dark.TEntry")
        self.ppt2p_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r8, text=_("str_browse"), command=self.choose_ppt2p_input, style="Secondary.TButton").pack(side="right")

        ttk.Label(f5, text=_("str_output_pdf"), style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(14, 0))
        r9 = ttk.Frame(f5, style="Card.TFrame")
        r9.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.ppt2p_output_entry = ttk.Entry(r9, textvariable=self.ppt2p_output_var, width=50, style="Dark.TEntry")
        self.ppt2p_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r9, text=_("str_save"), command=self.choose_ppt2p_output, style="Secondary.TButton").pack(side="right")
        f5.columnconfigure(0, weight=1)

        # ── Excel -> PDF frame ──
        f6 = ttk.Frame(self.convert_dynamic, style="Card.TFrame")
        ttk.Label(f6, text=_("convert_input_excel"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        r10 = ttk.Frame(f6, style="Card.TFrame")
        r10.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.excel2p_input_entry = ttk.Entry(r10, textvariable=self.excel2p_input_var, width=50, style="Dark.TEntry")
        self.excel2p_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r10, text=_("str_browse"), command=self.choose_excel2p_input, style="Secondary.TButton").pack(side="right")

        ttk.Label(f6, text=_("str_output_pdf"), style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(14, 0))
        r11 = ttk.Frame(f6, style="Card.TFrame")
        r11.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.excel2p_output_entry = ttk.Entry(r11, textvariable=self.excel2p_output_var, width=50, style="Dark.TEntry")
        self.excel2p_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r11, text=_("str_save"), command=self.choose_excel2p_output, style="Secondary.TButton").pack(side="right")
        f6.columnconfigure(0, weight=1)

        # ── PDF -> TXT frame ──
        f7 = ttk.Frame(self.convert_dynamic, style="Card.TFrame")
        ttk.Label(f7, text=_("str_input_pdf"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        r12 = ttk.Frame(f7, style="Card.TFrame")
        r12.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.p2txt_input_entry = ttk.Entry(r12, textvariable=self.p2txt_input_var, width=50, style="Dark.TEntry")
        self.p2txt_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r12, text=_("str_browse"), command=self.choose_p2txt_input, style="Secondary.TButton").pack(side="right")

        ttk.Label(f7, text=_("convert_output_txt"), style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(14, 0))
        r13 = ttk.Frame(f7, style="Card.TFrame")
        r13.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.p2txt_output_entry = ttk.Entry(r13, textvariable=self.p2txt_output_var, width=50, style="Dark.TEntry")
        self.p2txt_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r13, text=_("str_save"), command=self.choose_p2txt_output, style="Secondary.TButton").pack(side="right")
        f7.columnconfigure(0, weight=1)

        self.convert_frames = {
            _("convert_pdf2img"): f1,
            _("convert_img2pdf"): f2,
            _("convert_pdf2word"): f3,
            _("convert_word2pdf"): f4,
            _("convert_ppt2pdf"): f5,
            _("convert_excel2pdf"): f6,
            _("convert_pdf2txt"): f7,
        }
        self.switch_convert_mode()

        # Action button + progress
        self.convert_button = ttk.Button(c, text=_("convert_btn"), command=self.start_convert, style="Convert.TButton")
        self.convert_button.grid(row=3, column=0, sticky="w", pady=(22, 12))
        self.convert_progress_bar = ttk.Progressbar(c, mode="indeterminate", length=520, style="Convert.Horizontal.TProgressbar")
        self.convert_progress_bar.grid(row=4, column=0, sticky="ew", pady=(2, 12))
        self.convert_status_label = ttk.Label(c, textvariable=self.convert_status_var, style="ConvertStatus.TLabel")
        self.convert_status_label.grid(row=5, column=0, sticky="w")
        c.columnconfigure(0, weight=1)
        c.rowconfigure(2, weight=1)

    def switch_convert_mode(self):
        for frame in self.convert_frames.values():
            frame.grid_remove()
        mode = self.convert_mode_var.get()
        if mode in self.convert_frames:
            self.convert_frames[mode].grid(row=0, column=0, sticky="nsew")
        self.convert_dynamic.columnconfigure(0, weight=1)

    # ... File dialogs ...
    def choose_p2i_input(self):
        f = filedialog.askopenfilename(title=_("convert_dialog_pdf"), filetypes=[("PDF", "*.pdf")])
        if f:
            self.p2i_input_var.set(f)
            base = os.path.splitext(f)[0]
            self.p2i_folder_var.set(f"{base}_resimler")

    def choose_p2i_folder(self):
        f = filedialog.askdirectory(title=_("convert_dialog_folder"))
        if f:
            self.p2i_folder_var.set(f)

    def i2p_add_files(self):
        files = filedialog.askopenfilenames(title=_("convert_dialog_img"),
                                             filetypes=[(_("convert_images_label"), "*.png *.jpg *.jpeg *.bmp *.tiff *.gif")])
        for f in files:
            self.i2p_file_list.append(f)
            self.i2p_listbox.insert(tk.END, os.path.basename(f))
        if self.i2p_file_list and not self.i2p_output_var.get().strip():
            base = os.path.splitext(self.i2p_file_list[0])[0]
            self.i2p_output_var.set(f"{base}_birlesik.pdf")

    def i2p_remove_selected(self):
        sel = self.i2p_listbox.curselection()
        for i in reversed(sel):
            self.i2p_listbox.delete(i)
            del self.i2p_file_list[i]

    def choose_i2p_output(self):
        f = filedialog.asksaveasfilename(title=_("convert_dialog_pdf_save"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if f:
            self.i2p_output_var.set(f)

    def choose_p2w_input(self):
        f = filedialog.askopenfilename(title=_("convert_dialog_pdf"), filetypes=[("PDF", "*.pdf")])
        if f:
            self.p2w_input_var.set(f)
            base = os.path.splitext(f)[0]
            self.p2w_output_var.set(f"{base}.docx")

    def choose_p2w_output(self):
        f = filedialog.asksaveasfilename(title=_("convert_dialog_word_save"), defaultextension=".docx", filetypes=[("Word", "*.docx")])
        if f:
            self.p2w_output_var.set(f)

    def choose_w2p_input(self):
        f = filedialog.askopenfilename(title=_("convert_dialog_pdf"), filetypes=[("Word", "*.docx")])
        if f:
            self.w2p_input_var.set(f)
            base = os.path.splitext(f)[0]
            self.w2p_output_var.set(f"{base}.pdf")

    def choose_w2p_output(self):
        f = filedialog.asksaveasfilename(title=_("convert_dialog_pdf_save"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if f:
            self.w2p_output_var.set(f)

    def choose_ppt2p_input(self):
        f = filedialog.askopenfilename(title=_("str_file_selection"), filetypes=[("PowerPoint", "*.ppt *.pptx")])
        if f:
            self.ppt2p_input_var.set(f)
            base = os.path.splitext(f)[0]
            self.ppt2p_output_var.set(f"{base}.pdf")

    def choose_ppt2p_output(self):
        f = filedialog.asksaveasfilename(title=_("convert_dialog_pdf_save"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if f:
            self.ppt2p_output_var.set(f)

    def choose_excel2p_input(self):
        f = filedialog.askopenfilename(title=_("str_file_selection"), filetypes=[("Excel", "*.xls *.xlsx")])
        if f:
            self.excel2p_input_var.set(f)
            base = os.path.splitext(f)[0]
            self.excel2p_output_var.set(f"{base}.pdf")

    def choose_excel2p_output(self):
        f = filedialog.asksaveasfilename(title=_("convert_dialog_pdf_save"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if f:
            self.excel2p_output_var.set(f)

    def choose_p2txt_input(self):
        f = filedialog.askopenfilename(title=_("convert_dialog_pdf"), filetypes=[("PDF", "*.pdf")])
        if f:
            self.p2txt_input_var.set(f)
            base = os.path.splitext(f)[0]
            self.p2txt_output_var.set(f"{base}.txt")

    def choose_p2txt_output(self):
        f = filedialog.asksaveasfilename(title=_("adv_dialog_txt_save"), defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if f:
            self.p2txt_output_var.set(f)

    # Dispatch conversion
    def start_convert(self):
        mode = self.convert_mode_var.get()
        set_busy(self.convert_button, self.convert_progress_bar, True)
        self.convert_status_var.set(_("convert_running").format(mode=mode))

        if mode == _("convert_pdf2img"):
            inp = self.p2i_input_var.get().strip()
            folder = self.p2i_folder_var.get().strip()
            if not inp or not os.path.isfile(inp):
                quick_error(_("err_select_valid_file"), self.convert_button, self.convert_progress_bar, self.convert_status_var)
                return
            if not folder:
                quick_error(_("err_set_output_folder"), self.convert_button, self.convert_progress_bar, self.convert_status_var)
                return
            dpi = int(self.p2i_dpi_var.get())
            fmt = self.p2i_format_var.get().lower()
            threading.Thread(target=self._run_p2i, args=(inp, folder, dpi, fmt), daemon=True).start()

        elif mode == _("convert_img2pdf"):
            if not self.i2p_file_list:
                quick_error(_("err_add_min_1_image"), self.convert_button, self.convert_progress_bar, self.convert_status_var)
                return
            output = self.i2p_output_var.get().strip()
            if not output:
                quick_error(_("err_set_output"), self.convert_button, self.convert_progress_bar, self.convert_status_var)
                return
            size = self.i2p_size_var.get()
            threading.Thread(target=self._run_i2p, args=(list(self.i2p_file_list), output, size), daemon=True).start()

        elif mode == _("convert_pdf2word"):
            inp = self.p2w_input_var.get().strip()
            out = self.p2w_output_var.get().strip()
            if not inp or not os.path.isfile(inp):
                quick_error(_("err_select_valid_file"), self.convert_button, self.convert_progress_bar, self.convert_status_var)
                return
            if not out:
                quick_error(_("err_set_output"), self.convert_button, self.convert_progress_bar, self.convert_status_var)
                return
            threading.Thread(target=self._run_p2w, args=(inp, out), daemon=True).start()

        elif mode == _("convert_word2pdf"):
            inp = self.w2p_input_var.get().strip()
            out = self.w2p_output_var.get().strip()
            if not inp or not os.path.isfile(inp):
                quick_error(_("err_select_valid_word"), self.convert_button, self.convert_progress_bar, self.convert_status_var)
                return
            if not out:
                quick_error(_("err_set_output"), self.convert_button, self.convert_progress_bar, self.convert_status_var)
                return
            threading.Thread(target=self._run_w2p, args=(inp, out), daemon=True).start()

        elif mode == _("convert_ppt2pdf"):
            inp = self.ppt2p_input_var.get().strip()
            out = self.ppt2p_output_var.get().strip()
            if not inp or not os.path.isfile(inp):
                quick_error(_("err_select_valid_ppt"), self.convert_button, self.convert_progress_bar, self.convert_status_var)
                return
            if not out:
                quick_error(_("err_set_output"), self.convert_button, self.convert_progress_bar, self.convert_status_var)
                return
            threading.Thread(target=self._run_ppt2p, args=(inp, out), daemon=True).start()

        elif mode == _("convert_excel2pdf"):
            inp = self.excel2p_input_var.get().strip()
            out = self.excel2p_output_var.get().strip()
            if not inp or not os.path.isfile(inp):
                quick_error(_("err_select_valid_excel"), self.convert_button, self.convert_progress_bar, self.convert_status_var)
                return
            if not out:
                quick_error(_("err_set_output"), self.convert_button, self.convert_progress_bar, self.convert_status_var)
                return
            threading.Thread(target=self._run_excel2p, args=(inp, out), daemon=True).start()

        elif mode == _("convert_pdf2txt"):
            inp = self.p2txt_input_var.get().strip()
            out = self.p2txt_output_var.get().strip()
            if not inp or not os.path.isfile(inp):
                quick_error(_("err_select_valid_pdf"), self.convert_button, self.convert_progress_bar, self.convert_status_var)
                return
            if not out:
                quick_error(_("err_set_output"), self.convert_button, self.convert_progress_bar, self.convert_status_var)
                return
            threading.Thread(target=self._run_p2txt, args=(inp, out), daemon=True).start()

    def _run_p2i(self, inp, folder, dpi, fmt):
        try:
            count = pdf_to_images(inp, folder, dpi, fmt)
            msg = _("convert_result_p2i").format(count=count, dpi=dpi, folder=folder)
            self.app_root.after(0, operation_done, self.app_root, self.convert_button, self.convert_progress_bar,
                            self.convert_status_var, _("convert_done"), msg, None)
        except Exception as exc:
            self.app_root.after(0, operation_done, self.app_root, self.convert_button, self.convert_progress_bar,
                            self.convert_status_var, _("convert_fail"), None, str(exc))

    def _run_i2p(self, image_paths, output, size):
        try:
            images_to_pdf(image_paths, output, size)
            sz = format_size_mb(output)
            msg = _("convert_result_i2p").format(count=len(image_paths), size=sz, output=output)
            self.app_root.after(0, operation_done, self.app_root, self.convert_button, self.convert_progress_bar,
                            self.convert_status_var, _("convert_done"), msg, None)
        except Exception as exc:
            self.app_root.after(0, operation_done, self.app_root, self.convert_button, self.convert_progress_bar,
                            self.convert_status_var, _("convert_fail"), None, str(exc))

    def _run_p2w(self, inp, out):
        try:
            pdf_to_word(inp, out)
            msg = _("convert_result_p2w").format(output=out)
            self.app_root.after(0, operation_done, self.app_root, self.convert_button, self.convert_progress_bar,
                            self.convert_status_var, _("convert_done"), msg, None)
        except Exception as exc:
            self.app_root.after(0, operation_done, self.app_root, self.convert_button, self.convert_progress_bar,
                            self.convert_status_var, _("convert_fail"), None, str(exc))

    def _run_w2p(self, inp, out):
        try:
            word_to_pdf(inp, out)
            msg = _("convert_result_w2p").format(output=out)
            self.app_root.after(0, operation_done, self.app_root, self.convert_button, self.convert_progress_bar,
                            self.convert_status_var, _("convert_done"), msg, None)
        except Exception as exc:
            self.app_root.after(0, operation_done, self.app_root, self.convert_button, self.convert_progress_bar,
                            self.convert_status_var, _("convert_fail"), None, str(exc))

    def _run_ppt2p(self, inp, out):
        try:
            ppt_to_pdf(inp, out)
            msg = _("convert_result_ppt2pdf").format(output=out)
            self.app_root.after(0, operation_done, self.app_root, self.convert_button, self.convert_progress_bar,
                            self.convert_status_var, _("convert_done"), msg, None)
        except Exception as exc:
            self.app_root.after(0, operation_done, self.app_root, self.convert_button, self.convert_progress_bar,
                            self.convert_status_var, _("convert_fail"), None, str(exc))

    def _run_excel2p(self, inp, out):
        try:
            excel_to_pdf(inp, out)
            msg = _("convert_result_excel2pdf").format(output=out)
            self.app_root.after(0, operation_done, self.app_root, self.convert_button, self.convert_progress_bar,
                            self.convert_status_var, _("convert_done"), msg, None)
        except Exception as exc:
            self.app_root.after(0, operation_done, self.app_root, self.convert_button, self.convert_progress_bar,
                            self.convert_status_var, _("convert_fail"), None, str(exc))

    def _run_p2txt(self, inp, out):
        try:
            pdf_to_txt(inp, out)
            msg = _("convert_result_pdf2txt").format(output=out)
            self.app_root.after(0, operation_done, self.app_root, self.convert_button, self.convert_progress_bar,
                            self.convert_status_var, _("convert_done"), msg, None)
        except Exception as exc:
            self.app_root.after(0, operation_done, self.app_root, self.convert_button, self.convert_progress_bar,
                            self.convert_status_var, _("convert_fail"), None, str(exc))
