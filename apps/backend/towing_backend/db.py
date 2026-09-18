"""Async SQLAlchemy engine/session plumbing, plus the `garages` Core table.

`Account`/`AccountSession` (see `towing_backend.models`) are ORM-mapped
declarative classes - that shape is forced on them by fastapi-users' own
SQLAlchemy adapter, which subclasses `Mapped`/`mapped_column`. `garages`
stays a plain SQLAlchemy Core `Table`, queried directly with Core
`insert`/`select`/`delete` statements (see `towing_backend.garages`) rather
than the ORM, per ADR 0011's "SQLAlchemy Core, not the full ORM" decision -
this is the one table in this schema that decision was actually free to
apply to. Both live on the same `MetaData` (`Base.metadata`) so Alembic and
`create_all` see every table together, and so `garages.account_id`'s
`ForeignKey("accounts.id")` resolves correctly regardless of import order.
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    event,
    func,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


metadata: MetaData = Base.metadata

garages = Table(
    "garages",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "account_id",
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
)


def make_engine(database_url: str) -> AsyncEngine:
    engine = create_async_engine(database_url)
    if engine.url.get_backend_name() == "sqlite":
        # SQLite does not enforce FOREIGN KEY constraints (including
        # ON DELETE CASCADE) unless told to per-connection - without this,
        # deleting an Account would silently leave its Garage row behind on
        # SQLite while correctly cascading on Postgres, exactly the kind of
        # dialect drift TESTING.md's tier-3 Postgres bench exists to catch.
        # Enabled unconditionally here (not just for tests) so dev/test and
        # a hypothetical SQLite production target behave identically to
        # Postgres, and so the persistence-layer tests catch it offline.
        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
