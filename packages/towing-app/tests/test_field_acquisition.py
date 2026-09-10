from pathlib import Path

import anthropic
import httpx2
import pytest
from towing_app.field_acquisition import (
    ClaudeVisionScaleTicketFieldSource,
    ClaudeVisionTrailerTagFieldSource,
    ClaudeVisionTruckTagFieldSource,
    WebAxleCountFieldSource,
)
from towing_core.field_acquisition import FieldSourceUnavailableError

# ---------------------------------------------------------------------------
# ClaudeVisionTrailerTagFieldSource
# ---------------------------------------------------------------------------


def test_trailer_propose_returns_extracted_value_for_known_field(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "tag.jpg"
    photo_path.write_bytes(b"fake-image-bytes")

    def fake_vision_completion(image_b64: str, media_type: str) -> str:
        return '{"gvwr": 23500, "gawr": 8000, "uvw": 20554}'

    source = ClaudeVisionTrailerTagFieldSource(photo_path, fake_vision_completion)

    assert source.propose("gvwr") == 23500
    assert source.propose("gawr") == 8000
    assert source.propose("uvw") == 20554


def test_trailer_propose_returns_none_for_field_missing_from_extraction(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "tag.jpg"
    photo_path.write_bytes(b"fake-image-bytes")

    def fake_vision_completion(image_b64: str, media_type: str) -> str:
        return '{"gvwr": 23500, "gawr": 8000, "uvw": null}'

    source = ClaudeVisionTrailerTagFieldSource(photo_path, fake_vision_completion)

    assert source.propose("uvw") is None


def test_trailer_propose_returns_none_when_extraction_is_not_valid_json(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "tag.jpg"
    photo_path.write_bytes(b"fake-image-bytes")

    def fake_vision_completion(image_b64: str, media_type: str) -> str:
        return "I could not read this label clearly."

    source = ClaudeVisionTrailerTagFieldSource(photo_path, fake_vision_completion)

    assert source.propose("gvwr") is None


def test_trailer_propose_raises_service_unavailable_when_the_api_call_fails(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "tag.jpg"
    photo_path.write_bytes(b"fake-image-bytes")
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    def failing_vision_completion(image_b64: str, media_type: str) -> str:
        raise anthropic.APIConnectionError(request=request)

    source = ClaudeVisionTrailerTagFieldSource(photo_path, failing_vision_completion)

    with pytest.raises(FieldSourceUnavailableError):
        source.propose("gvwr")


def test_trailer_propose_raises_service_unavailable_when_api_key_is_missing(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "tag.jpg"
    photo_path.write_bytes(b"fake-image-bytes")

    def missing_key_vision_completion(image_b64: str, media_type: str) -> str:
        raise TypeError(
            "Could not resolve authentication method. Expected one of "
            "api_key, auth_token, or credentials to be set."
        )

    source = ClaudeVisionTrailerTagFieldSource(
        photo_path, missing_key_vision_completion
    )

    with pytest.raises(FieldSourceUnavailableError):
        source.propose("gvwr")


def test_trailer_propose_calls_vision_completion_only_once_across_multiple_fields(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "tag.jpg"
    photo_path.write_bytes(b"fake-image-bytes")
    call_count = 0

    def fake_vision_completion(image_b64: str, media_type: str) -> str:
        nonlocal call_count
        call_count += 1
        return '{"gvwr": 23500, "gawr": 8000, "uvw": 20554}'

    source = ClaudeVisionTrailerTagFieldSource(photo_path, fake_vision_completion)
    source.propose("gvwr")
    source.propose("gawr")
    source.propose("uvw")

    assert call_count == 1


# ---------------------------------------------------------------------------
# WebAxleCountFieldSource
# ---------------------------------------------------------------------------


def test_axle_count_propose_returns_looked_up_value() -> None:
    def fake_lookup(make: str, model: str) -> str:
        assert make == "Grand Design"
        assert model == "Reflection 315RLTS"
        return '{"axle_count": 2}'

    source = WebAxleCountFieldSource("Grand Design", "Reflection 315RLTS", fake_lookup)

    assert source.propose("axle_count") == 2


def test_axle_count_propose_returns_none_when_lookup_finds_no_match() -> None:
    def fake_lookup(make: str, model: str) -> str:
        return '{"axle_count": null}'

    source = WebAxleCountFieldSource("Unknown Co", "Mystery Model", fake_lookup)

    assert source.propose("axle_count") is None


def test_axle_count_propose_returns_none_when_lookup_is_not_valid_json() -> None:
    def fake_lookup(make: str, model: str) -> str:
        return "I couldn't find specs for this trailer."

    source = WebAxleCountFieldSource("Unknown Co", "Mystery Model", fake_lookup)

    assert source.propose("axle_count") is None


def test_axle_count_propose_raises_service_unavailable_when_the_api_call_fails() -> (
    None
):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    def failing_lookup(make: str, model: str) -> str:
        raise anthropic.APIConnectionError(request=request)

    source = WebAxleCountFieldSource(
        "Grand Design", "Reflection 315RLTS", failing_lookup
    )

    with pytest.raises(FieldSourceUnavailableError):
        source.propose("axle_count")


def test_axle_count_propose_raises_service_unavailable_when_api_key_is_missing() -> (
    None
):
    def missing_key_lookup(make: str, model: str) -> str:
        raise TypeError(
            "Could not resolve authentication method. Expected one of "
            "api_key, auth_token, or credentials to be set."
        )

    source = WebAxleCountFieldSource(
        "Grand Design", "Reflection 315RLTS", missing_key_lookup
    )

    with pytest.raises(FieldSourceUnavailableError):
        source.propose("axle_count")


def test_axle_count_propose_raises_service_unavailable_when_api_key_is_invalid() -> (
    None
):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(
        401, request=request, json={"error": {"type": "authentication_error"}}
    )

    def invalid_key_lookup(make: str, model: str) -> str:
        raise anthropic.AuthenticationError(
            "Error code: 401", response=response, body=None
        )

    source = WebAxleCountFieldSource(
        "Grand Design", "Reflection 315RLTS", invalid_key_lookup
    )

    with pytest.raises(FieldSourceUnavailableError):
        source.propose("axle_count")


def test_axle_count_propose_calls_lookup_only_once_across_multiple_calls() -> None:
    call_count = 0

    def fake_lookup(make: str, model: str) -> str:
        nonlocal call_count
        call_count += 1
        return '{"axle_count": 2}'

    source = WebAxleCountFieldSource("Grand Design", "Reflection 315RLTS", fake_lookup)
    source.propose("axle_count")
    source.propose("axle_count")

    assert call_count == 1


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


# ---------------------------------------------------------------------------
# ClaudeVisionScaleTicketFieldSource
# ---------------------------------------------------------------------------


def test_scale_ticket_propose_returns_extracted_numeric_values(tmp_path: Path) -> None:
    photo_path = tmp_path / "ticket.jpg"
    photo_path.write_bytes(b"fake-image-bytes")

    def fake_vision_completion(image_b64: str, media_type: str) -> str:
        return (
            '{"steer": 5640, "drive": 9080, "trailer_axle": 19680, "gross": 34400, '
            '"timestamp": "7-12-26 10:10", "reweigh_reference": "1327426192434"}'
        )

    source = ClaudeVisionScaleTicketFieldSource(photo_path, fake_vision_completion)

    assert source.propose("steer") == 5640
    assert source.propose("drive") == 9080
    assert source.propose("trailer_axle") == 19680
    assert source.propose("gross") == 34400


def test_scale_ticket_propose_text_returns_extracted_text_values(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "ticket.jpg"
    photo_path.write_bytes(b"fake-image-bytes")

    def fake_vision_completion(image_b64: str, media_type: str) -> str:
        return (
            '{"steer": 5640, "drive": 9080, "trailer_axle": 19680, "gross": 34400, '
            '"timestamp": "7-12-26 10:10", "reweigh_reference": "1327426192434"}'
        )

    source = ClaudeVisionScaleTicketFieldSource(photo_path, fake_vision_completion)

    assert source.propose_text("timestamp") == "7-12-26 10:10"
    assert source.propose_text("reweigh_reference") == "1327426192434"


def test_scale_ticket_propose_text_returns_none_when_field_not_printed(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "ticket.jpg"
    photo_path.write_bytes(b"fake-image-bytes")

    def fake_vision_completion(image_b64: str, media_type: str) -> str:
        return (
            '{"steer": 5560, "drive": 4420, "trailer_axle": 0, "gross": 9980, '
            '"timestamp": "7-11-26 15:50", "reweigh_reference": null}'
        )

    source = ClaudeVisionScaleTicketFieldSource(photo_path, fake_vision_completion)

    assert source.propose_text("reweigh_reference") is None


def test_scale_ticket_propose_returns_none_for_field_missing_from_extraction(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "ticket.jpg"
    photo_path.write_bytes(b"fake-image-bytes")

    def fake_vision_completion(image_b64: str, media_type: str) -> str:
        return (
            '{"steer": 5640, "drive": 9080, "trailer_axle": null, "gross": 34400, '
            '"timestamp": null, "reweigh_reference": null}'
        )

    source = ClaudeVisionScaleTicketFieldSource(photo_path, fake_vision_completion)

    assert source.propose("trailer_axle") is None
    assert source.propose_text("timestamp") is None


def test_scale_ticket_propose_returns_none_when_extraction_is_not_valid_json(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "ticket.jpg"
    photo_path.write_bytes(b"fake-image-bytes")

    def fake_vision_completion(image_b64: str, media_type: str) -> str:
        return "I could not read this ticket clearly."

    source = ClaudeVisionScaleTicketFieldSource(photo_path, fake_vision_completion)

    assert source.propose("steer") is None
    assert source.propose_text("timestamp") is None


def test_scale_ticket_propose_raises_service_unavailable_when_the_api_call_fails(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "ticket.jpg"
    photo_path.write_bytes(b"fake-image-bytes")
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    def failing_vision_completion(image_b64: str, media_type: str) -> str:
        raise anthropic.APIConnectionError(request=request)

    source = ClaudeVisionScaleTicketFieldSource(photo_path, failing_vision_completion)

    with pytest.raises(FieldSourceUnavailableError):
        source.propose("steer")


def test_scale_ticket_propose_raises_service_unavailable_when_api_key_is_missing(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "ticket.jpg"
    photo_path.write_bytes(b"fake-image-bytes")

    def missing_key_vision_completion(image_b64: str, media_type: str) -> str:
        raise TypeError(
            "Could not resolve authentication method. Expected one of "
            "api_key, auth_token, or credentials to be set."
        )

    source = ClaudeVisionScaleTicketFieldSource(
        photo_path, missing_key_vision_completion
    )

    with pytest.raises(FieldSourceUnavailableError):
        source.propose_text("timestamp")


def test_scale_ticket_propose_calls_vision_completion_only_once_across_fields(
    tmp_path: Path,
) -> None:
    photo_path = tmp_path / "ticket.jpg"
    photo_path.write_bytes(b"fake-image-bytes")
    call_count = 0

    def fake_vision_completion(image_b64: str, media_type: str) -> str:
        nonlocal call_count
        call_count += 1
        return (
            '{"steer": 5640, "drive": 9080, "trailer_axle": 19680, "gross": 34400, '
            '"timestamp": "7-12-26 10:10", "reweigh_reference": "1327426192434"}'
        )

    source = ClaudeVisionScaleTicketFieldSource(photo_path, fake_vision_completion)
    source.propose("steer")
    source.propose("drive")
    source.propose_text("timestamp")
    source.propose_text("reweigh_reference")

    assert call_count == 1
