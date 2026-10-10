"""Python -> page events for the web window.

Everything the page did not ask for -- job progress, the assistant's
replies, files dropped on the window -- reaches it as an event. They go
out with run_js, which does not wait (evaluate_js wraps its script in
eval() and waits for the result; see spikes/faz0/RAPOR.md), as a call to
``window.__aura.emit(name, data)`` that web/src/lib/bridge.ts defines.

Events sent before the page has said it is ready are kept and sent once it
has; otherwise the first progress of a job started at once would be lost.
"""
import json
import logging
import threading


class EventBus:
    def __init__(self, run_js=None):
        """``run_js(script)`` sends a script to the page without waiting."""
        self._run_js = run_js
        self._lock = threading.Lock()
        self._ready = False
        self._pending = []

    def attach(self, run_js):
        self._run_js = run_js

    def emit(self, name, data=None):
        script = f"window.__aura&&window.__aura.emit({json.dumps(name)},{json.dumps(data)})"
        with self._lock:
            if not self._ready or self._run_js is None:
                self._pending.append(script)
                return
        self._send(script)

    def ready(self):
        """The page is listening: send what was kept, in order."""
        with self._lock:
            self._ready = True
            pending, self._pending = self._pending, []
        for script in pending:
            self._send(script)

    def reset(self):
        """The page is reloading: keep events until it is ready again."""
        with self._lock:
            self._ready = False

    def _send(self, script):
        try:
            self._run_js(script)
        except Exception:
            # The window may be closing; an event is never worth a crash.
            logging.getLogger(__name__).debug("Event not delivered", exc_info=True)
