"""Issue #22: dead code, no tests, UI access from worker threads, loose pins."""
import ast
import os
import re

import pytest

from conftest import ROOT

def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


# ── Worker threads reach the page only through events (#22.3, #25) ──────

APP_FILES = sorted(os.path.join("src", "app", n) for n in os.listdir(os.path.join(ROOT, "src", "app"))
                   if n.endswith(".py"))


@pytest.mark.parametrize("path", APP_FILES)
def test_only_the_window_touches_pywebview(path):
    """The tools and their jobs know nothing of the window; window.py owns
    it and bridge.py only opens its dialogs."""
    if os.path.basename(path) in ("window.py", "bridge.py"):
        return
    tree = ast.parse(read(path))
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                for alias in node.names}
    imported |= {(node.module or "").split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "webview" not in imported


@pytest.mark.parametrize("path", APP_FILES)
def test_scripts_reach_the_page_only_through_the_event_bus(path):
    """A worker that ran a script in the page itself would skip the queue
    that holds events until the page is listening (events.py)."""
    if os.path.basename(path) in ("events.py", "window.py"):
        return
    source = read(path)
    assert not re.search(r"\b(run_js|evaluate_js)\(", source), path


def test_the_scanner_snapshots_its_pages_before_exporting():
    """The export walked the tab's live page list from the worker thread
    (see #12). It runs in src.app.scanner, which only gets a snapshot that
    the board takes before the job starts."""
    import inspect
    from src.app import scanner
    assert list(inspect.signature(scanner.export_pdf).parameters) == ["ctx", "shots", "output_pdf", "mode"]
    source = read("src/app/scanboard.py")
    body = source.split("def export(")[1].split("\n    def ")[0]
    assert body.index("scanner.snapshot(self.pages)") < body.index("start_work(")


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
    workflow = read(".github/workflows/ci.yml")
    python = workflow.split("  python:")[1].split("\n  web:")[0]
    assert "windows-latest" in python
    assert "pytest" in python
    assert "requirements-dev.txt" in python


def test_ci_checks_the_page_and_the_packaged_app():
    workflow = read(".github/workflows/ci.yml")
    for step in ("npm run lint", "npm run check", "npm test", "npm run build", "pytest -m e2e",
                 "pyinstaller --noconfirm PDFAura.spec", "setup.iss"):
        assert step in workflow, step


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
