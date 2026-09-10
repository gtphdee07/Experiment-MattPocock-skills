"""Evaluate-level regression for the Streamlit results grid.

No Streamlit runtime: these assert the ``OverloadStatus`` each coloured box
would take for a known rig, straight from ``evaluate_weigh_event``, plus that
the colour / label maps cover every status. The wizard's own rendering is a
thin ``st.markdown`` shell over ``towing_streamlit.results`` and this logic.
"""

from towing_core.calculations import TRAILER_GVWR_NEAR_LIMIT_MARGIN_LBS
from towing_core.evaluation import OverloadStatus, evaluate_weigh_event
from towing_core.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile
from towing_streamlit.results import (
    STATUS_BORDER,
    STATUS_COLOR,
    STATUS_ICON,
    STATUS_LABEL,
    check_box_html,
    grid_checks,
)

# Same rig shape the compute-tier tests use (test_calculations / test_evaluation).
TRUCK = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500)
TRUCK_NO_GCWR = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=None)
TRAILER = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)

# Known-overloaded Combined Ticket:
#   drive 10000 > 9900 rear GAWR         -> Drive Axle FAIL
#   steer 3000 <= 6000 front GAWR        -> Steer Axle PASS
#   steer + drive = 13000 <= 14000 GVWR -> Hitched GVWR PASS
#   trailer axle 19000 <= 24000 group   -> Trailer Axle PASS
#   gross 33000 > 32500 GCWR            -> GCWR FAIL
COMBINED = CombinedTicket(steer=3000, drive=10000, trailer_axle=19000, gross=33000)
# Solo gross 9560 -> Derived Trailer Weight 33000 - 9560 = 23440, i.e. 60 lb
# under the 23500 Trailer GVWR: inside the trusted 100 lb near-limit margin.
SOLO = SoloTicket(steer=3000, drive=6560, gross=9560)


def test_near_limit_margin_constant_is_as_expected() -> None:
    # The rig is built against this exact value - confirm it, don't assume.
    assert TRAILER_GVWR_NEAR_LIMIT_MARGIN_LBS == 100
    assert (23500 - 23440) == 60  # inside the 100 lb trusted margin, not over


def test_known_overloaded_rig_box_statuses() -> None:
    ev = evaluate_weigh_event(TRUCK, TRAILER, COMBINED, SOLO)

    assert ev.drive_axle.status is OverloadStatus.FAIL
    assert ev.gcwr.status is OverloadStatus.FAIL
    assert ev.trailer_gvwr.status is OverloadStatus.NEAR_LIMIT
    assert ev.steer_axle.status is OverloadStatus.PASS
    assert ev.trailer_axle.status is OverloadStatus.PASS
    assert ev.hitched_gvwr.status is OverloadStatus.PASS
    assert ev.overall_status is OverloadStatus.FAIL


def test_gcwr_not_evaluated_when_truck_has_no_gcwr() -> None:
    ev = evaluate_weigh_event(TRUCK_NO_GCWR, TRAILER, COMBINED, SOLO)

    assert ev.gcwr.status is OverloadStatus.NOT_EVALUATED
    assert ev.gcwr.actual is None
    assert ev.gcwr.rating is None
    assert ev.gcwr.note  # the grey box shows this reason


def test_trailer_gvwr_not_evaluated_when_solo_skipped() -> None:
    ev = evaluate_weigh_event(TRUCK, TRAILER, COMBINED, solo=None)

    assert ev.trailer_gvwr.status is OverloadStatus.NOT_EVALUATED
    assert ev.trailer_gvwr.note
    # GCWR still evaluates off the Combined Ticket alone.
    assert ev.gcwr.status is OverloadStatus.FAIL


def test_time_gap_advisory_only_present_when_hours_supplied() -> None:
    without = evaluate_weigh_event(TRUCK, TRAILER, COMBINED, SOLO)
    with_gap = evaluate_weigh_event(TRUCK, TRAILER, COMBINED, SOLO, time_gap_hours=6.0)

    assert without.time_gap_result is None
    assert with_gap.time_gap_result is not None
    assert with_gap.time_gap_result.exceeds_threshold is True


def test_status_maps_cover_every_status() -> None:
    # check_box_html indexes all four maps by status - a missing entry would be
    # a runtime KeyError in the rendered app, so guard every one here.
    for status in OverloadStatus:
        assert status in STATUS_COLOR
        assert status in STATUS_LABEL
        assert status in STATUS_BORDER
        assert status in STATUS_ICON


def test_check_box_html_renders_for_every_status() -> None:
    ev = evaluate_weigh_event(TRUCK_NO_GCWR, TRAILER, COMBINED, SOLO)
    for check in grid_checks(ev):
        box = check_box_html(check)
        assert STATUS_COLOR[check.status] in box
        assert STATUS_LABEL[check.status] in box
        assert box.startswith("<div") and box.rstrip().endswith("</div>")


def test_grid_checks_is_the_six_boxes_in_display_order() -> None:
    ev = evaluate_weigh_event(TRUCK, TRAILER, COMBINED, SOLO)

    labels = [check.label for check in grid_checks(ev)]
    assert labels == [
        "Steer Axle",
        "Drive Axle",
        "Trailer Axle",
        "Hitched GVWR",
        "GCWR",
        "Trailer GVWR",
    ]
