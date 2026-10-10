import io
import os
import sys
from datetime import datetime

if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

# numpy's OpenBLAS reserves about 31 MB for every CPU thread as it loads:
# 620 MB of commit on a 20-thread machine, for an app whose only BLAS work
# is a few vector norms. One thread costs nothing measurable. It has to be
# set before anything imports numpy; a value the user set still wins.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")


def main():
    args = sys.argv[1:]
    if "--tk" in args:
        # The old Tk window, kept for one release in case WebView2 fails
        # somewhere (#25). --web is the default and still accepted.
        run_tk()
        return
    sys.exit(run_web(_debug_port(args)))


def _debug_port(args):
    """--debug-port N opens the DevTools protocol on 127.0.0.1:N (tests only)."""
    if "--debug-port" in args:
        try:
            return int(args[args.index("--debug-port") + 1])
        except (IndexError, ValueError):
            pass
    return None


def run_web(debug_port=None):
    """The window: Edge WebView2 drawing web/ (#25). Tk is never loaded."""
    try:
        from src.app.window import run
        return run(debug_port=debug_port)
    except Exception:
        _report_crash()
        raise


def run_tk():
    try:
        # Loaded here, not at the top, so --web starts without Tk.
        from tkinterdnd2 import TkinterDnD
        from src.gui.main_window import MainWindow

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

    message = details.strip().splitlines()[-1] if details.strip() else ""
    if path:
        message = f"{message}\n\n{path}"
    # A native message box: there may be no window left to show it in.
    from src.app.native import show_error
    show_error("PDF Aura", message)

if __name__ == "__main__":
    main()
