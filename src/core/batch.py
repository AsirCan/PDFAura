import os
import re
import shutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.core.compress import compress_pdf
from src.core.convert import images_to_pdf, pdf_to_images
from src.core.common import get_pdf_page_count
from src.core.output_paths import is_inside, mirrored_output, unique_path
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

def batch_compress_dir(input_dir, output_dir, quality="screen", progress_callback=None, ctx=None):
    """
    Finds all PDFs in input_dir, compresses them and saves them into output_dir.
    Returns (success_count, error_list)

    One file at a time: compression now runs inside PyMuPDF, which must not be
    used from several threads at once (the old parallel Ghostscript runs were
    separate processes).
    """
    os.makedirs(output_dir, exist_ok=True)
    pdfs = get_files_in_dir(input_dir, [".pdf"], exclude_dir=output_dir)
    if not pdfs:
        return 0, [_("batch_no_pdf_found")]

    success = 0
    errors = []
    total = len(pdfs)
    taken = set()

    for idx, pdf in enumerate(pdfs):
        if ctx:
            ctx.check_cancelled()
        base = os.path.relpath(pdf, input_dir)
        out_path = mirrored_output(pdf, input_dir, output_dir, prefix="compressed_", taken=taken)
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
    """
    os.makedirs(output_dir, exist_ok=True)
    success = 0
    errors = []
    taken = set()
    
    if mode == "pdf2img":
        files = get_files_in_dir(input_dir, [".pdf"], exclude_dir=output_dir)
        total = len(files)
        for idx, f in enumerate(files):
            if ctx:
                ctx.check_cancelled()
            base = os.path.relpath(f, input_dir)
            # A separate subfolder per PDF, mirroring the input tree so that
            # rapor.pdf and alt/rapor.pdf do not share one image folder.
            pdf_out_dir = mirrored_output(f, input_dir, output_dir, ext="", taken=taken)
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
        files = get_files_in_dir(input_dir, [".png", ".jpg", ".jpeg"], exclude_dir=output_dir)
        total = len(files)
        
        # Çoklu çekirdek: paralel dönüştürme
        max_workers = min(os.cpu_count() or 4, total, 4)
        
        if max_workers > 1 and total > 1:
            completed = 0
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_img = {}
                for img in files:
                    if ctx and ctx.is_cancelled:
                        break
                    base = os.path.relpath(img, input_dir)
                    out_pdf = mirrored_output(img, input_dir, output_dir, ext=".pdf", taken=taken)
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
            for idx, img in enumerate(files):
                if ctx:
                    ctx.check_cancelled()
                base = os.path.relpath(img, input_dir)
                out_pdf = mirrored_output(img, input_dir, output_dir, ext=".pdf", taken=taken)
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
                    
    if not files:
        return 0, [_("batch_no_file_found")]

    _write_report(output_dir, f"Batch_Convert_Report_{mode}", len(files), success, errors)
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
    pdfs = get_files_in_dir(input_dir, [".pdf"], exclude_dir=output_dir)
    if not pdfs:
        return 0, [_("batch_no_pdf_found")]

    success = 0
    errors = []
    total = len(pdfs)
    taken = set()
    now_str = datetime.now().strftime("%Y-%m-%d")
    
    for idx, pdf in enumerate(pdfs):
        if ctx:
            ctx.check_cancelled()
        try:
            base = os.path.basename(pdf)
            name_only = os.path.splitext(base)[0]
            size_mb = f"{format_size_mb(pdf):.1f}MB"
            pages = str(get_pdf_page_count(pdf))
            seq = f"{(idx + 1):03d}"  # 001, 002...
            
            values = {
                "original_name": name_only,
                "page_count": pages + "pp",
                "size": size_mb,
                "order": seq,
                "date": now_str,
            }
            new_name = _apply_rename_tokens(naming_rule, values)

            # Sanitize new_name to ensure it's a valid path avoiding illegal chars
            invalid_chars = r'<>:"/\|?*'
            for char in invalid_chars:
                new_name = new_name.replace(char, "_")

            out_pdf = unique_path(os.path.join(output_dir, f"{new_name}.pdf"), taken, check_disk=False)

            # Simple copy operation for rename mapping
            shutil.copy2(pdf, out_pdf)
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
