import { useCallback, useRef, useState } from 'react';
import type { FollowUpEmailResponse } from '@/lib/types';
import { MOCK_FOLLOW_UP_RESPONSES } from '@/lib/mock/recommendations';

/**
 * State machine for the follow-up email draft workflow (Phase 15 WF-01).
 *
 * - `idle`    — no follow-up has been requested yet
 * - `loading` — follow-up request is in flight
 * - `success` — follow-up email draft received
 * - `error`   — follow-up request failed
 */
export type FollowUpState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: FollowUpEmailResponse }
  | { status: 'error'; httpStatus: number };

/**
 * Data hook for the follow-up email draft workflow.
 *
 * Calls `GET /recommendations/{customerId}/follow-up` and returns the
 * draft email response. Mock fallback when VITE_API_URL is unset.
 */
export function useFollowUp() {
  const [state, setState] = useState<FollowUpState>({ status: 'idle' });
  const abortRef = useRef<AbortController | null>(null);

  const fetchFollowUp = useCallback(async (customerId: string) => {
    // Cancel any in-flight request.
    abortRef.current?.abort();

    setState({ status: 'loading' });

    const apiUrl = import.meta.env.VITE_API_URL;

    // Mock mode — same pattern as useRecommendations.
    if (!apiUrl) {
      const mockData = MOCK_FOLLOW_UP_RESPONSES[customerId];
      if (!mockData) {
        setState({ status: 'error', httpStatus: 404 });
        return;
      }
      setState({ status: 'success', data: mockData });
      return;
    }

    // Real API fetch.
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const response = await fetch(
        `${apiUrl}/recommendations/${encodeURIComponent(customerId)}/follow-up`,
        { signal: ctrl.signal },
      );

      if (!response.ok) {
        setState({ status: 'error', httpStatus: response.status });
        return;
      }

      const data = (await response.json()) as FollowUpEmailResponse;
      setState({ status: 'success', data });
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      setState({ status: 'error', httpStatus: 0 });
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState({ status: 'idle' });
  }, []);

  return { state, fetchFollowUp, reset } as const;
}
