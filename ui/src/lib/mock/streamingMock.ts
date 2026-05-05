import type { TraceStepEvent, StreamingErrorEvent, RecommendationResponse, HardshipResponse } from '../types';
import { MOCK_REASONING_TRACE_CUST003, MOCK_RECOMMENDATIONS, MOCK_HARDSHIP_RESPONSES } from './recommendations';

/**
 * Callbacks for streaming simulation events.
 * Mirrors the SSE wire protocol event types from design.md §Wire Protocol Events.
 */
export interface StreamingCallbacks {
  onTraceStep: (event: TraceStepEvent) => void;
  onResult: (data: RecommendationResponse | HardshipResponse) => void;
  onError: (event: StreamingErrorEvent) => void;
  onDone: () => void;
}

/**
 * Simulate SSE streaming for mock mode (VITE_API_URL and VITE_STREAMING_URL unset).
 *
 * Emits events in the same sequence as the real streaming endpoint:
 *   1. trace_step events (one per tool, with ~300ms delay between each)
 *   2. result event (final payload)
 *   3. done event (terminal)
 *
 * For unknown customer IDs: emits error event (404) + done event.
 *
 * Requirements: 6.1, 6.2, 6.3
 */
export function simulateStreaming(
  customerId: string,
  callbacks: StreamingCallbacks,
): () => void {
  let aborted = false;
  const timers: ReturnType<typeof setTimeout>[] = [];

  const schedule = (fn: () => void, delay: number) => {
    const timer = setTimeout(() => {
      if (!aborted) fn();
    }, delay);
    timers.push(timer);
  };

  // Check if this is a known persona (recommendation or hardship)
  const recommendation = MOCK_RECOMMENDATIONS[customerId];
  const hardship = MOCK_HARDSHIP_RESPONSES[customerId];

  if (!recommendation && !hardship) {
    // Unknown customer ID → error 404 + done
    schedule(() => {
      callbacks.onError({ status: 404, message: 'Customer not found' });
    }, 100);
    schedule(() => {
      callbacks.onDone();
    }, 150);

    return () => {
      aborted = true;
      timers.forEach(clearTimeout);
    };
  }

  // Determine trace steps: CUST-003 has a full trace; others have empty trace
  const traceSteps = customerId === 'CUST-003' ? MOCK_REASONING_TRACE_CUST003 : [];

  // Emit trace_step events with ~300ms delay between each
  let delay = 300;
  for (const step of traceSteps) {
    const currentDelay = delay;
    schedule(() => {
      callbacks.onTraceStep({ tool: step.tool, summary: step.summary });
    }, currentDelay);
    delay += 300;
  }

  // Emit result event after all trace steps
  const resultDelay = delay + 100;
  schedule(() => {
    if (hardship) {
      callbacks.onResult(hardship);
    } else {
      callbacks.onResult(recommendation!);
    }
  }, resultDelay);

  // Emit done event as terminal
  schedule(() => {
    callbacks.onDone();
  }, resultDelay + 50);

  // Return abort function
  return () => {
    aborted = true;
    timers.forEach(clearTimeout);
  };
}
