from towing_core.calculations import (
    AxleCheckResult,
    HitchedGvwrOverloadResult,
    TrailerGvwrOverloadResult,
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
