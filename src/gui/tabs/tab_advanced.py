import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from src.core.errors import friendly_error
from src.core.lang_manager import _
from src.core.metainfo import read_metadata, update_metadata
from src.core.ocr import check_tesseract_availability, perform_ocr_to_text
from src.core.signature import stamp_visual_signature
from src.core.task_manager import TaskContext, CancelledError
from src.gui.widgets import SegmentedControl
from src.gui.helpers import InlineFeedback, ProgressFooter, ToolLayout, bind_preview, follow_width, quick_error
from src.gui.pdf_viewer import PDFViewerWindow


class AdvancedTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        self._task_ctx = None

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.action_var = tk.StringVar(value=_("adv_preview"))
        self.status_var = tk.StringVar(value=_("str_ready"))

        self.title_var = tk.StringVar()
        self.author_var = tk.StringVar()
        self.subject_var = tk.StringVar()
        self.creator_var = tk.StringVar()
        # False until the fields hold this document's metadata; until then an
        # empty field means "leave alone", not "erase".
        self._meta_loaded_for = None
        self.meta_clean_var = tk.BooleanVar(value=False)

        self.sig_image_var = tk.StringVar()
        self.sig_page_var = tk.StringVar(value="1")
        self.sig_x_var = tk.StringVar(value="100")
        self.sig_y_var = tk.StringVar(value="100")
        self.sig_scale_var = tk.StringVar(value="1.0")

        bind_preview(self.app_root, self.input_var)
        self.build_ui()

    def build_ui(self):
        self.layout = ToolLayout(self.parent, _("hint_advanced"))
        left = self.layout.form

        ttk.Label(left, text=_("str_input_pdf"), style="Field.TLabel").pack(anchor="w")
        input_row = ttk.Frame(left, style="Surface.TFrame")
        input_row.pack(fill="x", pady=(8, 0))
        self.input_entry = ttk.Entry(input_row, textvariable=self.input_var, style="Input.TEntry")
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(input_row, text=_("str_select"), command=self.choose_input, style="Secondary.TButton").pack(side="right")

        ttk.Label(left, text=_("adv_operation"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        self.mode_picker = SegmentedControl(
            left, self.action_var,
            [_("adv_preview"), _("adv_ocr"), _("adv_metadata"), _("adv_signature")],
            command=self.switch_mode)
        self.mode_picker.pack(fill="x", pady=(8, 0))

        self.dyn_frame = ttk.Frame(left, style="PanelCard.TFrame", padding=16)
        self.dyn_frame.pack(fill="x", pady=(18, 0))

        self.f_preview = ttk.Frame(self.dyn_frame, style="Panel.TFrame")
        preview_hint = ttk.Label(self.f_preview, text=_("adv_preview_hint"), style="Hint.TLabel", justify="left")
        preview_hint.pack(anchor="w")
        follow_width(preview_hint, self.dyn_frame, 32)

        self.f_ocr = ttk.Frame(self.dyn_frame, style="Panel.TFrame")
        ocr_hint = ttk.Label(self.f_ocr, text=_("adv_ocr_hint"), style="Hint.TLabel", justify="left")
        ocr_hint.pack(anchor="w")
        follow_width(ocr_hint, self.dyn_frame, 32)
        self.tess_warn_label = ttk.Label(self.f_ocr, text="", style="Section.TLabel")
        self.tess_warn_label.pack(anchor="w", pady=(12, 0))
        self.tess_install_btn = ttk.Button(self.f_ocr, text=_("adv_tess_install_btn"), command=self.trigger_tesseract_install, style="Secondary.TButton")

        self.f_meta = ttk.Frame(self.dyn_frame, style="Panel.TFrame")
        ttk.Button(self.f_meta, text=_("adv_read_meta_btn"), command=self.load_metadata, style="Secondary.TButton").grid(row=0, column=0, columnspan=2, sticky="w")
        self._meta_row(self.f_meta, 1, _("adv_meta_title"), self.title_var)
        self._meta_row(self.f_meta, 2, _("adv_meta_author"), self.author_var)
        self._meta_row(self.f_meta, 3, _("adv_meta_subject"), self.subject_var)
        self._meta_row(self.f_meta, 4, _("adv_meta_creator"), self.creator_var)
        ttk.Checkbutton(self.f_meta, text=_("adv_meta_clean"), variable=self.meta_clean_var, style="Flat.TCheckbutton").grid(row=5, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.f_meta.columnconfigure(1, weight=1)

        self.f_sig = ttk.Frame(self.dyn_frame, style="Panel.TFrame")
        self._meta_row(self.f_sig, 0, _("adv_sig_image"), self.sig_image_var, self.choose_sig, _("adv_sig_choose"))
        self._meta_row(self.f_sig, 1, _("adv_sig_page"), self.sig_page_var)
        self._meta_row(self.f_sig, 2, _("adv_sig_x"), self.sig_x_var)
        self._meta_row(self.f_sig, 3, _("adv_sig_y"), self.sig_y_var)
        self._meta_row(self.f_sig, 4, _("adv_sig_scale"), self.sig_scale_var)
        self.f_sig.columnconfigure(1, weight=1)

        self.frames = {
            _("adv_preview"): self.f_preview,
            _("adv_ocr"): self.f_ocr,
            _("adv_metadata"): self.f_meta,
            _("adv_signature"): self.f_sig,
        }
        self.switch_mode()

        ttk.Label(left, text=_("str_output_dir_file"), style="Field.TLabel").pack(anchor="w", pady=(18, 0))
        output_row = ttk.Frame(left, style="Surface.TFrame")
        output_row.pack(fill="x", pady=(8, 0))
        self.output_entry = ttk.Entry(output_row, textvariable=self.output_var, style="Input.TEntry")
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.output_button = ttk.Button(output_row, text=_("str_save_as"), command=self.choose_output, style="Secondary.TButton")
        self.output_button.pack(side="right")

        self.footer = ProgressFooter(left, _("str_start"), self.start_action)
        self.footer.pack(fill="x", pady=(24, 0))

        self.feedback = InlineFeedback(left)
        self.feedback.pack(fill="x", pady=(16, 0))
        self.feedback.set_info(_("adv_operation"), _("adv_preview_hint"))

    def _meta_row(self, parent, row, label_text, variable, button_command=None, button_text=None):
        ttk.Label(parent, text=label_text, style="Field.TLabel").grid(row=row, column=0, sticky="w", pady=(10, 0))
        entry_row = ttk.Frame(parent, style="Panel.TFrame")
        entry_row.grid(row=row, column=1, sticky="ew", pady=(10, 0), padx=(12, 0))
        ttk.Entry(entry_row, textvariable=variable, style="Input.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 10))
        if button_command and button_text:
            ttk.Button(entry_row, text=button_text, command=button_command, style="Secondary.TButton").pack(side="right")

    def switch_mode(self):
        for frame in self.frames.values():
            frame.pack_forget()
        mode = self.action_var.get()
        if mode in self.frames:
            self.frames[mode].pack(fill="both", expand=True)
        if mode == _("adv_ocr"):
            if check_tesseract_availability():
                self.tess_warn_label.config(text=_("adv_tess_installed"))
                self.tess_install_btn.pack_forget()
            else:
                self.tess_warn_label.config(text=_("adv_tess_not_installed"))
                self.tess_install_btn.pack(anchor="w", pady=(10, 0))
        if hasattr(self, "feedback"):
            self.feedback.set_info(_("adv_operation"), mode)

    def choose_input(self):
        selected = filedialog.askopenfilename(title=_("security_dialog_input"), filetypes=[("PDF", "*.pdf")])
        if selected:
            self.input_var.set(selected)
            self.load_metadata(quiet=True)

    def choose_output(self):
        mode = self.action_var.get()
        if mode == _("adv_ocr"):
            selected = filedialog.asksaveasfilename(title=_("adv_dialog_txt_save"), defaultextension=".txt", filetypes=[("Text", "*.txt")])
        else:
            selected = filedialog.asksaveasfilename(title=_("adv_dialog_pdf_save"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.output_var.set(selected)

    def choose_sig(self):
        selected = filedialog.askopenfilename(title=_("adv_dialog_sig_img"), filetypes=[(_("convert_images_label"), "*.png *.jpg *.jpeg")])
        if selected:
            self.sig_image_var.set(selected)

    def load_metadata(self, quiet=False):
        """Fill the metadata fields from the selected PDF.

        quiet=True is the automatic load on file selection: a failure there
        (an encrypted document, say) must not pop an error before the user
        has asked for anything.
        """
        inp = self.input_var.get().strip()
        if not inp or not os.path.isfile(inp):
            if not quiet:
                self.feedback.set_error(_("str_error"), _("err_select_valid_file"))
            return
        try:
            meta = read_metadata(inp)
        except Exception as exc:
            self._meta_loaded_for = None
            if not quiet:
                self.feedback.set_error(_("str_error"), f"{_('err_metadata_read')} {exc}")
            return
        self.title_var.set(meta.get("title", ""))
        self.author_var.set(meta.get("author", ""))
        self.subject_var.set(meta.get("subject", ""))
        self.creator_var.set(meta.get("creator", ""))
        self._meta_loaded_for = inp
        if not quiet:
            self.feedback.set_info(_("str_info"), _("adv_meta_read_ok"))

    def trigger_tesseract_install(self):
        from src.core.install_tesseract import install_target_tesseract

        self.tess_install_btn.config(text=_("adv_tess_installing"), state="disabled")

        def success():
            self.app_root.after(0, self.switch_mode)
            self.app_root.after(0, lambda: self.feedback.set_success(_("adv_tess_install_title"), _("adv_tess_install_ok")))

        def fail(message):
            self.app_root.after(0, lambda: self.feedback.set_error(_("str_error"), message))
            self.app_root.after(0, lambda: self.tess_install_btn.config(text=_("adv_tess_install_btn"), state="normal"))

        install_target_tesseract(on_success=success, on_error=fail)

    def handle_external_drop(self, file_path):
        if file_path.lower().endswith(".pdf"):
            self.input_var.set(file_path)
            self.load_metadata(quiet=True)

    def _cancel_task(self):
        if self._task_ctx:
            self._task_ctx.cancel()

    def start_action(self):
        inp = self.input_var.get().strip()
        out = self.output_var.get().strip()
        mode = self.action_var.get()

        if not inp or not os.path.isfile(inp):
            quick_error(_("err_select_valid_file"), self.footer.action_button, None, self.status_var, self.feedback)
            return

        if mode == _("adv_preview"):
            PDFViewerWindow(self.app_root, inp)
            self.feedback.set_info(_("adv_preview"), _("viewer_title"))
            return

        if not out:
            quick_error(_("err_set_output_file"), self.footer.action_button, None, self.status_var, self.feedback)
            return

        def _on_progress(current, total, message=""):
            self.app_root.after(0, self.footer.update_progress, current, total, message)

        self._task_ctx = TaskContext(progress_callback=_on_progress)
        # Only OCR can actually be cancelled; showing Cancel for metadata and
        # signature meant pressing it said "Cancelling..." and then
        # "Succeeded" anyway.
        cancellable = mode == _("adv_ocr")
        self.footer.start_busy(cancel_callback=self._cancel_task if cancellable else None)
        self.feedback.set_busy(_("str_processing"))
        self.status_var.set(_("str_processing"))

        # Every field is read here, on the main thread, and handed to the
        # worker; workers must not touch Tk variables.
        if mode == _("adv_ocr"):
            threading.Thread(target=self._run_ocr, args=(inp, out), daemon=True).start()
        elif mode == _("adv_metadata"):
            clean = bool(self.meta_clean_var.get())
            # Fields never loaded from this document must not overwrite it.
            known = self._meta_loaded_for == inp
            meta = {
                "clean": clean,
                "title": self.title_var.get() if not clean and known else None,
                "author": self.author_var.get() if not clean and known else None,
                "subject": self.subject_var.get() if not clean and known else None,
                "creator": self.creator_var.get() if not clean and known else None,
            }
            threading.Thread(target=self._run_meta, args=(inp, out, meta), daemon=True).start()
        elif mode == _("adv_signature"):
            signature = {
                "image": self.sig_image_var.get(),
                "page": self.sig_page_var.get(),
                "x": self.sig_x_var.get(),
                "y": self.sig_y_var.get(),
                "scale": self.sig_scale_var.get(),
            }
            threading.Thread(target=self._run_sig, args=(inp, out, signature), daemon=True).start()

    def _finish(self, title, message, output_path):
        def _do():
            self.footer.finish_success()
            self.status_var.set(title)
            self.feedback.set_success(title, message, output_path)
        self.app_root.after(0, _do)

    def _fail(self, title, exc):
        message = friendly_error(exc)
        def _do():
            self.footer.stop_busy()
            self.status_var.set(title)
            self.feedback.set_error(title, message)
        self.app_root.after(0, _do)

    def _cancelled(self):
        def _do():
            self.footer.stop_busy()
            self.status_var.set(_("perf_cancelled"))
            self.feedback.set_cancelled()
        self.app_root.after(0, _do)

    def _run_ocr(self, inp, out):
        try:
            perform_ocr_to_text(inp, out, ctx=self._task_ctx)
            self._finish(_("str_success"), _("adv_result_ocr").format(output=out), out)
        except CancelledError:
            self._cancelled()
        except Exception as exc:
            self._fail(_("str_error"), exc)

    def _run_meta(self, inp, out, meta):
        try:
            update_metadata(
                inp,
                out,
                title=meta["title"],
                author=meta["author"],
                subject=meta["subject"],
                creator=meta["creator"],
                clean=meta["clean"],
            )
            self._finish(_("str_success"), _("adv_result_meta").format(output=out), out)
        except CancelledError:
            self._cancelled()
        except Exception as exc:
            self._fail(_("str_error"), exc)

    def _run_sig(self, inp, out, signature):
        try:
            # The core parses the coordinates, so "100.5" and "100,5" work.
            stamp_visual_signature(
                inp,
                out,
                signature["image"],
                int(float(signature["page"].strip().replace(",", "."))),
                signature["x"],
                signature["y"],
                signature["scale"],
            )
            self._finish(_("str_success"), _("adv_result_sig").format(output=out), out)
        except CancelledError:
            self._cancelled()
        except Exception as exc:
            self._fail(_("str_error"), exc)
