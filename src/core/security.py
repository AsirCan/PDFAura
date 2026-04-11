import io
from PyPDF2 import PdfReader, PdfWriter

def encrypt_pdf(input_pdf, output_pdf, password):
    """Encrypt a PDF with the given password."""
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    writer.encrypt(password)
    
    with open(output_pdf, "wb") as f:
        writer.write(f)

def decrypt_pdf(input_pdf, output_pdf, password):
    """Decrypt a PDF using the given password."""
    reader = PdfReader(input_pdf)
    
    if not reader.is_encrypted:
        raise ValueError("Bu PDF zaten sifreli degil.")
        
    if not reader.decrypt(password):
        raise ValueError("Gecersiz parola.")
        
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
        
    with open(output_pdf, "wb") as f:
        writer.write(f)

def add_watermark_to_pdf(input_pdf, output_pdf, text, opacity=0.3, angle=45, font_size=60):
    """Add a diagonal text watermark to all pages of a PDF."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import Color, black
    except ImportError:
        raise ImportError("Filigran eklemek icin reportlab kutuphanesi kurulmali. (pip install reportlab)")
        
    # Generate watermark PDF in memory
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    # Move to center of A4
    page_width, page_height = A4
    can.translate(page_width / 2, page_height / 2)
    can.rotate(angle)
    # Set color and opacity
    c = Color(black.red, black.green, black.blue, alpha=opacity)
    can.setFillColor(c)
    can.setFont("Helvetica-Bold", font_size)
    can.drawCentredString(0, 0, text)
    can.save()
    
    packet.seek(0)
    watermark_reader = PdfReader(packet)
    watermark_page = watermark_reader.pages[0]
    
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    
    for page in reader.pages:
        # Merge watermark
        page.merge_page(watermark_page)
        writer.add_page(page)
        
    with open(output_pdf, "wb") as f:
        writer.write(f)
