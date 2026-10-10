import os
import tkinter as tk
from tkinter import ttk, filedialog

from src.app.tools import mode_from_label, suggest_output
from src.core.lang_manager import _
from src.gui import styles
from src.gui.styles import P
from src.gui.theme.images import Icons
from src.gui.widgets import SegmentedControl
from src.gui.helpers import (
    InlineFeedback,
    ListEmptyHint,
    ProgressFooter,
    ToolLayout,
    ToolRun,
    bind_preview,
    move_listbox_item,
    notify_preview,
    style_listbox,
)


class ConvertTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root

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
        self.layout = ToolLayout(self.parent, _("hint_convert"))
        left = self.layout.form

        ttk.Label(left, text=_("convert_type"), style="Field.TLabel").pack(anchor="w")
        self.convert_mode_picker = SegmentedControl(left, self.convert_mode_var, [
            _("convert_pdf2img"),
            _("convert_img2pdf"),
            _("convert_pdf2word"),
            _("convert_word2pdf"),
            _("convert_ppt2pdf"),
            _("convert_excel2pdf"),
            _("convert_pdf2txt"),
        ], command=self.switch_convert_mode)
        self.convert_mode_picker.pack(fill="x", pady=(8, 0))

        self.convert_dynamic = ttk.Frame(left, style="PanelCard.TFrame", padding=16)
        self.convert_dynamic.pack(fill="both", expand=True, pady=(18, 0))

        f1 = ttk.Frame(self.convert_dynamic, style="Panel.TFrame")
        ttk.Label(f1, text=_("str_input_pdf"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        r1 = ttk.Frame(f1, style="Panel.TFrame")
        r1.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.p2i_input_entry = ttk.Entry(r1, textvariable=self.p2i_input_var, style="Input.TEntry")
        self.p2i_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r1, text=_("str_browse"), command=self.choose_p2i_input, style="Secondary.TButton").pack(side="right")

        ttk.Label(f1, text=_("str_output_folder"), style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(14, 0))
        r2 = ttk.Frame(f1, style="Panel.TFrame")
        r2.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.p2i_folder_entry = ttk.Entry(r2, textvariable=self.p2i_folder_var, style="Input.TEntry")
        self.p2i_folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r2, text=_("str_browse"), command=self.choose_p2i_folder, style="Secondary.TButton").pack(side="right")

        sf = ttk.Frame(f1, style="Panel.TFrame")
        sf.grid(row=4, column=0, sticky="w", pady=(14, 0))
        ttk.Label(sf, text="DPI", style="Field.TLabel").pack(side="left")
        ttk.Combobox(sf, textvariable=self.p2i_dpi_var, values=["72", "150", "300", "600"], state="readonly", width=6, style="Input.TCombobox").pack(side="left", padx=(10, 18))
        ttk.Label(sf, text="Format", style="Field.TLabel").pack(side="left")
        ttk.Combobox(sf, textvariable=self.p2i_format_var, values=["PNG", "JPEG"], state="readonly", width=8, style="Input.TCombobox").pack(side="left", padx=(10, 0))
        f1.columnconfigure(0, weight=1)

        f2 = ttk.Frame(self.convert_dynamic, style="Panel.TFrame")
        ttk.Label(f2, text=_("convert_image_files"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        self.i2p_listbox = tk.Listbox(f2, height=7)
        style_listbox(self.i2p_listbox)
        self.i2p_empty_hint = ListEmptyHint(self.i2p_listbox, _("convert_images_empty_hint"), self.i2p_add_files)
        self.i2p_listbox.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        ib = ttk.Frame(f2, style="Panel.TFrame")
        ib.grid(row=1, column=1, sticky="n", padx=(10, 0), pady=(8, 0))
        ttk.Button(ib, text=_("str_add"), image=styles.icon(Icons.ADD, 12, P.text) or "", compound="left", command=self.i2p_add_files, style="Secondary.TButton").pack(fill="x")
        ttk.Button(ib, text=_("str_up"), image=styles.icon(Icons.UP, 12, P.text_secondary) or "", compound="left", command=lambda: move_listbox_item(self.i2p_listbox, self.i2p_file_list, -1), style="Small.TButton").pack(fill="x", pady=(8, 0))
        ttk.Button(ib, text=_("str_down"), image=styles.icon(Icons.DOWN, 12, P.text_secondary) or "", compound="left", command=lambda: move_listbox_item(self.i2p_listbox, self.i2p_file_list, 1), style="Small.TButton").pack(fill="x", pady=(6, 0))
        ttk.Button(ib, text=_("str_remove"), image=styles.icon(Icons.DELETE, 12, P.text_secondary) or "", compound="left", command=self.i2p_remove_selected, style="Ghost.TButton").pack(fill="x", pady=(8, 0))

        ttk.Label(f2, text=_("str_output_pdf"), style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(14, 0))
        r3 = ttk.Frame(f2, style="Panel.TFrame")
        r3.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.i2p_output_entry = ttk.Entry(r3, textvariable=self.i2p_output_var, style="Input.TEntry")
        self.i2p_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(r3, text=_("str_save"), command=self.choose_i2p_output, style="Secondary.TButton").pack(side="right")

        sz = ttk.Frame(f2, style="Panel.TFrame")
        sz.grid(row=4, column=0, sticky="w", pady=(12, 0))
        ttk.Label(sz, text=_("convert_page_size"), style="Field.TLabel").pack(side="left")
        ttk.Combobox(sz, textvariable=self.i2p_size_var, values=[_("convert_original"), "A4", "Letter"], state="readonly", width=10, style="Input.TCombobox").pack(side="left", padx=(10, 0))
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

        self.footer = ProgressFooter(left, _("convert_btn"), self.start_convert)
        self.footer.pack(fill="x", pady=(24, 0))

        self.feedback = InlineFeedback(left)
        self.feedback.pack(fill="x", pady=(16, 0))
        self.feedback.set_info(_("convert_type"), _("convert_running").format(mode=self.convert_mode_var.get()))
        self.run = ToolRun(self.app_root, self.footer, self.feedback, self.convert_status_var)

    def _file_output_pair(self, frame, input_label, input_var, choose_input, output_label, output_var, choose_output, output_button_text):
        ttk.Label(frame, text=input_label, style="Field.TLabel").grid(row=0, column=0, sticky="w")
        row_in = ttk.Frame(frame, style="Panel.TFrame")
        row_in.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Entry(row_in, textvariable=input_var, style="Input.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(row_in, text=_("str_browse"), command=choose_input, style="Secondary.TButton").pack(side="right")

        ttk.Label(frame, text=output_label, style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(14, 0))
        row_out = ttk.Frame(frame, style="Panel.TFrame")
        row_out.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Entry(row_out, textvariable=output_var, style="Input.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(row_out, text=output_button_text, command=choose_output, style="Secondary.TButton").pack(side="right")
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
            self.p2i_folder_var.set(suggest_output("convert", selected, "pdf2img"))

    def choose_p2i_folder(self):
        selected = filedialog.askdirectory(title=_("convert_dialog_folder"))
        if selected:
            self.p2i_folder_var.set(selected)

    def i2p_add_files(self):
        files = filedialog.askopenfilenames(title=_("convert_dialog_img"), filetypes=[(_("convert_images_label"), "*.png *.jpg *.jpeg *.bmp *.tiff *.gif")])
        for file_path in files:
            self.i2p_file_list.append(file_path)
            self.i2p_listbox.insert(tk.END, os.path.basename(file_path))
            self.i2p_empty_hint.refresh()
        if self.i2p_file_list and not self.i2p_output_var.get().strip():
            self.i2p_output_var.set(suggest_output("convert", self.i2p_file_list[0], "img2pdf"))

    def i2p_remove_selected(self):
        selected = self.i2p_listbox.curselection()
        for index in reversed(selected):
            self.i2p_listbox.delete(index)
            del self.i2p_file_list[index]
        self.i2p_empty_hint.refresh()

    def choose_i2p_output(self):
        selected = filedialog.asksaveasfilename(title=_("convert_dialog_pdf_save"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.i2p_output_var.set(selected)

    def choose_p2w_input(self):
        selected = filedialog.askopenfilename(title=_("convert_dialog_pdf"), filetypes=[("PDF", "*.pdf")])
        if selected:
            self.p2w_input_var.set(selected)
            self.p2w_output_var.set(suggest_output("convert", selected, "pdf2word"))

    def choose_p2w_output(self):
        selected = filedialog.asksaveasfilename(title=_("convert_dialog_word_save"), defaultextension=".docx", filetypes=[("Word", "*.docx")])
        if selected:
            self.p2w_output_var.set(selected)

    def choose_w2p_input(self):
        selected = filedialog.askopenfilename(title=_("convert_dialog_word"), filetypes=[("Word", "*.doc *.docx")])
        if selected:
            self.w2p_input_var.set(selected)
            self.w2p_output_var.set(suggest_output("convert", selected, "word2pdf"))

    def choose_w2p_output(self):
        selected = filedialog.asksaveasfilename(title=_("convert_dialog_pdf_save"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.w2p_output_var.set(selected)

    def choose_ppt2p_input(self):
        selected = filedialog.askopenfilename(title=_("str_file_selection"), filetypes=[("PowerPoint", "*.ppt *.pptx")])
        if selected:
            self.ppt2p_input_var.set(selected)
            self.ppt2p_output_var.set(suggest_output("convert", selected, "ppt2pdf"))

    def choose_ppt2p_output(self):
        selected = filedialog.asksaveasfilename(title=_("convert_dialog_pdf_save"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.ppt2p_output_var.set(selected)

    def choose_excel2p_input(self):
        selected = filedialog.askopenfilename(title=_("str_file_selection"), filetypes=[("Excel", "*.xls *.xlsx")])
        if selected:
            self.excel2p_input_var.set(selected)
            self.excel2p_output_var.set(suggest_output("convert", selected, "excel2pdf"))

    def choose_excel2p_output(self):
        selected = filedialog.asksaveasfilename(title=_("convert_dialog_pdf_save"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.excel2p_output_var.set(selected)

    def choose_p2txt_input(self):
        selected = filedialog.askopenfilename(title=_("convert_dialog_pdf"), filetypes=[("PDF", "*.pdf")])
        if selected:
            self.p2txt_input_var.set(selected)
            self.p2txt_output_var.set(suggest_output("convert", selected, "pdf2txt"))

    def choose_p2txt_output(self):
        selected = filedialog.asksaveasfilename(title=_("adv_dialog_txt_save"), defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if selected:
            self.p2txt_output_var.set(selected)

    def handle_external_drop(self, file_path):
        mode = self.convert_mode_var.get()
        if mode == _("convert_pdf2img") and file_path.lower().endswith(".pdf"):
            self.p2i_input_var.set(file_path)
            self.p2i_folder_var.set(suggest_output("convert", file_path, "pdf2img"))
        elif mode == _("convert_img2pdf") and file_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif")):
            self.i2p_file_list.append(file_path)
            self.i2p_listbox.insert(tk.END, os.path.basename(file_path))
            self.i2p_empty_hint.refresh()
            if not self.i2p_output_var.get().strip():
                self.i2p_output_var.set(suggest_output("convert", file_path, "img2pdf"))
        elif mode == _("convert_pdf2word") and file_path.lower().endswith(".pdf"):
            self.p2w_input_var.set(file_path)
            self.p2w_output_var.set(suggest_output("convert", file_path, "pdf2word"))
        elif mode == _("convert_word2pdf") and file_path.lower().endswith((".doc", ".docx")):
            self.w2p_input_var.set(file_path)
            self.w2p_output_var.set(suggest_output("convert", file_path, "word2pdf"))
        elif mode == _("convert_ppt2pdf") and file_path.lower().endswith((".ppt", ".pptx")):
            self.ppt2p_input_var.set(file_path)
            self.ppt2p_output_var.set(suggest_output("convert", file_path, "ppt2pdf"))
        elif mode == _("convert_excel2pdf") and file_path.lower().endswith((".xls", ".xlsx")):
            self.excel2p_input_var.set(file_path)
            self.excel2p_output_var.set(suggest_output("convert", file_path, "excel2pdf"))
        elif mode == _("convert_pdf2txt") and file_path.lower().endswith(".pdf"):
            self.p2txt_input_var.set(file_path)
            self.p2txt_output_var.set(suggest_output("convert", file_path, "pdf2txt"))
        else:
            # A file that does not suit the selected mode was dropped and
            # silently ignored, which looked like the drop had not worked.
            self.feedback.set_info(
                _("convert_dialog_pdf"),
                _("convert_drop_mismatch").format(name=os.path.basename(file_path)))

    def start_convert(self):
        mode = mode_from_label("convert", self.convert_mode_var.get())
        params = {"mode": mode}
        if mode == "pdf2img":
            params.update(input=self.p2i_input_var.get().strip(), output=self.p2i_folder_var.get().strip(),
                          dpi=self.p2i_dpi_var.get(), fmt=self.p2i_format_var.get())
        elif mode == "img2pdf":
            params.update(images=list(self.i2p_file_list), output=self.i2p_output_var.get().strip(),
                          page_size=self.i2p_size_var.get())
        else:
            source, target = {
                "pdf2word": (self.p2w_input_var, self.p2w_output_var),
                "word2pdf": (self.w2p_input_var, self.w2p_output_var),
                "ppt2pdf": (self.ppt2p_input_var, self.ppt2p_output_var),
                "excel2pdf": (self.excel2p_input_var, self.excel2p_output_var),
                "pdf2txt": (self.p2txt_input_var, self.p2txt_output_var),
            }[mode]
            params.update(input=source.get().strip(), output=target.get().strip())
        self.run.start("convert", params)
