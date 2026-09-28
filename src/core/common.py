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
            start_text, end_text = part.split('-', 1)
            try:
                start, end = int(start_text.strip()), int(end_text.strip())
            except ValueError:
                # Without this the user saw "invalid literal for int()".
                raise ValueError(_("err_invalid_range").format(part=part))
            if start < 1 or end > total_pages or start > end:
                raise ValueError(_("err_invalid_range").format(part=part))
            pages.update(range(start, end + 1))
        else:
            try:
                page = int(part)
            except ValueError:
                raise ValueError(_("err_invalid_page").format(page=part))
            if page < 1 or page > total_pages:
                raise ValueError(_("err_invalid_page").format(page=page))
            pages.add(page)
    if not pages:
        raise ValueError(_("err_need_one_page"))
    return sorted(pages)


def parse_page_order(text, total_pages):
    """Parse a page order like '3, 1, 2' or '5-1' into a list of page numbers.

    Accepts ranges in either direction, stray whitespace and a trailing comma.
    The result must be a full permutation of 1..total_pages: reordering is not
    a way to drop or duplicate pages, and silently doing so lost real content.
    Raises ValueError naming the missing or repeated pages.
    """
    order = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue  # tolerate a trailing or doubled comma
        if "-" in part.lstrip("-"):
            start_text, _sep, end_text = part.partition("-")
            try:
                start, end = int(start_text.strip()), int(end_text.strip())
            except ValueError:
                raise ValueError(_("err_order_invalid_token").format(token=part))
            step = 1 if end >= start else -1
            order.extend(range(start, end + step, step))
        else:
            try:
                order.append(int(part))
            except ValueError:
                raise ValueError(_("err_order_invalid_token").format(token=part))

    if not order:
        raise ValueError(_("err_order_empty"))

    out_of_range = sorted({p for p in order if p < 1 or p > total_pages})
    if out_of_range:
        raise ValueError(_("err_order_out_of_range").format(
            pages=", ".join(str(p) for p in out_of_range), total=total_pages))

    missing = sorted(set(range(1, total_pages + 1)) - set(order))
    duplicates = sorted({p for p in order if order.count(p) > 1})
    if missing or duplicates:
        problems = []
        if missing:
            problems.append(_("err_order_missing").format(
                pages=", ".join(str(p) for p in missing)))
        if duplicates:
            problems.append(_("err_order_duplicate").format(
                pages=", ".join(str(p) for p in duplicates)))
        raise ValueError(_("err_order_not_permutation").format(
            total=total_pages, problems=" ".join(problems)))

    return order
