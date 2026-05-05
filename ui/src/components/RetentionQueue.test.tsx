// Retention Queue + CohortCard component tests.
// Validates: Requirements 8.1, 8.3, 8.4, 8.5, 8.7 (narrative=off still shows queue).
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import type { RetentionQueueResponse } from '@/lib/types';

const mockQueueData: RetentionQueueResponse = {
  customers_at_risk: 3,
  queue: [
    {
      customer_id: 'CUST-003',
      risk_score: 82,
      risk_summary: 'Bill shock: +$45 over baseline',
      bill_shock_detected: true,
      usage_trend: 'increasing',
      hardship_flag: false,
    },
    {
      customer_id: 'CUST-002',
      risk_score: 55,
      risk_summary: 'Usage trending up, no shock detected',
      bill_shock_detected: false,
      usage_trend: 'increasing',
      hardship_flag: false,
    },
    {
      customer_id: 'CUST-001',
      risk_score: 30,
      risk_summary: 'Moderate usage increase',
      bill_shock_detected: false,
      usage_trend: 'stable',
      hardship_flag: false,
    },
    {
      customer_id: 'CUST-006',
      risk_score: 0,
      risk_summary: 'Hardship — routed to specialist',
      bill_shock_detected: false,
      usage_trend: 'stable',
      hardship_flag: true,
    },
  ],
};

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.resetModules();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('RetentionQueue', () => {
  it('shows loading state initially', async () => {
    // Never-resolving fetch to keep loading state
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));

    const { RetentionQueue } = await import('./RetentionQueue');
    render(<RetentionQueue onInvestigate={vi.fn()} />);

    expect(screen.getByRole('status', { name: /loading retention queue/i })).toBeInTheDocument();
    expect(screen.getByText(/Loading retention queue/)).toBeInTheDocument();
  });

  it('renders "N customers at risk today" header with correct count of non-zero scores', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockQueueData),
      }),
    ));

    const { RetentionQueue } = await import('./RetentionQueue');
    render(<RetentionQueue onInvestigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('3 customers at risk today')).toBeInTheDocument();
    });
  });

  it('renders a CohortCard for each customer in the queue', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockQueueData),
      }),
    ));

    const { RetentionQueue } = await import('./RetentionQueue');
    render(<RetentionQueue onInvestigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('CUST-003')).toBeInTheDocument();
    });

    expect(screen.getByText('CUST-002')).toBeInTheDocument();
    expect(screen.getByText('CUST-001')).toBeInTheDocument();
    expect(screen.getByText('CUST-006')).toBeInTheDocument();
    expect(screen.getByText('Bill shock: +$45 over baseline')).toBeInTheDocument();
  });

  it('falls back gracefully on fetch error (shows EmptyState-like message)', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 502,
        json: () => Promise.resolve({ error: 'Upstream service error' }),
      }),
    ));

    const { RetentionQueue } = await import('./RetentionQueue');
    render(<RetentionQueue onInvestigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('No customer selected')).toBeInTheDocument();
    });
  });

  it('falls back gracefully on network error', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('Network error'))));

    const { RetentionQueue } = await import('./RetentionQueue');
    render(<RetentionQueue onInvestigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('No customer selected')).toBeInTheDocument();
    });
  });

  it('fetches from VITE_API_URL/retention-queue', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockQueueData),
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { RetentionQueue } = await import('./RetentionQueue');
    render(<RetentionQueue onInvestigate={vi.fn()} />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/retention-queue',
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      );
    });
  });

  it('displays singular "customer" when only 1 at risk', async () => {
    const singleRisk: RetentionQueueResponse = {
      customers_at_risk: 1,
      queue: [
        {
          customer_id: 'CUST-003',
          risk_score: 82,
          risk_summary: 'Bill shock: +$45 over baseline',
          bill_shock_detected: true,
          usage_trend: 'increasing',
          hardship_flag: false,
        },
      ],
    };

    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(singleRisk),
      }),
    ));

    const { RetentionQueue } = await import('./RetentionQueue');
    render(<RetentionQueue onInvestigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('1 customer at risk today')).toBeInTheDocument();
    });
  });
});

describe('CohortCard', () => {
  it('displays customer_id, risk_summary, and risk_score', async () => {
    const { CohortCard } = await import('./CohortCard');
    render(
      <CohortCard
        signal={mockQueueData.queue[0]}
        onInvestigate={vi.fn()}
      />,
    );

    expect(screen.getByText('CUST-003')).toBeInTheDocument();
    expect(screen.getByText('Bill shock: +$45 over baseline')).toBeInTheDocument();
    expect(screen.getByText('82')).toBeInTheDocument();
  });

  it('calls onInvestigate with customer_id on click', async () => {
    const onInvestigate = vi.fn();
    const { CohortCard } = await import('./CohortCard');
    render(
      <CohortCard
        signal={mockQueueData.queue[0]}
        onInvestigate={onInvestigate}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /investigate cust-003/i }));
    expect(onInvestigate).toHaveBeenCalledWith('CUST-003');
  });

  it('applies red border for high risk scores (≥70)', async () => {
    const { CohortCard } = await import('./CohortCard');
    const { container } = render(
      <CohortCard
        signal={{ ...mockQueueData.queue[0], risk_score: 82 }}
        onInvestigate={vi.fn()}
      />,
    );

    const button = container.querySelector('button');
    expect(button).toHaveClass('border-l-red-500');
  });

  it('applies amber border for medium risk scores (40-69)', async () => {
    const { CohortCard } = await import('./CohortCard');
    const { container } = render(
      <CohortCard
        signal={{ ...mockQueueData.queue[1], risk_score: 55 }}
        onInvestigate={vi.fn()}
      />,
    );

    const button = container.querySelector('button');
    expect(button).toHaveClass('border-l-amber-500');
  });

  it('applies yellow border for low risk scores (1-39)', async () => {
    const { CohortCard } = await import('./CohortCard');
    const { container } = render(
      <CohortCard
        signal={{ ...mockQueueData.queue[2], risk_score: 30 }}
        onInvestigate={vi.fn()}
      />,
    );

    const button = container.querySelector('button');
    expect(button).toHaveClass('border-l-yellow-500');
  });
});

describe('RetentionQueue — ?narrative=off still displays (Req 8.7)', () => {
  it('renders retention queue when ?narrative=off is active', async () => {
    vi.stubGlobal('location', { search: '?narrative=off' } as Location);
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockQueueData),
      }),
    ));

    vi.resetModules();
    const { RetentionQueue } = await import('./RetentionQueue');
    render(<RetentionQueue onInvestigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('3 customers at risk today')).toBeInTheDocument();
    });

    // Verify all cards are still visible
    expect(screen.getByText('CUST-003')).toBeInTheDocument();
    expect(screen.getByText('CUST-002')).toBeInTheDocument();
  });
});
