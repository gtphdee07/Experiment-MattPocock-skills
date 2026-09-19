"""Canonical ASGI entry point for a real process manager (uvicorn, gunicorn
with uvicorn workers, etc.) - `app` is built once, at import time, which
happens synchronously before any event loop exists.

This exists specifically to avoid issue #35: uvicorn's `--factory` mode
starts its own event loop *first*, then calls a factory function (e.g.
`towing_backend.app:create_app`) from *inside* that already-running loop to
build the app object. `create_app()`'s unconditional `run_migrations()` call
drives Alembic's async migration path (`alembic/env.py`'s
`asyncio.run(run_async_migrations())`), and `asyncio.run()` cannot be called
from inside a loop that's already running - it raises immediately, and the
server never starts.

A plain module-level `app` sidesteps this entirely: importing this module
runs `create_app()` during Python's normal, loop-free import step - the same
moment `apps/backend/tests/conftest.py`'s fixtures already build the app,
which is exactly why no existing test caught the bug. Point a process
manager here instead of at the factory:

    uvicorn towing_backend.asgi:app

(no `--factory` flag).
"""

from __future__ import annotations

from towing_backend.app import create_app

app = create_app()
