"""Core-style queries against the `truck_profiles` table.

Every read/update/delete below is scoped by `garage_id` - the mechanism
behind issue #19's "404, not 403" cross-Account behavior (Story 15): a
query for a Truck Profile outside the caller's own Garage simply matches no
row, indistinguishable from a nonexistent ID, so the HTTP layer
(`towing_backend.profiles_routes`) never needs a separate ownership check.

Kept separate from the ORM-mapped `towing_backend.models` for the same
reason as `towing_backend.garages`: this table isn't forced into
fastapi-users' declarative style, so it's queried with plain SQLAlchemy
Core statements (ADR 0011).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from towing_backend.db import truck_profiles

# The value types a PATCH may set a column to - `None` is valid for the
# nullable columns (`gcwr`, `nickname`) only; `TruckUpdate`'s own
# validation (towing_backend.schemas) keeps `None` from reaching the
# required columns.
UpdateValue = float | str | None


class TruckProfileRow(NamedTuple):
    id: int
    garage_id: int
    gvwr: float
    front_gawr: float
    rear_gawr: float
    gcwr: float | None
    nickname: str | None


def _row(raw: object) -> TruckProfileRow:
    return TruckProfileRow(
        id=raw.id,  # type: ignore[attr-defined]
        garage_id=raw.garage_id,  # type: ignore[attr-defined]
        gvwr=raw.gvwr,  # type: ignore[attr-defined]
        front_gawr=raw.front_gawr,  # type: ignore[attr-defined]
        rear_gawr=raw.rear_gawr,  # type: ignore[attr-defined]
        gcwr=raw.gcwr,  # type: ignore[attr-defined]
        nickname=raw.nickname,  # type: ignore[attr-defined]
    )


async def create_truck_profile(
    session: AsyncSession,
    *,
    garage_id: int,
    gvwr: float,
    front_gawr: float,
    rear_gawr: float,
    gcwr: float | None = None,
    nickname: str | None = None,
) -> TruckProfileRow:
    result = await session.execute(
        insert(truck_profiles)
        .values(
            garage_id=garage_id,
            gvwr=gvwr,
            front_gawr=front_gawr,
            rear_gawr=rear_gawr,
            gcwr=gcwr,
            nickname=nickname,
        )
        .returning(truck_profiles)
    )
    return _row(result.one())


async def list_truck_profiles(
    session: AsyncSession, *, garage_id: int
) -> list[TruckProfileRow]:
    result = await session.execute(
        select(truck_profiles)
        .where(truck_profiles.c.garage_id == garage_id)
        .order_by(truck_profiles.c.id)
    )
    return [_row(row) for row in result.all()]


async def get_truck_profile(
    session: AsyncSession, *, id: int, garage_id: int
) -> TruckProfileRow | None:
    result = await session.execute(
        select(truck_profiles).where(
            truck_profiles.c.id == id, truck_profiles.c.garage_id == garage_id
        )
    )
    row = result.one_or_none()
    return None if row is None else _row(row)


async def update_truck_profile(
    session: AsyncSession,
    *,
    id: int,
    garage_id: int,
    fields: Mapping[str, UpdateValue],
) -> TruckProfileRow | None:
    """Applies `fields` (already filtered to "explicitly provided in the
    PATCH body" by `TruckUpdate.model_dump(exclude_unset=True)`) to the one
    row matching both `id` and `garage_id`. An empty `fields` mapping (a
    PATCH with no recognized changes) still round-trips the current row
    rather than issuing a no-op `UPDATE ... SET` (invalid SQL with an empty
    `SET` clause), so callers get the same 404-or-current-row contract
    either way.
    """
    if fields:
        result = await session.execute(
            update(truck_profiles)
            .where(truck_profiles.c.id == id, truck_profiles.c.garage_id == garage_id)
            .values(**fields)
            .returning(truck_profiles)
        )
    else:
        result = await session.execute(
            select(truck_profiles).where(
                truck_profiles.c.id == id, truck_profiles.c.garage_id == garage_id
            )
        )
    row = result.one_or_none()
    return None if row is None else _row(row)


async def delete_truck_profile(
    session: AsyncSession, *, id: int, garage_id: int
) -> bool:
    result = await session.execute(
        delete(truck_profiles)
        .where(truck_profiles.c.id == id, truck_profiles.c.garage_id == garage_id)
        .returning(truck_profiles.c.id)
    )
    return result.first() is not None
