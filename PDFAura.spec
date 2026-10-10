# PyInstaller spec for PDF Aura.
#
# Build with:  cd web && npm ci && npm run build && cd ..
#              pyinstaller --noconfirm PDFAura.spec
# The result is dist\PDFAura\, which setup.iss packages into the installer.
# pywebview brings its own hook (its JavaScript and the WebView2 loader
# DLLs) and pyinstaller-hooks-contrib covers pythonnet.
import os

block_cipher = None

# The window's page, built from web/ by Vite. It is not in git.
if not os.path.isfile(os.path.join("web", "dist", "index.html")):
    raise SystemExit("web/dist is missing: run  cd web && npm ci && npm run build  first")

datas = [
    ("assets", "assets"),
    ("web/dist", "web/dist"),
]

# models/ holds only READMEs in a clean clone; ship it if it has content.
if os.path.isdir("models"):
    datas.append(("models", "models"))

hiddenimports = [
    # pystray picks its backend at runtime, so PyInstaller cannot see it.
    "pystray._win32",
    # pywin32 modules used through win32com.client for the Office conversions.
    "win32com.client",
    "win32timezone",
    "pythoncom",
    "pywintypes",
]

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
    # Tk is not used since the window moved to WebView2 (#25).
    excludes=["torch", "tensorflow", "matplotlib", "pytest", "tkinter", "_tkinter"],
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
