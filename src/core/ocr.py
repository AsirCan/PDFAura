import os
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

def perform_ocr_to_text(input_pdf, output_txt, lang='tur'):
    """Read a PDF using PyMuPDF, OCR the images/pages, and save to a text file."""
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        raise EnvironmentError(
            "Tesseract-OCR bulunamadi. Lutfen bilgisayariniza Tesseract kurun "
            "ve PATH'e ekleyin veya C:\\Program Files\\Tesseract-OCR icine yukleyin."
        )

    doc = fitz.open(input_pdf)
    full_text = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # Render high-res image
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        
        # Convert to PIL Image
        mode = "RGBA" if pix.alpha else "RGB"
        img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        
        try:
            text = pytesseract.image_to_string(img, lang=lang)
            full_text.append(f"--- Sayfa {page_num + 1} ---\n{text}\n")
        except pytesseract.TesseractError as e:
            raise RuntimeError(f"OCR silsilesinde hata: {str(e)}\n{lang} dil paketi kurulu olmayabilir.")

    doc.close()

    with open(output_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(full_text))

def check_tesseract_availability():
    """Returns True if Tesseract can be called, else False."""
    try:
        version = pytesseract.get_tesseract_version()
        return True
    except Exception:
        # Check standard installation dir just in case
        std_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(std_path):
            pytesseract.pytesseract.tesseract_cmd = std_path
            return True
        return False
