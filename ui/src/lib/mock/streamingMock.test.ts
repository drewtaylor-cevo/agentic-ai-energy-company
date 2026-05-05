/**
 * Tests for the mock streaming simulation module.
 *
 * Validates: Requirements 6.1, 6.2, 6.3
 *
 * Strategy: Use vi.useFakeTimers() to control setTimeout delays and verify
 * that events are emitted in the correct order with the expected delays.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { simulateStreaming } from './streamingMock';
import type { StreamingCallbacks } from './streamingMock';
import { MOCK_REASONING_TRACE_CUST003, MOCK_RECOMMENDATIONS, MOCK_HARDSHIP_RESPONSES } from './recommendations';

function createCallbacks() {
  return {
    onTraceStep: vi.fn(),
    onResult: vi.fn(),
    onError: vi.fn(),
    onDone: vi.fn(),
  } satisfies StreamingCallbacks;
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('simulateStreaming — known recommendation personas (Requirement 6.1, 6.2)', () => {
  it('emits trace_step events with ~300ms delay for CUST-003 (bill-shock persona)', () => {
    const callbacks = createCallbacks();
    simulateStreaming('CUST-003', callbacks);

    // No events emitted synchronously
    expect(callbacks.onTraceStep).not.toHaveBeenCalled();

    // After 300ms: first trace step
    vi.advanceTimersByTime(300);
    expect(callbacks.onTraceStep).toHaveBeenCalledTimes(1);
    expect(callbacks.onTraceStep).toHaveBeenCalledWith({
      tool: MOCK_REASONING_TRACE_CUST003[0].tool,
      summary: MOCK_REASONING_TRACE_CUST003[0].summary,
    });

    // After 600ms: second trace step
    vi.advanceTimersByTime(300);
    expect(callbacks.onTraceStep).toHaveBeenCalledTimes(2);
    expect(callbacks.onTraceStep).toHaveBeenCalledWith({
      tool: MOCK_REASONING_TRACE_CUST003[1].tool,
      summary: MOCK_REASONING_TRACE_CUST003[1].summary,
    });

    // After 900ms: third trace step
    vi.advanceTimersByTime(300);
    expect(callbacks.onTraceStep).toHaveBeenCalledTimes(3);
    expect(callbacks.onTraceStep).toHaveBeenCalledWith({
      tool: MOCK_REASONING_TRACE_CUST003[2].tool,
      summary: MOCK_REASONING_TRACE_CUST003[2].summary,
    });
  });

  it('emits result event after all trace steps for CUST-003', () => {
    const callbacks = createCallbacks();
    simulateStreaming('CUST-003', callbacks);

    // Timing: 3 steps at 300/600/900ms, delay counter ends at 1200,
    // resultDelay = 1200 + 100 = 1300ms
    vi.advanceTimersByTime(1400);

    expect(callbacks.onResult).toHaveBeenCalledTimes(1);
    expect(callbacks.onResult).toHaveBeenCalledWith(MOCK_RECOMMENDATIONS['CUST-003']);
  });

  it('emits done event as the terminal event for CUST-003', () => {
    const callbacks = createCallbacks();
    simulateStreaming('CUST-003', callbacks);

    // Timing: resultDelay=1300, done at resultDelay+50=1350
    vi.advanceTimersByTime(1500);

    expect(callbacks.onDone).toHaveBeenCalledTimes(1);
    // done should come after result
    const resultOrder = callbacks.onResult.mock.invocationCallOrder[0];
    const doneOrder = callbacks.onDone.mock.invocationCallOrder[0];
    expect(doneOrder).toBeGreaterThan(resultOrder);
  });

  it('emits no trace_step events for CUST-001 (empty trace persona)', () => {
    const callbacks = createCallbacks();
    simulateStreaming('CUST-001', callbacks);

    // Advance past all timers
    vi.advanceTimersByTime(2000);

    // CUST-001 has empty reasoning_trace — no trace_step events
    expect(callbacks.onTraceStep).not.toHaveBeenCalled();
    expect(callbacks.onResult).toHaveBeenCalledTimes(1);
    expect(callbacks.onResult).toHaveBeenCalledWith(MOCK_RECOMMENDATIONS['CUST-001']);
    expect(callbacks.onDone).toHaveBeenCalledTimes(1);
  });

  it('uses same MOCK_RECOMMENDATIONS fixtures as batch mock path (Requirement 6.2)', () => {
    const callbacks = createCallbacks();
    simulateStreaming('CUST-002', callbacks);

    vi.advanceTimersByTime(2000);

    expect(callbacks.onResult).toHaveBeenCalledWith(MOCK_RECOMMENDATIONS['CUST-002']);
  });
});

describe('simulateStreaming — hardship persona', () => {
  it('emits hardship result for CUST-006', () => {
    const callbacks = createCallbacks();
    simulateStreaming('CUST-006', callbacks);

    vi.advanceTimersByTime(2000);

    expect(callbacks.onResult).toHaveBeenCalledTimes(1);
    expect(callbacks.onResult).toHaveBeenCalledWith(MOCK_HARDSHIP_RESPONSES['CUST-006']);
    expect(callbacks.onDone).toHaveBeenCalledTimes(1);
  });
});

describe('simulateStreaming — unknown customer ID (Requirement 6.3)', () => {
  it('emits error event with status 404 for unknown customer', () => {
    const callbacks = createCallbacks();
    simulateStreaming('CUST-999', callbacks);

    // Error emitted after short delay (~100ms)
    vi.advanceTimersByTime(150);

    expect(callbacks.onError).toHaveBeenCalledTimes(1);
    expect(callbacks.onError).toHaveBeenCalledWith({
      status: 404,
      message: 'Customer not found',
    });
    // No result or trace_step events
    expect(callbacks.onResult).not.toHaveBeenCalled();
    expect(callbacks.onTraceStep).not.toHaveBeenCalled();
  });

  it('emits done event after error for unknown customer', () => {
    const callbacks = createCallbacks();
    simulateStreaming('CUST-999', callbacks);

    vi.advanceTimersByTime(200);

    expect(callbacks.onDone).toHaveBeenCalledTimes(1);
    // done should come after error
    const errorOrder = callbacks.onError.mock.invocationCallOrder[0];
    const doneOrder = callbacks.onDone.mock.invocationCallOrder[0];
    expect(doneOrder).toBeGreaterThan(errorOrder);
  });
});

describe('simulateStreaming — abort function', () => {
  it('returns an abort function that stops further event emission', () => {
    const callbacks = createCallbacks();
    const abort = simulateStreaming('CUST-003', callbacks);

    // Advance to get first trace step
    vi.advanceTimersByTime(300);
    expect(callbacks.onTraceStep).toHaveBeenCalledTimes(1);

    // Abort — no further events should fire
    abort();

    vi.advanceTimersByTime(5000);
    expect(callbacks.onTraceStep).toHaveBeenCalledTimes(1);
    expect(callbacks.onResult).not.toHaveBeenCalled();
    expect(callbacks.onDone).not.toHaveBeenCalled();
  });
});
