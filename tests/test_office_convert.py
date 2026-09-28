"""Issue #7: Office conversions need CoInitialize and must not touch the user's Office.

There is no Office on the test machine, so a fake pythoncom/win32com.client
pair is injected into sys.modules and the COM calls are recorded.
"""
import sys
import types

import pytest

from src.core import convert


class FakeComError(Exception):
    def __init__(self, hresult):
        super().__init__(hresult, "fake com error")
        self.hresult = hresult


class Recorder:
    def __init__(self):
        self.events = []

    def log(self, name, *args):
        self.events.append((name,) + args)

    def names(self):
        return [e[0] for e in self.events]


class FakeDocument:
    def __init__(self, rec, kind, open_kwargs):
        self.rec = rec
        self.kind = kind
        self.open_kwargs = open_kwargs

    def ExportAsFixedFormat(self, *args, **kwargs):
        self.rec.log("export", self.kind, args)

    def SaveAs(self, *args):
        self.rec.log("saveas", self.kind, args)

    def Close(self, *args):
        self.rec.log("close", self.kind)


class FakeCollection:
    def __init__(self, rec, kind, count=0):
        self.rec = rec
        self.kind = kind
        self.Count = count

    def Open(self, path, **kwargs):
        self.rec.log("open", self.kind, kwargs)
        return FakeDocument(self.rec, self.kind, kwargs)


class FakeApp:
    def __init__(self, rec, prog_id):
        self.rec = rec
        self.prog_id = prog_id
        self.Documents = FakeCollection(rec, "word")
        self.Presentations = FakeCollection(rec, "ppt")
        self.Workbooks = FakeCollection(rec, "excel")

    def __setattr__(self, name, value):
        if name in ("DisplayAlerts", "Visible", "Interactive"):
            self.rec.log("set", name, value)
        object.__setattr__(self, name, value)

    def Quit(self):
        self.rec.log("quit", self.prog_id)


@pytest.fixture
def fake_com(monkeypatch):
    """Install a fake pythoncom + win32com.client and record what is called."""
    rec = Recorder()
    rec.running = set()          # prog_ids the "user" already has open
    rec.dispatch_error = None    # HRESULT to raise from DispatchEx

    pythoncom = types.ModuleType("pythoncom")
    pythoncom.com_error = FakeComError
    pythoncom.CoInitialize = lambda: rec.log("CoInitialize")
    pythoncom.CoUninitialize = lambda: rec.log("CoUninitialize")

    def dispatch_ex(prog_id):
        rec.log("DispatchEx", prog_id)
        if rec.dispatch_error is not None:
            raise FakeComError(rec.dispatch_error)
        return FakeApp(rec, prog_id)

    def get_active_object(prog_id):
        if prog_id in rec.running:
            return FakeApp(rec, prog_id)
        raise FakeComError(-2147221021)

    client = types.ModuleType("win32com.client")
    client.DispatchEx = dispatch_ex
    client.Dispatch = lambda prog_id: pytest.fail("Dispatch attaches to the user's Office")
    client.GetActiveObject = get_active_object

    win32com = types.ModuleType("win32com")
    win32com.client = client

    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    return rec


CONVERTERS = [
    (convert.word_to_pdf, "in.docx", "Word.Application"),
    (convert.ppt_to_pdf, "in.pptx", "PowerPoint.Application"),
    (convert.excel_to_pdf, "in.xlsx", "Excel.Application"),
]


@pytest.mark.parametrize("func, name, prog_id", CONVERTERS)
def test_conversion_initialises_com_on_this_thread(tmp_path, fake_com, func, name, prog_id):
    """Without CoInitialize every conversion fails with 'CoInitialize was not called'."""
    src = tmp_path / name
    src.write_bytes(b"x")

    func(str(src), str(tmp_path / "out.pdf"))

    assert fake_com.names()[0] == "CoInitialize"
    assert fake_com.names()[-1] == "CoUninitialize"


@pytest.mark.parametrize("func, name, prog_id", CONVERTERS)
def test_conversion_uses_a_private_instance(tmp_path, fake_com, func, name, prog_id):
    """Dispatch would attach to the user's Office; DispatchEx asks for our own."""
    src = tmp_path / name
    src.write_bytes(b"x")

    func(str(src), str(tmp_path / "out.pdf"))

    assert ("DispatchEx", prog_id) in fake_com.events


@pytest.mark.parametrize("func, name, prog_id", CONVERTERS)
def test_documents_are_opened_read_only(tmp_path, fake_com, func, name, prog_id):
    src = tmp_path / name
    src.write_bytes(b"x")

    func(str(src), str(tmp_path / "out.pdf"))

    opens = [e for e in fake_com.events if e[0] == "open"]
    assert opens and opens[0][2].get("ReadOnly") is True


@pytest.mark.parametrize("func, name, prog_id", CONVERTERS)
def test_our_own_document_is_closed(tmp_path, fake_com, func, name, prog_id):
    src = tmp_path / name
    src.write_bytes(b"x")

    func(str(src), str(tmp_path / "out.pdf"))

    assert "close" in fake_com.names()


def test_powerpoint_already_open_is_not_quit(tmp_path, fake_com):
    """PowerPoint is single-instance: quitting it closes the user's decks."""
    fake_com.running.add("PowerPoint.Application")
    src = tmp_path / "in.pptx"
    src.write_bytes(b"x")

    convert.ppt_to_pdf(str(src), str(tmp_path / "out.pdf"))

    assert "quit" not in fake_com.names()


def test_powerpoint_we_started_is_quit(tmp_path, fake_com):
    src = tmp_path / "in.pptx"
    src.write_bytes(b"x")

    convert.ppt_to_pdf(str(src), str(tmp_path / "out.pdf"))

    assert ("quit", "PowerPoint.Application") in fake_com.events


@pytest.mark.parametrize("func, name, prog_id", CONVERTERS)
def test_missing_office_gives_readable_message(tmp_path, fake_com, func, name, prog_id):
    fake_com.dispatch_error = -2147221005  # invalid class string
    src = tmp_path / name
    src.write_bytes(b"x")

    with pytest.raises(RuntimeError) as excinfo:
        func(str(src), str(tmp_path / "out.pdf"))

    message = str(excinfo.value)
    assert "-2147221005" not in message
    assert prog_id.split(".")[0] in message
    # The thread is still uninitialised even though dispatch failed.
    assert fake_com.names()[-1] == "CoUninitialize"


@pytest.mark.parametrize("func, name, prog_id", CONVERTERS)
def test_failure_still_uninitialises_and_quits(tmp_path, fake_com, func, name, prog_id):
    src = tmp_path / name
    src.write_bytes(b"x")

    def boom(*a, **k):
        raise FakeComError(-2147352567)

    monkey = {"Word.Application": "Documents", "PowerPoint.Application": "Presentations",
              "Excel.Application": "Workbooks"}[prog_id]
    original = FakeCollection.Open
    FakeCollection.Open = boom
    try:
        with pytest.raises(RuntimeError):
            func(str(src), str(tmp_path / "out.pdf"))
    finally:
        FakeCollection.Open = original

    assert monkey  # sanity: the collection name is the one we expect to fail
    assert fake_com.names()[-1] == "CoUninitialize"


def test_word_no_longer_uses_docx2pdf():
    """docx2pdf never calls CoInitialize and quits the user's Word."""
    import inspect
    source = inspect.getsource(convert)
    assert "docx2pdf" not in source
