def delete_pages_from_pdf(input_pdf, output_pdf, pages_to_delete, ctx=None):
    """Delete specific pages from PDF. pages_to_delete is 1-indexed list."""
    from PyPDF2 import PdfReader, PdfWriter
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    delete_set = set(pages_to_delete)
    total = len(reader.pages)
    
    for i, page in enumerate(reader.pages, 1):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(i, total, f"Sayfa {i}/{total} işleniyor...")
        if i not in delete_set:
            writer.add_page(page)
    
    if len(writer.pages) == 0:
        raise ValueError("Tum sayfalar silinemez.")
    with open(output_pdf, "wb") as f:
        writer.write(f)

def rotate_pages_in_pdf(input_pdf, output_pdf, pages_to_rotate, angle, ctx=None):
    """Rotate specific pages by angle (90, 180, 270). Pages are 1-indexed."""
    from PyPDF2 import PdfReader, PdfWriter
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    rotate_set = set(pages_to_rotate)
    total = len(reader.pages)
    
    for i, page in enumerate(reader.pages, 1):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(i, total, f"Sayfa {i}/{total} döndürülüyor...")
        if i in rotate_set:
            page.rotate(angle)
        writer.add_page(page)
    
    with open(output_pdf, "wb") as f:
        writer.write(f)

def reorder_pages_in_pdf(input_pdf, output_pdf, new_order, ctx=None):
    """Reorder pages according to new_order (1-indexed list)."""
    from PyPDF2 import PdfReader, PdfWriter
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    total = len(new_order)
    
    for idx, page_num in enumerate(new_order, 1):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(idx, total, f"Sayfa {idx}/{total} yeniden sıralanıyor...")
        if page_num < 1 or page_num > len(reader.pages):
            raise ValueError(f"Gecersiz sayfa numarasi: {page_num}")
        writer.add_page(reader.pages[page_num - 1])
    
    with open(output_pdf, "wb") as f:
        writer.write(f)
