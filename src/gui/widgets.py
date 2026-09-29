"""Reusable interface components built on the theme's ttk styles."""
import tkinter as tk
from tkinter import ttk

from src.gui import styles
from src.gui.styles import P


# ── Keyboard focus ring ─────────────────────────────────────────────────────

class FocusVisible:
    """Show the focus ring only when focus arrived from the keyboard.

    A ring on every clicked button is noise; no ring at all makes Tab
    navigation unusable. Buttons get ttk's user1 state while they hold
    keyboard focus, and the button images draw the ring for "user1 focus"
    (like CSS :focus-visible).
    """

    CLASSES = ("TButton", "TCheckbutton", "TRadiobutton")

    def __init__(self, root):
        self.keyboard = False
        root.bind_all("<KeyPress-Tab>", self._key, add="+")
        root.bind_all("<ISO_Left_Tab>", self._key, add="+")
        root.bind_all("<Button>", self._mouse, add="+")
        for cls in self.CLASSES:
            root.bind_class(cls, "<FocusIn>", self._focus_in, add="+")
            root.bind_class(cls, "<FocusOut>", self._focus_out, add="+")

    def _key(self, _event):
        self.keyboard = True

    def _mouse(self, _event):
        self.keyboard = False

    def _focus_in(self, event):
        try:
            event.widget.state(["user1"] if self.keyboard else ["!user1"])
        except (tk.TclError, AttributeError):
            pass

    @staticmethod
    def _focus_out(event):
        try:
            event.widget.state(["!user1"])
        except (tk.TclError, AttributeError):
            pass


# ── Tooltip ─────────────────────────────────────────────────────────────────

class Tooltip:
    """A small delayed label for icon-only controls and shortcuts."""

    DELAY_MS = 450

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self._job = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._job = self.widget.after(self.DELAY_MS, self._show)

    def _cancel(self):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None

    def _show(self):
        self._job = None
        if self._tip or not self.text or not self.widget.winfo_ismapped():
            return
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.attributes("-topmost", True)
        tk.Label(tip, text=self.text, bg=P.stage, fg=P.stage_text, font=styles.font("small"),
                 padx=8, pady=4, justify="left").pack()
        tip.update_idletasks()
        x = self.widget.winfo_rootx() + (self.widget.winfo_width() - tip.winfo_width()) // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        screen_w = self.widget.winfo_screenwidth()
        x = max(4, min(x, screen_w - tip.winfo_width() - 4))
        tip.geometry(f"+{x}+{y}")
        self._tip = tip

    def _hide(self, _event=None):
        self._cancel()
        if self._tip:
            self._tip.destroy()
            self._tip = None


# ── Segmented control ───────────────────────────────────────────────────────

class SegmentedControl(ttk.Frame):
    """Pick one of a few options with every option in view.

    A read-only combobox hides the choices behind a click; for two to seven
    modes a segmented row is faster and shows what the tool can do. Bound to
    a StringVar holding the option's *label*, so existing code that compares
    the variable with translated labels keeps working. Segments wrap onto
    more rows when the control is narrower than its options.
    """

    def __init__(self, parent, variable, values, command=None, on_canvas=False):
        style = "CanvasSegmented.TFrame" if on_canvas else "Segmented.TFrame"
        super().__init__(parent, style=style, padding=3)
        self.variable = variable
        self.command = command
        self._button_style = "CanvasSegment.TButton" if on_canvas else "Segment.TButton"
        self.buttons = {}
        self._columns = None
        for value in values:
            button = ttk.Button(self, text=value, style=self._button_style,
                                command=lambda v=value: self.select(v))
            self.buttons[value] = button
        self._trace = variable.trace_add("write", lambda *_a: self._sync())
        self.bind("<Configure>", self._reflow)
        self._layout(len(self.buttons))
        self._sync()

    @property
    def values(self):
        return list(self.buttons)

    def select(self, value, notify=True):
        if value not in self.buttons:
            return
        changed = self.variable.get() != value
        self.variable.set(value)
        if notify and changed and self.command:
            self.command()

    def _sync(self):
        current = self.variable.get()
        for value, button in self.buttons.items():
            button.state(["selected"] if value == current else ["!selected"])

    def _natural_width(self):
        return max(b.winfo_reqwidth() for b in self.buttons.values()) if self.buttons else 0

    def _layout(self, columns):
        if columns == self._columns:
            return
        self._columns = columns
        for index, button in enumerate(self.buttons.values()):
            button.grid(row=index // columns, column=index % columns, sticky="nsew", padx=1, pady=1)
        for column in range(len(self.buttons)):
            used = column < columns
            self.columnconfigure(column, weight=1 if used else 0, uniform="seg" if used else "")

    def _reflow(self, event):
        needed = self._natural_width() + 2
        count = len(self.buttons)
        if not count or needed <= 2:
            return
        columns = max(1, min(count, (event.width - 6) // needed))
        if columns < count:
            # Even rows: 7 options in 4+3, not 6+1.
            rows = -(-count // columns)
            columns = -(-count // rows)
        self._layout(columns)


# ── Scrollable area ─────────────────────────────────────────────────────────

class ScrollArea(ttk.Frame):
    """A vertically scrolling column that only shows a scrollbar when its
    content is taller than the window.

    Children go into `.body`. The body is stretched to the visible height
    when the content is shorter, so `pack(expand=True)` inside it still
    fills the space; tall forms simply scroll instead of being cut off at
    small window sizes.
    """

    _areas = []
    _wheel_bound = False
    _OWN_WHEEL = ("Listbox", "Text", "Treeview", "Canvas", "TCombobox")
    WATCH_MS = 150

    def __init__(self, parent, style="App.TFrame", background=None):
        super().__init__(parent, style=style)
        bg = background or P.canvas
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, width=1, height=1)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                       style="Canvas.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.canvas, style=style)
        self._window = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self._pending = False
        self._scrolling = False
        self._applied = None
        self._last_req = None
        self.canvas.bind("<Configure>", lambda _e: self.schedule_reflow())
        # Any widget inside changing size may change the content height; the
        # toplevel's bindtag sees every <Configure> in the window.
        self.winfo_toplevel().bind("<Configure>", self._on_any_configure, add="+")
        ScrollArea._areas.append(self)
        self.bind("<Destroy>", self._forget, add="+")
        self.after(self.WATCH_MS, self._watch)
        if not ScrollArea._wheel_bound:
            self.bind_all("<MouseWheel>", ScrollArea._on_wheel, add="+")
            ScrollArea._wheel_bound = True

    def _forget(self, event):
        if event.widget is self and self in ScrollArea._areas:
            ScrollArea._areas.remove(self)

    def _on_any_configure(self, event):
        if self in ScrollArea._areas and str(event.widget).startswith(str(self.body)):
            self.schedule_reflow()

    def _watch(self):
        """Content that grows past the visible height is unmapped by pack and
        sends no <Configure>, so watch the requested height as well."""
        if not self.winfo_exists():
            return
        if self.winfo_ismapped():
            req = self.body.winfo_reqheight()
            if req != self._last_req:
                self._last_req = req
                self.schedule_reflow()
        self.after(self.WATCH_MS, self._watch)

    def schedule_reflow(self):
        if not self._pending:
            self._pending = True
            self.after_idle(self.reflow)

    def reflow(self):
        self._pending = False
        if not self.winfo_exists():
            return
        view_w = max(1, self.canvas.winfo_width())
        view_h = max(1, self.canvas.winfo_height())
        content_h = self.body.winfo_reqheight()
        scrolling = content_h > view_h + 1
        if scrolling != self._scrolling:
            # The scrollbar changes the canvas width; measure again once the
            # geometry has settled rather than forcing it here (update_idletasks
            # inside an idle handler re-enters and never finishes).
            self._scrolling = scrolling
            if scrolling:
                self.scrollbar.pack(side="right", fill="y", padx=(6, 0))
            else:
                self.scrollbar.pack_forget()
                self.canvas.yview_moveto(0)
            self.schedule_reflow()
            return
        height = content_h if scrolling else view_h
        if (view_w, height) != self._applied:
            self._applied = (view_w, height)
            self.canvas.itemconfigure(self._window, width=view_w, height=height)
            self.canvas.configure(scrollregion=(0, 0, view_w, height))

    @property
    def is_scrolling(self):
        return self._scrolling

    def see(self, widget, margin=16):
        """Scroll just far enough that `widget` (inside the body) is visible."""
        if not self._scrolling:
            return
        top = widget.winfo_rooty() - self.body.winfo_rooty()
        bottom = top + widget.winfo_height()
        total = max(1, self.body.winfo_height())
        view_top, view_bottom = (f * total for f in self.canvas.yview())
        if bottom + margin > view_bottom:
            target = min(bottom + margin, total) - (view_bottom - view_top)
        elif top - margin < view_top:
            target = max(0, top - margin)
        else:
            return
        self.canvas.yview_moveto(max(0.0, target) / total)

    @staticmethod
    def owning(widget):
        """The ScrollArea a widget sits in, or None."""
        node = widget
        while node is not None:
            if isinstance(node, ScrollArea):
                return node
            node = node.master
        return None

    @classmethod
    def _on_wheel(cls, event):
        widget = event.widget
        try:
            if isinstance(widget, str) or widget.winfo_class() in cls._OWN_WHEEL:
                return
        except tk.TclError:
            return
        path = str(widget)
        for area in cls._areas:
            if area._scrolling and (path == str(area.canvas) or path.startswith(str(area.body) + ".")
                                    or path == str(area.body)):
                area.canvas.yview_scroll(int(-event.delta / 120) * 3, "units")
                return
