"""Pydantic boundary schemas for the Account and Garage-CRUD API surfaces.

`AccountRead`/`AccountCreate`/`AccountUpdate` - not fastapi-users' default
`UserRead`/`UserCreate`/`UserUpdate` - so "User" never appears in this
codebase's schema or API surface, per CONTEXT.md's explicit `_Avoid: User`
note on the Account entry (issue #18 Story 15).

`TruckIn`/`TruckOut`/`TruckUpdate` and `TrailerIn`/`TrailerOut`/
`TrailerUpdate` (issue #19) are hand-written per endpoint rather than
generated through a shared mapping helper, per ADR 0011's decision - the
same style as `docs/design/web/api/main.py`'s reference `TruckIn`/
`CheckOut`. Field constraints (`gt=0`) enforce CODING_STANDARDS.md's
"fail fast: validate at the boundary via Pydantic" rule and mirror each
domain dataclass's own `__post_init__` positivity floor
(`towing_core.models.TruckProfile`/`TrailerProfile`).
"""

from __future__ import annotations

from datetime import datetime

from fastapi_users import schemas
from pydantic import BaseModel, Field, model_validator


class AccountRead(schemas.BaseUser[int]):
    created_at: datetime


class AccountCreate(schemas.BaseUserCreate):
    pass


class AccountUpdate(schemas.BaseUserUpdate):
    pass


def display_nickname(nickname: str | None, kind: str, profile_id: int) -> str:
    """The Nickname to show for a Truck/Trailer Profile in an API response -
    the stored value, or a default computed live from its ID (e.g.
    "Truck 3") when it's `None` (CONTEXT.md: Nickname). Mirrors
    `towing_core.report._display_nickname`'s logic exactly (issue #19's
    Implementation Decisions) without importing it - that helper is
    module-private to `towing_core.report`, and `towing_core` itself stays
    untouched by this backend-only feature (ADR 0010). Computed here, at
    the response boundary, only - never written back to storage, matching
    how `towing_core.report` and the CLI already treat this (ticket #12).
    """
    return nickname if nickname is not None else f"{kind} {profile_id}"


class TruckIn(BaseModel):
    gvwr: float = Field(gt=0)
    front_gawr: float = Field(gt=0)
    rear_gawr: float = Field(gt=0)
    gcwr: float | None = Field(default=None, gt=0)
    nickname: str | None = None


class TruckUpdate(BaseModel):
    """All fields optional, for a partial update - only the keys actually
    present in the request body are applied (`model_dump(exclude_unset=True)`
    at the route, see `towing_backend.profiles_routes`), so omitting a field
    leaves it unchanged while explicitly sending `"nickname": null` clears
    it. `gvwr`/`front_gawr`/`rear_gawr` can never be null on
    `TruckProfile` itself (see its `__post_init__`), so an explicit null
    for one of those three is rejected below rather than allowed to reach
    the database as a `NOT NULL` constraint violation.
    """

    gvwr: float | None = Field(default=None, gt=0)
    front_gawr: float | None = Field(default=None, gt=0)
    rear_gawr: float | None = Field(default=None, gt=0)
    gcwr: float | None = Field(default=None, gt=0)
    nickname: str | None = None

    @model_validator(mode="after")
    def _reject_null_required_fields(self) -> TruckUpdate:
        for name in ("gvwr", "front_gawr", "rear_gawr"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be explicitly cleared")
        return self


class TruckOut(BaseModel):
    id: int
    gvwr: float
    front_gawr: float
    rear_gawr: float
    gcwr: float | None
    nickname: str


class TrailerIn(BaseModel):
    gvwr: float = Field(gt=0)
    gawr: float = Field(gt=0)
    axle_count: int = Field(gt=0)
    uvw: float | None = Field(default=None, gt=0)
    nickname: str | None = None


class TrailerUpdate(BaseModel):
    """Mirrors `TruckUpdate` - see its docstring."""

    gvwr: float | None = Field(default=None, gt=0)
    gawr: float | None = Field(default=None, gt=0)
    axle_count: int | None = Field(default=None, gt=0)
    uvw: float | None = Field(default=None, gt=0)
    nickname: str | None = None

    @model_validator(mode="after")
    def _reject_null_required_fields(self) -> TrailerUpdate:
        for name in ("gvwr", "gawr", "axle_count"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be explicitly cleared")
        return self


class TrailerOut(BaseModel):
    id: int
    gvwr: float
    gawr: float
    axle_count: int
    uvw: float | None
    nickname: str
