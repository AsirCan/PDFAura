import os
import shutil
import tempfile

from src.core.lang_manager import _

VALID_QUALITIES = ("screen", "ebook", "printer", "prepress")

# Image resolution and JPEG quality per profile, after Ghostscript's
# distiller presets of the same names: an image is downsampled to `dpi` only
# when it is more than 1.5x sharper than that.
PROFILES = {
    "screen":   {"dpi": 72,  "jpeg_quality": 40},
    "ebook":    {"dpi": 150, "jpeg_quality": 60},
    "printer":  {"dpi": 300, "jpeg_quality": 80},
    "prepress": {"dpi": 300, "jpeg_quality": 90},
}


def compress_pdf(input_pdf, output_pdf, quality, ctx=None):
    """Shrink a PDF with PyMuPDF: downsample and re-encode its images,
    subset its fonts and rewrite it without unused objects.

    This used to run Ghostscript, which every user had to install first.
    PyMuPDF is already a dependency, gave the same or smaller files in
    testing and runs several times faster.

    The result goes to a temporary file in the destination folder that is
    moved into place only on success, so the input survives being picked as
    the output and a failed or cancelled run leaves no half-written file.
    A result larger than the input is not kept: the output is then a copy of
    the input.
    """
    import fitz

    if quality not in VALID_QUALITIES:
        raise ValueError(f"{_('err_select_quality')}{', '.join(VALID_QUALITIES)}")

    input_pdf = os.path.abspath(input_pdf)
    output_pdf = os.path.abspath(output_pdf)
    out_dir = os.path.dirname(output_pdf) or "."
    os.makedirs(out_dir, exist_ok=True)

    def step(pct, message):
        if ctx:
            ctx.check_cancelled()
            ctx.report_progress(pct, 100, message)

    step(0, _("progress_starting"))

    handle, temp_output = tempfile.mkstemp(suffix=".pdf", prefix=".pdfaura-", dir=out_dir)
    os.close(handle)
    try:
        doc = fitz.open(input_pdf)
        try:
            if doc.needs_pass:
                from src.core.common import PdfPasswordError
                raise PdfPasswordError(_("err_pdf_password_protected"))

            step(10, _("progress_percent").format(pct=10))
            doc.rewrite_images(options=_image_options(PROFILES[quality]))

            step(70, _("progress_percent").format(pct=70))
            try:
                doc.subset_fonts()
            except Exception:
                pass   # an odd font only costs some size; keep going

            step(85, _("progress_saving"))
            doc.save(temp_output, garbage=4, deflate=True, deflate_images=True,
                     deflate_fonts=True, use_objstms=1)
        finally:
            doc.close()

        if os.path.getsize(temp_output) >= os.path.getsize(input_pdf):
            shutil.copyfile(input_pdf, temp_output)

        step(95, _("progress_saving"))
        os.replace(temp_output, output_pdf)
    except BaseException:
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except OSError:
                pass
        raise

    if ctx:
        ctx.report_progress(100, 100, _("progress_finished"))


def _image_options(profile):
    """MuPDF image rewriter settings for one profile.

    Bicubic subsampling, not MuPDF's default "average": average only divides
    by whole factors and left a 300 dpi scan at 300 dpi when asked for 150.
    """
    from fitz import mupdf

    dpi = profile["dpi"]
    threshold = int(dpi * 1.5)
    quality = str(profile["jpeg_quality"])
    bicubic = getattr(mupdf, "FZ_SUBSAMPLE_BICUBIC", mupdf.FZ_SUBSAMPLE_AVERAGE)

    options = mupdf.PdfImageRewriterOptions()
    for kind in ("color_lossy", "color_lossless", "gray_lossy", "gray_lossless"):
        setattr(options, f"{kind}_image_recompress_method", mupdf.FZ_RECOMPRESS_JPEG)
        setattr(options, f"{kind}_image_recompress_quality", quality)
        setattr(options, f"{kind}_image_subsample_method", bicubic)
        setattr(options, f"{kind}_image_subsample_threshold", threshold)
        setattr(options, f"{kind}_image_subsample_to", dpi)
    # Black-and-white scans stay lossless (CCITT fax), only fewer pixels.
    options.bitonal_image_recompress_method = mupdf.FZ_RECOMPRESS_FAX
    options.bitonal_image_subsample_method = mupdf.FZ_SUBSAMPLE_AVERAGE
    options.bitonal_image_subsample_threshold = threshold
    options.bitonal_image_subsample_to = dpi
    return options
