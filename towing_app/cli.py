import argparse
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from towing_app.calculations import (
    AxleOverloadResult,
    GcwrOverloadResult,
    HitchedGvwrOverloadResult,
    TimeGapWarningResult,
    TrailerGvwrOverloadResult,
    check_axle_overload,
    check_gcwr_overload,
    check_hitched_gvwr_overload,
    check_time_gap,
    check_trailer_gvwr_overload,
)
from towing_app.field_acquisition import (
    ClaudeVisionScaleTicketFieldSource,
    ClaudeVisionTrailerTagFieldSource,
    ClaudeVisionTruckTagFieldSource,
    FieldSource,
    FieldSourceUnavailableError,
    TextFieldSource,
    WebAxleCountFieldSource,
)
from towing_app.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile
from towing_app.storage import (
    SqliteTrailerStore,
    SqliteTruckStore,
    SqliteWeighEventStore,
    TrailerStore,
    TruckStore,
    WeighEventRecord,
    WeighEventStore,
)

ReadFn = Callable[[str], str]


class _HasId(Protocol):
    @property
    def id(self) -> int | None: ...


DEFAULT_DB_PATH = Path.home() / ".towing_app" / "garage.db"
DB_PATH_ENV_VAR = "TOWING_APP_DB_PATH"

# NOTE: Placeholder legal copy. This wording has NOT been reviewed by a
# lawyer and must not ship in a paid product until it gets that review.
LEGAL_DISCLAIMER = (
    "DISCLAIMER (placeholder - not legal advice, pending legal review): "
    "This app is a personal reference tool for recreational RV towing only. "
    "It is not for commercial or for-hire use. Results are estimates based "
    "on user-entered data and are not a substitute for certified scale "
    "readings, your vehicle manufacturer's documentation, or advice from a "
    "qualified professional. The app's authors accept no legal "
    "responsibility for towing decisions made using this tool - when in "
    "doubt, consult a weight-distribution/towing expert or your vehicle "
    "manufacturer before towing."
)


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def resolve_db_path(env: Mapping[str, str] | None = None) -> Path:
    env = env if env is not None else os.environ
    override = env.get(DB_PATH_ENV_VAR)
    return Path(override) if override else DEFAULT_DB_PATH


def _prompt_until_valid[T](
    read: ReadFn, prompt: str, parse: Callable[[str], T], label: str
) -> T:
    while True:
        raw = read(prompt)
        try:
            return parse(raw)
        except ValueError:
            print(f"'{raw}' is not a valid {label}. Please try again.")


def _confirm(read: ReadFn, message: str) -> bool:
    response = read(message)
    return response.strip().lower() == "y"


def _read_float(read: ReadFn, prompt: str) -> float:
    return _prompt_until_valid(read, prompt, float, "number")


def _read_optional_float(read: ReadFn, prompt: str) -> float | None:
    def parse(raw: str) -> float | None:
        return None if not raw.strip() else float(raw)

    return _prompt_until_valid(read, prompt, parse, "number")


def _read_optional_str(read: ReadFn, prompt: str) -> str | None:
    stripped = read(prompt).strip()
    return stripped if stripped else None


def _read_optional_str_with_default(
    read: ReadFn, prompt: str, current: str | None
) -> str | None:
    stripped = read(prompt).strip()
    return stripped if stripped else current


def _read_float_with_default(read: ReadFn, prompt: str, current: float) -> float:
    def parse(raw: str) -> float:
        return current if not raw.strip() else float(raw)

    return _prompt_until_valid(read, prompt, parse, "number")


def _read_optional_float_with_default(
    read: ReadFn, prompt: str, current: float | None
) -> float | None:
    def parse(raw: str) -> float | None:
        stripped = raw.strip()
        if not stripped:
            return current
        if stripped.lower() == "none":
            return None
        return float(stripped)

    return _prompt_until_valid(read, prompt, parse, "number")


def _list_with_ids(profiles: Sequence[_HasId]) -> None:
    for profile in profiles:
        print(f"[{profile.id}] {profile}")


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
        gvwr=gvwr, front_gawr=front_gawr, rear_gawr=rear_gawr, gcwr=gcwr
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

    confirmation = read(
        f"GVWR: {gvwr} lbs, Front GAWR: {front_gawr} lbs, Rear GAWR: {rear_gawr} lbs, "
        f"GCWR: {gcwr_display} lbs. Save these changes? [y/N]: "
    )
    if confirmation.strip().lower() != "y":
        return None

    return replace(
        current, gvwr=gvwr, front_gawr=front_gawr, rear_gawr=rear_gawr, gcwr=gcwr
    )


def collect_truck_profile(read: ReadFn) -> TruckProfile | None:
    gvwr = _read_float(read, "GVWR (lbs): ")
    front_gawr = _read_float(read, "Front GAWR (lbs): ")
    rear_gawr = _read_float(read, "Rear GAWR (lbs): ")
    gcwr = _read_optional_float(read, "GCWR (lbs, optional - press Enter to skip): ")
    return _confirm_truck_profile(read, gvwr, front_gawr, rear_gawr, gcwr)


def _resolve_required_field(
    read: ReadFn, field_source: FieldSource, field: str, prompt: str
) -> float:
    proposed = field_source.propose(field)
    if proposed is None:
        print(f"Could not read {field} from the photo - enter it manually.")
        return _read_float(read, prompt)
    return proposed


def _resolve_optional_field(
    read: ReadFn, field_source: FieldSource, field: str, prompt: str
) -> float | None:
    proposed = field_source.propose(field)
    if proposed is None:
        print(
            f"Could not read {field} from the photo - enter it manually, "
            "or press Enter to skip."
        )
        return _read_optional_float(read, prompt)
    return proposed


def _resolve_optional_text_field(
    read: ReadFn, field_source: TextFieldSource, field: str, prompt: str
) -> str | None:
    proposed = field_source.propose_text(field)
    if proposed is None:
        print(
            f"Could not read {field} from the photo - enter it manually, "
            "or press Enter to skip."
        )
        return _read_optional_str(read, prompt)
    return proposed


def collect_truck_profile_from_photo(
    read: ReadFn, field_source: FieldSource
) -> TruckProfile | None:
    """Proposes GVWR/Front GAWR/Rear GAWR from a photo via `field_source`.

    GCWR is never printed on any tag (see ADR 0002), so it is always
    collected manually here, same as in `collect_truck_profile`. Every
    proposed value - whether accepted from the photo or filled in manually
    because extraction couldn't determine it - is confirmed through the same
    `_confirm_truck_profile` gate manual entry uses.
    """
    try:
        gvwr = _resolve_required_field(read, field_source, "gvwr", "GVWR (lbs): ")
        front_gawr = _resolve_required_field(
            read, field_source, "front_gawr", "Front GAWR (lbs): "
        )
        rear_gawr = _resolve_required_field(
            read, field_source, "rear_gawr", "Rear GAWR (lbs): "
        )
    except FieldSourceUnavailableError:
        # The service itself is unreachable, not just this one field - no
        # point trying the remaining fields against it, and the message
        # must not imply the photo was the problem (see ADR 0003).
        print("Couldn't reach the extraction service - enter all values manually.")
        gvwr = _read_float(read, "GVWR (lbs): ")
        front_gawr = _read_float(read, "Front GAWR (lbs): ")
        rear_gawr = _read_float(read, "Rear GAWR (lbs): ")
    gcwr = _read_optional_float(read, "GCWR (lbs, optional - press Enter to skip): ")
    return _confirm_truck_profile(read, gvwr, front_gawr, rear_gawr, gcwr)


def _read_int(read: ReadFn, prompt: str) -> int:
    return _prompt_until_valid(read, prompt, int, "whole number")


def _confirm_trailer_profile(
    read: ReadFn,
    gvwr: float,
    gawr: float,
    axle_count: int,
    uvw: float | None,
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

    return TrailerProfile(gvwr=gvwr, gawr=gawr, axle_count=axle_count, uvw=uvw)


def _collect_axle_count(
    read: ReadFn,
    axle_count_source_factory: Callable[[str, str], FieldSource],
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
        print(
            "Couldn't reach the axle-count lookup service - enter axle count manually."
        )
        return _read_int(read, "Axle count: ")
    if proposed is None:
        print("Could not find axle count for this make/model - enter it manually.")
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
    return _confirm_trailer_profile(read, gvwr, gawr, axle_count, uvw)


def collect_trailer_profile_from_photo(
    read: ReadFn,
    field_source: FieldSource,
    axle_count_source_factory: Callable[[str, str], FieldSource] = (
        WebAxleCountFieldSource
    ),
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
        gvwr = _resolve_required_field(read, field_source, "gvwr", "GVWR (lbs): ")
        gawr = _resolve_required_field(
            read, field_source, "gawr", "GAWR, each axle (lbs): "
        )
        uvw = _resolve_optional_field(
            read,
            field_source,
            "uvw",
            "UVW (lbs, optional - press Enter to skip): ",
        )
    except FieldSourceUnavailableError:
        # The service itself is unreachable, not just this one field - no
        # point trying the remaining fields against it, and the message
        # must not imply the photo was the problem (see ADR 0003).
        print("Couldn't reach the extraction service - enter all values manually.")
        gvwr = _read_float(read, "GVWR (lbs): ")
        gawr = _read_float(read, "GAWR, each axle (lbs): ")
        uvw = _read_optional_float(read, "UVW (lbs, optional - press Enter to skip): ")
    axle_count = _collect_axle_count(read, axle_count_source_factory)
    return _confirm_trailer_profile(read, gvwr, gawr, axle_count, uvw)


def _read_int_with_default(read: ReadFn, prompt: str, current: int) -> int:
    def parse(raw: str) -> int:
        return current if not raw.strip() else int(raw)

    return _prompt_until_valid(read, prompt, parse, "whole number")


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

    confirmation = read(
        f"GVWR: {gvwr} lbs, GAWR (each axle): {gawr} lbs, Axle count: {axle_count}, "
        f"UVW: {uvw_display} lbs. Save these changes? [y/N]: "
    )
    if confirmation.strip().lower() != "y":
        return None

    return replace(current, gvwr=gvwr, gawr=gawr, axle_count=axle_count, uvw=uvw)


def run_truck_add(
    store: TruckStore,
    read: ReadFn,
    photo_path: Path | None = None,
    field_source_factory: Callable[
        [Path], FieldSource
    ] = ClaudeVisionTruckTagFieldSource,
) -> None:
    if photo_path is not None:
        profile = collect_truck_profile_from_photo(
            read, field_source_factory(photo_path)
        )
    else:
        profile = collect_truck_profile(read)
    if profile is None:
        print("Discarded - Truck Profile not saved.")
        return
    store.save(profile)
    print("Truck Profile saved.")


def run_truck_edit(store: TruckStore, read: ReadFn) -> None:
    profiles = store.list()
    if not profiles:
        print("No Truck Profiles saved yet.")
        return
    _list_with_ids(profiles)
    current = _select_profile(
        read, profiles, "Enter the ID of the Truck Profile to edit: "
    )
    updated = collect_truck_profile_edit(read, current)
    if updated is None:
        print("Discarded - Truck Profile not updated.")
        return
    store.update(updated)
    print("Truck Profile updated.")


def run_truck_delete(store: TruckStore, read: ReadFn) -> None:
    profiles = store.list()
    if not profiles:
        print("No Truck Profiles saved yet.")
        return
    _list_with_ids(profiles)
    selected = _select_profile(
        read, profiles, "Enter the ID of the Truck Profile to delete: "
    )
    confirmation = read(f"Delete Truck Profile [{selected.id}] {selected}? [y/N]: ")
    if confirmation.strip().lower() != "y":
        print("Cancelled - Truck Profile not deleted.")
        return
    assert selected.id is not None
    store.delete(selected.id)
    print("Truck Profile deleted.")


def run_trailer_add(
    store: TrailerStore,
    read: ReadFn,
    photo_path: Path | None = None,
    field_source_factory: Callable[
        [Path], FieldSource
    ] = ClaudeVisionTrailerTagFieldSource,
    axle_count_source_factory: Callable[
        [str, str], FieldSource
    ] = WebAxleCountFieldSource,
) -> None:
    if photo_path is not None:
        profile = collect_trailer_profile_from_photo(
            read, field_source_factory(photo_path), axle_count_source_factory
        )
    else:
        profile = collect_trailer_profile(read, axle_count_source_factory)
    if profile is None:
        print("Discarded - Trailer Profile not saved.")
        return
    store.save(profile)
    print("Trailer Profile saved.")


def run_trailer_edit(store: TrailerStore, read: ReadFn) -> None:
    profiles = store.list()
    if not profiles:
        print("No Trailer Profiles saved yet.")
        return
    _list_with_ids(profiles)
    current = _select_profile(
        read, profiles, "Enter the ID of the Trailer Profile to edit: "
    )
    updated = collect_trailer_profile_edit(read, current)
    if updated is None:
        print("Discarded - Trailer Profile not updated.")
        return
    store.update(updated)
    print("Trailer Profile updated.")


def run_trailer_delete(store: TrailerStore, read: ReadFn) -> None:
    profiles = store.list()
    if not profiles:
        print("No Trailer Profiles saved yet.")
        return
    _list_with_ids(profiles)
    selected = _select_profile(
        read, profiles, "Enter the ID of the Trailer Profile to delete: "
    )
    confirmation = read(f"Delete Trailer Profile [{selected.id}] {selected}? [y/N]: ")
    if confirmation.strip().lower() != "y":
        print("Cancelled - Trailer Profile not deleted.")
        return
    assert selected.id is not None
    store.delete(selected.id)
    print("Trailer Profile deleted.")


def run_trailer_list(store: TrailerStore) -> None:
    profiles = store.list()
    if not profiles:
        print("No Trailer Profiles saved yet.")
        return
    for profile in profiles:
        print(profile)


def run_truck_list(store: TruckStore) -> None:
    profiles = store.list()
    if not profiles:
        print("No Truck Profiles saved yet.")
        return
    for profile in profiles:
        print(profile)


def select_profile[T](read: ReadFn, profiles: Sequence[T], label: str) -> T:
    """Print a numbered list of `profiles` and prompt until the user picks a
    valid one. Assumes `profiles` is non-empty - callers should check first
    so they can print a more specific "none saved yet" message."""
    for index, profile in enumerate(profiles, start=1):
        print(f"{index}. {profile}")

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
    read: ReadFn, field_source: TextFieldSource
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
            read, field_source, "steer", "Steer Axle weight (lbs): "
        )
        drive = _resolve_required_field(
            read, field_source, "drive", "Drive Axle weight (lbs): "
        )
        trailer_axle = _resolve_required_field(
            read, field_source, "trailer_axle", "Trailer Axle weight (lbs): "
        )
        gross = _resolve_required_field(
            read, field_source, "gross", "Gross Weight (lbs): "
        )
        timestamp = _resolve_optional_text_field(
            read,
            field_source,
            "timestamp",
            "Ticket date/time, if any (optional, press Enter to skip): ",
        )
        reweigh_reference = _resolve_optional_text_field(
            read,
            field_source,
            "reweigh_reference",
            "Reweigh reference printed on the ticket, if any (optional, "
            "press Enter to skip): ",
        )
    except FieldSourceUnavailableError:
        # The service itself is unreachable, not just this one field - no
        # point trying the remaining fields against it, and the message
        # must not imply the photo was the problem (see ADR 0003).
        print("Couldn't reach the extraction service - enter all values manually.")
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
    read: ReadFn, field_source: TextFieldSource
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
            read, field_source, "steer", "Steer Axle weight (lbs): "
        )
        drive = _resolve_required_field(
            read, field_source, "drive", "Drive Axle weight (lbs): "
        )
        gross = _resolve_required_field(
            read, field_source, "gross", "Gross Weight (lbs): "
        )
        timestamp = _resolve_optional_text_field(
            read,
            field_source,
            "timestamp",
            "Ticket date/time, if any (optional, press Enter to skip): ",
        )
        reweigh_reference = _resolve_optional_text_field(
            read,
            field_source,
            "reweigh_reference",
            "Reweigh reference printed on the ticket, if any (optional, "
            "press Enter to skip): ",
        )
    except FieldSourceUnavailableError:
        print("Couldn't reach the extraction service - enter all values manually.")
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


def _read_photo_path(read: ReadFn, prompt: str) -> Path:
    return Path(read(prompt))


def collect_combined_ticket_interactive(
    read: ReadFn,
    field_source_factory: Callable[
        [Path], TextFieldSource
    ] = ClaudeVisionScaleTicketFieldSource,
) -> CombinedTicket | None:
    """Offers a photo path alongside manual entry for the Combined Ticket,
    per issue #10's acceptance criteria - see `_ask_ticket_entry_mode` for
    why this is asked here rather than via a CLI flag."""
    mode = _ask_ticket_entry_mode(read, "Combined Ticket")
    if mode == "manual":
        return collect_combined_ticket(read)
    photo_path = _read_photo_path(read, "Path to the Combined Ticket photo: ")
    return collect_combined_ticket_from_photo(read, field_source_factory(photo_path))


def collect_solo_ticket_interactive(
    read: ReadFn,
    field_source_factory: Callable[
        [Path], TextFieldSource
    ] = ClaudeVisionScaleTicketFieldSource,
) -> SoloTicket | None:
    """Offers a photo path alongside manual entry for a freshly-weighed Solo
    Ticket - mirrors `collect_combined_ticket_interactive`. Not used for the
    "reuse last known weight" path (`_collect_reused_solo_ticket`), which
    has no ticket to collect at all."""
    mode = _ask_ticket_entry_mode(read, "Solo Ticket")
    if mode == "manual":
        return collect_solo_ticket(read)
    photo_path = _read_photo_path(read, "Path to the Solo Ticket photo: ")
    return collect_solo_ticket_from_photo(read, field_source_factory(photo_path))


def determine_solo_link(
    read: ReadFn, combined: CombinedTicket, solo: SoloTicket
) -> bool:
    """Decide whether a Solo Ticket belongs to the same Weigh Event as the
    Combined Ticket (see CONTEXT.md: Reweigh Reference).

    Automatic when both tickets carry a matching, non-blank reweigh
    reference - CAT Scale's own printed field connecting a reweigh to its
    original ticket. Otherwise this falls back to asking the user to
    manually confirm the link, per the acceptance criteria in issue #9."""
    combined_ref = combined.reweigh_reference
    solo_ref = solo.reweigh_reference
    if (
        combined_ref is not None
        and solo_ref is not None
        and combined_ref.strip().lower() == solo_ref.strip().lower()
    ):
        print(
            f"Reweigh reference '{combined_ref}' matches on both tickets - "
            "linked automatically."
        )
        return True

    return _confirm(
        read,
        "No matching reweigh reference found on the two tickets. Manually "
        "confirm the Solo Ticket belongs to the same Weigh Event as the "
        "Combined Ticket? [y/N]: ",
    )


def _format_axle_check(check: AxleOverloadResult) -> list[str]:
    lines = []
    for result in (check.steer, check.drive, check.trailer):
        verdict = "OVERLOADED" if result.is_overloaded else "OK"
        lines.append(
            f"  {result.axle_name}: {result.actual} lbs actual vs. "
            f"{result.rating} lbs rated -> {verdict}"
        )
    return lines


def format_weigh_event_results(
    axle_result: AxleOverloadResult,
    gvwr_result: HitchedGvwrOverloadResult,
    gcwr_result: GcwrOverloadResult | None,
    trailer_gvwr_result: TrailerGvwrOverloadResult | None = None,
    time_gap_result: TimeGapWarningResult | None = None,
) -> str:
    """Render all checks as plain-language results, always followed by the
    legal disclaimer.

    `gcwr_result` is `None` when the Truck Profile has no GCWR on file - a
    distinct "not evaluated" state (see ADR 0002), reported without blocking
    or hiding the other two checks. When it is present, GCWR Overload
    depends on a manually-typed value with no photo/CAT Scale Ticket backing
    it, so its result is labeled an Unverified Value (see CONTEXT.md:
    Unverified Value).

    `trailer_gvwr_result` is `None` whenever there's no linked Solo Ticket
    for this Weigh Event - also reported as "not evaluated" rather than
    hidden (see CONTEXT.md: Trailer GVWR Overload). When it's present and
    not overloaded but `is_near_limit`, an extra "Near limit" line is shown
    (see ADR 0006) - never alongside an OVERLOADED verdict. `time_gap_result`
    is only present at all when a Solo Ticket was linked - unlike the
    Overload checks it's advisory only and never labeled OVERLOADED/OK (see
    CONTEXT.md: Time-Gap Warning)."""
    lines = ["=== Weigh Event Results ===", ""]

    lines.append("Axle Overload")
    lines.append(
        "  Checks whether any single axle group's actual weight exceeds "
        "what it's rated to carry (its GAWR)."
    )
    lines.extend(_format_axle_check(axle_result))
    if axle_result.any_overloaded:
        lines.append("  Result: Axle Overload detected.")
    else:
        lines.append("  Result: no Axle Overload detected.")
    lines.append("")

    lines.append("Hitched GVWR Overload")
    lines.append(
        "  Checks whether the tow vehicle's own axle groups (Steer + Drive), "
        "summed while hitched to the trailer, exceed the tow vehicle's own "
        "GVWR - this can happen even when neither axle is individually "
        "overloaded."
    )
    verdict = "OVERLOADED" if gvwr_result.is_overloaded else "OK"
    lines.append(
        f"  Steer + Drive: {gvwr_result.combined_actual} lbs actual vs. "
        f"{gvwr_result.gvwr_rating} lbs rated -> {verdict}"
    )
    if gvwr_result.is_overloaded:
        lines.append("  Result: Hitched GVWR Overload detected.")
    else:
        lines.append("  Result: no Hitched GVWR Overload detected.")
    lines.append("")

    lines.append("GCWR Overload")
    lines.append(
        "  Checks whether the Combined Ticket's Gross Weight exceeds the "
        "tow vehicle's GCWR (Gross Combined Weight Rating)."
    )
    if gcwr_result is None:
        lines.append(
            "  Result: not evaluated - no GCWR on file for this Truck Profile."
        )
    else:
        verdict = "OVERLOADED" if gcwr_result.is_overloaded else "OK"
        lines.append(
            f"  Gross Weight: {gcwr_result.combined_actual} lbs actual vs. "
            f"{gcwr_result.gcwr_rating} lbs rated (Unverified Value - GCWR is "
            f"manually entered, not backed by a photo or CAT Scale Ticket) "
            f"-> {verdict}"
        )
        if gcwr_result.is_overloaded:
            lines.append("  Result: GCWR Overload detected.")
        else:
            lines.append("  Result: no GCWR Overload detected.")
    lines.append("")

    lines.append("Trailer GVWR Overload")
    lines.append(
        "  Checks whether Derived Trailer Weight (a linked Solo Ticket's "
        "Gross Weight subtracted from the Combined Ticket's Gross Weight) "
        "exceeds the Trailer Profile's GVWR."
    )
    if trailer_gvwr_result is None:
        lines.append(
            "  Result: not evaluated - no linked Solo Ticket for this Weigh Event."
        )
    else:
        verdict = "OVERLOADED" if trailer_gvwr_result.is_overloaded else "OK"
        lines.append(
            f"  Derived Trailer Weight: {trailer_gvwr_result.derived_trailer_weight} "
            f"lbs vs. {trailer_gvwr_result.gvwr_rating} lbs rated -> {verdict}"
        )
        if trailer_gvwr_result.is_overloaded:
            lines.append("  Result: Trailer GVWR Overload detected.")
        else:
            lines.append("  Result: no Trailer GVWR Overload detected.")
            if trailer_gvwr_result.is_near_limit:
                lines.append(
                    "  Near limit: Derived Trailer Weight is within 100 lbs "
                    "of the Trailer's GVWR."
                )
    lines.append("")

    if time_gap_result is not None:
        lines.append("Time-Gap Warning")
        lines.append(
            "  Non-blocking: flags when the linked pair's two physical "
            "weighings were far enough apart that the Trailer may have "
            "changed weight in between."
        )
        gap = abs(time_gap_result.gap_hours)
        if time_gap_result.exceeds_threshold:
            lines.append(
                f"  Warning: the Combined and Solo Tickets were weighed {gap} "
                f"hours apart, more than the {time_gap_result.threshold_hours}-"
                "hour threshold. Derived Trailer Weight may be less accurate."
            )
        else:
            lines.append(
                f"  Combined and Solo Tickets were weighed {gap} hours apart - "
                f"within the {time_gap_result.threshold_hours}-hour threshold."
            )
        lines.append("")

    lines.append(LEGAL_DISCLAIMER)

    return "\n".join(lines)


def _format_weigh_event_record(record: WeighEventRecord) -> list[str]:
    lines = [
        f"[{record.timestamp}] Truck Profile #{record.truck_id} + "
        f"Trailer Profile #{record.trailer_id}"
    ]
    lines.extend(f"  {line}" for line in _format_axle_check(record.axle_result))
    axle_verdict = "OVERLOADED" if record.axle_result.any_overloaded else "OK"
    lines.append(f"  Axle Overload: {axle_verdict}")

    gvwr_verdict = "OVERLOADED" if record.gvwr_result.is_overloaded else "OK"
    lines.append(
        f"  Hitched GVWR Overload: {record.gvwr_result.combined_actual} lbs actual "
        f"vs. {record.gvwr_result.gvwr_rating} lbs rated -> {gvwr_verdict}"
    )

    if record.gcwr_result is None:
        lines.append(
            "  GCWR Overload: not evaluated - no GCWR on file for this Truck Profile."
        )
    else:
        gcwr_verdict = "OVERLOADED" if record.gcwr_result.is_overloaded else "OK"
        lines.append(
            f"  GCWR Overload: {record.gcwr_result.combined_actual} lbs actual "
            f"vs. {record.gcwr_result.gcwr_rating} lbs rated (Unverified Value) "
            f"-> {gcwr_verdict}"
        )

    if record.trailer_gvwr_result is None:
        lines.append(
            "  Trailer GVWR Overload: not evaluated - no linked Solo Ticket "
            "for this Weigh Event."
        )
    else:
        trailer_verdict = (
            "OVERLOADED" if record.trailer_gvwr_result.is_overloaded else "OK"
        )
        lines.append(
            "  Trailer GVWR Overload: Derived Trailer Weight "
            f"{record.trailer_gvwr_result.derived_trailer_weight} lbs vs. "
            f"{record.trailer_gvwr_result.gvwr_rating} lbs rated -> {trailer_verdict}"
        )
        if record.trailer_gvwr_result.is_near_limit:
            lines.append(
                "  Near limit: Derived Trailer Weight is within 100 lbs of "
                "the Trailer's GVWR."
            )
        if record.time_gap_hours is not None:
            gap = abs(record.time_gap_hours)
            lines.append(f"  Time-Gap: Combined and Solo Tickets {gap} hours apart.")
        if record.reused_solo_from_timestamp is not None:
            lines.append(
                "  Solo Ticket: reused, unchanged, from a Weigh Event recorded "
                f"{record.reused_solo_from_timestamp}."
            )

    return lines


def format_weigh_event_history(records: Sequence[WeighEventRecord]) -> str:
    """Render past Weigh Events in chronological order, each showing the
    Truck+Trailer pairing used and its check results, followed by the legal
    disclaimer once for the whole listing."""
    lines = ["=== Weigh Event History ===", ""]
    for record in records:
        lines.extend(_format_weigh_event_record(record))
        lines.append("")
    lines.append(LEGAL_DISCLAIMER)
    return "\n".join(lines)


def run_weigh_event_history(weigh_event_store: WeighEventStore) -> None:
    """List past Weigh Events, in chronological order, showing the
    Truck+Trailer pairing used and each check's pass/fail result."""
    records = weigh_event_store.list()
    if not records:
        print("No Weigh Events recorded yet.")
        return
    print(format_weigh_event_history(records))


SoloTicketChoice = Literal["weigh_now", "reuse", "skip"]


def _find_last_solo_ticket_record(
    records: Sequence[WeighEventRecord], truck_id: int
) -> WeighEventRecord | None:
    """The most recent past Weigh Event for `truck_id` that has a linked
    Solo Ticket - the source for "reuse the last known weight" (see
    CONTEXT.md: Reused Solo Weight). `None` when this Truck Profile has no
    such history, which is also the signal that "reuse" should not be
    offered at all.

    `WeighEventStore.list()` returns every record unfiltered, so this
    filter-then-pick-the-latest is done here rather than as a new store
    method."""
    candidates = [
        record
        for record in records
        if record.truck_id == truck_id and record.solo_ticket is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda record: record.timestamp)


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
    read: ReadFn, past_record: WeighEventRecord
) -> tuple[SoloTicket, str]:
    """Reuse a past Weigh Event's linked Solo Ticket for this Truck Profile
    (see CONTEXT.md: Reused Solo Weight). Shows the past Gross Weight and
    the date it was recorded, then asks whether anything's changed since
    then - no staleness threshold gates this, regardless of how old
    `past_record` is (see ADR 0006).

    Only the "no, nothing's changed" branch is implemented here: the past
    Solo Ticket is reused exactly as-is, still a trusted reading rather
    than an Unverified Value (see ADR 0006). The "yes, something's
    changed" branch - typing a new figure, which becomes an Unverified
    Value - is issue #16's scope, worked separately; answering "yes" here
    falls back to "no change" for now so #16 has a clean seam to extend
    without reshaping this function's return type.

    Returns the reused `SoloTicket` and the original record's `timestamp`,
    for `WeighEventRecord.reused_solo_from_timestamp`."""
    past_solo = past_record.solo_ticket
    assert past_solo is not None
    print(
        f"Last known Solo weight for this Truck Profile: {past_solo.gross} lbs, "
        f"recorded {past_record.timestamp}."
    )
    changed = _confirm(
        read,
        "Has anything changed since then (cargo, fuel, passengers)? [y/N]: ",
    )
    if changed:
        # TODO(#16): collect a new Gross Weight here and mark the resulting
        # Trailer GVWR Overload as an Unverified Value (see ADR 0006).
        print("Adjusting the reused weight isn't supported yet - using it as-is.")
    return past_solo, past_record.timestamp


def _collect_linked_solo_ticket(
    read: ReadFn,
    ticket: CombinedTicket,
    past_records: Sequence[WeighEventRecord],
    truck_id: int,
    field_source_factory: Callable[
        [Path], TextFieldSource
    ] = ClaudeVisionScaleTicketFieldSource,
) -> tuple[CombinedTicket, SoloTicket | None, TimeGapWarningResult | None, str | None]:
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
    one, see ADR 0006), and the original timestamp a reused weight came from
    (`None` unless reuse was actually used)."""
    last_solo_record = _find_last_solo_ticket_record(past_records, truck_id)
    choice = _ask_solo_ticket_choice(read, reuse_available=last_solo_record is not None)

    if choice == "skip":
        return ticket, None, None, None

    if choice == "reuse":
        assert last_solo_record is not None
        solo, reused_from_timestamp = _collect_reused_solo_ticket(
            read, last_solo_record
        )
        return ticket, solo, None, reused_from_timestamp

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

    fresh_solo = collect_solo_ticket_interactive(read, field_source_factory)
    if fresh_solo is None:
        print("Discarded - Solo Ticket not recorded.")
        return ticket, None, None, None

    if not determine_solo_link(read, ticket, fresh_solo):
        print(
            "Solo Ticket not linked - discarding it. Derived Trailer Weight "
            "and Trailer GVWR Overload will not be evaluated for this Weigh "
            "Event."
        )
        return ticket, None, None, None

    gap_hours = _read_float(
        read,
        "Hours between when the Combined and Solo Tickets were weighed "
        "(0 if the same time): ",
    )
    return ticket, fresh_solo, check_time_gap(gap_hours), None


def run_weigh_event(
    truck_store: TruckStore,
    trailer_store: TrailerStore,
    weigh_event_store: WeighEventStore,
    read: ReadFn,
    now: Callable[[], str] = _iso_now,
    field_source_factory: Callable[
        [Path], TextFieldSource
    ] = ClaudeVisionScaleTicketFieldSource,
) -> None:
    """Pick a saved Truck Profile + Trailer Profile pairing, collect a
    Combined Ticket (by photo or manual entry - see
    `collect_combined_ticket_interactive`), report Axle Overload + Hitched
    GVWR Overload + GCWR Overload (reported as "not evaluated" when the
    Truck Profile has no GCWR on file), and persist the completed Weigh
    Event to History."""
    trucks = truck_store.list()
    if not trucks:
        print("No Truck Profiles saved yet. Add one with 'truck add' first.")
        return

    trailers = trailer_store.list()
    if not trailers:
        print("No Trailer Profiles saved yet. Add one with 'trailer add' first.")
        return

    print("Saved Truck Profiles:")
    truck = select_profile(read, trucks, "Truck Profile")

    print("Saved Trailer Profiles:")
    trailer = select_profile(read, trailers, "Trailer Profile")

    assert truck.id is not None
    assert trailer.id is not None

    ticket = collect_combined_ticket_interactive(read, field_source_factory)
    if ticket is None:
        print("Discarded - Combined Ticket not recorded.")
        return

    past_records = weigh_event_store.list()
    ticket, solo_ticket, time_gap_result, reused_solo_from_timestamp = (
        _collect_linked_solo_ticket(
            read, ticket, past_records, truck.id, field_source_factory
        )
    )

    axle_result = check_axle_overload(truck, trailer, ticket)
    gvwr_result = check_hitched_gvwr_overload(truck, ticket)
    gcwr_result = check_gcwr_overload(truck, ticket)
    trailer_gvwr_result = check_trailer_gvwr_overload(trailer, ticket, solo_ticket)

    print(
        format_weigh_event_results(
            axle_result,
            gvwr_result,
            gcwr_result,
            trailer_gvwr_result,
            time_gap_result,
        )
    )

    weigh_event_store.save(
        WeighEventRecord(
            truck_id=truck.id,
            trailer_id=trailer.id,
            ticket=ticket,
            axle_result=axle_result,
            gvwr_result=gvwr_result,
            gcwr_result=gcwr_result,
            solo_ticket=solo_ticket,
            trailer_gvwr_result=trailer_gvwr_result,
            time_gap_hours=(
                time_gap_result.gap_hours if time_gap_result is not None else None
            ),
            reused_solo_from_timestamp=reused_solo_from_timestamp,
            timestamp=now(),
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="towing-app", description="Towing Limit Checker"
    )
    subparsers = parser.add_subparsers(dest="entity", required=True)

    truck_parser = subparsers.add_parser("truck", help="Manage Truck Profiles")
    truck_subparsers = truck_parser.add_subparsers(dest="action", required=True)
    truck_add_parser = truck_subparsers.add_parser("add", help="Create a Truck Profile")
    truck_add_parser.add_argument(
        "--photo",
        type=Path,
        default=None,
        help=(
            "Path to a photo of the truck's federal certification label. "
            "When given, GVWR/Front GAWR/Rear GAWR are proposed from the "
            "photo instead of typed manually; GCWR is still entered "
            "manually either way. Every proposed value still requires "
            "confirmation before saving."
        ),
    )
    truck_subparsers.add_parser("list", help="List saved Truck Profiles")
    truck_subparsers.add_parser("edit", help="Edit an existing Truck Profile")
    truck_subparsers.add_parser("delete", help="Delete a Truck Profile")

    trailer_parser = subparsers.add_parser("trailer", help="Manage Trailer Profiles")
    trailer_subparsers = trailer_parser.add_subparsers(dest="action", required=True)
    trailer_add_parser = trailer_subparsers.add_parser(
        "add", help="Create a Trailer Profile"
    )
    trailer_add_parser.add_argument(
        "--photo",
        type=Path,
        default=None,
        help=(
            "Path to a photo of the trailer's federal certification label. "
            "When given, GVWR/GAWR/UVW are proposed from the photo instead "
            "of typed manually; Axle Count is always looked up by "
            "make/model either way, with manual entry as the fallback when "
            "the lookup can't find a match. Every proposed value still "
            "requires confirmation before saving."
        ),
    )
    trailer_subparsers.add_parser("list", help="List saved Trailer Profiles")
    trailer_subparsers.add_parser("edit", help="Edit an existing Trailer Profile")
    trailer_subparsers.add_parser("delete", help="Delete a Trailer Profile")

    weigh_event_parser = subparsers.add_parser(
        "weigh-event", help="Record and check a Weigh Event"
    )
    weigh_event_subparsers = weigh_event_parser.add_subparsers(
        dest="action", required=True
    )
    weigh_event_subparsers.add_parser(
        "run",
        help=(
            "Pick a Truck Profile + Trailer Profile, enter a Combined "
            "Ticket, and check for Axle Overload / Hitched GVWR Overload / "
            "GCWR Overload"
        ),
    )
    weigh_event_subparsers.add_parser(
        "history",
        help="List past Weigh Events in chronological order",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    db_path = resolve_db_path()

    if args.entity == "truck" and args.action == "add":
        run_truck_add(SqliteTruckStore(db_path), input, photo_path=args.photo)
    elif args.entity == "truck" and args.action == "list":
        run_truck_list(SqliteTruckStore(db_path))
    elif args.entity == "truck" and args.action == "edit":
        run_truck_edit(SqliteTruckStore(db_path), input)
    elif args.entity == "truck" and args.action == "delete":
        run_truck_delete(SqliteTruckStore(db_path), input)
    elif args.entity == "trailer" and args.action == "add":
        run_trailer_add(SqliteTrailerStore(db_path), input, photo_path=args.photo)
    elif args.entity == "trailer" and args.action == "list":
        run_trailer_list(SqliteTrailerStore(db_path))
    elif args.entity == "trailer" and args.action == "edit":
        run_trailer_edit(SqliteTrailerStore(db_path), input)
    elif args.entity == "trailer" and args.action == "delete":
        run_trailer_delete(SqliteTrailerStore(db_path), input)
    elif args.entity == "weigh-event" and args.action == "run":
        run_weigh_event(
            SqliteTruckStore(db_path),
            SqliteTrailerStore(db_path),
            SqliteWeighEventStore(db_path),
            input,
        )
    elif args.entity == "weigh-event" and args.action == "history":
        run_weigh_event_history(SqliteWeighEventStore(db_path))
