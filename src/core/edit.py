from src.core.lang_manager import _
from src.core.output_paths import write_pdf


def delete_pages_from_pdf(input_pdf, output_pdf, pages_to_delete, ctx=None):
    """Delete specific pages from PDF. pages_to_delete is 1-indexed list.

    Bookmarks and form fields on the pages that stay are kept.
    """
    from src.core.common import open_pdf_reader, pick_pages
    reader = open_pdf_reader(input_pdf)
    delete_set = set(pages_to_delete)
    total = len(reader.pages)
    keep = [i for i in range(total) if i + 1 not in delete_set]

    if not keep:
        raise ValueError(_("err_delete_all_pages"))
    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, total, _("progress_starting"))
    write_pdf(pick_pages(reader, keep), output_pdf)
    if ctx:
        ctx.report_progress(total, total, _("progress_finished"))

def rotate_pages_in_pdf(input_pdf, output_pdf, pages_to_rotate, angle, ctx=None):
    """Rotate specific pages by angle (90, 180, 270). Pages are 1-indexed.

    The whole document is copied and turned in place, so nothing besides the
    pages' rotation changes.
    """
    from pypdf import PdfWriter
    from src.core.common import open_pdf_reader
    reader = open_pdf_reader(input_pdf)
    writer = PdfWriter(clone_from=reader)
    rotate_set = set(pages_to_rotate)
    total = len(writer.pages)
    
    for i, page in enumerate(writer.pages, 1):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(i, total, _("progress_page_of").format(current=i, total=total))
        if i in rotate_set:
            page.rotate(angle)

    write_pdf(writer, output_pdf)

def reorder_pages_in_pdf(input_pdf, output_pdf, new_order, ctx=None):
    """Reorder pages according to new_order (1-indexed list)."""
    from src.core.common import open_pdf_reader, pick_pages
    reader = open_pdf_reader(input_pdf)
    page_count = len(reader.pages)

    # Reordering must not drop or duplicate pages: "2, 1" on a 5-page document
    # used to write a 2-page file and report success.
    missing = sorted(set(range(1, page_count + 1)) - set(new_order))
    duplicates = sorted({p for p in new_order if new_order.count(p) > 1})
    if missing or duplicates:
        problems = []
        if missing:
            problems.append(_("err_order_missing").format(
                pages=", ".join(str(p) for p in missing)))
        if duplicates:
            problems.append(_("err_order_duplicate").format(
                pages=", ".join(str(p) for p in duplicates)))
        raise ValueError(_("err_order_not_permutation").format(
            total=page_count, problems=" ".join(problems)))

    outside = [p for p in new_order if p < 1 or p > page_count]
    if outside:
        raise ValueError(_("err_order_out_of_range").format(
            pages=", ".join(str(p) for p in outside), total=page_count))

    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, page_count, _("progress_starting"))
    write_pdf(pick_pages(reader, [p - 1 for p in new_order]), output_pdf)
    if ctx:
        ctx.report_progress(page_count, page_count, _("progress_finished"))
