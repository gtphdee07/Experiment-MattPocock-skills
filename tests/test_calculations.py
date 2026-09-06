from towing_app.calculations import (
    TrailerGvwrOverloadResult,
    check_axle_overload,
    check_gcwr_overload,
    check_hitched_gvwr_overload,
    check_time_gap,
    check_trailer_gvwr_overload,
    compute_derived_trailer_weight,
)
from towing_app.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile

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


def test_gcwr_overload_worked_example_is_overloaded() -> None:
    # TRUCK's GCWR is 32500; the worked-example Gross Weight of 34400
    # exceeds it.
    ticket = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)

    result = check_gcwr_overload(TRUCK, ticket)

    assert result is not None
    assert result.combined_actual == 34400
    assert result.gcwr_rating == 32500
    assert result.is_overloaded is True


def test_gcwr_overload_not_triggered_when_under_gcwr() -> None:
    ticket = CombinedTicket(steer=5000, drive=8000, trailer_axle=15000, gross=28000)

    result = check_gcwr_overload(TRUCK, ticket)

    assert result is not None
    assert result.combined_actual == 28000
    assert result.is_overloaded is False


def test_gcwr_overload_exact_match_to_gcwr_is_not_overloaded() -> None:
    ticket = CombinedTicket(steer=5000, drive=8000, trailer_axle=19500, gross=32500)

    result = check_gcwr_overload(TRUCK, ticket)

    assert result is not None
    assert result.combined_actual == 32500
    assert result.is_overloaded is False


def test_gcwr_overload_ignores_individual_axle_readings() -> None:
    # GCWR Overload compares against the Combined Ticket's Gross Weight only
    # - it must not be recomputed from the individual axle readings.
    ticket = CombinedTicket(steer=1, drive=1, trailer_axle=1, gross=34400)

    result = check_gcwr_overload(TRUCK, ticket)

    assert result is not None
    assert result.combined_actual == 34400


def test_gcwr_overload_not_evaluated_when_no_gcwr_on_file() -> None:
    # See CONTEXT.md: GCWR Overload / ADR 0002 - GCWR is optional on the
    # Truck Profile, so this must be a distinct "not evaluated" state, never
    # a silent pass.
    truck_without_gcwr = TruckProfile(
        gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=None
    )
    ticket = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)

    result = check_gcwr_overload(truck_without_gcwr, ticket)

    assert result is None


# --- Derived Trailer Weight --------------------------------------------------


def test_derived_trailer_weight_subtracts_solo_gross_from_combined_gross() -> None:
    combined = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)
    solo = SoloTicket(steer=5000, drive=9720, gross=14720)

    result = compute_derived_trailer_weight(combined, solo)

    assert result == 19680


def test_derived_trailer_weight_can_be_negative_for_a_bad_pairing() -> None:
    # A negative result signals a mismatched/erroneous pairing rather than a
    # real trailer weight - the pure function still just does the math and
    # leaves any "does this look right" judgment to the caller.
    combined = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=14720)
    solo = SoloTicket(steer=5000, drive=9720, gross=34400)

    result = compute_derived_trailer_weight(combined, solo)

    assert result == -19680


# --- Trailer GVWR Overload ----------------------------------------------------


def test_trailer_gvwr_overload_not_evaluated_when_no_linked_solo_ticket() -> None:
    # See CONTEXT.md: Trailer GVWR Overload - not evaluated without a linked
    # Solo Ticket to derive Trailer Weight from, mirroring the "not
    # evaluated" shape of check_gcwr_overload (see ADR 0002).
    combined = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)

    result = check_trailer_gvwr_overload(TRAILER, combined, None)

    assert result is None


def test_trailer_gvwr_overload_worked_example_is_overloaded() -> None:
    # TRAILER's GVWR is 23500; a Derived Trailer Weight of 24000 exceeds it.
    combined = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=38720)
    solo = SoloTicket(steer=5000, drive=9720, gross=14720)

    result = check_trailer_gvwr_overload(TRAILER, combined, solo)

    assert result is not None
    assert result.derived_trailer_weight == 24000
    assert result.gvwr_rating == 23500
    assert result.is_overloaded is True


def test_trailer_gvwr_overload_not_triggered_when_under_gvwr() -> None:
    combined = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)
    solo = SoloTicket(steer=5000, drive=9720, gross=14720)

    result = check_trailer_gvwr_overload(TRAILER, combined, solo)

    assert result is not None
    assert result.derived_trailer_weight == 19680
    assert result.is_overloaded is False


def test_trailer_gvwr_overload_exact_match_to_gvwr_is_not_overloaded() -> None:
    combined = CombinedTicket(steer=5640, drive=9080, trailer_axle=23500, gross=38220)
    solo = SoloTicket(steer=5000, drive=9720, gross=14720)

    result = check_trailer_gvwr_overload(TRAILER, combined, solo)

    assert result is not None
    assert result.derived_trailer_weight == 23500
    assert result.is_overloaded is False


# --- Trailer GVWR Overload: Unverified Value (#16, see ADR 0006) ------------


def test_trailer_gvwr_overload_is_not_unverified_by_default() -> None:
    # A fresh or reused-unchanged Solo Ticket is a trusted reading - not an
    # Unverified Value (see ADR 0006).
    combined = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)
    solo = SoloTicket(steer=5000, drive=9720, gross=14720)

    result = check_trailer_gvwr_overload(TRAILER, combined, solo)

    assert result is not None
    assert result.is_unverified is False


def test_trailer_gvwr_overload_is_unverified_when_solo_is_unverified() -> None:
    # When the caller reports the Solo Ticket's weight came from a
    # manually-adjusted reuse, the resulting Trailer GVWR Overload result is
    # an Unverified Value (see CONTEXT.md: Unverified Value; ADR 0006).
    combined = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)
    solo = SoloTicket(steer=5000, drive=9720, gross=14720)

    result = check_trailer_gvwr_overload(
        TRAILER, combined, solo, solo_is_unverified=True
    )

    assert result is not None
    assert result.is_unverified is True


def test_trailer_gvwr_overload_result_defaults_to_not_unverified() -> None:
    # Direct construction (as used elsewhere, e.g. Weigh Event history
    # reconstruction) defaults to trusted/not-Unverified.
    result = TrailerGvwrOverloadResult(derived_trailer_weight=19680, gvwr_rating=23500)

    assert result.is_unverified is False


# --- Trailer GVWR Overload: near-limit flagging (#14, see ADR 0006) ----------


def test_trailer_gvwr_overload_flagged_near_limit_when_exactly_100_under() -> None:
    # Boundary inclusive - exactly 100 lbs under counts as flagged.
    result = TrailerGvwrOverloadResult(derived_trailer_weight=23400, gvwr_rating=23500)

    assert result.is_overloaded is False
    assert result.is_near_limit is True


def test_trailer_gvwr_overload_flagged_near_limit_when_exact_match_to_gvwr() -> None:
    # Exactly at the rating (0 lbs of margin) is still "under", not over.
    result = TrailerGvwrOverloadResult(derived_trailer_weight=23500, gvwr_rating=23500)

    assert result.is_overloaded is False
    assert result.is_near_limit is True


def test_trailer_gvwr_overload_not_flagged_near_limit_when_comfortably_under() -> None:
    # 101 lbs under - just outside the 100 lb margin.
    result = TrailerGvwrOverloadResult(derived_trailer_weight=23399, gvwr_rating=23500)

    assert result.is_overloaded is False
    assert result.is_near_limit is False


def test_trailer_gvwr_overload_never_flagged_near_limit_when_barely_over() -> None:
    # Only 1 lb over the limit - despite the tiny margin, being over is
    # reported as overloaded, full stop, with no "close" qualifier layered on
    # top (see ADR 0006: the flag never fires on the over-the-limit side).
    result = TrailerGvwrOverloadResult(derived_trailer_weight=23501, gvwr_rating=23500)

    assert result.is_overloaded is True
    assert result.is_near_limit is False


def test_trailer_gvwr_overload_never_flagged_near_limit_when_far_over() -> None:
    result = TrailerGvwrOverloadResult(derived_trailer_weight=30000, gvwr_rating=23500)

    assert result.is_overloaded is True
    assert result.is_near_limit is False


# --- Time-Gap Warning ---------------------------------------------------------


def test_time_gap_warning_does_not_exceed_threshold_within_default_window() -> None:
    result = check_time_gap(3.5)

    assert result.gap_hours == 3.5
    assert result.threshold_hours == 4.0
    assert result.exceeds_threshold is False


def test_time_gap_warning_exceeds_default_threshold() -> None:
    result = check_time_gap(4.5)

    assert result.exceeds_threshold is True


def test_time_gap_warning_exact_match_to_threshold_does_not_exceed() -> None:
    result = check_time_gap(4.0)

    assert result.exceeds_threshold is False


def test_time_gap_warning_respects_a_custom_threshold() -> None:
    result = check_time_gap(2.5, threshold_hours=2.0)

    assert result.exceeds_threshold is True


def test_time_gap_warning_uses_absolute_value_of_the_gap() -> None:
    # A Solo Ticket weighed *before* the Combined Ticket is still a gap - the
    # sign of the input shouldn't matter, only its magnitude.
    result = check_time_gap(-5.0)

    assert result.exceeds_threshold is True
