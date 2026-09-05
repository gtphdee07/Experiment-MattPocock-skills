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
