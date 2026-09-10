import type { EvaluateResponse } from './types';

const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? 'http://localhost:8000';

export async function evaluate(payload: unknown): Promise<EvaluateResponse> {
  const res = await fetch(`${API_BASE}/api/evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Evaluate failed: ${res.status}`);
  return res.json();
}
