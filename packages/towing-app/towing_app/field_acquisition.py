"""The Field Acquisition seam: proposing a value for a field, or none.

A `FieldSource` proposes a value for a named field without knowing how the
caller will use it - the manual-entry path in `towing_cli` never uses
this seam at all, but any alternative source (starting with the Claude-vision
truck tag adapter below) can plug in here. Every proposed value still passes
through the same confirm-or-edit step manual entry already uses before it is
saved; this module only concerns itself with proposing.
"""

import base64
import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path

import anthropic
from anthropic.types import ContentBlock, MessageParam

from towing_core.field_acquisition import (
    AxleCountLookupFn,
    FieldSourceUnavailableError,
    MediaType,
    VisionCompletionFn,
)

__all__ = [
    "ClaudeVisionScaleTicketFieldSource",
    "ClaudeVisionTrailerTagFieldSource",
    "ClaudeVisionTruckTagFieldSource",
    "WebAxleCountFieldSource",
]

logger = logging.getLogger(__name__)

# The one model id every Claude call in this module uses - vision extraction
# and the web-search axle-count lookup alike. Kept as a single constant so
# a model change is a one-line edit, not a grep-and-replace.
_MODEL_ID = "claude-opus-5"

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

_TRAILER_TAG_FIELDS = ("gvwr", "gawr", "uvw")

_TRAILER_EXTRACTION_PROMPT = (
    "This is a photo of a travel trailer's or fifth-wheel's federal "
    "certification label. Extract the GVWR, GAWR (the single per-axle "
    "figure printed on the label, not multiplied by axle count), and UVW "
    "(Unloaded Vehicle Weight), in POUNDS only - ignore the kg figures "
    "printed alongside them. Respond with ONLY a JSON object of the form "
    '{"gvwr": <number>, "gawr": <number>, "uvw": <number>}, using null for '
    "any value you cannot read. No other text."
)


_SCALE_TICKET_NUMERIC_FIELDS = ("steer", "drive", "trailer_axle", "gross")
_SCALE_TICKET_TEXT_FIELDS = ("timestamp", "reweigh_reference")

_SCALE_TICKET_EXTRACTION_PROMPT = (
    "This is a photo of a CAT Scale weigh ticket - either a Combined Ticket "
    "(a truck and trailer weighed hitched together) or a Solo Ticket (a "
    "truck weighed alone). Extract the Steer Axle, Drive Axle, Trailer Axle, "
    "and Gross Weight readings, all in POUNDS. Also extract the ticket's "
    "printed date and time as a single string exactly as printed (e.g. "
    '"7-12-26 10:10"), and whatever is written in the "TICKET # OF FULL $ '
    'WEIGH (IF REWEIGH)" field, if anything. Respond with ONLY a JSON object '
    'of the form {"steer": <number>, "drive": <number>, "trailer_axle": '
    '<number>, "gross": <number>, "timestamp": <string or null>, '
    '"reweigh_reference": <string or null>}, using null for any value you '
    "cannot read or that isn't printed on this ticket. No other text."
)


_AXLE_COUNT_FIELDS = ("axle_count",)

_AXLE_COUNT_PROMPT_TEMPLATE = (
    'Look up how many axles a "{make} {model}" travel trailer or '
    "fifth-wheel RV has, using the manufacturer's published specifications. "
    "Search the web if needed. Respond with ONLY a JSON object of the form "
    '{{"axle_count": <integer>}}, using null if you cannot find a reliable '
    "axle count for this make/model. No other text."
)


def _media_type_for(photo_path: Path) -> MediaType:
    return _MEDIA_TYPES.get(photo_path.suffix.lower(), "image/jpeg")


def _last_text_block(content: Sequence[ContentBlock]) -> str:
    """Picks the last text block out of a Claude response's content list.

    A plain completion (no tools) always returns a single text block, so
    "last" and "first" are the same block there. A tool-using completion
    (e.g. the web-search axle-count lookup) can return intermediate
    tool-use/tool-result blocks before the model's final answer, so "last"
    is the one that matters - this one helper is correct for both cases.
    """
    for block in reversed(content):
        if block.type == "text":
            return block.text
    return ""


def _vision_completion(image_b64: str, media_type: MediaType, prompt: str) -> str:
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
                {"type": "text", "text": prompt},
            ],
        }
    ]
    response = client.messages.create(
        model=_MODEL_ID,
        max_tokens=1024,
        messages=messages,
    )
    return _last_text_block(response.content)


def _default_vision_completion(image_b64: str, media_type: MediaType) -> str:
    return _vision_completion(image_b64, media_type, _EXTRACTION_PROMPT)


def _default_trailer_vision_completion(image_b64: str, media_type: MediaType) -> str:
    return _vision_completion(image_b64, media_type, _TRAILER_EXTRACTION_PROMPT)


def _default_scale_ticket_vision_completion(
    image_b64: str, media_type: MediaType
) -> str:
    return _vision_completion(image_b64, media_type, _SCALE_TICKET_EXTRACTION_PROMPT)


def _default_axle_count_lookup(make: str, model: str) -> str:
    """Looks up Axle Count via a Claude web search. Requires
    ANTHROPIC_API_KEY in the env - see `_vision_completion` for how
    credentials are resolved; the same resolution applies here.
    """
    client = anthropic.Anthropic()
    prompt = _AXLE_COUNT_PROMPT_TEMPLATE.format(make=make, model=model)
    response = client.messages.create(
        model=_MODEL_ID,
        max_tokens=1024,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
        messages=[{"role": "user", "content": prompt}],
    )
    return _last_text_block(response.content)


def _propose_via_claude(call: Callable[[], str], *, unavailable_context: str) -> str:
    """Invokes `call` (an adapter's injected completion/lookup function) and
    returns its raw text response, mapping a service-level failure to
    `FieldSourceUnavailableError`.

    Catches `anthropic.APIError` (network/auth/rate-limit failures once a
    request is actually attempted) and `TypeError` (the bare exception the
    SDK raises from `client.messages.create()` when no credentials resolve -
    "Could not resolve authentication method...", not an `anthropic.*`
    exception, so it must be caught here too or a missing key crashes the
    CLI with a raw traceback).

    Either way this is a *service*-level failure, not a content one - the
    model never got a chance to read anything - so it's raised rather than
    treated as a content miss (an all-None parse result), letting the
    caller tell "couldn't reach the service" apart from "reached it, but
    couldn't read this specific field."

    `unavailable_context` is logged via `logger.exception` so the log line
    identifies which adapter/target failed; it plays no part in the raised
    exception's message, which is always `str(exc)`.
    """
    try:
        return call()
    except (anthropic.APIError, TypeError) as exc:
        logger.exception(unavailable_context)
        raise FieldSourceUnavailableError(str(exc)) from exc


def _parse_tag_fields(
    raw_text: str, fields: tuple[str, ...]
) -> dict[str, float | None]:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return dict.fromkeys(fields)

    if not isinstance(data, dict):
        return dict.fromkeys(fields)

    parsed: dict[str, float | None] = {}
    for field in fields:
        value = data.get(field)
        parsed[field] = float(value) if isinstance(value, int | float) else None
    return parsed


def _parse_truck_tag_fields(raw_text: str) -> dict[str, float | None]:
    return _parse_tag_fields(raw_text, _TRUCK_TAG_FIELDS)


def _parse_trailer_tag_fields(raw_text: str) -> dict[str, float | None]:
    return _parse_tag_fields(raw_text, _TRAILER_TAG_FIELDS)


def _parse_axle_count_fields(raw_text: str) -> dict[str, float | None]:
    return _parse_tag_fields(raw_text, _AXLE_COUNT_FIELDS)


def _parse_scale_ticket_fields(raw_text: str) -> dict[str, float | str | None]:
    all_fields = _SCALE_TICKET_NUMERIC_FIELDS + _SCALE_TICKET_TEXT_FIELDS
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return dict.fromkeys(all_fields)

    if not isinstance(data, dict):
        return dict.fromkeys(all_fields)

    parsed: dict[str, float | str | None] = {}
    for field in _SCALE_TICKET_NUMERIC_FIELDS:
        value = data.get(field)
        parsed[field] = float(value) if isinstance(value, int | float) else None
    for field in _SCALE_TICKET_TEXT_FIELDS:
        value = data.get(field)
        stripped = value.strip() if isinstance(value, str) else ""
        parsed[field] = stripped if stripped else None
    return parsed


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
        raw_text = _propose_via_claude(
            lambda: self._vision_completion(image_b64, media_type),
            unavailable_context=(
                f"Claude vision extraction failed for {self._photo_path}"
            ),
        )
        return _parse_truck_tag_fields(raw_text)


class ClaudeVisionTrailerTagFieldSource:
    """Extracts GVWR, GAWR (per axle), and UVW from a trailer tag photo.

    Mirrors `ClaudeVisionTruckTagFieldSource` - see that class's docstring
    for the injection/caching rationale, which applies identically here.
    """

    def __init__(
        self,
        photo_path: Path,
        vision_completion: VisionCompletionFn = _default_trailer_vision_completion,
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
        raw_text = _propose_via_claude(
            lambda: self._vision_completion(image_b64, media_type),
            unavailable_context=(
                f"Claude vision extraction failed for {self._photo_path}"
            ),
        )
        return _parse_trailer_tag_fields(raw_text)


class ClaudeVisionScaleTicketFieldSource:
    """Extracts Steer/Drive/Trailer Axle weights, Gross Weight, timestamp,
    and Reweigh Reference from a CAT Scale ticket photo (see CONTEXT.md: CAT
    Scale Ticket, Reweigh Reference).

    Mirrors `ClaudeVisionTruckTagFieldSource` for the four numeric fields -
    `propose()` implements the same `FieldSource` shape, so every field
    still goes through the same propose-or-manual-entry pattern. Timestamp
    and Reweigh Reference are free text, not numbers, so they're proposed
    through the separate `propose_text()` method (see `TextFieldSource`)
    rather than widening `propose()`'s `float | None` return type.

    A Solo Ticket photo has no Trailer Axle line at all (see CONTEXT.md:
    Solo Ticket) - this class doesn't need to special-case that itself,
    because `SoloTicket` has no `trailer_axle` field for a caller to ask
    about in the first place; `collect_solo_ticket_from_photo` simply never
    calls `propose("trailer_axle")`. A Combined Ticket's Trailer Axle being
    unreadable (a content failure) still comes back as `None`, same as any
    other field, and is resolved through the usual manual-entry fallback."""

    def __init__(
        self,
        photo_path: Path,
        vision_completion: VisionCompletionFn = _default_scale_ticket_vision_completion,
    ) -> None:
        self._photo_path = photo_path
        self._vision_completion = vision_completion
        self._fields: dict[str, float | str | None] | None = None

    def propose(self, field: str) -> float | None:
        value = self._propose_any(field)
        return value if isinstance(value, float) else None

    def propose_text(self, field: str) -> str | None:
        value = self._propose_any(field)
        return value if isinstance(value, str) else None

    def _propose_any(self, field: str) -> float | str | None:
        if self._fields is None:
            self._fields = self._extract()
        return self._fields.get(field)

    def _extract(self) -> dict[str, float | str | None]:
        image_bytes = self._photo_path.read_bytes()
        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        media_type = _media_type_for(self._photo_path)
        raw_text = _propose_via_claude(
            lambda: self._vision_completion(image_b64, media_type),
            unavailable_context=(
                f"Claude vision extraction failed for {self._photo_path}"
            ),
        )
        return _parse_scale_ticket_fields(raw_text)


class WebAxleCountFieldSource:
    """Proposes a Trailer's Axle Count, looked up by make/model.

    Unlike the tag photo adapters, there is only one field ("axle_count")
    this source can ever propose, but it still implements the same
    `FieldSource` shape (see module docstring) so callers and the
    confirm-or-edit step treat every source uniformly.

    The lookup call is injected as `lookup` (default: a real Claude
    web-search call) so tests can supply a fake that returns canned lookup
    text without making a network call. It runs at most once, on the first
    `propose()` call; the result is cached for subsequent calls.
    """

    def __init__(
        self,
        make: str,
        model: str,
        lookup: AxleCountLookupFn = _default_axle_count_lookup,
    ) -> None:
        self._make = make
        self._model = model
        self._lookup = lookup
        self._fields: dict[str, float | None] | None = None

    def propose(self, field: str) -> float | None:
        if self._fields is None:
            self._fields = self._extract()
        return self._fields.get(field)

    def _extract(self) -> dict[str, float | None]:
        # See _propose_via_claude for why anthropic.APIError and a bare
        # TypeError are treated as service-level failures (raised) rather
        # than a content miss (folded into the all-None return) - per ADR
        # 0003, any future external dependency follows this same split.
        raw_text = _propose_via_claude(
            lambda: self._lookup(self._make, self._model),
            unavailable_context=(
                f"Axle-count lookup failed for {self._make} {self._model}"
            ),
        )
        return _parse_axle_count_fields(raw_text)
