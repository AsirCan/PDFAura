def get_pdf_page_count(pdf_path):
    """Return the total number of pages in a PDF."""
    from PyPDF2 import PdfReader
    reader = PdfReader(pdf_path)
    return len(reader.pages)

def parse_page_numbers(text, total_pages):
    """Parse page specification like '1, 3-5, 8' into a sorted list of page numbers."""
    pages = set()
    for part in text.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            start, end = part.split('-', 1)
            start, end = int(start.strip()), int(end.strip())
            if start < 1 or end > total_pages or start > end:
                raise ValueError(f"Gecersiz aralik: {part}")
            pages.update(range(start, end + 1))
        else:
            p = int(part)
            if p < 1 or p > total_pages:
                raise ValueError(f"Gecersiz sayfa: {p}")
            pages.add(p)
    if not pages:
        raise ValueError("En az bir sayfa numarasi girilmeli.")
    return sorted(pages)
