"""Issue #11: stale output paths, hardcoded Turkish suffixes, partial files."""
import os

import pytest

from src.core.config_manager import cfg
from src.core.output_paths import atomic_output, is_inside, suggest_output, unique_path
from src.utils.file_helper import suggest_output_path, suggest_split_output_path

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
    assert suggest_output_path("C:/x/rapor.pdf").endswith("_sikistirilmis.pdf")
    cfg.config["language"] = "en"
    assert suggest_output_path("C:/x/rapor.pdf").endswith("_compressed.pdf")
    cfg.config["language"] = "tr"


def test_split_suffix_follows_the_language():
    cfg.config["language"] = "en"
    assert "_split_2-4" in suggest_split_output_path("C:/x/a.pdf", 2, 4)
    cfg.config["language"] = "tr"
    assert "_kesilmis_2-4" in suggest_split_output_path("C:/x/a.pdf", 2, 4)


def test_suggestion_sits_next_to_the_input():
    assert os.path.dirname(suggest_output(os.path.join("C:/x", "a.pdf"), "merged")) == "C:/x"


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
