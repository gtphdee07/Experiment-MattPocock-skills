"""Tier 2 (real-Anthropic HTTP-level contract bench, `test_real_*`, excluded
from `-k "not real"`): the four photo-OCR/axle-count-lookup endpoints
(issue #20), called through `TestClient` with the *real* adapters wired in
(`PhotoOCRDependencies()`'s own defaults - no fakes), against the same
golden fixture photos and expected values
`packages/towing-app/tests/test_real_photo_smoke.py` /
`test_real_trailer_photo_smoke.py` / `test_real_scale_ticket_photo_smoke.py`
already use.

This proves the whole path - HTTP boundary -> adapter -> real Anthropic API
-> response shaping - matches those lower-level adapter tests' results, not
just that the adapter itself still works (issue #20 Testing Decisions,
Story 13).

Skipped unless `ANTHROPIC_API_KEY` is set, exactly like the adapter-level
real-photo smoke tests it mirrors - this makes real network calls and costs
real API usage, so it never runs as part of the default hermetic suite.
Currently blocked by exhausted Anthropic Console API credit (same known,
separate issue the adapter-level real tests are already blocked by) - not
something this spec fixes.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from towing_backend.app import create_app
from towing_backend.settings import Settings

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="requires a real ANTHROPIC_API_KEY - opt-in only, makes a real API call",
)

FIXTURES_DIR = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "towing-app"
    / "tests"
    / "fixtures"
)
TRUCK_TAG_FIXTURE = FIXTURES_DIR / "truck_tag_ford_f450.jpg"
TRAILER_TAG_FIXTURE = FIXTURES_DIR / "trailer_tag_goose.jpg"
COMBINED_TICKET_FIXTURE = FIXTURES_DIR / "cat_ticket_combined.jpg"
SOLO_TICKET_FIXTURE = FIXTURES_DIR / "cat_ticket_solo.jpg"

# Ground truth - see the towing-app real-photo smoke tests this mirrors.
GOLDEN_TRUCK_GVWR = 14000.0
GOLDEN_TRUCK_FRONT_GAWR = 6000.0
GOLDEN_TRUCK_REAR_GAWR = 9900.0

GOLDEN_TRAILER_GVWR = 23500.0
GOLDEN_TRAILER_GAWR = 8000.0
GOLDEN_TRAILER_UVW = 20554.0

COMBINED_GOLDEN_STEER = 5640.0
COMBINED_GOLDEN_DRIVE = 9080.0
COMBINED_GOLDEN_TRAILER_AXLE = 19680.0
COMBINED_GOLDEN_GROSS = 34400.0

SOLO_GOLDEN_STEER = 5560.0
SOLO_GOLDEN_DRIVE = 4420.0
SOLO_GOLDEN_GROSS = 9980.0

EMAIL = "addie@example.com"
PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'backend.db'}",
        cors_origin="http://localhost:5173",
        secret="test-secret",
    )
    app: FastAPI = create_app(settings)
    with TestClient(app) as test_client:
        register_response = test_client.post(
            "/auth/register", json={"email": EMAIL, "password": PASSWORD}
        )
        assert register_response.status_code == 201, register_response.text
        login_response = test_client.post(
            "/auth/login", data={"username": EMAIL, "password": PASSWORD}
        )
        assert login_response.status_code == 204, login_response.text
        yield test_client


def test_real_trucks_from_photo_matches_golden_truck_tag_fields(
    client: TestClient,
) -> None:
    with TRUCK_TAG_FIXTURE.open("rb") as photo:
        response = client.post(
            "/trucks/from-photo",
            files={"file": ("truck_tag_ford_f450.jpg", photo, "image/jpeg")},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["gvwr"] == GOLDEN_TRUCK_GVWR
    assert body["front_gawr"] == GOLDEN_TRUCK_FRONT_GAWR
    assert body["rear_gawr"] == GOLDEN_TRUCK_REAR_GAWR


def test_real_trailers_from_photo_matches_golden_trailer_tag_fields(
    client: TestClient,
) -> None:
    with TRAILER_TAG_FIXTURE.open("rb") as photo:
        response = client.post(
            "/trailers/from-photo",
            files={"file": ("trailer_tag_goose.jpg", photo, "image/jpeg")},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["gvwr"] == GOLDEN_TRAILER_GVWR
    assert body["gawr"] == GOLDEN_TRAILER_GAWR
    assert body["uvw"] == GOLDEN_TRAILER_UVW


def test_real_axle_count_lookup_returns_a_plausible_value(
    client: TestClient,
) -> None:
    response = client.get(
        "/trailers/axle-count-lookup",
        params={"make": "Grand Design", "model": "Reflection 315RLTS"},
    )

    assert response.status_code == 200, response.text
    axle_count = response.json()["axle_count"]
    # Loose on purpose: this is a live web-search lookup, not a fixture -
    # `packages/towing-app` has no golden real-lookup value to mirror
    # either (only fake-based unit coverage). Proves the HTTP path wires
    # through to a real answer shape, not an exact figure.
    assert axle_count is None or axle_count > 0


def test_real_tickets_from_photo_combined_matches_golden_fields(
    client: TestClient,
) -> None:
    with COMBINED_TICKET_FIXTURE.open("rb") as photo:
        response = client.post(
            "/tickets/from-photo",
            files={"file": ("cat_ticket_combined.jpg", photo, "image/jpeg")},
            data={"ticket_type": "combined"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["steer"] == COMBINED_GOLDEN_STEER
    assert body["drive"] == COMBINED_GOLDEN_DRIVE
    assert body["trailer_axle"] == COMBINED_GOLDEN_TRAILER_AXLE
    assert body["gross"] == COMBINED_GOLDEN_GROSS
    assert body["timestamp"] is not None
    assert "10:10" in body["timestamp"]
    assert body["reweigh_reference"] is not None
    assert "1327426192434" in body["reweigh_reference"]


def test_real_tickets_from_photo_solo_matches_golden_fields_and_omits_trailer_axle(
    client: TestClient,
) -> None:
    with SOLO_TICKET_FIXTURE.open("rb") as photo:
        response = client.post(
            "/tickets/from-photo",
            files={"file": ("cat_ticket_solo.jpg", photo, "image/jpeg")},
            data={"ticket_type": "solo"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["steer"] == SOLO_GOLDEN_STEER
    assert body["drive"] == SOLO_GOLDEN_DRIVE
    assert body["gross"] == SOLO_GOLDEN_GROSS
    assert body["trailer_axle"] is None
    assert body["timestamp"] is not None
    assert "15:50" in body["timestamp"]
    assert body["reweigh_reference"] is None
