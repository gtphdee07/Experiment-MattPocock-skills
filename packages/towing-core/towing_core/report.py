"""Pure CLI-output helpers: rendering Weigh Event checks and history as
plain text, and the shared legal disclaimer.

No I/O and no `argparse` - these take result objects / records and return
strings (or line lists). `towing_app.cli` imports them and does the actual
printing.
"""

from collections.abc import Sequence

from towing_core.calculations import (
    TRAILER_GVWR_NEAR_LIMIT_MARGIN_LBS,
    TRAILER_GVWR_NEAR_LIMIT_UNVERIFIED_MARGIN_LBS,
    AxleOverloadResult,
    GcwrOverloadResult,
    HitchedGvwrOverloadResult,
    TimeGapWarningResult,
    TrailerGvwrOverloadResult,
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


def _trailer_gvwr_near_limit_margin_lbs(result: TrailerGvwrOverloadResult) -> int:
    """The near-limit margin that actually applies to `result` - the wider
    `TRAILER_GVWR_NEAR_LIMIT_UNVERIFIED_MARGIN_LBS` for an Unverified Value,
    otherwise the trusted `TRAILER_GVWR_NEAR_LIMIT_MARGIN_LBS` (see ADR 0006;
    issue #17)."""
    return (
        TRAILER_GVWR_NEAR_LIMIT_UNVERIFIED_MARGIN_LBS
        if result.is_unverified
        else TRAILER_GVWR_NEAR_LIMIT_MARGIN_LBS
    )


def format_weigh_event_results(
    axle_result: AxleOverloadResult,
    gvwr_result: HitchedGvwrOverloadResult,
    gcwr_result: GcwrOverloadResult | None,
    trailer_gvwr_result: TrailerGvwrOverloadResult | None = None,
    time_gap_result: TimeGapWarningResult | None = None,
) -> str:
    """Render all checks as plain-language results, always followed by the
    legal disclaimer.

    `gcwr_result` is `None` when the Truck Profile has no GCWR on file - a
    distinct "not evaluated" state (see ADR 0002), reported without blocking
    or hiding the other two checks. When it is present, GCWR Overload
    depends on a manually-typed value with no photo/CAT Scale Ticket backing
    it, so its result is labeled an Unverified Value (see CONTEXT.md:
    Unverified Value).

    `trailer_gvwr_result` is `None` whenever there's no linked Solo Ticket
    for this Weigh Event - also reported as "not evaluated" rather than
    hidden (see CONTEXT.md: Trailer GVWR Overload). When it's present and
    `is_unverified` (a manually-adjusted Reused Solo Weight - see ADR 0006;
    issue #16), it's labeled an Unverified Value the same way GCWR Overload
    is above. When it's present and not overloaded but `is_near_limit`, an
    extra "Near limit" line is shown (see ADR 0006) - never alongside an
    OVERLOADED verdict. `time_gap_result`
    is only present at all when a Solo Ticket was linked - unlike the
    Overload checks it's advisory only and never labeled OVERLOADED/OK (see
    CONTEXT.md: Time-Gap Warning)."""
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
    verdict = "OVERLOADED" if gvwr_result.is_overloaded else "OK"
    lines.append(
        f"  Steer + Drive: {gvwr_result.combined_actual} lbs actual vs. "
        f"{gvwr_result.gvwr_rating} lbs rated -> {verdict}"
    )
    if gvwr_result.is_overloaded:
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
        verdict = "OVERLOADED" if gcwr_result.is_overloaded else "OK"
        lines.append(
            f"  Gross Weight: {gcwr_result.combined_actual} lbs actual vs. "
            f"{gcwr_result.gcwr_rating} lbs rated (Unverified Value - GCWR is "
            f"manually entered, not backed by a photo or CAT Scale Ticket) "
            f"-> {verdict}"
        )
        if gcwr_result.is_overloaded:
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
        verdict = "OVERLOADED" if trailer_gvwr_result.is_overloaded else "OK"
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
        if trailer_gvwr_result.is_overloaded:
            lines.append("  Result: Trailer GVWR Overload detected.")
        else:
            lines.append("  Result: no Trailer GVWR Overload detected.")
            if trailer_gvwr_result.is_near_limit:
                margin = _trailer_gvwr_near_limit_margin_lbs(trailer_gvwr_result)
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
    lines = [f"[{record.timestamp}] {truck_label} + {trailer_label}"]
    lines.extend(f"  {line}" for line in _format_axle_check(record.axle_result))
    axle_verdict = "OVERLOADED" if record.axle_result.any_overloaded else "OK"
    lines.append(f"  Axle Overload: {axle_verdict}")

    gvwr_verdict = "OVERLOADED" if record.gvwr_result.is_overloaded else "OK"
    lines.append(
        f"  Hitched GVWR Overload: {record.gvwr_result.combined_actual} lbs actual "
        f"vs. {record.gvwr_result.gvwr_rating} lbs rated -> {gvwr_verdict}"
    )

    if record.gcwr_result is None:
        lines.append(
            "  GCWR Overload: not evaluated - no GCWR on file for this Truck Profile."
        )
    else:
        gcwr_verdict = "OVERLOADED" if record.gcwr_result.is_overloaded else "OK"
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
        trailer_verdict = (
            "OVERLOADED" if record.trailer_gvwr_result.is_overloaded else "OK"
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
        if record.trailer_gvwr_result.is_near_limit:
            margin = _trailer_gvwr_near_limit_margin_lbs(record.trailer_gvwr_result)
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
