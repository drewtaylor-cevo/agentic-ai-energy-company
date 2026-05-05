// Conversational chat layer — useChat hook tests.
// Requirements: 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 9.1, 9.2
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useChat } from './useChat';

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('useChat - mock mode (VITE_API_URL unset)', () => {
  // By default in test environment, VITE_API_URL is unset → mock mode.

  it('starts with empty initial state', () => {
    const { result } = renderHook(() => useChat('CUST-001'));
    expect(result.current.state.messages).toHaveLength(0);
    expect(result.current.state.isProcessing).toBe(false);
    expect(result.current.state.currentTrace).toHaveLength(0);
    expect(result.current.state.sessionId).toBeNull();
    expect(result.current.state.error).toBeNull();
  });

  it('sendMessage adds user message and sets isProcessing=true', async () => {
    const { result } = renderHook(() => useChat('CUST-001'));

    await act(async () => {
      result.current.sendMessage('Tell me about the bill');
    });

    expect(result.current.state.messages).toHaveLength(1);
    expect(result.current.state.messages[0].role).toBe('user');
    expect(result.current.state.messages[0].content).toBe('Tell me about the bill');
    expect(result.current.state.isProcessing).toBe(true);
  });

  it('does not send empty or whitespace-only messages', async () => {
    const { result } = renderHook(() => useChat('CUST-001'));

    await act(async () => {
      result.current.sendMessage('   ');
    });

    expect(result.current.state.messages).toHaveLength(0);
    expect(result.current.state.isProcessing).toBe(false);
  });

  it('mock mode returns keyword-matched reply for "bill"', async () => {
    const { result } = renderHook(() => useChat('CUST-001'));

    await act(async () => {
      result.current.sendMessage('Tell me about the bill');
    });

    // Advance past trace steps and reply delay
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    expect(result.current.state.isProcessing).toBe(false);
    expect(result.current.state.messages).toHaveLength(2);

    const assistantMsg = result.current.state.messages[1];
    expect(assistantMsg.role).toBe('assistant');
    // "bill" keyword should produce billing-related reply
    expect(assistantMsg.content.toLowerCase()).toContain('billing');
    expect(assistantMsg.reasoning_trace).toBeDefined();
    expect(assistantMsg.reasoning_trace!.length).toBeGreaterThan(0);
    expect(assistantMsg.reasoning_trace![0].tool).toBe('get_billing_history');
  });

  it('mock mode returns keyword-matched reply for "solar"', async () => {
    const { result } = renderHook(() => useChat('CUST-001'));

    await act(async () => {
      result.current.sendMessage('What about solar options?');
    });

    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    expect(result.current.state.isProcessing).toBe(false);
    const assistantMsg = result.current.state.messages[1];
    expect(assistantMsg.role).toBe('assistant');
    expect(assistantMsg.content.toLowerCase()).toContain('solar');
    expect(assistantMsg.reasoning_trace![0].tool).toBe('simulate_savings');
  });

  it('mock mode returns keyword-matched reply for "green"', async () => {
    const { result } = renderHook(() => useChat('CUST-001'));

    await act(async () => {
      result.current.sendMessage('Tell me about the green plan');
    });

    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    expect(result.current.state.isProcessing).toBe(false);
    const assistantMsg = result.current.state.messages[1];
    expect(assistantMsg.role).toBe('assistant');
    expect(assistantMsg.content.toLowerCase()).toContain('green');
  });

  it('mock mode returns fallback reply for unmatched keywords', async () => {
    const { result } = renderHook(() => useChat('CUST-001'));

    await act(async () => {
      result.current.sendMessage('What is the weather like?');
    });

    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    expect(result.current.state.isProcessing).toBe(false);
    expect(result.current.state.messages).toHaveLength(2);
    const assistantMsg = result.current.state.messages[1];
    expect(assistantMsg.role).toBe('assistant');
    expect(assistantMsg.content).toBeTruthy();
  });

  it('mock mode returns error for unknown customer ID', async () => {
    const { result } = renderHook(() => useChat('CUST-999'));

    await act(async () => {
      result.current.sendMessage('Tell me about the bill');
    });

    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    expect(result.current.state.isProcessing).toBe(false);
    expect(result.current.state.error).toBeTruthy();
    // Only the user message should be in the thread (no assistant reply)
    expect(result.current.state.messages).toHaveLength(1);
    expect(result.current.state.messages[0].role).toBe('user');
  });

  it('mock mode emits trace steps progressively', async () => {
    const { result } = renderHook(() => useChat('CUST-001'));

    await act(async () => {
      result.current.sendMessage('What are the savings options?');
    });

    // After first trace step delay (~300ms)
    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(result.current.state.isProcessing).toBe(true);
    expect(result.current.state.currentTrace.length).toBeGreaterThan(0);
  });

  it('mock mode sets sessionId after reply', async () => {
    const { result } = renderHook(() => useChat('CUST-001'));

    await act(async () => {
      result.current.sendMessage('Tell me about the bill');
    });

    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    expect(result.current.state.sessionId).toContain('mock-session-CUST-001');
  });

  it('reset clears messages and state', async () => {
    const { result } = renderHook(() => useChat('CUST-001'));

    await act(async () => {
      result.current.sendMessage('Hello');
    });

    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    expect(result.current.state.messages.length).toBeGreaterThan(0);

    act(() => {
      result.current.reset();
    });

    expect(result.current.state.messages).toHaveLength(0);
    expect(result.current.state.isProcessing).toBe(false);
    expect(result.current.state.sessionId).toBeNull();
    expect(result.current.state.error).toBeNull();
  });

  it('resets on customer change (customerId prop change)', async () => {
    const { result, rerender } = renderHook(
      ({ customerId }) => useChat(customerId),
      { initialProps: { customerId: 'CUST-001' } }
    );

    await act(async () => {
      result.current.sendMessage('Hello');
    });

    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    expect(result.current.state.messages.length).toBeGreaterThan(0);

    // Change customer — should reset
    rerender({ customerId: 'CUST-002' });

    expect(result.current.state.messages).toHaveLength(0);
    expect(result.current.state.isProcessing).toBe(false);
    expect(result.current.state.sessionId).toBeNull();
    expect(result.current.state.error).toBeNull();
  });
});

describe('useChat - API mode (VITE_API_URL set)', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_API_URL', 'https://api.example.com');
  });

  it('sendMessage triggers fetch to /chat/{customer_id} with SSE accept header', async () => {
    // Create a mock response that returns an SSE stream
    const sseBody = [
      'event: trace_step\ndata: {"tool":"get_billing_history","summary":"12 months retrieved"}\n\n',
      'event: chat_reply\ndata: {"reply":"Here is the info.","reasoning_trace":[{"tool":"get_billing_history","summary":"12 months retrieved"}],"session_id":"sess-123","customer_id":"CUST-001"}\n\n',
      'event: done\ndata: {}\n\n',
    ].join('');

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(sseBody));
        controller.close();
      },
    });

    const fetchMock = vi.fn(() =>
      Promise.resolve(new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }))
    );
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useChat('CUST-001'));

    await act(async () => {
      await result.current.sendMessage('Tell me about the bill');
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit & { headers: Record<string, string>; body: string }];
    expect(url).toBe('https://api.example.com/chat/CUST-001');
    expect(init.method).toBe('POST');
    expect(init.headers['Accept']).toBe('text/event-stream');
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(init.body)).toEqual({ message: 'Tell me about the bill' });
  });

  it('state transitions correctly through SSE stream: idle → processing → complete', async () => {
    const sseBody = [
      'event: trace_step\ndata: {"tool":"get_billing_history","summary":"12 months retrieved"}\n\n',
      'event: chat_reply\ndata: {"reply":"Answer here.","reasoning_trace":[{"tool":"get_billing_history","summary":"12 months retrieved"}],"session_id":"sess-abc","customer_id":"CUST-001"}\n\n',
      'event: done\ndata: {}\n\n',
    ].join('');

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(sseBody));
        controller.close();
      },
    });

    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve(new Response(stream, { status: 200 }))
    ));

    const { result } = renderHook(() => useChat('CUST-001'));

    // Before sending — idle
    expect(result.current.state.isProcessing).toBe(false);

    await act(async () => {
      await result.current.sendMessage('Hello');
    });

    // After stream completes — back to idle with messages
    expect(result.current.state.isProcessing).toBe(false);
    expect(result.current.state.messages).toHaveLength(2); // user + assistant
    expect(result.current.state.messages[1].role).toBe('assistant');
    expect(result.current.state.messages[1].content).toBe('Answer here.');
    expect(result.current.state.sessionId).toBe('sess-abc');
  });

  it('handles SSE error event and sets error state', async () => {
    const sseBody = 'event: error\ndata: {"status":502,"message":"Chat service error. Please try again."}\n\nevent: done\ndata: {}\n\n';

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(sseBody));
        controller.close();
      },
    });

    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve(new Response(stream, { status: 200 }))
    ));

    const { result } = renderHook(() => useChat('CUST-001'));

    await act(async () => {
      await result.current.sendMessage('Hello');
    });

    expect(result.current.state.isProcessing).toBe(false);
    expect(result.current.state.error).toBe('Chat service error. Please try again.');
  });

  it('handles pre-stream HTTP error (non-200 response)', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify({ error: 'Invalid customer ID format.' }), { status: 400 }))
    ));

    const { result } = renderHook(() => useChat('CUST-INVALID'));

    await act(async () => {
      await result.current.sendMessage('Hello');
    });

    expect(result.current.state.isProcessing).toBe(false);
    expect(result.current.state.error).toBe('Invalid customer ID format.');
  });

  it('handles network failure gracefully', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))));

    const { result } = renderHook(() => useChat('CUST-001'));

    await act(async () => {
      await result.current.sendMessage('Hello');
    });

    expect(result.current.state.isProcessing).toBe(false);
    expect(result.current.state.error).toBe('Connection lost. Please try again.');
  });

  it('includes session_id in subsequent requests for multi-turn context', async () => {
    const makeSSEResponse = (sessionId: string) => {
      const body = `event: chat_reply\ndata: {"reply":"Reply.","reasoning_trace":[],"session_id":"${sessionId}","customer_id":"CUST-001"}\n\nevent: done\ndata: {}\n\n`;
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(body));
          controller.close();
        },
      });
      return new Response(stream, { status: 200 });
    };

    const fetchMock = vi.fn()
      .mockResolvedValueOnce(makeSSEResponse('sess-first'))
      .mockResolvedValueOnce(makeSSEResponse('sess-second'));
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useChat('CUST-001'));

    // First message — no session_id
    await act(async () => {
      await result.current.sendMessage('First question');
    });

    const firstBody = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(firstBody.session_id).toBeUndefined();

    // Second message — should include session_id from first response
    await act(async () => {
      await result.current.sendMessage('Follow-up question');
    });

    const secondBody = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(secondBody.session_id).toBe('sess-first');
  });
});
