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
import { useState } from 'react';
import { NARRATIVE_ENABLED } from '@/lib/flags';
import type { ReasoningTraceEntry } from '@/lib/types';

interface ReasoningTraceProps {
  trace: ReasoningTraceEntry[];
}

export function ReasoningTrace({ trace }: ReasoningTraceProps) {
  // Hook must be called unconditionally (React Rules of Hooks) — guards
  // below short-circuit rendering, not state creation.
  const [expanded, setExpanded] = useState(false);

  // LD-7 kill-switch — checked FIRST so empty list is also null under ?narrative=off.
  if (!NARRATIVE_ENABLED) return null;

  // Empty-list short-circuit — single-tool personas render zero vertical cost.
  if (!trace || trace.length === 0) return null;

  const toolNames = trace.map((entry) => entry.tool);
  const chevron = expanded ? '▼' : '▶';
  const label = `${chevron} ${trace.length} steps: ${toolNames.join(' → ')}`;

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
        </ol>
      )}
    </section>
  );
}
