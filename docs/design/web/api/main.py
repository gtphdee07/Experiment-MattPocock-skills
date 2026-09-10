"""FastAPI evaluation service for the Towing Limit Checker.

Thin HTTP wrapper over the existing `towing_core` package - no duplicated
math. Mount this alongside the workspace (it imports `towing_core` exactly
like `apps/streamlit` and `apps/cli` already do), so the calculation stays
the single source of truth across every front-end.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from towing_core.evaluation import evaluate_weigh_event
from towing_core.models import CombinedTicket, SoloTicket, TrailerProfile, TruckProfile
from towing_core.report import LEGAL_DISCLAIMER

app = FastAPI(title="Towing Limit Checker API")

# Tighten allow_origins to the deployed frontend origin(s) before shipping.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/evaluate", response_model=EvaluateResponse)
def evaluate(req: EvaluateRequest) -> EvaluateResponse:
    truck = TruckProfile(
        gvwr=req.truck.gvwr,
        front_gawr=req.truck.front_gawr,
        rear_gawr=req.truck.rear_gawr,
        gcwr=req.truck.gcwr,
    )
    trailer = TrailerProfile(
        gvwr=req.trailer.gvwr,
        gawr=req.trailer.gawr,
        axle_count=req.trailer.axle_count,
        uvw=req.trailer.uvw,
    )
    combined = CombinedTicket(
        steer=req.combined.steer,
        drive=req.combined.drive,
        trailer_axle=req.combined.trailer_axle,
        gross=req.combined.gross,
    )
    solo = (
        SoloTicket(steer=req.solo.steer, drive=req.solo.drive, gross=req.solo.gross)
        if req.solo is not None
        else None
    )

    evaluation = evaluate_weigh_event(
        truck, trailer, combined, solo, time_gap_hours=req.time_gap_hours
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
            CheckOut(label=c.label, status=c.status.value, actual=c.actual, rating=c.rating, note=c.note)
            for c in checks
        ],
        time_gap_hours=evaluation.time_gap_result.gap_hours if evaluation.time_gap_result else None,
        time_gap_exceeds_threshold=(
            evaluation.time_gap_result.exceeds_threshold if evaluation.time_gap_result else None
        ),
        disclaimer=LEGAL_DISCLAIMER,
    )
