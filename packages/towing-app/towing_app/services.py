"""The non-interactive Weigh Event use case.

`record_weigh_event` is the headless core of what `cli.run_weigh_event` does
once every value has been gathered: run the rig evaluation, snapshot the
Profile nicknames, build the `WeighEventRecord`, and persist it. It performs
no I/O of its own beyond the injected store, and it never raises for an
expected precondition failure - a missing Profile or an unsaved Profile
comes back as a `list[Problem]` the caller can render however it likes.

The CLI is not wired to this yet (that is a later step); this module exists
so a non-interactive front-end has something to call.
"""

from collections.abc import Callable
from dataclasses import dataclass

from towing_core.evaluation import RigEvaluation, evaluate_weigh_event
from towing_core.models import (
    CombinedTicket,
    SoloTicket,
    TrailerProfile,
    TruckProfile,
)
from towing_core.report import _display_nickname
from towing_core.storage import WeighEventRecord, WeighEventStore


@dataclass(frozen=True)
class Problem:
    """One expected precondition failure, reported rather than raised.

    `message` is the exact wording `cli.run_weigh_event` prints for the same
    condition today, so a caller can surface it unchanged.
    """

    code: str
    message: str


def record_weigh_event(
    truck: TruckProfile | None,
    trailer: TrailerProfile | None,
    combined: CombinedTicket,
    solo: SoloTicket | None,
    *,
    solo_is_unverified: bool,
    time_gap_hours: float | None,
    reused_solo_from_timestamp: str | None,
    weigh_event_store: WeighEventStore,
    now: Callable[[], str],
) -> tuple[RigEvaluation, WeighEventRecord] | list[Problem]:
    """Evaluate and persist one Weigh Event, non-interactively.

    Returns `(evaluation, record)` on success, or a non-empty `list[Problem]`
    when a precondition fails: no Truck Profile, no Trailer Profile, or a
    selected Profile that has never been saved (no `id`). The `record` is the
    one built and handed to `weigh_event_store.save`.
    """
    if truck is None:
        return [
            Problem(
                "no_truck_profiles",
                "No Truck Profiles saved yet. Add one with 'truck add' first.",
            )
        ]
    if trailer is None:
        return [
            Problem(
                "no_trailer_profiles",
                "No Trailer Profiles saved yet. Add one with 'trailer add' first.",
            )
        ]
    if truck.id is None or trailer.id is None:
        return [
            Problem(
                "profile_missing_id",
                "Selected Profile has not been saved yet - save it before "
                "recording a Weigh Event.",
            )
        ]

    evaluation = evaluate_weigh_event(
        truck,
        trailer,
        combined,
        solo,
        solo_is_unverified=solo_is_unverified,
        time_gap_hours=time_gap_hours,
    )

    # Snapshot the Nickname (or its computed default) each Profile had right
    # now, at save time - not a live reference - so a later rename or
    # deletion never changes how this entry renders in history (see
    # CONTEXT.md: Nickname, ADR 0004).
    truck_nickname = _display_nickname(truck.nickname, "Truck", truck.id)
    trailer_nickname = _display_nickname(trailer.nickname, "Trailer", trailer.id)

    record = WeighEventRecord(
        truck_id=truck.id,
        trailer_id=trailer.id,
        ticket=combined,
        axle_result=evaluation.axle_result,
        gvwr_result=evaluation.hitched_gvwr_result,
        gcwr_result=evaluation.gcwr_result,
        solo_ticket=solo,
        trailer_gvwr_result=evaluation.trailer_gvwr_result,
        truck_nickname=truck_nickname,
        trailer_nickname=trailer_nickname,
        time_gap_hours=(
            evaluation.time_gap_result.gap_hours
            if evaluation.time_gap_result is not None
            else None
        ),
        reused_solo_from_timestamp=reused_solo_from_timestamp,
        reused_solo_is_unverified=solo_is_unverified,
        timestamp=now(),
    )
    weigh_event_store.save(record)
    return evaluation, record
