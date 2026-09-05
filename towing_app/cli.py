import argparse
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from towing_app.models import TruckProfile
from towing_app.storage import SqliteTruckStore, TruckStore

ReadFn = Callable[[str], str]

DEFAULT_DB_PATH = Path.home() / ".towing_app" / "garage.db"
DB_PATH_ENV_VAR = "TOWING_APP_DB_PATH"


def resolve_db_path(env: Mapping[str, str] | None = None) -> Path:
    env = env if env is not None else os.environ
    override = env.get(DB_PATH_ENV_VAR)
    return Path(override) if override else DEFAULT_DB_PATH


def _read_float(read: ReadFn, prompt: str) -> float:
    while True:
        raw = read(prompt)
        try:
            return float(raw)
        except ValueError:
            print(f"'{raw}' is not a valid number. Please try again.")


def _read_optional_float(read: ReadFn, prompt: str) -> float | None:
    while True:
        raw = read(prompt)
        if not raw.strip():
            return None
        try:
            return float(raw)
        except ValueError:
            print(f"'{raw}' is not a valid number. Please try again.")


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


def run_truck_add(store: TruckStore, read: ReadFn) -> None:
    profile = collect_truck_profile(read)
    if profile is None:
        print("Discarded - Truck Profile not saved.")
        return
    store.save(profile)
    print("Truck Profile saved.")


def run_truck_list(store: TruckStore) -> None:
    profiles = store.list()
    if not profiles:
        print("No Truck Profiles saved yet.")
        return
    for profile in profiles:
        gcwr_display = profile.gcwr if profile.gcwr is not None else "(not on file)"
        print(
            f"GVWR: {profile.gvwr} lb | Front GAWR: {profile.front_gawr} lb | "
            f"Rear GAWR: {profile.rear_gawr} lb | GCWR: {gcwr_display}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="towing-app", description="Towing Limit Checker"
    )
    subparsers = parser.add_subparsers(dest="entity", required=True)

    truck_parser = subparsers.add_parser("truck", help="Manage Truck Profiles")
    truck_subparsers = truck_parser.add_subparsers(dest="action", required=True)
    truck_subparsers.add_parser("add", help="Create a Truck Profile")
    truck_subparsers.add_parser("list", help="List saved Truck Profiles")

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = SqliteTruckStore(resolve_db_path())

    if args.entity == "truck" and args.action == "add":
        run_truck_add(store, input)
    elif args.entity == "truck" and args.action == "list":
        run_truck_list(store)
