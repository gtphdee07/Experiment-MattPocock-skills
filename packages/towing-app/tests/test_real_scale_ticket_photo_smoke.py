"""Real, opt-in integration test against the live Claude API.

Skipped unless ANTHROPIC_API_KEY is set - this makes a real network call and
costs real API usage, so it never runs as part of the default hermetic
suite. Run explicitly with the key present to verify the real extraction
still matches the golden weights whenever the prompt, model, or SDK changes.

Ground truth for the four weights on both fixtures is provided directly by
the project owner from the physical CAT Scale tickets (see the ticket #10
task brief), not derived from any OCR output:

- tests/fixtures/cat_ticket_combined.jpg (a Combined Ticket): Steer 5640,
  Drive 9080, Trailer Axle 19680, Gross 34400 lbs.
- tests/fixtures/cat_ticket_solo.jpg (a Solo Ticket): Steer 5560, Drive
  4420, Gross 9980 lbs. No Trailer Axle golden value - a Solo Ticket has no
  such field (see CONTEXT.md: Solo Ticket) - so this test never proposes
  "trailer_axle" for it, mirroring `collect_solo_ticket_from_photo`.

Neither ticket's golden data includes a timestamp or Reweigh Reference -
the old HDTTools OCR never extracted those fields, so there is no
pre-verified value to assert exact equality against. Direct visual
inspection of both photos (by the agent that wrote this test, looking at
the images themselves) found:

- Combined Ticket: printed date/time "7-12-26" / "10:10", and
  "1327426192434" written in the "TICKET # OF FULL $ WEIGH (IF REWEIGH)"
  field (interestingly, this matches the Solo Ticket's own printed Ticket
  Number, though that ticket's own reweigh field is blank - the two tickets
  don't cross-reference each other via matching Reweigh Reference values,
  so `determine_solo_link` would not auto-link this real pair).
- Solo Ticket: printed date/time "7-11-26" / "15:50", and nothing written
  in the reweigh field (blank).

Assertions on `timestamp` are intentionally loose (checking the time
portion is present, not the exact string) since a real model may format the
date differently across runs/versions; `reweigh_reference` is asserted more
strictly since it's an exact alphanumeric code, not a free-form date.
"""

import os
from pathlib import Path

import pytest
from towing_app.field_acquisition import ClaudeVisionScaleTicketFieldSource

COMBINED_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "cat_ticket_combined.jpg"
SOLO_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "cat_ticket_solo.jpg"

# Ground truth from the physical tickets (see module docstring).
COMBINED_GOLDEN_STEER = 5640.0
COMBINED_GOLDEN_DRIVE = 9080.0
COMBINED_GOLDEN_TRAILER_AXLE = 19680.0
COMBINED_GOLDEN_GROSS = 34400.0

SOLO_GOLDEN_STEER = 5560.0
SOLO_GOLDEN_DRIVE = 4420.0
SOLO_GOLDEN_GROSS = 9980.0

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="requires a real ANTHROPIC_API_KEY - opt-in only, makes a real API call",
)


def test_real_extraction_matches_golden_combined_ticket_fields() -> None:
    source = ClaudeVisionScaleTicketFieldSource(COMBINED_FIXTURE_PATH)

    assert source.propose("steer") == COMBINED_GOLDEN_STEER
    assert source.propose("drive") == COMBINED_GOLDEN_DRIVE
    assert source.propose("trailer_axle") == COMBINED_GOLDEN_TRAILER_AXLE
    assert source.propose("gross") == COMBINED_GOLDEN_GROSS


def test_real_extraction_reads_combined_ticket_timestamp_and_reweigh_reference() -> (
    None
):
    source = ClaudeVisionScaleTicketFieldSource(COMBINED_FIXTURE_PATH)

    timestamp = source.propose_text("timestamp")
    assert timestamp is not None
    assert "10:10" in timestamp

    reweigh_reference = source.propose_text("reweigh_reference")
    assert reweigh_reference is not None
    assert "1327426192434" in reweigh_reference


def test_real_extraction_matches_golden_solo_ticket_fields() -> None:
    # Trailer Axle is never proposed for a Solo Ticket - see
    # collect_solo_ticket_from_photo and this module's docstring.
    source = ClaudeVisionScaleTicketFieldSource(SOLO_FIXTURE_PATH)

    assert source.propose("steer") == SOLO_GOLDEN_STEER
    assert source.propose("drive") == SOLO_GOLDEN_DRIVE
    assert source.propose("gross") == SOLO_GOLDEN_GROSS


def test_real_extraction_reads_solo_ticket_timestamp_and_blank_reweigh_reference() -> (
    None
):
    source = ClaudeVisionScaleTicketFieldSource(SOLO_FIXTURE_PATH)

    timestamp = source.propose_text("timestamp")
    assert timestamp is not None
    assert "15:50" in timestamp

    # The Solo Ticket's own reweigh field is blank on the physical ticket.
    assert source.propose_text("reweigh_reference") is None
