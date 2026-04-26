// Phase 8 D-06, D-07, D-10 — component tests for the extended
// RecommendationSkeletons:
//   * default render adds narrative placeholder (`.space-y-2` group, 2 lines:
//     h-4 w-full + h-4 w-4/5) and call_script placeholder shell
//     (`border-l-4 border-l-muted pl-4 py-2`, 3 lines: h-5 w-full + h-5 w-5/6
//     + h-5 w-3/5) in each of the 2 cards (D-06);
//   * `?narrative=off` suppresses both placeholder groups while preserving
//     the v1.0 base skeleton shape (D-10 non-negotiable);
//   * no sub-component extraction — skeleton stays single-file per D-07
//     (enforced at the source-level via the acceptance-criteria grep in the
//     plan; not asserted in this test file).
// Uses the same `vi.stubGlobal('location', …)` + `vi.resetModules()` +
// dynamic import idiom as flags.test.ts / RecommendationCard.test.tsx so
// flags.ts re-evaluates per test.
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render } from '@testing-library/react';

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('RecommendationSkeletons — default render (flag on)', () => {
  it('renders narrative placeholder (2-line .space-y-2 group)', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { RecommendationSkeletons } = await import('./RecommendationSkeletons');
    const { container } = render(<RecommendationSkeletons />);
    // Two cards, each with a `.space-y-2` narrative group.
    const narrativeGroups = container.querySelectorAll('.space-y-2');
    expect(narrativeGroups.length).toBeGreaterThanOrEqual(2);
  });

  it('renders call_script placeholder shell with border-l-muted', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { RecommendationSkeletons } = await import('./RecommendationSkeletons');
    const { container } = render(<RecommendationSkeletons />);
    const shells = container.querySelectorAll('.border-l-muted');
    expect(shells.length).toBeGreaterThanOrEqual(2);
    // Each shell has border-l-4 as well.
    shells.forEach((shell) => {
      expect(shell.classList.contains('border-l-4')).toBe(true);
    });
  });

  it('narrative placeholder contains h-4 w-full + h-4 w-4/5 skeletons', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { RecommendationSkeletons } = await import('./RecommendationSkeletons');
    const { container } = render(<RecommendationSkeletons />);
    // First card's narrative placeholder group
    const firstNarrativeGroup = container.querySelector('.space-y-2');
    expect(firstNarrativeGroup).not.toBeNull();
    const lineOne = firstNarrativeGroup?.querySelector('.h-4.w-full');
    const lineTwo = firstNarrativeGroup?.querySelector('.h-4.w-4\\/5');
    expect(lineOne).not.toBeNull();
    expect(lineTwo).not.toBeNull();
  });

  it('call_script placeholder shell contains h-5 w-full + h-5 w-5/6 + h-5 w-3/5 skeletons', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { RecommendationSkeletons } = await import('./RecommendationSkeletons');
    const { container } = render(<RecommendationSkeletons />);
    const firstShell = container.querySelector('.border-l-muted');
    expect(firstShell).not.toBeNull();
    expect(firstShell?.querySelector('.h-5.w-full')).not.toBeNull();
    expect(firstShell?.querySelector('.h-5.w-5\\/6')).not.toBeNull();
    expect(firstShell?.querySelector('.h-5.w-3\\/5')).not.toBeNull();
  });
});

describe('RecommendationSkeletons — ?narrative=off suppresses placeholders (D-10 non-negotiable)', () => {
  it('does NOT render the narrative placeholder group', async () => {
    vi.stubGlobal('location', { search: '?narrative=off' } as Location);
    vi.resetModules();
    const { RecommendationSkeletons } = await import('./RecommendationSkeletons');
    const { container } = render(<RecommendationSkeletons />);
    expect(container.querySelector('.space-y-2')).toBeNull();
  });

  it('does NOT render the call_script placeholder shell', async () => {
    vi.stubGlobal('location', { search: '?narrative=off' } as Location);
    vi.resetModules();
    const { RecommendationSkeletons } = await import('./RecommendationSkeletons');
    const { container } = render(<RecommendationSkeletons />);
    expect(container.querySelector('.border-l-muted')).toBeNull();
  });

  it('preserves the v1.0 base skeleton shape (CardHeader + savings grid + methodology bar)', async () => {
    vi.stubGlobal('location', { search: '?narrative=off' } as Location);
    vi.resetModules();
    const { RecommendationSkeletons } = await import('./RecommendationSkeletons');
    const { container } = render(<RecommendationSkeletons />);
    // Outer grid with two cards unchanged.
    expect(container.querySelector('.grid.grid-cols-1.md\\:grid-cols-2.gap-8')).not.toBeNull();
    // Each Card has `border-t-muted` top border from the v1.0 shape.
    expect(container.querySelectorAll('.border-t-muted').length).toBeGreaterThanOrEqual(2);
  });
});
