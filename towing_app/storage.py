import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Protocol

from towing_app.models import TrailerProfile, TruckProfile


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
