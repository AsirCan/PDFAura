import os
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from src.core.lang_manager import _
from src.gui import styles
from src.gui.helpers import follow_width
from src.gui.pdf_viewer import PDFViewerWindow
from src.gui.styles import P
from src.gui.theme.images import Icons, rounded_box

# First page is rendered once at this width and scaled to fit the stage.
_RENDER_WIDTH = 560
_STAGE_PAD = 22


class PreviewPanel(ttk.Frame):
    """First page of the selected PDF on a paper-grey stage, with its name,
    size and shortcuts. The stage takes all the height the window gives it."""

    def __init__(self, parent, app_root):
        super().__init__(parent, style="Preview.TFrame", padding=18)
        self.app_root = app_root
        self.current_path = None
        self.tk_image = None
        self._page_image = None      # PIL render of page 1, reused on resize
        self._stage_photo = None
        self._error = None
        self._resize_job = None
        self._build_ui()
        self.set_path(None)

    def _build_ui(self):
        ttk.Label(self, text=_("preview_title"), style="PreviewTitle.TLabel").pack(anchor="w")
        subtitle = ttk.Label(self, text=_("preview_subtitle"), style="PreviewMeta.TLabel",
                             wraplength=280, justify="left")
        subtitle.pack(anchor="w", fill="x", pady=(2, 0))
        follow_width(subtitle, self, 36)

        # Bottom-up so the stage keeps whatever height is left.
        actions = ttk.Frame(self, style="Surface.TFrame")
        actions.pack(side="bottom", fill="x", pady=(14, 0))
        self.open_button = ttk.Button(actions, text=_("preview_open"), command=self.open_viewer,
                                      style="Secondary.TButton",
                                      image=styles.icon_states(Icons.OPEN, 13, P.text), compound="left")
        self.open_button.pack(side="left")
        self.folder_button = ttk.Button(actions, text=_("preview_open_folder"), command=self.open_folder,
                                        style="Ghost.TButton",
                                        image=styles.icon_states(Icons.FOLDER, 13, P.text_secondary),
                                        compound="left")
        self.folder_button.pack(side="left", padx=(6, 0))
        # The panel is narrow; in longer languages ("Ordner öffnen") the two
        # buttons do not fit side by side, so the second one moves below.
        actions.bind("<Configure>", self._fit_actions, add="+")

        self.name_var = tk.StringVar()
        self.meta_var = tk.StringVar()
        self.path_var = tk.StringVar()
        self.info = ttk.Frame(self, style="Surface.TFrame")
        self.info.pack(side="bottom", fill="x", pady=(14, 0))
        name = ttk.Label(self.info, textvariable=self.name_var, style="PreviewName.TLabel",
                         wraplength=280, justify="left")
        name.pack(anchor="w", fill="x")
        ttk.Label(self.info, textvariable=self.meta_var, style="PreviewMeta.TLabel").pack(anchor="w", pady=(2, 0))
        path = ttk.Label(self.info, textvariable=self.path_var, style="PreviewPath.TLabel",
                         wraplength=280, justify="left")
        path.pack(anchor="w", fill="x", pady=(6, 0))
        follow_width(name, self.info, 4)
        follow_width(path, self.info, 4)

        self.canvas = styles.themed(tk.Canvas(self, width=280, height=240, bd=0, highlightthickness=0),
                                    bg=P.surface)
        self.canvas.pack(fill="both", expand=True, pady=(14, 0))
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Double-Button-1>", lambda _e: self.open_viewer())
        styles.on_theme_change(self._draw)

    # ── State ─────────────────────────────────────────────────────────────

    def set_path(self, path):
        self.current_path = path if path and os.path.isfile(path) and path.lower().endswith(".pdf") else None
        self._page_image = None
        self._error = None
        self.tk_image = None

        if not self.current_path:
            self.name_var.set(_("preview_empty_title"))
            self.meta_var.set("")
            self.path_var.set("")
            self.info.pack_forget()
            self.open_button.state(["disabled"])
            self.folder_button.state(["disabled"])
            self._draw()
            return

        self.open_button.state(["!disabled"])
        self.folder_button.state(["!disabled"])
        if not self.info.winfo_manager():
            self.info.pack(side="bottom", fill="x", pady=(14, 0), before=self.canvas)

        import fitz    # PyMuPDF: loaded with the first preview, not at startup
        doc = None
        try:
            doc = fitz.open(self.current_path)
            page = doc.load_page(0)
            zoom = _RENDER_WIDTH / max(1.0, page.rect.width)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            self._page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            file_size = os.path.getsize(self.current_path) / (1024 * 1024)
            self.name_var.set(os.path.basename(self.current_path))
            self.meta_var.set(_("preview_pages_mb").format(pages=len(doc), size=file_size))
            self.path_var.set(os.path.dirname(self.current_path))
        except Exception as exc:
            self._error = str(exc)
            self.name_var.set(os.path.basename(self.current_path))
            self.meta_var.set(str(exc))
            self.path_var.set(os.path.dirname(self.current_path))
        finally:
            # The error path left the document open, holding the file locked.
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass
        self._draw()

    # ── Drawing ───────────────────────────────────────────────────────────

    def _on_resize(self, _event):
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(40, self._draw)

    def _draw(self):
        self._resize_job = None
        c = self.canvas
        c.delete("all")
        w, h = max(40, c.winfo_width()), max(40, c.winfo_height())

        # The stage: a rounded paper-grey well.
        self._stage_photo = ImageTk.PhotoImage(
            rounded_box(w, h, styles.M.radius, P.sunken), master=c)
        c.create_image(0, 0, anchor="nw", image=self._stage_photo)

        if self._page_image is not None:
            self._draw_page(w, h)
        elif self._error:
            c.create_text(w / 2, h / 2, text=_("preview_unavailable"), fill=P.danger,
                          width=w - 40, font=styles.font("body_strong"), justify="center")
        else:
            self._draw_empty(w, h)

    def _draw_page(self, w, h):
        img = self._page_image
        scale = min((w - _STAGE_PAD * 2) / img.width, (h - _STAGE_PAD * 2) / img.height)
        size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
        self.tk_image = ImageTk.PhotoImage(img.resize(size, Image.LANCZOS), master=self.canvas)
        x0, y0 = (w - size[0]) // 2, (h - size[1]) // 2
        # A hairline edge and a soft drop so white pages read on the stage.
        self.canvas.create_rectangle(x0 + 1, y0 + 3, x0 + size[0] + 1, y0 + size[1] + 3,
                                     fill=P.border_subtle, outline="")
        self.canvas.create_image(x0, y0, anchor="nw", image=self.tk_image)
        self.canvas.create_rectangle(x0, y0, x0 + size[0], y0 + size[1], outline=P.border_subtle)

    def _draw_empty(self, w, h):
        c = self.canvas
        inset = 12
        c.create_rectangle(inset, inset, w - inset, h - inset, outline=P.border, dash=(4, 3))
        cy = h / 2
        glyph = styles.icon_font(26)
        if glyph:
            c.create_text(w / 2, cy - 38, text=Icons.DOCUMENT, fill=P.text_tertiary, font=glyph)
        c.create_text(w / 2, cy + 2, text=_("preview_empty_title"), fill=P.text,
                      font=styles.font("body_strong"), width=w - 60, justify="center")
        c.create_text(w / 2, cy + 24, text=_("str_drag_drop_hint"), fill=P.text_secondary,
                      font=styles.font("small"), width=w - 60, justify="center", anchor="n")

    # ── Actions ───────────────────────────────────────────────────────────

    def _fit_actions(self, event):
        needed = self.open_button.winfo_reqwidth() + 6 + self.folder_button.winfo_reqwidth()
        stacked = needed > event.width
        if stacked == getattr(self, "_actions_stacked", False):
            return
        self._actions_stacked = stacked
        if stacked:
            self.folder_button.pack_configure(side="top", anchor="w", padx=0, pady=(6, 0))
            self.open_button.pack_configure(side="top", anchor="w")
        else:
            self.open_button.pack_configure(side="left", anchor="center")
            self.folder_button.pack_configure(side="left", anchor="center", padx=(6, 0), pady=0)

    def open_viewer(self):
        if self.current_path:
            PDFViewerWindow(self.app_root, self.current_path)

    def open_folder(self):
        if self.current_path:
            os.startfile(os.path.dirname(self.current_path))
