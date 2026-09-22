import os
import sys
import win32process
import win32con
import win32service
import win32gui
import time

def launch():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    python_exe = os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Programs\Python\Python312\python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    si = win32process.STARTUPINFO()
    si.lpDesktop = r"WinSta0\Default"
    si.dwFlags = win32con.STARTF_USESHOWWINDOW
    si.wShowWindow = win32con.SW_SHOW

    cmd = f'"{python_exe}" "{os.path.join(base_dir, "main.py")}"'
    
    hProcess, hThread, dwProcessId, dwThreadId = win32process.CreateProcess(
        None,
        cmd,
        None,
        None,
        False,
        win32process.CREATE_NEW_PROCESS_GROUP | win32process.DETACHED_PROCESS,
        None,
        base_dir,
        si
    )
    print(f"PDF Aura launched successfully on user desktop (PID: {dwProcessId})")
    
    # Verify window appearance on Default desktop
    time.sleep(1.5)
    try:
        hDesk = win32service.OpenDesktop("Default", 0, False, win32con.GENERIC_ALL)
        hDesk.SetThreadDesktop()
        
        found = []
        def enum_cb(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            if "PDF Aura" in title:
                found.append((hwnd, title, win32gui.IsWindowVisible(hwnd)))
                # Bring to front
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
            return True
            
        win32gui.EnumWindows(enum_cb, None)
        if found:
            print(f"Verified window on Default desktop: {found}")
        else:
            print("Window is initializing...")
    except Exception as e:
        print(f"Desktop check note: {e}")

if __name__ == "__main__":
    launch()
