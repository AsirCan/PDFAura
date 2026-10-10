"""What each tool checks before it starts, and what it does and reports.

These used to live in the Tk tabs, each with its own copy of the
"validate, start a thread, format the result" code. Every tool here is a
``check`` (raises Invalid with a message the user can act on) and a ``run``
(does the work with a TaskContext and returns an Outcome). Neither touches
a UI, so both are tested without a window.

Modes are language-independent keys ("encrypt", "pdf2word"); the labels a
UI shows for them come from ``mode_label``.
"""
import os
from dataclasses import dataclass, field

from src.core.lang_manager import _


class Invalid(ValueError):
    """The input has to be fixed before the job can start. str() is the
    message for the user."""


@dataclass
class Outcome:
    title: str
    message: str
    output_path: str | None = None
    tone: str = "success"          # success, warning, error or info
    details: dict = field(default_factory=dict)     # tool-specific numbers, e.g. batch counts


@dataclass(frozen=True)
class Tool:
    name: str
    check: object                   # check(**params) -> None, raises Invalid
    run: object                     # run(ctx, **params) -> Outcome
    fail_title: str                 # lang key of the title shown when run() raises
    busy: object                    # busy(**params) -> text while it runs
    cancellable: object = True      # bool, or cancellable(**params) -> bool
    writes: object = None           # writes(**params) -> the file it creates, if any
    log_progress: bool = False      # progress messages are a log: keep every one


def _require_file(path, message_key):
    if not path or not os.path.isfile(path):
        raise Invalid(_(message_key))


def _require_value(value, message_key):
    if not value:
        raise Invalid(_(message_key))


def _output_written(path):
    if not os.path.isfile(path):
        raise RuntimeError(_("err_output_not_created"))


def _size_mb(path):
    from src.utils.file_helper import format_size_mb
    return format_size_mb(path)


# ── Compress ──────────────────────────────────────────────────────────────

def _compress_check(input, output, quality):
    from src.core.compress import VALID_QUALITIES
    if quality not in VALID_QUALITIES:
        raise Invalid(f"{_('err_select_quality')}{', '.join(VALID_QUALITIES)}")
    _require_file(input, "err_select_valid_pdf")
    _require_value(output, "err_set_output")


def _compress_run(ctx, input, output, quality):
    from src.core.compress import compress_pdf
    original_size = _size_mb(input)
    compress_pdf(input, output, quality, ctx=ctx)
    _output_written(output)
    message = (
        f"{_('compress_result_original')}{original_size:.2f} MB\n"
        f"{_('compress_result_compressed')}{_size_mb(output):.2f} MB\n"
        f"{_('compress_result_quality')}{quality}\n"
        f"{_('compress_result_saved')}{output}"
    )
    return Outcome(_("compress_done"), message, output)


# ── Split ─────────────────────────────────────────────────────────────────

def _page_range(start, end):
    try:
        return int(start), int(end)
    except (TypeError, ValueError):
        raise Invalid(_("err_enter_page_numbers")) from None


def _split_check(input, output, start, end):
    _require_file(input, "err_select_valid_file")
    _page_range(start, end)
    _require_value(output, "err_set_output")


def _split_run(ctx, input, output, start, end):
    from src.core.split import split_pdf
    start, end = _page_range(start, end)
    original_size = _size_mb(input)
    split_pdf(input, output, start, end, ctx=ctx)
    _output_written(output)
    message = _("split_result").format(orig=original_size, result=_size_mb(output), start=start, end=end,
                                       count=end - start + 1, output=output)
    return Outcome(_("split_done"), message, output)


def _split_busy(input, output, start, end):
    start, end = _page_range(start, end)
    return _("split_running").format(start=start, end=end)


# ── Merge ─────────────────────────────────────────────────────────────────

def _merge_check(files, output):
    if len(files) < 2:
        raise Invalid(_("err_min_2_pdf"))
    _require_value(output, "err_set_output")


def _merge_run(ctx, files, output):
    from src.core.common import get_pdf_page_count
    from src.core.merge import merge_pdfs
    files = list(files)
    merge_pdfs(files, output, ctx=ctx)
    _output_written(output)
    message = _("merge_result").format(count=len(files), pages=get_pdf_page_count(output),
                                       size=_size_mb(output), output=output)
    return Outcome(_("merge_done"), message, output)


# ── Edit pages ────────────────────────────────────────────────────────────

EDIT_MODES = ("delete", "rotate", "reorder")


def _edit_check(input, output, mode, **_fields):
    _require_file(input, "err_select_valid_file")
    _require_value(output, "err_set_output")


def _edit_run(ctx, input, output, mode, delete_pages="", rotate_pages="", angle="90", order=""):
    from src.core.common import get_pdf_page_count, parse_page_numbers, parse_page_order
    from src.core.edit import delete_pages_from_pdf, reorder_pages_in_pdf, rotate_pages_in_pdf
    total = get_pdf_page_count(input)
    if mode == "delete":
        if not delete_pages:
            raise ValueError(_("edit_err_enter_delete"))
        pages = parse_page_numbers(delete_pages, total)
        delete_pages_from_pdf(input, output, pages, ctx=ctx)
        message = _("edit_result_delete").format(count=len(pages), remaining=total - len(pages), output=output)
    elif mode == "rotate":
        angle = int(angle)
        pages = parse_page_numbers(rotate_pages, total) if rotate_pages else list(range(1, total + 1))
        rotate_pages_in_pdf(input, output, pages, angle, ctx=ctx)
        message = _("edit_result_rotate").format(count=len(pages), angle=angle, output=output)
    elif mode == "reorder":
        if not order:
            raise ValueError(_("edit_err_enter_order"))
        new_order = parse_page_order(order, total)
        reorder_pages_in_pdf(input, output, new_order, ctx=ctx)
        message = _("edit_result_reorder").format(count=len(new_order), output=output)
    else:
        raise ValueError(f"{_('err_unknown_op')}{mode}")
    return Outcome(_("edit_done"), message, output)


# ── Security ──────────────────────────────────────────────────────────────

SECURITY_MODES = ("encrypt", "decrypt", "watermark")


def _security_check(input, output, mode, password="", confirm="", watermark_text=""):
    from src.core.security import check_new_password
    _require_file(input, "err_select_valid_file")
    _require_value(output, "err_set_output")
    if mode == "encrypt":
        try:
            check_new_password(password, confirm)
        except ValueError as exc:
            raise Invalid(str(exc)) from None
    elif mode == "decrypt" and not password:
        raise Invalid(_("err_password_empty"))


def _security_run(ctx, input, output, mode, password="", confirm="", watermark_text=""):
    from src.core.security import add_watermark_to_pdf, decrypt_pdf, encrypt_pdf
    if mode == "encrypt":
        encrypt_pdf(input, output, password, ctx=ctx)
        message = _("security_result_encrypt").format(output=output)
    elif mode == "decrypt":
        decrypt_pdf(input, output, password, ctx=ctx)
        message = _("security_result_decrypt").format(output=output)
    elif mode == "watermark":
        if not watermark_text:
            raise ValueError(_("err_watermark_empty"))
        add_watermark_to_pdf(input, output, watermark_text, ctx=ctx)
        message = _("security_result_watermark").format(output=output)
    else:
        raise ValueError(f"{_('err_unknown_op')}{mode}")
    return Outcome(_("str_success"), message, output)


# ── Convert ───────────────────────────────────────────────────────────────

CONVERT_MODES = ("pdf2img", "img2pdf", "pdf2word", "word2pdf", "ppt2pdf", "excel2pdf", "pdf2txt")
# The input check's message, by mode.
_CONVERT_INPUT_ERRORS = {
    "pdf2img": "err_select_valid_file",
    "pdf2word": "err_select_valid_file",
    "word2pdf": "err_select_valid_word",
    "ppt2pdf": "err_select_valid_ppt",
    "excel2pdf": "err_select_valid_excel",
    "pdf2txt": "err_select_valid_pdf",
}
# Office conversions and PDF -> Word run inside libraries with no point to
# stop at; a Cancel button there said "Cancelling..." and then succeeded.
_UNCANCELLABLE_CONVERSIONS = ("word2pdf", "ppt2pdf", "excel2pdf", "pdf2word")


def _convert_check(mode, input="", output="", images=(), **_options):
    if mode == "img2pdf":
        if not images:
            raise Invalid(_("err_add_min_1_image"))
        _require_value(output, "err_set_output")
        return
    if mode not in _CONVERT_INPUT_ERRORS:
        raise Invalid(f"{_('err_unknown_op')}{mode}")
    _require_file(input, _CONVERT_INPUT_ERRORS[mode])
    _require_value(output, "err_set_output_folder" if mode == "pdf2img" else "err_set_output")


def _convert_run(ctx, mode, input="", output="", images=(), dpi=300, fmt="png", page_size=None):
    from src.core import convert
    if mode == "pdf2img":
        dpi = int(dpi)
        count = convert.pdf_to_images(input, output, dpi, fmt.lower(), ctx=ctx)
        return Outcome(_("convert_done"), _("convert_result_p2i").format(count=count, dpi=dpi, folder=output),
                       output)
    if mode == "img2pdf":
        images = list(images)
        convert.images_to_pdf(images, output, page_size if page_size is not None else _("convert_original"),
                              ctx=ctx)
        message = _("convert_result_i2p").format(count=len(images), size=_size_mb(output), output=output)
        return Outcome(_("convert_done"), message, output)
    run, result_key = {
        "pdf2word": (convert.pdf_to_word, "convert_result_p2w"),
        "word2pdf": (convert.word_to_pdf, "convert_result_w2p"),
        "ppt2pdf": (convert.ppt_to_pdf, "convert_result_ppt2pdf"),
        "excel2pdf": (convert.excel_to_pdf, "convert_result_excel2pdf"),
        "pdf2txt": (convert.pdf_to_txt, "convert_result_pdf2txt"),
    }[mode]
    run(input, output, ctx=ctx)
    return Outcome(_("convert_done"), _(result_key).format(output=output), output)


# ── Advanced: OCR, metadata, visual signature ─────────────────────────────

ADVANCED_MODES = ("ocr", "metadata", "signature")


def _advanced_check(input, output, mode, **_fields):
    _require_file(input, "err_select_valid_file")
    _require_value(output, "err_set_output_file")


def _advanced_run(ctx, input, output, mode, metadata=None, signature=None):
    if mode == "ocr":
        from src.core.ocr import perform_ocr_to_text
        perform_ocr_to_text(input, output, ctx=ctx)
        return Outcome(_("str_success"), _("adv_result_ocr").format(output=output), output)
    if mode == "metadata":
        from src.core.metainfo import update_metadata
        meta = metadata or {}
        update_metadata(input, output, title=meta.get("title"), author=meta.get("author"),
                        subject=meta.get("subject"), creator=meta.get("creator"),
                        clean=bool(meta.get("clean")))
        return Outcome(_("str_success"), _("adv_result_meta").format(output=output), output)
    if mode == "signature":
        from src.core.signature import stamp_visual_signature
        sig = signature or {}
        # The core parses the coordinates, so "100.5" and "100,5" work.
        page = int(float(str(sig.get("page", "1")).strip().replace(",", ".")))
        stamp_visual_signature(input, output, sig.get("image", ""), page, sig.get("x", "100"),
                               sig.get("y", "100"), sig.get("scale", "1.0"))
        return Outcome(_("str_success"), _("adv_result_sig").format(output=output), output)
    raise ValueError(f"{_('err_unknown_op')}{mode}")


def metadata_fields(clean, loaded, title="", author="", subject="", creator=""):
    """The metadata a run should write. Fields never loaded from this
    document must not overwrite it, so they are None unless ``loaded``."""
    keep = not clean and loaded
    return {"clean": bool(clean), "title": title if keep else None, "author": author if keep else None,
            "subject": subject if keep else None, "creator": creator if keep else None}


# ── Batch ─────────────────────────────────────────────────────────────────

BATCH_MODES = ("compress", "convert", "rename")


def _batch_check(mode, input_dir, output_dir, **_options):
    if not input_dir or not os.path.isdir(input_dir):
        raise Invalid(_("err_select_valid_input_dir"))
    if not output_dir or not os.path.isdir(output_dir):
        raise Invalid(_("err_select_valid_output_dir"))


def _batch_run(ctx, mode, input_dir, output_dir, quality="screen", convert_mode="pdf2img", rename_rule=""):
    from src.core import batch
    # The batch loops report each file through progress_callback; the tab
    # used to pass None there, so its log and bar never moved until the end.
    log = ctx.notify if ctx else None
    if mode == "compress":
        succeeded, errors = batch.batch_compress_dir(input_dir, output_dir, quality, log, ctx=ctx)
    elif mode == "convert":
        succeeded, errors = batch.batch_convert_dir(input_dir, output_dir, convert_mode, log, ctx=ctx)
    else:
        succeeded, errors = batch.batch_rename_dir(input_dir, output_dir, rename_rule, log, ctx=ctx)
    return batch_outcome(succeeded, errors, output_dir)


def batch_outcome(succeeded, errors, output_dir):
    """Say what actually happened: a run where every file failed used to
    show the green DONE badge."""
    title = _("batch_result_title")
    counts = {"succeeded": succeeded, "failed": len(errors)}
    message = _("batch_result").format(succ=succeeded, errs=len(errors))
    if errors:
        message += _("batch_result_errors").format(dir=output_dir)
    if succeeded == 0 and errors:
        return Outcome(title, _("batch_result_all_failed").format(errs=len(errors)), None, "error", counts)
    if errors:
        return Outcome(title, message, output_dir, "warning", counts)
    if succeeded == 0:
        return Outcome(title, _("batch_no_file_found"), None, "info", counts)
    return Outcome(title, message, output_dir, details=counts)


# ── Registry ──────────────────────────────────────────────────────────────

def _plain(key):
    return lambda **_params: _(key)


def _writes_output(output="", **_params):
    return output


def _convert_writes(mode, output="", **_params):
    # PDF -> Images fills a folder; asking about the folder itself means nothing.
    return None if mode == "pdf2img" else output


TOOLS = {tool.name: tool for tool in (
    Tool("compress", _compress_check, _compress_run, "compress_fail", _plain("compress_running"),
         writes=_writes_output),
    Tool("split", _split_check, _split_run, "split_fail", _split_busy, writes=_writes_output),
    Tool("merge", _merge_check, _merge_run, "merge_fail",
         lambda files, **_p: _("merge_running").format(count=len(files)), writes=_writes_output),
    Tool("edit", _edit_check, _edit_run, "edit_fail",
         lambda mode, **_p: _("edit_running").format(mode=mode_label("edit", mode)), writes=_writes_output),
    Tool("security", _security_check, _security_run, "str_failed",
         lambda mode, **_p: _("security_running").format(mode=mode_label("security", mode)),
         writes=_writes_output),
    Tool("convert", _convert_check, _convert_run, "convert_fail",
         lambda mode, **_p: _("convert_running").format(mode=mode_label("convert", mode)),
         cancellable=lambda mode, **_p: mode not in _UNCANCELLABLE_CONVERSIONS, writes=_convert_writes),
    Tool("advanced", _advanced_check, _advanced_run, "str_error", _plain("str_processing"),
         cancellable=lambda mode, **_p: mode == "ocr", writes=_writes_output),
    Tool("batch", _batch_check, _batch_run, "err_critical", _plain("str_processing"), log_progress=True),
)}

# The label each UI shows for a mode, by lang key.
_MODE_LABEL_KEYS = {
    "edit": {"delete": "edit_mode_delete", "rotate": "edit_mode_rotate", "reorder": "edit_mode_reorder"},
    "security": {"encrypt": "security_encrypt", "decrypt": "security_decrypt",
                 "watermark": "security_watermark"},
    "convert": {mode: f"convert_{mode}" for mode in CONVERT_MODES},
    "advanced": {"preview": "adv_preview", "ocr": "adv_ocr", "metadata": "adv_metadata",
                 "signature": "adv_signature"},
    "batch": {"compress": "batch_compress", "convert": "batch_convert", "rename": "batch_rename"},
}


def mode_label(tool, mode):
    """The localised label for ``mode`` of ``tool`` ("encrypt" -> "Şifrele")."""
    key = _MODE_LABEL_KEYS[tool].get(mode)
    return _(key) if key else mode


def get(name):
    return TOOLS[name]


def check(name, params):
    """None if the tool can start with ``params``, else the message to show."""
    try:
        TOOLS[name].check(**params)
    except Invalid as exc:
        return str(exc)
    return None


def busy_text(name, params):
    return TOOLS[name].busy(**params)


def is_cancellable(name, params):
    cancellable = TOOLS[name].cancellable
    return cancellable(**params) if callable(cancellable) else bool(cancellable)


def existing_target(name, params):
    """The file a run would replace, if the tool writes one that exists now."""
    writes = TOOLS[name].writes
    path = writes(**params) if writes else None
    return path if path and os.path.isfile(path) else None


# ── Suggested output ──────────────────────────────────────────────────────

# What a tool writes when the user has not picked a place, by (tool, mode):
# the suffix (an output_paths.SUFFIX_KEYS name, or None for none) and the
# extension (None keeps the input's; "" is a folder).
_OUTPUT_NAMES = {
    ("compress", None): ("compressed", None),
    ("split", None): ("split", None),
    ("merge", None): ("merged", ".pdf"),
    ("edit", None): ("edited", None),
    ("security", "encrypt"): ("encrypted", None),
    ("security", "decrypt"): ("decrypted", None),
    ("security", "watermark"): ("watermarked", None),
    ("convert", "pdf2img"): ("images", ""),
    ("convert", "img2pdf"): ("merged", ".pdf"),
    ("convert", "pdf2word"): (None, ".docx"),
    ("convert", "word2pdf"): (None, ".pdf"),
    ("convert", "ppt2pdf"): (None, ".pdf"),
    ("convert", "excel2pdf"): (None, ".pdf"),
    ("convert", "pdf2txt"): (None, ".txt"),
    ("scanner", None): ("scanned", ".pdf"),
}


def suggest_output(tool, source, mode=None, start=None, end=None):
    """Where ``tool`` writes for ``source`` (its input, or the first of
    several) unless the user picks a place.

    The name is '<stem><suffix><ext>'; it goes in the default output folder
    from Settings when one is set, otherwise next to ``source``. Every tool
    follows that setting now; only Compress used to. Split adds the page
    range, as '_<start>-<end>'. "" when there is no source yet.
    """
    from src.core.output_paths import suggest_output as suggest
    if not source:
        return ""
    kind, ext = _OUTPUT_NAMES.get((tool, mode)) or _OUTPUT_NAMES[(tool, None)]
    tail = f"_{start}-{end}" if tool == "split" else ""
    return suggest(source, kind, ext, tail=tail)
