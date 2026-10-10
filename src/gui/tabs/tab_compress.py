import os
import tkinter as tk
from tkinter import ttk, filedialog

from src.app.tools import suggest_output
from src.core.compress import VALID_QUALITIES
from src.core.lang_manager import _
from src.gui.helpers import InlineFeedback, ProgressFooter, ToolLayout, ToolRun, bind_preview


class CompressTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        # A suggested path follows the input; one the user picked does not.
        self._output_chosen = False
        self.quality_var = tk.StringVar(value=_("quality_ebook"))
        self.status_var = tk.StringVar(value=_("str_ready"))

        bind_preview(self.app_root, self.input_var)
        self.build_ui()

    def build_ui(self):
        self.layout = ToolLayout(self.parent, _("hint_compress"))
        left = self.layout.form

        ttk.Label(left, text=_("str_file_selection"), style="Section.TLabel").pack(anchor="w")
        ttk.Label(left, text=_("str_input_pdf"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        input_row = ttk.Frame(left, style="Surface.TFrame")
        input_row.pack(fill="x", pady=(8, 0))
        self.input_entry = ttk.Entry(input_row, textvariable=self.input_var, style="Input.TEntry")
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.input_button = ttk.Button(input_row, text=_("str_browse"), command=self.choose_input_pdf, style="Secondary.TButton")
        self.input_button.pack(side="right")

        ttk.Label(left, text=_("str_output_pdf"), style="Field.TLabel").pack(anchor="w", pady=(16, 0))
        output_row = ttk.Frame(left, style="Surface.TFrame")
        output_row.pack(fill="x", pady=(8, 0))
        self.output_entry = ttk.Entry(output_row, textvariable=self.output_var, style="Input.TEntry")
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.output_button = ttk.Button(output_row, text=_("str_save_as"), command=self.choose_output_pdf, style="Secondary.TButton")
        self.output_button.pack(side="right")

        settings = ttk.Frame(left, style="PanelCard.TFrame", padding=16)
        settings.pack(fill="x", pady=(22, 0))
        ttk.Label(settings, text=_("compress_settings"), style="Section.TLabel").pack(anchor="w")
        ttk.Label(settings, text=_("compress_quality"), style="Field.TLabel").pack(anchor="w", pady=(12, 2))
        # Bare "screen/ebook/printer/prepress" said nothing about what they do.
        self._quality_labels = {q: _(f"quality_{q}") for q in VALID_QUALITIES}
        self._quality_by_label = {v: k for k, v in self._quality_labels.items()}
        # All four profiles in view: the choice is the whole point of the tool.
        self.quality_buttons = []
        for label in self._quality_labels.values():
            button = ttk.Radiobutton(settings, text=label, value=label, variable=self.quality_var,
                                     style="Flat.TRadiobutton")
            button.pack(anchor="w", pady=(6, 0))
            self.quality_buttons.append(button)
        ttk.Label(settings, text=_("compress_quality_hint"), style="Hint.TLabel", justify="left").pack(anchor="w", pady=(10, 0))

        self.footer = ProgressFooter(left, _("compress_btn"), self.start_compression)
        self.footer.pack(fill="x", pady=(24, 0))

        self.feedback = InlineFeedback(left)
        self.feedback.pack(fill="x", pady=(16, 0))
        self.feedback.set_info(_("compress_settings"), _("compress_quality_hint"))
        self.run = ToolRun(self.app_root, self.footer, self.feedback, self.status_var)

    def choose_input_pdf(self):
        selected = filedialog.askopenfilename(title=_("compress_dialog_input"), filetypes=[("PDF", "*.pdf")])
        if selected:
            self.input_var.set(selected)
            self._refresh_suggestion(selected)

    def choose_output_pdf(self):
        init = ""
        current = self.input_var.get().strip()
        if current:
            init = os.path.basename(suggest_output("compress", current))
        selected = filedialog.asksaveasfilename(
            title=_("compress_dialog_output"),
            defaultextension=".pdf",
            initialfile=init,
            filetypes=[("PDF", "*.pdf")],
        )
        if selected:
            self.output_var.set(selected)
            self._output_chosen = True

    def _refresh_suggestion(self, input_path):
        """Follow the input unless the user picked the output themselves.

        The suggestion used to be set only when the box was empty, so
        selecting a second file left the first file's output path in place
        and the new result overwrote it.
        """
        if not self._output_chosen:
            self.output_var.set(suggest_output("compress", input_path))

    def handle_external_drop(self, file_path):
        if file_path.lower().endswith(".pdf"):
            self.input_var.set(file_path)
            self._refresh_suggestion(file_path)

    def start_compression(self):
        # The radio buttons show a descriptive label; map it back to the preset.
        label = self.quality_var.get().strip()
        self.run.start("compress", {
            "input": self.input_var.get().strip(),
            "output": self.output_var.get().strip(),
            "quality": self._quality_by_label.get(label, label.lower()),
        }, ask_overwrite=not self._output_chosen)
