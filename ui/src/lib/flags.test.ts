import { describe, it, expect, beforeEach, vi } from 'vitest';

// Exercises ui/src/lib/flags.ts::NARRATIVE_ENABLED. The const is evaluated
// once at module load from window.location.search, so each case must:
//   1. Stub window.location BEFORE the import.
//   2. vi.resetModules() to drop the cached evaluation.
//   3. Dynamic `await import('./flags')` to force re-evaluation.
// D-13 is asserted explicitly via the case-sensitive `?narrative=OFF` probe.

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('NARRATIVE_ENABLED (flags.ts)', () => {
  it('is true when the query param is absent', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { NARRATIVE_ENABLED } = await import('./flags');
    expect(NARRATIVE_ENABLED).toBe(true);
  });

  it('is false when ?narrative=off is present (exact-match token)', async () => {
    vi.stubGlobal('location', { search: '?narrative=off' } as Location);
    vi.resetModules();
    const { NARRATIVE_ENABLED } = await import('./flags');
    expect(NARRATIVE_ENABLED).toBe(false);
  });

  it.each([
    ['?narrative=on',    true],
    ['?narrative=0',     true],
    ['?narrative=false', true],
    ['?narrative=OFF',   true],
    ['?other=off',       true],
  ])('is %s for non-exact match (D-13 case-sensitive)', async (search, expected) => {
    vi.stubGlobal('location', { search } as Location);
    vi.resetModules();
    const { NARRATIVE_ENABLED } = await import('./flags');
    expect(NARRATIVE_ENABLED).toBe(expected);
  });
});
