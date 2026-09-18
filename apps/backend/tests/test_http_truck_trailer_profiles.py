"""Tier 1 (HTTP-level, offline): drives Truck/Trailer Profile CRUD through
`fastapi.testclient.TestClient`, exactly like `test_http_auth_flow.py`
does for Account/session routes - reusing that file's `register`/`login`
helpers (issue #19's Testing Decisions: "reusing #18's register+login test
helper") rather than duplicating the setup.

Every test gets its own fresh SQLite file (the `client`/`settings`
fixtures in conftest.py) - no mock ever stands in for the database.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_http_auth_flow import login, register

TRUCK_PAYLOAD = {"gvwr": 10000.0, "front_gawr": 4500.0, "rear_gawr": 6500.0}
TRAILER_PAYLOAD = {"gvwr": 8000.0, "gawr": 3500.0, "axle_count": 2}


def _register_and_login(
    client: TestClient, *, email: str = "addie@example.com"
) -> dict[str, Any]:
    account = register(client, email=email)
    login(client, email=email)
    return account


def _second_account_client(
    app: FastAPI, *, email: str = "bea@example.com"
) -> TestClient:
    """A second `TestClient` against the same app, registered and logged in
    as a different Account - a fresh cookie jar so the first Account's
    session is never reused (Story 14/15's Account-scoping tests)."""
    other = TestClient(app)
    _register_and_login(other, email=email)
    return other


# --- Story 1/2/3/8/9/10: create ----------------------------------------


def test_create_truck_minimal_fields(client: TestClient) -> None:
    _register_and_login(client)

    response = client.post("/trucks", json=TRUCK_PAYLOAD)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["gvwr"] == TRUCK_PAYLOAD["gvwr"]
    assert body["front_gawr"] == TRUCK_PAYLOAD["front_gawr"]
    assert body["rear_gawr"] == TRUCK_PAYLOAD["rear_gawr"]
    assert body["gcwr"] is None
    # Story 4: no Nickname given -> default display name from the ID.
    assert body["nickname"] == f"Truck {body['id']}"


def test_create_truck_with_gcwr_and_nickname(client: TestClient) -> None:
    _register_and_login(client)

    response = client.post(
        "/trucks", json={**TRUCK_PAYLOAD, "gcwr": 20000.0, "nickname": "Big Blue"}
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["gcwr"] == 20000.0
    assert body["nickname"] == "Big Blue"


def test_create_trailer_minimal_fields(client: TestClient) -> None:
    _register_and_login(client)

    response = client.post("/trailers", json=TRAILER_PAYLOAD)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["gvwr"] == TRAILER_PAYLOAD["gvwr"]
    assert body["gawr"] == TRAILER_PAYLOAD["gawr"]
    assert body["axle_count"] == TRAILER_PAYLOAD["axle_count"]
    assert body["uvw"] is None
    assert body["nickname"] == f"Trailer {body['id']}"


def test_create_trailer_with_uvw_and_nickname(client: TestClient) -> None:
    _register_and_login(client)

    response = client.post(
        "/trailers", json={**TRAILER_PAYLOAD, "uvw": 6000.0, "nickname": "Goose"}
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["uvw"] == 6000.0
    assert body["nickname"] == "Goose"


# --- Story 17: validation errors ----------------------------------------


def test_create_truck_negative_gvwr_fails_validation(client: TestClient) -> None:
    _register_and_login(client)

    response = client.post("/trucks", json={**TRUCK_PAYLOAD, "gvwr": -1})

    assert response.status_code == 422


def test_create_truck_missing_required_field_fails_validation(
    client: TestClient,
) -> None:
    _register_and_login(client)

    response = client.post("/trucks", json={"gvwr": 10000.0, "front_gawr": 4500.0})

    assert response.status_code == 422


def test_create_truck_non_numeric_rating_fails_validation(client: TestClient) -> None:
    _register_and_login(client)

    response = client.post("/trucks", json={**TRUCK_PAYLOAD, "gvwr": "not-a-number"})

    assert response.status_code == 422


def test_create_trailer_negative_axle_count_fails_validation(
    client: TestClient,
) -> None:
    _register_and_login(client)

    response = client.post("/trailers", json={**TRAILER_PAYLOAD, "axle_count": 0})

    assert response.status_code == 422


# --- Story 16: unauthenticated access -----------------------------------


def test_unauthenticated_create_truck_is_rejected(client: TestClient) -> None:
    response = client.post("/trucks", json=TRUCK_PAYLOAD)
    assert response.status_code == 401


def test_unauthenticated_list_trucks_is_rejected(client: TestClient) -> None:
    response = client.get("/trucks")
    assert response.status_code == 401


def test_unauthenticated_update_truck_is_rejected(client: TestClient) -> None:
    response = client.patch("/trucks/1", json={"nickname": "Nope"})
    assert response.status_code == 401


def test_unauthenticated_delete_truck_is_rejected(client: TestClient) -> None:
    response = client.delete("/trucks/1")
    assert response.status_code == 401


def test_unauthenticated_trailer_routes_are_rejected(client: TestClient) -> None:
    assert client.post("/trailers", json=TRAILER_PAYLOAD).status_code == 401
    assert client.get("/trailers").status_code == 401
    assert client.patch("/trailers/1", json={"nickname": "Nope"}).status_code == 401
    assert client.delete("/trailers/1").status_code == 401


# --- Story 5/11: list -----------------------------------------------------


def test_list_trucks_returns_only_own_profiles(client: TestClient) -> None:
    _register_and_login(client)
    client.post("/trucks", json=TRUCK_PAYLOAD)
    client.post("/trucks", json={**TRUCK_PAYLOAD, "nickname": "Second"})

    response = client.get("/trucks")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2


def test_list_trailers_empty_for_new_account(client: TestClient) -> None:
    _register_and_login(client)

    response = client.get("/trailers")

    assert response.status_code == 200
    assert response.json() == []


# --- Story 6/12: edit -----------------------------------------------------


def test_patch_truck_updates_nickname_only(client: TestClient) -> None:
    _register_and_login(client)
    created = client.post("/trucks", json=TRUCK_PAYLOAD).json()

    response = client.patch(f"/trucks/{created['id']}", json={"nickname": "Renamed"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["nickname"] == "Renamed"
    assert body["gvwr"] == TRUCK_PAYLOAD["gvwr"]


def test_patch_truck_updates_gcwr_and_ratings(client: TestClient) -> None:
    _register_and_login(client)
    created = client.post("/trucks", json=TRUCK_PAYLOAD).json()

    response = client.patch(
        f"/trucks/{created['id']}", json={"gcwr": 22000.0, "gvwr": 11000.0}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["gcwr"] == 22000.0
    assert body["gvwr"] == 11000.0


def test_patch_truck_can_clear_nickname_back_to_default(client: TestClient) -> None:
    _register_and_login(client)
    created = client.post("/trucks", json={**TRUCK_PAYLOAD, "nickname": "Temp"}).json()

    response = client.patch(f"/trucks/{created['id']}", json={"nickname": None})

    assert response.status_code == 200, response.text
    assert response.json()["nickname"] == f"Truck {created['id']}"


def test_patch_truck_explicit_null_gvwr_fails_validation(client: TestClient) -> None:
    _register_and_login(client)
    created = client.post("/trucks", json=TRUCK_PAYLOAD).json()

    response = client.patch(f"/trucks/{created['id']}", json={"gvwr": None})

    assert response.status_code == 422


def test_patch_trailer_updates_axle_count(client: TestClient) -> None:
    _register_and_login(client)
    created = client.post("/trailers", json=TRAILER_PAYLOAD).json()

    response = client.patch(f"/trailers/{created['id']}", json={"axle_count": 3})

    assert response.status_code == 200, response.text
    assert response.json()["axle_count"] == 3


def test_patch_nonexistent_truck_returns_404(client: TestClient) -> None:
    _register_and_login(client)

    response = client.patch("/trucks/999999", json={"nickname": "Ghost"})

    assert response.status_code == 404


def test_patch_truck_with_no_fields_returns_current_row_unchanged(
    client: TestClient,
) -> None:
    """An empty PATCH body still round-trips the current row (rather than
    issuing a no-op `UPDATE ... SET`, invalid SQL with an empty `SET`
    clause - see `truck_profiles.update_truck_profile`'s docstring), so a
    caller gets the same 200-with-current-row response either way."""
    _register_and_login(client)
    created = client.post("/trucks", json=TRUCK_PAYLOAD).json()

    response = client.patch(f"/trucks/{created['id']}", json={})

    assert response.status_code == 200, response.text
    assert response.json() == created


# --- Story 7/13: delete ---------------------------------------------------


def test_delete_truck_removes_it(client: TestClient) -> None:
    _register_and_login(client)
    created = client.post("/trucks", json=TRUCK_PAYLOAD).json()

    delete_response = client.delete(f"/trucks/{created['id']}")
    assert delete_response.status_code == 204

    list_response = client.get("/trucks")
    assert list_response.json() == []


def test_delete_nonexistent_trailer_returns_404(client: TestClient) -> None:
    _register_and_login(client)

    response = client.delete("/trailers/999999")

    assert response.status_code == 404


# --- Story 14/15: Account-scoping, 404 not 403 for another Account -------


def test_second_account_cannot_see_first_accounts_trucks(
    client: TestClient, app: FastAPI
) -> None:
    _register_and_login(client, email="addie@example.com")
    client.post("/trucks", json=TRUCK_PAYLOAD)

    other_client = _second_account_client(app)

    response = other_client.get("/trucks")
    assert response.status_code == 200
    assert response.json() == []


def test_second_account_cannot_edit_first_accounts_truck(
    client: TestClient, app: FastAPI
) -> None:
    _register_and_login(client, email="addie@example.com")
    created = client.post("/trucks", json=TRUCK_PAYLOAD).json()

    other_client = _second_account_client(app)

    response = other_client.patch(
        f"/trucks/{created['id']}", json={"nickname": "Hijacked"}
    )
    assert response.status_code == 404


def test_second_account_cannot_delete_first_accounts_truck(
    client: TestClient, app: FastAPI
) -> None:
    _register_and_login(client, email="addie@example.com")
    created = client.post("/trucks", json=TRUCK_PAYLOAD).json()

    other_client = _second_account_client(app)

    response = other_client.delete(f"/trucks/{created['id']}")
    assert response.status_code == 404

    # The original owner can still see it - it was never actually deleted.
    still_there = client.get("/trucks").json()
    assert len(still_there) == 1
    assert still_there[0]["id"] == created["id"]


def test_second_account_cannot_see_first_accounts_trailers(
    client: TestClient, app: FastAPI
) -> None:
    _register_and_login(client, email="addie@example.com")
    client.post("/trailers", json=TRAILER_PAYLOAD)

    other_client = _second_account_client(app)

    response = other_client.get("/trailers")
    assert response.status_code == 200
    assert response.json() == []


def test_second_account_cannot_delete_first_accounts_trailer(
    client: TestClient, app: FastAPI
) -> None:
    _register_and_login(client, email="addie@example.com")
    created = client.post("/trailers", json=TRAILER_PAYLOAD).json()

    other_client = _second_account_client(app)

    response = other_client.delete(f"/trailers/{created['id']}")
    assert response.status_code == 404
