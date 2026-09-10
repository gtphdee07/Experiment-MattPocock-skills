"""The Field Acquisition seam: proposing a value for a field, or none.

A `FieldSource` proposes a value for a named field without knowing how the
caller will use it - the manual-entry path in `towing_app.cli` never uses
this seam at all, but any alternative source (starting with the Claude-vision
truck tag adapter in `towing_app.field_acquisition`) can plug in here. Every
proposed value still passes through the same confirm-or-edit step manual
entry already uses before it is saved; this module only concerns itself with
proposing.

This module is the dependency-free tier of the seam: the port types only,
with no `anthropic` import. The concrete Claude-vision / web-lookup adapters
live in `towing_app.field_acquisition`.
"""

from collections.abc import Callable
from typing import Literal, Protocol


class FieldSourceUnavailableError(Exception):
    """The source itself couldn't be reached or authenticated - not a content
    problem with what it returned. Distinct from returning None, which means
    the source was reached and responded, but couldn't determine this
    particular value (e.g. an unreadable field on an otherwise-fine photo).
    Callers should degrade differently for each: None means "ask the user to
    fill in just this field"; this exception means "the whole source is
    unavailable right now, fall back to manual entry entirely."
    """


class FieldSource(Protocol):
    """Proposes a value for a named field, or None if it can't determine one.

    May raise FieldSourceUnavailableError if the source itself is unreachable
    (see that class's docstring for how this differs from returning None).
    """

    def propose(self, field: str) -> float | None: ...


class TextFieldSource(Protocol):
    """A `FieldSource` that also proposes free-text (non-numeric) field
    values - e.g. a CAT Scale ticket's timestamp or Reweigh Reference,
    neither of which is a number. `propose` still serves a ticket's numeric
    axle/Gross Weight fields exactly as `FieldSource` does; `propose_text` is
    the parallel entry point for the two string fields. Kept as a separate
    method (rather than widening `propose`'s return type) so every existing
    `FieldSource` implementation, and every caller typed against it, is
    unaffected."""

    def propose(self, field: str) -> float | None: ...

    def propose_text(self, field: str) -> str | None: ...


MediaType = Literal["image/jpeg", "image/png", "image/gif", "image/webp"]

# (image_b64, media_type) -> raw text response from the model.
VisionCompletionFn = Callable[[str, MediaType], str]

# (make, model) -> raw text response from the model.
AxleCountLookupFn = Callable[[str, str], str]
