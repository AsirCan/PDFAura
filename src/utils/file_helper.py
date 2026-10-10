import os

def format_size_mb(file_path):
    """Return file size in MB as a float."""
    return os.path.getsize(file_path) / (1024 * 1024)
