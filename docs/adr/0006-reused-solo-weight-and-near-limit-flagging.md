# Reused Solo Weight, and near-limit flagging scoped to Trailer GVWR Overload only

A Tow Vehicle's own weight rarely changes much between visits, so requiring a fresh Solo Ticket every single Weigh Event is unnecessary friction. This ADR records the design for reusing a past Solo Ticket's Gross Weight instead, and the near-limit flagging that reuse motivated.

## Reuse has no staleness threshold

Choosing to reuse a Solo Weight always shows its date and asks whether anything's changed since then (extra cargo, fuel, passengers) — regardless of how old it is. No day/week threshold gates this prompt.

**Considered option** (rejected): gate the prompt behind a staleness threshold (e.g. only ask if the reused weight is more than N days old). Rejected as needless complexity — the threshold would be arbitrary, and the person entering it already knows whether their situation changed far better than a day-count could infer. Asking every time costs nothing and is never wrong.

## Provenance decides whether a reused weight is an Unverified Value

A Reused Solo Weight used unchanged is still a real CAT Scale reading — just an old one — and is not an Unverified Value. Only when the user types a new figure to account for a known change does that Weigh Event's Trailer GVWR Overload become an Unverified Value, identical treatment to how GCWR Overload already works. This corrects `TrailerGvwrOverloadResult`'s docstring, which previously stated Trailer GVWR Overload is *never* an Unverified Value — true only when the Solo Ticket is fresh or reused unchanged.

## Near-limit flagging is scoped to Trailer GVWR Overload alone

Axle Overload, Hitched GVWR Overload, and GCWR Overload all compare a CAT Scale Combined Ticket reading (ground truth) against a certification-label rating or a manually-entered-but-fixed GCWR — none of them carry solo-weight-derived uncertainty. Only Trailer GVWR Overload's input (Derived Trailer Weight) can come from a Reused Solo Weight, so only it gets margin-based flagging. Extending it to the other three checks was considered and rejected: it would be a mechanically easy change (they share the same actual-vs-rating shape), but a behavior change to already-shipped checks with no actual uncertainty to flag.

## The flag never fires when actually over the limit

Flagging only applies on the under-the-limit side: within 100 lbs under, on a trusted reading; within 300 lbs under, on an Unverified Value (a wider margin because the number itself is a guess, not just an old-but-real reading). Being over the limit is reported as overloaded, full stop, with no "close" qualifier.

**Why**: a "close but technically legal" tag reads as reassurance. Over the line, that reassurance is actively wrong and carries real legal/liability weight; under the line, a thin margin is exactly the useful thing to flag before it becomes a real overload on the next trip.

## Time-Gap Warning is unaffected

`check_time_gap`/`TimeGapWarningResult`, merged in #9, stays exactly as it is. It serves a different scenario (two tickets from the same visit, hours apart) than Reused Solo Weight (a past visit, weeks or months apart) — the two don't overlap: reusing a weight means no fresh Solo Ticket is entered at all, so `check_time_gap` never runs in that path.

## Consequences

- `SoloTicket`'s Gross Weight, whether fresh or reused, is what `compute_derived_trailer_weight` and `check_trailer_gvwr_overload` consume — a Reused Solo Weight is represented the same way once resolved, with an additional flag/date carried alongside for display and Unverified Value labeling.
- If margin-based flagging is ever wanted on the other three checks, this ADR's rejection above is the place to revisit — nothing in `check_axle_overload`, `check_hitched_gvwr_overload`, or `check_gcwr_overload` needs to change to add it later, since flagging is additive to each result's existing actual-vs-rating shape.
