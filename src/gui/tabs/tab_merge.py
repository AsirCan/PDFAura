import os
import tkinter as tk
from tkinter import ttk, filedialog

from src.app.tools import suggest_output
from src.core.lang_manager import _
from src.gui import styles
from src.gui.styles import P
from src.gui.theme.images import Icons
from src.gui.helpers import (InlineFeedback, ListEmptyHint, ProgressFooter, ToolLayout, ToolRun,
                             notify_preview, style_listbox)


class MergeTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root

        self.merge_file_list = []
        self.merge_output_var = tk.StringVar()
        self.merge_status_var = tk.StringVar(value=_("str_ready"))
        self.build_ui()

    def build_ui(self):
        self.layout = ToolLayout(self.parent, _("hint_merge"))
        left = self.layout.form

        ttk.Label(left, text=_("merge_pdf_files"), style="Section.TLabel").pack(anchor="w")
        top_row = ttk.Frame(left, style="Surface.TFrame")
        top_row.pack(fill="both", expand=True, pady=(14, 0))

        self.merge_listbox = tk.Listbox(top_row, height=10)
        style_listbox(self.merge_listbox)
        self.merge_listbox.pack(side="left", fill="both", expand=True)
        self.merge_listbox.bind("<<ListboxSelect>>", self.on_selection_changed)
        self.empty_hint = ListEmptyHint(self.merge_listbox, _("merge_empty_hint"), self.merge_add_files)

        controls = ttk.Frame(top_row, style="Surface.TFrame")
        controls.pack(side="left", fill="y", padx=(14, 0))
        self.merge_add_btn = ttk.Button(controls, text=_("str_add"), image=styles.icon(Icons.ADD, 12, P.text) or "", compound="left", command=self.merge_add_files, style="Secondary.TButton")
        self.merge_add_btn.pack(fill="x")
        self.merge_remove_btn = ttk.Button(controls, text=_("str_remove"), image=styles.icon(Icons.DELETE, 12, P.text_secondary) or "", compound="left", command=self.merge_remove_selected, style="Ghost.TButton")
        self.merge_remove_btn.pack(fill="x", pady=(8, 0))
        self.merge_up_btn = ttk.Button(controls, text=_("str_up"), image=styles.icon(Icons.UP, 12, P.text_secondary) or "", compound="left", command=self.merge_move_up, style="Small.TButton")
        self.merge_up_btn.pack(fill="x", pady=(8, 0))
        self.merge_down_btn = ttk.Button(controls, text=_("str_down"), image=styles.icon(Icons.DOWN, 12, P.text_secondary) or "", compound="left", command=self.merge_move_down, style="Small.TButton")
        self.merge_down_btn.pack(fill="x", pady=(8, 0))

        ttk.Label(left, text=_("str_output_pdf"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        output_row = ttk.Frame(left, style="Surface.TFrame")
        output_row.pack(fill="x", pady=(8, 0))
        self.merge_output_entry = ttk.Entry(output_row, textvariable=self.merge_output_var, style="Input.TEntry")
        self.merge_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.merge_output_button = ttk.Button(output_row, text=_("str_save_as"), command=self.choose_merge_output, style="Secondary.TButton")
        self.merge_output_button.pack(side="right")

        self.footer = ProgressFooter(left, _("merge_btn"), self.start_merge)
        self.footer.pack(fill="x", pady=(24, 0))

        self.feedback = InlineFeedback(left)
        self.feedback.pack(fill="x", pady=(16, 0))
        self.feedback.set_info(_("merge_pdf_files"), _("str_drag_drop_hint"))
        self.run = ToolRun(self.app_root, self.footer, self.feedback, self.merge_status_var)

    def merge_add_files(self):
        files = filedialog.askopenfilenames(title=_("merge_dialog_input"), filetypes=[("PDF", "*.pdf")])
        for file_path in files:
            self._append_file(file_path)

    def _append_file(self, file_path):
        if not file_path.lower().endswith(".pdf"):
            return
        self.merge_file_list.append(file_path)
        self.merge_listbox.insert(tk.END, os.path.basename(file_path))
        self.empty_hint.refresh()
        if len(self.merge_file_list) == 1:
            notify_preview(self.app_root, file_path)
        if self.merge_file_list and not self.merge_output_var.get().strip():
            self.merge_output_var.set(suggest_output("merge", self.merge_file_list[0]))

    def merge_remove_selected(self):
        selected = self.merge_listbox.curselection()
        for index in reversed(selected):
            self.merge_listbox.delete(index)
            del self.merge_file_list[index]
        self.empty_hint.refresh()
        if self.merge_file_list:
            notify_preview(self.app_root, self.merge_file_list[0])

    def merge_move_up(self):
        selected = self.merge_listbox.curselection()
        if not selected or selected[0] == 0:
            return
        index = selected[0]
        self.merge_file_list[index - 1], self.merge_file_list[index] = self.merge_file_list[index], self.merge_file_list[index - 1]
        label = self.merge_listbox.get(index)
        self.merge_listbox.delete(index)
        self.merge_listbox.insert(index - 1, label)
        self.merge_listbox.selection_set(index - 1)
        notify_preview(self.app_root, self.merge_file_list[index - 1])

    def merge_move_down(self):
        selected = self.merge_listbox.curselection()
        if not selected or selected[0] >= len(self.merge_file_list) - 1:
            return
        index = selected[0]
        self.merge_file_list[index], self.merge_file_list[index + 1] = self.merge_file_list[index + 1], self.merge_file_list[index]
        label = self.merge_listbox.get(index)
        self.merge_listbox.delete(index)
        self.merge_listbox.insert(index + 1, label)
        self.merge_listbox.selection_set(index + 1)
        notify_preview(self.app_root, self.merge_file_list[index + 1])

    def on_selection_changed(self, _event=None):
        selected = self.merge_listbox.curselection()
        if selected:
            notify_preview(self.app_root, self.merge_file_list[selected[0]])

    def choose_merge_output(self):
        selected = filedialog.asksaveasfilename(title=_("merge_dialog_output"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.merge_output_var.set(selected)

    def handle_external_drop(self, file_path):
        self._append_file(file_path)

    def start_merge(self):
        self.run.start("merge", {"files": list(self.merge_file_list),
                                 "output": self.merge_output_var.get().strip()})
