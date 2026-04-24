import { describe, it, expect } from 'vitest';
import { normalizeCustomerId, CUSTOMER_ID_PATTERN } from './validate';

// Positive normalization cases — each input yields the canonical CUST-NNNNNN
// form that satisfies CUSTOMER_ID_PATTERN. Covers D-10 (trim + uppercase +
// auto-dash) and the operator's "common typing shortcut" scenarios.
describe('normalizeCustomerId', () => {
  it.each([
    ['CUST-001',    'CUST-001'],
    ['cust-001',    'CUST-001'],
    ['  CUST-001 ', 'CUST-001'],
    ['CUST001234',  'CUST-001234'],
    ['cust001',     'CUST-001'],
  ])('normalizes "%s" to "%s" (valid after normalize)', (raw, expected) => {
    const normalized = normalizeCustomerId(raw);
    expect(normalized).toBe(expected);
    expect(CUSTOMER_ID_PATTERN.test(normalized)).toBe(true);
  });
});

// Mirrors the parametrize in tests/test_backend_api_handler.py:70-73 (minus
// `cust-001` which normalizes to a valid ID). These inputs remain invalid
// even after normalization and the UI must surface the 400 copy client-side.
describe('CUSTOMER_ID_PATTERN rejects invalid IDs after normalization', () => {
  it.each(['NOTVALID', 'CUST-1', 'CUST-1234567', ''])(
    '"%s" fails regex after normalization',
    (bad) => {
      expect(CUSTOMER_ID_PATTERN.test(normalizeCustomerId(bad))).toBe(false);
    }
  );
});
