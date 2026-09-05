"""The Field Acquisition seam: proposing a value for a field, or none.

A `FieldSource` proposes a value for a named field without knowing how the
caller will use it - the manual-entry path in `towing_app.cli` never uses
this seam at all, but any alternative source (starting with the Claude-vision
truck tag adapter below) can plug in here. Every proposed value still passes
through the same confirm-or-edit step manual entry already uses before it is
saved; this module only concerns itself with proposing.
"""

import base64
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol

import anthropic
from anthropic.types import MessageParam

logger = logging.getLogger(__name__)


class FieldSource(Protocol):
    """Proposes a value for a named field, or None if it can't determine one."""

    def propose(self, field: str) -> float | None: ...


MediaType = Literal["image/jpeg", "image/png", "image/gif", "image/webp"]

# (image_b64, media_type) -> raw text response from the model.
VisionCompletionFn = Callable[[str, MediaType], str]

_MEDIA_TYPES: dict[str, MediaType] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

_TRUCK_TAG_FIELDS = ("gvwr", "front_gawr", "rear_gawr")

_EXTRACTION_PROMPT = (
    "This is a photo of a truck's federal certification label (the door-jamb "
    "sticker). Extract the GVWR, Front GAWR, and Rear GAWR, in POUNDS only - "
    "ignore the kg figures printed alongside them. "
    "Respond with ONLY a JSON object of the form "
    '{"gvwr": <number>, "front_gawr": <number>, "rear_gawr": <number>}, '
    "using null for any value you cannot read. No other text."
)


def _media_type_for(photo_path: Path) -> MediaType:
    return _MEDIA_TYPES.get(photo_path.suffix.lower(), "image/jpeg")


def _default_vision_completion(image_b64: str, media_type: MediaType) -> str:
    """Calls Claude with vision input. Requires ANTHROPIC_API_KEY in the env.

    `anthropic.Anthropic()` resolves credentials from the environment
    (ANTHROPIC_API_KEY, or an `ant auth login` profile) - no key is read or
    hardcoded here.
    """
    client = anthropic.Anthropic()
    messages: list[MessageParam] = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": _EXTRACTION_PROMPT},
            ],
        }
    ]
    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        messages=messages,
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def _parse_truck_tag_fields(raw_text: str) -> dict[str, float | None]:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return dict.fromkeys(_TRUCK_TAG_FIELDS)

    if not isinstance(data, dict):
        return dict.fromkeys(_TRUCK_TAG_FIELDS)

    fields: dict[str, float | None] = {}
    for field in _TRUCK_TAG_FIELDS:
        value = data.get(field)
        fields[field] = float(value) if isinstance(value, int | float) else None
    return fields


class ClaudeVisionTruckTagFieldSource:
    """Extracts GVWR, Front GAWR, and Rear GAWR from a truck tag photo.

    The vision call is injected as `vision_completion` (default: a real call
    to the Anthropic API) so tests can supply a fake that returns canned
    extraction text without making a network call. The photo is read and
    sent at most once, on the first `propose()` call; the result is cached
    for subsequent field lookups.
    """

    def __init__(
        self,
        photo_path: Path,
        vision_completion: VisionCompletionFn = _default_vision_completion,
    ) -> None:
        self._photo_path = photo_path
        self._vision_completion = vision_completion
        self._fields: dict[str, float | None] | None = None

    def propose(self, field: str) -> float | None:
        if self._fields is None:
            self._fields = self._extract()
        return self._fields.get(field)

    def _extract(self) -> dict[str, float | None]:
        image_bytes = self._photo_path.read_bytes()
        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        media_type = _media_type_for(self._photo_path)
        try:
            raw_text = self._vision_completion(image_b64, media_type)
        except anthropic.APIError:
            logger.exception("Claude vision extraction failed for %s", self._photo_path)
            return dict.fromkeys(_TRUCK_TAG_FIELDS)
        return _parse_truck_tag_fields(raw_text)
