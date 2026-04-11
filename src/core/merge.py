def merge_pdfs(pdf_list, output_pdf):
    """Merge multiple PDF files into one."""
    from PyPDF2 import PdfReader, PdfWriter
    writer = PdfWriter()
    for pdf_path in pdf_list:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            writer.add_page(page)
    with open(output_pdf, "wb") as f:
        writer.write(f)
