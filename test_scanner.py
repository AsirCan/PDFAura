"""
Document Scanner – Test Suite
─────────────────────────────
Tests the core scanner engine with 1.jpeg, 2.jpeg, 3.jpeg
"""

import os
import sys
import traceback

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

from src.core.document_scanner import (
    detect_document_corners,
    perspective_warp,
    apply_scan_mode,
    rotate_image,
    scan_document,
    scanned_image_to_pdf,
    save_scanned_image,
    MODE_ORIGINAL,
    MODE_CLEAN_DOC,
    MODE_BW,
    MODE_GRAYSCALE,
    MODE_SHARP,
    A4_WIDTH_PX,
    A4_HEIGHT_PX,
)
import cv2

TEST_IMAGES = ["1.jpeg", "2.jpeg", "3.jpeg"]
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_scanner_output")
MODES = [
    ("original", MODE_ORIGINAL),
    ("clean_doc", MODE_CLEAN_DOC),
    ("bw", MODE_BW),
    ("grayscale", MODE_GRAYSCALE),
    ("sharp", MODE_SHARP),
]

passed = 0
failed = 0
total = 0


def test(name, func):
    global passed, failed, total
    total += 1
    try:
        func()
        print(f"  ✅ {name}")
        passed += 1
    except Exception as e:
        print(f"  ❌ {name} → {e}")
        traceback.print_exc()
        failed += 1


def main():
    global passed, failed, total

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"\n{'='*60}")
    print(f"  DOCUMENT SCANNER TEST SUITE")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"{'='*60}\n")

    for img_name in TEST_IMAGES:
        img_path = os.path.abspath(img_name)
        base = os.path.splitext(img_name)[0]
        print(f"── {img_name} ──")

        # 1) Image loading
        def test_load():
            img = cv2.imread(img_path)
            assert img is not None, f"cv2.imread returned None for {img_path}"
            h, w = img.shape[:2]
            assert h > 0 and w > 0, f"Invalid dimensions: {w}x{h}"
            print(f"      Boyut: {w}x{h}")
        test(f"[{img_name}] Fotoğraf okundu", test_load)

        # 2) Corner detection
        corners = None
        def test_corners():
            nonlocal corners
            corners = detect_document_corners(img_path)
            assert len(corners) == 4, f"Expected 4 corners, got {len(corners)}"
            for i, (x, y) in enumerate(corners):
                assert isinstance(x, (int, float)), f"Corner {i} x is not numeric"
                assert isinstance(y, (int, float)), f"Corner {i} y is not numeric"
            print(f"      Köşeler: {corners}")
        test(f"[{img_name}] Otomatik köşe algılama", test_corners)

        # 3) Perspective warp
        warped = None
        def test_warp():
            nonlocal warped
            img = cv2.imread(img_path)
            c = corners if corners else [(20,20), (img.shape[1]-20,20), (img.shape[1]-20,img.shape[0]-20), (20,img.shape[0]-20)]
            warped = perspective_warp(img, c)
            assert warped is not None, "Warp returned None"
            assert warped.shape[1] == A4_WIDTH_PX, f"Width mismatch: {warped.shape[1]} vs {A4_WIDTH_PX}"
            assert warped.shape[0] == A4_HEIGHT_PX, f"Height mismatch: {warped.shape[0]} vs {A4_HEIGHT_PX}"
            print(f"      Warp boyutu: {warped.shape[1]}x{warped.shape[0]}")
        test(f"[{img_name}] Perspektif düzeltme (A4)", test_warp)

        # 4) Rotation tests
        def test_rotation():
            img = cv2.imread(img_path)
            for angle in [90, 180, 270]:
                rotated = rotate_image(img, angle)
                assert rotated is not None, f"Rotation {angle}° returned None"
                oh, ow = img.shape[:2]
                rh, rw = rotated.shape[:2]
                if angle in (90, 270):
                    assert rw == oh and rh == ow, f"Dimensions wrong for {angle}°"
                else:
                    assert rw == ow and rh == oh, f"Dimensions wrong for {angle}°"
            print(f"      90°, 180°, 270° döndürme OK")
        test(f"[{img_name}] Döndürme (3 açı)", test_rotation)

        # 5) All 5 scan modes
        for mode_name, mode_const in MODES:
            def test_mode(mn=mode_name, mc=mode_const, w=warped):
                if w is None:
                    img = cv2.imread(img_path)
                    h_, w_ = img.shape[:2]
                    w = perspective_warp(img, [(20,20),(w_-20,20),(w_-20,h_-20),(20,h_-20)])
                result = apply_scan_mode(w, mc)
                assert result is not None, f"Mode {mn} returned None"
                assert result.shape == w.shape, f"Shape mismatch after mode {mn}"
                # Save sample
                out_path = os.path.join(OUTPUT_DIR, f"{base}_{mn}.png")
                save_scanned_image(result, out_path)
                fsize = os.path.getsize(out_path) / 1024
                print(f"      Kaydedildi: {os.path.basename(out_path)} ({fsize:.0f} KB)")
            test(f"[{img_name}] Gama modu: {mode_name}", test_mode)

        # 6) Full pipeline → PDF
        def test_full_pipeline():
            c = corners if corners else [(20,20),(100,20),(100,100),(20,100)]
            pdf_path = os.path.join(OUTPUT_DIR, f"{base}_scanned.pdf")
            result = scan_document(img_path, c, MODE_CLEAN_DOC)
            assert result is not None, "scan_document returned None"
            scanned_image_to_pdf(result, pdf_path)
            assert os.path.isfile(pdf_path), "PDF not created"
            fsize = os.path.getsize(pdf_path) / 1024
            print(f"      PDF: {os.path.basename(pdf_path)} ({fsize:.0f} KB)")
        test(f"[{img_name}] Tam pipeline → PDF", test_full_pipeline)

        # 7) Full pipeline with rotation → PDF
        def test_rotated_pipeline():
            c = corners if corners else [(20,20),(100,20),(100,100),(20,100)]
            pdf_path = os.path.join(OUTPUT_DIR, f"{base}_rotated_scanned.pdf")
            result = scan_document(img_path, c, MODE_SHARP, rotation=90)
            assert result is not None, "Rotated scan returned None"
            scanned_image_to_pdf(result, pdf_path)
            assert os.path.isfile(pdf_path), "Rotated PDF not created"
            fsize = os.path.getsize(pdf_path) / 1024
            print(f"      PDF: {os.path.basename(pdf_path)} ({fsize:.0f} KB)")
        test(f"[{img_name}] Döndürülmüş pipeline → PDF", test_rotated_pipeline)

        print()

    # Final summary
    print(f"{'='*60}")
    print(f"  SONUÇ: {passed}/{total} başarılı, {failed} hatalı")
    if failed == 0:
        print(f"  🎉 TÜM TESTLER GEÇTİ!")
    else:
        print(f"  ⚠ {failed} test başarısız!")
    print(f"  Çıktılar: {OUTPUT_DIR}")
    print(f"{'='*60}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
