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
    truck_is_one_off: bool = False,
    trailer_is_one_off: bool = False,
) -> tuple[RigEvaluation, WeighEventRecord] | list[Problem]:
    """Evaluate and persist one Weigh Event, non-interactively.

    Returns `(evaluation, record)` on success, or a non-empty `list[Problem]`
    when a precondition fails: no Truck Profile, no Trailer Profile, or a
    selected Profile that has never been saved (no `id`) *and* isn't an
    explicit One-Off. The `record` is the one built and handed to
    `weigh_event_store.save`.

    `truck_is_one_off`/`trailer_is_one_off` (issue #45 / ADR 0017) mark a
    side as a One-Off Truck/Trailer - entered for this Weigh Event only,
    deliberately never saved as a real Profile, so `truck.id`/`trailer.id`
    being `None` is expected, not the "selected Profile was never saved"
    caller bug the check below still catches for every other caller (in
    particular the CLI, which never passes either flag and always selects
    from already-saved Profiles). Both default `False` so every existing
    caller's behavior is unchanged.
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
    if (truck.id is None and not truck_is_one_off) or (
        trailer.id is None and not trailer_is_one_off
    ):
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
    # CONTEXT.md: Nickname, ADR 0004). A One-Off side has no `id` to derive
    # an ID-based default from, so it gets its own distinct fallback
    # ("One-Off Truck"/"One-Off Trailer") instead of `_display_nickname`'s
    # "Truck {id}" shape (CONTEXT.md: One-Off Truck/Trailer).
    truck_nickname = (
        (truck.nickname if truck.nickname is not None else "One-Off Truck")
        if truck_is_one_off
        else _display_nickname(truck.nickname, "Truck", truck.id)
    )
    trailer_nickname = (
        (trailer.nickname if trailer.nickname is not None else "One-Off Trailer")
        if trailer_is_one_off
        else _display_nickname(trailer.nickname, "Trailer", trailer.id)
    )

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
