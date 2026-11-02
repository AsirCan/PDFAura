"""Faz 8: scanner quality control on synthetic frames.

Each test builds the photo it needs (sharp text, blur, darkness, glare,
shadow, bad framing) so the thresholds are pinned without fixture images.
"""
import os
import time

import cv2
import numpy as np
import pytest

from src.core import document_scanner, scan_quality
from src.core.scan_quality import QUALITY_GOOD, QUALITY_MEDIUM, QUALITY_RETRY, assess_quality

WIDTH, HEIGHT = 1600, 1200
LABELS = {QUALITY_GOOD, QUALITY_MEDIUM, QUALITY_RETRY}


def document_page(width=WIDTH, height=HEIGHT, background=245):
    """A sharp, evenly lit page with black text-like lines."""
    image = np.full((height, width, 3), background, np.uint8)
    for index, y in enumerate(range(120, height - 90, 60)):
        cv2.putText(image, f"PDF Aura kalite kontrol satiri {index}", (120, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2, cv2.LINE_AA)
        cv2.line(image, (120, y + 20), (width - 140, y + 20),
                 (40, 40, 40), 1, cv2.LINE_AA)
    return image


def full_frame_corners(width=WIDTH, height=HEIGHT):
    return [(0, 0), (width - 1, 0), (width - 1, height - 1), (0, height - 1)]


def warning_text(result):
    return " ".join(result["warnings"]).lower()


# ── Blur ──────────────────────────────────────────────────────────────────

def test_a_sharp_page_is_good():
    result = assess_quality(document_page())

    assert result["label"] == QUALITY_GOOD
    assert result["warnings"] == []
    assert result["issues"] == []
    assert result["blur"]["ok"] is True
    assert result["blur"]["laplacian_var"] > 1000
    assert result["score"] >= 90


def test_a_blurred_page_is_flagged_for_a_retake():
    blurred = cv2.GaussianBlur(document_page(), (0, 0), 6)
    result = assess_quality(blurred)

    assert result["label"] == QUALITY_RETRY
    assert "blur" in result["issues"]
    assert result["blur"]["ok"] is False
    assert "bulanık" in warning_text(result)


# ── Brightness ────────────────────────────────────────────────────────────

def test_a_dark_page_is_flagged():
    dark = (document_page() * 0.18).astype(np.uint8)
    result = assess_quality(dark)

    assert result["brightness"]["status"] == "karanlık"
    assert "dark" in result["issues"]
    assert result["label"] == QUALITY_RETRY
    assert "karanlık" in warning_text(result)


def test_a_blown_out_page_is_flagged_as_too_bright():
    bright = np.full((HEIGHT, WIDTH, 3), 255, np.uint8)
    result = assess_quality(bright)

    assert result["brightness"]["status"] == "parlak"
    assert "bright" in result["issues"]
    assert "parlak" in warning_text(result)


# ── Glare and shadow ──────────────────────────────────────────────────────

def test_a_hot_highlight_is_reported_as_glare():
    image = document_page(background=200)
    cv2.circle(image, (WIDTH // 2, HEIGHT // 2), 140, (255, 255, 255), -1)
    result = assess_quality(image)

    assert result["glare"]["ratio"] > 0.02
    assert "glare" in result["issues"]
    assert "parlama" in warning_text(result)
    assert result["label"] in (QUALITY_MEDIUM, QUALITY_RETRY)


def test_a_white_page_is_paper_not_glare():
    """A plain white background is saturated too, but it is not a highlight."""
    result = assess_quality(document_page(background=255))

    assert result["glare"]["ratio"] > 0.35
    assert result["glare"]["ok"] is True
    assert "glare" not in result["issues"]
    assert result["brightness"]["ok"] is True
    assert "bright" not in result["issues"]


def test_uneven_lighting_is_reported_as_shadow():
    height, width = HEIGHT, WIDTH
    gradient = np.linspace(50, 230, width, dtype=np.float32)
    shaded = np.repeat(gradient[None, :, None], height, axis=0)
    shaded = np.repeat(shaded, 3, axis=2).astype(np.uint8)
    for index, y in enumerate(range(120, height - 90, 60)):
        cv2.putText(shaded, f"PDF Aura golge satiri {index}", (120, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (15, 15, 15), 2, cv2.LINE_AA)

    result = assess_quality(shaded)

    assert result["shadow"]["ok"] is False
    assert "shadow" in result["issues"]
    assert "gölge" in warning_text(result)
    assert result["label"] == QUALITY_RETRY


# ── Framing ───────────────────────────────────────────────────────────────

def test_corners_touching_the_border_are_incomplete_framing():
    result = assess_quality(document_page(), full_frame_corners())

    assert result["framing"]["touching"] == 4
    assert result["framing"]["outside"] == 0
    assert "framing" in result["issues"]
    assert "kadraja" in warning_text(result)


def test_corners_outside_the_photo_are_incomplete_framing():
    width, height = WIDTH, HEIGHT
    corners = [(-40, -40), (width + 30, 0), (width - 1, height - 1), (0, height - 1)]
    result = assess_quality(document_page(), corners)

    assert result["framing"]["outside"] >= 2
    assert "framing" in result["issues"]
    assert result["label"] == QUALITY_RETRY


def test_a_too_small_document_is_flagged():
    centre_x, centre_y = WIDTH // 2, HEIGHT // 2
    corners = [(centre_x - 150, centre_y - 100), (centre_x + 150, centre_y - 100),
               (centre_x + 150, centre_y + 100), (centre_x - 150, centre_y + 100)]
    result = assess_quality(document_page(), corners)

    assert result["framing"]["area_ratio"] < scan_quality.FRAMING_MIN_AREA
    assert "too_small" in result["issues"]
    assert "küçük" in warning_text(result)


def test_dark_desk_around_the_page_is_not_a_shadow():
    """Metrics follow the detected document, not the background around it."""
    image = np.full((1200, 900, 3), (55, 70, 90), np.uint8)
    sheet = np.array([[90, 80], [820, 110], [840, 1110], [70, 1080]], np.int32)
    cv2.fillPoly(image, [sheet], (235, 240, 242))
    for index, y in enumerate(range(180, 1000, 60)):
        cv2.putText(image, f"Belge satiri {index}", (150, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2, cv2.LINE_AA)

    result = assess_quality(image, [(90, 80), (820, 110), (840, 1110), (70, 1080)])

    assert result["shadow"]["ok"] is True
    assert "shadow" not in result["issues"]
    assert result["label"] == QUALITY_GOOD


def test_without_corners_framing_is_skipped():
    result = assess_quality(document_page())

    assert result["framing"]["score"] is None
    assert result["framing"]["ok"] is None
    assert not {"framing", "too_small"} & set(result["issues"])


@pytest.mark.parametrize("corners", ["bad", [(0, 0)], [(0, 0), (1, 0), (1, 1)],
                                     [(0, 0), (1, 0), (1, 1), (0, float("nan"))]])
def test_invalid_corners_do_not_break_the_report(corners):
    result = assess_quality(document_page(), corners)

    assert result["framing"]["score"] is None
    assert result["label"] in LABELS


# ── Input flavours and degradation ────────────────────────────────────────

def test_a_gray_image_is_accepted():
    gray = cv2.cvtColor(document_page(), cv2.COLOR_BGR2GRAY)
    result = assess_quality(gray)

    assert result["label"] == QUALITY_GOOD
    assert result["brightness"]["ok"] is True


def test_a_unicode_path_is_accepted(tmp_path):
    path = os.path.join(str(tmp_path), "çekim ışığı.png")
    document_scanner.imwrite_unicode(path, document_page())

    result = assess_quality(path)

    assert result["label"] == QUALITY_GOOD
    assert result["blur"]["laplacian_var"] > 1000


def test_an_unreadable_path_degrades_instead_of_raising(tmp_path):
    result = assess_quality(str(tmp_path / "yok.png"))

    assert result["label"] == QUALITY_RETRY
    assert result["issues"] == ["unreadable"]
    assert result["warnings"]


def test_missing_opencv_degrades_gracefully(monkeypatch):
    monkeypatch.setattr(scan_quality, "cv2", None)
    monkeypatch.setattr(scan_quality, "np", None)

    result = assess_quality("herhangi.png")

    assert result["label"] == QUALITY_MEDIUM
    assert result["issues"] == ["dependency"]
    assert result["warnings"]
    assert result["score"] is None


def test_the_report_has_every_metric():
    result = assess_quality(document_page())

    assert set(result) >= {"label", "score", "issues", "warnings",
                           "blur", "brightness", "glare", "shadow", "framing"}
    for name in ("blur", "brightness", "glare", "shadow", "framing"):
        assert "score" in result[name]
        assert "ok" in result[name]


# ── Speed and the detection result ────────────────────────────────────────

def test_two_megapixels_are_analysed_quickly():
    big = cv2.resize(document_page(2000, 1500), (2000, 1500))
    assess_quality(big)  # warm up OpenCV's code paths

    started = time.perf_counter()
    assess_quality(big)
    elapsed = time.perf_counter() - started
    assert elapsed < 0.20, f"quality assessment took {elapsed * 1000:.0f} ms"


def test_detection_result_can_carry_the_quality_report(tmp_path):
    image = np.full((900, 700, 3), (55, 70, 90), np.uint8)
    sheet = np.array([[80, 70], [620, 90], [640, 850], [60, 820]], np.int32)
    cv2.fillPoly(image, [sheet], (230, 236, 240))
    for index, y in enumerate(range(150, 780, 60)):
        cv2.putText(image, f"Belge {index}", (120, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (20, 20, 20), 2, cv2.LINE_AA)
    path = str(tmp_path / "tarama.png")
    document_scanner.imwrite_unicode(path, image)

    detected = document_scanner.detect_document_with_quality(path)

    assert set(detected) == {"corners", "quality"}
    assert len(detected["corners"]) == 4
    assert detected["quality"]["label"] in LABELS
    assert detected["quality"]["framing"]["area_ratio"] is not None
