import sqlite3
from pathlib import Path

from towing_core.calculations import (
    AxleCheckResult,
    AxleOverloadResult,
    GcwrOverloadResult,
    HitchedGvwrOverloadResult,
    TrailerGvwrOverloadResult,
)
from towing_core.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile
from towing_core.storage import (
    InMemoryTrailerStore,
    InMemoryTruckStore,
    InMemoryWeighEventStore,
    TrailerStore,
    TruckStore,
    WeighEventRecord,
    WeighEventStore,
)

__all__ = [
    "InMemoryTrailerStore",
    "InMemoryTruckStore",
    "InMemoryWeighEventStore",
    "SqliteTrailerStore",
    "SqliteTruckStore",
    "SqliteWeighEventStore",
    "TrailerStore",
    "TruckStore",
    "WeighEventRecord",
    "WeighEventStore",
]


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
