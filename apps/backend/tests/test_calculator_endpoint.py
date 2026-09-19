"""HTTP-level tests for `POST /api/evaluate` (issue #38).

Unlike every other route in `apps/backend`, this one is deliberately
unauthenticated - the free calculator has to stay anonymous per ADR 0013 -
so its abuse mitigation is a per-IP rate limit (slowapi) rather than a
session-auth gate. The canned rig scenario below is reused verbatim from
`packages/towing-core/tests/test_evaluation.py::test_evaluate_weigh_event_folds_each_check`
so the expected FAIL/PASS/NEAR_LIMIT buckets are already independently
verified at the compute layer, not re-derived here.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

VALID_PAYLOAD: dict[str, Any] = {
    "truck": {"gvwr": 14000, "front_gawr": 6000, "rear_gawr": 9900, "gcwr": 32500},
    "trailer": {"gvwr": 23500, "gawr": 8000, "axle_count": 3, "uvw": 20554},
    "combined": {"steer": 5000, "drive": 10000, "trailer_axle": 19000, "gross": 33000},
    "solo": {"steer": 5000, "drive": 4580, "gross": 9580},
    "time_gap_hours": None,
}


def test_evaluate_returns_expected_statuses_for_a_known_rig(client: TestClient) -> None:
    response = client.post("/api/evaluate", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "fail"
    by_label = {check["label"]: check["status"] for check in body["checks"]}
    assert by_label["Drive Axle"] == "fail"
    assert by_label["Steer Axle"] == "pass"
    assert by_label["GCWR"] == "fail"
    assert by_label["Trailer GVWR"] == "near_limit"
    assert body["disclaimer"]


def test_evaluate_requires_no_session_cookie(client: TestClient) -> None:
    # No login step anywhere in this test - the calculator must stay
    # reachable by a fully anonymous visitor (ADR 0013).
    response = client.post("/api/evaluate", json=VALID_PAYLOAD)

    assert response.status_code == 200


def test_evaluate_without_solo_leaves_trailer_gvwr_and_time_gap_unset(
    client: TestClient,
) -> None:
    payload = {**VALID_PAYLOAD, "solo": None, "time_gap_hours": None}

    response = client.post("/api/evaluate", json=payload)

    assert response.status_code == 200
    body = response.json()
    by_label = {check["label"]: check["status"] for check in body["checks"]}
    assert by_label["Trailer GVWR"] == "not_evaluated"
    assert body["time_gap_hours"] is None


def test_evaluate_rejects_malformed_payload(client: TestClient) -> None:
    response = client.post("/api/evaluate", json={"truck": {"gvwr": "not-a-number"}})

    assert response.status_code == 422


def test_evaluate_rejects_non_positive_ratings(client: TestClient) -> None:
    # Matches towing_backend.schemas.TruckIn/TrailerIn's own `gt=0`
    # convention - this route has no session-auth layer behind it the way
    # every other one does, so boundary validation carries more weight here.
    payload = {**VALID_PAYLOAD, "truck": {**VALID_PAYLOAD["truck"], "gvwr": 0}}

    response = client.post("/api/evaluate", json=payload)

    assert response.status_code == 422


def test_evaluate_is_rate_limited_past_its_threshold(client: TestClient) -> None:
    # The route's own limit is 30/minute (see towing_backend.calculator) -
    # drive past it and confirm the 31st request in the same window is
    # rejected, not silently served.
    statuses = [
        client.post("/api/evaluate", json=VALID_PAYLOAD).status_code for _ in range(31)
    ]

    assert statuses[:30] == [200] * 30
    assert statuses[30] == 429


def test_evaluate_rate_limit_is_keyed_by_forwarded_for_not_shared_globally(
    client: TestClient,
) -> None:
    # Issue #38 fix: apps/backend deploys behind Render's reverse proxy
    # (ADR 0016), which terminates TLS and forwards every request over
    # HTTP - `request.client.host` is Render's own proxy address for every
    # visitor there, not the real caller's IP. Keying the limiter on that
    # would collapse the per-IP limit into one shared bucket for the whole
    # site. This drives one simulated visitor past the limit, then confirms
    # a *different* X-Forwarded-For value still gets served - proving the
    # limiter is actually keyed per-client, not globally.
    for _ in range(30):
        response = client.post(
            "/api/evaluate",
            json=VALID_PAYLOAD,
            headers={"X-Forwarded-For": "203.0.113.1"},
        )
        assert response.status_code == 200

    exhausted = client.post(
        "/api/evaluate", json=VALID_PAYLOAD, headers={"X-Forwarded-For": "203.0.113.1"}
    )
    assert exhausted.status_code == 429

    other_visitor = client.post(
        "/api/evaluate", json=VALID_PAYLOAD, headers={"X-Forwarded-For": "203.0.113.2"}
    )
    assert other_visitor.status_code == 200
