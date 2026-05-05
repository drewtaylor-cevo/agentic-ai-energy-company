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


describe('ReasoningTrace — streaming progressive rendering (Requirements 5.2, 5.6)', () => {
  it('renders skeleton-only state when isStreaming=true and trace is empty', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { ReasoningTrace } = await import('./ReasoningTrace');
    render(<ReasoningTrace trace={[]} isStreaming={true} />);

    // Should render the streaming skeleton (not null)
    const skeleton = screen.getByTestId('trace-streaming-skeleton');
    expect(skeleton).toBeInTheDocument();
  });

  it('renders trace entries alongside skeleton when isStreaming=true and trace has entries', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { ReasoningTrace } = await import('./ReasoningTrace');
    const partialTrace = traceFixture(2);
    render(<ReasoningTrace trace={partialTrace} isStreaming={true} />);

    // Should show the collapsed label with "2+" step count (streaming indicator)
    const label = screen.getByRole('button', { expanded: false });
    expect(label).toHaveTextContent(/2\+ steps:/);
    expect(label).toHaveTextContent(/get_hardship_flag/);
    expect(label).toHaveTextContent(/detect_bill_shock/);
  });

  it('shows streaming indicator when collapsed and isStreaming=true', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { ReasoningTrace } = await import('./ReasoningTrace');
    render(<ReasoningTrace trace={traceFixture(2)} isStreaming={true} />);

    // Collapsed streaming indicator should be visible
    const indicator = screen.getByTestId('trace-streaming-indicator');
    expect(indicator).toBeInTheDocument();
    expect(screen.getByText(/Analysing…/)).toBeInTheDocument();
  });

  it('shows skeleton step in expanded list when isStreaming=true', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { ReasoningTrace } = await import('./ReasoningTrace');
    render(<ReasoningTrace trace={traceFixture(2)} isStreaming={true} />);

    // Expand the disclosure
    const disclosure = screen.getByRole('button', { expanded: false });
    fireEvent.click(disclosure);

    // Should show the existing entries plus a skeleton for the next step
    expect(screen.getByText(/hardship_flag=False/)).toBeInTheDocument();
    expect(screen.getByTestId('trace-step-skeleton')).toBeInTheDocument();
  });

  it('does NOT show skeleton or streaming indicator when isStreaming=false', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { ReasoningTrace } = await import('./ReasoningTrace');
    render(<ReasoningTrace trace={traceFixture(3)} isStreaming={false} />);

    // No streaming indicators
    expect(screen.queryByTestId('trace-streaming-skeleton')).not.toBeInTheDocument();
    expect(screen.queryByTestId('trace-streaming-indicator')).not.toBeInTheDocument();

    // Step count should NOT have "+" suffix
    const label = screen.getByRole('button', { expanded: false });
    expect(label).toHaveTextContent(/3 steps:/);
    expect(label.textContent).not.toMatch(/3\+ steps:/);
  });

  it('renders progressive entries as trace array grows (simulates incremental append)', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { ReasoningTrace } = await import('./ReasoningTrace');

    // Start with 1 entry
    const { rerender } = render(<ReasoningTrace trace={traceFixture(1)} isStreaming={true} />);
    let label = screen.getByRole('button', { expanded: false });
    expect(label).toHaveTextContent(/1\+ steps:/);

    // Grow to 2 entries (simulates new trace_step arriving)
    rerender(<ReasoningTrace trace={traceFixture(2)} isStreaming={true} />);
    label = screen.getByRole('button', { expanded: false });
    expect(label).toHaveTextContent(/2\+ steps:/);

    // Streaming completes — final render with isStreaming=false
    rerender(<ReasoningTrace trace={traceFixture(3)} isStreaming={false} />);
    label = screen.getByRole('button', { expanded: false });
    expect(label).toHaveTextContent(/3 steps:/);
    expect(screen.queryByTestId('trace-streaming-indicator')).not.toBeInTheDocument();
  });
});
