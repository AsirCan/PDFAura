import os
import subprocess
import urllib.request
import threading
from tkinter import messagebox

def install_target_tesseract(on_success=None, on_error=None):
    """
    Downloads and installs Tesseract silently via winget,
    then downloads the Turkish language pack.
    """
    def run_install():
        try:
            # 1. Install via Winget
            res = subprocess.run(
                ["winget", "install", "-e", "--id", "UB-Mannheim.TesseractOCR", "--accept-source-agreements", "--accept-package-agreements", "--silent"],
                capture_output=True, text=True
            )
            
            # Check if tesseract folder exists now
            tess_path = r"C:\Program Files\Tesseract-OCR"
            if not os.path.exists(tess_path):
                if on_error:
                    on_error("Tesseract kurulamadi. Winget basarisiz oldu veya yetki (UAC) verilmedi.\nLutfen manuel kurunuz.")
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
                        subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_cmd])
                    except Exception:
                        pass
                        
            if on_success:
                on_success()
                
        except Exception as e:
            if on_error:
                on_error(f"Kurulum Sirasinda Hata:\n{str(e)}")

    t = threading.Thread(target=run_install, daemon=True)
    t.start()
