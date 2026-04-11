import shutil

GHOSTSCRIPT_EXE = "gswin64c"

def find_ghostscript():
    """Return the full path to gswin64c if found in PATH, otherwise None."""
    return shutil.which(GHOSTSCRIPT_EXE)
