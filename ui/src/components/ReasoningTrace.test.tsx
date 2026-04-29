// Phase 13 D-30: six vitest cases for ReasoningTrace.
//
// The kill-switch cases use the LOAD-BEARING
//   vi.stubGlobal('location', { search: '?narrative=off' })
//   vi.resetModules()
//   await import('./ReasoningTrace')
// idiom because flags.ts evaluates URLSearchParams at module load. A top-level
// static import of ReasoningTrace would pin NARRATIVE_ENABLED=true forever in
// the test runner. DO NOT refactor to top-level imports.
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import type { ReasoningTraceEntry } from '@/lib/types';

function traceFixture(n: number = 3): ReasoningTraceEntry[] {
  const tools = ['get_hardship_flag', 'detect_bill_shock', 'simulate_savings'];
  const summaries = [
    'hardship_flag=False',
    'Bill shock detected: +$47.00 2025-10 vs 11-month avg ($135.00 vs $88.00)',
    'Green $14.00/mo; Cheapest $25.67/mo',
  ];
  return Array.from({ length: n }, (_, i) => ({
    tool: tools[i] ?? 'unknown',
    summary: summaries[i] ?? 'summary',
  }));
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('ReasoningTrace — flag ON (default), rendering states', () => {
  it('renders null when trace is empty', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { ReasoningTrace } = await import('./ReasoningTrace');
    const { container } = render(<ReasoningTrace trace={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders collapsed state with tool names and chevron when trace has 3 entries', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { ReasoningTrace } = await import('./ReasoningTrace');
    render(<ReasoningTrace trace={traceFixture(3)} />);

    // Collapsed label contains chevron + step count + tool names (NAMES ONLY, no numbers).
    const label = screen.getByRole('button', { expanded: false });
    expect(label).toHaveTextContent(/3 steps:/);
    expect(label).toHaveTextContent(/get_hardship_flag/);
    expect(label).toHaveTextContent(/detect_bill_shock/);
    expect(label).toHaveTextContent(/simulate_savings/);

    // UI-01 guard: collapsed copy does NOT contain $ or digits-from-summary.
    expect(label.textContent).not.toMatch(/\$/);
    expect(label.textContent).not.toMatch(/2025-10/);
  });

  it('click on disclosure row expands to show numbered summary list', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { ReasoningTrace } = await import('./ReasoningTrace');
    render(<ReasoningTrace trace={traceFixture(3)} />);

    const disclosure = screen.getByRole('button', { expanded: false });
    fireEvent.click(disclosure);

    // After click: button is expanded, summaries visible.
    expect(screen.getByRole('button', { expanded: true })).toBeInTheDocument();
    expect(screen.getByText(/hardship_flag=False/)).toBeInTheDocument();
    expect(screen.getByText(/Bill shock detected:/)).toBeInTheDocument();
    expect(screen.getByText(/Green \$14.00\/mo/)).toBeInTheDocument();
  });

  it('renders collapsed state with 1 entry correctly (edge case)', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { ReasoningTrace } = await import('./ReasoningTrace');
    render(<ReasoningTrace trace={traceFixture(1)} />);

    const label = screen.getByRole('button', { expanded: false });
    expect(label).toHaveTextContent(/1 steps:/);
    expect(label).toHaveTextContent(/get_hardship_flag/);
  });
});

describe('ReasoningTrace — ?narrative=off kill switch (LD-7, D-27)', () => {
  it('renders null when flag is off and trace is non-empty', async () => {
    vi.stubGlobal('location', { search: '?narrative=off' } as Location);
    vi.resetModules();
    const { ReasoningTrace } = await import('./ReasoningTrace');
    const { container } = render(<ReasoningTrace trace={traceFixture(3)} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders null when flag is off and trace is empty', async () => {
    vi.stubGlobal('location', { search: '?narrative=off' } as Location);
    vi.resetModules();
    const { ReasoningTrace } = await import('./ReasoningTrace');
    const { container } = render(<ReasoningTrace trace={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
