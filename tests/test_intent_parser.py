"""Issue #9: the assistant misread commands. One test per row of the issue table."""
import pytest

from src.ai.intent_parser import parse_actions, parse_input_files, parse_intent


def actions_of(text):
    return [a["action"] for a in parse_intent(text)["action_chain"]]


def kwargs_of(text, action):
    for a in parse_intent(text)["action_chain"]:
        if a["action"] == action:
            return a["kwargs"]
    raise AssertionError(f"{action} not in {parse_intent(text)['action_chain']}")


# ── The table in issue #9 ─────────────────────────────────────────────────

def test_convert_to_word_does_not_rotate():
    """Used to rotate every page 90 degrees and report success."""
    assert actions_of("rapor.pdf dosyasını Word'e çevir") == ["pdf_to_word"]


def test_convert_to_image_does_not_rotate():
    assert actions_of("rapor.pdf dosyasını resme çevir") == ["pdf_to_image"]


def test_encrypt_without_a_password_asks_instead_of_using_123456():
    intent = parse_intent("rapor.pdf dosyasını şifrele")
    encrypt = [a for a in intent["action_chain"] if a["action"] == "encrypt"]
    assert encrypt, "encrypt action missing"
    assert encrypt[0]["kwargs"].get("needs_password") is True
    assert "password" not in encrypt[0]["kwargs"]


def test_encrypt_with_a_spoken_password_uses_it():
    assert kwargs_of("rapor.pdf dosyasını abc123 ile şifrele", "encrypt")["password"] == "abc123"


def test_filename_containing_kes_is_not_a_split():
    """'herkes.pdf' contains 'kes'; it must not trigger a split."""
    assert actions_of("herkes.pdf dosyasını sıkıştır") == ["compress"]


def test_digits_in_the_filename_are_not_page_numbers():
    """'rapor_5.pdf' used to contribute page 5 to the delete list."""
    assert kwargs_of("rapor_5.pdf dosyasının 3. sayfasını sil", "delete_pages")["pages"] == [3]


def test_number_word_in_filename_is_not_converted():
    """'bir.pdf' used to become '1.pdf'."""
    assert parse_intent("bir.pdf dosyasını sıkıştır")["input_file"] == "bir.pdf"


def test_number_word_outside_the_filename_is_still_converted():
    assert kwargs_of("rapor.pdf ilk beş sayfasını kes", "split") == {"start": 1, "end": 5}


def test_ayir_is_recognised_as_split():
    """README's 'İlk 3 sayfayı ayır' matched nothing at all."""
    assert kwargs_of("rapor.pdf ilk 3 sayfayı ayır", "split") == {"start": 1, "end": 3}


def test_merge_is_recognised():
    """There was no merge action at all."""
    intent = parse_intent("a.pdf ve b.pdf dosyalarını birleştir")
    assert [a["action"] for a in intent["action_chain"]] == ["merge"]
    assert intent["input_files"] == ["a.pdf", "b.pdf"]


def test_english_command_is_understood():
    assert actions_of("compress report.pdf") == ["compress"]


# ── Explicit rotation still works ─────────────────────────────────────────

def test_dondur_still_rotates():
    assert kwargs_of("rapor.pdf dosyasını döndür", "rotate")["angle"] == 90


def test_cevir_with_a_degree_rotates():
    assert kwargs_of("rapor.pdf dosyasını 180 derece çevir", "rotate")["angle"] == 180


def test_rotate_left():
    assert kwargs_of("rapor.pdf dosyasını sola 90 derece döndür", "rotate")["angle"] == 270


def test_invalid_angle_falls_back_to_90():
    assert kwargs_of("rapor.pdf dosyasını 45 derece döndür", "rotate")["angle"] == 90


# ── File name extraction ──────────────────────────────────────────────────

def test_explicit_pdf_names_are_found_in_order():
    assert parse_input_files("a.pdf ve b.pdf birleştir") == ["a.pdf", "b.pdf"]


def test_dosya_pattern():
    assert parse_input_files("rapor dosyasını sıkıştır") == ["rapor.pdf"]


def test_spelled_out_pdf():
    assert parse_input_files("sunum p d f ini sıkıştır") == ["sunum.pdf"]


def test_bare_name_resolved_from_desktop(tmp_path, monkeypatch):
    """README's 'Masaüstündeki sözleşmeyi sıkıştır' found no file."""
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "sözleşme.pdf").write_bytes(b"%PDF-1.4")
    monkeypatch.setattr("os.path.expanduser", lambda p: str(tmp_path) if p == "~" else p)

    intent = parse_intent("Masaüstündeki sözleşmeyi sıkıştır")
    assert intent["input_file"] == "sözleşme.pdf"
    assert [a["action"] for a in intent["action_chain"]] == ["compress"]


def test_unknown_bare_name_returns_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr("os.path.expanduser", lambda p: str(tmp_path) if p == "~" else p)
    assert parse_input_files("Masaüstündeki sözleşmeyi sıkıştır") == []


# ── Split ranges ──────────────────────────────────────────────────────────

def test_range_split():
    assert kwargs_of("rapor.pdf 3 ile 7 arasını kes", "split") == {"start": 3, "end": 7}


def test_single_page_split():
    assert kwargs_of("rapor.pdf 5. sayfayı kes", "split") == {"start": 5, "end": 5}


# ── Chains and other actions ──────────────────────────────────────────────

def test_chained_compress_and_watermark():
    assert set(actions_of("rapor.pdf sıkıştır ve GİZLİ yazılı filigran ekle")) == \
           {"compress", "watermark"}


def test_watermark_text_is_picked_up():
    assert kwargs_of("rapor.pdf TASLAK yazılı filigran ekle", "watermark")["text"] == "TASLAK"


def test_ocr_is_recognised():
    assert "ocr" in actions_of("rapor.pdf dosyasına ocr uygula")


def test_convert_to_text():
    assert actions_of("rapor.pdf dosyasını metne çevir") == ["pdf_to_text"]


def test_jpg_format_is_honoured():
    assert kwargs_of("rapor.pdf dosyasını jpg resme çevir", "pdf_to_image")["format"] == "jpg"


def test_empty_text_gives_empty_intent():
    assert parse_intent("") == {}


def test_unrecognised_command_has_no_actions():
    assert parse_intent("rapor.pdf dosyasına merhaba de")["action_chain"] == []
