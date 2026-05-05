// Phase 13 D-26 / D-27 / D-28: collapsed-by-default reasoning-trace disclosure.
//
// Placement: ABOVE the 2-column card grid in App.tsx (D-28 — trace is
// turn-level, shared across both cards).
//
// UI-01 contract: collapsed state is ONE row showing only tool NAMES.
// Numbers / dollar amounts / dates live in the EXPANDED state.
//
// LD-7 kill-switch: if `?narrative=off` in the URL, the component renders
// `null` (same pattern as RecommendationCard's narrative + call_script).
// The kill-switch is evaluated ONCE at flags.ts module load — do NOT read
// the URL directly in this component (module-load semantics are load-bearing
// for test isolation; see ReasoningTrace.test.tsx).
//
// D-11 EXEMPTION: expanded summaries intentionally contain digits, `$`,
// percentages, and dates — do NOT apply narrative validators.
//
// Streaming progressive rendering (Task 7.5, Requirements 5.2, 5.6):
// When `isStreaming` is true, the component renders already-received trace
// steps alongside a skeleton indicator for the next expected step. The trace
// array grows incrementally as the parent passes new entries — React re-renders
// within one animation frame. When streaming completes (isStreaming=false),
// the component renders all entries in the standard disclosure pattern.
import { useState } from 'react';
import { NARRATIVE_ENABLED } from '@/lib/flags';
import { Skeleton } from '@/components/ui/skeleton';
import type { ReasoningTraceEntry } from '@/lib/types';

interface ReasoningTraceProps {
  trace: ReasoningTraceEntry[];
  /** When true, shows a skeleton indicator alongside received entries. */
  isStreaming?: boolean;
}

export function ReasoningTrace({ trace, isStreaming = false }: ReasoningTraceProps) {
  // Hook must be called unconditionally (React Rules of Hooks) — guards
  // below short-circuit rendering, not state creation.
  const [expanded, setExpanded] = useState(false);

  // LD-7 kill-switch — checked FIRST so empty list is also null under ?narrative=off.
  if (!NARRATIVE_ENABLED) return null;

  // During streaming: show skeleton even if no entries have arrived yet.
  // When not streaming: empty-list short-circuit (single-tool personas render zero vertical cost).
  if (!isStreaming && (!trace || trace.length === 0)) return null;

  // Streaming with no entries yet — show only the skeleton loading indicator.
  if (isStreaming && (!trace || trace.length === 0)) {
    return (
      <section className="mb-4" aria-label="Agent reasoning trace">
        <div className="flex items-center gap-2" data-testid="trace-streaming-skeleton">
          <Skeleton className="h-4 w-4 rounded" />
          <Skeleton className="h-4 w-48" />
        </div>
      </section>
    );
  }

  const toolNames = trace.map((entry) => entry.tool);
  const chevron = expanded ? '▼' : '▶';
  const stepCount = isStreaming ? `${trace.length}+` : `${trace.length}`;
  const label = `${chevron} ${stepCount} steps: ${toolNames.join(' → ')}`;

  return (
    <section className="mb-4" aria-label="Agent reasoning trace">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
        className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1 font-mono"
      >
        {label}
      </button>
      {expanded && (
        <ol className="mt-2 ml-6 list-decimal text-sm space-y-1 text-foreground">
          {trace.map((entry, idx) => (
            <li key={`${entry.tool}-${idx}`}>
              <span className="font-mono text-muted-foreground">
                {entry.tool}:
              </span>{' '}
              <span>{entry.summary}</span>
            </li>
          ))}
          {isStreaming && (
            <li key="streaming-skeleton" data-testid="trace-step-skeleton">
              <div className="flex items-center gap-2">
                <Skeleton className="h-3 w-24 inline-block" />
                <Skeleton className="h-3 w-40 inline-block" />
              </div>
            </li>
          )}
        </ol>
      )}
      {/* Collapsed streaming indicator — visible when collapsed and still streaming */}
      {!expanded && isStreaming && (
        <div className="mt-1 ml-1 flex items-center gap-2" data-testid="trace-streaming-indicator">
          <Skeleton className="h-3 w-3 rounded-full" />
          <span className="text-xs text-muted-foreground">Analysing…</span>
        </div>
      )}
    </section>
  );
}
