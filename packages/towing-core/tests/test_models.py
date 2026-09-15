import pytest

from towing_core.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile


def test_combined_ticket_reweigh_reference_defaults_to_none() -> None:
    ticket = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)

    assert ticket.reweigh_reference is None


def test_combined_ticket_str_omits_reweigh_reference_when_absent() -> None:
    ticket = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)

    assert "Reweigh" not in str(ticket)


def test_combined_ticket_str_includes_reweigh_reference_when_present() -> None:
    ticket = CombinedTicket(
        steer=5640,
        drive=9080,
        trailer_axle=19680,
        gross=34400,
        reweigh_reference="R12345",
    )

    assert "R12345" in str(ticket)


def test_solo_ticket_str_formats_fields() -> None:
    ticket = SoloTicket(steer=5640, drive=9080, gross=14720)

    rendered = str(ticket)

    assert "5640" in rendered
    assert "9080" in rendered
    assert "14720" in rendered


def test_solo_ticket_reweigh_reference_defaults_to_none() -> None:
    ticket = SoloTicket(steer=5640, drive=9080, gross=14720)

    assert ticket.reweigh_reference is None


def test_solo_ticket_str_includes_reweigh_reference_when_present() -> None:
    ticket = SoloTicket(steer=5640, drive=9080, gross=14720, reweigh_reference="R999")

    assert "R999" in str(ticket)


def test_solo_ticket_equality() -> None:
    a = SoloTicket(steer=5640, drive=9080, gross=14720)
    b = SoloTicket(steer=5640, drive=9080, gross=14720)

    assert a == b


# --- timestamp (#10) ---------------------------------------------------------


def test_combined_ticket_timestamp_defaults_to_none() -> None:
    ticket = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)

    assert ticket.timestamp is None


def test_combined_ticket_str_omits_timestamp_when_absent() -> None:
    ticket = CombinedTicket(steer=5640, drive=9080, trailer_axle=19680, gross=34400)

    assert "Timestamp" not in str(ticket)


def test_combined_ticket_str_includes_timestamp_when_present() -> None:
    ticket = CombinedTicket(
        steer=5640,
        drive=9080,
        trailer_axle=19680,
        gross=34400,
        timestamp="7-12-26 10:10",
    )

    assert "7-12-26 10:10" in str(ticket)


def test_solo_ticket_timestamp_defaults_to_none() -> None:
    ticket = SoloTicket(steer=5640, drive=9080, gross=14720)

    assert ticket.timestamp is None


def test_solo_ticket_str_includes_timestamp_when_present() -> None:
    ticket = SoloTicket(steer=5640, drive=9080, gross=14720, timestamp="7-11-26 15:50")

    assert "7-11-26 15:50" in str(ticket)


# --- positivity floor (#22) ---------------------------------------------------


def test_truck_profile_rejects_non_positive_required_field() -> None:
    with pytest.raises(ValueError):
        TruckProfile(gvwr=14000, front_gawr=-6000, rear_gawr=9900)


def test_truck_profile_rejects_non_positive_gcwr_when_provided() -> None:
    with pytest.raises(ValueError):
        TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=-32500)


def test_truck_profile_allows_gcwr_none() -> None:
    profile = TruckProfile(gvwr=14000, front_gawr=6000, rear_gawr=9900, gcwr=None)

    assert profile.gcwr is None


def test_trailer_profile_rejects_non_positive_required_field() -> None:
    with pytest.raises(ValueError):
        TrailerProfile(gvwr=7000, gawr=-3500, axle_count=2)


def test_trailer_profile_rejects_axle_count_below_one() -> None:
    with pytest.raises(ValueError):
        TrailerProfile(gvwr=7000, gawr=3500, axle_count=0)


def test_trailer_profile_rejects_non_positive_uvw_when_provided() -> None:
    with pytest.raises(ValueError):
        TrailerProfile(gvwr=7000, gawr=3500, axle_count=2, uvw=-1200)


def test_combined_ticket_rejects_non_positive_required_field() -> None:
    with pytest.raises(ValueError):
        CombinedTicket(steer=6000, drive=-6500, trailer_axle=3000, gross=8000)


def test_solo_ticket_rejects_non_positive_required_field() -> None:
    with pytest.raises(ValueError):
        SoloTicket(steer=5640, drive=-9080, gross=14720)
