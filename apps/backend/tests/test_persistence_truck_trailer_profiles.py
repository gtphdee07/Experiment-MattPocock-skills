"""Tier 2 (persistence-layer, offline): the `truck_profiles`/
`trailer_profiles` tables directly, with no FastAPI/fastapi-users routing
involved - insert, the `garage_id` foreign key, and `ON DELETE CASCADE`
when a Garage's owning Account is deleted (issue #19's Testing Decisions,
mirroring #18's `test_persistence_accounts_garages.py` pattern for
`garages`/`accounts`). Same real-SQLite-file-per-test pattern as
`test_sqlite_storage.py` testing `SqliteTruckStore` without going through
the CLI.

Schema comes from the real Alembic migrations (`run_migrations`), never an
ad-hoc `CREATE TABLE`, same as tier 2's precedent in #18.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, NamedTuple

import pytest
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from towing_backend.db import (
    garages,
    make_engine,
    make_session_factory,
    trailer_profiles,
    truck_profiles,
)
from towing_backend.migrate import run_migrations
from towing_backend.models import Account
from towing_backend.settings import Settings


def run(coro: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coro)


def _make_session(settings: Settings) -> AsyncSession:
    # Must run before any event loop exists in this thread - see
    # test_persistence_accounts_garages.py's `_make_session` docstring.
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    return session_factory()


class _AccountGarage(NamedTuple):
    account_id: int
    garage_id: int


async def _insert_account_and_garage(
    session: AsyncSession, *, email: str
) -> _AccountGarage:
    account_id = (
        await session.execute(
            insert(Account)
            .values(email=email, hashed_password="not-a-real-hash")
            .returning(Account.id)
        )
    ).scalar_one()
    garage_id = (
        await session.execute(
            insert(garages).values(account_id=account_id).returning(garages.c.id)
        )
    ).scalar_one()
    await session.commit()
    return _AccountGarage(account_id=account_id, garage_id=garage_id)


# --- Insert + round trip -----------------------------------------------------


def test_insert_truck_profile_round_trip(settings: Settings) -> None:
    session = _make_session(settings)

    async def body() -> None:
        async with session:
            owner = await _insert_account_and_garage(session, email="addie@example.com")

            await session.execute(
                insert(truck_profiles).values(
                    garage_id=owner.garage_id,
                    gvwr=10000.0,
                    front_gawr=4500.0,
                    rear_gawr=6500.0,
                )
            )
            await session.commit()

            row = (
                await session.execute(
                    select(truck_profiles).where(
                        truck_profiles.c.garage_id == owner.garage_id
                    )
                )
            ).one()
            assert row.gvwr == 10000.0
            assert row.gcwr is None
            assert row.nickname is None

    run(body())


def test_insert_trailer_profile_round_trip(settings: Settings) -> None:
    session = _make_session(settings)

    async def body() -> None:
        async with session:
            owner = await _insert_account_and_garage(session, email="addie@example.com")

            await session.execute(
                insert(trailer_profiles).values(
                    garage_id=owner.garage_id, gvwr=8000.0, gawr=3500.0, axle_count=2
                )
            )
            await session.commit()

            row = (
                await session.execute(
                    select(trailer_profiles).where(
                        trailer_profiles.c.garage_id == owner.garage_id
                    )
                )
            ).one()
            assert row.gvwr == 8000.0
            assert row.axle_count == 2
            assert row.uvw is None

    run(body())


# --- garage_id foreign key ----------------------------------------------


def test_truck_profile_with_nonexistent_garage_violates_foreign_key(
    settings: Settings,
) -> None:
    session = _make_session(settings)

    async def body() -> None:
        async with session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    insert(truck_profiles).values(
                        garage_id=999999,
                        gvwr=10000.0,
                        front_gawr=4500.0,
                        rear_gawr=6500.0,
                    )
                )
                await session.commit()

    run(body())


def test_trailer_profile_with_nonexistent_garage_violates_foreign_key(
    settings: Settings,
) -> None:
    session = _make_session(settings)

    async def body() -> None:
        async with session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    insert(trailer_profiles).values(
                        garage_id=999999, gvwr=8000.0, gawr=3500.0, axle_count=2
                    )
                )
                await session.commit()

    run(body())


# --- ON DELETE CASCADE, from Account all the way down to Profiles --------


def test_deleting_account_cascades_to_truck_and_trailer_profiles(
    settings: Settings,
) -> None:
    session = _make_session(settings)

    async def body() -> None:
        async with session:
            owner = await _insert_account_and_garage(session, email="addie@example.com")
            await session.execute(
                insert(truck_profiles).values(
                    garage_id=owner.garage_id,
                    gvwr=10000.0,
                    front_gawr=4500.0,
                    rear_gawr=6500.0,
                )
            )
            await session.execute(
                insert(trailer_profiles).values(
                    garage_id=owner.garage_id, gvwr=8000.0, gawr=3500.0, axle_count=2
                )
            )
            await session.commit()

            # Deleting the owning Account, not the Garage directly - this
            # is what actually happens in production (DELETE /users/me),
            # and it's the two-hop cascade (Account -> Garage -> Profiles)
            # issue #19 Story 19/20 asks this tier to confirm reaches all
            # the way down, not just Garage -> Profiles directly.
            await session.execute(delete(Account).where(Account.id == owner.account_id))
            await session.commit()

            remaining_trucks = (
                await session.execute(
                    select(truck_profiles).where(
                        truck_profiles.c.garage_id == owner.garage_id
                    )
                )
            ).all()
            remaining_trailers = (
                await session.execute(
                    select(trailer_profiles).where(
                        trailer_profiles.c.garage_id == owner.garage_id
                    )
                )
            ).all()
            remaining_garages = (
                await session.execute(
                    select(garages).where(garages.c.id == owner.garage_id)
                )
            ).all()

            assert remaining_trucks == []
            assert remaining_trailers == []
            assert remaining_garages == []

    run(body())
