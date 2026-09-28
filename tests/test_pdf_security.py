"""Issue #6: AES-encrypted PDFs, strong encryption, empty/mismatched passwords."""
import os
import re

import fitz
import pytest
from pypdf import PdfReader

from conftest import ROOT, make_encrypted_pdf, make_pdf, page_widths
from src.core.common import PdfPasswordError, get_pdf_page_count
from src.core.security import add_watermark_to_pdf, check_new_password, decrypt_pdf, encrypt_pdf


@pytest.mark.parametrize("algorithm", ["AES-128", "AES-256"])
def test_decrypt_aes_with_correct_password(tmp_path, algorithm):
    src = make_encrypted_pdf(tmp_path / "in.pdf", "abc", algorithm=algorithm)
    out = tmp_path / "out.pdf"

    decrypt_pdf(src, str(out), "abc")

    reader = PdfReader(str(out))
    assert not reader.is_encrypted
    assert len(reader.pages) == 3


def test_decrypt_wrong_password_is_rejected(tmp_path):
    src = make_encrypted_pdf(tmp_path / "in.pdf", "abc")
    with pytest.raises(ValueError, match="Parola yanlış"):
        decrypt_pdf(src, str(tmp_path / "out.pdf"), "wrong")
    assert not (tmp_path / "out.pdf").exists()


def test_decrypt_unencrypted_pdf_is_rejected(tmp_path):
    src = make_pdf(tmp_path / "in.pdf")
    with pytest.raises(ValueError, match="şifreli değil"):
        decrypt_pdf(src, str(tmp_path / "out.pdf"), "abc")


def test_owner_only_pdf_opens_in_page_tools(tmp_path):
    """User password empty, owner password set: Acrobat 'restrictions only' files."""
    from src.core.edit import delete_pages_from_pdf, reorder_pages_in_pdf, rotate_pages_in_pdf
    from src.core.merge import merge_pdfs
    from src.core.metainfo import read_metadata
    from src.core.split import split_pdf

    src = make_encrypted_pdf(tmp_path / "owner.pdf", "", owner_password="owner", algorithm="AES-256")

    assert get_pdf_page_count(src) == 3

    split_pdf(src, str(tmp_path / "split.pdf"), 2, 3)
    assert page_widths(tmp_path / "split.pdf") == [596, 597]

    merge_pdfs([src, src], str(tmp_path / "merged.pdf"))
    assert len(page_widths(tmp_path / "merged.pdf")) == 6

    delete_pages_from_pdf(src, str(tmp_path / "deleted.pdf"), [1])
    assert page_widths(tmp_path / "deleted.pdf") == [596, 597]

    rotate_pages_in_pdf(src, str(tmp_path / "rotated.pdf"), [1], 90)
    assert PdfReader(str(tmp_path / "rotated.pdf")).pages[0].rotation == 90

    reorder_pages_in_pdf(src, str(tmp_path / "reordered.pdf"), [3, 2, 1])
    assert page_widths(tmp_path / "reordered.pdf") == [597, 596, 595]

    assert isinstance(read_metadata(src), dict)


def test_user_password_pdf_gives_clear_error_in_page_tools(tmp_path):
    from src.core.split import split_pdf

    src = make_encrypted_pdf(tmp_path / "locked.pdf", "secret")
    with pytest.raises(PdfPasswordError, match="parola korumalı"):
        split_pdf(src, str(tmp_path / "split.pdf"), 1, 1)
    with pytest.raises(PdfPasswordError):
        get_pdf_page_count(src)


def test_encrypt_uses_aes256_and_needs_password(tmp_path):
    src = make_pdf(tmp_path / "in.pdf")
    out = str(tmp_path / "out.pdf")

    encrypt_pdf(src, out, "Parola1")

    encrypt_dict = PdfReader(out).trailer["/Encrypt"]
    assert encrypt_dict["/V"] == 5 and encrypt_dict["/R"] == 6  # AES-256

    doc = fitz.open(out)
    try:
        assert doc.needs_pass
        assert not doc.authenticate("wrong")
        assert doc.authenticate("Parola1")
        assert doc.page_count == 3
    finally:
        doc.close()


def test_encrypt_rejects_empty_password(tmp_path):
    src = make_pdf(tmp_path / "in.pdf")
    with pytest.raises(ValueError, match="Parola boş olamaz"):
        encrypt_pdf(src, str(tmp_path / "out.pdf"), "")
    assert not (tmp_path / "out.pdf").exists()


def test_check_new_password():
    check_new_password("abc", "abc")
    with pytest.raises(ValueError, match="boş olamaz"):
        check_new_password("", "")
    with pytest.raises(ValueError, match="eşleşmiyor"):
        check_new_password("abc", "abd")


def test_error_messages_follow_language(tmp_path):
    from src.core.config_manager import cfg

    cfg.config["language"] = "en"
    with pytest.raises(ValueError, match="Passwords do not match"):
        check_new_password("abc", "abd")


def test_watermark_works_on_owner_only_pdf(tmp_path):
    src = make_encrypted_pdf(tmp_path / "owner.pdf", "", owner_password="owner")
    out = str(tmp_path / "wm.pdf")
    add_watermark_to_pdf(src, out, "GIZLI")
    assert len(PdfReader(out).pages) == 3


def test_no_pypdf2_left():
    offenders = []
    for folder in ("src", "tests"):
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, folder)):
            for name in files:
                if name.endswith(".py") and name != os.path.basename(__file__):
                    path = os.path.join(dirpath, name)
                    with open(path, encoding="utf-8") as f:
                        if re.search(r"\bPyPDF2\b", f.read()):
                            offenders.append(os.path.relpath(path, ROOT))
    with open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8") as f:
        if re.search(r"^PyPDF2", f.read(), re.MULTILINE | re.IGNORECASE):
            offenders.append("requirements.txt")
    assert offenders == []
