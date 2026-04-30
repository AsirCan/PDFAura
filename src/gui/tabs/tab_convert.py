import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from src.core.convert import excel_to_pdf, images_to_pdf, pdf_to_images, pdf_to_txt, pdf_to_word, ppt_to_pdf, word_to_pdf
from src.core.lang_manager import _
from src.core.task_manager import TaskContext, CancelledError
from src.gui.helpers import InlineFeedback, ProgressFooter, bind_preview, build_tool_header, notify_preview, quick_error
from src.gui.styles import CONVERT_ACCENT, FIELD_COLOR, TEXT_COLOR
from src.utils.file_helper import format_size_mb


class ConvertTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        self._task_ctx = None

        self.convert_mode_var = tk.StringVar(value=_("convert_pdf2img"))
        self.convert_status_var = tk.StringVar(value=_("str_ready"))

        self.p2i_input_var = tk.StringVar()
        self.p2i_folder_var = tk.StringVar()
        self.p2i_dpi_var = tk.StringVar(value="300")
        self.p2i_format_var = tk.StringVar(value="PNG")

        self.i2p_file_list = []
        self.i2p_output_var = tk.StringVar()
        self.i2p_size_var = tk.StringVar(value=_("convert_original"))

        self.p2w_input_var = tk.StringVar()
        self.p2w_output_var = tk.StringVar()

        self.w2p_input_var = tk.StringVar()
        self.w2p_output_var = tk.StringVar()

        self.ppt2p_input_var = tk.StringVar()
        self.ppt2p_output_var = tk.StringVar()

        self.excel2p_input_var = tk.StringVar()
        self.excel2p_output_var = tk.StringVar()

        self.p2txt_input_var = tk.StringVar()
        self.p2txt_output_var = tk.StringVar()

        bind_preview(self.app_root, self.p2i_input_var, self.p2w_input_var, self.p2txt_input_var)
        self.build_ui()

    def build_ui(self):
        shell = ttk.Frame(self.parent, style="App.TFrame")
        shell.pack(fill="both", expand=True)

        build_tool_header(shell, _("txt_convert"), _("convert_btn"), _("convert_type"), badge_text=_("convert_type"))

        body = ttk.Frame(shell, style="App.TFrame")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, style="Surface.TFrame", padding=22)
        left.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text=_("convert_type"), style="Field.TLabel").pack(anchor="w")
        self.convert_mode_combo = ttk.Combobox(
            left,
            textvariable=self.convert_mode_var,
            values=[
                _("convert_pdf2img"),
                _("convert_img2pdf"),
                _("convert_pdf2word"),
                _("convert_word2pdf"),
                _("convert_ppt2pdf"),
                _("convert_excel2pdf"),
                _("convert_pdf2txt"),
            ],
            state="readonly",
            width=24,
            style="Dark.TCombobox",
        )
        self.convert_mode_combo.pack(anchor="w", pady=(8, 0))
        self.convert_mode_combo.bind("<<ComboboxSelected>>", lambda _event: self.switch_convert_mode())

        self.convert_dynamic = ttk.Frame(left, style="Panel.TFrame", padding=16)
        self.convert_dynamic.pack(fill="both", expand=True, pady=(18, 0))

        f1 = ttk.Frame(self.convert_dynamic, style="Panel.TFrame")
        ttk.Label(f1, text=_("str_input_pdf"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        r1 = ttk.Frame(f1, style="Panel.TFrame")
        r1.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.p2i_input_entry = ttk.Entry(r1, textvariable=self.p2i_input_var, style="Dark.TEntry")
        self.p2i_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r1, text=_("str_browse"), command=self.choose_p2i_input, style="Secondary.TButton").pack(side="right")

        ttk.Label(f1, text=_("str_output_folder"), style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(14, 0))
        r2 = ttk.Frame(f1, style="Panel.TFrame")
        r2.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.p2i_folder_entry = ttk.Entry(r2, textvariable=self.p2i_folder_var, style="Dark.TEntry")
        self.p2i_folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r2, text=_("str_browse"), command=self.choose_p2i_folder, style="Secondary.TButton").pack(side="right")

        sf = ttk.Frame(f1, style="Panel.TFrame")
        sf.grid(row=4, column=0, sticky="w", pady=(14, 0))
        ttk.Label(sf, text="DPI", style="Field.TLabel").pack(side="left")
        ttk.Combobox(sf, textvariable=self.p2i_dpi_var, values=["72", "150", "300", "600"], state="readonly", width=6, style="Dark.TCombobox").pack(side="left", padx=(10, 18))
        ttk.Label(sf, text="Format", style="Field.TLabel").pack(side="left")
        ttk.Combobox(sf, textvariable=self.p2i_format_var, values=["PNG", "JPEG"], state="readonly", width=8, style="Dark.TCombobox").pack(side="left", padx=(10, 0))
        f1.columnconfigure(0, weight=1)

        f2 = ttk.Frame(self.convert_dynamic, style="Panel.TFrame")
        ttk.Label(f2, text=_("convert_image_files"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        self.i2p_listbox = tk.Listbox(
            f2,
            bg=FIELD_COLOR,
            fg=TEXT_COLOR,
            selectbackground=CONVERT_ACCENT,
            selectforeground=TEXT_COLOR,
            font=("Segoe UI", 9),
            height=5,
            borderwidth=1,
            relief="solid",
            highlightthickness=0,
            activestyle="none",
        )
        self.i2p_listbox.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        ib = ttk.Frame(f2, style="Panel.TFrame")
        ib.grid(row=1, column=1, sticky="n", padx=(10, 0), pady=(8, 0))
        ttk.Button(ib, text=_("str_add"), command=self.i2p_add_files, style="Secondary.TButton").pack(fill="x")
        ttk.Button(ib, text=_("str_remove"), command=self.i2p_remove_selected, style="Ghost.TButton").pack(fill="x", pady=(8, 0))

        ttk.Label(f2, text=_("str_output_pdf"), style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(14, 0))
        r3 = ttk.Frame(f2, style="Panel.TFrame")
        r3.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.i2p_output_entry = ttk.Entry(r3, textvariable=self.i2p_output_var, style="Dark.TEntry")
        self.i2p_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r3, text=_("str_save"), command=self.choose_i2p_output, style="Secondary.TButton").pack(side="right")

        sz = ttk.Frame(f2, style="Panel.TFrame")
        sz.grid(row=4, column=0, sticky="w", pady=(12, 0))
        ttk.Label(sz, text=_("convert_page_size"), style="Field.TLabel").pack(side="left")
        ttk.Combobox(sz, textvariable=self.i2p_size_var, values=[_("convert_original"), "A4", "Letter"], state="readonly", width=10, style="Dark.TCombobox").pack(side="left", padx=(10, 0))
        f2.columnconfigure(0, weight=1)

        f3 = ttk.Frame(self.convert_dynamic, style="Panel.TFrame")
        self._file_output_pair(f3, _("str_input_pdf"), self.p2w_input_var, self.choose_p2w_input, _("convert_output_word"), self.p2w_output_var, self.choose_p2w_output, _("str_save"))

        f4 = ttk.Frame(self.convert_dynamic, style="Panel.TFrame")
        self._file_output_pair(f4, _("convert_input_word"), self.w2p_input_var, self.choose_w2p_input, _("str_output_pdf"), self.w2p_output_var, self.choose_w2p_output, _("str_save"))

        f5 = ttk.Frame(self.convert_dynamic, style="Panel.TFrame")
        self._file_output_pair(f5, _("convert_input_ppt"), self.ppt2p_input_var, self.choose_ppt2p_input, _("str_output_pdf"), self.ppt2p_output_var, self.choose_ppt2p_output, _("str_save"))

        f6 = ttk.Frame(self.convert_dynamic, style="Panel.TFrame")
        self._file_output_pair(f6, _("convert_input_excel"), self.excel2p_input_var, self.choose_excel2p_input, _("str_output_pdf"), self.excel2p_output_var, self.choose_excel2p_output, _("str_save"))

        f7 = ttk.Frame(self.convert_dynamic, style="Panel.TFrame")
        self._file_output_pair(f7, _("str_input_pdf"), self.p2txt_input_var, self.choose_p2txt_input, _("convert_output_txt"), self.p2txt_output_var, self.choose_p2txt_output, _("str_save"))

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

        self.footer = ProgressFooter(left, _("convert_btn"), self.start_convert, button_style="Convert.TButton", progress_style="Convert.Horizontal.TProgressbar")
        self.footer.pack(fill="x", pady=(22, 0))

        right = ttk.Frame(body, style="App.TFrame")
        right.pack(side="left", fill="y", padx=(18, 0))
        self.feedback = InlineFeedback(right)
        self.feedback.pack(fill="x")
        self.feedback.set_info(_("convert_type"), _("convert_running").format(mode=self.convert_mode_var.get()))

    def _file_output_pair(self, frame, input_label, input_var, choose_input, output_label, output_var, choose_output, output_button_text):
        ttk.Label(frame, text=input_label, style="Field.TLabel").grid(row=0, column=0, sticky="w")
        row_in = ttk.Frame(frame, style="Panel.TFrame")
        row_in.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Entry(row_in, textvariable=input_var, style="Dark.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(row_in, text=_("str_browse"), command=choose_input, style="Secondary.TButton").pack(side="right")

        ttk.Label(frame, text=output_label, style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(14, 0))
        row_out = ttk.Frame(frame, style="Panel.TFrame")
        row_out.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Entry(row_out, textvariable=output_var, style="Dark.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(row_out, text=output_button_text, command=choose_output, style="Ghost.TButton").pack(side="right")
        frame.columnconfigure(0, weight=1)

    def switch_convert_mode(self):
        for frame in self.convert_frames.values():
            frame.grid_remove()
        mode = self.convert_mode_var.get()
        if mode in self.convert_frames:
            self.convert_frames[mode].grid(row=0, column=0, sticky="nsew")
        self.convert_dynamic.columnconfigure(0, weight=1)
        if mode in (_("convert_word2pdf"), _("convert_ppt2pdf"), _("convert_excel2pdf"), _("convert_img2pdf")):
            notify_preview(self.app_root, None)
        if hasattr(self, "feedback"):
            self.feedback.set_info(_("convert_type"), _("convert_running").format(mode=mode))

    def choose_p2i_input(self):
        selected = filedialog.askopenfilename(title=_("convert_dialog_pdf"), filetypes=[("PDF", "*.pdf")])
        if selected:
            self.p2i_input_var.set(selected)
            base = os.path.splitext(selected)[0]
            self.p2i_folder_var.set(f"{base}_resimler")

    def choose_p2i_folder(self):
        selected = filedialog.askdirectory(title=_("convert_dialog_folder"))
        if selected:
            self.p2i_folder_var.set(selected)

    def i2p_add_files(self):
        files = filedialog.askopenfilenames(title=_("convert_dialog_img"), filetypes=[(_("convert_images_label"), "*.png *.jpg *.jpeg *.bmp *.tiff *.gif")])
        for file_path in files:
            self.i2p_file_list.append(file_path)
            self.i2p_listbox.insert(tk.END, os.path.basename(file_path))
        if self.i2p_file_list and not self.i2p_output_var.get().strip():
            base = os.path.splitext(self.i2p_file_list[0])[0]
            self.i2p_output_var.set(f"{base}_birleşik.pdf")

    def i2p_remove_selected(self):
        selected = self.i2p_listbox.curselection()
        for index in reversed(selected):
            self.i2p_listbox.delete(index)
            del self.i2p_file_list[index]

    def choose_i2p_output(self):
        selected = filedialog.asksaveasfilename(title=_("convert_dialog_pdf_save"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.i2p_output_var.set(selected)

    def choose_p2w_input(self):
        selected = filedialog.askopenfilename(title=_("convert_dialog_pdf"), filetypes=[("PDF", "*.pdf")])
        if selected:
            self.p2w_input_var.set(selected)
            self.p2w_output_var.set(f"{os.path.splitext(selected)[0]}.docx")

    def choose_p2w_output(self):
        selected = filedialog.asksaveasfilename(title=_("convert_dialog_word_save"), defaultextension=".docx", filetypes=[("Word", "*.docx")])
        if selected:
            self.p2w_output_var.set(selected)

    def choose_w2p_input(self):
        selected = filedialog.askopenfilename(title=_("convert_dialog_pdf"), filetypes=[("Word", "*.docx")])
        if selected:
            self.w2p_input_var.set(selected)
            self.w2p_output_var.set(f"{os.path.splitext(selected)[0]}.pdf")

    def choose_w2p_output(self):
        selected = filedialog.asksaveasfilename(title=_("convert_dialog_pdf_save"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.w2p_output_var.set(selected)

    def choose_ppt2p_input(self):
        selected = filedialog.askopenfilename(title=_("str_file_selection"), filetypes=[("PowerPoint", "*.ppt *.pptx")])
        if selected:
            self.ppt2p_input_var.set(selected)
            self.ppt2p_output_var.set(f"{os.path.splitext(selected)[0]}.pdf")

    def choose_ppt2p_output(self):
        selected = filedialog.asksaveasfilename(title=_("convert_dialog_pdf_save"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.ppt2p_output_var.set(selected)

    def choose_excel2p_input(self):
        selected = filedialog.askopenfilename(title=_("str_file_selection"), filetypes=[("Excel", "*.xls *.xlsx")])
        if selected:
            self.excel2p_input_var.set(selected)
            self.excel2p_output_var.set(f"{os.path.splitext(selected)[0]}.pdf")

    def choose_excel2p_output(self):
        selected = filedialog.asksaveasfilename(title=_("convert_dialog_pdf_save"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.excel2p_output_var.set(selected)

    def choose_p2txt_input(self):
        selected = filedialog.askopenfilename(title=_("convert_dialog_pdf"), filetypes=[("PDF", "*.pdf")])
        if selected:
            self.p2txt_input_var.set(selected)
            self.p2txt_output_var.set(f"{os.path.splitext(selected)[0]}.txt")

    def choose_p2txt_output(self):
        selected = filedialog.asksaveasfilename(title=_("adv_dialog_txt_save"), defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if selected:
            self.p2txt_output_var.set(selected)

    def handle_external_drop(self, file_path):
        mode = self.convert_mode_var.get()
        if mode == _("convert_pdf2img") and file_path.lower().endswith(".pdf"):
            self.p2i_input_var.set(file_path)
            self.p2i_folder_var.set(f"{os.path.splitext(file_path)[0]}_resimler")
        elif mode == _("convert_img2pdf") and file_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif")):
            self.i2p_file_list.append(file_path)
            self.i2p_listbox.insert(tk.END, os.path.basename(file_path))
            if not self.i2p_output_var.get().strip():
                self.i2p_output_var.set(f"{os.path.splitext(file_path)[0]}_birleşik.pdf")
        elif mode == _("convert_pdf2word") and file_path.lower().endswith(".pdf"):
            self.p2w_input_var.set(file_path)
            self.p2w_output_var.set(f"{os.path.splitext(file_path)[0]}.docx")
        elif mode == _("convert_word2pdf") and file_path.lower().endswith(".docx"):
            self.w2p_input_var.set(file_path)
            self.w2p_output_var.set(f"{os.path.splitext(file_path)[0]}.pdf")
        elif mode == _("convert_ppt2pdf") and file_path.lower().endswith((".ppt", ".pptx")):
            self.ppt2p_input_var.set(file_path)
            self.ppt2p_output_var.set(f"{os.path.splitext(file_path)[0]}.pdf")
        elif mode == _("convert_excel2pdf") and file_path.lower().endswith((".xls", ".xlsx")):
            self.excel2p_input_var.set(file_path)
            self.excel2p_output_var.set(f"{os.path.splitext(file_path)[0]}.pdf")
        elif mode == _("convert_pdf2txt") and file_path.lower().endswith(".pdf"):
            self.p2txt_input_var.set(file_path)
            self.p2txt_output_var.set(f"{os.path.splitext(file_path)[0]}.txt")

    def _cancel_task(self):
        if self._task_ctx:
            self._task_ctx.cancel()

    def start_convert(self):
        mode = self.convert_mode_var.get()
        busy_text = _("convert_running").format(mode=mode)

        def _on_progress(current, total, message=""):
            self.app_root.after(0, self.footer.update_progress, current, total, message)

        self._task_ctx = TaskContext(progress_callback=_on_progress)
        self.footer.start_busy(cancel_callback=self._cancel_task)
        self.feedback.set_busy(busy_text)
        self.convert_status_var.set(busy_text)

        if mode == _("convert_pdf2img"):
            inp = self.p2i_input_var.get().strip()
            folder = self.p2i_folder_var.get().strip()
            if not inp or not os.path.isfile(inp):
                self.footer.stop_busy()
                quick_error(_("err_select_valid_file"), self.footer.action_button, None, self.convert_status_var, self.feedback)
                return
            if not folder:
                self.footer.stop_busy()
                quick_error(_("err_set_output_folder"), self.footer.action_button, None, self.convert_status_var, self.feedback)
                return
            threading.Thread(target=self._run_p2i, args=(inp, folder, int(self.p2i_dpi_var.get()), self.p2i_format_var.get().lower()), daemon=True).start()
        elif mode == _("convert_img2pdf"):
            if not self.i2p_file_list:
                self.footer.stop_busy()
                quick_error(_("err_add_min_1_image"), self.footer.action_button, None, self.convert_status_var, self.feedback)
                return
            output = self.i2p_output_var.get().strip()
            if not output:
                self.footer.stop_busy()
                quick_error(_("err_set_output"), self.footer.action_button, None, self.convert_status_var, self.feedback)
                return
            threading.Thread(target=self._run_i2p, args=(list(self.i2p_file_list), output, self.i2p_size_var.get()), daemon=True).start()
        elif mode == _("convert_pdf2word"):
            inp = self.p2w_input_var.get().strip()
            out = self.p2w_output_var.get().strip()
            if not inp or not os.path.isfile(inp):
                self.footer.stop_busy()
                quick_error(_("err_select_valid_file"), self.footer.action_button, None, self.convert_status_var, self.feedback)
                return
            if not out:
                self.footer.stop_busy()
                quick_error(_("err_set_output"), self.footer.action_button, None, self.convert_status_var, self.feedback)
                return
            threading.Thread(target=self._run_p2w, args=(inp, out), daemon=True).start()
        elif mode == _("convert_word2pdf"):
            inp = self.w2p_input_var.get().strip()
            out = self.w2p_output_var.get().strip()
            if not inp or not os.path.isfile(inp):
                self.footer.stop_busy()
                quick_error(_("err_select_valid_word"), self.footer.action_button, None, self.convert_status_var, self.feedback)
                return
            if not out:
                self.footer.stop_busy()
                quick_error(_("err_set_output"), self.footer.action_button, None, self.convert_status_var, self.feedback)
                return
            threading.Thread(target=self._run_w2p, args=(inp, out), daemon=True).start()
        elif mode == _("convert_ppt2pdf"):
            inp = self.ppt2p_input_var.get().strip()
            out = self.ppt2p_output_var.get().strip()
            if not inp or not os.path.isfile(inp):
                self.footer.stop_busy()
                quick_error(_("err_select_valid_ppt"), self.footer.action_button, None, self.convert_status_var, self.feedback)
                return
            if not out:
                self.footer.stop_busy()
                quick_error(_("err_set_output"), self.footer.action_button, None, self.convert_status_var, self.feedback)
                return
            threading.Thread(target=self._run_ppt2p, args=(inp, out), daemon=True).start()
        elif mode == _("convert_excel2pdf"):
            inp = self.excel2p_input_var.get().strip()
            out = self.excel2p_output_var.get().strip()
            if not inp or not os.path.isfile(inp):
                self.footer.stop_busy()
                quick_error(_("err_select_valid_excel"), self.footer.action_button, None, self.convert_status_var, self.feedback)
                return
            if not out:
                self.footer.stop_busy()
                quick_error(_("err_set_output"), self.footer.action_button, None, self.convert_status_var, self.feedback)
                return
            threading.Thread(target=self._run_excel2p, args=(inp, out), daemon=True).start()
        elif mode == _("convert_pdf2txt"):
            inp = self.p2txt_input_var.get().strip()
            out = self.p2txt_output_var.get().strip()
            if not inp or not os.path.isfile(inp):
                self.footer.stop_busy()
                quick_error(_("err_select_valid_pdf"), self.footer.action_button, None, self.convert_status_var, self.feedback)
                return
            if not out:
                self.footer.stop_busy()
                quick_error(_("err_set_output"), self.footer.action_button, None, self.convert_status_var, self.feedback)
                return
            threading.Thread(target=self._run_p2txt, args=(inp, out), daemon=True).start()

    def _finish(self, title, message, output_path):
        def _do():
            self.footer.finish_success()
            self.convert_status_var.set(title)
            self.feedback.set_success(title, message, output_path)
        self.app_root.after(0, _do)

    def _fail(self, title, exc):
        def _do():
            self.footer.stop_busy()
            self.convert_status_var.set(title)
            self.feedback.set_error(title, str(exc))
        self.app_root.after(0, _do)

    def _cancelled(self):
        def _do():
            self.footer.stop_busy()
            self.convert_status_var.set(_("perf_cancelled"))
            self.feedback.set_cancelled()
        self.app_root.after(0, _do)

    def _run_p2i(self, inp, folder, dpi, fmt):
        try:
            count = pdf_to_images(inp, folder, dpi, fmt, ctx=self._task_ctx)
            self._finish(_("convert_done"), _("convert_result_p2i").format(count=count, dpi=dpi, folder=folder), folder)
        except CancelledError:
            self._cancelled()
        except Exception as exc:
            self._fail(_("convert_fail"), exc)

    def _run_i2p(self, image_paths, output, size):
        try:
            images_to_pdf(image_paths, output, size, ctx=self._task_ctx)
            message = _("convert_result_i2p").format(count=len(image_paths), size=format_size_mb(output), output=output)
            self._finish(_("convert_done"), message, output)
        except CancelledError:
            self._cancelled()
        except Exception as exc:
            self._fail(_("convert_fail"), exc)

    def _run_p2w(self, inp, out):
        try:
            pdf_to_word(inp, out, ctx=self._task_ctx)
            self._finish(_("convert_done"), _("convert_result_p2w").format(output=out), out)
        except CancelledError:
            self._cancelled()
        except Exception as exc:
            self._fail(_("convert_fail"), exc)

    def _run_w2p(self, inp, out):
        try:
            word_to_pdf(inp, out, ctx=self._task_ctx)
            self._finish(_("convert_done"), _("convert_result_w2p").format(output=out), out)
        except CancelledError:
            self._cancelled()
        except Exception as exc:
            self._fail(_("convert_fail"), exc)

    def _run_ppt2p(self, inp, out):
        try:
            ppt_to_pdf(inp, out, ctx=self._task_ctx)
            self._finish(_("convert_done"), _("convert_result_ppt2pdf").format(output=out), out)
        except CancelledError:
            self._cancelled()
        except Exception as exc:
            self._fail(_("convert_fail"), exc)

    def _run_excel2p(self, inp, out):
        try:
            excel_to_pdf(inp, out, ctx=self._task_ctx)
            self._finish(_("convert_done"), _("convert_result_excel2pdf").format(output=out), out)
        except CancelledError:
            self._cancelled()
        except Exception as exc:
            self._fail(_("convert_fail"), exc)

    def _run_p2txt(self, inp, out):
        try:
            pdf_to_txt(inp, out, ctx=self._task_ctx)
            self._finish(_("convert_done"), _("convert_result_pdf2txt").format(output=out), out)
        except CancelledError:
            self._cancelled()
        except Exception as exc:
            self._fail(_("convert_fail"), exc)
