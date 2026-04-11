import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from src.core.merge import merge_pdfs
from src.core.common import get_pdf_page_count
from src.utils.file_helper import format_size_mb
from src.gui.helpers import set_busy, operation_done
from src.core.lang_manager import _

class MergeTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        
        self.merge_file_list = []
        self.merge_output_var = tk.StringVar()
        self.merge_status_var = tk.StringVar(value=_("str_ready"))
        
        self.build_ui()

    def build_ui(self):
        c = ttk.Frame(self.parent, padding=20, style="Card.TFrame")
        c.pack(fill="both", expand=True, pady=(12, 0))

        ttk.Label(c, text=_("merge_pdf_files"), style="Section.TLabel").grid(row=0, column=0, sticky="w", columnspan=2)

        from src.gui.styles import FIELD_COLOR, TEXT_COLOR, MERGE_ACCENT
        self.merge_listbox = tk.Listbox(c, bg=FIELD_COLOR, fg=TEXT_COLOR, selectbackground=MERGE_ACCENT,
                                         selectforeground=TEXT_COLOR, font=("Segoe UI", 10), height=7,
                                         borderwidth=1, relief="solid", highlightthickness=0, activestyle="none")
        self.merge_listbox.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(12, 0))

        btn_frame = ttk.Frame(c, style="Card.TFrame")
        btn_frame.grid(row=1, column=1, sticky="n", pady=(12, 0))
        self.merge_add_btn = ttk.Button(btn_frame, text=_("str_add"), command=self.merge_add_files, style="Secondary.TButton")
        self.merge_add_btn.pack(fill="x", pady=(0, 6))
        self.merge_remove_btn = ttk.Button(btn_frame, text=_("str_remove"), command=self.merge_remove_selected, style="Secondary.TButton")
        self.merge_remove_btn.pack(fill="x", pady=(0, 6))
        self.merge_up_btn = ttk.Button(btn_frame, text=_("str_up"), command=self.merge_move_up, style="Small.TButton")
        self.merge_up_btn.pack(fill="x", pady=(0, 6))
        self.merge_down_btn = ttk.Button(btn_frame, text=_("str_down"), command=self.merge_move_down, style="Small.TButton")
        self.merge_down_btn.pack(fill="x")

        ttk.Label(c, text=_("str_output_pdf"), style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(16, 8))
        self.merge_output_entry = ttk.Entry(c, textvariable=self.merge_output_var, width=64, style="Dark.TEntry")
        self.merge_output_entry.grid(row=3, column=0, sticky="ew", padx=(0, 10))
        self.merge_output_button = ttk.Button(c, text=_("str_save_as"), command=self.choose_merge_output, style="Secondary.TButton")
        self.merge_output_button.grid(row=3, column=1, sticky="ew")

        self.merge_button = ttk.Button(c, text=_("merge_btn"), command=self.start_merge, style="Merge.TButton")
        self.merge_button.grid(row=4, column=0, sticky="w", pady=(22, 12))
        self.merge_progress_bar = ttk.Progressbar(c, mode="indeterminate", length=520, style="Merge.Horizontal.TProgressbar")
        self.merge_progress_bar.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(2, 12))
        self.merge_status_label = ttk.Label(c, textvariable=self.merge_status_var, style="MergeStatus.TLabel")
        self.merge_status_label.grid(row=6, column=0, columnspan=2, sticky="w")
        c.columnconfigure(0, weight=1)
        c.rowconfigure(1, weight=1)

    def merge_add_files(self):
        files = filedialog.askopenfilenames(title=_("merge_dialog_input"), filetypes=[("PDF", "*.pdf")])
        for f in files:
            self.merge_file_list.append(f)
            self.merge_listbox.insert(tk.END, os.path.basename(f))
        if self.merge_file_list and not self.merge_output_var.get().strip():
            base = os.path.splitext(self.merge_file_list[0])[0]
            self.merge_output_var.set(f"{base}_birlesik.pdf")

    def merge_remove_selected(self):
        sel = self.merge_listbox.curselection()
        for i in reversed(sel):
            self.merge_listbox.delete(i)
            del self.merge_file_list[i]

    def merge_move_up(self):
        sel = self.merge_listbox.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        self.merge_file_list[i - 1], self.merge_file_list[i] = self.merge_file_list[i], self.merge_file_list[i - 1]
        text = self.merge_listbox.get(i)
        self.merge_listbox.delete(i)
        self.merge_listbox.insert(i - 1, text)
        self.merge_listbox.selection_set(i - 1)

    def merge_move_down(self):
        sel = self.merge_listbox.curselection()
        if not sel or sel[0] >= len(self.merge_file_list) - 1:
            return
        i = sel[0]
        self.merge_file_list[i], self.merge_file_list[i + 1] = self.merge_file_list[i + 1], self.merge_file_list[i]
        text = self.merge_listbox.get(i)
        self.merge_listbox.delete(i)
        self.merge_listbox.insert(i + 1, text)
        self.merge_listbox.selection_set(i + 1)

    def choose_merge_output(self):
        f = filedialog.asksaveasfilename(title=_("merge_dialog_output"), defaultextension=".pdf",
                                          filetypes=[("PDF", "*.pdf")])
        if f:
            self.merge_output_var.set(f)

    def start_merge(self):
        if len(self.merge_file_list) < 2:
            messagebox.showerror(_("str_error"), _("err_min_2_pdf"))
            return
        output_pdf = self.merge_output_var.get().strip()
        if not output_pdf:
            messagebox.showerror(_("str_error"), _("err_set_output"))
            return
        set_busy(self.merge_button, self.merge_progress_bar, True)
        self.merge_status_var.set(_("merge_running").format(count=len(self.merge_file_list)))
        threading.Thread(target=self._run_merge, args=(list(self.merge_file_list), output_pdf), daemon=True).start()

    def _run_merge(self, pdf_list, output_pdf):
        try:
            merge_pdfs(pdf_list, output_pdf)
            if not os.path.isfile(output_pdf):
                raise RuntimeError(_("err_output_not_created"))
            size = format_size_mb(output_pdf)
            total_pages = get_pdf_page_count(output_pdf)
            msg = _("merge_result").format(count=len(pdf_list), pages=total_pages, size=size, output=output_pdf)
            self.app_root.after(0, operation_done, self.app_root, self.merge_button, self.merge_progress_bar,
                            self.merge_status_var, _("merge_done"), msg, None)
        except Exception as exc:
            self.app_root.after(0, operation_done, self.app_root, self.merge_button, self.merge_progress_bar,
                            self.merge_status_var, _("merge_fail"), None, str(exc))
