import os
import re
import shutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.core.compress import compress_pdf
from src.core.convert import images_to_pdf, pdf_to_images
from src.core.common import get_pdf_page_count
from src.core.output_paths import atomic_output, is_inside, mirrored_output, unique_path
from src.utils.file_helper import format_size_mb
from src.core.lang_manager import _


# Naming-rule tokens. Each canonical token carries every spelling shown in
# the UI hints: the Turkish hint uses the dotted "İ" while the code used to
# expect "I", so [TARİH] was copied into the filename verbatim.
RENAME_TOKENS = {
    "original_name": ["ORIJINAL_AD", "ORİJİNAL_AD", "ORIGINAL_NAME"],
    "page_count":    ["SAYFA_SAYISI", "PAGE_COUNT"],
    "size":          ["BOYUT", "SIZE"],
    "order":         ["SIRA", "ORDER"],
    "date":          ["TARIH", "TARİH", "DATE"],
}

CONVERT_MODES = ("pdf2img", "img2pdf")
IMAGE_EXTS = [".png", ".jpg", ".jpeg"]

# Names Windows will not create a file under, whatever the extension.
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {f"{port}{n}" for port in ("COM", "LPT") for n in range(1, 10)}
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def get_files_in_dir(directory, exts=[".pdf"], exclude_dir=None):
    """Absolute paths of matching files under *directory*.

    *exclude_dir* keeps the output folder out of the scan; without it, an
    output folder inside the input folder meant a second run reprocessed its
    own results into compressed_compressed_rapor.pdf.
    """
    matched = []
    if not os.path.isdir(directory):
        return matched

    for root, dirs, files in os.walk(directory):
        if exclude_dir:
            dirs[:] = [d for d in dirs if not is_inside(os.path.join(root, d), exclude_dir)]
            if is_inside(root, exclude_dir):
                continue
        for f in files:
            for ext in exts:
                if f.lower().endswith(ext.lower()):
                    matched.append(os.path.join(root, f))
    return sorted(matched)


# ── Where every file of a run goes ───────────────────────────────────────
#
# Planned before the run: the window asks before a run replaces files that
# are already in the output folder (#34), and the run follows the same plan.
# Within a run every name is unique; on disk a name may be taken, by an
# earlier run or by a file of the user's -- that is what gets asked about.

def plan_compress(input_dir, output_dir, create=False):
    """(pdf, compressed copy) for every PDF under *input_dir*."""
    pdfs = get_files_in_dir(input_dir, [".pdf"], exclude_dir=output_dir)
    taken = set()
    return [(pdf, mirrored_output(pdf, input_dir, output_dir, prefix="compressed_", taken=taken, create=create))
            for pdf in pdfs]


def plan_convert(input_dir, output_dir, mode, create=False):
    """(source, target) pairs: an image folder per PDF, or a PDF per image."""
    if mode not in CONVERT_MODES:
        raise ValueError(f"{_('err_unknown_op')}{mode}")
    taken = set()
    if mode == "pdf2img":
        files = get_files_in_dir(input_dir, [".pdf"], exclude_dir=output_dir)
        return [(f, mirrored_output(f, input_dir, output_dir, ext="", taken=taken, create=create)) for f in files]
    files = get_files_in_dir(input_dir, IMAGE_EXTS, exclude_dir=output_dir)
    return [(f, mirrored_output(f, input_dir, output_dir, ext=".pdf", taken=taken, create=create))
            for f in files]


def plan_rename(input_dir, output_dir, naming_rule):
    """(pdf, renamed copy, None) for every PDF, in order; a file whose name
    cannot be worked out gets (pdf, None, the error)."""
    pdfs = get_files_in_dir(input_dir, [".pdf"], exclude_dir=output_dir)
    taken = set()
    today = datetime.now().strftime("%Y-%m-%d")
    plan = []
    for idx, pdf in enumerate(pdfs):
        try:
            values = {
                "original_name": os.path.splitext(os.path.basename(pdf))[0],
                "page_count": f"{get_pdf_page_count(pdf)}pp",
                "size": f"{format_size_mb(pdf):.1f}MB",
                "order": f"{idx + 1:03d}",  # 001, 002...
                "date": today,
            }
            stem = rename_stem(naming_rule, values)
            plan.append((pdf, unique_path(os.path.join(output_dir, f"{stem}.pdf"), taken, check_disk=False), None))
        except Exception as exc:
            plan.append((pdf, None, exc))
    return plan


def existing_outputs(mode, input_dir, output_dir, convert_mode="pdf2img", rename_rule=""):
    """What a run would replace: planned files that exist, and planned image
    folders that already hold files."""
    if not os.path.isdir(output_dir) or not os.listdir(output_dir):
        return []
    if mode == "compress":
        targets = [target for _pdf, target in plan_compress(input_dir, output_dir)]
    elif mode == "convert":
        targets = [target for _source, target in plan_convert(input_dir, output_dir, convert_mode)]
    else:
        targets = [target for _pdf, target, _problem in plan_rename(input_dir, output_dir, rename_rule) if target]
    return [target for target in targets
            if os.path.isfile(target) or (os.path.isdir(target) and os.listdir(target))]


def batch_compress_dir(input_dir, output_dir, quality="screen", progress_callback=None, ctx=None):
    """
    Finds all PDFs in input_dir, compresses them and saves them into output_dir.
    Returns (success_count, error_list)

    One file at a time: compression now runs inside PyMuPDF, which must not be
    used from several threads at once (the old parallel Ghostscript runs were
    separate processes).
    """
    os.makedirs(output_dir, exist_ok=True)
    plan = plan_compress(input_dir, output_dir, create=True)
    if not plan:
        return 0, [_("batch_no_pdf_found")]

    success = 0
    errors = []
    total = len(plan)

    for idx, (pdf, out_path) in enumerate(plan):
        if ctx:
            ctx.check_cancelled()
        base = os.path.relpath(pdf, input_dir)
        try:
            compress_pdf(pdf, out_path, quality)
            success += 1
            if progress_callback:
                progress_callback(idx + 1, total, f"{_('batch_log_compressed')}: {base}")
        except Exception as e:
            err = f"{base} -> {_('str_error')}: {str(e)}"
            errors.append(err)
            if progress_callback:
                progress_callback(idx + 1, total, err)

    _write_report(output_dir, "Batch_Compress_Report", total, success, errors)
    return success, errors

def batch_convert_dir(input_dir, output_dir, mode="img2pdf", progress_callback=None, ctx=None):
    """
    mode: "img2pdf" or "pdf2img"
    img2pdf -> Finds all images, creates 1 Independent PDF for each.
    pdf2img -> Finds all PDFs, runs pdf_to_images for each, dumps them into output_dir.
    Any other mode is a ValueError; it used to end in an UnboundLocalError.
    """
    plan = plan_convert(input_dir, output_dir, mode, create=True)
    os.makedirs(output_dir, exist_ok=True)
    success = 0
    errors = []
    total = len(plan)

    if mode == "pdf2img":
        # A separate subfolder per PDF, mirroring the input tree so that
        # rapor.pdf and alt/rapor.pdf do not share one image folder.
        for idx, (f, pdf_out_dir) in enumerate(plan):
            if ctx:
                ctx.check_cancelled()
            base = os.path.relpath(f, input_dir)
            try:
                pdf_to_images(f, pdf_out_dir, img_format="png", dpi=200)
                success += 1
                if progress_callback:
                    progress_callback(idx + 1, total, f"{_('batch_log_pages_extracted')}: {base}")
            except Exception as e:
                err = f"{base} -> {_('str_error')}: {str(e)}"
                errors.append(err)
                if progress_callback:
                    progress_callback(idx + 1, total, err)

    elif mode == "img2pdf":
        # Çoklu çekirdek: paralel dönüştürme
        max_workers = min(os.cpu_count() or 4, total, 4)

        if max_workers > 1 and total > 1:
            completed = 0
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_img = {}
                for img, out_pdf in plan:
                    if ctx and ctx.is_cancelled:
                        break
                    base = os.path.relpath(img, input_dir)
                    future = executor.submit(images_to_pdf, [img], out_pdf)
                    future_to_img[future] = (img, base)

                for future in as_completed(future_to_img):
                    if ctx and ctx.is_cancelled:
                        executor.shutdown(wait=False, cancel_futures=True)
                        from src.core.task_manager import CancelledError
                        raise CancelledError("İşlem kullanıcı tarafından iptal edildi.")

                    img, base = future_to_img[future]
                    completed += 1
                    try:
                        future.result()
                        success += 1
                        if progress_callback:
                            progress_callback(completed, total, f"{_('batch_log_pdf_created')}: {base}")
                    except Exception as e:
                        err = f"{base} -> {_('str_error')}: {str(e)}"
                        errors.append(err)
                        if progress_callback:
                            progress_callback(completed, total, err)
        else:
            for idx, (img, out_pdf) in enumerate(plan):
                if ctx:
                    ctx.check_cancelled()
                base = os.path.relpath(img, input_dir)
                try:
                    images_to_pdf([img], out_pdf)
                    success += 1
                    if progress_callback:
                        progress_callback(idx + 1, total, f"{_('batch_log_pdf_created')}: {base}")
                except Exception as e:
                    err = f"{base} -> {_('str_error')}: {str(e)}"
                    errors.append(err)
                    if progress_callback:
                        progress_callback(idx + 1, total, err)

    if not plan:
        return 0, [_("batch_no_file_found")]

    _write_report(output_dir, f"Batch_Convert_Report_{mode}", total, success, errors)
    return success, errors

def batch_rename_dir(input_dir, output_dir, naming_rule, progress_callback=None, ctx=None):
    """
    naming_rule specifies the formatting string.
    Supported tokens:
    [ORIJINAL_AD], [SAYFA_SAYISI], [BOYUT], [SIRA], [TARIH]
    Example: Fatura_[ORIJINAL_AD]_[SIRA]
    The files are effectively COPIED and Renamed into the output_dir.
    """
    os.makedirs(output_dir, exist_ok=True)
    plan = plan_rename(input_dir, output_dir, naming_rule)
    if not plan:
        return 0, [_("batch_no_pdf_found")]

    success = 0
    errors = []
    total = len(plan)

    for idx, (pdf, out_pdf, problem) in enumerate(plan):
        if ctx:
            ctx.check_cancelled()
        base = os.path.basename(pdf)
        try:
            if problem is not None:
                raise problem
            # A copy cut short must not leave half a file under the new name.
            with atomic_output(out_pdf) as temp_path:
                shutil.copy2(pdf, temp_path)
            success += 1
            if progress_callback:
                progress_callback(idx + 1, total, f"{base} -> {os.path.basename(out_pdf)}")

        except Exception as e:
            err = f"{base} -> {_('str_error')}: {str(e)}"
            errors.append(err)
            if progress_callback:
                progress_callback(idx + 1, total, err)

    _write_report(output_dir, "Batch_Rename_Report", total, success, errors)
    return success, errors


# Values like a real file's, to try a naming rule before a run.
SAMPLE_RENAME_VALUES = {"original_name": "rapor", "page_count": "3pp", "size": "0.1MB", "order": "001",
                        "date": "2026-01-01"}


def rename_stem(rule, values):
    """The name (without .pdf) *rule* gives a file with these *values*.

    Characters Windows forbids become "_", and a name that is still no
    usable file name is a ValueError: an empty rule wrote '.pdf', '.pdf (2)'
    and so on, and Windows will not create 'CON.pdf' at all.
    """
    name = _INVALID_CHARS.sub("_", _apply_rename_tokens(rule or "", values))
    name = name.strip().rstrip(". ")
    if not name or name.split(".")[0].rstrip().upper() in _RESERVED_NAMES:
        raise ValueError(_("err_rename_rule_invalid"))
    return name


def _apply_rename_tokens(rule, values):
    """Replace every spelling of every naming token in *rule*.

    Tokens are matched case-insensitively and across the Turkish dotted-I
    spellings, so the [ORİJİNAL_AD] and [TARİH] shown in the Turkish hint
    work as well as the [ORIGINAL_NAME] and [DATE] in the English one.
    """
    result = rule
    for canonical, aliases in RENAME_TOKENS.items():
        replacement = values[canonical]
        for alias in aliases:
            pattern = re.compile(r"\[" + re.escape(alias) + r"\]", re.IGNORECASE)
            result = pattern.sub(lambda _m: replacement, result)
    return result


def _write_report(output_dir, report_name, total, success, errors):
    """Dumps the log internally so the user doesn't lose it if they close the app."""
    if total == 0: return

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(output_dir, f"{report_name}_{date_str}.txt")

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"PDF Aura - {report_name.replace('_', ' ')}\n")
        f.write(f"{_('batch_report_date')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*50 + "\n")
        f.write(f"{_('batch_report_total')}: {total}\n")
        f.write(f"{_('batch_report_success')}: {success}\n")
        f.write(f"{_('batch_report_errors')}: {len(errors)}\n")
        f.write("="*50 + "\n\n")

        if errors:
            f.write(f"{_('batch_report_error_details')}:\n")
            for e in errors:
                f.write(f"- {e}\n")
        else:
            f.write(f"{_('batch_report_no_errors')}\n")
