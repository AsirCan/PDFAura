"""The document scanner for the web window.

The page cannot hold the photos (numpy arrays), so this board owns the
page list and its photos, and the page tells it what the user did -- add, remove, move, rotate, drag a
corner (sent once, when the handle is let go), rename, pick a mode or a
place to save, export. The page draws from small descriptions (state())
and asks for pictures by URL: /scan/<token>/<uid>/<kind>?v=<version>,
where the version changes whenever the page's picture would.

Corner detection and the session restore run on threads; when they
change something the board sends a "scanner" event with the whole state,
which holds no pixels and stays small.

The model itself (rotation, detection, session format, export) is
src/app/scanner.py.
"""
import os
import threading
from types import SimpleNamespace

from src.app import scanner
from src.core.lang_manager import _

PHOTO_MAX = 2000          # px, long side of the photo the editor shows
JPEG_QUALITY = 88
SAVE_DELAY_S = 0.4        # a burst of changes is saved once


def _notice(title_key, message, tone="info"):
    return {"tone": tone, "title": _(title_key), "message": message}


class ScannerBoard:
    def __init__(self, emit, store=None):
        """``emit(name, data)`` sends an event to the page; ``store`` is a
        ScannerSessionStore (the user's session folder when None)."""
        self._emit = emit
        self._lock = threading.RLock()
        self._store = store
        self.pages = []
        self.current = -1
        self.mode = scanner.DEFAULT_MODE
        self.output = ""
        self._versions = {}
        self._detecting = False
        self._exporting = False
        self._restoring = False
        self._restore_started = False
        self._detect_run = 0
        self._save_timer = None
        self._rev = 0                 # bumped on every change; guards the clear after an export

    # ── State the page draws from ─────────────────────────────────────
    @property
    def store(self):
        if self._store is None:
            from src.core.config_manager import cfg
            from src.core.scanner_session import ScannerSessionStore
            self._store = ScannerSessionStore(cfg.scanner_session_dir,
                                              enabled=cfg.get("scanner_session_enabled", True),
                                              on_error=self._session_error)
        return self._store

    @property
    def busy(self):
        if self._restoring:
            return "restoring"
        if self._exporting:
            return "exporting"
        if self._detecting:
            return "detecting"
        return None

    def state(self, notice=None, progress=None):
        with self._lock:
            return {
                "pages": [self._describe(page) for page in self.pages],
                "current": self.current,
                "mode": self.mode,
                "output": self.output,
                "busy": self.busy,
                "notice": notice,
                "progress": progress,
            }

    def _describe(self, page):
        height, width = page.display_shape
        return {"uid": page.uid, "label": page.label, "name": os.path.basename(page.path or ""),
                "width": int(width), "height": int(height), "rotation": page.rotation,
                "corners": [[int(round(x)), int(round(y))] for x, y in page.corners],
                "version": self._versions.get(page.uid, 0)}

    def _send(self, notice=None, progress=None):
        self._emit("scanner", self.state(notice, progress))

    def _find(self, uid):
        for index, page in enumerate(self.pages):
            if page.uid == uid:
                return index, page
        return -1, None

    def _changed(self, page=None):
        """Something worth saving changed (and, for ``page``, its picture)."""
        if page is not None:
            self._versions[page.uid] = self._versions.get(page.uid, 0) + 1
        self._rev += 1
        self._schedule_save()

    def _refused(self):
        """While a detection, export or restore depends on the page list, it
        must not change (#12: the PDF once had other pages than the screen)."""
        return self.state(_notice("scanner_crop_area", _("scanner_detect_busy")))

    # ── Pages ─────────────────────────────────────────────────────────
    def add(self, paths):
        with self._lock:
            if self.busy:
                return self._refused()
            added = []
            for path in paths:
                if os.path.splitext(path)[1].lower() not in scanner.IMAGE_EXTENSIONS:
                    continue
                page = scanner.load_photo(path)
                if page is None:
                    continue
                self.pages.append(page)
                self._versions[page.uid] = 0
                added.append((page, path))
            if not added:
                return self.state()
            # Jump to the first new photo so its corners can be checked.
            self.current = self.pages.index(added[0][0])
            if not self.output:
                from src.app.tools import suggest_output
                self.output = suggest_output("scanner", self.pages[0].path)
            self._changed()
            jobs = [scanner.detection_job(page, path) for page, path in added]
            self._begin_detection(jobs)
            return self.state(_notice("scanner_crop_area",
                                      _("scanner_page_count").format(count=len(self.pages))))

    def remove(self, uid):
        with self._lock:
            if self.busy:
                return self._refused()
            index, page = self._find(uid)
            if page is None:
                return self.state()
            del self.pages[index]
            self._versions.pop(uid, None)
            self.current = min(self.current, len(self.pages) - 1) if self.pages else -1
            self._changed()
            return self.state()

    def clear(self):
        """Drop every page and the saved session, to start a new document."""
        with self._lock:
            if self.busy:
                return self._refused()
            self.pages.clear()
            self._versions.clear()
            self.current = -1
            self.output = ""
            self._rev += 1
            self._cancel_save()
            self.store.clear()
            return self.state(_notice("scanner_crop_area", _("scanner_select_hint")))

    def select(self, index):
        # Not a change worth a save of its own; the next one keeps it.
        with self._lock:
            if 0 <= index < len(self.pages):
                self.current = index
            return self.state()

    def move(self, uid, index):
        """Put the page at ``index`` of the list (clamped)."""
        with self._lock:
            source, page = self._find(uid)
            if page is None:
                return self.state()
            target = max(0, min(len(self.pages) - 1, int(index)))
            if target != source:
                self.pages.insert(target, self.pages.pop(source))
                self.current = target
                self._changed()
            return self.state()

    def rename(self, uid, label):
        with self._lock:
            _index, page = self._find(uid)
            if page is not None:
                label = scanner.clean_label(label)
                if label != page.label:
                    page.label = label
                    self._changed()
            return self.state()

    def rotate(self, uid, step):
        with self._lock:
            if self.busy:
                return self._refused()
            _index, page = self._find(uid)
            if page is not None and step in (90, -90):
                scanner.rotate(page, step)
                self._changed(page)
            return self.state()

    def set_corners(self, uid, corners):
        with self._lock:
            if self.busy:
                return self._refused()
            _index, page = self._find(uid)
            if page is not None and scanner.valid_corners(corners):
                height, width = page.display_shape
                page.corners = [(min(max(int(round(x)), 0), width), min(max(int(round(y)), 0), height))
                                for x, y in corners]
                self._changed(page)
            return self.state()

    def reset(self, uid):
        with self._lock:
            if self.busy:
                return self._refused()
            _index, page = self._find(uid)
            if page is not None:
                page.reset_corners()
                self._changed(page)
            return self.state()

    def detect(self, uid):
        with self._lock:
            if self.busy:
                return self._refused()
            _index, page = self._find(uid)
            if page is not None:
                self._begin_detection([scanner.detection_job(page, self._source_path(page))])
            return self.state()

    def set_mode(self, mode):
        with self._lock:
            if mode in dict(scanner.MODES) and mode != self.mode:
                self.mode = mode
                self._changed()
            return self.state()

    def set_output(self, path):
        with self._lock:
            path = str(path or "").strip()
            if path != self.output:
                self.output = path
                self._changed()
            return self.state()

    def _source_path(self, page):
        """A file with the page's pixels. The session copy wins: the original
        may have been moved, deleted or edited since it was added."""
        stored = self.store.image_path(page.uid)
        if os.path.isfile(stored):
            return stored
        return page.path if page.path and os.path.isfile(page.path) else None

    # ── Corner detection ──────────────────────────────────────────────
    def _begin_detection(self, jobs):
        """Call with the lock held."""
        self._detect_run += 1
        run = self._detect_run
        self._detecting = True
        threading.Thread(target=self._detect_all, args=(run, jobs), daemon=True,
                         name="pdfaura-scanner-detect").start()

    def _detect_all(self, run, jobs):
        found_count, total = 0, len(jobs)
        for done, job in enumerate(jobs, start=1):
            corners, found = scanner.detect(job)
            found_count += int(found)
            with self._lock:
                if run != self._detect_run:
                    return
                if job["page"] in self.pages:
                    job["page"].corners = list(corners)
                    self._changed(job["page"])
            self._send(progress={"current": done, "total": total})
        with self._lock:
            if run != self._detect_run:
                return
            self._detecting = False
        self._send(_notice("scanner_crop_area", _("scanner_detect_done").format(count=found_count)))

    # ── Session (survives a restart) ──────────────────────────────────
    def restore(self):
        """Bring back the pages of the last session, once, on a thread. The
        result arrives as a "scanner" event."""
        with self._lock:
            if self._restore_started:
                return self.state()
            self._restore_started = True
            store = self.store
            if store.locked_by_other:
                return self.state(_notice("scanner_session_title", _("scanner_session_locked")))
            meta = store.load_meta()
            if not meta or not meta.get("pages"):
                return self.state()
            self._restoring = True
        threading.Thread(target=self._restore, args=(meta,), daemon=True, name="pdfaura-scanner-restore").start()
        return self.state()

    def _restore(self, meta):
        restored, skipped = scanner.restore_pages(self.store, meta)
        with self._lock:
            self._restoring = False
            if not restored:
                self.store.clear()
                notice = _notice("scanner_session_title", _("scanner_session_failed"))
            else:
                # Nothing could be added meanwhile: every change was refused.
                self.pages = restored + self.pages
                for page in restored:
                    self._versions[page.uid] = 0
                index = meta.get("current_index", 0)
                self.current = index if isinstance(index, int) and 0 <= index < len(self.pages) else 0
                if meta.get("scan_mode") in dict(scanner.MODES):
                    self.mode = meta["scan_mode"]
                output = meta.get("output_path")
                if isinstance(output, str) and output and not self.output:
                    self.output = output
                if skipped:
                    notice = _notice("scanner_session_title", _("scanner_session_restored_partial").format(
                        count=len(restored), skipped=skipped))
                    self._changed()        # rewrite session.json without the broken pages
                else:
                    notice = _notice("scanner_session_title",
                                     _("scanner_session_restored").format(count=len(restored)))
        self._send(notice)

    def _schedule_save(self):
        """Call with the lock held: a debounced save of the whole session."""
        if self._restoring or not self.store.enabled:
            return
        self._cancel_save()
        self._save_timer = threading.Timer(SAVE_DELAY_S, self.save_now)
        self._save_timer.daemon = True
        self._save_timer.start()

    def _cancel_save(self):
        if self._save_timer is not None:
            self._save_timer.cancel()
            self._save_timer = None

    def save_now(self):
        """Hand the session to the store's writer thread now (the window is
        being hidden, or a debounced save is due)."""
        with self._lock:
            self._cancel_save()
            # No store yet: the scanner was never opened, nothing to keep.
            if self._store is None or self._restoring or not self.store.enabled:
                return
            if not self.pages:
                self.store.clear()
                return
            meta = scanner.session_meta(self.pages, self.mode, self.output, self.current)
            # References, not copies: a page's photo is never changed in place.
            images = {page.uid: page.cv_image for page in self.pages}
        self.store.save(meta, images)

    def flush(self, timeout=10.0):
        """Save and wait until it is on disk (the app is quitting)."""
        if self._store is None:
            return True
        self.save_now()
        return self.store.flush(timeout)

    def _session_error(self, message):
        self._emit("scanner", self.state(_notice("scanner_session_title",
                                                 _("scanner_session_save_failed").format(error=message),
                                                 tone="error")))

    # ── Export ────────────────────────────────────────────────────────
    def export(self, start_work, callbacks):
        """Write the PDF as a job started with ``start_work``
        (src.app.api.Api.start_work, so the bridge's cancel() reaches it).
        ``callbacks`` are the job's on_* handlers (the bridge's "job"
        events). Returns the Job, or {"problem": text}."""
        with self._lock:
            if self.busy:
                return {"problem": _("scanner_detect_busy")}
            if not self.pages:
                return {"problem": _("scanner_no_image")}
            output = self.output
            if not output:
                return {"problem": _("err_set_output")}
            # Snapshot now: the job must not read the live list (#12).
            shots = scanner.snapshot(self.pages)
            mode = self.mode
            started_rev = self._rev
            self._exporting = True

        def finished(success):
            with self._lock:
                self._exporting = False
                # Forget the session only if nothing changed while the PDF was
                # written; otherwise those edits are not in it yet.
                if success and self._rev == started_rev:
                    self._cancel_save()
                    self.store.clear()
                    self.output = ""
            self._send()

        def wrap(name, success=None):
            original = callbacks.get(name)

            def handler(*args):
                if success is not None:
                    finished(success)
                if original:
                    original(*args)
            return handler

        return start_work(
            lambda ctx: scanner.export_pdf(ctx, shots, output, mode), fail_title="scanner_fail",
            on_progress=callbacks.get("on_progress"), on_done=wrap("on_done", True),
            on_failed=wrap("on_failed", False), on_cancelled=wrap("on_cancelled", False))

    # ── Pictures ──────────────────────────────────────────────────────
    def render(self, uid, kind, width, height):
        """JPEG bytes of a page: "photo" (as rotated, for the editor),
        "thumb" (as it will be exported) or "preview" (with the scan mode);
        None if there is no such page. Runs on a server thread: it takes
        references under the lock and draws without it (a page's arrays are
        never changed in place)."""
        with self._lock:
            _index, page = self._find(uid)
            if page is None:
                return None
            snapshot = SimpleNamespace(display_image=page.display_image, corners=list(page.corners),
                                       display_shape=page.display_shape)
            mode = self.mode
        width = max(16, min(int(width), 4096))
        height = max(16, min(int(height), 4096))
        import cv2
        if kind == "photo":
            image = snapshot.display_image
            h, w = image.shape[:2]
            scale = min(1.0, min(width, PHOTO_MAX) / max(h, w))
            if scale < 1.0:
                image = cv2.resize(image, (max(1, round(w * scale)), max(1, round(h * scale))),
                                   interpolation=cv2.INTER_AREA)
            ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            return buffer.tobytes() if ok else None
        if kind == "thumb":
            picture = scanner.fitted(snapshot, width, height)
        elif kind == "preview":
            picture = scanner.preview(snapshot, mode, width, height)
        else:
            return None
        import io
        out = io.BytesIO()
        picture.save(out, "JPEG", quality=JPEG_QUALITY)
        return out.getvalue()
