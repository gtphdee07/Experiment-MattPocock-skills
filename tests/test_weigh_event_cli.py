import pytest

from towing_app.calculations import (
    AxleCheckResult,
    AxleOverloadResult,
    GcwrOverloadResult,
    HitchedGvwrOverloadResult,
)
from towing_app.cli import (
    LEGAL_DISCLAIMER,
    collect_combined_ticket,
    run_weigh_event,
    run_weigh_event_history,
    select_profile,
)
from towing_app.models import CombinedTicket, TrailerProfile, TruckProfile
from towing_app.storage import (
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
    weigh_event_store = InMemoryWeighEventStore()

    responses = iter(["1", "1", "5640", "9080", "19680", "34400", "y"])

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

    responses = iter(["1", "1", "5640", "9080", "19680", "34400", "n"])

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

    responses = iter(["1", "1", "5640", "9080", "19680", "34400", "y"])

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

    responses = iter(["1", "1", "5640", "9080", "19680", "34400", "y"])

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

    responses = iter(["1", "1", "5640", "9080", "19680", "34400", "y"])

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


# --- run_weigh_event_history --------------------------------------------------


def _make_record(
    truck_id: int,
    trailer_id: int,
    timestamp: str,
    *,
    axle_overloaded: bool,
    gvwr_overloaded: bool,
    gcwr_result: GcwrOverloadResult | None = None,
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
