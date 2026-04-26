// Tests for VersionIndicator (UI-07, D-14–D-17). The component reads the
// build-time `__GIT_SHA__` Vite-injected global; under vitest `__GIT_SHA__`
// is NOT substituted automatically, so each test stubs it via vi.stubGlobal
// BEFORE dynamic import (module-reset + dynamic-import pattern from
// useRecommendations.test.ts; D-09 testability hook applied to a global).
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('VersionIndicator', () => {
  it('renders "v2.0 · <sha>" using the injected __GIT_SHA__ global (U+00B7 separator)', async () => {
    vi.stubGlobal('__GIT_SHA__', 'abc1234');
    vi.resetModules();
    const { VersionIndicator } = await import('./VersionIndicator');
    const { container } = render(<VersionIndicator />);
    // Exact string match including U+00B7 MIDDLE DOT.
    expect(screen.getByText('v2.0 · abc1234')).toBeInTheDocument();
    // Assert separator is U+00B7, not a hyphen-minus.
    expect(container.textContent).toContain('·');
    expect(container.textContent).not.toContain('v2.0 - ');
  });

  it('renders as a <span> with fixed bottom-2 right-2 z-50 classes', async () => {
    vi.stubGlobal('__GIT_SHA__', 'abc1234');
    vi.resetModules();
    const { VersionIndicator } = await import('./VersionIndicator');
    const { container } = render(<VersionIndicator />);
    const span = container.querySelector('span');
    expect(span).not.toBeNull();
    expect(span).toHaveClass('fixed');
    expect(span).toHaveClass('bottom-2');
    expect(span).toHaveClass('right-2');
    expect(span).toHaveClass('z-50');
    expect(span).toHaveClass('text-xs');
    expect(span).toHaveClass('text-muted-foreground');
    expect(span).toHaveClass('opacity-60');
  });

  it('renders "v2.0 · unknown" cleanly when __GIT_SHA__ falls back to the git-failure literal', async () => {
    vi.stubGlobal('__GIT_SHA__', 'unknown');
    vi.resetModules();
    const { VersionIndicator } = await import('./VersionIndicator');
    render(<VersionIndicator />);
    expect(screen.getByText('v2.0 · unknown')).toBeInTheDocument();
  });
});
