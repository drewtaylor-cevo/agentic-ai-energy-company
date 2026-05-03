import { useCallback, useRef, useState } from 'react';
import type { ApiResponse, RecommendationResponse, HardshipResponse } from '@/lib/types';
import { isHardshipResponse } from '@/lib/types';
import { CUSTOMER_ID_PATTERN, normalizeCustomerId } from '@/lib/validate';
import { MOCK_RECOMMENDATIONS, MOCK_HARDSHIP_RESPONSES } from '@/lib/mock/recommendations';

/**
 * Discriminated-union state machine for the single `GET /recommendations/{id}`
 * call that drives the entire Phase 4 UI.
 *
 * - `idle`    — initial render, no lookup has been attempted yet (UI-SPEC "Empty" state)
 * - `loading` — a lookup is in flight OR the mock branch is about to resolve synchronously
 *               (UI-SPEC "Loading" state — previous results cleared)
 * - `success` — 200 response parsed into a typed `RecommendationResponse`
 * - `error`   — any non-2xx status, client-side validation failure, network error,
 *               or mock-mode cache miss. `httpStatus` is keyed into `errorCopyForStatus`
 *               by the component layer; `0` signals "no HTTP response was received".
 */
export type RecommendationState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: RecommendationResponse; customerId: string }
  | { status: 'hardship'; data: HardshipResponse; customerId: string }
  | { status: 'error'; httpStatus: number; customerId: string };

/**
 * Single-source data hook for the Phase 4 agent-assist UI.
 *
 * Design decisions:
 *   - D-01: native `fetch`, no data-fetching library (one endpoint, one screen).
 *   - D-03: if `VITE_API_URL` is unset/empty, reads from the local MOCK_RECOMMENDATIONS
 *           fixture. Unknown IDs still surface as 404 so the error flow is demoable
 *           end-to-end without the backend deployed.
 *   - D-04: single fetch per lookup, no automatic re-attempt on failure. Operator
 *           re-submits via the form to trigger a fresh call.
 *   - UI-SPEC "Re-query": submitting a new ID CANCELS the in-flight request (via
 *           AbortController) AND clears previous results before the new request resolves
 *           so stale data is never shown during loading.
 *   - T-04-06 (injection): `encodeURIComponent` on the path segment; client regex gate
 *           means only `CUST-\d{3,6}` ever reaches URL construction anyway.
 *
 * Status-code-first parsing: `response.ok` is checked BEFORE `response.json()`. Non-200
 * response bodies may be `{error: string}` (see api_lambda/handler.py::_error) but the UI
 * discards that string and keys error copy off the status code in the component layer.
 */
export function useRecommendations() {
  const [state, setState] = useState<RecommendationState>({ status: 'idle' });
  const abortRef = useRef<AbortController | null>(null);

  const lookup = useCallback(async (rawId: string) => {
    // 1. Cancel any in-flight request — UI-SPEC "Re-query" state: stale data
    //    must not paint while a newer request is pending.
    abortRef.current?.abort();

    // 2. Normalize + client-side validate (D-10). Normalized form is what reaches
    //    both the error state's customerId echo and the URL path segment.
    const customerId = normalizeCustomerId(rawId);
    if (!CUSTOMER_ID_PATTERN.test(customerId)) {
      setState({ status: 'error', httpStatus: 400, customerId });
      return;
    }

    // 3. Clear previous results — the component layer shows skeletons immediately.
    setState({ status: 'loading' });

    // 4. Branch on VITE_API_URL (D-02 build-time env, D-03 mock fallback).
    //    Empty string OR undefined both map to mock mode. Any truthy origin
    //    string triggers a real fetch.
    const apiUrl = import.meta.env.VITE_API_URL;

    if (!apiUrl) {
      // Phase 14: check hardship mocks first.
      const hardshipData = MOCK_HARDSHIP_RESPONSES[customerId];
      if (hardshipData) {
        setState({ status: 'hardship', data: hardshipData, customerId });
        return;
      }
      const mockData = MOCK_RECOMMENDATIONS[customerId];
      if (!mockData) {
        // Unknown persona in mock mode — mirror the backend 404 so the UI's
        // error flow is exercised identically with or without the API.
        setState({ status: 'error', httpStatus: 404, customerId });
        return;
      }
      setState({ status: 'success', data: mockData, customerId });
      return;
    }

    // 5. Real API fetch. AbortController lets a later lookup pre-empt an
    //    older in-flight request so we don't paint stale data on re-query.
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const response = await fetch(
        `${apiUrl}/recommendations/${encodeURIComponent(customerId)}`,
        { signal: ctrl.signal },
      );

      if (!response.ok) {
        // Status-first branching — body is not read on non-200 paths. Operator
        // copy is owned by the UI (errors.ts::errorCopyForStatus), not the server.
        setState({ status: 'error', httpStatus: response.status, customerId });
        return;
      }

      const data = (await response.json()) as ApiResponse;
      if (isHardshipResponse(data)) {
        setState({ status: 'hardship', data, customerId });
      } else {
        setState({ status: 'success', data: data as RecommendationResponse, customerId });
      }
    } catch (err: unknown) {
      // Superseded requests resolve via AbortError — silently ignored so the
      // newer lookup's state is never overwritten by an older rejection.
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      // Network failure, DNS error, CORS preflight failure — no HTTP response
      // received. Status 0 keys the "generic server" copy in errorCopyForStatus.
      setState({ status: 'error', httpStatus: 0, customerId });
    }
  }, []);

  return { state, lookup } as const;
}
