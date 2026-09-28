@echo off
rem Start PDF Aura without a console window.
rem Prefers the project's venv, then whatever pythonw is on PATH.
cd /d "%~dp0"

if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" main.py
    goto :eof
)
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
    goto :eof
)

where pythonw >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw main.py
    goto :eof
)

echo Python bulunamadi. Python 3.10+ kurun veya venv olusturun.
echo Python was not found. Install Python 3.10+ or create a venv.
pause
