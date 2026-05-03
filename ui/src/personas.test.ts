import { describe, it, expect } from 'vitest';
import { PERSONAS } from './personas';
import { CUSTOMER_ID_PATTERN } from './lib/validate';

// Shape assertions mirroring tests/test_simulate_savings.py:50-56 style —
// keeps the persona constant locked to the 3 Phase 1 seed customers and
// guards against accidental regex drift between personas.ts and validate.ts.
describe('PERSONAS', () => {
  it('has exactly 4 entries (3 recommendation + 1 hardship persona)', () => {
    expect(PERSONAS).toHaveLength(4);
  });

  it('all IDs satisfy CUSTOMER_ID_PATTERN', () => {
    for (const p of PERSONAS) {
      expect(CUSTOMER_ID_PATTERN.test(p.id)).toBe(true);
    }
  });

  it('IDs match the seeded customers in order', () => {
    expect(PERSONAS.map((p) => p.id)).toEqual(['CUST-001', 'CUST-002', 'CUST-003', 'CUST-006']);
  });

  it('every persona has a non-empty label', () => {
    for (const p of PERSONAS) {
      expect(p.label.length).toBeGreaterThan(0);
    }
  });
});
