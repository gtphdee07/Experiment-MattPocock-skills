"""Standalone offline Streamlit calculator for the Towing Limit Checker.

A five-step wizard - Tow Vehicle ratings, Trailer ratings, Combined Ticket,
an optional fresh Solo Ticket, then a colour-coded Rig Evaluation grid. It
imports only the compute tier (``towing_core``): no persistence, no accounts,
no OCR, no ``anthropic`` (see ADR 0008 / ADR 0009 and the plan's Phase 1).
The only reset is "Start over" - there is no saved history to reuse.

Run with ``streamlit run apps/streamlit/streamlit_app.py`` (the same path is
the Streamlit Community Cloud main-file setting; ``apps/streamlit/`` also
holds the ``requirements.txt`` Cloud installs from). Streamlit executes this
module as ``__main__`` with ``apps/streamlit/`` on ``sys.path``, which is what
makes the sibling ``towing_streamlit`` package importable below.
"""

from collections.abc import Callable
from pathlib import Path

import streamlit as st

from towing_core.evaluation import OverloadStatus, RigEvaluation, evaluate_weigh_event
from towing_core.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile
from towing_core.report import LEGAL_DISCLAIMER

# This entry point lives beside the ``towing_streamlit`` package, not inside
# it: ``streamlit run`` executes it as top-level ``__main__`` (no parent
# package, so ``from .results import ...`` cannot work), and Community Cloud
# runs it the same way. With ``apps/streamlit/`` on ``sys.path`` -
# ``streamlit run`` and the workspace-installed package both put it there -
# the absolute import resolves without ``towing-streamlit`` needing to be a
# pip dependency of the deploy.
from towing_streamlit.results import check_box_html, grid_checks

_TOTAL_STEPS = 5

# WTWT brand marks (see docs/design/). Absolute paths off this file so they
# resolve no matter the working directory `streamlit run` is invoked from -
# `page_icon` / `st.logo` take a local path here, not a CWD-relative one.
_ASSETS = Path(__file__).parent / "assets"
_FAVICON = str(_ASSETS / "wtwt-favicon-mono.png")
_LOGO = str(_ASSETS / "wtwt-logo.png")


def _num(value: float | None) -> float:
    """Prefill helper: a previously entered weight, or ``0.0`` when unset.

    ``st.number_input`` has no true empty state, so the wizard uses ``0.0``
    as the "not supplied" sentinel and maps it back to ``None`` for the
    optional fields (GCWR, UVW, the time gap)."""
    return float(value) if value is not None else 0.0


def _goto(step: int) -> None:
    """Move to ``step`` and re-run the script from the top so the new step
    renders immediately."""
    st.session_state.step = step
    st.rerun()


def _start_over() -> None:
    """Clear every wizard input and return to step 0 - the only reset."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    _goto(0)


def _back_button(to_step: int) -> None:
    if st.button("Back", key=f"back_to_{to_step}"):
        _goto(to_step)


# --- Steps -----------------------------------------------------------------


def _step_truck_ratings() -> None:
    st.header(f"Step 1 of {_TOTAL_STEPS}: Tow Vehicle ratings")
    st.write(
        "From the Tow Vehicle's certification label, plus its GCWR from the "
        "owner's manual (never printed on a tag)."
    )
    truck = st.session_state.get("truck")
    with st.form("truck_ratings"):
        gvwr = st.number_input(
            "GVWR (lb)",
            min_value=0.0,
            step=100.0,
            value=_num(truck.gvwr if truck else None),
        )
        front_gawr = st.number_input(
            "Front GAWR (lb)",
            min_value=0.0,
            step=100.0,
            value=_num(truck.front_gawr if truck else None),
        )
        rear_gawr = st.number_input(
            "Rear GAWR (lb)",
            min_value=0.0,
            step=100.0,
            value=_num(truck.rear_gawr if truck else None),
        )
        gcwr = st.number_input(
            "GCWR (lb) - optional, leave 0 if not on file",
            min_value=0.0,
            step=100.0,
            value=_num(truck.gcwr if truck else None),
        )
        submitted = st.form_submit_button("Next")
    if submitted:
        if min(gvwr, front_gawr, rear_gawr) <= 0:
            st.error("Enter the GVWR, Front GAWR and Rear GAWR (all greater than 0).")
            return
        st.session_state.truck = TruckProfile(
            gvwr=gvwr,
            front_gawr=front_gawr,
            rear_gawr=rear_gawr,
            gcwr=gcwr or None,
            nickname=None,
            id=None,
        )
        _goto(1)


def _step_trailer_ratings() -> None:
    st.header(f"Step 2 of {_TOTAL_STEPS}: Trailer ratings")
    st.write(
        "From the Trailer's certification label. GAWR is the single per-axle "
        "figure; Axle Count multiplies it into a group rating comparable to the "
        "Trailer Axle reading on a CAT Scale Ticket."
    )
    trailer = st.session_state.get("trailer")
    with st.form("trailer_ratings"):
        gvwr = st.number_input(
            "GVWR (lb)",
            min_value=0.0,
            step=100.0,
            value=_num(trailer.gvwr if trailer else None),
        )
        gawr = st.number_input(
            "GAWR per axle (lb)",
            min_value=0.0,
            step=100.0,
            value=_num(trailer.gawr if trailer else None),
        )
        axle_count = st.number_input(
            "Axle Count",
            min_value=1,
            max_value=10,
            step=1,
            value=int(trailer.axle_count) if trailer else 2,
        )
        uvw = st.number_input(
            "UVW (lb) - optional, leave 0 if unknown",
            min_value=0.0,
            step=100.0,
            value=_num(trailer.uvw if trailer else None),
        )
        submitted = st.form_submit_button("Next")
    _back_button(0)
    if submitted:
        if min(gvwr, gawr) <= 0:
            st.error("Enter the Trailer GVWR and per-axle GAWR (both greater than 0).")
            return
        st.session_state.trailer = TrailerProfile(
            gvwr=gvwr,
            gawr=gawr,
            axle_count=int(axle_count),
            uvw=uvw or None,
            nickname=None,
            id=None,
        )
        _goto(2)


def _step_combined_ticket() -> None:
    st.header(f"Step 3 of {_TOTAL_STEPS}: Combined Ticket")
    st.write(
        "The CAT Scale Ticket from weighing the Tow Vehicle and Trailer hitched "
        "together."
    )
    combined = st.session_state.get("combined")
    with st.form("combined_ticket"):
        steer = st.number_input(
            "Steer Axle (lb)",
            min_value=0.0,
            step=100.0,
            value=_num(combined.steer if combined else None),
        )
        drive = st.number_input(
            "Drive Axle (lb)",
            min_value=0.0,
            step=100.0,
            value=_num(combined.drive if combined else None),
        )
        trailer_axle = st.number_input(
            "Trailer Axle group (lb)",
            min_value=0.0,
            step=100.0,
            value=_num(combined.trailer_axle if combined else None),
        )
        gross = st.number_input(
            "Gross Weight (lb)",
            min_value=0.0,
            step=100.0,
            value=_num(combined.gross if combined else None),
        )
        submitted = st.form_submit_button("Next")
    _back_button(1)
    if submitted:
        if min(steer, drive, trailer_axle, gross) <= 0:
            st.error("Enter all four Combined Ticket weights (each greater than 0).")
            return
        st.session_state.combined = CombinedTicket(
            steer=steer, drive=drive, trailer_axle=trailer_axle, gross=gross
        )
        _goto(3)


def _step_solo_ticket() -> None:
    st.header(f"Step 4 of {_TOTAL_STEPS}: Solo Ticket (optional)")
    st.write(
        "If you also weighed the Tow Vehicle alone on the same trip, add that "
        "ticket: it lets the Trailer GVWR check run off the Derived Trailer "
        "Weight. Skip it and that one check is reported as Not Evaluated."
    )
    solo = st.session_state.get("solo")
    if "has_solo" not in st.session_state:
        st.session_state.has_solo = solo is not None
    has_solo = st.checkbox("I also weighed the truck alone", key="has_solo")

    with st.form("solo_ticket"):
        steer = drive = gross = 0.0
        gap_hours = 0.0
        if has_solo:
            steer = st.number_input(
                "Solo Steer Axle (lb)",
                min_value=0.0,
                step=100.0,
                value=_num(solo.steer if solo else None),
            )
            drive = st.number_input(
                "Solo Drive Axle (lb)",
                min_value=0.0,
                step=100.0,
                value=_num(solo.drive if solo else None),
            )
            gross = st.number_input(
                "Solo Gross Weight (lb)",
                min_value=0.0,
                step=100.0,
                value=_num(solo.gross if solo else None),
            )
            gap_hours = st.number_input(
                "Hours between the two weighings - optional, leave 0 if unknown",
                min_value=0.0,
                step=0.5,
                value=_num(st.session_state.get("time_gap_hours")),
            )
        else:
            st.caption("Leave the box above unchecked to go straight to the results.")
        submitted = st.form_submit_button("See results")
    _back_button(2)
    if submitted:
        if has_solo and min(steer, drive, gross) <= 0:
            st.error("Enter the Solo Steer, Drive and Gross weights (each above 0).")
            return
        if has_solo:
            st.session_state.solo = SoloTicket(steer=steer, drive=drive, gross=gross)
            st.session_state.time_gap_hours = gap_hours or None
        else:
            st.session_state.solo = None
            st.session_state.time_gap_hours = None
        _goto(4)


def _render_banner(status: OverloadStatus) -> None:
    if status is OverloadStatus.FAIL:
        st.error("This rig is over at least one legal limit - do not tow as loaded.")
    elif status is OverloadStatus.NEAR_LIMIT:
        st.warning("Nothing is over a limit, but at least one check is close to one.")
    elif status is OverloadStatus.PASS:
        st.success("Every evaluated check is within its limit.")
    else:
        st.info("There was not enough information to evaluate this rig.")


def _render_time_gap(evaluation: RigEvaluation) -> None:
    """Advisory Time-Gap line - only when a gap was supplied, and never
    coloured pass / fail (see CONTEXT.md: Time-Gap Warning)."""
    result = evaluation.time_gap_result
    if result is None:
        return
    gap = abs(result.gap_hours)
    if result.exceeds_threshold:
        st.info(
            f"Time-Gap Warning (advisory): the two physical weighings were about "
            f"{gap:g} hours apart, more than the {result.threshold_hours:g}-hour "
            "threshold. The Trailer may have gained or lost weight (fuel, cargo, "
            "hitching or unhitching) in between, so the Derived Trailer Weight - "
            "and the Trailer GVWR box above - is less reliable. This never changes "
            "the pass / fail results."
        )
    else:
        st.caption(
            f"The two physical weighings were about {gap:g} hours apart - within "
            f"the {result.threshold_hours:g}-hour Time-Gap threshold."
        )


def _step_results() -> None:
    st.header(f"Step 5 of {_TOTAL_STEPS}: Rig Evaluation")
    truck = st.session_state.truck
    trailer = st.session_state.trailer
    combined = st.session_state.combined
    solo = st.session_state.get("solo")
    time_gap_hours = st.session_state.get("time_gap_hours")

    evaluation = evaluate_weigh_event(
        truck, trailer, combined, solo, time_gap_hours=time_gap_hours
    )

    _render_banner(evaluation.overall_status)

    columns = st.columns(3)
    for index, check in enumerate(grid_checks(evaluation)):
        with columns[index % 3]:
            st.markdown(check_box_html(check), unsafe_allow_html=True)

    _render_time_gap(evaluation)
    st.caption(LEGAL_DISCLAIMER)

    col_back, col_reset = st.columns(2)
    with col_back:
        if st.button("Back", key="results_back"):
            _goto(3)
    with col_reset:
        if st.button("Start over", key="results_start_over"):
            _start_over()


# --- Entry point ---------------------------------------------------------------

_STEPS: list[Callable[[], None]] = [
    _step_truck_ratings,
    _step_trailer_ratings,
    _step_combined_ticket,
    _step_solo_ticket,
    _step_results,
]


def main() -> None:
    st.set_page_config(page_title="Towing Limit Checker", page_icon=_FAVICON)
    st.logo(_LOGO)
    st.title("Towing Limit Checker")
    st.caption(
        "Enter your rig's ratings and a CAT Scale weigh ticket to see whether the "
        "Tow Vehicle and Trailer are within every weight limit. Fully offline - "
        "nothing is saved."
    )

    if "step" not in st.session_state:
        st.session_state.step = 0

    with st.sidebar:
        st.write(f"Step {int(st.session_state.step) + 1} of {_TOTAL_STEPS}")
        if st.button("Start over", key="sidebar_start_over"):
            _start_over()

    _STEPS[int(st.session_state.step)]()


if __name__ == "__main__":
    main()
