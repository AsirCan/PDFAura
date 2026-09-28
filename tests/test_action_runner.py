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


def test_missing_file_is_reported(home, spoken):
    action_runner.execute_intent(parse_intent("yok.pdf dosyasını sıkıştır"))
    assert any("bulamad" in m.lower() for m in spoken)


def test_no_action_is_reported(home, spoken):
    make_pdf(home / "rapor.pdf")
    action_runner.execute_intent(parse_intent("rapor.pdf dosyasına merhaba de"))
    assert any("anlayamad" in m.lower() for m in spoken)
