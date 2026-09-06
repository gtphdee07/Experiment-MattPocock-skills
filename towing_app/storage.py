import sqlite3
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Protocol

from towing_app.calculations import (
    AxleCheckResult,
    AxleOverloadResult,
    GcwrOverloadResult,
    HitchedGvwrOverloadResult,
    TrailerGvwrOverloadResult,
)
from towing_app.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile


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


class SqliteTruckStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS truck_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gvwr REAL NOT NULL,
                    front_gawr REAL NOT NULL,
                    rear_gawr REAL NOT NULL,
                    gcwr REAL,
                    nickname TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def save(self, profile: TruckProfile) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO truck_profiles "
                "(gvwr, front_gawr, rear_gawr, gcwr, nickname) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    profile.gvwr,
                    profile.front_gawr,
                    profile.rear_gawr,
                    profile.gcwr,
                    profile.nickname,
                ),
            )

    def list(self) -> list[TruckProfile]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, gvwr, front_gawr, rear_gawr, gcwr, nickname "
                "FROM truck_profiles ORDER BY id"
            ).fetchall()
        return [
            TruckProfile(
                gvwr=row[1],
                front_gawr=row[2],
                rear_gawr=row[3],
                gcwr=row[4],
                nickname=row[5],
                id=row[0],
            )
            for row in rows
        ]

    def update(self, profile: TruckProfile) -> None:
        if profile.id is None:
            raise ValueError("Cannot update a Truck Profile with no id.")
        with self._connect() as conn:
            conn.execute(
                "UPDATE truck_profiles "
                "SET gvwr = ?, front_gawr = ?, rear_gawr = ?, gcwr = ?, nickname = ? "
                "WHERE id = ?",
                (
                    profile.gvwr,
                    profile.front_gawr,
                    profile.rear_gawr,
                    profile.gcwr,
                    profile.nickname,
                    profile.id,
                ),
            )

    def delete(self, profile_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM truck_profiles WHERE id = ?", (profile_id,))


class SqliteTrailerStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trailer_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gvwr REAL NOT NULL,
                    gawr REAL NOT NULL,
                    axle_count INTEGER NOT NULL,
                    uvw REAL,
                    nickname TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def save(self, profile: TrailerProfile) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO trailer_profiles (gvwr, gawr, axle_count, uvw, nickname) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    profile.gvwr,
                    profile.gawr,
                    profile.axle_count,
                    profile.uvw,
                    profile.nickname,
                ),
            )

    def list(self) -> list[TrailerProfile]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, gvwr, gawr, axle_count, uvw, nickname "
                "FROM trailer_profiles ORDER BY id"
            ).fetchall()
        return [
            TrailerProfile(
                gvwr=row[1],
                gawr=row[2],
                axle_count=row[3],
                uvw=row[4],
                nickname=row[5],
                id=row[0],
            )
            for row in rows
        ]

    def update(self, profile: TrailerProfile) -> None:
        if profile.id is None:
            raise ValueError("Cannot update a Trailer Profile with no id.")
        with self._connect() as conn:
            conn.execute(
                "UPDATE trailer_profiles "
                "SET gvwr = ?, gawr = ?, axle_count = ?, uvw = ?, nickname = ? "
                "WHERE id = ?",
                (
                    profile.gvwr,
                    profile.gawr,
                    profile.axle_count,
                    profile.uvw,
                    profile.nickname,
                    profile.id,
                ),
            )

    def delete(self, profile_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM trailer_profiles WHERE id = ?", (profile_id,))


class SqliteWeighEventStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS weigh_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    truck_id INTEGER NOT NULL,
                    trailer_id INTEGER NOT NULL,
                    steer REAL NOT NULL,
                    drive REAL NOT NULL,
                    trailer_axle REAL NOT NULL,
                    gross REAL NOT NULL,
                    steer_rating REAL NOT NULL,
                    drive_rating REAL NOT NULL,
                    trailer_rating REAL NOT NULL,
                    gvwr_rating REAL NOT NULL,
                    gcwr_rating REAL,
                    timestamp TEXT NOT NULL,
                    combined_reweigh_reference TEXT,
                    solo_steer REAL,
                    solo_drive REAL,
                    solo_gross REAL,
                    solo_reweigh_reference TEXT,
                    trailer_gvwr_rating REAL,
                    time_gap_hours REAL,
                    reused_solo_from_timestamp TEXT,
                    ticket_timestamp TEXT,
                    solo_timestamp TEXT,
                    reused_solo_is_unverified INTEGER,
                    truck_nickname TEXT,
                    trailer_nickname TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

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
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO weigh_events (truck_id, trailer_id, steer, drive, "
                "trailer_axle, gross, steer_rating, drive_rating, trailer_rating, "
                "gvwr_rating, gcwr_rating, timestamp, combined_reweigh_reference, "
                "solo_steer, solo_drive, solo_gross, solo_reweigh_reference, "
                "trailer_gvwr_rating, time_gap_hours, reused_solo_from_timestamp, "
                "ticket_timestamp, solo_timestamp, reused_solo_is_unverified, "
                "truck_nickname, trailer_nickname) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?, ?, ?)",
                (
                    record.truck_id,
                    record.trailer_id,
                    record.ticket.steer,
                    record.ticket.drive,
                    record.ticket.trailer_axle,
                    record.ticket.gross,
                    record.axle_result.steer.rating,
                    record.axle_result.drive.rating,
                    record.axle_result.trailer.rating,
                    record.gvwr_result.gvwr_rating,
                    gcwr_rating,
                    record.timestamp,
                    record.ticket.reweigh_reference,
                    solo.steer if solo is not None else None,
                    solo.drive if solo is not None else None,
                    solo.gross if solo is not None else None,
                    solo.reweigh_reference if solo is not None else None,
                    trailer_gvwr_rating,
                    record.time_gap_hours,
                    record.reused_solo_from_timestamp,
                    record.ticket.timestamp,
                    solo.timestamp if solo is not None else None,
                    record.reused_solo_is_unverified,
                    record.truck_nickname,
                    record.trailer_nickname,
                ),
            )

    def list(self) -> list[WeighEventRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, truck_id, trailer_id, steer, drive, trailer_axle, "
                "gross, steer_rating, drive_rating, trailer_rating, gvwr_rating, "
                "gcwr_rating, timestamp, combined_reweigh_reference, solo_steer, "
                "solo_drive, solo_gross, solo_reweigh_reference, "
                "trailer_gvwr_rating, time_gap_hours, reused_solo_from_timestamp, "
                "ticket_timestamp, solo_timestamp, reused_solo_is_unverified, "
                "truck_nickname, trailer_nickname "
                "FROM weigh_events ORDER BY id"
            ).fetchall()
        records = []
        for row in rows:
            solo_steer = row[14]
            solo_ticket = (
                SoloTicket(
                    steer=solo_steer,
                    drive=row[15],
                    gross=row[16],
                    reweigh_reference=row[17],
                    timestamp=row[22],
                )
                if solo_steer is not None
                else None
            )
            trailer_gvwr_rating = row[18]
            reused_solo_is_unverified = bool(row[23])
            trailer_gvwr_result = (
                TrailerGvwrOverloadResult(
                    derived_trailer_weight=row[6] - solo_ticket.gross,
                    gvwr_rating=trailer_gvwr_rating,
                    is_unverified=reused_solo_is_unverified,
                )
                if solo_ticket is not None and trailer_gvwr_rating is not None
                else None
            )
            records.append(
                WeighEventRecord(
                    truck_id=row[1],
                    trailer_id=row[2],
                    ticket=CombinedTicket(
                        steer=row[3],
                        drive=row[4],
                        trailer_axle=row[5],
                        gross=row[6],
                        reweigh_reference=row[13],
                        timestamp=row[21],
                    ),
                    axle_result=AxleOverloadResult(
                        steer=AxleCheckResult(
                            axle_name="Steer Axle", actual=row[3], rating=row[7]
                        ),
                        drive=AxleCheckResult(
                            axle_name="Drive Axle", actual=row[4], rating=row[8]
                        ),
                        trailer=AxleCheckResult(
                            axle_name="Trailer Axle", actual=row[5], rating=row[9]
                        ),
                    ),
                    gvwr_result=HitchedGvwrOverloadResult(
                        combined_actual=row[3] + row[4], gvwr_rating=row[10]
                    ),
                    gcwr_result=(
                        GcwrOverloadResult(combined_actual=row[6], gcwr_rating=row[11])
                        if row[11] is not None
                        else None
                    ),
                    timestamp=row[12],
                    solo_ticket=solo_ticket,
                    trailer_gvwr_result=trailer_gvwr_result,
                    time_gap_hours=row[19],
                    reused_solo_from_timestamp=row[20],
                    reused_solo_is_unverified=reused_solo_is_unverified,
                    truck_nickname=row[24],
                    trailer_nickname=row[25],
                    id=row[0],
                )
            )
        return records
