import { useCallback, useRef, useState } from 'react';
import type { ApiResponse, ReasoningTraceEntry, RecommendationResponse, HardshipResponse } from '@/lib/types';
import { isHardshipResponse } from '@/lib/types';
import { CUSTOMER_ID_PATTERN, normalizeCustomerId } from '@/lib/validate';
import { simulateStreaming } from '@/lib/mock/streamingMock';
import { useStreamingRecommendations } from './useStreamingRecommendations';

/**
 * Discriminated-union state machine for the `GET /recommendations/{id}` call.
 *
 * - `idle`      — initial render, no lookup has been attempted yet (UI-SPEC "Empty" state)
 * - `loading`   — a batch lookup is in flight (UI-SPEC "Loading" state — previous results cleared)
 * - `streaming` — SSE or mock streaming in progress; traceSteps grow progressively
 * - `success`   — 200 response parsed into a typed `RecommendationResponse`
 * - `hardship`  — hardship short-circuit response
 * - `error`     — any non-2xx status, client-side validation failure, network error,
 *                 or mock-mode cache miss. `httpStatus` is keyed into `errorCopyForStatus`
 *                 by the component layer; `0` signals "no HTTP response was received".
 */
export type RecommendationState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'streaming'; traceSteps: ReasoningTraceEntry[]; customerId: string }
  | { status: 'success'; data: RecommendationResponse; customerId: string; traceSteps: ReasoningTraceEntry[] }
  | { status: 'hardship'; data: HardshipResponse; customerId: string; traceSteps: ReasoningTraceEntry[] }
  | { status: 'error'; httpStatus: number; customerId: string; traceSteps: ReasoningTraceEntry[] };

/**
 * Single-source data hook for the agent-assist UI.
 *
 * Decision logic (Requirements 5.1, 6.1, 7.1):
 *   1. If `VITE_STREAMING_URL` is set → delegate to `useStreamingRecommendations` hook
 *   2. If neither `VITE_API_URL` nor `VITE_STREAMING_URL` is set → use mock streaming simulation
 *   3. If only `VITE_API_URL` is set → preserve existing batch fetch path (unchanged)
 *
 * All hooks are called unconditionally to satisfy React's rules of hooks.
 * The mode selection only affects which state/lookup is returned.
 *
 * Design decisions:
 *   - D-01: native `fetch`, no data-fetching library (one endpoint, one screen).
 *   - D-03: if `VITE_API_URL` is unset/empty AND `VITE_STREAMING_URL` is unset/empty,
 *           uses mock streaming simulation from `streamingMock.ts`.
 *   - D-04: single fetch per lookup, no automatic re-attempt on failure.
 *   - UI-SPEC "Re-query": submitting a new ID CANCELS the in-flight request (via
 *           AbortController or EventSource close) AND clears previous results.
 */
export function useRecommendations() {
  // --- Streaming SSE path (always instantiated to satisfy rules of hooks) ---
  const { state: streamingState, lookup: streamingLookup } = useStreamingRecommendations();

  // --- Local state for mock-streaming and batch paths ---
  const [localState, setLocalState] = useState<RecommendationState>({ status: 'idle' });
  const abortRef = useRef<AbortController | (() => void) | null>(null);

  const localLookup = useCallback(async (rawId: string) => {
    // Read env vars at call time (not module level) so tests can stub per-case.
    const streamingUrl = import.meta.env.VITE_STREAMING_URL;
    const apiUrl = import.meta.env.VITE_API_URL;

    if (!streamingUrl && !apiUrl) {
      // --- Mock streaming path (Requirements 6.1, 6.2, 6.3) ---
      // Cancel any in-flight mock streaming simulation.
      if (typeof abortRef.current === 'function') {
        abortRef.current();
      }
      abortRef.current = null;

      // Normalize + client-side validate.
      const customerId = normalizeCustomerId(rawId);
      if (!CUSTOMER_ID_PATTERN.test(customerId)) {
        setLocalState({ status: 'error', httpStatus: 400, customerId, traceSteps: [] });
        return;
      }

      // Transition to streaming state — clears previous results.
      setLocalState({ status: 'streaming', traceSteps: [], customerId });

      // Start mock streaming simulation.
      let traceSteps: ReasoningTraceEntry[] = [];

      const abort = simulateStreaming(customerId, {
        onTraceStep: (event) => {
          traceSteps = [...traceSteps, { tool: event.tool, summary: event.summary }];
          setLocalState({ status: 'streaming', traceSteps, customerId });
        },
        onResult: (data) => {
          if (isHardshipResponse(data)) {
            setLocalState({ status: 'hardship', data, customerId, traceSteps });
          } else {
            setLocalState({ status: 'success', data: data as RecommendationResponse, customerId, traceSteps });
          }
        },
        onError: (event) => {
          setLocalState({ status: 'error', httpStatus: event.status, customerId, traceSteps });
        },
        onDone: () => {
          // Stream complete — no state change needed beyond what onResult/onError set.
        },
      });

      abortRef.current = abort;
    } else if (!streamingUrl && apiUrl) {
      // --- Batch fetch path (Requirement 7.1) ---
      // Cancel any in-flight request — UI-SPEC "Re-query" state.
      if (abortRef.current instanceof AbortController) {
        abortRef.current.abort();
      }

      // Normalize + client-side validate (D-10).
      const customerId = normalizeCustomerId(rawId);
      if (!CUSTOMER_ID_PATTERN.test(customerId)) {
        setLocalState({ status: 'error', httpStatus: 400, customerId, traceSteps: [] });
        return;
      }

      // Clear previous results — the component layer shows skeletons immediately.
      setLocalState({ status: 'loading' });

      // Real API fetch. AbortController lets a later lookup pre-empt an
      // older in-flight request so we don't paint stale data on re-query.
      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        const response = await fetch(
          `${apiUrl}/recommendations/${encodeURIComponent(customerId)}`,
          { signal: ctrl.signal },
        );

        if (!response.ok) {
          // Status-first branching — body is not read on non-200 paths.
          setLocalState({ status: 'error', httpStatus: response.status, customerId, traceSteps: [] });
          return;
        }

        const data = (await response.json()) as ApiResponse;
        if (isHardshipResponse(data)) {
          setLocalState({ status: 'hardship', data, customerId, traceSteps: [] });
        } else {
          const recData = data as RecommendationResponse;
          // Extract reasoning_trace from batch response if present.
          const traceSteps = recData.reasoning_trace ?? [];
          setLocalState({ status: 'success', data: recData, customerId, traceSteps });
        }
      } catch (err: unknown) {
        // Superseded requests resolve via AbortError — silently ignored.
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        // Network failure — status 0 keys the "generic server" copy.
        setLocalState({ status: 'error', httpStatus: 0, customerId, traceSteps: [] });
      }
    }
    // If streamingUrl is set, localLookup is never called (streamingLookup is used instead).
  }, []);

  // Wrap streamingLookup in a stable async callback for API compatibility.
  const streamingLookupAsync = useCallback(async (rawId: string) => {
    streamingLookup(rawId);
  }, [streamingLookup]);

  // --- Mode selection: which state/lookup to expose ---
  // Read env vars to determine mode. In production these are build-time constants;
  // in tests they may be stubbed per-case.
  const streamingUrl = import.meta.env.VITE_STREAMING_URL;

  if (streamingUrl) {
    // Map StreamingState → RecommendationState for transparent consumer API.
    const state: RecommendationState = (() => {
      switch (streamingState.status) {
        case 'idle':
          return { status: 'idle' as const };
        case 'streaming':
          return {
            status: 'streaming' as const,
            traceSteps: streamingState.traceSteps,
            customerId: streamingState.customerId,
          };
        case 'success':
          return {
            status: 'success' as const,
            data: streamingState.data,
            customerId: streamingState.customerId,
            traceSteps: streamingState.traceSteps,
          };
        case 'hardship':
          return {
            status: 'hardship' as const,
            data: streamingState.data,
            customerId: streamingState.customerId,
            traceSteps: streamingState.traceSteps,
          };
        case 'error':
          return {
            status: 'error' as const,
            httpStatus: streamingState.httpStatus,
            customerId: streamingState.customerId,
            traceSteps: streamingState.traceSteps,
          };
      }
    })();

    return { state, lookup: streamingLookupAsync } as const;
  }

  return { state: localState, lookup: localLookup } as const;
}
