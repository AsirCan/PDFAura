import tkinter as tk
from tkinter import ttk, messagebox
import fitz # PyMuPDF
from PIL import Image, ImageTk
from src.core.lang_manager import _
from src.gui import styles
from src.gui.styles import P
from src.gui.theme.images import Icons
from src.gui.widgets import Tooltip

class PDFViewerWindow(tk.Toplevel):
    def __init__(self, parent, pdf_path):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.title(_("viewer_title"))
        self.geometry("1000x800")
        
        try:
            self.doc = fitz.open(self.pdf_path)
            self.total_pages = len(self.doc)
        except Exception as e:
            messagebox.showerror(_("str_error"), f"{_('err_pdf_open_fail')}{e}", parent=self)
            self.destroy()
            return
            
        self.current_page = 0
        self.zoom_factor = 1.0  # Fit standard pages better
        
        self.build_ui()
        self.show_page(0)

    def build_ui(self):
        self.configure(bg=P.stage)
        self.toolbar = ttk.Frame(self, style="Surface.TFrame", padding=(16, 8))
        self.toolbar.pack(side="top", fill="x")
        ttk.Frame(self, style="Divider.TFrame", height=1).pack(side="top", fill="x")

        def tool(text, glyph, command, shortcut):
            button = ttk.Button(self.toolbar, text=text, command=command, style="Ghost.TButton",
                                image=styles.icon(glyph, 13, P.text_secondary) or "", compound="left")
            button.pack(side="left", padx=(0, 2))
            Tooltip(button, shortcut)
            return button

        tool(_("viewer_prev"), Icons.LEFT, self.prev_page, "← / PgUp")
        self.page_label = ttk.Label(self.toolbar, text=_("viewer_page").format(current=1, total=self.total_pages),
                                    style="Body.TLabel")
        self.page_label.pack(side="left", padx=12)
        tool(_("viewer_next"), Icons.RIGHT, self.next_page, "→ / PgDn")

        ttk.Frame(self.toolbar, style="Divider.TFrame", width=1).pack(side="left", fill="y", padx=12, pady=4)
        tool(_("viewer_zoom_out"), Icons.ZOOM_OUT, self.zoom_out, "−")
        tool(_("viewer_zoom_in"), Icons.ZOOM_IN, self.zoom_in, "+")
        self.zoom_label = ttk.Label(self.toolbar, text="100%", style="Hint.TLabel")
        self.zoom_label.pack(side="left", padx=(8, 0))

        # Canvas for image
        self.canvas_frame = ttk.Frame(self, style="Stage.TFrame")
        self.canvas_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg=P.stage, highlightthickness=0, bd=0)
        self.scroll_y = ttk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview,
                                      style="Stage.Vertical.TScrollbar")
        self.scroll_x = ttk.Scrollbar(self.canvas_frame, orient="horizontal", command=self.canvas.xview,
                                      style="Stage.Horizontal.TScrollbar")

        self.canvas.configure(yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set)

        self.scroll_y.pack(side="right", fill="y")
        self.scroll_x.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._center())

        # Binding mouse wheel
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

        # Keyboard shortcuts: the viewer had none at all.
        self.bind("<Left>", lambda e: self.prev_page())
        self.bind("<Right>", lambda e: self.next_page())
        self.bind("<Prior>", lambda e: self.prev_page())      # PageUp
        self.bind("<Next>", lambda e: self.next_page())       # PageDown
        self.bind("<Home>", lambda e: self.show_page(0))
        self.bind("<End>", lambda e: self.show_page(self.total_pages - 1))
        self.bind("<plus>", lambda e: self.zoom_in())
        self.bind("<KP_Add>", lambda e: self.zoom_in())
        self.bind("<minus>", lambda e: self.zoom_out())
        self.bind("<KP_Subtract>", lambda e: self.zoom_out())
        self.bind("<Escape>", lambda e: self.destroy())
        self.focus_set()

        # The document was never closed, so the file stayed locked.
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def destroy(self):
        doc = getattr(self, "doc", None)
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass
            self.doc = None
        super().destroy()

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def show_page(self, page_num):
        if page_num < 0 or page_num >= self.total_pages:
            return
        self.current_page = page_num
        self.page_label.config(text=_("viewer_page").format(current=self.current_page + 1, total=self.total_pages))
        
        page = self.doc.load_page(self.current_page)
        mat = fitz.Matrix(self.zoom_factor, self.zoom_factor)
        pix = page.get_pixmap(matrix=mat)
        
        mode = "RGBA" if pix.alpha else "RGB"
        img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        
        self.tk_image = ImageTk.PhotoImage(img) # Keep reference
        
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image, tags="page")
        self._page_size = (pix.width, pix.height)
        self.zoom_label.config(text=f"{int(round(self.zoom_factor * 100))}%")
        self._center()

    def _center(self):
        """Keep the page centred on the stage with a margin around it; a
        small page used to sit in the top-left corner."""
        size = getattr(self, "_page_size", None)
        if not size:
            return
        margin = 24
        view_w, view_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        page_w, page_h = size
        x = max(margin, (view_w - page_w) // 2)
        y = max(margin, (view_h - page_h) // 2) if page_h + margin * 2 < view_h else margin
        self.canvas.coords("page", x, y)
        self.canvas.config(scrollregion=(0, 0, max(view_w, page_w + margin * 2), max(view_h, page_h + margin * 2)))

    def next_page(self):
        self.show_page(self.current_page + 1)
        
    def prev_page(self):
        self.show_page(self.current_page - 1)
        
    def zoom_in(self):
        if self.zoom_factor < 5.0:
            self.zoom_factor += 0.5
            self.show_page(self.current_page)
            
    def zoom_out(self):
        if self.zoom_factor > 0.5:
            self.zoom_factor -= 0.5
            self.show_page(self.current_page)
