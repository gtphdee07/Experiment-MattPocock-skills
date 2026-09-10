"""Pure rendering helpers for the Streamlit results grid.

Kept free of any ``streamlit`` import so the colour / label mapping and the
box markup can be unit-tested without a Streamlit runtime (see
``apps/streamlit/tests``). The wizard composes these strings into
``st.markdown(..., unsafe_allow_html=True)`` boxes - the background colour
*is* the pass / near-limit / fail signal, which is why this is deliberately
not ``st.metric``.
"""

import html

from towing_core.evaluation import EvaluatedCheck, OverloadStatus, RigEvaluation

# Colours from the plan's Phase 1 spec (GitHub's status palette). Every box
# uses white text on the solid fill: that stays legible on all four fills in
# both the light and the dark Streamlit themes, so nothing here leans on the
# theme's default text colour.
STATUS_COLOR: dict[OverloadStatus, str] = {
    OverloadStatus.PASS: "#1a7f37",
    OverloadStatus.NEAR_LIMIT: "#9a6700",
    OverloadStatus.FAIL: "#cf222e",
    OverloadStatus.NOT_EVALUATED: "#6e7781",
}

# Human form of each status name, for the box body ("Near Limit", not
# "NEAR_LIMIT").
STATUS_LABEL: dict[OverloadStatus, str] = {
    OverloadStatus.PASS: "Pass",
    OverloadStatus.NEAR_LIMIT: "Near Limit",
    OverloadStatus.FAIL: "Fail",
    OverloadStatus.NOT_EVALUATED: "Not Evaluated",
}


def status_label(status: OverloadStatus) -> str:
    """The human-facing name for a status (e.g. ``NEAR_LIMIT`` -> "Near Limit")."""
    return STATUS_LABEL[status]


def grid_checks(evaluation: RigEvaluation) -> list[EvaluatedCheck]:
    """The six checks in the fixed left-to-right, top-to-bottom order the
    results grid lays them out in."""
    return [
        evaluation.steer_axle,
        evaluation.drive_axle,
        evaluation.trailer_axle,
        evaluation.hitched_gvwr,
        evaluation.gcwr,
        evaluation.trailer_gvwr,
    ]


def check_box_html(check: EvaluatedCheck) -> str:
    """One coloured results box as a self-contained HTML string.

    Shows the check label, its status name, the ``actual vs rating`` figures
    when both are known, and - for a ``NOT_EVALUATED`` check - the reason
    note carried on the ``EvaluatedCheck``.
    """
    color = STATUS_COLOR[check.status]
    rows = [
        f'<div style="font-weight:700;font-size:0.95rem">'
        f"{html.escape(check.label)}</div>",
        f'<div style="font-size:0.85rem;margin-top:0.15rem">'
        f"{html.escape(status_label(check.status))}</div>",
    ]
    if check.actual is not None and check.rating is not None:
        rows.append(
            f'<div style="font-size:0.85rem;margin-top:0.35rem">'
            f"{check.actual:g} lb vs {check.rating:g} lb</div>"
        )
    if check.status is OverloadStatus.NOT_EVALUATED and check.note:
        rows.append(
            f'<div style="font-size:0.8rem;margin-top:0.35rem;opacity:0.9">'
            f"{html.escape(check.note)}</div>"
        )
    return (
        f'<div style="background:{color};color:#ffffff;border-radius:8px;'
        f"padding:0.7rem 0.85rem;margin-bottom:0.75rem;height:100%;"
        f'min-height:7rem">{"".join(rows)}</div>'
    )
