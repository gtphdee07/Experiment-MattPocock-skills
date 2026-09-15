"""Direct unit tests for `towing_cli.solo_ticket` - the Solo Ticket linking
decision extracted from `towing_cli.collect` / `towing_cli.cli` (issue #29).

Unlike `test_weigh_event_cli.py`'s full `run_weigh_event` CLI-flow tests,
these exercise `decide_solo_ticket` (and the smaller decision-relay
functions it's built from) directly - no Truck/Trailer Profile selection or
Combined Ticket collection needed first, since those aren't part of this
module's job."""

from dataclasses import replace

from towing_cli.solo_ticket import (
    SoloTicketDecision,
    _ask_solo_ticket_choice,
    _collect_reused_solo_ticket,
    decide_solo_ticket,
)
from towing_core.calculations import (
    AxleCheckResult,
    AxleOverloadResult,
    HitchedGvwrOverloadResult,
    check_time_gap,
)
from towing_core.models import CombinedTicket, SoloTicket
from towing_core.storage import WeighEventRecord

COMBINED = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)
PAST_SOLO = SoloTicket(steer=5000, drive=9720, gross=14720)
PAST_TIMESTAMP = "2026-01-15T09:00:00+00:00"

_DUMMY_AXLE_RESULT = AxleOverloadResult(
    steer=AxleCheckResult(axle_name="Steer Axle", actual=5640, rating=6000),
    drive=AxleCheckResult(axle_name="Drive Axle", actual=9080, rating=9900),
    trailer=AxleCheckResult(axle_name="Trailer Axle", actual=19680, rating=24000),
)
_DUMMY_GVWR_RESULT = HitchedGvwrOverloadResult(combined_actual=14000, gvwr_rating=14500)


def _past_record(
    *, truck_id: int, timestamp: str = PAST_TIMESTAMP, solo_ticket: SoloTicket | None
) -> WeighEventRecord:
    """A minimal past Weigh Event record - only the fields
    `decide_solo_ticket` (via `_find_last_solo_ticket_record`) actually
    looks at are meaningful; the rest are unused filler."""
    return WeighEventRecord(
        truck_id=truck_id,
        trailer_id=999,
        ticket=COMBINED,
        axle_result=_DUMMY_AXLE_RESULT,
        gvwr_result=_DUMMY_GVWR_RESULT,
        timestamp=timestamp,
        solo_ticket=solo_ticket,
    )


# --- decide_solo_ticket: skip -------------------------------------------------


def test_decide_solo_ticket_skip_chosen_no_reuse_available() -> None:
    responses = iter(["n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = decide_solo_ticket(read, COMBINED, [], truck_id=1)

    assert result == SoloTicketDecision(
        ticket=COMBINED,
        solo_ticket=None,
        time_gap_result=None,
        reused_solo_from_timestamp=None,
        reused_solo_is_unverified=False,
    )


def test_decide_solo_ticket_skip_chosen_with_reuse_available() -> None:
    past = _past_record(truck_id=1, solo_ticket=PAST_SOLO)
    responses = iter(["n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = decide_solo_ticket(read, COMBINED, [past], truck_id=1)

    assert result == SoloTicketDecision(COMBINED, None, None, None, False)


# --- decide_solo_ticket: reuse -------------------------------------------------


def test_decide_solo_ticket_reuse_chosen_unchanged() -> None:
    past = _past_record(truck_id=1, solo_ticket=PAST_SOLO)
    responses = iter(["r", "n"])  # reuse; nothing's changed

    def read(prompt: str) -> str:
        return next(responses)

    result = decide_solo_ticket(read, COMBINED, [past], truck_id=1)

    assert result == SoloTicketDecision(
        ticket=COMBINED,
        solo_ticket=PAST_SOLO,
        time_gap_result=None,
        reused_solo_from_timestamp=PAST_TIMESTAMP,
        reused_solo_is_unverified=False,
    )


def test_decide_solo_ticket_reuse_chosen_adjusted_is_unverified() -> None:
    past = _past_record(truck_id=1, solo_ticket=PAST_SOLO)
    responses = iter(["r", "y", "15000"])  # reuse; changed; new Gross Weight

    def read(prompt: str) -> str:
        return next(responses)

    result = decide_solo_ticket(read, COMBINED, [past], truck_id=1)

    assert result == SoloTicketDecision(
        ticket=COMBINED,
        solo_ticket=replace(PAST_SOLO, gross=15000),
        time_gap_result=None,
        reused_solo_from_timestamp=PAST_TIMESTAMP,
        reused_solo_is_unverified=True,
    )


def test_decide_solo_ticket_reuse_picks_most_recent_record() -> None:
    newer = PAST_SOLO
    older = SoloTicket(steer=4900, drive=9500, gross=14400)
    records = [
        _past_record(
            truck_id=1, timestamp="2026-01-01T00:00:00+00:00", solo_ticket=older
        ),
        _past_record(
            truck_id=1, timestamp="2026-03-01T00:00:00+00:00", solo_ticket=newer
        ),
    ]
    responses = iter(["r", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = decide_solo_ticket(read, COMBINED, records, truck_id=1)

    assert result.solo_ticket == newer
    assert result.reused_solo_from_timestamp == "2026-03-01T00:00:00+00:00"


# --- decide_solo_ticket: fresh Solo Ticket, weighed now -----------------------


def test_decide_solo_ticket_fresh_ticket_auto_linked_on_matching_ref() -> None:
    responses = iter(
        [
            "y",  # weigh it now
            "R12345",  # Combined Ticket's reweigh reference
            "",  # enter the Solo Ticket manually
            "5000",
            "9720",
            "14720",
            "R12345",  # Solo Ticket's reweigh reference - matches
            "y",  # confirm saving the Solo Ticket
            # matching references -> linked automatically, no manual prompt
            "0",  # hours apart
        ]
    )

    def read(prompt: str) -> str:
        return next(responses)

    result = decide_solo_ticket(read, COMBINED, [], truck_id=1)

    assert result == SoloTicketDecision(
        ticket=replace(COMBINED, reweigh_reference="R12345"),
        solo_ticket=SoloTicket(
            steer=5000, drive=9720, gross=14720, reweigh_reference="R12345"
        ),
        time_gap_result=check_time_gap(0),
        reused_solo_from_timestamp=None,
        reused_solo_is_unverified=False,
    )


def test_decide_solo_ticket_fresh_ticket_manually_confirmed_on_mismatch() -> None:
    responses = iter(
        [
            "y",  # weigh it now
            "",  # no Combined Ticket reweigh reference
            "",  # enter the Solo Ticket manually
            "5000",
            "9720",
            "14720",
            "",  # Solo Ticket, no reweigh reference either - no match
            "y",  # confirm saving the Solo Ticket
            "y",  # manual confirm: yes, same Weigh Event
            "5",  # hours apart
        ]
    )

    def read(prompt: str) -> str:
        return next(responses)

    result = decide_solo_ticket(read, COMBINED, [], truck_id=1)

    assert result == SoloTicketDecision(
        ticket=COMBINED,
        solo_ticket=SoloTicket(steer=5000, drive=9720, gross=14720),
        time_gap_result=check_time_gap(5),
        reused_solo_from_timestamp=None,
        reused_solo_is_unverified=False,
    )


def test_decide_solo_ticket_fresh_ticket_link_declined() -> None:
    responses = iter(
        [
            "y",  # weigh it now
            "",  # no Combined Ticket reweigh reference
            "",  # enter the Solo Ticket manually
            "5000",
            "9720",
            "14720",
            "",  # Solo Ticket, no reweigh reference either
            "y",  # confirm saving the Solo Ticket itself
            "n",  # manual confirm: no, not the same Weigh Event
        ]
    )

    def read(prompt: str) -> str:
        return next(responses)

    result = decide_solo_ticket(read, COMBINED, [], truck_id=1)

    assert result == SoloTicketDecision(
        ticket=COMBINED,
        solo_ticket=None,
        time_gap_result=None,
        reused_solo_from_timestamp=None,
        reused_solo_is_unverified=False,
    )


def test_decide_solo_ticket_fresh_ticket_discarded_when_not_saved() -> None:
    """Declining the Solo Ticket's own save confirmation discards it before
    a link is ever asked about - `determine_solo_link` shouldn't be reached
    at all (only the responses consumed above prove that: one more "y/n"
    queued for a link prompt would leave it unconsumed, but the iterator
    running dry on a stray `next()` call would fail loudly instead)."""
    responses = iter(
        [
            "y",  # weigh it now
            "",  # no Combined Ticket reweigh reference
            "",  # enter the Solo Ticket manually
            "5000",
            "9720",
            "14720",
            "",
            "n",  # decline saving the Solo Ticket itself
        ]
    )

    def read(prompt: str) -> str:
        return next(responses)

    result = decide_solo_ticket(read, COMBINED, [], truck_id=1)

    assert result == SoloTicketDecision(
        ticket=COMBINED,
        solo_ticket=None,
        time_gap_result=None,
        reused_solo_from_timestamp=None,
        reused_solo_is_unverified=False,
    )


def test_decide_solo_ticket_keeps_photo_proposed_reweigh_reference_on_enter() -> None:
    """A photo-based Combined Ticket may already carry a Reweigh Reference
    OCR'd off the ticket - pressing Enter at the mid-flow reweigh-reference
    prompt must keep it, not blank it out (see ADR 0007)."""
    ticket_with_ref = replace(COMBINED, reweigh_reference="R777")
    responses = iter(
        [
            "y",  # weigh it now
            "",  # press Enter - keep the existing reweigh reference
            "",  # enter the Solo Ticket manually
            "5000",
            "9720",
            "14720",
            "R777",
            "y",  # confirm saving the Solo Ticket
            "0",
        ]
    )

    def read(prompt: str) -> str:
        return next(responses)

    result = decide_solo_ticket(read, ticket_with_ref, [], truck_id=1)

    assert result.ticket.reweigh_reference == "R777"
    assert result.solo_ticket is not None


# --- _ask_solo_ticket_choice ---------------------------------------------------


def test_ask_solo_ticket_choice_two_way_when_reuse_unavailable() -> None:
    prompts: list[str] = []
    responses = iter(["y"])

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    result = _ask_solo_ticket_choice(read, reuse_available=False)

    assert result == "weigh_now"
    assert "reuse" not in prompts[0].lower()


def test_ask_solo_ticket_choice_three_way_when_reuse_available() -> None:
    prompts: list[str] = []
    responses = iter(["r"])

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    result = _ask_solo_ticket_choice(read, reuse_available=True)

    assert result == "reuse"
    assert "last known weight" in prompts[0].lower()


# --- _collect_reused_solo_ticket -----------------------------------------------


def test_collect_reused_solo_ticket_unchanged_returns_past_solo_as_is() -> None:
    past = _past_record(truck_id=1, solo_ticket=PAST_SOLO)
    responses = iter(["n"])

    def read(prompt: str) -> str:
        return next(responses)

    solo, timestamp, is_unverified = _collect_reused_solo_ticket(read, past)

    assert solo == PAST_SOLO
    assert timestamp == PAST_TIMESTAMP
    assert is_unverified is False


def test_collect_reused_solo_ticket_adjusted_carries_rest_forward() -> None:
    past = _past_record(truck_id=1, solo_ticket=PAST_SOLO)
    responses = iter(["y", "15000"])

    def read(prompt: str) -> str:
        return next(responses)

    solo, timestamp, is_unverified = _collect_reused_solo_ticket(read, past)

    assert solo == replace(PAST_SOLO, gross=15000)
    assert solo.steer == PAST_SOLO.steer
    assert solo.drive == PAST_SOLO.drive
    assert timestamp == PAST_TIMESTAMP
    assert is_unverified is True


def test_collect_reused_solo_ticket_adjusted_reprompts_on_non_positive_gross() -> None:
    """A sign-typo'd negative adjusted Gross Weight (issue #22) must
    re-prompt for that field via the same retry loop `_prompt_until_valid`
    already uses for an unparseable value, not be silently carried into the
    replaced `SoloTicket` - see `_read_positive_float`. This is a regression
    test: `solo_ticket.py` was extracted (#29) from a branch point before
    #22's fix landed, so this call site briefly reverted to the
    unvalidated `_read_float`."""
    past = _past_record(truck_id=1, solo_ticket=PAST_SOLO)
    responses = iter(["y", "-15000", "15000"])  # changed; rejected; accepted

    def read(prompt: str) -> str:
        return next(responses)

    solo, timestamp, is_unverified = _collect_reused_solo_ticket(read, past)

    assert solo == replace(PAST_SOLO, gross=15000)
    assert timestamp == PAST_TIMESTAMP
    assert is_unverified is True
