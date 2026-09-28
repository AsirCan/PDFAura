from src.core.lang_manager import _


class PdfPasswordError(ValueError):
    """The PDF needs a user password that we were not given."""


def open_pdf_reader(pdf_path, password=None):
    """Open a PDF with pypdf, unlocking it when possible.

    Owner-password-only files (empty user password) open transparently. Files
    that need a user password raise PdfPasswordError unless *password* is right.
    """
    from pypdf import PdfReader, PasswordType

    reader = PdfReader(pdf_path)
    if reader.is_encrypted:
        if reader.decrypt(password or "") == PasswordType.NOT_DECRYPTED:
            if password:
                raise PdfPasswordError(_("err_wrong_password"))
            raise PdfPasswordError(_("err_pdf_password_protected"))
    return reader


def get_pdf_page_count(pdf_path):
    """Return the total number of pages in a PDF."""
    return len(open_pdf_reader(pdf_path).pages)

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
