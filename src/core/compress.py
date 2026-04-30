import subprocess
import os
import time
import threading
from src.utils.ghostscript_helper import find_ghostscript

VALID_QUALITIES = ("screen", "ebook", "printer", "prepress")

def compress_pdf(input_pdf, output_pdf, quality, ctx=None):
    """Run Ghostscript to compress the PDF."""
    gs_path = find_ghostscript()
    if not gs_path:
        raise FileNotFoundError(
            "Ghostscript bulunamadi. 64-bit surumu kurun ve "
            "'gswin64c' PATH'te erisilebilir olsun."
        )
    command = [
        gs_path, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS=/{quality}", "-dNOPAUSE", "-dQUIET", "-dBATCH",
        f"-sOutputFile={output_pdf}", input_pdf,
    ]

    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, 100, "Sıkıştırma başlatılıyor...")

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Ghostscript subprocess ile ilerleme takibi
    if ctx:
        input_size = os.path.getsize(input_pdf)
        _monitor_subprocess_progress(process, output_pdf, input_size, ctx)
    else:
        process.wait()

    if process.returncode != 0:
        _, stderr = process.communicate()
        error_message = stderr.decode().strip() if stderr else "Bilinmeyen Ghostscript hatasi."
        raise RuntimeError(f"Ghostscript hatasi: {error_message}")

    if ctx:
        ctx.report_progress(100, 100, "Sıkıştırma tamamlandı.")


def _monitor_subprocess_progress(process, output_path, input_size, ctx):
    """Ghostscript subprocess'in ilerlemesini output dosyası boyutuna göre takip eder."""
    estimated_ratio = 0.6  # Sıkıştırma tahmini oran
    target_size = input_size * estimated_ratio

    while process.poll() is None:
        if ctx.is_cancelled:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
            # Yarım kalan output dosyasını temizle
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except OSError:
                    pass
            from src.core.task_manager import CancelledError
            raise CancelledError("İşlem kullanıcı tarafından iptal edildi.")

        try:
            if os.path.exists(output_path):
                current_size = os.path.getsize(output_path)
                progress = min(int((current_size / max(target_size, 1)) * 90), 90)
                ctx.report_progress(progress, 100, f"İşleniyor... ({progress}%)")
        except OSError:
            pass

        time.sleep(0.3)
