from dataclasses import replace

from towing_app.models import TruckProfile
from towing_app.storage import InMemoryTruckStore


def test_save_and_list_returns_saved_truck_profile() -> None:
    store = InMemoryTruckStore()
    profile = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500)

    store.save(profile)

    assert store.list() == [profile]


def test_save_assigns_an_id() -> None:
    store = InMemoryTruckStore()
    profile = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500)

    store.save(profile)

    [saved] = store.list()
    assert saved.id is not None


def test_save_assigns_distinct_ids_to_successive_profiles() -> None:
    store = InMemoryTruckStore()
    store.save(TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900))
    store.save(TruckProfile(gvwr=10000, front_gawr=5000, rear_gawr=6000))

    ids = [profile.id for profile in store.list()]

    assert len(ids) == len(set(ids))


def test_update_replaces_profile_with_matching_id() -> None:
    store = InMemoryTruckStore()
    store.save(TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500))
    [saved] = store.list()

    updated = replace(saved, gvwr=15000)
    store.update(updated)

    assert store.list() == [updated]
    [result] = store.list()
    assert result.gvwr == 15000


def test_delete_removes_profile_with_matching_id() -> None:
    store = InMemoryTruckStore()
    store.save(TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900))
    store.save(TruckProfile(gvwr=10000, front_gawr=5000, rear_gawr=6000))
    [first, second] = store.list()
    assert first.id is not None

    store.delete(first.id)

    assert store.list() == [second]


# --- Nickname (#12) ----------------------------------------------------------


def test_save_and_list_round_trips_nickname() -> None:
    store = InMemoryTruckStore()
    profile = TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, nickname="Addie"
    )

    store.save(profile)

    [saved] = store.list()
    assert saved.nickname == "Addie"


def test_save_and_list_round_trips_no_nickname() -> None:
    store = InMemoryTruckStore()
    store.save(TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900))

    [saved] = store.list()
    assert saved.nickname is None
