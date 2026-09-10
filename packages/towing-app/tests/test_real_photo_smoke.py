"""Real, opt-in integration test against the live Claude API.

Skipped unless ANTHROPIC_API_KEY is set - this makes a real network call and
costs real API usage, so it never runs as part of the default hermetic
suite. Run explicitly with the key present to verify the real extraction
still matches the golden ground truth whenever the prompt, model, or SDK
changes.

Ground truth for tests/fixtures/truck_tag_ford_f450.jpg (Blue Goose's real
federal certification label) is taken directly from
HDTTools/ExampleDocs/golden_fields.json's "AddieTag.jpg" entry, provided by
the project owner from the physical tag, not derived from any OCR output.
"""

import os
from pathlib import Path

import pytest
from towing_app.field_acquisition import ClaudeVisionTruckTagFieldSource

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "truck_tag_ford_f450.jpg"

# Ground truth from HDTTools/ExampleDocs/golden_fields.json -> photos -> "AddieTag.jpg".
GOLDEN_GVWR = 14000.0
GOLDEN_FRONT_GAWR = 6000.0
GOLDEN_REAR_GAWR = 9900.0

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="requires a real ANTHROPIC_API_KEY - opt-in only, makes a real API call",
)


def test_real_extraction_matches_golden_truck_tag_fields() -> None:
    source = ClaudeVisionTruckTagFieldSource(FIXTURE_PATH)

    assert source.propose("gvwr") == GOLDEN_GVWR
    assert source.propose("front_gawr") == GOLDEN_FRONT_GAWR
    assert source.propose("rear_gawr") == GOLDEN_REAR_GAWR
