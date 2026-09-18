"""Alembic environment - async recipe.

Both target engines (SQLite via aiosqlite, Postgres via asyncpg) are async
drivers (see towing_backend.app's module docstring for why), so migrations
run through SQLAlchemy's async engine, not the sync `engine_from_config`
Alembic's default template uses.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import order matters here only in that both must happen before
# `target_metadata` is read below - `towing_backend.models` registers
# `Account`/`AccountSession` onto the same `Base.metadata` that
# `towing_backend.db` also defines `garages` on.
from towing_backend.db import Base
from towing_backend.models import Account, AccountSession  # noqa: F401

config = context.config

if config.config_file_name is not None:
    # `disable_existing_loggers` defaults to True, which would silently
    # disable every logger created before this call (including any of
    # `towing_backend`'s own, e.g. `settings.py`'s startup warning) -
    # `run_migrations` runs on every `create_app()` call, not just via the
    # standalone `alembic` CLI, so this must not clobber application
    # logging each time. Alembic's own docs call this out as the fix for
    # exactly this embedded/programmatic-use case.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
