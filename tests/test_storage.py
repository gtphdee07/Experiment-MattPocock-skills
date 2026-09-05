from towing_app.models import TruckProfile
from towing_app.storage import InMemoryTruckStore


def test_save_and_list_returns_saved_truck_profile() -> None:
    store = InMemoryTruckStore()
    profile = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500)

    store.save(profile)

    assert store.list() == [profile]
