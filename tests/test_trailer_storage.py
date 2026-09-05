from dataclasses import replace

from towing_app.models import TrailerProfile
from towing_app.storage import InMemoryTrailerStore


def test_save_and_list_returns_saved_trailer_profile() -> None:
    store = InMemoryTrailerStore()
    profile = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)

    store.save(profile)

    assert store.list() == [profile]


def test_save_assigns_an_id() -> None:
    store = InMemoryTrailerStore()
    profile = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)

    store.save(profile)

    [saved] = store.list()
    assert saved.id is not None


def test_save_assigns_distinct_ids_to_successive_profiles() -> None:
    store = InMemoryTrailerStore()
    store.save(TrailerProfile(gvwr=23500, gawr=8000, axle_count=3))
    store.save(TrailerProfile(gvwr=10000, gawr=4000, axle_count=2))

    ids = [profile.id for profile in store.list()]

    assert len(ids) == len(set(ids))


def test_update_replaces_profile_with_matching_id() -> None:
    store = InMemoryTrailerStore()
    store.save(TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554))
    [saved] = store.list()

    updated = replace(saved, gvwr=24000)
    store.update(updated)

    assert store.list() == [updated]
    [result] = store.list()
    assert result.gvwr == 24000


def test_delete_removes_profile_with_matching_id() -> None:
    store = InMemoryTrailerStore()
    store.save(TrailerProfile(gvwr=23500, gawr=8000, axle_count=3))
    store.save(TrailerProfile(gvwr=10000, gawr=4000, axle_count=2))
    [first, second] = store.list()
    assert first.id is not None

    store.delete(first.id)

    assert store.list() == [second]
