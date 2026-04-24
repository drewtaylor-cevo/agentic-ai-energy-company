// Must match api_lambda/handler.py:27 and lambda/handler.py:39 exactly.
// Defense-in-depth: the API has the identical regex; this client gate just
// prevents a wasted round-trip for obviously-malformed IDs.
export const CUSTOMER_ID_PATTERN = /^CUST-\d{3,6}$/;

// Matches CUST followed by 3-6 digits with no dash — the common typing shortcut
// we auto-normalize per D-10.
const DASHLESS_PATTERN = /^CUST(\d{3,6})$/;

/**
 * Normalize a customer ID input per D-10:
 *   1. Trim whitespace
 *   2. Uppercase (accept lowercase `cust-001`)
 *   3. Auto-insert the dash if the operator typed `CUST001234` (no dash)
 *
 * The returned value is NOT guaranteed to match `CUSTOMER_ID_PATTERN` — callers
 * must test it against the pattern before submitting to the API.
 */
export function normalizeCustomerId(raw: string): string {
  const trimmed = raw.trim().toUpperCase();
  const dashless = DASHLESS_PATTERN.exec(trimmed);
  if (dashless) {
    return `CUST-${dashless[1]}`;
  }
  return trimmed;
}
