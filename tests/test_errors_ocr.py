"""Issue #19: raw Python errors on screen, a Cancel button that did nothing,
OCR with no progress and a hardcoded language."""

import pytest

from conftest import make_pdf
from src.core import ocr
from src.core.common import parse_page_numbers, parse_page_order
from src.core.config_manager import cfg
from src.core.errors import friendly_error
from src.core.task_manager import CancelledError, TaskContext


# ── friendly_error (#19.1, #19.6) ─────────────────────────────────────────

def test_file_in_use_is_explained():
    """A PDF open in another program showed a WinError 32 message."""
    exc = OSError(13, "The process cannot access the file")
    exc.winerror = 32
    exc.filename = "C:/x/rapor.pdf"

    message = friendly_error(exc)

    assert "WinError" not in message
    assert "rapor.pdf" in message


def test_permission_error_is_explained():
    exc = PermissionError(13, "Permission denied")
    exc.filename = "C:/Windows/out.pdf"

    message = friendly_error(exc)

    assert "Permission denied" not in message
    assert "out.pdf" in message


def test_disk_full_is_explained():
    import errno
    exc = OSError(errno.ENOSPC, "No space left on device")

    assert "No space left" not in friendly_error(exc)


def test_broken_pdf_is_explained():
    message = friendly_error(Exception("EOF marker not found"))
    assert "EOF marker" not in message


def test_missing_dependency_is_explained():
    message = friendly_error(ImportError("No module named 'reportlab'"))
    assert "reportlab" in message


def test_cancellation_reads_as_cancellation():
    assert "iptal" in friendly_error(CancelledError("x")).lower() or \
           "cancel" in friendly_error(CancelledError("x")).lower()


def test_our_own_messages_pass_through():
    """Messages we wrote for the user are already readable."""
    assert friendly_error(ValueError("Parola boş olamaz.")) == "Parola boş olamaz."


def test_int_conversion_errors_never_show_bare():
    """'invalid literal for int() with base 10' reached the screen."""
    message = friendly_error(ValueError("invalid literal for int() with base 10: 'abc'"))
    assert message != "invalid literal for int() with base 10: 'abc'"


# ── No raw int() errors from the parsers (#19.1) ──────────────────────────

@pytest.mark.parametrize("text", ["abc", "1, abc", "3, 1, 2,", "", " , , "])
def test_page_order_never_leaks_int_errors(text):
    try:
        parse_page_order(text, 3)
    except ValueError as exc:
        assert "invalid literal" not in str(exc)


@pytest.mark.parametrize("text", ["abc", "1-abc", ""])
def test_page_numbers_never_leak_int_errors(text):
    try:
        parse_page_numbers(text, 3)
    except ValueError as exc:
        assert "invalid literal" not in str(exc)


def test_signature_coordinates_never_leak_int_errors():
    from src.core.signature import _to_number
    with pytest.raises(ValueError) as excinfo:
        _to_number("abc", "X")
    assert "invalid literal" not in str(excinfo.value)
    assert "could not convert" not in str(excinfo.value)


# ── Core messages are translated (#19.2) ──────────────────────────────────

@pytest.mark.parametrize("key", [
    "err_start_page_min", "err_end_page_max", "err_start_after_end",
    "err_delete_all_pages", "err_invalid_range", "err_invalid_page",
    "err_need_one_page", "err_pdf_password_protected", "err_tesseract_missing",
])
def test_core_messages_are_translated(key):
    from src.core.lang_manager import _
    cfg.config["language"] = "tr"
    turkish = _(key)
    cfg.config["language"] = "en"
    english = _(key)
    cfg.config["language"] = "tr"
    assert turkish != english, f"{key} is the same in both languages"
    assert english != key, f"{key} has no English text"


def test_split_errors_are_localised(tmp_path):
    from src.core.split import split_pdf
    from src.core.lang_manager import _
    src = make_pdf(tmp_path / "in.pdf", pages=3)

    cfg.config["language"] = "en"
    try:
        with pytest.raises(ValueError) as excinfo:
            split_pdf(src, str(tmp_path / "o.pdf"), 1, 9)
        assert "Baslangic" not in str(excinfo.value)
        assert "end page" in str(excinfo.value).lower()
    finally:
        cfg.config["language"] = "tr"


# ── OCR language (#19.4) ──────────────────────────────────────────────────

def test_ocr_language_prefers_installed_packs(monkeypatch):
    """The language was hardcoded "tur", so OCR failed without that pack."""
    monkeypatch.setattr(ocr, "installed_languages", lambda: ["eng", "osd"])
    assert ocr.resolve_ocr_language(None) == "eng"


def test_ocr_language_combines_what_is_there(monkeypatch):
    monkeypatch.setattr(ocr, "installed_languages", lambda: ["eng", "tur", "osd"])
    assert ocr.resolve_ocr_language(None) == "tur+eng"


def test_ocr_honours_a_requested_language_when_installed(monkeypatch):
    monkeypatch.setattr(ocr, "installed_languages", lambda: ["eng", "tur"])
    assert ocr.resolve_ocr_language("eng") == "eng"


def test_ocr_ignores_a_requested_language_that_is_missing(monkeypatch):
    monkeypatch.setattr(ocr, "installed_languages", lambda: ["eng"])
    assert ocr.resolve_ocr_language("tur") == "eng"


def test_ocr_falls_back_to_any_installed_language(monkeypatch):
    monkeypatch.setattr(ocr, "installed_languages", lambda: ["deu", "osd"])
    assert ocr.resolve_ocr_language(None) == "deu"


def test_ocr_reports_when_no_language_pack_exists(monkeypatch):
    monkeypatch.setattr(ocr, "installed_languages", lambda: ["osd"])
    with pytest.raises(RuntimeError):
        ocr.resolve_ocr_language(None)


# ── OCR progress and cancellation (#19.3, #19.4) ──────────────────────────

def test_ocr_reports_progress_and_can_be_cancelled(tmp_path, monkeypatch):
    """OCR sat at 0% and ignored Cancel, then reported success."""
    src = make_pdf(tmp_path / "in.pdf", pages=4)

    monkeypatch.setattr(ocr, "check_tesseract_availability", lambda: True)
    monkeypatch.setattr(ocr, "resolve_ocr_language", lambda requested=None: "eng")
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", lambda img, lang=None: "text")

    seen = []
    ctx = TaskContext(progress_callback=lambda c, t, m="": seen.append(c))
    pages = ocr.perform_ocr_to_text(src, str(tmp_path / "out.txt"), ctx=ctx)

    assert pages == 4
    assert len(seen) >= 4, "no per-page progress"


def test_ocr_stops_when_cancelled(tmp_path, monkeypatch):
    src = make_pdf(tmp_path / "in.pdf", pages=4)

    monkeypatch.setattr(ocr, "check_tesseract_availability", lambda: True)
    monkeypatch.setattr(ocr, "resolve_ocr_language", lambda requested=None: "eng")
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", lambda img, lang=None: "text")

    ctx = TaskContext()
    ctx.cancel()

    with pytest.raises(CancelledError):
        ocr.perform_ocr_to_text(src, str(tmp_path / "out.txt"), ctx=ctx)


def test_missing_tesseract_gives_a_readable_message(tmp_path, monkeypatch):
    src = make_pdf(tmp_path / "in.pdf")
    monkeypatch.setattr(ocr, "check_tesseract_availability", lambda: False)

    with pytest.raises(EnvironmentError, match="Tesseract"):
        ocr.perform_ocr_to_text(src, str(tmp_path / "out.txt"))


# ── Cancel button only where it works (#19.3) ─────────────────────────────

def test_advanced_tab_only_offers_cancel_for_ocr():
    with open("src/gui/tabs/tab_advanced.py", encoding="utf-8") as f:
        text = f.read()
    assert "cancel_callback=self._cancel_task if cancellable else None" in text


def test_convert_tab_hides_cancel_for_office_conversions():
    with open("src/gui/tabs/tab_convert.py", encoding="utf-8") as f:
        text = f.read()
    assert "cancel_callback=self._cancel_task if cancellable else None" in text


# ── Subprocess windows (#19.5) ────────────────────────────────────────────

def test_tesseract_installer_hides_console_windows():
    with open("src/core/install_tesseract.py", encoding="utf-8") as f:
        text = f.read()
    assert text.count("creationflags=CREATE_NO_WINDOW") >= 2


def test_tesseract_installer_checks_the_exit_code():
    """Only "does the folder exist" was checked before."""
    with open("src/core/install_tesseract.py", encoding="utf-8") as f:
        text = f.read()
    assert "result.returncode" in text
