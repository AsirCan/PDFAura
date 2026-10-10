"""Local AI models for Settings: the list, a download and a test.

The Tk settings dialog started its own threads for these, and an error
other than the expected one left its Download button disabled for good.
The window now asks for rows to show and starts a download or a test as a job:
progress, then exactly one of done / failed / cancelled, through ``post``.
"""
from dataclasses import dataclass

from src.app.jobs import JobRunner, call_now
from src.app.tools import Outcome
from src.core.lang_manager import _


@dataclass(frozen=True)
class ModelRow:
    id: str
    name: str
    category: str
    size: str               # "4.7 MB" when installed, "~460 MB" to download
    hardware: str
    installed: bool
    description: str
    message: str            # the status in words
    path: str
    license: str
    notes: str
    downloadable: bool      # a direct download exists; otherwise offer source_url
    source_url: str


def _row(status):
    spec = status.spec
    size = f"{status.size_mb:.1f} MB" if status.size_mb else f"~{spec.size_mb:.0f} MB"
    return ModelRow(id=spec.id, name=spec.name, category=spec.category, size=size,
                    hardware=spec.hardware_profile, installed=status.installed,
                    description=spec.description, message=status.message, path=status.path or "",
                    license=spec.license_name, notes=spec.notes, downloadable=bool(spec.download_url),
                    source_url=spec.source_url)


class Models:
    def __init__(self, post=call_now, root=None):
        """``root`` is the model folder to look in; the configured one if None."""
        self._runner = JobRunner(post)
        self.use_root(root)

    @property
    def root(self):
        return str(self.manager.model_root)

    def use_root(self, root):
        """Look in ``root`` from now on, without saving it (Settings saves on Save)."""
        from src.ai.model_manager import ModelManager
        self.manager = ModelManager(root or None)
        self.manager.ensure_directories()

    def save_root(self, root):
        """Look in ``root`` and remember it."""
        self.use_root(root)
        self.manager.set_model_root(root)

    def rows(self):
        return [_row(status) for status in self.manager.all_statuses()]

    def row(self, model_id):
        return _row(self.manager.status(model_id))

    def set_path(self, model_id, path):
        """Use the model file or folder the user picked."""
        self.manager.set_model_path(model_id, path)

    def download(self, model_id, *, on_progress=None, on_done=None, on_failed=None, on_cancelled=None):
        """Start downloading and return the Job, or None if the model has no
        direct download (the UI offers its source_url instead).

        on_progress(done_bytes, total_bytes, ""), on_done(outcome),
        on_failed(title, message) and on_cancelled() arrive through post.
        """
        if not self.row(model_id).downloadable:
            return None
        manager = self.manager

        def work(ctx):
            path = manager.download_model(model_id,
                                          progress=lambda done, total: ctx.report_progress(done, total))
            return Outcome(_("str_success"), _("settings_ai_download_done").format(path=path), str(path))

        def failed(message):
            if on_failed:
                on_failed(_("str_error"), message)

        return self._runner.start(work, on_progress=on_progress, on_done=on_done, on_error=failed,
                                  on_cancelled=on_cancelled)

    def test(self, model_id, *, on_done=None):
        """Check that the model can be read; on_done(ok, message)."""
        manager = self.manager

        def work(_ctx):
            try:
                return manager.test_model(model_id)
            except Exception as exc:
                return False, str(exc)

        def done(result):
            if on_done:
                on_done(*result)

        return self._runner.start(work, on_done=done, on_error=lambda message: done((False, message)))
