"""Faz 6: sensitive-data detection and real PDF redaction."""
import builtins
import os

import fitz
import pytest

from src.core import redact
from src.core.redact import (
    apply_redactions,
    find_sensitive,
    is_valid_credit_card,
    is_valid_iban,
    is_valid_tax_number,
    is_valid_tc_kimlik,
    normalize_phone,
)

TC = "10000000146"
IBAN = "TR33 0006 1005 1978 6457 8413 26"
PHONE = "0532 123 45 67"
EMAIL = "ahmet.yilmaz@example.com"
TAX = "4540536920"
CARD = "4111 1111 1111 1111"


def make_text_pdf(path, pages):
    """A PDF with a real text layer; page i's lines come from pages[i]."""
    doc = fitz.open()
    try:
        for lines in pages:
            page = doc.new_page()
            y = 72
            for line in lines:
                page.insert_text((72, y), line, fontsize=11)
                y += 24
        doc.save(str(path))
    finally:
        doc.close()
    return str(path)


@pytest.fixture
def sample_pdf(tmp_path):
    return make_text_pdf(tmp_path / "sensitive.pdf", [
        [f"Kimlik: {TC}", f"IBAN: {IBAN}", f"Telefon: {PHONE}", f"E-posta: {EMAIL}"],
        [f"Vergi No: {TAX}", f"Kart: {CARD}",
         "Gecersiz: 10000000147 / TR330006100519786457841327 / 4111111111111112"],
        ["Bu sayfada hassas bilgi yok."],
    ])


# ── Checksums ────────────────────────────────────────────────────────────

def test_tc_kimlik_checksum():
    assert is_valid_tc_kimlik(TC)
    assert is_valid_tc_kimlik("100 000 001 46")
    assert not is_valid_tc_kimlik("10000000147")   # last digit wrong
    assert not is_valid_tc_kimlik("00000000000")   # cannot start with 0
    assert not is_valid_tc_kimlik("11111111110")   # placeholder, all digits same
    assert not is_valid_tc_kimlik("1234567890")    # too short


def test_iban_mod97():
    assert is_valid_iban(IBAN)
    assert is_valid_iban(IBAN.replace(" ", ""))
    assert not is_valid_iban("TR330006100519786457841327")
    assert not is_valid_iban("DE89370400440532013000")  # only TR is supported


def test_tax_number_checksum():
    assert is_valid_tax_number(TAX)
    assert not is_valid_tax_number("4540536921")
    assert not is_valid_tax_number("454053692")


def test_credit_card_luhn():
    assert is_valid_credit_card(CARD)
    assert is_valid_credit_card("5555 5555 5555 4444")
    assert is_valid_credit_card("378282246310005")
    assert not is_valid_credit_card("4111 1111 1111 1112")
    assert not is_valid_credit_card("411111111111")


def test_phone_formats_normalise_to_the_same_number():
    assert normalize_phone("+90 532 123 45 67") == "05321234567"
    assert normalize_phone("0532 123 45 67") == "05321234567"
    assert normalize_phone("532 123 45 67") == "05321234567"
    assert normalize_phone("0 (212) 123 45 67") == "02121234567"
    assert normalize_phone("123 456 78 90") is None


# ── Detection ────────────────────────────────────────────────────────────

def test_find_sensitive_reports_type_text_page_and_rect(sample_pdf):
    matches = find_sensitive(sample_pdf, use_presidio=False)
    found = {(match["type"], match["text"]) for match in matches}

    assert (redact.TC_KIMLIK, TC) in found
    assert (redact.IBAN, IBAN) in found
    assert (redact.TELEFON, PHONE) in found
    assert (redact.EPOSTA, EMAIL) in found
    assert (redact.VERGI_NO, TAX) in found
    assert (redact.KREDI_KARTI, CARD) in found

    by_type = {match["type"]: match for match in matches}
    assert by_type[redact.TC_KIMLIK]["page"] == 1
    assert by_type[redact.VERGI_NO]["page"] == 2

    for match in matches:
        assert set(match) == {"type", "text", "page", "rect"}
        x0, y0, x1, y1 = match["rect"]
        assert x0 < x1 and y0 < y1


def test_find_sensitive_ignores_bad_checksums(sample_pdf):
    matches = find_sensitive(sample_pdf, use_presidio=False)
    texts = [match["text"] for match in matches]

    assert "10000000147" not in texts
    assert "TR330006100519786457841327" not in texts
    assert "4111111111111112" not in texts


def test_find_sensitive_on_a_document_without_sensitive_data(tmp_path):
    src = make_text_pdf(tmp_path / "plain.pdf", [["Merhaba, bu siradan bir belge."]])
    assert find_sensitive(src, use_presidio=False) == []


def test_presidio_is_optional_and_regex_still_runs(monkeypatch, sample_pdf):
    real_import = builtins.__import__

    def import_without_presidio(name, *args, **kwargs):
        if name == "presidio_analyzer":
            raise ImportError("Presidio is not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_presidio)
    monkeypatch.setattr(redact, "_analyzer", None)
    monkeypatch.setattr(redact, "_analyzer_loaded", False)

    matches = find_sensitive(sample_pdf)  # default use_presidio=True
    assert any(match["type"] == redact.TC_KIMLIK for match in matches)


# ── Real redaction ───────────────────────────────────────────────────────

def test_redacted_text_cannot_be_found_or_copied(tmp_path, sample_pdf):
    output = str(tmp_path / "redacted.pdf")
    matches = find_sensitive(sample_pdf, use_presidio=False)

    apply_redactions(sample_pdf, matches, output)

    doc = fitz.open(output)
    try:
        text = "".join(page.get_text() for page in doc)
        assert "Kimlik:" in text and "IBAN:" in text  # non-sensitive labels stay
        for match in matches:
            assert match["text"] not in text
            page = doc[match["page"] - 1]
            assert page.search_for(match["text"]) == []
    finally:
        doc.close()

    # The input document is untouched.
    original = fitz.open(sample_pdf)
    try:
        assert TC in original[0].get_text()
    finally:
        original.close()


def test_original_is_replaced_when_the_output_is_the_input(tmp_path, sample_pdf):
    matches = find_sensitive(sample_pdf, use_presidio=False)
    apply_redactions(sample_pdf, matches, sample_pdf)

    doc = fitz.open(sample_pdf)
    try:
        text = "".join(page.get_text() for page in doc)
        assert TC not in text
        assert EMAIL not in text
    finally:
        doc.close()


def test_apply_redactions_accepts_a_manual_rect(tmp_path):
    src = make_text_pdf(tmp_path / "manual.pdf", [["Gizli: 12345678901"]])
    doc = fitz.open(src)
    try:
        rect = doc[0].search_for("12345678901")[0]
    finally:
        doc.close()

    output = str(tmp_path / "manual-out.pdf")
    apply_redactions(src, [{"type": "manual", "text": "12345678901", "page": 1,
                            "rect": tuple(rect)}], output)

    doc = fitz.open(output)
    try:
        assert "12345678901" not in doc[0].get_text()
    finally:
        doc.close()


def test_empty_match_list_still_produces_a_copy(tmp_path):
    src = make_text_pdf(tmp_path / "copy.pdf", [["Silinecek bir sey yok."]])
    output = str(tmp_path / "copy-out.pdf")

    apply_redactions(src, [], output)

    assert os.path.exists(output)
    doc = fitz.open(output)
    try:
        assert "Silinecek bir sey yok." in doc[0].get_text()
    finally:
        doc.close()


def test_invalid_page_is_rejected_without_writing_output(tmp_path, sample_pdf):
    output = str(tmp_path / "never.pdf")
    with pytest.raises(ValueError, match="Gecersiz sayfa"):
        apply_redactions(sample_pdf, [{"type": "x", "text": "x", "page": 99,
                                       "rect": (0, 0, 10, 10)}], output)
    assert not os.path.exists(output)
