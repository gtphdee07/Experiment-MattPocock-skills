"""The interactive command-line client: `argparse` wiring, the `run_*` flows
that drive one subcommand each, and `main` - the only place the concrete
`Sqlite*Store` classes and the builtin `input` are named.

Value-gathering lives in `towing_cli.collect` / `towing_cli.prompt`; the
Weigh Event evaluate-and-persist step is `towing_app.services
.record_weigh_event`. The `run_*` functions here own only the CLI-tier
concerns: the subcommand's early "nothing saved yet" guards, and printing
results / status lines.
"""

import argparse
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from towing_app.clock import iso_now
from towing_app.field_acquisition import (
    ClaudeVisionScaleTicketFieldSource,
    ClaudeVisionTrailerTagFieldSource,
    ClaudeVisionTruckTagFieldSource,
    WebAxleCountFieldSource,
)
from towing_app.services import record_weigh_event
from towing_app.sqlite import (
    SqliteTrailerStore,
    SqliteTruckStore,
    SqliteWeighEventStore,
)
from towing_cli.collect import (
    _collect_linked_solo_ticket,
    _list_with_ids,
    _select_profile,
    collect_combined_ticket,
    collect_combined_ticket_from_photo,
    collect_combined_ticket_interactive,
    collect_solo_ticket,
    collect_solo_ticket_from_photo,
    collect_solo_ticket_interactive,
    collect_trailer_profile,
    collect_trailer_profile_edit,
    collect_trailer_profile_from_photo,
    collect_truck_profile,
    collect_truck_profile_edit,
    collect_truck_profile_from_photo,
    determine_solo_link,
    select_profile,
)
from towing_cli.prompt import ReadFn
from towing_core.field_acquisition import FieldSource, TextFieldSource
from towing_core.report import (
    LEGAL_DISCLAIMER,
    _display_nickname,
    _format_axle_check,
    _format_weigh_event_record,
    _trailer_gvwr_near_limit_margin_lbs,
    format_weigh_event_history,
    format_weigh_event_results,
)
from towing_core.storage import (
    TrailerStore,
    TruckStore,
    WeighEventStore,
)

# Explicit re-exports: these live in `towing_cli.collect` / `towing_core
# .report` now, but the moved CLI test files and any external importer still
# do `from towing_cli.cli import ...`, matching what `towing_app.cli`
# exported before Step 4. `__all__` keeps that working under mypy's
# `--no-implicit-reexport`.
__all__ = [
    "DB_PATH_ENV_VAR",
    "DEFAULT_DB_PATH",
    "LEGAL_DISCLAIMER",
    "_collect_linked_solo_ticket",
    "_display_nickname",
    "_format_axle_check",
    "_format_weigh_event_record",
    "_list_with_ids",
    "_select_profile",
    "_trailer_gvwr_near_limit_margin_lbs",
    "build_parser",
    "collect_combined_ticket",
    "collect_combined_ticket_from_photo",
    "collect_combined_ticket_interactive",
    "collect_solo_ticket",
    "collect_solo_ticket_from_photo",
    "collect_solo_ticket_interactive",
    "collect_trailer_profile",
    "collect_trailer_profile_edit",
    "collect_trailer_profile_from_photo",
    "collect_truck_profile",
    "collect_truck_profile_edit",
    "collect_truck_profile_from_photo",
    "determine_solo_link",
    "format_weigh_event_history",
    "format_weigh_event_results",
    "main",
    "resolve_db_path",
    "run_trailer_add",
    "run_trailer_delete",
    "run_trailer_edit",
    "run_trailer_list",
    "run_truck_add",
    "run_truck_delete",
    "run_truck_edit",
    "run_truck_list",
    "run_weigh_event",
    "run_weigh_event_history",
    "select_profile",
]

DEFAULT_DB_PATH = Path.home() / ".towing_app" / "garage.db"
DB_PATH_ENV_VAR = "TOWING_APP_DB_PATH"


def resolve_db_path(env: Mapping[str, str] | None = None) -> Path:
    env = env if env is not None else os.environ
    override = env.get(DB_PATH_ENV_VAR)
    return Path(override) if override else DEFAULT_DB_PATH


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
    _list_with_ids(profiles, "Truck")
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
    _list_with_ids(profiles, "Truck")
    selected = _select_profile(
        read, profiles, "Enter the ID of the Truck Profile to delete: "
    )
    selected_nickname = _display_nickname(selected.nickname, "Truck", selected.id)
    confirmation = read(
        f"Delete Truck Profile [{selected.id}] {selected_nickname} — "
        f"{selected}? [y/N]: "
    )
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
    _list_with_ids(profiles, "Trailer")
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
    _list_with_ids(profiles, "Trailer")
    selected = _select_profile(
        read, profiles, "Enter the ID of the Trailer Profile to delete: "
    )
    selected_nickname = _display_nickname(selected.nickname, "Trailer", selected.id)
    confirmation = read(
        f"Delete Trailer Profile [{selected.id}] {selected_nickname} — "
        f"{selected}? [y/N]: "
    )
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
    _list_with_ids(profiles, "Trailer")


def run_truck_list(store: TruckStore) -> None:
    profiles = store.list()
    if not profiles:
        print("No Truck Profiles saved yet.")
        return
    _list_with_ids(profiles, "Truck")


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
    now: Callable[[], str] = iso_now,
    field_source_factory: Callable[
        [Path], TextFieldSource
    ] = ClaudeVisionScaleTicketFieldSource,
) -> None:
    """Pick a saved Truck Profile + Trailer Profile pairing, collect a
    Combined Ticket (by photo or manual entry - see
    `collect_combined_ticket_interactive`), report Axle Overload + Hitched
    GVWR Overload + GCWR Overload (reported as "not evaluated" when the
    Truck Profile has no GCWR on file), and persist the completed Weigh
    Event to History via `record_weigh_event`."""
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
    (
        ticket,
        solo_ticket,
        time_gap_result,
        reused_solo_from_timestamp,
        reused_solo_is_unverified,
    ) = _collect_linked_solo_ticket(
        read, ticket, past_records, truck.id, field_source_factory
    )

    time_gap_hours = time_gap_result.gap_hours if time_gap_result is not None else None

    outcome = record_weigh_event(
        truck,
        trailer,
        ticket,
        solo_ticket,
        solo_is_unverified=reused_solo_is_unverified,
        time_gap_hours=time_gap_hours,
        reused_solo_from_timestamp=reused_solo_from_timestamp,
        weigh_event_store=weigh_event_store,
        now=now,
    )

    if isinstance(outcome, list):
        for problem in outcome:
            print(problem.message)
        return

    evaluation, _record = outcome
    print(
        format_weigh_event_results(
            evaluation.axle_result,
            evaluation.hitched_gvwr_result,
            evaluation.gcwr_result,
            evaluation.trailer_gvwr_result,
            evaluation.time_gap_result,
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
