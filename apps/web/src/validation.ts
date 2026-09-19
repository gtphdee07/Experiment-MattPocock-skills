/** Parses a form's raw string input into a number, or `null` when it's
 * blank/not a finite number - shared by every numeric field across the
 * Garage and Weigh Event forms (extracted from the calculator's own
 * inline `num()` helper in the original `App.tsx`). */
export function parseNumber(raw: string): number | null {
  if (raw.trim() === '') return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

/** Story 15: "Invalid input (zero/negative rating) shows inline validation
 * error before submit." Returns an error message, or `null` when valid. */
export function validatePositive(raw: string, label: string, required = true): string | null {
  if (raw.trim() === '') {
    return required ? `${label} is required.` : null;
  }
  const value = parseNumber(raw);
  if (value === null) return `${label} must be a number.`;
  if (value <= 0) return `${label} must be greater than zero.`;
  return null;
}

/** Same as `validatePositive`, but for a value that must additionally be a
 * whole number (Axle Count). */
export function validatePositiveInt(raw: string, label: string, required = true): string | null {
  const base = validatePositive(raw, label, required);
  if (base) return base;
  if (raw.trim() === '') return null;
  const value = Number(raw);
  if (!Number.isInteger(value)) return `${label} must be a whole number.`;
  return null;
}
