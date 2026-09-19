"""Regression test for issue #35: uvicorn's `--factory` mode invokes
`create_app()` from inside its own already-running event loop, and
`create_app()`'s `run_migrations()` call drives Alembic's async migration
path (`alembic/env.py`'s `asyncio.run(...)`), which cannot nest inside a
running loop - the server crashed on every real startup.

This is the one test in this suite that can't use `TestClient`/`conftest.py`'s
`app` fixture: both construct the app object directly, outside of any
process launch, which is exactly the scenario that does *not* reproduce the
bug (see `towing_backend.asgi`'s own module docstring). Proving the fix
holds means spawning a real `uvicorn` process against the real entrypoint,
the same way a process manager would - TESTING.md's "test external seams
directly" principle, applied here to the process-launch boundary rather
than a third-party API/database.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# Deliberately avoids the substring "real" in its name - this test needs no
# external API/DB credential (TESTING.md's `test_real_*` convention, and the
# repo's default `-k "not real"` gate), so it must stay in the default suite.
def test_asgi_entrypoint_starts_when_launched_as_a_subprocess(tmp_path: Path) -> None:
    port = _free_port()
    db_path = tmp_path / "asgi-entrypoint.db"
    env = {
        **os.environ,
        "TOWING_BACKEND_DB_URL": f"sqlite+aiosqlite:///{db_path}",
        "TOWING_BACKEND_CORS_ORIGIN": "http://localhost:5173",
        "TOWING_BACKEND_SECRET": "test-secret-for-asgi-entrypoint-regression-test",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "towing_backend.asgi:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise AssertionError(
                    f"uvicorn exited early (code {process.returncode}) - "
                    f"issue #35 regression?\n{output}"
                )
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/health", timeout=1
                ) as response:
                    assert response.status == 200
                    return
            except (urllib.error.URLError, ConnectionError) as exc:
                last_error = exc
                time.sleep(0.25)
        raise AssertionError(f"server never became healthy: {last_error}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
