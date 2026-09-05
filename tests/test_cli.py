from pathlib import Path

from towing_app.cli import (
    DEFAULT_DB_PATH,
    collect_truck_profile,
    collect_truck_profile_edit,
    resolve_db_path,
    run_truck_add,
    run_truck_delete,
    run_truck_edit,
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


def test_collect_truck_profile_edit_prefills_and_returns_updated_profile() -> None:
    current = TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500, id=1
    )
    responses = iter(["15000", "", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_truck_profile_edit(read, current)

    assert result == TruckProfile(
        gvwr=15000, front_gawr=6000, rear_gawr=9900, gcwr=32500
    )
    assert result is not None
    assert result.id == 1


def test_collect_truck_profile_edit_returns_none_when_declined() -> None:
    current = TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500, id=1
    )
    responses = iter(["", "", "", "", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_truck_profile_edit(read, current)

    assert result is None


def test_collect_truck_profile_edit_allows_clearing_gcwr() -> None:
    current = TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500, id=1
    )
    responses = iter(["", "", "", "none", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_truck_profile_edit(read, current)

    assert result == TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=None
    )


def test_collect_truck_profile_edit_reprompts_on_invalid_number() -> None:
    current = TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500, id=1
    )
    responses = iter(["not-a-number", "15000", "", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_truck_profile_edit(read, current)

    assert result == TruckProfile(
        gvwr=15000, front_gawr=6000, rear_gawr=9900, gcwr=32500
    )


def test_run_truck_edit_updates_selected_profile_in_store() -> None:
    store = InMemoryTruckStore()
    store.save(TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500))
    [saved] = store.list()
    responses = iter([str(saved.id), "15000", "", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    run_truck_edit(store, read)

    [result] = store.list()
    assert result.gvwr == 15000
    assert result.front_gawr == 6000
    assert result.id == saved.id


def test_run_truck_edit_does_not_update_when_declined() -> None:
    store = InMemoryTruckStore()
    store.save(TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500))
    [saved] = store.list()
    responses = iter([str(saved.id), "15000", "", "", "", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_truck_edit(store, read)

    assert store.list() == [saved]


def test_run_truck_edit_reprompts_on_invalid_id() -> None:
    store = InMemoryTruckStore()
    store.save(TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900))
    [saved] = store.list()
    responses = iter(["abc", "999", str(saved.id), "15000", "", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    run_truck_edit(store, read)

    [result] = store.list()
    assert result.gvwr == 15000


def test_run_truck_edit_with_no_profiles_does_not_prompt() -> None:
    store = InMemoryTruckStore()

    def read(prompt: str) -> str:
        raise AssertionError("should not prompt when there are no profiles")

    run_truck_edit(store, read)

    assert store.list() == []


def test_run_truck_delete_removes_selected_profile_from_store() -> None:
    store = InMemoryTruckStore()
    store.save(TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900))
    store.save(TruckProfile(gvwr=10000, front_gawr=5000, rear_gawr=6000))
    [first, second] = store.list()
    responses = iter([str(first.id), "y"])

    def read(prompt: str) -> str:
        return next(responses)

    run_truck_delete(store, read)

    assert store.list() == [second]


def test_run_truck_delete_does_not_remove_when_declined() -> None:
    store = InMemoryTruckStore()
    store.save(TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900))
    [saved] = store.list()
    responses = iter([str(saved.id), "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_truck_delete(store, read)

    assert store.list() == [saved]


def test_run_truck_delete_reprompts_on_invalid_id() -> None:
    store = InMemoryTruckStore()
    store.save(TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900))
    [saved] = store.list()
    responses = iter(["abc", "999", str(saved.id), "y"])

    def read(prompt: str) -> str:
        return next(responses)

    run_truck_delete(store, read)

    assert store.list() == []


def test_run_truck_delete_with_no_profiles_does_not_prompt() -> None:
    store = InMemoryTruckStore()

    def read(prompt: str) -> str:
        raise AssertionError("should not prompt when there are no profiles")

    run_truck_delete(store, read)

    assert store.list() == []
