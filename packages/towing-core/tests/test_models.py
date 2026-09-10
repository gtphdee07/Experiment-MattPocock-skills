from towing_core.models import CombinedTicket, SoloTicket


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
