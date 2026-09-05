import argparse
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from towing_app.calculations import (
    AxleOverloadResult,
    HitchedGvwrOverloadResult,
    check_axle_overload,
    check_hitched_gvwr_overload,
)
from towing_app.field_acquisition import (
    ClaudeVisionTruckTagFieldSource,
    FieldSource,
    FieldSourceUnavailableError,
)
from towing_app.models import CombinedTicket, TrailerProfile, TruckProfile
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


def _resolve_truck_field(
    read: ReadFn, field_source: FieldSource, field: str, prompt: str
) -> float:
    proposed = field_source.propose(field)
    if proposed is None:
        print(f"Could not read {field} from the photo - enter it manually.")
        return _read_float(read, prompt)
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
        gvwr = _resolve_truck_field(read, field_source, "gvwr", "GVWR (lbs): ")
        front_gawr = _resolve_truck_field(
            read, field_source, "front_gawr", "Front GAWR (lbs): "
        )
        rear_gawr = _resolve_truck_field(
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


def collect_trailer_profile(read: ReadFn) -> TrailerProfile | None:
    gvwr = _read_float(read, "GVWR (lbs): ")
    gawr = _read_float(read, "GAWR, each axle (lbs): ")
    axle_count = _read_int(read, "Axle count: ")
    uvw = _read_optional_float(read, "UVW (lbs, optional - press Enter to skip): ")
    uvw_display = uvw if uvw is not None else "(not provided)"

    confirmed = _confirm(
        read,
        f"GVWR: {gvwr} lbs, GAWR (each axle): {gawr} lbs, Axle count: {axle_count}, "
        f"UVW: {uvw_display} lbs. Save this Trailer Profile? [y/N]: ",
    )
    if not confirmed:
        return None

    return TrailerProfile(gvwr=gvwr, gawr=gawr, axle_count=axle_count, uvw=uvw)


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


def run_trailer_add(store: TrailerStore, read: ReadFn) -> None:
    profile = collect_trailer_profile(read)
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
    axle_result: AxleOverloadResult, gvwr_result: HitchedGvwrOverloadResult
) -> str:
    """Render both checks as plain-language results, always followed by the
    legal disclaimer."""
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


def run_weigh_event(
    truck_store: TruckStore,
    trailer_store: TrailerStore,
    weigh_event_store: WeighEventStore,
    read: ReadFn,
    now: Callable[[], str] = _iso_now,
) -> None:
    """Pick a saved Truck Profile + Trailer Profile pairing, type in a
    Combined Ticket, report Axle Overload + Hitched GVWR Overload, and
    persist the completed Weigh Event to History."""
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

    ticket = collect_combined_ticket(read)
    if ticket is None:
        print("Discarded - Combined Ticket not recorded.")
        return

    axle_result = check_axle_overload(truck, trailer, ticket)
    gvwr_result = check_hitched_gvwr_overload(truck, ticket)

    print(format_weigh_event_results(axle_result, gvwr_result))

    assert truck.id is not None
    assert trailer.id is not None
    weigh_event_store.save(
        WeighEventRecord(
            truck_id=truck.id,
            trailer_id=trailer.id,
            ticket=ticket,
            axle_result=axle_result,
            gvwr_result=gvwr_result,
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
    trailer_subparsers.add_parser("add", help="Create a Trailer Profile")
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
            "Ticket, and check for Axle Overload / Hitched GVWR Overload"
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
        run_trailer_add(SqliteTrailerStore(db_path), input)
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
