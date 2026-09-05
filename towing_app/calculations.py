"""Pure weight-compliance calculations for a Weigh Event.

Every function here takes plain numbers (by way of the domain dataclasses)
and returns a structured result - no I/O, no side effects. That means they
need no test double / fake to unit-test: real numeric inputs in, a real
result out.
"""

from dataclasses import dataclass

from towing_app.models import CombinedTicket, TrailerProfile, TruckProfile


@dataclass(frozen=True)
class AxleCheckResult:
    """One axle group's actual weight compared against its rating."""

    axle_name: str
    actual: float
    rating: float

    @property
    def is_overloaded(self) -> bool:
        return self.actual > self.rating


@dataclass(frozen=True)
class AxleOverloadResult:
    """Axle Overload: each Combined Ticket axle-group reading compared
    against the matching profile's GAWR (see CONTEXT.md: Axle Overload)."""

    steer: AxleCheckResult
    drive: AxleCheckResult
    trailer: AxleCheckResult

    @property
    def any_overloaded(self) -> bool:
        return any(
            check.is_overloaded for check in (self.steer, self.drive, self.trailer)
        )


@dataclass(frozen=True)
class HitchedGvwrOverloadResult:
    """Hitched GVWR Overload: the tow vehicle's own axle groups (Steer +
    Drive), summed while hitched, compared against its GVWR. This can fire
    even when no individual axle exceeds its own GAWR (see CONTEXT.md:
    Hitched GVWR Overload)."""

    combined_actual: float
    gvwr_rating: float

    @property
    def is_overloaded(self) -> bool:
        return self.combined_actual > self.gvwr_rating


def check_axle_overload(
    truck: TruckProfile, trailer: TrailerProfile, ticket: CombinedTicket
) -> AxleOverloadResult:
    """Compare each Combined Ticket axle-group reading to its group rating.

    The Trailer Profile's GAWR is a per-axle figure (CONTEXT.md: GAWR), so it
    is multiplied by Axle Count to get a group rating comparable to the
    ticket's single Trailer Axle reading.
    """
    trailer_group_rating = trailer.gawr * trailer.axle_count
    return AxleOverloadResult(
        steer=AxleCheckResult(
            axle_name="Steer Axle", actual=ticket.steer, rating=truck.front_gawr
        ),
        drive=AxleCheckResult(
            axle_name="Drive Axle", actual=ticket.drive, rating=truck.rear_gawr
        ),
        trailer=AxleCheckResult(
            axle_name="Trailer Axle",
            actual=ticket.trailer_axle,
            rating=trailer_group_rating,
        ),
    )


def check_hitched_gvwr_overload(
    truck: TruckProfile, ticket: CombinedTicket
) -> HitchedGvwrOverloadResult:
    """Sum the tow vehicle's own axle groups (Steer + Drive) and compare
    against its GVWR. Only the tow vehicle's readings are involved - the
    Trailer Axle reading plays no part in this check."""
    combined_actual = ticket.steer + ticket.drive
    return HitchedGvwrOverloadResult(
        combined_actual=combined_actual, gvwr_rating=truck.gvwr
    )
