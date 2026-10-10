"""The single door to run tools by.

The window's bridge (bridge.py) calls it for the page. A UI checks the
input, asks before replacing a file, starts the tool and gets back
progress and exactly one of done / failed / cancelled, through ``post``.
"""
from src.app import tools
from src.app.jobs import JobRunner, call_now
from src.core.config_manager import cfg
from src.core.lang_manager import _


class Api:
    def __init__(self, post=call_now):
        """``post(fn, *args)`` runs fn on the UI's thread; see jobs.JobRunner."""
        self._runner = JobRunner(post)
        self._jobs = {}

    # ── Before a run ──────────────────────────────────────────────────
    def check(self, tool, params):
        """None if ``tool`` can start with ``params``, else what to fix."""
        return tools.check(tool, params)

    def existing_target(self, tool, params):
        """The file the run would replace, if one exists: ask first."""
        return tools.existing_target(tool, params)

    def busy_text(self, tool, params):
        return tools.busy_text(tool, params)

    def cancellable(self, tool, params):
        return tools.is_cancellable(tool, params)

    def suggest_output(self, tool, source, mode=None, start=None, end=None):
        """Where the tool should write unless the user picks a place."""
        return tools.suggest_output(tool, source, mode, start=start, end=end)

    # ── Running ───────────────────────────────────────────────────────
    def start(self, tool, params, *, on_progress=None, on_done=None, on_failed=None, on_cancelled=None):
        """Start ``tool`` and return its Job. Call check() first.

        on_done(outcome), on_failed(title, message) and on_cancelled() come
        back through ``post``.
        """
        spec = tools.get(tool)
        return self.start_work(lambda ctx: spec.run(ctx, **params), fail_title=spec.fail_title,
                               on_progress=on_progress, on_done=on_done, on_failed=on_failed,
                               on_cancelled=on_cancelled, log_progress=spec.log_progress)

    def start_work(self, work, *, fail_title, on_progress=None, on_done=None, on_failed=None, on_cancelled=None,
                   log_progress=False):
        """Like start(), for work that is not a registered tool (the
        scanner's export): ``work(ctx)`` returns an Outcome."""
        def done(outcome):
            self._remember(outcome)
            if on_done:
                on_done(outcome)

        def failed(message):
            if on_failed:
                on_failed(_(fail_title), message)

        job = self._runner.start(work, on_progress=on_progress, on_done=done, on_error=failed,
                                 on_cancelled=on_cancelled, throttle=not log_progress)
        self._jobs = {i: j for i, j in self._jobs.items() if j.running}
        self._jobs[job.id] = job
        return job

    def cancel(self, job_id):
        job = self._jobs.get(job_id)
        if job is not None:
            job.cancel()

    @staticmethod
    def _remember(outcome):
        # Every tool finishes here, so this is where the recent-files list is
        # kept, whichever UI started the job.
        if outcome.tone == "success" and outcome.output_path:
            cfg.add_recent_file(outcome.output_path)
