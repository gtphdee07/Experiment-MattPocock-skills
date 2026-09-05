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

**Derived Trailer Weight**:
The Trailer's actual weight, computed by subtracting a Solo Ticket's Gross Weight from its paired Combined Ticket's Gross Weight.

**Reweigh Reference**:
A field CAT Scale itself prints on a ticket, connecting a reweigh to the original ticket it belongs with. When a Combined Ticket and a Solo Ticket carry the same (non-blank) Reweigh Reference, they're linked automatically as one Weigh Event's pair; otherwise the user is asked to manually confirm the link (see ADR 0005). Entered manually today, same as every other ticket field — there's no OCR for CAT Scale Tickets yet (see #10).

**Garage**:
The user's saved collection of Truck Profiles and Trailer Profiles, mixed and matched per Weigh Event.

**Truck Profile** / **Trailer Profile**:
The saved specs for one Tow Vehicle or Trailer in the Garage: certification-label ratings, plus GCWR (Truck Profile, manual entry) or Axle Count (Trailer Profile, looked up and user-confirmed).

**Nickname**:
A user-editable display name for a Truck Profile or Trailer Profile — e.g. "Addie", "Goose", or a CDL-style truck number. Set at creation (optional) or during a later edit; when left blank, defaults to a name derived from the Profile's database ID (e.g. "Truck 3"). Not required to be unique. Used everywhere a Profile is shown to the user — the database ID itself is never surfaced as the primary way to refer to a Profile.
_Avoid_: Reference, Unit Number, Truck Number.

**Axle Overload**:
A single axle group's actual weight (from a CAT Scale Ticket) exceeds its GAWR.

**Hitched GVWR Overload**:
The Tow Vehicle's own axle groups, summed while hitched to the Trailer, exceed the Tow Vehicle's GVWR — even when no individual axle exceeds its GAWR.

**GCWR Overload**:
The combined actual weight of Tow Vehicle and Trailer exceeds the Tow Vehicle's GCWR. Not evaluated when the Truck Profile has no GCWR on file.

**Trailer GVWR Overload**:
Derived Trailer Weight exceeds the Trailer Profile's GVWR. Not evaluated when there's no linked Solo Ticket for the Weigh Event.

**Time-Gap Warning**:
A non-blocking, advisory warning shown when a linked Combined+Solo Ticket pair's two physical weighings are more than a configurable threshold apart (default ~4 hours) — the Trailer may have changed weight (fuel, cargo, hitching/unhitching) in between, making Derived Trailer Weight less reliable. Never blocks or invalidates a Weigh Event, unlike the Overload checks.

**Unverified Value**:
A number entered manually with no photo or CAT Scale Ticket backing it — most commonly GCWR. Any check depending on one is labeled distinctly in output from checks backed by an OCR'd tag or Ticket.
_Avoid_: manual value, self-reported value.
