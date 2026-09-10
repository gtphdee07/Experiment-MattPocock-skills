from towing_core.calculations import (
    AxleCheckResult,
    GcwrOverloadResult,
    HitchedGvwrOverloadResult,
    TimeGapWarningResult,
    TrailerGvwrOverloadResult,
    check_axle_overload,
    check_gcwr_overload,
    check_hitched_gvwr_overload,
    check_trailer_gvwr_overload,
)
from towing_core.evaluation import (
    OverloadStatus,
    evaluate_weigh_event,
    status_for,
)
from towing_core.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile

TRUCK = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500)
TRUCK_NO_GCWR = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=None)
TRAILER = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)


def test_status_for_none_is_not_evaluated() -> None:
    assert status_for(None) == OverloadStatus.NOT_EVALUATED


def test_status_for_axle_check_result_fail_and_pass() -> None:
    overloaded = AxleCheckResult(axle_name="Drive Axle", actual=10000, rating=9900)
    clear = AxleCheckResult(axle_name="Steer Axle", actual=5000, rating=6000)

    assert status_for(overloaded) == OverloadStatus.FAIL
    assert status_for(clear) == OverloadStatus.PASS


def test_status_for_hitched_gvwr_result_fail_and_pass() -> None:
    overloaded = HitchedGvwrOverloadResult(combined_actual=15000, gvwr_rating=14000)
    clear = HitchedGvwrOverloadResult(combined_actual=13000, gvwr_rating=14000)

    assert status_for(overloaded) == OverloadStatus.FAIL
    assert status_for(clear) == OverloadStatus.PASS


def test_status_for_trailer_gvwr_near_limit() -> None:
    near = TrailerGvwrOverloadResult(derived_trailer_weight=23450, gvwr_rating=23500)

    assert near.is_overloaded is False
    assert status_for(near) == OverloadStatus.NEAR_LIMIT


def test_evaluate_weigh_event_folds_each_check() -> None:
    # Drive axle 10000 > 9900 -> FAIL; steer 5000 <= 6000 -> PASS.
    # Gross 33000 > 32500 GCWR -> FAIL.
    # Derived Trailer Weight 33000 - 9580 = 23420, i.e. 80 lb under the
    # 23500 GVWR (within the trusted 100 lb margin) -> NEAR_LIMIT.
    combined = CombinedTicket(steer=5000, drive=10000, trailer_axle=19000, gross=33000)
    solo = SoloTicket(steer=5000, drive=4580, gross=9580)

    result = evaluate_weigh_event(TRUCK, TRAILER, combined, solo)

    assert result.drive_axle.status == OverloadStatus.FAIL
    assert result.steer_axle.status == OverloadStatus.PASS
    assert result.gcwr.status == OverloadStatus.FAIL
    assert result.trailer_gvwr.status == OverloadStatus.NEAR_LIMIT
    assert result.overall_status == OverloadStatus.FAIL


def test_evaluate_weigh_event_gcwr_not_evaluated_without_gcwr_on_file() -> None:
    combined = CombinedTicket(steer=5000, drive=9000, trailer_axle=19000, gross=30000)

    result = evaluate_weigh_event(TRUCK_NO_GCWR, TRAILER, combined)

    assert result.gcwr.status == OverloadStatus.NOT_EVALUATED


def test_evaluate_weigh_event_trailer_gvwr_not_evaluated_without_solo() -> None:
    combined = CombinedTicket(steer=5000, drive=9000, trailer_axle=19000, gross=30000)

    result = evaluate_weigh_event(TRUCK, TRAILER, combined, solo=None)

    assert result.trailer_gvwr.status == OverloadStatus.NOT_EVALUATED


# --- status_for for GcwrOverloadResult ---------------------------------------


def test_status_for_gcwr_result_fail_and_pass() -> None:
    overloaded = GcwrOverloadResult(combined_actual=33000, gcwr_rating=32500)
    clear = GcwrOverloadResult(combined_actual=30000, gcwr_rating=32500)

    assert status_for(overloaded) == OverloadStatus.FAIL
    assert status_for(clear) == OverloadStatus.PASS


# --- NEAR_LIMIT margin boundaries ------------------------------------------------


def test_status_for_trailer_gvwr_trusted_margin_boundary() -> None:
    # Exactly at the 100 lb trusted margin -> NEAR_LIMIT (boundary inclusive).
    at_margin = TrailerGvwrOverloadResult(
        derived_trailer_weight=23400, gvwr_rating=23500, is_unverified=False
    )
    # One pound further under (101 lb) -> PASS.
    just_clear = TrailerGvwrOverloadResult(
        derived_trailer_weight=23399, gvwr_rating=23500, is_unverified=False
    )

    assert (23500 - 23400) == 100
    assert status_for(at_margin) == OverloadStatus.NEAR_LIMIT
    assert status_for(just_clear) == OverloadStatus.PASS


def test_evaluate_threads_solo_is_unverified_into_wider_margin() -> None:
    # Derived Trailer Weight 30000 - 6750 = 23250, i.e. 250 lb under the
    # 23500 GVWR: inside the 300 lb Unverified margin, outside the 100 lb
    # trusted margin.
    combined = CombinedTicket(steer=5000, drive=9000, trailer_axle=16000, gross=30000)
    solo = SoloTicket(steer=5000, drive=1750, gross=6750)

    unverified = evaluate_weigh_event(
        TRUCK, TRAILER, combined, solo, solo_is_unverified=True
    )
    trusted = evaluate_weigh_event(
        TRUCK, TRAILER, combined, solo, solo_is_unverified=False
    )

    assert unverified.trailer_gvwr.status == OverloadStatus.NEAR_LIMIT
    assert trusted.trailer_gvwr.status == OverloadStatus.PASS


# --- overall_status precedence -------------------------------------------------


def test_overall_status_near_limit_outranks_not_evaluated() -> None:
    # Derived Trailer Weight 30000 - 6550 = 23450 -> 50 lb under 23500 GVWR
    # -> NEAR_LIMIT. TRUCK_NO_GCWR -> gcwr NOT_EVALUATED. Every other check PASS.
    combined = CombinedTicket(steer=5000, drive=9000, trailer_axle=16000, gross=30000)
    solo = SoloTicket(steer=5000, drive=1550, gross=6550)

    rig = evaluate_weigh_event(TRUCK_NO_GCWR, TRAILER, combined, solo)

    assert rig.trailer_gvwr.status == OverloadStatus.NEAR_LIMIT
    assert rig.gcwr.status == OverloadStatus.NOT_EVALUATED
    assert rig.overall_status == OverloadStatus.NEAR_LIMIT


def test_overall_status_not_evaluated_when_that_is_the_only_gap() -> None:
    combined = CombinedTicket(steer=5000, drive=9000, trailer_axle=16000, gross=30000)
    solo = SoloTicket(steer=5000, drive=5000, gross=10000)

    rig = evaluate_weigh_event(TRUCK_NO_GCWR, TRAILER, combined, solo)

    assert rig.gcwr.status == OverloadStatus.NOT_EVALUATED
    assert rig.overall_status == OverloadStatus.NOT_EVALUATED


def test_overall_status_pass_when_every_check_clears() -> None:
    combined = CombinedTicket(steer=5000, drive=9000, trailer_axle=16000, gross=30000)
    solo = SoloTicket(steer=5000, drive=5000, gross=10000)

    rig = evaluate_weigh_event(TRUCK, TRAILER, combined, solo)

    assert rig.overall_status == OverloadStatus.PASS


# --- time_gap wiring ----------------------------------------------------------


def test_evaluate_time_gap_none_yields_no_result() -> None:
    combined = CombinedTicket(steer=5000, drive=9000, trailer_axle=16000, gross=30000)

    rig = evaluate_weigh_event(TRUCK, TRAILER, combined, time_gap_hours=None)

    assert rig.time_gap_result is None


def test_evaluate_time_gap_exceeds_default_threshold() -> None:
    combined = CombinedTicket(steer=5000, drive=9000, trailer_axle=16000, gross=30000)

    rig = evaluate_weigh_event(TRUCK, TRAILER, combined, time_gap_hours=6.0)

    assert isinstance(rig.time_gap_result, TimeGapWarningResult)
    assert rig.time_gap_result.gap_hours == 6.0
    assert rig.time_gap_result.exceeds_threshold is True


def test_evaluate_time_gap_within_custom_threshold() -> None:
    combined = CombinedTicket(steer=5000, drive=9000, trailer_axle=16000, gross=30000)

    rig = evaluate_weigh_event(
        TRUCK, TRAILER, combined, time_gap_hours=6.0, time_gap_threshold_hours=8.0
    )

    assert isinstance(rig.time_gap_result, TimeGapWarningResult)
    assert rig.time_gap_result.exceeds_threshold is False


# --- EvaluatedCheck payload --------------------------------------------------


def test_evaluated_check_payload_carries_actuals_ratings_and_notes() -> None:
    combined = CombinedTicket(steer=5000, drive=9000, trailer_axle=16000, gross=30000)

    rig = evaluate_weigh_event(TRUCK_NO_GCWR, TRAILER, combined, solo=None)

    assert rig.steer_axle.actual == combined.steer
    assert rig.steer_axle.rating == TRUCK_NO_GCWR.front_gawr
    assert rig.hitched_gvwr.actual == combined.steer + combined.drive
    assert rig.hitched_gvwr.rating == TRUCK_NO_GCWR.gvwr
    assert rig.gcwr.actual is None
    assert rig.gcwr.rating is None
    assert rig.gcwr.note
    assert rig.trailer_gvwr.actual is None
    assert rig.trailer_gvwr.rating is None
    assert rig.trailer_gvwr.note


# --- equivalence spot-check --------------------------------------------------


def test_evaluate_carries_through_the_exact_check_results() -> None:
    combined = CombinedTicket(steer=5000, drive=9000, trailer_axle=16000, gross=30000)
    solo = SoloTicket(steer=5000, drive=5000, gross=10000)

    rig = evaluate_weigh_event(TRUCK, TRAILER, combined, solo)

    assert rig.axle_result == check_axle_overload(TRUCK, TRAILER, combined)
    assert rig.hitched_gvwr_result == check_hitched_gvwr_overload(TRUCK, combined)
    assert rig.gcwr_result == check_gcwr_overload(TRUCK, combined)
    assert rig.trailer_gvwr_result == check_trailer_gvwr_overload(
        TRAILER, combined, solo, solo_is_unverified=False
    )
