from pathlib import Path

import anthropic
import httpx2
import pytest

from towing_app.field_acquisition import (
    ClaudeVisionTruckTagFieldSource,
    FieldSourceUnavailableError,
)


def test_propose_returns_extracted_value_for_known_field(tmp_path: Path) -> None:
    photo_path = tmp_path / "tag.jpg"
    photo_path.write_bytes(b"fake-image-bytes")

    def fake_vision_completion(image_b64: str, media_type: str) -> str:
        return '{"gvwr": 14000, "front_gawr": 6000, "rear_gawr": 9900}'

    source = ClaudeVisionTruckTagFieldSource(photo_path, fake_vision_completion)

    assert source.propose("gvwr") == 14000
    assert source.propose("front_gawr") == 6000
    assert source.propose("rear_gawr") == 9900


def test_propose_returns_none_for_field_missing_from_extraction(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "tag.jpg"
    photo_path.write_bytes(b"fake-image-bytes")

    def fake_vision_completion(image_b64: str, media_type: str) -> str:
        return '{"gvwr": 14000, "front_gawr": null, "rear_gawr": 9900}'

    source = ClaudeVisionTruckTagFieldSource(photo_path, fake_vision_completion)

    assert source.propose("front_gawr") is None


def test_propose_returns_none_when_extraction_is_not_valid_json(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "tag.jpg"
    photo_path.write_bytes(b"fake-image-bytes")

    def fake_vision_completion(image_b64: str, media_type: str) -> str:
        return "I could not read this label clearly."

    source = ClaudeVisionTruckTagFieldSource(photo_path, fake_vision_completion)

    assert source.propose("gvwr") is None


def test_propose_raises_service_unavailable_when_the_api_call_fails(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "tag.jpg"
    photo_path.write_bytes(b"fake-image-bytes")
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    def failing_vision_completion(image_b64: str, media_type: str) -> str:
        raise anthropic.APIConnectionError(request=request)

    source = ClaudeVisionTruckTagFieldSource(photo_path, failing_vision_completion)

    with pytest.raises(FieldSourceUnavailableError):
        source.propose("gvwr")


def test_propose_raises_service_unavailable_when_api_key_is_missing(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "tag.jpg"
    photo_path.write_bytes(b"fake-image-bytes")

    def missing_key_vision_completion(image_b64: str, media_type: str) -> str:
        # The real SDK raises a bare TypeError (not an anthropic.* exception)
        # from client.messages.create() when no credentials resolve.
        raise TypeError(
            "Could not resolve authentication method. Expected one of "
            "api_key, auth_token, or credentials to be set."
        )

    source = ClaudeVisionTruckTagFieldSource(photo_path, missing_key_vision_completion)

    with pytest.raises(FieldSourceUnavailableError):
        source.propose("gvwr")


def test_propose_raises_service_unavailable_when_api_key_is_invalid(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "tag.jpg"
    photo_path.write_bytes(b"fake-image-bytes")
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(
        401, request=request, json={"error": {"type": "authentication_error"}}
    )

    def invalid_key_vision_completion(image_b64: str, media_type: str) -> str:
        raise anthropic.AuthenticationError(
            "Error code: 401", response=response, body=None
        )

    source = ClaudeVisionTruckTagFieldSource(photo_path, invalid_key_vision_completion)

    with pytest.raises(FieldSourceUnavailableError):
        source.propose("gvwr")


def test_propose_calls_vision_completion_only_once_across_multiple_fields(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "tag.jpg"
    photo_path.write_bytes(b"fake-image-bytes")
    call_count = 0

    def fake_vision_completion(image_b64: str, media_type: str) -> str:
        nonlocal call_count
        call_count += 1
        return '{"gvwr": 14000, "front_gawr": 6000, "rear_gawr": 9900}'

    source = ClaudeVisionTruckTagFieldSource(photo_path, fake_vision_completion)
    source.propose("gvwr")
    source.propose("front_gawr")
    source.propose("rear_gawr")

    assert call_count == 1
