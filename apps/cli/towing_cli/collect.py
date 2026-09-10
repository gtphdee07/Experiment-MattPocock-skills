"""Interactive value-gathering for the CLI: turn a `read` callable (real
`input`, or a test fake) into confirmed domain objects - Truck/Trailer
Profiles and Combined/Solo Tickets - by manual entry or photo-assisted
extraction.

No `argparse`, no persistence: these functions only prompt, propose, and
confirm. Every function that writes progress/fallback messages does so
through an injected `emit` (default `print`), so the shipped CLI behavior is
byte-identical to printing. The concrete `ClaudeVision*` / `WebAxleCount*`
field sources appear here only as default factory arguments.
"""

from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Literal, Protocol

from towing_app.field_acquisition import (
    ClaudeVisionScaleTicketFieldSource,
    WebAxleCountFieldSource,
)
from towing_core.calculations import (
    TimeGapWarningResult,
    check_time_gap,
)
from towing_core.field_acquisition import (
    FieldSource,
    FieldSourceUnavailableError,
    TextFieldSource,
)
from towing_core.linking import (
    _find_last_solo_ticket_record,
    reweigh_references_match,
)
from towing_core.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile
from towing_core.report import _display_nickname
from towing_core.storage import WeighEventRecord

from towing_cli.prompt import (
    NICKNAME_PROMPT,
    ReadFn,
    _confirm,
    _prompt_until_valid,
    _read_float,
    _read_float_with_default,
    _read_int,
    _read_int_with_default,
    _read_optional_float,
    _read_optional_float_with_default,
    _read_optional_str,
    _read_optional_str_with_default,
    _read_photo_path,
)


class _HasId(Protocol):
    @property
    def id(self) -> int | None: ...


class _HasNicknameAndId(Protocol):
    @property
    def id(self) -> int | None: ...

    @property
    def nickname(self) -> str | None: ...


def _list_with_ids(
    profiles: Sequence[_HasNicknameAndId],
    kind: str,
    emit: Callable[[str], None] = print,
) -> None:
    """Lists Truck/Trailer Profiles for edit/delete selection, leading with
    each one's Nickname (or computed default) ahead of its ratings - see
    `_display_nickname`. Selection itself is unchanged: still the typed
    numeric ID shown in brackets (see `_select_profile`)."""
    for profile in profiles:
        nickname = _display_nickname(profile.nickname, kind, profile.id)
        emit(f"[{profile.id}] {nickname} — {profile}")


def _select_profile[T: _HasId](read: ReadFn, profiles: Sequence[T], prompt: str) -> T:
    ids = {profile.id for profile in profiles if profile.id is not None}

    def parse(raw: str) -> int:
        selected_id = int(raw)
        if selected_id not in ids:
            raise ValueError(f"no profile with id {selected_id}")
        return selected_id

    selected_id = _prompt_until_valid(read, prompt, parse, "ID")
    return next(profile for profile in profiles if profile.id == selected_id)


def _confirm_truck_profile(
    read: ReadFn,
    gvwr: float,
    front_gawr: float,
    rear_gawr: float,
    gcwr: float | None,
    nickname: str | None,
) -> TruckProfile | None:
    """The single confirm-or-discard gate every Truck Profile passes through.

    Manual entry and photo-based entry both funnel their gathered values
    through this same prompt before anything is saved - a value's source
    (typed or OCR-proposed) never skips this step.
    """
    gcwr_display = gcwr if gcwr is not None else "(not provided)"

    confirmed = _confirm(
        read,
        f"GVWR: {gvwr} lbs, Front GAWR: {front_gawr} lbs, Rear GAWR: {rear_gawr} lbs, "
        f"GCWR: {gcwr_display} lbs. Save this Truck Profile? [y/N]: ",
    )
    if not confirmed:
        return None

    return TruckProfile(
        gvwr=gvwr,
        front_gawr=front_gawr,
        rear_gawr=rear_gawr,
        gcwr=gcwr,
        nickname=nickname,
    )


def collect_truck_profile_edit(
    read: ReadFn, current: TruckProfile
) -> TruckProfile | None:
    gvwr = _read_float_with_default(
        read, f"GVWR (lbs) [{current.gvwr}, Enter to keep]: ", current.gvwr
    )
    front_gawr = _read_float_with_default(
        read,
        f"Front GAWR (lbs) [{current.front_gawr}, Enter to keep]: ",
        current.front_gawr,
    )
    rear_gawr = _read_float_with_default(
        read,
        f"Rear GAWR (lbs) [{current.rear_gawr}, Enter to keep]: ",
        current.rear_gawr,
    )
    gcwr_current = current.gcwr if current.gcwr is not None else "(not provided)"
    gcwr = _read_optional_float_with_default(
        read,
        f"GCWR (lbs) [{gcwr_current}, Enter to keep, 'none' to clear]: ",
        current.gcwr,
    )
    gcwr_display = gcwr if gcwr is not None else "(not provided)"
    nickname_current = (
        current.nickname if current.nickname is not None else "(not provided)"
    )
    nickname = _read_optional_str_with_default(
        read,
        f"Nick Name / Reference [{nickname_current}, Enter to keep]: ",
        current.nickname,
    )

    confirmation = read(
        f"GVWR: {gvwr} lbs, Front GAWR: {front_gawr} lbs, Rear GAWR: {rear_gawr} lbs, "
        f"GCWR: {gcwr_display} lbs. Save these changes? [y/N]: "
    )
    if confirmation.strip().lower() != "y":
        return None

    return replace(
        current,
        gvwr=gvwr,
        front_gawr=front_gawr,
        rear_gawr=rear_gawr,
        gcwr=gcwr,
        nickname=nickname,
    )


def collect_truck_profile(read: ReadFn) -> TruckProfile | None:
    gvwr = _read_float(read, "GVWR (lbs): ")
    front_gawr = _read_float(read, "Front GAWR (lbs): ")
    rear_gawr = _read_float(read, "Rear GAWR (lbs): ")
    gcwr = _read_optional_float(read, "GCWR (lbs, optional - press Enter to skip): ")
    nickname = _read_optional_str(read, NICKNAME_PROMPT)
    return _confirm_truck_profile(read, gvwr, front_gawr, rear_gawr, gcwr, nickname)


def _resolve_required_field(
    read: ReadFn,
    field_source: FieldSource,
    field: str,
    prompt: str,
    emit: Callable[[str], None] = print,
) -> float:
    proposed = field_source.propose(field)
    if proposed is None:
        emit(f"Could not read {field} from the photo - enter it manually.")
        return _read_float(read, prompt)
    return proposed


def _resolve_optional_field(
    read: ReadFn,
    field_source: FieldSource,
    field: str,
    prompt: str,
    emit: Callable[[str], None] = print,
) -> float | None:
    proposed = field_source.propose(field)
    if proposed is None:
        emit(
            f"Could not read {field} from the photo - enter it manually, "
            "or press Enter to skip."
        )
        return _read_optional_float(read, prompt)
    return proposed


def _resolve_optional_text_field(
    read: ReadFn,
    field_source: TextFieldSource,
    field: str,
    prompt: str,
    emit: Callable[[str], None] = print,
) -> str | None:
    proposed = field_source.propose_text(field)
    if proposed is None:
        emit(
            f"Could not read {field} from the photo - enter it manually, "
            "or press Enter to skip."
        )
        return _read_optional_str(read, prompt)
    return proposed


def collect_truck_profile_from_photo(
    read: ReadFn,
    field_source: FieldSource,
    emit: Callable[[str], None] = print,
) -> TruckProfile | None:
    """Proposes GVWR/Front GAWR/Rear GAWR from a photo via `field_source`.

    GCWR is never printed on any tag (see ADR 0002), so it is always
    collected manually here, same as in `collect_truck_profile`. Every
    proposed value - whether accepted from the photo or filled in manually
    because extraction couldn't determine it - is confirmed through the same
    `_confirm_truck_profile` gate manual entry uses.
    """
    try:
        gvwr = _resolve_required_field(read, field_source, "gvwr", "GVWR (lbs): ", emit)
        front_gawr = _resolve_required_field(
            read, field_source, "front_gawr", "Front GAWR (lbs): ", emit
        )
        rear_gawr = _resolve_required_field(
            read, field_source, "rear_gawr", "Rear GAWR (lbs): ", emit
        )
    except FieldSourceUnavailableError:
        # The service itself is unreachable, not just this one field - no
        # point trying the remaining fields against it, and the message
        # must not imply the photo was the problem (see ADR 0003).
        emit("Couldn't reach the extraction service - enter all values manually.")
        gvwr = _read_float(read, "GVWR (lbs): ")
        front_gawr = _read_float(read, "Front GAWR (lbs): ")
        rear_gawr = _read_float(read, "Rear GAWR (lbs): ")
    gcwr = _read_optional_float(read, "GCWR (lbs, optional - press Enter to skip): ")
    nickname = _read_optional_str(read, NICKNAME_PROMPT)
    return _confirm_truck_profile(read, gvwr, front_gawr, rear_gawr, gcwr, nickname)


def _confirm_trailer_profile(
    read: ReadFn,
    gvwr: float,
    gawr: float,
    axle_count: int,
    uvw: float | None,
    nickname: str | None,
) -> TrailerProfile | None:
    """The single confirm-or-discard gate every Trailer Profile passes
    through - see `_confirm_truck_profile` for the rationale, which applies
    identically here: manual entry, photo-based tag extraction, and
    web-looked-up Axle Count all funnel through this same prompt.
    """
    uvw_display = uvw if uvw is not None else "(not provided)"

    confirmed = _confirm(
        read,
        f"GVWR: {gvwr} lbs, GAWR (each axle): {gawr} lbs, Axle count: {axle_count}, "
        f"UVW: {uvw_display} lbs. Save this Trailer Profile? [y/N]: ",
    )
    if not confirmed:
        return None

    return TrailerProfile(
        gvwr=gvwr, gawr=gawr, axle_count=axle_count, uvw=uvw, nickname=nickname
    )


def _collect_axle_count(
    read: ReadFn,
    axle_count_source_factory: Callable[[str, str], FieldSource],
    emit: Callable[[str], None] = print,
) -> int:
    """Looks up Axle Count from trailer make/model via
    `axle_count_source_factory` (default: `WebAxleCountFieldSource`), with
    manual entry as the fallback whenever the lookup can't find a match or
    the lookup service itself is unavailable (see ADR 0003) - used by both
    the manual-entry and photo-based Trailer Profile flows, since Axle Count
    is never printed on any tag.
    """
    make = read("Trailer make: ")
    model = read("Trailer model: ")
    axle_count_source = axle_count_source_factory(make, model)
    try:
        proposed = axle_count_source.propose("axle_count")
    except FieldSourceUnavailableError:
        emit(
            "Couldn't reach the axle-count lookup service - enter axle count manually."
        )
        return _read_int(read, "Axle count: ")
    if proposed is None:
        emit("Could not find axle count for this make/model - enter it manually.")
        return _read_int(read, "Axle count: ")
    return int(proposed)


def collect_trailer_profile(
    read: ReadFn,
    axle_count_source_factory: Callable[[str, str], FieldSource] = (
        WebAxleCountFieldSource
    ),
) -> TrailerProfile | None:
    gvwr = _read_float(read, "GVWR (lbs): ")
    gawr = _read_float(read, "GAWR, each axle (lbs): ")
    axle_count = _read_int(read, "Axle count: ")
    uvw = _read_optional_float(read, "UVW (lbs, optional - press Enter to skip): ")
    nickname = _read_optional_str(read, NICKNAME_PROMPT)
    return _confirm_trailer_profile(read, gvwr, gawr, axle_count, uvw, nickname)


def collect_trailer_profile_from_photo(
    read: ReadFn,
    field_source: FieldSource,
    axle_count_source_factory: Callable[[str, str], FieldSource] = (
        WebAxleCountFieldSource
    ),
    emit: Callable[[str], None] = print,
) -> TrailerProfile | None:
    """Proposes GVWR/GAWR/UVW from a photo via `field_source`, and Axle
    Count via a make/model lookup (`axle_count_source_factory`) - Axle Count
    is never printed on any tag, so it always goes through the lookup-or-
    manual path in `_collect_axle_count`, same as GCWR is always manual for
    Truck Profiles. Every value - proposed, looked up, or manually typed
    because a source couldn't determine it - is confirmed through the same
    `_confirm_trailer_profile` gate manual entry uses.
    """
    try:
        gvwr = _resolve_required_field(read, field_source, "gvwr", "GVWR (lbs): ", emit)
        gawr = _resolve_required_field(
            read, field_source, "gawr", "GAWR, each axle (lbs): ", emit
        )
        uvw = _resolve_optional_field(
            read,
            field_source,
            "uvw",
            "UVW (lbs, optional - press Enter to skip): ",
            emit,
        )
    except FieldSourceUnavailableError:
        # The service itself is unreachable, not just this one field - no
        # point trying the remaining fields against it, and the message
        # must not imply the photo was the problem (see ADR 0003).
        emit("Couldn't reach the extraction service - enter all values manually.")
        gvwr = _read_float(read, "GVWR (lbs): ")
        gawr = _read_float(read, "GAWR, each axle (lbs): ")
        uvw = _read_optional_float(read, "UVW (lbs, optional - press Enter to skip): ")
    axle_count = _collect_axle_count(read, axle_count_source_factory, emit)
    nickname = _read_optional_str(read, NICKNAME_PROMPT)
    return _confirm_trailer_profile(read, gvwr, gawr, axle_count, uvw, nickname)


def collect_trailer_profile_edit(
    read: ReadFn, current: TrailerProfile
) -> TrailerProfile | None:
    gvwr = _read_float_with_default(
        read, f"GVWR (lbs) [{current.gvwr}, Enter to keep]: ", current.gvwr
    )
    gawr = _read_float_with_default(
        read,
        f"GAWR, each axle (lbs) [{current.gawr}, Enter to keep]: ",
        current.gawr,
    )
    axle_count = _read_int_with_default(
        read,
        f"Axle count [{current.axle_count}, Enter to keep]: ",
        current.axle_count,
    )
    uvw_current = current.uvw if current.uvw is not None else "(not provided)"
    uvw = _read_optional_float_with_default(
        read,
        f"UVW (lbs) [{uvw_current}, Enter to keep, 'none' to clear]: ",
        current.uvw,
    )
    uvw_display = uvw if uvw is not None else "(not provided)"
    nickname_current = (
        current.nickname if current.nickname is not None else "(not provided)"
    )
    nickname = _read_optional_str_with_default(
        read,
        f"Nick Name / Reference [{nickname_current}, Enter to keep]: ",
        current.nickname,
    )

    confirmation = read(
        f"GVWR: {gvwr} lbs, GAWR (each axle): {gawr} lbs, Axle count: {axle_count}, "
        f"UVW: {uvw_display} lbs. Save these changes? [y/N]: "
    )
    if confirmation.strip().lower() != "y":
        return None

    return replace(
        current,
        gvwr=gvwr,
        gawr=gawr,
        axle_count=axle_count,
        uvw=uvw,
        nickname=nickname,
    )


def select_profile[T](
    read: ReadFn,
    profiles: Sequence[T],
    label: str,
    emit: Callable[[str], None] = print,
) -> T:
    """Print a numbered list of `profiles` and prompt until the user picks a
    valid one. Assumes `profiles` is non-empty - callers should check first
    so they can print a more specific "none saved yet" message."""
    for index, profile in enumerate(profiles, start=1):
        emit(f"{index}. {profile}")

    def parse(raw: str) -> T:
        selection = int(raw)
        if not (1 <= selection <= len(profiles)):
            raise ValueError
        return profiles[selection - 1]

    prompt = f"Select a {label} by number (1-{len(profiles)}): "
    return _prompt_until_valid(read, prompt, parse, "selection")


def collect_combined_ticket(read: ReadFn) -> CombinedTicket | None:
    """Manually enter a Combined Ticket: the CAT Scale reading for a Weigh
    Event where the Tow Vehicle and Trailer were weighed hitched together."""
    steer = _read_float(read, "Steer Axle weight (lbs): ")
    drive = _read_float(read, "Drive Axle weight (lbs): ")
    trailer_axle = _read_float(read, "Trailer Axle weight (lbs): ")
    gross = _read_float(read, "Gross Weight (lbs): ")

    confirmed = _confirm(
        read,
        f"Steer: {steer} lbs, Drive: {drive} lbs, Trailer Axle: {trailer_axle} lbs, "
        f"Gross: {gross} lbs. Save this Combined Ticket? [y/N]: ",
    )
    if not confirmed:
        return None

    return CombinedTicket(
        steer=steer, drive=drive, trailer_axle=trailer_axle, gross=gross
    )


def collect_solo_ticket(read: ReadFn) -> SoloTicket | None:
    """Manually enter a Solo Ticket: the CAT Scale reading for a Weigh
    Event where the Tow Vehicle was weighed alone (see CONTEXT.md: Solo
    Ticket). No Trailer Axle field - nothing is hitched behind the Tow
    Vehicle for a Solo Ticket."""
    steer = _read_float(read, "Steer Axle weight (lbs): ")
    drive = _read_float(read, "Drive Axle weight (lbs): ")
    gross = _read_float(read, "Gross Weight (lbs): ")
    reweigh_reference = _read_optional_str(
        read,
        "Reweigh reference printed on the ticket, if any (optional, press "
        "Enter to skip): ",
    )

    confirmed = _confirm(
        read,
        f"Steer: {steer} lbs, Drive: {drive} lbs, Gross: {gross} lbs. "
        "Save this Solo Ticket? [y/N]: ",
    )
    if not confirmed:
        return None

    return SoloTicket(
        steer=steer, drive=drive, gross=gross, reweigh_reference=reweigh_reference
    )


def collect_combined_ticket_from_photo(
    read: ReadFn,
    field_source: TextFieldSource,
    emit: Callable[[str], None] = print,
) -> CombinedTicket | None:
    """Proposes Steer/Drive/Trailer Axle/Gross Weight, timestamp, and
    Reweigh Reference from a CAT Scale ticket photo via `field_source`.

    Mirrors `collect_truck_profile_from_photo`'s propose-or-manual-per-field
    shape (see that function's docstring): the four weights are required,
    resolved through `_resolve_required_field` exactly as truck/trailer tag
    fields are; timestamp and Reweigh Reference are optional free text,
    resolved through `_resolve_optional_text_field` instead since they are
    not numbers. Every value - proposed or manually typed because extraction
    couldn't determine it - is confirmed through the same gate
    `collect_combined_ticket` uses before anything is saved."""
    try:
        steer = _resolve_required_field(
            read, field_source, "steer", "Steer Axle weight (lbs): ", emit
        )
        drive = _resolve_required_field(
            read, field_source, "drive", "Drive Axle weight (lbs): ", emit
        )
        trailer_axle = _resolve_required_field(
            read, field_source, "trailer_axle", "Trailer Axle weight (lbs): ", emit
        )
        gross = _resolve_required_field(
            read, field_source, "gross", "Gross Weight (lbs): ", emit
        )
        timestamp = _resolve_optional_text_field(
            read,
            field_source,
            "timestamp",
            "Ticket date/time, if any (optional, press Enter to skip): ",
            emit,
        )
        reweigh_reference = _resolve_optional_text_field(
            read,
            field_source,
            "reweigh_reference",
            "Reweigh reference printed on the ticket, if any (optional, "
            "press Enter to skip): ",
            emit,
        )
    except FieldSourceUnavailableError:
        # The service itself is unreachable, not just this one field - no
        # point trying the remaining fields against it, and the message
        # must not imply the photo was the problem (see ADR 0003).
        emit("Couldn't reach the extraction service - enter all values manually.")
        steer = _read_float(read, "Steer Axle weight (lbs): ")
        drive = _read_float(read, "Drive Axle weight (lbs): ")
        trailer_axle = _read_float(read, "Trailer Axle weight (lbs): ")
        gross = _read_float(read, "Gross Weight (lbs): ")
        timestamp = _read_optional_str(
            read, "Ticket date/time, if any (optional, press Enter to skip): "
        )
        reweigh_reference = _read_optional_str(
            read,
            "Reweigh reference printed on the ticket, if any (optional, "
            "press Enter to skip): ",
        )

    confirmed = _confirm(
        read,
        f"Steer: {steer} lbs, Drive: {drive} lbs, Trailer Axle: {trailer_axle} lbs, "
        f"Gross: {gross} lbs. Save this Combined Ticket? [y/N]: ",
    )
    if not confirmed:
        return None

    return CombinedTicket(
        steer=steer,
        drive=drive,
        trailer_axle=trailer_axle,
        gross=gross,
        timestamp=timestamp,
        reweigh_reference=reweigh_reference,
    )


def collect_solo_ticket_from_photo(
    read: ReadFn,
    field_source: TextFieldSource,
    emit: Callable[[str], None] = print,
) -> SoloTicket | None:
    """Proposes Steer/Drive Axle/Gross Weight, timestamp, and Reweigh
    Reference from a CAT Scale ticket photo via `field_source` - mirrors
    `collect_combined_ticket_from_photo`, minus Trailer Axle.

    A Solo Ticket has no Trailer Axle field at all (see CONTEXT.md: Solo
    Ticket, `SoloTicket`) - unlike a Combined Ticket's Trailer Axle, which
    falls back to manual entry when unreadable (a content failure, still a
    real field the ticket has), Trailer Axle is never proposed here in the
    first place, because there is nowhere on `SoloTicket` to put a value
    even if one came back."""
    try:
        steer = _resolve_required_field(
            read, field_source, "steer", "Steer Axle weight (lbs): ", emit
        )
        drive = _resolve_required_field(
            read, field_source, "drive", "Drive Axle weight (lbs): ", emit
        )
        gross = _resolve_required_field(
            read, field_source, "gross", "Gross Weight (lbs): ", emit
        )
        timestamp = _resolve_optional_text_field(
            read,
            field_source,
            "timestamp",
            "Ticket date/time, if any (optional, press Enter to skip): ",
            emit,
        )
        reweigh_reference = _resolve_optional_text_field(
            read,
            field_source,
            "reweigh_reference",
            "Reweigh reference printed on the ticket, if any (optional, "
            "press Enter to skip): ",
            emit,
        )
    except FieldSourceUnavailableError:
        emit("Couldn't reach the extraction service - enter all values manually.")
        steer = _read_float(read, "Steer Axle weight (lbs): ")
        drive = _read_float(read, "Drive Axle weight (lbs): ")
        gross = _read_float(read, "Gross Weight (lbs): ")
        timestamp = _read_optional_str(
            read, "Ticket date/time, if any (optional, press Enter to skip): "
        )
        reweigh_reference = _read_optional_str(
            read,
            "Reweigh reference printed on the ticket, if any (optional, "
            "press Enter to skip): ",
        )

    confirmed = _confirm(
        read,
        f"Steer: {steer} lbs, Drive: {drive} lbs, Gross: {gross} lbs. "
        "Save this Solo Ticket? [y/N]: ",
    )
    if not confirmed:
        return None

    return SoloTicket(
        steer=steer,
        drive=drive,
        gross=gross,
        timestamp=timestamp,
        reweigh_reference=reweigh_reference,
    )


TicketEntryMode = Literal["photo", "manual"]


def _ask_ticket_entry_mode(read: ReadFn, ticket_label: str) -> TicketEntryMode:
    """Ask whether to enter a ticket via photo or by typing it in - offered
    at the point each ticket (Combined or Solo) is collected mid-flow, since
    Weigh Events have no top-level 'add' subcommand of their own to hang a
    `--photo` CLI flag on the way Truck/Trailer Profiles do (see
    `run_truck_add`/`run_trailer_add`). Manual is the default on any
    response other than "p", matching `_ask_solo_ticket_choice`'s style."""
    response = (
        read(f"Enter the {ticket_label} via photo or manually? [p]hoto / [M]anual: ")
        .strip()
        .lower()
    )
    return "photo" if response == "p" else "manual"


def collect_combined_ticket_interactive(
    read: ReadFn,
    field_source_factory: Callable[
        [Path], TextFieldSource
    ] = ClaudeVisionScaleTicketFieldSource,
    emit: Callable[[str], None] = print,
) -> CombinedTicket | None:
    """Offers a photo path alongside manual entry for the Combined Ticket,
    per issue #10's acceptance criteria - see `_ask_ticket_entry_mode` for
    why this is asked here rather than via a CLI flag."""
    mode = _ask_ticket_entry_mode(read, "Combined Ticket")
    if mode == "manual":
        return collect_combined_ticket(read)
    photo_path = _read_photo_path(read, "Path to the Combined Ticket photo: ")
    return collect_combined_ticket_from_photo(
        read, field_source_factory(photo_path), emit
    )


def collect_solo_ticket_interactive(
    read: ReadFn,
    field_source_factory: Callable[
        [Path], TextFieldSource
    ] = ClaudeVisionScaleTicketFieldSource,
    emit: Callable[[str], None] = print,
) -> SoloTicket | None:
    """Offers a photo path alongside manual entry for a freshly-weighed Solo
    Ticket - mirrors `collect_combined_ticket_interactive`. Not used for the
    "reuse last known weight" path (`_collect_reused_solo_ticket`), which
    has no ticket to collect at all."""
    mode = _ask_ticket_entry_mode(read, "Solo Ticket")
    if mode == "manual":
        return collect_solo_ticket(read)
    photo_path = _read_photo_path(read, "Path to the Solo Ticket photo: ")
    return collect_solo_ticket_from_photo(read, field_source_factory(photo_path), emit)


def determine_solo_link(
    read: ReadFn,
    combined: CombinedTicket,
    solo: SoloTicket,
    emit: Callable[[str], None] = print,
) -> bool:
    """Decide whether a Solo Ticket belongs to the same Weigh Event as the
    Combined Ticket (see CONTEXT.md: Reweigh Reference).

    Automatic when both tickets carry a matching, non-blank reweigh
    reference - CAT Scale's own printed field connecting a reweigh to its
    original ticket. Otherwise this falls back to asking the user to
    manually confirm the link, per the acceptance criteria in issue #9."""
    if reweigh_references_match(combined, solo):
        emit(
            f"Reweigh reference '{combined.reweigh_reference}' matches on both "
            "tickets - linked automatically."
        )
        return True

    return _confirm(
        read,
        "No matching reweigh reference found on the two tickets. Manually "
        "confirm the Solo Ticket belongs to the same Weigh Event as the "
        "Combined Ticket? [y/N]: ",
    )


SoloTicketChoice = Literal["weigh_now", "reuse", "skip"]


def _ask_solo_ticket_choice(read: ReadFn, *, reuse_available: bool) -> SoloTicketChoice:
    """Ask whether to add a Solo Ticket for this Weigh Event.

    When no past Weigh Event for this Truck Profile has a linked Solo
    Ticket, this is the same yes/no question the app has always asked,
    worded identically - "reuse" is never mentioned when it isn't an actual
    option. Only when `reuse_available` is true does the question grow a
    third choice (see CONTEXT.md: Reused Solo Weight, ADR 0006 - no
    staleness threshold gates whether reuse is offered, only whether
    qualifying history exists at all)."""
    if not reuse_available:
        return (
            "weigh_now"
            if _confirm(read, "Add a Solo Ticket for this Weigh Event? [y/N]: ")
            else "skip"
        )

    response = (
        read(
            "Add a Solo Ticket for this Weigh Event? [y]es - weigh it now / "
            "[r]euse last known weight / [N]o: "
        )
        .strip()
        .lower()
    )
    if response == "y":
        return "weigh_now"
    if response == "r":
        return "reuse"
    return "skip"


def _collect_reused_solo_ticket(
    read: ReadFn,
    past_record: WeighEventRecord,
    emit: Callable[[str], None] = print,
) -> tuple[SoloTicket, str, bool]:
    """Reuse a past Weigh Event's linked Solo Ticket for this Truck Profile
    (see CONTEXT.md: Reused Solo Weight). Shows the past Gross Weight and
    the date it was recorded, then asks whether anything's changed since
    then - no staleness threshold gates this, regardless of how old
    `past_record` is (see ADR 0006).

    "No, nothing's changed" reuses the past Solo Ticket exactly as-is, still
    a trusted reading rather than an Unverified Value. "Yes, something's
    changed" prompts for a new Gross Weight on the spot (a plain float, no
    special validation) and carries the rest of the past Solo Ticket
    forward unchanged - that figure has no photo or CAT Scale Ticket behind
    it, so it becomes an Unverified Value (see CONTEXT.md: Unverified
    Value; ADR 0006; issue #16).

    Returns the resulting `SoloTicket`, the original record's `timestamp`
    (for `WeighEventRecord.reused_solo_from_timestamp`), and whether the
    weight was adjusted (for `WeighEventRecord.reused_solo_is_unverified`
    and `TrailerGvwrOverloadResult.is_unverified`)."""
    past_solo = past_record.solo_ticket
    assert past_solo is not None
    emit(
        f"Last known Solo weight for this Truck Profile: {past_solo.gross} lbs, "
        f"recorded {past_record.timestamp}."
    )
    changed = _confirm(
        read,
        "Has anything changed since then (cargo, fuel, passengers)? [y/N]: ",
    )
    if changed:
        new_gross = _read_float(
            read,
            "New Gross Weight for the Tow Vehicle, lbs (Unverified Value - not "
            "backed by a photo or CAT Scale Ticket): ",
        )
        return replace(past_solo, gross=new_gross), past_record.timestamp, True
    return past_solo, past_record.timestamp, False


def _collect_linked_solo_ticket(
    read: ReadFn,
    ticket: CombinedTicket,
    past_records: Sequence[WeighEventRecord],
    truck_id: int,
    field_source_factory: Callable[
        [Path], TextFieldSource
    ] = ClaudeVisionScaleTicketFieldSource,
    emit: Callable[[str], None] = print,
) -> tuple[
    CombinedTicket, SoloTicket | None, TimeGapWarningResult | None, str | None, bool
]:
    """Decide how (or whether) this Weigh Event gets a Solo Ticket: weigh it
    now, reuse the last known weight for this Truck Profile, or skip
    entirely (see CONTEXT.md: Solo Ticket, Reused Solo Weight).

    Returns the possibly-updated Combined Ticket (its `reweigh_reference` is
    asked about here, not in `collect_combined_ticket`, only when it wasn't
    already proposed from a Combined Ticket photo - see the
    `_read_optional_str_with_default` call below - since it's otherwise only
    relevant when a fresh Solo Ticket might link to it), the resulting Solo
    Ticket (`None` if skipped, declined, or not linked), a Time-Gap Warning
    result (only for a freshly-linked pair - reusing a weight never produces
    one, see ADR 0006), the original timestamp a reused weight came from
    (`None` unless reuse was actually used), and whether that reused weight
    was manually adjusted rather than reused unchanged (always `False` for
    a fresh or skipped Solo Ticket - see CONTEXT.md: Unverified Value; ADR
    0006; issue #16)."""
    last_solo_record = _find_last_solo_ticket_record(past_records, truck_id)
    choice = _ask_solo_ticket_choice(read, reuse_available=last_solo_record is not None)

    if choice == "skip":
        return ticket, None, None, None, False

    if choice == "reuse":
        assert last_solo_record is not None
        solo, reused_from_timestamp, solo_is_unverified = _collect_reused_solo_ticket(
            read, last_solo_record, emit
        )
        return ticket, solo, None, reused_from_timestamp, solo_is_unverified

    # A photo-based Combined Ticket may already carry a Reweigh Reference
    # OCR'd straight off the ticket (see `collect_combined_ticket_from_photo`)
    # - pressing Enter here keeps that value rather than blanking it out, so
    # asking again mid-flow never silently discards an already-confirmed
    # value (see ADR 0007). For a manually-entered ticket, `ticket
    # .reweigh_reference` is still `None` at this point, so blank input
    # behaves exactly as before.
    combined_ref = _read_optional_str_with_default(
        read,
        "Reweigh reference printed on the Combined Ticket, if any (optional, "
        "press Enter to skip/keep): ",
        ticket.reweigh_reference,
    )
    ticket = replace(ticket, reweigh_reference=combined_ref)

    fresh_solo = collect_solo_ticket_interactive(read, field_source_factory, emit)
    if fresh_solo is None:
        emit("Discarded - Solo Ticket not recorded.")
        return ticket, None, None, None, False

    if not determine_solo_link(read, ticket, fresh_solo, emit):
        emit(
            "Solo Ticket not linked - discarding it. Derived Trailer Weight "
            "and Trailer GVWR Overload will not be evaluated for this Weigh "
            "Event."
        )
        return ticket, None, None, None, False

    gap_hours = _read_float(
        read,
        "Hours between when the Combined and Solo Tickets were weighed "
        "(0 if the same time): ",
    )
    return ticket, fresh_solo, check_time_gap(gap_hours), None, False
