"""
Document Scanner Engine
-----------------------
CamScanner-like document scanning: edge detection, perspective correction,
gamma/filter modes, and PDF export.  Uses OpenCV + Pillow.
"""

import os
import numpy as np

try:
    import cv2
except ImportError:
    raise ImportError(
        "opencv-python kütüphanesi bulunamadı.\n"
        "Lütfen kurun: pip install opencv-python"
    )

from PIL import Image


# ── A4 output dimensions at 300 DPI ──────────────────────────────────────────
A4_WIDTH_PX = 2480   # 210 mm @ 300 dpi
A4_HEIGHT_PX = 3508  # 297 mm @ 300 dpi


# ── Scan mode constants ──────────────────────────────────────────────────────
MODE_ORIGINAL = "original"
MODE_CLEAN_DOC = "clean_doc"
MODE_BW = "bw"
MODE_GRAYSCALE = "grayscale"
MODE_SHARP = "sharp"


# ─────────────────────────────────────────────────────────────────────────────
#  Corner Detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_document_corners(image_path: str):
    """
    Attempt to auto-detect a rectangular document in the image.
    Returns a list of 4 (x, y) tuples in order:
        [top-left, top-right, bottom-right, bottom-left]
    If detection fails, returns the 4 image corners as fallback.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Görüntü okunamadı: {image_path}")

    h, w = img.shape[:2]

    # Resize for faster processing (keep aspect ratio)
    scale = 1.0
    max_dim = 1000
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        small = img.copy()

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(gray, 50, 200, apertureSize=3)
    edged = cv2.dilate(edged, None, iterations=2)
    edged = cv2.erode(edged, None, iterations=1)

    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    doc_contour = None
    for cnt in contours[:10]:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4 and cv2.contourArea(approx) > (small.shape[0] * small.shape[1] * 0.1):
            doc_contour = approx
            break

    if doc_contour is not None:
        pts = doc_contour.reshape(4, 2).astype(float)
        pts /= scale  # scale back to original resolution
        return _order_points(pts)
    else:
        # Fallback: slight margin inside image edges
        margin_x = int(w * 0.05)
        margin_y = int(h * 0.05)
        return [
            (margin_x, margin_y),
            (w - margin_x, margin_y),
            (w - margin_x, h - margin_y),
            (margin_x, h - margin_y),
        ]


def _order_points(pts):
    """
    Order 4 points as: top-left, top-right, bottom-right, bottom-left.
    """
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]      # top-left has smallest sum
    rect[2] = pts[np.argmax(s)]      # bottom-right has largest sum
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]   # top-right has smallest diff
    rect[3] = pts[np.argmax(diff)]   # bottom-left has largest diff
    return [(int(x), int(y)) for x, y in rect]


# ─────────────────────────────────────────────────────────────────────────────
#  Perspective Warp
# ─────────────────────────────────────────────────────────────────────────────

def perspective_warp(img_bgr, corners, output_w=A4_WIDTH_PX, output_h=A4_HEIGHT_PX):
    """
    Warp the region defined by *corners* into a rectangle of (output_w, output_h).
    *corners*: 4 (x,y) in order TL, TR, BR, BL.
    Returns the warped image (numpy BGR array).
    """
    src = np.array(corners, dtype="float32")
    dst = np.array([
        [0, 0],
        [output_w - 1, 0],
        [output_w - 1, output_h - 1],
        [0, output_h - 1],
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img_bgr, M, (output_w, output_h),
                                  flags=cv2.INTER_LANCZOS4,
                                  borderMode=cv2.BORDER_REPLICATE)
    return warped


# ─────────────────────────────────────────────────────────────────────────────
#  Rotation helpers
# ─────────────────────────────────────────────────────────────────────────────

def rotate_image(img_bgr, angle_degrees: int):
    """
    Rotate image by 90, 180 or 270 degrees clockwise (or any multiple of 90).
    """
    angle = angle_degrees % 360
    if angle == 0:
        return img_bgr
    elif angle == 90:
        return cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180:
        return cv2.rotate(img_bgr, cv2.ROTATE_180)
    elif angle == 270:
        return cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
    # Arbitrary angle: not needed for this feature but safe fallback
    return img_bgr


# ─────────────────────────────────────────────────────────────────────────────
#  Scan / Filter modes
# ─────────────────────────────────────────────────────────────────────────────

def apply_scan_mode(img_bgr, mode: str):
    """
    Apply the selected scan filter/gamma mode to a BGR image.
    Uses advanced adaptive thresholding and morphological operations
    to handle uneven lighting effectively.
    """
    if mode == MODE_ORIGINAL:
        return img_bgr

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    if mode == MODE_BW:
        # Adaptive Thresholding for B&W - Handles uneven lighting perfectly
        bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 15)
        return cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)

    if mode == MODE_GRAYSCALE:
        # Increase contrast with CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    if mode == MODE_CLEAN_DOC:
        # Morphological background estimation map (removes text to find background)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
        bg = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
        bg = cv2.medianBlur(bg, 21)
        
        # Divide image by background to normalize lighting (white background, dark text)
        clean = cv2.divide(gray, bg, scale=255)
        
        # Slight morphological cleanup to crisp text edges
        clean = cv2.normalize(clean, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
        return cv2.cvtColor(clean, cv2.COLOR_GRAY2BGR)

    if mode == MODE_SHARP:
        # High contrast + Sharpness
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        enhanced_bgr = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
        blurred = cv2.GaussianBlur(enhanced_bgr, (0, 0), 3)
        sharpened = cv2.addWeighted(enhanced_bgr, 1.5, blurred, -0.5, 0)
        return sharpened

    return img_bgr


# ─────────────────────────────────────────────────────────────────────────────
#  Full pipeline
# ─────────────────────────────────────────────────────────────────────────────

def scan_document(image_path: str, corners, scan_mode: str,
                  rotation: int = 0,
                  output_w: int = A4_WIDTH_PX,
                  output_h: int = A4_HEIGHT_PX):
    """
    Full scan pipeline:
      1. Load image
      2. Perspective warp using user-defined corners
      3. Rotate if requested
      4. Apply scan mode / filter

    Returns the processed image as a BGR numpy array.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Görüntü okunamadı: {image_path}")

    warped = perspective_warp(img, corners, output_w, output_h)

    if rotation:
        warped = rotate_image(warped, rotation)

    result = apply_scan_mode(warped, scan_mode)
    return result


def save_scanned_image(img_bgr, output_path: str):
    """
    Save a processed BGR image to a file (PNG/JPEG/etc based on extension).
    """
    cv2.imwrite(output_path, img_bgr)


def scanned_image_to_pdf(img_bgr, output_pdf: str):
    """
    Convert a processed BGR image to a single-page PDF using Pillow.
    """
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)

    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")

    # Calculate DPI from A4 dimensions
    # A4 = 210mm x 297mm.  dpi = pixels / (mm / 25.4)
    w, h = pil_img.size
    dpi_x = w / (210 / 25.4)
    dpi_y = h / (297 / 25.4)

    pil_img.save(output_pdf, "PDF", resolution=max(dpi_x, dpi_y))


def scanned_images_to_pdf(images_bgr: list, output_pdf: str):
    """
    Convert multiple processed BGR images to a multi-page PDF.
    Each image becomes one page.
    """
    if not images_bgr:
        raise ValueError("En az bir görüntü gerekli.")

    pil_pages = []
    for img_bgr in images_bgr:
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        pil_pages.append(pil_img)

    w, h = pil_pages[0].size
    dpi_x = w / (210 / 25.4)
    dpi_y = h / (297 / 25.4)
    dpi = max(dpi_x, dpi_y)

    pil_pages[0].save(
        output_pdf, "PDF",
        save_all=True,
        append_images=pil_pages[1:],
        resolution=dpi,
    )
