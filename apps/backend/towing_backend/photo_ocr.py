"""Read-only "propose a value" endpoints wrapping `towing_app`'s existing
Claude-vision / web-lookup `FieldSource` adapters behind the backend's HTTP
boundary (issue #20).

Four session-authenticated endpoints, none of which write to any table:
`POST /trucks/from-photo`, `POST /trailers/from-photo`,
`GET /trailers/axle-count-lookup`, and `POST /tickets/from-photo`. Each
wraps one of `towing_app.field_acquisition`'s adapters - unmodified - and
returns whatever it could determine per field, `None` for anything it
couldn't read (a content failure per ADR 0003 - not an HTTP error at all).
A service-level failure (bad credentials, network, rate limit) is raised by
the adapter as `FieldSourceUnavailableError` and mapped here to `503`,
distinct from a per-field `None`, so the frontend never blames the user's
photo for a problem on our end.

**Async/sync boundary (ADR 0015)**: every route handler here is `async def`
to match the rest of `apps/backend`'s auth-boundary routes, but the
`ClaudeVision*`/`WebAxleCountFieldSource` adapters this module wraps are
synchronous - they make a blocking `anthropic` SDK call. Calling `propose()`/
`propose_text()` directly from an `async def` handler would block the whole
event loop for every other in-flight request for the duration of that call.
Every adapter call in this module is therefore offloaded via
`fastapi.concurrency.run_in_threadpool` (see `_run_extraction`), never called
inline.

**Dependency injection**: each adapter is constructed via a factory
(`PhotoOCRDependencies`), defaulting to the real `ClaudeVision*`/
`WebAxleCountFieldSource` classes themselves (their constructors already
match the factory shapes below). Tests inject fakes by building the app with
a different `PhotoOCRDependencies`, mirroring how `apps/backend/tests`
already injects a per-test `Settings` into `create_app` rather than
patching global state.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from towing_app.field_acquisition import (
    _MEDIA_TYPES,
    ClaudeVisionScaleTicketFieldSource,
    ClaudeVisionTrailerTagFieldSource,
    ClaudeVisionTruckTagFieldSource,
    WebAxleCountFieldSource,
)
from towing_core.field_acquisition import (
    FieldSource,
    FieldSourceUnavailableError,
    TextFieldSource,
)

# Upload contract (issue #20 Implementation Decisions): content-type
# restricted to the exact set `towing_app.field_acquisition._MEDIA_TYPES`
# already recognizes - imported directly (not duplicated) so this can never
# drift from the adapters' own idea of what a readable photo is. A max
# upload size is a "sane default... left to implementation time" per the
# issue and ADR 0011's existing upload-size deferral; 10 MB comfortably
# covers a phone-camera JPEG of a tag or ticket without being an open door.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

_ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(_MEDIA_TYPES.values())


def _build_extension_by_content_type() -> dict[str, str]:
    """Inverts `_MEDIA_TYPES` (ext -> content-type) so a validated upload's
    content-type can be mapped back to *some* extension for the temp file
    written below - `_media_type_for` in `towing_app.field_acquisition`
    looks the media type back up from that suffix. Two extensions
    (`.jpg`/`.jpeg`) share `image/jpeg`; `setdefault` keeps the first
    (`.jpg`) rather than hand-duplicating the mapping, so this can never
    silently drift from `_MEDIA_TYPES` itself.
    """
    mapping: dict[str, str] = {}
    for ext, media_type in _MEDIA_TYPES.items():
        mapping.setdefault(media_type, ext)
    return mapping


_EXTENSION_BY_CONTENT_TYPE: dict[str, str] = _build_extension_by_content_type()

_TRUCK_TAG_FIELDS: tuple[str, ...] = ("gvwr", "front_gawr", "rear_gawr")
_TRAILER_TAG_FIELDS: tuple[str, ...] = ("gvwr", "gawr", "uvw")

TagPhotoSourceFactory = Callable[[Path], FieldSource]
TicketPhotoSourceFactory = Callable[[Path], TextFieldSource]
AxleCountSourceFactory = Callable[[str, str], FieldSource]


@dataclass(frozen=True)
class PhotoOCRDependencies:
    """The four adapter factories this router's routes call through.

    Defaults are the real `towing_app.field_acquisition` classes themselves
    - each one's constructor (`(photo_path)` or `(make, model)`, both with
    an optional trailing `vision_completion`/`lookup` override) already
    matches the factory shape declared above, so no wrapping is needed to
    use them as-is. Tests substitute fakes here instead of monkeypatching or
    hitting the real Anthropic API.
    """

    truck_tag_source: TagPhotoSourceFactory = ClaudeVisionTruckTagFieldSource
    trailer_tag_source: TagPhotoSourceFactory = ClaudeVisionTrailerTagFieldSource
    scale_ticket_source: TicketPhotoSourceFactory = ClaudeVisionScaleTicketFieldSource
    axle_count_source: AxleCountSourceFactory = WebAxleCountFieldSource


class TruckPhotoProposal(BaseModel):
    gvwr: float | None
    front_gawr: float | None
    rear_gawr: float | None


class TrailerPhotoProposal(BaseModel):
    gvwr: float | None
    gawr: float | None
    uvw: float | None


class AxleCountProposal(BaseModel):
    axle_count: float | None


class TicketPhotoProposal(BaseModel):
    steer: float | None
    drive: float | None
    gross: float | None
    # Always `None` for a Solo Ticket - see `_extract_ticket_fields`, which
    # never calls `propose("trailer_axle")` at all in that case (ADR 0007).
    trailer_axle: float | None = None
    timestamp: str | None
    reweigh_reference: str | None


def _write_temp_photo(image_bytes: bytes, suffix: str) -> Path:
    """Writes an uploaded photo's bytes to a temp file so it can be handed
    to a `ClaudeVision*` adapter, which expects a `Path` (issue #20's own
    "base64 conversion happens inside the route handler" decision - the
    adapters themselves are unmodified). Always called from inside
    `run_in_threadpool` alongside the adapter call it feeds, never inline
    on the event loop.
    """
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(image_bytes)
        return Path(tmp.name)


def _extract_tag_fields(
    factory: TagPhotoSourceFactory,
    image_bytes: bytes,
    suffix: str,
    fields: tuple[str, ...],
) -> dict[str, float | None]:
    tmp_path = _write_temp_photo(image_bytes, suffix)
    try:
        source = factory(tmp_path)
        return {field: source.propose(field) for field in fields}
    finally:
        tmp_path.unlink(missing_ok=True)


def _extract_ticket_fields(
    factory: TicketPhotoSourceFactory,
    image_bytes: bytes,
    suffix: str,
    ticket_type: Literal["combined", "solo"],
) -> dict[str, float | str | None]:
    tmp_path = _write_temp_photo(image_bytes, suffix)
    try:
        source = factory(tmp_path)
        data: dict[str, float | str | None] = {
            "steer": source.propose("steer"),
            "drive": source.propose("drive"),
            "gross": source.propose("gross"),
            "timestamp": source.propose_text("timestamp"),
            "reweigh_reference": source.propose_text("reweigh_reference"),
        }
        # A Solo Ticket has no Trailer Axle field at all (ADR 0007,
        # CONTEXT.md: Solo Ticket) - `propose("trailer_axle")` is simply
        # never called for one, mirroring `collect_solo_ticket_from_photo`.
        # The omission happens here, at the call site, not by asking the
        # adapter to special-case ticket type.
        data["trailer_axle"] = (
            source.propose("trailer_axle") if ticket_type == "combined" else None
        )
        return data
    finally:
        tmp_path.unlink(missing_ok=True)


def _as_float(value: float | str | None) -> float | None:
    return value if isinstance(value, float) else None


def _as_str(value: float | str | None) -> str | None:
    return value if isinstance(value, str) else None


def _extract_axle_count(
    factory: AxleCountSourceFactory, make: str, model: str
) -> float | None:
    source = factory(make, model)
    return source.propose("axle_count")


async def _run_extraction[**P, T](
    func: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    """Runs a (blocking) extraction call off the event loop (ADR 0015) and
    maps a service-level failure to `503` (ADR 0003) - a per-field `None`
    is not an error and passes straight through untouched.
    """
    try:
        return await run_in_threadpool(func, *args, **kwargs)
    except FieldSourceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The extraction service is temporarily unavailable. "
                "Please try again later."
            ),
        ) from exc


async def _read_and_validate_photo(file: UploadFile) -> tuple[bytes, str]:
    content_type = file.content_type
    if content_type is None or content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Unsupported file type: {content_type!r}. Supported types: "
                + ", ".join(sorted(_ALLOWED_CONTENT_TYPES))
            ),
        )
    image_bytes = await file.read()
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_BYTES} bytes.",
        )
    suffix = _EXTENSION_BY_CONTENT_TYPE[content_type]
    return image_bytes, suffix


def build_photo_ocr_router(
    current_active_account: Any,
    dependencies: PhotoOCRDependencies | None = None,
) -> APIRouter:
    """Builds the photo-OCR/axle-count-lookup router.

    `current_active_account` is `apps/backend/towing_backend/app.py`'s
    `fastapi_users.current_user(active=True)` dependency, passed in rather
    than imported/rebuilt here so this module has no fastapi-users wiring of
    its own - `create_app` owns that. It carries no static type beyond `Any`
    in this codebase: `FastAPIUsers.current_user()`'s return type is itself
    inferred as `Any` by mypy (verified directly - the dynamically
    `@with_signature`-decorated dependency it returns has no static
    signature), the same as its existing use for `delete_me` in `app.py`.
    """
    deps = dependencies if dependencies is not None else PhotoOCRDependencies()
    router = APIRouter(
        dependencies=[Depends(current_active_account)], tags=["photo-ocr"]
    )

    @router.post("/trucks/from-photo", response_model=TruckPhotoProposal)
    async def trucks_from_photo(file: UploadFile = File(...)) -> TruckPhotoProposal:
        image_bytes, suffix = await _read_and_validate_photo(file)
        data = await _run_extraction(
            _extract_tag_fields,
            deps.truck_tag_source,
            image_bytes,
            suffix,
            _TRUCK_TAG_FIELDS,
        )
        return TruckPhotoProposal(**data)

    @router.post("/trailers/from-photo", response_model=TrailerPhotoProposal)
    async def trailers_from_photo(
        file: UploadFile = File(...),
    ) -> TrailerPhotoProposal:
        image_bytes, suffix = await _read_and_validate_photo(file)
        data = await _run_extraction(
            _extract_tag_fields,
            deps.trailer_tag_source,
            image_bytes,
            suffix,
            _TRAILER_TAG_FIELDS,
        )
        return TrailerPhotoProposal(**data)

    @router.get("/trailers/axle-count-lookup", response_model=AxleCountProposal)
    async def trailers_axle_count_lookup(
        make: str = Query(...), model: str = Query(...)
    ) -> AxleCountProposal:
        axle_count = await _run_extraction(
            _extract_axle_count, deps.axle_count_source, make, model
        )
        return AxleCountProposal(axle_count=axle_count)

    @router.post("/tickets/from-photo", response_model=TicketPhotoProposal)
    async def tickets_from_photo(
        file: UploadFile = File(...),
        ticket_type: Literal["combined", "solo"] = Form(...),
    ) -> TicketPhotoProposal:
        image_bytes, suffix = await _read_and_validate_photo(file)
        data = await _run_extraction(
            _extract_ticket_fields,
            deps.scale_ticket_source,
            image_bytes,
            suffix,
            ticket_type,
        )
        return TicketPhotoProposal(
            steer=_as_float(data["steer"]),
            drive=_as_float(data["drive"]),
            gross=_as_float(data["gross"]),
            trailer_axle=_as_float(data["trailer_axle"]),
            timestamp=_as_str(data["timestamp"]),
            reweigh_reference=_as_str(data["reweigh_reference"]),
        )

    return router
