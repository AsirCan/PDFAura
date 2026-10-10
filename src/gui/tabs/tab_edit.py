import tkinter as tk
from tkinter import ttk, filedialog

from src.app.tools import mode_from_label, suggest_output
from src.core.common import get_pdf_page_count
from src.core.lang_manager import _
from src.gui.widgets import SegmentedControl
from src.gui.helpers import InlineFeedback, ProgressFooter, ToolLayout, ToolRun, bind_preview, follow_width


class EditTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root

        self.edit_input_var = tk.StringVar()
        self.edit_output_var = tk.StringVar()
        self.edit_mode_var = tk.StringVar(value=_("edit_mode_delete"))
        self.edit_delete_pages_var = tk.StringVar()
        self.edit_rotate_pages_var = tk.StringVar()
        self.edit_angle_var = tk.StringVar(value="90")
        self.edit_order_var = tk.StringVar()
        self.edit_page_info_var = tk.StringVar(value="")
        self.edit_status_var = tk.StringVar(value=_("str_ready"))

        bind_preview(self.app_root, self.edit_input_var)
        self.build_ui()

    def build_ui(self):
        self.layout = ToolLayout(self.parent, _("hint_edit"))
        left = self.layout.form

        ttk.Label(left, text=_("str_input_pdf"), style="Field.TLabel").pack(anchor="w")
        input_row = ttk.Frame(left, style="Surface.TFrame")
        input_row.pack(fill="x", pady=(8, 0))
        self.edit_input_entry = ttk.Entry(input_row, textvariable=self.edit_input_var, style="Input.TEntry")
        self.edit_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.edit_input_button = ttk.Button(input_row, text=_("str_browse"), command=self.choose_edit_input_pdf, style="Secondary.TButton")
        self.edit_input_button.pack(side="right")
        ttk.Label(left, textvariable=self.edit_page_info_var, style="PageInfo.TLabel").pack(anchor="w", pady=(8, 0))

        ttk.Label(left, text=_("edit_operation"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        self.edit_mode_picker = SegmentedControl(
            left, self.edit_mode_var,
            [_("edit_mode_delete"), _("edit_mode_rotate"), _("edit_mode_reorder")],
            command=self.switch_edit_mode)
        self.edit_mode_picker.pack(fill="x", pady=(8, 0))

        self.edit_dynamic = ttk.Frame(left, style="PanelCard.TFrame", padding=16)
        self.edit_dynamic.pack(fill="x", pady=(18, 0))

        self.edit_delete_frame = ttk.Frame(self.edit_dynamic, style="Panel.TFrame")
        ttk.Label(self.edit_delete_frame, text=_("edit_pages_to_delete"), style="Field.TLabel").pack(anchor="w")
        ttk.Entry(self.edit_delete_frame, textvariable=self.edit_delete_pages_var, style="Input.TEntry").pack(fill="x", pady=(8, 0))
        delete_hint = ttk.Label(self.edit_delete_frame, text=_("edit_delete_hint"), style="Hint.TLabel", justify="left")
        delete_hint.pack(anchor="w", pady=(8, 0))
        follow_width(delete_hint, self.edit_dynamic, 32)

        self.edit_rotate_frame = ttk.Frame(self.edit_dynamic, style="Panel.TFrame")
        ttk.Label(self.edit_rotate_frame, text=_("edit_pages_to_rotate"), style="Field.TLabel").pack(anchor="w")
        ttk.Entry(self.edit_rotate_frame, textvariable=self.edit_rotate_pages_var, style="Input.TEntry").pack(fill="x", pady=(8, 0))
        ttk.Label(self.edit_rotate_frame, text=_("edit_rotate_hint"), style="Hint.TLabel").pack(anchor="w", pady=(8, 0))
        angle_row = ttk.Frame(self.edit_rotate_frame, style="Panel.TFrame")
        angle_row.pack(anchor="w", pady=(10, 0))
        ttk.Label(angle_row, text=_("edit_angle"), style="Field.TLabel").pack(side="left")
        ttk.Combobox(angle_row, textvariable=self.edit_angle_var, values=["90", "180", "270"], state="readonly", width=8, style="Input.TCombobox").pack(side="left", padx=(12, 0))
        ttk.Label(angle_row, text=_("edit_angle_hint"), style="Hint.TLabel").pack(side="left", padx=(12, 0))

        self.edit_reorder_frame = ttk.Frame(self.edit_dynamic, style="Panel.TFrame")
        ttk.Label(self.edit_reorder_frame, text=_("edit_new_order"), style="Field.TLabel").pack(anchor="w")
        ttk.Entry(self.edit_reorder_frame, textvariable=self.edit_order_var, style="Input.TEntry").pack(fill="x", pady=(8, 0))
        order_hint = ttk.Label(self.edit_reorder_frame, text=_("edit_order_hint"), style="Hint.TLabel", justify="left")
        order_hint.pack(anchor="w", pady=(8, 0))
        follow_width(order_hint, self.edit_dynamic, 32)

        self.edit_frames = {
            _("edit_mode_delete"): self.edit_delete_frame,
            _("edit_mode_rotate"): self.edit_rotate_frame,
            _("edit_mode_reorder"): self.edit_reorder_frame,
        }
        self.switch_edit_mode()

        ttk.Label(left, text=_("str_output_pdf"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        output_row = ttk.Frame(left, style="Surface.TFrame")
        output_row.pack(fill="x", pady=(8, 0))
        self.edit_output_entry = ttk.Entry(output_row, textvariable=self.edit_output_var, style="Input.TEntry")
        self.edit_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.edit_output_button = ttk.Button(output_row, text=_("str_save_as"), command=self.choose_edit_output_pdf, style="Secondary.TButton")
        self.edit_output_button.pack(side="right")

        self.footer = ProgressFooter(left, _("str_apply"), self.start_edit)
        self.footer.pack(fill="x", pady=(24, 0))

        self.feedback = InlineFeedback(left)
        self.feedback.pack(fill="x", pady=(16, 0))
        self.feedback.set_info(_("edit_operation"), _("edit_delete_hint"))
        self.run = ToolRun(self.app_root, self.footer, self.feedback, self.edit_status_var)

    def switch_edit_mode(self):
        for frame in self.edit_frames.values():
            frame.pack_forget()
        current = self.edit_mode_var.get()
        if current in self.edit_frames:
            self.edit_frames[current].pack(fill="x", expand=True)

    def choose_edit_input_pdf(self):
        selected = filedialog.askopenfilename(title=_("edit_dialog_input"), filetypes=[("PDF", "*.pdf")])
        if not selected:
            return
        self.edit_input_var.set(selected)
        try:
            total = get_pdf_page_count(selected)
            self.edit_page_info_var.set(_("edit_total_pages").format(count=total))
        except Exception as exc:
            self.edit_page_info_var.set(f"{_('str_error')}: {exc}")
        self.edit_output_var.set(suggest_output("edit", selected))

    def choose_edit_output_pdf(self):
        selected = filedialog.asksaveasfilename(title=_("edit_dialog_output"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.edit_output_var.set(selected)

    def handle_external_drop(self, file_path):
        if file_path.lower().endswith(".pdf"):
            self.edit_input_var.set(file_path)
            try:
                total = get_pdf_page_count(file_path)
                self.edit_page_info_var.set(_("edit_total_pages").format(count=total))
            except Exception as exc:
                self.edit_page_info_var.set(f"{_('str_error')}: {exc}")
            self.edit_output_var.set(suggest_output("edit", file_path))

    def start_edit(self):
        # Every field is read here, on the main thread; the job gets values.
        self.run.start("edit", {
            "input": self.edit_input_var.get().strip(),
            "output": self.edit_output_var.get().strip(),
            "mode": mode_from_label("edit", self.edit_mode_var.get()),
            "delete_pages": self.edit_delete_pages_var.get().strip(),
            "rotate_pages": self.edit_rotate_pages_var.get().strip(),
            "angle": self.edit_angle_var.get(),
            "order": self.edit_order_var.get().strip(),
        })
