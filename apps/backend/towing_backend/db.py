"""Async SQLAlchemy engine/session plumbing, plus the `garages`,
`truck_profiles`, and `trailer_profiles` Core tables.

`Account`/`AccountSession` (see `towing_backend.models`) are ORM-mapped
declarative classes - that shape is forced on them by fastapi-users' own
SQLAlchemy adapter, which subclasses `Mapped`/`mapped_column`. `garages`,
`truck_profiles`, and `trailer_profiles` stay plain SQLAlchemy Core
`Table`s, queried directly with Core `insert`/`select`/`update`/`delete`
statements (see `towing_backend.garages`, `towing_backend.truck_profiles`,
`towing_backend.trailer_profiles`) rather than the ORM, per ADR 0011's
"SQLAlchemy Core, not the full ORM" decision - these are the tables in this
schema that decision was actually free to apply to. All live on the same
`MetaData` (`Base.metadata`) so Alembic and `create_all` see every table
together, and so their `ForeignKey(...)` columns resolve correctly
regardless of import order.
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
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

# Issue #19: field-for-field matches to `towing_core.models.TruckProfile` /
# `TrailerProfile` plus the new `garage_id` FK - see that module's
# docstrings for why each field is optional or required. No `created_at`:
# the issue's persisted-schema decision lists only the domain fields plus
# `garage_id`, not an audit timestamp.
truck_profiles = Table(
    "truck_profiles",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "garage_id",
        Integer,
        ForeignKey("garages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("gvwr", Float, nullable=False),
    Column("front_gawr", Float, nullable=False),
    Column("rear_gawr", Float, nullable=False),
    Column("gcwr", Float, nullable=True),
    Column("nickname", String(255), nullable=True),
)

trailer_profiles = Table(
    "trailer_profiles",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "garage_id",
        Integer,
        ForeignKey("garages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("gvwr", Float, nullable=False),
    Column("gawr", Float, nullable=False),
    Column("axle_count", Integer, nullable=False),
    Column("uvw", Float, nullable=True),
    Column("nickname", String(255), nullable=True),
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
