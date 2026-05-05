// Agentic Actions Portfolio — ActionCard component.
// Renders a single Confirmable_Action with Confirm (primary) and Dismiss (ghost) buttons.
// States: default, loading, success (confirmed), dismissed (collapsed), error.
// Validates: Requirements 4.1–4.8 (Action Card UI Component).
import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Check, Loader2 } from 'lucide-react';
import type { ConfirmableAction } from '@/lib/types';

type ActionCardState = 'default' | 'confirming' | 'dismissing' | 'success' | 'dismissed' | 'error';

/** Human-readable label derived from action_type + payload. */
function getActionLabel(action: ConfirmableAction): string {
  switch (action.action_type) {
    case 'tariff_switch':
      return `Switch to ${(action.payload.plan_name as string) || 'new plan'}`;
    case 'send_sms':
      return 'Send SMS follow-up';
    case 'payment_plan_offer': {
      const installments = action.payload.proposed_installments as number | undefined;
      return installments
        ? `Offer payment plan (${installments} instalments)`
        : 'Offer payment plan';
    }
    default:
      return 'Pending action';
  }
}

interface ActionCardProps {
  action: ConfirmableAction;
}

export function ActionCard({ action }: ActionCardProps) {
  const [cardState, setCardState] = useState<ActionCardState>('default');
  const [errorMessage, setErrorMessage] = useState<string>('');

  const apiBase = import.meta.env.VITE_API_URL || '';

  const handleConfirm = async () => {
    setCardState('confirming');
    setErrorMessage('');
    try {
      const res = await fetch(`${apiBase}/actions/${action.action_id}/confirm`, {
        method: 'POST',
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ error: 'Request failed' }));
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      setCardState('success');
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Request failed');
      setCardState('error');
    }
  };

  const handleDismiss = async () => {
    setCardState('dismissing');
    setErrorMessage('');
    try {
      const res = await fetch(`${apiBase}/actions/${action.action_id}/dismiss`, {
        method: 'POST',
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ error: 'Request failed' }));
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      setCardState('dismissed');
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Request failed');
      setCardState('error');
    }
  };

  // Dismissed state: collapse card from view (Req 4.5).
  if (cardState === 'dismissed') {
    return null;
  }

  const isLoading = cardState === 'confirming' || cardState === 'dismissing';
  const isDisabled = isLoading || cardState === 'success';

  return (
    <Card className="border-l-4 border-l-primary" data-testid={`action-card-${action.action_id}`}>
      <CardContent className="flex items-center justify-between gap-4 py-4">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{getActionLabel(action)}</p>
          {cardState === 'success' && (
            <p className="text-xs text-emerald-600 flex items-center gap-1 mt-1" data-testid="success-indicator">
              <Check className="h-3 w-3" /> Confirmed
            </p>
          )}
          {cardState === 'error' && errorMessage && (
            <p className="text-xs text-destructive mt-1" data-testid="error-message">
              {errorMessage}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button
            size="sm"
            disabled={isDisabled}
            onClick={handleConfirm}
            aria-label={`Confirm ${getActionLabel(action)}`}
          >
            {cardState === 'confirming' && <Loader2 className="h-4 w-4 animate-spin" />}
            Confirm
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={isDisabled}
            onClick={handleDismiss}
            aria-label={`Dismiss ${getActionLabel(action)}`}
          >
            {cardState === 'dismissing' && <Loader2 className="h-4 w-4 animate-spin" />}
            Dismiss
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
