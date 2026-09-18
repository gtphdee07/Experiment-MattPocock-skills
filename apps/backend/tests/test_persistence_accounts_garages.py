"""Tier 2 (persistence-layer, offline): the `accounts`/`garages` tables
directly, with no FastAPI/fastapi-users routing involved - insert, the
unique-email constraint, the unique-`account_id`-per-garage constraint, and
`ON DELETE CASCADE`. Same real-SQLite-file-per-test pattern as
`test_sqlite_storage.py` testing `SqliteTruckStore` without going through
the CLI.

Schema comes from the real Alembic migrations (`run_migrations`), never an
ad-hoc `CREATE TABLE` - issue #18 Story 19 is explicit that this is true
for every environment, not just production.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

import pytest
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from towing_backend.db import garages, make_engine, make_session_factory
from towing_backend.migrate import run_migrations
from towing_backend.models import Account
from towing_backend.settings import Settings


def run(coro: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coro)


def _make_session(settings: Settings) -> AsyncSession:
    # Must run before any event loop exists in this thread: `run_migrations`
    # calls `asyncio.run()` internally, which errors if a loop is already
    # running - so every test builds its session here, at the top of the
    # (plain sync) test function, before `run()`/`asyncio.run()` opens one.
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    return session_factory()


async def _insert_account(session: AsyncSession, *, email: str) -> int:
    result = await session.execute(
        insert(Account)
        .values(email=email, hashed_password="not-a-real-hash")
        .returning(Account.id)
    )
    await session.commit()
    return result.scalar_one()


# --- Insert + round trip -----------------------------------------------------


def test_insert_account_and_garage_round_trip(settings: Settings) -> None:
    session = _make_session(settings)

    async def body() -> None:
        async with session:
            account_id = await _insert_account(session, email="addie@example.com")

            await session.execute(insert(garages).values(account_id=account_id))
            await session.commit()

            account = (
                await session.execute(select(Account).where(Account.id == account_id))
            ).scalar_one()
            assert account.email == "addie@example.com"

            garage_row = (
                await session.execute(
                    select(garages).where(garages.c.account_id == account_id)
                )
            ).one()
            assert garage_row.account_id == account_id
            assert garage_row.created_at is not None

    run(body())


# --- Unique email constraint --------------------------------------------------


def test_duplicate_email_violates_unique_constraint(settings: Settings) -> None:
    session = _make_session(settings)

    async def body() -> None:
        async with session:
            await _insert_account(session, email="addie@example.com")

            with pytest.raises(IntegrityError):
                await session.execute(
                    insert(Account).values(
                        email="addie@example.com", hashed_password="another-hash"
                    )
                )
                await session.commit()

    run(body())


# --- Unique account_id-per-garage constraint (1:1 ownership, ADR 0010) -----


def test_duplicate_garage_for_same_account_violates_unique_constraint(
    settings: Settings,
) -> None:
    session = _make_session(settings)

    async def body() -> None:
        async with session:
            account_id = await _insert_account(session, email="addie@example.com")
            await session.execute(insert(garages).values(account_id=account_id))
            await session.commit()

            with pytest.raises(IntegrityError):
                await session.execute(insert(garages).values(account_id=account_id))
                await session.commit()

    run(body())


# --- ON DELETE CASCADE --------------------------------------------------------


def test_deleting_account_cascades_to_garage(settings: Settings) -> None:
    session = _make_session(settings)

    async def body() -> None:
        async with session:
            account_id = await _insert_account(session, email="addie@example.com")
            await session.execute(insert(garages).values(account_id=account_id))
            await session.commit()

            await session.execute(delete(Account).where(Account.id == account_id))
            await session.commit()

            remaining = (
                await session.execute(
                    select(garages).where(garages.c.account_id == account_id)
                )
            ).all()
            assert remaining == []

    run(body())
