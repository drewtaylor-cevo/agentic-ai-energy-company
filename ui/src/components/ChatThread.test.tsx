// Conversational chat layer — ChatThread component tests.
// Requirements: 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4
import { beforeEach, describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChatThread } from './ChatThread';
import type { ChatMessage, ReasoningTraceEntry } from '@/lib/types';

// Mock scrollIntoView which is not available in jsdom.
beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

// Mock the ReasoningTrace component to simplify assertions.
vi.mock('@/components/ReasoningTrace', () => ({
  ReasoningTrace: ({ trace, isStreaming }: { trace: ReasoningTraceEntry[]; isStreaming?: boolean }) => (
    <div data-testid="reasoning-trace" data-streaming={isStreaming ? 'true' : 'false'}>
      {trace.map((t, i) => (
        <span key={i}>{t.tool}: {t.summary}</span>
      ))}
    </div>
  ),
}));

function makeMessage(overrides: Partial<ChatMessage> & { id: string; role: 'user' | 'assistant'; content: string }): ChatMessage {
  return {
    timestamp: Date.now(),
    ...overrides,
  };
}

describe('ChatThread', () => {
  it('renders nothing when messages is empty and not processing and no error', () => {
    const { container } = render(
      <ChatThread messages={[]} isProcessing={false} currentTrace={[]} error={null} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders messages with correct alignment — user right, assistant left', () => {
    const messages: ChatMessage[] = [
      makeMessage({ id: '1', role: 'user', content: 'Why did her bill jump?' }),
      makeMessage({ id: '2', role: 'assistant', content: 'Based on the billing records...' }),
    ];

    render(
      <ChatThread messages={messages} isProcessing={false} currentTrace={[]} error={null} />
    );

    const thread = screen.getByRole('region', { name: /chat thread/i });
    expect(thread).toBeInTheDocument();

    // User message container should have justify-end (right-aligned)
    const userMsg = screen.getByText('Why did her bill jump?');
    const userContainer = userMsg.closest('.flex');
    expect(userContainer).toHaveClass('justify-end');

    // Assistant message container should have justify-start (left-aligned)
    const assistantMsg = screen.getByText('Based on the billing records...');
    const assistantContainer = assistantMsg.closest('.flex');
    expect(assistantContainer).toHaveClass('justify-start');
  });

  it('auto-scrolls on new message (scrollIntoView called)', () => {
    const scrollIntoViewMock = Element.prototype.scrollIntoView as ReturnType<typeof vi.fn>;
    scrollIntoViewMock.mockClear();

    const messages: ChatMessage[] = [
      makeMessage({ id: '1', role: 'user', content: 'Hello' }),
    ];

    const { rerender } = render(
      <ChatThread messages={messages} isProcessing={false} currentTrace={[]} error={null} />
    );

    scrollIntoViewMock.mockClear();

    // Add a new message — should trigger auto-scroll
    const updatedMessages = [
      ...messages,
      makeMessage({ id: '2', role: 'assistant', content: 'Hi there!' }),
    ];

    rerender(
      <ChatThread messages={updatedMessages} isProcessing={false} currentTrace={[]} error={null} />
    );

    expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: 'smooth' });
  });

  it('shows typing indicator during processing', () => {
    render(
      <ChatThread messages={[]} isProcessing={true} currentTrace={[]} error={null} />
    );

    const indicator = screen.getByTestId('typing-indicator');
    expect(indicator).toBeInTheDocument();
    expect(indicator).toHaveAttribute('aria-label', 'Agent is typing');
  });

  it('does not show typing indicator when not processing', () => {
    const messages: ChatMessage[] = [
      makeMessage({ id: '1', role: 'user', content: 'Hello' }),
    ];

    render(
      <ChatThread messages={messages} isProcessing={false} currentTrace={[]} error={null} />
    );

    expect(screen.queryByTestId('typing-indicator')).not.toBeInTheDocument();
  });

  it('shows inline error on error event', () => {
    render(
      <ChatThread
        messages={[]}
        isProcessing={false}
        currentTrace={[]}
        error="Connection lost. Please try again."
      />
    );

    const errorEl = screen.getByTestId('chat-error');
    expect(errorEl).toBeInTheDocument();
    expect(errorEl).toHaveAttribute('role', 'alert');
    expect(screen.getByText('Connection lost. Please try again.')).toBeInTheDocument();
  });

  it('displays reasoning trace for assistant messages that used tools', () => {
    const trace: ReasoningTraceEntry[] = [
      { tool: 'get_billing_history', summary: '12 months retrieved' },
    ];
    const messages: ChatMessage[] = [
      makeMessage({ id: '1', role: 'assistant', content: 'Here is the info.', reasoning_trace: trace }),
    ];

    render(
      <ChatThread messages={messages} isProcessing={false} currentTrace={[]} error={null} />
    );

    const traceEl = screen.getByTestId('reasoning-trace');
    expect(traceEl).toBeInTheDocument();
    expect(screen.getByText('get_billing_history: 12 months retrieved')).toBeInTheDocument();
  });

  it('shows live reasoning trace while processing with isStreaming=true', () => {
    const currentTrace: ReasoningTraceEntry[] = [
      { tool: 'simulate_savings', summary: 'Running simulation' },
    ];

    render(
      <ChatThread messages={[]} isProcessing={true} currentTrace={currentTrace} error={null} />
    );

    const traceEl = screen.getByTestId('reasoning-trace');
    expect(traceEl).toHaveAttribute('data-streaming', 'true');
  });
});

describe('ChatThread — ?narrative=off kill-switch', () => {
  // The ?narrative=off flag is evaluated in App.tsx which passes visible=false
  // to ChatInputBox. The ChatInputBox component already tests visible=false
  // rendering nothing. Here we verify the flag computation logic that drives
  // the chatVisible variable in App.tsx.
  it('NARRATIVE_ENABLED is false when ?narrative=off is in the URL', async () => {
    // Dynamically re-evaluate the flags module with ?narrative=off
    const originalSearch = window.location.search;
    Object.defineProperty(window, 'location', {
      value: { ...window.location, search: '?narrative=off' },
      writable: true,
    });

    // Re-import the flags module to pick up the new URL
    vi.resetModules();
    const { NARRATIVE_ENABLED } = await import('@/lib/flags');
    expect(NARRATIVE_ENABLED).toBe(false);

    // Restore
    Object.defineProperty(window, 'location', {
      value: { ...window.location, search: originalSearch },
      writable: true,
    });
  });

  it('NARRATIVE_ENABLED is true when ?narrative=off is NOT in the URL', async () => {
    Object.defineProperty(window, 'location', {
      value: { ...window.location, search: '' },
      writable: true,
    });

    vi.resetModules();
    const { NARRATIVE_ENABLED } = await import('@/lib/flags');
    expect(NARRATIVE_ENABLED).toBe(true);

    // Restore
    Object.defineProperty(window, 'location', {
      value: { ...window.location, search: '' },
      writable: true,
    });
  });
});
