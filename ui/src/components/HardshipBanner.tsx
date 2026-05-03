// Phase 14 AGENT-02: dignity-preserving hardship routing banner.
//
// Replaces the recommendation card grid when the API returns kind: "hardship".
// No tariff info, no savings figures, no plan IDs — just a routing message
// and a call script the operator reads verbatim.
//
// LD-7 kill-switch: if `?narrative=off` in the URL, the component renders
// null (same pattern as ReasoningTrace). The kill-switch collapses all v3.0
// surfaces to v2.0 shape.
//
// Accessibility: uses shadcn Alert with a non-destructive variant. The banner
// is a landmark region with aria-label for screen readers.
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { NARRATIVE_ENABLED } from '@/lib/flags';
import type { HardshipResponse } from '@/lib/types';

interface HardshipBannerProps {
  data: HardshipResponse;
}

export function HardshipBanner({ data }: HardshipBannerProps) {
  // LD-7 kill-switch — collapse to v2.0 shape (no hardship banner).
  if (!NARRATIVE_ENABLED) return null;

  return (
    <section aria-label="Hardship support routing">
      <Alert className="border-amber-500/50 bg-amber-50 dark:bg-amber-950/20">
        <AlertTitle className="text-amber-800 dark:text-amber-200 font-semibold">
          Specialist Support Required
        </AlertTitle>
        <AlertDescription className="mt-2 space-y-3">
          <p className="text-sm text-amber-700 dark:text-amber-300">
            {data.reason}
          </p>
          <blockquote className="border-l-2 border-amber-400 pl-3 italic text-sm text-amber-600 dark:text-amber-400">
            {data.call_script}
          </blockquote>
          <p className="text-xs text-muted-foreground">
            Routing to: {data.routing_target}
          </p>
        </AlertDescription>
      </Alert>
    </section>
  );
}
