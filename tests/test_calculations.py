from towing_app.calculations import (
    check_axle_overload,
    check_hitched_gvwr_overload,
)
from towing_app.models import CombinedTicket, TrailerProfile, TruckProfile

TRUCK = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500)
TRAILER = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)


def test_axle_overload_reports_group_rating_for_each_axle() -> None:
    ticket = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)

    result = check_axle_overload(TRUCK, TRAILER, ticket)

    assert result.steer.actual == 5640
    assert result.steer.rating == 6000
    assert result.drive.actual == 9080
    assert result.drive.rating == 9900
    assert result.trailer.actual == 19680
    assert result.trailer.rating == 24000  # 8000 per-axle GAWR * 3 axles


def test_axle_overload_worked_example_has_no_overload() -> None:
    ticket = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)

    result = check_axle_overload(TRUCK, TRAILER, ticket)

    assert result.steer.is_overloaded is False
    assert result.drive.is_overloaded is False
    assert result.trailer.is_overloaded is False
    assert result.any_overloaded is False


def test_axle_overload_detects_steer_axle_overload() -> None:
    ticket = CombinedTicket(steer=6001, drive=9080, trailer_axle=19680, gross=34400)

    result = check_axle_overload(TRUCK, TRAILER, ticket)

    assert result.steer.is_overloaded is True
    assert result.drive.is_overloaded is False
    assert result.trailer.is_overloaded is False
    assert result.any_overloaded is True


def test_axle_overload_detects_drive_axle_overload() -> None:
    ticket = CombinedTicket(steer=5640, drive=9901, trailer_axle=19680, gross=34400)

    result = check_axle_overload(TRUCK, TRAILER, ticket)

    assert result.drive.is_overloaded is True
    assert result.any_overloaded is True


def test_axle_overload_detects_trailer_axle_group_overload() -> None:
    # 24001 exceeds the 24000 group rating (8000 * 3), even though it would
    # look fine against the raw per-axle GAWR of 8000.
    ticket = CombinedTicket(steer=5640, drive=9080, trailer_axle=24001, gross=38721)

    result = check_axle_overload(TRUCK, TRAILER, ticket)

    assert result.trailer.is_overloaded is True
    assert result.any_overloaded is True


def test_axle_overload_exact_match_to_rating_is_not_overloaded() -> None:
    ticket = CombinedTicket(steer=6000, drive=9900, trailer_axle=24000, gross=39900)

    result = check_axle_overload(TRUCK, TRAILER, ticket)

    assert result.steer.is_overloaded is False
    assert result.drive.is_overloaded is False
    assert result.trailer.is_overloaded is False


def test_hitched_gvwr_overload_worked_example_is_overloaded() -> None:
    ticket = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)

    result = check_hitched_gvwr_overload(TRUCK, ticket)

    assert result.combined_actual == 14720
    assert result.gvwr_rating == 14000
    assert result.is_overloaded is True


def test_hitched_gvwr_overload_not_triggered_when_under_gvwr() -> None:
    ticket = CombinedTicket(steer=5000, drive=8000, trailer_axle=19680, gross=32680)

    result = check_hitched_gvwr_overload(TRUCK, ticket)

    assert result.combined_actual == 13000
    assert result.is_overloaded is False


def test_hitched_gvwr_overload_exact_match_to_gvwr_is_not_overloaded() -> None:
    ticket = CombinedTicket(steer=6000, drive=8000, trailer_axle=19680, gross=33680)

    result = check_hitched_gvwr_overload(TRUCK, ticket)

    assert result.combined_actual == 14000
    assert result.is_overloaded is False


def test_hitched_gvwr_overload_ignores_trailer_axle_weight() -> None:
    # Hitched GVWR Overload only concerns the tow vehicle's own axle groups
    # (Steer + Drive) - the Trailer Axle reading must not factor in.
    ticket = CombinedTicket(steer=5640, drive=9080, trailer_axle=999999, gross=1014719)

    result = check_hitched_gvwr_overload(TRUCK, ticket)

    assert result.combined_actual == 14720
