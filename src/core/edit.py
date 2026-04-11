def delete_pages_from_pdf(input_pdf, output_pdf, pages_to_delete):
    """Delete specific pages from PDF. pages_to_delete is 1-indexed list."""
    from PyPDF2 import PdfReader, PdfWriter
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    delete_set = set(pages_to_delete)
    for i, page in enumerate(reader.pages, 1):
        if i not in delete_set:
            writer.add_page(page)
    if len(writer.pages) == 0:
        raise ValueError("Tum sayfalar silinemez.")
    with open(output_pdf, "wb") as f:
        writer.write(f)

def rotate_pages_in_pdf(input_pdf, output_pdf, pages_to_rotate, angle):
    """Rotate specific pages by angle (90, 180, 270). Pages are 1-indexed."""
    from PyPDF2 import PdfReader, PdfWriter
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    rotate_set = set(pages_to_rotate)
    for i, page in enumerate(reader.pages, 1):
        if i in rotate_set:
            page.rotate(angle)
        writer.add_page(page)
    with open(output_pdf, "wb") as f:
        writer.write(f)

def reorder_pages_in_pdf(input_pdf, output_pdf, new_order):
    """Reorder pages according to new_order (1-indexed list)."""
    from PyPDF2 import PdfReader, PdfWriter
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    for page_num in new_order:
        if page_num < 1 or page_num > len(reader.pages):
            raise ValueError(f"Gecersiz sayfa numarasi: {page_num}")
        writer.add_page(reader.pages[page_num - 1])
    with open(output_pdf, "wb") as f:
        writer.write(f)
