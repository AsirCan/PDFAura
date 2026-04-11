import sys
import tkinter as tk
from tkinterdnd2 import TkinterDnD

from src.gui.main_window import MainWindow

def main():
    try:
        # Use TkinterDnD for drag and drop support
        root = TkinterDnD.Tk()
    except Exception as exc:
        print(f"Error: GUI could not be started: {exc}", file=sys.stderr)
        sys.exit(1)
        
    app = MainWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main()
