import os
import shutil
import tempfile
from pathlib import Path

from src.core.split import split_pdf
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
        speak("Anlayamadım, lütfen tekrar söyleyin.")
        return

    input_file = intent.get("input_file")
    if not input_file:
        speak("Hangi dosya üzerinde işlem yapmak istediğinizi anlayamadım. Lütfen dosya adını belirtin.")
        return

    # Dosya adını case-insensitive arayalım
    found_path = _find_file(input_file)

    if not found_path:
        speak(f"Belirttiğiniz {input_file} dosyasını masaüstünde, belgelerimde veya indirilenler klasöründe bulamadım.")
        return

    actions = intent.get("action_chain", [])
    if not actions:
        speak("Dosyaya ne yapmam gerektiğini tam olarak anlayamadım. Örneğin sıkıştır, kes veya filigran ekle diyebilirsiniz.")
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
            current_output = final_output_path if is_last_pdf else tempfile.mktemp(suffix=".pdf")
            if not is_last_pdf:
                temp_files.append(current_output)

            if action_type == "split":
                split_pdf(current_input, current_output, kwargs.get("start", 1), kwargs.get("end", 1))
            elif action_type == "watermark":
                add_watermark_to_pdf(current_input, current_output, kwargs.get("text", "AURA"))
            elif action_type == "compress":
                compress_pdf(current_input, current_output, kwargs.get("quality", "ebook"))
            elif action_type == "encrypt":
                encrypt_pdf(current_input, current_output, kwargs.get("password", "123456"))
            elif action_type == "delete_pages":
                delete_pages_from_pdf(current_input, current_output, kwargs.get("pages", []))
            elif action_type == "rotate":
                from PyPDF2 import PdfReader
                reader = PdfReader(current_input)
                all_pages = list(range(1, len(reader.pages) + 1))
                rotate_pages_in_pdf(current_input, current_output, all_pages, kwargs.get("angle", 90))
            else:
                shutil.copy(current_input, current_output)

            current_input = current_output

        # Sonuç mesajı
        target_str = _get_target_display_name(output_target_dir)
        action_names = [_get_action_name(a["action"]) for a in actions]
        action_summary = ", ".join(action_names)
        msg = f"{action_summary} işlemleri başarıyla tamamlandı. Dosyanız {target_str} kaydedildi."
        speak(msg)

    except FileNotFoundError as e:
        speak(f"Dosya bulunamadı hatası: {str(e)}")
    except ValueError as e:
        speak(f"Geçersiz parametre hatası: {str(e)}")
    except PermissionError:
        speak("Dosya yazma izni yok. Hedef klasöre erişim reddedildi.")
    except Exception as e:
        print(f"[Action Runner Error] {e}")
        speak(f"İşlem sırasında beklenmedik bir hata oluştu.")
    finally:
        # Geçici dosyaları her durumda temizle (hata olsa bile)
        for tf in temp_files:
            try:
                if os.path.exists(tf):
                    os.remove(tf)
            except Exception:
                pass


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
            speak("OCR işlemi tamamlandı. Metin dosyası kaydedildi.")

        elif action_type == "pdf_to_image":
            img_folder = os.path.join(output_dir, f"{base_name}_resimler")
            fmt = kwargs.get("format", "png")
            count = pdf_to_images(input_path, img_folder, dpi=300, img_format=fmt)
            speak(f"PDF başarıyla {count} adet {fmt.upper()} resme dönüştürüldü.")

        elif action_type == "pdf_to_word":
            output_docx = os.path.join(output_dir, f"{base_name}.docx")
            pdf_to_word(input_path, output_docx)
            speak("PDF başarıyla Word formatına dönüştürüldü.")

        elif action_type == "pdf_to_text":
            output_txt = os.path.join(output_dir, f"{base_name}.txt")
            pdf_to_txt(input_path, output_txt)
            speak("PDF'deki metinler başarıyla çıkarıldı ve metin dosyasına kaydedildi.")

    except Exception as e:
        print(f"[Non-PDF Action Error] {e}")
        speak(f"İşlem sırasında bir hata oluştu: {str(e)}")


def _get_target_display_name(output_target_dir: str) -> str:
    """Hedef klasörü kullanıcı dostu Türkçe isme çevirir."""
    folder = os.path.basename(output_target_dir).lower()
    if folder in ("desktop", "masaüstü"):
        return "Masaüstüne"
    elif folder in ("documents", "belgeler"):
        return "Belgelerim klasörüne"
    elif folder in ("downloads", "indirilenler"):
        return "İndirilenler klasörüne"
    return "bulunduğu klasöre"


def _get_action_name(action: str) -> str:
    """İşlem kodlarını Türkçe isimlendirme."""
    names = {
        "split": "Kesme",
        "watermark": "Filigran ekleme",
        "compress": "Sıkıştırma",
        "encrypt": "Şifreleme",
        "delete_pages": "Sayfa silme",
        "rotate": "Döndürme",
        "ocr": "OCR",
        "pdf_to_image": "Resme dönüştürme",
        "pdf_to_word": "Word'e dönüştürme",
        "pdf_to_text": "Metin çıkarma",
    }
    return names.get(action, action)
