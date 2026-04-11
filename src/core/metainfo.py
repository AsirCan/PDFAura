from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime

def read_metadata(input_pdf):
    """Retrieve metadata from PDF."""
    reader = PdfReader(input_pdf)
    meta = reader.metadata
    if meta is None:
        return {}
    
    return {
        "title": meta.title or "",
        "author": meta.author or "",
        "subject": meta.subject or "",
        "creator": meta.creator or "",
        "producer": meta.producer or "",
    }

def update_metadata(input_pdf, output_pdf, title=None, author=None, subject=None, creator=None, clean=False):
    """Update or completely clear the metadata of a PDF."""
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    new_meta = {}
    if not clean:
        meta = reader.metadata
        if meta:
            new_meta.update(meta)
            
    if title is not None: new_meta['/Title'] = title
    if author is not None: new_meta['/Author'] = author
    if subject is not None: new_meta['/Subject'] = subject
    if creator is not None: new_meta['/Creator'] = creator
    
    # update date
    now = datetime.now()
    date_str = now.strftime("D:%Y%m%d%H%M%S")
    new_meta['/ModDate'] = date_str
    
    writer.add_metadata(new_meta)

    with open(output_pdf, "wb") as f:
        writer.write(f)
