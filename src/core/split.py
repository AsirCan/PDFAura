def split_pdf(input_pdf, output_pdf, start_page, end_page):
    """Extract a range of pages from a PDF (1-indexed)."""
    from PyPDF2 import PdfReader, PdfWriter
    reader = PdfReader(input_pdf)
    total_pages = len(reader.pages)
    if start_page < 1:
        raise ValueError("Baslangic sayfasi 1'den kucuk olamaz.")
    if end_page > total_pages:
        raise ValueError(f"Bitis sayfasi toplam sayfa sayisindan ({total_pages}) buyuk olamaz.")
    if start_page > end_page:
        raise ValueError("Baslangic sayfasi bitis sayfasindan buyuk olamaz.")
    writer = PdfWriter()
    for i in range(start_page - 1, end_page):
        writer.add_page(reader.pages[i])
    with open(output_pdf, "wb") as f:
        writer.write(f)
