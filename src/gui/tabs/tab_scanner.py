"""
Scanner Tab – CamScanner-like document scanning UI  (multi-page)
────────────────────────────────────────────────────────────────
• Add multiple photos → each becomes one PDF page
• Interactive 4-corner cropping on a tk.Canvas (draggable points)
• Rotation controls in the toolbar
• Gamma / scan-mode selector with live preview
• Export all pages to a single multi-page PDF
"""

import logging
import math
import os
import statistics
import threading
import tempfile
import time
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import font as tkfont

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
    rotate_image, imread_unicode, imwrite_unicode,
    scanned_images_to_pdf,
)
from src.core.config_manager import cfg
from src.core.lang_manager import _ as tr   # rename to avoid shadowing
from src.core.scanner_session import ScannerSessionStore, SESSION_VERSION
from src.core.task_manager import TaskContext, CancelledError
from src.gui.helpers import InlineFeedback, ProgressFooter, build_hint_strip, quick_error
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

SESSION_SAVE_DELAY_MS = 400
PAGE_LABEL_MAX = 60


def _clean_label(text):
    """One printable line, trimmed; an empty string means the page is unnamed."""
    text = "".join(ch for ch in str(text) if ch.isprintable() or ch.isspace())
    return " ".join(text.split())[:PAGE_LABEL_MAX]


def _valid_corners(corners):
    if not isinstance(corners, list) or len(corners) != 4:
        return False
    for pt in corners:
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            return False
        for v in pt:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                return False
    return True


class _PageData:
    """Per-page state for one photo in the scan list."""
    __slots__ = ("path", "cv_image", "display_image", "rotation", "corners", "uid", "label")

    def __init__(self, path, cv_image, corners, uid=None, label=""):
        self.path = path
        self.cv_image = cv_image
        self.display_image = cv_image.copy()
        self.rotation = 0
        self.corners = list(corners)
        # Names this page's PNG in the session folder. cv_image must never be
        # changed in place; a page with different pixels needs a new uid.
        self.uid = uid or uuid.uuid4().hex
        self.label = label        # user-given page name shown under the thumbnail


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
        self._task_ctx = None
        self._detecting_corners = False
        self._detect_job_id = 0
        self._detect_controls = []

        # ── tkinter vars ──
        self.output_var = tk.StringVar()
        self.status_var = tk.StringVar(value=tr("str_ready"))
        self.scan_mode_var = tk.StringVar(value=tr("scanner_mode_clean_doc"))
        self.page_label_var = tk.StringVar(value=tr("scanner_no_pages"))
        self._thumb_cache = {}   # id(page) -> ((rotation, corners, w, h), PhotoImage)
        self._debounce_jobs = {}

        # ── page strip interaction ──
        self._strip_press = None          # (page, x, y) of the last press on a thumbnail
        self._strip_dragging = False
        self._strip_drag_xy = (0, 0)      # pointer, strip-canvas widget coords
        self._drag_ghost = None
        self._autoscroll_job = None
        self._rename_page = None
        self._rename_entry = None
        self._sash_drag = None            # [x_root at press, width at press, moved]
        # 0 = auto: the strip takes the room a narrow (portrait) photo leaves free.
        self._strip_auto = not cfg.get("scanner_strip_width", 0)

        # ── session persistence ──
        self._session_save_job = None     # after() id of the pending debounced save
        self._session_restoring = False   # True from "session found" until it is applied
        self._session_meta = None         # read in __init__, applied on first show
        self._session_rev = 0             # bumped on every change; guards the post-export clear
        self._scan_start_rev = None
        self._session_error_shown = False
        self._session_store = ScannerSessionStore(
            cfg.scanner_session_dir,
            enabled=cfg.get("scanner_session_enabled", True),
            on_error=lambda msg: self.app_root.after(0, self._on_session_error, msg),
        )

        self.build_ui()
        self.output_var.trace_add("write", lambda *_args: self._schedule_session_save())
        self._load_session()

    # ─────────────────────────────────────────────────────────────────────
    #  UI construction
    # ─────────────────────────────────────────────────────────────────────

    def build_ui(self):
        shell = ttk.Frame(self.parent, style="App.TFrame")
        shell.pack(fill="both", expand=True)

        build_hint_strip(shell, tr("hint_scanner"))

        body = ttk.Frame(shell, style="App.TFrame")
        body.pack(fill="both", expand=True)

        # ── Left panel ──
        left = ttk.Frame(body, style="Card.TFrame", padding=14)
        left.pack(side="left", fill="both", expand=True)

        # ── Toolbar row 1: photos in/out ──
        toolbar1 = ttk.Frame(left, style="Surface.TFrame")
        toolbar1.pack(fill="x", pady=(0, 8))

        self.add_photo_button = ttk.Button(toolbar1, text="＋ " + tr("scanner_add_photo"), command=self.add_photos, style="Secondary.TButton")
        self.add_photo_button.pack(side="left", padx=(0, 6))
        self.remove_photo_button = ttk.Button(toolbar1, text=tr("scanner_remove_photo"), command=self.remove_current, style="Ghost.TButton")
        self.remove_photo_button.pack(side="left", padx=(0, 6))
        ttk.Button(toolbar1, text=tr("scanner_clear_all"), command=self.clear_all_pages, style="Ghost.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(toolbar1, text=tr("scanner_fullscreen_crop"), command=self.open_fullscreen_crop, style="Ghost.TButton").pack(side="right")

        # ── Toolbar row 2: per-page corrections ──
        toolbar2 = ttk.Frame(left, style="Surface.TFrame")
        toolbar2.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar2, text=tr("scanner_rotate_ccw"), command=self.rotate_ccw, style="Small.TButton").pack(side="left", padx=(0, 4))
        ttk.Button(toolbar2, text=tr("scanner_rotate_cw"), command=self.rotate_cw, style="Small.TButton").pack(side="left", padx=(0, 12))
        ttk.Button(toolbar2, text=tr("scanner_auto_detect"), command=self.auto_detect, style="Small.TButton").pack(side="left", padx=(0, 4))
        ttk.Button(toolbar2, text=tr("scanner_reset_corners"), command=self.reset_corners, style="Small.TButton").pack(side="left")

        # ── Page strip (left) | sash | crop canvas (right) ──
        work = ttk.Frame(left, style="Surface.TFrame")
        work.pack(fill="both", expand=True)
        self.work_frame = work

        self._caption_font = tkfont.Font(root=self.app_root, family="Segoe UI", size=9)
        self._caption_font_sel = tkfont.Font(root=self.app_root, family="Segoe UI Semibold", size=9)

        strip_w = self._STRIP_MIN_W if self._strip_auto else max(self._STRIP_MIN_W, int(cfg.get("scanner_strip_width", 0)))
        strip = ttk.Frame(work, style="Surface.TFrame", width=strip_w)
        strip.pack(side="left", fill="y")
        strip.pack_propagate(False)
        self.strip_frame = strip
        ttk.Label(strip, text=tr("scanner_pages"), style="Section.TLabel").pack(anchor="w")
        ttk.Label(strip, textvariable=self.page_label_var, style="Hint.TLabel").pack(anchor="w", pady=(2, 0))
        self.strip_hint_widget = ttk.Label(strip, style="Hint.TLabel", justify="left")
        self.strip_hint_widget.pack(anchor="w", pady=(0, 6))
        strip_buttons = ttk.Frame(strip, style="Surface.TFrame")
        strip_buttons.pack(side="bottom", fill="x", pady=(8, 0))
        self.move_up_button = ttk.Button(strip_buttons, text=tr("scanner_move_up"), command=lambda: self.move_page(-1), style="Small.TButton")
        self.move_down_button = ttk.Button(strip_buttons, text=tr("scanner_move_down"), command=lambda: self.move_page(1), style="Small.TButton")
        self._strip_wide = None
        self._relayout_strip_header(strip_w)

        self.strip_canvas = tk.Canvas(strip, bg=SURFACE_ALT, highlightthickness=1, highlightbackground=BORDER_COLOR,
                                      width=128, yscrollincrement=20)
        self.strip_canvas.pack(fill="both", expand=True)
        c = self.strip_canvas
        c.bind("<ButtonPress-1>", self._on_strip_press)
        c.bind("<B1-Motion>", self._on_strip_motion)
        c.bind("<ButtonRelease-1>", self._on_strip_release)
        c.bind("<Double-Button-1>", self._on_strip_double)
        c.bind("<Button-3>", self._on_strip_menu)
        c.bind("<MouseWheel>", lambda e: c.yview_scroll(int(-e.delta / 120) * 3, "units"))
        c.bind("<Up>", lambda e: self._select_relative(-self._strip_layout()[0]))
        c.bind("<Down>", lambda e: self._select_relative(self._strip_layout()[0]))
        c.bind("<Left>", lambda e: self._select_relative(-1))
        c.bind("<Right>", lambda e: self._select_relative(1))
        c.bind("<F2>", lambda e: self.rename_current())
        c.bind("<Escape>", lambda e: self._end_strip_drag())
        c.bind("<Configure>", lambda e: self._debounce("strip", 60, self._refresh_strip))

        # Drag to resize the strip; double-click returns to auto width.
        self.strip_sash = tk.Frame(work, width=self._SASH_W, bg=SURFACE_COLOR, cursor="sb_h_double_arrow")
        self.strip_sash.pack(side="left", fill="y")
        self._sash_grip = tk.Frame(self.strip_sash, width=4, height=48, bg=BORDER_COLOR, cursor="sb_h_double_arrow")
        self._sash_grip.place(relx=0.5, rely=0.5, anchor="center")
        for w in (self.strip_sash, self._sash_grip):
            w.bind("<ButtonPress-1>", self._on_sash_press)
            w.bind("<B1-Motion>", self._on_sash_drag)
            w.bind("<ButtonRelease-1>", self._on_sash_release)
            w.bind("<Double-Button-1>", self._on_sash_double)
            w.bind("<Enter>", lambda e: self._sash_grip.configure(bg=PRIMARY_ACCENT))
            w.bind("<Leave>", lambda e: self._sash_drag or self._sash_grip.configure(bg=BORDER_COLOR))
        work.bind("<Configure>", lambda e: self._debounce("fit", 60, self._fit_strip))

        self._detect_controls = [
            child
            for row in (toolbar1, toolbar2)
            for child in row.winfo_children()
            if isinstance(child, ttk.Button)
        ]

        canvas_frame = ttk.Frame(work, style="Surface.TFrame")
        canvas_frame.pack(side="left", fill="both", expand=True)

        # width=1: never request more room than the strip leaves, or pack would
        # squeeze the preview panel on the right when the strip is wide.
        self.canvas = tk.Canvas(canvas_frame, bg=CANVAS_BG, highlightthickness=0, cursor="crosshair", width=1)
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
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_changed)

        ttk.Label(options_row, text=tr("scanner_output_pdf"), style="Field.TLabel").pack(side="left")
        self.output_entry = ttk.Entry(options_row, textvariable=self.output_var, style="Dark.TEntry", width=26)
        self.output_entry.pack(side="left", padx=(8, 4), fill="x", expand=True)
        ttk.Button(options_row, text=tr("str_save"), command=self.choose_output, style="Ghost.TButton").pack(side="left")

        self.footer = ProgressFooter(left, tr("scanner_btn"), self.start_scan, button_style="Convert.TButton", progress_style="Convert.Horizontal.TProgressbar")
        self.footer.pack(fill="x", pady=(14, 0))

        # ── Right panel: preview + feedback ──
        right = ttk.Frame(body, style="App.TFrame")
        right.pack(side="left", fill="y", padx=(14, 0))

        ttk.Label(right, text=tr("scanner_preview"), style="PageEyebrow.TLabel").pack(anchor="w", pady=(0, 6))
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
            text = tr("scanner_no_pages")
        else:
            text = tr("scanner_page_label").format(num=self.current_index + 1, total=len(self.pages))
            pg = self.current_page
            if pg is not None and pg.label:
                text += f" · {pg.label}"
        self._page_label_text = text
        self._fit_page_label(self._strip_width())

    def _fit_page_label(self, strip_width):
        # One line only: a long page name must not push the thumbnails down.
        text = getattr(self, "_page_label_text", self.page_label_var.get())
        self.page_label_var.set(self._ellipsize(text, self._caption_font, strip_width - 4))

    def _show_current_page(self):
        self._update_page_label()
        self._fit_strip()
        self._redraw_canvas()
        self.update_preview()

    def _debounce(self, key, delay_ms, fn):
        job = self._debounce_jobs.pop(key, None)
        if job is not None:
            self.app_root.after_cancel(job)

        def run():
            self._debounce_jobs.pop(key, None)
            fn()
        self._debounce_jobs[key] = self.app_root.after(delay_ms, run)

    def _default_corners_for_shape(self, h, w):
        margin = max(0, min(20, min(h, w) // 12))
        right = max(0, w - 1 - margin)
        bottom = max(0, h - 1 - margin)
        return [(margin, margin), (right, margin), (right, bottom), (margin, bottom)]

    def _default_corners_for_image(self, img):
        h, w = img.shape[:2]
        return self._default_corners_for_shape(h, w)

    def _add_image_pages(self, files):
        if self._detecting_corners:
            self.feedback.set_info(tr("scanner_crop_area"), tr("scanner_detect_busy"))
            return 0

        jobs = []
        first_new_page = None
        for f in files:
            img = imread_unicode(f)
            if img is None:
                continue
            page = _PageData(f, img, self._default_corners_for_image(img))
            self.pages.append(page)
            if first_new_page is None:
                first_new_page = page
            jobs.append({
                "page": page,
                "path": f,
                "image": None,
                "shape": img.shape[:2],
            })

        if not jobs:
            return 0

        # Jump to the first newly added photo so its corners can be checked.
        self.current_index = self.pages.index(first_new_page)

        if not self.output_var.get().strip() and self.pages:
            base = os.path.splitext(self.pages[0].path)[0]
            self.output_var.set(f"{base}_tarandi.pdf")

        self._show_current_page()
        self.feedback.set_info(
            tr("scanner_crop_area"),
            tr("scanner_page_count").format(count=len(self.pages))
        )
        self._schedule_session_save()
        self._start_corner_detection(jobs)
        return len(jobs)

    def _set_corner_detection_busy(self, busy, message=None):
        state = "disabled" if busy else "normal"
        for control in self._detect_controls:
            try:
                control.config(state=state)
            except tk.TclError:
                pass

        if busy:
            msg = message or tr("scanner_detecting")
            self.footer.action_button.config(state="disabled")
            self.footer.progress_bar.config(mode="indeterminate")
            self.footer.progress_bar["value"] = 0
            self.footer.progress_bar.start(12)
            self.footer.pct_label.config(text=msg)
            self.feedback.set_busy(msg)
            self.status_var.set(msg)
        else:
            self.footer.progress_bar.stop()
            self.footer.progress_bar.config(mode="determinate")
            self.footer.progress_bar["value"] = 0
            self.footer.pct_label.config(text="")
            self.footer.action_button.config(state="normal")

    def _start_corner_detection(self, jobs):
        if not jobs:
            return
        if self._detecting_corners:
            self.feedback.set_info(tr("scanner_crop_area"), tr("scanner_detect_busy"))
            return

        self._detect_job_id += 1
        job_id = self._detect_job_id
        self._detecting_corners = True
        self._set_corner_detection_busy(
            True,
            tr("scanner_detecting_progress").format(current=0, total=len(jobs))
        )
        threading.Thread(target=self._run_corner_detection, args=(job_id, jobs), daemon=True).start()

    def _run_corner_detection(self, job_id, jobs):
        errors = 0
        total = len(jobs)
        for completed, job in enumerate(jobs, start=1):
            corners = None
            tmp_path = None
            try:
                if job["image"] is not None:
                    fd, tmp_path = tempfile.mkstemp(prefix="pdfaura_scan_", suffix=".png")
                    os.close(fd)
                    imwrite_unicode(tmp_path, job["image"])
                    corners = detect_document_corners(tmp_path)
                else:
                    corners = detect_document_corners(job["path"])
            except Exception:
                errors += 1
                h, w = job["shape"]
                corners = self._default_corners_for_shape(h, w)
            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

            self.app_root.after(
                0,
                self._apply_corner_detection_result,
                job_id,
                job["page"],
                corners,
                completed,
                total,
            )

        self.app_root.after(0, self._finish_corner_detection, job_id, total, errors)

    def _apply_corner_detection_result(self, job_id, page, corners, completed, total):
        if job_id != self._detect_job_id:
            return
        if page not in self.pages:
            return

        page.corners = list(corners)
        self._schedule_session_save()
        if page is self.current_page:
            self._redraw_canvas()
            self.update_preview()

        self.footer.pct_label.config(
            text=tr("scanner_detecting_progress").format(current=completed, total=total)
        )

    def _finish_corner_detection(self, job_id, total, errors):
        if job_id != self._detect_job_id:
            return

        self._detecting_corners = False
        self._set_corner_detection_busy(False)
        detected = max(0, total - errors)
        self.feedback.set_info(
            tr("scanner_crop_area"),
            tr("scanner_detect_done").format(count=detected)
        )
        self.status_var.set(tr("str_ready"))

    def add_photos(self):
        files = filedialog.askopenfilenames(
            title=tr("scanner_select_photo"),
            filetypes=[(tr("convert_images_label"), "*.png *.jpg *.jpeg *.bmp *.tiff *.webp")],
        )
        if not files:
            return
        self._add_image_pages(files)

    def remove_current(self):
        if not self.pages or self.current_index < 0:
            return
        self._thumb_cache.pop(id(self.pages[self.current_index]), None)
        del self.pages[self.current_index]
        if not self.pages:
            self.current_index = -1
            self.canvas.delete("all")
            self.preview_canvas.delete("all")
        else:
            self.current_index = min(self.current_index, len(self.pages) - 1)
        self._show_current_page()
        self._schedule_session_save()

    def clear_all_pages(self):
        """Drop every page and the saved session to start a new document."""
        if not self.pages or self._detecting_corners:
            return
        if not messagebox.askyesno(tr("scanner_clear_all"), tr("scanner_clear_all_confirm"), parent=self.app_root):
            return
        self.pages.clear()
        self._thumb_cache.clear()
        self.current_index = -1
        self.canvas.delete("all")
        self.preview_canvas.delete("all")
        self._show_current_page()
        self._clear_session()
        self.feedback.set_info(tr("scanner_crop_area"), tr("scanner_select_hint"))

    def prev_page(self):
        if self.pages and self.current_index > 0:
            self.current_index -= 1
            self._show_current_page()

    def next_page(self):
        if self.pages and self.current_index < len(self.pages) - 1:
            self.current_index += 1
            self._show_current_page()

    def move_page(self, step):
        """Move the selected page earlier (-1) or later (+1) in the PDF order."""
        # Detection results are matched by page object, so reordering while
        # corners are still being detected is safe.
        i = self.current_index
        j = i + step
        if not self.pages or not (0 <= i < len(self.pages)) or not (0 <= j < len(self.pages)):
            return
        self.pages[i], self.pages[j] = self.pages[j], self.pages[i]
        self.current_index = j
        self._show_current_page()
        self._schedule_session_save()

    def _move_page_to(self, page, insert_at):
        """Move *page* so it lands before the page currently at *insert_at*
        (len(self.pages) = to the end)."""
        if page not in self.pages:
            return
        src = self.pages.index(page)
        dst = insert_at - 1 if insert_at > src else insert_at
        dst = max(0, min(len(self.pages) - 1, dst))
        if dst == src:
            return
        self.pages.insert(dst, self.pages.pop(src))
        self.current_index = dst
        self._show_current_page()
        self._schedule_session_save()

    def _remove_page(self, page):
        if page in self.pages:
            self.current_index = self.pages.index(page)
            self.remove_current()

    def _select_relative(self, delta):
        if self.pages:
            index = max(0, min(len(self.pages) - 1, self.current_index + delta))
            if index != self.current_index:
                self.current_index = index
                self._show_current_page()
        return "break"

    # ─────────────────────────────────────────────────────────────────────
    #  Page strip: thumbnail grid, drag to reorder, rename, resizable
    # ─────────────────────────────────────────────────────────────────────

    _STRIP_MIN_W = 132
    _CANVAS_MIN_W = 320       # the crop canvas never gets narrower than this
    _SASH_W = 10
    _FIT_MARGIN = 8           # room kept on each side of the photo in auto width
    _THUMB_TARGET_W = 112     # a new column opens once there is room for this
    _THUMB_MIN_W = 72
    _THUMB_MAX_W = 180
    _THUMB_GAP = 12
    _THUMB_TOP = 8
    _THUMB_CAPTION_H = 22
    _THUMB_ASPECT = A4_HEIGHT_PX / A4_WIDTH_PX
    _DRAG_START_PX = 6
    _AUTOSCROLL_ZONE = 28

    def _strip_layout(self):
        """(cols, thumb_w, thumb_h, cell_w, cell_h, left) for the strip's current width."""
        width = max(int(self.strip_canvas.winfo_width()), self._STRIP_MIN_W - 4)
        gap = self._THUMB_GAP
        cols = max(1, (width - gap) // (self._THUMB_TARGET_W + gap))
        cols = max(1, min(cols, len(self.pages)))    # few pages → fewer, bigger thumbnails
        thumb_w = (width - gap * (cols + 1)) // cols
        # Steps of 4 px keep the thumbnail cache warm while the strip is resized.
        thumb_w = max(self._THUMB_MIN_W, min(self._THUMB_MAX_W, thumb_w)) // 4 * 4
        thumb_h = int(round(thumb_w * self._THUMB_ASPECT))
        cell_w = thumb_w + gap
        cell_h = thumb_h + self._THUMB_CAPTION_H + gap
        left = max(gap // 2, (width - (cols * cell_w - gap)) // 2)
        return cols, thumb_w, thumb_h, cell_w, cell_h, left

    def _cell_xy(self, index, layout):
        """Top-left corner of thumbnail *index*, canvas coordinates."""
        cols, _tw, _th, cell_w, cell_h, left = layout
        row, col = divmod(index, cols)
        return left + col * cell_w, self._THUMB_TOP + row * cell_h

    def _strip_index_at(self, x, y, layout):
        cols, _tw, _th, cell_w, cell_h, left = layout
        half_gap = self._THUMB_GAP / 2
        col = int((x - left + half_gap) // cell_w)
        row = int((y - self._THUMB_TOP + half_gap) // cell_h)
        if not (0 <= col < cols) or row < 0:
            return None
        index = row * cols + col
        return index if index < len(self.pages) else None

    def _strip_drop_slot(self, x, y, layout):
        """Gap nearest to (x, y) as (insert_index, row, col)."""
        cols, _tw, _th, cell_w, cell_h, left = layout
        n = len(self.pages)
        half_gap = self._THUMB_GAP / 2
        if cols == 1:
            k = max(0, min(n, int(round((y - self._THUMB_TOP + half_gap) / cell_h))))
            return k, k, 0
        rows = max(1, -(-n // cols))
        row = max(0, min(rows - 1, int((y - self._THUMB_TOP + half_gap) // cell_h)))
        col = max(0, min(cols, int(round((x - left + half_gap) / cell_w))))
        col = min(col, n - row * cols)
        return row * cols + col, row, col

    def _page_thumb(self, pg, thumb_w, thumb_h):
        key = (pg.rotation, tuple(pg.corners), thumb_w, thumb_h)
        cached = self._thumb_cache.get(id(pg))
        if cached and cached[0] == key:
            return cached[1]
        warped = perspective_warp(pg.display_image, pg.corners, thumb_w * 2, thumb_h * 2)
        small = cv2.resize(warped, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)
        photo = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB)))
        self._thumb_cache[id(pg)] = (key, photo)
        return photo

    @staticmethod
    def _ellipsize(text, font, max_px):
        if font.measure(text) <= max_px:
            return text
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if font.measure(text[:mid] + "…") <= max_px:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo].rstrip() + "…"

    def _refresh_strip(self):
        c = self.strip_canvas
        c.delete("strip", "drag")          # the rename entry ("rename") survives redraws
        layout = self._strip_layout()
        cols, tw, th, cell_w, cell_h, _left = layout
        for i, pg in enumerate(self.pages):
            x, y = self._cell_xy(i, layout)
            selected = i == self.current_index
            if selected:
                c.create_rectangle(x - 5, y - 4, x + tw + 5, y + th + 4, outline=PRIMARY_ACCENT, width=3, tags="strip")
            try:
                c.create_image(x, y, image=self._page_thumb(pg, tw, th), anchor="nw", tags="strip")
            except Exception:
                c.create_rectangle(x, y, x + tw, y + th, fill="#dfe6ee", outline="", tags="strip")
            font = self._caption_font_sel if selected else self._caption_font
            caption = str(i + 1) + (f" · {pg.label}" if pg.label else "")
            c.create_text(x + tw / 2, y + th + 13, text=self._ellipsize(caption, font, cell_w - 4),
                          fill=PRIMARY_ACCENT if selected else MUTED_TEXT, font=font, tags="strip")

        width = max(int(c.winfo_width()), self._STRIP_MIN_W - 4)
        total_h = self._THUMB_TOP + -(-len(self.pages) // cols) * cell_h
        c.configure(scrollregion=(0, 0, width, max(total_h, 1)))
        self._place_rename_entry(layout)

        if self._strip_dragging:
            self._draw_drag_overlay(layout)
        elif self.pages and 0 <= self.current_index < len(self.pages) and total_h > 0:
            # keep the selected page in view
            view_h = max(1, c.winfo_height())
            _x, top = self._cell_xy(self.current_index, layout)
            first, last = c.yview()
            if top < first * total_h or top + cell_h > last * total_h:
                c.yview_moveto(max(0.0, (top - (view_h - cell_h) / 2) / total_h))

    # ── drag to reorder ──────────────────────────────────────────────────

    def _on_strip_press(self, event):
        c = self.strip_canvas
        c.focus_set()
        self._finish_rename()
        self._strip_press = None
        index = self._strip_index_at(c.canvasx(event.x), c.canvasy(event.y), self._strip_layout())
        if index is None:
            return
        self._strip_press = (self.pages[index], event.x, event.y)
        if index != self.current_index:
            self.current_index = index
            self._show_current_page()

    def _on_strip_motion(self, event):
        if self._strip_press is None:
            return
        page, x0, y0 = self._strip_press
        if not self._strip_dragging:
            if abs(event.x - x0) < self._DRAG_START_PX and abs(event.y - y0) < self._DRAG_START_PX:
                return
            if page not in self.pages:
                self._strip_press = None
                return
            self._strip_dragging = True
            self._drag_ghost = self._make_drag_ghost(page)
            self.strip_canvas.configure(cursor="fleur")
        self._strip_drag_xy = (event.x, event.y)
        self._draw_drag_overlay()
        if self._autoscroll_job is None and self._autoscroll_step():
            self._autoscroll_job = self.strip_canvas.after(40, self._autoscroll_tick)

    def _on_strip_release(self, event):
        press, dragging = self._strip_press, self._strip_dragging
        self._end_strip_drag()
        if press is None or not dragging:
            return
        c = self.strip_canvas
        if event.x < -40 or event.x > c.winfo_width() + 40:
            return      # dropped outside the strip: cancel
        y = max(0, min(c.winfo_height(), event.y))
        insert_at, _row, _col = self._strip_drop_slot(c.canvasx(event.x), c.canvasy(y), self._strip_layout())
        self._move_page_to(press[0], insert_at)

    def _end_strip_drag(self):
        self._strip_press = None
        self._strip_dragging = False
        self._drag_ghost = None
        if self._autoscroll_job is not None:
            self.strip_canvas.after_cancel(self._autoscroll_job)
            self._autoscroll_job = None
        self.strip_canvas.delete("drag")
        self.strip_canvas.configure(cursor="")

    def _make_drag_ghost(self, page):
        gw = 56
        gh = int(round(gw * self._THUMB_ASPECT))
        try:
            warped = perspective_warp(page.display_image, page.corners, gw * 2, gh * 2)
            small = cv2.resize(warped, (gw, gh), interpolation=cv2.INTER_AREA)
            return ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB)))
        except Exception:
            return None

    def _draw_drag_overlay(self, layout=None):
        c = self.strip_canvas
        c.delete("drag")
        page = self._strip_press[0] if self._strip_press else None
        if page is None or page not in self.pages:
            return
        layout = layout or self._strip_layout()
        cols, tw, th, cell_w, cell_h, left = layout
        half_gap = self._THUMB_GAP / 2

        # fade the page being moved
        sx, sy = self._cell_xy(self.pages.index(page), layout)
        c.create_rectangle(sx, sy, sx + tw, sy + th, fill=SURFACE_ALT, stipple="gray50",
                           outline=MUTED_TEXT, dash=(4, 3), tags="drag")

        # where it will land
        ex, ey = self._strip_drag_xy
        x, y = c.canvasx(ex), c.canvasy(ey)
        _insert_at, row, col = self._strip_drop_slot(x, y, layout)
        if cols == 1:
            ly = self._THUMB_TOP + row * cell_h - half_gap
            c.create_line(left - 4, ly, left + tw + 4, ly, fill=PRIMARY_ACCENT, width=4, capstyle="round", tags="drag")
        else:
            lx = left + col * cell_w - half_gap
            ly = self._THUMB_TOP + row * cell_h
            c.create_line(lx, ly - 4, lx, ly + th + 4, fill=PRIMARY_ACCENT, width=4, capstyle="round", tags="drag")

        # small copy under the pointer
        if self._drag_ghost is not None:
            gw, gh = self._drag_ghost.width(), self._drag_ghost.height()
            gx = x + 14 if ex + 14 + gw < c.winfo_width() else x - 14 - gw
            gy = y + 10
            c.create_image(gx, gy, image=self._drag_ghost, anchor="nw", tags="drag")
            c.create_rectangle(gx - 1, gy - 1, gx + gw + 1, gy + gh + 1, outline=PRIMARY_ACCENT, width=2, tags="drag")

    def _autoscroll_step(self):
        if not self._strip_dragging:
            return 0
        y = self._strip_drag_xy[1]
        if y < self._AUTOSCROLL_ZONE:
            return -1
        if y > self.strip_canvas.winfo_height() - self._AUTOSCROLL_ZONE:
            return 1
        return 0

    def _autoscroll_tick(self):
        self._autoscroll_job = None
        step = self._autoscroll_step()
        if step:
            self.strip_canvas.yview_scroll(step, "units")
            self._draw_drag_overlay()
            self._autoscroll_job = self.strip_canvas.after(40, self._autoscroll_tick)

    # ── rename ───────────────────────────────────────────────────────────

    def rename_current(self):
        if self.current_page is not None:
            self._start_rename(self.current_page)
        return "break"

    def _on_strip_double(self, event):
        c = self.strip_canvas
        index = self._strip_index_at(c.canvasx(event.x), c.canvasy(event.y), self._strip_layout())
        if index is None:
            return
        self._strip_press = None
        if index != self.current_index:
            self.current_index = index
            self._show_current_page()
        self._start_rename(self.pages[index])

    def _start_rename(self, page):
        self._finish_rename()
        if page not in self.pages:
            return
        entry = tk.Entry(self.strip_canvas, font=self._caption_font, justify="center", relief="flat",
                         bg=SURFACE_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
                         highlightthickness=2, highlightcolor=PRIMARY_ACCENT, highlightbackground=PRIMARY_ACCENT)
        entry.insert(0, page.label)
        entry.select_range(0, "end")
        entry.bind("<Return>", lambda e: self._finish_rename(refocus=True))
        entry.bind("<KP_Enter>", lambda e: self._finish_rename(refocus=True))
        entry.bind("<Escape>", lambda e: self._finish_rename(commit=False, refocus=True))
        entry.bind("<Tab>", lambda e: self._rename_step(1))
        entry.bind("<Shift-Tab>", lambda e: self._rename_step(-1))
        entry.bind("<FocusOut>", lambda e: self._finish_rename())
        self._rename_page = page
        self._rename_entry = entry
        self._place_rename_entry(self._strip_layout())
        entry.focus_set()

    def _place_rename_entry(self, layout):
        entry, page = self._rename_entry, self._rename_page
        if entry is None:
            return
        if page not in self.pages:
            self._finish_rename(commit=False)
            return
        _cols, tw, th, cell_w, _cell_h, _left = layout
        x, y = self._cell_xy(self.pages.index(page), layout)
        c = self.strip_canvas
        width = max(cell_w - 2, 96)
        if c.find_withtag("rename"):
            c.coords("rename", x + tw / 2, y + th + 2)
            c.itemconfigure("rename", width=width)
        else:
            c.create_window(x + tw / 2, y + th + 2, window=entry, width=width, anchor="n", tags="rename")

    def _finish_rename(self, commit=True, refocus=False):
        entry, page = self._rename_entry, self._rename_page
        if entry is None:
            return "break"
        self._rename_entry = self._rename_page = None     # before destroy(): FocusOut re-enters
        text = entry.get()
        self.strip_canvas.delete("rename")
        entry.destroy()
        if refocus:
            self.strip_canvas.focus_set()
        if commit and page in self.pages:
            label = _clean_label(text)
            if label != page.label:
                page.label = label
                self._update_page_label()
                self._schedule_session_save()
        self._refresh_strip()
        return "break"

    def _rename_step(self, step):
        """Tab / Shift+Tab: save this name and go straight to the next page's."""
        page = self._rename_page
        self._finish_rename()
        if page in self.pages:
            index = self.pages.index(page) + step
            if 0 <= index < len(self.pages):
                self.current_index = index
                self._show_current_page()
                self._start_rename(self.pages[index])
                return "break"
        self.strip_canvas.focus_set()
        return "break"

    def _on_strip_menu(self, event):
        c = self.strip_canvas
        index = self._strip_index_at(c.canvasx(event.x), c.canvasy(event.y), self._strip_layout())
        if index is None:
            return
        self._finish_rename()
        if index != self.current_index:
            self.current_index = index
            self._show_current_page()
        page = self.pages[index]
        menu = tk.Menu(c, tearoff=0)
        # after(): let the menu release focus first, or the new entry loses it at once.
        menu.add_command(label=tr("scanner_page_rename"), accelerator="F2",
                         command=lambda: self.app_root.after(50, self._start_rename, page))
        menu.add_command(label=tr("scanner_page_to_start"), command=lambda: self._move_page_to(page, 0))
        menu.add_command(label=tr("scanner_page_to_end"), command=lambda: self._move_page_to(page, len(self.pages)))
        menu.add_separator()
        menu.add_command(label=tr("scanner_remove_photo"), command=lambda: self._remove_page(page),
                         state="disabled" if self._detecting_corners else "normal")
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ── resizable strip ──────────────────────────────────────────────────

    def _strip_width(self):
        return int(self.strip_frame.cget("width"))

    def _set_strip_width(self, width):
        work_w = self.work_frame.winfo_width()
        if work_w > 1:
            width = min(width, work_w - self._SASH_W - self._CANVAS_MIN_W)
        width = int(max(self._STRIP_MIN_W, width))
        if width != self._strip_width():
            self.strip_frame.configure(width=width)
            self._relayout_strip_header(width)

    def _relayout_strip_header(self, width):
        """Narrow strip: hint on two short lines, buttons stacked.
        Wide strip: one hint line, buttons side by side."""
        self._fit_page_label(width)
        wide = width >= 260
        if wide == self._strip_wide:
            return
        self._strip_wide = wide
        sep = " · " if wide else "\n"
        self.strip_hint_widget.configure(text=tr("scanner_strip_hint_drag") + sep + tr("scanner_strip_hint_name"))
        self.move_up_button.pack_forget()
        self.move_down_button.pack_forget()
        if wide:
            self.move_up_button.pack(side="left", fill="x", expand=True, padx=(0, 3))
            self.move_down_button.pack(side="left", fill="x", expand=True, padx=(3, 0))
        else:
            self.move_up_button.pack(fill="x")
            self.move_down_button.pack(fill="x", pady=(4, 0))

    def _fit_strip(self):
        """Auto width: the strip takes the empty room beside a narrow (e.g. 9:16)
        photo. Manual width: keep the user's choice, clamped to the window."""
        if not self._strip_auto:
            self._set_strip_width(int(cfg.get("scanner_strip_width", 0)) or self._STRIP_MIN_W)
            return
        work_w = self.work_frame.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if work_w < 100 or canvas_h < 50:
            return      # not laid out yet; <Configure> calls again
        if not self.pages:
            self._set_strip_width(self._STRIP_MIN_W)
            return
        # Median, so one odd landscape page doesn't reshape a portrait document.
        aspect = statistics.median([pg.display_image.shape[1] / pg.display_image.shape[0] for pg in self.pages])
        photo_w = int(canvas_h * aspect) + 2 * self._FIT_MARGIN
        self._set_strip_width(work_w - self._SASH_W - photo_w)

    def _on_sash_press(self, event):
        self._sash_drag = [event.x_root, self._strip_width(), False]
        self._sash_grip.configure(bg=PRIMARY_ACCENT)

    def _on_sash_drag(self, event):
        if not self._sash_drag:
            return
        x0, w0, _moved = self._sash_drag
        if abs(event.x_root - x0) >= 2:
            self._sash_drag[2] = True
        self._set_strip_width(w0 + event.x_root - x0)

    def _on_sash_release(self, _event):
        drag, self._sash_drag = self._sash_drag, None
        self._sash_grip.configure(bg=BORDER_COLOR)
        if drag and drag[2]:
            self._strip_auto = False
            cfg.set("scanner_strip_width", self._strip_width())

    def _on_sash_double(self, _event):
        self._strip_auto = True
        cfg.set("scanner_strip_width", 0)
        self._fit_strip()

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
        self.handle_external_drop_many([file_path])

    def handle_external_drop_many(self, file_paths):
        # All dropped photos go in as one batch; one-by-one adds would be
        # rejected while the first photo's corners are still being detected.
        images = [p for p in file_paths
                  if os.path.splitext(p)[1].lower() in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp")]
        if images:
            self._add_image_pages(images)

    # ─────────────────────────────────────────────────────────────────────
    #  Rotation
    # ─────────────────────────────────────────────────────────────────────

    def rotate_cw(self):
        pg = self.current_page
        if pg is None:
            return
        pg.rotation = (pg.rotation + 90) % 360
        self._apply_rotation(pg, 90)

    def rotate_ccw(self):
        pg = self.current_page
        if pg is None:
            return
        pg.rotation = (pg.rotation - 90) % 360
        self._apply_rotation(pg, -90)

    def _apply_rotation(self, pg: _PageData, angle_step=90):
        # We need the dimensions BEFORE rotation to transform corners correctly
        old_h, old_w = pg.display_image.shape[:2]
        pg.display_image = rotate_image(pg.cv_image, pg.rotation)
        new_h, new_w = pg.display_image.shape[:2]

        # Rotate corners
        new_corners = []
        for (x, y) in pg.corners:
            if angle_step == 90:
                new_corners.append((new_w - y, x))
            elif angle_step == -90:
                new_corners.append((y, new_h - x))
            else:
                new_corners.append((x, y))
        # The quad turned with the photo, so its first point is no longer the
        # top-left one. perspective_warp maps corners[0] to the output's top-left,
        # so without re-anchoring the preview and PDF keep the old orientation.
        # CW: the old bottom-left becomes top-left; CCW: the old top-right does.
        if angle_step == 90:
            new_corners = new_corners[-1:] + new_corners[:-1]
        elif angle_step == -90:
            new_corners = new_corners[1:] + new_corners[:1]
        pg.corners = new_corners

        self._fit_strip()     # the photo's shape changed
        self._redraw_canvas()
        self.update_preview()
        self._schedule_session_save()

    def auto_detect(self):
        pg = self.current_page
        if pg is None:
            return
        if self._detecting_corners:
            self.feedback.set_info(tr("scanner_crop_area"), tr("scanner_detect_busy"))
            return

        path = self._detection_source_path(pg) if pg.rotation == 0 else None
        image = pg.display_image.copy() if path is None else None
        self._start_corner_detection([{
            "page": pg,
            "path": path,
            "image": image,
            "shape": pg.display_image.shape[:2],
        }])

    def reset_corners(self):
        pg = self.current_page
        if pg is None:
            return
        if self._detecting_corners:
            self.feedback.set_info(tr("scanner_crop_area"), tr("scanner_detect_busy"))
            return
        pg.corners = self._default_corners_for_image(pg.display_image)
        self._redraw_canvas()
        self.update_preview()
        self._schedule_session_save()

    # ─────────────────────────────────────────────────────────────────────
    #  Canvas drawing
    # ─────────────────────────────────────────────────────────────────────

    def _redraw_canvas(self):
        self.canvas.delete("all")
        pg = self.current_page

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            self.canvas.after(50, self._redraw_canvas)
            return

        if pg is None:
            self.canvas.create_text(cw // 2, ch // 2 - 22, text="📷", fill="#64748b", font=("Segoe UI Emoji", 30))
            self.canvas.create_text(cw // 2, ch // 2 + 26, text=tr("scanner_empty_canvas"), fill="#cbd5e1",
                                    font=("Segoe UI", 11), width=max(200, cw - 80), justify="center")
            return

        ih, iw = pg.display_image.shape[:2]
        scale = min(cw / iw, ch / ih)
        new_w = int(iw * scale)
        new_h = int(ih * scale)
        self.canvas_scale = scale
        ox = (cw - new_w) // 2
        oy = (ch - new_h) // 2
        self.canvas_offset = (ox, oy)

        if getattr(self, "_last_cw", None) != cw or getattr(self, "_last_ch", None) != ch or getattr(self, "_last_pg", None) != pg or getattr(self, "_last_rot", None) != pg.rotation:
            rgb = cv2.cvtColor(pg.display_image, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb).resize((new_w, new_h), Image.LANCZOS)
            self.tk_photo = ImageTk.PhotoImage(pil_img)
            self._last_cw = cw
            self._last_ch = ch
            self._last_pg = pg; self._last_rot = pg.rotation

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
        # Rescaling the photo is the slow part; do it once the size settles
        # (window or strip being dragged fires dozens of these).
        self._debounce("canvas", 40, self._redraw_canvas)

    # ─────────────────────────────────────────────────────────────────────
    #  Corner dragging
    # ─────────────────────────────────────────────────────────────────────

    def _canvas_to_image(self, cx, cy):
        ox, oy = self.canvas_offset
        return (cx - ox) / self.canvas_scale, (cy - oy) / self.canvas_scale

    def _on_canvas_press(self, event):
        if self._detecting_corners:
            return
        pg = self.current_page
        if pg is None:
            self.add_photos()
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
            self._schedule_session_save()

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
        self._refresh_strip()
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

    def _on_mode_changed(self, _event=None):
        self.update_preview()
        self._schedule_session_save()

    # ─────────────────────────────────────────────────────────────────────
    #  Session persistence (survives app restart)
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _mode_label(mode):
        for m, key in _MODE_MAP:
            if m == mode:
                return tr(key)
        return None

    def _detection_source_path(self, pg):
        """A file whose pixels equal pg.cv_image. The session PNG wins: the
        original may have been moved, deleted or edited since it was added."""
        stored = self._session_store.image_path(pg.uid)
        if os.path.isfile(stored):
            return stored
        if pg.path and os.path.isfile(pg.path):
            return pg.path
        return None

    def _schedule_session_save(self):
        """Debounced autosave. Call after ANY change to pages, corners, rotation,
        order, scan mode or output path. Main thread only."""
        if self._session_restoring or not self._session_store.enabled:
            return
        self._session_rev += 1
        if self._session_save_job is not None:
            self.app_root.after_cancel(self._session_save_job)
        self._session_save_job = self.app_root.after(SESSION_SAVE_DELAY_MS, self._save_session)

    def _save_session(self):
        """Snapshot the state (cheap, main thread) and hand it to the writer thread."""
        self._session_save_job = None
        if self._session_restoring or not self._session_store.enabled:
            return
        if not self.pages:
            self._session_store.clear()
            return

        meta = {
            "version": SESSION_VERSION,
            # corners[0] is the display-space top-left (see _apply_rotation).
            # Sessions without this key predate that fix.
            "corner_order": "display",
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "scan_mode": self._get_selected_mode(),   # internal id, not the translated label
            "output_path": self.output_var.get().strip(),
            "current_index": max(0, self.current_index),
            "pages": [
                {
                    "uid": pg.uid,
                    "source_path": pg.path,
                    "width": int(pg.cv_image.shape[1]),
                    "height": int(pg.cv_image.shape[0]),
                    "rotation": int(pg.rotation) % 360,
                    "label": pg.label,
                    # Corners are integer pixels everywhere in this tab; int() also
                    # turns any numpy scalar into something json can encode.
                    "corners": [[int(round(float(x))), int(round(float(y)))] for x, y in pg.corners],
                }
                for pg in self.pages
            ],
        }
        # References only, no copies: cv_image is never modified in place.
        self._session_store.save(meta, {pg.uid: pg.cv_image for pg in self.pages})

    def save_session_now(self):
        """Run a pending debounced save immediately (e.g. window hidden to tray)."""
        if self._session_save_job is not None:
            self.app_root.after_cancel(self._session_save_job)
            self._save_session()

    def flush_session(self, timeout=10.0):
        """Save pending changes and wait until they are on disk. Used on app exit."""
        self.save_session_now()
        return self._session_store.flush(timeout)

    def _clear_session(self):
        if self._session_save_job is not None:
            self.app_root.after_cancel(self._session_save_job)
            self._session_save_job = None
        self._session_store.clear()

    def _on_session_error(self, message):
        # Once per run is enough; the next save retries whatever is missing.
        if self._session_error_shown:
            return
        self._session_error_shown = True
        self.feedback.set_error(tr("scanner_session_title"),
                                tr("scanner_session_save_failed").format(error=message))

    def _load_session(self):
        """Called once from __init__. Reads session.json now (small, fast);
        the images are decoded the first time the tab is shown."""
        if self._session_store.locked_by_other:
            self.feedback.set_info(tr("scanner_session_title"), tr("scanner_session_locked"))
            return
        meta = self._session_store.load_meta()
        if not meta or not meta.get("pages"):
            return
        self._session_meta = meta
        self._session_restoring = True        # nothing may overwrite it before it is applied
        self.parent.bind("<Map>", self._on_tab_mapped, add="+")
        if self.parent.winfo_ismapped():
            self._begin_session_restore()

    def _on_tab_mapped(self, event):
        if event.widget is self.parent and self._session_meta is not None:
            self._begin_session_restore()

    def _begin_session_restore(self):
        meta, self._session_meta = self._session_meta, None   # one-shot
        if meta is None:
            return
        # Reuse the tab's busy lock: add/rotate/detect/scan already refuse to
        # run while it is set, and the toolbar gets disabled.
        self._detecting_corners = True
        self._set_corner_detection_busy(True, tr("scanner_session_restoring"))
        threading.Thread(target=self._restore_session_worker, args=(meta,), daemon=True).start()

    def _restore_session_worker(self, meta):
        # Worker thread: disk + numpy only, no Tk calls.
        restored, skipped = [], 0
        legacy_order = meta.get("corner_order") != "display"
        for entry in meta["pages"]:
            try:
                page = self._page_from_session_entry(entry, legacy_order)
            except Exception:
                logging.exception("Scanner session page could not be restored")
                page = None
            if page is None:
                skipped += 1
            else:
                restored.append(page)
        self.app_root.after(0, self._apply_restored_session, meta, restored, skipped)

    def _page_from_session_entry(self, entry, legacy_order=False):
        if not isinstance(entry, dict):
            return None
        uid = entry.get("uid")
        img = self._session_store.read_image(uid)    # also validates the uid
        if img is None:
            return None
        h, w = img.shape[:2]
        if entry.get("width") != w or entry.get("height") != h:
            return None    # pixels don't match the metadata, corners would be wrong

        source = entry.get("source_path")
        if not isinstance(source, str) or not source:
            source = self._session_store.image_path(uid)
        label = entry.get("label", "")
        page = _PageData(source, img, [], uid=uid, label=_clean_label(label) if isinstance(label, str) else "")

        rotation = entry.get("rotation", 0)
        if rotation in (90, 180, 270):
            page.rotation = int(rotation)
            page.display_image = rotate_image(img, page.rotation)

        dh, dw = page.display_image.shape[:2]
        corners = entry.get("corners")
        if _valid_corners(corners):
            # Already in display (rotated) coordinates: do NOT call _apply_rotation.
            page.corners = [(min(max(int(round(x)), 0), dw), min(max(int(round(y)), 0), dh))
                            for x, y in corners]
            if legacy_order:
                # Rotating used to leave the list starting at any corner (the
                # clockwise order itself was kept). Start it at the top-left.
                k = min(range(4), key=lambda i: page.corners[i][0] + page.corners[i][1])
                page.corners = page.corners[k:] + page.corners[:k]
        else:
            page.corners = self._default_corners_for_shape(dh, dw)
        return page

    def _apply_restored_session(self, meta, restored, skipped):
        if restored:
            # self.pages is empty: every way to add a page was locked meanwhile.
            self.pages = restored + self.pages
            idx = meta.get("current_index", 0)
            self.current_index = idx if isinstance(idx, int) and 0 <= idx < len(self.pages) else 0
            label = self._mode_label(meta.get("scan_mode"))
            if label:
                self.scan_mode_var.set(label)
            out = meta.get("output_path")
            if isinstance(out, str) and out and not self.output_var.get().strip():
                self.output_var.set(out)      # trace fires, saves are still suppressed

        self._session_restoring = False
        self._detecting_corners = False
        self._set_corner_detection_busy(False)
        self.status_var.set(tr("str_ready"))

        if not restored:
            self._session_store.clear()
            self.feedback.set_info(tr("scanner_session_title"), tr("scanner_session_failed"))
            return

        self._show_current_page()
        if skipped:
            self.feedback.set_info(
                tr("scanner_session_title"),
                tr("scanner_session_restored_partial").format(count=len(restored), skipped=skipped),
            )
            self._schedule_session_save()    # rewrite session.json without the broken pages
        else:
            self.feedback.set_info(
                tr("scanner_session_title"),
                tr("scanner_session_restored").format(count=len(restored)),
            )

    # ─────────────────────────────────────────────────────────────────────
    #  Scan & export (multi-page)
    # ─────────────────────────────────────────────────────────────────────

    def start_scan(self):
        if self._detecting_corners:
            self.feedback.set_info(tr("scanner_crop_area"), tr("scanner_detect_busy"))
            return

        if not self.pages:
            self.feedback.set_error(tr("str_error"), tr("scanner_no_image"))
            return

        output = self.output_var.get().strip()
        if not output:
            quick_error(tr("err_set_output"), self.footer.action_button, None, self.status_var, self.feedback)
            return

        def _on_progress(current, total, message=""):
            self.app_root.after(0, self.footer.update_progress, current, total, message)

        self._task_ctx = TaskContext(progress_callback=_on_progress)
        self._scan_start_rev = self._session_rev
        self.footer.start_busy(cancel_callback=self._cancel_task)
        self.feedback.set_busy(tr("scanner_running"))
        self.status_var.set(tr("scanner_running"))

        threading.Thread(target=self._run_scan, args=(output,), daemon=True).start()

    def _cancel_task(self):
        if self._task_ctx:
            self._task_ctx.cancel()

    def _run_scan(self, output_pdf):
        try:
            mode = self._get_selected_mode()
            processed = []
            
            total = len(self.pages)

            for i, pg in enumerate(self.pages):
                if self._task_ctx:
                    self._task_ctx.check_cancelled()
                    self._task_ctx.report_progress(i, total, f"{i+1}/{total} resim işleniyor...")
                warped = perspective_warp(pg.display_image, pg.corners, A4_WIDTH_PX, A4_HEIGHT_PX)
                result = apply_scan_mode(warped, mode)
                processed.append(result)

            out_dir = os.path.dirname(output_pdf)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

            scanned_images_to_pdf(processed, output_pdf, ctx=self._task_ctx)

            count = len(processed)
            if count == 1:
                msg = tr("scanner_result").format(output=output_pdf)
            else:
                msg = tr("scanner_result_multi").format(count=count, output=output_pdf)

            def _done():
                self.footer.finish_success()
                self.status_var.set(tr("scanner_done"))
                self.feedback.set_success(tr("scanner_done"), msg, output_pdf)
                # Only forget the session if nothing changed while the PDF was
                # being written; otherwise those edits are not in the PDF yet.
                if self._session_rev == self._scan_start_rev:
                    self._clear_session()
            self.app_root.after(0, _done)

        except CancelledError:
            def _cancel():
                self.footer.stop_busy()
                self.status_var.set(tr("perf_cancelled"))
                self.feedback.set_cancelled()
            self.app_root.after(0, _cancel)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            err_msg = str(exc)
            def _err(msg=err_msg):
                self.footer.stop_busy()
                self.status_var.set(tr("scanner_fail"))
                self.feedback.set_error(tr("scanner_fail"), msg)
            self.app_root.after(0, _err)

    # ─────────────────────────────────────────────────────────────────────
    #  Fullscreen Crop
    # ─────────────────────────────────────────────────────────────────────

    def open_fullscreen_crop(self):
        if self._detecting_corners:
            self.feedback.set_info(tr("scanner_crop_area"), tr("scanner_detect_busy"))
            return
        pg = self.current_page
        if pg is None:
            return

        self.fs_top = tk.Toplevel(self.app_root)
        self.fs_top.title(tr("scanner_fullscreen_crop"))
        self.fs_top.configure(bg=CANVAS_BG)
        self.fs_top.state('zoomed')  # Maximize on Windows

        header = ttk.Frame(self.fs_top, style="Card.TFrame", padding=10)
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
        self._last_fs_cw = None
        self._last_fs_ch = None
        self._last_fs_pg = None
        self._last_fs_rot = None

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

        if getattr(self, "_last_fs_cw", None) != cw or getattr(self, "_last_fs_ch", None) != ch or getattr(self, "_last_fs_pg", None) != pg or getattr(self, "_last_fs_rot", None) != pg.rotation:
            rgb = cv2.cvtColor(pg.display_image, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb).resize((new_w, new_h), Image.LANCZOS)
            self.fs_tk_photo = ImageTk.PhotoImage(pil_img, master=self.fs_top)
            self._last_fs_cw = cw
            self._last_fs_ch = ch
            self._last_fs_pg = pg; self._last_fs_rot = pg.rotation

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
            self._schedule_session_save()

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


