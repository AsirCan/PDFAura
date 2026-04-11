import io
from PyPDF2 import PdfReader, PdfWriter
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
except ImportError:
    pass

def stamp_visual_signature(input_pdf, output_pdf, image_path, page_num=1, x_pos=100, y_pos=100, scale=1.0):
    """
    Stamp a visual signature (image) onto a specific document page.
    page_num is 1-indexed. Coordinates are from bottom-left in points (pt).
    """
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    
    total_pages = len(reader.pages)
    if page_num < 1 or page_num > total_pages:
        raise ValueError(f"Gecersiz sayfa numarasi: {page_num}. Belge {total_pages} sayfa.")

    # Create a fresh canvas with reportlab
    packet = io.BytesIO()
    from PIL import Image
    try:
        img = Image.open(image_path)
        img_w, img_h = img.size
    except Exception:
        raise FileNotFoundError("Imza resmi (png/jpg) okunamadi.")
        
    scaled_w = img_w * scale * 0.2  # arbitrary resize factor
    scaled_h = img_h * scale * 0.2
    
    # Needs to match the page size being stamped
    target_page = reader.pages[page_num - 1]
    page_width = float(target_page.mediabox.width)
    page_height = float(target_page.mediabox.height)
    
    can = canvas.Canvas(packet, pagesize=(page_width, page_height))
    # We draw the image
    can.drawImage(image_path, x_pos, y_pos, width=scaled_w, height=scaled_h, mask='auto')
    can.save()
    packet.seek(0)
    
    stamp_reader = PdfReader(packet)
    stamp_page = stamp_reader.pages[0]
    
    for i, page in enumerate(reader.pages):
        if i == (page_num - 1):
            page.merge_page(stamp_page)
        writer.add_page(page)
        
    with open(output_pdf, "wb") as f:
        writer.write(f)
