from src.core.lang_manager import _


def delete_pages_from_pdf(input_pdf, output_pdf, pages_to_delete, ctx=None):
    """Delete specific pages from PDF. pages_to_delete is 1-indexed list."""
    from pypdf import PdfWriter
    from src.core.common import open_pdf_reader
    reader = open_pdf_reader(input_pdf)
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
        raise ValueError(_("err_delete_all_pages"))
    with open(output_pdf, "wb") as f:
        writer.write(f)

def rotate_pages_in_pdf(input_pdf, output_pdf, pages_to_rotate, angle, ctx=None):
    """Rotate specific pages by angle (90, 180, 270). Pages are 1-indexed."""
    from pypdf import PdfWriter
    from src.core.common import open_pdf_reader
    reader = open_pdf_reader(input_pdf)
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
    from pypdf import PdfWriter
    from src.core.common import open_pdf_reader
    reader = open_pdf_reader(input_pdf)
    writer = PdfWriter()
    total = len(new_order)
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

    for idx, page_num in enumerate(new_order, 1):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(idx, total, f"Sayfa {idx}/{total} yeniden sıralanıyor...")
        if page_num < 1 or page_num > page_count:
            raise ValueError(_("err_order_out_of_range").format(
                pages=page_num, total=page_count))
        writer.add_page(reader.pages[page_num - 1])
    
    with open(output_pdf, "wb") as f:
        writer.write(f)
