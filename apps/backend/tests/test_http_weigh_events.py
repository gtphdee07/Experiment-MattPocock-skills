"""Tier 1 (HTTP-level, offline): drives Weigh Event creation and history
through `fastapi.testclient.TestClient` (issue #21), reusing #18's
register+login helper and #19's create-Profile payloads as test setup
(Testing Decisions), rather than re-deriving them.

Every test gets its own fresh SQLite file (the `client`/`settings` fixtures
in conftest.py) - no mock ever stands in for the database, and the
synchronous `weigh_events` store (`towing_backend.sync_db`) points at that
same file.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_http_auth_flow import login, register
from test_http_truck_trailer_profiles import TRAILER_PAYLOAD, TRUCK_PAYLOAD


def _register_and_login(
    client: TestClient, *, email: str = "addie@example.com"
) -> dict[str, Any]:
    account = register(client, email=email)
    login(client, email=email)
    return account


def _second_account_client(
    app: FastAPI, *, email: str = "bea@example.com"
) -> TestClient:
    other = TestClient(app)
    _register_and_login(other, email=email)
    return other


def _create_truck(client: TestClient, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = client.post(
        "/trucks", json={**TRUCK_PAYLOAD, **overrides}
    ).json()
    return body


def _create_trailer(client: TestClient, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = client.post(
        "/trailers", json={**TRAILER_PAYLOAD, **overrides}
    ).json()
    return body


# A Combined Ticket comfortably within every rating on `TRUCK_PAYLOAD`/
# `TRAILER_PAYLOAD` (hitched actual == GVWR exactly, at the not-overloaded
# boundary; trailer axle group rating is 3500 * 2 = 7000).
BASE_COMBINED = {
    "steer": 4000.0,
    "drive": 6000.0,
    "trailer_axle": 6500.0,
    "gross": 16000.0,
}


def _checks_by_label(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {check["label"]: check for check in body["checks"]}


def _create_weigh_event(
    client: TestClient,
    *,
    truck_id: int,
    trailer_id: int,
    combined: dict[str, Any] | None = None,
    solo: dict[str, Any] | None = None,
    confirm_solo_link: bool = False,
) -> Any:
    return client.post(
        "/weigh-events",
        json={
            "truck_id": truck_id,
            "trailer_id": trailer_id,
            "combined": combined if combined is not None else BASE_COMBINED,
            "solo": solo,
            "confirm_solo_link": confirm_solo_link,
        },
    )


# --- Story 17: unauthenticated access -----------------------------------


def test_unauthenticated_weigh_event_routes_are_rejected(client: TestClient) -> None:
    assert (
        client.post(
            "/weigh-events",
            json={"truck_id": 1, "trailer_id": 1, "combined": BASE_COMBINED},
        ).status_code
        == 401
    )
    assert client.get("/weigh-events").status_code == 401
    assert client.get("/trucks/1/reusable-solo-ticket").status_code == 401


# --- Story 16: Truck/Trailer ownership -----------------------------------


def test_create_weigh_event_truck_not_owned_returns_404(client: TestClient) -> None:
    _register_and_login(client)
    trailer = _create_trailer(client)

    response = _create_weigh_event(client, truck_id=999999, trailer_id=trailer["id"])

    assert response.status_code == 404


def test_create_weigh_event_trailer_not_owned_returns_404(client: TestClient) -> None:
    _register_and_login(client)
    truck = _create_truck(client)

    response = _create_weigh_event(client, truck_id=truck["id"], trailer_id=999999)

    assert response.status_code == 404


def test_second_account_cannot_weigh_first_accounts_truck(
    client: TestClient, app: FastAPI
) -> None:
    _register_and_login(client, email="addie@example.com")
    truck = _create_truck(client)
    trailer = _create_trailer(client)

    other_client = _second_account_client(app)
    other_trailer = _create_trailer(other_client)

    response = _create_weigh_event(
        other_client, truck_id=truck["id"], trailer_id=other_trailer["id"]
    )
    assert response.status_code == 404

    # Sanity: the caller's own Profiles still work together fine.
    own_response = _create_weigh_event(
        client, truck_id=truck["id"], trailer_id=trailer["id"]
    )
    assert own_response.status_code == 201, own_response.text


def test_second_account_cannot_see_first_accounts_reusable_solo_ticket(
    client: TestClient, app: FastAPI
) -> None:
    _register_and_login(client, email="addie@example.com")
    truck = _create_truck(client)

    other_client = _second_account_client(app)

    response = other_client.get(f"/trucks/{truck['id']}/reusable-solo-ticket")
    assert response.status_code == 404


# --- Story 20: validation errors -----------------------------------------


def test_create_weigh_event_negative_weight_fails_validation(
    client: TestClient,
) -> None:
    _register_and_login(client)
    truck = _create_truck(client)
    trailer = _create_trailer(client)

    response = _create_weigh_event(
        client,
        truck_id=truck["id"],
        trailer_id=trailer["id"],
        combined={**BASE_COMBINED, "steer": -1},
    )

    assert response.status_code == 422


def test_create_weigh_event_missing_required_field_fails_validation(
    client: TestClient,
) -> None:
    _register_and_login(client)
    truck = _create_truck(client)
    trailer = _create_trailer(client)

    response = client.post(
        "/weigh-events",
        json={
            "truck_id": truck["id"],
            "trailer_id": trailer["id"],
            "combined": {"steer": 4000.0, "drive": 6000.0, "trailer_axle": 6500.0},
        },
    )

    assert response.status_code == 422


# --- Stories 2/3/5: checks, GCWR/Trailer GVWR not-evaluated ---------------


def test_create_weigh_event_no_solo_ticket_not_evaluates_gcwr_and_trailer_gvwr(
    client: TestClient,
) -> None:
    _register_and_login(client)
    truck = _create_truck(client)
    trailer = _create_trailer(client)

    response = _create_weigh_event(
        client, truck_id=truck["id"], trailer_id=trailer["id"]
    )

    assert response.status_code == 201, response.text
    body = response.json()
    checks = _checks_by_label(body)
    assert checks["GCWR"]["status"] == "not_evaluated"
    assert checks["Trailer GVWR"]["status"] == "not_evaluated"
    # NOT_EVALUATED outranks PASS in the overall-status precedence (FAIL >
    # NEAR_LIMIT > NOT_EVALUATED > PASS - see `RigEvaluation.overall_status`).
    assert body["overall_status"] == "not_evaluated"
    assert body["time_gap_hours"] is None
    assert "id" in body and isinstance(body["id"], int)
    assert body["timestamp"]


def test_create_weigh_event_with_gcwr_evaluates_as_unverified(
    client: TestClient,
) -> None:
    _register_and_login(client)
    truck = _create_truck(client, gcwr=20000.0)
    trailer = _create_trailer(client)

    response = _create_weigh_event(
        client, truck_id=truck["id"], trailer_id=trailer["id"]
    )

    assert response.status_code == 201, response.text
    gcwr_check = _checks_by_label(response.json())["GCWR"]
    assert gcwr_check["status"] == "pass"
    assert gcwr_check["actual"] == BASE_COMBINED["gross"]
    assert gcwr_check["rating"] == 20000.0
    assert gcwr_check["note"] is not None
    assert "Unverified Value" in gcwr_check["note"]


# --- Story 15: Nickname snapshot -------------------------------------------


def test_create_weigh_event_snapshots_nicknames(client: TestClient) -> None:
    _register_and_login(client)
    truck = _create_truck(client, nickname="Big Blue")
    trailer = _create_trailer(client, nickname="Goose")

    response = _create_weigh_event(
        client, truck_id=truck["id"], trailer_id=trailer["id"]
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["truck_nickname"] == "Big Blue"
    assert body["trailer_nickname"] == "Goose"


# --- Stories 6/7/8: Solo Ticket linking ------------------------------------


def test_reusable_solo_ticket_returns_null_when_no_history(client: TestClient) -> None:
    _register_and_login(client)
    truck = _create_truck(client)

    response = client.get(f"/trucks/{truck['id']}/reusable-solo-ticket")

    assert response.status_code == 200
    assert response.json() is None


def test_create_weigh_event_fresh_solo_auto_linked_by_matching_reference(
    client: TestClient,
) -> None:
    _register_and_login(client)
    truck = _create_truck(client)
    trailer = _create_trailer(client)

    response = _create_weigh_event(
        client,
        truck_id=truck["id"],
        trailer_id=trailer["id"],
        combined={**BASE_COMBINED, "reweigh_reference": " ABC-123 "},
        solo={
            "kind": "fresh",
            "steer": 4000.0,
            "drive": 5000.0,
            "gross": 9000.0,
            "reweigh_reference": "abc-123",
            "time_gap_hours": 1.0,
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    trailer_gvwr = _checks_by_label(body)["Trailer GVWR"]
    assert trailer_gvwr["status"] != "not_evaluated"
    assert trailer_gvwr["actual"] == BASE_COMBINED["gross"] - 9000.0
    assert trailer_gvwr["note"] is None
    assert body["time_gap_hours"] == 1.0
    assert body["time_gap_exceeds_threshold"] is False


def test_create_weigh_event_fresh_solo_mismatched_without_confirm_returns_409(
    client: TestClient,
) -> None:
    _register_and_login(client)
    truck = _create_truck(client)
    trailer = _create_trailer(client)

    response = _create_weigh_event(
        client,
        truck_id=truck["id"],
        trailer_id=trailer["id"],
        combined={**BASE_COMBINED, "reweigh_reference": "ABC-1"},
        solo={
            "kind": "fresh",
            "steer": 4000.0,
            "drive": 5000.0,
            "gross": 9000.0,
            "reweigh_reference": "XYZ-2",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {"reason": "solo_link_unconfirmed"}

    # Nothing was persisted.
    history = client.get("/weigh-events")
    assert history.json() == []


def test_create_weigh_event_fresh_solo_mismatched_with_confirm_links(
    client: TestClient,
) -> None:
    _register_and_login(client)
    truck = _create_truck(client)
    trailer = _create_trailer(client)

    response = _create_weigh_event(
        client,
        truck_id=truck["id"],
        trailer_id=trailer["id"],
        combined={**BASE_COMBINED, "reweigh_reference": "ABC-1"},
        solo={
            "kind": "fresh",
            "steer": 4000.0,
            "drive": 5000.0,
            "gross": 9000.0,
            "reweigh_reference": "XYZ-2",
        },
        confirm_solo_link=True,
    )

    assert response.status_code == 201, response.text
    trailer_gvwr = _checks_by_label(response.json())["Trailer GVWR"]
    assert trailer_gvwr["status"] != "not_evaluated"


def test_create_weigh_event_fresh_solo_near_limit_trusted_margin(
    client: TestClient,
) -> None:
    """ADR 0006: a trusted (fresh) reading is Near Limit within 100 lbs
    under the Trailer's GVWR (8000 here)."""
    _register_and_login(client)
    truck = _create_truck(client)
    trailer = _create_trailer(client)

    # Derived Trailer Weight = 16000 - 8050 = 7950; 8000 - 7950 = 50 <= 100.
    response = _create_weigh_event(
        client,
        truck_id=truck["id"],
        trailer_id=trailer["id"],
        solo={"kind": "fresh", "steer": 4000.0, "drive": 4000.0, "gross": 8050.0},
        confirm_solo_link=True,
    )

    assert response.status_code == 201, response.text
    trailer_gvwr = _checks_by_label(response.json())["Trailer GVWR"]
    assert trailer_gvwr["status"] == "near_limit"
    assert trailer_gvwr["note"] is None


# --- Stories 10/11/12/13/14: Reused Solo Weight ----------------------------


def test_create_weigh_event_reused_solo_unchanged_is_not_unverified(
    client: TestClient,
) -> None:
    _register_and_login(client)
    truck = _create_truck(client)
    trailer = _create_trailer(client)

    first = _create_weigh_event(
        client,
        truck_id=truck["id"],
        trailer_id=trailer["id"],
        solo={"kind": "fresh", "steer": 4000.0, "drive": 5000.0, "gross": 9000.0},
        confirm_solo_link=True,
    )
    assert first.status_code == 201, first.text

    reusable = client.get(f"/trucks/{truck['id']}/reusable-solo-ticket")
    assert reusable.status_code == 200
    reusable_body = reusable.json()
    assert reusable_body == {
        "gross": 9000.0,
        "from_timestamp": first.json()["timestamp"],
    }

    second = _create_weigh_event(
        client,
        truck_id=truck["id"],
        trailer_id=trailer["id"],
        solo={
            "kind": "reused",
            "from_timestamp": reusable_body["from_timestamp"],
            "gross": reusable_body["gross"],
            "adjusted": False,
        },
    )

    assert second.status_code == 201, second.text
    trailer_gvwr = _checks_by_label(second.json())["Trailer GVWR"]
    assert trailer_gvwr["status"] != "not_evaluated"
    assert trailer_gvwr["note"] is None
    # No fresh weighing happened, so no Time-Gap Warning either.
    assert second.json()["time_gap_hours"] is None


def test_create_weigh_event_reused_solo_adjusted_is_unverified_with_wider_margin(
    client: TestClient,
) -> None:
    """ADR 0006: an Unverified (adjusted) reused reading gets the wider
    300 lb margin - Near Limit here even though 250 lbs under would *not*
    be Near Limit for a trusted (100 lb margin) reading."""
    _register_and_login(client)
    truck = _create_truck(client)
    trailer = _create_trailer(client)

    first = _create_weigh_event(
        client,
        truck_id=truck["id"],
        trailer_id=trailer["id"],
        solo={"kind": "fresh", "steer": 4000.0, "drive": 5000.0, "gross": 9000.0},
        confirm_solo_link=True,
    )
    assert first.status_code == 201, first.text
    reusable_body = client.get(f"/trucks/{truck['id']}/reusable-solo-ticket").json()

    # Adjusted Gross Weight -> Derived Trailer Weight = 16000 - 8250 = 7750;
    # 8000 - 7750 = 250, within the 300 lb Unverified-Value margin (but
    # would NOT be within the 100 lb trusted margin).
    second = _create_weigh_event(
        client,
        truck_id=truck["id"],
        trailer_id=trailer["id"],
        solo={
            "kind": "reused",
            "from_timestamp": reusable_body["from_timestamp"],
            "gross": 8250.0,
            "adjusted": True,
        },
    )

    assert second.status_code == 201, second.text
    trailer_gvwr = _checks_by_label(second.json())["Trailer GVWR"]
    assert trailer_gvwr["status"] == "near_limit"
    assert trailer_gvwr["note"] is not None
    assert "Unverified Value" in trailer_gvwr["note"]


def test_create_weigh_event_reused_solo_overloaded_never_near_limit(
    client: TestClient,
) -> None:
    """ADR 0006: the Near-Limit flag never fires when actually overloaded,
    even though the margin would otherwise apply."""
    _register_and_login(client)
    truck = _create_truck(client)
    trailer = _create_trailer(client)

    first = _create_weigh_event(
        client,
        truck_id=truck["id"],
        trailer_id=trailer["id"],
        solo={"kind": "fresh", "steer": 4000.0, "drive": 5000.0, "gross": 9000.0},
        confirm_solo_link=True,
    )
    assert first.status_code == 201, first.text
    reusable_body = client.get(f"/trucks/{truck['id']}/reusable-solo-ticket").json()

    # Derived Trailer Weight = 16000 - 7900 = 8100 > 8000 -> overloaded.
    second = _create_weigh_event(
        client,
        truck_id=truck["id"],
        trailer_id=trailer["id"],
        solo={
            "kind": "reused",
            "from_timestamp": reusable_body["from_timestamp"],
            "gross": 7900.0,
            "adjusted": True,
        },
    )

    assert second.status_code == 201, second.text
    trailer_gvwr = _checks_by_label(second.json())["Trailer GVWR"]
    assert trailer_gvwr["status"] == "fail"


def test_reusable_solo_ticket_for_unknown_truck_returns_404(client: TestClient) -> None:
    _register_and_login(client)

    response = client.get("/trucks/999999/reusable-solo-ticket")

    assert response.status_code == 404


def test_create_weigh_event_reused_solo_unknown_timestamp_returns_404(
    client: TestClient,
) -> None:
    _register_and_login(client)
    truck = _create_truck(client)
    trailer = _create_trailer(client)

    response = _create_weigh_event(
        client,
        truck_id=truck["id"],
        trailer_id=trailer["id"],
        solo={
            "kind": "reused",
            "from_timestamp": "2020-01-01T00:00:00+00:00",
            "gross": 9000.0,
            "adjusted": False,
        },
    )

    assert response.status_code == 404


# --- Stories 18/19: history, newest-first, pagination ----------------------


def test_weigh_event_history_returns_newest_first(client: TestClient) -> None:
    _register_and_login(client)
    truck = _create_truck(client)
    trailer = _create_trailer(client)

    first = _create_weigh_event(client, truck_id=truck["id"], trailer_id=trailer["id"])
    second = _create_weigh_event(client, truck_id=truck["id"], trailer_id=trailer["id"])
    third = _create_weigh_event(client, truck_id=truck["id"], trailer_id=trailer["id"])
    for response in (first, second, third):
        assert response.status_code == 201, response.text

    history = client.get("/weigh-events")

    assert history.status_code == 200
    ids = [entry["id"] for entry in history.json()]
    assert ids == [third.json()["id"], second.json()["id"], first.json()["id"]]


def test_weigh_event_history_pagination(client: TestClient) -> None:
    _register_and_login(client)
    truck = _create_truck(client)
    trailer = _create_trailer(client)

    created = [
        _create_weigh_event(client, truck_id=truck["id"], trailer_id=trailer["id"])
        for _ in range(5)
    ]
    created_ids = [response.json()["id"] for response in created]

    page1 = client.get("/weigh-events", params={"limit": 2, "offset": 0})
    page2 = client.get("/weigh-events", params={"limit": 2, "offset": 2})

    assert [entry["id"] for entry in page1.json()] == list(reversed(created_ids))[0:2]
    assert [entry["id"] for entry in page2.json()] == list(reversed(created_ids))[2:4]


def test_weigh_event_history_only_returns_own_garage(
    client: TestClient, app: FastAPI
) -> None:
    _register_and_login(client, email="addie@example.com")
    truck = _create_truck(client)
    trailer = _create_trailer(client)
    _create_weigh_event(client, truck_id=truck["id"], trailer_id=trailer["id"])

    other_client = _second_account_client(app)

    response = other_client.get("/weigh-events")
    assert response.status_code == 200
    assert response.json() == []
