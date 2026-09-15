"""Pure CLI-output helpers: rendering Weigh Event checks and history as
plain text, and the shared legal disclaimer.

No I/O and no `argparse` - these take result objects / records and return
strings (or line lists). `towing_cli` (the CLI client) imports them and does
the actual printing.
"""

from collections.abc import Sequence

from towing_core.calculations import AxleOverloadResult
from towing_core.evaluation import (
    OverloadStatus,
    RigEvaluation,
    rig_evaluation_from_record,
)
from towing_core.storage import WeighEventRecord

# NOTE: Placeholder legal copy. This wording has NOT been reviewed by a
# lawyer and must not ship in a paid product until it gets that review.
LEGAL_DISCLAIMER = (
    "DISCLAIMER (placeholder - not legal advice, pending legal review): "
    "This app is a personal reference tool for recreational RV towing only. "
    "It is not for commercial or for-hire use. Results are estimates based "
    "on user-entered data and are not a substitute for certified scale "
    "readings, your vehicle manufacturer's documentation, or advice from a "
    "qualified professional. The app's authors accept no legal "
    "responsibility for towing decisions made using this tool - when in "
    "doubt, consult a weight-distribution/towing expert or your vehicle "
    "manufacturer before towing."
)


def _display_nickname(nickname: str | None, kind: str, profile_id: int | None) -> str:
    """The Nickname to show for a Truck/Trailer Profile - the stored value,
    or a default computed live from its ID (e.g. "Truck 3") when it's
    `None` (see CONTEXT.md: Nickname). This default is only ever computed
    for display - it is never written back to storage, so leaving the
    Nickname blank never silently locks in a stored value (see ticket #12).
    `kind` is "Truck" or "Trailer"."""
    return nickname if nickname is not None else f"{kind} {profile_id}"


def _format_axle_check(check: AxleOverloadResult) -> list[str]:
    lines = []
    for result in (check.steer, check.drive, check.trailer):
        verdict = "OVERLOADED" if result.is_overloaded else "OK"
        lines.append(
            f"  {result.axle_name}: {result.actual} lbs actual vs. "
            f"{result.rating} lbs rated -> {verdict}"
        )
    return lines


def format_weigh_event_results(evaluation: RigEvaluation) -> str:
    """Render all checks as plain-language results, always followed by the
    legal disclaimer.

    Takes the already-folded `RigEvaluation` (see `towing_core.evaluation`)
    rather than raw `check_*` results, so this is the one place that turns a
    check's `OverloadStatus` into rendered text - it does not independently
    re-derive Pass/Near-Limit/Fail/Not-Evaluated from the raw numbers. The
    raw result objects are still read off the `RigEvaluation` for the
    numbers themselves (actual/rating values) and for fields not yet
    exposed via `EvaluatedCheck`, e.g. `near_limit_margin_lbs`.

    `evaluation.gcwr_result` is `None` when the Truck Profile has no GCWR on
    file - a distinct "not evaluated" state (see ADR 0002), reported without
    blocking or hiding the other two checks. When it is present, GCWR
    Overload depends on a manually-typed value with no photo/CAT Scale
    Ticket backing it, so its result is labeled an Unverified Value (see
    CONTEXT.md: Unverified Value).

    `evaluation.trailer_gvwr_result` is `None` whenever there's no linked
    Solo Ticket for this Weigh Event - also reported as "not evaluated"
    rather than hidden (see CONTEXT.md: Trailer GVWR Overload). When it's
    present and `is_unverified` (a manually-adjusted Reused Solo Weight -
    see ADR 0006; issue #16), it's labeled an Unverified Value the same way
    GCWR Overload is above. When it's present and not overloaded but
    `is_near_limit`, an extra "Near limit" line is shown (see ADR 0006) -
    never alongside an OVERLOADED verdict. `evaluation.time_gap_result` is
    only present at all when a Solo Ticket was linked - unlike the Overload
    checks it's advisory only and never labeled OVERLOADED/OK (see
    CONTEXT.md: Time-Gap Warning)."""
    axle_result = evaluation.axle_result
    gvwr_result = evaluation.hitched_gvwr_result
    gcwr_result = evaluation.gcwr_result
    trailer_gvwr_result = evaluation.trailer_gvwr_result
    time_gap_result = evaluation.time_gap_result

    lines = ["=== Weigh Event Results ===", ""]

    lines.append("Axle Overload")
    lines.append(
        "  Checks whether any single axle group's actual weight exceeds "
        "what it's rated to carry (its GAWR)."
    )
    lines.extend(_format_axle_check(axle_result))
    if axle_result.any_overloaded:
        lines.append("  Result: Axle Overload detected.")
    else:
        lines.append("  Result: no Axle Overload detected.")
    lines.append("")

    lines.append("Hitched GVWR Overload")
    lines.append(
        "  Checks whether the tow vehicle's own axle groups (Steer + Drive), "
        "summed while hitched to the trailer, exceed the tow vehicle's own "
        "GVWR - this can happen even when neither axle is individually "
        "overloaded."
    )
    hitched_gvwr_overloaded = evaluation.hitched_gvwr.status == OverloadStatus.FAIL
    verdict = "OVERLOADED" if hitched_gvwr_overloaded else "OK"
    lines.append(
        f"  Steer + Drive: {gvwr_result.combined_actual} lbs actual vs. "
        f"{gvwr_result.gvwr_rating} lbs rated -> {verdict}"
    )
    if hitched_gvwr_overloaded:
        lines.append("  Result: Hitched GVWR Overload detected.")
    else:
        lines.append("  Result: no Hitched GVWR Overload detected.")
    lines.append("")

    lines.append("GCWR Overload")
    lines.append(
        "  Checks whether the Combined Ticket's Gross Weight exceeds the "
        "tow vehicle's GCWR (Gross Combined Weight Rating)."
    )
    if gcwr_result is None:
        lines.append(
            "  Result: not evaluated - no GCWR on file for this Truck Profile."
        )
    else:
        gcwr_overloaded = evaluation.gcwr.status == OverloadStatus.FAIL
        verdict = "OVERLOADED" if gcwr_overloaded else "OK"
        lines.append(
            f"  Gross Weight: {gcwr_result.combined_actual} lbs actual vs. "
            f"{gcwr_result.gcwr_rating} lbs rated (Unverified Value - GCWR is "
            f"manually entered, not backed by a photo or CAT Scale Ticket) "
            f"-> {verdict}"
        )
        if gcwr_overloaded:
            lines.append("  Result: GCWR Overload detected.")
        else:
            lines.append("  Result: no GCWR Overload detected.")
    lines.append("")

    lines.append("Trailer GVWR Overload")
    lines.append(
        "  Checks whether Derived Trailer Weight (a linked Solo Ticket's "
        "Gross Weight subtracted from the Combined Ticket's Gross Weight) "
        "exceeds the Trailer Profile's GVWR."
    )
    if trailer_gvwr_result is None:
        lines.append(
            "  Result: not evaluated - no linked Solo Ticket for this Weigh Event."
        )
    else:
        trailer_gvwr_status = evaluation.trailer_gvwr.status
        trailer_gvwr_overloaded = trailer_gvwr_status == OverloadStatus.FAIL
        verdict = "OVERLOADED" if trailer_gvwr_overloaded else "OK"
        if trailer_gvwr_result.is_unverified:
            lines.append(
                "  Derived Trailer Weight: "
                f"{trailer_gvwr_result.derived_trailer_weight} lbs vs. "
                f"{trailer_gvwr_result.gvwr_rating} lbs rated (Unverified Value - "
                f"the reused Solo weight was manually adjusted, not backed by a "
                f"photo or CAT Scale Ticket) -> {verdict}"
            )
        else:
            lines.append(
                "  Derived Trailer Weight: "
                f"{trailer_gvwr_result.derived_trailer_weight} lbs vs. "
                f"{trailer_gvwr_result.gvwr_rating} lbs rated -> {verdict}"
            )
        if trailer_gvwr_overloaded:
            lines.append("  Result: Trailer GVWR Overload detected.")
        else:
            lines.append("  Result: no Trailer GVWR Overload detected.")
            if trailer_gvwr_status == OverloadStatus.NEAR_LIMIT:
                margin = trailer_gvwr_result.near_limit_margin_lbs
                lines.append(
                    f"  Near limit: Derived Trailer Weight is within {margin} lbs "
                    "of the Trailer's GVWR."
                )
    lines.append("")

    if time_gap_result is not None:
        lines.append("Time-Gap Warning")
        lines.append(
            "  Non-blocking: flags when the linked pair's two physical "
            "weighings were far enough apart that the Trailer may have "
            "changed weight in between."
        )
        gap = abs(time_gap_result.gap_hours)
        if time_gap_result.exceeds_threshold:
            lines.append(
                f"  Warning: the Combined and Solo Tickets were weighed {gap} "
                f"hours apart, more than the {time_gap_result.threshold_hours}-"
                "hour threshold. Derived Trailer Weight may be less accurate."
            )
        else:
            lines.append(
                f"  Combined and Solo Tickets were weighed {gap} hours apart - "
                f"within the {time_gap_result.threshold_hours}-hour threshold."
            )
        lines.append("")

    lines.append(LEGAL_DISCLAIMER)

    return "\n".join(lines)


def _format_weigh_event_record(record: WeighEventRecord) -> list[str]:
    # `truck_nickname`/`trailer_nickname` are snapshots of the Nickname (or
    # its computed default) as it stood when this Weigh Event was saved -
    # never a live lookup, so a later rename or Profile deletion never
    # changes how this already-recorded entry renders (see CONTEXT.md:
    # Nickname, ADR 0004). `None` only for a record saved before this field
    # existed, which falls back to the original ID-only display.
    truck_label = (
        record.truck_nickname
        if record.truck_nickname is not None
        else f"Truck Profile #{record.truck_id}"
    )
    trailer_label = (
        record.trailer_nickname
        if record.trailer_nickname is not None
        else f"Trailer Profile #{record.trailer_id}"
    )
    # `rig_evaluation_from_record` runs the record's already-persisted raw
    # results through the same `_assemble_rig_evaluation` fold
    # `format_weigh_event_results` consumes, so this compact history
    # rendering and that verbose per-Weigh-Event rendering derive their
    # OVERLOADED/OK/Near-Limit verdicts from one place rather than each
    # re-deriving them from the raw `is_overloaded`/`is_near_limit` values
    # independently. The line format itself stays specific to this
    # function - it renders one compact line per check rather than
    # `format_weigh_event_results`'s labeled section with description text,
    # so the two can't share print statements, only the status fold.
    evaluation = rig_evaluation_from_record(record)

    lines = [f"[{record.timestamp}] {truck_label} + {trailer_label}"]
    lines.extend(f"  {line}" for line in _format_axle_check(record.axle_result))
    axle_verdict = "OVERLOADED" if record.axle_result.any_overloaded else "OK"
    lines.append(f"  Axle Overload: {axle_verdict}")

    gvwr_verdict = (
        "OVERLOADED" if evaluation.hitched_gvwr.status == OverloadStatus.FAIL else "OK"
    )
    lines.append(
        f"  Hitched GVWR Overload: {record.gvwr_result.combined_actual} lbs actual "
        f"vs. {record.gvwr_result.gvwr_rating} lbs rated -> {gvwr_verdict}"
    )

    if record.gcwr_result is None:
        lines.append(
            "  GCWR Overload: not evaluated - no GCWR on file for this Truck Profile."
        )
    else:
        gcwr_verdict = (
            "OVERLOADED" if evaluation.gcwr.status == OverloadStatus.FAIL else "OK"
        )
        lines.append(
            f"  GCWR Overload: {record.gcwr_result.combined_actual} lbs actual "
            f"vs. {record.gcwr_result.gcwr_rating} lbs rated (Unverified Value) "
            f"-> {gcwr_verdict}"
        )

    if record.trailer_gvwr_result is None:
        lines.append(
            "  Trailer GVWR Overload: not evaluated - no linked Solo Ticket "
            "for this Weigh Event."
        )
    else:
        trailer_gvwr_status = evaluation.trailer_gvwr.status
        trailer_verdict = (
            "OVERLOADED" if trailer_gvwr_status == OverloadStatus.FAIL else "OK"
        )
        if record.trailer_gvwr_result.is_unverified:
            lines.append(
                "  Trailer GVWR Overload: Derived Trailer Weight "
                f"{record.trailer_gvwr_result.derived_trailer_weight} lbs vs. "
                f"{record.trailer_gvwr_result.gvwr_rating} lbs rated (Unverified "
                f"Value) -> {trailer_verdict}"
            )
        else:
            lines.append(
                "  Trailer GVWR Overload: Derived Trailer Weight "
                f"{record.trailer_gvwr_result.derived_trailer_weight} lbs vs. "
                f"{record.trailer_gvwr_result.gvwr_rating} lbs rated -> "
                f"{trailer_verdict}"
            )
        if trailer_gvwr_status == OverloadStatus.NEAR_LIMIT:
            margin = record.trailer_gvwr_result.near_limit_margin_lbs
            lines.append(
                f"  Near limit: Derived Trailer Weight is within {margin} lbs of "
                "the Trailer's GVWR."
            )
        if record.time_gap_hours is not None:
            gap = abs(record.time_gap_hours)
            lines.append(f"  Time-Gap: Combined and Solo Tickets {gap} hours apart.")
        if record.reused_solo_from_timestamp is not None:
            if record.reused_solo_is_unverified:
                lines.append(
                    "  Solo Ticket: reused and manually adjusted from a Weigh "
                    f"Event recorded {record.reused_solo_from_timestamp} "
                    "(Unverified Value)."
                )
            else:
                lines.append(
                    "  Solo Ticket: reused, unchanged, from a Weigh Event recorded "
                    f"{record.reused_solo_from_timestamp}."
                )

    return lines


def format_weigh_event_history(records: Sequence[WeighEventRecord]) -> str:
    """Render past Weigh Events in chronological order, each showing the
    Truck+Trailer pairing used and its check results, followed by the legal
    disclaimer once for the whole listing."""
    lines = ["=== Weigh Event History ===", ""]
    for record in records:
        lines.extend(_format_weigh_event_record(record))
        lines.append("")
    lines.append(LEGAL_DISCLAIMER)
    return "\n".join(lines)
