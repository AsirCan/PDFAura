"""
Scanner session persistence
───────────────────────────
Keeps the Belge Tarayıcı work (photos, corners, rotation, order, scan mode,
output path) on disk so it survives an app restart.

Layout (under %APPDATA%\\PDFAura\\scanner_session\\):
    .lock               held for the lifetime of the owning PDF Aura process
    session.json        metadata, written atomically (.tmp + os.replace)
    images/<uid>.png    lossless copy of each page's ORIGINAL (unrotated) pixels

All writes happen on ONE background thread, in the order they were queued, so
an image is always on disk before the session.json that references it.
"""

import atexit
import json
import logging
import os
import queue
import re
import shutil
import threading
import time

import cv2

from src.core.document_scanner import imread_unicode

SESSION_VERSION = 1
SESSION_FILE = "session.json"
IMAGES_DIR = "images"
LOCK_FILE = ".lock"
# Level 1 = fastest zlib setting; PNG stays lossless at any level.
PNG_PARAMS = [cv2.IMWRITE_PNG_COMPRESSION, 1]
UID_RE = re.compile(r"^[0-9a-f]{32}$")


def _replace_with_retry(src, dst, attempts=5):
    # Antivirus / search indexer can hold a file for a few ms on Windows.
    for i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(0.05 * (i + 1))


def _try_lock(path):
    """Return an open handle holding an exclusive lock, or None if another process owns it."""
    try:
        fh = open(path, "a+b")
    except OSError:
        return None
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError:
        fh.close()
        return None


class ScannerSessionStore:
    """Disk side of the scanner session. Thread-safe; never touches Tk."""

    def __init__(self, session_dir, enabled=True, on_error=None):
        self.session_dir = session_dir
        self.images_dir = os.path.join(session_dir, IMAGES_DIR)
        self.meta_path = os.path.join(session_dir, SESSION_FILE)
        self.on_error = on_error          # called from the WORKER thread with a message
        self.enabled = False
        self.locked_by_other = False
        self._lock_fh = None
        self._queue = queue.Queue()

        if not enabled:
            return
        try:
            os.makedirs(session_dir, exist_ok=True)
        except OSError as exc:
            logging.error("Scanner session dir could not be created: %s", exc)
            return

        self._lock_fh = _try_lock(os.path.join(session_dir, LOCK_FILE))
        if self._lock_fh is None:
            # A second PDF Aura instance: never write, or the two would delete
            # each other's images during orphan cleanup.
            self.locked_by_other = True
            return

        self.enabled = True
        threading.Thread(target=self._run, name="ScannerSessionWriter", daemon=True).start()
        atexit.register(self.flush, 3.0)

    # ── paths ────────────────────────────────────────────────────────────

    def image_path(self, uid):
        return os.path.join(self.images_dir, f"{uid}.png")

    # ── read side (synchronous) ──────────────────────────────────────────

    def load_meta(self):
        """Return the stored metadata dict, or None when there is nothing usable."""
        if not self.enabled or not os.path.isfile(self.meta_path):
            return None

        raw = None
        for attempt in range(3):
            try:
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    raw = f.read()
                break
            except OSError as exc:
                if attempt == 2:
                    # Probably locked, not broken: keep the files and stop
                    # persisting for this run so nothing overwrites them.
                    logging.error("Scanner session could not be read, persistence off for this run: %s", exc)
                    self.enabled = False
                    return None
                time.sleep(0.1)

        try:
            meta = json.loads(raw)
        except ValueError as exc:
            logging.warning("Scanner session is corrupt, discarding: %s", exc)
            self._quarantine()
            return None

        if not isinstance(meta, dict) or not isinstance(meta.get("pages"), list):
            logging.warning("Scanner session has an unexpected shape, discarding")
            self._quarantine()
            return None

        version = meta.get("version")
        if isinstance(version, int) and version > SESSION_VERSION:
            # Written by a newer PDF Aura: don't touch it.
            logging.warning("Scanner session version %s is newer than supported %s", version, SESSION_VERSION)
            self.enabled = False
            return None
        if version != SESSION_VERSION:
            self._quarantine()
            return None
        return meta

    def read_image(self, uid):
        """Decode one stored page image (safe to call from a worker thread)."""
        if not isinstance(uid, str) or not UID_RE.fullmatch(uid):
            return None
        path = self.image_path(uid)
        if not os.path.isfile(path):
            return None
        return imread_unicode(path)

    def _quarantine(self):
        # Only called from load_meta, before any write is queued.
        try:
            _replace_with_retry(self.meta_path, self.meta_path + ".corrupt")
        except OSError:
            pass
        shutil.rmtree(self.images_dir, ignore_errors=True)

    # ── write side (asynchronous) ────────────────────────────────────────

    def save(self, meta, images):
        """Queue a full snapshot.

        meta   – JSON-ready dict (plain Python types only).
        images – {uid: ndarray} for EVERY page; only files missing on disk are
                 encoded, so passing all of them is cheap and self-healing.
        """
        if self.enabled:
            self._queue.put(("save", meta, images))

    def clear(self):
        if self.enabled:
            self._queue.put(("clear", None, None))

    def flush(self, timeout=10.0):
        """Block until everything queued so far is on disk. Returns False on timeout."""
        if not self.enabled:
            return True
        done = threading.Event()
        self._queue.put(("flush", done, None))
        return done.wait(timeout)

    def _run(self):
        while True:
            op, a, b = self._queue.get()
            try:
                if op == "save":
                    self._do_save(a, b)
                elif op == "clear":
                    self._do_clear()
                elif op == "flush":
                    a.set()
            except Exception as exc:
                logging.exception("Scanner session write failed")
                if self.on_error:
                    try:
                        self.on_error(str(exc))
                    except Exception:
                        pass

    def _do_save(self, meta, images):
        os.makedirs(self.images_dir, exist_ok=True)
        for uid, img in images.items():
            path = self.image_path(uid)
            if os.path.isfile(path):
                continue                       # written once, never rewritten
            ok, buf = cv2.imencode(".png", img, PNG_PARAMS)
            if not ok:
                raise IOError(f"PNG encode failed for page {uid}")
            tmp = path + ".tmp"
            buf.tofile(tmp)
            _replace_with_retry(tmp, path)

        tmp = self.meta_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        _replace_with_retry(tmp, self.meta_path)

        self._remove_orphans({p["uid"] for p in meta["pages"]})

    def _remove_orphans(self, keep):
        try:
            names = os.listdir(self.images_dir)
        except FileNotFoundError:
            return
        for name in names:
            if name.endswith(".tmp") or name.split(".", 1)[0] not in keep:
                try:
                    os.remove(os.path.join(self.images_dir, name))
                except OSError:
                    pass

    def _do_clear(self):
        # session.json first: a crash halfway must not leave metadata that
        # points at deleted images.
        for name in (SESSION_FILE, SESSION_FILE + ".tmp"):
            try:
                os.remove(os.path.join(self.session_dir, name))
            except FileNotFoundError:
                pass
        shutil.rmtree(self.images_dir, ignore_errors=True)
