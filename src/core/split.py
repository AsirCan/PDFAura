from src.core.lang_manager import _


def split_pdf(input_pdf, output_pdf, start_page, end_page, ctx=None):
    """Extract a range of pages from a PDF (1-indexed)."""
    from pypdf import PdfWriter
    from src.core.common import open_pdf_reader
    reader = open_pdf_reader(input_pdf)
    total_pages = len(reader.pages)
    if start_page < 1:
        raise ValueError(_("err_start_page_min"))
    if end_page > total_pages:
        raise ValueError(_("err_end_page_max").format(total=total_pages))
    if start_page > end_page:
        raise ValueError(_("err_start_after_end"))
    
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
