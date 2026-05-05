// Retention Queue Cohort Card — displays a single customer's risk signal
// with click-to-investigate affordance (same pattern as PersonaChips).
// Contains no LLM-generated content — safe to display when ?narrative=off.
import type { RiskSignal } from '@/lib/types';

interface CohortCardProps {
  signal: RiskSignal;
  onInvestigate: (customerId: string) => void;
}

/**
 * Risk level color coding based on score thresholds:
 *   - High (≥70): red accent
 *   - Medium (40-69): amber accent
 *   - Low (1-39): yellow accent
 *   - Zero (0): muted/grey
 */
function riskColor(score: number): string {
  if (score >= 70) return 'border-l-red-500';
  if (score >= 40) return 'border-l-amber-500';
  if (score >= 1) return 'border-l-yellow-500';
  return 'border-l-muted';
}

function riskBadgeColor(score: number): string {
  if (score >= 70) return 'bg-red-100 text-red-800';
  if (score >= 40) return 'bg-amber-100 text-amber-800';
  if (score >= 1) return 'bg-yellow-100 text-yellow-800';
  return 'bg-muted text-muted-foreground';
}

export function CohortCard({ signal, onInvestigate }: CohortCardProps) {
  return (
    <button
      type="button"
      className={`w-full text-left border border-border rounded-lg p-4 border-l-4 ${riskColor(signal.risk_score)} hover:bg-accent/50 transition-colors cursor-pointer`}
      onClick={() => onInvestigate(signal.customer_id)}
      aria-label={`Investigate ${signal.customer_id}`}
    >
      <div className="flex items-center justify-between">
        <span className="font-medium text-sm">{signal.customer_id}</span>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded ${riskBadgeColor(signal.risk_score)}`}>
          {signal.risk_score}
        </span>
      </div>
      <p className="text-sm text-muted-foreground mt-1">{signal.risk_summary}</p>
    </button>
  );
}
