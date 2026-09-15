"""Rig evaluation: run every Weigh Event overload check and fold each result
into a single pass / near-limit / fail / not-evaluated status.

This is a pure aggregation layer over `towing_core.calculations` - no I/O.
It exists so callers (the CLI's text renderer today, other front-ends
later) can ask "how did this rig do?" without re-deriving the per-check
verdict logic themselves. `NEAR_LIMIT` is only ever reachable for the
Trailer GVWR Overload check (see ADR 0006: near-limit flagging is scoped to
Trailer GVWR Overload alone).
"""

from dataclasses import dataclass
from enum import Enum

from towing_core.calculations import (
    DEFAULT_TIME_GAP_THRESHOLD_HOURS,
    AxleCheckResult,
    AxleOverloadResult,
    GcwrOverloadResult,
    HitchedGvwrOverloadResult,
    TimeGapWarningResult,
    TrailerGvwrOverloadResult,
    check_axle_overload,
    check_gcwr_overload,
    check_hitched_gvwr_overload,
    check_time_gap,
    check_trailer_gvwr_overload,
)
from towing_core.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile
from towing_core.storage import WeighEventRecord

CheckResult = (
    AxleCheckResult
    | HitchedGvwrOverloadResult
    | GcwrOverloadResult
    | TrailerGvwrOverloadResult
)


class OverloadStatus(Enum):
    PASS = "pass"
    NEAR_LIMIT = "near_limit"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"


def status_for(result: CheckResult | None) -> OverloadStatus:
    """Fold one raw check result into an `OverloadStatus`.

    `None` (a check that never ran - no GCWR on file, no linked Solo Ticket)
    is `NOT_EVALUATED`. `NEAR_LIMIT` is only ever returned for a
    `TrailerGvwrOverloadResult` - the other check results carry no
    solo-weight-derived uncertainty to flag (see ADR 0006)."""
    if result is None:
        return OverloadStatus.NOT_EVALUATED
    if isinstance(result, TrailerGvwrOverloadResult):
        if result.is_overloaded:
            return OverloadStatus.FAIL
        if result.is_near_limit:
            return OverloadStatus.NEAR_LIMIT
        return OverloadStatus.PASS
    return OverloadStatus.FAIL if result.is_overloaded else OverloadStatus.PASS


@dataclass(frozen=True)
class EvaluatedCheck:
    """One overload check, reduced to a labelled actual-vs-rating verdict.

    `actual` / `rating` are `None` for a check that was not evaluated;
    `note` carries the reason in that case."""

    label: str
    actual: float | None
    rating: float | None
    status: OverloadStatus
    note: str | None = None


_STATUS_PRECEDENCE = {
    OverloadStatus.FAIL: 3,
    OverloadStatus.NEAR_LIMIT: 2,
    OverloadStatus.NOT_EVALUATED: 1,
    OverloadStatus.PASS: 0,
}


@dataclass(frozen=True)
class RigEvaluation:
    """Every Weigh Event check for one Truck+Trailer+ticket(s) combination,
    each as an `EvaluatedCheck`, plus the raw result objects carried through
    for callers that need the underlying numbers."""

    steer_axle: EvaluatedCheck
    drive_axle: EvaluatedCheck
    trailer_axle: EvaluatedCheck
    hitched_gvwr: EvaluatedCheck
    gcwr: EvaluatedCheck
    trailer_gvwr: EvaluatedCheck
    time_gap_result: TimeGapWarningResult | None
    axle_result: AxleOverloadResult
    hitched_gvwr_result: HitchedGvwrOverloadResult
    gcwr_result: GcwrOverloadResult | None
    trailer_gvwr_result: TrailerGvwrOverloadResult | None

    @property
    def overall_status(self) -> OverloadStatus:
        """The worst of the six checks. Precedence:
        FAIL > NEAR_LIMIT > NOT_EVALUATED > PASS."""
        checks = (
            self.steer_axle,
            self.drive_axle,
            self.trailer_axle,
            self.hitched_gvwr,
            self.gcwr,
            self.trailer_gvwr,
        )
        return max(
            (check.status for check in checks),
            key=lambda status: _STATUS_PRECEDENCE[status],
        )


def _assemble_rig_evaluation(
    axle_result: AxleOverloadResult,
    hitched_gvwr_result: HitchedGvwrOverloadResult,
    gcwr_result: GcwrOverloadResult | None,
    trailer_gvwr_result: TrailerGvwrOverloadResult | None,
    time_gap_result: TimeGapWarningResult | None,
) -> RigEvaluation:
    """Fold five already-computed raw check results into a `RigEvaluation`
    of `EvaluatedCheck`s. The one place both `evaluate_weigh_event` (fresh
    checks, run from truck/trailer/ticket inputs) and
    `rig_evaluation_from_record` (checks already run and persisted on a
    `WeighEventRecord`) converge, so there is exactly one fold from raw
    results to Overload Status regardless of where the raw results came
    from."""
    steer_axle = EvaluatedCheck(
        label="Steer Axle",
        actual=axle_result.steer.actual,
        rating=axle_result.steer.rating,
        status=status_for(axle_result.steer),
    )
    drive_axle = EvaluatedCheck(
        label="Drive Axle",
        actual=axle_result.drive.actual,
        rating=axle_result.drive.rating,
        status=status_for(axle_result.drive),
    )
    trailer_axle = EvaluatedCheck(
        label="Trailer Axle",
        actual=axle_result.trailer.actual,
        rating=axle_result.trailer.rating,
        status=status_for(axle_result.trailer),
    )

    hitched_gvwr = EvaluatedCheck(
        label="Hitched GVWR",
        actual=hitched_gvwr_result.combined_actual,
        rating=hitched_gvwr_result.gvwr_rating,
        status=status_for(hitched_gvwr_result),
    )

    if gcwr_result is None:
        gcwr = EvaluatedCheck(
            label="GCWR",
            actual=None,
            rating=None,
            status=OverloadStatus.NOT_EVALUATED,
            note="No GCWR on file for this Truck Profile.",
        )
    else:
        gcwr = EvaluatedCheck(
            label="GCWR",
            actual=gcwr_result.combined_actual,
            rating=gcwr_result.gcwr_rating,
            status=status_for(gcwr_result),
        )

    if trailer_gvwr_result is None:
        trailer_gvwr = EvaluatedCheck(
            label="Trailer GVWR",
            actual=None,
            rating=None,
            status=OverloadStatus.NOT_EVALUATED,
            note="No Solo Ticket for this Weigh Event.",
        )
    else:
        trailer_gvwr = EvaluatedCheck(
            label="Trailer GVWR",
            actual=trailer_gvwr_result.derived_trailer_weight,
            rating=trailer_gvwr_result.gvwr_rating,
            status=status_for(trailer_gvwr_result),
        )

    return RigEvaluation(
        steer_axle=steer_axle,
        drive_axle=drive_axle,
        trailer_axle=trailer_axle,
        hitched_gvwr=hitched_gvwr,
        gcwr=gcwr,
        trailer_gvwr=trailer_gvwr,
        time_gap_result=time_gap_result,
        axle_result=axle_result,
        hitched_gvwr_result=hitched_gvwr_result,
        gcwr_result=gcwr_result,
        trailer_gvwr_result=trailer_gvwr_result,
    )


def evaluate_weigh_event(
    truck: TruckProfile,
    trailer: TrailerProfile,
    combined: CombinedTicket,
    solo: SoloTicket | None = None,
    *,
    solo_is_unverified: bool = False,
    time_gap_hours: float | None = None,
    time_gap_threshold_hours: float = DEFAULT_TIME_GAP_THRESHOLD_HOURS,
) -> RigEvaluation:
    """Run every overload check for this Weigh Event and fold each into an
    `EvaluatedCheck`, keeping the raw result objects on the `RigEvaluation`.

    `solo` is the linked Solo Ticket, if any; `solo_is_unverified` flows into
    `check_trailer_gvwr_overload` (a manually-adjusted Reused Solo Weight -
    see ADR 0006). A Time-Gap Warning is only produced when `time_gap_hours`
    is given."""
    axle = check_axle_overload(truck, trailer, combined)
    hitched = check_hitched_gvwr_overload(truck, combined)
    gcwr_result = check_gcwr_overload(truck, combined)
    trailer_gvwr_result = check_trailer_gvwr_overload(
        trailer, combined, solo, solo_is_unverified=solo_is_unverified
    )
    time_gap_result = (
        check_time_gap(time_gap_hours, time_gap_threshold_hours)
        if time_gap_hours is not None
        else None
    )

    return _assemble_rig_evaluation(
        axle, hitched, gcwr_result, trailer_gvwr_result, time_gap_result
    )


def rig_evaluation_from_record(
    record: WeighEventRecord,
    *,
    time_gap_threshold_hours: float = DEFAULT_TIME_GAP_THRESHOLD_HOURS,
) -> RigEvaluation:
    """The history-path equivalent of `evaluate_weigh_event`: fold a
    persisted `WeighEventRecord`'s already-computed raw check results into a
    `RigEvaluation`, via the same `_assemble_rig_evaluation` fold, without
    reconstructing truck/trailer/ticket objects or re-running any `check_*`
    function - the record already carries `axle_result`/`gvwr_result`
    (Hitched GVWR)/`gcwr_result`/`trailer_gvwr_result` from when the Weigh
    Event was first evaluated and saved.

    A Time-Gap Warning is re-derived from the record's stored
    `time_gap_hours` (rather than persisted itself), the same "only present
    when there was a linked Solo Ticket" rule `evaluate_weigh_event` follows."""
    time_gap_result = (
        check_time_gap(record.time_gap_hours, time_gap_threshold_hours)
        if record.time_gap_hours is not None
        else None
    )
    return _assemble_rig_evaluation(
        record.axle_result,
        record.gvwr_result,
        record.gcwr_result,
        record.trailer_gvwr_result,
        time_gap_result,
    )
