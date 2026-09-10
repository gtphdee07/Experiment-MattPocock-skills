# Coding Standards

Architectural patterns and code quality expectations for this project.

## Project phase

This project is currently a **CLI** (Python stdlib + SQLite, no web framework). A **FastAPI phase** is planned but not started — no ADR or spec change has committed a timeline yet. Sections below are marked **(current)** or **(FastAPI phase)**. Don't hold CLI-phase code to FastAPI-phase rules: they don't apply until that phase actually begins.

## 1. Stack

- **Language:** Python 3.12+.
- **Database:** SQLite. **(current)** via the stdlib `sqlite3` module. **(FastAPI phase)** via SQLAlchemy (sync or `aiosqlite`-backed async, decide when the phase starts).
- **Framework:** **(FastAPI phase)** FastAPI, async endpoints where beneficial.

## 2. Code style & linting

Enforced by Ruff — line length, import grouping/sorting, and quote style all live in `pyproject.toml`'s `[tool.ruff]` config, not restated here. Run `uv run ruff check .` and `uv run ruff format .`.

## 3. Type hinting & validation

- **(current and FastAPI phase)** Every function signature, variable, and class attribute is typed (enforced by `mypy --strict`). Don't use `Any` unless truly unavoidable — reach for `TypeVar`/generics first.
- **(FastAPI phase)** Pydantic v2 schemas for all request, response, and internal data-transfer shapes.

## 4. SQLite & database patterns

- **(current and FastAPI phase)** Parameterized queries always (`?` placeholders) — never string-interpolate values into SQL.
- **(current and FastAPI phase)** Connection lifecycle via context managers (`with`), or a FastAPI dependency once that phase starts.
- **(current and FastAPI phase)** Store datetimes as ISO 8601 strings, booleans as integers.
- **(FastAPI phase)** Explicit migration files instead of ad-hoc schema changes. **(current)** A `CREATE TABLE IF NOT EXISTS` at store construction is the accepted lightweight equivalent while there's no migration tooling yet.
- **(FastAPI phase)** An ORM (SQLAlchemy) or hand-written SQL with the same parameterization discipline as above.

## 5. Async

**(FastAPI phase only.)** `async def` for endpoints doing network I/O or using an async DB driver; plain `def` for CPU-bound or synchronous work, so the event loop never blocks. The CLI phase is fully synchronous — this section doesn't apply yet.

## 6. Error handling & logging

- Never a bare `except: pass`. Catch specific exceptions.
- Use the `logging` module for failures and diagnostics — not for a CLI's primary output. A CLI command's user-facing result (the thing the user ran the command to see) goes to `print`/stdout; `logging` is for what went wrong or what happened internally, not what the user asked for.
- Fail fast: validate at the boundary — **(current)** at CLI input collection, **(FastAPI phase)** via Pydantic — before data reaches business logic or the database.
- **External dependency calls** (Claude API today; a future manufacturer lookup, payment, or account call): distinguish a *service* failure (the call couldn't complete — bad/missing credentials, network, timeout, rate limit) from a *content* failure (it completed, but couldn't determine one value). Raise a distinct exception for the former; return `None`/a per-field miss for the latter. Never let one degrade into the other's user-facing message. See ADR 0003 — and note its policy (no auto-retry, no idempotency handling) is a v1 baseline, not sufficient once payment/account dependencies land.

## 7. Monorepo layout

- **(current and FastAPI phase)** The repo is a single `uv` **workspace** with a **virtual root** — the root `pyproject.toml` has no `[project]` and no `[build-system]`; it exists to declare `[tool.uv.workspace]` members and hold shared config. Members: `packages/towing-core`, `packages/towing-app`, `apps/cli` (and, from Phase 1, `apps/streamlit`).
- **Shared tool config lives once, at the root `pyproject.toml`:** `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` (with `testpaths` spanning every member). Per-package `pyproject.toml` files carry only `[project]`, `[build-system]`, and their own `[tool.uv.sources]` for workspace deps. One `uv.lock`, one `.venv`; run every gate from the root (`uv run pytest`, `uv run mypy .`, `uv run ruff check .`).
- **Tier dependency rule — the arrow only points down:**
  - `towing-core` depends on **nothing** outside the standard library.
  - `towing-app` may depend on `towing-core` plus third-party adapter libraries (`anthropic`, and later a DB driver / ORM).
  - `apps/*` depend on `towing-app` (or `towing-core` alone for a stateless surface).
  - **Nothing depends on `apps/*`.**
- **`towing-core` must stay import-pure:** no `anthropic`, `sqlite3`, `argparse`, `streamlit`, or any higher-tier package. This is enforced by `packages/towing-core/tests/test_layering.py` (an `ast`-based scan, not a convention), which also keeps `towing_app` out of the client tiers.
- **Build backend:** every package uses `hatchling`. Each library package ships a `py.typed` marker so `mypy --strict` resolves exported types across the package boundary.
