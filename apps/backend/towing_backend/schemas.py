"""Pydantic boundary schemas for the Account API surface.

Named `AccountRead`/`AccountCreate`/`AccountUpdate` - not fastapi-users'
default `UserRead`/`UserCreate`/`UserUpdate` - so "User" never appears in
this codebase's schema or API surface, per CONTEXT.md's explicit
`_Avoid: User` note on the Account entry (issue #18 Story 15).
"""

from __future__ import annotations

from datetime import datetime

from fastapi_users import schemas


class AccountRead(schemas.BaseUser[int]):
    created_at: datetime


class AccountCreate(schemas.BaseUserCreate):
    pass


class AccountUpdate(schemas.BaseUserUpdate):
    pass
