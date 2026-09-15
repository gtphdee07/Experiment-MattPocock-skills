"""Static import-direction guards for the package layering.

These checks parse each source file with ``ast`` rather than importing it, so
they hold regardless of runtime import behavior or the CWD the suite runs from.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CORE_DIR = _REPO_ROOT / "packages" / "towing-core" / "towing_core"
_APP_DIR = _REPO_ROOT / "packages" / "towing-app" / "towing_app"
_STREAMLIT_APP_DIR = _REPO_ROOT / "apps" / "streamlit"

# towing_core is the pure, stdlib-only compute tier: it must never reach for a
# third-party dependency or a higher tier.
_CORE_FORBIDDEN = (
    "anthropic",
    "sqlite3",
    "argparse",
    "streamlit",
    "towing_app",
    "towing_cli",
)

# towing_app is the services tier: it may use anthropic / sqlite3 / towing_core
# but must not reach up into the client tiers.
_APP_FORBIDDEN = (
    "streamlit",
    "argparse",
    "towing_cli",
)

# apps/streamlit is the standalone offline calculator (the entry point plus
# the towing_streamlit package and its tests): it may import only streamlit +
# towing_core (+ stdlib). No anthropic, no persistence, no other client tier
# (see the plan's Phase 1; ADR 0008).
_STREAMLIT_FORBIDDEN = (
    "anthropic",
    "sqlite3",
    "argparse",
    "towing_app",
    "towing_cli",
)


def _dynamic_import_target(call: ast.Call) -> str | None:
    """Return the module name named by a dynamic-import call, if any.

    Handles ``importlib.import_module("x")`` / ``import_module("x")`` (the
    latter when imported via ``from importlib import import_module``) and
    ``__import__("x")``, where the module name is a string literal. None of
    these leave an ``ast.Import``/``ast.ImportFrom`` node, but they are
    equivalent to a static import for layering purposes and easy to spot when
    the module name is a literal (the common case for a lazily-loaded
    dependency; an attacker sophisticated enough to build the name at runtime
    or alias ``importlib`` itself is out of scope for this defense-in-depth
    backstop).
    """
    func = call.func
    is_import_module_call = (
        isinstance(func, ast.Attribute)
        and func.attr == "import_module"
        and isinstance(func.value, ast.Name)
        and func.value.id == "importlib"
    ) or (isinstance(func, ast.Name) and func.id == "import_module")
    is_dunder_import_call = isinstance(func, ast.Name) and func.id == "__import__"
    if not (is_import_module_call or is_dunder_import_call):
        return None
    if not call.args:
        return None
    first_arg = call.args[0]
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        return first_arg.value
    return None


def _imported_modules(path: Path) -> set[str]:
    """Return the top-level module name of every import (static or dynamic
    with a string-literal target) in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".", 1)[0])
        # Ignore relative imports (node.level > 0); they stay within the package.
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call):
            dynamic_target = _dynamic_import_target(node)
            if dynamic_target is not None:
                modules.add(dynamic_target.split(".", 1)[0])
    return modules


# Calls that can load or execute code in a way no static scan of their
# arguments can fully vouch for: ``exec``/``eval`` can run an arbitrary
# string built at runtime, and ``importlib.util.spec_from_file_location``
# loads a module from a file path rather than a name. Unlike
# ``importlib.import_module``/``__import__`` these have no fixed "module
# name" argument to check against the forbidden list, so they are flagged
# outright rather than only when their argument happens to be a forbidden
# name.
_SUSPICIOUS_BUILTIN_CALLS = ("exec", "eval")


def _suspicious_dynamic_calls(path: Path) -> list[str]:
    """Return the name of every suspicious dynamic-loading call in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in _SUSPICIOUS_BUILTIN_CALLS:
            findings.append(func.id)
        elif isinstance(func, ast.Attribute) and func.attr == "spec_from_file_location":
            findings.append("importlib.util.spec_from_file_location")
    return findings


def _violations(source_dir: Path, forbidden: tuple[str, ...]) -> list[str]:
    problems: list[str] = []
    for py_file in sorted(source_dir.rglob("*.py")):
        for module in sorted(_imported_modules(py_file)):
            if module in forbidden:
                rel = py_file.relative_to(_REPO_ROOT)
                problems.append(f"{rel} imports forbidden module '{module}'")
        for call_name in _suspicious_dynamic_calls(py_file):
            rel = py_file.relative_to(_REPO_ROOT)
            problems.append(
                f"{rel} uses dynamic code-loading call '{call_name}', which "
                "bypasses static import checks and is forbidden outright"
            )
    return problems


def test_towing_core_dir_exists() -> None:
    assert _CORE_DIR.is_dir(), f"expected towing_core package at {_CORE_DIR}"
    assert any(_CORE_DIR.rglob("*.py")), "no source files found under towing_core"


def test_towing_core_imports_stay_pure() -> None:
    problems = _violations(_CORE_DIR, _CORE_FORBIDDEN)
    assert not problems, "towing_core layering violation(s):\n" + "\n".join(problems)


def test_towing_app_does_not_import_client_tiers() -> None:
    assert _APP_DIR.is_dir(), f"expected towing_app package at {_APP_DIR}"
    problems = _violations(_APP_DIR, _APP_FORBIDDEN)
    assert not problems, "towing_app layering violation(s):\n" + "\n".join(problems)


def test_towing_streamlit_imports_stay_thin() -> None:
    assert _STREAMLIT_APP_DIR.is_dir(), (
        f"expected the streamlit app at {_STREAMLIT_APP_DIR}"
    )
    assert (_STREAMLIT_APP_DIR / "streamlit_app.py").is_file(), (
        "expected the entry point at apps/streamlit/streamlit_app.py"
    )
    problems = _violations(_STREAMLIT_APP_DIR, _STREAMLIT_FORBIDDEN)
    assert not problems, "towing_streamlit layering violation(s):\n" + "\n".join(
        problems
    )


# --- Regression coverage for dynamic-import detection (issue #25) ---------
#
# A prior audit flagged that `importlib.import_module(...)`, `__import__(...)`,
# and exec/eval-based loading satisfy neither ast.Import nor ast.ImportFrom,
# so they could slip past `_violations()` undetected even though they are
# equivalent (or worse) from a layering standpoint. These fixtures under
# tests/fixtures/dynamic_imports/ are never imported/executed by anything —
# they exist only to be parsed as text — and live outside the three scanned
# source trees so they don't themselves trip the real layering tests above.

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "dynamic_imports"


def test_import_module_call_with_forbidden_literal_is_detected() -> None:
    path = _FIXTURES_DIR / "forbidden_via_import_module.py"
    assert "sqlite3" in _imported_modules(path)


def test_dunder_import_call_with_forbidden_literal_is_detected() -> None:
    path = _FIXTURES_DIR / "forbidden_via_dunder_import.py"
    assert "argparse" in _imported_modules(path)


def test_exec_call_is_flagged_as_suspicious() -> None:
    path = _FIXTURES_DIR / "suspicious_exec.py"
    assert "exec" in _suspicious_dynamic_calls(path)


def test_eval_call_is_flagged_as_suspicious() -> None:
    path = _FIXTURES_DIR / "suspicious_eval.py"
    assert "eval" in _suspicious_dynamic_calls(path)


def test_spec_from_file_location_call_is_flagged_as_suspicious() -> None:
    path = _FIXTURES_DIR / "suspicious_spec_from_file_location.py"
    assert "importlib.util.spec_from_file_location" in _suspicious_dynamic_calls(path)


def test_violations_catches_dynamic_import_of_forbidden_module() -> None:
    """End-to-end: pointing `_violations()` (what the real tests above call)
    at the fixture dir must flag the dynamic imports, proving the hardened
    scanner would fail `test_towing_core_imports_stay_pure` had this file
    actually lived under towing_core."""
    problems = _violations(_FIXTURES_DIR, _CORE_FORBIDDEN)
    assert any("sqlite3" in p for p in problems)
    assert any("argparse" in p for p in problems)


def test_violations_catches_suspicious_dynamic_loading_calls() -> None:
    problems = _violations(_FIXTURES_DIR, _CORE_FORBIDDEN)
    assert any("'exec'" in p for p in problems)
    assert any("'eval'" in p for p in problems)
    assert any("spec_from_file_location" in p for p in problems)
