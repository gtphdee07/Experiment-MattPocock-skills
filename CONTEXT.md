# Towing Limit Checker

Helps an RV owner determine whether a specific Tow Vehicle and Trailer pairing is within its legal weight limits, using actual scale weights rather than estimated capacity.

## Language

**Tow Vehicle**:
The truck or SUV that pulls a Trailer.

**Trailer**:
The towable RV being pulled — a conventional travel trailer or fifth-wheel. Motorhome-towed dinghy vehicles are out of scope.
_Avoid_: RV (too broad), towable.

**GVWR** (Gross Vehicle Weight Rating):
The maximum total weight a single vehicle (Tow Vehicle or Trailer) is rated to weigh on its own. Printed on its certification label.

**GAWR** (Gross Axle Weight Rating):
The maximum weight a specific axle or axle group is rated to carry. Printed on the certification label — given directly per axle position (Front/Rear) for a Tow Vehicle, but as a single per-axle figure for a Trailer that must be multiplied by Axle Count to get a group rating comparable to a CAT Scale Ticket reading.

**GCWR** (Gross Combined Weight Rating):
The maximum total weight of a Tow Vehicle and Trailer combined, as rated by the tow vehicle's manufacturer. Never printed on any physical tag; entered manually into the Truck Profile.

**Axle Count**:
The number of axles on a Trailer. Used to convert its per-axle GAWR into a group rating.

**CAT Scale Ticket**:
A certified weigh ticket from a CAT Scale, reporting Steer Axle, Drive Axle, and Trailer Axle group weights plus Gross Weight.

**Weigh Event**:
A single real-world visit to a scale. Consists of one Combined Ticket and, optionally, a paired Solo Ticket.

**Combined Ticket**:
The CAT Scale Ticket for a Weigh Event where the Tow Vehicle and Trailer were weighed hitched together.

**Solo Ticket**:
The CAT Scale Ticket for a Weigh Event where the Tow Vehicle was weighed alone, used to derive Derived Trailer Weight.

**Reused Solo Weight**:
A past Weigh Event's Solo Ticket Gross Weight, carried forward in place of weighing solo again today — since a Tow Vehicle's own weight rarely changes much between visits. Shown with the date it was recorded. The user may adjust it for a known change since then (extra cargo, fuel, passengers); an adjusted figure is an Unverified Value (see ADR 0006). An unchanged Reused Solo Weight is not.

**Derived Trailer Weight**:
The Trailer's actual weight, computed by subtracting a Solo Ticket's Gross Weight from its paired Combined Ticket's Gross Weight.

**Reweigh Reference**:
A field CAT Scale itself prints on a ticket, connecting a reweigh to the original ticket it belongs with. When a Combined Ticket and a Solo Ticket carry the same (non-blank) Reweigh Reference, they're linked automatically as one Weigh Event's pair; otherwise the user is asked to manually confirm the link (see ADR 0005). Entered manually, or read via the Claude-vision ticket adapter from a photo (see ADR 0007) — same confirm-or-edit step either way.

**Ticket Timestamp**:
A CAT Scale Ticket's own printed date/time, captured as free-form text when a Combined or Solo Ticket is entered via photo (see ADR 0007) — `None` for manual entry, which has no source for it. Distinct from a Weigh Event's own timestamp (when the record was saved) and from the Time-Gap Warning's elapsed-hours entry, which it does not currently feed (see ADR 0005, ADR 0007).

**Garage**:
The user's saved collection of Truck Profiles and Trailer Profiles, mixed and matched per Weigh Event.

**Truck Profile** / **Trailer Profile**:
The saved specs for one Tow Vehicle or Trailer in the Garage: certification-label ratings, plus GCWR (Truck Profile, manual entry) or Axle Count (Trailer Profile, looked up and user-confirmed).

**Nickname**:
A user-editable display name for a Truck Profile or Trailer Profile — e.g. "Addie", "Goose", or a CDL-style truck number. Set at creation (optional) or during a later edit; when left blank, defaults to a name derived from the Profile's database ID (e.g. "Truck 3"). Not required to be unique. Used everywhere a Profile is shown to the user — the database ID itself is never surfaced as the primary way to refer to a Profile.
_Avoid_: Reference, Unit Number, Truck Number.

**Rig**:
A specific Tow Vehicle and Trailer pairing under evaluation.
_Avoid_: combo, setup.

**Rig Evaluation**:
The outcome of running all six overload comparisons for one Weigh Event together (Steer / Drive / Trailer Axle, Hitched GVWR, GCWR, Trailer GVWR) — each carrying its actual weight, its rating, and an Overload Status — plus the advisory Time-Gap Warning.

**Overload Status**:
The state one comparison is in: `Pass`, `Near Limit`, `Fail`, or `Not Evaluated`. `Near Limit` currently applies only to Trailer GVWR Overload (see ADR 0006); `Not Evaluated` only to GCWR Overload (no GCWR on file) and Trailer GVWR Overload (no Solo Ticket).
_Avoid_: verdict, severity, RAG.

**Axle Overload**:
A single axle group's actual weight (from a CAT Scale Ticket) exceeds its GAWR.

**Hitched GVWR Overload**:
The Tow Vehicle's own axle groups, summed while hitched to the Trailer, exceed the Tow Vehicle's GVWR — even when no individual axle exceeds its GAWR.

**GCWR Overload**:
The combined actual weight of Tow Vehicle and Trailer exceeds the Tow Vehicle's GCWR. Not evaluated when the Truck Profile has no GCWR on file.

**Trailer GVWR Overload**:
Derived Trailer Weight exceeds the Trailer Profile's GVWR. Not evaluated when there's neither a linked Solo Ticket nor a Reused Solo Weight for the Weigh Event. Flagged as close to the limit on a narrow under-the-limit margin — never softened when actually over it; see ADR 0006 for the exact margins and why they differ for an Unverified Value.

**Time-Gap Warning**:
A non-blocking, advisory warning shown when a linked Combined+Solo Ticket pair's two physical weighings are more than a configurable threshold apart (default ~4 hours) — the Trailer may have changed weight (fuel, cargo, hitching/unhitching) in between, making Derived Trailer Weight less reliable. Never blocks or invalidates a Weigh Event, unlike the Overload checks.

**Unverified Value**:
A number entered manually with no photo or CAT Scale Ticket backing it — most commonly GCWR, or a Reused Solo Weight the user has adjusted. Any check depending on one is labeled distinctly in output from checks backed by an OCR'd tag or Ticket.
_Avoid_: manual value, self-reported value.

## Code layout

The code is one `uv` workspace with two library tiers and its client apps. `towing-core` (`packages/towing-core`) is the compute tier — domain models, the overload calculations, Rig Evaluation, and the storage / field-acquisition ports with in-memory implementations; it depends on nothing outside the standard library. `towing-app` (`packages/towing-app`) is the application-services tier — Weigh Event orchestration, persistence coordination, and the concrete SQLite and Claude-vision adapters. The workspace members are `packages/towing-core`, `packages/towing-app`, `apps/cli` (the interactive client), and the future `apps/streamlit` calculator (compute tier only). ADR 0008 records the tier split and the workspace; ADR 0009 records why the interactive review/confirm/retry flows stay in the frontends rather than the shared tiers. The pre-existing CLI-flow test suite (`apps/cli/tests/`) is the behavior-invariance safety net for that extraction.
