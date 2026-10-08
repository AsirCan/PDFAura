"""Issue #21: build steps that did not work and README claims that were wrong."""
import os
import re
import subprocess

import pytest

from conftest import ROOT


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


# ── Files the documented build needs ──────────────────────────────────────

def test_the_pyinstaller_spec_exists():
    """README said to run `pyinstaller PDFAura.spec`; it was not in the repo."""
    assert os.path.isfile(os.path.join(ROOT, "PDFAura.spec"))


def test_the_spec_is_not_gitignored():
    """.gitignore excluded *.spec, which is why it was never committed."""
    result = subprocess.run(["git", "check-ignore", "PDFAura.spec"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0, "PDFAura.spec is still ignored by git"


def test_the_spec_is_valid_python():
    """A spec file is executed as Python by PyInstaller."""
    import ast
    ast.parse(read("PDFAura.spec"))


def test_the_spec_keeps_the_runtime_only_imports():
    spec = read("PDFAura.spec")
    # pystray chooses its backend at runtime and tkinterdnd2 ships Tcl data;
    # neither survives a frozen build without being named here.
    assert "pystray._win32" in spec
    assert "tkinterdnd2" in spec


def test_the_license_file_exists():
    """README linked to [MIT Lisansı](LICENSE) with no LICENSE file."""
    licence = read("LICENSE")
    assert "MIT License" in licence
    assert "Copyright (c)" in licence


def test_every_relative_readme_link_resolves():
    readme = read("README.md")
    targets = re.findall(r"\]\((?!https?://|#)([^)\s]+)\)", readme)
    missing = [t for t in targets if not os.path.exists(os.path.join(ROOT, t))]
    assert missing == [], f"broken links in README: {missing}"


def test_every_readme_image_exists():
    readme = read("README.md")
    images = re.findall(r'src="((?!https?://)[^"?]+)[^"]*"', readme)  # drop ?v= cache busters
    missing = [i for i in images if not os.path.exists(os.path.join(ROOT, i))]
    assert missing == [], f"missing images: {missing}"


def test_readme_embeds_the_demo_videos():
    """The screenshots became videos. GitHub only plays an attachment URL
    that stands on a line of its own."""
    videos = re.findall(r"^https://github\.com/user-attachments/assets/[0-9a-f-]+$",
                        read("README.md"), re.MULTILINE)
    assert len(videos) >= 8, f"expected the demo videos, found {len(videos)}"
    assert len(set(videos)) == len(videos), "the same video is embedded twice"


# ── Installer ─────────────────────────────────────────────────────────────

def test_installer_output_name_matches_the_readme():
    """README promised PDFAura-Setup.exe; the script produced PDFAura.exe."""
    assert "OutputBaseFilename=PDFAura-Setup" in read("setup.iss")


def test_ghostscript_bundling_is_optional():
    """assets\\gs10040w64.exe is not in the repo, so `iscc setup.iss` failed."""
    iss = read("setup.iss")
    assert "#if FileExists(GhostscriptInstaller)" in iss
    assert iss.count("#endif") >= 2


def test_the_broken_cx_freeze_script_is_gone():
    """It listed "fonttools" (the package is fontTools) and built to the wrong
    folder; the documented path is PyInstaller + Inno Setup."""
    assert not os.path.isfile(os.path.join(ROOT, "setup.py"))


# ── No personal paths ─────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["baslat.bat", "run_app.py", "main.py", "PDFAura.spec"])
def test_no_hardcoded_developer_paths(path):
    """A path baked in from one machine only ever worked on that machine."""
    content = read(path)
    assert "canca" not in content
    # An absolute path into a specific Python install, not a mention in prose.
    for line in content.splitlines():
        if "Python3" in line and ":" in line:
            assert line.lstrip().startswith(("#", "rem ", "REM ")), \
                f"hardcoded interpreter path: {line.strip()}"


def test_launcher_prefers_the_venv():
    batch = read("baslat.bat")
    assert "venv\\Scripts\\pythonw.exe" in batch
    assert "where pythonw" in batch


# ── Crash reporting ───────────────────────────────────────────────────────

def test_crash_log_goes_somewhere_writable(tmp_path, monkeypatch):
    """It was written to the working directory, which is Program Files in an
    installed build, so the real error was lost."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import main

    path = main._crash_log_path()
    assert str(tmp_path) in path
    assert path.endswith("crash.log")


def test_crash_is_recorded_and_surfaced(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import main

    shown = []
    import tkinter.messagebox as messagebox
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: shown.append(a))

    try:
        raise RuntimeError("kaboom")
    except RuntimeError:
        main._report_crash()

    log = open(main._crash_log_path(), encoding="utf-8").read()
    assert "kaboom" in log
    assert shown, "the user was told nothing"


# ── README claims match the code ──────────────────────────────────────────

def test_readme_does_not_claim_customtkinter():
    """The UI is plain ttk."""
    assert "CustomTkinter" not in read("README.md")


def test_readme_does_not_claim_grabcut_or_watershed():
    """Neither is used anywhere in the detection pipeline."""
    readme = read("README.md")
    assert "GrabCut" not in readme
    assert "Watershed" not in readme


def test_readme_puts_onnx_where_the_code_puts_it():
    """detect_document_corners() tries line and fast CV first; ONNX is the
    last fallback and must beat the current candidate."""
    readme = read("README.md")
    scanner = read("src/core/document_scanner.py")
    assert 'B -->|"Öncelik 1"| C["ONNX' not in readme
    assert "ONNX is slower" in scanner   # the code comment that states the order


def test_readme_describes_the_real_black_and_white_filter():
    """It is adaptive thresholding, not Otsu."""
    assert "Siyah-Beyaz (Otsu)" not in read("README.md")
    assert "adaptiveThreshold" in read("src/core/document_scanner.py")


def test_readme_does_not_promise_drag_and_drop_merge_ordering():
    """Merge orders with Up/Down buttons."""
    readme = read("README.md")
    assert "Sürükle-bırak sıralama ile sınırsız" not in readme


def test_readme_is_honest_about_the_first_run_download():
    """"100% offline" ignored the ~460 MB Whisper download on first use."""
    readme = read("README.md")
    assert "%25100%20Offline" not in readme
    assert "460 MB" in readme


def test_readme_calls_ghostscript_required_for_compression():
    """compress_pdf() raises without it, so "recommended" was wrong."""
    assert "Sıkıştırma için gerekli" in read("README.md")


def test_readme_assistant_examples_actually_parse():
    """The listed commands produced no action at all."""
    from src.ai.intent_parser import parse_intent

    readme = read("README.md")
    section = readme.split("Çalışan örnek komutlar:")[1].split("---")[0]
    examples = re.findall(r'\*"([^"]+)"\*', section)
    assert len(examples) >= 5, f"expected several examples, found {examples}"

    for command in examples:
        intent = parse_intent(command)
        assert intent.get("action_chain"), f"no action parsed from {command!r}"


def test_models_readme_link_matches_the_downloader():
    """The manual URL pointed at a different repository than the script used."""
    downloader = read("download_models.py")
    models_readme = read("models/README.md")
    url = re.search(r'"url": "([^"]+u2netp\.onnx)"', downloader).group(1)
    assert url in models_readme
