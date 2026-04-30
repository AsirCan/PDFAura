def split_pdf(input_pdf, output_pdf, start_page, end_page, ctx=None):
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
    page_count = end_page - start_page + 1
    
    for idx, i in enumerate(range(start_page - 1, end_page)):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(idx + 1, page_count, f"Sayfa {i + 1} işleniyor...")
        writer.add_page(reader.pages[i])
    
    with open(output_pdf, "wb") as f:
        writer.write(f)
    
    if ctx:
        ctx.report_progress(page_count, page_count, "Bölme tamamlandı.")
