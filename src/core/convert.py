import os
import subprocess
import time
from src.utils.ghostscript_helper import find_ghostscript

def pdf_to_images(input_pdf, output_folder, dpi=300, img_format="png", ctx=None):
    """Convert PDF pages to images using Ghostscript. Returns number of created files."""
    gs_path = find_ghostscript()
    if not gs_path:
        raise FileNotFoundError("Ghostscript bulunamadi.")
    os.makedirs(output_folder, exist_ok=True)
    device = "png16m" if img_format.lower() == "png" else "jpeg"
    ext = "png" if img_format.lower() == "png" else "jpg"
    output_pattern = os.path.join(output_folder, f"sayfa_%03d.{ext}")
    command = [
        gs_path, f"-sDEVICE={device}", f"-r{dpi}",
        "-dNOPAUSE", "-dQUIET", "-dBATCH",
        f"-sOutputFile={output_pattern}", input_pdf,
    ]
    if device == "jpeg":
        command.insert(-1, "-dJPEGQ=95")
    
    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, 100, "PDF resme dönüştürülüyor...")
    
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    if ctx:
        # Çıktı klasöründeki dosya sayısını izleyerek ilerleme takibi
        while process.poll() is None:
            if ctx.is_cancelled:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                from src.core.task_manager import CancelledError
                raise CancelledError("İşlem kullanıcı tarafından iptal edildi.")
            
            try:
                files = [f for f in os.listdir(output_folder) if f.startswith("sayfa_") and f.endswith(f".{ext}")]
                count = len(files)
                if count > 0:
                    ctx.report_progress(count, max(count + 1, 10), f"{count} sayfa dönüştürüldü...")
            except OSError:
                pass
            time.sleep(0.3)
    else:
        process.wait()
    
    if process.returncode != 0:
        _, stderr = process.communicate()
        raise RuntimeError(f"Ghostscript hatasi: {stderr.decode().strip() if stderr else 'Bilinmeyen hata'}")
    
    files = [f for f in os.listdir(output_folder) if f.startswith("sayfa_") and f.endswith(f".{ext}")]
    
    if ctx:
        ctx.report_progress(len(files), len(files), f"{len(files)} sayfa dönüştürüldü.")
    
    return len(files)

def images_to_pdf(image_paths, output_pdf, page_size="Orijinal", ctx=None):
    """Convert images to PDF using Pillow."""
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("Pillow kutuphanesi bulunamadi.\nLutfen kurun: pip install Pillow")
    if not image_paths:
        raise ValueError("En az bir resim secilmeli.")
    PAGE_SIZES = {"A4": (595, 842), "Letter": (612, 792)}
    pdf_images = []
    total = len(image_paths)
    
    for idx, img_path in enumerate(image_paths):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(idx + 1, total, f"Resim {idx + 1}/{total} işleniyor...")
        
        img = Image.open(img_path)
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
        if page_size in PAGE_SIZES:
            target_w, target_h = PAGE_SIZES[page_size]
            img_w, img_h = img.size
            ratio = min(target_w / img_w, target_h / img_h)
            new_w, new_h = int(img_w * ratio), int(img_h * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
        pdf_images.append(img)
    
    pdf_images[0].save(output_pdf, "PDF", save_all=True, append_images=pdf_images[1:], resolution=100.0)
    
    if ctx:
        ctx.report_progress(total, total, "PDF oluşturuldu.")

def pdf_to_word(input_pdf, output_docx, ctx=None):
    """Convert PDF to Word using pdf2docx."""
    try:
        from pdf2docx import Converter
    except ImportError:
        raise ImportError("pdf2docx kutuphanesi bulunamadi.\nLutfen kurun: pip install pdf2docx")
    
    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, 100, "PDF Word'e dönüştürülüyor...")
    
    cv = Converter(input_pdf)
    cv.convert(output_docx, start=0, end=None)
    cv.close()
    
    if ctx:
        ctx.report_progress(100, 100, "Dönüştürme tamamlandı.")

def word_to_pdf(input_docx, output_pdf, ctx=None):
    """Convert Word to PDF using docx2pdf (requires Microsoft Word)."""
    try:
        from docx2pdf import convert
    except ImportError:
        raise ImportError(
            "docx2pdf kutuphanesi bulunamadi.\n"
            "Lutfen kurun: pip install docx2pdf\n"
            "Not: Bu ozellik Microsoft Word gerektirir."
        )
    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, 100, "Word PDF'e dönüştürülüyor...")
    
    convert(input_docx, output_pdf)
    
    if ctx:
        ctx.report_progress(100, 100, "Dönüştürme tamamlandı.")

def ppt_to_pdf(input_ppt, output_pdf, ctx=None):
    """Convert PowerPoint to PDF using pywin32 (requires Microsoft PowerPoint)."""
    try:
        import win32com.client
    except ImportError:
        raise ImportError(
            "pywin32 kutuphanesi bulunamadi.\n"
            "Lutfen kurun: pip install pywin32\n"
            "Not: Bu ozellik Microsoft PowerPoint gerektirir."
        )
    import os
    
    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, 100, "PowerPoint PDF'e dönüştürülüyor...")
    
    powerpoint = win32com.client.Dispatch("Powerpoint.Application")
    # Abs paths are specifically required for pywin32 Office interop
    input_ppt_abs = os.path.abspath(input_ppt)
    output_pdf_abs = os.path.abspath(output_pdf)
    try:
        deck = powerpoint.Presentations.Open(input_ppt_abs, WithWindow=False)
        deck.SaveAs(output_pdf_abs, 32) # ppSaveAsPDF = 32
        deck.Close()
    finally:
        powerpoint.Quit()
    
    if ctx:
        ctx.report_progress(100, 100, "Dönüştürme tamamlandı.")

def excel_to_pdf(input_excel, output_pdf, ctx=None):
    """Convert Excel to PDF using pywin32 (requires Microsoft Excel)."""
    try:
        import win32com.client
    except ImportError:
        raise ImportError(
            "pywin32 kutuphanesi bulunamadi.\n"
            "Lutfen kurun: pip install pywin32\n"
            "Not: Bu ozellik Microsoft Excel gerektirir."
        )
    import os
    
    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, 100, "Excel PDF'e dönüştürülüyor...")
    
    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    excel.Interactive = False
    input_excel_abs = os.path.abspath(input_excel)
    output_pdf_abs = os.path.abspath(output_pdf)
    wb = None
    try:
        wb = excel.Workbooks.Open(input_excel_abs)
        # xlTypePDF = 0
        wb.ExportAsFixedFormat(0, output_pdf_abs)
    finally:
        if wb:
            wb.Close(False)
        excel.Quit()
    
    if ctx:
        ctx.report_progress(100, 100, "Dönüştürme tamamlandı.")

def pdf_to_txt(input_pdf, output_txt, ctx=None):
    """Convert PDF to Text natively using PyPDF2."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        raise ImportError("PyPDF2 kutuphanesi bulunamadi.")
    
    reader = PdfReader(input_pdf)
    text = []
    total = len(reader.pages)
    
    for i, page in enumerate(reader.pages, 1):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(i, total, f"Sayfa {i}/{total} okunuyor...")
        page_text = page.extract_text()
        if page_text:
            text.append(page_text)
            
    with open(output_txt, "w", encoding="utf-8") as f:
        f.write("\n\n--- Sayfa Sonu ---\n\n".join(text))
    
    if ctx:
        ctx.report_progress(total, total, "Metin çıkarma tamamlandı.")
