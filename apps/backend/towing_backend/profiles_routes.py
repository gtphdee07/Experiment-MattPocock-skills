"""HTTP routes for Truck/Trailer Profile CRUD (issue #19).

Every route is scoped to the caller's own Garage, resolved from the
signed-in Account via `current_active_account` - never a client-supplied
Garage or Account ID (Story 18). Built as a factory (`build_profile_router`)
rather than a module-level `APIRouter`, because both dependencies it wires
in are themselves closures built inside `towing_backend.app.create_app`
around a runtime `Settings` (the account manager's secret, the session
factory's engine) - there's no module-level object to import here the way
`towing_backend.garages`'s plain functions can be.

A PATCH/DELETE against an `{id}` outside the caller's own Garage returns
404, not 403 (Story 15, matching #18's "don't confirm whether an email is
registered" instinct): every query in `towing_backend.truck_profiles`/
`trailer_profiles` is already scoped by `garage_id`, so a foreign profile
simply matches no row, indistinguishable from a nonexistent one - no
separate ownership check is needed to get this behavior.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from towing_backend import garages, trailer_profiles, truck_profiles
from towing_backend.models import Account
from towing_backend.schemas import (
    TrailerIn,
    TrailerOut,
    TrailerUpdate,
    TruckIn,
    TruckOut,
    TruckUpdate,
    display_nickname,
)

# `current_active_account` (a `fastapi_users.FastAPIUsers.current_user(...)`
# result) is an ordinary async dependency; `get_async_session` is an async
# generator dependency (`yield`-based, per `towing_backend.app`) - FastAPI
# treats both as valid `Depends(...)` targets, but they have genuinely
# different callable shapes, hence two separate aliases here.
CurrentAccountDependency = Callable[..., Awaitable[Account]]
AsyncSessionDependency = Callable[..., AsyncIterator[AsyncSession]]


def build_profile_router(
    *,
    current_active_account: CurrentAccountDependency,
    get_async_session: AsyncSessionDependency,
) -> APIRouter:
    router = APIRouter()

    async def _caller_garage_id(account: Account, session: AsyncSession) -> int:
        garage = await garages.get_garage_by_account_id(session, account_id=account.id)
        if garage is None:
            # Every Account gets a Garage on registration
            # (AccountManager.on_after_register) - this would only fire if
            # that step's known non-atomic gap (see its own docstring) was
            # actually hit for this Account. Not a client-facing 404: the
            # client did nothing wrong, so this propagates as a 500 rather
            # than overloading the "cross-Account 404" convention above.
            raise RuntimeError(f"Account {account.id} has no Garage")
        return garage.id

    def _truck_out(row: truck_profiles.TruckProfileRow) -> TruckOut:
        return TruckOut(
            id=row.id,
            gvwr=row.gvwr,
            front_gawr=row.front_gawr,
            rear_gawr=row.rear_gawr,
            gcwr=row.gcwr,
            nickname=display_nickname(row.nickname, "Truck", row.id),
        )

    def _trailer_out(row: trailer_profiles.TrailerProfileRow) -> TrailerOut:
        return TrailerOut(
            id=row.id,
            gvwr=row.gvwr,
            gawr=row.gawr,
            axle_count=row.axle_count,
            uvw=row.uvw,
            nickname=display_nickname(row.nickname, "Trailer", row.id),
        )

    # --- Trucks --------------------------------------------------------

    @router.post(
        "/trucks", response_model=TruckOut, status_code=status.HTTP_201_CREATED
    )
    async def create_truck(
        payload: TruckIn,
        account: Account = Depends(current_active_account),
        session: AsyncSession = Depends(get_async_session),
    ) -> TruckOut:
        garage_id = await _caller_garage_id(account, session)
        row = await truck_profiles.create_truck_profile(
            session,
            garage_id=garage_id,
            gvwr=payload.gvwr,
            front_gawr=payload.front_gawr,
            rear_gawr=payload.rear_gawr,
            gcwr=payload.gcwr,
            nickname=payload.nickname,
        )
        await session.commit()
        return _truck_out(row)

    @router.get("/trucks", response_model=list[TruckOut])
    async def list_trucks(
        account: Account = Depends(current_active_account),
        session: AsyncSession = Depends(get_async_session),
    ) -> list[TruckOut]:
        garage_id = await _caller_garage_id(account, session)
        rows = await truck_profiles.list_truck_profiles(session, garage_id=garage_id)
        return [_truck_out(row) for row in rows]

    @router.patch("/trucks/{truck_id}", response_model=TruckOut)
    async def update_truck(
        truck_id: int,
        payload: TruckUpdate,
        account: Account = Depends(current_active_account),
        session: AsyncSession = Depends(get_async_session),
    ) -> TruckOut:
        garage_id = await _caller_garage_id(account, session)
        fields = payload.model_dump(exclude_unset=True)
        row = await truck_profiles.update_truck_profile(
            session, id=truck_id, garage_id=garage_id, fields=fields
        )
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        await session.commit()
        return _truck_out(row)

    @router.delete("/trucks/{truck_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_truck(
        truck_id: int,
        account: Account = Depends(current_active_account),
        session: AsyncSession = Depends(get_async_session),
    ) -> None:
        garage_id = await _caller_garage_id(account, session)
        deleted = await truck_profiles.delete_truck_profile(
            session, id=truck_id, garage_id=garage_id
        )
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        await session.commit()

    # --- Trailers --------------------------------------------------------

    @router.post(
        "/trailers", response_model=TrailerOut, status_code=status.HTTP_201_CREATED
    )
    async def create_trailer(
        payload: TrailerIn,
        account: Account = Depends(current_active_account),
        session: AsyncSession = Depends(get_async_session),
    ) -> TrailerOut:
        garage_id = await _caller_garage_id(account, session)
        row = await trailer_profiles.create_trailer_profile(
            session,
            garage_id=garage_id,
            gvwr=payload.gvwr,
            gawr=payload.gawr,
            axle_count=payload.axle_count,
            uvw=payload.uvw,
            nickname=payload.nickname,
        )
        await session.commit()
        return _trailer_out(row)

    @router.get("/trailers", response_model=list[TrailerOut])
    async def list_trailers(
        account: Account = Depends(current_active_account),
        session: AsyncSession = Depends(get_async_session),
    ) -> list[TrailerOut]:
        garage_id = await _caller_garage_id(account, session)
        rows = await trailer_profiles.list_trailer_profiles(
            session, garage_id=garage_id
        )
        return [_trailer_out(row) for row in rows]

    @router.patch("/trailers/{trailer_id}", response_model=TrailerOut)
    async def update_trailer(
        trailer_id: int,
        payload: TrailerUpdate,
        account: Account = Depends(current_active_account),
        session: AsyncSession = Depends(get_async_session),
    ) -> TrailerOut:
        garage_id = await _caller_garage_id(account, session)
        fields = payload.model_dump(exclude_unset=True)
        row = await trailer_profiles.update_trailer_profile(
            session, id=trailer_id, garage_id=garage_id, fields=fields
        )
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        await session.commit()
        return _trailer_out(row)

    @router.delete("/trailers/{trailer_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_trailer(
        trailer_id: int,
        account: Account = Depends(current_active_account),
        session: AsyncSession = Depends(get_async_session),
    ) -> None:
        garage_id = await _caller_garage_id(account, session)
        deleted = await trailer_profiles.delete_trailer_profile(
            session, id=trailer_id, garage_id=garage_id
        )
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        await session.commit()

    return router
