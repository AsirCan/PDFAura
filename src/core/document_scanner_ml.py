"""
ML-Enhanced Document Scanner
-----------------------------
Uses a hybrid approach: classical CV + simple ML for better corner detection
"""

import os
import numpy as np
import cv2


def detect_document_corners_ml(image_path: str):
    """
    ML-enhanced document corner detection.
    Uses a combination of edge detection, contour analysis, and heuristics.
    """
    from .document_scanner import imread_unicode, _order_points
    
    img = imread_unicode(image_path)
    if img is None:
        return None
    
    h, w = img.shape[:2]
    
    # Resize for processing
    scale = 1.0
    max_dim = 1200
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        small = img
    
    # Only use fast strategies (skip GrabCut and Watershed - too slow)
    strategies = [
        _detect_with_edge_linking,
    ]
    
    best_corners = None
    best_score = 0
    
    for strategy in strategies:
        try:
            corners, score = strategy(small)
            if corners is not None and score > best_score:
                best_corners = corners
                best_score = score
        except Exception:
            continue
    
    if best_corners is not None and best_score > 0.3:
        pts = np.array(best_corners, dtype=float)
        if scale != 1.0:
            pts /= scale
        return _order_points(pts)
    
    return None


def _detect_with_grabcut(img):
    """Use GrabCut for foreground/background segmentation"""
    h, w = img.shape[:2]
    
    # Initialize mask
    mask = np.zeros(img.shape[:2], np.uint8)
    
    # Background and foreground models
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    
    # Define initial rectangle (assume document is in center 80%)
    margin = 0.1
    rect = (
        int(w * margin),
        int(h * margin),
        int(w * (1 - 2 * margin)),
        int(h * (1 - 2 * margin))
    )
    
    # Apply GrabCut
    cv2.grabCut(img, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
    
    # Create binary mask
    mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
    
    # Morphological operations
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
    mask2 = cv2.morphologyEx(mask2, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask2 = cv2.morphologyEx(mask2, cv2.MORPH_OPEN, kernel, iterations=1)
    
    # Find contours
    contours, _ = cv2.findContours(mask2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None, 0
    
    # Get largest contour
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    
    if area < (h * w * 0.1):
        return None, 0
    
    # Approximate to quadrilateral
    peri = cv2.arcLength(largest, True)
    for eps in [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]:
        approx = cv2.approxPolyDP(largest, eps * peri, True)
        if len(approx) == 4:
            corners = approx.reshape(4, 2)
            score = _score_corners(corners, img.shape)
            return corners, score
    
    return None, 0


def _detect_with_watershed(img):
    """Use watershed algorithm for segmentation"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Enhance contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Threshold
    _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Noise removal
    kernel = np.ones((3, 3), np.uint8)
    opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
    
    # Sure background area
    sure_bg = cv2.dilate(opening, kernel, iterations=3)
    
    # Finding sure foreground area
    dist_transform = cv2.distanceTransform(opening, cv2.DIST_L2, 5)
    _, sure_fg = cv2.threshold(dist_transform, 0.5 * dist_transform.max(), 255, 0)
    
    # Finding unknown region
    sure_fg = np.uint8(sure_fg)
    unknown = cv2.subtract(sure_bg, sure_fg)
    
    # Marker labelling
    _, markers = cv2.connectedComponents(sure_fg)
    markers = markers + 1
    markers[unknown == 255] = 0
    
    # Apply watershed
    markers = cv2.watershed(img, markers)
    
    # Create mask from markers
    mask = np.zeros(gray.shape, dtype=np.uint8)
    mask[markers > 1] = 255
    
    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None, 0
    
    # Get largest contour
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    
    h, w = img.shape[:2]
    if area < (h * w * 0.1):
        return None, 0
    
    # Approximate to quadrilateral
    peri = cv2.arcLength(largest, True)
    for eps in [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]:
        approx = cv2.approxPolyDP(largest, eps * peri, True)
        if len(approx) == 4:
            corners = approx.reshape(4, 2)
            score = _score_corners(corners, img.shape)
            return corners, score
    
    return None, 0


def _detect_with_edge_linking(img):
    """Advanced edge detection with intelligent linking"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    
    # Multi-scale edge detection
    edges_list = []
    for sigma in [0.5, 1.0, 1.5]:
        blurred = cv2.GaussianBlur(gray, (0, 0), sigma)
        edges = cv2.Canny(blurred, 30, 100)
        edges_list.append(edges)
    
    # Combine edges
    combined = np.maximum.reduce(edges_list)
    
    # Morphological operations to connect edges
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    combined = cv2.dilate(combined, kernel, iterations=2)
    combined = cv2.erode(combined, kernel, iterations=1)
    
    # Find contours
    contours, _ = cv2.findContours(combined, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None, 0
    
    # Sort by area
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    
    # Try top contours
    for cnt in contours[:10]:
        area = cv2.contourArea(cnt)
        
        if area < (h * w * 0.1) or area > (h * w * 0.95):
            continue
        
        # Approximate to quadrilateral
        peri = cv2.arcLength(cnt, True)
        for eps in [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.06]:
            approx = cv2.approxPolyDP(cnt, eps * peri, True)
            if len(approx) == 4:
                corners = approx.reshape(4, 2)
                
                # Check if it's not the image border
                if _is_valid_document(corners, (w, h)):
                    score = _score_corners(corners, img.shape)
                    return corners, score
    
    return None, 0


def _is_valid_document(corners, img_size):
    """Check if detected corners represent a valid document"""
    w, h = img_size
    margin = min(w, h) * 0.05
    
    # Count corners near edges
    edge_count = 0
    for x, y in corners:
        if x < margin or x > w - margin or y < margin or y > h - margin:
            edge_count += 1
    
    # If more than 2 corners are on edges, probably not a document
    if edge_count > 2:
        return False
    
    # Check area
    area = cv2.contourArea(corners.reshape(-1, 1, 2).astype(np.int32))
    if area > (w * h * 0.95):
        return False
    
    return True


def _score_corners(corners, img_shape):
    """Score the quality of detected corners"""
    h, w = img_shape[:2]
    img_area = h * w
    
    # Calculate area
    area = cv2.contourArea(corners.reshape(-1, 1, 2).astype(np.int32))
    area_ratio = area / img_area
    
    # Prefer documents that are 20-90% of image
    if area_ratio < 0.2 or area_ratio > 0.9:
        return 0.1
    
    area_score = min(area_ratio / 0.7, 1.0)
    
    # Check if corners form a reasonable quadrilateral
    from .document_scanner import _order_points
    ordered = _order_points(corners)
    
    # Calculate side lengths
    side_lengths = []
    for i in range(4):
        p1 = ordered[i]
        p2 = ordered[(i + 1) % 4]
        length = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
        side_lengths.append(length)
    
    # Check aspect ratio
    width1, height1, width2, height2 = side_lengths
    avg_width = (width1 + width2) / 2
    avg_height = (height1 + height2) / 2
    
    if avg_width == 0 or avg_height == 0:
        return 0
    
    aspect_ratio = max(avg_width, avg_height) / min(avg_width, avg_height)
    
    if aspect_ratio > 3:
        aspect_score = 0.3
    elif aspect_ratio > 2:
        aspect_score = 0.7
    else:
        aspect_score = 1.0
    
    # Combined score
    return area_score * 0.6 + aspect_score * 0.4
