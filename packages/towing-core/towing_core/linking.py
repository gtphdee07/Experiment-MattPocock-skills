"""Pure decision helpers for linking a Solo Ticket to a Weigh Event.

No I/O - these take tickets / records and return a decision. The
print + interactive-confirm fallback stays in `towing_cli.collect`.
"""

from collections.abc import Sequence

from towing_core.models import CombinedTicket, SoloTicket
from towing_core.storage import WeighEventRecord


def _find_last_solo_ticket_record(
    records: Sequence[WeighEventRecord], truck_id: int
) -> WeighEventRecord | None:
    """The most recent past Weigh Event for `truck_id` that has a linked
    Solo Ticket - the source for "reuse the last known weight" (see
    CONTEXT.md: Reused Solo Weight). `None` when this Truck Profile has no
    such history, which is also the signal that "reuse" should not be
    offered at all.

    `WeighEventStore.list()` returns every record unfiltered, so this
    filter-then-pick-the-latest is done here rather than as a new store
    method."""
    candidates = [
        record
        for record in records
        if record.truck_id == truck_id and record.solo_ticket is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda record: record.timestamp)


def reweigh_references_match(combined: CombinedTicket, solo: SoloTicket) -> bool:
    """`True` iff both tickets carry a non-blank Reweigh Reference and the
    two match after trimming surrounding whitespace, compared
    case-insensitively (see CONTEXT.md: Reweigh Reference) - CAT Scale's own
    printed field connecting a reweigh to its original ticket.

    This is the pure automatic-link test; `towing_cli.collect.determine_solo_link`
    layers the print + manual-confirm fallback on top for the no-match case."""
    combined_ref = combined.reweigh_reference
    solo_ref = solo.reweigh_reference
    return (
        combined_ref is not None
        and solo_ref is not None
        and combined_ref.strip().lower() == solo_ref.strip().lower()
    )
