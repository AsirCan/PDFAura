"""The document scanner's model: pages, corners, rotation, the saved session
and the PDF export -- everything the scanner screen does that is not drawing.

It lived inside the 1,900-line Tk tab; moved here (#25) so it can be tested
on its own and the web window gets the same behaviour. Images are BGR
numpy arrays, OpenCV's order. Nothing heavy is imported at module level:
building the app's window must not load OpenCV before a photo is added.
"""
import logging
import math
import os
import tempfile
import time
import uuid

from src.core.lang_manager import _

# The same ids as src.core.document_scanner, repeated so the screen can be
# built without importing OpenCV (a test keeps the two in step).
MODE_ORIGINAL = "original"
MODE_CLEAN_DOC = "clean_doc"
MODE_BW = "bw"
MODE_GRAYSCALE = "grayscale"
MODE_SHARP = "sharp"
MODES = [
    (MODE_ORIGINAL, "scanner_mode_original"),
    (MODE_CLEAN_DOC, "scanner_mode_clean_doc"),
    (MODE_BW, "scanner_mode_bw"),
    (MODE_GRAYSCALE, "scanner_mode_grayscale"),
    (MODE_SHARP, "scanner_mode_sharp"),
]
DEFAULT_MODE = MODE_CLEAN_DOC
A4_ASPECT = 3508 / 2480            # height / width; see document_scanner.A4_*_PX
PAGE_LABEL_MAX = 60
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")


def mode_label(mode):
    """The localised label for a scan mode id, or None."""
    for known, key in MODES:
        if known == mode:
            return _(key)
    return None


def mode_from_label(label):
    for mode, key in MODES:
        if _(key) == label:
            return mode
    return MODE_ORIGINAL


# ── Pages ─────────────────────────────────────────────────────────────────

def clean_label(text):
    """One printable line, trimmed; an empty string means the page is unnamed."""
    text = "".join(ch for ch in str(text) if ch.isprintable() or ch.isspace())
    return " ".join(text.split())[:PAGE_LABEL_MAX]


def valid_corners(corners):
    if not isinstance(corners, list) or len(corners) != 4:
        return False
    for pt in corners:
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            return False
        for v in pt:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                return False
    return True


def default_corners(h, w):
    """A quad just inside the photo's edges, for when nothing is detected."""
    margin = max(0, min(20, min(h, w) // 12))
    right = max(0, w - 1 - margin)
    bottom = max(0, h - 1 - margin)
    return [(margin, margin), (right, margin), (right, bottom), (margin, bottom)]


class ScanPage:
    """One photo in the scan list."""
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

    @property
    def display_shape(self):
        """(height, width) of the photo as shown, after rotation."""
        return self.display_image.shape[:2]

    def reset_corners(self):
        self.corners = default_corners(*self.display_shape)


def load_photo(path):
    """A new page for the photo at ``path``, or None if it cannot be read."""
    from src.core.document_scanner import imread_unicode
    image = imread_unicode(path)
    if image is None:
        return None
    h, w = image.shape[:2]
    return ScanPage(path, image, default_corners(h, w))


def rotate(page, step):
    """Turn ``page`` by ``step`` degrees (90 = clockwise, -90 = counter-clockwise)
    and carry its corners along."""
    from src.core.document_scanner import rotate_image
    page.rotation = (page.rotation + step) % 360
    page.display_image = rotate_image(page.cv_image, page.rotation)
    new_h, new_w = page.display_shape

    corners = []
    for (x, y) in page.corners:
        if step == 90:
            corners.append((new_w - y, x))
        elif step == -90:
            corners.append((y, new_h - x))
        else:
            corners.append((x, y))
    # The quad turned with the photo, so its first point is no longer the
    # top-left one. perspective_warp maps corners[0] to the output's top-left,
    # so without re-anchoring the preview and PDF keep the old orientation.
    # CW: the old bottom-left becomes top-left; CCW: the old top-right does.
    if step == 90:
        corners = corners[-1:] + corners[:-1]
    elif step == -90:
        corners = corners[1:] + corners[:1]
    page.corners = corners


# ── Corner detection ──────────────────────────────────────────────────────

def detection_job(page, source_path=None):
    """What detect() needs for ``page``, taken now on the UI thread.

    The detector reads files; a file with the same pixels as the page
    (``source_path``) is used when the page is not rotated, otherwise the
    rotated pixels are copied and written to a temporary file.
    """
    use_file = source_path if page.rotation == 0 else None
    return {
        "page": page,
        "path": use_file,
        "image": page.display_image.copy() if use_file is None else None,
        "shape": page.display_shape,
    }


def detect(job):
    """Corners for one detection job: (corners, found). On failure the
    default quad, so the page still has handles to drag."""
    from src.core.document_scanner import detect_document_corners, imwrite_unicode
    tmp_path = None
    try:
        if job["image"] is not None:
            fd, tmp_path = tempfile.mkstemp(prefix="pdfaura_scan_", suffix=".png")
            os.close(fd)
            imwrite_unicode(tmp_path, job["image"])
            return detect_document_corners(tmp_path), True
        return detect_document_corners(job["path"]), True
    except Exception:
        return default_corners(*job["shape"]), False
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ── Session (survives a restart) ──────────────────────────────────────────

def session_meta(pages, mode, output_path, current_index):
    """What session.json stores. Cheap: references only, no pixel copies."""
    from src.core.scanner_session import SESSION_VERSION
    return {
        "version": SESSION_VERSION,
        # corners[0] is the display-space top-left (see rotate()).
        # Sessions without this key predate that fix.
        "corner_order": "display",
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "scan_mode": mode,                      # internal id, not the translated label
        "output_path": output_path,
        "current_index": max(0, current_index),
        "pages": [
            {
                "uid": pg.uid,
                "source_path": pg.path,
                "width": int(pg.cv_image.shape[1]),
                "height": int(pg.cv_image.shape[0]),
                "rotation": int(pg.rotation) % 360,
                "label": pg.label,
                # Corners are integer pixels everywhere; int() also turns any
                # numpy scalar into something json can encode.
                "corners": [[int(round(float(x))), int(round(float(y)))] for x, y in pg.corners],
            }
            for pg in pages
        ],
    }


def page_from_session_entry(store, entry, legacy_order=False):
    """Rebuild one saved page, or None if it no longer matches its image."""
    from src.core.document_scanner import rotate_image
    if not isinstance(entry, dict):
        return None
    uid = entry.get("uid")
    img = store.read_image(uid)    # also validates the uid
    if img is None:
        return None
    h, w = img.shape[:2]
    if entry.get("width") != w or entry.get("height") != h:
        return None    # pixels don't match the metadata, corners would be wrong

    source = entry.get("source_path")
    if not isinstance(source, str) or not source:
        source = store.image_path(uid)
    label = entry.get("label", "")
    page = ScanPage(source, img, [], uid=uid, label=clean_label(label) if isinstance(label, str) else "")

    rotation = entry.get("rotation", 0)
    if rotation in (90, 180, 270):
        page.rotation = int(rotation)
        page.display_image = rotate_image(img, page.rotation)

    dh, dw = page.display_shape
    corners = entry.get("corners")
    if valid_corners(corners):
        # Already in display (rotated) coordinates: do NOT rotate them again.
        page.corners = [(min(max(int(round(x)), 0), dw), min(max(int(round(y)), 0), dh))
                        for x, y in corners]
        if legacy_order:
            # Rotating used to leave the list starting at any corner (the
            # clockwise order itself was kept). Start it at the top-left.
            k = min(range(4), key=lambda i: page.corners[i][0] + page.corners[i][1])
            page.corners = page.corners[k:] + page.corners[:k]
    else:
        page.corners = default_corners(dh, dw)
    return page


def restore_pages(store, meta):
    """(pages, skipped) from a saved session. Disk and numpy only: safe to
    run on a worker thread."""
    restored, skipped = [], 0
    legacy_order = meta.get("corner_order") != "display"
    for entry in meta["pages"]:
        try:
            page = page_from_session_entry(store, entry, legacy_order)
        except Exception:
            logging.exception("Scanner session page could not be restored")
            page = None
        if page is None:
            skipped += 1
        else:
            restored.append(page)
    return restored, skipped


# ── Export ────────────────────────────────────────────────────────────────

def snapshot(pages):
    """What the export needs, taken on the UI thread: the worker must never
    read the live page list while the user can still edit it (#12)."""
    return [(page.display_image, list(page.corners)) for page in pages]


def export_pdf(ctx, shots, output_pdf, mode):
    """Write ``shots`` (from snapshot()) as one PDF and return the Outcome."""
    from src.app.tools import Outcome
    from src.core.document_scanner import apply_scan_mode, perspective_warp, scanned_images_to_pdf
    total = len(shots)

    def pages():
        """Warp and filter one page at a time.

        Yielding rather than building a list keeps memory flat: the old code
        held every processed page (~50 MB each) at once.
        """
        for i, (image, corners) in enumerate(shots):
            if ctx:
                ctx.check_cancelled()
                ctx.report_progress(i, total, _("progress_image_of").format(current=i + 1, total=total))
            # No explicit size: the page keeps its own proportions.
            yield apply_scan_mode(perspective_warp(image, corners), mode)

    out_dir = os.path.dirname(output_pdf)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    count = scanned_images_to_pdf(pages(), output_pdf, ctx=ctx, mode=mode)
    if count == 1:
        message = _("scanner_result").format(output=output_pdf)
    else:
        message = _("scanner_result_multi").format(count=count, output=output_pdf)
    return Outcome(_("scanner_done"), message, output_pdf)


# ── Pictures for the screen (PIL images; the UI wraps them) ───────────────

def to_pil(image_bgr, size=None, nearest=False):
    """A BGR array as an RGB PIL image, optionally resized."""
    import cv2
    from PIL import Image
    picture = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
    if size is not None:
        picture = picture.resize(size, Image.NEAREST if nearest else Image.LANCZOS)
    return picture


def thumbnail(page, thumb_w, thumb_h, background_hex):
    """The page as exported, letterboxed into a thumb_w x thumb_h cell.

    Warped at the page's real proportions: squeezing a landscape page into
    the A4-shaped cell made the strip disagree with the exported PDF.
    """
    import cv2
    import numpy as np
    from src.core.document_scanner import perspective_warp, target_size_from_corners
    full_w, full_h = target_size_from_corners(page.corners)
    scale = min(thumb_w / full_w, thumb_h / full_h)
    warp_w = max(1, int(round(full_w * scale)))
    warp_h = max(1, int(round(full_h * scale)))
    warped = perspective_warp(page.display_image, page.corners, warp_w * 2, warp_h * 2)
    small = cv2.resize(warped, (warp_w, warp_h), interpolation=cv2.INTER_AREA)

    back = background_hex.lstrip("#")
    cell = np.full((thumb_h, thumb_w, 3), [int(back[i:i + 2], 16) for i in (4, 2, 0)], dtype=np.uint8)
    top = (thumb_h - warp_h) // 2
    left = (thumb_w - warp_w) // 2
    cell[top:top + warp_h, left:left + warp_w] = small
    return to_pil(cell)


def fitted(page, box_w, box_h):
    """The page as it will be exported (straightened, at its own
    proportions), fitted into box_w x box_h, without a background around it:
    the web window letterboxes it with CSS in the theme's colour."""
    import cv2
    from src.core.document_scanner import perspective_warp, target_size_from_corners
    full_w, full_h = target_size_from_corners(page.corners)
    scale = min(box_w / full_w, box_h / full_h)
    warp_w = max(1, int(round(full_w * scale)))
    warp_h = max(1, int(round(full_h * scale)))
    warped = perspective_warp(page.display_image, page.corners, warp_w * 2, warp_h * 2)
    return to_pil(cv2.resize(warped, (warp_w, warp_h), interpolation=cv2.INTER_AREA))


def drag_ghost(page, width, height):
    """A small picture of the page that follows the pointer while dragging."""
    import cv2
    from src.core.document_scanner import perspective_warp
    warped = perspective_warp(page.display_image, page.corners, width * 2, height * 2)
    return to_pil(cv2.resize(warped, (width, height), interpolation=cv2.INTER_AREA))


def preview(page, mode, box_w, box_h):
    """The exported page with its scan mode applied, fitted into the box."""
    from src.core.document_scanner import apply_scan_mode, perspective_warp, target_size_from_corners
    # At the page's real proportions, not a fixed A4 box.
    full_w, full_h = target_size_from_corners(page.corners)
    preview_w = 520
    preview_h = max(1, int(round(preview_w * full_h / full_w)))
    result = apply_scan_mode(perspective_warp(page.display_image, page.corners, preview_w, preview_h), mode)
    rh, rw = result.shape[:2]
    scale = min(box_w / rw, box_h / rh)
    return to_pil(result, (int(rw * scale), int(rh * scale)))


def magnifier(page, corner_index, scale, size=200):
    """A zoomed square around one corner (2x the on-screen size), or None."""
    import cv2
    cx, cy = page.corners[corner_index]
    crop = int(100 / scale)
    x1, y1 = int(cx - crop / 2), int(cy - crop / 2)
    x2, y2 = int(cx + crop / 2), int(cy + crop / 2)
    ih, iw = page.display_shape
    pad_x1, pad_y1 = max(0, -x1), max(0, -y1)
    pad_x2, pad_y2 = max(0, x2 - iw), max(0, y2 - ih)
    cropped = page.display_image[max(0, y1):min(ih, y2), max(0, x1):min(iw, x2)]
    if cropped.size == 0:
        return None
    if pad_x1 or pad_y1 or pad_x2 or pad_y2:
        cropped = cv2.copyMakeBorder(cropped, pad_y1, pad_y2, pad_x1, pad_x2, cv2.BORDER_REPLICATE)
    # NEAREST gives a sharp, zoomed-pixel look.
    return to_pil(cropped, (size, size), nearest=True)
