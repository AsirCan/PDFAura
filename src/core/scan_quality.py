"""Faz 8 — Scanner AI quality control.

Turns one camera frame into a short quality report before it is exported:
blur, brightness, glare, illumination/shadow and framing. Everything runs on
a downscaled copy with OpenCV + NumPy only, so a 2 MP photo is analysed in a
few milliseconds and the scanner UI can call this while the preview updates.

The public entry point is :func:`assess_quality`:

    assess_quality(image_bgr_or_path, corners=None) -> dict

``image_bgr_or_path`` is a BGR/gray NumPy array or a path to an image.
``corners`` is the optional 4-point document quad (TL, TR, BR, BL) in the
*original* image coordinates, as returned by
``document_scanner.detect_document_corners``. When it is given, all metrics
focus on that document instead of the desk around it, and the framing checks
use it directly.

OpenCV is imported defensively: importing this module never fails when the
scanner dependencies are missing, and the assessment then degrades to an
"orta" result with an explanatory message instead of raising.
"""
import os

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - exercised where OpenCV is absent
    cv2 = None
    np = None

QUALITY_GOOD = "iyi"
QUALITY_MEDIUM = "orta"
QUALITY_RETRY = "tekrar çekilmesi önerilir"

# Analysis resolution: 1024 px is enough to see text sharpness while keeping
# the whole assessment well under 100 ms for a 2 MP phone photo.
MAX_ANALYSIS_DIM = 1024
MAX_ILLUMINATION_DIM = 320

# Blur: variance of the Laplacian. A sharp printed page lands far above
# BLUR_OK_VAR; a motion-blurred or out-of-focus frame stays near BLUR_BAD_VAR.
BLUR_BAD_VAR = 30.0
BLUR_OK_VAR = 150.0
BLUR_WARN_SCORE = 0.55

# Brightness: mean gray level. The limit is high because a white page with
# dark text legitimately averages ~245; only near-clipped frames count.
DARK_MEAN = 70.0
BRIGHT_MEAN = 250.0

# Glare: share of pixels whose darkest channel is saturated. A page whose
# *background* is white is mostly saturated, so ratios above this limit are
# treated as white paper rather than a specular highlight.
GLARE_SATURATION = 250
GLARE_PAPER_RATIO = 0.35
GLARE_WARN_RATIO = 0.02
GLARE_SEVERE_RATIO = 0.15

# Shadow: spread between the mean brightness of the 3 x 3 tiles of a heavily
# blurred copy. Blurring first removes text edges, leaving the lighting.
SHADOW_WARN_SPREAD = 55.0
SHADOW_RETRY_SPREAD = 110.0

# One corner within 1 % of the frame border counts as touching it.
FRAMING_EDGE_MARGIN = 0.01
FRAMING_MIN_AREA = 0.25
FRAMING_TOO_SMALL_AREA = 0.12

# Edge alignment: how strong the image gradient is along the detected quad.
EDGE_WARN_SCORE = 0.20

FLAT_WEIGHTS = {"blur": 0.35, "brightness": 0.15, "glare": 0.15,
                "shadow": 0.15, "framing": 0.20}

_WARNINGS = {
    "blur": "Fotoğraf bulanık; cihazı sabit tutup tekrar çekin.",
    "dark": "Fotoğraf çok karanlık; daha fazla ışıkla tekrar çekin.",
    "bright": "Fotoğraf fazla parlak; ışığı azaltın veya belgeyi gölgeleyin.",
    "glare": "Parlama var; ışık kaynağını belgeye doğrudan tutmayın.",
    "shadow": "Gölge veya eşit olmayan aydınlatma var; ışığı dengeli dağıtın.",
    "framing": "Belge kadraja tam sığmamış; dört kenarı da görünür şekilde çekin.",
    "too_small": "Belge görüntüde çok küçük; daha yakından çekin.",
    "edge": "Kenar algılama güveni düşük; köşe noktalarını kontrol edin.",
    "unreadable": "Görüntü okunamadı; kalite değerlendirmesi yapılamadı.",
    "dependency": "Kalite kontrolü için OpenCV ve NumPy gerekli.",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def _empty_metrics():
    return {
        "blur": {"score": None, "laplacian_var": None, "ok": None},
        "brightness": {"score": None, "mean": None, "status": None, "ok": None},
        "glare": {"score": None, "ratio": None, "ok": None},
        "shadow": {"score": None, "unevenness": None, "ok": None},
        "framing": {"score": None, "area_ratio": None, "touching": None,
                    "outside": None, "edge_quality": None, "ok": None},
    }


def _result(label, score, issues, warnings, metrics):
    return {
        "label": label,
        "score": score,          # 0-100, None when no metric could be measured
        "issues": list(issues),  # machine-readable ids, same order as warnings
        "warnings": list(warnings),
        "blur": metrics["blur"],
        "brightness": metrics["brightness"],
        "glare": metrics["glare"],
        "shadow": metrics["shadow"],
        "framing": metrics["framing"],
    }


def _load_image(image_bgr_or_path):
    """Return (BGR/gray ndarray, original (height, width)), or (None, None)."""
    if isinstance(image_bgr_or_path, (str, os.PathLike)):
        try:
            from src.core.document_scanner import imread_unicode
            image = imread_unicode(os.fspath(image_bgr_or_path))
        except Exception:
            image = None
        if image is None:
            return None, None
    elif isinstance(image_bgr_or_path, np.ndarray):
        image = image_bgr_or_path
    else:
        return None, None

    if image.size == 0:
        return None, None

    if image.dtype != np.uint8:
        image = np.asarray(image)
        # float arrays are commonly either 0..1 or 0..255; support both.
        if np.issubdtype(image.dtype, np.floating) and image.size and image.max() <= 1.0:
            image = image * 255.0
        image = np.clip(image, 0, 255).astype(np.uint8)

    if image.ndim == 2:
        pass
    elif image.ndim == 3 and image.shape[2] == 1:
        image = image[:, :, 0]
    elif image.ndim == 3 and image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    elif image.ndim != 3 or image.shape[2] != 3:
        return None, None

    return image, image.shape[:2]


def _to_gray(image):
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _resize_for_analysis(gray):
    h, w = gray.shape[:2]
    scale = min(1.0, MAX_ANALYSIS_DIM / float(max(h, w)))
    if scale < 1.0:
        size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
        gray = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
    return gray, scale


def _as_quad(corners):
    """A validated (4, 2) float array in TL, TR, BR, BL order, or None."""
    try:
        pts = np.asarray(corners, dtype=np.float64)
    except (TypeError, ValueError):
        return None
    if pts.shape != (4, 2) or not np.all(np.isfinite(pts)):
        return None
    return pts


# ── Metrics ──────────────────────────────────────────────────────────────────

def _region_mask(gray, corners, scale):
    """Mask of the detected document inside the analysis image, or None."""
    quad = _as_quad(corners)
    if quad is None:
        return None
    points = np.round(quad * scale).astype(np.int32)
    mask = np.zeros(gray.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [points], 255)
    if np.count_nonzero(mask) < mask.size * 0.05:
        return None
    return mask


def _masked(gray, mask):
    return gray[mask > 0] if mask is not None else gray.reshape(-1)


def _blur_metrics(gray, mask=None):
    laplacian = cv2.Laplacian(gray, cv2.CV_64F, ksize=3)
    variance = float(_masked(laplacian, mask).var())
    if variance >= BLUR_OK_VAR:
        score = 1.0
    elif variance <= BLUR_BAD_VAR:
        score = 0.3 * (variance / BLUR_BAD_VAR)
    else:
        span = BLUR_OK_VAR - BLUR_BAD_VAR
        score = 0.3 + 0.7 * ((variance - BLUR_BAD_VAR) / span)
    return {"score": round(_clamp(score), 3),
            "laplacian_var": round(variance, 2),
            "ok": score >= BLUR_WARN_SCORE}


def _brightness_metrics(gray, mask=None):
    mean = float(_masked(gray, mask).mean())
    if mean < DARK_MEAN:
        score = _clamp(mean / DARK_MEAN)
        status = "karanlık"
    elif mean > BRIGHT_MEAN:
        score = _clamp((255.0 - mean) / (255.0 - BRIGHT_MEAN))
        status = "parlak"
    else:
        score = 1.0
        status = "normal"
    return {"score": round(score, 3), "mean": round(mean, 2),
            "status": status, "ok": status == "normal"}


def _glare_metrics(image, mask=None):
    if image.ndim == 2:
        saturated = image >= GLARE_SATURATION
    else:
        # Pure/saturated highlights: all three channels are nearly clipped.
        min_channel = np.min(image, axis=2)
        saturated = min_channel >= GLARE_SATURATION

    values = _masked(saturated, mask)
    ratio = float(np.count_nonzero(values)) / float(values.size)
    if ratio > GLARE_PAPER_RATIO:
        # Most of the document is plain white paper; that is not a highlight.
        effective = 0.0
    else:
        effective = ratio
    score = _clamp(1.0 - effective / (GLARE_SEVERE_RATIO * 1.5))
    return {"score": round(score, 3), "ratio": round(ratio, 4),
            "ok": effective <= GLARE_WARN_RATIO}


def _shadow_metrics(gray, mask=None):
    h, w = gray.shape[:2]
    scale = min(1.0, MAX_ILLUMINATION_DIM / float(max(h, w)))
    if scale < 1.0:
        size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
        small = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
        small_mask = (cv2.resize(mask, size, interpolation=cv2.INTER_NEAREST)
                      if mask is not None else None)
    else:
        small = gray
        small_mask = mask

    # A wide blur removes text/edges and leaves only the lighting pattern.
    sigma = max(3.0, min(small.shape[:2]) / 12.0)
    background = cv2.GaussianBlur(small, (0, 0), sigmaX=sigma, sigmaY=sigma)

    bh, bw = background.shape[:2]
    block_h = max(1, bh // 3)
    block_w = max(1, bw // 3)
    means = []
    for row in range(3):
        y0 = row * block_h
        y1 = bh if row == 2 else y0 + block_h
        for col in range(3):
            x0 = col * block_w
            x1 = bw if col == 2 else x0 + block_w
            tile = background[y0:y1, x0:x1]
            if small_mask is not None:
                tile_mask = small_mask[y0:y1, x0:x1]
                values = tile[tile_mask > 0]
            else:
                values = tile.reshape(-1)
            if values.size:
                means.append(float(values.mean()))

    spread = max(means) - min(means) if means else 0.0
    score = _clamp(1.0 - max(0.0, spread - 15.0) / 90.0)
    return {"score": round(score, 3), "unevenness": round(spread, 2),
            "ok": spread <= SHADOW_WARN_SPREAD}


def _polygon_area(points):
    x = points[:, 0]
    y = points[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _edge_quality(gray, sampled_corners):
    """Mean Sobel gradient along the four sides of the detected quad (0..1)."""
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(gx, gy)
    h, w = magnitude.shape[:2]
    edge_scores = []

    for index in range(4):
        start = sampled_corners[index]
        end = sampled_corners[(index + 1) % 4]
        samples = 24
        values = []
        for step in range(samples):
            t = (step + 0.5) / samples
            x = int(round(start[0] + (end[0] - start[0]) * t))
            y = int(round(start[1] + (end[1] - start[1]) * t))
            if not (0 <= x < w and 0 <= y < h):
                continue
            window = magnitude[max(0, y - 2):min(h, y + 3),
                               max(0, x - 2):min(w, x + 3)]
            if window.size:
                values.append(float(window.max()))
        edge_scores.append(min(1.0, (sum(values) / len(values)) / 400.0)
                           if values else 0.0)

    return float(sum(edge_scores) / 4.0)


def _framing_metrics(gray, corners, original_shape):
    pts = _as_quad(corners)
    if pts is None:
        return {"score": None, "area_ratio": None, "touching": None,
                "outside": None, "edge_quality": None, "ok": None}

    h, w = original_shape
    margin = max(2.0, min(w, h) * FRAMING_EDGE_MARGIN)
    touching = 0
    outside = 0
    for x, y in pts:
        if x < -0.5 or y < -0.5 or x > w - 0.5 or y > h - 0.5:
            outside += 1
        elif x <= margin or x >= w - 1 - margin or y <= margin or y >= h - 1 - margin:
            touching += 1

    area_ratio = _polygon_area(pts) / float(max(1, w * h))
    area_score = _clamp(area_ratio / 0.55)
    geometry = _clamp(area_score - 0.08 * touching - 0.20 * outside)

    # Corners are in the original frame; the gradient image is downscaled.
    scale_x = gray.shape[1] / float(w)
    scale_y = gray.shape[0] / float(h)
    sampled = pts * np.array([scale_x, scale_y], dtype=np.float64)
    edge_quality = _edge_quality(gray, sampled)

    score = 0.8 * geometry + 0.2 * edge_quality
    ok = (outside == 0 and touching == 0
          and area_ratio >= FRAMING_MIN_AREA
          and edge_quality >= EDGE_WARN_SCORE)
    return {"score": round(score, 3),
            "area_ratio": round(area_ratio, 4),
            "touching": touching,
            "outside": outside,
            "edge_quality": round(edge_quality, 3),
            "ok": ok}


# ── Public API ───────────────────────────────────────────────────────────────

def assess_quality(image_bgr_or_path, corners=None):
    """Assess one scanner frame and return a quality report.

    Keys: ``label`` (iyi / orta / tekrar çekilmesi önerilir), ``score``
    (0-100), ``issues`` (machine ids), ``warnings`` (Turkish sentences) and
    one dict per metric: ``blur``, ``brightness``, ``glare``, ``shadow``,
    ``framing``. Metric dicts always contain ``score`` (0..1) and ``ok``.
    """
    metrics = _empty_metrics()
    if cv2 is None or np is None:  # pragma: no cover - depends on environment
        return _result(QUALITY_MEDIUM, None, ["dependency"],
                       [_WARNINGS["dependency"]], metrics)

    image, original_shape = _load_image(image_bgr_or_path)
    if image is None:
        return _result(QUALITY_RETRY, 0, ["unreadable"],
                       [_WARNINGS["unreadable"]], metrics)

    if image.ndim == 3:
        gray = _to_gray(image)
        glare_source = image
    else:
        gray = image
        glare_source = image
    gray, analysis_scale = _resize_for_analysis(gray)
    # Glare should use the same analysed resolution as the other metrics.
    if gray.shape != glare_source.shape[:2]:
        if glare_source.ndim == 2:
            glare_source = gray
        else:
            glare_source = cv2.resize(glare_source, (gray.shape[1], gray.shape[0]),
                                      interpolation=cv2.INTER_AREA)

    # With detected corners the metrics describe the document, not the desk
    # around it; a dark background would otherwise look like a shadow.
    mask = _region_mask(gray, corners, analysis_scale)

    metrics["blur"] = _blur_metrics(gray, mask)
    metrics["brightness"] = _brightness_metrics(gray, mask)
    metrics["glare"] = _glare_metrics(glare_source, mask)
    metrics["shadow"] = _shadow_metrics(gray, mask)
    metrics["framing"] = _framing_metrics(gray, corners, original_shape)

    issues = []
    warnings = []

    def add(issue, warning_key=None):
        issues.append(issue)
        warnings.append(_WARNINGS[warning_key or issue])

    if not metrics["blur"]["ok"]:
        add("blur")
    brightness = metrics["brightness"]
    if brightness["status"] == "karanlık":
        add("dark")
    elif brightness["status"] == "parlak":
        add("bright")
    if not metrics["glare"]["ok"]:
        add("glare")
    if not metrics["shadow"]["ok"]:
        add("shadow")

    framing = metrics["framing"]
    framing_failed = False
    if framing["ok"] is not None:
        if (framing["outside"] or framing["touching"]) and not framing_failed:
            add("framing")
            framing_failed = True
        if framing["area_ratio"] < FRAMING_MIN_AREA and not framing_failed:
            add("too_small")
            framing_failed = True
        if framing["edge_quality"] < EDGE_WARN_SCORE and not framing_failed:
            add("edge")

    weighted = 0.0
    total_weight = 0.0
    for name, weight in FLAT_WEIGHTS.items():
        score = metrics[name]["score"]
        if score is not None:
            weighted += score * weight
            total_weight += weight
    overall = weighted / total_weight if total_weight else 0.0

    severe = (
        metrics["blur"]["score"] < 0.30
        or (brightness["status"] == "karanlık" and brightness["mean"] < DARK_MEAN * 0.75)
        or (brightness["status"] == "parlak" and brightness["mean"] > BRIGHT_MEAN + 4)
        or (metrics["glare"]["ratio"] <= GLARE_PAPER_RATIO
            and metrics["glare"]["ratio"] > GLARE_SEVERE_RATIO)
        or metrics["shadow"]["unevenness"] > SHADOW_RETRY_SPREAD
        or (framing["ok"] is not None
            and (framing["outside"] >= 2
                 or framing["area_ratio"] < FRAMING_TOO_SMALL_AREA))
    )

    if severe or overall < 0.55:
        label = QUALITY_RETRY
    elif issues or overall < 0.78:
        label = QUALITY_MEDIUM
    else:
        label = QUALITY_GOOD

    return _result(label, int(round(overall * 100)), issues, warnings, metrics)
