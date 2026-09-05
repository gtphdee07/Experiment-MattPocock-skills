import argparse
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

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


def collect_truck_profile(read: ReadFn) -> TruckProfile | None:
    gvwr = _read_float(read, "GVWR (lbs): ")
    front_gawr = _read_float(read, "Front GAWR (lbs): ")
    rear_gawr = _read_float(read, "Rear GAWR (lbs): ")
    gcwr = _read_optional_float(read, "GCWR (lbs, optional - press Enter to skip): ")
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


def run_truck_add(store: TruckStore, read: ReadFn) -> None:
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
    truck_subparsers.add_parser("add", help="Create a Truck Profile")
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
        run_truck_add(SqliteTruckStore(db_path), input)
    elif args.entity == "truck" and args.action == "list":
        run_truck_list(SqliteTruckStore(db_path))
    elif args.entity == "trailer" and args.action == "add":
        run_trailer_add(SqliteTrailerStore(db_path), input)
    elif args.entity == "trailer" and args.action == "list":
        run_trailer_list(SqliteTrailerStore(db_path))
