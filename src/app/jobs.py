"""Background jobs, the same way for every tool and every UI.

Each tab used to start its own thread and hand results back with
root.after, ten times over with small differences. A job runs
``work(ctx)`` on a worker thread and reports through ``post``, which must
run a function on the UI's own thread: Tk passes ``root.after(0, ...)``,
tests pass a direct call, and the web window will pass its event emitter.
"""
import itertools
import logging
import threading
import time

from src.core.errors import friendly_error
from src.core.task_manager import CancelledError, TaskContext

# Progress more often than this is not visible and, for the web window,
# costs a bridge call per update.
PROGRESS_INTERVAL_S = 0.05

_ids = itertools.count(1)


def call_now(fn, *args):
    fn(*args)


class Job:
    """A running or finished job. ``state`` is running, done, failed or cancelled."""

    def __init__(self):
        self.id = next(_ids)
        self.ctx = None
        self.state = "running"
        self.result = None
        self.error = None
        self.finished = threading.Event()

    def cancel(self):
        if self.ctx is not None:
            self.ctx.cancel()

    @property
    def running(self):
        return self.state == "running"


class _Progress:
    """Forwards at most one update per interval. The newest skipped update
    is sent when the interval ends, so the bar never sticks at an old value
    while a slow step runs."""

    def __init__(self, post, on_progress, interval):
        self._post = post
        self._on_progress = on_progress
        self._interval = interval
        self._lock = threading.Lock()
        self._last = 0.0
        self._pending = None
        self._timer = None
        self.closed = False

    def __call__(self, current, total, message=""):
        with self._lock:
            if self.closed:
                return
            now = time.monotonic()
            final = total > 0 and current >= total
            if self._interval <= 0 or final or now - self._last >= self._interval:
                self._last = now
                self._pending = None
                self._post(self._on_progress, current, total, message)
                return
            self._pending = (current, total, message)
            if self._timer is None:
                self._timer = threading.Timer(self._interval - (now - self._last), self._flush)
                self._timer.daemon = True
                self._timer.start()

    def _flush(self):
        with self._lock:
            self._timer = None
            if self.closed or self._pending is None:
                return
            self._last = time.monotonic()
            pending, self._pending = self._pending, None
            self._post(self._on_progress, *pending)

    def close(self):
        """No updates after the job has ended: a late one would repaint a
        finished bar."""
        with self._lock:
            self.closed = True
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


class JobRunner:
    def __init__(self, post=call_now, progress_interval=PROGRESS_INTERVAL_S):
        self._post = post
        self._interval = progress_interval

    def start(self, work, *, on_progress=None, on_done=None, on_error=None, on_cancelled=None,
              throttle=True):
        """Run ``work(ctx)`` in the background and return its Job at once.

        on_done(result), on_error(message) and on_cancelled() arrive through
        ``post``; exactly one of them is called. ``throttle=False`` keeps
        every progress update, for jobs whose messages are a log.
        """
        job = Job()
        progress = None
        if on_progress is not None:
            progress = _Progress(self._post, on_progress, self._interval if throttle else 0)
        job.ctx = TaskContext(progress_callback=progress)

        def finish(state, callback, *args):
            if progress is not None:
                progress.close()
            job.state = state
            if callback is not None:
                self._post(callback, *args)
            job.finished.set()

        def run():
            try:
                result = work(job.ctx)
            except CancelledError:
                finish("cancelled", on_cancelled)
            except Exception as exc:
                # The user sees friendly_error(); the traceback is for us.
                logging.getLogger(__name__).exception("Job %s failed", job.id)
                job.error = friendly_error(exc)
                finish("failed", on_error, job.error)
            else:
                job.result = result
                finish("done", on_done, result)

        threading.Thread(target=run, daemon=True, name=f"pdfaura-job-{job.id}").start()
        return job
