import { useState } from 'react';
import type { FollowUpState } from '@/hooks/useFollowUp';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';

interface FollowUpDrawerProps {
  /** Current follow-up state from useFollowUp hook. */
  state: FollowUpState;
  /** Trigger the follow-up email draft fetch. */
  onDraft: () => void;
  /** Whether the ?narrative=off kill switch is active. */
  narrativeOff?: boolean;
}

/**
 * Phase 15 WF-01: Follow-up email drawer.
 *
 * Renders below the recommendation cards. Shows a "Draft follow-up email"
 * button; on click, fetches the draft and renders an editable email form.
 *
 * ?narrative=off → component renders null (LD-7 single-flag contract).
 */
export function FollowUpDrawer({ state, onDraft, narrativeOff }: FollowUpDrawerProps) {
  const [editedBody, setEditedBody] = useState('');
  const [copied, setCopied] = useState(false);

  // LD-7: ?narrative=off collapses this surface entirely.
  if (narrativeOff) return null;

  const handleCopy = async () => {
    if (state.status !== 'success') return;
    const text = `Subject: ${state.data.subject}\n\n${editedBody || state.data.body}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API may fail in some contexts — silent fallback.
    }
  };

  return (
    <div className="mt-8" role="region" aria-label="Follow-up email draft">
      {/* Idle state: show the draft button */}
      {state.status === 'idle' && (
        <Button
          onClick={onDraft}
          variant="outline"
          className="w-full"
          aria-label="Draft follow-up email for this customer"
        >
          Draft follow-up email
        </Button>
      )}

      {/* Loading state: skeleton */}
      {state.status === 'loading' && (
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-48" />
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-9 w-32" />
          </CardContent>
        </Card>
      )}

      {/* Error state */}
      {state.status === 'error' && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">
              Unable to generate follow-up email. Please try again.
            </p>
            <Button
              onClick={onDraft}
              variant="outline"
              size="sm"
              className="mt-3"
            >
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Success state: editable email draft */}
      {state.status === 'success' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">
              Follow-up email draft
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Subject (read-only) */}
            <div>
              <label
                htmlFor="follow-up-subject"
                className="text-sm font-medium text-muted-foreground"
              >
                Subject
              </label>
              <p
                id="follow-up-subject"
                className="mt-1 text-sm"
              >
                {state.data.subject}
              </p>
            </div>

            {/* Body (editable) */}
            <div>
              <label
                htmlFor="follow-up-body"
                className="text-sm font-medium text-muted-foreground"
              >
                Body
              </label>
              <Textarea
                id="follow-up-body"
                className="mt-1 min-h-[120px]"
                defaultValue={state.data.body}
                onChange={(e) => setEditedBody(e.target.value)}
                aria-label="Email body — edit before sending"
              />
            </div>

            {/* Plan reference (informational) */}
            <p className="text-xs text-muted-foreground">
              Referencing: {state.data.plan_reference}
            </p>

            {/* Copy to clipboard */}
            <Button
              onClick={handleCopy}
              variant="secondary"
              size="sm"
              aria-label="Copy email to clipboard"
            >
              {copied ? 'Copied!' : 'Copy to clipboard'}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
