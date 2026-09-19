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

// --- Account / auth (apps/backend, issue #18) -------------------------------

export interface Account {
  id: number;
  email: string;
  is_active: boolean;
  is_verified: boolean;
  is_superuser: boolean;
  created_at: string;
}

// --- Garage: Truck/Trailer Profiles (apps/backend, issue #19) --------------

export interface TruckProfile {
  id: number;
  gvwr: number;
  front_gawr: number;
  rear_gawr: number;
  gcwr: number | null;
  nickname: string;
}

export interface TruckProfileIn {
  gvwr: number;
  front_gawr: number;
  rear_gawr: number;
  gcwr?: number | null;
  nickname?: string | null;
}

export interface TruckProfileUpdate {
  gvwr?: number;
  front_gawr?: number;
  rear_gawr?: number;
  gcwr?: number | null;
  nickname?: string | null;
}

export interface TrailerProfile {
  id: number;
  gvwr: number;
  gawr: number;
  axle_count: number;
  uvw: number | null;
  nickname: string;
}

export interface TrailerProfileIn {
  gvwr: number;
  gawr: number;
  axle_count: number;
  uvw?: number | null;
  nickname?: string | null;
}

export interface TrailerProfileUpdate {
  gvwr?: number;
  gawr?: number;
  axle_count?: number;
  uvw?: number | null;
  nickname?: string | null;
}

// --- Weigh Events (apps/backend, issue #21) ---------------------------------

export interface ReusableSoloTicket {
  gross: number;
  from_timestamp: string;
}

export interface CombinedTicketIn {
  steer: number;
  drive: number;
  trailer_axle: number;
  gross: number;
  reweigh_reference?: string | null;
}

export interface FreshSoloTicketIn {
  kind: 'fresh';
  steer: number;
  drive: number;
  gross: number;
  reweigh_reference?: string | null;
  time_gap_hours?: number | null;
}

export interface ReusedSoloTicketIn {
  kind: 'reused';
  from_timestamp: string;
  gross: number;
  adjusted: boolean;
}

export type SoloTicketIn = FreshSoloTicketIn | ReusedSoloTicketIn;

export interface WeighEventCreateRequest {
  truck_id: number;
  trailer_id: number;
  combined: CombinedTicketIn;
  solo?: SoloTicketIn | null;
  confirm_solo_link?: boolean;
}

export interface WeighEventOut {
  id: number;
  timestamp: string;
  truck_nickname: string;
  trailer_nickname: string;
  overall_status: Status;
  checks: CheckOut[];
  time_gap_hours: number | null;
  time_gap_exceeds_threshold: boolean | null;
  disclaimer: string;
}
