"""Downloading a file the app will load or install: all of it, and only the
expected file, or nothing.

The scanner model came from a HuggingFace branch, so whatever the repository
held that day was loaded into ONNX Runtime, and the Tesseract language pack
was written straight to its final place: a cut connection left half a file
that was never downloaded again (#35). Every such download now names a fixed
revision and the exact size and hash of the file there; the bytes go to a
temporary file next to the destination and are moved into place only when
both match.
"""
import hashlib
import os
import urllib.request

from src.core.lang_manager import _
from src.core.output_paths import atomic_output

CHUNK = 1024 * 128


class DownloadError(RuntimeError):
    """The download failed, or what arrived was not the expected file."""


def _hasher(size, sha256=None, git_sha1=None):
    """A hash object for the expected digest. git_sha1 is the blob id GitHub
    lists for a file in a repository: SHA-1 over "blob <size>\\0" + content."""
    if sha256:
        return hashlib.sha256(), sha256.lower()
    if git_sha1:
        digest = hashlib.sha1()
        digest.update(b"blob %d\0" % size)
        return digest, git_sha1.lower()
    raise DownloadError(_("err_download_no_checksum"))


def file_matches(path, size, sha256=None, git_sha1=None):
    """True if *path* is exactly the expected file."""
    try:
        if os.path.getsize(path) != size:
            return False
        digest, expected = _hasher(size, sha256, git_sha1)
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(CHUNK), b""):
                digest.update(chunk)
        return digest.hexdigest() == expected
    except OSError:
        return False


def download_verified(url, destination, size, sha256=None, git_sha1=None, progress=None, timeout=30,
                      user_agent="PDFAura/1.0"):
    """Download *url* to *destination* if it is exactly *size* bytes with the
    given hash; raise DownloadError otherwise, leaving no file behind.

    *progress(done, total)* is called as bytes arrive; whatever it raises (a
    cancel) stops the download and is raised as it is. More bytes than
    expected stop it at once.
    """
    digest, expected = _hasher(size, sha256, git_sha1)
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with atomic_output(destination) as temp_path:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response, open(temp_path, "wb") as handle:
                announced = int(response.headers.get("Content-Length", 0) or 0)
                if announced and announced != size:
                    raise DownloadError(_("err_download_wrong_size").format(size=announced, expected=size))
                done = 0
                while True:
                    chunk = response.read(CHUNK)
                    if not chunk:
                        break
                    done += len(chunk)
                    if done > size:
                        raise DownloadError(_("err_download_wrong_size").format(size=done, expected=size))
                    digest.update(chunk)
                    handle.write(chunk)
                    if progress:
                        progress(done, size)
        except DownloadError:
            raise
        except OSError as exc:
            # Includes urllib's URLError and HTTPError.
            raise DownloadError(str(exc)) from exc
        if done != size:
            raise DownloadError(_("err_download_wrong_size").format(size=done, expected=size))
        if digest.hexdigest() != expected:
            raise DownloadError(_("err_download_corrupt"))
    return destination
