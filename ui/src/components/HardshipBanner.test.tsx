// Phase 14 AGENT-02: HardshipBanner component tests.
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { HardshipBanner } from './HardshipBanner';
import type { HardshipResponse } from '@/lib/types';

const MOCK_HARDSHIP: HardshipResponse = {
  kind: 'hardship',
  customer_id: 'CUST-006',
  reason: 'This customer account is flagged for dedicated support from our specialist team.',
  routing_target: 'hardship_team',
  call_script: 'Let me connect you with our specialist support team who can best help with your account.',
};

describe('HardshipBanner', () => {
  it('renders the reason text', () => {
    render(<HardshipBanner data={MOCK_HARDSHIP} />);
    expect(screen.getByText(MOCK_HARDSHIP.reason)).toBeInTheDocument();
  });

  it('renders the call script in a blockquote', () => {
    render(<HardshipBanner data={MOCK_HARDSHIP} />);
    const blockquote = screen.getByText(MOCK_HARDSHIP.call_script);
    expect(blockquote.closest('blockquote')).toBeInTheDocument();
  });

  it('renders the routing target', () => {
    render(<HardshipBanner data={MOCK_HARDSHIP} />);
    expect(screen.getByText(/hardship_team/)).toBeInTheDocument();
  });

  it('renders the Specialist Support Required title', () => {
    render(<HardshipBanner data={MOCK_HARDSHIP} />);
    expect(screen.getByText('Specialist Support Required')).toBeInTheDocument();
  });

  it('has an accessible section landmark', () => {
    render(<HardshipBanner data={MOCK_HARDSHIP} />);
    expect(screen.getByRole('region', { name: /hardship support routing/i })).toBeInTheDocument();
  });

  it('does not render green or cheapest content', () => {
    const { container } = render(<HardshipBanner data={MOCK_HARDSHIP} />);
    const html = container.innerHTML;
    expect(html).not.toContain('EcoFlex');
    expect(html).not.toContain('Value 12');
    expect(html).not.toContain('saving_monthly');
  });
});

describe('HardshipBanner with ?narrative=off', () => {
  it('renders null when NARRATIVE_ENABLED is false', async () => {
    vi.stubGlobal('location', { search: '?narrative=off' } as Location);
    vi.resetModules();
    const { HardshipBanner: HardshipBannerOff } = await import('./HardshipBanner');
    const { container } = render(<HardshipBannerOff data={MOCK_HARDSHIP} />);
    expect(container.firstChild).toBeNull();
  });
});
