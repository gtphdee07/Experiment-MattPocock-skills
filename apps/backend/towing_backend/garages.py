"""Core-style queries against the `garages` table.

Kept separate from the ORM-mapped `towing_backend.models` on purpose -
`garages` is the one table this spec doesn't force into fastapi-users'
declarative style, so it's queried with plain SQLAlchemy Core statements
(ADR 0011). One Garage per Account, created atomically on registration via
`towing_backend.users.AccountManager.on_after_register`.
"""

from __future__ import annotations

from datetime import datetime
from typing import NamedTuple

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from towing_backend.db import garages


class Garage(NamedTuple):
    id: int
    account_id: int
    created_at: datetime


async def create_garage(session: AsyncSession, *, account_id: int) -> Garage:
    result = await session.execute(
        insert(garages).values(account_id=account_id).returning(garages)
    )
    row = result.one()
    return Garage(id=row.id, account_id=row.account_id, created_at=row.created_at)


async def get_garage_by_account_id(
    session: AsyncSession, *, account_id: int
) -> Garage | None:
    result = await session.execute(
        select(garages).where(garages.c.account_id == account_id)
    )
    row = result.one_or_none()
    if row is None:
        return None
    return Garage(id=row.id, account_id=row.account_id, created_at=row.created_at)


async def delete_garage_by_account_id(
    session: AsyncSession, *, account_id: int
) -> None:
    await session.execute(delete(garages).where(garages.c.account_id == account_id))
