"""HTTP routes for Weigh Event creation and history (issue #21).

Every route is scoped to the caller's own Garage, exactly like
`towing_backend.profiles_routes` (issue #19) - `truck_id`/`trailer_id` are
always resolved against the caller's own Garage before use, and a Truck or
Trailer Profile outside it fails as 404, the same "no separate ownership
check needed, the scoped query just matches nothing" pattern that module's
docstring explains.

**Async/sync boundary (ADR 0015, restated in issue #21's own brief)**:
`towing_app.services.record_weigh_event` is fully synchronous. Every route
handler here is `async def` (matching the rest of `apps/backend`), so every
call that touches `towing_backend.weigh_events_store.BackendWeighEventStore`
(itself built on a synchronous SQLAlchemy engine - see
`towing_backend.sync_db`) or `record_weigh_event` is offloaded via
`fastapi.concurrency.run_in_threadpool` - never called inline on the event
loop. This is the exact pattern `towing_backend.photo_ocr`'s
`_run_extraction` already established for issue #20's synchronous
Claude-vision adapter calls.

**Solo Ticket request shape**: `WeighEventCreateRequest.solo` is a
Pydantic-discriminated union (tag field `kind`) between `FreshSoloTicketIn`
and `ReusedSoloTicketIn` - a judgment call within issue #21's own "exactly
one of: no Solo Ticket at all; a fresh Solo Ticket; a reused Solo Ticket"
shape, which doesn't name an exact wire discriminator. `isinstance` (not a
literal-tag `match`/`if kind ==` chain) narrows it below, for the most
unambiguous mypy narrowing across two `BaseModel` subclasses.

**One-Off Truck/Trailer (issue #45 / ADR 0017)**: `WeighEventCreateRequest`
gains a second exactly-one-of pair per side - `truck_id` (a real, saved
Truck Profile) XOR `truck` (a One-Off Truck's raw rating fields, mirroring
`TruckIn`'s shape exactly), same for `trailer_id`/`trailer` - enforced by
the request's own `model_validator` below, so an invalid combination is a
422 before any business logic runs. `record_weigh_event` itself gained two
new, default-`False` keyword-only flags (`truck_is_one_off`/
`trailer_is_one_off`) for this - every other caller (in particular the CLI)
passes neither and is unaffected; see that function's own docstring.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from towing_app.clock import iso_now
from towing_app.services import Problem, record_weigh_event
from towing_backend import garages, trailer_profiles, truck_profiles
from towing_backend.models import Account
from towing_backend.profiles_routes import (
    AsyncSessionDependency,
    CurrentAccountDependency,
)
from towing_backend.schemas import TrailerIn, TruckIn
from towing_backend.weigh_events_store import BackendWeighEventStore
from towing_core.evaluation import RigEvaluation, rig_evaluation_from_record
from towing_core.linking import _find_last_solo_ticket_record, reweigh_references_match
from towing_core.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile
from towing_core.report import LEGAL_DISCLAIMER
from towing_core.storage import WeighEventRecord

# "the exact page size default is left to implementation time, not grilled"
# (issue #21 Implementation Decisions) - a plain, unremarkable v1 default and
# an upper bound so a caller can't force an unbounded query.
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class CombinedTicketIn(BaseModel):
    steer: float = Field(gt=0)
    drive: float = Field(gt=0)
    trailer_axle: float = Field(gt=0)
    gross: float = Field(gt=0)
    reweigh_reference: str | None = None


class FreshSoloTicketIn(BaseModel):
    kind: Literal["fresh"] = "fresh"
    steer: float = Field(gt=0)
    drive: float = Field(gt=0)
    gross: float = Field(gt=0)
    reweigh_reference: str | None = None
    time_gap_hours: float | None = None


class ReusedSoloTicketIn(BaseModel):
    kind: Literal["reused"] = "reused"
    # Echoed back from `GET /trucks/{id}/reusable-solo-ticket` - identifies
    # which past Weigh Event's Solo Ticket is being reused (see
    # `_find_reusable_solo_ticket_record` below).
    from_timestamp: str
    gross: float = Field(gt=0)
    adjusted: bool


class WeighEventCreateRequest(BaseModel):
    """`truck_id`/`truck` (and `trailer_id`/`trailer`) are each an
    exactly-one-of pair (issue #45 / ADR 0017): a real, saved Truck/Trailer
    Profile's id, or a One-Off Truck/Trailer's raw rating fields - `TruckIn`/
    `TrailerIn` reused directly rather than duplicated, since a One-Off's
    shape (ratings plus an optional Nickname) is exactly `TruckIn`/
    `TrailerIn`'s own shape. Neither or both present on a side is rejected
    by `_exactly_one_truck_and_trailer_source` below, as a 422, before any
    business logic runs (fail fast, CODING_STANDARDS.md section 6)."""

    truck_id: int | None = None
    truck: TruckIn | None = None
    trailer_id: int | None = None
    trailer: TrailerIn | None = None
    combined: CombinedTicketIn
    solo: FreshSoloTicketIn | ReusedSoloTicketIn | None = Field(
        default=None, discriminator="kind"
    )
    # Only meaningful with a fresh Solo Ticket whose Reweigh Reference didn't
    # auto-match - see the 409 branch in `create_weigh_event` below.
    confirm_solo_link: bool = False

    @model_validator(mode="after")
    def _exactly_one_truck_and_trailer_source(self) -> WeighEventCreateRequest:
        if (self.truck_id is None) == (self.truck is None):
            raise ValueError(
                "Exactly one of truck_id or truck (a One-Off Truck) is required"
            )
        if (self.trailer_id is None) == (self.trailer is None):
            raise ValueError(
                "Exactly one of trailer_id or trailer (a One-Off Trailer) is required"
            )
        return self


class CheckOut(BaseModel):
    label: str
    status: str
    actual: float | None
    rating: float | None
    note: str | None


class WeighEventOut(BaseModel):
    """Extends `docs/design/web/api/main.py`'s reference `EvaluateResponse`
    shape with the persisted record's `id`, `timestamp`, `truck_nickname`,
    `trailer_nickname` (issue #21's own Implementation Decisions) -
    hand-written per ADR 0011, not a shared mapping helper."""

    id: int
    timestamp: str
    truck_nickname: str
    trailer_nickname: str
    # Issue #45 / ADR 0017: `None` exactly when that side is a One-Off Truck/
    # Trailer - the frontend keys its "(one-off)" badge and fallback label
    # off this, not off Nickname presence/absence (a One-Off can still have
    # a user-given Nickname and must still show the badge).
    truck_id: int | None
    trailer_id: int | None
    overall_status: str
    # Fixed order: Steer, Drive, Trailer Axle, Hitched GVWR, GCWR, Trailer GVWR
    checks: list[CheckOut]
    time_gap_hours: float | None
    time_gap_exceeds_threshold: bool | None
    disclaimer: str


class ReusableSoloTicketOut(BaseModel):
    gross: float
    from_timestamp: str


def _find_reusable_solo_ticket_record(
    records: list[WeighEventRecord], *, truck_id: int, from_timestamp: str
) -> WeighEventRecord | None:
    """Finds the specific past Weigh Event a `ReusedSoloTicketIn.
    from_timestamp` identifies (echoed back from `GET /trucks/{id}/
    reusable-solo-ticket`), rather than re-deriving "the latest" via
    `_find_last_solo_ticket_record` again - a judgment call: `from_timestamp`
    is meant as an explicit identifier of which record is being reused, not
    just a round-tripped display value, so an exact match is required."""
    for record in records:
        if (
            record.truck_id == truck_id
            and record.timestamp == from_timestamp
            and record.solo_ticket is not None
        ):
            return record
    return None


def build_weigh_events_router(
    *,
    current_active_account: CurrentAccountDependency,
    get_async_session: AsyncSessionDependency,
    sync_session_factory: sessionmaker[Session],
) -> APIRouter:
    router = APIRouter()

    async def _caller_garage_id(account: Account, session: AsyncSession) -> int:
        garage = await garages.get_garage_by_account_id(session, account_id=account.id)
        if garage is None:
            # Mirrors `towing_backend.profiles_routes`'s own helper - see
            # its docstring for why this is a 500, not a client-facing 404.
            raise RuntimeError(f"Account {account.id} has no Garage")
        return garage.id

    def _checks_from_evaluation(evaluation: RigEvaluation) -> list[CheckOut]:
        """The six overload checks, folded from `RigEvaluation`'s
        `EvaluatedCheck`s. `note` is overridden here for the two checks that
        can be an Unverified Value - GCWR Overload (always, whenever it's
        evaluated at all - manually entered, no photo/Ticket behind it, see
        CONTEXT.md) and Trailer GVWR Overload (only when its Solo Ticket was
        a manually-adjusted Reused Solo Weight - ADR 0006) - since
        `EvaluatedCheck.note` itself never carries this (confirmed directly
        against `towing_core.evaluation._assemble_rig_evaluation`, which is
        untouched by this issue). This is the HTTP-boundary equivalent of
        `towing_core.report.format_weigh_event_results`'s own "Unverified
        Value" labeling, which reads the same raw result objects rather than
        anything `EvaluatedCheck` carries - satisfying issue #21 Story 13's
        explicit acceptance criterion ("the distinction... is visible in the
        result") via the response shape's existing `note` field rather than
        adding a new field the Implementation Decisions' response-shape
        bullet doesn't name."""
        gcwr_note = evaluation.gcwr.note
        if evaluation.gcwr_result is not None:
            gcwr_note = (
                "Unverified Value - GCWR is manually entered, not backed by "
                "a photo or CAT Scale Ticket."
            )

        trailer_gvwr_note = evaluation.trailer_gvwr.note
        if (
            evaluation.trailer_gvwr_result is not None
            and evaluation.trailer_gvwr_result.is_unverified
        ):
            trailer_gvwr_note = (
                "Unverified Value - the reused Solo weight was manually "
                "adjusted, not backed by a photo or CAT Scale Ticket."
            )

        entries = [
            (evaluation.steer_axle, evaluation.steer_axle.note),
            (evaluation.drive_axle, evaluation.drive_axle.note),
            (evaluation.trailer_axle, evaluation.trailer_axle.note),
            (evaluation.hitched_gvwr, evaluation.hitched_gvwr.note),
            (evaluation.gcwr, gcwr_note),
            (evaluation.trailer_gvwr, trailer_gvwr_note),
        ]
        return [
            CheckOut(
                label=check.label,
                status=check.status.value,
                actual=check.actual,
                rating=check.rating,
                note=note,
            )
            for check, note in entries
        ]

    def _weigh_event_out(
        evaluation: RigEvaluation,
        *,
        id: int,
        timestamp: str,
        truck_nickname: str | None,
        trailer_nickname: str | None,
        truck_id: int | None,
        trailer_id: int | None,
    ) -> WeighEventOut:
        # `truck_nickname`/`trailer_nickname` are `None` only for a record
        # persisted before the Nickname snapshot field existed (see
        # `WeighEventRecord`'s docstring) - unreachable for a brand new
        # table, but the same pre-Nickname fallback ADR 0004 already
        # specifies is applied defensively rather than assumed away. A
        # `None` id (One-Off) has no ID to build that fallback from, so it
        # falls back to the One-Off's own distinct default instead
        # (CONTEXT.md: One-Off Truck/Trailer) - unreachable too in practice,
        # since `record_weigh_event` already snapshots one of those two
        # defaults into `truck_nickname`/`trailer_nickname` whenever no
        # Nickname was given.
        time_gap_result = evaluation.time_gap_result
        truck_fallback = (
            f"Truck Profile #{truck_id}" if truck_id is not None else "One-Off Truck"
        )
        trailer_fallback = (
            f"Trailer Profile #{trailer_id}"
            if trailer_id is not None
            else "One-Off Trailer"
        )
        return WeighEventOut(
            id=id,
            timestamp=timestamp,
            truck_nickname=truck_nickname or truck_fallback,
            trailer_nickname=trailer_nickname or trailer_fallback,
            truck_id=truck_id,
            trailer_id=trailer_id,
            overall_status=evaluation.overall_status.value,
            checks=_checks_from_evaluation(evaluation),
            time_gap_hours=(
                time_gap_result.gap_hours if time_gap_result is not None else None
            ),
            time_gap_exceeds_threshold=(
                time_gap_result.exceeds_threshold
                if time_gap_result is not None
                else None
            ),
            disclaimer=LEGAL_DISCLAIMER,
        )

    @router.get(
        "/trucks/{truck_id}/reusable-solo-ticket",
        response_model=ReusableSoloTicketOut | None,
    )
    async def reusable_solo_ticket(
        truck_id: int,
        account: Account = Depends(current_active_account),
        session: AsyncSession = Depends(get_async_session),
    ) -> ReusableSoloTicketOut | None:
        garage_id = await _caller_garage_id(account, session)
        truck = await truck_profiles.get_truck_profile(
            session, id=truck_id, garage_id=garage_id
        )
        if truck is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        store = BackendWeighEventStore(sync_session_factory, garage_id=garage_id)

        def _lookup() -> WeighEventRecord | None:
            return _find_last_solo_ticket_record(store.list(), truck_id)

        record = await run_in_threadpool(_lookup)
        if record is None or record.solo_ticket is None:
            return None
        return ReusableSoloTicketOut(
            gross=record.solo_ticket.gross, from_timestamp=record.timestamp
        )

    @router.post(
        "/weigh-events",
        response_model=WeighEventOut,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_weigh_event(
        payload: WeighEventCreateRequest,
        account: Account = Depends(current_active_account),
        session: AsyncSession = Depends(get_async_session),
    ) -> WeighEventOut:
        garage_id = await _caller_garage_id(account, session)

        # Issue #45 / ADR 0017: `WeighEventCreateRequest`'s own validator
        # already guarantees exactly one of `truck_id`/`truck` (and
        # `trailer_id`/`trailer`) is present - the `assert`s below just
        # narrow that guarantee for mypy at each branch.
        truck_is_one_off = payload.truck is not None
        trailer_is_one_off = payload.trailer is not None

        if truck_is_one_off:
            assert payload.truck is not None
            truck = TruckProfile(
                gvwr=payload.truck.gvwr,
                front_gawr=payload.truck.front_gawr,
                rear_gawr=payload.truck.rear_gawr,
                gcwr=payload.truck.gcwr,
                nickname=payload.truck.nickname,
            )
        else:
            assert payload.truck_id is not None
            truck_row = await truck_profiles.get_truck_profile(
                session, id=payload.truck_id, garage_id=garage_id
            )
            if truck_row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            truck = TruckProfile(
                gvwr=truck_row.gvwr,
                front_gawr=truck_row.front_gawr,
                rear_gawr=truck_row.rear_gawr,
                gcwr=truck_row.gcwr,
                nickname=truck_row.nickname,
                id=truck_row.id,
            )

        if trailer_is_one_off:
            assert payload.trailer is not None
            trailer = TrailerProfile(
                gvwr=payload.trailer.gvwr,
                gawr=payload.trailer.gawr,
                axle_count=payload.trailer.axle_count,
                uvw=payload.trailer.uvw,
                nickname=payload.trailer.nickname,
            )
        else:
            assert payload.trailer_id is not None
            trailer_row = await trailer_profiles.get_trailer_profile(
                session, id=payload.trailer_id, garage_id=garage_id
            )
            if trailer_row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            trailer = TrailerProfile(
                gvwr=trailer_row.gvwr,
                gawr=trailer_row.gawr,
                axle_count=trailer_row.axle_count,
                uvw=trailer_row.uvw,
                nickname=trailer_row.nickname,
                id=trailer_row.id,
            )
        combined = CombinedTicket(
            steer=payload.combined.steer,
            drive=payload.combined.drive,
            trailer_axle=payload.combined.trailer_axle,
            gross=payload.combined.gross,
            reweigh_reference=payload.combined.reweigh_reference,
        )

        store = BackendWeighEventStore(sync_session_factory, garage_id=garage_id)

        solo: SoloTicket | None = None
        solo_is_unverified = False
        time_gap_hours: float | None = None
        reused_solo_from_timestamp: str | None = None

        if payload.solo is None:
            pass
        elif isinstance(payload.solo, FreshSoloTicketIn):
            fresh = payload.solo
            solo = SoloTicket(
                steer=fresh.steer,
                drive=fresh.drive,
                gross=fresh.gross,
                reweigh_reference=fresh.reweigh_reference,
            )
            # Solo Ticket linking stays single-shot (ADR 0009): the pure
            # check runs unchanged, and a no-match without an explicit
            # `confirm_solo_link` rejects the whole request with nothing
            # persisted - the HTTP equivalent of the CLI's manual-confirm
            # prompt, collapsed into a reject-then-resubmit cycle.
            if not reweigh_references_match(combined, solo) and not (
                payload.confirm_solo_link
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"reason": "solo_link_unconfirmed"},
                )
            time_gap_hours = fresh.time_gap_hours
        else:
            # A reused Solo Ticket is keyed on a real, persistent `truck_id`
            # (Story 8 / ADR 0017) - a One-Off Truck has no history to reuse
            # from, by definition. The real frontend never offers "reuse"
            # for a One-Off Truck (it skips the reusable-Solo-Ticket lookup
            # entirely); this rejects a hand-crafted request the same way an
            # unknown `from_timestamp` is rejected below.
            if truck_is_one_off or payload.truck_id is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            reused = payload.solo
            past_records = await run_in_threadpool(store.list)
            match = _find_reusable_solo_ticket_record(
                past_records,
                truck_id=payload.truck_id,
                from_timestamp=reused.from_timestamp,
            )
            if match is None or match.solo_ticket is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            # A reused Solo Ticket never goes through the Reweigh Reference
            # match/confirm check above - it was never a second physical
            # ticket with its own reference to match against (ADR 0005/0006).
            solo = replace(match.solo_ticket, gross=reused.gross)
            solo_is_unverified = reused.adjusted
            reused_solo_from_timestamp = reused.from_timestamp

        def _persist() -> tuple[RigEvaluation, WeighEventRecord] | list[Problem]:
            return record_weigh_event(
                truck,
                trailer,
                combined,
                solo,
                solo_is_unverified=solo_is_unverified,
                time_gap_hours=time_gap_hours,
                reused_solo_from_timestamp=reused_solo_from_timestamp,
                weigh_event_store=store,
                now=iso_now,
                truck_is_one_off=truck_is_one_off,
                trailer_is_one_off=trailer_is_one_off,
            )

        outcome = await run_in_threadpool(_persist)
        if isinstance(outcome, list):
            # Unreachable per issue #21's own Implementation Decisions - see
            # module docstring (still true: every precondition
            # `record_weigh_event` can fail on - a missing Truck/Trailer
            # Profile, or one with no id and no One-Off flag - is already
            # excluded above before `_persist` ever runs). Surfaced as a
            # 500, not silently swallowed, so a real regression here is
            # never hidden.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=[problem.message for problem in outcome],
            )

        evaluation, record = outcome
        assert store.last_saved_id is not None
        return _weigh_event_out(
            evaluation,
            id=store.last_saved_id,
            timestamp=record.timestamp,
            truck_nickname=record.truck_nickname,
            trailer_nickname=record.trailer_nickname,
            truck_id=record.truck_id,
            trailer_id=record.trailer_id,
        )

    @router.get("/weigh-events", response_model=list[WeighEventOut])
    async def list_weigh_events(
        limit: int = Query(default=DEFAULT_PAGE_SIZE, gt=0, le=MAX_PAGE_SIZE),
        offset: int = Query(default=0, ge=0),
        account: Account = Depends(current_active_account),
        session: AsyncSession = Depends(get_async_session),
    ) -> list[WeighEventOut]:
        garage_id = await _caller_garage_id(account, session)
        store = BackendWeighEventStore(sync_session_factory, garage_id=garage_id)
        records = await run_in_threadpool(
            store.list_newest_first, limit=limit, offset=offset
        )
        results = []
        for record in records:
            assert record.id is not None
            evaluation = rig_evaluation_from_record(record)
            results.append(
                _weigh_event_out(
                    evaluation,
                    id=record.id,
                    timestamp=record.timestamp,
                    truck_nickname=record.truck_nickname,
                    trailer_nickname=record.trailer_nickname,
                    truck_id=record.truck_id,
                    trailer_id=record.trailer_id,
                )
            )
        return results

    return router
