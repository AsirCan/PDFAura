"""Priority 7 automatic updates: release checks, verified downloads, silent
installs.

No real network here: urlopen answers from memory, as in test_downloads.py.
"""
import hashlib
import io
import json
import os
import urllib.error
import urllib.request

import pytest

from src.core import updater
from src.core.config_manager import ConfigManager
from src.core.updater import (
    UpdateCancelled,
    UpdateError,
    check_for_update,
    compare_versions,
    download_update,
    run_installer,
)

API = "https://example.invalid/releases/latest"
INSTALLER_URL = "https://example.invalid/PDFAura-Setup.exe"
CHECKSUM_URL = "https://example.invalid/PDFAura-Setup.exe.sha256"
INSTALLER = b"innosetup installer bytes " * 400


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class Response(io.BytesIO):
    def __init__(self, body, length=None):
        super().__init__(body)
        self.headers = {"Content-Length": str(len(body) if length is None else length)}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def network(monkeypatch):
    """network(url, body) serves *body*; anything else is offline."""
    served = {}
    calls = []

    def urlopen(request, timeout=None):
        url = getattr(request, "full_url", str(request))
        calls.append(url)
        if url not in served:
            raise urllib.error.URLError("no route to host")
        body, length = served[url]
        return Response(body, length)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)

    def serve(url, body, length=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        served[url] = (body, length)

    serve.calls = calls
    return serve


def release(tag="v2.2.0", body="## What is new\n- Faster merge", size=None,
            installer=True, checksum=True):
    assets = []
    if installer:
        assets.append({
            "name": "PDFAura-Setup.exe",
            "browser_download_url": INSTALLER_URL,
            "size": len(INSTALLER) if size is None else size,
        })
    if checksum:
        assets.append({
            "name": "PDFAura-Setup.exe.sha256",
            "browser_download_url": CHECKSUM_URL,
            "size": 100,
        })
    return json.dumps({
        "tag_name": tag,
        "body": body,
        "assets": assets,
    })


# ── Version comparison ────────────────────────────────────────────────────

@pytest.mark.parametrize("left, right", [
    ("2.2.0", "2.1.0"),
    ("2.10.0", "2.9.9"),
    ("v2.1.1", "2.1"),
    ("2.1.0", "2.1.0-beta"),
    ("2.1.0-beta.2", "2.1.0-beta.1"),
])
def test_newer_semantic_versions_compare_greater(left, right):
    assert compare_versions(left, right) == 1
    assert compare_versions(right, left) == -1


def test_equal_versions_with_and_without_v_and_padding():
    assert compare_versions("v2.1", "2.1.0") == 0


# ── Checking for a release ────────────────────────────────────────────────

def test_a_newer_release_is_offered_with_notes_and_installer(network):
    network(API, release())

    result = check_for_update("2.1", url=API)

    assert result["available"] is True
    assert result["latest_version"] == "2.2.0"
    assert result["notes"] == "## What is new\n- Faster merge"
    assert result["download_url"] == INSTALLER_URL
    assert result["size"] == len(INSTALLER)
    assert result["checksum_url"] == CHECKSUM_URL


def test_the_current_or_an_older_release_is_not_offered(network):
    network(API, release(tag="v2.1.0"))

    assert check_for_update("2.1.0", url=API)["available"] is False


def test_offline_is_no_update_not_an_exception(network):
    result = check_for_update("2.1.0", url=API)

    assert result["available"] is False
    assert result["latest_version"] == ""
    assert result["download_url"] == ""


def test_a_broken_answer_is_no_update(network):
    network(API, "this is not json")

    assert check_for_update("2.1.0", url=API)["available"] is False


def test_a_release_without_an_asset_still_reports_the_version(network):
    network(API, release(installer=False, checksum=False))

    result = check_for_update("2.0", url=API)

    assert result["available"] is True
    assert result["download_url"] == ""
    assert result["size"] == 0


def test_the_app_version_is_read_from_setup_iss():
    assert updater.app_version() == "2.1"


# ── Downloading it ────────────────────────────────────────────────────────

def test_download_is_checked_against_its_sha256(tmp_path, network):
    network(INSTALLER_URL, INSTALLER)
    seen = []
    info = {
        "download_url": INSTALLER_URL,
        "name": "PDFAura-Setup.exe",
        "size": len(INSTALLER),
        "sha256": sha256(INSTALLER),
    }

    path = download_update(info, str(tmp_path), progress=lambda done, total: seen.append(done))

    assert open(path, "rb").read() == INSTALLER
    assert seen and seen[-1] == len(INSTALLER)
    assert os.listdir(tmp_path) == ["PDFAura-Setup.exe"]


def test_a_checksum_asset_is_read_and_used(tmp_path, network):
    network(INSTALLER_URL, INSTALLER)
    network(CHECKSUM_URL, f"{sha256(INSTALLER)}  PDFAura-Setup.exe\n")
    info = {
        "download_url": INSTALLER_URL,
        "name": "PDFAura-Setup.exe",
        "size": len(INSTALLER),
        "checksum_url": CHECKSUM_URL,
    }

    path = download_update(info, str(tmp_path))

    assert open(path, "rb").read() == INSTALLER


def test_a_wrong_download_leaves_nothing(tmp_path, network):
    network(INSTALLER_URL, INSTALLER)
    info = {
        "download_url": INSTALLER_URL,
        "name": "PDFAura-Setup.exe",
        "size": len(INSTALLER),
        "sha256": sha256(b"some other installer"),
    }

    with pytest.raises(UpdateError):
        download_update(info, str(tmp_path))

    assert os.listdir(tmp_path) == []


def test_a_half_download_is_refused(tmp_path, network):
    network(INSTALLER_URL, INSTALLER[:100], length=len(INSTALLER))
    info = {
        "download_url": INSTALLER_URL,
        "name": "PDFAura-Setup.exe",
        "size": len(INSTALLER),
        "sha256": sha256(INSTALLER),
    }

    with pytest.raises(UpdateError):
        download_update(info, str(tmp_path))

    assert os.listdir(tmp_path) == []


def test_cancel_stops_the_download_and_removes_the_part_file(tmp_path, network):
    large = b"x" * (updater.CHUNK * 3)
    network(INSTALLER_URL, large)
    cancelled = {"value": False}

    def progress(done, total):
        cancelled["value"] = True

    info = {
        "download_url": INSTALLER_URL,
        "name": "PDFAura-Setup.exe",
        "size": len(large),
    }

    with pytest.raises((UpdateCancelled, updater.CancelledError)):
        download_update(info, str(tmp_path), progress=progress,
                        cancel=lambda: cancelled["value"])

    assert os.listdir(tmp_path) == []


# ── Installing it ─────────────────────────────────────────────────────────

@pytest.fixture
def installer(tmp_path):
    path = tmp_path / "PDFAura-Setup.exe"
    path.write_bytes(INSTALLER)
    return str(path)


def test_silent_install_uses_the_inno_setup_flags(installer, monkeypatch):
    seen = {}
    monkeypatch.setattr(updater.subprocess, "Popen",
                        lambda args, **kwargs: seen.update(args=args, kwargs=kwargs) or "process")

    assert run_installer(installer, silent=True) == "process"
    assert seen["args"] == [installer, "/VERYSILENT", "/SUPPRESSMSGBOXES"]


def test_a_normal_install_opens_the_wizard(installer, monkeypatch):
    seen = {}
    monkeypatch.setattr(updater.subprocess, "Popen",
                        lambda args, **kwargs: seen.update(args=args) or "process")

    run_installer(installer)

    assert seen["args"] == [installer]


def test_a_missing_installer_is_refused(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_installer(str(tmp_path / "missing.exe"))


# ── Settings ──────────────────────────────────────────────────────────────

def test_update_settings_default_to_check_but_not_silent(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    manager = ConfigManager()

    assert manager.get("auto_check") is True
    assert manager.get("silent_update") is False
