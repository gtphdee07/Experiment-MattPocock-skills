"""Real, opt-in integration test against the live Claude API.

Skipped unless ANTHROPIC_API_KEY is set - this makes a real network call and
costs real API usage, so it never runs as part of the default hermetic
suite. Run explicitly with the key present to verify the real extraction
still matches the golden ground truth whenever the prompt, model, or SDK
changes.

Ground truth for tests/fixtures/trailer_tag_goose.jpg (the "addie_and_goose"
rig's real trailer certification label) is taken directly from
HDTTools/ExampleDocs/golden_fields.json's "GooseTag.jpg" entry, provided by
the project owner from the physical tag, not derived from any OCR output.
Axle Count (3, from that same file's "rigs" -> "addie_and_goose" entry) is
never printed on the tag - it is out of scope for this photo-extraction
smoke test and is covered instead by the WebAxleCountFieldSource unit tests
in test_field_acquisition.py, which use fakes rather than a real lookup call.
"""

import os
from pathlib import Path

import pytest

from towing_app.field_acquisition import ClaudeVisionTrailerTagFieldSource

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "trailer_tag_goose.jpg"

# Ground truth from HDTTools/ExampleDocs/golden_fields.json -> photos -> "GooseTag.jpg".
GOLDEN_GVWR = 23500.0
GOLDEN_GAWR = 8000.0
GOLDEN_UVW = 20554.0

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="requires a real ANTHROPIC_API_KEY - opt-in only, makes a real API call",
)


def test_real_extraction_matches_golden_trailer_tag_fields() -> None:
    source = ClaudeVisionTrailerTagFieldSource(FIXTURE_PATH)

    assert source.propose("gvwr") == GOLDEN_GVWR
    assert source.propose("gawr") == GOLDEN_GAWR
    assert source.propose("uvw") == GOLDEN_UVW
