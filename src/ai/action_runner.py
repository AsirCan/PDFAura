import os
import shutil
import tempfile
from pathlib import Path

from src.core.split import split_pdf
from src.core.merge import merge_pdfs
from src.core.lang_manager import _
from src.core.security import add_watermark_to_pdf, encrypt_pdf
from src.core.compress import compress_pdf
from src.core.edit import delete_pages_from_pdf, rotate_pages_in_pdf
from src.core.convert import pdf_to_images, pdf_to_word, pdf_to_txt
from src.core.ocr import perform_ocr_to_text
from src.ai.text_speaker import speak


# Bu işlemler PDF çıktısı değil, farklı format çıktısı üretir
NON_PDF_ACTIONS = {"ocr", "pdf_to_image", "pdf_to_word", "pdf_to_text"}


def execute_intent(intent: dict):
    if not intent:
        speak(_("assist_not_understood"))
        return

    input_file = intent.get("input_file")
    if not input_file:
        speak(_("assist_no_file"))
        return

    # Dosya adını case-insensitive arayalım
    found_path = _find_file(input_file)

    if not found_path:
        speak(_("assist_file_not_found").format(name=input_file))
        return

    # Any further files named in the same command (for merge).
    extra_paths = []
    for name in intent.get("input_files", [])[1:]:
        path = _find_file(name)
        if not path:
            speak(_("assist_file_not_found").format(name=name))
            return
        extra_paths.append(path)

    actions = intent.get("action_chain", [])
    if not actions:
        speak(_("assist_no_action"))
        return

    # Hedef klasör parse edilmediyse mevcut klasöre kaydet
    output_target_dir = intent.get("output_target") or os.path.dirname(found_path)
    if not os.path.exists(output_target_dir):
        os.makedirs(output_target_dir, exist_ok=True)

    base_name = Path(found_path).stem
    final_output_path = os.path.join(output_target_dir, f"{base_name}_aura.pdf")

    current_input = found_path
    temp_files = []

    # Sadece PDF üreten action var mı? (non-pdf hariç)
    has_pdf_actions = any(a["action"] not in NON_PDF_ACTIONS for a in actions)

    try:
        for i, act in enumerate(actions):
            action_type = act.get("action")
            kwargs = act.get("kwargs", {})

            # Özel çıktı formatları (PDF olmayan)
            if action_type in NON_PDF_ACTIONS:
                _run_non_pdf_action(action_type, current_input, output_target_dir, base_name, kwargs)
                continue

            # Son PDF action mı?
            remaining_pdf_actions = [a for a in actions[i+1:] if a["action"] not in NON_PDF_ACTIONS]
            is_last_pdf = len(remaining_pdf_actions) == 0
            current_output = final_output_path if is_last_pdf else _temp_pdf_path(temp_files)

            if action_type == "split":
                split_pdf(current_input, current_output, kwargs.get("start", 1), kwargs.get("end", 1))
            elif action_type == "watermark":
                add_watermark_to_pdf(current_input, current_output, kwargs.get("text", "AURA"))
            elif action_type == "compress":
                compress_pdf(current_input, current_output, kwargs.get("quality", "ebook"))
            elif action_type == "encrypt":
                password = kwargs.get("password")
                if not password:
                    # There is no safe default here: the old code used
                    # "123456" without telling anyone.
                    speak(_("assist_need_password"))
                    return
                encrypt_pdf(current_input, current_output, password)
            elif action_type == "merge":
                extra = extra_paths
                if not extra:
                    speak(_("assist_merge_needs_two"))
                    return
                merge_pdfs([current_input] + extra, current_output)
            elif action_type == "delete_pages":
                delete_pages_from_pdf(current_input, current_output, kwargs.get("pages", []))
            elif action_type == "rotate":
                from src.core.common import open_pdf_reader
                reader = open_pdf_reader(current_input)
                all_pages = list(range(1, len(reader.pages) + 1))
                rotate_pages_in_pdf(current_input, current_output, all_pages, kwargs.get("angle", 90))
            else:
                shutil.copy(current_input, current_output)

            current_input = current_output

        # Sonuç mesajı
        target_str = _get_target_display_name(output_target_dir)
        action_names = [_get_action_name(a["action"]) for a in actions]
        action_summary = ", ".join(action_names)
        msg = _("assist_result").format(actions=action_summary, target=target_str)
        speak(msg)

    except FileNotFoundError as e:
        speak(_("assist_error").format(error=e))
    except ValueError as e:
        speak(_("assist_error").format(error=e))
    except PermissionError:
        speak(_("assist_no_permission"))
    except Exception as e:
        print(f"[Action Runner Error] {e}")
        speak(_("assist_unexpected_error"))
    finally:
        # Geçici dosyaları her durumda temizle (hata olsa bile)
        for tf in temp_files:
            try:
                if os.path.exists(tf):
                    os.remove(tf)
            except Exception:
                pass


def _temp_pdf_path(temp_files):
    """A temp path for an intermediate step. mktemp() was insecure."""
    handle, path = tempfile.mkstemp(suffix=".pdf", prefix="pdfaura-")
    os.close(handle)
    temp_files.append(path)
    return path


def _find_file(input_file: str) -> str:
    """Dosyayı bilinen klasörlerde case-insensitive olarak arar."""
    user_home = os.path.expanduser("~")
    search_dirs = [
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "Documents"),
        os.path.join(user_home, "Downloads"),
    ]

    for d in search_dirs:
        # Direkt isim eşleşmesi
        exact_path = os.path.join(d, input_file)
        if os.path.exists(exact_path):
            return exact_path

        # Case-insensitive arama (Whisper bazen büyük/küçük harf karıştırıyor)
        if os.path.exists(d):
            try:
                for f in os.listdir(d):
                    if f.lower() == input_file.lower():
                        return os.path.join(d, f)
            except PermissionError:
                continue

    return None


def _run_non_pdf_action(action_type, input_path, output_dir, base_name, kwargs):
    """PDF olmayan çıktı üreten işlemleri yönetir."""
    try:
        if action_type == "ocr":
            output_txt = os.path.join(output_dir, f"{base_name}_ocr.txt")
            perform_ocr_to_text(input_path, output_txt)
            speak(_("assist_ocr_done"))

        elif action_type == "pdf_to_image":
            img_folder = os.path.join(output_dir, f"{base_name}_resimler")
            fmt = kwargs.get("format", "png")
            count = pdf_to_images(input_path, img_folder, dpi=300, img_format=fmt)
            speak(_("assist_images_done").format(count=count, fmt=fmt.upper()))

        elif action_type == "pdf_to_word":
            output_docx = os.path.join(output_dir, f"{base_name}.docx")
            pdf_to_word(input_path, output_docx)
            speak(_("assist_word_done"))

        elif action_type == "pdf_to_text":
            output_txt = os.path.join(output_dir, f"{base_name}.txt")
            pdf_to_txt(input_path, output_txt)
            speak(_("assist_text_done"))

    except Exception as e:
        print(f"[Non-PDF Action Error] {e}")
        speak(_("assist_error").format(error=e))


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
    return _(f"assist_act_{action}")
