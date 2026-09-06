from dataclasses import dataclass, field


@dataclass(frozen=True)
class TruckProfile:
    """`nickname` is a user-editable display name (see CONTEXT.md: Nickname)
    - `None` when left blank, which callers display as a computed default
    ("Truck {id}") rather than writing that default back to storage (see
    ticket #12). Deliberately excluded from `__str__`, which stays limited
    to the certification-label ratings - callers that want the Nickname
    alongside those ratings compose it themselves (see `cli._list_with_ids`)."""

    gvwr: float
    front_gawr: float
    rear_gawr: float
    gcwr: float | None = None
    nickname: str | None = None
    id: int | None = field(default=None, compare=False)

    def __str__(self) -> str:
        gcwr_display = self.gcwr if self.gcwr is not None else "(not on file)"
        return (
            f"GVWR: {self.gvwr} lb | Front GAWR: {self.front_gawr} lb | "
            f"Rear GAWR: {self.rear_gawr} lb | GCWR: {gcwr_display}"
        )


@dataclass(frozen=True)
class TrailerProfile:
    """`nickname` mirrors `TruckProfile.nickname` - see that field's
    docstring (default display: "Trailer {id}")."""

    gvwr: float
    gawr: float
    axle_count: int
    uvw: float | None = None
    nickname: str | None = None
    id: int | None = field(default=None, compare=False)

    def __str__(self) -> str:
        uvw_display = self.uvw if self.uvw is not None else "(not on file)"
        return (
            f"GVWR: {self.gvwr} lb | GAWR (each axle): {self.gawr} lb | "
            f"Axle count: {self.axle_count} | UVW: {uvw_display}"
        )


@dataclass(frozen=True)
class CombinedTicket:
    """A CAT Scale Ticket for a Weigh Event where the Tow Vehicle and Trailer
    were weighed hitched together (see CONTEXT.md: Combined Ticket).

    `reweigh_reference` is CAT Scale's own printed field connecting a
    reweigh to its original ticket - when it matches a paired Solo Ticket's
    `reweigh_reference`, the two are linked automatically (see CONTEXT.md:
    Reweigh Reference). `None` when the ticket doesn't carry one, which is
    the common case for a Combined Ticket entered with no Solo Ticket to
    link.

    `timestamp` is the ticket's own printed date/time, as a free-form string
    (e.g. from OCR - see ticket #10). `None` when entered manually, since
    manual entry has no source for it (see ADR 0005's Time-Gap entry, which
    still asks for elapsed hours directly rather than deriving it from this
    field - see ADR 0007). This is distinct from `WeighEventRecord.timestamp`
    in `towing_app/storage.py`, which is when the record was *saved*, not
    when the ticket was physically weighed."""

    steer: float
    drive: float
    trailer_axle: float
    gross: float
    reweigh_reference: str | None = None
    timestamp: str | None = None

    def __str__(self) -> str:
        base = (
            f"Steer: {self.steer} lb | Drive: {self.drive} lb | "
            f"Trailer Axle: {self.trailer_axle} lb | Gross: {self.gross} lb"
        )
        if self.timestamp is not None:
            base += f" | Timestamp: {self.timestamp}"
        if self.reweigh_reference is not None:
            base += f" | Reweigh Ref: {self.reweigh_reference}"
        return base


@dataclass(frozen=True)
class SoloTicket:
    """A CAT Scale Ticket for a Weigh Event where the Tow Vehicle was
    weighed alone, used to derive Derived Trailer Weight (see CONTEXT.md:
    Solo Ticket). No Trailer Axle reading - nothing is hitched behind the
    Tow Vehicle when a Solo Ticket is taken.

    `reweigh_reference` and `timestamp` mirror `CombinedTicket`'s fields of
    the same name - see those fields' docstrings."""

    steer: float
    drive: float
    gross: float
    reweigh_reference: str | None = None
    timestamp: str | None = None

    def __str__(self) -> str:
        base = (
            f"Steer: {self.steer} lb | Drive: {self.drive} lb | Gross: {self.gross} lb"
        )
        if self.timestamp is not None:
            base += f" | Timestamp: {self.timestamp}"
        if self.reweigh_reference is not None:
            base += f" | Reweigh Ref: {self.reweigh_reference}"
        return base
