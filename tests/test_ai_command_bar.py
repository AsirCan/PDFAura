"""Tests for Faz 9 AI Komut Cubugu backend:
- Rule-based parser (TR + EN phrasings for all operations)
- Action chaining & argument isolation
- build_plan (Turkish human-readable execution plan)
- Optional LLM fallback
- ActionRunner chain execution on generated PDFs with progress & cancellation
"""
import os
from pathlib import Path
import pytest
from pypdf import PdfReader

from conftest import make_pdf, make_encrypted_pdf, page_widths
from src.ai import action_runner
from src.ai.intent_parser import (
    build_plan,
    parse_actions,
    parse_input_files,
    parse_intent,
    parse_intent_with_llm,
    parse_target_folder,
    parse_watermark_text,
    parse_compression_quality,
)


@pytest.fixture
def spoken(monkeypatch):
    """Capture spoken messages instead of speaking aloud."""
    messages = []
    monkeypatch.setattr(action_runner, "speak", messages.append)
    return messages


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """A fake user home folder with Desktop, Documents, Downloads."""
    desktop = tmp_path / "Desktop"
    documents = tmp_path / "Documents"
    downloads = tmp_path / "Downloads"
    desktop.mkdir()
    documents.mkdir()
    downloads.mkdir()
    monkeypatch.setattr("os.path.expanduser", lambda p: str(tmp_path) if p == "~" else p)
    return tmp_path


# ── 1. RULE-BASED PARSER TR + EN PHRASINGS ─────────────────────────────────

def test_compress_phrasings_tr_and_en():
    cases = [
        ("rapor.pdf dosyasını sıkıştır", "ebook"),
        ("rapor.pdf en küçük dosya boyutuyla sıkıştır", "screen"),
        ("rapor.pdf dosyasını matbaa kalitesinde sıkıştır", "prepress"),
        ("rapor.pdf baskı kalitesinde küçült", "printer"),
        ("compress report.pdf with maximum compression", "screen"),
        ("shrink document.pdf with high quality", "printer"),
        ("reduce size of report.pdf", "ebook"),
        ("make report.pdf smaller", "ebook"),
    ]
    for cmd, expected_q in cases:
        intent = parse_intent(cmd)
        compress = [a for a in intent["action_chain"] if a["action"] == "compress"]
        assert compress, f"Compress missing for: {cmd}"
        assert compress[0]["kwargs"].get("quality") == expected_q, f"Failed for: {cmd}"


def test_split_page_ranges_tr_and_en():
    cases = [
        ("rapor.pdf ilk 3 sayfayı ayır", {"start": 1, "end": 3}),
        ("rapor.pdf son 2 sayfayı ayır", {"last": 2}),
        ("rapor.pdf 5-10 arası kes", {"start": 5, "end": 10}),
        ("rapor.pdf 4. sayfayı böl", {"start": 4, "end": 4}),
        ("extract first 4 pages of report.pdf", {"start": 1, "end": 4}),
        ("extract last 3 pages from report.pdf", {"last": 3}),
        ("split report.pdf pages 2-7", {"start": 2, "end": 7}),
        ("extract first three pages of report.pdf", {"start": 1, "end": 3}),
    ]
    for cmd, expected_range in cases:
        intent = parse_intent(cmd)
        split = [a for a in intent["action_chain"] if a["action"] == "split"]
        assert split, f"Split missing for: {cmd}"
        assert split[0]["kwargs"] == expected_range, f"Failed for: {cmd}"


def test_merge_phrasings_tr_and_en():
    cases = [
        ("a.pdf ve b.pdf dosyalarını birleştir", ["a.pdf", "b.pdf"]),
        ("doc1.pdf ile doc2.pdf bir araya getir", ["doc1.pdf", "doc2.pdf"]),
        ("merge report1.pdf and report2.pdf", ["report1.pdf", "report2.pdf"]),
        ("combine x.pdf, y.pdf and z.pdf", ["x.pdf", "y.pdf", "z.pdf"]),
    ]
    for cmd, expected_files in cases:
        intent = parse_intent(cmd)
        assert any(a["action"] == "merge" for a in intent["action_chain"]), f"Merge missing for: {cmd}"
        assert intent["input_files"] == expected_files, f"Files mismatch for: {cmd}"


def test_rotate_phrasings_tr_and_en():
    cases = [
        ("rapor.pdf dosyasını 90 derece döndür", 90),
        ("rapor.pdf ters çevir", 180),
        ("rapor.pdf baş aşağı çevir", 180),
        ("rapor.pdf dosyasını sola 90 derece döndür", 270),
        ("rotate report.pdf 180 degrees", 180),
        ("turn report.pdf upside down", 180),
        ("rotate report.pdf counterclockwise", 270),
        ("rotate report.pdf clockwise", 90),
    ]
    for cmd, expected_angle in cases:
        intent = parse_intent(cmd)
        rotate = [a for a in intent["action_chain"] if a["action"] == "rotate"]
        assert rotate, f"Rotate missing for: {cmd}"
        assert rotate[0]["kwargs"].get("angle") == expected_angle, f"Failed for: {cmd}"


def test_watermark_phrasings_tr_and_en():
    cases = [
        ('rapor.pdf "GİZLİ" yazılı filigran ekle', "GİZLİ"),
        ('rapor.pdf üzerine TASLAK filigranı koy', "TASLAK"),
        ('rapor.pdf filigran ekle', "GİZLİ"),
        ('watermark report.pdf with CONFIDENTIAL', "CONFIDENTIAL"),
        ('add "DRAFT" watermark to report.pdf', "DRAFT"),
        ('add watermark to report.pdf', "GİZLİ"),
    ]
    for cmd, expected_text in cases:
        intent = parse_intent(cmd)
        wm = [a for a in intent["action_chain"] if a["action"] == "watermark"]
        assert wm, f"Watermark missing for: {cmd}"
        assert wm[0]["kwargs"].get("text") == expected_text, f"Failed for: {cmd}"


def test_encrypt_decrypt_phrasings_tr_and_en():
    cases = [
        ("rapor.pdf dosyasını gizli123 ile şifrele", "encrypt", {"password": "gizli123"}),
        ("rapor.pdf dosyasını şifrele", "encrypt", {"needs_password": True}),
        ("sifreli.pdf şifresini gizli123 ile kaldır", "decrypt", {"password": "gizli123"}),
        ("sifreli.pdf şifresini kaldır", "decrypt", {"needs_password": True}),
        ("encrypt report.pdf with Pass123", "encrypt", {"password": "Pass123"}),
        ("remove password from locked.pdf with SecretKey", "decrypt", {"password": "SecretKey"}),
        ("unlock locked.pdf", "decrypt", {"needs_password": True}),
    ]
    for cmd, action_name, expected_kw in cases:
        intent = parse_intent(cmd)
        acts = [a for a in intent["action_chain"] if a["action"] == action_name]
        assert acts, f"{action_name} missing for: {cmd}"
        assert acts[0]["kwargs"] == expected_kw, f"Failed for: {cmd}"


def test_ocr_phrasings_tr_and_en():
    for cmd in [
        "rapor.pdf dosyasına ocr yap",
        "rapor.pdf metin tanı",
        "perform ocr on report.pdf",
        "recognize text in report.pdf",
    ]:
        intent = parse_intent(cmd)
        assert any(a["action"] == "ocr" for a in intent["action_chain"]), f"OCR missing for: {cmd}"


def test_delete_pages_phrasings_tr_and_en():
    cases = [
        ("rapor.pdf dosyasından ilk 2 sayfayı sil", {"pages": [1, 2]}),
        ("rapor.pdf dosyasından son 2 sayfayı sil", {"last": 2}),
        ("rapor.pdf dosyasından 4. sayfayı sil", {"pages": [4]}),
        ("rapor.pdf dosyasından 3-5 sayfalarını sil", {"pages": [3, 4, 5]}),
        ("delete page 4 from report.pdf", {"pages": [4]}),
        ("delete last 2 pages from report.pdf", {"last": 2}),
        ("remove pages 2-4 from report.pdf", {"pages": [2, 3, 4]}),
    ]
    for cmd, expected_kw in cases:
        intent = parse_intent(cmd)
        acts = [a for a in intent["action_chain"] if a["action"] == "delete_pages"]
        assert acts, f"delete_pages missing for: {cmd}"
        assert acts[0]["kwargs"] == expected_kw, f"Failed for: {cmd}"


def test_to_images_phrasings_tr_and_en():
    cases = [
        ("rapor.pdf dosyasını resimlere dönüştür", "png"),
        ("rapor.pdf sayfalarını jpg resim olarak kaydet", "jpg"),
        ("convert report.pdf to images", "png"),
        ("export report.pdf as jpg", "jpg"),
    ]
    for cmd, expected_fmt in cases:
        intent = parse_intent(cmd)
        acts = [a for a in intent["action_chain"] if a["action"] == "pdf_to_image"]
        assert acts, f"pdf_to_image missing for: {cmd}"
        assert acts[0]["kwargs"].get("format") == expected_fmt, f"Failed for: {cmd}"


def test_output_targets_tr_and_en(fake_home):
    home_str = str(fake_home)
    assert parse_target_folder("rapor.pdf sıkıştır ve Masaüstüne kaydet") == os.path.join(home_str, "Desktop")
    assert parse_target_folder("rapor.pdf sıkıştır ve Masaustune kaydet") == os.path.join(home_str, "Desktop")
    assert parse_target_folder("rapor.pdf sıkıştır ve Belgelerim klasörüne kaydet") == os.path.join(home_str, "Documents")
    assert parse_target_folder("rapor.pdf sıkıştır ve İndirilenler klasörüne kaydet") == os.path.join(home_str, "Downloads")
    assert parse_target_folder("rapor.pdf sıkıştır ve Indirilenlere kaydet") == os.path.join(home_str, "Downloads")
    assert parse_target_folder("save report.pdf to Desktop") == os.path.join(home_str, "Desktop")
    assert parse_target_folder("save report.pdf to Documents") == os.path.join(home_str, "Documents")
    assert parse_target_folder("save report.pdf to Downloads") == os.path.join(home_str, "Downloads")
    custom = parse_target_folder('rapor.pdf sıkıştır ve "C:\\Cikti" klasörüne kaydet')
    assert custom == os.path.normpath("C:/Cikti")


def test_chained_commands_ordering_and_isolation():
    # 1. Chained compress + split
    cmd1 = "rapor.pdf dosyasını sıkıştır, ilk 3 sayfayı ayır ve Masaüstüne kaydet"
    intent1 = parse_intent(cmd1)
    actions1 = [a["action"] for a in intent1["action_chain"]]
    assert actions1 == ["compress", "split"]
    assert intent1["action_chain"][1]["kwargs"] == {"start": 1, "end": 3}
    assert intent1["output_target"].endswith("Desktop")

    # 2. Chained split + delete_pages without argument confusion
    cmd2 = "rapor.pdf dosyasından 2. sayfayı sil ve 5-10 arasını ayır"
    intent2 = parse_intent(cmd2)
    actions2 = [a["action"] for a in intent2["action_chain"]]
    assert actions2 == ["delete_pages", "split"]
    assert intent2["action_chain"][0]["kwargs"] == {"pages": [2]}
    assert intent2["action_chain"][1]["kwargs"] == {"start": 5, "end": 10}

    # 3. Decrypt first, middle in order, encrypt last
    cmd3 = "sifreli.pdf şifresini 1234 ile çöz, 90 derece döndür ve Gizli99 ile şifrele"
    intent3 = parse_intent(cmd3)
    actions3 = [a["action"] for a in intent3["action_chain"]]
    assert actions3 == ["decrypt", "rotate", "encrypt"]
    assert intent3["action_chain"][0]["kwargs"] == {"password": "1234"}
    assert intent3["action_chain"][1]["kwargs"] == {"angle": 90}
    assert intent3["action_chain"][2]["kwargs"] == {"password": "Gizli99"}


# ── 2. BUILD_PLAN TESTS ───────────────────────────────────────────────────

def test_build_plan_single_action():
    intent = {
        "input_file": "rapor.pdf",
        "input_files": ["rapor.pdf"],
        "output_target": "C:\\Users\\test\\Desktop",
        "action_chain": [{"action": "compress", "kwargs": {"quality": "ebook"}}],
    }
    plan = build_plan(intent)
    assert "İşlem planı:" in plan
    assert "Girdi: rapor.pdf" in plan
    assert "1. Sıkıştır (dengeli / e-kitap kalitesi)" in plan
    assert "Masaüstü" in plan
    assert "rapor_aura.pdf" in plan


def test_build_plan_chained_actions_with_password():
    intent = {
        "input_file": "doc.pdf",
        "input_files": ["doc.pdf"],
        "output_target": None,
        "action_chain": [
            {"action": "split", "kwargs": {"start": 1, "end": 3}},
            {"action": "watermark", "kwargs": {"text": "ÖZEL"}},
            {"action": "encrypt", "kwargs": {"needs_password": True}},
        ],
    }
    plan = build_plan(intent)
    assert "Sayfa 1-3 arasını ayır" in plan
    assert "Filigran ekle: ÖZEL" in plan
    assert "PDF'i şifrele (parola sorulacak)" in plan
    assert "Not: İşlem için parola sorulacak." in plan
    assert "bulunduğu klasör" in plan


def test_build_plan_empty_intent():
    plan = build_plan({})
    assert "dosya belirtilmedi" in plan
    assert "işlem anlaşılamadı" in plan


# ── 3. OPTIONAL LOCAL LLM FALLBACK TESTS ──────────────────────────────────

def test_llm_fallback_used_when_rules_fail():
    class MockLLM:
        def generate(self, prompt, **kwargs):
            return """
            {
                "input_file": "ozel_belge.pdf",
                "action_chain": [
                    {"action": "compress", "kwargs": {"quality": "screen"}}
                ],
                "output_target": "Masaüstü"
            }
            """

    intent = parse_intent("bunu acayip bir sekilde ufalt", llm=MockLLM())
    assert intent["source"] == "llm"
    assert intent["input_file"] == "ozel_belge.pdf"
    assert len(intent["action_chain"]) == 1
    assert intent["action_chain"][0]["action"] == "compress"
    assert intent["action_chain"][0]["kwargs"]["quality"] == "screen"


def test_llm_fallback_invalid_json_rejected():
    class BadLLM:
        def generate(self, prompt, **kwargs):
            return "Ben bir yapay zekayım ama JSON veremem."

    intent = parse_intent("tanimsiz bir komut 123", llm=BadLLM())
    assert intent["source"] == "rules"
    assert intent["action_chain"] == []


def test_llm_fallback_exception_handled_gracefully():
    class CrashingLLM:
        def generate(self, prompt, **kwargs):
            raise RuntimeError("Model CUDA out of memory")

    intent = parse_intent("tanimsiz bir komut 456", llm=CrashingLLM())
    assert intent["source"] == "rules"
    assert intent["action_chain"] == []


# ── 4. ACTION RUNNER CHAIN EXECUTION ON GENERATED PDFS ────────────────────

def test_runner_executes_split_and_watermark_chain(fake_home, spoken):
    pdf_path = fake_home / "Desktop" / "deneme.pdf"
    make_pdf(pdf_path, pages=6)

    intent = parse_intent("deneme.pdf ilk 3 sayfayı ayır ve GİZLİ filigran ekle")
    result = action_runner.execute_intent(intent)

    assert result["ok"] is True
    out_pdf = fake_home / "Desktop" / "deneme_aura.pdf"
    assert out_pdf.exists()

    # Split to first 3 pages
    widths = page_widths(out_pdf)
    assert len(widths) == 3


def test_runner_executes_rotate_and_delete_pages(fake_home, spoken):
    pdf_path = fake_home / "Desktop" / "evrak.pdf"
    make_pdf(pdf_path, pages=4)

    intent = parse_intent("evrak.pdf dosyasından 2. sayfayı sil ve 90 derece döndür")
    result = action_runner.execute_intent(intent)

    assert result["ok"] is True
    out_pdf = fake_home / "Desktop" / "evrak_aura.pdf"
    assert out_pdf.exists()

    reader = PdfReader(str(out_pdf))
    assert len(reader.pages) == 3
    # All pages rotated 90 degrees
    for page in reader.pages:
        assert page.get("/Rotate") == 90


def test_runner_executes_encrypt_and_decrypt_chain(fake_home, spoken):
    # Create an encrypted PDF
    enc_path = fake_home / "Desktop" / "kilitli.pdf"
    make_encrypted_pdf(enc_path, user_password="pass123", pages=3)

    # Decrypt with pass123 and compress
    intent = parse_intent("kilitli.pdf şifresini pass123 ile kaldır ve sıkıştır")
    result = action_runner.execute_intent(intent)

    assert result["ok"] is True
    out_pdf = fake_home / "Desktop" / "kilitli_aura.pdf"
    assert out_pdf.exists()

    reader = PdfReader(str(out_pdf))
    assert not reader.is_encrypted
    assert len(reader.pages) == 3


def test_runner_progress_callback(fake_home, spoken):
    pdf_path = fake_home / "Desktop" / "test_prog.pdf"
    make_pdf(pdf_path, pages=4)

    progress_steps = []

    def on_progress(cur, total, msg=""):
        progress_steps.append((cur, total, msg))

    intent = parse_intent("test_prog.pdf ilk 2 sayfayı ayır ve sıkıştır")
    result = action_runner.execute_intent(intent, progress_callback=on_progress)

    assert result["ok"] is True
    assert len(progress_steps) > 0


def test_runner_cancellation(fake_home, spoken):
    pdf_path = fake_home / "Desktop" / "test_cancel.pdf"
    make_pdf(pdf_path, pages=4)

    def cancel_checker():
        return True  # Cancel immediately

    intent = parse_intent("test_cancel.pdf ilk 2 sayfayı ayır ve sıkıştır")
    result = action_runner.execute_intent(intent, cancel_check=cancel_checker)

    assert result["ok"] is False
    assert result["cancelled"] is True
    out_pdf = fake_home / "Desktop" / "test_cancel_aura.pdf"
    assert not out_pdf.exists()


def test_runner_friendly_error_on_missing_file(fake_home, spoken):
    intent = parse_intent("olmayan.pdf dosyasını sıkıştır")
    result = action_runner.execute_intent(intent)

    assert result["ok"] is False
    assert "olmayan.pdf" in result["error"]
    assert any("bulamad" in s for s in spoken)
