import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from src.core.common import get_pdf_page_count
from src.core.lang_manager import _
from src.core.merge import merge_pdfs
from src.core.task_manager import TaskContext, CancelledError
from src.gui.helpers import InlineFeedback, ProgressFooter, notify_preview, quick_error
from src.gui.styles import FIELD_COLOR, MERGE_ACCENT, TEXT_COLOR
from src.utils.file_helper import format_size_mb


class MergeTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        self._task_ctx = None

        self.merge_file_list = []
        self.merge_output_var = tk.StringVar()
        self.merge_status_var = tk.StringVar(value=_("str_ready"))
        self.build_ui()

    def build_ui(self):
        shell = ttk.Frame(self.parent, style="App.TFrame")
        shell.pack(fill="both", expand=True)

        hero = ttk.Frame(shell, style="Hero.TFrame", padding=22)
        hero.pack(fill="x", pady=(0, 18))
        ttk.Label(hero, text=_("txt_merge"), style="HeroEyebrow.TLabel").pack(anchor="w")
        ttk.Label(hero, text=_("merge_btn"), style="HeroTitle.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(hero, text=_("merge_result").format(count=2, pages=12, size=1.4, output="...").split("\n")[0], style="HeroBody.TLabel", wraplength=780, justify="left").pack(anchor="w", pady=(8, 0))

        body = ttk.Frame(shell, style="App.TFrame")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, style="Surface.TFrame", padding=22)
        left.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text=_("merge_pdf_files"), style="Section.TLabel").pack(anchor="w")
        top_row = ttk.Frame(left, style="Surface.TFrame")
        top_row.pack(fill="both", expand=True, pady=(14, 0))

        self.merge_listbox = tk.Listbox(
            top_row,
            bg=FIELD_COLOR,
            fg=TEXT_COLOR,
            selectbackground=MERGE_ACCENT,
            selectforeground=TEXT_COLOR,
            font=("Segoe UI", 10),
            height=10,
            borderwidth=1,
            relief="solid",
            highlightthickness=0,
            activestyle="none",
        )
        self.merge_listbox.pack(side="left", fill="both", expand=True)
        self.merge_listbox.bind("<<ListboxSelect>>", self.on_selection_changed)

        controls = ttk.Frame(top_row, style="Surface.TFrame")
        controls.pack(side="left", fill="y", padx=(14, 0))
        self.merge_add_btn = ttk.Button(controls, text=_("str_add"), command=self.merge_add_files, style="Secondary.TButton")
        self.merge_add_btn.pack(fill="x")
        self.merge_remove_btn = ttk.Button(controls, text=_("str_remove"), command=self.merge_remove_selected, style="Ghost.TButton")
        self.merge_remove_btn.pack(fill="x", pady=(8, 0))
        self.merge_up_btn = ttk.Button(controls, text=_("str_up"), command=self.merge_move_up, style="Small.TButton")
        self.merge_up_btn.pack(fill="x", pady=(8, 0))
        self.merge_down_btn = ttk.Button(controls, text=_("str_down"), command=self.merge_move_down, style="Small.TButton")
        self.merge_down_btn.pack(fill="x", pady=(8, 0))

        ttk.Label(left, text=_("str_output_pdf"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        output_row = ttk.Frame(left, style="Surface.TFrame")
        output_row.pack(fill="x", pady=(8, 0))
        self.merge_output_entry = ttk.Entry(output_row, textvariable=self.merge_output_var, style="Dark.TEntry")
        self.merge_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.merge_output_button = ttk.Button(output_row, text=_("str_save_as"), command=self.choose_merge_output, style="Ghost.TButton")
        self.merge_output_button.pack(side="right")

        self.footer = ProgressFooter(left, _("merge_btn"), self.start_merge, button_style="Merge.TButton", progress_style="Merge.Horizontal.TProgressbar")
        self.footer.pack(fill="x", pady=(22, 0))

        right = ttk.Frame(body, style="App.TFrame")
        right.pack(side="left", fill="y", padx=(18, 0))
        self.feedback = InlineFeedback(right)
        self.feedback.pack(fill="x")
        self.feedback.set_info(_("merge_pdf_files"), _("str_drag_drop_hint"))

    def merge_add_files(self):
        files = filedialog.askopenfilenames(title=_("merge_dialog_input"), filetypes=[("PDF", "*.pdf")])
        for file_path in files:
            self._append_file(file_path)

    def _append_file(self, file_path):
        if not file_path.lower().endswith(".pdf"):
            return
        self.merge_file_list.append(file_path)
        self.merge_listbox.insert(tk.END, os.path.basename(file_path))
        if len(self.merge_file_list) == 1:
            notify_preview(self.app_root, file_path)
        if self.merge_file_list and not self.merge_output_var.get().strip():
            base = os.path.splitext(self.merge_file_list[0])[0]
            self.merge_output_var.set(f"{base}_birleşik.pdf")

    def merge_remove_selected(self):
        selected = self.merge_listbox.curselection()
        for index in reversed(selected):
            self.merge_listbox.delete(index)
            del self.merge_file_list[index]
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

    def _cancel_task(self):
        if self._task_ctx:
            self._task_ctx.cancel()

    def start_merge(self):
        if len(self.merge_file_list) < 2:
            quick_error(_("err_min_2_pdf"), self.footer.action_button, None, self.merge_status_var, self.feedback)
            return
        output_pdf = self.merge_output_var.get().strip()
        if not output_pdf:
            quick_error(_("err_set_output"), self.footer.action_button, None, self.merge_status_var, self.feedback)
            return

        def _on_progress(current, total, message=""):
            self.app_root.after(0, self.footer.update_progress, current, total, message)

        self._task_ctx = TaskContext(progress_callback=_on_progress)
        busy_text = _("merge_running").format(count=len(self.merge_file_list))
        self.footer.start_busy(cancel_callback=self._cancel_task)
        self.feedback.set_busy(busy_text)
        self.merge_status_var.set(busy_text)
        threading.Thread(target=self._run_merge, args=(list(self.merge_file_list), output_pdf), daemon=True).start()

    def _run_merge(self, pdf_list, output_pdf):
        try:
            merge_pdfs(pdf_list, output_pdf, ctx=self._task_ctx)
            if not os.path.isfile(output_pdf):
                raise RuntimeError(_("err_output_not_created"))
            size = format_size_mb(output_pdf)
            total_pages = get_pdf_page_count(output_pdf)
            message = _("merge_result").format(count=len(pdf_list), pages=total_pages, size=size, output=output_pdf)
            self.app_root.after(0, self._on_done, message, output_pdf)
        except CancelledError:
            self.app_root.after(0, self._on_cancelled)
        except Exception as exc:
            self.app_root.after(0, self._on_error, str(exc))

    def _on_done(self, message, output_pdf):
        self.footer.finish_success()
        self.merge_status_var.set(_("merge_done"))
        self.feedback.set_success(_("merge_done"), message, output_pdf)

    def _on_cancelled(self):
        self.footer.stop_busy()
        self.merge_status_var.set(_("perf_cancelled"))
        self.feedback.set_cancelled()

    def _on_error(self, error_msg):
        self.footer.stop_busy()
        self.merge_status_var.set(_("merge_fail"))
        self.feedback.set_error(_("merge_fail"), error_msg)
