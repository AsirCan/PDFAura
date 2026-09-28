from datetime import datetime

from pypdf import PdfWriter

from src.core.common import open_pdf_reader

# Info-dictionary key for each field name we expose.
_FIELD_KEYS = {
    "title": "/Title",
    "author": "/Author",
    "subject": "/Subject",
    "creator": "/Creator",
    "producer": "/Producer",
}


def read_metadata(input_pdf):
    """Retrieve metadata from PDF."""
    reader = open_pdf_reader(input_pdf)
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


def update_metadata(input_pdf, output_pdf, title=None, author=None, subject=None,
                    creator=None, clean=False):
    """Update or completely clear the metadata of a PDF.

    A field left as None is kept as it is in the source document -- only
    fields that were actually given are written. Saving without having read
    the document first used to blank Title/Author/Subject/Creator.

    With clean=True both the Info dictionary and the XMP stream are dropped,
    so no producer string survives.
    """
    reader = open_pdf_reader(input_pdf)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    if clean:
        # metadata = None drops the whole Info dictionary, including the
        # /Producer that add_metadata({}) would still leave behind. XMP has
        # to go too, or the old values live on in the XML stream.
        writer.metadata = None
        try:
            writer.xmp_metadata = None
        except Exception:
            pass
        with open(output_pdf, "wb") as f:
            writer.write(f)
        return

    new_meta = {}
    source_meta = reader.metadata
    if source_meta:
        new_meta.update(source_meta)

    for name, value in (("title", title), ("author", author),
                        ("subject", subject), ("creator", creator)):
        if value is None:
            continue  # not supplied: leave whatever the document had
        key = _FIELD_KEYS[name]
        if value == "":
            new_meta.pop(key, None)  # explicitly emptied
        else:
            new_meta[key] = value

    new_meta["/ModDate"] = datetime.now().strftime("D:%Y%m%d%H%M%S")

    writer.add_metadata(new_meta)

    with open(output_pdf, "wb") as f:
        writer.write(f)
