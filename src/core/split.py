from src.core.lang_manager import _
from src.core.output_paths import write_pdf


def split_pdf(input_pdf, output_pdf, start_page, end_page, ctx=None):
    """Extract a range of pages from a PDF (1-indexed), with the bookmarks
    and form fields on those pages and the document info."""
    from src.core.common import open_pdf_reader, pick_pages
    reader = open_pdf_reader(input_pdf)
    total_pages = len(reader.pages)
    if start_page < 1:
        raise ValueError(_("err_start_page_min"))
    if end_page > total_pages:
        raise ValueError(_("err_end_page_max").format(total=total_pages))
    if start_page > end_page:
        raise ValueError(_("err_start_after_end"))
    
    page_count = end_page - start_page + 1
    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, page_count, _("progress_starting"))

    write_pdf(pick_pages(reader, range(start_page - 1, end_page)), output_pdf)
    
    if ctx:
        ctx.report_progress(page_count, page_count, _("progress_finished"))
