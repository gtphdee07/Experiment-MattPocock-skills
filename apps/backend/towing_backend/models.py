"""ORM-mapped tables that fastapi-users' SQLAlchemy adapter requires.

`Account` is this codebase's public name for fastapi-users' generic "user"
concept - the table is `accounts`, the class is `Account`, matching
CONTEXT.md's Account entry and its explicit `_Avoid: User` note (issue #18
Story 15).

`AccountSession` backs the session-cookie `DatabaseStrategy` (an opaque
per-session token row, looked up on every request - not a JWT, per ADR
0011's "session-cookie backend (not JWT)" decision). Its `user_id` column
name is *not* renamed to `account_id` like every other Account-referencing
column in this codebase: `fastapi_users.authentication.strategy.db.strategy.
DatabaseStrategy` hardcodes the literal key `"user_id"` when it builds the
row to insert on login (`_create_access_token_dict`), so renaming it would
mean overriding library internals for a table whose rows are never part of
the public API surface (unlike `accounts`, which Story 15 is actually
about).
"""

from __future__ import annotations

from datetime import datetime

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTable
from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from towing_backend.db import Base


class Account(SQLAlchemyBaseUserTable[int], Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AccountSession(SQLAlchemyBaseAccessTokenTable[int], Base):
    __tablename__ = "sessions"

    # A plain `mapped_column` (not fastapi-users' own `@declared_attr`
    # pattern, which exists so a *mixin* can be reused across several
    # concrete classes with different FK targets) - `AccountSession` is
    # only ever this one concrete class, so the indirection isn't needed,
    # and mypy resolves the plain form as a real `int` attribute, which is
    # what satisfies `AccessTokenProtocol`'s structural typing below.
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
