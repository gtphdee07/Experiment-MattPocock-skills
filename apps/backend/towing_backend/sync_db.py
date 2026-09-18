"""Synchronous SQLAlchemy engine/session plumbing for the `weigh_events`
table only (issue #21).

`towing_app.services.record_weigh_event` is reused **unmodified** (per issue
#21's own Implementation Decisions) and is fully synchronous top to bottom -
it expects a synchronous `towing_core.storage.WeighEventStore` (exactly
`save(record) -> None` and `list() -> list[WeighEventRecord]`), and it is not
itself async-aware. `apps/backend`'s other tables (`accounts`, `garages`,
`truck_profiles`, `trailer_profiles`) all go through the async engine in
`towing_backend.db` because fastapi-users' SQLAlchemy adapter requires an
`AsyncSession` (ADR 0015) - but nothing about `weigh_events` forces that, and
reimplementing `record_weigh_event` as async would violate "called
unmodified". So this module builds a **second**, synchronous engine/session
factory pointed at the same `database_url`, translated to a sync-capable
driver below - never the async engine itself. Every call through a store
built on this session factory must be offloaded via
`fastapi.concurrency.run_in_threadpool` from the `async def` route handlers
that use it (see `towing_backend.weigh_events_store` and
`towing_backend.weigh_events_routes`), exactly the offloading pattern
`towing_backend.photo_ocr`'s `_run_extraction` already established for
issue #20's synchronous Claude-vision adapter calls.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# `apps/backend`'s async engines use `sqlite+aiosqlite://`/`postgresql+
# asyncpg://` (see towing_backend.db.make_engine / towing_backend.settings) -
# neither driver has a synchronous mode, so the URL's driver is swapped for a
# sync-capable one rather than reused as-is. `sqlite` needs no explicit
# driver suffix (the stdlib `sqlite3` module is SQLAlchemy's default sync
# SQLite dialect). Postgres uses `psycopg2` (added as an explicit backend
# dependency alongside `asyncpg` - see apps/backend/pyproject.toml) since
# `asyncpg` itself has no sync mode to fall back to.
_ASYNC_TO_SYNC_DRIVER_PREFIXES: tuple[tuple[str, str], ...] = (
    ("sqlite+aiosqlite://", "sqlite://"),
    ("postgresql+asyncpg://", "postgresql+psycopg2://"),
)


def sync_database_url(database_url: str) -> str:
    """Translates an async-driver `database_url` to its sync-driver
    equivalent, for the second engine this module builds. A URL that
    already names no async driver (or an unrecognized one) is returned
    unchanged - callers that pass a bespoke URL are responsible for it
    already being sync-capable."""
    for async_prefix, sync_prefix in _ASYNC_TO_SYNC_DRIVER_PREFIXES:
        if database_url.startswith(async_prefix):
            return sync_prefix + database_url[len(async_prefix) :]
    return database_url


def make_sync_engine(database_url: str) -> Engine:
    engine = create_engine(sync_database_url(database_url))
    if engine.url.get_backend_name() == "sqlite":
        # Mirrors `towing_backend.db.make_engine`'s own PRAGMA setup - SQLite
        # does not enforce FOREIGN KEY constraints (the `weigh_events.
        # garage_id` FK's `ON DELETE CASCADE`) unless told to per-connection.
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def make_sync_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
