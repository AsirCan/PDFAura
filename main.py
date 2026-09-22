import sys
import io

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
    except Exception as exc:
        import traceback
        with open("crash.log", "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise

if __name__ == "__main__":
    main()
