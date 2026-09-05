import sqlite3
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Protocol

from towing_app.calculations import (
    AxleCheckResult,
    AxleOverloadResult,
    HitchedGvwrOverloadResult,
)
from towing_app.models import CombinedTicket, TrailerProfile, TruckProfile


@dataclass(frozen=True)
class WeighEventRecord:
    """One persisted Weigh Event: the Truck+Trailer pairing used, the
    Combined Ticket entered, and the resulting Axle Overload / Hitched GVWR
    Overload checks (see CONTEXT.md: Weigh Event)."""

    truck_id: int
    trailer_id: int
    ticket: CombinedTicket
    axle_result: AxleOverloadResult
    gvwr_result: HitchedGvwrOverloadResult
    timestamp: str
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
                    gcwr REAL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def save(self, profile: TruckProfile) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO truck_profiles (gvwr, front_gawr, rear_gawr, gcwr) "
                "VALUES (?, ?, ?, ?)",
                (profile.gvwr, profile.front_gawr, profile.rear_gawr, profile.gcwr),
            )

    def list(self) -> list[TruckProfile]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, gvwr, front_gawr, rear_gawr, gcwr "
                "FROM truck_profiles ORDER BY id"
            ).fetchall()
        return [
            TruckProfile(
                gvwr=row[1],
                front_gawr=row[2],
                rear_gawr=row[3],
                gcwr=row[4],
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
                "SET gvwr = ?, front_gawr = ?, rear_gawr = ?, gcwr = ? "
                "WHERE id = ?",
                (
                    profile.gvwr,
                    profile.front_gawr,
                    profile.rear_gawr,
                    profile.gcwr,
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
                    uvw REAL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def save(self, profile: TrailerProfile) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO trailer_profiles (gvwr, gawr, axle_count, uvw) "
                "VALUES (?, ?, ?, ?)",
                (profile.gvwr, profile.gawr, profile.axle_count, profile.uvw),
            )

    def list(self) -> list[TrailerProfile]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, gvwr, gawr, axle_count, uvw "
                "FROM trailer_profiles ORDER BY id"
            ).fetchall()
        return [
            TrailerProfile(
                gvwr=row[1], gawr=row[2], axle_count=row[3], uvw=row[4], id=row[0]
            )
            for row in rows
        ]

    def update(self, profile: TrailerProfile) -> None:
        if profile.id is None:
            raise ValueError("Cannot update a Trailer Profile with no id.")
        with self._connect() as conn:
            conn.execute(
                "UPDATE trailer_profiles "
                "SET gvwr = ?, gawr = ?, axle_count = ?, uvw = ? "
                "WHERE id = ?",
                (
                    profile.gvwr,
                    profile.gawr,
                    profile.axle_count,
                    profile.uvw,
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
                    timestamp TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def save(self, record: WeighEventRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO weigh_events (truck_id, trailer_id, steer, drive, "
                "trailer_axle, gross, steer_rating, drive_rating, trailer_rating, "
                "gvwr_rating, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                    record.timestamp,
                ),
            )

    def list(self) -> list[WeighEventRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, truck_id, trailer_id, steer, drive, trailer_axle, "
                "gross, steer_rating, drive_rating, trailer_rating, gvwr_rating, "
                "timestamp FROM weigh_events ORDER BY id"
            ).fetchall()
        return [
            WeighEventRecord(
                truck_id=row[1],
                trailer_id=row[2],
                ticket=CombinedTicket(
                    steer=row[3], drive=row[4], trailer_axle=row[5], gross=row[6]
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
                timestamp=row[11],
                id=row[0],
            )
            for row in rows
        ]
