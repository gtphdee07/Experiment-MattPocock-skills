from dataclasses import dataclass


@dataclass(frozen=True)
class TruckProfile:
    gvwr: float
    front_gawr: float
    rear_gawr: float
    gcwr: float | None = None
