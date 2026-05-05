/**
 * Tests for useStreamingRecommendations hook — SSE consumer for streaming reasoning trace.
 *
 * Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.7
 *
 * Strategy: Mock the browser EventSource API to simulate SSE events.
 * Each test verifies a specific state transition in the streaming state machine.
 */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStreamingRecommendations } from './useStreamingRecommendations';

// --- EventSource mock infrastructure ---

type EventSourceListener = (event: MessageEvent) => void;

interface MockEventSource {
  url: string;
  close: ReturnType<typeof vi.fn>;
  addEventListener: ReturnType<typeof vi.fn>;
  onerror: ((event: Event) => void) | null;
  // Test helpers — not part of the real EventSource API.
  _listeners: Record<string, EventSourceListener[]>;
  _emit: (type: string, data: string) => void;
  _triggerError: () => void;
}

/**
 * Creates a class-based EventSource mock that works with `new EventSource(url)`.
 * Tracks all instances for test assertions.
 */
function createMockEventSourceClass() {
  const instances: MockEventSource[] = [];

  class MockES {
    url: string;
    close: ReturnType<typeof vi.fn>;
    addEventListener: ReturnType<typeof vi.fn>;
    onerror: ((event: Event) => void) | null = null;
    _listeners: Record<string, EventSourceListener[]> = {};

    constructor(url: string) {
      this.url = url;
      this.close = vi.fn();
      this.addEventListener = vi.fn((type: string, handler: EventSourceListener) => {
        if (!this._listeners[type]) this._listeners[type] = [];
        this._listeners[type].push(handler);
      });
      instances.push(this as unknown as MockEventSource);
    }

    _emit(type: string, data: string) {
      const handlers = this._listeners[type] ?? [];
      const event = new MessageEvent(type, { data });
      handlers.forEach((h) => h(event));
    }

    _triggerError() {
      if (this.onerror) {
        this.onerror(new Event('error'));
      }
    }

    static instances = instances;
  }

  return MockES as unknown as (new (url: string) => MockEventSource) & { instances: MockEventSource[] };
}

let MockEventSourceClass: ReturnType<typeof createMockEventSourceClass>;

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  MockEventSourceClass = createMockEventSourceClass();
  vi.stubGlobal('EventSource', MockEventSourceClass);
  vi.stubEnv('VITE_STREAMING_URL', 'https://streaming.example.com');
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('useStreamingRecommendations — state transitions', () => {
  it('starts in idle state', () => {
    const { result } = renderHook(() => useStreamingRecommendations());
    expect(result.current.state.status).toBe('idle');
  });

  it('transitions to streaming state on lookup', () => {
    const { result } = renderHook(() => useStreamingRecommendations());

    act(() => {
      result.current.lookup('CUST-001');
    });

    expect(result.current.state.status).toBe('streaming');
    if (result.current.state.status === 'streaming') {
      expect(result.current.state.traceSteps).toHaveLength(0);
      expect(result.current.state.customerId).toBe('CUST-001');
    }
  });

  it('trace_step events append to traceSteps array (Requirement 5.2)', () => {
    const { result } = renderHook(() => useStreamingRecommendations());

    act(() => {
      result.current.lookup('CUST-003');
    });

    const es = MockEventSourceClass.instances[0];

    // Emit first trace_step
    act(() => {
      es._emit('trace_step', JSON.stringify({ tool: 'get_hardship_flag', summary: 'hardship_flag=False' }));
    });

    expect(result.current.state.status).toBe('streaming');
    if (result.current.state.status === 'streaming') {
      expect(result.current.state.traceSteps).toHaveLength(1);
      expect(result.current.state.traceSteps[0].tool).toBe('get_hardship_flag');
      expect(result.current.state.traceSteps[0].summary).toBe('hardship_flag=False');
    }

    // Emit second trace_step
    act(() => {
      es._emit('trace_step', JSON.stringify({
        tool: 'detect_bill_shock',
        summary: 'Bill shock detected: +$65.16 2025-10 vs 11-month avg ($167.88 vs $102.72)',
      }));
    });

    if (result.current.state.status === 'streaming') {
      expect(result.current.state.traceSteps).toHaveLength(2);
      expect(result.current.state.traceSteps[1].tool).toBe('detect_bill_shock');
    }
  });

  it('result event transitions to success state for recommendation (Requirement 5.3)', () => {
    const { result } = renderHook(() => useStreamingRecommendations());

    act(() => {
      result.current.lookup('CUST-001');
    });

    const es = MockEventSourceClass.instances[0];

    // Emit a trace step first
    act(() => {
      es._emit('trace_step', JSON.stringify({ tool: 'simulate_savings', summary: 'Green $30.00/mo; Cheapest $55.00/mo' }));
    });

    // Emit result event
    const resultPayload = {
      kind: 'recommendation',
      green: { plan_id: 'ECO', plan_name: 'EcoFlex 100', saving_monthly: 30.0, saving_annual: 360.0, usage_narrative: 'test', call_script: 'test' },
      cheapest: { plan_id: 'VAL', plan_name: 'Value 12', saving_monthly: 55.0, saving_annual: 660.0, usage_narrative: 'test', call_script: 'test' },
    };

    act(() => {
      es._emit('result', JSON.stringify(resultPayload));
    });

    expect(result.current.state.status).toBe('success');
    if (result.current.state.status === 'success') {
      expect(result.current.state.data.green.plan_id).toBe('ECO');
      expect(result.current.state.data.cheapest.plan_id).toBe('VAL');
      expect(result.current.state.traceSteps).toHaveLength(1);
      expect(result.current.state.customerId).toBe('CUST-001');
    }
  });

  it('result event transitions to hardship state for hardship response', () => {
    const { result } = renderHook(() => useStreamingRecommendations());

    act(() => {
      result.current.lookup('CUST-006');
    });

    const es = MockEventSourceClass.instances[0];

    const hardshipPayload = {
      kind: 'hardship',
      customer_id: 'CUST-006',
      reason: 'Hardship flagged',
      routing_target: 'hardship_team',
      call_script: 'Connecting to specialist team.',
    };

    act(() => {
      es._emit('result', JSON.stringify(hardshipPayload));
    });

    expect(result.current.state.status).toBe('hardship');
    if (result.current.state.status === 'hardship') {
      expect(result.current.state.data.kind).toBe('hardship');
      expect(result.current.state.data.customer_id).toBe('CUST-006');
    }
  });

  it('done event closes EventSource connection (Requirement 5.4)', () => {
    const { result } = renderHook(() => useStreamingRecommendations());

    act(() => {
      result.current.lookup('CUST-001');
    });

    const es = MockEventSourceClass.instances[0];

    // Emit result then done
    act(() => {
      es._emit('result', JSON.stringify({
        green: { plan_id: 'ECO', plan_name: 'EcoFlex 100', saving_monthly: 30.0, saving_annual: 360.0, usage_narrative: 'x', call_script: 'x' },
        cheapest: { plan_id: 'VAL', plan_name: 'Value 12', saving_monthly: 55.0, saving_annual: 660.0, usage_narrative: 'x', call_script: 'x' },
      }));
    });

    act(() => {
      es._emit('done', '{}');
    });

    expect(es.close).toHaveBeenCalledTimes(1);
  });

  it('error event transitions to error state with httpStatus (Requirement 5.5)', () => {
    const { result } = renderHook(() => useStreamingRecommendations());

    act(() => {
      result.current.lookup('CUST-999');
    });

    const es = MockEventSourceClass.instances[0];

    act(() => {
      es._emit('error', JSON.stringify({ status: 404, message: 'Customer not found' }));
    });

    expect(result.current.state.status).toBe('error');
    if (result.current.state.status === 'error') {
      expect(result.current.state.httpStatus).toBe(404);
      expect(result.current.state.customerId).toBe('CUST-999');
    }
    expect(es.close).toHaveBeenCalled();
  });

  it('native onerror transitions to error state with httpStatus 0 when still streaming', () => {
    const { result } = renderHook(() => useStreamingRecommendations());

    act(() => {
      result.current.lookup('CUST-001');
    });

    const es = MockEventSourceClass.instances[0];

    act(() => {
      es._triggerError();
    });

    expect(result.current.state.status).toBe('error');
    if (result.current.state.status === 'error') {
      expect(result.current.state.httpStatus).toBe(0);
    }
    expect(es.close).toHaveBeenCalled();
  });

  it('invalid customer ID returns 400 error without opening EventSource', () => {
    const { result } = renderHook(() => useStreamingRecommendations());

    act(() => {
      result.current.lookup('NOTVALID');
    });

    expect(result.current.state.status).toBe('error');
    if (result.current.state.status === 'error') {
      expect(result.current.state.httpStatus).toBe(400);
    }
    // No EventSource should have been created
    expect(MockEventSourceClass.instances).toHaveLength(0);
  });
});

describe('useStreamingRecommendations — abort on re-query (Requirement 5.7)', () => {
  it('closes existing EventSource when a new lookup is initiated', () => {
    const { result } = renderHook(() => useStreamingRecommendations());

    // First lookup
    act(() => {
      result.current.lookup('CUST-001');
    });

    const firstEs = MockEventSourceClass.instances[0];
    expect(firstEs.close).not.toHaveBeenCalled();

    // Second lookup — should close the first connection
    act(() => {
      result.current.lookup('CUST-002');
    });

    expect(firstEs.close).toHaveBeenCalledTimes(1);
    expect(MockEventSourceClass.instances).toHaveLength(2);

    const secondEs = MockEventSourceClass.instances[1];
    expect(secondEs.url).toContain('CUST-002');
  });

  it('new lookup resets traceSteps to empty', () => {
    const { result } = renderHook(() => useStreamingRecommendations());

    act(() => {
      result.current.lookup('CUST-003');
    });

    const firstEs = MockEventSourceClass.instances[0];

    // Accumulate some trace steps
    act(() => {
      firstEs._emit('trace_step', JSON.stringify({ tool: 'get_hardship_flag', summary: 'hardship_flag=False' }));
    });

    if (result.current.state.status === 'streaming') {
      expect(result.current.state.traceSteps).toHaveLength(1);
    }

    // Re-query — should reset
    act(() => {
      result.current.lookup('CUST-001');
    });

    expect(result.current.state.status).toBe('streaming');
    if (result.current.state.status === 'streaming') {
      expect(result.current.state.traceSteps).toHaveLength(0);
      expect(result.current.state.customerId).toBe('CUST-001');
    }
  });
});

describe('useStreamingRecommendations — EventSource URL construction', () => {
  it('constructs URL from VITE_STREAMING_URL with encoded customer ID', () => {
    const { result } = renderHook(() => useStreamingRecommendations());

    act(() => {
      result.current.lookup('CUST-001');
    });

    const es = MockEventSourceClass.instances[0];
    expect(es.url).toBe('https://streaming.example.com/recommendations/CUST-001');
  });

  it('normalizes customer ID before constructing URL', () => {
    const { result } = renderHook(() => useStreamingRecommendations());

    act(() => {
      result.current.lookup('  cust003  ');
    });

    const es = MockEventSourceClass.instances[0];
    expect(es.url).toBe('https://streaming.example.com/recommendations/CUST-003');
  });
});
