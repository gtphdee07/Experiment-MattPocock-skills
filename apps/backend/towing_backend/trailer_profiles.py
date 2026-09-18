"""Core-style queries against the `trailer_profiles` table.

Mirrors `towing_backend.truck_profiles` field-for-field, substituting
`gawr`/`axle_count`/`uvw` for `front_gawr`/`rear_gawr`/`gcwr` - see that
module's docstring for the scoping and empty-PATCH rationale shared by both.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from towing_backend.db import trailer_profiles

UpdateValue = float | int | str | None


class TrailerProfileRow(NamedTuple):
    id: int
    garage_id: int
    gvwr: float
    gawr: float
    axle_count: int
    uvw: float | None
    nickname: str | None


def _row(raw: object) -> TrailerProfileRow:
    return TrailerProfileRow(
        id=raw.id,  # type: ignore[attr-defined]
        garage_id=raw.garage_id,  # type: ignore[attr-defined]
        gvwr=raw.gvwr,  # type: ignore[attr-defined]
        gawr=raw.gawr,  # type: ignore[attr-defined]
        axle_count=raw.axle_count,  # type: ignore[attr-defined]
        uvw=raw.uvw,  # type: ignore[attr-defined]
        nickname=raw.nickname,  # type: ignore[attr-defined]
    )


async def create_trailer_profile(
    session: AsyncSession,
    *,
    garage_id: int,
    gvwr: float,
    gawr: float,
    axle_count: int,
    uvw: float | None = None,
    nickname: str | None = None,
) -> TrailerProfileRow:
    result = await session.execute(
        insert(trailer_profiles)
        .values(
            garage_id=garage_id,
            gvwr=gvwr,
            gawr=gawr,
            axle_count=axle_count,
            uvw=uvw,
            nickname=nickname,
        )
        .returning(trailer_profiles)
    )
    return _row(result.one())


async def list_trailer_profiles(
    session: AsyncSession, *, garage_id: int
) -> list[TrailerProfileRow]:
    result = await session.execute(
        select(trailer_profiles)
        .where(trailer_profiles.c.garage_id == garage_id)
        .order_by(trailer_profiles.c.id)
    )
    return [_row(row) for row in result.all()]


async def get_trailer_profile(
    session: AsyncSession, *, id: int, garage_id: int
) -> TrailerProfileRow | None:
    result = await session.execute(
        select(trailer_profiles).where(
            trailer_profiles.c.id == id, trailer_profiles.c.garage_id == garage_id
        )
    )
    row = result.one_or_none()
    return None if row is None else _row(row)


async def update_trailer_profile(
    session: AsyncSession,
    *,
    id: int,
    garage_id: int,
    fields: Mapping[str, UpdateValue],
) -> TrailerProfileRow | None:
    if fields:
        result = await session.execute(
            update(trailer_profiles)
            .where(
                trailer_profiles.c.id == id, trailer_profiles.c.garage_id == garage_id
            )
            .values(**fields)
            .returning(trailer_profiles)
        )
    else:
        result = await session.execute(
            select(trailer_profiles).where(
                trailer_profiles.c.id == id, trailer_profiles.c.garage_id == garage_id
            )
        )
    row = result.one_or_none()
    return None if row is None else _row(row)


async def delete_trailer_profile(
    session: AsyncSession, *, id: int, garage_id: int
) -> bool:
    result = await session.execute(
        delete(trailer_profiles)
        .where(trailer_profiles.c.id == id, trailer_profiles.c.garage_id == garage_id)
        .returning(trailer_profiles.c.id)
    )
    return result.first() is not None
