import os
import tkinter as tk
from tkinter import ttk

import fitz
from PIL import Image, ImageTk

from src.core.lang_manager import _
from src.gui.pdf_viewer import PDFViewerWindow
from src.gui.styles import PREVIEW_BG


class PreviewPanel(ttk.Frame):
    def __init__(self, parent, app_root):
        super().__init__(parent, style="Preview.TFrame", padding=18)
        self.app_root = app_root
        self.current_path = None
        self.tk_image = None
        self._build_ui()
        self.set_path(None)

    def _build_ui(self):
        ttk.Label(self, text=_("preview_title"), style="PreviewTitle.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text=_("preview_subtitle"),
            style="PreviewMeta.TLabel",
            wraplength=280,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        self.canvas = tk.Canvas(self, width=280, height=360, bg=PREVIEW_BG, bd=0, highlightthickness=0)
        self.canvas.pack(fill="x", pady=(16, 0))

        self.name_var = tk.StringVar()
        self.meta_var = tk.StringVar()
        self.path_var = tk.StringVar()

        ttk.Label(self, textvariable=self.name_var, style="PreviewTitle.TLabel", wraplength=280, justify="left").pack(anchor="w", pady=(14, 0))
        ttk.Label(self, textvariable=self.meta_var, style="PreviewMeta.TLabel", wraplength=280, justify="left").pack(anchor="w", pady=(6, 0))
        ttk.Label(self, textvariable=self.path_var, style="PreviewMeta.TLabel", wraplength=280, justify="left").pack(anchor="w", pady=(10, 0))

        actions = ttk.Frame(self, style="Preview.TFrame")
        actions.pack(anchor="w", pady=(14, 0))
        self.open_button = ttk.Button(actions, text=_("preview_open"), command=self.open_viewer, style="Secondary.TButton")
        self.open_button.pack(side="left")
        self.folder_button = ttk.Button(actions, text=_("preview_open_folder"), command=self.open_folder, style="Ghost.TButton")
        self.folder_button.pack(side="left", padx=(8, 0))

    def set_path(self, path):
        self.current_path = path if path and os.path.isfile(path) and path.lower().endswith(".pdf") else None
        self.canvas.delete("all")
        self.tk_image = None

        if not self.current_path:
            self.name_var.set(_("preview_empty_title"))
            self.meta_var.set(_("preview_empty_body"))
            self.path_var.set(_("preview_empty_sources"))
            self.open_button.state(["disabled"])
            self.folder_button.state(["disabled"])
            return

        self.open_button.state(["!disabled"])
        self.folder_button.state(["!disabled"])

        try:
            doc = fitz.open(self.current_path)
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(0.42, 0.42), alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self.tk_image = ImageTk.PhotoImage(image)

            self.canvas.create_rectangle(10, 10, 270, 350, fill="#dce6f0", outline="")
            self.canvas.create_image(140, 180, image=self.tk_image)

            file_size = os.path.getsize(self.current_path) / (1024 * 1024)
            self.name_var.set(os.path.basename(self.current_path))
            self.meta_var.set(_("preview_pages_mb").format(pages=len(doc), size=file_size))
            self.path_var.set(self.current_path)
            doc.close()
        except Exception as exc:
            self.canvas.create_text(140, 180, text=_("preview_unavailable"), fill="#b42318", width=220, font=("Segoe UI Semibold", 11))
            self.name_var.set(os.path.basename(self.current_path))
            self.meta_var.set(str(exc))
            self.path_var.set(self.current_path)

    def open_viewer(self):
        if self.current_path:
            PDFViewerWindow(self.app_root, self.current_path)

    def open_folder(self):
        if self.current_path:
            os.startfile(os.path.dirname(self.current_path))
