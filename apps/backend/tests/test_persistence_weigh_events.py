"""Tier 2 (persistence-layer, offline): the `weigh_events` table directly,
with no FastAPI/fastapi-users routing and no `BackendWeighEventStore`
involved - insert, the `garage_id` foreign key, and `ON DELETE CASCADE` when
a Garage's owning Account is deleted (issue #21's Testing Decisions,
mirroring #18/#19's own tier-2 pattern for `garages`/`truck_profiles`/
`trailer_profiles`). Same real-SQLite-file-per-test pattern as
`test_sqlite_weigh_event_storage.py` testing `SqliteWeighEventStore` without
going through the CLI.

Schema comes from the real Alembic migrations (`run_migrations`), never an
ad-hoc `CREATE TABLE`, same as tier 2's precedent in #18/#19. Uses the async
engine (`towing_backend.db`), not `towing_backend.sync_db`'s synchronous
one - this tier proves the schema/constraints, not the synchronous store's
own read/write mapping (which the HTTP-level tier-1 tests exercise
end-to-end through the real API).
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, NamedTuple

import pytest
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from towing_backend.db import garages, make_engine, make_session_factory, weigh_events
from towing_backend.migrate import run_migrations
from towing_backend.models import Account
from towing_backend.settings import Settings

WEIGH_EVENT_VALUES: dict[str, Any] = {
    "truck_id": 1,
    "trailer_id": 1,
    "steer": 4000.0,
    "drive": 6000.0,
    "trailer_axle": 6500.0,
    "gross": 16500.0,
    "steer_rating": 4500.0,
    "drive_rating": 6500.0,
    "trailer_rating": 7000.0,
    "gvwr_rating": 10000.0,
    "timestamp": "2026-09-18T00:00:00+00:00",
}


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


def test_insert_weigh_event_round_trip(settings: Settings) -> None:
    session = _make_session(settings)

    async def body() -> None:
        async with session:
            owner = await _insert_account_and_garage(session, email="addie@example.com")

            await session.execute(
                insert(weigh_events).values(
                    garage_id=owner.garage_id, **WEIGH_EVENT_VALUES
                )
            )
            await session.commit()

            row = (
                await session.execute(
                    select(weigh_events).where(
                        weigh_events.c.garage_id == owner.garage_id
                    )
                )
            ).one()
            assert row.truck_id == 1
            assert row.gross == 16500.0
            assert row.gcwr_rating is None
            assert row.solo_steer is None
            assert row.reused_solo_is_unverified is False
            assert row.truck_nickname is None

    run(body())


def test_insert_weigh_event_with_solo_and_reused_fields_round_trip(
    settings: Settings,
) -> None:
    session = _make_session(settings)

    async def body() -> None:
        async with session:
            owner = await _insert_account_and_garage(session, email="addie@example.com")

            await session.execute(
                insert(weigh_events).values(
                    garage_id=owner.garage_id,
                    **{
                        **WEIGH_EVENT_VALUES,
                        "gcwr_rating": 20000.0,
                        "solo_steer": 4000.0,
                        "solo_drive": 5000.0,
                        "solo_gross": 9000.0,
                        "trailer_gvwr_rating": 8000.0,
                        "time_gap_hours": 1.5,
                        "reused_solo_from_timestamp": "2026-09-01T00:00:00+00:00",
                        "reused_solo_is_unverified": True,
                        "truck_nickname": "Big Blue",
                        "trailer_nickname": "Goose",
                    },
                )
            )
            await session.commit()

            row = (
                await session.execute(
                    select(weigh_events).where(
                        weigh_events.c.garage_id == owner.garage_id
                    )
                )
            ).one()
            assert row.solo_gross == 9000.0
            assert row.reused_solo_is_unverified is True
            assert row.truck_nickname == "Big Blue"
            assert row.trailer_nickname == "Goose"

    run(body())


# --- garage_id foreign key ----------------------------------------------


def test_weigh_event_with_nonexistent_garage_violates_foreign_key(
    settings: Settings,
) -> None:
    session = _make_session(settings)

    async def body() -> None:
        async with session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    insert(weigh_events).values(garage_id=999999, **WEIGH_EVENT_VALUES)
                )
                await session.commit()

    run(body())


# --- ON DELETE CASCADE, from Account all the way down to weigh_events ----


def test_deleting_account_cascades_to_weigh_events(settings: Settings) -> None:
    session = _make_session(settings)

    async def body() -> None:
        async with session:
            owner = await _insert_account_and_garage(session, email="addie@example.com")
            await session.execute(
                insert(weigh_events).values(
                    garage_id=owner.garage_id, **WEIGH_EVENT_VALUES
                )
            )
            await session.commit()

            # Deleting the owning Account, not the Garage directly - the
            # two-hop cascade (Account -> Garage -> weigh_events), same
            # convention as #19's Truck/Trailer Profile cascade test.
            await session.execute(delete(Account).where(Account.id == owner.account_id))
            await session.commit()

            remaining = (
                await session.execute(
                    select(weigh_events).where(
                        weigh_events.c.garage_id == owner.garage_id
                    )
                )
            ).all()
            assert remaining == []

    run(body())
