"""Tier 3 (real-Postgres contract bench, `test_real_*`): the same
schema/constraint operations as tier 2, run against an actual Postgres
instance instead of SQLite - migrate via Alembic, insert an Account + its
Garage, exercise both unique constraints, exercise the cascade delete.

Extended by issue #19 to cover `truck_profiles`/`trailer_profiles` the same
way - insert, the `garage_id` foreign key, and the Account -> Garage ->
Profiles cascade delete - in this same file rather than a second Postgres
bench (Testing Decisions: "extends #18's Postgres bench to cover these two
new tables instead of standing up a second one").

Excluded from the default `-k "not real"` loop, same convention as
`packages/towing-app/tests/test_real_*_photo_smoke.py`. Skipped
(`pytest.mark.skipif`, not a hard failure) when
`TOWING_BACKEND_TEST_POSTGRES_URL` isn't set - a missing local Postgres is
the expected common case in this environment, not a broken one (issue #18's
Testing Decisions, explicitly contrasting this with the photo-smoke tests'
"fails loudly when creds are missing" behavior).

This tier exists specifically to catch SQLite/Postgres dialect drift (e.g.
the `PRAGMA foreign_keys=ON` SQLite needs for `ON DELETE CASCADE` to do
anything at all - see `towing_backend.db.make_engine` - is a no-op on
Postgres, which enforces FKs unconditionally) before production does, and
doubles as the contract-validation bench for ever swapping the database
provider.
"""

from __future__ import annotations

import asyncio
import os
import uuid
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
    weigh_events,
)
from towing_backend.migrate import run_migrations
from towing_backend.models import Account

POSTGRES_URL_ENV_VAR = "TOWING_BACKEND_TEST_POSTGRES_URL"

pytestmark = pytest.mark.skipif(
    not os.environ.get(POSTGRES_URL_ENV_VAR),
    reason=(
        f"requires a real Postgres instance - set {POSTGRES_URL_ENV_VAR} "
        "(e.g. to a local Docker container's URL) to run this bench"
    ),
)


def run(coro: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coro)


def _postgres_url() -> str:
    url = os.environ[POSTGRES_URL_ENV_VAR]
    # Normalize to the async driver this backend uses everywhere else,
    # regardless of how the URL was supplied.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _make_session() -> AsyncSession:
    # Must run before any event loop exists in this thread - see
    # test_persistence_accounts_garages.py's `_make_session` docstring.
    url = _postgres_url()
    run_migrations(url)
    engine = make_engine(url)
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


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


def test_real_insert_account_and_garage_round_trip() -> None:
    session = _make_session()

    async def body() -> None:
        async with session:
            email = _unique_email()
            account_id = await _insert_account(session, email=email)

            await session.execute(insert(garages).values(account_id=account_id))
            await session.commit()

            account = (
                await session.execute(select(Account).where(Account.id == account_id))
            ).scalar_one()
            assert account.email == email

            garage_row = (
                await session.execute(
                    select(garages).where(garages.c.account_id == account_id)
                )
            ).one()
            assert garage_row.account_id == account_id

    run(body())


def test_real_duplicate_email_violates_unique_constraint() -> None:
    session = _make_session()

    async def body() -> None:
        async with session:
            email = _unique_email()
            await _insert_account(session, email=email)

            with pytest.raises(IntegrityError):
                await session.execute(
                    insert(Account).values(email=email, hashed_password="another-hash")
                )
                await session.commit()

    run(body())


def test_real_duplicate_garage_for_same_account_violates_unique_constraint() -> None:
    session = _make_session()

    async def body() -> None:
        async with session:
            account_id = await _insert_account(session, email=_unique_email())
            await session.execute(insert(garages).values(account_id=account_id))
            await session.commit()

            with pytest.raises(IntegrityError):
                await session.execute(insert(garages).values(account_id=account_id))
                await session.commit()

    run(body())


def test_real_deleting_account_cascades_to_garage() -> None:
    session = _make_session()

    async def body() -> None:
        async with session:
            account_id = await _insert_account(session, email=_unique_email())
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


# --- Issue #19: truck_profiles / trailer_profiles --------------------------


class _AccountGarage(NamedTuple):
    account_id: int
    garage_id: int


async def _insert_account_and_garage(session: AsyncSession) -> _AccountGarage:
    account_id = await _insert_account(session, email=_unique_email())
    garage_id = (
        await session.execute(
            insert(garages).values(account_id=account_id).returning(garages.c.id)
        )
    ).scalar_one()
    await session.commit()
    return _AccountGarage(account_id=account_id, garage_id=garage_id)


def test_real_insert_truck_and_trailer_profile_round_trip() -> None:
    session = _make_session()

    async def body() -> None:
        async with session:
            owner = await _insert_account_and_garage(session)

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

            truck_row = (
                await session.execute(
                    select(truck_profiles).where(
                        truck_profiles.c.garage_id == owner.garage_id
                    )
                )
            ).one()
            assert truck_row.gvwr == 10000.0
            assert truck_row.gcwr is None

            trailer_row = (
                await session.execute(
                    select(trailer_profiles).where(
                        trailer_profiles.c.garage_id == owner.garage_id
                    )
                )
            ).one()
            assert trailer_row.axle_count == 2
            assert trailer_row.uvw is None

    run(body())


def test_real_truck_profile_with_nonexistent_garage_violates_foreign_key() -> None:
    session = _make_session()

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


def test_real_deleting_account_cascades_to_truck_and_trailer_profiles() -> None:
    session = _make_session()

    async def body() -> None:
        async with session:
            owner = await _insert_account_and_garage(session)
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
            assert remaining_trucks == []
            assert remaining_trailers == []

    run(body())


# --- Issue #21: weigh_events -------------------------------------------------

_WEIGH_EVENT_VALUES: dict[str, Any] = {
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


def test_real_insert_weigh_event_round_trip() -> None:
    session = _make_session()

    async def body() -> None:
        async with session:
            owner = await _insert_account_and_garage(session)

            await session.execute(
                insert(weigh_events).values(
                    garage_id=owner.garage_id, **_WEIGH_EVENT_VALUES
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
            assert row.gross == 16500.0
            assert row.gcwr_rating is None
            assert row.reused_solo_is_unverified is False

    run(body())


def test_real_insert_weigh_event_with_null_truck_and_trailer_id_round_trips() -> None:
    """Issue #45 / ADR 0017: confirms the nullable `truck_id`/`trailer_id`
    columns (migration 0004) behave the same on real Postgres as SQLite -
    the dialect-drift class of bug this tier exists to catch."""
    session = _make_session()

    async def body() -> None:
        async with session:
            owner = await _insert_account_and_garage(session)

            await session.execute(
                insert(weigh_events).values(
                    garage_id=owner.garage_id,
                    **{**_WEIGH_EVENT_VALUES, "truck_id": None, "trailer_id": None},
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
            assert row.truck_id is None
            assert row.trailer_id is None

    run(body())


def test_real_weigh_event_with_nonexistent_garage_violates_foreign_key() -> None:
    session = _make_session()

    async def body() -> None:
        async with session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    insert(weigh_events).values(garage_id=999999, **_WEIGH_EVENT_VALUES)
                )
                await session.commit()

    run(body())


def test_real_deleting_account_cascades_to_weigh_events() -> None:
    session = _make_session()

    async def body() -> None:
        async with session:
            owner = await _insert_account_and_garage(session)
            await session.execute(
                insert(weigh_events).values(
                    garage_id=owner.garage_id, **_WEIGH_EVENT_VALUES
                )
            )
            await session.commit()

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
