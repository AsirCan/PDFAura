"""Issue #35: downloads the app loads or installs are pinned and checked.

The scanner model came from a branch with no checksum, the Tesseract language
pack went straight to its final place (a cut connection left half a file that
was never downloaded again), and a refused UAC prompt still read "installed".
No real network here: urlopen answers from memory.
"""
import base64
import hashlib
import io
import os
import urllib.request

import pytest

from src.ai import model_manager
from src.core import install_tesseract
from src.core.lang_manager import _
from src.utils import download
from src.utils.download import DownloadError, download_verified, file_matches


class Response(io.BytesIO):
    def __init__(self, body, length=None):
        super().__init__(body)
        self.headers = {"Content-Length": str(len(body) if length is None else length)}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def serve(monkeypatch):
    """serve(body, length=None): what the next download receives."""
    served = {}

    def answer(request, timeout=None):
        served["url"] = request.full_url
        return Response(served["body"], served["length"])

    monkeypatch.setattr(urllib.request, "urlopen", answer)

    def set_body(body, length=None):
        served["body"], served["length"] = body, length
        return served
    return set_body


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git_sha1(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


GOOD = b"onnx model bytes " * 1000


# ── The verified download ─────────────────────────────────────────────────

def test_the_expected_file_is_put_in_place(tmp_path, serve):
    serve(GOOD)
    target = tmp_path / "model.onnx"

    download_verified("https://example.invalid/m", str(target), len(GOOD), sha256=sha256(GOOD))

    assert target.read_bytes() == GOOD
    assert os.listdir(tmp_path) == ["model.onnx"]


@pytest.mark.parametrize("body, length", [
    (b"X" + GOOD[1:], None),                  # altered on the way, same size
    (GOOD[: len(GOOD) // 2], len(GOOD)),      # connection cut halfway
    (GOOD + b"more", len(GOOD)),              # more than the file has
    (GOOD + b"more", None),                   # ...and announced as such
])
def test_a_wrong_or_half_download_leaves_nothing(tmp_path, serve, body, length):
    serve(body, length)
    target = tmp_path / "model.onnx"
    target_folder_before = sorted(os.listdir(tmp_path))

    with pytest.raises(DownloadError):
        download_verified("https://example.invalid/m", str(target), len(GOOD), sha256=sha256(GOOD))

    assert sorted(os.listdir(tmp_path)) == target_folder_before == []


def test_a_wrong_download_does_not_replace_a_good_file(tmp_path, serve):
    target = tmp_path / "model.onnx"
    target.write_bytes(GOOD)
    serve(b"X" + GOOD[1:])

    with pytest.raises(DownloadError):
        download_verified("https://example.invalid/m", str(target), len(GOOD), sha256=sha256(GOOD))

    assert target.read_bytes() == GOOD


def test_a_git_blob_id_is_checked_like_github_computes_it(tmp_path, serve):
    serve(GOOD)
    target = tmp_path / "tur.traineddata"

    download_verified("https://example.invalid/t", str(target), len(GOOD), git_sha1=git_sha1(GOOD))

    assert file_matches(str(target), len(GOOD), git_sha1=git_sha1(GOOD))
    assert not file_matches(str(target), len(GOOD), git_sha1=git_sha1(b"other"))


def test_nothing_is_downloaded_without_a_checksum(tmp_path, serve):
    serve(GOOD)
    with pytest.raises(DownloadError):
        download_verified("https://example.invalid/m", str(tmp_path / "m"), len(GOOD))
    assert os.listdir(tmp_path) == []


# ── The scanner model ─────────────────────────────────────────────────────

def test_the_scanner_model_is_pinned_to_a_commit_and_a_checksum():
    spec = model_manager.ModelManager(".").get_spec("scanner_u2netp")
    assert "/resolve/main/" not in spec.download_url
    assert "/resolve/b89fabdfd832c6adc357cfc7430e5eb60357a8ff/" in spec.download_url
    assert len(spec.sha256) == 64 and spec.size_bytes > 0


def test_a_scanner_model_that_does_not_match_is_refused(tmp_path, serve):
    spec = model_manager.ModelManager(str(tmp_path)).get_spec("scanner_u2netp")
    served = serve(b"\0" * spec.size_bytes)
    manager = model_manager.ModelManager(str(tmp_path))

    with pytest.raises(model_manager.ModelDownloadError, match=_("err_download_corrupt")):
        manager.download_model("scanner_u2netp")

    assert served["url"] == spec.download_url
    assert list((tmp_path / "vision").iterdir()) == []


# ── The Tesseract language pack ───────────────────────────────────────────

PACK = b"tesseract traineddata " * 500


@pytest.fixture
def pack(monkeypatch, serve):
    """The language pack is PACK; the server sends it unless told otherwise."""
    monkeypatch.setattr(install_tesseract, "TUR_SIZE", len(PACK))
    monkeypatch.setattr(install_tesseract, "TUR_GIT_SHA1", git_sha1(PACK))
    serve(PACK)
    return serve


def test_the_language_pack_url_is_pinned():
    assert "/main/" not in install_tesseract.TUR_URL
    assert install_tesseract.TUR_COMMIT in install_tesseract.TUR_URL


def test_the_language_pack_is_installed_checked(tmp_path, pack):
    install_tesseract.install_turkish_pack(str(tmp_path))
    assert (tmp_path / "tur.traineddata").read_bytes() == PACK


def test_a_half_language_pack_is_not_left_behind(tmp_path, pack):
    pack(PACK[:100], len(PACK))

    with pytest.raises(DownloadError):
        install_tesseract.install_turkish_pack(str(tmp_path))

    assert os.listdir(tmp_path) == []


def test_a_half_pack_left_by_an_older_version_is_downloaded_again(tmp_path, pack):
    """os.path.exists() kept a cut-off file there for good."""
    (tmp_path / "tur.traineddata").write_bytes(PACK[:100])

    install_tesseract.install_turkish_pack(str(tmp_path))

    assert (tmp_path / "tur.traineddata").read_bytes() == PACK


@pytest.fixture
def protected(monkeypatch, tmp_path):
    """tessdata needs administrator rights; returns what the elevated copy got."""
    tessdata = tmp_path / "Program Files" / "Tesseract-OCR" / "tessdata"
    tessdata.mkdir(parents=True)
    real = download.download_verified

    def guarded(url, destination, *args, **kwargs):
        if str(tessdata) in str(destination):
            raise PermissionError(13, "Access is denied", destination)
        return real(url, destination, *args, **kwargs)
    monkeypatch.setattr(download, "download_verified", guarded)
    copies = []
    monkeypatch.setattr(install_tesseract, "_copy_as_administrator", lambda src, dst: copies.append((src, dst)))
    return tessdata, copies


def test_a_refused_administrator_copy_is_an_error(protected, pack):
    tessdata, copies = protected

    with pytest.raises(RuntimeError, match="tessdata"):
        install_tesseract.install_turkish_pack(str(tessdata))

    assert len(copies) == 1
    assert not os.path.exists(copies[0][0])        # the staged copy is cleaned up


def test_the_install_reports_the_failed_copy_instead_of_success(protected, pack, monkeypatch):
    tessdata, _copies = protected
    monkeypatch.setattr(install_tesseract.subprocess, "run",
                        lambda *a, **k: type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})())
    monkeypatch.setattr(install_tesseract, "_installed_dir", lambda: str(tessdata.parent))
    outcome = []

    install_tesseract.install_tesseract_now(on_success=lambda: outcome.append("ok"),
                                            on_error=lambda message: outcome.append(message))

    assert outcome and outcome[0] != "ok"
    assert _("err_tesseract_lang_copy").format(folder=str(tessdata)) in outcome[0]


def test_a_successful_administrator_copy_is_accepted(protected, pack, monkeypatch):
    import shutil
    tessdata, _copies = protected
    monkeypatch.setattr(install_tesseract, "_copy_as_administrator", lambda src, dst: shutil.copyfile(src, dst))

    install_tesseract.install_turkish_pack(str(tessdata))

    assert (tessdata / "tur.traineddata").read_bytes() == PACK


def test_paths_never_reach_the_command_line(monkeypatch):
    """A quote in the user name (O'Brien) broke the copy command."""
    seen = []
    monkeypatch.setattr(install_tesseract.subprocess, "run", lambda args, **kwargs: seen.append(args))
    source = r"C:\Users\O'Brien\AppData\Local\Temp\tur.traineddata"
    target = r"C:\Program Files\Tesseract-OCR\tessdata\tur.traineddata"

    install_tesseract._copy_as_administrator(source, target)

    (args,) = seen
    assert "O'Brien" not in " ".join(args) and "Program Files" not in " ".join(args)
    encoded = args[-1].split("'-EncodedCommand','")[1].split("'")[0]
    script = base64.b64decode(encoded).decode("utf-16-le")
    assert r"'C:\Users\O''Brien\AppData\Local\Temp\tur.traineddata'" in script
    assert f"'{target}'" in script
