"""Pure weight-compliance calculations for a Weigh Event.

Every function here takes plain numbers (by way of the domain dataclasses)
and returns a structured result - no I/O, no side effects. That means they
need no test double / fake to unit-test: real numeric inputs in, a real
result out.
"""

from dataclasses import dataclass

from towing_app.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile

DEFAULT_TIME_GAP_THRESHOLD_HOURS = 4.0


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


@dataclass(frozen=True)
class GcwrOverloadResult:
    """GCWR Overload: the Combined Ticket's Gross Weight compared against the
    tow vehicle's GCWR (see CONTEXT.md: GCWR Overload). Only ever constructed
    when the Truck Profile has a GCWR on file - `check_gcwr_overload` returns
    `None` instead when it doesn't, a distinct "not evaluated" state rather
    than a silent pass (see ADR 0002). Because GCWR is a manually-typed
    value with no photo/CAT Scale Ticket backing it, any result here is an
    Unverified Value (see CONTEXT.md: Unverified Value)."""

    combined_actual: float
    gcwr_rating: float

    @property
    def is_overloaded(self) -> bool:
        return self.combined_actual > self.gcwr_rating


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


def check_gcwr_overload(
    truck: TruckProfile, ticket: CombinedTicket
) -> GcwrOverloadResult | None:
    """Compare the Combined Ticket's Gross Weight against the tow vehicle's
    GCWR. GCWR is optional, manual-entry-only on the Truck Profile (see ADR
    0002), so this returns `None` - "not evaluated" - when the profile has
    none on file, rather than treating the check as passed."""
    if truck.gcwr is None:
        return None
    return GcwrOverloadResult(combined_actual=ticket.gross, gcwr_rating=truck.gcwr)


def compute_derived_trailer_weight(combined: CombinedTicket, solo: SoloTicket) -> float:
    """Derived Trailer Weight: a linked pair's Combined Ticket Gross Weight
    minus its Solo Ticket Gross Weight (see CONTEXT.md: Derived Trailer
    Weight). Pure arithmetic - it's the caller's job to only call this for
    a pair that's actually linked (see CONTEXT.md: Reweigh Reference)."""
    return combined.gross - solo.gross


@dataclass(frozen=True)
class TrailerGvwrOverloadResult:
    """Trailer GVWR Overload: Derived Trailer Weight compared against the
    Trailer Profile's GVWR (see CONTEXT.md: Trailer GVWR Overload). Only
    ever constructed when there's a linked Solo Ticket to derive Trailer
    Weight from - `check_trailer_gvwr_overload` returns `None` instead when
    there isn't, the same "not evaluated" shape `check_gcwr_overload` uses
    (see ADR 0002), though unlike GCWR this is never an Unverified Value:
    Trailer GVWR is a required field on every saved Trailer Profile, not an
    optional manually-typed one."""

    derived_trailer_weight: float
    gvwr_rating: float

    @property
    def is_overloaded(self) -> bool:
        return self.derived_trailer_weight > self.gvwr_rating


def check_trailer_gvwr_overload(
    trailer: TrailerProfile, combined: CombinedTicket, solo: SoloTicket | None
) -> TrailerGvwrOverloadResult | None:
    """Compare Derived Trailer Weight against the Trailer Profile's GVWR.
    Not evaluated - returns `None` - when there's no linked Solo Ticket to
    derive a Trailer Weight from (see CONTEXT.md: Trailer GVWR Overload)."""
    if solo is None:
        return None
    return TrailerGvwrOverloadResult(
        derived_trailer_weight=compute_derived_trailer_weight(combined, solo),
        gvwr_rating=trailer.gvwr,
    )


@dataclass(frozen=True)
class TimeGapWarningResult:
    """Time-Gap Warning: a linked Combined+Solo Ticket pair's timestamps are
    more than a configurable threshold apart (see CONTEXT.md: Time-Gap
    Warning). Non-blocking and advisory only - unlike the Overload checks,
    nothing in this result stops or invalidates a Weigh Event."""

    gap_hours: float
    threshold_hours: float

    @property
    def exceeds_threshold(self) -> bool:
        return abs(self.gap_hours) > self.threshold_hours


def check_time_gap(
    gap_hours: float,
    threshold_hours: float = DEFAULT_TIME_GAP_THRESHOLD_HOURS,
) -> TimeGapWarningResult:
    """Compare the elapsed time between a linked pair's two physical
    weighings against `threshold_hours` (default ~4 hours, see CONTEXT.md:
    Time-Gap Warning). `gap_hours` may be negative (Solo weighed before
    Combined) - only its magnitude matters."""
    return TimeGapWarningResult(gap_hours=gap_hours, threshold_hours=threshold_hours)
