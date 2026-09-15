"""SQLite-backed implementations of the `towing_core.storage` Store ports.

Each class structurally satisfies the matching Protocol in
`towing_core.storage` (`TruckStore` / `TrailerStore` / `WeighEventStore`)
without importing it - the compute core stays free of `sqlite3`, and these
adapters are what the shipped CLI wires in via `cli.main`.
"""

import sqlite3
from pathlib import Path
from typing import Any

from towing_core.calculations import (
    AxleCheckResult,
    AxleOverloadResult,
    GcwrOverloadResult,
    HitchedGvwrOverloadResult,
    TrailerGvwrOverloadResult,
    compute_derived_trailer_weight,
)
from towing_core.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile
from towing_core.storage import WeighEventRecord


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
    """The `weigh_events` table's column names/types/order live in exactly
    one place - `_COLUMN_DEFS` below - and the `CREATE TABLE` DDL, the
    `INSERT`, and the `SELECT` all derive their column list from it (`id`,
    the autoincrement primary key, is handled separately since it's never
    written by `save`). Reads use `sqlite3.Row` and name-based access
    (`row["column_name"]`), and writes use named placeholders (`:column_name`)
    fed by a dict, so a future accidental reordering of `_COLUMN_DEFS` - the
    one place left to transpose - surfaces as a wrong *value* under a given
    column name rather than silently reading/writing the wrong column."""

    # (column name, SQL type + constraints) in the table's actual on-disk
    # order. Adding/reordering a column only requires editing this tuple.
    _COLUMN_DEFS: tuple[tuple[str, str], ...] = (
        ("truck_id", "INTEGER NOT NULL"),
        ("trailer_id", "INTEGER NOT NULL"),
        ("steer", "REAL NOT NULL"),
        ("drive", "REAL NOT NULL"),
        ("trailer_axle", "REAL NOT NULL"),
        ("gross", "REAL NOT NULL"),
        ("steer_rating", "REAL NOT NULL"),
        ("drive_rating", "REAL NOT NULL"),
        ("trailer_rating", "REAL NOT NULL"),
        ("gvwr_rating", "REAL NOT NULL"),
        ("gcwr_rating", "REAL"),
        ("timestamp", "TEXT NOT NULL"),
        ("combined_reweigh_reference", "TEXT"),
        ("solo_steer", "REAL"),
        ("solo_drive", "REAL"),
        ("solo_gross", "REAL"),
        ("solo_reweigh_reference", "TEXT"),
        ("trailer_gvwr_rating", "REAL"),
        ("time_gap_hours", "REAL"),
        ("reused_solo_from_timestamp", "TEXT"),
        ("ticket_timestamp", "TEXT"),
        ("solo_timestamp", "TEXT"),
        ("reused_solo_is_unverified", "INTEGER"),
        ("truck_nickname", "TEXT"),
        ("trailer_nickname", "TEXT"),
    )
    _COLUMNS: tuple[str, ...] = tuple(name for name, _decl in _COLUMN_DEFS)

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        column_lines = ",\n                    ".join(
            f"{name} {decl}" for name, decl in self._COLUMN_DEFS
        )
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS weigh_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    {column_lines}
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

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
            "solo_reweigh_reference": solo.reweigh_reference
            if solo is not None
            else None,
            "trailer_gvwr_rating": trailer_gvwr_rating,
            "time_gap_hours": record.time_gap_hours,
            "reused_solo_from_timestamp": record.reused_solo_from_timestamp,
            "ticket_timestamp": record.ticket.timestamp,
            "solo_timestamp": solo.timestamp if solo is not None else None,
            "reused_solo_is_unverified": record.reused_solo_is_unverified,
            "truck_nickname": record.truck_nickname,
            "trailer_nickname": record.trailer_nickname,
        }
        # Re-keying through `_COLUMNS` (rather than executing `values`
        # as-is) means a name missing from either side raises a KeyError
        # here instead of silently inserting NULL/being ignored.
        params = {name: values[name] for name in self._COLUMNS}
        columns_clause = ", ".join(self._COLUMNS)
        placeholders = ", ".join(f":{name}" for name in self._COLUMNS)
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO weigh_events ({columns_clause}) VALUES ({placeholders})",
                params,
            )

    def list(self) -> list[WeighEventRecord]:
        columns_clause = ", ".join(self._COLUMNS)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT id, {columns_clause} FROM weigh_events ORDER BY id"
            ).fetchall()
        records = []
        for row in rows:
            solo_steer = row["solo_steer"]
            solo_ticket = (
                SoloTicket(
                    steer=solo_steer,
                    drive=row["solo_drive"],
                    gross=row["solo_gross"],
                    reweigh_reference=row["solo_reweigh_reference"],
                    timestamp=row["solo_timestamp"],
                )
                if solo_steer is not None
                else None
            )
            trailer_gvwr_rating = row["trailer_gvwr_rating"]
            reused_solo_is_unverified = bool(row["reused_solo_is_unverified"])
            combined_ticket = CombinedTicket(
                steer=row["steer"],
                drive=row["drive"],
                trailer_axle=row["trailer_axle"],
                gross=row["gross"],
                reweigh_reference=row["combined_reweigh_reference"],
                timestamp=row["ticket_timestamp"],
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
            records.append(
                WeighEventRecord(
                    truck_id=row["truck_id"],
                    trailer_id=row["trailer_id"],
                    ticket=combined_ticket,
                    axle_result=AxleOverloadResult(
                        steer=AxleCheckResult(
                            axle_name="Steer Axle",
                            actual=row["steer"],
                            rating=row["steer_rating"],
                        ),
                        drive=AxleCheckResult(
                            axle_name="Drive Axle",
                            actual=row["drive"],
                            rating=row["drive_rating"],
                        ),
                        trailer=AxleCheckResult(
                            axle_name="Trailer Axle",
                            actual=row["trailer_axle"],
                            rating=row["trailer_rating"],
                        ),
                    ),
                    gvwr_result=HitchedGvwrOverloadResult(
                        combined_actual=row["steer"] + row["drive"],
                        gvwr_rating=row["gvwr_rating"],
                    ),
                    gcwr_result=(
                        GcwrOverloadResult(
                            combined_actual=row["gross"],
                            gcwr_rating=row["gcwr_rating"],
                        )
                        if row["gcwr_rating"] is not None
                        else None
                    ),
                    timestamp=row["timestamp"],
                    solo_ticket=solo_ticket,
                    trailer_gvwr_result=trailer_gvwr_result,
                    time_gap_hours=row["time_gap_hours"],
                    reused_solo_from_timestamp=row["reused_solo_from_timestamp"],
                    reused_solo_is_unverified=reused_solo_is_unverified,
                    truck_nickname=row["truck_nickname"],
                    trailer_nickname=row["trailer_nickname"],
                    id=row["id"],
                )
            )
        return records
