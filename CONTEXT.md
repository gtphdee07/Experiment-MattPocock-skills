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

**Garage**:
The user's saved collection of Truck Profiles and Trailer Profiles, mixed and matched per Weigh Event.

**Truck Profile** / **Trailer Profile**:
The saved specs for one Tow Vehicle or Trailer in the Garage: certification-label ratings, plus GCWR (Truck Profile, manual entry) or Axle Count (Trailer Profile, looked up and user-confirmed).

**Axle Overload**:
A single axle group's actual weight (from a CAT Scale Ticket) exceeds its GAWR.

**Hitched GVWR Overload**:
The Tow Vehicle's own axle groups, summed while hitched to the Trailer, exceed the Tow Vehicle's GVWR — even when no individual axle exceeds its GAWR.

**GCWR Overload**:
The combined actual weight of Tow Vehicle and Trailer exceeds the Tow Vehicle's GCWR. Not evaluated when the Truck Profile has no GCWR on file.

**Unverified Value**:
A number entered manually with no photo or CAT Scale Ticket backing it — most commonly GCWR. Any check depending on one is labeled distinctly in output from checks backed by an OCR'd tag or Ticket.
_Avoid_: manual value, self-reported value.
