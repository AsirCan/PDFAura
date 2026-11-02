"""PDF Aura's command line interface.

Every subcommand runs the same src.core function the window uses, so scripts
and automation get exactly the behaviour of the app without opening it:

    python -m src.cli compress input.pdf -q ebook
    python -m src.cli split input.pdf --pages 1-100 -o ilk.pdf
    python -m src.cli merge a.pdf b.pdf -o birlesik.pdf

Output paths default to the same "<input><suffix>" names the UI suggests, and
any failure prints one readable line and exits non-zero.
"""
import argparse
import getpass
import os
import re
import sys

from src.core.compress import VALID_QUALITIES, compress_pdf
from src.core.convert import pdf_to_images
from src.core.edit import rotate_pages_in_pdf
from src.core.errors import friendly_error
from src.core.merge import merge_pdfs
from src.core.output_paths import suggest_output
from src.core.security import add_watermark_to_pdf, decrypt_pdf, encrypt_pdf
from src.core.split import split_pdf

EXAMPLES = """examples:
  python -m src.cli compress input.pdf -q ebook
  python -m src.cli split input.pdf --pages 1-100 -o first.pdf
  python -m src.cli merge a.pdf b.pdf -o merged.pdf
  python -m src.cli to-images input.pdf -o pages --dpi 150"""

_PAGE_RANGE = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+)\s*)?$")


def _require_input(path):
    """Reject a missing or non-file input with a message naming the path."""
    if "\x00" in str(path):
        raise ValueError(f"Path contains invalid null character: {path}")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Input file not found: {path}")
    return path


def _default_output(input_path, kind, ext=None):
    """The app's suggested output name, e.g. 'report_compressed.pdf'."""
    return suggest_output(input_path, kind, ext=ext)


def _parse_page_range(text):
    """'1-100' or '5' -> (1, 100) or (5, 5), 1-indexed."""
    match = _PAGE_RANGE.match(text)
    if not match:
        raise ValueError(f"Invalid page range '{text}'. Use START-END, e.g. 1-100.")
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if start < 1 or end < start:
        raise ValueError(f"Invalid page range '{text}': pages start at 1 and END must not be smaller than START.")
    return start, end


def _positive_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a whole number, got '{text}'")
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or greater")
    return value


def _opacity(text):
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a number, got '{text}'")
    if not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return value


def _cmd_compress(args, parser):
    _require_input(args.input)
    output = args.output or _default_output(args.input, "compressed")
    compress_pdf(args.input, output, args.quality)
    print(f"Wrote {os.path.abspath(output)}")
    return 0


def _cmd_split(args, parser):
    _require_input(args.input)
    start, end = _parse_page_range(args.pages)
    output = args.output or _default_output(args.input, "split")
    split_pdf(args.input, output, start, end)
    print(f"Wrote {os.path.abspath(output)}")
    return 0


def _cmd_merge(args, parser):
    if len(args.inputs) < 2:
        parser.error("merge needs at least two PDF files")
    for path in args.inputs:
        _require_input(path)
    output = args.output or _default_output(args.inputs[0], "merged")
    merge_pdfs(args.inputs, output)
    print(f"Merged {len(args.inputs)} files into {os.path.abspath(output)}")
    return 0


def _cmd_rotate(args, parser):
    from src.core.common import get_pdf_page_count, parse_page_numbers

    _require_input(args.input)
    if args.pages:
        pages = parse_page_numbers(args.pages, get_pdf_page_count(args.input))
    else:
        pages = list(range(1, get_pdf_page_count(args.input) + 1))
    output = args.output or _default_output(args.input, "edited")
    rotate_pages_in_pdf(args.input, output, pages, args.angle)
    print(f"Rotated {len(pages)} page(s) by {args.angle} degrees into {os.path.abspath(output)}")
    return 0


def _password(args, confirm=False):
    """The password from --password, or a hidden prompt on a terminal."""
    password = args.password
    if password is None:
        if not sys.stdin.isatty():
            raise ValueError("A password is required (use --password).")
        password = getpass.getpass("Password: ")
        if confirm and password != getpass.getpass("Confirm password: "):
            raise ValueError("Passwords do not match.")
    return password


def _cmd_encrypt(args, parser):
    _require_input(args.input)
    output = args.output or _default_output(args.input, "encrypted")
    encrypt_pdf(args.input, output, _password(args, confirm=True))
    print(f"Wrote {os.path.abspath(output)}")
    return 0


def _cmd_decrypt(args, parser):
    _require_input(args.input)
    output = args.output or _default_output(args.input, "decrypted")
    decrypt_pdf(args.input, output, _password(args))
    print(f"Wrote {os.path.abspath(output)}")
    return 0


def _cmd_watermark(args, parser):
    _require_input(args.input)
    if not args.text.strip():
        raise ValueError("Watermark text cannot be empty.")
    output = args.output or _default_output(args.input, "watermarked")
    add_watermark_to_pdf(args.input, output, args.text,
                         opacity=args.opacity, angle=args.angle,
                         font_size=args.font_size)
    print(f"Wrote {os.path.abspath(output)}")
    return 0


def _cmd_to_images(args, parser):
    _require_input(args.input)
    folder = args.output or _default_output(args.input, "images", ext="")
    written = pdf_to_images(args.input, folder, dpi=args.dpi, img_format=args.format)
    print(f"Wrote {written} image(s) to {os.path.abspath(folder)}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="pdfaura",
        description="PDF Aura command line tools.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = subparsers.add_parser("compress", help="shrink a PDF")
    p.add_argument("input", help="input PDF")
    p.add_argument("-q", "--quality", choices=VALID_QUALITIES, default="ebook",
                   help="compression profile (default: ebook)")
    p.add_argument("-o", "--output", help="output PDF")
    p.set_defaults(func=_cmd_compress)

    p = subparsers.add_parser("split", help="extract a page range")
    p.add_argument("input", help="input PDF")
    p.add_argument("--pages", required=True, metavar="START-END",
                   help="pages to keep, 1-indexed, e.g. 1-100")
    p.add_argument("-o", "--output", help="output PDF")
    p.set_defaults(func=_cmd_split)

    p = subparsers.add_parser("merge", help="join PDFs in the given order")
    p.add_argument("inputs", nargs="+", metavar="PDF", help="PDFs to merge")
    p.add_argument("-o", "--output", help="output PDF")
    p.set_defaults(func=_cmd_merge)

    p = subparsers.add_parser("rotate", help="rotate pages")
    p.add_argument("input", help="input PDF")
    p.add_argument("--pages", metavar="PAGES",
                   help="pages to rotate, e.g. 1,3-5 (default: all pages)")
    p.add_argument("--angle", type=int, choices=(90, 180, 270), default=90,
                   help="rotation in degrees (default: 90)")
    p.add_argument("-o", "--output", help="output PDF")
    p.set_defaults(func=_cmd_rotate)

    p = subparsers.add_parser("encrypt", help="password-protect a PDF (AES-256)")
    p.add_argument("input", help="input PDF")
    p.add_argument("-p", "--password", help="password (prompted for when omitted)")
    p.add_argument("-o", "--output", help="output PDF")
    p.set_defaults(func=_cmd_encrypt)

    p = subparsers.add_parser("decrypt", help="remove a PDF's password")
    p.add_argument("input", help="input PDF")
    p.add_argument("-p", "--password", help="password (prompted for when omitted)")
    p.add_argument("-o", "--output", help="output PDF")
    p.set_defaults(func=_cmd_decrypt)

    p = subparsers.add_parser("watermark", help="stamp text on every page")
    p.add_argument("input", help="input PDF")
    p.add_argument("-t", "--text", required=True, help="watermark text")
    p.add_argument("--opacity", type=_opacity, default=0.3,
                   help="text opacity, 0-1 (default: 0.3)")
    p.add_argument("--angle", type=int, default=45,
                   help="text angle in degrees (default: 45)")
    p.add_argument("--font-size", type=float, default=60,
                   help="font size in points (default: 60)")
    p.add_argument("-o", "--output", help="output PDF")
    p.set_defaults(func=_cmd_watermark)

    p = subparsers.add_parser("to-images", help="render each page as an image")
    p.add_argument("input", help="input PDF")
    p.add_argument("-o", "--output", metavar="FOLDER",
                   help="output folder (default: <input>_images)")
    p.add_argument("--dpi", type=_positive_int, default=300,
                   help="render resolution (default: 300)")
    p.add_argument("--format", choices=("png", "jpg"), default="png",
                   help="image format (default: png)")
    p.set_defaults(func=_cmd_to_images)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args, parser) or 0
    except KeyboardInterrupt:
        print(f"{parser.prog}: cancelled", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"{parser.prog}: error: {friendly_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
