from towing_app.cli import (
    collect_trailer_profile,
    collect_trailer_profile_edit,
    run_trailer_add,
    run_trailer_delete,
    run_trailer_edit,
)
from towing_app.models import TrailerProfile
from towing_app.storage import InMemoryTrailerStore


def test_collect_trailer_profile_returns_profile_when_confirmed() -> None:
    responses = iter(["23500", "8000", "3", "20554", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile(read)

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)


def test_collect_trailer_profile_returns_none_when_declined() -> None:
    responses = iter(["23500", "8000", "3", "20554", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile(read)

    assert result is None


def test_collect_trailer_profile_allows_blank_uvw() -> None:
    responses = iter(["23500", "8000", "3", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile(read)

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=None)


def test_collect_trailer_profile_confirmation_prompt_echoes_entered_values() -> None:
    responses = iter(["23500", "8000", "3", "20554", "y"])
    prompts: list[str] = []

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    collect_trailer_profile(read)

    confirmation_prompt = prompts[-1]
    assert "23500" in confirmation_prompt
    assert "8000" in confirmation_prompt
    assert "3" in confirmation_prompt
    assert "20554" in confirmation_prompt


def test_collect_trailer_profile_reprompts_on_invalid_number() -> None:
    responses = iter(["not-a-number", "23500", "8000", "3", "20554", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile(read)

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)


def test_collect_trailer_profile_reprompts_on_invalid_axle_count() -> None:
    responses = iter(["23500", "8000", "not-a-number", "3", "20554", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile(read)

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)


def test_run_trailer_add_saves_confirmed_profile_to_store() -> None:
    store = InMemoryTrailerStore()
    responses = iter(["23500", "8000", "3", "20554", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    run_trailer_add(store, read)

    expected = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)
    assert store.list() == [expected]


def test_run_trailer_add_does_not_save_when_declined() -> None:
    store = InMemoryTrailerStore()
    responses = iter(["23500", "8000", "3", "20554", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_trailer_add(store, read)

    assert store.list() == []


def test_collect_trailer_profile_edit_prefills_and_returns_updated_profile() -> None:
    current = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554, id=1)
    responses = iter(["24000", "", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_edit(read, current)

    assert result == TrailerProfile(gvwr=24000, gawr=8000, axle_count=3, uvw=20554)
    assert result is not None
    assert result.id == 1


def test_collect_trailer_profile_edit_returns_none_when_declined() -> None:
    current = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554, id=1)
    responses = iter(["", "", "", "", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_edit(read, current)

    assert result is None


def test_collect_trailer_profile_edit_allows_clearing_uvw() -> None:
    current = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554, id=1)
    responses = iter(["", "", "", "none", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_edit(read, current)

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=None)


def test_collect_trailer_profile_edit_reprompts_on_invalid_number() -> None:
    current = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554, id=1)
    responses = iter(["not-a-number", "24000", "", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_edit(read, current)

    assert result == TrailerProfile(gvwr=24000, gawr=8000, axle_count=3, uvw=20554)


def test_run_trailer_edit_updates_selected_profile_in_store() -> None:
    store = InMemoryTrailerStore()
    store.save(TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554))
    [saved] = store.list()
    responses = iter([str(saved.id), "24000", "", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    run_trailer_edit(store, read)

    [result] = store.list()
    assert result.gvwr == 24000
    assert result.gawr == 8000
    assert result.id == saved.id


def test_run_trailer_edit_does_not_update_when_declined() -> None:
    store = InMemoryTrailerStore()
    store.save(TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554))
    [saved] = store.list()
    responses = iter([str(saved.id), "24000", "", "", "", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_trailer_edit(store, read)

    assert store.list() == [saved]


def test_run_trailer_edit_reprompts_on_invalid_id() -> None:
    store = InMemoryTrailerStore()
    store.save(TrailerProfile(gvwr=23500, gawr=8000, axle_count=3))
    [saved] = store.list()
    responses = iter(["abc", "999", str(saved.id), "24000", "", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    run_trailer_edit(store, read)

    [result] = store.list()
    assert result.gvwr == 24000


def test_run_trailer_edit_with_no_profiles_does_not_prompt() -> None:
    store = InMemoryTrailerStore()

    def read(prompt: str) -> str:
        raise AssertionError("should not prompt when there are no profiles")

    run_trailer_edit(store, read)

    assert store.list() == []


def test_run_trailer_delete_removes_selected_profile_from_store() -> None:
    store = InMemoryTrailerStore()
    store.save(TrailerProfile(gvwr=23500, gawr=8000, axle_count=3))
    store.save(TrailerProfile(gvwr=10000, gawr=4000, axle_count=2))
    [first, second] = store.list()
    responses = iter([str(first.id), "y"])

    def read(prompt: str) -> str:
        return next(responses)

    run_trailer_delete(store, read)

    assert store.list() == [second]


def test_run_trailer_delete_does_not_remove_when_declined() -> None:
    store = InMemoryTrailerStore()
    store.save(TrailerProfile(gvwr=23500, gawr=8000, axle_count=3))
    [saved] = store.list()
    responses = iter([str(saved.id), "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_trailer_delete(store, read)

    assert store.list() == [saved]


def test_run_trailer_delete_reprompts_on_invalid_id() -> None:
    store = InMemoryTrailerStore()
    store.save(TrailerProfile(gvwr=23500, gawr=8000, axle_count=3))
    [saved] = store.list()
    responses = iter(["abc", "999", str(saved.id), "y"])

    def read(prompt: str) -> str:
        return next(responses)

    run_trailer_delete(store, read)

    assert store.list() == []


def test_run_trailer_delete_with_no_profiles_does_not_prompt() -> None:
    store = InMemoryTrailerStore()

    def read(prompt: str) -> str:
        raise AssertionError("should not prompt when there are no profiles")

    run_trailer_delete(store, read)

    assert store.list() == []
