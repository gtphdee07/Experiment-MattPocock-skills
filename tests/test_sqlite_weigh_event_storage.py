from pathlib import Path

from towing_app.calculations import (
    AxleCheckResult,
    AxleOverloadResult,
    HitchedGvwrOverloadResult,
    TrailerGvwrOverloadResult,
)
from towing_app.models import CombinedTicket, SoloTicket
from towing_app.storage import SqliteWeighEventStore, WeighEventRecord

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


def test_save_and_list_persists_across_store_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    record = _record()

    SqliteWeighEventStore(db_path).save(record)

    assert SqliteWeighEventStore(db_path).list() == [record]


def test_save_assigns_an_id(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    SqliteWeighEventStore(db_path).save(_record())

    [saved] = SqliteWeighEventStore(db_path).list()

    assert saved.id is not None


def test_list_returns_records_in_chronological_order(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    store = SqliteWeighEventStore(db_path)
    store.save(_record(truck_id=1))
    store.save(_record(truck_id=2))

    result = SqliteWeighEventStore(db_path).list()

    assert [record.truck_id for record in result] == [1, 2]


def test_save_and_list_round_trips_linked_solo_ticket_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
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

    SqliteWeighEventStore(db_path).save(record)

    [saved] = SqliteWeighEventStore(db_path).list()
    assert saved.solo_ticket == SoloTicket(steer=5000, drive=9720, gross=14720)
    assert saved.trailer_gvwr_result == TrailerGvwrOverloadResult(
        derived_trailer_weight=19680, gvwr_rating=23500
    )
    assert saved.time_gap_hours == 1.5


def test_save_and_list_round_trips_unlinked_event_with_no_solo_ticket(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "garage.db"

    SqliteWeighEventStore(db_path).save(_record())

    [saved] = SqliteWeighEventStore(db_path).list()
    assert saved.solo_ticket is None
    assert saved.trailer_gvwr_result is None
    assert saved.time_gap_hours is None
    assert saved.reused_solo_from_timestamp is None


def test_save_and_list_round_trips_ticket_timestamp(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
    record = WeighEventRecord(
        truck_id=1,
        trailer_id=2,
        ticket=CombinedTicket(
            steer=5640,
            drive=9080,
            trailer_axle=19680,
            gross=34400,
            timestamp="7-12-26 10:10",
        ),
        axle_result=AXLE_RESULT,
        gvwr_result=GVWR_RESULT,
        timestamp="2026-09-05T12:00:00+00:00",
        solo_ticket=SoloTicket(
            steer=5000, drive=9720, gross=14720, timestamp="7-11-26 15:50"
        ),
        trailer_gvwr_result=TrailerGvwrOverloadResult(
            derived_trailer_weight=19680, gvwr_rating=23500
        ),
    )

    SqliteWeighEventStore(db_path).save(record)

    [saved] = SqliteWeighEventStore(db_path).list()
    assert saved.ticket.timestamp == "7-12-26 10:10"
    assert saved.solo_ticket is not None
    assert saved.solo_ticket.timestamp == "7-11-26 15:50"


def test_save_and_list_round_trips_reused_solo_from_timestamp(tmp_path: Path) -> None:
    db_path = tmp_path / "garage.db"
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
        reused_solo_from_timestamp="2026-01-15T09:00:00+00:00",
    )

    SqliteWeighEventStore(db_path).save(record)

    [saved] = SqliteWeighEventStore(db_path).list()
    assert saved.reused_solo_from_timestamp == "2026-01-15T09:00:00+00:00"
