import os
import tkinter as tk
from tkinter import messagebox, ttk

from src.core.config_manager import cfg
from src.core.lang_manager import _
from src.core.notify import play_error, play_success
from src.gui import styles
from src.gui.styles import P, TONES
from src.gui.theme.images import Icons
from src.gui.widgets import ScrollArea


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


def build_hint_strip(parent, text):
    """One-line "how to use this tool" hint shown above a tool's form."""
    frame = ttk.Frame(parent, style="Hint.TFrame", padding=(12, 7))
    frame.pack(fill="x", pady=(0, 12))
    icon = styles.icon(Icons.INFO, 13, P.text_tertiary)
    ttk.Label(frame, image=icon, style="HintIcon.TLabel").pack(side="left", anchor="n", pady=(1, 0))
    label = ttk.Label(frame, text=text, style="HintStrip.TLabel", wraplength=820, justify="left")
    label.pack(side="left", padx=(8, 0))
    follow_width(label, frame, 48)
    return frame


def follow_width(label, container, margin=0, minimum=160):
    """Wrap a label to its container's width instead of a fixed wraplength.

    A fixed wraplength asks for that width no matter how narrow the window
    is, which pushed the preview panel off the right edge; a label that
    never wraps runs past it.
    """
    def _rewrap(event):
        width = max(minimum, event.width - margin)
        try:
            current = int(float(str(label.cget("wraplength")) or 0))
        except ValueError:
            current = 0
        if abs(current - width) > 8:
            label.configure(wraplength=width)

    container.bind("<Configure>", _rewrap, add="+")


def collapse_to_icons(row, buttons):
    """Show *buttons* as bare icons while *row* is too narrow for their labels.

    A row of labelled buttons does not wrap, so in longer languages (or a
    narrow window) the last ones were cut off mid-word. The last buttons
    collapse first; each should carry a Tooltip with its label.
    """
    def _width(widget):
        padx = widget.pack_info().get("padx", 0)
        # pack reports (left, right) for uneven padding, one number otherwise.
        pad = sum(int(p) for p in padx) if isinstance(padx, tuple) else int(padx) * 2
        return widget.winfo_reqwidth() + pad

    def _refit(event):
        for button in buttons:
            button.configure(compound="left")
        needed = sum(_width(child) for child in row.pack_slaves())
        for button in reversed(buttons):
            if needed <= event.width:
                break
            before = button.winfo_reqwidth()
            button.configure(compound="image")
            needed -= before - button.winfo_reqwidth()

    row.bind("<Configure>", _refit, add="+")


class ToolLayout:
    """The frame every tool page is built in: a hint strip above a scrolling
    column that holds one card. The card grows with the window, and scrolls
    instead of being cut off when the window is too short for it."""

    def __init__(self, parent, hint, padding=24):
        self.shell = ttk.Frame(parent, style="App.TFrame")
        self.shell.pack(fill="both", expand=True)
        build_hint_strip(self.shell, hint)
        self.scroll = ScrollArea(self.shell)
        self.scroll.pack(fill="both", expand=True)
        self.form = ttk.Frame(self.scroll.body, style="Card.TFrame", padding=padding)
        self.form.pack(fill="both", expand=True)


def style_listbox(listbox):
    """Give a tk.Listbox the same flat look as the ttk entries around it."""
    listbox.configure(
        font=styles.font("body"),
        borderwidth=0,
        relief="flat",
        highlightthickness=1,
        activestyle="none",
    )
    styles.themed(
        listbox,
        bg=P.field,
        fg=P.text,
        selectbackground=P.accent_subtle_hover,
        selectforeground=P.text,
        highlightbackground=P.border,
        highlightcolor=P.accent,
        disabledforeground=P.text_disabled,
    )


class ListEmptyHint:
    """Centred text over an empty listbox saying how to fill it; clicking
    it runs the add action. Call refresh() after changing the list."""

    def __init__(self, listbox, text, command=None):
        self.listbox = listbox
        self.label = styles.themed(
            tk.Label(listbox, text=text, font=styles.font("small"), justify="center",
                     wraplength=260, cursor="hand2" if command else ""),
            bg=P.field, fg=P.text_tertiary)
        if command:
            self.label.bind("<Button-1>", lambda _e: command())
        self.refresh()

    def refresh(self):
        if self.listbox.size() == 0:
            self.label.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.label.place_forget()


def move_listbox_item(listbox, items, step):
    """Move the selected listbox row (and its backing list entry) by *step*."""
    selected = listbox.curselection()
    if not selected:
        return
    index = selected[0]
    target = index + step
    if target < 0 or target >= len(items):
        return
    items[index], items[target] = items[target], items[index]
    text = listbox.get(index)
    listbox.delete(index)
    listbox.insert(target, text)
    listbox.selection_clear(0, tk.END)
    listbox.selection_set(target)
    listbox.see(target)


class ProgressFooter(ttk.Frame):
    """The tool's action row: the main button, then progress and Cancel
    while a job runs. The progress bar stays hidden while there is nothing
    to report."""

    def __init__(self, parent, action_text, action_command, button_style="Primary.TButton",
                 progress_style="Accent.Horizontal.TProgressbar"):
        super().__init__(parent, style="Surface.TFrame")

        self._cancel_callback = None
        self._progress_style = progress_style

        ttk.Frame(self, style="Divider.TFrame", height=1).pack(fill="x", pady=(0, 16))
        row = ttk.Frame(self, style="Surface.TFrame")
        row.pack(fill="x")

        self.action_button = ttk.Button(row, text=action_text, command=action_command, style=button_style)
        self.action_button.pack(side="left")

        # Shown only while a cancellable job runs.
        self.cancel_button = ttk.Button(row, text=_("perf_cancel"), command=self._on_cancel,
                                        style="Secondary.TButton")

        self.status = ttk.Frame(row, style="Surface.TFrame")
        self.progress_bar = ttk.Progressbar(self.status, mode="determinate", style=progress_style, length=160)
        self.progress_bar.pack(side="top", fill="x", pady=(2, 0))
        self.pct_label = ttk.Label(self.status, text="", style="Hint.TLabel")
        self.pct_label.pack(side="top", anchor="w", pady=(4, 0))

    def _show_status(self, visible):
        if visible and not self.status.winfo_manager():
            self.status.pack(side="left", fill="x", expand=True, padx=(16, 0))
        elif not visible:
            self.status.pack_forget()

    def start_busy(self, cancel_callback=None):
        """Called when a job starts: progress from 0 and, if the job can be
        cancelled, a Cancel button."""
        self._cancel_callback = cancel_callback
        self.action_button.config(state="disabled")
        self.progress_bar.configure(style=self._progress_style)
        self.progress_bar["value"] = 0
        self.progress_bar["maximum"] = 100
        self.pct_label.config(text="0%")
        self._show_status(True)

        if cancel_callback:
            self.cancel_button.config(state="normal", text=_("perf_cancel"))
            self.cancel_button.pack(side="left", padx=(8, 0), before=self.status)

    def update_progress(self, current, total, message=""):
        """Progress update. Not thread-safe: call it through app_root.after."""
        if total <= 0:
            total = 1
        pct = int((current / total) * 100)
        self.progress_bar["value"] = pct
        self.progress_bar["maximum"] = 100
        display = f"{pct}%"
        if message:
            short_msg = message if len(message) < 48 else message[:45] + "..."
            display = f"{pct}%  ·  {short_msg}"
        self.pct_label.config(text=display)

    def stop_busy(self):
        """Called when a job ends without a result to show."""
        self.action_button.config(state="normal")
        self.cancel_button.pack_forget()
        self.cancel_button.config(state="normal", text=_("perf_cancel"))
        self._cancel_callback = None
        self.pct_label.config(text="")
        self.progress_bar["value"] = 0
        self._show_status(False)

    def finish_success(self):
        """Called when a job succeeds: a full bar in the success colour."""
        self.stop_busy()
        self._show_status(True)
        self.progress_bar.configure(style="Done.Horizontal.TProgressbar")
        self.progress_bar["value"] = 100
        self.pct_label.config(text="100%")

    def _on_cancel(self):
        self.cancel_button.config(state="disabled", text=_("perf_cancelling"))
        if self._cancel_callback:
            self._cancel_callback()


class InlineFeedback(ttk.Frame):
    """The tool's result panel: its state, what happened, and buttons to
    open the output once there is one."""

    def __init__(self, parent):
        super().__init__(parent, style="Feedback.TFrame", padding=(14, 12))
        self.output_path = None
        self.tone = "neutral"

        head = ttk.Frame(self, style="FeedbackRow.TFrame")
        head.pack(fill="x")
        self.icon = styles.themed(tk.Label(head, bd=0), bg=P.surface_subtle)
        self.icon.pack(side="left", padx=(0, 6))
        self.badge = styles.themed(tk.Label(head, text=_("feedback_ready_badge"),
                                            font=styles.font("micro"), bd=0),
                                   bg=P.surface_subtle, fg=P.text_secondary)
        self.badge.pack(side="left")

        self.title_var = tk.StringVar(value=_("feedback_ready_title"))
        self.title_label = ttk.Label(self, textvariable=self.title_var, style="StatusTitle.TLabel",
                                     justify="left")
        self.title_label.pack(anchor="w", fill="x", pady=(8, 0))

        self.message_var = tk.StringVar(value=_("feedback_ready_body"))
        self.message_label = ttk.Label(self, textvariable=self.message_var, style="StatusBody.TLabel",
                                       wraplength=420, justify="left")
        self.message_label.pack(anchor="w", fill="x", pady=(3, 0))
        follow_width(self.title_label, self, 32)
        follow_width(self.message_label, self, 32)

        self.actions = ttk.Frame(self, style="FeedbackRow.TFrame")
        self.open_file_button = ttk.Button(self.actions, text=_("feedback_open_output"),
                                           command=self.open_result, style="Feedback.Secondary.TButton",
                                           image=styles.icon(Icons.OPEN, 12, P.text), compound="left")
        self.open_file_button.pack(side="left")
        self.open_folder_button = ttk.Button(self.actions, text=_("feedback_open_folder"),
                                             command=self.open_folder, style="Feedback.Ghost.TButton",
                                             image=styles.icon(Icons.FOLDER, 12, P.text_secondary),
                                             compound="left")
        self.open_folder_button.pack(side="left", padx=(6, 0))
        self._set_badge(_("feedback_ready_badge"), "neutral")
        self.clear_actions()

    def _set_badge(self, text, tone):
        """Status line: a coloured icon and label. Colour is never the only
        signal; the label always says the state in words."""
        self.tone = tone
        foreground, glyph = TONES[tone]
        self.badge.config(text=text)
        styles.themed(self.badge, fg=foreground)
        image = styles.icon(glyph, 12, foreground, box=14)
        self.icon.config(image=image or "", text="" if image else "•")
        styles.themed(self.icon, fg=foreground)
        self.icon.image = image

    def _reveal(self):
        """A finished job's result must be on screen, not below the fold of a
        scrolled form. Waits for the scroll area to re-measure first."""
        def scroll():
            area = ScrollArea.owning(self)
            if area is not None and self.winfo_exists():
                area.see(self)
        self.after(ScrollArea.WATCH_MS * 2, scroll)

    def clear_actions(self):
        self.output_path = None
        self.open_file_button.state(["disabled"])
        self.open_folder_button.state(["disabled"])
        self.actions.pack_forget()

    def _set_actions(self, output_path=None):
        self.output_path = output_path
        if output_path:
            self.open_file_button.state(["!disabled"])
            self.open_folder_button.state(["!disabled"])
            self.actions.pack(anchor="w", pady=(12, 0))
        else:
            self.clear_actions()

    def set_idle(self, title=None, message=None):
        self._set_badge(_("feedback_ready_badge"), "neutral")
        self.title_var.set(title or _("feedback_ready_title"))
        self.message_var.set(message or _("feedback_ready_body"))
        self.clear_actions()

    def set_busy(self, message):
        self._set_badge(_("feedback_busy_badge"), "busy")
        self.title_var.set(_("feedback_busy_title"))
        self.message_var.set(message)
        self.clear_actions()

    def set_success(self, title, message, output_path=None):
        self._set_badge(_("feedback_done_badge"), "success")
        self._reveal()
        self.title_var.set(title)
        self.message_var.set(message)
        self._set_actions(output_path)
        # Every tool finishes through here, so this is where the "play a
        # sound when a job finishes" setting and the recent-files list are
        # actually honoured.
        play_success()
        if output_path:
            cfg.add_recent_file(output_path)
            refresh = getattr(self.winfo_toplevel(), "pdf_aura_refresh_recent", None)
            if refresh:
                refresh()

    def set_error(self, title, message):
        self._set_badge(_("feedback_error_badge"), "danger")
        self._reveal()
        self.title_var.set(title)
        self.message_var.set(message)
        self.clear_actions()
        play_error()

    def set_warning(self, title, message, output_path=None):
        """Partial success: some items worked, some did not."""
        self._set_badge(_("feedback_warning_badge"), "warning")
        self._reveal()
        self.title_var.set(title)
        self.message_var.set(message)
        self._set_actions(output_path)

    def set_info(self, title, message):
        self._set_badge(_("feedback_info_badge"), "info")
        self.title_var.set(title)
        self.message_var.set(message)
        self.clear_actions()

    def set_cancelled(self, message=""):
        self._set_badge(_("perf_cancelled_badge"), "warning")
        self._reveal()
        self.title_var.set(_("perf_cancelled"))
        self.message_var.set(message or _("perf_cancelled_msg"))
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


def confirm_overwrite(path, parent=None):
    """Ask before replacing an existing file. True means go ahead.

    Only for paths the app suggested: a path the user picked in a save
    dialog was already confirmed there.
    """
    if not path or not os.path.isfile(path):
        return True
    return messagebox.askyesno(
        _("overwrite_title"),
        _("overwrite_body").format(path=path),
        parent=parent,
        icon="warning",
    )


def quick_error(msg, button, progress_bar, status_var, feedback=None):
    set_busy(button, progress_bar, False)
    status_var.set(_("str_error"))
    if feedback:
        feedback.set_error(status_var.get(), msg)
