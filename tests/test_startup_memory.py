"""Issue #25: numpy's OpenBLAS reserved about 31 MB of commit per CPU thread
as it loaded, roughly 620 MB on a 20-thread machine, before the window even
opened. main.py caps it to one thread."""
import ast
import os
import site
import subprocess
import sys

import pytest

from conftest import ROOT


def _is_blas_cap(node):
    """os.environ.setdefault("OPENBLAS_NUM_THREADS", ...): setdefault, so a
    value the user set themselves is kept."""
    call = getattr(node, "value", None)
    return (isinstance(node, ast.Expr) and isinstance(call, ast.Call)
            and getattr(call.func, "attr", "") == "setdefault"
            and call.args and isinstance(call.args[0], ast.Constant)
            and call.args[0].value == "OPENBLAS_NUM_THREADS")


def _may_load_numpy(node):
    names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
             else [node.module or ""])
    return any(name.split(".")[0] in ("src", "numpy", "cv2") for name in names)


def test_blas_threads_are_capped_before_anything_imports_numpy():
    with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as f:
        body = ast.parse(f.read()).body
    cap = next((n.lineno for n in body if _is_blas_cap(n)), None)
    first_import = next(n.lineno for n in body
                        if isinstance(n, (ast.Import, ast.ImportFrom)) and _may_load_numpy(n))
    assert cap is not None, "main.py no longer caps OPENBLAS_NUM_THREADS"
    assert cap < first_import, "the cap comes after an import that loads numpy"


# Imports the app the way main.py does, then reads this process's commit.
_CHILD = """
import ctypes
import ctypes.wintypes as wt

import main
import numpy


class Counters(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
            "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage",
            "PrivateUsage")]


kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
kernel32.GetCurrentProcess.restype = ctypes.c_void_p
psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]
counters = Counters()
counters.cb = ctypes.sizeof(counters)
psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
print(counters.PrivateUsage / 2**20)
"""


@pytest.mark.skipif(sys.platform != "win32", reason="reads Windows process counters")
def test_loading_the_app_does_not_reserve_memory_per_cpu():
    """Uncapped, this was about 690 MB here (20 threads) and about 190 MB on
    a 4-vCPU CI runner; capped, about 80 MB on either."""
    env = {k: v for k, v in os.environ.items() if k != "OPENBLAS_NUM_THREADS"}
    # conftest moved APPDATA, which is also where pip's --user packages live.
    env["PYTHONUSERBASE"] = site.getuserbase()
    result = subprocess.run([sys.executable, "-c", _CHILD], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert float(result.stdout) < 150
