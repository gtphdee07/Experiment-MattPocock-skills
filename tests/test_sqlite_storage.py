from dataclasses import replace
from pathlib import Path

from towing_app.models import TruckProfile
from towing_app.storage import SqliteTruckStore


def test_save_and_list_persists_across_store_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    profile = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500)

    SqliteTruckStore(db_path).save(profile)

    assert SqliteTruckStore(db_path).list() == [profile]


def test_save_assigns_an_id(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    profile = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500)

    SqliteTruckStore(db_path).save(profile)

    [saved] = SqliteTruckStore(db_path).list()
    assert saved.id is not None


def test_update_persists_changes_across_store_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    store = SqliteTruckStore(db_path)
    store.save(TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500))
    [saved] = store.list()

    updated = replace(saved, gvwr=15000)
    SqliteTruckStore(db_path).update(updated)

    assert SqliteTruckStore(db_path).list() == [updated]
    [result] = SqliteTruckStore(db_path).list()
    assert result.gvwr == 15000


def test_delete_removes_profile_across_store_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    store = SqliteTruckStore(db_path)
    store.save(TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900))
    store.save(TruckProfile(gvwr=10000, front_gawr=5000, rear_gawr=6000))
    [first, second] = store.list()
    assert first.id is not None

    SqliteTruckStore(db_path).delete(first.id)

    assert SqliteTruckStore(db_path).list() == [second]


# --- Nickname (#12) ----------------------------------------------------------


def test_save_and_list_round_trips_nickname(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    profile = TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, nickname="Addie"
    )

    SqliteTruckStore(db_path).save(profile)

    [saved] = SqliteTruckStore(db_path).list()
    assert saved.nickname == "Addie"


def test_save_and_list_round_trips_no_nickname(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    SqliteTruckStore(db_path).save(
        TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900)
    )

    [saved] = SqliteTruckStore(db_path).list()
    assert saved.nickname is None


def test_update_persists_nickname_across_store_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    store = SqliteTruckStore(db_path)
    store.save(TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900))
    [saved] = store.list()

    updated = replace(saved, nickname="Addie")
    SqliteTruckStore(db_path).update(updated)

    [result] = SqliteTruckStore(db_path).list()
    assert result.nickname == "Addie"
