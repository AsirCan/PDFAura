import tkinter as tk
from tkinter import ttk, messagebox
import fitz # PyMuPDF
from PIL import Image, ImageTk
from src.core.lang_manager import _

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
        # Toolbar
        self.toolbar = ttk.Frame(self, padding=5)
        self.toolbar.pack(side="top", fill="x")
        
        ttk.Button(self.toolbar, text=_("viewer_prev"), command=self.prev_page).pack(side="left", padx=5)
        self.page_label = ttk.Label(self.toolbar, text=_("viewer_page").format(current=1, total=self.total_pages))
        self.page_label.pack(side="left", padx=10)
        ttk.Button(self.toolbar, text=_("viewer_next"), command=self.next_page).pack(side="left", padx=5)
        
        ttk.Separator(self.toolbar, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(self.toolbar, text=_("viewer_zoom_in"), command=self.zoom_in).pack(side="left", padx=5)
        ttk.Button(self.toolbar, text=_("viewer_zoom_out"), command=self.zoom_out).pack(side="left", padx=5)

        # Canvas for image
        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.pack(fill="both", expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#2d2d30")
        self.scroll_y = ttk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scroll_x = ttk.Scrollbar(self.canvas_frame, orient="horizontal", command=self.canvas.xview)
        
        self.canvas.configure(yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set)
        
        self.scroll_y.pack(side="right", fill="y")
        self.scroll_x.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Binding mouse wheel
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

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
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        self.canvas.config(scrollregion=(0, 0, pix.width, pix.height))

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
