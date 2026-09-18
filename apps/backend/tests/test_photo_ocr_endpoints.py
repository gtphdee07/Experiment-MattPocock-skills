"""Tier 1 (HTTP-level, offline): the four photo-OCR/axle-count-lookup
endpoints (issue #20), driven through `fastapi.testclient.TestClient` -
exactly `test_http_auth_flow.py`'s "drive the outermost interface" pattern.

Every `ClaudeVision*`/`WebAxleCountFieldSource` adapter is dependency-
injected as a fake (`PhotoOCRDependencies`, built via `create_app`) that
returns canned proposals or raises `FieldSourceUnavailableError` - never a
real network call, mirroring `packages/towing-app/tests/test_field_acquisition.py`'s
existing fake-based pattern per issue #20's own Testing Decisions.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from towing_backend.app import create_app
from towing_backend.photo_ocr import (
    MAX_UPLOAD_BYTES,
    PhotoOCRDependencies,
    _read_and_validate_photo,
)
from towing_backend.settings import Settings
from towing_core.field_acquisition import FieldSourceUnavailableError

EMAIL = "addie@example.com"
PASSWORD = "correct-horse-battery-staple"


class _FakeFieldSource:
    """Stands in for a `ClaudeVision*FieldSource` - returns canned values
    from a fixed dict, never touches the network."""

    def __init__(self, values: dict[str, float | None]) -> None:
        self._values = values

    def propose(self, field: str) -> float | None:
        return self._values.get(field)


class _FakeTextFieldSource:
    """Stands in for `ClaudeVisionScaleTicketFieldSource` - same shape as
    `_FakeFieldSource`, plus `propose_text` for the ticket's string fields.
    Fails loudly (`AssertionError`, not silently returning `None`) if
    `propose("trailer_axle")` is ever called when the fixture says it
    shouldn't be - the direct check for issue #20 Story 7 / ADR 0007's
    "never asked", not "asked and told no" behavior."""

    def __init__(
        self, values: dict[str, float | str | None], *, allow_trailer_axle: bool = True
    ) -> None:
        self._values = values
        self._allow_trailer_axle = allow_trailer_axle

    def propose(self, field: str) -> float | None:
        if field == "trailer_axle" and not self._allow_trailer_axle:
            raise AssertionError(
                "propose('trailer_axle') must never be called for a Solo "
                "Ticket - see ADR 0007"
            )
        value = self._values.get(field)
        return value if isinstance(value, int | float) else None

    def propose_text(self, field: str) -> str | None:
        value = self._values.get(field)
        return value if isinstance(value, str) else None


class _UnavailableFieldSource:
    """Stands in for any adapter whose underlying service call failed -
    every `propose`/`propose_text` call raises `FieldSourceUnavailableError`,
    matching what a real bad-credentials/network/rate-limit failure looks
    like from the adapter's side (ADR 0003)."""

    def propose(self, field: str) -> float | None:
        raise FieldSourceUnavailableError("service unavailable")

    def propose_text(self, field: str) -> str | None:
        raise FieldSourceUnavailableError("service unavailable")


def make_settings(db_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{db_path}",
        cors_origin="http://localhost:5173",
        secret="test-secret",
    )


def make_app(
    tmp_path: Path, dependencies: PhotoOCRDependencies
) -> tuple[FastAPI, Settings]:
    settings = make_settings(tmp_path / "backend.db")
    return create_app(settings, dependencies), settings


def register_and_login(client: TestClient) -> None:
    register_response = client.post(
        "/auth/register", json={"email": EMAIL, "password": PASSWORD}
    )
    assert register_response.status_code == 201, register_response.text
    login_response = client.post(
        "/auth/login", data={"username": EMAIL, "password": PASSWORD}
    )
    assert login_response.status_code == 204, login_response.text


@pytest.fixture
def client_factory(
    tmp_path: Path,
) -> Iterator[Any]:
    created: list[TestClient] = []

    def factory(dependencies: PhotoOCRDependencies) -> TestClient:
        app, _ = make_app(tmp_path, dependencies)
        test_client = TestClient(app)
        created.append(test_client)
        return test_client

    yield factory
    for test_client in created:
        test_client.close()


JPEG_FILE = ("tag.jpg", b"fake-image-bytes", "image/jpeg")


# --- POST /trucks/from-photo -------------------------------------------


def test_trucks_from_photo_returns_proposal_with_nulls_for_unreadable_fields(
    client_factory: Any,
) -> None:
    deps = PhotoOCRDependencies(
        truck_tag_source=lambda photo_path: _FakeFieldSource(
            {"gvwr": 14000.0, "front_gawr": None, "rear_gawr": 9900.0}
        )
    )
    client = client_factory(deps)
    register_and_login(client)

    response = client.post("/trucks/from-photo", files={"file": JPEG_FILE})

    assert response.status_code == 200, response.text
    assert response.json() == {"gvwr": 14000.0, "front_gawr": None, "rear_gawr": 9900.0}


def test_trucks_from_photo_requires_authentication(client_factory: Any) -> None:
    deps = PhotoOCRDependencies(
        truck_tag_source=lambda photo_path: _FakeFieldSource({"gvwr": 14000.0})
    )
    client = client_factory(deps)

    response = client.post("/trucks/from-photo", files={"file": JPEG_FILE})

    assert response.status_code == 401


def test_trucks_from_photo_rejects_unsupported_file_type(client_factory: Any) -> None:
    deps = PhotoOCRDependencies()
    client = client_factory(deps)
    register_and_login(client)

    response = client.post(
        "/trucks/from-photo",
        files={"file": ("tag.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 422

    error_response = client.post(
        "/trucks/from-photo",
        files={"file": ("tag.txt", b"not a photo", "text/plain")},
    )
    assert error_response.status_code == 422


class _FakeUploadFile:
    """A duck-typed stand-in for `fastapi.UploadFile` that serves bytes in
    fixed-size chunks via `read(size)`, so `_read_and_validate_photo`'s
    chunked-read loop (#34) can be tested directly without going through a
    real HTTP request - `TestClient` fully buffers a request body client-
    side regardless of how the server reads it, so an HTTP-level test alone
    could never prove the server-side loop actually stops early."""

    def __init__(self, content_type: str, body: bytes) -> None:
        self.content_type = content_type
        self._body = body
        self._offset = 0
        self.read_calls: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        self.read_calls.append(size)
        assert size > 0, "must read in bounded chunks, never read()-everything"
        chunk = self._body[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


def test_read_and_validate_photo_aborts_before_reading_the_whole_oversized_body() -> (
    None
):
    # One byte past the limit, but "long" enough that reading it all in one
    # unbounded call would be the naive (and, per #34, memory-unsafe) thing
    # to do - the body is deliberately much larger than the limit so a
    # bug that reads-to-completion-then-checks would read far more than a
    # bug that aborts as soon as the cumulative size crosses the limit.
    huge_body = b"x" * (MAX_UPLOAD_BYTES * 4)
    fake_file = _FakeUploadFile("image/jpeg", huge_body)

    with pytest.raises(Exception) as exc_info:
        asyncio.run(_read_and_validate_photo(fake_file))  # type: ignore[arg-type]

    assert getattr(exc_info.value, "status_code", None) == 413

    bytes_actually_read = sum(
        min(call_size, len(huge_body)) for call_size in fake_file.read_calls
    )
    # The whole point of #34: never buffer the entire oversized body before
    # rejecting it. A generous margin above MAX_UPLOAD_BYTES (rather than an
    # exact chunk-size assertion) keeps this test from being coupled to the
    # implementation's specific chunk size, while still failing hard against
    # a regression back to "read everything, then check the length."
    assert bytes_actually_read < MAX_UPLOAD_BYTES * 2


def test_trucks_from_photo_rejects_oversized_upload(client_factory: Any) -> None:
    deps = PhotoOCRDependencies()
    client = client_factory(deps)
    register_and_login(client)

    oversized = b"x" * (10 * 1024 * 1024 + 1)
    response = client.post(
        "/trucks/from-photo",
        files={"file": ("tag.jpg", oversized, "image/jpeg")},
    )

    assert response.status_code == 413


def test_trucks_from_photo_maps_service_unavailable_to_503(
    client_factory: Any,
) -> None:
    deps = PhotoOCRDependencies(
        truck_tag_source=lambda photo_path: _UnavailableFieldSource()
    )
    client = client_factory(deps)
    register_and_login(client)

    response = client.post("/trucks/from-photo", files={"file": JPEG_FILE})

    assert response.status_code == 503
    assert "photo" not in response.json()["detail"].lower()


# --- POST /trailers/from-photo ------------------------------------------


def test_trailers_from_photo_returns_proposal(client_factory: Any) -> None:
    deps = PhotoOCRDependencies(
        trailer_tag_source=lambda photo_path: _FakeFieldSource(
            {"gvwr": 23500.0, "gawr": 8000.0, "uvw": 20554.0}
        )
    )
    client = client_factory(deps)
    register_and_login(client)

    response = client.post("/trailers/from-photo", files={"file": JPEG_FILE})

    assert response.status_code == 200, response.text
    assert response.json() == {"gvwr": 23500.0, "gawr": 8000.0, "uvw": 20554.0}


def test_trailers_from_photo_requires_authentication(client_factory: Any) -> None:
    deps = PhotoOCRDependencies()
    client = client_factory(deps)

    response = client.post("/trailers/from-photo", files={"file": JPEG_FILE})

    assert response.status_code == 401


def test_trailers_from_photo_maps_service_unavailable_to_503(
    client_factory: Any,
) -> None:
    deps = PhotoOCRDependencies(
        trailer_tag_source=lambda photo_path: _UnavailableFieldSource()
    )
    client = client_factory(deps)
    register_and_login(client)

    response = client.post("/trailers/from-photo", files={"file": JPEG_FILE})

    assert response.status_code == 503


# --- GET /trailers/axle-count-lookup -------------------------------------


def test_axle_count_lookup_returns_looked_up_value(client_factory: Any) -> None:
    deps = PhotoOCRDependencies(
        axle_count_source=lambda make, model: _FakeFieldSource({"axle_count": 2.0})
    )
    client = client_factory(deps)
    register_and_login(client)

    response = client.get(
        "/trailers/axle-count-lookup",
        params={"make": "Grand Design", "model": "Reflection 315RLTS"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"axle_count": 2.0}


def test_axle_count_lookup_returns_null_not_error_when_unknown(
    client_factory: Any,
) -> None:
    deps = PhotoOCRDependencies(
        axle_count_source=lambda make, model: _FakeFieldSource({"axle_count": None})
    )
    client = client_factory(deps)
    register_and_login(client)

    response = client.get(
        "/trailers/axle-count-lookup",
        params={"make": "Unknown Co", "model": "Mystery Model"},
    )

    assert response.status_code == 200
    assert response.json() == {"axle_count": None}


def test_axle_count_lookup_requires_authentication(client_factory: Any) -> None:
    deps = PhotoOCRDependencies()
    client = client_factory(deps)

    response = client.get(
        "/trailers/axle-count-lookup", params={"make": "Grand Design", "model": "X"}
    )

    assert response.status_code == 401


def test_axle_count_lookup_maps_service_unavailable_to_503(client_factory: Any) -> None:
    deps = PhotoOCRDependencies(
        axle_count_source=lambda make, model: _UnavailableFieldSource()
    )
    client = client_factory(deps)
    register_and_login(client)

    response = client.get(
        "/trailers/axle-count-lookup", params={"make": "Grand Design", "model": "X"}
    )

    assert response.status_code == 503


# --- POST /tickets/from-photo --------------------------------------------


def test_tickets_from_photo_combined_returns_trailer_axle(client_factory: Any) -> None:
    deps = PhotoOCRDependencies(
        scale_ticket_source=lambda photo_path: _FakeTextFieldSource(
            {
                "steer": 5640.0,
                "drive": 9080.0,
                "trailer_axle": 19680.0,
                "gross": 34400.0,
                "timestamp": "7-12-26 10:10",
                "reweigh_reference": "1327426192434",
            },
            allow_trailer_axle=True,
        )
    )
    client = client_factory(deps)
    register_and_login(client)

    response = client.post(
        "/tickets/from-photo",
        files={"file": JPEG_FILE},
        data={"ticket_type": "combined"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "steer": 5640.0,
        "drive": 9080.0,
        "gross": 34400.0,
        "trailer_axle": 19680.0,
        "timestamp": "7-12-26 10:10",
        "reweigh_reference": "1327426192434",
    }


def test_tickets_from_photo_solo_never_asks_for_trailer_axle(
    client_factory: Any,
) -> None:
    deps = PhotoOCRDependencies(
        scale_ticket_source=lambda photo_path: _FakeTextFieldSource(
            {
                "steer": 5560.0,
                "drive": 4420.0,
                "gross": 9980.0,
                "timestamp": "7-11-26 15:50",
                "reweigh_reference": None,
            },
            allow_trailer_axle=False,
        )
    )
    client = client_factory(deps)
    register_and_login(client)

    response = client.post(
        "/tickets/from-photo",
        files={"file": JPEG_FILE},
        data={"ticket_type": "solo"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["trailer_axle"] is None
    assert body["steer"] == 5560.0
    assert body["drive"] == 4420.0
    assert body["gross"] == 9980.0
    assert body["timestamp"] == "7-11-26 15:50"
    assert body["reweigh_reference"] is None


def test_tickets_from_photo_rejects_invalid_ticket_type(client_factory: Any) -> None:
    deps = PhotoOCRDependencies()
    client = client_factory(deps)
    register_and_login(client)

    response = client.post(
        "/tickets/from-photo",
        files={"file": JPEG_FILE},
        data={"ticket_type": "not-a-real-type"},
    )

    assert response.status_code == 422


def test_tickets_from_photo_rejects_unsupported_file_type(client_factory: Any) -> None:
    deps = PhotoOCRDependencies()
    client = client_factory(deps)
    register_and_login(client)

    response = client.post(
        "/tickets/from-photo",
        files={"file": ("ticket.pdf", b"%PDF-1.4", "application/pdf")},
        data={"ticket_type": "combined"},
    )

    assert response.status_code == 422


def test_tickets_from_photo_requires_authentication(client_factory: Any) -> None:
    deps = PhotoOCRDependencies()
    client = client_factory(deps)

    response = client.post(
        "/tickets/from-photo",
        files={"file": JPEG_FILE},
        data={"ticket_type": "combined"},
    )

    assert response.status_code == 401


def test_tickets_from_photo_maps_service_unavailable_to_503(
    client_factory: Any,
) -> None:
    deps = PhotoOCRDependencies(
        scale_ticket_source=lambda photo_path: _UnavailableFieldSource()
    )
    client = client_factory(deps)
    register_and_login(client)

    response = client.post(
        "/tickets/from-photo",
        files={"file": JPEG_FILE},
        data={"ticket_type": "combined"},
    )

    assert response.status_code == 503
