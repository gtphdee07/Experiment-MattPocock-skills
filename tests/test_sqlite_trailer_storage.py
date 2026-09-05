from dataclasses import replace
from pathlib import Path

from towing_app.models import TrailerProfile
from towing_app.storage import SqliteTrailerStore


def test_save_and_list_persists_across_store_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    profile = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)

    SqliteTrailerStore(db_path).save(profile)

    assert SqliteTrailerStore(db_path).list() == [profile]


def test_save_assigns_an_id(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    profile = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)

    SqliteTrailerStore(db_path).save(profile)

    [saved] = SqliteTrailerStore(db_path).list()
    assert saved.id is not None


def test_update_persists_changes_across_store_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    store = SqliteTrailerStore(db_path)
    store.save(TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554))
    [saved] = store.list()

    updated = replace(saved, gvwr=24000)
    SqliteTrailerStore(db_path).update(updated)

    assert SqliteTrailerStore(db_path).list() == [updated]
    [result] = SqliteTrailerStore(db_path).list()
    assert result.gvwr == 24000


def test_delete_removes_profile_across_store_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    store = SqliteTrailerStore(db_path)
    store.save(TrailerProfile(gvwr=23500, gawr=8000, axle_count=3))
    store.save(TrailerProfile(gvwr=10000, gawr=4000, axle_count=2))
    [first, second] = store.list()
    assert first.id is not None

    SqliteTrailerStore(db_path).delete(first.id)

    assert SqliteTrailerStore(db_path).list() == [second]
