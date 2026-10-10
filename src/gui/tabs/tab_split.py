import os
import tkinter as tk
from tkinter import ttk, filedialog

from src.app.tools import suggest_output
from src.core.common import get_pdf_page_count
from src.core.lang_manager import _
from src.gui.helpers import InlineFeedback, ProgressFooter, ToolLayout, ToolRun, bind_preview, follow_width


class SplitTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root

        self.split_input_var = tk.StringVar()
        self.split_output_var = tk.StringVar()
        self.split_start_var = tk.StringVar(value="1")
        self.split_end_var = tk.StringVar(value="")
        self.split_status_var = tk.StringVar(value=_("str_ready"))
        self.split_page_info_var = tk.StringVar(value="")

        bind_preview(self.app_root, self.split_input_var)
        self.build_ui()

    def build_ui(self):
        self.layout = ToolLayout(self.parent, _("hint_split"))
        left = self.layout.form

        ttk.Label(left, text=_("str_input_pdf"), style="Field.TLabel").pack(anchor="w")
        input_row = ttk.Frame(left, style="Surface.TFrame")
        input_row.pack(fill="x", pady=(8, 0))
        self.split_input_entry = ttk.Entry(input_row, textvariable=self.split_input_var, style="Input.TEntry")
        self.split_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.split_input_button = ttk.Button(input_row, text=_("str_browse"), command=self.choose_split_input_pdf, style="Secondary.TButton")
        self.split_input_button.pack(side="right")

        ttk.Label(left, textvariable=self.split_page_info_var, style="PageInfo.TLabel").pack(anchor="w", pady=(8, 0))

        ttk.Label(left, text=_("str_output_pdf"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        output_row = ttk.Frame(left, style="Surface.TFrame")
        output_row.pack(fill="x", pady=(8, 0))
        self.split_output_entry = ttk.Entry(output_row, textvariable=self.split_output_var, style="Input.TEntry")
        self.split_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.split_output_button = ttk.Button(output_row, text=_("str_save_as"), command=self.choose_split_output_pdf, style="Secondary.TButton")
        self.split_output_button.pack(side="right")
        action_hint = ttk.Label(
            left,
            text=_("output_action_hint").format(action=_("split_btn")),
            style="Hint.TLabel",
            justify="left",
        )
        action_hint.pack(anchor="w", pady=(8, 0))
        follow_width(action_hint, left)

        range_card = ttk.Frame(left, style="PanelCard.TFrame", padding=16)
        range_card.pack(fill="x", pady=(22, 0))
        ttk.Label(range_card, text=_("split_page_range"), style="Section.TLabel").pack(anchor="w")
        grid = ttk.Frame(range_card, style="Panel.TFrame")
        grid.pack(anchor="w", pady=(14, 0))
        ttk.Label(grid, text=_("split_start"), style="Field.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(grid, text=_("split_end"), style="Field.TLabel").grid(row=0, column=2, sticky="w", padx=(20, 0))
        self.split_start_spin = ttk.Spinbox(grid, from_=1, to=99999, textvariable=self.split_start_var, width=10, style="Input.TSpinbox", command=self.update_split_output_name)
        self.split_start_spin.grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(grid, text="-", style="CardTitle.TLabel").grid(row=1, column=1, padx=12, pady=(8, 0))
        self.split_end_spin = ttk.Spinbox(grid, from_=1, to=99999, textvariable=self.split_end_var, width=10, style="Input.TSpinbox", command=self.update_split_output_name)
        self.split_end_spin.grid(row=1, column=2, sticky="w", padx=(20, 0), pady=(8, 0))
        split_hint = ttk.Label(range_card, text=_("split_hint"), style="Hint.TLabel", justify="left")
        split_hint.pack(anchor="w", pady=(12, 0))
        follow_width(split_hint, range_card, 32)

        self.footer = ProgressFooter(left, _("split_btn"), self.start_split)
        self.footer.pack(fill="x", pady=(24, 0))

        self.feedback = InlineFeedback(left)
        self.feedback.pack(fill="x", pady=(16, 0))
        self.feedback.set_info(_("split_page_range"), _("output_action_hint").format(action=_("split_btn")))
        self.run = ToolRun(self.app_root, self.footer, self.feedback, self.split_status_var)

        self.split_start_var.trace_add("write", lambda *_args: self.update_split_output_name())
        self.split_end_var.trace_add("write", lambda *_args: self.update_split_output_name())

    def choose_split_input_pdf(self):
        selected = filedialog.askopenfilename(title=_("split_dialog_input"), filetypes=[("PDF", "*.pdf")])
        if not selected:
            return
        self.split_input_var.set(selected)
        self._refresh_page_info(selected)
        self.update_split_output_name()

    def _refresh_page_info(self, path):
        try:
            total = get_pdf_page_count(path)
            self.split_page_info_var.set(_("split_total_pages").format(count=total))
            self.split_end_var.set(str(total))
            self.split_start_var.set("1")
        except Exception as exc:
            self.split_page_info_var.set(f"{_('split_page_read_err')}{exc}")

    def choose_split_output_pdf(self):
        init = ""
        current = self.split_input_var.get().strip()
        if current:
            try:
                start_page, end_page = int(self.split_start_var.get()), int(self.split_end_var.get())
                init = os.path.basename(suggest_output("split", current, start=start_page, end=end_page))
            except ValueError:
                init = os.path.basename(current)
        selected = filedialog.asksaveasfilename(
            title=_("split_dialog_output"),
            defaultextension=".pdf",
            initialfile=init,
            filetypes=[("PDF", "*.pdf")],
        )
        if selected:
            self.split_output_var.set(selected)

    def update_split_output_name(self):
        current = self.split_input_var.get().strip()
        if not current:
            return
        try:
            start_page, end_page = int(self.split_start_var.get()), int(self.split_end_var.get())
            self.split_output_var.set(suggest_output("split", current, start=start_page, end=end_page))
        except ValueError:
            pass

    def handle_external_drop(self, file_path):
        if file_path.lower().endswith(".pdf"):
            self.split_input_var.set(file_path)
            self._refresh_page_info(file_path)
            self.update_split_output_name()

    def start_split(self):
        self.run.start("split", {
            "input": self.split_input_var.get().strip(),
            "output": self.split_output_var.get().strip(),
            "start": self.split_start_var.get(),
            "end": self.split_end_var.get(),
        })
