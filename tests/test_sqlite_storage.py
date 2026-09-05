from pathlib import Path

from towing_app.models import TruckProfile
from towing_app.storage import SqliteTruckStore


def test_save_and_list_persists_across_store_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    profile = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500)

    SqliteTruckStore(db_path).save(profile)

    assert SqliteTruckStore(db_path).list() == [profile]
