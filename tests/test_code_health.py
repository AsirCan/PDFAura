"""Issue #22: dead code, no tests, Tk access from worker threads, loose pins."""
import ast
import os
import re

import pytest

from conftest import ROOT

GUI_FILES = sorted(
    [os.path.join("src", "gui", "tabs", n) for n in os.listdir(os.path.join(ROOT, "src", "gui", "tabs"))
     if n.startswith("tab_") and n.endswith(".py")]
    + [os.path.join("src", "gui", "main_window.py")]
)


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def thread_targets(tree):
    """Method names passed as threading.Thread(target=...)."""
    targets = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "Thread":
            for keyword in node.keywords:
                if keyword.arg == "target":
                    value = keyword.value
                    name = getattr(value, "attr", None) or getattr(value, "id", None)
                    if name:
                        targets.add(name)
    return targets


# ── Worker threads must not touch Tk (#22.3) ──────────────────────────────

@pytest.mark.parametrize("path", GUI_FILES)
def test_no_worker_thread_reads_a_tk_variable(path):
    """Tkinter marshals cross-thread access while the mainloop runs, but it is
    fragile; values are read on the main thread and passed in instead."""
    tree = ast.parse(read(path))
    targets = thread_targets(tree)

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in targets:
            continue
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call)
                    and getattr(sub.func, "attr", "") == "get"
                    and isinstance(sub.func.value, ast.Attribute)
                    and sub.func.value.attr.endswith("_var")):
                offenders.append(f"{node.name} reads {sub.func.value.attr} (line {sub.lineno})")

    assert offenders == [], f"{path}: {offenders}"


def test_the_scanner_snapshots_its_pages_before_exporting():
    """_run_scan walked self.pages from the worker thread (see #12)."""
    source = read("src/gui/tabs/tab_scanner.py")
    assert "def _run_scan(self, output_pdf, snapshot, mode):" in source
    body = source.split("def _run_scan(")[1].split("\n    def ")[0]
    assert "self.pages" not in body, "the worker still reads the live page list"


# ── Dead code (#22.1) ─────────────────────────────────────────────────────

REMOVED = {
    "src/core/document_scanner.py": [
        "_detect_strategy_contour_hierarchy", "_detect_strategy_canny_aggressive",
        "_detect_strategy_adaptive", "_detect_strategy_morphological",
        "_detect_strategy_hough", "_detect_strategy_color_based",
        "_find_best_quad_contour", "_is_image_border", "_calculate_quad_score",
        "_group_lines", "_find_line_intersections", "_line_intersection",
        "_evaluate_corners_quality", "_calculate_inward_score",
        "scan_document", "save_scanned_image", "scanned_image_to_pdf",
    ],
    "src/core/document_scanner_ml.py": ["_detect_with_grabcut", "_detect_with_watershed"],
    "src/core/task_manager.py": ["run_parallel", "is_large_file"],
    "src/gui/helpers.py": ["operation_done", "build_file_picker_row"],
}


@pytest.mark.parametrize("path, names", sorted(REMOVED.items()))
def test_dead_code_is_gone(path, names):
    tree = ast.parse(read(path))
    defined = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    still_there = sorted(defined & set(names))
    assert still_there == [], f"{path} still defines {still_there}"


def test_the_live_scanner_entry_points_survive():
    """Deleting dead code must not have taken the used functions with it."""
    from src.core import document_scanner as scanner
    for name in ("detect_document_corners", "perspective_warp", "apply_scan_mode",
                 "rotate_image", "scanned_images_to_pdf", "target_size_from_corners",
                 "imread_unicode", "imwrite_unicode"):
        assert hasattr(scanner, name), f"{name} was removed by mistake"


def test_no_module_level_function_is_unreachable():
    """Guards against a new dead cluster forming in the scanner."""
    source = read("src/core/document_scanner.py")
    tree = ast.parse(source)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    calls = {}
    for name, node in funcs.items():
        used = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name):
                used.add(sub.id)
            elif isinstance(sub, ast.Attribute):
                used.add(sub.attr)
        calls[name] = used & set(funcs)

    # Public names are the module's API; everything else must be reachable.
    roots = {name for name in funcs if not name.startswith("_")}
    reachable, stack = set(), list(roots)
    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        stack.extend(calls.get(current, ()))

    assert sorted(set(funcs) - reachable) == []


# ── Dependency pins (#22.4) ───────────────────────────────────────────────

def requirement_lines(path):
    for raw in read(path).splitlines():
        line = raw.split("#")[0].strip()
        if line and not line.startswith("-r"):
            yield line


def test_every_dependency_has_a_lower_bound():
    unpinned = [line for line in requirement_lines("requirements.txt")
                if not re.search(r"[><=]=", line)]
    assert unpinned == [], f"no version bound: {unpinned}"


def test_the_breaking_dependencies_have_upper_bounds():
    """opencv 5.x and numpy 2.x both shipped breaking changes."""
    lines = list(requirement_lines("requirements.txt"))
    for package in ("opencv-python", "numpy", "pypdf", "PyMuPDF"):
        line = next(l for l in lines if l.lower().startswith(package.lower()))
        assert "<" in line, f"{package} has no upper bound: {line}"


def test_dev_requirements_exist_and_include_pytest():
    dev = read("requirements-dev.txt")
    assert "-r requirements.txt" in dev
    assert "pytest" in dev


def test_pytest_is_not_a_runtime_dependency():
    assert "pytest" not in read("requirements.txt")


# ── CI (#22.2) ────────────────────────────────────────────────────────────

def test_a_ci_workflow_runs_the_tests_on_windows():
    workflow = read(".github/workflows/tests.yml")
    assert "windows-latest" in workflow
    assert "pytest" in workflow
    assert "requirements-dev.txt" in workflow


def test_test_fixtures_are_generated_not_committed():
    """.gitignore excludes *.pdf and *.png, so fixtures must be built at run
    time; a committed fixture would silently vanish from a fresh clone."""
    gitignore = read(".gitignore")
    assert "*.pdf" in gitignore and "*.png" in gitignore

    committed = [name for name in os.listdir(os.path.join(ROOT, "tests"))
                 if name.lower().endswith((".pdf", ".png", ".jpg", ".docx"))]
    assert committed == [], f"committed fixtures would be gitignored: {committed}"

    conftest = read("tests/conftest.py")
    assert "def make_pdf(" in conftest, "no run-time PDF fixture helper"
