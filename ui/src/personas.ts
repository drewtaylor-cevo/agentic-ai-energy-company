// Mirrors the 3 personas seeded by infrastructure/seed_data/billing_records.py
// (Sarah Chen / Marcus Webb / Elena Vasquez — CUST-001/002/003).
//
// IDs MUST satisfy CUSTOMER_ID_PATTERN from ./lib/validate — asserted in
// personas.test.ts so any drift is caught immediately.
//
// Labels per D-08: "CUST-NNN · <short-profile>" — the middle dot (·, U+00B7)
// gives one-click operator safety with a label that identifies both the ID and
// the usage shape at a glance during a live call.
export interface Persona {
  id: string;
  label: string;
}

export const PERSONAS: readonly Persona[] = [
  { id: 'CUST-001', label: 'CUST-001 · High usage' },
  { id: 'CUST-002', label: 'CUST-002 · Mid usage' },
  { id: 'CUST-003', label: 'CUST-003 · Low usage' },
] as const;
