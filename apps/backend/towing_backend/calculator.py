"""The free calculator's `POST /api/evaluate` (issue #38).

Ports `docs/design/web/api/main.py`'s logic directly - already a thin,
correct wrapper over `towing_core.evaluate_weigh_event` with no duplicated
math - into `apps/backend`, since that's the backend `apps/web`'s
calculator page (`Calculator.tsx`) actually calls in production. Request/
response shapes are unchanged from that reference implementation, confirmed
byte-for-byte against what `Calculator.tsx` sends and `apps/web/src/
types.ts` expects.

**Deliberately unauthenticated**: the calculator must stay reachable by a
fully anonymous visitor, no Account, per ADR 0013 - this is the one route
in `apps/backend` that isn't gated by `current_active_account`. Every other
route relies on session auth as its abuse mitigation; this one can't, so it
gets a per-IP rate limit (slowapi) instead. `evaluate_weigh_event` is pure,
dependency-free, in-memory compute (no I/O, no external cost - unlike the
photo-OCR routes, which are auth-gated specifically to protect Anthropic
spend), so the risk here is availability, not billing.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel
from slowapi import Limiter

from towing_core.evaluation import evaluate_weigh_event
from towing_core.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile
from towing_core.report import LEGAL_DISCLAIMER

# A generous per-IP ceiling for genuine interactive use, low enough to blunt
# a scripted flood - the exact number is an implementation-time call, not
# grilled (issue #38's own text).
RATE_LIMIT = "30/minute"


class TruckIn(BaseModel):
    gvwr: float
    front_gawr: float
    rear_gawr: float
    gcwr: float | None = None


class TrailerIn(BaseModel):
    gvwr: float
    gawr: float
    axle_count: int
    uvw: float | None = None


class CombinedIn(BaseModel):
    steer: float
    drive: float
    trailer_axle: float
    gross: float


class SoloIn(BaseModel):
    steer: float
    drive: float
    gross: float


class EvaluateRequest(BaseModel):
    truck: TruckIn
    trailer: TrailerIn
    combined: CombinedIn
    solo: SoloIn | None = None
    time_gap_hours: float | None = None


class CheckOut(BaseModel):
    label: str
    status: str
    actual: float | None
    rating: float | None
    note: str | None


class EvaluateResponse(BaseModel):
    overall_status: str
    # Fixed order: Steer, Drive, Trailer Axle, Hitched GVWR, GCWR, Trailer GVWR
    checks: list[CheckOut]
    time_gap_hours: float | None
    time_gap_exceeds_threshold: bool | None
    disclaimer: str


def build_calculator_router(limiter: Limiter) -> APIRouter:
    router = APIRouter()

    @router.post("/api/evaluate", response_model=EvaluateResponse)
    @limiter.limit(RATE_LIMIT)
    def evaluate(request: Request, payload: EvaluateRequest) -> EvaluateResponse:
        truck = TruckProfile(
            gvwr=payload.truck.gvwr,
            front_gawr=payload.truck.front_gawr,
            rear_gawr=payload.truck.rear_gawr,
            gcwr=payload.truck.gcwr,
        )
        trailer = TrailerProfile(
            gvwr=payload.trailer.gvwr,
            gawr=payload.trailer.gawr,
            axle_count=payload.trailer.axle_count,
            uvw=payload.trailer.uvw,
        )
        combined = CombinedTicket(
            steer=payload.combined.steer,
            drive=payload.combined.drive,
            trailer_axle=payload.combined.trailer_axle,
            gross=payload.combined.gross,
        )
        solo = (
            SoloTicket(
                steer=payload.solo.steer,
                drive=payload.solo.drive,
                gross=payload.solo.gross,
            )
            if payload.solo is not None
            else None
        )

        evaluation = evaluate_weigh_event(
            truck, trailer, combined, solo, time_gap_hours=payload.time_gap_hours
        )

        checks = [
            evaluation.steer_axle,
            evaluation.drive_axle,
            evaluation.trailer_axle,
            evaluation.hitched_gvwr,
            evaluation.gcwr,
            evaluation.trailer_gvwr,
        ]

        return EvaluateResponse(
            overall_status=evaluation.overall_status.value,
            checks=[
                CheckOut(
                    label=c.label,
                    status=c.status.value,
                    actual=c.actual,
                    rating=c.rating,
                    note=c.note,
                )
                for c in checks
            ],
            time_gap_hours=(
                evaluation.time_gap_result.gap_hours
                if evaluation.time_gap_result
                else None
            ),
            time_gap_exceeds_threshold=(
                evaluation.time_gap_result.exceeds_threshold
                if evaluation.time_gap_result
                else None
            ),
            disclaimer=LEGAL_DISCLAIMER,
        )

    return router
