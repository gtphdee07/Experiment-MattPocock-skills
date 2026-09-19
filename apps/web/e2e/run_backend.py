"""E2E-only launcher for the real `apps/backend` FastAPI app.

Not part of `apps/backend` itself (issue #30 is frontend-only - no change to
`apps/backend`, `towing_core`, or `towing_app` is in scope) - this lives
under `apps/web/e2e/` purely as Playwright's `webServer` command for the
authenticated-journey test project.

Why this exists instead of `uv run uvicorn towing_backend.app:create_app
--factory ...` (the form the issue's own brief suggests): with the uvicorn
version this workspace resolves (0.52.x), `--factory` mode invokes the
factory from *inside* the server's already-running asyncio event loop.
`towing_backend.migrate.run_migrations` (called unconditionally by
`create_app()`) calls `asyncio.run(...)` internally - which raises
"asyncio.run() cannot be called from a running event loop" when the
factory runs inside that loop. This is a latent bug in `apps/backend`
itself (out of scope to fix here), reproducible with a plain manual
`uvicorn --factory` launch, not something this script's approach
introduces. Building the app object with a single, eager `create_app()`
call *before* handing it to `uvicorn.run()` avoids the nested-loop
altogether, since `uvicorn.run()` only starts its own loop after this
script's own top-level code (never inside one) has already finished
building the app.
"""

from __future__ import annotations

import uvicorn

from towing_backend.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
