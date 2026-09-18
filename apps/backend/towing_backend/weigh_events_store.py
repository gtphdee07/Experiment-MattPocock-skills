"""A synchronous, Garage-scoped `WeighEventStore` (issue #21).

Structurally satisfies `towing_core.storage.WeighEventStore`'s Protocol
(`save(record) -> None`, `list() -> list[WeighEventRecord]`) without
importing it - the same "structural, not inherited" relationship
`towing_app.sqlite.SqliteWeighEventStore` already has with the same
Protocol. Built on the synchronous engine/session factory in
`towing_backend.sync_db`, never the async one `towing_backend.db` builds for
`accounts`/`garages`/`truck_profiles`/`trailer_profiles` - see that module's
docstring for why.

Every instance is scoped to exactly one Garage (`garage_id`, baked in at
construction - mirroring `SqliteWeighEventStore` baking in a `db_path`
rather than taking one per call): `list()` only ever returns that Garage's
records, and `save()` always inserts with that Garage's id. `WeighEventStore`
's Protocol has no `garage_id` parameter (by design - see ADR 0010, `record_
weigh_event` is called "unmodified"), so scoping happens at the instance
boundary instead, exactly like `towing_backend.truck_profiles`/
`trailer_profiles` scope every query by an explicit `garage_id` argument, but
baked into the object here because the Protocol's own shape doesn't have
room for one.

Every instance is short-lived - constructed fresh per request (see
`towing_backend.weigh_events_routes`), used for exactly one logical
operation, then discarded. `last_saved_id` is deliberately instance state
set by `save()`: `WeighEventStore.save()` returns `None` per the Protocol
(and `WeighEventRecord` is a frozen dataclass `record_weigh_event` cannot
mutate to report a new id back to its caller), so the route handler - which
holds its own reference to this concrete class, not just the Protocol-typed
parameter it hands to `record_weigh_event` - reads the newly-inserted row's
id off this attribute after the call returns, rather than needing `save()`
to violate the Protocol's `-> None` return type.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.orm import Session, sessionmaker

from towing_backend.db import weigh_events
from towing_core.calculations import (
    AxleCheckResult,
    AxleOverloadResult,
    GcwrOverloadResult,
    HitchedGvwrOverloadResult,
    TrailerGvwrOverloadResult,
    compute_derived_trailer_weight,
)
from towing_core.models import CombinedTicket, SoloTicket
from towing_core.storage import WeighEventRecord


class BackendWeighEventStore:
    def __init__(
        self, session_factory: sessionmaker[Session], *, garage_id: int
    ) -> None:
        self._session_factory = session_factory
        self._garage_id = garage_id
        # Set by `save()` - the id of the most recently inserted row, for a
        # route handler to read directly off this instance (see class
        # docstring). `None` until a `save()` call actually succeeds.
        self.last_saved_id: int | None = None

    def save(self, record: WeighEventRecord) -> None:
        gcwr_rating = (
            record.gcwr_result.gcwr_rating if record.gcwr_result is not None else None
        )
        solo = record.solo_ticket
        trailer_gvwr_rating = (
            record.trailer_gvwr_result.gvwr_rating
            if record.trailer_gvwr_result is not None
            else None
        )
        values: dict[str, Any] = {
            "garage_id": self._garage_id,
            "truck_id": record.truck_id,
            "trailer_id": record.trailer_id,
            "steer": record.ticket.steer,
            "drive": record.ticket.drive,
            "trailer_axle": record.ticket.trailer_axle,
            "gross": record.ticket.gross,
            "steer_rating": record.axle_result.steer.rating,
            "drive_rating": record.axle_result.drive.rating,
            "trailer_rating": record.axle_result.trailer.rating,
            "gvwr_rating": record.gvwr_result.gvwr_rating,
            "gcwr_rating": gcwr_rating,
            "timestamp": record.timestamp,
            "combined_reweigh_reference": record.ticket.reweigh_reference,
            "solo_steer": solo.steer if solo is not None else None,
            "solo_drive": solo.drive if solo is not None else None,
            "solo_gross": solo.gross if solo is not None else None,
            "solo_reweigh_reference": (
                solo.reweigh_reference if solo is not None else None
            ),
            "trailer_gvwr_rating": trailer_gvwr_rating,
            "time_gap_hours": record.time_gap_hours,
            "reused_solo_from_timestamp": record.reused_solo_from_timestamp,
            "ticket_timestamp": record.ticket.timestamp,
            "solo_timestamp": solo.timestamp if solo is not None else None,
            "reused_solo_is_unverified": record.reused_solo_is_unverified,
            "truck_nickname": record.truck_nickname,
            "trailer_nickname": record.trailer_nickname,
        }
        with self._session_factory() as session:
            new_id = session.execute(
                insert(weigh_events).values(**values).returning(weigh_events.c.id)
            ).scalar_one()
            session.commit()
        self.last_saved_id = new_id

    def list_newest_first(self, *, limit: int, offset: int) -> list[WeighEventRecord]:
        """The `GET /weigh-events` history endpoint's own query - newest
        first (by `id`, a monotonic proxy for insertion order - see
        `towing_backend.weigh_events_routes`'s docstring for why `id` rather
        than the `timestamp` string column), paginated. Not part of
        `WeighEventStore`'s Protocol (which has only the unfiltered,
        unordered `list()` below, used internally by `record_weigh_event`/
        `_find_last_solo_ticket_record`) - an additional method this
        concrete class exposes, called directly off this instance rather
        than through the Protocol-typed parameter.

        Defined *before* `list()` below in this class body on purpose: once
        a method named `list` is defined, that name shadows the builtin
        `list` for every subsequent statement in this class body (including
        annotations, even with `from __future__ import annotations` - mypy
        still resolves them against the enclosing class namespace), which
        would break this method's own `-> list[WeighEventRecord]` return
        annotation if it came second."""
        with self._session_factory() as session:
            rows = session.execute(
                select(weigh_events)
                .where(weigh_events.c.garage_id == self._garage_id)
                .order_by(weigh_events.c.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        return [_row_to_record(row) for row in rows]

    def list(self) -> list[WeighEventRecord]:
        with self._session_factory() as session:
            rows = session.execute(
                select(weigh_events)
                .where(weigh_events.c.garage_id == self._garage_id)
                .order_by(weigh_events.c.id)
            ).all()
        return [_row_to_record(row) for row in rows]


def _row_to_record(row: Any) -> WeighEventRecord:
    """Mirrors `SqliteWeighEventStore.list()`'s row-reconstruction exactly -
    see that method's own comments for why `TrailerGvwrOverloadResult` is
    only rebuilt when both a linked Solo Ticket and a persisted
    `trailer_gvwr_rating` are present."""
    solo_steer = row.solo_steer
    solo_ticket = (
        SoloTicket(
            steer=solo_steer,
            drive=row.solo_drive,
            gross=row.solo_gross,
            reweigh_reference=row.solo_reweigh_reference,
            timestamp=row.solo_timestamp,
        )
        if solo_steer is not None
        else None
    )
    trailer_gvwr_rating = row.trailer_gvwr_rating
    reused_solo_is_unverified = bool(row.reused_solo_is_unverified)
    combined_ticket = CombinedTicket(
        steer=row.steer,
        drive=row.drive,
        trailer_axle=row.trailer_axle,
        gross=row.gross,
        reweigh_reference=row.combined_reweigh_reference,
        timestamp=row.ticket_timestamp,
    )
    trailer_gvwr_result = (
        TrailerGvwrOverloadResult(
            derived_trailer_weight=compute_derived_trailer_weight(
                combined_ticket, solo_ticket
            ),
            gvwr_rating=trailer_gvwr_rating,
            is_unverified=reused_solo_is_unverified,
        )
        if solo_ticket is not None and trailer_gvwr_rating is not None
        else None
    )
    return WeighEventRecord(
        truck_id=row.truck_id,
        trailer_id=row.trailer_id,
        ticket=combined_ticket,
        axle_result=AxleOverloadResult(
            steer=AxleCheckResult(
                axle_name="Steer Axle", actual=row.steer, rating=row.steer_rating
            ),
            drive=AxleCheckResult(
                axle_name="Drive Axle", actual=row.drive, rating=row.drive_rating
            ),
            trailer=AxleCheckResult(
                axle_name="Trailer Axle",
                actual=row.trailer_axle,
                rating=row.trailer_rating,
            ),
        ),
        gvwr_result=HitchedGvwrOverloadResult(
            combined_actual=row.steer + row.drive,
            gvwr_rating=row.gvwr_rating,
        ),
        gcwr_result=(
            GcwrOverloadResult(combined_actual=row.gross, gcwr_rating=row.gcwr_rating)
            if row.gcwr_rating is not None
            else None
        ),
        timestamp=row.timestamp,
        solo_ticket=solo_ticket,
        trailer_gvwr_result=trailer_gvwr_result,
        time_gap_hours=row.time_gap_hours,
        reused_solo_from_timestamp=row.reused_solo_from_timestamp,
        reused_solo_is_unverified=reused_solo_is_unverified,
        truck_nickname=row.truck_nickname,
        trailer_nickname=row.trailer_nickname,
        id=row.id,
    )
