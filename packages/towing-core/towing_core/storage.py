from dataclasses import dataclass, field, replace
from typing import Protocol

from towing_core.calculations import (
    AxleOverloadResult,
    GcwrOverloadResult,
    HitchedGvwrOverloadResult,
    TrailerGvwrOverloadResult,
)
from towing_core.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile


@dataclass(frozen=True)
class WeighEventRecord:
    """One persisted Weigh Event: the Truck+Trailer pairing used, the
    Combined Ticket entered, and the resulting Axle Overload / Hitched GVWR
    Overload / GCWR Overload checks (see CONTEXT.md: Weigh Event).

    `gcwr_result` is `None` when the Truck Profile had no GCWR on file at
    the time of the Weigh Event - the same "not evaluated" state
    `check_gcwr_overload` returns (see ADR 0002) - rather than a check that
    ran and passed.

    `solo_ticket` is `None` unless a Solo Ticket was entered *and* linked
    (automatically via a matching Reweigh Reference, or manually confirmed -
    see CONTEXT.md: Reweigh Reference) to this Weigh Event; an entered but
    unlinked Solo Ticket is discarded rather than persisted (see ADR 0005).
    `trailer_gvwr_result` mirrors that - `None` whenever `solo_ticket` is,
    the same "not evaluated" shape as `gcwr_result`. `time_gap_hours` is the
    user-supplied elapsed time between the two physical weighings for a
    linked pair (see ADR 0005), also `None` when there's no linked Solo
    Ticket.

    `reused_solo_from_timestamp` is the original `timestamp` of the past
    Weigh Event this record's `solo_ticket` was carried forward from, when
    the user chose "reuse last known weight" instead of weighing solo again
    (see CONTEXT.md: Reused Solo Weight, ADR 0006). Set whether the reused
    weight was carried forward unchanged or manually adjusted; `None` for a
    fresh Solo Ticket or when none was linked - it is never set
    independently of `solo_ticket`.

    `reused_solo_is_unverified` is `True` exactly when the reused weight
    above was manually adjusted (the user typed a new Gross Weight) rather
    than reused unchanged - mirrors `trailer_gvwr_result.is_unverified` at
    the time this record was saved, persisted separately so `weigh-event
    history` can still render the Unverified Value label without
    recomputing it (see CONTEXT.md: Unverified Value; ADR 0006). Always
    `False` when `reused_solo_from_timestamp` is `None`.

    `truck_nickname`/`trailer_nickname` snapshot the Truck/Trailer Profile's
    Nickname (or its computed default, e.g. "Truck 3", if it was blank) as
    it stood at the moment this Weigh Event was saved - a snapshot, not a
    live lookup, so a later rename or Profile deletion never changes how an
    already-recorded history entry renders (see CONTEXT.md: Nickname, ADR
    0004). Every record saved by `cli.run_weigh_event` populates both with a
    real string; `None` here is reserved for a record persisted before this
    field existed (see `SqliteWeighEventStore`'s nullable column), and is
    rendered with the pre-Nickname fallback ("Truck Profile #{truck_id}")
    rather than a guess at a Nickname that was never captured."""

    truck_id: int
    trailer_id: int
    ticket: CombinedTicket
    axle_result: AxleOverloadResult
    gvwr_result: HitchedGvwrOverloadResult
    timestamp: str
    gcwr_result: GcwrOverloadResult | None = None
    solo_ticket: SoloTicket | None = None
    trailer_gvwr_result: TrailerGvwrOverloadResult | None = None
    time_gap_hours: float | None = None
    reused_solo_from_timestamp: str | None = None
    reused_solo_is_unverified: bool = False
    truck_nickname: str | None = None
    trailer_nickname: str | None = None
    id: int | None = field(default=None, compare=False)


class TruckStore(Protocol):
    def save(self, profile: TruckProfile) -> None: ...

    def list(self) -> list[TruckProfile]: ...

    def update(self, profile: TruckProfile) -> None: ...

    def delete(self, profile_id: int) -> None: ...


class TrailerStore(Protocol):
    def save(self, profile: TrailerProfile) -> None: ...

    def list(self) -> list[TrailerProfile]: ...

    def update(self, profile: TrailerProfile) -> None: ...

    def delete(self, profile_id: int) -> None: ...


class WeighEventStore(Protocol):
    def save(self, record: WeighEventRecord) -> None: ...

    def list(self) -> list[WeighEventRecord]: ...


class InMemoryTruckStore:
    def __init__(self) -> None:
        self._profiles: dict[int, TruckProfile] = {}
        self._next_id = 1

    def save(self, profile: TruckProfile) -> None:
        profile_id = self._next_id
        self._next_id += 1
        self._profiles[profile_id] = replace(profile, id=profile_id)

    def list(self) -> list[TruckProfile]:
        return list(self._profiles.values())

    def update(self, profile: TruckProfile) -> None:
        if profile.id is None or profile.id not in self._profiles:
            raise ValueError(f"No Truck Profile with id {profile.id} to update.")
        self._profiles[profile.id] = profile

    def delete(self, profile_id: int) -> None:
        self._profiles.pop(profile_id, None)


class InMemoryTrailerStore:
    def __init__(self) -> None:
        self._profiles: dict[int, TrailerProfile] = {}
        self._next_id = 1

    def save(self, profile: TrailerProfile) -> None:
        profile_id = self._next_id
        self._next_id += 1
        self._profiles[profile_id] = replace(profile, id=profile_id)

    def list(self) -> list[TrailerProfile]:
        return list(self._profiles.values())

    def update(self, profile: TrailerProfile) -> None:
        if profile.id is None or profile.id not in self._profiles:
            raise ValueError(f"No Trailer Profile with id {profile.id} to update.")
        self._profiles[profile.id] = profile

    def delete(self, profile_id: int) -> None:
        self._profiles.pop(profile_id, None)


class InMemoryWeighEventStore:
    def __init__(self) -> None:
        self._records: dict[int, WeighEventRecord] = {}
        self._next_id = 1

    def save(self, record: WeighEventRecord) -> None:
        record_id = self._next_id
        self._next_id += 1
        self._records[record_id] = replace(record, id=record_id)

    def list(self) -> list[WeighEventRecord]:
        return list(self._records.values())
