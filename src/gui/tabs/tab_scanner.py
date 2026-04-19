"""
Scanner Tab – CamScanner-like document scanning UI  (multi-page)
────────────────────────────────────────────────────────────────
• Add multiple photos → each becomes one PDF page
• Interactive 4-corner cropping on a tk.Canvas (draggable points)
• Rotation controls in the toolbar
• Gamma / scan-mode selector with live preview
• Export all pages to a single multi-page PDF
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog

import cv2
import numpy as np
from PIL import Image, ImageTk

from src.core.document_scanner import (
    MODE_BW,
    MODE_CLEAN_DOC,
    MODE_GRAYSCALE,
    MODE_ORIGINAL,
    MODE_SHARP,
    A4_WIDTH_PX,
    A4_HEIGHT_PX,
    detect_document_corners,
    perspective_warp,
    apply_scan_mode,
    rotate_image,
    scanned_images_to_pdf,
)
from src.core.lang_manager import _ as tr   # rename to avoid shadowing
from src.gui.helpers import InlineFeedback, build_tool_header, operation_done, quick_error, set_busy
from src.gui.styles import (
    SURFACE_COLOR, SURFACE_ALT, FIELD_COLOR, TEXT_COLOR, MUTED_TEXT,
    BORDER_COLOR, PRIMARY_ACCENT, CONVERT_ACCENT,
)

# ── Constants ────────────────────────────────────────────────────────────────
CORNER_RADIUS = 8
CORNER_COLOR = "#ef4444"
CORNER_ACTIVE = "#f97316"
LINE_COLOR = "#3b82f6"
LINE_WIDTH = 2
CANVAS_BG = "#1e293b"

# Map internal mode constants → i18n keys
_MODE_MAP = [
    (MODE_ORIGINAL,  "scanner_mode_original"),
    (MODE_CLEAN_DOC, "scanner_mode_clean_doc"),
    (MODE_BW,        "scanner_mode_bw"),
    (MODE_GRAYSCALE, "scanner_mode_grayscale"),
    (MODE_SHARP,     "scanner_mode_sharp"),
]


class _PageData:
    """Per-page state for one photo in the scan list."""
    __slots__ = ("path", "cv_image", "display_image", "rotation", "corners")

    def __init__(self, path, cv_image, corners):
        self.path = path
        self.cv_image = cv_image
        self.display_image = cv_image.copy()
        self.rotation = 0
        self.corners = list(corners)


class ScannerTab:
    """CamScanner-like document scanner tab with multi-page support."""

    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root

        # ── state ──
        self.pages: list[_PageData] = []
        self.current_index = -1           # index of currently selected page
        self.tk_photo = None
        self.preview_photo = None
        self.canvas_scale = 1.0
        self.canvas_offset = (0, 0)
        self.dragging_corner = None

        # ── tkinter vars ──
        self.output_var = tk.StringVar()
        self.status_var = tk.StringVar(value=tr("str_ready"))
        self.scan_mode_var = tk.StringVar(value=tr("scanner_mode_original"))
        self.page_label_var = tk.StringVar(value=tr("scanner_no_pages"))

        self.build_ui()

    # ─────────────────────────────────────────────────────────────────────
    #  UI construction
    # ─────────────────────────────────────────────────────────────────────

    def build_ui(self):
        shell = ttk.Frame(self.parent, style="App.TFrame")
        shell.pack(fill="both", expand=True)

        build_tool_header(
            shell,
            tr("scanner_title"),
            tr("scanner_btn"),
            tr("scanner_select_hint"),
            badge_text=tr("scanner_scan_mode"),
        )

        body = ttk.Frame(shell, style="App.TFrame")
        body.pack(fill="both", expand=True)

        # ── Left panel ──
        left = ttk.Frame(body, style="Surface.TFrame", padding=14)
        left.pack(side="left", fill="both", expand=True)

        # ── Toolbar row 1: add/remove photos + page nav ──
        toolbar1 = ttk.Frame(left, style="Surface.TFrame")
        toolbar1.pack(fill="x", pady=(0, 6))

        ttk.Button(toolbar1, text=tr("scanner_add_photo"), command=self.add_photos, style="Secondary.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(toolbar1, text=tr("scanner_remove_photo"), command=self.remove_current, style="Ghost.TButton").pack(side="left", padx=(0, 14))

        # Page navigator
        ttk.Button(toolbar1, text="◀", command=self.prev_page, style="Small.TButton", width=3).pack(side="left", padx=(0, 4))
        ttk.Label(toolbar1, textvariable=self.page_label_var, style="Field.TLabel").pack(side="left", padx=(0, 4))
        ttk.Button(toolbar1, text="▶", command=self.next_page, style="Small.TButton", width=3).pack(side="left", padx=(0, 14))

        # Rotation
        ttk.Button(toolbar1, text=tr("scanner_rotate_ccw"), command=self.rotate_ccw, style="Small.TButton").pack(side="left", padx=(0, 4))
        ttk.Button(toolbar1, text=tr("scanner_rotate_cw"), command=self.rotate_cw, style="Small.TButton").pack(side="left", padx=(0, 10))

        # Auto detect + reset
        ttk.Button(toolbar1, text=tr("scanner_auto_detect"), command=self.auto_detect, style="Small.TButton").pack(side="left", padx=(0, 4))
        ttk.Button(toolbar1, text=tr("scanner_reset_corners"), command=self.reset_corners, style="Small.TButton").pack(side="left", padx=(0, 10))
        
        # Fullscreen crop
        ttk.Button(toolbar1, text=tr("scanner_fullscreen_crop"), command=self.open_fullscreen_crop, style="Secondary.TButton").pack(side="left")

        # ── Canvas ──
        canvas_frame = ttk.Frame(left, style="Surface.TFrame")
        canvas_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg=CANVAS_BG, highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        ttk.Label(left, text=tr("scanner_corners_hint"), style="Hint.TLabel").pack(anchor="w", pady=(6, 0))

        # ── Mode + Output row ──
        options_row = ttk.Frame(left, style="Surface.TFrame")
        options_row.pack(fill="x", pady=(10, 0))

        ttk.Label(options_row, text=tr("scanner_scan_mode"), style="Field.TLabel").pack(side="left")
        mode_values = [tr(key) for _mode, key in _MODE_MAP]
        self.mode_combo = ttk.Combobox(
            options_row, textvariable=self.scan_mode_var, values=mode_values,
            state="readonly", width=28, style="Dark.TCombobox",
        )
        self.mode_combo.pack(side="left", padx=(8, 18))
        self.mode_combo.bind("<<ComboboxSelected>>", lambda evt: self.update_preview())

        ttk.Label(options_row, text=tr("scanner_output_pdf"), style="Field.TLabel").pack(side="left")
        self.output_entry = ttk.Entry(options_row, textvariable=self.output_var, style="Dark.TEntry", width=26)
        self.output_entry.pack(side="left", padx=(8, 4), fill="x", expand=True)
        ttk.Button(options_row, text=tr("str_save"), command=self.choose_output, style="Ghost.TButton").pack(side="left")

        # ── Footer ──
        footer = ttk.Frame(left, style="Surface.TFrame")
        footer.pack(fill="x", pady=(14, 0))
        self.action_button = ttk.Button(footer, text=tr("scanner_btn"), command=self.start_scan, style="Convert.TButton")
        self.action_button.pack(side="left")
        self.progress_bar = ttk.Progressbar(footer, mode="indeterminate", style="Convert.Horizontal.TProgressbar", length=220)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(16, 0))

        # ── Right panel: preview + feedback ──
        right = ttk.Frame(body, style="App.TFrame")
        right.pack(side="left", fill="y", padx=(14, 0))

        ttk.Label(right, text=tr("scanner_preview"), style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        self.preview_canvas = tk.Canvas(right, bg=CANVAS_BG, width=260, height=370,
                                         highlightthickness=1, highlightbackground=BORDER_COLOR)
        self.preview_canvas.pack(fill="x")

        self.feedback = InlineFeedback(right)
        self.feedback.pack(fill="x", pady=(12, 0))
        self.feedback.set_info(tr("scanner_scan_mode"), tr("scanner_select_hint"))

    # ─────────────────────────────────────────────────────────────────────
    #  Page management
    # ─────────────────────────────────────────────────────────────────────

    @property
    def current_page(self) -> _PageData | None:
        if 0 <= self.current_index < len(self.pages):
            return self.pages[self.current_index]
        return None

    def _update_page_label(self):
        if not self.pages:
            self.page_label_var.set(tr("scanner_no_pages"))
        else:
            self.page_label_var.set(
                tr("scanner_page_label").format(num=self.current_index + 1, total=len(self.pages))
            )

    def _show_current_page(self):
        self._update_page_label()
        self._redraw_canvas()
        self.update_preview()

    def add_photos(self):
        files = filedialog.askopenfilenames(
            title=tr("scanner_select_photo"),
            filetypes=[(tr("convert_images_label"), "*.png *.jpg *.jpeg *.bmp *.tiff *.webp")],
        )
        if not files:
            return
        for f in files:
            img = cv2.imread(f)
            if img is None:
                continue
            try:
                corners = detect_document_corners(f)
            except Exception:
                h, w = img.shape[:2]
                m = 20
                corners = [(m, m), (w - m, m), (w - m, h - m), (m, h - m)]
            self.pages.append(_PageData(f, img, corners))

        if self.current_index < 0:
            self.current_index = 0

        # auto-suggest output
        if not self.output_var.get().strip() and self.pages:
            base = os.path.splitext(self.pages[0].path)[0]
            self.output_var.set(f"{base}_tarandi.pdf")

        self._show_current_page()
        self.feedback.set_info(
            tr("scanner_crop_area"),
            tr("scanner_page_count").format(count=len(self.pages))
        )

    def remove_current(self):
        if not self.pages or self.current_index < 0:
            return
        del self.pages[self.current_index]
        if not self.pages:
            self.current_index = -1
            self.canvas.delete("all")
            self.preview_canvas.delete("all")
        else:
            self.current_index = min(self.current_index, len(self.pages) - 1)
        self._show_current_page()

    def prev_page(self):
        if self.pages and self.current_index > 0:
            self.current_index -= 1
            self._show_current_page()

    def next_page(self):
        if self.pages and self.current_index < len(self.pages) - 1:
            self.current_index += 1
            self._show_current_page()

    # ─────────────────────────────────────────────────────────────────────
    #  File picking
    # ─────────────────────────────────────────────────────────────────────

    def choose_output(self):
        selected = filedialog.asksaveasfilename(
            title=tr("scanner_output_pdf"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
        )
        if selected:
            self.output_var.set(selected)

    def handle_external_drop(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"):
            img = cv2.imread(file_path)
            if img is None:
                return
            try:
                corners = detect_document_corners(file_path)
            except Exception:
                h, w = img.shape[:2]
                m = 20
                corners = [(m, m), (w - m, m), (w - m, h - m), (m, h - m)]
            self.pages.append(_PageData(file_path, img, corners))
            self.current_index = len(self.pages) - 1
            if not self.output_var.get().strip():
                base = os.path.splitext(file_path)[0]
                self.output_var.set(f"{base}_tarandi.pdf")
            self._show_current_page()

    # ─────────────────────────────────────────────────────────────────────
    #  Rotation
    # ─────────────────────────────────────────────────────────────────────

    def rotate_cw(self):
        pg = self.current_page
        if pg is None:
            return
        pg.rotation = (pg.rotation + 90) % 360
        self._apply_rotation(pg)

    def rotate_ccw(self):
        pg = self.current_page
        if pg is None:
            return
        pg.rotation = (pg.rotation - 90) % 360
        self._apply_rotation(pg)

    def _apply_rotation(self, pg: _PageData):
        pg.display_image = rotate_image(pg.cv_image, pg.rotation)
        h, w = pg.display_image.shape[:2]
        m = 20
        pg.corners = [(m, m), (w - m, m), (w - m, h - m), (m, h - m)]
        self._redraw_canvas()
        self.update_preview()

    def auto_detect(self):
        pg = self.current_page
        if pg is None:
            return
        try:
            if pg.rotation != 0:
                import tempfile
                tmp = os.path.join(tempfile.gettempdir(), "_pdfaura_scan_tmp.png")
                cv2.imwrite(tmp, pg.display_image)
                pg.corners = detect_document_corners(tmp)
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
            else:
                pg.corners = detect_document_corners(pg.path)
        except Exception:
            h, w = pg.display_image.shape[:2]
            m = 20
            pg.corners = [(m, m), (w - m, m), (w - m, h - m), (m, h - m)]
        self._redraw_canvas()
        self.update_preview()

    def reset_corners(self):
        pg = self.current_page
        if pg is None:
            return
        h, w = pg.display_image.shape[:2]
        m = 20
        pg.corners = [(m, m), (w - m, m), (w - m, h - m), (m, h - m)]
        self._redraw_canvas()
        self.update_preview()

    # ─────────────────────────────────────────────────────────────────────
    #  Canvas drawing
    # ─────────────────────────────────────────────────────────────────────

    def _redraw_canvas(self):
        self.canvas.delete("all")
        pg = self.current_page
        if pg is None:
            return

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            self.canvas.after(50, self._redraw_canvas)
            return

        ih, iw = pg.display_image.shape[:2]
        scale = min(cw / iw, ch / ih)
        new_w = int(iw * scale)
        new_h = int(ih * scale)
        self.canvas_scale = scale
        ox = (cw - new_w) // 2
        oy = (ch - new_h) // 2
        self.canvas_offset = (ox, oy)

        if getattr(self, "_last_cw", None) != cw or getattr(self, "_last_ch", None) != ch or getattr(self, "_last_pg", None) != pg:
            rgb = cv2.cvtColor(pg.display_image, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb).resize((new_w, new_h), Image.LANCZOS)
            self.tk_photo = ImageTk.PhotoImage(pil_img)
            self._last_cw = cw
            self._last_ch = ch
            self._last_pg = pg

        self.canvas.create_image(ox, oy, image=self.tk_photo, anchor="nw", tags="bg")

        # polygon
        canvas_pts = []
        for (px, py) in pg.corners:
            canvas_pts.extend([ox + px * scale, oy + py * scale])
        self.canvas.create_polygon(canvas_pts, outline=LINE_COLOR, fill="", width=LINE_WIDTH, dash=(6, 4), tags="poly")

        # corner handles
        for i, (px, py) in enumerate(pg.corners):
            cx = ox + px * scale
            cy = oy + py * scale
            r = CORNER_RADIUS
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                     fill=CORNER_COLOR, outline="#ffffff", width=2, tags=f"corner_{i}")

        if self.dragging_corner is not None and getattr(self, "last_ex", None) is not None:
            self._draw_magnifier(self.canvas, pg, self.dragging_corner, self.last_ex, self.last_ey, scale)

    def _on_canvas_resize(self, event):
        self._redraw_canvas()

    # ─────────────────────────────────────────────────────────────────────
    #  Corner dragging
    # ─────────────────────────────────────────────────────────────────────

    def _canvas_to_image(self, cx, cy):
        ox, oy = self.canvas_offset
        return (cx - ox) / self.canvas_scale, (cy - oy) / self.canvas_scale

    def _on_canvas_press(self, event):
        pg = self.current_page
        if pg is None:
            return
        ox, oy = self.canvas_offset
        for i, (px, py) in enumerate(pg.corners):
            cx = ox + px * self.canvas_scale
            cy = oy + py * self.canvas_scale
            if abs(event.x - cx) < CORNER_RADIUS * 2 and abs(event.y - cy) < CORNER_RADIUS * 2:
                self.dragging_corner = i
                self.canvas.itemconfigure(f"corner_{i}", fill=CORNER_ACTIVE)
                return
        self.dragging_corner = None

    def _on_canvas_drag(self, event):
        pg = self.current_page
        if self.dragging_corner is None or pg is None:
            return
        self.last_ex = event.x
        self.last_ey = event.y
        ix, iy = self._canvas_to_image(event.x, event.y)
        h, w = pg.display_image.shape[:2]
        ix = max(0, min(w, ix))
        iy = max(0, min(h, iy))
        pg.corners[self.dragging_corner] = (int(ix), int(iy))
        self._redraw_canvas()

    def _on_canvas_release(self, event):
        if self.dragging_corner is not None:
            self.canvas.itemconfigure(f"corner_{self.dragging_corner}", fill=CORNER_COLOR)
            self.dragging_corner = None
            self._redraw_canvas() # remove magnifier
            self.update_preview()

    # ─────────────────────────────────────────────────────────────────────
    #  Live preview
    # ─────────────────────────────────────────────────────────────────────

    def _get_selected_mode(self) -> str:
        label = self.scan_mode_var.get()
        for mode, key in _MODE_MAP:
            if tr(key) == label:
                return mode
        return MODE_ORIGINAL

    def update_preview(self):
        pg = self.current_page
        if pg is None:
            return
        try:
            preview_w = 520
            preview_h = int(preview_w * (A4_HEIGHT_PX / A4_WIDTH_PX))
            warped = perspective_warp(pg.display_image, pg.corners, preview_w, preview_h)
            result = apply_scan_mode(warped, self._get_selected_mode())

            pw = self.preview_canvas.winfo_width()
            ph = self.preview_canvas.winfo_height()
            if pw < 10: pw = 260
            if ph < 10: ph = 370

            rh, rw = result.shape[:2]
            scale = min(pw / rw, ph / rh)
            rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb).resize((int(rw * scale), int(rh * scale)), Image.LANCZOS)
            self.preview_photo = ImageTk.PhotoImage(pil_img)
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(pw // 2, ph // 2, image=self.preview_photo, anchor="center")
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────
    #  Scan & export (multi-page)
    # ─────────────────────────────────────────────────────────────────────

    def start_scan(self):
        if not self.pages:
            self.feedback.set_error(tr("str_error"), tr("scanner_no_image"))
            return

        output = self.output_var.get().strip()
        if not output:
            quick_error(tr("err_set_output"), self.action_button, self.progress_bar, self.status_var, self.feedback)
            return

        set_busy(self.action_button, self.progress_bar, True, self.feedback, tr("scanner_running"))
        self.status_var.set(tr("scanner_running"))

        threading.Thread(target=self._run_scan, args=(output,), daemon=True).start()

    def _run_scan(self, output_pdf):
        try:
            mode = self._get_selected_mode()
            processed = []

            for pg in self.pages:
                warped = perspective_warp(pg.display_image, pg.corners, A4_WIDTH_PX, A4_HEIGHT_PX)
                result = apply_scan_mode(warped, mode)
                processed.append(result)

            out_dir = os.path.dirname(output_pdf)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

            scanned_images_to_pdf(processed, output_pdf)

            count = len(processed)
            if count == 1:
                msg = tr("scanner_result").format(output=output_pdf)
            else:
                msg = tr("scanner_result_multi").format(count=count, output=output_pdf)

            self.app_root.after(
                0, operation_done,
                self.action_button, self.progress_bar, self.status_var,
                tr("scanner_done"), msg, None, self.feedback, output_pdf,
            )
        except Exception as exc:
            self.app_root.after(
                0, operation_done,
                self.action_button, self.progress_bar, self.status_var,
                tr("scanner_fail"), None, str(exc), self.feedback, None,
            )

    # ─────────────────────────────────────────────────────────────────────
    #  Fullscreen Crop
    # ─────────────────────────────────────────────────────────────────────

    def open_fullscreen_crop(self):
        pg = self.current_page
        if pg is None:
            return

        self.fs_top = tk.Toplevel(self.app_root)
        self.fs_top.title(tr("scanner_fullscreen_crop"))
        self.fs_top.configure(bg=CANVAS_BG)
        self.fs_top.state('zoomed')  # Maximize on Windows

        header = ttk.Frame(self.fs_top, style="Surface.TFrame", padding=10)
        header.pack(fill="x", side="top")
        
        ttk.Label(header, text=tr("scanner_corners_hint"), style="Hint.TLabel").pack(side="left")
        ttk.Button(header, text=tr("scanner_fullscreen_close"), style="Convert.TButton", 
                   command=self.close_fullscreen_crop).pack(side="right")

        self.fs_canvas = tk.Canvas(self.fs_top, bg=CANVAS_BG, highlightthickness=0, cursor="crosshair")
        self.fs_canvas.pack(fill="both", expand=True)

        self.fs_canvas_scale = 1.0
        self.fs_canvas_offset = (0, 0)
        self.fs_dragging_corner = None
        self.fs_tk_photo = None

        self.fs_canvas.bind("<ButtonPress-1>", self._fs_on_press)
        self.fs_canvas.bind("<B1-Motion>", self._fs_on_drag)
        self.fs_canvas.bind("<ButtonRelease-1>", self._fs_on_release)
        self.fs_canvas.bind("<Configure>", self._fs_on_resize)
        
        # Draw initially
        self._fs_redraw()

    def close_fullscreen_crop(self):
        if hasattr(self, "fs_top") and self.fs_top:
            self.fs_top.destroy()
        self._redraw_canvas()
        self.update_preview()

    def _fs_redraw(self):
        pg = self.current_page
        if not pg or not hasattr(self, "fs_canvas"):
            return

        self.fs_canvas.delete("all")
        cw = self.fs_canvas.winfo_width()
        ch = self.fs_canvas.winfo_height()
        if cw < 10 or ch < 10:
            self.fs_canvas.after(50, self._fs_redraw)
            return

        ih, iw = pg.display_image.shape[:2]
        scale = min(cw / iw, ch / ih)
        new_w = int(iw * scale)
        new_h = int(ih * scale)
        self.fs_canvas_scale = scale
        ox = (cw - new_w) // 2
        oy = (ch - new_h) // 2
        self.fs_canvas_offset = (ox, oy)

        if getattr(self, "_last_fs_cw", None) != cw or getattr(self, "_last_fs_ch", None) != ch or getattr(self, "_last_fs_pg", None) != pg:
            rgb = cv2.cvtColor(pg.display_image, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb).resize((new_w, new_h), Image.LANCZOS)
            self.fs_tk_photo = ImageTk.PhotoImage(pil_img)
            self._last_fs_cw = cw
            self._last_fs_ch = ch
            self._last_fs_pg = pg

        self.fs_canvas.create_image(ox, oy, image=self.fs_tk_photo, anchor="nw", tags="bg")

        canvas_pts = []
        for (px, py) in pg.corners:
            canvas_pts.extend([ox + px * scale, oy + py * scale])
        self.fs_canvas.create_polygon(canvas_pts, outline=LINE_COLOR, fill="", width=3, dash=(6, 4), tags="poly")

        for i, (px, py) in enumerate(pg.corners):
            cx = ox + px * scale
            cy = oy + py * scale
            r = CORNER_RADIUS + 4  # Bigger handle in fullscreen
            self.fs_canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                     fill=CORNER_COLOR, outline="#ffffff", width=2, tags=f"corner_{i}")

        if self.fs_dragging_corner is not None and getattr(self, "last_fs_ex", None) is not None:
            self._draw_magnifier(self.fs_canvas, pg, self.fs_dragging_corner, self.last_fs_ex, self.last_fs_ey, scale)

    def _fs_on_resize(self, event):
        self._fs_redraw()

    def _fs_on_press(self, event):
        pg = self.current_page
        if not pg: return
        ox, oy = self.fs_canvas_offset
        for i, (px, py) in enumerate(pg.corners):
            cx = ox + px * self.fs_canvas_scale
            cy = oy + py * self.fs_canvas_scale
            if abs(event.x - cx) < (CORNER_RADIUS + 4) * 2 and abs(event.y - cy) < (CORNER_RADIUS + 4) * 2:
                self.fs_dragging_corner = i
                self.fs_canvas.itemconfigure(f"corner_{i}", fill=CORNER_ACTIVE)
                return
        self.fs_dragging_corner = None

    def _fs_on_drag(self, event):
        pg = self.current_page
        if self.fs_dragging_corner is None or not pg: return
        ox, oy = self.fs_canvas_offset
        self.last_fs_ex = event.x
        self.last_fs_ey = event.y
        ix = (event.x - ox) / self.fs_canvas_scale
        iy = (event.y - oy) / self.fs_canvas_scale
        h, w = pg.display_image.shape[:2]
        pg.corners[self.fs_dragging_corner] = (int(max(0, min(w, ix))), int(max(0, min(h, iy))))
        self._fs_redraw()

    def _fs_on_release(self, event):
        if self.fs_dragging_corner is not None:
            self.fs_canvas.itemconfigure(f"corner_{self.fs_dragging_corner}", fill=CORNER_COLOR)
            self.fs_dragging_corner = None
            self._fs_redraw() # remove magnifier

    # ─────────────────────────────────────────────────────────────────────
    #  Magnifier UI
    # ─────────────────────────────────────────────────────────────────────

    def _draw_magnifier(self, canvas, pg, corner_idx, ex, ey, scale):
        cx, cy = pg.corners[corner_idx]
        
        # Crop region from original image (simulating 2x zoom on screen)
        crop_sz_im = int(100 / scale)
        x1, y1 = int(cx - crop_sz_im/2), int(cy - crop_sz_im/2)
        x2, y2 = int(cx + crop_sz_im/2), int(cy + crop_sz_im/2)
        
        ih, iw = pg.display_image.shape[:2]
        
        pad_x1, pad_y1 = max(0, -x1), max(0, -y1)
        pad_x2, pad_y2 = max(0, x2 - iw), max(0, y2 - ih)
        
        cropped = pg.display_image[max(0, y1) : min(ih, y2), max(0, x1) : min(iw, x2)]
        if cropped.size == 0: return
        
        if pad_x1 > 0 or pad_y1 > 0 or pad_x2 > 0 or pad_y2 > 0:
            cropped = cv2.copyMakeBorder(cropped, pad_y1, pad_y2, pad_x1, pad_x2, cv2.BORDER_REPLICATE)
            
        mag_size = 200
        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        # NEAREST provides a sharp zoomed pixel look
        pil_mag = Image.fromarray(rgb).resize((mag_size, mag_size), Image.NEAREST)
        
        if canvas == self.canvas:
            self.mag_photo = ImageTk.PhotoImage(pil_mag)
            photo = self.mag_photo
        else:
            self.fs_mag_photo = ImageTk.PhotoImage(pil_mag)
            photo = self.fs_mag_photo
            
        # Position magnifier top-left to pointer to avoid obscuring
        mag_x, mag_y = ex - mag_size//2 - 60, ey - mag_size//2 - 60
        
        # Keep inside canvas
        cw, ch = canvas.winfo_width(), canvas.winfo_height()
        if mag_x < 0: mag_x = ex + 40
        if mag_y < 0: mag_y = ey + 40
        if mag_x + mag_size > cw: mag_x = ex - mag_size - 40
        if mag_y + mag_size > ch: mag_y = ey - mag_size - 40
        
        # Draw Loupe background and image
        canvas.create_rectangle(mag_x-2, mag_y-2, mag_x+mag_size+2, mag_y+mag_size+2, outline="#3b82f6", width=4, fill="#1e293b", tags="mag")
        canvas.create_image(mag_x, mag_y, image=photo, anchor="nw", tags="mag")
        
        # Crosshair inside Loupe
        center_x, center_y = mag_x + mag_size//2, mag_y + mag_size//2
        canvas.create_line(center_x-15, center_y, center_x+15, center_y, fill="#22c55e", width=2, tags="mag")
        canvas.create_line(center_x, center_y-15, center_x, center_y+15, fill="#22c55e", width=2, tags="mag")
        canvas.create_oval(center_x-3, center_y-3, center_x+3, center_y+3, fill="#ef4444", outline="#ef4444", tags="mag")


