"""Issue #9: execute_intent must never invent a password, and must merge."""
import pytest

from conftest import make_pdf, page_widths
from src.ai import action_runner
from src.ai.intent_parser import parse_intent


@pytest.fixture
def spoken(monkeypatch):
    """Capture what the assistant says instead of speaking it."""
    said = []
    monkeypatch.setattr(action_runner, "speak", said.append)
    return said


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A fake Desktop that _find_file and the parser both search."""
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    monkeypatch.setattr("os.path.expanduser", lambda p: str(tmp_path) if p == "~" else p)
    return desktop


def test_encrypt_without_a_password_writes_nothing(home, spoken):
    """It used to encrypt with "123456" and never mention it."""
    make_pdf(home / "rapor.pdf")

    action_runner.execute_intent(parse_intent("rapor.pdf dosyasını şifrele"))

    assert not (home / "rapor_aura.pdf").exists()
    assert any("parola" in m.lower() for m in spoken)


def test_encrypt_with_a_password_produces_the_file(home, spoken):
    make_pdf(home / "rapor.pdf")

    action_runner.execute_intent(parse_intent("rapor.pdf dosyasını abc123 ile şifrele"))

    out = home / "rapor_aura.pdf"
    assert out.exists()
    from pypdf import PdfReader
    reader = PdfReader(str(out))
    assert reader.is_encrypted
    assert reader.decrypt("abc123")


def test_encrypt_keeps_the_case_of_the_password_and_says_it(home, spoken):
    """'Gizli123' used to lock the file with 'gizli123', and nobody was told (#29)."""
    make_pdf(home / "rapor.pdf")

    action_runner.execute_intent(parse_intent("rapor.pdf dosyasını Gizli123 ile şifrele"))

    from pypdf import PdfReader
    reader = PdfReader(str(home / "rapor_aura.pdf"))
    assert not reader.decrypt("gizli123")
    assert reader.decrypt("Gizli123")
    assert "Gizli123" in spoken[-1]


def test_merge_combines_both_files(home, spoken):
    make_pdf(home / "a.pdf", pages=2)
    make_pdf(home / "b.pdf", pages=3)

    action_runner.execute_intent(parse_intent("a.pdf ve b.pdf dosyalarını birleştir"))

    out = home / "a_aura.pdf"
    assert out.exists()
    assert len(page_widths(out)) == 5


def test_convert_to_word_does_not_write_a_rotated_pdf(home, spoken, monkeypatch):
    """The reported symptom: a rotated rapor_aura.pdf instead of a .docx."""
    make_pdf(home / "rapor.pdf")
    called = []
    monkeypatch.setattr(action_runner, "pdf_to_word",
                        lambda inp, out, *a, **k: called.append(out))

    action_runner.execute_intent(parse_intent("rapor.pdf dosyasını Word'e çevir"))

    assert called and called[0].endswith(".docx")
    assert not (home / "rapor_aura.pdf").exists()


# ── Files that are already there stay as they are (#30) ──────────────────

def _fake_writer(content):
    def write(_input, output, *args, **kwargs):
        with open(output, "w", encoding="utf-8") as handle:
            handle.write(content)
    return write


@pytest.mark.parametrize("command, existing, written", [
    ("rapor.pdf dosyasını word'e çevir", "rapor.docx", "rapor (2).docx"),
    ("rapor.pdf dosyasını metne çevir", "rapor.txt", "rapor (2).txt"),
    ("rapor.pdf dosyasına ocr yap", "rapor_ocr.txt", "rapor_ocr (2).txt"),
    ("rapor.pdf dosyasını sıkıştır", "rapor_aura.pdf", "rapor_aura (2).pdf"),
])
def test_an_existing_output_is_kept_and_the_new_name_is_said(home, spoken, monkeypatch, command, existing,
                                                             written):
    """'rapor.pdf'yi word'e çevir' replaced the user's own rapor.docx."""
    make_pdf(home / "rapor.pdf")
    monkeypatch.setattr(action_runner, "pdf_to_word", _fake_writer("donusturuldu"))
    monkeypatch.setattr(action_runner, "pdf_to_txt", _fake_writer("metin"))
    monkeypatch.setattr(action_runner, "perform_ocr_to_text", _fake_writer("ocr"))
    (home / existing).write_bytes(b"kullanicinin kendi dosyasi")

    action_runner.execute_intent(parse_intent(command))

    assert (home / existing).read_bytes() == b"kullanicinin kendi dosyasi"
    assert (home / written).exists()
    assert written in spoken[-1]


# ── "Son N sayfa" and failed steps (#33) ─────────────────────────────────

@pytest.mark.parametrize("command", ["rapor.pdf son 3 sayfayı ayır", "extract the last 3 pages of rapor.pdf"])
def test_last_pages_are_the_last_pages(home, spoken, command):
    """It took page 1 alone and said the split went well."""
    make_pdf(home / "rapor.pdf", pages=5)

    action_runner.execute_intent(parse_intent(command))

    assert page_widths(home / "rapor_aura.pdf") == [597, 598, 599]


def test_more_last_pages_than_the_document_has_is_explained(home, spoken):
    make_pdf(home / "rapor.pdf", pages=5)

    action_runner.execute_intent(parse_intent("rapor.pdf son 9 sayfayı ayır"))

    assert not (home / "rapor_aura.pdf").exists()
    assert len(spoken) == 1 and "5" in spoken[0] and "9" in spoken[0]


def test_a_failed_step_is_not_followed_by_a_success_message(home, spoken, monkeypatch):
    """It said "İşlem sırasında bir hata oluştu" and then "Metin çıkarma
    işlemleri tamamlandı. Dosyanız Masaüstüne kaydedildi."."""
    make_pdf(home / "rapor.pdf")

    def broken(*_args, **_kwargs):
        raise RuntimeError("metin okunamadi")
    monkeypatch.setattr(action_runner, "pdf_to_txt", broken)

    action_runner.execute_intent(parse_intent("rapor.pdf dosyasını metne çevir ve sıkıştır"))

    assert len(spoken) == 1
    assert "metin okunamadi" in spoken[0]
    # The command stopped there: nothing was compressed either.
    assert not (home / "rapor_aura.pdf").exists()


def test_missing_file_is_reported(home, spoken):
    action_runner.execute_intent(parse_intent("yok.pdf dosyasını sıkıştır"))
    assert any("bulamad" in m.lower() for m in spoken)


def test_no_action_is_reported(home, spoken):
    make_pdf(home / "rapor.pdf")
    action_runner.execute_intent(parse_intent("rapor.pdf dosyasına merhaba de"))
    assert any("anlayamad" in m.lower() for m in spoken)
