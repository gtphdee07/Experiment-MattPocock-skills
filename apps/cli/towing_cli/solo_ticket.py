"""The Solo Ticket linking decision for a Weigh Event: whether (and how) a
Weigh Event gets a Solo Ticket - weighed fresh, reused from the last known
weight, or skipped - and whether a freshly-weighed one links to the Combined
Ticket (see CONTEXT.md: Solo Ticket, Reused Solo Weight, Reweigh Reference).

This module owns the choice -> collect -> link pipeline end to end, behind
one entry point (`decide_solo_ticket`) returning one named result
(`SoloTicketDecision`). The lower-level "collect a ticket, by photo or
manually" functions it calls (`collect_solo_ticket_interactive` and friends)
stay in `towing_cli.collect` - they are generic ticket collectors, not
specific to this decision, and mirror `collect_combined_ticket_interactive`
there.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from towing_app.field_acquisition import ClaudeVisionScaleTicketFieldSource
from towing_cli.collect import collect_solo_ticket_interactive
from towing_cli.prompt import (
    ReadFn,
    _confirm,
    _read_float,
    _read_optional_str_with_default,
)
from towing_core.calculations import TimeGapWarningResult, check_time_gap
from towing_core.field_acquisition import TextFieldSource
from towing_core.linking import _find_last_solo_ticket_record, reweigh_references_match
from towing_core.models import CombinedTicket, SoloTicket
from towing_core.storage import WeighEventRecord


@dataclass(frozen=True)
class SoloTicketDecision:
    """The outcome of `decide_solo_ticket`: the (possibly-updated) Combined
    Ticket alongside whatever was decided for the Solo Ticket."""

    ticket: CombinedTicket
    solo_ticket: SoloTicket | None
    time_gap_result: TimeGapWarningResult | None
    reused_solo_from_timestamp: str | None
    reused_solo_is_unverified: bool


SoloTicketChoice = Literal["weigh_now", "reuse", "skip"]


def _ask_solo_ticket_choice(read: ReadFn, *, reuse_available: bool) -> SoloTicketChoice:
    """Ask whether to add a Solo Ticket for this Weigh Event.

    When no past Weigh Event for this Truck Profile has a linked Solo
    Ticket, this is the same yes/no question the app has always asked,
    worded identically - "reuse" is never mentioned when it isn't an actual
    option. Only when `reuse_available` is true does the question grow a
    third choice (see CONTEXT.md: Reused Solo Weight, ADR 0006 - no
    staleness threshold gates whether reuse is offered, only whether
    qualifying history exists at all)."""
    if not reuse_available:
        return (
            "weigh_now"
            if _confirm(read, "Add a Solo Ticket for this Weigh Event? [y/N]: ")
            else "skip"
        )

    response = (
        read(
            "Add a Solo Ticket for this Weigh Event? [y]es - weigh it now / "
            "[r]euse last known weight / [N]o: "
        )
        .strip()
        .lower()
    )
    if response == "y":
        return "weigh_now"
    if response == "r":
        return "reuse"
    return "skip"


def _collect_reused_solo_ticket(
    read: ReadFn,
    past_record: WeighEventRecord,
    emit: Callable[[str], None] = print,
) -> tuple[SoloTicket, str, bool]:
    """Reuse a past Weigh Event's linked Solo Ticket for this Truck Profile
    (see CONTEXT.md: Reused Solo Weight). Shows the past Gross Weight and
    the date it was recorded, then asks whether anything's changed since
    then - no staleness threshold gates this, regardless of how old
    `past_record` is (see ADR 0006).

    "No, nothing's changed" reuses the past Solo Ticket exactly as-is, still
    a trusted reading rather than an Unverified Value. "Yes, something's
    changed" prompts for a new Gross Weight on the spot (a plain float, no
    special validation) and carries the rest of the past Solo Ticket
    forward unchanged - that figure has no photo or CAT Scale Ticket behind
    it, so it becomes an Unverified Value (see CONTEXT.md: Unverified
    Value; ADR 0006; issue #16).

    Returns the resulting `SoloTicket`, the original record's `timestamp`
    (for `WeighEventRecord.reused_solo_from_timestamp`), and whether the
    weight was adjusted (for `WeighEventRecord.reused_solo_is_unverified`
    and `TrailerGvwrOverloadResult.is_unverified`)."""
    past_solo = past_record.solo_ticket
    assert past_solo is not None
    emit(
        f"Last known Solo weight for this Truck Profile: {past_solo.gross} lbs, "
        f"recorded {past_record.timestamp}."
    )
    changed = _confirm(
        read,
        "Has anything changed since then (cargo, fuel, passengers)? [y/N]: ",
    )
    if changed:
        new_gross = _read_float(
            read,
            "New Gross Weight for the Tow Vehicle, lbs (Unverified Value - not "
            "backed by a photo or CAT Scale Ticket): ",
        )
        return replace(past_solo, gross=new_gross), past_record.timestamp, True
    return past_solo, past_record.timestamp, False


def determine_solo_link(
    read: ReadFn,
    combined: CombinedTicket,
    solo: SoloTicket,
    emit: Callable[[str], None] = print,
) -> bool:
    """Decide whether a Solo Ticket belongs to the same Weigh Event as the
    Combined Ticket (see CONTEXT.md: Reweigh Reference).

    Automatic when both tickets carry a matching, non-blank reweigh
    reference - CAT Scale's own printed field connecting a reweigh to its
    original ticket. Otherwise this falls back to asking the user to
    manually confirm the link, per the acceptance criteria in issue #9."""
    if reweigh_references_match(combined, solo):
        emit(
            f"Reweigh reference '{combined.reweigh_reference}' matches on both "
            "tickets - linked automatically."
        )
        return True

    return _confirm(
        read,
        "No matching reweigh reference found on the two tickets. Manually "
        "confirm the Solo Ticket belongs to the same Weigh Event as the "
        "Combined Ticket? [y/N]: ",
    )


def decide_solo_ticket(
    read: ReadFn,
    ticket: CombinedTicket,
    past_records: Sequence[WeighEventRecord],
    truck_id: int,
    field_source_factory: Callable[
        [Path], TextFieldSource
    ] = ClaudeVisionScaleTicketFieldSource,
    emit: Callable[[str], None] = print,
) -> SoloTicketDecision:
    """Decide how (or whether) this Weigh Event gets a Solo Ticket: weigh it
    now, reuse the last known weight for this Truck Profile, or skip
    entirely (see CONTEXT.md: Solo Ticket, Reused Solo Weight).

    Returns a `SoloTicketDecision` carrying: the possibly-updated Combined
    Ticket (its `reweigh_reference` is asked about here, not in
    `collect_combined_ticket`, only when it wasn't already proposed from a
    Combined Ticket photo - see the `_read_optional_str_with_default` call
    below - since it's otherwise only relevant when a fresh Solo Ticket
    might link to it); the resulting Solo Ticket (`None` if skipped,
    declined, or not linked); a Time-Gap Warning result (only for a
    freshly-linked pair - reusing a weight never produces one, see ADR
    0006); the original timestamp a reused weight came from (`None` unless
    reuse was actually used); and whether that reused weight was manually
    adjusted rather than reused unchanged (always `False` for a fresh or
    skipped Solo Ticket - see CONTEXT.md: Unverified Value; ADR 0006; issue
    #16)."""
    last_solo_record = _find_last_solo_ticket_record(past_records, truck_id)
    choice = _ask_solo_ticket_choice(read, reuse_available=last_solo_record is not None)

    if choice == "skip":
        return SoloTicketDecision(ticket, None, None, None, False)

    if choice == "reuse":
        assert last_solo_record is not None
        solo, reused_from_timestamp, solo_is_unverified = _collect_reused_solo_ticket(
            read, last_solo_record, emit
        )
        return SoloTicketDecision(
            ticket, solo, None, reused_from_timestamp, solo_is_unverified
        )

    # A photo-based Combined Ticket may already carry a Reweigh Reference
    # OCR'd straight off the ticket (see `collect_combined_ticket_from_photo`)
    # - pressing Enter here keeps that value rather than blanking it out, so
    # asking again mid-flow never silently discards an already-confirmed
    # value (see ADR 0007). For a manually-entered ticket, `ticket
    # .reweigh_reference` is still `None` at this point, so blank input
    # behaves exactly as before.
    combined_ref = _read_optional_str_with_default(
        read,
        "Reweigh reference printed on the Combined Ticket, if any (optional, "
        "press Enter to skip/keep): ",
        ticket.reweigh_reference,
    )
    ticket = replace(ticket, reweigh_reference=combined_ref)

    fresh_solo = collect_solo_ticket_interactive(read, field_source_factory, emit)
    if fresh_solo is None:
        emit("Discarded - Solo Ticket not recorded.")
        return SoloTicketDecision(ticket, None, None, None, False)

    if not determine_solo_link(read, ticket, fresh_solo, emit):
        emit(
            "Solo Ticket not linked - discarding it. Derived Trailer Weight "
            "and Trailer GVWR Overload will not be evaluated for this Weigh "
            "Event."
        )
        return SoloTicketDecision(ticket, None, None, None, False)

    gap_hours = _read_float(
        read,
        "Hours between when the Combined and Solo Tickets were weighed "
        "(0 if the same time): ",
    )
    return SoloTicketDecision(
        ticket, fresh_solo, check_time_gap(gap_hours), None, False
    )
