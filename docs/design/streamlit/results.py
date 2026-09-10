"""Pure rendering helpers for the Streamlit results grid.

Kept free of any ``streamlit`` import so the colour / label mapping and the
box markup can be unit-tested without a Streamlit runtime (see
``apps/streamlit/tests``). The wizard composes these strings into
``st.markdown(..., unsafe_allow_html=True)`` boxes - the background colour
*is* the pass / near-limit / fail signal, which is why this is deliberately
not ``st.metric``.

Colours + icons per the WTWT theme deliverable (see ``streamlit-theme/``):
hue alone never carries the status - each fill also gets a distinct border
style (solid/dashed/dotted) and a small stroke icon, so the four statuses
stay distinguishable for red-green colour blindness.
"""

import html

from towing_core.evaluation import EvaluatedCheck, OverloadStatus, RigEvaluation

STATUS_COLOR: dict[OverloadStatus, str] = {
    OverloadStatus.PASS: "#335a2b",
    OverloadStatus.NEAR_LIMIT: "#8a4d12",
    OverloadStatus.FAIL: "#a8402f",
    OverloadStatus.NOT_EVALUATED: "#4f4d48",
}

STATUS_BORDER: dict[OverloadStatus, str] = {
    OverloadStatus.PASS: "1px solid rgba(255,255,255,.28)",
    OverloadStatus.NEAR_LIMIT: "2px dashed rgba(255,255,255,.6)",
    OverloadStatus.FAIL: "2px solid rgba(255,255,255,.7)",
    OverloadStatus.NOT_EVALUATED: "2px dotted rgba(255,255,255,.4)",
}

# 14px stroke icons, no icon font / external asset - inlined per the brief's
# "no external assets" constraint.
STATUS_ICON: dict[OverloadStatus, str] = {
    OverloadStatus.PASS: (
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" '
        'stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 12l6 6L20 6"/></svg>'
    ),
    OverloadStatus.NEAR_LIMIT: (
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" '
        'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 3l10 18H2z"/><line x1="12" y1="10" x2="12" y2="14.5"/>'
        '<circle cx="12" cy="17.3" r="0.9" fill="#fff" stroke="none"/></svg>'
    ),
    OverloadStatus.FAIL: (
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" '
        'stroke-width="3.5" stroke-linecap="round">'
        '<path d="M5 5l14 14M19 5L5 19"/></svg>'
    ),
    OverloadStatus.NOT_EVALUATED: (
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" '
        'stroke-width="3.5" stroke-linecap="round"><path d="M5 12h14"/></svg>'
    ),
}

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
    """One coloured results box as a self-contained HTML string."""
    color = STATUS_COLOR[check.status]
    border = STATUS_BORDER[check.status]
    icon = STATUS_ICON[check.status]
    rows = [
        f'<div style="display:flex;align-items:center;gap:6px">{icon}'
        f'<span style="font-weight:700;font-size:0.95rem">{html.escape(check.label)}</span></div>',
        f'<div style="font-size:0.85rem;font-weight:600;margin-top:0.3rem">'
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
        f'<div style="background:{color};color:#ffffff;border-radius:1rem;'
        f'border:{border};padding:0.7rem 0.85rem;margin-bottom:0.75rem;height:100%;'
        f'min-height:7rem">{"".join(rows)}</div>'
    )
