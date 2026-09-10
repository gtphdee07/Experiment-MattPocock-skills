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
_STREAMLIT_DIR = _REPO_ROOT / "apps" / "streamlit" / "towing_streamlit"

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

# towing_streamlit is the standalone offline calculator: it may import only
# streamlit + towing_core (+ stdlib). No anthropic, no persistence, no other
# client tier (see the plan's Phase 1; ADR 0008).
_STREAMLIT_FORBIDDEN = (
    "anthropic",
    "sqlite3",
    "argparse",
    "towing_app",
    "towing_cli",
)


def _imported_modules(path: Path) -> set[str]:
    """Return the top-level module name of every import in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".", 1)[0])
        # Ignore relative imports (node.level > 0); they stay within the package.
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".", 1)[0])
    return modules


def _violations(source_dir: Path, forbidden: tuple[str, ...]) -> list[str]:
    problems: list[str] = []
    for py_file in sorted(source_dir.rglob("*.py")):
        for module in sorted(_imported_modules(py_file)):
            if module in forbidden:
                rel = py_file.relative_to(_REPO_ROOT)
                problems.append(f"{rel} imports forbidden module '{module}'")
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
    assert _STREAMLIT_DIR.is_dir(), (
        f"expected towing_streamlit package at {_STREAMLIT_DIR}"
    )
    problems = _violations(_STREAMLIT_DIR, _STREAMLIT_FORBIDDEN)
    assert not problems, "towing_streamlit layering violation(s):\n" + "\n".join(
        problems
    )
