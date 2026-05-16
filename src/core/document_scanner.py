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
def imread_unicode(path):
    """Read an image from a path that may contain Unicode characters."""
    try:
        import numpy as np
        import cv2
        return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None

def imwrite_unicode(path, img):
    """Write an image to a path that may contain Unicode characters."""
    try:
        import numpy as np
        import cv2
        ext = os.path.splitext(path)[1]
        is_success, buffer = cv2.imencode(ext, img)
        if is_success:
            buffer.tofile(path)
            return True
    except Exception:
        pass
    return False



# ── A4 output dimensions at 300 DPI ──────────────────────────────────────────
A4_WIDTH_PX = 2480   # 210 mm @ 300 dpi
A4_HEIGHT_PX = 3508  # 297 mm @ 300 dpi


# ── Scan mode constants ──────────────────────────────────────────────────────
MODE_ORIGINAL = "original"
MODE_CLEAN_DOC = "clean_doc"
MODE_BW = "bw"
MODE_GRAYSCALE = "grayscale"
MODE_SHARP = "sharp"
DETECTION_MAX_DIM = 960
LINE_DETECTION_ACCEPT_SCORE = 0.74
FAST_DETECTION_ACCEPT_SCORE = 0.68


# ─────────────────────────────────────────────────────────────────────────────
#  Corner Detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_document_corners(image_path: str):
    """
    Fast document corner detection with AI fallback.
    The primary path uses cheap OpenCV masks and contour scoring. ONNX is only
    used when the fast detector is uncertain, because the bundled U2-Net model
    is a segmentation fallback, not a dedicated corner detector.
    Returns a list of 4 (x, y) tuples in order:
        [top-left, top-right, bottom-right, bottom-left]
    """
    img = imread_unicode(image_path)
    if img is None:
        raise FileNotFoundError(f"Görüntü okunamadı: {image_path}")
    
    h, w = img.shape[:2]
    candidates = []

    if _is_low_detail_image(img):
        return _default_corners((w, h))

    line_corners, line_score = _detect_document_corners_lines(img)
    if line_corners is not None:
        candidates.append(("Line CV", line_corners, line_score))
        if line_score >= LINE_DETECTION_ACCEPT_SCORE:
            return _clip_and_order_corners(line_corners, (w, h))

    fast_corners, fast_score = _detect_document_corners_fast(img)
    if fast_corners is not None:
        candidates.append(("Fast CV", fast_corners, fast_score))
        if fast_score >= FAST_DETECTION_ACCEPT_SCORE:
            return _clip_and_order_corners(fast_corners, (w, h))

    # ONNX is slower and can return foreground/image-border masks, so keep it
    # behind the fast detector and require it to beat the current candidate.
    try:
        from .document_scanner_onnx import detect_with_onnx_fallback
        onnx_corners = detect_with_onnx_fallback(image_path)
        if onnx_corners is not None:
            score = _score_document_quad(
                np.array(onnx_corners, dtype=np.float32),
                (h, w),
                method_weight=0.92,
            )
            if score > 0.45:
                candidates.append(("ONNX", onnx_corners, score))
    except Exception:
        pass
    
    # Legacy lightweight fallback; useful when the page has weak contrast.
    try:
        from .document_scanner_ml import detect_document_corners_ml
        ml_corners = detect_document_corners_ml(image_path)
        if ml_corners and len(ml_corners) == 4:
            score = _score_document_quad(
                np.array(ml_corners, dtype=np.float32),
                (h, w),
                method_weight=0.90,
            )
            if score > 0.42:
                candidates.append(("ML-Enhanced", ml_corners, score))
    except Exception:
        pass

    if candidates:
        candidates.sort(key=lambda x: x[2], reverse=True)
        return _clip_and_order_corners(candidates[0][1], (w, h))

    return _default_corners((w, h))


def _detect_document_corners_lines(img):
    """Detect page borders from strong top/bottom/left/right line candidates."""
    orig_h, orig_w = img.shape[:2]
    scale = min(1.0, DETECTION_MAX_DIM / max(orig_h, orig_w))
    if scale < 1.0:
        small = cv2.resize(img, (int(orig_w * scale), int(orig_h * scale)), interpolation=cv2.INTER_AREA)
    else:
        small = img

    h, w = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 110)
    edges = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)

    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=50,
        minLineLength=int(w * 0.16),
        maxLineGap=28,
    )
    if lines is None:
        return None, 0.0

    candidates = {"top": [], "bottom": [], "left": [], "right": []}
    for raw_line in lines[:, 0]:
        x1, y1, x2, y2 = [int(v) for v in raw_line]
        length = float(np.hypot(x2 - x1, y2 - y1))
        if length <= 1:
            continue

        angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        x_mid = (x1 + x2) / 2.0
        y_mid = (y1 + y2) / 2.0
        line = np.array([x1, y1, x2, y2], dtype=np.float32)

        if (abs(angle) < 14 or abs(angle) > 166) and length > w * 0.22:
            if y_mid < h * 0.56:
                contrast = _line_contrast(gray, line, "top")
                score = (length / w) * max(0.0, contrast) / 40.0
                candidates["top"].append((score, line))
            if y_mid > h * 0.42:
                contrast = _line_contrast(gray, line, "bottom")
                score = (length / w) * max(0.0, contrast) / 40.0
                candidates["bottom"].append((score, line))

        if 65 < abs(angle) < 115 and length > h * 0.30:
            if x_mid < w * 0.50:
                contrast = _line_contrast(gray, line, "left")
                score = (length / h) * max(0.0, contrast) / 40.0
                candidates["left"].append((score, line))
            if x_mid > w * 0.50:
                contrast = _line_contrast(gray, line, "right")
                score = (length / h) * max(0.0, contrast) / 40.0
                candidates["right"].append((score, line))

    for key in candidates:
        candidates[key] = sorted(candidates[key], key=lambda item: item[0], reverse=True)[:6]
        if not candidates[key]:
            return None, 0.0

    best_quad = None
    best_score = 0.0
    for top_score, top in candidates["top"]:
        for bottom_score, bottom in candidates["bottom"]:
            for left_score, left in candidates["left"]:
                for right_score, right in candidates["right"]:
                    quad = _quad_from_border_lines(top, bottom, left, right)
                    if quad is None:
                        continue

                    score = _score_line_quad(
                        quad,
                        small.shape,
                        (top_score, bottom_score, left_score, right_score),
                        (top, bottom, left, right),
                    )
                    if score > best_score:
                        best_quad = quad
                        best_score = score

    if best_quad is None:
        return None, 0.0

    if scale < 1.0:
        best_quad = best_quad / scale

    return _clip_and_order_corners(best_quad, (orig_w, orig_h)), float(best_score)


def _quad_from_border_lines(top, bottom, left, right):
    top_line = _line_from_segment(top)
    bottom_line = _line_from_segment(bottom)
    left_line = _line_from_segment(left)
    right_line = _line_from_segment(right)
    if any(line is None for line in (top_line, bottom_line, left_line, right_line)):
        return None

    points = [
        _intersect_param_lines(top_line, left_line),
        _intersect_param_lines(top_line, right_line),
        _intersect_param_lines(bottom_line, right_line),
        _intersect_param_lines(bottom_line, left_line),
    ]
    if any(point is None for point in points):
        return None

    return np.array(_order_points(np.array(points, dtype=np.float32)), dtype=np.float32)


def _line_from_segment(segment):
    x1, y1, x2, y2 = [float(v) for v in segment]
    a = y1 - y2
    b = x2 - x1
    c = x1 * y2 - x2 * y1
    norm = np.hypot(a, b)
    if norm <= 1e-6:
        return None
    return np.array([a / norm, b / norm, c / norm], dtype=np.float32)


def _intersect_param_lines(line1, line2):
    a1, b1, c1 = line1
    a2, b2, c2 = line2
    det = a1 * b2 - a2 * b1
    if abs(det) <= 1e-6:
        return None
    x = (b1 * c2 - b2 * c1) / det
    y = (c1 * a2 - c2 * a1) / det
    return np.array([x, y], dtype=np.float32)


def _line_contrast(gray, segment, mode, offset=8):
    x1, y1, x2, y2 = [int(v) for v in segment]
    length = max(2, int(np.hypot(x2 - x1, y2 - y1)))
    sample_count = min(60, max(10, length // 6))
    xs = np.linspace(x1, x2, sample_count).astype(np.int32)
    ys = np.linspace(y1, y2, sample_count).astype(np.int32)
    h, w = gray.shape

    if mode in ("top", "bottom"):
        above_y = np.clip(ys - offset, 0, h - 1)
        below_y = np.clip(ys + offset, 0, h - 1)
        x_vals = np.clip(xs, 0, w - 1)
        above = gray[above_y, x_vals].astype(np.float32)
        below = gray[below_y, x_vals].astype(np.float32)
        if mode == "top":
            return float(np.mean(below - above))
        return float(np.mean(above - below))

    left_x = np.clip(xs - offset, 0, w - 1)
    right_x = np.clip(xs + offset, 0, w - 1)
    y_vals = np.clip(ys, 0, h - 1)
    left_vals = gray[y_vals, left_x].astype(np.float32)
    right_vals = gray[y_vals, right_x].astype(np.float32)
    if mode == "left":
        return float(np.mean(right_vals - left_vals))
    return float(np.mean(left_vals - right_vals))


def _score_line_quad(quad, img_shape, line_scores, line_segments):
    h, w = img_shape[:2]
    pts = np.array(quad, dtype=np.float32).reshape(4, 2)
    if np.any(pts[:, 0] < -w * 0.10) or np.any(pts[:, 0] > w * 1.10):
        return 0.0
    if np.any(pts[:, 1] < -h * 0.10) or np.any(pts[:, 1] > h * 1.10):
        return 0.0

    area = abs(cv2.contourArea(pts.reshape(-1, 1, 2).astype(np.float32)))
    area_ratio = area / float(w * h)
    if area_ratio < 0.35 or area_ratio > 0.97:
        return 0.0

    top_width = np.linalg.norm(pts[1] - pts[0])
    bottom_width = np.linalg.norm(pts[2] - pts[3])
    left_height = np.linalg.norm(pts[3] - pts[0])
    right_height = np.linalg.norm(pts[2] - pts[1])
    avg_width = (top_width + bottom_width) / 2.0
    avg_height = (left_height + right_height) / 2.0
    aspect = avg_height / max(avg_width, 1.0)
    aspect_score = max(0.0, 1.0 - abs(aspect - 1.414) / 0.50)

    top, bottom, left, right = line_segments
    coverage = (
        _line_segment_coverage(top, pts[0])
        + _line_segment_coverage(top, pts[1])
        + _line_segment_coverage(bottom, pts[2])
        + _line_segment_coverage(bottom, pts[3])
        + _line_segment_coverage(left, pts[0])
        + _line_segment_coverage(left, pts[3])
        + _line_segment_coverage(right, pts[1])
        + _line_segment_coverage(right, pts[2])
    ) / 8.0

    contrast_score = min(1.0, sum(line_scores) / 2.10)
    top_y = (pts[0, 1] + pts[1, 1]) / 2.0
    top_position_score = min(1.0, max(0.0, top_y / (h * 0.12)))

    return float(
        aspect_score * 0.34
        + coverage * 0.34
        + contrast_score * 0.22
        + top_position_score * 0.10
    )


def _line_segment_coverage(segment, point):
    start = np.array(segment[:2], dtype=np.float32)
    end = np.array(segment[2:], dtype=np.float32)
    direction = end - start
    denom = float(np.dot(direction, direction))
    if denom <= 1e-6:
        return 0.0
    t = float(np.dot(point - start, direction) / denom)
    if 0.0 <= t <= 1.0:
        return 1.0
    return max(0.0, 1.0 - abs(t - 0.5) * 1.4)


def _detect_document_corners_fast(img):
    """Detect the best document quad using fast contour-based CV."""
    h, w = img.shape[:2]
    scale = min(1.0, DETECTION_MAX_DIM / max(h, w))
    if scale < 1.0:
        small = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        small = img

    masks = _build_document_masks(small)
    best_quad = None
    best_score = 0.0

    for mask, method_weight in masks:
        for quad, score in _find_quads_in_mask(mask, small.shape, method_weight):
            if score > best_score:
                best_quad = quad
                best_score = score

    if best_quad is None:
        return None, 0.0

    pts = best_quad.astype(np.float32)
    if scale < 1.0:
        pts /= scale

    return _clip_and_order_corners(pts, (w, h)), best_score


def _is_low_detail_image(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(np.std(gray)) < 6.0


def _build_document_masks(img):
    """Create a small set of cheap masks that work across common scan photos."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)

    median = float(np.median(blurred))
    if median < 8:
        low, high = 30, 100
    else:
        low = int(max(10, 0.66 * median))
        high = int(min(255, 1.33 * median))
        if high <= low:
            high = min(255, low * 2)

    edges = cv2.Canny(blurred, low, high)
    edge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.dilate(edges, edge_kernel, iterations=1)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, edge_kernel, iterations=1)

    _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    otsu_inv = cv2.bitwise_not(otsu)

    adaptive = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 7
    )

    grad_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    gradient = cv2.morphologyEx(blurred, cv2.MORPH_GRADIENT, grad_kernel)
    _, gradient = cv2.threshold(gradient, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    masks = []
    for raw_mask, weight in (
        (edges, 1.00),
        (otsu, 0.94),
        (otsu_inv, 0.88),
        (adaptive, 0.82),
        (gradient, 0.78),
    ):
        cleaned = cv2.morphologyEx(raw_mask, cv2.MORPH_CLOSE, close_kernel, iterations=1)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, edge_kernel, iterations=1)
        masks.append((cleaned, weight))

    return masks


def _find_quads_in_mask(mask, img_shape, method_weight=1.0):
    h, w = img_shape[:2]
    img_area = h * w
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:14]

    results = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < img_area * 0.06 or area > img_area * 0.998:
            continue

        for quad, fit_weight in _quad_candidates_from_contour(cnt):
            score = _score_document_quad(quad, img_shape, method_weight * fit_weight, contour_area=area)
            if score > 0.28:
                results.append((quad, score))

    return results


def _quad_candidates_from_contour(contour):
    hull = cv2.convexHull(contour)
    peri = cv2.arcLength(hull, True)
    if peri <= 0:
        return []

    candidates = []
    for eps in (0.012, 0.018, 0.025, 0.035, 0.05, 0.07):
        approx = cv2.approxPolyDP(hull, eps * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            candidates.append((approx.reshape(4, 2).astype(np.float32), 1.0 - min(eps, 0.05)))
            break

    rect = cv2.minAreaRect(hull)
    box = cv2.boxPoints(rect).astype(np.float32)
    candidates.append((box, 0.82))

    return candidates


def _score_document_quad(quad, img_shape, method_weight=1.0, contour_area=None):
    h, w = img_shape[:2]
    img_area = float(h * w)
    pts = np.array(quad, dtype=np.float32).reshape(4, 2)
    ordered = np.array(_order_points(pts), dtype=np.float32)

    area = abs(cv2.contourArea(ordered.reshape(-1, 1, 2).astype(np.float32)))
    if area <= 1:
        return 0.0

    area_ratio = area / img_area
    if area_ratio < 0.06 or area_ratio > 0.995:
        return 0.0
    if area_ratio < 0.18:
        area_score = area_ratio / 0.18
    elif area_ratio <= 0.92:
        area_score = 1.0
    else:
        area_score = max(0.55, 1.0 - ((area_ratio - 0.92) / 0.075) * 0.35)

    sides = []
    for idx in range(4):
        sides.append(np.linalg.norm(ordered[idx] - ordered[(idx + 1) % 4]))
    if min(sides) < min(w, h) * 0.08:
        return 0.0

    width = (sides[0] + sides[2]) / 2.0
    height = (sides[1] + sides[3]) / 2.0
    aspect = max(width, height) / max(1.0, min(width, height))
    if aspect > 3.2:
        aspect_score = 0.25
    elif aspect > 2.4:
        aspect_score = 0.55
    elif aspect > 1.8:
        aspect_score = 0.82
    else:
        aspect_score = 1.0

    angle_score = _quad_angle_score(ordered)
    side_balance = min(sides[0], sides[2]) / max(sides[0], sides[2]) * 0.5
    side_balance += min(sides[1], sides[3]) / max(sides[1], sides[3]) * 0.5

    rect_fit = 0.75
    if contour_area:
        rect_fit = min(1.0, max(0.35, float(contour_area) / area))

    center = ordered.mean(axis=0)
    center_offset = np.linalg.norm(center - np.array([w / 2.0, h / 2.0]))
    center_score = max(0.45, 1.0 - center_offset / (0.75 * max(w, h)))

    margin = min(w, h) * 0.015
    near_edges = sum(
        x <= margin or x >= w - margin or y <= margin or y >= h - margin
        for x, y in ordered
    )
    border_penalty = 0.88 if near_edges >= 3 and area_ratio > 0.93 else 1.0

    score = (
        area_score * 0.27
        + angle_score * 0.24
        + aspect_score * 0.18
        + rect_fit * 0.14
        + side_balance * 0.10
        + center_score * 0.07
    )

    return float(score * method_weight * border_penalty)


def _quad_angle_score(ordered):
    scores = []
    for idx in range(4):
        prev_pt = ordered[(idx - 1) % 4]
        pt = ordered[idx]
        next_pt = ordered[(idx + 1) % 4]
        v1 = prev_pt - pt
        v2 = next_pt - pt
        denom = np.linalg.norm(v1) * np.linalg.norm(v2)
        if denom <= 1e-6:
            return 0.0
        cos_angle = np.dot(v1, v2) / denom
        angle = np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0)))
        diff = abs(angle - 90.0)
        scores.append(max(0.0, 1.0 - diff / 45.0))
    return float(np.mean(scores))


def _clip_and_order_corners(corners, img_size):
    w, h = img_size
    pts = np.array(corners, dtype=np.float32).reshape(4, 2)
    pts[:, 0] = np.clip(pts[:, 0], 0, w - 1)
    pts[:, 1] = np.clip(pts[:, 1], 0, h - 1)
    return _apply_smart_inset(_order_points(pts), (w, h))


def _default_corners(img_size):
    w, h = img_size
    margin_x = max(8, int(w * 0.025))
    margin_y = max(8, int(h * 0.025))
    return [
        (margin_x, margin_y),
        (w - margin_x, margin_y),
        (w - margin_x, h - margin_y),
        (margin_x, h - margin_y),
    ]


def _calculate_inward_score(corners, img_size):
    """Calculate how far inward the corners are from image edges"""
    w, h = img_size
    total_distance = 0
    
    for x, y in corners:
        # Distance from nearest edge
        dist = min(x, y, w - x, h - y)
        total_distance += dist
    
    # Normalize by image size
    return total_distance / (min(w, h) * 4)


def _evaluate_corners_quality(corners, img_size):
    """
    Evaluate the quality of detected corners.
    Returns a score between 0 and 1 (higher is better).
    """
    w, h = img_size
    img_area = w * h
    
    # Convert to numpy array if needed
    if not isinstance(corners, np.ndarray):
        corners = np.array(corners)
    
    # Calculate area
    try:
        area = cv2.contourArea(corners.reshape(-1, 1, 2).astype(np.int32))
    except:
        return 0.0
    
    area_ratio = area / img_area
    
    # Penalize if too small or too large
    if area_ratio < 0.15 or area_ratio > 0.95:
        return 0.1
    
    # Optimal area is 40-85% of image
    if 0.4 <= area_ratio <= 0.85:
        area_score = 1.0
    elif 0.25 <= area_ratio < 0.4:
        area_score = 0.7
    elif 0.85 < area_ratio <= 0.92:
        area_score = 0.6
    else:
        area_score = 0.4
    
    # Check edge proximity (penalize corners on image edges)
    margin = min(w, h) * 0.04
    edge_count = 0
    edge_penalty = 0
    
    for x, y in corners:
        if x < margin or x > w - margin or y < margin or y > h - margin:
            edge_count += 1
            # Calculate how close to edge
            dist_to_edge = min(x, y, w - x, h - y)
            if dist_to_edge < margin:
                edge_penalty += (1 - dist_to_edge / margin) * 0.15
    
    # Heavy penalty if 3+ corners are on edges
    if edge_count >= 3:
        edge_score = 0.2
    elif edge_count == 2:
        edge_score = 0.6
    elif edge_count == 1:
        edge_score = 0.85
    else:
        edge_score = 1.0
    
    edge_score = max(0, edge_score - edge_penalty)
    
    # Check if corners form a reasonable quadrilateral
    ordered = _order_points(corners)
    
    # Calculate side lengths
    side_lengths = []
    for i in range(4):
        p1 = np.array(ordered[i])
        p2 = np.array(ordered[(i + 1) % 4])
        length = np.linalg.norm(p2 - p1)
        side_lengths.append(length)
    
    # Check aspect ratio
    width1, height1, width2, height2 = side_lengths
    avg_width = (width1 + width2) / 2
    avg_height = (height1 + height2) / 2
    
    if avg_width == 0 or avg_height == 0:
        return 0.0
    
    aspect_ratio = max(avg_width, avg_height) / min(avg_width, avg_height)
    
    # Documents typically have aspect ratio between 1:1 and 2:1
    if aspect_ratio <= 1.5:
        aspect_score = 1.0
    elif aspect_ratio <= 2.0:
        aspect_score = 0.9
    elif aspect_ratio <= 2.5:
        aspect_score = 0.7
    elif aspect_ratio <= 3.0:
        aspect_score = 0.5
    else:
        aspect_score = 0.3
    
    # Check angles (should be close to 90 degrees)
    angles = []
    for i in range(4):
        p1 = np.array(ordered[i])
        p2 = np.array(ordered[(i + 1) % 4])
        p3 = np.array(ordered[(i + 2) % 4])
        
        v1 = p1 - p2
        v2 = p3 - p2
        
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        angle = np.arccos(np.clip(cos_angle, -1, 1))
        angles.append(np.degrees(angle))
    
    # Calculate how close angles are to 90 degrees
    angle_diffs = [abs(angle - 90) for angle in angles]
    avg_angle_diff = np.mean(angle_diffs)
    
    if avg_angle_diff < 5:
        angle_score = 1.0
    elif avg_angle_diff < 10:
        angle_score = 0.95
    elif avg_angle_diff < 15:
        angle_score = 0.85
    elif avg_angle_diff < 20:
        angle_score = 0.7
    elif avg_angle_diff < 30:
        angle_score = 0.5
    else:
        angle_score = 0.3
    
    # Combined score with weights
    total_score = (
        area_score * 0.25 +
        edge_score * 0.35 +
        aspect_score * 0.20 +
        angle_score * 0.20
    )
    
    return total_score


def _apply_smart_inset(corners, img_size):
    """Apply intelligent inset if corners are too close to image edges"""
    w, h = img_size
    edge_threshold = min(w, h) * 0.03  # 3% from edge is considered "on edge"
    
    adjusted = []
    for x, y in corners:
        # Check if point is very close to any edge
        near_left = x < edge_threshold
        near_right = x > w - edge_threshold
        near_top = y < edge_threshold
        near_bottom = y > h - edge_threshold
        
        # If on edge, move it inward slightly
        if near_left or near_right or near_top or near_bottom:
            inset = min(w, h) * 0.02  # 2% inset
            new_x = x
            new_y = y
            
            if near_left:
                new_x = max(x, inset)
            elif near_right:
                new_x = min(x, w - inset)
            
            if near_top:
                new_y = max(y, inset)
            elif near_bottom:
                new_y = min(y, h - inset)
            
            adjusted.append((int(new_x), int(new_y)))
        else:
            adjusted.append((int(x), int(y)))
    
    return adjusted


def _detect_strategy_contour_hierarchy(img):
    """Strategy 5: Use contour hierarchy to find inner document contours"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Enhance contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Multiple threshold attempts
    best_contour = None
    best_score = 0
    
    # Try Otsu
    _, thresh1 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Try adaptive
    thresh2 = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 11, 2)
    
    # Try mean-based
    mean_val = np.mean(enhanced)
    _, thresh3 = cv2.threshold(enhanced, mean_val - 20, 255, cv2.THRESH_BINARY)
    
    for thresh in [thresh1, thresh2, thresh3]:
        # Check if we need to invert
        if np.mean(thresh) < 127:
            thresh = cv2.bitwise_not(thresh)
        
        # Morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
        
        # Find contours with hierarchy
        contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        if hierarchy is None or len(contours) == 0:
            continue
        
        # Look for contours that have a parent (inner contours)
        h, w = img.shape[:2]
        img_area = h * w
        
        for i, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            
            # Skip if too small or too large
            if area < img_area * 0.05 or area > img_area * 0.98:
                continue
            
            # Try to approximate to quad
            peri = cv2.arcLength(cnt, True)
            for eps in [0.01, 0.015, 0.02, 0.025, 0.03, 0.04]:
                approx = cv2.approxPolyDP(cnt, eps * peri, True)
                if len(approx) == 4:
                    pts = approx.reshape(4, 2)
                    if not _is_image_border(pts, img.shape):
                        score = _calculate_quad_score(pts, img.shape)
                        if score > best_score:
                            best_contour = approx
                            best_score = score
                    break
    
    return best_contour, best_score


def _detect_strategy_canny_aggressive(img):
    """Strategy 0: Aggressive Canny edge detection with multiple thresholds"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply bilateral filter
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    
    # Try multiple Canny thresholds
    best_contour = None
    best_score = 0
    
    for low, high in [(30, 100), (50, 150), (75, 200), (100, 250)]:
        edges = cv2.Canny(gray, low, high)
        
        # Dilate to connect edges
        kernel = np.ones((5, 5), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=2)
        edges = cv2.erode(edges, kernel, iterations=1)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        contour, score = _find_best_quad_contour(contours, img.shape)
        if score > best_score:
            best_contour = contour
            best_score = score
    
    return best_contour, best_score


def _detect_strategy_adaptive(img):
    """Strategy 1: Adaptive thresholding + contour detection"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply bilateral filter to reduce noise while keeping edges sharp
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    
    # Adaptive thresholding
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                    cv2.THRESH_BINARY, 11, 2)
    
    # Invert if needed (document should be white)
    if np.mean(thresh) < 127:
        thresh = cv2.bitwise_not(thresh)
    
    # Morphological operations to close gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    return _find_best_quad_contour(contours, img.shape)


def _detect_strategy_morphological(img):
    """Strategy 2: Morphological gradient + edge detection"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Morphological gradient to enhance edges
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    gradient = cv2.morphologyEx(blurred, cv2.MORPH_GRADIENT, kernel)
    
    # Apply threshold
    _, thresh = cv2.threshold(gradient, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Close gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=3)
    
    # Remove small noise
    kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel_small, iterations=1)
    
    # Find contours
    contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    return _find_best_quad_contour(contours, img.shape)


def _detect_strategy_hough(img):
    """Strategy 3: Hough line detection + intersection finding"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Edge detection with multiple thresholds
    edges = cv2.Canny(gray, 30, 150, apertureSize=3)
    
    # Dilate to connect broken edges
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)
    
    # Detect lines using Hough transform
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80, 
                            minLineLength=int(min(img.shape[:2]) * 0.2), 
                            maxLineGap=20)
    
    if lines is None or len(lines) < 4:
        return None, 0
    
    # Group lines into horizontal and vertical
    h_lines, v_lines = _group_lines(lines, img.shape)
    
    if len(h_lines) < 2 or len(v_lines) < 2:
        return None, 0
    
    # Find intersections to form corners
    corners = _find_line_intersections(h_lines, v_lines, img.shape)
    
    if corners is not None and len(corners) == 4:
        score = _calculate_quad_score(corners, img.shape)
        return corners.reshape(-1, 1, 2).astype(np.int32), score
    
    return None, 0


def _detect_strategy_color_based(img):
    """Strategy 4: Color-based segmentation for documents on colored backgrounds"""
    # Convert to LAB color space for better color separation
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    
    # Apply CLAHE to L channel
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    
    # Merge back
    lab = cv2.merge([l_channel, a_channel, b_channel])
    enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    # Convert to grayscale
    gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
    
    # Apply Otsu's thresholding
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Check if we need to invert
    if np.mean(thresh) < 127:
        thresh = cv2.bitwise_not(thresh)
    
    # Morphological operations
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=3)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    return _find_best_quad_contour(contours, img.shape)


def _find_best_quad_contour(contours, img_shape):
    """Find the best quadrilateral contour from a list of contours"""
    if not contours:
        return None, 0
    
    h, w = img_shape[:2]
    img_area = h * w
    
    # Sort by area
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    
    best_contour = None
    best_score = 0
    
    # Check top 20 contours
    for cnt in contours[:20]:
        area = cv2.contourArea(cnt)
        
        # Skip if too small or too large
        if area < img_area * 0.05 or area > img_area * 0.98:
            continue
        
        # Approximate to polygon
        peri = cv2.arcLength(cnt, True)
        
        # Try multiple epsilon values to find a quadrilateral
        for epsilon_factor in [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]:
            approx = cv2.approxPolyDP(cnt, epsilon_factor * peri, True)
            if len(approx) == 4:
                # Check if this quad is not just the image border
                pts = approx.reshape(4, 2)
                if _is_image_border(pts, img_shape):
                    continue
                    
                score = _calculate_quad_score(approx.reshape(4, 2), img_shape)
                if score > best_score:
                    best_contour = approx
                    best_score = score
                break
    
    return best_contour, best_score


def _is_image_border(quad, img_shape):
    """Check if the quadrilateral is just the image border"""
    h, w = img_shape[:2]
    margin = min(w, h) * 0.04  # 4% margin - more strict
    
    # Count how many points are near edges
    edge_points = 0
    for x, y in quad:
        if x < margin or x > w - margin or y < margin or y > h - margin:
            edge_points += 1
    
    # If 3 or more points are on edges, it's probably the border
    if edge_points >= 3:
        return True
    
    # Check if quad covers almost entire image
    area = cv2.contourArea(quad.reshape(-1, 1, 2).astype(np.int32))
    if area > (h * w * 0.92):  # More strict - 92% instead of 95%
        return True
    
    # Check if all sides are very close to image edges
    ordered = _order_points(quad)
    tl, tr, br, bl = ordered
    
    # Check if top edge is near top
    top_near = (tl[1] < margin and tr[1] < margin)
    # Check if bottom edge is near bottom
    bottom_near = (bl[1] > h - margin and br[1] > h - margin)
    # Check if left edge is near left
    left_near = (tl[0] < margin and bl[0] < margin)
    # Check if right edge is near right
    right_near = (tr[0] > w - margin and br[0] > w - margin)
    
    # If 3 or 4 edges are near image edges, it's the border
    edge_count = sum([top_near, bottom_near, left_near, right_near])
    if edge_count >= 3:
        return True
    
    return False


def _calculate_quad_score(quad, img_shape):
    """Calculate a quality score for a detected quadrilateral"""
    h, w = img_shape[:2]
    img_area = h * w
    
    # Calculate area
    area = cv2.contourArea(quad.reshape(-1, 1, 2).astype(np.int32))
    area_ratio = area / img_area
    
    # Prefer larger areas (but not too large)
    if area_ratio < 0.1:
        return 0
    area_score = min(area_ratio, 0.9) if area_ratio < 0.95 else 0.5
    
    # Check if it's roughly rectangular
    ordered = _order_points(quad)
    
    # Calculate side lengths
    side_lengths = []
    for i in range(4):
        p1 = ordered[i]
        p2 = ordered[(i + 1) % 4]
        length = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
        side_lengths.append(length)
    
    # Check aspect ratio (should be reasonable for a document)
    width1 = side_lengths[0]
    width2 = side_lengths[2]
    height1 = side_lengths[1]
    height2 = side_lengths[3]
    
    avg_width = (width1 + width2) / 2
    avg_height = (height1 + height2) / 2
    
    if avg_width == 0 or avg_height == 0:
        return 0
    
    aspect_ratio = max(avg_width, avg_height) / min(avg_width, avg_height)
    
    # Documents typically have aspect ratio between 1:1 and 2:1
    if aspect_ratio > 3:
        aspect_score = 0.3
    elif aspect_ratio > 2:
        aspect_score = 0.6
    else:
        aspect_score = 1.0
    
    # Check angles (should be close to 90 degrees)
    angles = []
    for i in range(4):
        p1 = np.array(ordered[i])
        p2 = np.array(ordered[(i + 1) % 4])
        p3 = np.array(ordered[(i + 2) % 4])
        
        v1 = p1 - p2
        v2 = p3 - p2
        
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        angle = np.arccos(np.clip(cos_angle, -1, 1))
        angles.append(np.degrees(angle))
    
    # Calculate how close angles are to 90 degrees
    angle_diffs = [abs(angle - 90) for angle in angles]
    avg_angle_diff = np.mean(angle_diffs)
    
    if avg_angle_diff < 10:
        angle_score = 1.0
    elif avg_angle_diff < 20:
        angle_score = 0.8
    elif avg_angle_diff < 30:
        angle_score = 0.5
    else:
        angle_score = 0.2
    
    # Combined score
    total_score = (area_score * 0.4 + aspect_score * 0.3 + angle_score * 0.3)
    
    return total_score


def _group_lines(lines, img_shape):
    """Group lines into horizontal and vertical"""
    h, w = img_shape[:2]
    h_lines = []
    v_lines = []
    
    for line in lines:
        x1, y1, x2, y2 = line[0]
        
        # Calculate angle
        angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
        
        # Horizontal lines (angle close to 0 or 180)
        if abs(angle) < 20 or abs(angle) > 160:
            h_lines.append(line[0])
        # Vertical lines (angle close to 90 or -90)
        elif 70 < abs(angle) < 110:
            v_lines.append(line[0])
    
    return h_lines, v_lines


def _find_line_intersections(h_lines, v_lines, img_shape):
    """Find intersections between horizontal and vertical lines to form corners"""
    h, w = img_shape[:2]
    
    # Sort lines by position
    h_lines = sorted(h_lines, key=lambda l: (l[1] + l[3]) / 2)
    v_lines = sorted(v_lines, key=lambda l: (l[0] + l[2]) / 2)
    
    # Take top and bottom horizontal lines
    if len(h_lines) >= 2:
        top_h = h_lines[0]
        bottom_h = h_lines[-1]
    else:
        return None
    
    # Take left and right vertical lines
    if len(v_lines) >= 2:
        left_v = v_lines[0]
        right_v = v_lines[-1]
    else:
        return None
    
    # Calculate intersections
    corners = []
    
    # Top-left
    tl = _line_intersection(top_h, left_v)
    if tl is not None:
        corners.append(tl)
    
    # Top-right
    tr = _line_intersection(top_h, right_v)
    if tr is not None:
        corners.append(tr)
    
    # Bottom-right
    br = _line_intersection(bottom_h, right_v)
    if br is not None:
        corners.append(br)
    
    # Bottom-left
    bl = _line_intersection(bottom_h, left_v)
    if bl is not None:
        corners.append(bl)
    
    if len(corners) == 4:
        return np.array(corners, dtype=np.float32)
    
    return None


def _line_intersection(line1, line2):
    """Calculate intersection point of two lines"""
    x1, y1, x2, y2 = line1
    x3, y3, x4, y4 = line2
    
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    
    if abs(denom) < 1e-6:
        return None
    
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
    
    return (int(px), int(py))


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
    img = imread_unicode(image_path)
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
    imwrite_unicode(output_path, img_bgr)


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


def scanned_images_to_pdf(images_bgr: list, output_pdf: str, ctx=None):
    """
    Convert multiple processed BGR images to a multi-page PDF.
    Each image becomes one page.
    """
    if not images_bgr:
        raise ValueError("En az bir görüntü gerekli.")

    pil_pages = []
    total = len(images_bgr)
    for i, img_bgr in enumerate(images_bgr):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(i, total, f"{i+1}/{total} resim PDF için hazırlanıyor...")

        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        pil_pages.append(pil_img)

    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(total, total, "PDF kaydediliyor...")

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
