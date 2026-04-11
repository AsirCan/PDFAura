from tkinter import messagebox
from src.core.lang_manager import _

def set_busy(button, progress_bar, is_busy):
    if is_busy:
        button.config(state="disabled")
        if progress_bar:
            progress_bar.start(12)
    else:
        button.config(state="normal")
        if progress_bar:
            progress_bar.stop()

def operation_done(app_root, button, progress_bar, status_var, status_text, success_msg, error_msg):
    set_busy(button, progress_bar, False)
    status_var.set(status_text)
    if success_msg:
        messagebox.showinfo(_("str_done"), success_msg)
    elif error_msg:
        messagebox.showerror(_("str_error"), error_msg)

def quick_error(msg, button, progress_bar, status_var):
    set_busy(button, progress_bar, False)
    status_var.set(_("str_error") + ".")
    messagebox.showerror(_("str_error"), msg)
