"""Shared fixtures for the offline (tier 1 + tier 2) test suites.

Every test gets its own fresh SQLite file under pytest's per-test
`tmp_path`, matching `packages/towing-app/tests/test_sqlite_*_storage.py`'s
existing "real file, fresh per test" pattern - never a mock standing in
for the database (TESTING.md's "external seams" principle, restated in
issue #18's own Testing Decisions).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from towing_backend.app import create_app
from towing_backend.settings import Settings


def make_settings(db_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{db_path}",
        cors_origin="http://localhost:5173",
        secret="test-secret",
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path / "backend.db")


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
