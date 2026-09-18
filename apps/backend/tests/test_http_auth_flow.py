"""Tier 1 (HTTP-level, offline): drives the app end-to-end through
`fastapi.testclient.TestClient`, exactly as a browser would - the same
"drive the outermost interface" pattern `apps/cli/tests` already uses for
the CLI's `run_*` functions (see TESTING.md's "Surface tests" category).

Every test gets its own fresh SQLite file (the `client`/`settings`
fixtures in conftest.py) - no mock ever stands in for the database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

# `starlette.testclient.TestClient` (this installed version) is built on
# `httpx2`, not the classic `httpx` package - matching its own response
# type here, rather than the classic `httpx`, is what keeps this
# annotation accurate.
import httpx2 as httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from towing_backend.settings import Settings

EMAIL = "addie@example.com"
PASSWORD = "correct-horse-battery-staple"


def register(
    client: TestClient, *, email: str = EMAIL, password: str = PASSWORD
) -> dict[str, Any]:
    response = client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def login(
    client: TestClient, *, email: str = EMAIL, password: str = PASSWORD
) -> httpx.Response:
    return client.post("/auth/login", data={"username": email, "password": password})


def garages_table_rows(settings: Settings) -> list[sqlite3.Row]:
    db_path = settings.database_url.removeprefix("sqlite+aiosqlite:///")
    conn = sqlite3.connect(Path(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM garages").fetchall()
    finally:
        conn.close()


# --- Story 1/4: register creates an Account and a Garage -------------------


def test_register_creates_account_and_garage(
    client: TestClient, settings: Settings
) -> None:
    account = register(client)

    assert account["email"] == EMAIL
    assert "created_at" in account

    rows = garages_table_rows(settings)
    assert len(rows) == 1
    assert rows[0]["account_id"] == account["id"]


# --- Story 2: duplicate email ------------------------------------------------


def test_register_duplicate_email_fails_with_clear_error(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/auth/register", json={"email": EMAIL, "password": PASSWORD}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "REGISTER_USER_ALREADY_EXISTS"


# --- Story 3: password policy ------------------------------------------------


def test_register_too_short_password_fails(client: TestClient) -> None:
    response = client.post("/auth/register", json={"email": EMAIL, "password": "short"})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "REGISTER_INVALID_PASSWORD"


# --- Story 5/6/7: login, cookie persistence, wrong credentials -------------


def test_login_then_me_succeeds_and_cookie_persists(client: TestClient) -> None:
    register(client)

    login_response = login(client)

    assert login_response.status_code == 204
    assert "towing_backend_session" in login_response.cookies

    me_response = client.get("/users/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == EMAIL


def test_login_wrong_password_fails_generically(client: TestClient) -> None:
    register(client)

    response = login(client, password="not-the-password")

    assert response.status_code == 400
    assert response.json()["detail"] == "LOGIN_BAD_CREDENTIALS"


def test_login_unregistered_email_fails_generically(client: TestClient) -> None:
    response = login(client, email="nobody@example.com")

    assert response.status_code == 400
    assert response.json()["detail"] == "LOGIN_BAD_CREDENTIALS"


# --- Story 8: logout ---------------------------------------------------------


def test_logout_revokes_the_session_cookie(client: TestClient) -> None:
    register(client)
    login(client)
    assert client.get("/users/me").status_code == 200

    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 204

    assert client.get("/users/me").status_code == 401


# --- Story 9: unauthenticated access to a protected route ------------------


def test_unauthenticated_me_is_rejected(client: TestClient) -> None:
    response = client.get("/users/me")

    assert response.status_code == 401


# --- Story 18: unauthenticated health check ---------------------------------


def test_health_requires_no_auth(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


# --- Story 10/11/12: read/update own account info ---------------------------


def test_get_me_returns_basic_account_info(client: TestClient) -> None:
    register(client)
    login(client)

    response = client.get("/users/me")

    body = response.json()
    assert body["email"] == EMAIL
    assert "created_at" in body
    assert "id" in body


def test_patch_me_changes_email(client: TestClient) -> None:
    register(client)
    login(client)

    response = client.patch("/users/me", json={"email": "new@example.com"})

    assert response.status_code == 200
    assert response.json()["email"] == "new@example.com"


def test_patch_me_changes_password(client: TestClient, app: FastAPI) -> None:
    register(client)
    login(client)

    response = client.patch("/users/me", json={"password": "a-new-strong-password"})
    assert response.status_code == 200

    # The old password should no longer work; a fresh client avoids any
    # stale cookie state from the update.
    fresh = TestClient(app)
    stale_login = login(fresh)
    assert stale_login.status_code == 400

    new_login = login(fresh, password="a-new-strong-password")
    assert new_login.status_code == 204


# --- Story 13/14: delete own account, cascading Garage deletion ------------


def test_delete_me_removes_account_garage_and_session(
    client: TestClient, settings: Settings
) -> None:
    account = register(client)
    login(client)
    assert len(garages_table_rows(settings)) == 1

    delete_response = client.delete("/users/me")
    assert delete_response.status_code == 204

    assert garages_table_rows(settings) == []

    # The session cookie the client still holds must no longer work - the
    # underlying `sessions` row is expected to have cascaded away with the
    # Account it referenced.
    assert client.get("/users/me").status_code == 401

    # Re-registering the same email now succeeds again (the unique-email
    # constraint would otherwise reject it with REGISTER_USER_ALREADY_EXISTS)
    # - proof the account itself, not just its Garage, is really gone. Its
    # `id` isn't asserted against the original: SQLite reissues rowids from
    # the deleted table's now-lowest free value, so reuse here is expected
    # dialect behavior, not evidence either way.
    reregistered = register(client, email=EMAIL)
    assert reregistered["email"] == account["email"] == EMAIL
