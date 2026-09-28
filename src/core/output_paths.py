"""Helpers for choosing and writing output files without losing data.

Batch runs used to collapse several inputs onto one output name -- three
files "successfully" processed, one file on disk -- and every tab wrote
straight to its destination, so a crash or a cancel left a half-written file
where a good one used to be.
"""
import os
import tempfile
from contextlib import contextmanager

from src.core.lang_manager import _

# Default filename suffixes, by lang_manager key.
SUFFIX_KEYS = {
    "merged": "suffix_merged",
    "edited": "suffix_edited",
    "encrypted": "security_suffix_encrypted",
    "decrypted": "security_suffix_decrypted",
    "watermarked": "security_suffix_watermarked",
    "compressed": "suffix_compressed",
    "images": "suffix_images",
    "scanned": "suffix_scanned",
    "split": "suffix_split",
}


def suffix(name):
    """The localised filename suffix for *name* (see SUFFIX_KEYS)."""
    return _(SUFFIX_KEYS[name])


def suggest_output(input_path, kind, ext=None):
    """Suggest '<input stem><localised suffix><ext>' next to the input."""
    base, original_ext = os.path.splitext(input_path)
    return f"{base}{suffix(kind)}{ext if ext is not None else original_ext}"


def unique_path(path, taken=None, check_disk=True):
    """Return *path*, or '<stem> (2)<ext>' etc. if it is already taken.

    *taken* is a set of names already handed out but not yet written; batch
    runs plan every output before the first one exists, so checking the disk
    alone would give 'foto.png' and 'foto.jpg' the same 'foto.pdf'. The
    returned name is added to the set.

    *check_disk* False makes uniqueness run-scoped: a given input then maps
    to the same output name every time, so re-running a batch replaces its
    own previous results instead of piling up 'rapor (2).pdf', 'rapor (3)'...

    Used for generated names only; a path the user picked in a save dialog
    should ask before overwriting instead.
    """
    def is_free(candidate):
        if check_disk and os.path.exists(candidate):
            return False
        return taken is None or os.path.normcase(candidate) not in taken

    def claim(candidate):
        if taken is not None:
            taken.add(os.path.normcase(candidate))
        return candidate

    if is_free(path):
        return claim(path)
    base, ext = os.path.splitext(path)
    counter = 2
    while True:
        candidate = f"{base} ({counter}){ext}"
        if is_free(candidate):
            return claim(candidate)
        counter += 1


def mirrored_output(input_path, input_root, output_root, prefix="", ext=None, taken=None,
                    check_disk=False):
    """Place *input_path* under *output_root* keeping its folder structure.

    Flattening the tree meant 'rapor.pdf' and 'alt/rapor.pdf' both wrote to
    'compressed_rapor.pdf' and one of them was lost.
    """
    relative = os.path.relpath(input_path, input_root)
    folder, name = os.path.split(relative)
    stem, original_ext = os.path.splitext(name)
    target_ext = ext if ext is not None else original_ext
    target_dir = os.path.join(output_root, folder) if folder not in ("", ".") else output_root
    os.makedirs(target_dir, exist_ok=True)
    return unique_path(os.path.join(target_dir, f"{prefix}{stem}{target_ext}"), taken, check_disk)


def is_inside(path, folder):
    """True if *path* is *folder* or lives under it."""
    try:
        path = os.path.abspath(path)
        folder = os.path.abspath(folder)
        return os.path.commonpath([path, folder]) == folder
    except ValueError:
        return False  # different drives on Windows


@contextmanager
def atomic_output(path):
    """Yield a temp path in the destination folder; move it into place on success.

    An error or a cancel then leaves the previous file untouched instead of a
    truncated one, and writing to the same path as the input is safe.
    """
    path = os.path.abspath(path)
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    handle, temp_path = tempfile.mkstemp(suffix=os.path.splitext(path)[1],
                                         prefix=".pdfaura-", dir=folder)
    os.close(handle)
    try:
        yield temp_path
        os.replace(temp_path, path)
    except BaseException:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise
