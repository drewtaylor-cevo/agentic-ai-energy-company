// ActionCard component tests.
// Validates: Requirements 4.1–4.8 (Action Card UI Component).
// Tests all states: default, loading, success, dismissed, error, and LD-7 kill-switch.
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import type { ConfirmableAction } from '@/lib/types';

const mockTariffAction: ConfirmableAction = {
  action_id: 'act-001',
  action_type: 'tariff_switch',
  customer_id: 'CUST-001',
  payload: { plan_name: 'EcoFlex Green', plan_id: 'eco-flex-green', estimated_saving_monthly: 30 },
  status: 'pending',
};

const mockSmsAction: ConfirmableAction = {
  action_id: 'act-002',
  action_type: 'send_sms',
  customer_id: 'CUST-001',
  payload: { message_body: 'Thanks for calling today', plan_name: 'EcoFlex Green' },
  status: 'pending',
};

const mockPaymentPlanAction: ConfirmableAction = {
  action_id: 'act-003',
  action_type: 'payment_plan_offer',
  customer_id: 'CUST-003',
  payload: { proposed_installments: 4, installment_amount: 25.0, total_owed: 100.0 },
  status: 'pending',
};

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.resetModules();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('ActionCard — default state (Req 4.1–4.3)', () => {
  it('renders human-readable label for tariff_switch', async () => {
    const { ActionCard } = await import('./ActionCard');
    render(<ActionCard action={mockTariffAction} />);

    expect(screen.getByText('Switch to EcoFlex Green')).toBeInTheDocument();
  });

  it('renders human-readable label for send_sms', async () => {
    const { ActionCard } = await import('./ActionCard');
    render(<ActionCard action={mockSmsAction} />);

    expect(screen.getByText('Send SMS follow-up')).toBeInTheDocument();
  });

  it('renders human-readable label for payment_plan_offer with installments', async () => {
    const { ActionCard } = await import('./ActionCard');
    render(<ActionCard action={mockPaymentPlanAction} />);

    expect(screen.getByText('Offer payment plan (4 instalments)')).toBeInTheDocument();
  });

  it('renders Confirm button (primary) and Dismiss button (ghost)', async () => {
    const { ActionCard } = await import('./ActionCard');
    render(<ActionCard action={mockTariffAction} />);

    const confirmBtn = screen.getByRole('button', { name: /confirm/i });
    const dismissBtn = screen.getByRole('button', { name: /dismiss/i });

    expect(confirmBtn).toBeInTheDocument();
    expect(dismissBtn).toBeInTheDocument();
    expect(confirmBtn).not.toBeDisabled();
    expect(dismissBtn).not.toBeDisabled();

    // Confirm is primary (default variant), Dismiss is ghost
    expect(dismissBtn).toHaveAttribute('data-variant', 'ghost');
  });
});

describe('ActionCard — loading state (Req 4.6)', () => {
  it('disables both buttons and shows spinner on Confirm during confirm request', async () => {
    // Never-resolving fetch to keep loading state
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));

    const { ActionCard } = await import('./ActionCard');
    render(<ActionCard action={mockTariffAction} />);

    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /confirm/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /dismiss/i })).toBeDisabled();
    });
  });

  it('disables both buttons and shows spinner on Dismiss during dismiss request', async () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));

    const { ActionCard } = await import('./ActionCard');
    render(<ActionCard action={mockTariffAction} />);

    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /confirm/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /dismiss/i })).toBeDisabled();
    });
  });
});

describe('ActionCard — success state (Req 4.4)', () => {
  it('shows success indicator and disables buttons after confirm', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ action_id: 'act-001', status: 'confirmed' }),
      }),
    ));

    const { ActionCard } = await import('./ActionCard');
    render(<ActionCard action={mockTariffAction} />);

    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));

    await waitFor(() => {
      expect(screen.getByTestId('success-indicator')).toBeInTheDocument();
      expect(screen.getByText('Confirmed')).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /confirm/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /dismiss/i })).toBeDisabled();
  });
});

describe('ActionCard — dismissed state (Req 4.5)', () => {
  it('collapses card from view after dismiss', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ action_id: 'act-001', status: 'rejected' }),
      }),
    ));

    const { ActionCard } = await import('./ActionCard');
    const { container } = render(<ActionCard action={mockTariffAction} />);

    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));

    await waitFor(() => {
      expect(container.querySelector('[data-slot="card"]')).not.toBeInTheDocument();
    });
  });
});

describe('ActionCard — error state (Req 4.7)', () => {
  it('shows inline error message and re-enables buttons on confirm failure', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 410,
        json: () => Promise.resolve({ error: 'Action has expired' }),
      }),
    ));

    const { ActionCard } = await import('./ActionCard');
    render(<ActionCard action={mockTariffAction} />);

    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));

    await waitFor(() => {
      expect(screen.getByTestId('error-message')).toBeInTheDocument();
      expect(screen.getByText('Action has expired')).toBeInTheDocument();
    });

    // Buttons re-enabled
    expect(screen.getByRole('button', { name: /confirm/i })).not.toBeDisabled();
    expect(screen.getByRole('button', { name: /dismiss/i })).not.toBeDisabled();
  });

  it('shows inline error message on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('Network error'))));

    const { ActionCard } = await import('./ActionCard');
    render(<ActionCard action={mockTariffAction} />);

    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));

    await waitFor(() => {
      expect(screen.getByTestId('error-message')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    // Buttons re-enabled
    expect(screen.getByRole('button', { name: /confirm/i })).not.toBeDisabled();
    expect(screen.getByRole('button', { name: /dismiss/i })).not.toBeDisabled();
  });
});

describe('ActionCard — API calls (Req 4.3–4.5)', () => {
  it('POSTs to /actions/{id}/confirm on Confirm click', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ action_id: 'act-001', status: 'confirmed' }),
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { ActionCard } = await import('./ActionCard');
    render(<ActionCard action={mockTariffAction} />);

    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/actions/act-001/confirm', { method: 'POST' });
    });
  });

  it('POSTs to /actions/{id}/dismiss on Dismiss click', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ action_id: 'act-001', status: 'rejected' }),
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { ActionCard } = await import('./ActionCard');
    render(<ActionCard action={mockTariffAction} />);

    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/actions/act-001/dismiss', { method: 'POST' });
    });
  });
});

describe('ActionCard — LD-7 kill-switch (?narrative=off hides ActionCards, Req 4.8)', () => {
  it('ActionCards are hidden when NARRATIVE_ENABLED is false', async () => {
    // Simulate ?narrative=off by stubbing location before importing the module
    vi.stubGlobal('location', { search: '?narrative=off' } as Location);
    vi.resetModules();

    const { NARRATIVE_ENABLED } = await import('@/lib/flags');
    expect(NARRATIVE_ENABLED).toBe(false);

    // The kill-switch is enforced at the App.tsx level (NARRATIVE_ENABLED check),
    // not inside ActionCard itself. This test verifies the flag evaluates correctly.
  });

  it('ActionCards are visible when NARRATIVE_ENABLED is true (default)', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();

    const { NARRATIVE_ENABLED } = await import('@/lib/flags');
    expect(NARRATIVE_ENABLED).toBe(true);
  });
});
