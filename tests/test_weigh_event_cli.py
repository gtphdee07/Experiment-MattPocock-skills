import pytest

from towing_app.cli import (
    LEGAL_DISCLAIMER,
    collect_combined_ticket,
    run_weigh_event,
    select_profile,
)
from towing_app.models import CombinedTicket, TrailerProfile, TruckProfile
from towing_app.storage import InMemoryTrailerStore, InMemoryTruckStore

TRUCK = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=32500)
TRAILER = TrailerProfile(gvwr=23500, gawr=8000, axle_count=3, uvw=20554)


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

    responses = iter(["1", "1", "5640", "9080", "19680", "34400", "y"])

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, read)

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

    responses = iter(["1", "1", "5640", "9080", "19680", "34400", "n"])

    def read(prompt: str) -> str:
        return next(responses)

    run_weigh_event(truck_store, trailer_store, read)

    output = capsys.readouterr().out
    assert "not recorded" in output.lower()


def test_run_weigh_event_requires_at_least_one_truck_profile(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    trailer_store = InMemoryTrailerStore()
    trailer_store.save(TRAILER)

    def read(prompt: str) -> str:
        raise AssertionError("should not prompt when no Truck Profiles exist")

    run_weigh_event(truck_store, trailer_store, read)

    output = capsys.readouterr().out
    assert "No Truck Profiles" in output


def test_run_weigh_event_requires_at_least_one_trailer_profile(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truck_store = InMemoryTruckStore()
    truck_store.save(TRUCK)
    trailer_store = InMemoryTrailerStore()

    def read(prompt: str) -> str:
        raise AssertionError("should not prompt when no Trailer Profiles exist")

    run_weigh_event(truck_store, trailer_store, read)

    output = capsys.readouterr().out
    assert "No Trailer Profiles" in output
