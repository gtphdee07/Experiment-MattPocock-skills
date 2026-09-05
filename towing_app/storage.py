import sqlite3
from pathlib import Path
from typing import Protocol

from towing_app.models import TrailerProfile, TruckProfile


class TruckStore(Protocol):
    def save(self, profile: TruckProfile) -> None: ...

    def list(self) -> list[TruckProfile]: ...


class TrailerStore(Protocol):
    def save(self, profile: TrailerProfile) -> None: ...

    def list(self) -> list[TrailerProfile]: ...


class InMemoryTruckStore:
    def __init__(self) -> None:
        self._profiles: list[TruckProfile] = []

    def save(self, profile: TruckProfile) -> None:
        self._profiles.append(profile)

    def list(self) -> list[TruckProfile]:
        return list(self._profiles)


class InMemoryTrailerStore:
    def __init__(self) -> None:
        self._profiles: list[TrailerProfile] = []

    def save(self, profile: TrailerProfile) -> None:
        self._profiles.append(profile)

    def list(self) -> list[TrailerProfile]:
        return list(self._profiles)


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
                "SELECT gvwr, front_gawr, rear_gawr, gcwr "
                "FROM truck_profiles ORDER BY id"
            ).fetchall()
        return [
            TruckProfile(gvwr=row[0], front_gawr=row[1], rear_gawr=row[2], gcwr=row[3])
            for row in rows
        ]


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
                "SELECT gvwr, gawr, axle_count, uvw FROM trailer_profiles ORDER BY id"
            ).fetchall()
        return [
            TrailerProfile(gvwr=row[0], gawr=row[1], axle_count=row[2], uvw=row[3])
            for row in rows
        ]
