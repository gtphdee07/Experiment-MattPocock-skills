from towing_app.cli import collect_trailer_profile, run_trailer_add
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
