from towing_app.models import TrailerProfile
from towing_app.storage import InMemoryTrailerStore


def test_save_and_list_returns_saved_trailer_profile() -> None:
    store = InMemoryTrailerStore()
    profile = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)

    store.save(profile)

    assert store.list() == [profile]
