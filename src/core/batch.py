import os
import shutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyPDF2 import PdfReader

from src.core.compress import compress_pdf
from src.core.convert import images_to_pdf, pdf_to_images
from src.core.common import get_pdf_page_count
from src.utils.file_helper import format_size_mb
from src.core.lang_manager import _

def get_files_in_dir(directory, exts=[".pdf"]):
    """Returns a list of absolute paths pointing to files matching the extensions in the given directory."""
    matched = []
    if not os.path.isdir(directory):
        return matched
        
    for root, _, files in os.walk(directory):
        for f in files:
            for ext in exts:
                if f.lower().endswith(ext.lower()):
                    matched.append(os.path.join(root, f))
    return matched

def batch_compress_dir(input_dir, output_dir, quality="screen", progress_callback=None, ctx=None):
    """
    Finds all PDFs in input_dir, compresses them via Python Core, saves into output_dir.
    Çoklu çekirdek desteği ile paralel çalışır.
    Returns (success_count, error_list)
    """
    pdfs = get_files_in_dir(input_dir, [".pdf"])
    if not pdfs:
        return 0, [_("batch_no_pdf_found")]
        
    os.makedirs(output_dir, exist_ok=True)
    success = 0
    errors = []
    total = len(pdfs)
    
    # Çoklu çekirdek: paralel sıkıştırma
    max_workers = min(os.cpu_count() or 4, total, 4)
    
    if max_workers > 1 and total > 1:
        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_pdf = {}
            for pdf in pdfs:
                if ctx and ctx.is_cancelled:
                    break
                base = os.path.basename(pdf)
                out_path = os.path.join(output_dir, f"compressed_{base}")
                future = executor.submit(compress_pdf, pdf, out_path, quality)
                future_to_pdf[future] = (pdf, base, out_path)
            
            for future in as_completed(future_to_pdf):
                if ctx and ctx.is_cancelled:
                    executor.shutdown(wait=False, cancel_futures=True)
                    from src.core.task_manager import CancelledError
                    raise CancelledError("İşlem kullanıcı tarafından iptal edildi.")
                
                pdf, base, out_path = future_to_pdf[future]
                completed += 1
                try:
                    future.result()
                    success += 1
                    if progress_callback:
                        progress_callback(completed, total, f"{_('batch_log_compressed')}: {base}")
                except Exception as e:
                    err = f"{base} -> {_('str_error')}: {str(e)}"
                    errors.append(err)
                    if progress_callback:
                        progress_callback(completed, total, err)
    else:
        # Tek çekirdek: sıralı çalışma
        for idx, pdf in enumerate(pdfs):
            if ctx:
                ctx.check_cancelled()
            base = os.path.basename(pdf)
            out_path = os.path.join(output_dir, f"compressed_{base}")
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
    
    if mode == "pdf2img":
        files = get_files_in_dir(input_dir, [".pdf"])
        total = len(files)
        for idx, f in enumerate(files):
            if ctx:
                ctx.check_cancelled()
            base = os.path.basename(f)
            name_no_ext = os.path.splitext(base)[0]
            # Create a separate subfolder for each PDF's images
            pdf_out_dir = os.path.join(output_dir, name_no_ext)
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
        files = get_files_in_dir(input_dir, [".png", ".jpg", ".jpeg"])
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
                    base = os.path.basename(img)
                    name_no_ext = os.path.splitext(base)[0]
                    out_pdf = os.path.join(output_dir, f"{name_no_ext}.pdf")
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
                base = os.path.basename(img)
                name_no_ext = os.path.splitext(base)[0]
                out_pdf = os.path.join(output_dir, f"{name_no_ext}.pdf")
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
    pdfs = get_files_in_dir(input_dir, [".pdf"])
    if not pdfs:
        return 0, [_("batch_no_pdf_found")]
        
    os.makedirs(output_dir, exist_ok=True)
    success = 0
    errors = []
    total = len(pdfs)
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
            
            new_name = naming_rule
            new_name = new_name.replace("[ORIJINAL_AD]", name_only)
            new_name = new_name.replace("[SAYFA_SAYISI]", pages + "pp")
            new_name = new_name.replace("[BOYUT]", size_mb)
            new_name = new_name.replace("[SIRA]", seq)
            new_name = new_name.replace("[TARIH]", now_str)
            
            # Sanitize new_name to ensure it's a valid path avoiding illegal chars
            invalid_chars = '<>:"/\\|?*'
            for char in invalid_chars:
                new_name = new_name.replace(char, "_")
            
            out_pdf = os.path.join(output_dir, f"{new_name}.pdf")
            
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
