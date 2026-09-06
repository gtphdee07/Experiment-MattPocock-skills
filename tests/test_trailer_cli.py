from pathlib import Path

import pytest

from towing_app.cli import (
    collect_trailer_profile,
    collect_trailer_profile_edit,
    collect_trailer_profile_from_photo,
    run_trailer_add,
    run_trailer_delete,
    run_trailer_edit,
)
from towing_app.field_acquisition import FieldSourceUnavailableError
from towing_app.models import TrailerProfile
from towing_app.storage import InMemoryTrailerStore


class _FakeFieldSource:
    """A canned field source standing in for OCR extraction in tests."""

    def __init__(self, values: dict[str, float | None]) -> None:
        self._values = values

    def propose(self, field: str) -> float | None:
        return self._values.get(field)


class _UnavailableFieldSource:
    """Simulates the extraction/lookup service itself being unreachable."""

    def propose(self, field: str) -> float | None:
        raise FieldSourceUnavailableError("simulated outage")


def test_collect_trailer_profile_returns_profile_when_confirmed() -> None:
    responses = iter(["23500", "8000", "3", "20554", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile(read)

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)


def test_collect_trailer_profile_returns_none_when_declined() -> None:
    responses = iter(["23500", "8000", "3", "20554", "", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile(read)

    assert result is None


def test_collect_trailer_profile_allows_blank_uvw() -> None:
    responses = iter(["23500", "8000", "3", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile(read)

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=None)


def test_collect_trailer_profile_confirmation_prompt_echoes_entered_values() -> None:
    responses = iter(["23500", "8000", "3", "20554", "", "y"])
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
    responses = iter(["not-a-number", "23500", "8000", "3", "20554", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile(read)

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)


def test_collect_trailer_profile_reprompts_on_invalid_axle_count() -> None:
    responses = iter(["23500", "8000", "not-a-number", "3", "20554", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile(read)

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)


# --- Nickname (#12) ----------------------------------------------------------


def test_collect_trailer_profile_captures_nickname_when_provided() -> None:
    responses = iter(["23500", "8000", "3", "20554", "Goose", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile(read)

    assert result == TrailerProfile(
        gvwr=23500, gawr=8000, axle_count=3, uvw=20554, nickname="Goose"
    )


def test_collect_trailer_profile_allows_blank_nickname() -> None:
    responses = iter(["23500", "8000", "3", "20554", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile(read)

    assert result is not None
    assert result.nickname is None


def test_collect_trailer_profile_nickname_prompt_labeled_nick_name_reference() -> None:
    responses = iter(["23500", "8000", "3", "20554", "Goose", "y"])
    prompts: list[str] = []

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    collect_trailer_profile(read)

    assert any("Nick Name / Reference" in p for p in prompts)


def test_run_trailer_add_saves_confirmed_profile_to_store() -> None:
    store = InMemoryTrailerStore()
    responses = iter(["23500", "8000", "3", "20554", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    run_trailer_add(store, read)

    expected = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)
    assert store.list() == [expected]


def test_run_trailer_add_allows_duplicate_nicknames() -> None:
    store = InMemoryTrailerStore()
    responses = iter(
        [
            "23500",
            "8000",
            "3",
            "20554",
            "Goose",
            "y",
            "10000",
            "4000",
            "2",
            "",
            "Goose",
            "y",
        ]
    )

    def read(prompt: str) -> str:
        return next(responses)

    run_trailer_add(store, read)
    run_trailer_add(store, read)

    nicknames = [profile.nickname for profile in store.list()]
    assert nicknames == ["Goose", "Goose"]


def test_run_trailer_add_does_not_save_when_declined() -> None:
    store = InMemoryTrailerStore()
    responses = iter(["23500", "8000", "3", "20554", "", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_trailer_add(store, read)

    assert store.list() == []


def test_collect_trailer_profile_edit_prefills_and_returns_updated_profile() -> None:
    current = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554, id=1)
    responses = iter(["24000", "", "", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_edit(read, current)

    assert result == TrailerProfile(gvwr=24000, gawr=8000, axle_count=3, uvw=20554)
    assert result is not None
    assert result.id == 1


def test_collect_trailer_profile_edit_returns_none_when_declined() -> None:
    current = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554, id=1)
    responses = iter(["", "", "", "", "", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_edit(read, current)

    assert result is None


def test_collect_trailer_profile_edit_allows_clearing_uvw() -> None:
    current = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554, id=1)
    responses = iter(["", "", "", "none", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_edit(read, current)

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=None)


def test_collect_trailer_profile_edit_reprompts_on_invalid_number() -> None:
    current = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554, id=1)
    responses = iter(["not-a-number", "24000", "", "", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_edit(read, current)

    assert result == TrailerProfile(gvwr=24000, gawr=8000, axle_count=3, uvw=20554)


def test_collect_trailer_profile_edit_changes_nickname() -> None:
    current = TrailerProfile(
        gvwr=23500, gawr=8000, axle_count=3, uvw=20554, nickname="Goose", id=1
    )
    responses = iter(["", "", "", "", "Loose Goose", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_edit(read, current)

    assert result is not None
    assert result.nickname == "Loose Goose"


def test_collect_trailer_profile_edit_keeps_nickname_when_blank() -> None:
    current = TrailerProfile(
        gvwr=23500, gawr=8000, axle_count=3, uvw=20554, nickname="Goose", id=1
    )
    responses = iter(["", "", "", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_edit(read, current)

    assert result is not None
    assert result.nickname == "Goose"


def test_run_trailer_edit_updates_selected_profile_in_store() -> None:
    store = InMemoryTrailerStore()
    store.save(TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554))
    [saved] = store.list()
    responses = iter([str(saved.id), "24000", "", "", "", "", "y"])

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
    responses = iter([str(saved.id), "24000", "", "", "", "", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_trailer_edit(store, read)

    assert store.list() == [saved]


def test_run_trailer_edit_reprompts_on_invalid_id() -> None:
    store = InMemoryTrailerStore()
    store.save(TrailerProfile(gvwr=23500, gawr=8000, axle_count=3))
    [saved] = store.list()
    responses = iter(["abc", "999", str(saved.id), "24000", "", "", "", "", "y"])

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


def test_run_trailer_edit_lists_profiles_leading_with_nickname_or_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = InMemoryTrailerStore()
    store.save(TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, nickname="Goose"))
    store.save(TrailerProfile(gvwr=10000, gawr=4000, axle_count=2))
    [named, unnamed] = store.list()
    responses = iter([str(named.id), "", "", "", "", "", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_trailer_edit(store, read)

    output = capsys.readouterr().out
    assert f"[{named.id}] Goose —" in output
    assert f"[{unnamed.id}] Trailer {unnamed.id} —" in output


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


# ---------------------------------------------------------------------------
# collect_trailer_profile_from_photo
# ---------------------------------------------------------------------------


def test_collect_trailer_profile_from_photo_uses_proposed_values() -> None:
    field_source = _FakeFieldSource({"gvwr": 23500, "gawr": 8000, "uvw": 20554})
    axle_count_source = _FakeFieldSource({"axle_count": 3})
    responses = iter(["Grand Design", "Reflection 315RLTS", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_from_photo(
        read, field_source, lambda make, model: axle_count_source
    )

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)


def test_collect_trailer_profile_from_photo_captures_nickname() -> None:
    field_source = _FakeFieldSource({"gvwr": 23500, "gawr": 8000, "uvw": 20554})
    axle_count_source = _FakeFieldSource({"axle_count": 3})
    responses = iter(["Grand Design", "Reflection 315RLTS", "Goose", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_from_photo(
        read, field_source, lambda make, model: axle_count_source
    )

    assert result == TrailerProfile(
        gvwr=23500, gawr=8000, axle_count=3, uvw=20554, nickname="Goose"
    )


def test_collect_trailer_profile_from_photo_returns_none_when_declined() -> None:
    field_source = _FakeFieldSource({"gvwr": 23500, "gawr": 8000, "uvw": 20554})
    axle_count_source = _FakeFieldSource({"axle_count": 3})
    responses = iter(["Grand Design", "Reflection 315RLTS", "", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_from_photo(
        read, field_source, lambda make, model: axle_count_source
    )

    assert result is None


def test_collect_trailer_profile_from_photo_falls_back_when_tag_field_missing() -> None:
    # uvw couldn't be read from the photo - the user must type it (or skip).
    field_source = _FakeFieldSource({"gvwr": 23500, "gawr": 8000})
    axle_count_source = _FakeFieldSource({"axle_count": 3})
    responses = iter(["20554", "Grand Design", "Reflection 315RLTS", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_from_photo(
        read, field_source, lambda make, model: axle_count_source
    )

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)


def test_collect_trailer_profile_from_photo_falls_back_fully_on_vision_service_outage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    field_source = _UnavailableFieldSource()
    axle_count_source = _FakeFieldSource({"axle_count": 3})
    responses = iter(
        ["23500", "8000", "20554", "Grand Design", "Reflection 315RLTS", "", "y"]
    )

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_from_photo(
        read, field_source, lambda make, model: axle_count_source
    )

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)
    printed = capsys.readouterr().out.lower()
    assert "service" in printed
    assert "photo" not in printed


def test_collect_trailer_profile_from_photo_falls_back_when_lookup_finds_no_match(
    capsys: pytest.CaptureFixture[str],
) -> None:
    field_source = _FakeFieldSource({"gvwr": 23500, "gawr": 8000, "uvw": 20554})
    axle_count_source = _FakeFieldSource({})  # no axle_count -> propose returns None
    responses = iter(["Unknown Co", "Mystery Model", "3", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_from_photo(
        read, field_source, lambda make, model: axle_count_source
    )

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)
    printed = capsys.readouterr().out.lower()
    assert "manually" in printed


def test_collect_trailer_profile_from_photo_falls_back_on_lookup_service_outage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    field_source = _FakeFieldSource({"gvwr": 23500, "gawr": 8000, "uvw": 20554})
    axle_count_source = _UnavailableFieldSource()
    responses = iter(["Grand Design", "Reflection 315RLTS", "3", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_trailer_profile_from_photo(
        read, field_source, lambda make, model: axle_count_source
    )

    assert result == TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)
    printed = capsys.readouterr().out.lower()
    assert "service" in printed


def test_run_trailer_add_with_photo_saves_using_field_source_and_lookup() -> None:
    store = InMemoryTrailerStore()
    field_source = _FakeFieldSource({"gvwr": 23500, "gawr": 8000, "uvw": 20554})
    axle_count_source = _FakeFieldSource({"axle_count": 3})
    responses = iter(["Grand Design", "Reflection 315RLTS", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    run_trailer_add(
        store,
        read,
        photo_path=Path("tag.jpg"),
        field_source_factory=lambda _photo_path: field_source,
        axle_count_source_factory=lambda make, model: axle_count_source,
    )

    expected = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)
    assert store.list() == [expected]
