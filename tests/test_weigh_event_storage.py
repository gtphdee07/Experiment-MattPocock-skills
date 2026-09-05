from towing_app.calculations import (
    AxleCheckResult,
    AxleOverloadResult,
    HitchedGvwrOverloadResult,
    TrailerGvwrOverloadResult,
)
from towing_app.models import CombinedTicket, SoloTicket
from towing_app.storage import InMemoryWeighEventStore, WeighEventRecord

TICKET = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)
AXLE_RESULT = AxleOverloadResult(
    steer=AxleCheckResult(axle_name="Steer Axle", actual=5640, rating=6000),
    drive=AxleCheckResult(axle_name="Drive Axle", actual=9080, rating=9900),
    trailer=AxleCheckResult(axle_name="Trailer Axle", actual=19680, rating=24000),
)
GVWR_RESULT = HitchedGvwrOverloadResult(combined_actual=14720, gvwr_rating=14000)


def _record(truck_id: int = 1, trailer_id: int = 2) -> WeighEventRecord:
    return WeighEventRecord(
        truck_id=truck_id,
        trailer_id=trailer_id,
        ticket=TICKET,
        axle_result=AXLE_RESULT,
        gvwr_result=GVWR_RESULT,
        timestamp="2026-09-05T12:00:00+00:00",
    )


def test_save_and_list_returns_saved_weigh_event_record() -> None:
    store = InMemoryWeighEventStore()
    record = _record()

    store.save(record)

    assert store.list() == [record]


def test_save_assigns_an_id() -> None:
    store = InMemoryWeighEventStore()
    store.save(_record())

    [saved] = store.list()

    assert saved.id is not None


def test_save_assigns_distinct_ids_to_successive_records() -> None:
    store = InMemoryWeighEventStore()
    store.save(_record())
    store.save(_record())

    ids = [record.id for record in store.list()]

    assert len(ids) == len(set(ids))


def test_list_returns_records_in_chronological_order() -> None:
    store = InMemoryWeighEventStore()
    first = _record(truck_id=1)
    second = _record(truck_id=2)
    store.save(first)
    store.save(second)

    result = store.list()

    assert [record.truck_id for record in result] == [1, 2]


def test_save_and_list_round_trips_linked_solo_ticket_fields() -> None:
    store = InMemoryWeighEventStore()
    record = WeighEventRecord(
        truck_id=1,
        trailer_id=2,
        ticket=TICKET,
        axle_result=AXLE_RESULT,
        gvwr_result=GVWR_RESULT,
        timestamp="2026-09-05T12:00:00+00:00",
        solo_ticket=SoloTicket(steer=5000, drive=9720, gross=14720),
        trailer_gvwr_result=TrailerGvwrOverloadResult(
            derived_trailer_weight=19680, gvwr_rating=23500
        ),
        time_gap_hours=1.5,
    )

    store.save(record)

    [saved] = store.list()
    assert saved.solo_ticket == SoloTicket(steer=5000, drive=9720, gross=14720)
    assert saved.trailer_gvwr_result == TrailerGvwrOverloadResult(
        derived_trailer_weight=19680, gvwr_rating=23500
    )
    assert saved.time_gap_hours == 1.5
