from pathlib import Path

from towing_app.models import TrailerProfile
from towing_app.storage import SqliteTrailerStore


def test_save_and_list_persists_across_store_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    profile = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)

    SqliteTrailerStore(db_path).save(profile)

    assert SqliteTrailerStore(db_path).list() == [profile]
