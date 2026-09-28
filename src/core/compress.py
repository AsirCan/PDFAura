import os
import tempfile

from src.core.lang_manager import _
from src.utils.ghostscript_helper import escape_gs_path, run_ghostscript

VALID_QUALITIES = ("screen", "ebook", "printer", "prepress")


def compress_pdf(input_pdf, output_pdf, quality, ctx=None):
    """Run Ghostscript to compress the PDF.

    Ghostscript writes to a temporary file in the destination folder that is
    moved into place only on success, so the input survives being picked as
    the output and a cancelled run leaves no half-written file behind.
    """
    if quality not in VALID_QUALITIES:
        raise ValueError(f"{_('err_select_quality')}{', '.join(VALID_QUALITIES)}")

    input_pdf = os.path.abspath(input_pdf)
    output_pdf = os.path.abspath(output_pdf)

    out_dir = os.path.dirname(output_pdf) or "."
    os.makedirs(out_dir, exist_ok=True)

    handle, temp_output = tempfile.mkstemp(suffix=".pdf", prefix=".pdfaura-", dir=out_dir)
    os.close(handle)

    command = [
        "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS=/{quality}", "-dNOPAUSE", "-dQUIET", "-dBATCH",
        f"-sOutputFile={escape_gs_path(temp_output)}", input_pdf,
    ]

    if ctx:
        ctx.check_cancelled()
        ctx.report_progress(0, 100, "Sıkıştırma başlatılıyor...")

    try:
        on_tick = _progress_ticker(temp_output, input_pdf, ctx) if ctx else None
        run_ghostscript(command, ctx=ctx, on_tick=on_tick)
        os.replace(temp_output, output_pdf)
    except BaseException:
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except OSError:
                pass
        raise

    if ctx:
        ctx.report_progress(100, 100, "Sıkıştırma tamamlandı.")


def _progress_ticker(temp_output, input_pdf, ctx):
    """Estimate progress from how large the output has grown so far."""
    try:
        input_size = os.path.getsize(input_pdf)
    except OSError:
        input_size = 0
    target_size = max(input_size * 0.6, 1)  # rough expected compression ratio

    def tick():
        try:
            current_size = os.path.getsize(temp_output)
        except OSError:
            return
        progress = min(int((current_size / target_size) * 90), 90)
        ctx.report_progress(progress, 100, f"İşleniyor... ({progress}%)")

    return tick
