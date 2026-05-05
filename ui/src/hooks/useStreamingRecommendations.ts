import { useCallback, useRef, useState } from 'react';
import type {
  ReasoningTraceEntry,
  RecommendationResponse,
  HardshipResponse,
} from '@/lib/types';
import { isHardshipResponse } from '@/lib/types';
import { CUSTOMER_ID_PATTERN, normalizeCustomerId } from '@/lib/validate';

/**
 * Discriminated-union state machine for the SSE streaming path.
 *
 * State transitions:
 *   idle → streaming       (on lookup)
 *   streaming → streaming  (on trace_step — append to traceSteps)
 *   streaming → success    (on result with kind=recommendation)
 *   streaming → hardship   (on result with kind=hardship)
 *   streaming → error      (on error event or connection failure)
 *   Any → idle             (on reset)
 *
 * Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.7
 */
export type StreamingState =
  | { status: 'idle' }
  | { status: 'streaming'; traceSteps: ReasoningTraceEntry[]; customerId: string }
  | { status: 'success'; traceSteps: ReasoningTraceEntry[]; data: RecommendationResponse; customerId: string }
  | { status: 'hardship'; traceSteps: ReasoningTraceEntry[]; data: HardshipResponse; customerId: string }
  | { status: 'error'; traceSteps: ReasoningTraceEntry[]; httpStatus: number; customerId: string };

/**
 * SSE consumer hook for the streaming reasoning trace endpoint.
 *
 * Uses native `EventSource` to connect to the Lambda Function URL at
 * `VITE_STREAMING_URL`. The Function URL detects the SSE connection and
 * streams typed events: trace_step, result, error, done.
 *
 * Design decisions:
 *   - EventSource for simplicity — the Function URL handles SSE detection
 *     without needing custom headers.
 *   - On new lookup: abort in-flight EventSource before opening a new one
 *     (same pattern as AbortController in useRecommendations).
 *   - traceSteps accumulates progressively; final state preserves the full trace.
 */
export function useStreamingRecommendations() {
  const [state, setState] = useState<StreamingState>({ status: 'idle' });
  const eventSourceRef = useRef<EventSource | null>(null);

  /** Close and clean up the current EventSource connection. */
  const closeConnection = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const lookup = useCallback((rawId: string) => {
    // 1. Abort any in-flight SSE connection (Requirement 5.7).
    closeConnection();

    // 2. Normalize + client-side validate.
    const customerId = normalizeCustomerId(rawId);
    if (!CUSTOMER_ID_PATTERN.test(customerId)) {
      setState({ status: 'error', traceSteps: [], httpStatus: 400, customerId });
      return;
    }

    // 3. Transition to streaming state — clears previous results.
    setState({ status: 'streaming', traceSteps: [], customerId });

    // 4. Open SSE connection to the streaming endpoint.
    const streamingUrl = import.meta.env.VITE_STREAMING_URL;
    const url = `${streamingUrl}/recommendations/${encodeURIComponent(customerId)}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    // Accumulate trace steps in a mutable array for the closure — React state
    // updates are batched, so we track the running list here and spread into state.
    let traceSteps: ReasoningTraceEntry[] = [];

    // trace_step event: append to traceSteps array (Requirement 5.2).
    es.addEventListener('trace_step', (event: MessageEvent) => {
      const entry: ReasoningTraceEntry = JSON.parse(event.data);
      traceSteps = [...traceSteps, entry];
      setState({ status: 'streaming', traceSteps, customerId });
    });

    // result event: transition to success or hardship state (Requirement 5.3).
    es.addEventListener('result', (event: MessageEvent) => {
      const data = JSON.parse(event.data);
      if (isHardshipResponse(data)) {
        setState({ status: 'hardship', traceSteps, data, customerId });
      } else {
        setState({ status: 'success', traceSteps, data: data as RecommendationResponse, customerId });
      }
    });

    // done event: close EventSource (Requirement 5.4).
    es.addEventListener('done', () => {
      closeConnection();
    });

    // error event from server: transition to error state (Requirement 5.5).
    es.addEventListener('error', (event: MessageEvent) => {
      // Server-sent error event has data with status + message.
      if (event.data) {
        const errorData = JSON.parse(event.data);
        setState({ status: 'error', traceSteps, httpStatus: errorData.status ?? 502, customerId });
        closeConnection();
      }
    });

    // Native EventSource onerror: connection drop / network failure.
    es.onerror = () => {
      // Only transition to error if we're still in streaming state —
      // if we already got a result or server error, ignore the connection close.
      setState((prev) => {
        if (prev.status === 'streaming') {
          return { status: 'error', traceSteps, httpStatus: 0, customerId };
        }
        return prev;
      });
      closeConnection();
    };
  }, [closeConnection]);

  return { state, lookup } as const;
}
