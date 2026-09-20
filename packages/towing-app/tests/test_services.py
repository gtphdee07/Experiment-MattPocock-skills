from towing_app.services import Problem, record_weigh_event
from towing_core.evaluation import RigEvaluation, evaluate_weigh_event
from towing_core.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile
from towing_core.storage import InMemoryWeighEventStore, WeighEventRecord

TRUCK = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500, id=1)
TRAILER = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554, id=2)
COMBINED = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)
SOLO = SoloTicket(steer=5600, drive=4400, gross=10000)


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


def test_record_snapshots_computed_default_nicknames() -> None:
    store = InMemoryWeighEventStore()
    truck = TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500, nickname=None, id=3
    )
    trailer = TrailerProfile(
        gvwr=23500, gawr=8000, axle_count=3, uvw=20554, nickname=None, id=7
    )

    result = record_weigh_event(
        truck,
        trailer,
        COMBINED,
        None,
        solo_is_unverified=False,
        time_gap_hours=None,
        reused_solo_from_timestamp=None,
        weigh_event_store=store,
        now=_fixed_now,
    )

    assert isinstance(result, tuple)
    _, record = result
    assert record.truck_nickname == "Truck 3"
    assert record.trailer_nickname == "Trailer 7"


def test_record_returns_problem_list_when_trailer_missing() -> None:
    store = InMemoryWeighEventStore()

    result = record_weigh_event(
        TRUCK,
        None,
        COMBINED,
        None,
        solo_is_unverified=False,
        time_gap_hours=None,
        reused_solo_from_timestamp=None,
        weigh_event_store=store,
        now=_fixed_now,
    )

    assert result == [
        Problem(
            "no_trailer_profiles",
            "No Trailer Profiles saved yet. Add one with 'trailer add' first.",
        )
    ]
    assert store.list() == []


def test_record_returns_problem_list_when_profile_unsaved() -> None:
    store = InMemoryWeighEventStore()
    unsaved_truck = TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500
    )

    result = record_weigh_event(
        unsaved_truck,
        TRAILER,
        COMBINED,
        None,
        solo_is_unverified=False,
        time_gap_hours=None,
        reused_solo_from_timestamp=None,
        weigh_event_store=store,
        now=_fixed_now,
    )

    assert result == [
        Problem(
            "profile_missing_id",
            "Selected Profile has not been saved yet - save it before "
            "recording a Weigh Event.",
        )
    ]
    assert store.list() == []


def test_record_threads_solo_is_unverified_onto_record() -> None:
    store = InMemoryWeighEventStore()

    result = record_weigh_event(
        TRUCK,
        TRAILER,
        COMBINED,
        SOLO,
        solo_is_unverified=True,
        time_gap_hours=None,
        reused_solo_from_timestamp=None,
        weigh_event_store=store,
        now=_fixed_now,
    )

    assert isinstance(result, tuple)
    _, record = result
    assert record.reused_solo_is_unverified is True
    assert record.trailer_gvwr_result is not None
    assert record.trailer_gvwr_result.is_unverified is True


def test_record_persists_time_gap_hours() -> None:
    store = InMemoryWeighEventStore()

    result = record_weigh_event(
        TRUCK,
        TRAILER,
        COMBINED,
        SOLO,
        solo_is_unverified=False,
        time_gap_hours=5.0,
        reused_solo_from_timestamp=None,
        weigh_event_store=store,
        now=_fixed_now,
    )

    assert isinstance(result, tuple)
    _, record = result
    assert record.time_gap_hours == 5.0


def test_record_time_gap_hours_is_none_without_solo() -> None:
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
    _, record = result
    assert record.time_gap_hours is None


def test_record_round_trips_reused_solo_from_timestamp() -> None:
    store = InMemoryWeighEventStore()

    result = record_weigh_event(
        TRUCK,
        TRAILER,
        COMBINED,
        SOLO,
        solo_is_unverified=False,
        time_gap_hours=None,
        reused_solo_from_timestamp="2025-12-31T12:00:00+00:00",
        weigh_event_store=store,
        now=_fixed_now,
    )

    assert isinstance(result, tuple)
    _, record = result
    assert record.reused_solo_from_timestamp == "2025-12-31T12:00:00+00:00"


# --- Issue #45 / ADR 0017: One-Off Truck/Trailer ----------------------------


def test_record_allows_one_off_truck_with_no_id() -> None:
    """A One-Off Truck (`truck_is_one_off=True`) is exempt from the
    "profile_missing_id" precondition above - its `id` is `None` by
    definition (ADR 0017: never saved as a real Truck Profile), not a sign
    of a caller bug."""
    store = InMemoryWeighEventStore()
    one_off_truck = TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500
    )

    result = record_weigh_event(
        one_off_truck,
        TRAILER,
        COMBINED,
        None,
        solo_is_unverified=False,
        time_gap_hours=None,
        reused_solo_from_timestamp=None,
        weigh_event_store=store,
        now=_fixed_now,
        truck_is_one_off=True,
    )

    assert isinstance(result, tuple)
    _, record = result
    assert record.truck_id is None
    assert record.trailer_id == 2
    # No ID to compute a "Truck N" fallback from - a distinct fallback,
    # per CONTEXT.md's One-Off Truck entry.
    assert record.truck_nickname == "One-Off Truck"

    [saved] = store.list()
    assert saved.truck_id is None


def test_record_allows_one_off_trailer_with_no_id() -> None:
    store = InMemoryWeighEventStore()
    one_off_trailer = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3)

    result = record_weigh_event(
        TRUCK,
        one_off_trailer,
        COMBINED,
        None,
        solo_is_unverified=False,
        time_gap_hours=None,
        reused_solo_from_timestamp=None,
        weigh_event_store=store,
        now=_fixed_now,
        trailer_is_one_off=True,
    )

    assert isinstance(result, tuple)
    _, record = result
    assert record.trailer_id is None
    assert record.trailer_nickname == "One-Off Trailer"


def test_record_one_off_truck_uses_given_nickname_when_present() -> None:
    """A One-Off Truck's own Nickname (Story 3) is stored as given - it
    never gets the ID-derived fallback ("Truck N"), since there is no ID."""
    store = InMemoryWeighEventStore()
    one_off_truck = TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, nickname="Borrowed Bertha"
    )

    result = record_weigh_event(
        one_off_truck,
        TRAILER,
        COMBINED,
        None,
        solo_is_unverified=False,
        time_gap_hours=None,
        reused_solo_from_timestamp=None,
        weigh_event_store=store,
        now=_fixed_now,
        truck_is_one_off=True,
    )

    assert isinstance(result, tuple)
    _, record = result
    assert record.truck_nickname == "Borrowed Bertha"


def test_record_both_sides_one_off() -> None:
    store = InMemoryWeighEventStore()
    one_off_truck = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900)
    one_off_trailer = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3)

    result = record_weigh_event(
        one_off_truck,
        one_off_trailer,
        COMBINED,
        None,
        solo_is_unverified=False,
        time_gap_hours=None,
        reused_solo_from_timestamp=None,
        weigh_event_store=store,
        now=_fixed_now,
        truck_is_one_off=True,
        trailer_is_one_off=True,
    )

    assert isinstance(result, tuple)
    _, record = result
    assert record.truck_id is None
    assert record.trailer_id is None

    [saved] = store.list()
    assert saved.truck_id is None
    assert saved.trailer_id is None


def test_record_returns_the_same_evaluation_as_evaluate_weigh_event() -> None:
    store = InMemoryWeighEventStore()

    result = record_weigh_event(
        TRUCK,
        TRAILER,
        COMBINED,
        SOLO,
        solo_is_unverified=False,
        time_gap_hours=5.0,
        reused_solo_from_timestamp=None,
        weigh_event_store=store,
        now=_fixed_now,
    )

    assert isinstance(result, tuple)
    evaluation, _ = result
    expected = evaluate_weigh_event(
        TRUCK,
        TRAILER,
        COMBINED,
        SOLO,
        solo_is_unverified=False,
        time_gap_hours=5.0,
    )
    assert evaluation.overall_status == expected.overall_status
    assert evaluation == expected
