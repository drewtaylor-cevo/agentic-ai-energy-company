// Phase 8 D-01, D-02, D-03, D-04, D-10, D-12, D-21 — component tests for the
// extended RecommendationCard:
//   * renders usage_narrative (italic, muted, text-sm) BETWEEN savings grid
//     and methodology line (D-01/D-02);
//   * renders call_script as a bordered quote block with a track-accent left
//     border AFTER methodology (D-03);
//   * both narrative + call_script are suppressed when ?narrative=off is in
//     the URL — the v2.0 runtime rollback lever (D-10 non-negotiable);
//   * inline U+275D / U+275E quote marks, no prop plumbing (D-12).
// Uses the `vi.stubGlobal('location', …)` + `vi.resetModules()` + dynamic
// import idiom so flags.ts (module-level single-const init) re-evaluates per
// test. jest-dom matchers come via src/test-setup.ts (`toHaveClass`, etc.).
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { TrackInfo } from '@/lib/types';

const trackFixture = (overrides: Partial<TrackInfo> = {}): TrackInfo => ({
  plan_id: 'ECO',
  plan_name: 'EcoFlex 100',
  saving_monthly: 30.0,
  saving_annual: 360.0,
  usage_narrative: 'Strong cool-season usage with a family-sized load across the year.',
  call_script: 'Ask about EcoFlex — it suits a strong winter-heating profile like yours.',
  ...overrides,
});

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('RecommendationCard — flag ON (default)', () => {
  it('renders narrative and call_script for Green track with emerald-600 left border', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { RecommendationCard } = await import('./RecommendationCard');
    const { container } = render(<RecommendationCard track="green" data={trackFixture()} />);
    expect(screen.getByText(/Strong cool-season usage/)).toBeInTheDocument();
    expect(screen.getByText(/Ask about EcoFlex/)).toBeInTheDocument();
    const quote = container.querySelector('blockquote');
    expect(quote).not.toBeNull();
    expect(quote).toHaveClass('border-l-4');
    expect(quote).toHaveClass('border-l-emerald-600');
    expect(quote).toHaveClass('pl-4');
    expect(quote).toHaveClass('py-2');
    expect(quote).toHaveClass('text-base');
  });

  it('renders Cheapest track with blue-600 left border', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { RecommendationCard } = await import('./RecommendationCard');
    const { container } = render(
      <RecommendationCard
        track="cheapest"
        data={trackFixture({
          plan_id: 'VAL',
          plan_name: 'Value 12',
          saving_monthly: 55.0,
          saving_annual: 660.0,
          usage_narrative: 'Consistently high household consumption with cool-season peaks.',
          call_script: 'Bring up Value Twelve — a budget-first pick for a high-usage home.',
        })}
      />,
    );
    expect(screen.getByText(/Consistently high household consumption/)).toBeInTheDocument();
    const quote = container.querySelector('blockquote');
    expect(quote).not.toBeNull();
    expect(quote).toHaveClass('border-l-blue-600');
  });

  it('orders narrative between savings grid and methodology, call_script after methodology', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { RecommendationCard } = await import('./RecommendationCard');
    const { container } = render(<RecommendationCard track="green" data={trackFixture()} />);
    const text = container.textContent ?? '';
    const savingsIdx = text.indexOf('/mo');
    const narrativeIdx = text.indexOf('Strong cool-season');
    const methodologyIdx = text.indexOf('Based on your 12-month');
    const scriptIdx = text.indexOf('Ask about EcoFlex');
    expect(savingsIdx).toBeGreaterThan(-1);
    expect(narrativeIdx).toBeGreaterThan(-1);
    expect(methodologyIdx).toBeGreaterThan(-1);
    expect(scriptIdx).toBeGreaterThan(-1);
    expect(savingsIdx).toBeLessThan(narrativeIdx);
    expect(narrativeIdx).toBeLessThan(methodologyIdx);
    expect(methodologyIdx).toBeLessThan(scriptIdx);
  });

  it('wraps the call_script with U+275D and U+275E quote marks', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { RecommendationCard } = await import('./RecommendationCard');
    const { container } = render(<RecommendationCard track="green" data={trackFixture()} />);
    const quoteText = container.querySelector('blockquote')?.textContent ?? '';
    expect(quoteText).toContain('❝'); // ❝
    expect(quoteText).toContain('❞'); // ❞
  });

  it('renders narrative as italic + text-muted-foreground text-sm', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { RecommendationCard } = await import('./RecommendationCard');
    const { container } = render(<RecommendationCard track="green" data={trackFixture()} />);
    // Narrative: the single paragraph with italic + text-muted-foreground + text-sm
    const paragraphs = container.querySelectorAll('p');
    const narrativeEl = Array.from(paragraphs).find((p) =>
      p.textContent?.includes('Strong cool-season'),
    );
    expect(narrativeEl).toBeDefined();
    expect(narrativeEl).toHaveClass('italic');
    expect(narrativeEl).toHaveClass('text-muted-foreground');
    expect(narrativeEl).toHaveClass('text-sm');
  });
});

describe('RecommendationCard — ?narrative=off suppresses narrative + call_script (D-10)', () => {
  it('hides narrative and call_script on Green track', async () => {
    vi.stubGlobal('location', { search: '?narrative=off' } as Location);
    vi.resetModules();
    const { RecommendationCard } = await import('./RecommendationCard');
    const { container } = render(<RecommendationCard track="green" data={trackFixture()} />);
    expect(screen.queryByText(/Strong cool-season usage/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Ask about EcoFlex/)).not.toBeInTheDocument();
    expect(container.querySelector('blockquote')).toBeNull();
  });

  it('hides narrative and call_script on Cheapest track', async () => {
    vi.stubGlobal('location', { search: '?narrative=off' } as Location);
    vi.resetModules();
    const { RecommendationCard } = await import('./RecommendationCard');
    const { container } = render(
      <RecommendationCard
        track="cheapest"
        data={trackFixture({
          plan_id: 'VAL',
          plan_name: 'Value 12',
          usage_narrative: 'Consistently high household consumption with cool-season peaks.',
          call_script: 'Bring up Value Twelve — a budget-first pick for a high-usage home.',
        })}
      />,
    );
    expect(screen.queryByText(/Consistently high household consumption/)).not.toBeInTheDocument();
    expect(container.querySelector('blockquote')).toBeNull();
  });
});
