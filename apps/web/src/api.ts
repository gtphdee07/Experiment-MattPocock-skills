import type {
  Account,
  EvaluateResponse,
  ReusableSoloTicket,
  TrailerProfile,
  TrailerProfileIn,
  TrailerProfileUpdate,
  TruckProfile,
  TruckProfileIn,
  TruckProfileUpdate,
  WeighEventCreateRequest,
  WeighEventOut,
} from './types';

const API_BASE = import.meta.env?.VITE_API_BASE ?? 'http://localhost:8000';

/** A non-2xx response from the API, carrying the parsed body (if any) so
 * callers can read fastapi-users'/FastAPI's `detail` shape without
 * re-parsing. `status` lets callers branch on 404 ("not found", Story 30),
 * 409 (Solo Ticket link confirmation, Story 23), etc. */
export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `Request failed with status ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;

/** Wires a single callback that fires whenever any authenticated request
 * gets a 401 back - "not signed in", uniformly, rather than every page
 * handling it individually (issue #30 Implementation Decisions). The
 * AuthContext provider is the only intended caller in the real app; tests
 * can call it directly to assert the behavior without a router. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const hasBody = init?.body !== undefined;
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    ...init,
    headers: {
      ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers ?? {}),
    },
  });

  if (res.status === 401) {
    unauthorizedHandler?.();
    throw new ApiError(401, null, 'Not signed in');
  }

  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      // No JSON body - leave detail null.
    }
    const parsedDetail =
      detail && typeof detail === 'object' && 'detail' in detail
        ? (detail as { detail: unknown }).detail
        : detail;
    throw new ApiError(res.status, parsedDetail, `Request failed with status ${res.status}`);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

// --- Free calculator (unauthenticated, unchanged - talks to the existing
// stateless reference API this app has always used, not apps/backend) ------

export async function evaluate(payload: unknown): Promise<EvaluateResponse> {
  const res = await fetch(`${API_BASE}/api/evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Evaluate failed: ${res.status}`);
  return res.json();
}

// --- Auth (apps/backend, issue #18) -----------------------------------------

export async function register(email: string, password: string): Promise<Account> {
  return request<Account>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function login(email: string, password: string): Promise<void> {
  // fastapi-users' cookie login endpoint takes form-encoded data, field
  // names `username`/`password` (OAuth2 password-flow convention), not JSON.
  const body = new URLSearchParams();
  body.set('username', email);
  body.set('password', password);
  await request<void>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });
}

export async function logout(): Promise<void> {
  await request<void>('/auth/logout', { method: 'POST' });
}

export async function getMe(): Promise<Account> {
  return request<Account>('/users/me');
}

// --- Garage: Truck Profiles (apps/backend, issue #19) -----------------------

export async function listTrucks(): Promise<TruckProfile[]> {
  return request<TruckProfile[]>('/trucks');
}

export async function createTruck(payload: TruckProfileIn): Promise<TruckProfile> {
  return request<TruckProfile>('/trucks', { method: 'POST', body: JSON.stringify(payload) });
}

export async function updateTruck(
  id: number,
  payload: TruckProfileUpdate
): Promise<TruckProfile> {
  return request<TruckProfile>(`/trucks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteTruck(id: number): Promise<void> {
  await request<void>(`/trucks/${id}`, { method: 'DELETE' });
}

// --- Garage: Trailer Profiles (apps/backend, issue #19) ---------------------

export async function listTrailers(): Promise<TrailerProfile[]> {
  return request<TrailerProfile[]>('/trailers');
}

export async function createTrailer(payload: TrailerProfileIn): Promise<TrailerProfile> {
  return request<TrailerProfile>('/trailers', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateTrailer(
  id: number,
  payload: TrailerProfileUpdate
): Promise<TrailerProfile> {
  return request<TrailerProfile>(`/trailers/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteTrailer(id: number): Promise<void> {
  await request<void>(`/trailers/${id}`, { method: 'DELETE' });
}

// --- Weigh Events (apps/backend, issue #21) ---------------------------------

export async function getReusableSoloTicket(
  truckId: number
): Promise<ReusableSoloTicket | null> {
  return request<ReusableSoloTicket | null>(`/trucks/${truckId}/reusable-solo-ticket`);
}

export async function createWeighEvent(
  payload: WeighEventCreateRequest
): Promise<WeighEventOut> {
  return request<WeighEventOut>('/weigh-events', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function listWeighEvents(
  limit: number,
  offset: number
): Promise<WeighEventOut[]> {
  return request<WeighEventOut[]>(`/weigh-events?limit=${limit}&offset=${offset}`);
}
