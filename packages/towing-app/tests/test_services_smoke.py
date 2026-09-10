from towing_app.services import Problem, record_weigh_event
from towing_core.evaluation import RigEvaluation
from towing_core.models import CombinedTicket, TrailerProfile, TruckProfile
from towing_core.storage import InMemoryWeighEventStore, WeighEventRecord

TRUCK = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500, id=1)
TRAILER = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554, id=2)
COMBINED = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)


def _fixed_now() -> str:
    return "2026-01-01T00:00:00+00:00"


def test_record_weigh_event_evaluates_and_persists() -> None:
    store = InMemoryWeighEventStore()

    result = record_weigh_event(
        TRUCK,
        TRAILER,
        COMBINED,
        None,
        solo_is_unverified=False,
        time_gap_hours=None,
        reused_solo_from_timestamp=None,
        weigh_event_store=store,
        now=_fixed_now,
    )

    assert isinstance(result, tuple)
    evaluation, record = result
    assert isinstance(evaluation, RigEvaluation)
    assert isinstance(record, WeighEventRecord)
    assert record.timestamp == "2026-01-01T00:00:00+00:00"
    # Nickname-less Truck -> computed default snapshot.
    assert record.truck_nickname == "Truck 1"
    assert record.trailer_nickname == "Trailer 2"

    [saved] = store.list()
    assert saved.truck_id == 1
    assert saved.trailer_id == 2


def test_record_weigh_event_returns_problem_list_when_truck_missing() -> None:
    store = InMemoryWeighEventStore()

    result = record_weigh_event(
        None,
        TRAILER,
        COMBINED,
        None,
        solo_is_unverified=False,
        time_gap_hours=None,
        reused_solo_from_timestamp=None,
        weigh_event_store=store,
        now=_fixed_now,
    )

    assert isinstance(result, list)
    assert result == [
        Problem(
            "no_truck_profiles",
            "No Truck Profiles saved yet. Add one with 'truck add' first.",
        )
    ]
    assert store.list() == []
