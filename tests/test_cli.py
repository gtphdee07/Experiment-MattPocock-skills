from pathlib import Path

import pytest

from towing_app.cli import (
    DEFAULT_DB_PATH,
    collect_truck_profile,
    collect_truck_profile_from_photo,
    resolve_db_path,
    run_truck_add,
)
from towing_app.field_acquisition import FieldSourceUnavailableError
from towing_app.models import TruckProfile
from towing_app.storage import InMemoryTruckStore


class _FakeFieldSource:
    """A canned field source standing in for OCR extraction in tests."""

    def __init__(self, values: dict[str, float | None]) -> None:
        self._values = values

    def propose(self, field: str) -> float | None:
        return self._values.get(field)


class _UnavailableFieldSource:
    """Simulates the extraction service itself being unreachable."""

    def propose(self, field: str) -> float | None:
        raise FieldSourceUnavailableError("simulated outage")


def test_collect_truck_profile_returns_profile_when_confirmed() -> None:
    responses = iter(["14000", "6000", "9900", "32500", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_truck_profile(read)

    assert result == TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500
    )


def test_collect_truck_profile_returns_none_when_declined() -> None:
    responses = iter(["14000", "6000", "9900", "32500", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_truck_profile(read)

    assert result is None


def test_collect_truck_profile_allows_blank_gcwr() -> None:
    responses = iter(["14000", "6000", "9900", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_truck_profile(read)

    assert result == TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=None
    )


def test_collect_truck_profile_confirmation_prompt_echoes_entered_values() -> None:
    responses = iter(["14000", "6000", "9900", "32500", "y"])
    prompts: list[str] = []

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    collect_truck_profile(read)

    confirmation_prompt = prompts[-1]
    assert "14000" in confirmation_prompt
    assert "6000" in confirmation_prompt
    assert "9900" in confirmation_prompt
    assert "32500" in confirmation_prompt


def test_run_truck_add_saves_confirmed_profile_to_store() -> None:
    store = InMemoryTruckStore()
    responses = iter(["14000", "6000", "9900", "32500", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    run_truck_add(store, read)

    expected = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500)
    assert store.list() == [expected]


def test_collect_truck_profile_reprompts_on_invalid_number() -> None:
    responses = iter(["not-a-number", "14000", "6000", "9900", "32500", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_truck_profile(read)

    assert result == TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500
    )


def test_collect_truck_profile_reprompts_on_invalid_gcwr_then_accepts_blank() -> None:
    responses = iter(["14000", "6000", "9900", "not-a-number", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_truck_profile(read)

    assert result == TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=None
    )


def test_collect_truck_profile_from_photo_uses_proposed_values() -> None:
    field_source = _FakeFieldSource(
        {"gvwr": 14000, "front_gawr": 6000, "rear_gawr": 9900}
    )
    responses = iter(["32500", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_truck_profile_from_photo(read, field_source)

    assert result == TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500
    )


def test_collect_truck_profile_from_photo_returns_none_when_declined() -> None:
    field_source = _FakeFieldSource(
        {"gvwr": 14000, "front_gawr": 6000, "rear_gawr": 9900}
    )
    responses = iter(["32500", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_truck_profile_from_photo(read, field_source)

    assert result is None


def test_collect_truck_profile_from_photo_confirmation_echoes_proposed_values() -> None:
    field_source = _FakeFieldSource(
        {"gvwr": 14000, "front_gawr": 6000, "rear_gawr": 9900}
    )
    responses = iter(["32500", "y"])
    prompts: list[str] = []

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    collect_truck_profile_from_photo(read, field_source)

    confirmation_prompt = prompts[-1]
    assert "14000" in confirmation_prompt
    assert "6000" in confirmation_prompt
    assert "9900" in confirmation_prompt
    assert "32500" in confirmation_prompt


def test_collect_truck_profile_from_photo_falls_back_to_manual_entry_when_missing() -> (
    None
):
    # front_gawr couldn't be read from the photo - the user must type it.
    field_source = _FakeFieldSource({"gvwr": 14000, "rear_gawr": 9900})
    responses = iter(["6000", "32500", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_truck_profile_from_photo(read, field_source)

    assert result == TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500
    )


def test_collect_truck_profile_from_photo_falls_back_fully_on_service_outage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    field_source = _UnavailableFieldSource()
    responses = iter(["14000", "6000", "9900", "32500", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_truck_profile_from_photo(read, field_source)

    assert result == TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500
    )
    # A field-source outage is a different message than "this one field was
    # unreadable" - the user shouldn't be told to blame their photo, and it
    # should print once, not once per field.
    printed = capsys.readouterr().out.lower()
    assert "service" in printed
    assert "photo" not in printed
    assert printed.count("enter") <= 1 or printed.count("manually") == 1


def test_run_truck_add_with_photo_saves_using_field_source() -> None:
    store = InMemoryTruckStore()
    field_source = _FakeFieldSource(
        {"gvwr": 14000, "front_gawr": 6000, "rear_gawr": 9900}
    )
    responses = iter(["32500", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    run_truck_add(
        store,
        read,
        photo_path=Path("tag.jpg"),
        field_source_factory=lambda _photo_path: field_source,
    )

    expected = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500)
    assert store.list() == [expected]


def test_resolve_db_path_uses_env_override() -> None:
    env = {"TOWING_APP_DB_PATH": "/tmp/custom.db"}
    assert resolve_db_path(env) == Path("/tmp/custom.db")


def test_resolve_db_path_falls_back_to_default() -> None:
    assert resolve_db_path({}) == DEFAULT_DB_PATH


def test_run_truck_add_does_not_save_when_declined() -> None:
    store = InMemoryTruckStore()
    responses = iter(["14000", "6000", "9900", "32500", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_truck_add(store, read)

    assert store.list() == []
