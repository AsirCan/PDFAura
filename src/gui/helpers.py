import os
import tkinter as tk
from tkinter import ttk

from src.core.lang_manager import _


def notify_preview(root, path):
    if hasattr(root, "pdf_aura_set_preview"):
        root.pdf_aura_set_preview(path)


def bind_preview(root, *variables):
    for variable in variables:
        if not variable:
            continue

        def _handle(*_args, bound_var=variable):
            value = bound_var.get().strip()
            if value.lower().endswith(".pdf") and os.path.isfile(value):
                notify_preview(root, value)
            elif not value:
                notify_preview(root, None)

        variable.trace_add("write", _handle)


def open_path(path):
    if not path:
        return
    target = path
    if not os.path.exists(target) and os.path.isfile(os.path.dirname(target)):
        target = os.path.dirname(target)
    try:
        os.startfile(target)
    except OSError:
        pass


def open_containing_folder(path):
    if not path:
        return
    target = path if os.path.isdir(path) else os.path.dirname(path)
    if target:
        open_path(target)


def build_tool_header(parent, eyebrow, title, description, badge_text=None):
    frame = ttk.Frame(parent, style="Hero.TFrame", padding=22)
    frame.pack(fill="x", pady=(0, 18))
    ttk.Label(frame, text=eyebrow, style="HeroEyebrow.TLabel").pack(anchor="w")
    ttk.Label(frame, text=title, style="HeroTitle.TLabel").pack(anchor="w", pady=(6, 0))
    ttk.Label(frame, text=description, style="HeroBody.TLabel", wraplength=780, justify="left").pack(anchor="w", pady=(8, 0))
    if badge_text:
        ttk.Label(frame, text=badge_text, style="Badge.TLabel").pack(anchor="w", pady=(14, 0))
    return frame


def build_file_picker_row(parent, label_text, variable, button_text, command):
    ttk.Label(parent, text=label_text, style="Field.TLabel").pack(anchor="w")
    row = ttk.Frame(parent, style="Surface.TFrame")
    row.pack(fill="x", pady=(8, 0))
    entry = ttk.Entry(row, textvariable=variable, style="Dark.TEntry")
    entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
    button = ttk.Button(row, text=button_text, command=command, style="Secondary.TButton")
    button.pack(side="right")
    return entry, button


class InlineFeedback(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="Panel.TFrame", padding=16)
        self.output_path = None

        self.badge = tk.Label(
            self,
            text=_("feedback_ready_badge"),
            bg="#e6f2ef",
            fg="#0f766e",
            padx=10,
            pady=4,
            font=("Segoe UI Semibold", 9),
        )
        self.badge.pack(anchor="w")

        self.title_var = tk.StringVar(value=_("feedback_ready_title"))
        ttk.Label(self, textvariable=self.title_var, style="StatusTitle.TLabel").pack(anchor="w", pady=(10, 0))

        self.message_var = tk.StringVar(value=_("feedback_ready_body"))
        ttk.Label(self, textvariable=self.message_var, style="StatusBody.TLabel", wraplength=420, justify="left").pack(anchor="w", pady=(6, 0))

        actions = ttk.Frame(self, style="Panel.TFrame")
        actions.pack(anchor="w", pady=(14, 0))
        self.open_file_button = ttk.Button(actions, text=_("feedback_open_output"), command=self.open_result, style="Secondary.TButton")
        self.open_file_button.pack(side="left")
        self.open_folder_button = ttk.Button(actions, text=_("feedback_open_folder"), command=self.open_folder, style="Ghost.TButton")
        self.open_folder_button.pack(side="left", padx=(8, 0))
        self.clear_actions()

    def _set_badge(self, text, background, foreground):
        self.badge.config(text=text, bg=background, fg=foreground)

    def clear_actions(self):
        self.output_path = None
        self.open_file_button.state(["disabled"])
        self.open_folder_button.state(["disabled"])

    def _set_actions(self, output_path=None):
        self.output_path = output_path
        if output_path:
            self.open_file_button.state(["!disabled"])
            self.open_folder_button.state(["!disabled"])
        else:
            self.clear_actions()

    def set_idle(self, title=None, message=None):
        self._set_badge(_("feedback_ready_badge"), "#e6f2ef", "#0f766e")
        self.title_var.set(title or _("feedback_ready_title"))
        self.message_var.set(message or _("feedback_ready_body"))
        self.clear_actions()

    def set_busy(self, message):
        self._set_badge(_("feedback_busy_badge"), "#eaf2ff", "#175cd3")
        self.title_var.set(_("feedback_busy_title"))
        self.message_var.set(message)
        self.clear_actions()

    def set_success(self, title, message, output_path=None):
        self._set_badge(_("feedback_done_badge"), "#e9f7ef", "#15803d")
        self.title_var.set(title)
        self.message_var.set(message)
        self._set_actions(output_path)

    def set_error(self, title, message):
        self._set_badge(_("feedback_error_badge"), "#fff1f2", "#b42318")
        self.title_var.set(title)
        self.message_var.set(message)
        self.clear_actions()

    def set_info(self, title, message):
        self._set_badge(_("feedback_info_badge"), "#fff8e8", "#b45309")
        self.title_var.set(title)
        self.message_var.set(message)
        self.clear_actions()

    def open_result(self):
        if self.output_path:
            open_path(self.output_path)

    def open_folder(self):
        if self.output_path:
            open_containing_folder(self.output_path)


def set_busy(button, progress_bar, is_busy, feedback=None, busy_message=None):
    if is_busy:
        button.config(state="disabled")
        if progress_bar:
            progress_bar.start(12)
        if feedback and busy_message:
            feedback.set_busy(busy_message)
    else:
        button.config(state="normal")
        if progress_bar:
            progress_bar.stop()


def operation_done(button, progress_bar, status_var, status_text, success_msg=None, error_msg=None, feedback=None, output_path=None):
    set_busy(button, progress_bar, False)
    status_var.set(status_text)
    if success_msg and feedback:
        feedback.set_success(status_text, success_msg, output_path)
    elif error_msg and feedback:
        feedback.set_error(status_text, error_msg)


def quick_error(msg, button, progress_bar, status_var, feedback=None):
    set_busy(button, progress_bar, False)
    status_var.set(_("str_error"))
    if feedback:
        feedback.set_error(status_var.get(), msg)
