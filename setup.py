import sys
from cx_Freeze import setup, Executable

sys.setrecursionlimit(5000)
build_exe_options = {
    "packages": [
        "os", "shutil", "subprocess", "sys", "threading", "tkinter", "io",
        "PyPDF2", "PIL", "pdf2docx", "docx2pdf", "reportlab", "pytesseract",
        "docx", "lxml", "fonttools", "cv2", "numpy", "fitz",
    ],
    "excludes": [],
    "include_files": [("assets/app_icon.ico", "assets/app_icon.ico")],
}

bdist_msi_options = {
    "add_to_path": False,
    "initial_target_dir": r"[ProgramFilesFolder]\PDFAura",
}

base = "Win32GUI" if sys.platform == "win32" else None

setup(
    name="PDF Aura",
    version="2.0",
    description="PDF sikistirma, kesme, birlestirme, duzenleme ve donusturme araci",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=[
        Executable(
            "main.py",
            base=base,
            target_name="PDFAura.exe",
            shortcut_name="PDF Aura",
            shortcut_dir="DesktopFolder",
            icon="assets/app_icon.ico",
        )
    ]
)
