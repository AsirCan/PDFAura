"""Build the spike and today's app with PyInstaller and compare their size.

    python spikes/faz0/build_exe.py

Both go to %TEMP%\\pdfaura-faz0\\build, never into the repository. The spike
build loads src/core and src/ai (--import-core), so it is close to what the
finished web app would ship minus its HTML/JS (a few hundred KB).
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(tempfile.gettempdir(), "pdfaura-faz0", "build")


def size_mb(path):
    total = 0
    for folder, _dirs, files in os.walk(path):
        total += sum(os.path.getsize(os.path.join(folder, f)) for f in files)
    return round(total / 2**20, 1)


def build_spike():
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", "PDFAuraFaz0",
        "--distpath", os.path.join(OUT, "dist"), "--workpath", os.path.join(OUT, "work-spike"),
        "--specpath", OUT,
        "--add-data", f"{os.path.join(HERE, 'web')};web",
        "--paths", ROOT, "--paths", HERE,
        "--hidden-import", "src.core.compress",
        # Same heavy-stack exclusions as PDFAura.spec.
        "--exclude-module", "torch", "--exclude-module", "tensorflow", "--exclude-module", "matplotlib",
        "--exclude-module", "pytest", "--exclude-module", "tkinter",
        os.path.join(HERE, "app.py"),
    ], check=True, cwd=ROOT)
    return os.path.join(OUT, "dist", "PDFAuraFaz0")


def build_today():
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--distpath", os.path.join(OUT, "dist"), "--workpath", os.path.join(OUT, "work-today"),
        "PDFAura.spec",
    ], check=True, cwd=ROOT)
    return os.path.join(OUT, "dist", "PDFAura")


def breakdown(dist, names):
    internal = os.path.join(dist, "_internal")
    rows = {}
    for name in names:
        path = os.path.join(internal, name)
        if os.path.isdir(path):
            rows[name] = size_mb(path)
        elif os.path.isfile(path):
            rows[name] = round(os.path.getsize(path) / 2**20, 1)
    return rows


if __name__ == "__main__":
    spike = build_spike()
    today = build_today()
    print("spike  ", size_mb(spike), "MB",
          breakdown(spike, ["webview", "pythonnet", "clr_loader", "web", "bottle.py"]))
    print("today  ", size_mb(today), "MB",
          breakdown(today, ["_tcl_data", "_tk_data", "tcl8", "tkinterdnd2", "_tkinter.pyd", "tcl86t.dll",
                            "tk86t.dll"]))
