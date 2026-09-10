export interface TruckForm { gvwr: string; frontGawr: string; rearGawr: string; gcwr: string; }
export interface TrailerForm { gvwr: string; gawr: string; axleCount: string; uvw: string; }
export interface CombinedForm { steer: string; drive: string; trailerAxle: string; gross: string; }
export interface SoloForm { steer: string; drive: string; gross: string; }

export type Status = 'pass' | 'near_limit' | 'fail' | 'not_evaluated';

export interface CheckOut {
  label: string;
  status: Status;
  actual: number | null;
  rating: number | null;
  note: string | null;
}

export interface EvaluateResponse {
  overall_status: Status;
  checks: CheckOut[];
  time_gap_hours: number | null;
  time_gap_exceeds_threshold: boolean | null;
  disclaimer: string;
}
