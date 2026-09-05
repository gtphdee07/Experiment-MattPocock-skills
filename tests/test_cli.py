from pathlib import Path

from towing_app.cli import (
    DEFAULT_DB_PATH,
    collect_truck_profile,
    resolve_db_path,
    run_truck_add,
)
from towing_app.models import TruckProfile
from towing_app.storage import InMemoryTruckStore


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
