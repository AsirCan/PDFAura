"""Checking for and installing PDF Aura updates.

The release information comes from the GitHub releases API. Everything here
has to survive a machine that is offline or behind a proxy: a failed check
returns "no update" instead of raising, and a download that does not arrive
whole is thrown away before the installer ever sees it.
"""
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request

from src.core.task_manager import CancelledError

logger = logging.getLogger(__name__)

GITHUB_OWNER = "AsirCan"
GITHUB_REPO = "PDFAura"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

USER_AGENT = "PDFAura-Updater/1.0"
CHUNK = 1024 * 128
CHECKSUM_SUFFIXES = (
    ".sha256", ".sha256sum", ".sha256.txt", ".sha256sums", ".sha256sums.txt",
    ".checksums", ".checksums.txt",
)
CHECKSUM_NAMES = (
    "sha256sums.txt", "sha256sums", "sha256.txt", "checksums.txt", "checksums",
)

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class UpdateError(RuntimeError):
    """The update could not be downloaded or verified."""


class UpdateCancelled(CancelledError):
    """The user stopped the download."""


# ── Versions ──────────────────────────────────────────────────────────────

def app_version():
    """AppVersion from setup.iss, the one place the version is written."""
    try:
        with open(os.path.join(APP_ROOT, "setup.iss"), encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("AppVersion="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def _clean_version(value):
    """'v2.1.0' -> '2.1.0'; the app itself stores it without the prefix."""
    text = str(value or "").strip()
    return text[1:] if text[:1] in ("v", "V") else text


def parse_version(value):
    """A comparable (core, prerelease) pair for a semantic version string.

    Missing parts count as zero, so "2.1" and "2.1.0" are the same version.
    A prerelease ("2.1.0-beta.1") sorts below its release.
    """
    text = _clean_version(value).split("+", 1)[0]
    core, _separator, prerelease = text.partition("-")
    numbers = []
    for part in core.split("."):
        match = re.match(r"\d+", part)
        numbers.append(int(match.group()) if match else 0)
    while len(numbers) < 3:
        numbers.append(0)
    pre = tuple(
        int(piece) if piece.isdigit() else piece.lower()
        for piece in prerelease.split(".") if piece != ""
    )
    return tuple(numbers), pre


def _compare_prerelease(left, right):
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    for a, b in zip(left, right):
        if a == b:
            continue
        # A numeric identifier always sorts below an alphanumeric one.
        if isinstance(a, int) and isinstance(b, int):
            return -1 if a < b else 1
        if isinstance(a, int):
            return -1
        if isinstance(b, int):
            return 1
        return -1 if a < b else 1
    if len(left) == len(right):
        return 0
    return -1 if len(left) < len(right) else 1


def compare_versions(left, right):
    """-1, 0 or 1, comparing two semantic versions (a leading 'v' is fine)."""
    left_core, left_pre = parse_version(left)
    right_core, right_pre = parse_version(right)
    width = max(len(left_core), len(right_core))
    left_core += (0,) * (width - len(left_core))
    right_core += (0,) * (width - len(right_core))
    if left_core != right_core:
        return -1 if left_core < right_core else 1
    return _compare_prerelease(left_pre, right_pre)


def is_newer(candidate, current):
    return compare_versions(candidate, current) > 0


# ── Checking for a release ────────────────────────────────────────────────

def _empty_result():
    return {
        "available": False,
        "latest_version": "",
        "notes": "",
        "download_url": "",
        "size": 0,
    }


def _asset_url(asset):
    return str(asset.get("browser_download_url") or asset.get("url") or "")


def _pick_installer_asset(assets):
    """The setup .exe when there is one, otherwise the most likely file."""
    def score(asset):
        name = str(asset.get("name") or "").lower()
        if not _asset_url(asset):
            return -1
        if name.endswith(".exe"):
            value = 100
            if "setup" in name or "installer" in name:
                value += 20
            if name == "pdfaura-setup.exe":
                value += 10
            return value
        if name.endswith((".msi", ".msix")):
            return 80
        return 10

    usable = [asset for asset in assets if score(asset) >= 0]
    return max(usable, key=score) if usable else None


def _is_checksum_asset(name):
    lowered = name.lower()
    return lowered in CHECKSUM_NAMES or lowered.endswith(CHECKSUM_SUFFIXES)


def _find_checksum_asset(assets, installer):
    installer_name = str((installer or {}).get("name") or "").lower()
    candidates = [asset for asset in assets
                  if _is_checksum_asset(str(asset.get("name") or "")) and _asset_url(asset)]
    if not candidates:
        return None
    # A per-file ".exe.sha256" next to the installer is the most precise.
    candidates.sort(key=lambda asset: (
        installer_name not in str(asset.get("name") or "").lower(),
        str(asset.get("name") or "").lower() not in CHECKSUM_NAMES,
    ))
    return candidates[0]


def _asset_sha256(asset):
    digest = str((asset or {}).get("digest") or "")
    match = re.match(r"sha256:([a-fA-F0-9]{64})", digest)
    return match.group(1).lower() if match else ""


def check_for_update(current_version=None, url=None, timeout=5):
    """Ask GitHub for the latest release and compare it with this build.

    Returns a dict with ``available``, ``latest_version``, ``notes`` (the
    release body as markdown), ``download_url`` and ``size``. It never
    raises: offline, a timeout or a malformed answer all mean no update.
    """
    result = _empty_result()
    if current_version is None:
        current_version = app_version()
    try:
        request = urllib.request.Request(
            url or RELEASES_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
        data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("release information is not an object")

        tag = str(data.get("tag_name") or data.get("name") or "").strip()
        if not tag:
            raise ValueError("release has no version tag")

        assets = [asset for asset in (data.get("assets") or []) if isinstance(asset, dict)]
        installer = _pick_installer_asset(assets)
        checksum = _find_checksum_asset(assets, installer)

        result.update({
            "available": is_newer(tag, current_version),
            "latest_version": _clean_version(tag),
            "notes": str(data.get("body") or ""),
        })
        if installer:
            result["download_url"] = _asset_url(installer)
            result["size"] = int(installer.get("size") or 0)
            if installer.get("name"):
                result["name"] = str(installer["name"])
            digest = _asset_sha256(installer)
            if digest:
                result["sha256"] = digest
        if checksum:
            result["checksum_url"] = _asset_url(checksum)
            if checksum.get("name"):
                result["checksum_name"] = str(checksum["name"])
        return result
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError,
            ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
        # Offline is an ordinary state for this app, not an error dialog.
        logger.info("Update check failed: %s", exc)
        return result
    except Exception as exc:                     # a proxied or broken response
        logger.warning("Unexpected update check failure: %s", exc)
        return result


# ── Downloading it ────────────────────────────────────────────────────────

def _validate_url(url: str) -> str:
    from urllib.parse import urlsplit
    parsed = urlsplit(str(url or ""))
    if parsed.scheme.lower() not in ("https", "http"):
        raise UpdateError(f"Untrusted URL scheme: {parsed.scheme}")
    return url


def _safe_filename(name, fallback="PDFAura-Setup.exe"):
    name = os.path.basename(str(name or "").replace("\\", "/")).strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = re.sub(r"\.{2,}", ".", name).strip(" .-_")
    if not name or name in (".", "..") or not name.lower().endswith((".exe", ".msi", ".msix")):
        return fallback
    return name


def _cancelled(cancel):
    if cancel is None:
        return False
    if callable(cancel):
        return bool(cancel())
    if hasattr(cancel, "is_set"):
        return bool(cancel.is_set())
    return bool(cancel)


def _sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checksum_from_text(text, filename):
    """The sha256 for *filename* in a SHA256SUMS-style file, or ""."""
    entries = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([a-fA-F0-9]{64})\s+\*?(.+?)\s*$", line)
        if match:
            entries.append((match.group(1).lower(),
                            os.path.basename(match.group(2).strip().replace("\\", "/"))))
            continue
        bare = re.fullmatch(r"([a-fA-F0-9]{64})", line)
        if bare:
            entries.append((bare.group(1).lower(), ""))
    wanted = os.path.basename(str(filename or "")).lower()
    for digest, name in entries:
        if name and name.lower() == wanted:
            return digest
    bare_entries = [digest for digest, name in entries if not name]
    if bare_entries:
        return bare_entries[0]
    return entries[0][0] if len(entries) == 1 else ""


def _direct_sha256(info):
    match = re.search(r"\b([a-fA-F0-9]{64})\b", str(info.get("sha256") or ""))
    return match.group(1).lower() if match else ""


def _download_checksum(url, filename, timeout):
    _validate_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", errors="replace")
    return _checksum_from_text(text, filename)


def download_update(info, dest_dir, progress=None, cancel=None, timeout=30):
    """Download the installer named by check_for_update() into *dest_dir*.

    ``progress(done, total)`` is called while the bytes arrive and ``cancel``
    may be a callable (or an Event) checked before each chunk. When the
    release carries a sha256 (directly or as a checksum asset) the file is
    verified before it is moved into place; a broken download leaves nothing
    behind. Returns the path of the downloaded file.
    """
    url = str(info.get("download_url") or info.get("browser_download_url") or "")
    if not url:
        raise UpdateError("Update information has no download URL")
    _validate_url(url)
    if _cancelled(cancel):
        raise UpdateCancelled("Update download cancelled")

    os.makedirs(dest_dir, exist_ok=True)
    filename = _safe_filename(info.get("name") or os.path.basename(url.split("?", 1)[0]))
    target = os.path.join(dest_dir, filename)
    dest_dir_abs = os.path.abspath(dest_dir)
    target_abs = os.path.abspath(target)
    if not target_abs.startswith(dest_dir_abs + os.sep) and target_abs != dest_dir_abs:
        raise UpdateError("Target path escapes destination directory")
    expected_size = int(info.get("size") or 0)

    handle_fd, temp_path = tempfile.mkstemp(prefix=".pdfaura-update-", suffix=".part", dir=dest_dir)
    os.close(handle_fd)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        done = 0
        announced = 0
        with urllib.request.urlopen(request, timeout=timeout) as response, open(temp_path, "wb") as handle:
            announced = int(response.headers.get("Content-Length", 0) or 0)
            if expected_size and announced and expected_size != announced:
                raise UpdateError(
                    f"Installer is {announced} bytes, expected {expected_size}")
            total = expected_size or announced
            while True:
                if _cancelled(cancel):
                    raise UpdateCancelled("Update download cancelled")
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                done += len(chunk)
                if expected_size and done > expected_size:
                    raise UpdateError("Installer is larger than the release says")
                handle.write(chunk)
                if progress:
                    progress(done, total)

        if expected_size and done != expected_size:
            raise UpdateError(f"Installer is {done} bytes, expected {expected_size}")
        if not expected_size and announced and done != announced:
            raise UpdateError(f"Installer is {done} bytes, expected {announced}")

        expected_hash = _direct_sha256(info)
        checksum_url = str(info.get("checksum_url") or info.get("sha256_url") or "")
        if not expected_hash and checksum_url:
            try:
                expected_hash = _download_checksum(checksum_url, filename, timeout)
            except Exception as exc:
                raise UpdateError(f"Checksum could not be read: {exc}") from exc
        if expected_hash and _sha256_of(temp_path) != expected_hash:
            raise UpdateError("Downloaded installer does not match its sha256")

        os.replace(temp_path, target)
        return target
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise


# ── Installing it ─────────────────────────────────────────────────────────

def run_installer(path, silent=False):
    """Start an Inno Setup installer and return its Popen.

    Silent mode is the flags the package was built to accept:
    ``/VERYSILENT /SUPPRESSMSGBOXES``. Without it the installer shows its
    normal wizard.
    """
    path = os.fspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    path = os.path.abspath(path)
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".exe", ".msi", ".msix"):
        raise UpdateError(f"Refusing to execute non-installer binary: {path}")

    args = [path]
    if silent:
        args.extend(["/VERYSILENT", "/SUPPRESSMSGBOXES"])

    kwargs = {}
    if os.name == "nt" and silent:
        try:
            from src.utils.process_helper import CREATE_NO_WINDOW
            if CREATE_NO_WINDOW:
                kwargs["creationflags"] = CREATE_NO_WINDOW
        except Exception:
            pass
    return subprocess.Popen(args, **kwargs)
