import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from src.core.edit import delete_pages_from_pdf, rotate_pages_in_pdf, reorder_pages_in_pdf
from src.core.common import get_pdf_page_count, parse_page_numbers
from src.gui.helpers import set_busy, operation_done
from src.core.lang_manager import _

class EditTab:
    def __init__(self, parent, app_root):
        self.parent = parent
        self.app_root = app_root
        
        self.edit_input_var = tk.StringVar()
        self.edit_output_var = tk.StringVar()
        self.edit_mode_var = tk.StringVar(value=_("edit_mode_delete"))
        self.edit_pages_var = tk.StringVar()
        self.edit_angle_var = tk.StringVar(value="90")
        self.edit_order_var = tk.StringVar()
        self.edit_page_info_var = tk.StringVar(value="")
        self.edit_status_var = tk.StringVar(value=_("str_ready"))
        
        self.build_ui()

    def build_ui(self):
        c = ttk.Frame(self.parent, padding=20, style="Card.TFrame")
        c.pack(fill="both", expand=True, pady=(12, 0))

        ttk.Label(c, text=_("str_file_selection"), style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(c, text=_("str_input_pdf"), style="Field.TLabel").grid(row=1, column=0, sticky="w", pady=(14, 8))
        ef = ttk.Frame(c, style="Card.TFrame")
        ef.grid(row=2, column=0, sticky="ew")
        self.edit_input_entry = ttk.Entry(ef, textvariable=self.edit_input_var, width=58, style="Dark.TEntry")
        self.edit_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.edit_input_button = ttk.Button(ef, text=_("str_browse"), command=self.choose_edit_input_pdf, style="Secondary.TButton")
        self.edit_input_button.pack(side="right")

        self.edit_page_info_label = ttk.Label(c, textvariable=self.edit_page_info_var, style="PageInfo.TLabel")
        self.edit_page_info_label.grid(row=3, column=0, sticky="w", pady=(4, 0))

        ttk.Label(c, text=_("edit_operation"), style="Section.TLabel").grid(row=4, column=0, sticky="w", pady=(18, 0))
        self.edit_mode_combo = ttk.Combobox(c, textvariable=self.edit_mode_var,
                                             values=[_("edit_mode_delete"), _("edit_mode_rotate"), _("edit_mode_reorder")],
                                             state="readonly", width=24, style="Dark.TCombobox")
        self.edit_mode_combo.grid(row=5, column=0, sticky="w", pady=(10, 0))
        self.edit_mode_combo.bind("<<ComboboxSelected>>", lambda e: self.switch_edit_mode())

        self.edit_dynamic = ttk.Frame(c, style="Card.TFrame")
        self.edit_dynamic.grid(row=6, column=0, sticky="ew", pady=(12, 0))

        # Delete frame
        self.edit_delete_frame = ttk.Frame(self.edit_dynamic, style="Card.TFrame")
        ttk.Label(self.edit_delete_frame, text=_("edit_pages_to_delete"), style="Field.TLabel").pack(anchor="w")
        self.edit_delete_entry = ttk.Entry(self.edit_delete_frame, textvariable=self.edit_pages_var, width=40, style="Dark.TEntry")
        self.edit_delete_entry.pack(anchor="w", pady=(8, 0))
        ttk.Label(self.edit_delete_frame, text=_("edit_delete_hint"), style="Hint.TLabel").pack(anchor="w", pady=(6, 0))

        # Rotate frame
        self.edit_rotate_frame = ttk.Frame(self.edit_dynamic, style="Card.TFrame")
        ttk.Label(self.edit_rotate_frame, text=_("edit_pages_to_rotate"), style="Field.TLabel").pack(anchor="w")
        self.edit_rotate_pages_entry = ttk.Entry(self.edit_rotate_frame, textvariable=self.edit_pages_var, width=40, style="Dark.TEntry")
        self.edit_rotate_pages_entry.pack(anchor="w", pady=(8, 0))
        ttk.Label(self.edit_rotate_frame, text=_("edit_rotate_hint"), style="Hint.TLabel").pack(anchor="w", pady=(6, 0))
        af = ttk.Frame(self.edit_rotate_frame, style="Card.TFrame")
        af.pack(anchor="w", pady=(10, 0))
        ttk.Label(af, text=_("edit_angle"), style="Field.TLabel").pack(side="left", padx=(0, 10))
        self.edit_angle_combo = ttk.Combobox(af, textvariable=self.edit_angle_var,
                                              values=["90", "180", "270"], state="readonly",
                                              width=8, style="Dark.TCombobox")
        self.edit_angle_combo.pack(side="left")
        ttk.Label(af, text=_("edit_angle_hint"), style="Hint.TLabel").pack(side="left", padx=(10, 0))

        # Reorder frame
        self.edit_reorder_frame = ttk.Frame(self.edit_dynamic, style="Card.TFrame")
        ttk.Label(self.edit_reorder_frame, text=_("edit_new_order"), style="Field.TLabel").pack(anchor="w")
        self.edit_order_entry = ttk.Entry(self.edit_reorder_frame, textvariable=self.edit_order_var, width=40, style="Dark.TEntry")
        self.edit_order_entry.pack(anchor="w", pady=(8, 0))
        ttk.Label(self.edit_reorder_frame, text=_("edit_order_hint"),
                  style="Hint.TLabel").pack(anchor="w", pady=(6, 0))

        self.edit_frames = {
            _("edit_mode_delete"): self.edit_delete_frame,
            _("edit_mode_rotate"): self.edit_rotate_frame,
            _("edit_mode_reorder"): self.edit_reorder_frame,
        }
        self.switch_edit_mode()

        # Output
        ttk.Label(c, text=_("str_output_pdf"), style="Field.TLabel").grid(row=7, column=0, sticky="w", pady=(16, 8))
        of = ttk.Frame(c, style="Card.TFrame")
        of.grid(row=8, column=0, sticky="ew")
        self.edit_output_entry = ttk.Entry(of, textvariable=self.edit_output_var, width=58, style="Dark.TEntry")
        self.edit_output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.edit_output_button = ttk.Button(of, text=_("str_save_as"), command=self.choose_edit_output_pdf, style="Secondary.TButton")
        self.edit_output_button.pack(side="right")

        self.edit_button = ttk.Button(c, text=_("str_apply"), command=self.start_edit, style="Edit.TButton")
        self.edit_button.grid(row=9, column=0, sticky="w", pady=(22, 12))
        self.edit_progress_bar = ttk.Progressbar(c, mode="indeterminate", length=520, style="Edit.Horizontal.TProgressbar")
        self.edit_progress_bar.grid(row=10, column=0, sticky="ew", pady=(2, 12))
        self.edit_status_label = ttk.Label(c, textvariable=self.edit_status_var, style="EditStatus.TLabel")
        self.edit_status_label.grid(row=11, column=0, sticky="w")
        c.columnconfigure(0, weight=1)

    def switch_edit_mode(self):
        for frame in self.edit_frames.values():
            frame.pack_forget()
        mode = self.edit_mode_var.get()
        if mode in self.edit_frames:
            self.edit_frames[mode].pack(fill="x", expand=True)

    def choose_edit_input_pdf(self):
        f = filedialog.askopenfilename(title=_("edit_dialog_input"), filetypes=[("PDF", "*.pdf")])
        if not f:
            return
        self.edit_input_var.set(f)
        try:
            total = get_pdf_page_count(f)
            self.edit_page_info_var.set(_("edit_total_pages").format(count=total))
        except Exception as exc:
            self.edit_page_info_var.set(f"{_('str_error')}: {exc}")
        base, ext = os.path.splitext(f)
        self.edit_output_var.set(f"{base}_duzenlenmis{ext}")

    def choose_edit_output_pdf(self):
        f = filedialog.asksaveasfilename(title=_("edit_dialog_output"), defaultextension=".pdf",
                                          filetypes=[("PDF", "*.pdf")])
        if f:
            self.edit_output_var.set(f)

    def start_edit(self):
        input_pdf = self.edit_input_var.get().strip()
        output_pdf = self.edit_output_var.get().strip()
        mode = self.edit_mode_var.get()
        if not input_pdf or not os.path.isfile(input_pdf):
            messagebox.showerror(_("str_error"), _("err_select_valid_file"))
            return
        if not output_pdf:
            messagebox.showerror(_("str_error"), _("err_set_output"))
            return
        set_busy(self.edit_button, self.edit_progress_bar, True)
        self.edit_status_var.set(_("edit_running").format(mode=mode))
        threading.Thread(target=self._run_edit, args=(input_pdf, output_pdf, mode), daemon=True).start()

    def _run_edit(self, input_pdf, output_pdf, mode):
        try:
            total = get_pdf_page_count(input_pdf)
            if mode == _("edit_mode_delete"):
                pages_text = self.edit_pages_var.get().strip()
                if not pages_text:
                    raise ValueError(_("edit_err_enter_delete"))
                pages = parse_page_numbers(pages_text, total)
                delete_pages_from_pdf(input_pdf, output_pdf, pages)
                remaining = total - len(pages)
                msg = _("edit_result_delete").format(count=len(pages), remaining=remaining, output=output_pdf)

            elif mode == _("edit_mode_rotate"):
                pages_text = self.edit_pages_var.get().strip()
                angle = int(self.edit_angle_var.get())
                if pages_text:
                    pages = parse_page_numbers(pages_text, total)
                else:
                    pages = list(range(1, total + 1))
                rotate_pages_in_pdf(input_pdf, output_pdf, pages, angle)
                msg = _("edit_result_rotate").format(count=len(pages), angle=angle, output=output_pdf)

            elif mode == _("edit_mode_reorder"):
                order_text = self.edit_order_var.get().strip()
                if not order_text:
                    raise ValueError(_("edit_err_enter_order"))
                new_order = [int(x.strip()) for x in order_text.split(",")]
                reorder_pages_in_pdf(input_pdf, output_pdf, new_order)
                msg = _("edit_result_reorder").format(count=len(new_order), output=output_pdf)
            else:
                raise ValueError(f"{_('err_unknown_op')}{mode}")

            self.app_root.after(0, operation_done, self.app_root, self.edit_button, self.edit_progress_bar,
                            self.edit_status_var, _("edit_done"), msg, None)
        except Exception as exc:
            self.app_root.after(0, operation_done, self.app_root, self.edit_button, self.edit_progress_bar,
                            self.edit_status_var, _("edit_fail"), None, str(exc))
