"""
ONNX-Based Document Corner Detection
-------------------------------------
Uses ONNX Runtime with U2-Net model for accurate document corner detection.
"""

import os
import sys
import numpy as np
import cv2
from pathlib import Path


# Global cache for ONNX session
_ONNX_SESSION_CACHE = {}
MODEL_FILENAMES = (
    "u2netp_document.onnx",
    "u2net_document.onnx",
    "u2netp.onnx",
    "u2net.onnx",
)


def _unique_paths(paths):
    """Return existing candidate paths without duplicates."""
    seen = set()
    for path in paths:
        if not path:
            continue
        try:
            resolved = Path(path).expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        key = os.path.normcase(str(resolved))
        if key not in seen:
            seen.add(key)
            yield resolved


def _candidate_model_dirs():
    """Directories to search in source, frozen, and installed builds."""
    module_path = Path(__file__).resolve()
    project_root = module_path.parents[2]
    exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None
    bundle_dir = Path(getattr(sys, "_MEIPASS", "")).resolve() if getattr(sys, "_MEIPASS", None) else None

    env_model_dir = os.environ.get("PDFAURA_MODEL_DIR")
    local_app_data = os.environ.get("LOCALAPPDATA")

    candidates = [
        Path(env_model_dir) if env_model_dir else None,
        project_root / "models",
        Path.cwd() / "models",
        bundle_dir / "models" if bundle_dir else None,
        bundle_dir.parent / "models" if bundle_dir else None,
        exe_dir / "models" if exe_dir else None,
        exe_dir / "_internal" / "models" if exe_dir else None,
        Path(local_app_data) / "PDF Aura" / "models" if local_app_data else None,
    ]

    return list(_unique_paths(candidates))


def get_model_path():
    """Get the path to the ONNX model in source, frozen, or installed builds."""
    explicit_model = os.environ.get("PDFAURA_ONNX_MODEL")
    if explicit_model:
        explicit_path = Path(explicit_model).expanduser()
        if explicit_path.is_file():
            return str(explicit_path.resolve())

    for model_dir in _candidate_model_dirs():
        for filename in MODEL_FILENAMES:
            path = model_dir / filename
            if path.is_file():
                return str(path)
    
    return None


def is_onnx_available():
    """Check if ONNX Runtime is available and model exists"""
    try:
        import onnxruntime
        model_path = get_model_path()
        return model_path is not None
    except ImportError:
        return False


def _get_onnx_session():
    """Get or create cached ONNX session"""
    try:
        import onnxruntime as ort
    except ImportError:
        return None
    
    model_path = get_model_path()
    if model_path is None:
        return None
    
    # Check cache
    if model_path in _ONNX_SESSION_CACHE:
        return _ONNX_SESSION_CACHE[model_path]
    
    # Create new session
    try:
        session = ort.InferenceSession(
            model_path,
            providers=['CPUExecutionProvider']
        )
        _ONNX_SESSION_CACHE[model_path] = session
        return session
    except Exception:
        return None


def detect_document_corners_onnx(image_path: str):
    """
    Detect document corners using ONNX model.
    Returns list of 4 (x, y) tuples or None if detection fails.
    """
    from .document_scanner import imread_unicode, _order_points
    
    # Get cached session
    session = _get_onnx_session()
    if session is None:
        return None
    
    # Load image
    img = imread_unicode(image_path)
    if img is None:
        return None
    
    orig_h, orig_w = img.shape[:2]
    
    # Preprocess image for U2-Net
    input_size = 320  # U2-Net-P input size
    img_resized = cv2.resize(img, (input_size, input_size), interpolation=cv2.INTER_AREA)
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    
    # Normalize to [0, 1]
    img_normalized = img_rgb.astype(np.float32) / 255.0
    
    # Transpose to CHW format and add batch dimension
    img_input = np.transpose(img_normalized, (2, 0, 1))
    img_input = np.expand_dims(img_input, axis=0)
    
    # Run inference
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    
    result = session.run([output_name], {input_name: img_input})[0]
    
    # Post-process result
    mask = result[0, 0]  # Remove batch and channel dimensions
    mask = (mask * 255).astype(np.uint8)
    
    # Resize mask back to original size
    mask = cv2.resize(mask, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
    
    # Threshold
    _, binary_mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    
    # Find contours
    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None
    
    # Get largest contour
    largest_contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest_contour)
    
    # Check if area is reasonable
    if area < (orig_h * orig_w * 0.1):
        return None
    
    # Approximate to quadrilateral
    peri = cv2.arcLength(largest_contour, True)
    for epsilon_factor in [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]:
        approx = cv2.approxPolyDP(largest_contour, epsilon_factor * peri, True)
        if len(approx) == 4:
            corners = approx.reshape(4, 2)
            return _order_points(corners)
    
    # If we can't get exactly 4 corners, use bounding rectangle
    rect = cv2.minAreaRect(largest_contour)
    box = cv2.boxPoints(rect)
    box = np.intp(box)  # Use intp instead of deprecated int0
    return _order_points(box)


def detect_with_onnx_fallback(image_path: str):
    """
    Try ONNX detection, fall back to classical methods if it fails.
    """
    if not is_onnx_available():
        return None
    
    try:
        corners = detect_document_corners_onnx(image_path)
        
        if corners is not None:
            # Validate corners
            from .document_scanner import imread_unicode
            img = imread_unicode(image_path)
            if img is not None:
                h, w = img.shape[:2]
                margin = min(w, h) * 0.05
                
                # Count corners near edges
                edge_count = 0
                for x, y in corners:
                    if x < margin or x > w - margin or y < margin or y > h - margin:
                        edge_count += 1
                
                # If less than 3 corners are on edges, it's probably good
                if edge_count < 3:
                    return corners
        
        return None
        
    except Exception:
        return None
