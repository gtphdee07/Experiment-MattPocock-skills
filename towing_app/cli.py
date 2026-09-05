import argparse
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from towing_app.field_acquisition import (
    ClaudeVisionTruckTagFieldSource,
    FieldSource,
    FieldSourceUnavailableError,
)
from towing_app.models import TrailerProfile, TruckProfile
from towing_app.storage import (
    SqliteTrailerStore,
    SqliteTruckStore,
    TrailerStore,
    TruckStore,
)

ReadFn = Callable[[str], str]

DEFAULT_DB_PATH = Path.home() / ".towing_app" / "garage.db"
DB_PATH_ENV_VAR = "TOWING_APP_DB_PATH"


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


def _read_float(read: ReadFn, prompt: str) -> float:
    return _prompt_until_valid(read, prompt, float, "number")


def _read_optional_float(read: ReadFn, prompt: str) -> float | None:
    def parse(raw: str) -> float | None:
        return None if not raw.strip() else float(raw)

    return _prompt_until_valid(read, prompt, parse, "number")


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

    confirmation = read(
        f"GVWR: {gvwr} lbs, Front GAWR: {front_gawr} lbs, Rear GAWR: {rear_gawr} lbs, "
        f"GCWR: {gcwr_display} lbs. Save this Truck Profile? [y/N]: "
    )
    if confirmation.strip().lower() != "y":
        return None

    return TruckProfile(
        gvwr=gvwr, front_gawr=front_gawr, rear_gawr=rear_gawr, gcwr=gcwr
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

    confirmation = read(
        f"GVWR: {gvwr} lbs, GAWR (each axle): {gawr} lbs, Axle count: {axle_count}, "
        f"UVW: {uvw_display} lbs. Save this Trailer Profile? [y/N]: "
    )
    if confirmation.strip().lower() != "y":
        return None

    return TrailerProfile(gvwr=gvwr, gawr=gawr, axle_count=axle_count, uvw=uvw)


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


def run_trailer_add(store: TrailerStore, read: ReadFn) -> None:
    profile = collect_trailer_profile(read)
    if profile is None:
        print("Discarded - Trailer Profile not saved.")
        return
    store.save(profile)
    print("Trailer Profile saved.")


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

    trailer_parser = subparsers.add_parser("trailer", help="Manage Trailer Profiles")
    trailer_subparsers = trailer_parser.add_subparsers(dest="action", required=True)
    trailer_subparsers.add_parser("add", help="Create a Trailer Profile")
    trailer_subparsers.add_parser("list", help="List saved Trailer Profiles")

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    db_path = resolve_db_path()

    if args.entity == "truck" and args.action == "add":
        run_truck_add(SqliteTruckStore(db_path), input, photo_path=args.photo)
    elif args.entity == "truck" and args.action == "list":
        run_truck_list(SqliteTruckStore(db_path))
    elif args.entity == "trailer" and args.action == "add":
        run_trailer_add(SqliteTrailerStore(db_path), input)
    elif args.entity == "trailer" and args.action == "list":
        run_trailer_list(SqliteTrailerStore(db_path))
