from dataclasses import dataclass, field


@dataclass(frozen=True)
class TruckProfile:
    gvwr: float
    front_gawr: float
    rear_gawr: float
    gcwr: float | None = None
    id: int | None = field(default=None, compare=False)

    def __str__(self) -> str:
        gcwr_display = self.gcwr if self.gcwr is not None else "(not on file)"
        return (
            f"GVWR: {self.gvwr} lb | Front GAWR: {self.front_gawr} lb | "
            f"Rear GAWR: {self.rear_gawr} lb | GCWR: {gcwr_display}"
        )


@dataclass(frozen=True)
class TrailerProfile:
    gvwr: float
    gawr: float
    axle_count: int
    uvw: float | None = None
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
    link."""

    steer: float
    drive: float
    trailer_axle: float
    gross: float
    reweigh_reference: str | None = None

    def __str__(self) -> str:
        base = (
            f"Steer: {self.steer} lb | Drive: {self.drive} lb | "
            f"Trailer Axle: {self.trailer_axle} lb | Gross: {self.gross} lb"
        )
        if self.reweigh_reference is not None:
            base += f" | Reweigh Ref: {self.reweigh_reference}"
        return base


@dataclass(frozen=True)
class SoloTicket:
    """A CAT Scale Ticket for a Weigh Event where the Tow Vehicle was
    weighed alone, used to derive Derived Trailer Weight (see CONTEXT.md:
    Solo Ticket). No Trailer Axle reading - nothing is hitched behind the
    Tow Vehicle when a Solo Ticket is taken.

    `reweigh_reference` mirrors `CombinedTicket.reweigh_reference` - see
    that field's docstring."""

    steer: float
    drive: float
    gross: float
    reweigh_reference: str | None = None

    def __str__(self) -> str:
        base = (
            f"Steer: {self.steer} lb | Drive: {self.drive} lb | Gross: {self.gross} lb"
        )
        if self.reweigh_reference is not None:
            base += f" | Reweigh Ref: {self.reweigh_reference}"
        return base
