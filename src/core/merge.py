from src.core.lang_manager import _
from src.core.output_paths import write_pdf


def merge_pdfs(pdf_list, output_pdf, ctx=None):
    """Merge multiple PDF files into one.

    Each file brings its bookmarks and form fields; the document info is the
    first file's. add_page() used to drop all of them (#32).
    """
    from pypdf import PdfWriter
    from src.core.common import open_pdf_reader
    from src.core.task_manager import memory_optimize
    
    writer = PdfWriter()
    total_files = len(pdf_list)
    page_counter = 0
    info = None
    
    for file_idx, pdf_path in enumerate(pdf_list):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(file_idx, total_files, _("progress_page_of").format(current=file_idx + 1, total=total_files))
        
        reader = open_pdf_reader(pdf_path)
        if file_idx == 0 and reader.metadata:
            info = dict(reader.metadata)
        writer.append(reader, import_outline=True)
        page_counter += len(reader.pages)
        
        # Bellek optimizasyonu: her dosya sonrası reader'ı serbest bırak
        del reader
        if file_idx % 5 == 0:
            memory_optimize()
    
    if info:
        writer.add_metadata(info)
    write_pdf(writer, output_pdf)
    
    if ctx:
        ctx.report_progress(total_files, total_files, _("progress_pages_done").format(count=page_counter))
