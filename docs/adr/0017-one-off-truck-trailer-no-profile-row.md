# One-Off Truck/Trailer: no Profile row, nullable Weigh Event foreign keys

A Weigh Event's Truck or Trailer side can now be a **One-Off** (used once, never saved to the Garage) instead of always referencing a saved Truck Profile / Trailer Profile. Rather than silently creating a real, persisted Profile row behind the scenes, `weigh_events.truck_id`/`trailer_id` become nullable, and a One-Off's rating fields are carried directly on the Weigh Event create payload instead of a Profile ID — leaning on ADR 0004's existing snapshot columns, which already capture every rating and Nickname a Weigh Event record needs regardless of which path created it. Settled via a `/grill-with-docs` session on issue #41 (2026-09-19).

## Considered Options

- **Silently create a normal, permanent Profile row anyway.** Rejected — it would make "One-Off" a lie: the entry would permanently appear in the Garage dashboard and picker lists forever, with no way for the user to know it was never meant to be kept.
- **Create a Profile row but flag it hidden/excluded from Garage listings.** Rejected — introduces a new hidden/visible Profile concept to build, test, and explain, for no benefit over not creating a row at all, since ADR 0004 already means a Weigh Event never needs to re-read a Profile after creation.

## Consequences

- `weigh_events.truck_id`/`trailer_id` go from always-populated to nullable — any future code touching these columns must treat `NULL` as a real, expected case, not an error state.
- The reusable-Solo-Ticket lookup (keyed on a real, persistent `truck_id`) is simply skipped for a One-Off Truck — it has no history to find, by definition.
- See CONTEXT.md's **One-Off Truck** / **One-Off Trailer** entry for the corresponding domain term.
