"""Programmatic Alembic entry point.

Every environment - SQLite dev/test, Postgres production, and the tier-3
contract bench - creates its schema by running these same migrations,
never an ad-hoc `CREATE TABLE IF NOT EXISTS` (issue #18 Story 19). Wrapping
Alembic's `Config`/`command.upgrade` here, rather than shelling out to the
`alembic` CLI, lets `towing_backend.app.create_app` and the test fixtures
point migrations at an arbitrary `database_url` (a fresh `tmp_path` SQLite
file per test, or a real Postgres URL) without touching `alembic.ini`.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_ALEMBIC_INI = _BACKEND_ROOT / "alembic.ini"
_SCRIPT_LOCATION = _BACKEND_ROOT / "alembic"


def run_migrations(database_url: str) -> None:
    config = Config(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_SCRIPT_LOCATION))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
