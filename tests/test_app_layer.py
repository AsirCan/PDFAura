"""#25 Faz 1: the application layer, tested without any window.

src/app/jobs.py runs work in the background; src/app/tools.py checks and
runs each tool; src/app/api.py is what a UI calls. These are the tests the
Tk tabs' behaviour now rests on, and the web window will reuse them.
"""
import os
import threading
import time

import pytest
from PIL import Image

from conftest import make_pdf, page_widths
from src.app import tools
from src.app.api import Api
from src.app.jobs import JobRunner
from src.app.tools import Invalid, Outcome, mode_from_label, mode_label
from src.core.lang_manager import _


class Recorder:
    """Collects a job's callbacks; ``wait`` blocks until one of the final ones."""

    def __init__(self):
        self.progress = []
        self.events = []
        self._done = threading.Event()

    def on_progress(self, current, total, message=""):
        self.progress.append((current, total, message))

    def finish(self, kind):
        def callback(*args):
            self.events.append((kind, *args))
            self._done.set()
        return callback

    def callbacks(self, failed_key="on_error"):
        return {"on_progress": self.on_progress, "on_done": self.finish("done"),
                failed_key: self.finish("failed"), "on_cancelled": self.finish("cancelled")}

    def wait(self, timeout=10):
        assert self._done.wait(timeout), "the job never finished"
        time.sleep(0.05)            # a second final callback would show up here
        return self.events


def run_tool(name, **params):
    """Run a tool through the Api, as a UI would, and return its one result."""
    problem = Api().check(name, params)
    assert problem is None, problem
    rec = Recorder()
    Api().start(name, params, **rec.callbacks("on_failed"))
    events = rec.wait(60)
    assert len(events) == 1, events
    return events[0], rec


# ── Jobs ──────────────────────────────────────────────────────────────────

def test_a_job_reports_its_result_exactly_once():
    rec = Recorder()
    job = JobRunner().start(lambda ctx: 42, **rec.callbacks())
    assert rec.wait() == [("done", 42)]
    assert job.state == "done" and job.result == 42 and job.finished.is_set()


def test_a_failing_job_reports_a_readable_message():
    def work(ctx):
        raise RuntimeError("disk full")
    rec = Recorder()
    job = JobRunner().start(work, **rec.callbacks())
    assert rec.wait() == [("failed", "disk full")]
    assert job.state == "failed"


def test_python_internals_are_not_shown_raw():
    def work(ctx):
        int("abc")
    rec = Recorder()
    JobRunner().start(work, **rec.callbacks())
    [(kind, message)] = rec.wait()
    assert kind == "failed" and message.startswith(_("err_unexpected"))


def test_cancel_stops_a_job_at_its_next_check():
    started = threading.Event()

    def work(ctx):
        started.set()
        for _i in range(500):
            ctx.check_cancelled()
            time.sleep(0.01)
        return "finished anyway"
    rec = Recorder()
    job = JobRunner().start(work, **rec.callbacks())
    assert started.wait(2)
    job.cancel()
    assert rec.wait() == [("cancelled",)]
    assert job.state == "cancelled"


def test_progress_is_thinned_but_the_last_update_always_arrives():
    def work(ctx):
        for i in range(1, 1001):
            ctx.report_progress(i, 1000, f"page {i}")
    rec = Recorder()
    JobRunner(progress_interval=0.05).start(work, **rec.callbacks())
    rec.wait()
    assert 1 <= len(rec.progress) < 100
    assert rec.progress[-1] == (1000, 1000, "page 1000")


def test_a_slow_step_does_not_leave_the_bar_on_an_old_value():
    """The newest skipped update is sent when the interval ends."""
    def work(ctx):
        ctx.report_progress(1, 10)
        ctx.report_progress(2, 10)          # skipped at first...
        time.sleep(0.3)                     # ...but sent while this step runs
        return None
    rec = Recorder()
    JobRunner(progress_interval=0.05).start(work, **rec.callbacks())
    rec.wait()
    assert (2, 10, "") in rec.progress


def test_no_progress_arrives_after_the_result():
    order = []

    def work(ctx):
        for i in range(200):
            ctx.report_progress(i, 1000)
        return "ok"
    done = threading.Event()
    JobRunner(progress_interval=0.05).start(
        work, on_progress=lambda *a: order.append("progress"),
        on_done=lambda r: (order.append("done"), done.set()))
    assert done.wait(5)
    time.sleep(0.2)
    assert order[-1] == "done"


def test_a_log_keeps_every_message():
    def work(ctx):
        for i in range(300):
            ctx.notify(i + 1, 300, f"file {i}")
    rec = Recorder()
    JobRunner(progress_interval=0.05).start(work, throttle=False, **rec.callbacks())
    rec.wait()
    assert len(rec.progress) == 300


def test_callbacks_go_through_post():
    """Tk passes root.after; every callback must use it, none called directly."""
    posted = []

    def post(fn, *args):
        posted.append(getattr(fn, "__name__", "?"))
        fn(*args)
    rec = Recorder()

    def work(ctx):
        ctx.report_progress(1, 1)
        return 1
    JobRunner(post=post).start(work, **rec.callbacks())
    rec.wait()
    assert len(posted) == 2


# ── Checks before a run ───────────────────────────────────────────────────

def test_compress_checks_quality_input_and_output(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    assert _("err_select_quality") in tools.check("compress", {"input": pdf, "output": "x.pdf", "quality": "best"})
    assert tools.check("compress", {"input": "", "output": "x.pdf", "quality": "ebook"}) == _("err_select_valid_pdf")
    assert tools.check("compress", {"input": pdf, "output": "", "quality": "ebook"}) == _("err_set_output")
    assert tools.check("compress", {"input": pdf, "output": "x.pdf", "quality": "ebook"}) is None


def test_split_wants_numbers(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    assert tools.check("split", {"input": pdf, "output": "o.pdf", "start": "1", "end": "iki"}) \
        == _("err_enter_page_numbers")


def test_merge_needs_two_files():
    assert tools.check("merge", {"files": ["a.pdf"], "output": "o.pdf"}) == _("err_min_2_pdf")


def test_encrypting_needs_a_confirmed_password(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    base = {"input": pdf, "output": str(tmp_path / "o.pdf"), "mode": "encrypt"}
    assert tools.check("security", {**base, "password": "", "confirm": ""})
    assert tools.check("security", {**base, "password": "Gizli-123", "confirm": "başka"})
    assert tools.check("security", {**base, "password": "Gizli-123", "confirm": "Gizli-123"}) is None
    assert tools.check("security", {**base, "mode": "decrypt", "password": ""}) == _("err_password_empty")


@pytest.mark.parametrize("mode, message", [
    ("word2pdf", "err_select_valid_word"), ("ppt2pdf", "err_select_valid_ppt"),
    ("excel2pdf", "err_select_valid_excel"), ("pdf2txt", "err_select_valid_pdf"),
    ("pdf2img", "err_select_valid_file"),
])
def test_each_conversion_names_what_it_needs(mode, message):
    assert tools.check("convert", {"mode": mode, "input": "", "output": "o"}) == _(message)


def test_batch_needs_both_folders(tmp_path):
    assert tools.check("batch", {"mode": "compress", "input_dir": "", "output_dir": str(tmp_path)}) \
        == _("err_select_valid_input_dir")
    assert tools.check("batch", {"mode": "compress", "input_dir": str(tmp_path), "output_dir": ""}) \
        == _("err_select_valid_output_dir")


def test_only_an_existing_output_needs_confirming(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    target = tmp_path / "o.pdf"
    params = {"input": pdf, "output": str(target), "quality": "ebook"}
    assert tools.existing_target("compress", params) is None
    target.write_bytes(b"%PDF")
    assert tools.existing_target("compress", params) == str(target)


def test_invalid_is_a_value_error_with_the_message():
    with pytest.raises(ValueError, match=_("err_min_2_pdf")):
        tools.get("merge").check(files=[], output="o.pdf")
    assert issubclass(Invalid, ValueError)


@pytest.mark.parametrize("tool, mode", [
    ("edit", "delete"), ("edit", "reorder"), ("security", "watermark"), ("convert", "pdf2word"),
    ("advanced", "ocr"), ("batch", "rename"),
])
@pytest.mark.parametrize("language", ["tr", "en", "ar", "ja"])
def test_mode_labels_round_trip(tool, mode, language):
    from src.core.config_manager import cfg
    cfg.config["language"] = language
    assert mode_from_label(tool, mode_label(tool, mode)) == mode


# ── Each tool, start to finish ────────────────────────────────────────────

def test_compress_runs_and_reports_sizes(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf", pages=4)
    out = str(tmp_path / "small.pdf")
    (kind, outcome), rec = run_tool("compress", input=pdf, output=out, quality="screen")
    assert kind == "done" and outcome.output_path == out and os.path.isfile(out)
    assert outcome.title == _("compress_done")
    assert "screen" in outcome.message
    assert rec.progress, "compress reports progress"


def test_split_keeps_the_range(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf", pages=5)
    out = str(tmp_path / "part.pdf")
    (kind, outcome), _rec = run_tool("split", input=pdf, output=out, start="2", end="4")
    assert kind == "done"
    assert page_widths(out) == [596, 597, 598]


def test_merge_joins_in_order(tmp_path):
    a = make_pdf(tmp_path / "a.pdf", pages=2)
    b = make_pdf(tmp_path / "b.pdf", pages=1, size=(700, 842))
    out = str(tmp_path / "ab.pdf")
    (kind, outcome), _rec = run_tool("merge", files=[a, b], output=out)
    assert kind == "done" and page_widths(out) == [595, 596, 700]


@pytest.mark.parametrize("mode, fields, widths", [
    ("delete", {"delete_pages": "2"}, [595, 597]),
    ("reorder", {"order": "3,1,2"}, [597, 595, 596]),
])
def test_edit_modes(tmp_path, mode, fields, widths):
    pdf = make_pdf(tmp_path / "a.pdf", pages=3)
    out = str(tmp_path / "e.pdf")
    (kind, outcome), _rec = run_tool("edit", input=pdf, output=out, mode=mode, **fields)
    assert kind == "done", outcome
    assert page_widths(out) == widths


def test_an_empty_page_list_fails_with_the_tools_title(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    (kind, title, message), _rec = run_tool("edit", input=pdf, output=str(tmp_path / "e.pdf"), mode="delete")
    assert kind == "failed"
    assert title == _("edit_fail") and message == _("edit_err_enter_delete")


def test_encrypt_then_decrypt(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    locked, opened = str(tmp_path / "locked.pdf"), str(tmp_path / "open.pdf")
    (kind, _o), _r = run_tool("security", input=pdf, output=locked, mode="encrypt",
                               password="Gizli-123", confirm="Gizli-123")
    assert kind == "done"
    (kind, _o), _r = run_tool("security", input=locked, output=opened, mode="decrypt", password="Gizli-123")
    assert kind == "done" and page_widths(opened) == [595, 596, 597]


def test_a_wrong_password_is_a_failure_not_a_crash(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    locked = str(tmp_path / "locked.pdf")
    run_tool("security", input=pdf, output=locked, mode="encrypt", password="Gizli-123", confirm="Gizli-123")
    (kind, title, message), _r = run_tool("security", input=locked, output=str(tmp_path / "x.pdf"),
                                          mode="decrypt", password="yanlış")
    assert kind == "failed" and title == _("str_failed") and message


def test_pdf_to_images_and_back(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf", pages=2)
    folder = str(tmp_path / "pages")
    (kind, outcome), _r = run_tool("convert", mode="pdf2img", input=pdf, output=folder, dpi="72", fmt="PNG")
    assert kind == "done" and outcome.output_path == folder
    images = sorted(os.path.join(folder, f) for f in os.listdir(folder))
    assert len(images) == 2
    out = str(tmp_path / "back.pdf")
    (kind, outcome), _r = run_tool("convert", mode="img2pdf", images=images, output=out)
    assert kind == "done" and len(page_widths(out)) == 2


def test_metadata_writes_only_what_was_loaded(tmp_path):
    from src.core.metainfo import read_metadata
    pdf = make_pdf(tmp_path / "a.pdf", metadata={"/Title": "Eski", "/Author": "Yazar"})
    out = str(tmp_path / "m.pdf")
    fields = tools.metadata_fields(clean=False, loaded=False, title="Yeni")
    assert fields["title"] is None, "a field never loaded from this file must not overwrite it"
    (kind, _o), _r = run_tool("advanced", input=pdf, output=out, mode="metadata",
                              metadata=tools.metadata_fields(clean=False, loaded=True, title="Yeni",
                                                             author="Yazar"))
    assert kind == "done" and read_metadata(out)["title"] == "Yeni"


def test_a_signature_is_stamped(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    stamp = tmp_path / "imza.png"
    Image.new("RGBA", (120, 40), (20, 20, 120, 255)).save(stamp)
    out = str(tmp_path / "signed.pdf")
    (kind, outcome), _r = run_tool("advanced", input=pdf, output=out, mode="signature",
                                   signature={"image": str(stamp), "page": "1", "x": "100,5", "y": "100",
                                              "scale": "1.0"})
    assert kind == "done" and os.path.isfile(out)


def test_batch_logs_every_file_while_it_runs(tmp_path):
    """The tab used to pass no progress callback, so the log stayed empty
    until the end."""
    source, target = tmp_path / "in", tmp_path / "out"
    source.mkdir()
    target.mkdir()
    for name in ("a", "b", "c"):
        make_pdf(source / f"{name}.pdf")
    (kind, outcome), rec = run_tool("batch", mode="rename", input_dir=str(source), output_dir=str(target),
                                    rename_rule="belge_{n}")
    assert kind == "done" and outcome.tone == "success"
    assert outcome.details == {"succeeded": 3, "failed": 0}
    assert len(rec.progress) == 3 and all(message for _c, _t, message in rec.progress)


@pytest.mark.parametrize("succeeded, errors, tone", [
    (0, ["x"], "error"), (2, ["x"], "warning"), (0, [], "info"), (3, [], "success"),
])
def test_batch_outcome_says_what_happened(succeeded, errors, tone):
    outcome = tools.batch_outcome(succeeded, errors, "out")
    assert outcome.tone == tone
    assert (outcome.output_path is None) == (tone in ("error", "info"))


# ── The Api ───────────────────────────────────────────────────────────────

def test_cancelling_through_the_api():
    started = threading.Event()

    def work(ctx):
        started.set()
        while True:
            ctx.check_cancelled()
            time.sleep(0.01)
    api = Api()
    rec = Recorder()
    job = api.start_work(work, fail_title="str_error", **rec.callbacks("on_failed"))
    assert started.wait(2)
    api.cancel(job.id)
    assert rec.wait() == [("cancelled",)]


def test_a_failure_carries_the_tools_title():
    def work(ctx):
        raise PermissionError(13, "denied", "C:/x.pdf")
    rec = Recorder()
    Api().start_work(work, fail_title="compress_fail", **rec.callbacks("on_failed"))
    [(kind, title, message)] = rec.wait()
    assert title == _("compress_fail") and _("err_no_permission") in message


def test_outcome_defaults():
    outcome = Outcome("t", "m")
    assert outcome.tone == "success" and outcome.output_path is None and outcome.details == {}
