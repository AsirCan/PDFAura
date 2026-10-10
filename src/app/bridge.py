"""What the web page may call: ``window.pywebview.api.<method>(...)``.

pywebview exposes every public method of the js_api object to the page --
and the methods of any public attribute that is itself an object -- and
runs each call on a thread of its own. So everything here is a method that
takes and returns plain JSON values, all state lives in underscored
attributes, and nothing runs a command or code the page sends: tools are
started by name through src.app.api, which checks their input first, and
paths from the page are checked before they are opened.

Results that come later (job progress, assistant replies, dropped files)
are events; see events.py and web/src/lib/bridge.ts.
"""
import os
import subprocess
import threading
import time
from dataclasses import asdict

from src.app.api import Api
from src.app.jobs import call_now
from src.core.config_manager import cfg
from src.core.lang_manager import LANGUAGES, RTL_LANGUAGES, strings_for

THEMES = ("system", "paper", "night")

# Native dialog filters by kind. pywebview accepts "Description (*.a;*.b)"
# with letters, digits and spaces in the description.
FILE_TYPES = {
    "pdf": ("PDF (*.pdf)",),
    "image": ("Images (*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff;*.gif;*.webp)",),
    "word": ("Word (*.doc;*.docx)",),
    "powerpoint": ("PowerPoint (*.ppt;*.pptx)",),
    "excel": ("Excel (*.xls;*.xlsx)",),
    "text": ("Text (*.txt)",),
    "docx": ("Word (*.docx)",),
    "model": ("AI model files (*.onnx;*.bin;*.pdmodel;*.traineddata;*.ct2)", "All files (*.*)"),
}

# What a dropped or picked file is, by extension.
KINDS = {
    ".pdf": "pdf",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".bmp": "image", ".tif": "image",
    ".tiff": "image", ".gif": "image", ".webp": "image",
    ".doc": "word", ".docx": "word",
    ".ppt": "powerpoint", ".pptx": "powerpoint",
    ".xls": "excel", ".xlsx": "excel",
    ".txt": "text",
}


def file_info(path):
    """What the page needs to know about a path it holds."""
    path = os.path.abspath(str(path))
    exists = os.path.exists(path)
    is_dir = exists and os.path.isdir(path)
    ext = os.path.splitext(path)[1].lower()
    try:
        size = os.path.getsize(path) if exists and not is_dir else 0
    except OSError:
        size = 0
    return {"path": path, "name": os.path.basename(path) or path, "folder": os.path.dirname(path),
            "ext": ext, "kind": "folder" if is_dir else KINDS.get(ext, "other"),
            "size": size, "exists": exists, "is_dir": is_dir}


def _outcome(outcome):
    return {"title": outcome.title, "message": outcome.message, "output": outcome.output_path,
            "tone": outcome.tone, "details": outcome.details}


class JobEvents:
    """A job's reports as "job" events: progress, then one of done, failed
    or cancelled, each with the job's id.

    A fast job can report from its thread before start() has returned the
    Job, so the callbacks wait for bind() to give them the id.
    """

    def __init__(self, emit, sounds=True):
        self._emit = emit
        self._sounds = sounds
        self._id = None
        self._bound = threading.Event()

    def bind(self, job):
        self._id = job.id
        self._bound.set()
        return job

    def _send(self, data):
        self._bound.wait(5)
        self._emit("job", {"id": self._id, **data})

    def callbacks(self):
        return {"on_progress": self._progress, "on_done": self._done, "on_failed": self._failed,
                "on_cancelled": self._cancelled}

    def _progress(self, current, total, message=""):
        self._send({"type": "progress", "current": current, "total": total, "message": message})

    def _done(self, outcome):
        # Tk's result panel played these; the setting in Settings decides.
        if self._sounds:
            from src.core.notify import play_error, play_success
            if outcome.tone == "success":
                play_success()
            elif outcome.tone == "error":
                play_error()
        self._send({"type": "done", "outcome": _outcome(outcome)})

    def _failed(self, title, message):
        if self._sounds:
            from src.core.notify import play_error
            play_error()
        self._send({"type": "failed", "title": title, "message": message})

    def _cancelled(self):
        self._send({"type": "cancelled"})


class Bridge:
    def __init__(self, shell):
        """``shell`` is the window side (window.py): the pywebview window,
        events, image caches and the tray."""
        self._shell = shell
        self._events = shell.events
        self._api = Api(post=call_now)
        self._assistant = None
        self._models = None

    # ── Start-up, language, theme, settings ───────────────────────────
    def boot(self):
        """Everything the page needs to draw itself. The page is listening
        for events from here on."""
        language = cfg.get("language", "tr")
        if language not in LANGUAGES:
            language = "en"
        theme = cfg.get("theme", "system")
        self._events.ready()
        if os.environ.get("PDFAURA_TIMING"):
            # For spikes/faz0/measure.py: when the page is drawn and talking.
            print(f"READY {time.time():.4f}", flush=True)
        return {
            "language": language,
            "rtl": language in RTL_LANGUAGES,
            "strings": strings_for(language),
            "languages": [[code, name] for code, name in LANGUAGES.items()],
            "theme": theme if theme in THEMES else "system",
            "settings": self.settings(),
            "recent": self.recent_files(),
            "token": self._shell.token,
            "version": self._shell.version,
        }

    def set_language(self, code):
        """Switch language at once, without a restart."""
        if code not in LANGUAGES:
            raise ValueError(f"unknown language {code!r}")
        cfg.set("language", code)
        self._shell.language_changed()
        return {"language": code, "rtl": code in RTL_LANGUAGES, "strings": strings_for(code)}

    def set_theme(self, preference):
        if preference not in THEMES:
            raise ValueError(f"unknown theme {preference!r}")
        cfg.set("theme", preference)
        return preference

    def theme_shown(self, name):
        """The page now shows theme ``name`` ("paper" or "night"): paint the
        native title bar to match."""
        if name in THEMES[1:]:
            self._shell.style_title_bar(name)

    def settings(self):
        return {"close_to_tray": bool(cfg.get("close_to_tray", True)),
                "sound_enabled": bool(cfg.get("sound_enabled", True)),
                "default_output_dir": cfg.get("default_output_dir", "") or ""}

    def save_settings(self, values):
        folder = str(values.get("default_output_dir", "") or "").strip()
        if folder and not os.path.isdir(folder):
            raise ValueError("default_output_dir")
        cfg.set("close_to_tray", bool(values.get("close_to_tray", True)))
        cfg.set("sound_enabled", bool(values.get("sound_enabled", True)))
        cfg.set("default_output_dir", folder)
        return self.settings()

    def recent_files(self):
        return [file_info(path) for path in cfg.get_recent_files()[:5]]

    def clear_recent(self):
        cfg.clear_recent_files()
        return []

    # ── Files ─────────────────────────────────────────────────────────
    def file_info(self, paths):
        return [file_info(path) for path in paths]

    def pick_files(self, kind="pdf", multiple=False):
        import webview
        result = self._shell.window.create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=bool(multiple), file_types=FILE_TYPES.get(kind, ()))
        return [file_info(path) for path in (result or [])]

    def pick_folder(self, start=""):
        import webview
        result = self._shell.window.create_file_dialog(
            webview.FileDialog.FOLDER, directory=start if start and os.path.isdir(start) else "")
        return file_info(result[0]) if result else None

    def pick_save(self, kind="pdf", suggested=""):
        """A save dialog starting at ``suggested``; the chosen path or None."""
        import webview
        folder, name = os.path.split(suggested or "")
        result = self._shell.window.create_file_dialog(
            webview.FileDialog.SAVE, directory=folder if folder and os.path.isdir(folder) else "",
            save_filename=name, file_types=FILE_TYPES.get(kind, ()))
        if isinstance(result, (list, tuple)):
            result = result[0] if result else None
        return result or None

    def open_path(self, path):
        """Open a file or folder the way Explorer would. False if it is gone."""
        if not path or not os.path.exists(path):
            return False
        os.startfile(path)
        return True

    def reveal_path(self, path):
        """Show a file selected in its folder (or open a folder)."""
        if not path or not os.path.exists(path):
            return False
        if os.path.isdir(path):
            os.startfile(path)
        else:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        return True

    # ── Tools ─────────────────────────────────────────────────────────
    def check(self, tool, params):
        """None if the tool can start, else what to fix."""
        return self._api.check(tool, params)

    def existing_target(self, tool, params):
        """The file the run would replace, if one exists: ask first."""
        return self._api.existing_target(tool, params)

    def suggest_output(self, tool, source, mode=None, start=None, end=None):
        return self._api.suggest_output(tool, source, mode, start=start, end=end)

    def start(self, tool, params):
        """Start a tool; its progress and result arrive as "job" events.
        Returns the job id, the text to show while it runs, and whether it
        can be cancelled -- or the problem with the input."""
        problem = self._api.check(tool, params)
        if problem:
            return {"problem": problem}
        busy = self._api.busy_text(tool, params)
        cancellable = self._api.cancellable(tool, params)
        events = JobEvents(self._events.emit)
        job = events.bind(self._api.start(tool, params, **events.callbacks()))
        return {"job": job.id, "busy": busy, "cancellable": cancellable}

    def cancel(self, job_id):
        self._api.cancel(job_id)

    # ── Preview and viewer ────────────────────────────────────────────
    def document(self, path):
        """A PDF to show: its id for page URLs and what the preview says
        about it, or what is wrong with it."""
        info = file_info(path)
        if info["kind"] != "pdf" or not info["exists"]:
            return {**info, "error": "not-a-pdf"}
        pages = self._shell.pages
        doc_id = pages.register(info["path"])
        try:
            details = pages.info(info["path"])
        except Exception as exc:
            return {**info, "error": str(exc)}
        version = int(os.path.getmtime(info["path"]))
        return {**info, **details, "id": doc_id, "version": version,
                "base": f"/pdf/{self._shell.token}/{doc_id}/"}

    # ── Assistant ─────────────────────────────────────────────────────
    def _helper(self):
        if self._assistant is None:
            from src.app.assistant import Assistant
            emit = self._events.emit
            self._assistant = Assistant(
                on_state=lambda state, detail: emit("assistant", {"state": state, "detail": detail}),
                on_reply=lambda text: emit("assistant-reply", {"text": text}))
        return self._assistant

    def assistant_submit(self, text):
        return self._helper().submit(text)

    def assistant_press(self):
        self._helper().press()

    def assistant_release(self):
        self._helper().release()

    # ── Local AI models (Settings) ────────────────────────────────────
    def _model_list(self):
        if self._models is None:
            from src.app.models import Models
            self._models = Models()
        return self._models

    def models(self, root=None):
        models = self._model_list()
        if root:
            models.use_root(root)
        return {"root": models.root, "rows": [asdict(row) for row in models.rows()]}

    def models_save_root(self, root):
        self._model_list().save_root(root)
        return self.models()

    def models_pick_path(self, model_id):
        """Let the user point a model at a file (or, failing that, a folder)."""
        chosen = self.pick_files("model")
        path = chosen[0]["path"] if chosen else None
        if path is None:
            folder = self.pick_folder()
            path = folder["path"] if folder else None
        if path is None:
            return None
        self._model_list().set_path(model_id, path)
        return self.models()

    def models_download(self, model_id):
        """Start a download (its events are "job" events), or say where the
        model can be found when there is no direct download."""
        models = self._model_list()
        row = models.row(model_id)
        if not row.downloadable:
            if row.source_url:
                import webbrowser
                webbrowser.open(row.source_url)
            return {"source_url": row.source_url}
        events = JobEvents(self._events.emit, sounds=False)
        job = events.bind(models.download(model_id, **events.callbacks()))
        return {"job": job.id}

    def models_test(self, model_id):
        emit = self._events.emit
        self._model_list().test(
            model_id, on_done=lambda ok, message: emit("model-test", {"id": model_id, "ok": ok,
                                                                      "message": message}))

    # ── Window ────────────────────────────────────────────────────────
    def quit(self):
        self._shell.quit()
