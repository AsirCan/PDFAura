import os
import subprocess
import sys
import threading
import urllib.request

from src.core.lang_manager import _
from src.utils.process_helper import CREATE_NO_WINDOW

def _installed_dir():
    """Where Tesseract ended up, or "" if it is not installed."""
    for candidate in (
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Tesseract-OCR"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Tesseract-OCR"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR"),
    ):
        if candidate and os.path.isdir(candidate):
            return candidate
    return ""


def install_target_tesseract(on_success=None, on_error=None):
    """
    Downloads and installs Tesseract silently via winget,
    then downloads the Turkish language pack.
    """
    def run_install():
        try:
            # 1. Install via Winget
            result = subprocess.run(
                ["winget", "install", "-e", "--id", "UB-Mannheim.TesseractOCR",
                 "--accept-source-agreements", "--accept-package-agreements", "--silent"],
                capture_output=True, text=True,
                creationflags=CREATE_NO_WINDOW,   # no console window in a packaged build
            )

            tess_path = _installed_dir()
            if not tess_path:
                # winget's exit code and output say far more than "the folder
                # is missing", which was the only thing checked before.
                detail = (result.stderr or result.stdout or "").strip()
                message = _("err_tesseract_install_failed").format(code=result.returncode)
                if detail:
                    message = message + "\n" + detail[:400]
                if on_error:
                    on_error(message)
                return

            # 2. Download Turkish Language Pack
            tessdata_dir = os.path.join(tess_path, "tessdata")
            tur_dest = os.path.join(tessdata_dir, "tur.traineddata")
            
            # Download URL for the fast model of Turkish
            tur_url = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/tur.traineddata"
            
            if not os.path.exists(tur_dest):
                try:
                    urllib.request.urlretrieve(tur_url, tur_dest)
                except PermissionError:
                    # Windows requires admin rights for Program Files
                    temp_path = os.path.join(os.environ["TEMP"], "tur.traineddata")
                    urllib.request.urlretrieve(tur_url, temp_path)
                    
                    try:
                        ps_cmd = f"Start-Process cmd -ArgumentList '/c copy /Y \"{temp_path}\" \"{tessdata_dir}\"' -Verb RunAs -Wait"
                        subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_cmd],
                                       creationflags=CREATE_NO_WINDOW)
                    except Exception:
                        pass
                        
            if on_success:
                on_success()
                
        except Exception as e:
            if on_error:
                on_error(f"{_('err_tesseract_install_error')}\n{e}")

    t = threading.Thread(target=run_install, daemon=True)
    t.start()
