import subprocess
from src.utils.ghostscript_helper import find_ghostscript

VALID_QUALITIES = ("screen", "ebook", "printer", "prepress")

def compress_pdf(input_pdf, output_pdf, quality):
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
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        error_message = completed.stderr.strip() or completed.stdout.strip() or "Bilinmeyen Ghostscript hatasi."
        raise RuntimeError(f"Ghostscript hatasi: {error_message}")
