"""Test inputs for the Faz 0 measurements, generated once into %TEMP%.

A 12 MP photo-like JPEG (what a phone camera hands the scanner) and a
300-page PDF with text, vector shapes and an image on every page.
Nothing is committed; both are rebuilt if missing.
"""
import os
import tempfile

import cv2
import fitz
import numpy as np

FOLDER = os.path.join(tempfile.gettempdir(), "pdfaura-faz0")


def photo_path(width=4000, height=3000):
    path = os.path.join(FOLDER, f"photo_{width}x{height}.jpg")
    if os.path.exists(path):
        return path
    os.makedirs(FOLDER, exist_ok=True)
    rng = np.random.default_rng(7)
    # A desk-coloured gradient with a slightly rotated white sheet on it and
    # some sensor noise: compresses like a real photo (~3-5 MB), not like
    # flat colour or pure noise.
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)
    base = np.dstack([90 + 40 * x / width, 70 + 30 * y / height, 50 + 20 * (x + y) / (width + height)])
    image = base.astype(np.uint8)
    sheet = np.array([[800, 400], [3300, 550], [3150, 2700], [650, 2550]], np.int32)
    cv2.fillPoly(image, [sheet], (235, 238, 240))
    for row in range(30):
        y0 = 650 + row * 62
        cv2.line(image, (950 + row % 3 * 20, y0), (2900 - row % 5 * 60, y0 + 40), (60, 60, 60), 6)
    noise = rng.normal(0, 6, image.shape)
    image = np.clip(image + noise, 0, 255).astype(np.uint8)
    cv2.imwrite(path, image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return path


def pdf_path(pages=300):
    path = os.path.join(FOLDER, f"doc_{pages}p.pdf")
    if os.path.exists(path):
        return path
    os.makedirs(FOLDER, exist_ok=True)
    stamp = os.path.join(FOLDER, "stamp.png")
    small = cv2.resize(cv2.imread(photo_path()), (400, 300))
    cv2.imwrite(stamp, small)
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 80), f"Örnek Teknoloji A.Ş. — Sayfa {i + 1}", fontsize=20)
        for line in range(28):
            page.insert_text((60, 130 + line * 22), "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 1,
                             fontsize=11)
        page.draw_rect(fitz.Rect(60, 760, 535, 800), color=(0.2, 0.3, 0.8), fill=(0.9, 0.92, 1))
        page.draw_circle(fitz.Point(480, 90), 30, color=(0.8, 0.2, 0.2))
        page.insert_image(fitz.Rect(360, 560, 535, 690), filename=stamp)
    doc.save(path, garbage=3, deflate=True)
    doc.close()
    return path


if __name__ == "__main__":
    print(photo_path(), os.path.getsize(photo_path()) // 1024, "KB")
    print(pdf_path(), os.path.getsize(pdf_path()) // 1024, "KB")
