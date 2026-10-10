"""Issue #11: stale output paths, hardcoded Turkish suffixes, partial files."""
import os

import pytest

from src.core.config_manager import cfg
from src.core.output_paths import atomic_output, is_inside, suggest_output, unique_path
from src.app.tools import suggest_output as suggest_for

KINDS = ["merged", "edited", "encrypted", "decrypted", "watermarked",
         "compressed", "images", "scanned", "split"]


@pytest.mark.parametrize("kind", KINDS)
def test_every_suffix_is_translated(kind):
    """The suffixes were hardcoded Turkish and showed up in the English UI."""
    cfg.config["language"] = "tr"
    turkish = suggest_output("a.pdf", kind)
    cfg.config["language"] = "en"
    english = suggest_output("a.pdf", kind)
    cfg.config["language"] = "tr"
    assert turkish != english, f"{kind} is the same in both languages"


def test_compress_suffix_follows_the_language():
    cfg.config["language"] = "tr"
    assert suggest_for("compress", "C:/x/rapor.pdf").endswith("_sikistirilmis.pdf")
    cfg.config["language"] = "en"
    assert suggest_for("compress", "C:/x/rapor.pdf").endswith("_compressed.pdf")
    cfg.config["language"] = "tr"


def test_split_suffix_follows_the_language():
    cfg.config["language"] = "en"
    assert "_split_2-4" in suggest_for("split", "C:/x/a.pdf", start=2, end=4)
    cfg.config["language"] = "tr"
    assert "_kesilmis_2-4" in suggest_for("split", "C:/x/a.pdf", start=2, end=4)


def test_suggestion_sits_next_to_the_input():
    assert os.path.dirname(suggest_output(os.path.join("C:/x", "a.pdf"), "merged")) == "C:/x"


SUGGESTIONS = [
    (("compress", "rapor.pdf"), "rapor_compressed.pdf"),
    (("split", "rapor.pdf", None, 2, 4), "rapor_split_2-4.pdf"),
    (("merge", "rapor.pdf"), "rapor_merged.pdf"),
    (("edit", "rapor.pdf"), "rapor_edited.pdf"),
    (("security", "rapor.pdf", "encrypt"), "rapor_encrypted.pdf"),
    (("security", "rapor.pdf", "decrypt"), "rapor_decrypted.pdf"),
    (("security", "rapor.pdf", "watermark"), "rapor_watermarked.pdf"),
    (("convert", "rapor.pdf", "pdf2img"), "rapor_images"),
    (("convert", "foto.jpg", "img2pdf"), "foto_merged.pdf"),
    (("convert", "rapor.pdf", "pdf2word"), "rapor.docx"),
    (("convert", "rapor.docx", "word2pdf"), "rapor.pdf"),
    (("convert", "sunum.pptx", "ppt2pdf"), "sunum.pdf"),
    (("convert", "tablo.xlsx", "excel2pdf"), "tablo.pdf"),
    (("convert", "rapor.pdf", "pdf2txt"), "rapor.txt"),
    (("scanner", "foto.jpg"), "foto_scanned.pdf"),
    (("advanced", "rapor.pdf", "ocr"), "rapor.txt"),
    (("advanced", "rapor.pdf", "metadata"), "rapor_metadata.pdf"),
    (("advanced", "rapor.pdf", "signature"), "rapor_signed.pdf"),
]


def test_a_preview_writes_nothing():
    """Advanced's preview opens the viewer; there is no output to suggest."""
    assert suggest_for("advanced", "C:/in/rapor.pdf", "preview") == ""


@pytest.mark.parametrize("args, name", SUGGESTIONS)
def test_every_tool_follows_the_default_output_folder(tmp_path, args, name):
    """Only Compress used the folder set in Settings; the other tools
    always suggested a path next to the input."""
    tool, source, *rest = args
    mode, start, end = (rest + [None, None, None])[:3]
    old = cfg.config.get("default_output_dir"), cfg.config.get("language")
    cfg.config["language"] = "en"
    try:
        cfg.config["default_output_dir"] = ""
        beside = suggest_for(tool, os.path.join("C:/in", source), mode, start=start, end=end)
        assert beside == os.path.join("C:/in", name)
        cfg.config["default_output_dir"] = str(tmp_path)
        inside = suggest_for(tool, os.path.join("C:/in", source), mode, start=start, end=end)
        assert inside == os.path.join(str(tmp_path), name)
    finally:
        cfg.config["default_output_dir"], cfg.config["language"] = old


def test_no_suggestion_without_an_input():
    assert suggest_for("compress", "") == ""


# ── atomic_output ─────────────────────────────────────────────────────────

def test_atomic_output_moves_into_place_on_success(tmp_path):
    target = tmp_path / "out.pdf"
    with atomic_output(str(target)) as temp:
        with open(temp, "wb") as f:
            f.write(b"good")
    assert target.read_bytes() == b"good"


def test_atomic_output_leaves_the_old_file_on_failure(tmp_path):
    """A crash used to leave a truncated file where a good one had been."""
    target = tmp_path / "out.pdf"
    target.write_bytes(b"original")

    with pytest.raises(RuntimeError):
        with atomic_output(str(target)) as temp:
            with open(temp, "wb") as f:
                f.write(b"half")
            raise RuntimeError("boom")

    assert target.read_bytes() == b"original"
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".pdfaura-")] == []


def test_atomic_output_allows_input_equal_to_output(tmp_path):
    target = tmp_path / "same.pdf"
    target.write_bytes(b"original")

    with atomic_output(str(target)) as temp:
        data = target.read_bytes()          # input still readable while writing
        with open(temp, "wb") as f:
            f.write(data + b"+more")

    assert target.read_bytes() == b"original+more"


# ── is_inside ─────────────────────────────────────────────────────────────

def test_is_inside_detects_nesting(tmp_path):
    assert is_inside(str(tmp_path / "a" / "b"), str(tmp_path))
    assert not is_inside(str(tmp_path), str(tmp_path / "a"))


def test_is_inside_handles_different_drives():
    assert is_inside("C:/a", "D:/b") is False


def test_unique_path_returns_the_path_when_free(tmp_path):
    assert unique_path(str(tmp_path / "free.pdf")) == str(tmp_path / "free.pdf")
