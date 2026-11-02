"""Tests for the AI Assistant tool (Faz 4 AI PDF Sohbeti + Faz 5 Özet UI)."""
import os
import threading
import time
from pathlib import Path
import pytest

from src.app import tools
from src.app.api import Api
from src.app.jobs import JobRunner
from src.core.lang_manager import _


def _create_sample_pdf(path: Path) -> Path:
    import fitz

    doc = fitz.open()
    try:
        p1 = doc.new_page(width=595, height=842)
        p1.insert_text(
            (50, 72),
            "Sozlesme Madde 1: Isbu sozlesme 1 Ocak 2025 tarihinde yururluge girer.\n"
            "Toplam odeme bedeli 50000 Turk Lirasidir. Odeme uc esit taksitte yapilacaktir.",
            fontsize=11,
        )

        p2 = doc.new_page(width=595, height=842)
        p2.insert_text(
            (50, 72),
            "Sozlesme Madde 2: Fesih sartlari ve cezai sartlar.\n"
            "Taraflar 30 gun onceden yazili bildirimde bulunarak sozlesmeyi feshedebilir.\n"
            "Gecikme halinde gunluk yuzde 0.1 gecikme faizi uygulanir.",
            fontsize=11,
        )
        doc.save(str(path))
    finally:
        doc.close()
    return path


@pytest.fixture
def sample_pdf(tmp_path):
    return _create_sample_pdf(tmp_path / "ornek_sozlesme.pdf")


class Recorder:
    def __init__(self):
        self.events = []
        self._done = threading.Event()

    def on_progress(self, current, total, message=""):
        self.events.append(("progress", current, total, message))

    def on_done(self, outcome):
        self.events.append(("done", outcome))
        self._done.set()

    def on_failed(self, title, message):
        self.events.append(("failed", title, message))
        self._done.set()

    def on_cancelled(self):
        self.events.append(("cancelled",))
        self._done.set()

    def wait(self, timeout=30):
        assert self._done.wait(timeout), "the job never finished"
        time.sleep(0.05)
        return self.events


def test_ai_tool_is_registered():
    tool = tools.get("ai")
    assert tool is not None
    assert tool.name == "ai"
    assert tool.fail_title == "ai_fail"
    assert callable(tool.check)
    assert callable(tool.run)
    assert callable(tool.busy)


def test_ai_check_validation(sample_pdf, tmp_path):
    # Missing input
    err = tools.check("ai", {"input": "", "mode": "ask", "question": "Ne zaman?"})
    assert err is not None

    # Invalid mode
    err = tools.check("ai", {"input": str(sample_pdf), "mode": "unknown"})
    assert err is not None

    # Mode ask: empty question
    err = tools.check("ai", {"input": str(sample_pdf), "mode": "ask", "question": ""})
    assert err == _("ai_err_question")

    # Mode ask: valid question
    err = tools.check("ai", {"input": str(sample_pdf), "mode": "ask", "question": "Odeme bedeli ne kadar?"})
    assert err is None

    # Mode summary: invalid summary mode
    err = tools.check("ai", {"input": str(sample_pdf), "mode": "summary", "summary_mode": "gecersiz"})
    assert err == _("ai_err_summary_mode")

    # Mode summary: valid modes
    for m in ("kisa", "detayli", "ogrenci", "toplanti", "hukuki"):
        err = tools.check("ai", {"input": str(sample_pdf), "mode": "summary", "summary_mode": m})
        assert err is None, f"mode {m} should be valid"

    # Mode save: empty text
    err = tools.check("ai", {"mode": "save", "text": "", "format": "txt", "output": str(tmp_path / "out.txt")})
    assert err == _("ai_err_summary_empty")

    # Mode save: invalid format
    err = tools.check("ai", {"mode": "save", "text": "ozet", "format": "doc", "output": str(tmp_path / "out.doc")})
    assert err == _("ai_err_format")

    # Mode save: empty output
    err = tools.check("ai", {"mode": "save", "text": "ozet", "format": "txt", "output": ""})
    assert err is not None

    # Mode save: valid
    err = tools.check("ai", {"mode": "save", "text": "ozet", "format": "txt", "output": str(tmp_path / "out.txt")})
    assert err is None
    err = tools.check("ai", {"mode": "save", "text": "ozet", "format": "pdf", "output": str(tmp_path / "out.pdf")})
    assert err is None


def test_ai_run_ask_found(sample_pdf):
    api = Api()
    rec = Recorder()
    api.start(
        "ai",
        {"input": str(sample_pdf), "mode": "ask", "question": "Odeme bedeli kac lira?", "use_llm": False},
        on_progress=rec.on_progress,
        on_done=rec.on_done,
        on_failed=rec.on_failed,
        on_cancelled=rec.on_cancelled,
    )
    events = rec.wait()
    assert len(events) >= 1
    done_events = [ev for ev in events if ev[0] == "done"]
    assert len(done_events) == 1
    outcome = done_events[0][1]

    assert outcome.tone == "success"
    assert outcome.details["kind"] == "answer"
    assert outcome.details["found"] is True
    assert len(outcome.details["sources"]) >= 1
    assert outcome.details["sources"][0]["page"] == 1


def test_ai_run_ask_not_found(sample_pdf):
    api = Api()
    rec = Recorder()
    api.start(
        "ai",
        {"input": str(sample_pdf), "mode": "ask", "question": "Astronotlar uzayda ne yer?", "use_llm": False},
        on_progress=rec.on_progress,
        on_done=rec.on_done,
        on_failed=rec.on_failed,
        on_cancelled=rec.on_cancelled,
    )
    events = rec.wait()
    done_events = [ev for ev in events if ev[0] == "done"]
    assert len(done_events) == 1
    outcome = done_events[0][1]

    assert outcome.tone == "warning"
    assert outcome.details["kind"] == "answer"
    assert outcome.details["found"] is False


def test_ai_run_summary(sample_pdf):
    api = Api()
    for sm in ("kisa", "hukuki"):
        rec = Recorder()
        api.start(
            "ai",
            {"input": str(sample_pdf), "mode": "summary", "summary_mode": sm, "use_llm": False},
            on_progress=rec.on_progress,
            on_done=rec.on_done,
            on_failed=rec.on_failed,
            on_cancelled=rec.on_cancelled,
        )
        events = rec.wait()
        done_events = [ev for ev in events if ev[0] == "done"]
        assert len(done_events) == 1
        outcome = done_events[0][1]

        assert outcome.tone == "success"
        assert outcome.details["kind"] == "summary"
        assert outcome.details["summary_mode"] == sm
        assert len(outcome.details["text"]) > 0


def test_ai_run_save_txt_and_pdf(tmp_path):
    api = Api()
    summary_text = "Sozlesme Ozeti:\n- Odeme bedeli: 50.000 TL (Sayfa 1)\n- Fesih suresi: 30 gun (Sayfa 2)"

    # Save TXT
    txt_target = str(tmp_path / "ozet.txt")
    rec_txt = Recorder()
    api.start(
        "ai",
        {"mode": "save", "text": summary_text, "format": "txt", "output": txt_target},
        on_done=rec_txt.on_done,
        on_failed=rec_txt.on_failed,
    )
    rec_txt.wait()
    assert os.path.isfile(txt_target)
    with open(txt_target, "r", encoding="utf-8") as f:
        assert "Sozlesme Ozeti" in f.read()

    # Save PDF
    pdf_target = str(tmp_path / "ozet.pdf")
    rec_pdf = Recorder()
    api.start(
        "ai",
        {"mode": "save", "text": summary_text, "format": "pdf", "output": pdf_target},
        on_done=rec_pdf.on_done,
        on_failed=rec_pdf.on_failed,
    )
    rec_pdf.wait()
    assert os.path.isfile(pdf_target)
    assert os.path.getsize(pdf_target) > 500


def test_ai_mode_labels():
    assert tools.mode_label("ai", "ask") == _("ai_mode_ask")
    assert tools.mode_label("ai", "summary") == _("ai_mode_summary")
    assert tools.mode_label("ai", "save") == _("ai_mode_save")
