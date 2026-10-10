import tkinter as tk
from tkinter import ttk, filedialog

from src.app.tools import mode_from_label, suggest_output
from src.core.lang_manager import _
from src.gui.widgets import SegmentedControl
from src.gui.helpers import InlineFeedback, ProgressFooter, ToolLayout, ToolRun, bind_preview


class SecurityTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        # Changing the operation used to overwrite a path the user picked.
        self._output_chosen = False
        self.mode_var = tk.StringVar(value=_("security_encrypt"))
        self.password_var = tk.StringVar()
        self.confirm_var = tk.StringVar()
        self.watermark_text_var = tk.StringVar(value="GIZLI")
        self.status_var = tk.StringVar(value=_("str_ready"))

        bind_preview(self.app_root, self.input_var)
        self.build_ui()

    def build_ui(self):
        self.layout = ToolLayout(self.parent, _("hint_security"))
        left = self.layout.form

        ttk.Label(left, text=_("str_input_pdf"), style="Field.TLabel").pack(anchor="w")
        input_row = ttk.Frame(left, style="Surface.TFrame")
        input_row.pack(fill="x", pady=(8, 0))
        self.input_entry = ttk.Entry(input_row, textvariable=self.input_var, style="Input.TEntry")
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.input_button = ttk.Button(input_row, text=_("str_browse"), command=self.choose_input_pdf, style="Secondary.TButton")
        self.input_button.pack(side="right")

        ttk.Label(left, text=_("security_op_type"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        self.mode_picker = SegmentedControl(
            left, self.mode_var,
            [_("security_encrypt"), _("security_decrypt"), _("security_watermark")],
            command=self.switch_mode)
        self.mode_picker.pack(fill="x", pady=(8, 0))

        self.dynamic_frame = ttk.Frame(left, style="PanelCard.TFrame", padding=16)
        self.dynamic_frame.pack(fill="x", pady=(18, 0))

        self.password_frame = ttk.Frame(self.dynamic_frame, style="Panel.TFrame")
        ttk.Label(self.password_frame, text=_("security_password"), style="Field.TLabel").pack(anchor="w")
        self.password_entry = ttk.Entry(self.password_frame, textvariable=self.password_var, show="*", style="Input.TEntry")
        self.password_entry.pack(fill="x", pady=(8, 0))

        # Only shown when encrypting; removing a password needs no confirmation.
        self.confirm_row = ttk.Frame(self.password_frame, style="Panel.TFrame")
        ttk.Label(self.confirm_row, text=_("security_password_confirm"), style="Field.TLabel").pack(anchor="w", pady=(12, 0))
        self.confirm_entry = ttk.Entry(self.confirm_row, textvariable=self.confirm_var, show="*", style="Input.TEntry")
        self.confirm_entry.pack(fill="x", pady=(8, 0))

        self.watermark_frame = ttk.Frame(self.dynamic_frame, style="Panel.TFrame")
        ttk.Label(self.watermark_frame, text=_("security_watermark_text"), style="Field.TLabel").pack(anchor="w")
        self.watermark_entry = ttk.Entry(self.watermark_frame, textvariable=self.watermark_text_var, style="Input.TEntry")
        self.watermark_entry.pack(fill="x", pady=(8, 0))

        self.frames = {
            _("security_encrypt"): self.password_frame,
            _("security_decrypt"): self.password_frame,
            _("security_watermark"): self.watermark_frame,
        }
        self.switch_mode()

        ttk.Label(left, text=_("str_output_pdf"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        output_row = ttk.Frame(left, style="Surface.TFrame")
        output_row.pack(fill="x", pady=(8, 0))
        self.output_entry = ttk.Entry(output_row, textvariable=self.output_var, style="Input.TEntry")
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.output_button = ttk.Button(output_row, text=_("str_save_as"), command=self.choose_output_pdf, style="Secondary.TButton")
        self.output_button.pack(side="right")

        self.footer = ProgressFooter(left, _("str_apply"), self.start_action)
        self.footer.pack(fill="x", pady=(24, 0))

        self.feedback = InlineFeedback(left)
        self.feedback.pack(fill="x", pady=(16, 0))
        self.feedback.set_info(_("security_op_type"), _("security_watermark_text"))
        self.run = ToolRun(self.app_root, self.footer, self.feedback, self.status_var)

    def switch_mode(self):
        for frame in self.frames.values():
            frame.pack_forget()
        current = self.mode_var.get()
        if current in self.frames:
            self.frames[current].pack(fill="x", expand=True)
        if current == _("security_encrypt"):
            self.confirm_row.pack(fill="x")
        else:
            self.confirm_row.pack_forget()
        if self.input_var.get().strip():
            self._set_input(self.input_var.get().strip())

    def choose_input_pdf(self):
        selected = filedialog.askopenfilename(title=_("security_dialog_input"), filetypes=[("PDF", "*.pdf")])
        if selected:
            self._set_input(selected)

    def _set_input(self, path):
        self.input_var.set(path)
        if self._output_chosen:
            return
        mode = mode_from_label("security", self.mode_var.get())
        self.output_var.set(suggest_output("security", path, mode))

    def choose_output_pdf(self):
        selected = filedialog.asksaveasfilename(title=_("security_dialog_output"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.output_var.set(selected)
            self._output_chosen = True

    def handle_external_drop(self, file_path):
        if file_path.lower().endswith(".pdf"):
            self._set_input(file_path)

    def start_action(self):
        self.run.start("security", {
            "input": self.input_var.get().strip(),
            "output": self.output_var.get().strip(),
            "mode": mode_from_label("security", self.mode_var.get()),
            "password": self.password_var.get(),
            "confirm": self.confirm_var.get(),
            "watermark_text": self.watermark_text_var.get().strip(),
        }, ask_overwrite=not self._output_chosen)
