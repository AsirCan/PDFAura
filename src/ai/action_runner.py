import logging
import os
import shutil
import tempfile
import re
from pathlib import Path

from src.core.split import split_pdf
from src.core.merge import merge_pdfs
from src.core.lang_manager import _
from src.core.security import add_watermark_to_pdf, decrypt_pdf, encrypt_pdf
from src.core.compress import compress_pdf
from src.core.errors import friendly_error
from src.core.edit import delete_pages_from_pdf, rotate_pages_in_pdf
from src.core.convert import page_image_path, pdf_to_images, pdf_to_word, pdf_to_txt
from src.core.ocr import perform_ocr_to_text
from src.core.output_paths import unique_path
from src.core.task_manager import CancelledError, TaskContext
from src.ai.text_speaker import speak


# Bu işlemler PDF çıktısı değil, farklı format çıktısı üretir
NON_PDF_ACTIONS = {"ocr", "pdf_to_image", "pdf_to_word", "pdf_to_text"}


class _RunnerContext(TaskContext):
    """TaskContext with the caller's own cancel check and 2/3-arg progress.

    The core tools already take a TaskContext for per-page progress; wrapping
    the caller's callback here keeps that reuse and still lets a UI cancel
    between, and during, steps.
    """

    def __init__(self, progress_callback=None, cancel_check=None):
        super().__init__(progress_callback)
        self._external_cancel = cancel_check

    def check_cancelled(self):
        cancel = self._external_cancel
        if cancel is not None:
            checker = getattr(cancel, "check_cancelled", None)
            if callable(checker):
                checker()
            elif callable(cancel):
                if cancel():
                    raise CancelledError(_("perf_cancelled_msg"))
            elif getattr(cancel, "is_cancelled", False):
                raise CancelledError(_("perf_cancelled_msg"))
        super().check_cancelled()

    def notify(self, current, total, message=""):
        callback = self._progress_callback
        if callback is None:
            return
        try:
            callback(current, total, message)
        except TypeError:
            try:
                callback(current, total)
            except TypeError:
                pass


def _ordered_actions(actions):
    """Decrypt first and encrypt last; every step in between stays in order.

    An encrypted PDF cannot be read by the next step, and encrypting before
    a watermark or a page delete would make that step fail.
    """
    decrypts = [a for a in actions if a.get("action") == "decrypt"]
    middle = [a for a in actions if a.get("action") not in ("decrypt", "encrypt")]
    encrypts = [a for a in actions if a.get("action") == "encrypt"]
    return decrypts + middle + encrypts


def execute_intent(intent: dict, progress_callback=None, cancel_check=None):
    """Carry out *intent* through the core tools.

    *progress_callback* receives ``(current, total, message)`` and
    *cancel_check* is a callable (or TaskContext-like object) that stops the
    chain when it says so. Returns a small result dict; the spoken reply is
    unchanged for existing callers.
    """
    result = {"ok": False, "saved": [], "output_dir": "", "error": "",
              "cancelled": False}
    ctx = _RunnerContext(progress_callback, cancel_check) \
        if (progress_callback or cancel_check) else None

    temp_files = []
    try:
        if not intent:
            message = _("assist_not_understood")
            speak(message)
            result["error"] = message
            return result

        input_file = intent.get("input_file")
        if not input_file:
            message = _("assist_no_file")
            speak(message)
            result["error"] = message
            return result

        if "\x00" in str(input_file):
            message = _("assist_file_not_found").format(name=str(input_file).replace("\x00", ""))
            speak(message)
            result["error"] = message
            return result

        # Dosya adını case-insensitive arayalım
        found_path = _find_file(input_file)

        if not found_path:
            message = _("assist_file_not_found").format(name=input_file)
            speak(message)
            result["error"] = message
            return result

        # Any further files named in the same command (for merge).
        extra_paths = []
        for name in intent.get("input_files", [])[1:]:
            if "\x00" in str(name):
                message = _("assist_file_not_found").format(name=str(name).replace("\x00", ""))
                speak(message)
                result["error"] = message
                return result
            path = _find_file(name)
            if not path:
                message = _("assist_file_not_found").format(name=name)
                speak(message)
                result["error"] = message
                return result
            extra_paths.append(path)

        actions = _ordered_actions(intent.get("action_chain", []))
        if not actions:
            message = _("assist_no_action")
            speak(message)
            result["error"] = message
            return result

        # Hedef klasör parse edilmediyse mevcut klasöre kaydet
        raw_target_dir = intent.get("output_target") or os.path.dirname(found_path)
        if "\x00" in str(raw_target_dir):
            raw_target_dir = os.path.dirname(found_path)
        output_target_dir = os.path.abspath(str(raw_target_dir))
        base_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', Path(found_path).stem).strip(" .-_") or "belge"
        total_steps = len(actions)

        current_input = found_path
        password_used = None
        saved = []          # names of the files written, for the reply

        os.makedirs(output_target_dir, exist_ok=True)
        # Never over a file that is already there: "rapor.pdf'yi word'e çevir"
        # replaced the user's own rapor.docx with pdf2docx's lossy copy (#30).
        final_output_path = unique_path(
            os.path.join(output_target_dir, f"{base_name}_aura.pdf"))

        for i, act in enumerate(actions, 1):
            action_type = act.get("action")
            kwargs = act.get("kwargs", {})

            if ctx:
                ctx.report_progress(i - 1, total_steps,
                                    f"{i}/{total_steps} · {_get_action_name(action_type)}")

            # Özel çıktı formatları (PDF olmayan)
            if action_type in NON_PDF_ACTIONS:
                written = _run_non_pdf_action(action_type, current_input, output_target_dir,
                                              base_name, kwargs, ctx)
                if written:
                    saved.append(os.path.basename(written))
                continue

            # Son PDF action mı?
            remaining_pdf_actions = [a for a in actions[i:]
                                     if a.get("action") not in NON_PDF_ACTIONS]
            is_last_pdf = len(remaining_pdf_actions) == 0
            current_output = final_output_path if is_last_pdf else _temp_pdf_path(temp_files)

            if action_type == "split":
                start, end = _split_range(current_input, kwargs)
                split_pdf(current_input, current_output, start, end, ctx=ctx)
            elif action_type == "watermark":
                add_watermark_to_pdf(current_input, current_output,
                                     kwargs.get("text", "AURA"), ctx=ctx)
            elif action_type == "compress":
                compress_pdf(current_input, current_output,
                             kwargs.get("quality", "ebook"), ctx=ctx)
            elif action_type == "decrypt":
                password = kwargs.get("password")
                if not password:
                    message = _("assist_need_decrypt_password")
                    speak(message)
                    result["error"] = message
                    return result
                decrypt_pdf(current_input, current_output, password, ctx=ctx)
            elif action_type == "encrypt":
                password = kwargs.get("password")
                if not password:
                    # There is no safe default here: the old code used
                    # "123456" without telling anyone.
                    message = _("assist_need_password")
                    speak(message)
                    result["error"] = message
                    return result
                encrypt_pdf(current_input, current_output, password, ctx=ctx)
                password_used = password
            elif action_type == "merge":
                extra = extra_paths
                if not extra:
                    message = _("assist_merge_needs_two")
                    speak(message)
                    result["error"] = message
                    return result
                merge_pdfs([current_input] + extra, current_output, ctx=ctx)
            elif action_type == "delete_pages":
                delete_pages_from_pdf(current_input, current_output,
                                      _delete_pages(current_input, kwargs), ctx=ctx)
            elif action_type == "rotate":
                from src.core.common import open_pdf_reader
                reader = open_pdf_reader(current_input)
                try:
                    all_pages = list(range(1, len(reader.pages) + 1))
                finally:
                    if hasattr(reader, "close"):
                        reader.close()
                pages = kwargs.get("pages") or all_pages
                rotate_pages_in_pdf(current_input, current_output, pages,
                                    kwargs.get("angle", 90), ctx=ctx)
            else:
                raise ValueError(_("err_unknown_op") + str(action_type))

            current_input = current_output
            if is_last_pdf:
                saved.append(os.path.basename(final_output_path))

        # Sonuç mesajı
        target_str = _get_target_display_name(output_target_dir)
        action_names = [_get_action_name(a["action"]) for a in actions]
        action_summary = ", ".join(action_names)
        msg = _("assist_result").format(actions=action_summary, target=target_str)
        if saved:
            msg += " " + _("assist_saved_as").format(name=", ".join(saved))
        if password_used:
            # The password was read out of a sentence; say which one locks
            # the file, or a misheard one could never be opened again.
            msg += " " + _("assist_password_used").format(password=password_used)
        speak(msg)
        result.update(ok=True, saved=saved, output_dir=output_target_dir)

    except CancelledError as e:
        message = str(e) or _("perf_cancelled_msg")
        speak(message)
        result.update(error=message, cancelled=True)
    except PermissionError:
        message = _("assist_no_permission")
        speak(message)
        result["error"] = message
    except Exception as e:
        # Any failed step ends the command here, so the "done" message above
        # is only ever said when every step worked (#33).
        logging.getLogger(__name__).exception("Assistant command failed")
        message = _("assist_error").format(error=friendly_error(e))
        speak(message)
        result["error"] = message
    finally:
        # Geçici dosyaları her durumda temizle (hata olsa bile)
        for tf in temp_files:
            try:
                if os.path.exists(tf):
                    os.remove(tf)
            except Exception:
                pass

    return result


def _split_range(path, kwargs):
    """The (start, end) pages of a split. "son 3 sayfa" arrives as
    {"last": 3}; only start and end were read, so it took page 1 alone."""
    if "last" not in kwargs:
        return kwargs.get("start", 1), kwargs.get("end", 1)
    from src.core.common import get_pdf_page_count
    total = get_pdf_page_count(path)
    count = kwargs["last"]
    if count < 1 or count > total:
        raise ValueError(_("assist_last_pages_too_many").format(count=count, total=total))
    return total - count + 1, total


def _delete_pages(path, kwargs):
    """The list of 1-indexed page numbers to delete."""
    if "last" in kwargs:
        from src.core.common import get_pdf_page_count
        total = get_pdf_page_count(path)
        count = kwargs["last"]
        if count < 1 or count > total:
            raise ValueError(_("assist_last_pages_too_many").format(count=count, total=total))
        return list(range(total - count + 1, total + 1))
    return kwargs.get("pages", [])


def _temp_pdf_path(temp_files):
    """A temp path for an intermediate step. mktemp() was insecure."""
    handle, path = tempfile.mkstemp(suffix=".pdf", prefix="pdfaura-")
    os.close(handle)
    temp_files.append(path)
    return path


def _find_file(input_file: str) -> str:
    """Dosyayı bilinen klasörlerde case-insensitive olarak arar."""
    if not input_file or "\x00" in str(input_file):
        return None
    try:
        if os.path.exists(input_file):
            return os.path.abspath(input_file)
    except (ValueError, OSError):
        return None
    user_home = os.path.expanduser("~")
    search_dirs = [
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "Documents"),
        os.path.join(user_home, "Downloads"),
    ]

    try:
        search_name = os.path.basename(str(input_file).strip().replace("\\", "/"))
    except Exception:
        return None
    if not search_name or "\x00" in search_name:
        return None
    for d in search_dirs:
        # Direkt isim eşleşmesi
        try:
            exact_path = os.path.join(d, search_name)
            if os.path.exists(exact_path):
                return exact_path

            # Case-insensitive arama (Whisper bazen büyük/küçük harf karıştırıyor)
            if os.path.exists(d):
                for f in os.listdir(d):
                    if f.lower() == search_name.lower():
                        return os.path.join(d, f)
        except (PermissionError, ValueError, OSError):
            continue

    return None


def _run_non_pdf_action(action_type, input_path, output_dir, base_name, kwargs, ctx=None):
    """PDF olmayan çıktı üreten işlemleri yönetir.

    Returns the file or folder written. Each gets a name nothing has yet
    (rapor (2).docx), so the user's own files are never replaced. A failure
    is raised to execute_intent, which says so and stops: catching it here
    let the command carry on to its "done" message.
    """
    if action_type == "ocr":
        output_txt = unique_path(os.path.join(output_dir, f"{base_name}_ocr.txt"))
        try:
            perform_ocr_to_text(input_path, output_txt, ctx=ctx)
        except TypeError:
            perform_ocr_to_text(input_path, output_txt)
        speak(_("assist_ocr_done"))
        return output_txt

    if action_type == "pdf_to_image":
        img_folder = unique_path(os.path.join(output_dir, f"{base_name}_resimler"))
        fmt = kwargs.get("format", "png")
        try:
            count = pdf_to_images(input_path, img_folder, dpi=300, img_format=fmt, ctx=ctx)
        except TypeError:
            count = pdf_to_images(input_path, img_folder, dpi=300, img_format=fmt)
        speak(_("assist_images_done").format(count=count, fmt=fmt.upper()))
        return img_folder

    if action_type == "pdf_to_word":
        output_docx = unique_path(os.path.join(output_dir, f"{base_name}.docx"))
        try:
            pdf_to_word(input_path, output_docx, ctx=ctx)
        except TypeError:
            pdf_to_word(input_path, output_docx)
        speak(_("assist_word_done"))
        return output_docx

    if action_type == "pdf_to_text":
        output_txt = unique_path(os.path.join(output_dir, f"{base_name}.txt"))
        try:
            pdf_to_txt(input_path, output_txt, ctx=ctx)
        except TypeError:
            pdf_to_txt(input_path, output_txt)
        speak(_("assist_text_done"))
        return output_txt

    return None


def _get_target_display_name(output_target_dir: str) -> str:
    """Name the destination folder in the UI's language."""
    folder = os.path.basename(output_target_dir).lower()
    if folder in ("desktop", "masaüstü"):
        return _("assist_target_desktop")
    if folder in ("documents", "belgeler"):
        return _("assist_target_documents")
    if folder in ("downloads", "indirilenler"):
        return _("assist_target_downloads")
    return _("assist_target_same")


def _get_action_name(action: str) -> str:
    """Name an operation in the UI's language."""
    if action == "merge":
        return _("assist_merge_name")
    if action == "decrypt":
        val = _("assist_act_decrypt")
        return val if val != "assist_act_decrypt" else ("Şifre çözme" if _("assist_act_split") == "Kesme" else "Decrypt")
    return _(f"assist_act_{action}")
