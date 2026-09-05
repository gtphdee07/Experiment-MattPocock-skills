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
    were weighed hitched together (see CONTEXT.md: Combined Ticket)."""

    steer: float
    drive: float
    trailer_axle: float
    gross: float

    def __str__(self) -> str:
        return (
            f"Steer: {self.steer} lb | Drive: {self.drive} lb | "
            f"Trailer Axle: {self.trailer_axle} lb | Gross: {self.gross} lb"
        )
