import os

def format_size_mb(file_path):
    """Return file size in MB as a float."""
    return os.path.getsize(file_path) / (1024 * 1024)

def suggest_output_path(input_pdf):
    """Create a default output path based on the selected input PDF."""
    from src.core.output_paths import suggest_output
    return suggest_output(input_pdf, "compressed")

def suggest_split_output_path(input_pdf, start_page, end_page):
    """Create a default output path for split PDF based on page range."""
    from src.core.lang_manager import _
    base_name, ext = os.path.splitext(input_pdf)
    return f"{base_name}{_('suffix_split')}_{start_page}-{end_page}{ext}"
