# PyInstaller spec for PDF Aura.
#
# Build with:  pyinstaller --noconfirm PDFAura.spec
# The result is dist\PDFAura\, which setup.iss packages into the installer.
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = [
    ("assets", "assets"),
]

# models/ holds only READMEs in a clean clone; ship it if it has content.
if os.path.isdir("models"):
    datas.append(("models", "models"))

# tkinterdnd2 ships the tkdnd Tcl package as data; without it drag and drop
# fails at startup in a frozen build.
datas += collect_data_files("tkinterdnd2")

hiddenimports = [
    # pystray picks its backend at runtime, so PyInstaller cannot see it.
    "pystray._win32",
    # pywin32 modules used through win32com.client for the Office conversions.
    "win32com.client",
    "win32timezone",
    "pythoncom",
    "pywintypes",
]
hiddenimports += collect_submodules("tkinterdnd2")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # faster-whisper and its model are downloaded on first use rather than
    # bundled; excluding the heavy training stack keeps the build small.
    excludes=["torch", "tensorflow", "matplotlib", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDFAura",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # windowed app; crashes go to %APPDATA%\PDFAura\crash.log
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/app_icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PDFAura",
)
