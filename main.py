import io
import os
import sys
from datetime import datetime

if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

import tkinter as tk
from tkinterdnd2 import TkinterDnD

from src.gui.main_window import MainWindow

def main():
    try:
        # Use TkinterDnD for drag and drop support
        root = TkinterDnD.Tk()
        app = MainWindow(root)
        root.deiconify()
        root.lift()
        root.attributes("-topmost", True)
        root.after_idle(root.attributes, "-topmost", False)
        root.focus_force()
        root.mainloop()
    except Exception:
        # The working directory is Program Files in an installed build, where
        # we cannot write, so the real error used to be lost entirely and the
        # user saw nothing at all.
        _report_crash()
        raise


def _crash_log_path():
    folder = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "PDFAura")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "crash.log")


def _report_crash():
    """Save the traceback somewhere writable and tell the user where."""
    import traceback

    details = traceback.format_exc()
    path = ""
    try:
        path = _crash_log_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
            f.write(details)
    except Exception:
        pass   # nowhere to write; still show the dialog below

    try:
        from tkinter import messagebox
        message = details.strip().splitlines()[-1] if details.strip() else ""
        if path:
            message = f"{message}\n\n{path}"
        messagebox.showerror("PDF Aura", message)
    except Exception:
        print(details)

if __name__ == "__main__":
    main()
