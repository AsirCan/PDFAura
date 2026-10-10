"""Startup time and memory of a window, counting every process it spawns.

    python spikes/faz0/measure.py [runs] [variant ...]

Variants:
    tk-bare         an empty Tk window (the UI toolkit alone)
    tk-app          today's app (main.py)
    web-bare        pywebview + WebView2 with an empty page, fresh temp profile
    web-profile     same with a persistent WebView2 profile folder
    web-core        empty page, but src/core + src/ai loaded first like the real app
    exe             the PyInstaller build of the spike (run build_exe.py first)
    exe-core        the same build loading src/core + src/ai first
    tk-exe          today's app, built from PDFAura.spec by build_exe.py

"visible" is when a window titled "PDF Aura" appears; "ready" (web only) is
when the page has loaded and called back through the bridge. Memory is
read 4 s later and summed over the process and all its descendants
(msedgewebview2.exe: browser, GPU, renderer and utility processes).
private_ws_mb is what Task Manager's Memory column shows; working_set_mb
counts DLL pages shared between those processes once per process, so its
sum overstates.
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time

import win32gui
import win32process

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BUILD = os.path.join(tempfile.gettempdir(), "pdfaura-faz0", "build", "dist")
EXE = os.path.join(BUILD, "PDFAuraFaz0", "PDFAuraFaz0.exe")
TK_EXE = os.path.join(BUILD, "PDFAura", "PDFAura.exe")

TK_BARE = ("import tkinter as tk; r = tk.Tk(); r.title('PDF Aura'); r.geometry('1280x820'); "
           "r.after(9000, r.destroy); r.mainloop()")

VARIANTS = {
    "tk-bare": ([sys.executable, "-c", TK_BARE], False),
    "tk-app": ([sys.executable, os.path.join(ROOT, "main.py")], False),
    "web-bare": ([sys.executable, os.path.join(HERE, "app.py"), "--minimal"], True),
    "web-profile": ([sys.executable, os.path.join(HERE, "app.py"), "--minimal", "--persistent-profile"], True),
    "web-core": ([sys.executable, os.path.join(HERE, "app.py"), "--minimal", "--import-core"], True),
    "exe": ([EXE, "--minimal"], True),
    "exe-core": ([EXE, "--minimal", "--import-core"], True),
    "tk-exe": ([TK_EXE], False),
}


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


class PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD)] + [
        (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                       "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                       "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage",
                                       "PrivateUsage")] + [
        # PROCESS_MEMORY_COUNTERS_EX2 (Windows 10 1809+): what Task Manager shows.
        ("PrivateWorkingSetSize", ctypes.c_uint64), ("SharedCommitUsage", ctypes.c_uint64)]


k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
k32.OpenProcess.restype = ctypes.c_void_p
k32.CloseHandle.argtypes = [ctypes.c_void_p]
psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]


def process_tree(root_pid):
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    parents = {}
    ok = k32.Process32FirstW(snap, ctypes.byref(entry))
    while ok:
        parents[entry.th32ProcessID] = (entry.th32ParentProcessID, entry.szExeFile)
        ok = k32.Process32NextW(snap, ctypes.byref(entry))
    k32.CloseHandle(snap)
    tree, frontier = {root_pid: parents.get(root_pid, (0, "?"))[1]}, [root_pid]
    while frontier:
        pid = frontier.pop()
        for child, (parent, name) in parents.items():
            if parent == pid and child not in tree:
                tree[child] = name
                frontier.append(child)
    return tree


def memory(pid):
    handle = k32.OpenProcess(0x1000 | 0x0010, False, pid)   # QUERY_LIMITED_INFORMATION | VM_READ
    if not handle:
        return 0, 0, 0
    pmc = PMC()
    pmc.cb = ctypes.sizeof(pmc)
    psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb)
    k32.CloseHandle(handle)
    return pmc.WorkingSetSize, pmc.PrivateUsage, pmc.PrivateWorkingSetSize


def window_visible(pid):
    found = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == "PDF Aura":
            if win32process.GetWindowThreadProcessId(hwnd)[1] == pid:
                found.append(hwnd)
    win32gui.EnumWindows(cb, None)
    return bool(found)


def run_once(variant):
    cmd, web = VARIANTS[variant]
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    env.pop("OPENBLAS_NUM_THREADS", None)
    started = time.time()
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace")
    ready = {}

    def read():
        for line in proc.stdout:
            if line.startswith("READY "):
                ready["t"] = float(line.split()[1])
    threading.Thread(target=read, daemon=True).start()
    try:
        visible = None
        deadline = started + 60
        while time.time() < deadline:
            if visible is None and window_visible(proc.pid):
                visible = time.time() - started
            if visible is not None and (not web or "t" in ready):
                break
            if proc.poll() is not None:
                raise RuntimeError(f"{variant} exited with {proc.returncode}")
            time.sleep(0.01)
        time.sleep(4)
        tree = process_tree(proc.pid)
        ws = priv = private_ws = 0
        for pid in tree:
            w, p, pw = memory(pid)
            ws += w
            priv += p
            private_ws += pw
        return {"visible_s": round(visible, 2) if visible else None,
                "ready_s": round(ready["t"] - started, 2) if "t" in ready else None,
                "processes": len(tree), "private_ws_mb": round(private_ws / 2**20),
                "working_set_mb": round(ws / 2**20),
                "private_mb": round(priv / 2**20)}
    finally:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        proc.wait()


def main():
    args = sys.argv[1:]
    runs = int(args.pop(0)) if args and args[0].isdigit() else 5
    variants = args or [v for v in VARIANTS if "exe" not in v or os.path.exists(VARIANTS[v][0][0])]
    summary = {}
    for variant in variants:
        results = [run_once(variant) for _ in range(runs)]
        median = {key: statistics.median([r[key] for r in results if r[key] is not None] or [0])
                  for key in results[0]}
        summary[variant] = median
        print(f"{variant:12} {json.dumps(median)}", flush=True)
    return summary


if __name__ == "__main__":
    main()
