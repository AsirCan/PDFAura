def merge_pdfs(pdf_list, output_pdf, ctx=None):
    """Merge multiple PDF files into one."""
    from PyPDF2 import PdfReader, PdfWriter
    from src.core.task_manager import memory_optimize
    
    writer = PdfWriter()
    total_files = len(pdf_list)
    page_counter = 0
    
    for file_idx, pdf_path in enumerate(pdf_list):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(file_idx, total_files, f"Dosya birleştiriliyor: {file_idx + 1}/{total_files}")
        
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            writer.add_page(page)
            page_counter += 1
        
        # Bellek optimizasyonu: her dosya sonrası reader'ı serbest bırak
        del reader
        if file_idx % 5 == 0:
            memory_optimize()
    
    with open(output_pdf, "wb") as f:
        writer.write(f)
    
    if ctx:
        ctx.report_progress(total_files, total_files, f"Birleştirme tamamlandı. Toplam {page_counter} sayfa.")
