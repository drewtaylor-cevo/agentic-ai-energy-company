// Retention Queue — portfolio-level landing page that replaces EmptyState
// when state.status === 'idle'. Fetches GET /retention-queue on mount and
// displays ranked CohortCards. Contains no LLM-generated content — safe to
// display when ?narrative=off is active (Req 8.7).
import { useEffect, useState } from 'react';
import type { RetentionQueueResponse } from '@/lib/types';
import { CohortCard } from '@/components/CohortCard';

interface RetentionQueueProps {
  onInvestigate: (customerId: string) => void;
}

type QueueState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; data: RetentionQueueResponse };

export function RetentionQueue({ onInvestigate }: RetentionQueueProps) {
  const [queueState, setQueueState] = useState<QueueState>({ status: 'loading' });

  useEffect(() => {
    const controller = new AbortController();

    async function fetchQueue() {
      try {
        const apiUrl = import.meta.env.VITE_API_URL || '';
        const response = await fetch(`${apiUrl}/retention-queue`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          setQueueState({ status: 'error', message: `Failed to load retention queue (HTTP ${response.status})` });
          return;
        }

        const data = (await response.json()) as RetentionQueueResponse;
        setQueueState({ status: 'success', data });
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setQueueState({ status: 'error', message: 'Unable to load retention queue' });
      }
    }

    fetchQueue();
    return () => controller.abort();
  }, []);

  if (queueState.status === 'loading') {
    return (
      <div className="text-center py-12" role="status" aria-label="Loading retention queue">
        <p className="text-muted-foreground">Loading retention queue…</p>
      </div>
    );
  }

  if (queueState.status === 'error') {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold">No customer selected</h2>
        <p className="text-muted-foreground mt-2">
          Enter a customer ID to see tariff recommendations.
        </p>
      </div>
    );
  }

  const { data } = queueState;
  const atRiskCount = data.queue.filter((s) => s.risk_score > 0).length;

  return (
    <div className="py-4">
      <h2 className="text-xl font-semibold mb-4">
        {atRiskCount} customer{atRiskCount !== 1 ? 's' : ''} at risk today
      </h2>
      <div className="grid gap-3">
        {data.queue.map((signal) => (
          <CohortCard
            key={signal.customer_id}
            signal={signal}
            onInvestigate={onInvestigate}
          />
        ))}
      </div>
    </div>
  );
}
