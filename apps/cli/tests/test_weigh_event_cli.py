from dataclasses import replace
from pathlib import Path

import pytest
from towing_cli.cli import (
    LEGAL_DISCLAIMER,
    collect_combined_ticket,
    collect_combined_ticket_from_photo,
    collect_combined_ticket_interactive,
    collect_solo_ticket,
    collect_solo_ticket_from_photo,
    collect_solo_ticket_interactive,
    determine_solo_link,
    format_weigh_event_results,
    run_weigh_event,
    run_weigh_event_history,
    select_profile,
)
from towing_core.calculations import (
    AxleCheckResult,
    AxleOverloadResult,
    GcwrOverloadResult,
    HitchedGvwrOverloadResult,
    TrailerGvwrOverloadResult,
)
from towing_core.field_acquisition import FieldSourceUnavailableError
from towing_core.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile
from towing_core.storage import (
    InMemoryTrailerStore,
    InMemoryTruckStore,
    InMemoryWeighEventStore,
    WeighEventRecord,
)

TRUCK = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500)
TRAILER = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)
FIXED_TIMESTAMP = "2026-09-05T12:00:00+00:00"


def _fixed_now() -> str:
    return FIXED_TIMESTAMP


class _FakeTicketFieldSource:
    """A canned field source standing in for CAT Scale ticket OCR in tests -
    implements the `TextFieldSource` shape (numeric `propose` plus text
    `propose_text`) that `ClaudeVisionScaleTicketFieldSource` provides."""

    def __init__(
        self,
        numeric_values: dict[str, float | None],
        text_values: dict[str, str | None] | None = None,
    ) -> None:
        self._numeric_values = numeric_values
        self._text_values = text_values or {}

    def propose(self, field: str) -> float | None:
        return self._numeric_values.get(field)

    def propose_text(self, field: str) -> str | None:
        return self._text_values.get(field)


class _UnavailableTicketFieldSource:
    """Simulates the extraction service itself being unreachable."""

    def propose(self, field: str) -> float | None:
        raise FieldSourceUnavailableError("simulated outage")

    def propose_text(self, field: str) -> str | None:
        raise FieldSourceUnavailableError("simulated outage")


# --- collect_combined_ticket ------------------------------------------------


def test_collect_combined_ticket_returns_ticket_when_confirmed() -> None:
    responses = iter(["5640", "9080", "19680", "34400", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_combined_ticket(read)

    assert result == CombinedTicket(
        steer=5640, drive=9080, trailer_axle=19680, gross=34400
    )


def test_collect_combined_ticket_returns_none_when_declined() -> None:
    responses = iter(["5640", "9080", "19680", "34400", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_combined_ticket(read)

    assert result is None


def test_collect_combined_ticket_reprompts_on_invalid_number() -> None:
    responses = iter(["not-a-number", "5640", "9080", "19680", "34400", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_combined_ticket(read)

    assert result == CombinedTicket(
        steer=5640, drive=9080, trailer_axle=19680, gross=34400
    )


def test_collect_combined_ticket_confirmation_prompt_echoes_entered_values() -> None:
    responses = iter(["5640", "9080", "19680", "34400", "y"])
    prompts: list[str] = []

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    collect_combined_ticket(read)

    confirmation_prompt = prompts[-1]
    assert "5640" in confirmation_prompt
    assert "9080" in confirmation_prompt
    assert "19680" in confirmation_prompt
    assert "34400" in confirmation_prompt


# --- collect_solo_ticket -----------------------------------------------------


def test_collect_solo_ticket_returns_ticket_when_confirmed() -> None:
    responses = iter(["5000", "9720", "14720", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_solo_ticket(read)

    assert result == SoloTicket(steer=5000, drive=9720, gross=14720)


def test_collect_solo_ticket_returns_none_when_declined() -> None:
    responses = iter(["5000", "9720", "14720", "", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_solo_ticket(read)

    assert result is None


def test_collect_solo_ticket_captures_reweigh_reference_when_provided() -> None:
    responses = iter(["5000", "9720", "14720", "R12345", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_solo_ticket(read)

    assert result == SoloTicket(
        steer=5000, drive=9720, gross=14720, reweigh_reference="R12345"
    )


def test_collect_solo_ticket_reprompts_on_invalid_number() -> None:
    responses = iter(["not-a-number", "5000", "9720", "14720", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_solo_ticket(read)

    assert result == SoloTicket(steer=5000, drive=9720, gross=14720)


# --- collect_combined_ticket_from_photo (#10) --------------------------------


def test_collect_combined_ticket_from_photo_uses_proposed_values() -> None:
    field_source = _FakeTicketFieldSource(
        {"steer": 5640, "drive": 9080, "trailer_axle": 19680, "gross": 34400},
        {"timestamp": "7-12-26 10:10", "reweigh_reference": "1327426192434"},
    )
    responses = iter(["y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_combined_ticket_from_photo(read, field_source)

    assert result == CombinedTicket(
        steer=5640,
        drive=9080,
        trailer_axle=19680,
        gross=34400,
        timestamp="7-12-26 10:10",
        reweigh_reference="1327426192434",
    )


def test_collect_combined_ticket_from_photo_returns_none_when_declined() -> None:
    field_source = _FakeTicketFieldSource(
        {"steer": 5640, "drive": 9080, "trailer_axle": 19680, "gross": 34400}
    )
    responses = iter(["", "", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_combined_ticket_from_photo(read, field_source)

    assert result is None


def test_collect_combined_ticket_from_photo_falls_back_when_field_missing() -> None:
    # trailer_axle couldn't be read from the photo - the user must type it.
    # timestamp/reweigh_reference are also unproposed here, each falling
    # back to an (optional, left blank) manual prompt.
    field_source = _FakeTicketFieldSource(
        {"steer": 5640, "drive": 9080, "gross": 34400}
    )
    responses = iter(["19680", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_combined_ticket_from_photo(read, field_source)

    assert result == CombinedTicket(
        steer=5640, drive=9080, trailer_axle=19680, gross=34400
    )


def test_collect_combined_ticket_from_photo_falls_back_fully_on_service_outage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    field_source = _UnavailableTicketFieldSource()
    responses = iter(["5640", "9080", "19680", "34400", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_combined_ticket_from_photo(read, field_source)

    assert result == CombinedTicket(
        steer=5640, drive=9080, trailer_axle=19680, gross=34400
    )
    printed = capsys.readouterr().out.lower()
    assert "service" in printed


# --- collect_solo_ticket_from_photo (#10) -------------------------------------


def test_collect_solo_ticket_from_photo_uses_proposed_values() -> None:
    # reweigh_reference isn't proposed here, falling back to an (optional,
    # left blank) manual prompt - same as a real Solo Ticket, which
    # typically carries no Reweigh Reference of its own.
    field_source = _FakeTicketFieldSource(
        {"steer": 5560, "drive": 4420, "gross": 9980},
        {"timestamp": "7-11-26 15:50"},
    )
    responses = iter(["", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_solo_ticket_from_photo(read, field_source)

    assert result == SoloTicket(
        steer=5560, drive=4420, gross=9980, timestamp="7-11-26 15:50"
    )


def test_collect_solo_ticket_from_photo_never_asks_for_trailer_axle() -> None:
    """A Solo Ticket has no Trailer Axle field at all (see CONTEXT.md: Solo
    Ticket) - the photo-based collector must never even ask the field source
    to propose one, since SoloTicket has nowhere to put it."""

    class _AssertsNoTrailerAxle:
        def propose(self, field: str) -> float | None:
            assert field != "trailer_axle"
            return {"steer": 5560, "drive": 4420, "gross": 9980}.get(field)

        def propose_text(self, field: str) -> str | None:
            return None

    responses = iter(["", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_solo_ticket_from_photo(read, _AssertsNoTrailerAxle())

    assert result == SoloTicket(steer=5560, drive=4420, gross=9980)


def test_collect_solo_ticket_from_photo_falls_back_fully_on_service_outage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    field_source = _UnavailableTicketFieldSource()
    responses = iter(["5560", "4420", "9980", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = collect_solo_ticket_from_photo(read, field_source)

    assert result == SoloTicket(steer=5560, drive=4420, gross=9980)
    printed = capsys.readouterr().out.lower()
    assert "service" in printed


# --- collect_combined_ticket_interactive / collect_solo_ticket_interactive ---


def test_collect_combined_ticket_interactive_manual_by_default() -> None:
    responses = iter(["", "5640", "9080", "19680", "34400", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    def field_source_factory(photo_path: Path) -> _FakeTicketFieldSource:
        raise AssertionError("should not build a field source for manual entry")

    result = collect_combined_ticket_interactive(read, field_source_factory)

    assert result == CombinedTicket(
        steer=5640, drive=9080, trailer_axle=19680, gross=34400
    )


def test_collect_combined_ticket_interactive_uses_photo_when_chosen() -> None:
    responses = iter(["p", "photo.jpg", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    field_source = _FakeTicketFieldSource(
        {"steer": 5640, "drive": 9080, "trailer_axle": 19680, "gross": 34400}
    )

    def field_source_factory(photo_path: Path) -> _FakeTicketFieldSource:
        assert photo_path == Path("photo.jpg")
        return field_source

    result = collect_combined_ticket_interactive(read, field_source_factory)

    assert result == CombinedTicket(
        steer=5640, drive=9080, trailer_axle=19680, gross=34400
    )


def test_collect_solo_ticket_interactive_manual_by_default() -> None:
    responses = iter(["", "5560", "4420", "9980", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    def field_source_factory(photo_path: Path) -> _FakeTicketFieldSource:
        raise AssertionError("should not build a field source for manual entry")

    result = collect_solo_ticket_interactive(read, field_source_factory)

    assert result == SoloTicket(steer=5560, drive=4420, gross=9980)


def test_collect_solo_ticket_interactive_uses_photo_when_chosen() -> None:
    responses = iter(["p", "photo.jpg", "", "", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    field_source = _FakeTicketFieldSource({"steer": 5560, "drive": 4420, "gross": 9980})

    def field_source_factory(photo_path: Path) -> _FakeTicketFieldSource:
        assert photo_path == Path("photo.jpg")
        return field_source

    result = collect_solo_ticket_interactive(read, field_source_factory)

    assert result == SoloTicket(steer=5560, drive=4420, gross=9980)


# --- determine_solo_link ------------------------------------------------------


def test_determine_solo_link_links_automatically_on_matching_reference() -> None:
    combined = CombinedTicket(
        steer=5640,
        drive=9080,
        trailer_axle=19680,
        gross=34400,
        reweigh_reference="R12345",
    )
    solo = SoloTicket(steer=5000, drive=9720, gross=14720, reweigh_reference="R12345")

    def read(prompt: str) -> str:
        raise AssertionError("should not prompt when references match")

    result = determine_solo_link(read, combined, solo)

    assert result is True


def test_determine_solo_link_matches_case_insensitively_and_ignores_space() -> None:
    combined = CombinedTicket(
        steer=5640,
        drive=9080,
        trailer_axle=19680,
        gross=34400,
        reweigh_reference=" r12345 ",
    )
    solo = SoloTicket(steer=5000, drive=9720, gross=14720, reweigh_reference="R12345")

    def read(prompt: str) -> str:
        raise AssertionError("should not prompt when references match")

    result = determine_solo_link(read, combined, solo)

    assert result is True


def test_determine_solo_link_falls_back_to_manual_confirm_on_mismatch() -> None:
    combined = CombinedTicket(
        steer=5640,
        drive=9080,
        trailer_axle=19680,
        gross=34400,
        reweigh_reference="R12345",
    )
    solo = SoloTicket(steer=5000, drive=9720, gross=14720, reweigh_reference="R99999")
    responses = iter(["y"])

    def read(prompt: str) -> str:
        return next(responses)

    result = determine_solo_link(read, combined, solo)

    assert result is True


def test_determine_solo_link_falls_back_when_reference_missing() -> None:
    combined = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)
    solo = SoloTicket(steer=5000, drive=9720, gross=14720)
    responses = iter(["n"])

    def read(prompt: str) -> str:
        return next(responses)

    result = determine_solo_link(read, combined, solo)

    assert result is False


# --- select_profile ----------------------------------------------------------


def test_select_profile_returns_chosen_profile() -> None:
    other_truck = TruckProfile(gvwr=10000, front_gawr=5000, rear_gawr=5000)
    profiles = [TRUCK, other_truck]
    responses = iter(["2"])

    def read(prompt: str) -> str:
        return next(responses)

    result = select_profile(read, profiles, "Truck Profile")

    assert result == other_truck


def test_select_profile_reprompts_on_out_of_range_selection() -> None:
    profiles = [TRUCK]
    responses = iter(["5", "1"])

    def read(prompt: str) -> str:
        return next(responses)

    result = select_profile(read, profiles, "Truck Profile")

    assert result == TRUCK


def test_select_profile_reprompts_on_non_numeric_selection() -> None:
    profiles = [TRUCK]
    responses = iter(["nope", "1"])

    def read(prompt: str) -> str:
        return next(responses)

    result = select_profile(read, profiles, "Truck Profile")

    assert result == TRUCK


# --- run_weigh_event (end to end, with capsys) ------------------------------


def test_run_weigh_event_reports_worked_example_results(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()

    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "y", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "Axle Overload" in output
    assert "Hitched GVWR Overload" in output
    assert LEGAL_DISCLAIMER in output
    # Worked example: no axle overload, but a Hitched GVWR Overload.
    assert "14720" in output
    assert "14000" in output


def test_run_weigh_event_declines_without_saving_or_crashing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()

    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "not recorded" in output.lower()
    assert weigh_event_store.list() == []


def test_run_weigh_event_requires_at_least_one_truck_profile(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()

    def read(prompt: str) -> str:
        raise AssertionError("should not prompt when no Truck Profiles exist")

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "No Truck Profiles" in output


def test_run_weigh_event_requires_at_least_one_trailer_profile(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    trailer_store = InMemoryTrailerStore()
    weigh_event_store = InMemoryWeighEventStore()

    def read(prompt: str) -> str:
        raise AssertionError("should not prompt when no Trailer Profiles exist")

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "No Trailer Profiles" in output


# --- GCWR Overload (Weigh Event) --------------------------------------------


def test_run_weigh_event_reports_gcwr_overload_and_labels_it_unverified(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # TRUCK has gcwr=32500; the worked-example Gross Weight of 34400
    # exceeds it, so GCWR Overload should fire and be labeled Unverified.
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()

    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "y", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "GCWR Overload" in output
    assert "Unverified Value" in output
    assert "GCWR Overload detected" in output

    # The Weigh Event History record should carry the GCWR Overload result
    # too, not just the two checks ticket #7 originally persisted.
    [record] = weigh_event_store.list()
    assert record.gcwr_result is not None
    assert record.gcwr_result.is_overloaded is True


def test_run_weigh_event_reports_not_evaluated_when_no_gcwr_on_file(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_without_gcwr = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900)
    truck_store = InMemoryTruckStore()
    truck_store.save(truck_without_gcwr)
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()

    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "y", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "GCWR Overload" in output
    assert "not evaluated" in output.lower()
    assert "no GCWR on file" in output
    # The other two checks must still run - not evaluated GCWR must not
    # block or hide them.
    assert "Axle Overload" in output
    assert "Hitched GVWR Overload" in output

    [record] = weigh_event_store.list()
    assert record.gcwr_result is None


# --- run_weigh_event: persists to History ------------------------------------


def test_run_weigh_event_saves_completed_event_to_history() -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    [saved_truck] = truck_store.list()
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    [saved_trailer] = trailer_store.list()
    weigh_event_store = InMemoryWeighEventStore()

    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "y", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read, now=_fixed_now)

    [record] = weigh_event_store.list()
    assert record.truck_id == saved_truck.id
    assert record.trailer_id == saved_trailer.id
    assert record.ticket == CombinedTicket(
        steer=5640, drive=9080, trailer_axle=19680, gross=34400
    )
    assert record.axle_result.any_overloaded is False
    assert record.gvwr_result.is_overloaded is True
    # TRUCK has gcwr=32500; this worked example's Gross Weight of 34400
    # exceeds it, so the persisted record should carry a GCWR Overload too.
    assert record.gcwr_result is not None
    assert record.gcwr_result.is_overloaded is True
    assert record.timestamp == FIXED_TIMESTAMP
    # No Solo Ticket was added in this flow - Derived Trailer Weight /
    # Trailer GVWR Overload must not be evaluated.
    assert record.solo_ticket is None
    assert record.trailer_gvwr_result is None


def test_run_weigh_event_reports_trailer_gvwr_not_evaluated_without_solo_ticket(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()

    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "y", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "Trailer GVWR Overload" in output
    assert "not evaluated" in output.lower()
    assert "Solo Ticket" in output


# --- Trailer GVWR Overload: near-limit flagging (#14, see ADR 0006) --------

_AXLE_RESULT = AxleOverloadResult(
    steer=AxleCheckResult(axle_name="Steer Axle", actual=5640, rating=6000),
    drive=AxleCheckResult(axle_name="Drive Axle", actual=9080, rating=9900),
    trailer=AxleCheckResult(axle_name="Trailer Axle", actual=19680, rating=24000),
)
_GVWR_RESULT = HitchedGvwrOverloadResult(combined_actual=14720, gvwr_rating=14000)


def test_format_weigh_event_results_flags_near_limit_trailer_gvwr() -> None:
    # 100 lbs under TRAILER's 23500 GVWR - boundary inclusive, must flag.
    trailer_gvwr_result = TrailerGvwrOverloadResult(
        derived_trailer_weight=23400, gvwr_rating=23500
    )

    output = format_weigh_event_results(
        _AXLE_RESULT, _GVWR_RESULT, None, trailer_gvwr_result
    )

    assert "no Trailer GVWR Overload detected" in output
    assert "near" in output.lower()
    assert "limit" in output.lower()


def test_format_weigh_event_results_does_not_flag_near_limit_when_comfortably_under() -> (  # noqa: E501
    None
):
    trailer_gvwr_result = TrailerGvwrOverloadResult(
        derived_trailer_weight=19680, gvwr_rating=23500
    )

    output = format_weigh_event_results(
        _AXLE_RESULT, _GVWR_RESULT, None, trailer_gvwr_result
    )

    assert "no Trailer GVWR Overload detected" in output
    assert "near" not in output.lower()


def test_format_weigh_event_results_never_flags_near_limit_when_actually_overloaded() -> (  # noqa: E501
    None
):
    # Only 100 lbs over - a tiny margin, but being over is reported as
    # overloaded, full stop, with no "close" qualifier (see ADR 0006).
    trailer_gvwr_result = TrailerGvwrOverloadResult(
        derived_trailer_weight=23600, gvwr_rating=23500
    )

    output = format_weigh_event_results(
        _AXLE_RESULT, _GVWR_RESULT, None, trailer_gvwr_result
    )

    assert "Trailer GVWR Overload detected" in output
    assert "near" not in output.lower()


def test_format_weigh_event_results_near_limit_message_says_100_lbs_when_trusted() -> (
    None
):
    # 100 lbs under - trusted (not Unverified) - message must cite the 100 lb
    # margin that actually triggered the flag (#17).
    trailer_gvwr_result = TrailerGvwrOverloadResult(
        derived_trailer_weight=23400, gvwr_rating=23500, is_unverified=False
    )

    output = format_weigh_event_results(
        _AXLE_RESULT, _GVWR_RESULT, None, trailer_gvwr_result
    )

    assert "within 100 lbs" in output
    assert "within 300 lbs" not in output


def test_format_weigh_event_results_near_limit_message_says_300_lbs_when_unverified() -> (  # noqa: E501
    None
):
    # 200 lbs under - outside the trusted 100 lb margin but within the
    # widened 300 lb margin an Unverified Value gets - message must cite the
    # 300 lb margin that actually triggered the flag, not the trusted 100 (#17).
    trailer_gvwr_result = TrailerGvwrOverloadResult(
        derived_trailer_weight=23300, gvwr_rating=23500, is_unverified=True
    )

    output = format_weigh_event_results(
        _AXLE_RESULT, _GVWR_RESULT, None, trailer_gvwr_result
    )

    assert "within 300 lbs" in output
    assert "within 100 lbs" not in output


# --- Trailer GVWR Overload: Unverified Value (#16, see ADR 0006) -----------


def test_format_weigh_event_results_labels_unverified_trailer_gvwr() -> None:
    trailer_gvwr_result = TrailerGvwrOverloadResult(
        derived_trailer_weight=19680, gvwr_rating=23500, is_unverified=True
    )

    output = format_weigh_event_results(
        _AXLE_RESULT, _GVWR_RESULT, None, trailer_gvwr_result
    )

    trailer_section = output.split("Trailer GVWR Overload")[1].split("\n\n")[0]
    assert "Unverified Value" in trailer_section


def test_format_weigh_event_results_does_not_label_trusted_trailer_gvwr_unverified() -> (  # noqa: E501
    None
):
    trailer_gvwr_result = TrailerGvwrOverloadResult(
        derived_trailer_weight=19680, gvwr_rating=23500, is_unverified=False
    )

    output = format_weigh_event_results(
        _AXLE_RESULT, _GVWR_RESULT, None, trailer_gvwr_result
    )

    trailer_section = output.split("Trailer GVWR Overload")[1].split("\n\n")[0]
    assert "Unverified Value" not in trailer_section


# --- Solo Ticket linking, Derived Trailer Weight, Trailer GVWR Overload -----
# --- and the Time-Gap Warning (Weigh Event) ---------------------------------


def test_run_weigh_event_links_solo_automatically_on_matching_reweigh_reference(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()

    responses = iter(
        [
            "1",
            "1",
            "",
            "5640",
            "9080",
            "19680",
            "34400",
            "y",  # Combined Ticket
            "y",  # add a Solo Ticket
            "R12345",  # Combined Ticket's reweigh reference
            "",  # enter the Solo Ticket manually
            "5000",
            "9720",
            "14720",
            "R12345",
            "y",  # Solo Ticket
            # matching references -> linked automatically, no manual prompt
            "0",  # hours apart
        ]
    )

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "linked automatically" in output.lower()
    assert "Derived Trailer Weight" in output
    assert "19680" in output
    assert "Trailer GVWR Overload" in output

    [record] = weigh_event_store.list()
    assert record.solo_ticket == SoloTicket(
        steer=5000, drive=9720, gross=14720, reweigh_reference="R12345"
    )
    assert record.trailer_gvwr_result is not None
    assert record.trailer_gvwr_result.derived_trailer_weight == 19680
    assert record.trailer_gvwr_result.is_overloaded is False
    assert record.time_gap_hours == 0.0


def test_run_weigh_event_falls_back_to_manual_link_on_reference_mismatch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()

    responses = iter(
        [
            "1",
            "1",
            "",
            "5640",
            "9080",
            "19680",
            "34400",
            "y",
            "y",  # add a Solo Ticket
            "R12345",  # Combined Ticket's reweigh reference
            "",  # enter the Solo Ticket manually
            "5000",
            "9720",
            "14720",
            "R99999",
            "y",  # Solo Ticket (different ref)
            "y",  # manual confirm: yes, same Weigh Event
            "5",  # hours apart - exceeds the default 4-hour threshold
        ]
    )

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "Time-Gap Warning" in output
    assert "4" in output  # the threshold is named in the warning

    [record] = weigh_event_store.list()
    assert record.solo_ticket is not None
    assert record.trailer_gvwr_result is not None
    assert record.time_gap_hours == 5.0
    # The warning is advisory only - the Weigh Event is still fully recorded.
    assert record.id is not None


def test_run_weigh_event_discards_solo_ticket_when_manual_link_declined(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()

    responses = iter(
        [
            "1",
            "1",
            "",
            "5640",
            "9080",
            "19680",
            "34400",
            "y",
            "y",  # add a Solo Ticket
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

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "not linked" in output.lower() or "discard" in output.lower()
    assert "not evaluated" in output.lower()

    [record] = weigh_event_store.list()
    assert record.solo_ticket is None
    assert record.trailer_gvwr_result is None
    assert record.time_gap_hours is None


def test_run_weigh_event_no_time_gap_warning_within_threshold(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()

    responses = iter(
        [
            "1",
            "1",
            "",
            "5640",
            "9080",
            "19680",
            "34400",
            "y",
            "y",
            "R1",
            "",  # enter the Solo Ticket manually
            "5000",
            "9720",
            "14720",
            "R1",
            "y",
            "1",  # well within the default 4-hour threshold
        ]
    )

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "Time-Gap Warning" in output
    # No alarming language in the Time-Gap section when within threshold.
    time_gap_section = output[output.index("Time-Gap Warning") :]
    assert "warning:" not in time_gap_section.lower()
    assert "within the" in time_gap_section.lower()


# --- Reused Solo Weight (Weigh Event) ---------------------------------------

PAST_SOLO = SoloTicket(steer=5000, drive=9720, gross=14720)
PAST_TIMESTAMP = "2026-01-15T09:00:00+00:00"


def _seed_past_solo_record(
    weigh_event_store: InMemoryWeighEventStore,
    *,
    truck_id: int,
    timestamp: str = PAST_TIMESTAMP,
    solo_ticket: SoloTicket = PAST_SOLO,
) -> None:
    """Seed a past Weigh Event, for `truck_id`, with a linked Solo Ticket -
    the history "reuse last known weight" needs to be offered at all (see
    CONTEXT.md: Reused Solo Weight)."""
    weigh_event_store.save(
        _make_record(
            truck_id,
            999,
            timestamp,
            axle_overloaded=False,
            gvwr_overloaded=False,
            solo_ticket=solo_ticket,
            trailer_gvwr_result=TrailerGvwrOverloadResult(
                derived_trailer_weight=19680, gvwr_rating=23500
            ),
        )
    )


def test_run_weigh_event_reuse_not_offered_without_history(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()

    prompts: list[str] = []
    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "y", "n"])

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    assert "Add a Solo Ticket for this Weigh Event? [y/N]: " in prompts
    assert not any("reuse" in p.lower() for p in prompts)


def test_run_weigh_event_reuse_not_offered_for_different_truck(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    [saved_truck] = truck_store.list()
    assert saved_truck.id is not None
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()
    _seed_past_solo_record(weigh_event_store, truck_id=saved_truck.id + 1000)

    prompts: list[str] = []
    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "y", "n"])

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    assert "Add a Solo Ticket for this Weigh Event? [y/N]: " in prompts
    assert not any("reuse" in p.lower() for p in prompts)


def test_run_weigh_event_three_way_prompt_offered_when_reuse_available(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    [saved_truck] = truck_store.list()
    assert saved_truck.id is not None
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()
    _seed_past_solo_record(weigh_event_store, truck_id=saved_truck.id)

    prompts: list[str] = []
    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "y", "n"])

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    solo_prompt = next(p for p in prompts if "Add a Solo Ticket" in p)
    assert "last known weight" in solo_prompt.lower()


def test_run_weigh_event_reuse_last_known_solo_weight_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    [saved_truck] = truck_store.list()
    assert saved_truck.id is not None
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()
    _seed_past_solo_record(weigh_event_store, truck_id=saved_truck.id)

    responses = iter(
        [
            "1",
            "1",
            "",
            "5640",
            "9080",
            "19680",
            "34400",
            "y",  # Combined Ticket
            "r",  # reuse last known Solo weight
            "n",  # nothing has changed since then
        ]
    )

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "14720" in output
    assert PAST_TIMESTAMP in output
    assert "Trailer GVWR Overload" in output

    new_record = weigh_event_store.list()[-1]
    assert new_record.solo_ticket == PAST_SOLO
    assert new_record.reused_solo_from_timestamp == PAST_TIMESTAMP
    assert new_record.trailer_gvwr_result is not None
    assert new_record.trailer_gvwr_result.derived_trailer_weight == 19680
    assert new_record.trailer_gvwr_result.is_overloaded is False
    # Reusing a weight means no fresh Solo Ticket was entered, so the
    # Time-Gap Warning (a same-visit-pair concept) never runs (ADR 0006).
    assert new_record.time_gap_hours is None


def test_run_weigh_event_reuse_picks_most_recent_solo_record(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    [saved_truck] = truck_store.list()
    assert saved_truck.id is not None
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()
    newer_solo = PAST_SOLO
    older_solo = SoloTicket(steer=4900, drive=9500, gross=14400)
    # Insert the newer record first, older second - proves selection is by
    # timestamp, not merely "last in the list".
    _seed_past_solo_record(
        weigh_event_store,
        truck_id=saved_truck.id,
        timestamp="2026-03-01T00:00:00+00:00",
        solo_ticket=newer_solo,
    )
    _seed_past_solo_record(
        weigh_event_store,
        truck_id=saved_truck.id,
        timestamp="2026-01-01T00:00:00+00:00",
        solo_ticket=older_solo,
    )

    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "y", "r", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "14720" in output
    assert "2026-03-01T00:00:00+00:00" in output

    new_record = weigh_event_store.list()[-1]
    assert new_record.solo_ticket == newer_solo
    assert new_record.reused_solo_from_timestamp == "2026-03-01T00:00:00+00:00"


def test_run_weigh_event_reuse_reports_change_collects_new_gross_weight(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Issue #16: reporting a change during reuse prompts for a new Gross
    Weight, and the resulting Solo Ticket carries that new figure - marking
    Trailer GVWR Overload for this Weigh Event an Unverified Value (see
    CONTEXT.md: Unverified Value; ADR 0006)."""
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    [saved_truck] = truck_store.list()
    assert saved_truck.id is not None
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()
    _seed_past_solo_record(weigh_event_store, truck_id=saved_truck.id)

    responses = iter(
        [
            "1",
            "1",
            "",
            "5640",
            "9080",
            "19680",
            "34400",
            "y",  # Combined Ticket
            "r",  # reuse last known Solo weight
            "y",  # something has changed
            "15000",  # new Gross Weight
        ]
    )

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "Unverified Value" in output
    # Derived Trailer Weight: 34400 - 15000 = 19400.
    assert "19400" in output

    new_record = weigh_event_store.list()[-1]
    assert new_record.solo_ticket == replace(PAST_SOLO, gross=15000)
    assert new_record.reused_solo_from_timestamp == PAST_TIMESTAMP
    assert new_record.reused_solo_is_unverified is True
    assert new_record.trailer_gvwr_result is not None
    assert new_record.trailer_gvwr_result.derived_trailer_weight == 19400
    assert new_record.trailer_gvwr_result.is_unverified is True


def test_run_weigh_event_reuse_unchanged_is_never_unverified(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unchanged reused weight (#15) is never labeled Unverified."""
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    [saved_truck] = truck_store.list()
    assert saved_truck.id is not None
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()
    _seed_past_solo_record(weigh_event_store, truck_id=saved_truck.id)

    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "y", "r", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    new_record = weigh_event_store.list()[-1]
    assert new_record.reused_solo_is_unverified is False
    assert new_record.trailer_gvwr_result is not None
    assert new_record.trailer_gvwr_result.is_unverified is False

    output = capsys.readouterr().out
    trailer_section = output.split("Trailer GVWR Overload")[1].split("\n\n")[0]
    assert "Unverified Value" not in trailer_section


def test_run_weigh_event_weigh_now_unchanged_when_reuse_available(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    [saved_truck] = truck_store.list()
    assert saved_truck.id is not None
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()
    _seed_past_solo_record(weigh_event_store, truck_id=saved_truck.id)

    responses = iter(
        [
            "1",
            "1",
            "",
            "5640",
            "9080",
            "19680",
            "34400",
            "y",  # Combined Ticket
            "y",  # weigh solo now, despite reuse being offered
            "R555",  # Combined Ticket's reweigh reference
            "",  # enter the Solo Ticket manually
            "5100",
            "9600",
            "14700",
            "R555",
            "y",  # confirm Solo Ticket
            "0",  # hours apart
        ]
    )

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    output = capsys.readouterr().out
    assert "linked automatically" in output.lower()

    new_record = weigh_event_store.list()[-1]
    assert new_record.solo_ticket == SoloTicket(
        steer=5100, drive=9600, gross=14700, reweigh_reference="R555"
    )
    assert new_record.reused_solo_from_timestamp is None
    assert new_record.time_gap_hours == 0.0


def test_run_weigh_event_skip_unchanged_when_reuse_available(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    [saved_truck] = truck_store.list()
    assert saved_truck.id is not None
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()
    _seed_past_solo_record(weigh_event_store, truck_id=saved_truck.id)

    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "y", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    new_record = weigh_event_store.list()[-1]
    assert new_record.solo_ticket is None
    assert new_record.reused_solo_from_timestamp is None
    assert new_record.trailer_gvwr_result is None


# --- run_weigh_event_history --------------------------------------------------


def _make_record(
    truck_id: int,
    trailer_id: int,
    timestamp: str,
    *,
    axle_overloaded: bool,
    gvwr_overloaded: bool,
    gcwr_result: GcwrOverloadResult | None = None,
    solo_ticket: SoloTicket | None = None,
    trailer_gvwr_result: TrailerGvwrOverloadResult | None = None,
    time_gap_hours: float | None = None,
    reused_solo_from_timestamp: str | None = None,
    reused_solo_is_unverified: bool = False,
) -> WeighEventRecord:
    trailer_actual = 24500 if axle_overloaded else 19680
    return WeighEventRecord(
        truck_id=truck_id,
        trailer_id=trailer_id,
        ticket=CombinedTicket(
            steer=5640, drive=9080, trailer_axle=trailer_actual, gross=34400
        ),
        axle_result=AxleOverloadResult(
            steer=AxleCheckResult(axle_name="Steer Axle", actual=5640, rating=6000),
            drive=AxleCheckResult(axle_name="Drive Axle", actual=9080, rating=9900),
            trailer=AxleCheckResult(
                axle_name="Trailer Axle", actual=trailer_actual, rating=24000
            ),
        ),
        gvwr_result=HitchedGvwrOverloadResult(
            combined_actual=15000 if gvwr_overloaded else 14000, gvwr_rating=14500
        ),
        gcwr_result=gcwr_result,
        solo_ticket=solo_ticket,
        trailer_gvwr_result=trailer_gvwr_result,
        time_gap_hours=time_gap_hours,
        reused_solo_from_timestamp=reused_solo_from_timestamp,
        reused_solo_is_unverified=reused_solo_is_unverified,
        timestamp=timestamp,
    )


def test_run_weigh_event_history_with_no_events_prints_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weigh_event_store = InMemoryWeighEventStore()

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "no weigh events" in output.lower()


def test_run_weigh_event_history_lists_events_in_chronological_order(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        _make_record(
            1,
            2,
            "2026-09-01T08:00:00+00:00",
            axle_overloaded=False,
            gvwr_overloaded=False,
        )
    )
    weigh_event_store.save(
        _make_record(
            3,
            4,
            "2026-09-05T12:00:00+00:00",
            axle_overloaded=True,
            gvwr_overloaded=True,
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    first_index = output.index("2026-09-01T08:00:00+00:00")
    second_index = output.index("2026-09-05T12:00:00+00:00")
    assert first_index < second_index
    # Each entry names its Truck+Trailer pairing.
    assert "1" in output and "2" in output
    assert "3" in output and "4" in output
    # Each check's result is shown - the first event passes both, the second
    # fails both.
    assert output.count("OVERLOADED") >= 2
    assert "OK" in output
    assert LEGAL_DISCLAIMER in output


def test_run_weigh_event_history_shows_gcwr_result_when_present(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        _make_record(
            1,
            2,
            "2026-09-05T12:00:00+00:00",
            axle_overloaded=False,
            gvwr_overloaded=False,
            gcwr_result=GcwrOverloadResult(combined_actual=34400, gcwr_rating=32500),
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "GCWR Overload" in output
    assert "OVERLOADED" in output


def test_run_weigh_event_history_shows_not_evaluated_when_no_gcwr_result(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        _make_record(
            1,
            2,
            "2026-09-05T12:00:00+00:00",
            axle_overloaded=False,
            gvwr_overloaded=False,
            gcwr_result=None,
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "GCWR Overload" in output
    assert "not evaluated" in output.lower()


def test_run_weigh_event_history_shows_trailer_gvwr_result_when_present(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        _make_record(
            1,
            2,
            "2026-09-05T12:00:00+00:00",
            axle_overloaded=False,
            gvwr_overloaded=False,
            solo_ticket=SoloTicket(steer=5000, drive=9720, gross=14720),
            trailer_gvwr_result=TrailerGvwrOverloadResult(
                derived_trailer_weight=19680, gvwr_rating=23500
            ),
            time_gap_hours=1.0,
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "Trailer GVWR Overload" in output
    assert "19680" in output
    assert "23500" in output
    assert "Time-Gap" in output


def test_run_weigh_event_history_flags_near_limit_trailer_gvwr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        _make_record(
            1,
            2,
            "2026-09-05T12:00:00+00:00",
            axle_overloaded=False,
            gvwr_overloaded=False,
            solo_ticket=SoloTicket(steer=5000, drive=9720, gross=14720),
            trailer_gvwr_result=TrailerGvwrOverloadResult(
                derived_trailer_weight=23400, gvwr_rating=23500
            ),
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "near" in output.lower()
    assert "limit" in output.lower()


def test_run_weigh_event_history_never_flags_near_limit_when_actually_overloaded(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        _make_record(
            1,
            2,
            "2026-09-05T12:00:00+00:00",
            axle_overloaded=False,
            gvwr_overloaded=False,
            solo_ticket=SoloTicket(steer=5000, drive=9720, gross=14720),
            trailer_gvwr_result=TrailerGvwrOverloadResult(
                derived_trailer_weight=23600, gvwr_rating=23500
            ),
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "OVERLOADED" in output
    assert "near" not in output.lower()


def test_run_weigh_event_history_near_limit_message_says_100_lbs_when_trusted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        _make_record(
            1,
            2,
            "2026-09-05T12:00:00+00:00",
            axle_overloaded=False,
            gvwr_overloaded=False,
            solo_ticket=SoloTicket(steer=5000, drive=9720, gross=14720),
            trailer_gvwr_result=TrailerGvwrOverloadResult(
                derived_trailer_weight=23400, gvwr_rating=23500, is_unverified=False
            ),
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "within 100 lbs" in output
    assert "within 300 lbs" not in output


def test_run_weigh_event_history_near_limit_message_says_300_lbs_when_unverified(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        _make_record(
            1,
            2,
            "2026-09-05T12:00:00+00:00",
            axle_overloaded=False,
            gvwr_overloaded=False,
            solo_ticket=SoloTicket(steer=5000, drive=9720, gross=14720),
            trailer_gvwr_result=TrailerGvwrOverloadResult(
                derived_trailer_weight=23300, gvwr_rating=23500, is_unverified=True
            ),
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "within 300 lbs" in output
    assert "within 100 lbs" not in output


def test_run_weigh_event_history_shows_trailer_gvwr_not_evaluated_without_solo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        _make_record(
            1,
            2,
            "2026-09-05T12:00:00+00:00",
            axle_overloaded=False,
            gvwr_overloaded=False,
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "Trailer GVWR Overload" in output
    assert "not evaluated" in output.lower()


def test_run_weigh_event_history_shows_reused_solo_date_when_present(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        _make_record(
            1,
            2,
            "2026-09-05T12:00:00+00:00",
            axle_overloaded=False,
            gvwr_overloaded=False,
            solo_ticket=SoloTicket(steer=5000, drive=9720, gross=14720),
            trailer_gvwr_result=TrailerGvwrOverloadResult(
                derived_trailer_weight=19680, gvwr_rating=23500
            ),
            reused_solo_from_timestamp="2026-01-15T09:00:00+00:00",
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "2026-01-15T09:00:00+00:00" in output


def test_run_weigh_event_history_no_reused_solo_line_when_solo_ticket_fresh(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        _make_record(
            1,
            2,
            "2026-09-05T12:00:00+00:00",
            axle_overloaded=False,
            gvwr_overloaded=False,
            solo_ticket=SoloTicket(steer=5000, drive=9720, gross=14720),
            trailer_gvwr_result=TrailerGvwrOverloadResult(
                derived_trailer_weight=19680, gvwr_rating=23500
            ),
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "reused" not in output.lower()


# --- Nickname snapshot (#12) -------------------------------------------------


def test_run_weigh_event_snapshots_nicknames_at_save_time() -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(replace(TRUCK, nickname="Addie"))
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(replace(TRAILER, nickname="Goose"))
    weigh_event_store = InMemoryWeighEventStore()

    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "y", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    [record] = weigh_event_store.list()
    assert record.truck_nickname == "Addie"
    assert record.trailer_nickname == "Goose"


def test_run_weigh_event_snapshots_computed_default_when_nickname_blank() -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    [saved_truck] = truck_store.list()
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    [saved_trailer] = trailer_store.list()
    weigh_event_store = InMemoryWeighEventStore()

    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "y", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    [record] = weigh_event_store.list()
    assert record.truck_nickname == f"Truck {saved_truck.id}"
    assert record.trailer_nickname == f"Trailer {saved_trailer.id}"


def test_run_weigh_event_history_shows_nickname_snapshot(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        replace(
            _make_record(
                1,
                2,
                "2026-09-05T12:00:00+00:00",
                axle_overloaded=False,
                gvwr_overloaded=False,
            ),
            truck_nickname="Addie",
            trailer_nickname="Goose",
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "Addie" in output
    assert "Goose" in output
    assert "Truck Profile #1" not in output
    assert "Trailer Profile #2" not in output


def test_run_weigh_event_history_falls_back_to_id_when_no_nickname_snapshot(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A record persisted before this field existed - `truck_nickname`/
    # `trailer_nickname` are `None`, not a real Nickname that was never
    # captured, so the pre-Nickname ID-only display is used instead of a
    # guess (see `WeighEventRecord`'s docstring).
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        _make_record(
            1,
            2,
            "2026-09-05T12:00:00+00:00",
            axle_overloaded=False,
            gvwr_overloaded=False,
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "Truck Profile #1" in output
    assert "Trailer Profile #2" in output


def test_run_weigh_event_history_keeps_old_nickname_after_profile_renamed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Renaming a Truck Profile after a Weigh Event was already recorded
    must not change how that past entry renders - the snapshot on the
    record is independent of the Profile's current state (see CONTEXT.md:
    Nickname, ADR 0004, and issue #12 user stories 9/10)."""
    truck_store = InMemoryTruckStore()
    truck_store.save(replace(TRUCK, nickname="Addie"))
    [saved_truck] = truck_store.list()
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)
    weigh_event_store = InMemoryWeighEventStore()

    responses = iter(["1", "1", "", "5640", "9080", "19680", "34400", "y", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, weigh_event_store, read)

    # Rename the Truck Profile after the Weigh Event was recorded.
    truck_store.update(replace(saved_truck, nickname="Big Red"))

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "Addie" in output
    assert "Big Red" not in output


# --- Reused Solo Weight adjustment / Unverified Value (#16) ------------------


def test_run_weigh_event_history_labels_adjusted_reuse_unverified(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Issue #16: a past Weigh Event whose Solo Ticket was an adjusted reuse
    # must still render the Unverified Value label when reviewed later in
    # history (see CONTEXT.md: Unverified Value; ADR 0006).
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        _make_record(
            1,
            2,
            "2026-09-05T12:00:00+00:00",
            axle_overloaded=False,
            gvwr_overloaded=False,
            solo_ticket=SoloTicket(steer=5000, drive=9720, gross=15000),
            trailer_gvwr_result=TrailerGvwrOverloadResult(
                derived_trailer_weight=19400, gvwr_rating=23500, is_unverified=True
            ),
            reused_solo_from_timestamp="2026-01-15T09:00:00+00:00",
            reused_solo_is_unverified=True,
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "Unverified Value" in output
    assert "adjusted" in output.lower()
    assert "2026-01-15T09:00:00+00:00" in output


def test_run_weigh_event_history_unchanged_reuse_not_labeled_unverified(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weigh_event_store = InMemoryWeighEventStore()
    weigh_event_store.save(
        _make_record(
            1,
            2,
            "2026-09-05T12:00:00+00:00",
            axle_overloaded=False,
            gvwr_overloaded=False,
            solo_ticket=SoloTicket(steer=5000, drive=9720, gross=14720),
            trailer_gvwr_result=TrailerGvwrOverloadResult(
                derived_trailer_weight=19680, gvwr_rating=23500
            ),
            reused_solo_from_timestamp="2026-01-15T09:00:00+00:00",
        )
    )

    run_weigh_event_history(weigh_event_store)

    output = capsys.readouterr().out
    assert "unchanged" in output.lower()
    assert "Unverified Value" not in output
