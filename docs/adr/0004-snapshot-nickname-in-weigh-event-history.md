# Snapshot Nickname in Weigh Event history, not live lookup

Weigh Event history displays each Truck/Trailer Profile by Nickname rather than by database ID. Nicknames are user-editable and Profiles are deletable, so we snapshot the Nickname text onto the `WeighEventRecord` at save time rather than looking it up live from the Garage when history is rendered. This matches how the axle/GCWR ratings on the same record are already snapshotted rather than re-derived, and it avoids needing a fallback path for a Profile that's since been deleted — a concern ticket #7 deliberately designed around when it chose to store `truck_id`/`trailer_id` rather than resolving full Profile details at render time.

## Considered Options

- **Live lookup** (rejected): render history by resolving the Profile's current Nickname from `truck_id`/`trailer_id` at display time. Always shows the latest name, but reintroduces exactly the fragility ticket #7's design avoided — it needs a defined fallback for a deleted Profile, and it means the `WeighEventRecord` alone is no longer a self-contained historical record.

## Consequences

- A renamed Profile does not retroactively change how it appears in past history entries — the entry shows the Nickname as it was at the time of the Weigh Event. This is treated as correct behavior (an honest historical record), not a bug.
- If this decision is revisited in favor of live lookup, the following would need to change:
  - History rendering (`_format_weigh_event_record` and callers) would need the Truck/Trailer store threaded through, not just the `WeighEventRecord` — today it renders from the record alone.
  - A fallback display is needed for a Profile that's since been deleted (e.g. `"Truck Profile #3 (deleted)"`), since the store lookup can fail where a snapshot never could.
  - Existing history rows already hold a snapshotted Nickname string with no flag distinguishing them from a hypothetical future "live" row — a switch would need to decide whether old rows keep rendering their snapshot (mixed behavior across history) or whether the snapshot field is dropped/ignored in favor of always resolving live (accepting the deleted-Profile fallback for old entries too).
  - None of this risks losing data: `truck_id`/`trailer_id` are retained regardless of which rendering approach is used, so a future switch is a rendering-layer change, not a backfill of lost information.
