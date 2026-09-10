# Solo Ticket linking, unlinked-ticket disposal, and manual Time-Gap entry

Issue #9 left several implementation details to judgment: how a Reweigh Reference is collected given there's no OCR for CAT Scale Tickets yet (#10, blocked), what happens to a Solo Ticket that's entered but never linked, and where a "timestamp" for the Time-Gap Warning comes from when nothing captures the ticket's real weigh time. This ADR records the choices made and why.

## Reweigh Reference is only asked about when a Solo Ticket is actually added

`collect_combined_ticket` is unchanged - it still asks for Steer/Drive/Trailer Axle/Gross Weight only, exactly as before ticket #9. The Combined Ticket's Reweigh Reference is asked for later, only if the user says "yes" to adding a Solo Ticket for the same Weigh Event (`_collect_linked_solo_ticket` in `towing_cli/collect.py`), and then attached via `dataclasses.replace`.

**Considered option** (rejected): ask for the Combined Ticket's Reweigh Reference up front, inside `collect_combined_ticket`, every time. Rejected because most Weigh Events have no Solo Ticket at all - a Reweigh Reference that will never be used is a pure cost, and it would have required touching every existing test that drives `collect_combined_ticket`/`run_weigh_event` (all of ticket #7's and #9's Combined-Ticket-only tests supply a fixed sequence of typed responses) purely to skip a field they don't need.

## An unlinked Solo Ticket is discarded, not persisted standalone

When the user adds a Solo Ticket but it ends up not linked to the Combined Ticket - either they decline to save it, or they decline the manual-confirm fallback after a Reweigh Reference mismatch/absence - it is discarded entirely. `WeighEventRecord.solo_ticket` is `None` in that case, identical to a Weigh Event where no Solo Ticket was ever offered.

**Considered option** (rejected): persist the unlinked Solo Ticket anyway, unattached to any Weigh Event, for the user to link later. Rejected because CONTEXT.md already defines Weigh Event as "one Combined Ticket and, optionally, a paired Solo Ticket" - there's no concept yet of a free-floating Solo Ticket outside a Weigh Event, and adding one (a new store, a "link an orphan ticket" flow) is speculative machinery issue #9 doesn't ask for. A user who mis-enters a Solo Ticket can simply re-run the Weigh Event and re-enter it.

**Consequence**: `solo_ticket is None` alone tells you whether a Solo Ticket was linked - no separate boolean is needed, and this also means `WeighEventRecord.trailer_gvwr_result` and `time_gap_hours` are always `None` together with `solo_ticket`, never independently.

## Time-Gap entry: ask for the elapsed hours directly, not two timestamps

There's no OCR-derived timestamp for either ticket (that's blocked on #10), and CAT Scale Tickets are entered entirely by hand today. Rather than asking the user to type two absolute date-times (which would need parsing/validation, and would invite the CLI-entry-time trap - a user typing both tickets in the same sitting minutes apart would show a near-zero gap even if the *actual* scale visits were hours apart), `_collect_linked_solo_ticket` asks a single direct question once a pair is linked: "Hours between when the Combined and Solo Tickets were weighed (0 if the same time)". This is what `check_time_gap` (a pure function in `towing_core/calculations.py`) actually needs, and it's the simplest input that still serves the warning's real purpose - flagging that the Trailer may have changed weight between the two physical weighings.

**Considered option** (rejected): use each ticket's CLI entry time (`datetime.now()`) as its "timestamp". Rejected because it measures how long the *user took to type*, not how far apart the *two scale visits* were - the two are unrelated, and the common real workflow (weigh combined, drive to a truck stop, unhitch, weigh solo, then sit down and enter both tickets together at the end of the day) would always show a near-zero gap under this approach, defeating the warning entirely.

**Considered option** (rejected): prompt for two absolute timestamps (e.g. ISO datetimes) and diff them. Rejected as unnecessary complexity for v1 - it adds parsing/validation surface for a manual-entry-only flow, for no benefit over asking for the gap directly, since the gap is all `check_time_gap` consumes. Revisit if/when #10 lands and tickets carry a real captured timestamp - at that point computing the gap from two OCR'd/confirmed timestamps becomes the natural source, and this manual prompt can be dropped in favor of it.

**Consequence**: `WeighEventRecord.time_gap_hours` stores the raw elapsed-hours figure the user typed (possibly negative if they entered the Solo Ticket's weighing as happening first - `check_time_gap` takes the absolute value). The threshold itself (`DEFAULT_TIME_GAP_THRESHOLD_HOURS = 4.0` in `towing_core/calculations.py`) is a function default, not user-configurable from the CLI in this pass - issue #9 says "configurable" but doesn't specify a mechanism (env var vs. CLI flag vs. a Garage-level setting), and no existing config surface exists in this app to hang it on; wiring one up was treated as separate scope. `check_time_gap(gap_hours, threshold_hours=...)` already accepts an explicit override, so exposing it later is an additive, non-breaking change.

## Consequences

- `CombinedTicket` and `SoloTicket` both gained an optional `reweigh_reference: str | None = None` field (see CONTEXT.md: Reweigh Reference). `SqliteWeighEventStore` persists both (`combined_reweigh_reference`, `solo_reweigh_reference` columns) purely so a saved `WeighEventRecord`'s tickets round-trip losslessly - the reference itself plays no role after the linking decision is made.
- `check_trailer_gvwr_overload` and `compute_derived_trailer_weight` (both in `towing_core/calculations.py`) are pure functions with no CLI/storage dependency, directly unit-tested in `packages/towing-core/tests/test_calculations.py`, per issue #9's explicit acceptance criterion.
- If Reweigh Reference matching ever needs to become fuzzier (e.g. tolerating OCR misreads once #10 lands), `determine_solo_link`'s exact-match-after-strip-and-casefold comparison is the one place to change.
