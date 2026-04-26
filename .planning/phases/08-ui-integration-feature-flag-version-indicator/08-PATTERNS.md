# Phase 8: UI Integration + Feature Flag + Version Indicator — Pattern Map

**Mapped:** 2026-04-26
**Files analyzed:** 13 (6 new, 7 modified)
**Analogs found:** 13 / 13

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `ui/src/lib/types.ts` | type-module | n/a (pure types) | self (in-place extension) | exact |
| `ui/src/lib/mock/recommendations.ts` | fixture-module | n/a (static data) | self (in-place extension) | exact |
| `ui/src/components/RecommendationCard.tsx` | component | request-response (presentational) | self (in-place extension) | exact |
| `ui/src/components/RecommendationSkeletons.tsx` | component | request-response (presentational) | self (in-place extension) | exact |
| `ui/src/App.tsx` | component (root composition) | state-driven | self (minor edit: add one render) | exact |
| `ui/vite.config.ts` | config | n/a (build-time) | self (in-place extension) | exact |
| `ui/src/vite-env.d.ts` | type-declaration (global) | n/a | **net-new** (file does not exist); pattern from `tsconfig.app.json` `types: ["vite/client"]` | net-new |
| `ui/src/lib/flags.ts` | lib-module (single-const, module-level init) | build-/runtime-constant | `ui/src/lib/validate.ts` (single-const export + module-level RegExp), `ui/src/personas.ts` (const-only module) | role-match |
| `ui/src/components/VersionIndicator.tsx` | component (trivial, presentational) | n/a (reads module global) | `ui/src/components/EmptyState.tsx` (simplest component, no props) | exact |
| `ui/src/components/RecommendationCard.test.tsx` | test (component) | n/a | **no direct analog** (no component test exists yet); closest setup pattern from `ui/src/hooks/useRecommendations.test.ts` + `ui/src/personas.test.ts` | net-new |
| `ui/src/components/RecommendationSkeletons.test.tsx` | test (component) | n/a | same as above | net-new |
| `ui/src/components/VersionIndicator.test.tsx` | test (component, globalThis mock) | n/a | `ui/src/hooks/useRecommendations.test.ts` (`vi.stubGlobal`, `vi.restoreAllMocks`) | role-match |
| `ui/src/lib/mock/recommendations.test.ts` | test (data-rules iteration) | n/a | `ui/src/personas.test.ts` (iterates const, asserts regex rules) | exact |
| `ui/src/lib/flags.test.ts` | test (module reset + window.location mock) | n/a | `ui/src/hooks/useRecommendations.test.ts` (stubEnv/stubGlobal pattern) — no prior `window.location` mock in codebase | partial |

## Pattern Assignments

### `ui/src/lib/types.ts` (type-module) — MODIFY IN PLACE

**Analog:** self (`ui/src/lib/types.ts` lines 1–21)

**Comment header convention** (lines 1–3) — keep in extended file:
```typescript
// Mirrors agent/agent.py::TrackInfo (lines 32-37) and ::RecommendationResponse (lines 40-43).
// Field names are snake_case to match the JSON wire format — do NOT camelCase.
// If the backend schema changes, update this file in the same commit.
```

**Existing `TrackInfo` shape** (lines 4–9) — extend *inside* this interface with two required string fields; do not introduce a new type:
```typescript
export interface TrackInfo {
  plan_id: string;
  plan_name: string;
  saving_monthly: number;
  saving_annual: number;
}
```

**Extension rule (D-18):** new fields `usage_narrative: string` and `call_script: string` are REQUIRED (not optional) so `tsc -b` catches any test/mock/component site that forgets them. Snake-case preserved per the header comment.

---

### `ui/src/lib/mock/recommendations.ts` (fixture-module) — MODIFY IN PLACE

**Analog:** self (`ui/src/lib/mock/recommendations.ts` lines 1–28)

**Existing header-comment convention** (lines 1–14) — the pre-existing comment already defines the "update both this map AND the Python fixtures in the same commit" rule. Phase 8 EXTENDS this comment to cover `agent/narrative/fallbacks.py` (D-19 / D-20):
```typescript
import type { RecommendationResponse } from '../types';

// Values ported from tests/conftest.py:47-100 (mock_savings_response,
// mock_marcus_response, mock_elena_response). These MUST stay in sync with the
// deterministic output of lambda/handler.py::simulate_savings_pure for each
// persona (verified in tests/test_simulate_savings.py).
//
// DEMO-02 flagship: CUST-001 (Sarah) Green ~$30/mo, Cheapest ~$55/mo — these
// numbers are load-bearing for the demo narrative. If the backend savings
// formula changes, update both this map AND the Python fixtures in the same
// commit.
//
// Plan IDs are always `ECO` (green) and `VAL` (cheapest) across all personas —
// the backend invariant asserted by tests/test_agent_smoke.py:81-85.
```

**Existing fixture shape** (lines 15–28) — the entry-per-persona record. Extend each `green` and `cheapest` object *in place* with the two new string fields. Do not restructure:
```typescript
export const MOCK_RECOMMENDATIONS: Record<string, RecommendationResponse> = {
  'CUST-001': {
    green:    { plan_id: 'ECO', plan_name: 'EcoFlex 100', saving_monthly: 30.00, saving_annual: 360.00 },
    cheapest: { plan_id: 'VAL', plan_name: 'Value 12',    saving_monthly: 55.00, saving_annual: 660.00 },
  },
  'CUST-002': { /* ... */ },
  'CUST-003': { /* ... */ },
};
```

**Source of truth for the 6 strings (D-19):** copy verbatim (byte-for-byte) from `agent/narrative/fallbacks.py` lines 15–48. Reference table:

| Persona | Track | Field | Source line | Canonical value |
|---------|-------|-------|-------------|-----------------|
| CUST-001 | green | usage_narrative | fallbacks.py:19 | `"Strong cool-season usage with a family-sized load across the year."` |
| CUST-001 | green | call_script | fallbacks.py:20 | `"Ask about EcoFlex — it suits a strong winter-heating profile like yours."` |
| CUST-001 | cheapest | usage_narrative | fallbacks.py:23 | `"Consistently high household consumption with cool-season peaks."` |
| CUST-001 | cheapest | call_script | fallbacks.py:24 | `"Bring up Value Twelve — a budget-first pick for a high-usage home."` |
| CUST-002 | green | usage_narrative | fallbacks.py:30 | `"Mid-range apartment usage with gentle seasonal variation across the year."` |
| CUST-002 | green | call_script | fallbacks.py:31 | `"Ask about EcoFlex — a steady, eco-aligned option for a mid-range home."` |
| CUST-002 | cheapest | usage_narrative | fallbacks.py:34 | `"Moderate apartment consumption with only mild cool-season lifts."` |
| CUST-002 | cheapest | call_script | fallbacks.py:35 | `"Bring up Value Twelve — a cost-led pick for a mid-range apartment."` |
| CUST-003 | green | usage_narrative | fallbacks.py:41 | `"Summer-peak household profile with cooling-driven demand in warm months."` |
| CUST-003 | green | call_script | fallbacks.py:42 | `"Ask about EcoFlex — an eco-aligned fit for a summer-peak cooling load."` |
| CUST-003 | cheapest | usage_narrative | fallbacks.py:45 | `"Warm-season heavy with light winter usage and a cooling-led pattern."` |
| CUST-003 | cheapest | call_script | fallbacks.py:46 | `"Bring up Value Twelve — a cost-led option for a warm-season household."` |

**Watch-out:** the call_script strings use em-dash `—` (U+2014). Do NOT normalize to hyphen-minus. Paste with care.

---

### `ui/src/components/RecommendationCard.tsx` (component) — MODIFY IN PLACE

**Analog:** self (`ui/src/components/RecommendationCard.tsx` lines 1–85)

**Existing imports block** (lines 1–11) — the pattern to extend. Phase 8 adds `import { NARRATIVE_ENABLED } from '@/lib/flags';` beside the existing `@/lib/types` import:
```typescript
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Leaf, PiggyBank } from 'lucide-react';
import type { TrackInfo } from '@/lib/types';
```

**Existing `TRACK_CONFIG` shape** (lines 13–32) — the data-driven per-track map. Phase 8 MUST extend this same map rather than introduce ternaries in JSX (D-03 + "Claude's Discretion" recommends inline match via the existing pattern). Add exactly ONE new key per track: `accentBorderLeft` (matches the naming of the existing `accentBorder` which is `border-t-*`):
```typescript
const TRACK_CONFIG = {
  green: {
    heading: 'Green Option',
    badge: '100% renewable',
    icon: Leaf,
    accentBorder: 'border-t-emerald-600',
    accentText: 'text-emerald-600',
    methodologyTemplate:
      'Based on your 12-month kWh usage at the {plan_name} rate (100% renewable).',
  },
  cheapest: {
    heading: 'Cheapest Option',
    badge: 'Lowest unit price',
    icon: PiggyBank,
    accentBorder: 'border-t-blue-600',
    accentText: 'text-blue-600',
    methodologyTemplate:
      'Based on your 12-month kWh usage at the {plan_name} rate (lowest unit price).',
  },
} as const;
```
Phase 8 adds `accentBorderLeft: 'border-l-emerald-600'` / `'border-l-blue-600'` per track. Data-driven: the JSX references `config.accentBorderLeft` — no track-branch `if`.

**Existing `CardContent` structure** (lines 59–81) — the `space-y-4` pattern with the savings grid + methodology paragraph. Phase 8 extends this block with two new nodes in the explicit D-01 order (plan-name → savings-grid → **narrative** → methodology → **call_script**):
```typescript
<CardContent className="space-y-4">
  <div>
    <p className="text-sm font-semibold text-muted-foreground">Recommended plan</p>
    <p className={`text-lg font-semibold ${config.accentText}`}>{data.plan_name}</p>
  </div>
  <div className="grid grid-cols-2 gap-4">
    <div>
      <p className="text-sm font-semibold text-muted-foreground">Monthly saving</p>
      <p className="text-2xl font-semibold">
        ${data.saving_monthly.toFixed(2)}
        <span className="text-sm font-normal text-muted-foreground">/mo</span>
      </p>
    </div>
    <div>
      <p className="text-sm font-semibold text-muted-foreground">Annual saving</p>
      <p className="text-2xl font-semibold">
        ${data.saving_annual.toFixed(2)}
        <span className="text-sm font-normal text-muted-foreground">/yr</span>
      </p>
    </div>
  </div>
  <p className="text-sm text-muted-foreground">{methodology}</p>
</CardContent>
```

**Narrative-row pattern to add (D-02 + D-10):** italic, muted, text-sm, no label, no border. Inserted *between* the savings grid and the methodology paragraph. Wrap with `NARRATIVE_ENABLED` short-circuit:
```tsx
{NARRATIVE_ENABLED && (
  <p className="text-sm italic text-muted-foreground">{data.usage_narrative}</p>
)}
```

**Call-script block pattern to add (D-03 + D-10):** bordered left quote block, track-accent border via `config.accentBorderLeft`, `pl-4 py-2`, `text-base`, inline `❝ … ❞` (U+275D / U+275E — "Claude's Discretion" recommends inline text over pseudo-elements). Inserted *after* the methodology paragraph (last visible block):
```tsx
{NARRATIVE_ENABLED && (
  <blockquote className={`border-l-4 ${config.accentBorderLeft} pl-4 py-2 text-base`}>
    ❝ {data.call_script} ❞
  </blockquote>
)}
```

**Equal-cards contract reminder** (existing file header comment lines 1–7): the component stays track-agnostic. The ONLY per-track visual difference introduced is the `accentBorderLeft` color — identical to how `accentBorder` / `accentText` already vary. This preserves REC-03.

---

### `ui/src/components/RecommendationSkeletons.tsx` (component) — MODIFY IN PLACE

**Analog:** self (`ui/src/components/RecommendationSkeletons.tsx` lines 1–43)

**Existing imports block** (lines 7–8) — extend with `import { NARRATIVE_ENABLED } from '@/lib/flags';`:
```typescript
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
```

**Existing skeleton tree shape** (lines 10–43) — the 1:1 mirror of `RecommendationCard`'s content. Phase 8 adds the narrative placeholder *between* the savings-grid and the existing methodology placeholder (the `Skeleton h-4 w-full` on line 37), and the call_script placeholder *after* the existing methodology placeholder. Existing structure to extend:
```tsx
<CardContent className="space-y-4">
  <div>
    <Skeleton className="h-4 w-32" />
    <Skeleton className="h-6 w-40 mt-1" />
  </div>
  <div className="grid grid-cols-2 gap-4">
    <div>
      <Skeleton className="h-4 w-28" />
      <Skeleton className="h-8 w-24 mt-1" />
    </div>
    <div>
      <Skeleton className="h-4 w-28" />
      <Skeleton className="h-8 w-24 mt-1" />
    </div>
  </div>
  <Skeleton className="h-4 w-full" />
</CardContent>
```

**Narrative placeholder (D-06):** 2 lines matching typical narrative wrap at `text-sm`. Wrap in the same `NARRATIVE_ENABLED` gate so `?narrative=off` produces a v1.0-shaped skeleton (D-10 non-negotiable):
```tsx
{NARRATIVE_ENABLED && (
  <div className="space-y-2">
    <Skeleton className="h-4 w-full" />
    <Skeleton className="h-4 w-4/5" />
  </div>
)}
```

**Call-script placeholder (D-06):** shell-matched — wrap 3 lines in the same `border-l-4 border-l-muted pl-4` shell the final render uses (use muted border while loading, not the track-accent, because the skeleton is track-agnostic in this file). 3 lines matching `text-base` wrap:
```tsx
{NARRATIVE_ENABLED && (
  <div className="border-l-4 border-l-muted pl-4 py-2 space-y-2">
    <Skeleton className="h-5 w-full" />
    <Skeleton className="h-5 w-5/6" />
    <Skeleton className="h-5 w-3/5" />
  </div>
)}
```

**Inline rule (D-07):** do NOT extract a `NarrativeSkeleton` sub-component. Placeholders stay inline here so the "skeleton mirrors final card shape" rule stays auditable in one file.

**Grid-shell rule (file header comment lines 1–6):** the outer `grid grid-cols-1 md:grid-cols-2 gap-8` MUST stay identical to `App.tsx`'s success-state grid (App.tsx line 63). Do not change it.

---

### `ui/src/App.tsx` (root composition) — MINOR EDIT

**Analog:** self (`ui/src/App.tsx` lines 1–75)

**Existing imports block** (lines 22–28) — add `import { VersionIndicator } from '@/components/VersionIndicator';` beside the other `@/components/*` imports:
```typescript
import { useRecommendations } from '@/hooks/useRecommendations';
import { LookupForm } from '@/components/LookupForm';
import { PersonaChips } from '@/components/PersonaChips';
import { RecommendationCard } from '@/components/RecommendationCard';
import { RecommendationSkeletons } from '@/components/RecommendationSkeletons';
import { ErrorAlert } from '@/components/ErrorAlert';
import { EmptyState } from '@/components/EmptyState';
```

**Existing root shell** (lines 34–72) — render `<VersionIndicator />` as a SIBLING of `<main>`, inside the outer `<div className="min-h-screen …">` so it does not participate in the centered `max-w-4xl` column layout (D-17):
```tsx
return (
  <div className="min-h-screen bg-background text-foreground">
    <main className="mx-auto max-w-4xl px-6 py-16">
      {/* … existing children unchanged … */}
    </main>
  </div>
);
```

Phase 8 pattern (insert as the last child of the outer `<div>`, after `</main>`):
```tsx
return (
  <div className="min-h-screen bg-background text-foreground">
    <main className="mx-auto max-w-4xl px-6 py-16">
      {/* existing children unchanged */}
    </main>
    <VersionIndicator />
  </div>
);
```

No other edit in `App.tsx`. No `narrativeEnabled` prop plumbing (D-12).

---

### `ui/vite.config.ts` (config) — MODIFY IN PLACE

**Analog:** self (`ui/vite.config.ts` lines 1–20)

**Existing `defineConfig` structure** — single top-level `defineConfig` call with `plugins`, `resolve.alias`, `test`. Phase 8 adds a top-level `define` property between `resolve` and `test` (conventional ordering; Vite treats them as peers):
```typescript
/// <reference types="vitest/config" />
import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
})
```

**Extension pattern (D-15):** SHA resolution at config-load time inside a try/catch. Import `execSync` at the top (alongside `path`), compute `gitSha` once at module load, embed via `define` with `JSON.stringify` (required by Vite so the emitted JS is a valid string literal):
```typescript
import { execSync } from 'node:child_process'

let gitSha: string
try {
  gitSha = execSync('git rev-parse --short HEAD').toString().trim()
} catch {
  gitSha = 'unknown'
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  define: {
    __GIT_SHA__: JSON.stringify(gitSha),
  },
  test: { /* unchanged */ },
})
```

**Watch-outs:**
- `execSync` returns a `Buffer` by default in Node; the `.toString().trim()` chain is mandatory.
- `JSON.stringify(gitSha)` (NOT raw `gitSha`) — this is a Vite contract, not an optional sanity step.
- Node 24 (`@types/node: ^24`) in `package.json` supports both `require('child_process')` and the ESM `import { execSync } from 'node:child_process'`. Prefer the ESM form to match the existing `import path from 'node:path'` convention on line 2.
- Both `build` and `build:mock` (package.json scripts) share this file — one `define` automatically covers both.

---

### `ui/src/vite-env.d.ts` (type-declaration) — NEW FILE

**Status:** net-new (file does not currently exist — verified by filesystem scan).
**Analog:** `tsconfig.app.json` already lists `"types": ["vite/client"]`, so Vite's built-in client types (including `ImportMeta.env`) are already present. Phase 8 adds a project-local declaration for `__GIT_SHA__`.

**Pattern (D-15 + "Claude's Discretion"):** a triple-slash reference to `vite/client` (canonical Vite template boilerplate) plus a `declare const __GIT_SHA__: string;` global. Because `tsconfig.app.json::include = ["src"]`, dropping this file in `src/` automatically picks it up without any tsconfig edit.
```typescript
/// <reference types="vite/client" />

declare const __GIT_SHA__: string;
```

**Why this file, not `build-info.d.ts`:** the `tsconfig.app.json::types: ["vite/client"]` entry already covers Vite's module augmentations; this file is for project-local build-time globals. Colocating both in one file matches Vite template convention and keeps the declaration footprint discoverable.

---

### `ui/src/lib/flags.ts` (lib-module) — NEW FILE

**Analogs:**
1. `ui/src/lib/validate.ts` lines 1–8 — single-const-at-module-load pattern (`CUSTOMER_ID_PATTERN` is a module-level RegExp, evaluated once at import).
2. `ui/src/personas.ts` lines 10–19 — single-const-only module pattern (exported `const` is the entire module surface).

**Imports pattern** (from `validate.ts`) — NO imports needed for `flags.ts` (pure built-in `URLSearchParams` + `window.location`). Matches the zero-import ethos of `personas.ts`.

**Comment-header convention** (from `validate.ts` lines 1–3):
```typescript
// Must match api_lambda/handler.py:27 and lambda/handler.py:39 exactly.
// Defense-in-depth: the API has the identical regex; this client gate just
// prevents a wasted round-trip for obviously-malformed IDs.
export const CUSTOMER_ID_PATTERN = /^CUST-\d{3,6}$/;
```

**Phase 8 file pattern (D-09 + D-13 + "Claude's Discretion"):**
```typescript
// Runtime feature flag (UI-06, D-09–D-13): the URL query parameter
// `?narrative=off` suppresses the v2.0 usage-narrative + call-script rows
// (AND their skeleton placeholders) so the UI collapses to its v1.0 shape
// without a redeploy. Evaluated exactly once at module load — no React
// state, no context, no hook. Case-sensitive match on the literal "off".
export const NARRATIVE_ENABLED =
  new URLSearchParams(window.location.search).get('narrative') !== 'off';
```

**Testability hook:** the module-level const is evaluated on import, so tests must `vi.resetModules()` AFTER setting `window.location.search`, then dynamically `import()` to force re-evaluation (see `flags.test.ts` pattern below).

---

### `ui/src/components/VersionIndicator.tsx` (component) — NEW FILE

**Analog:** `ui/src/components/EmptyState.tsx` lines 1–12 (simplest existing component: no props, single element, file-header comment).

**EmptyState pattern to mirror:**
```typescript
// Rendered when state.status === 'idle'. Copy verbatim from UI-SPEC
// §Copywriting lines 111-112.
export function EmptyState() {
  return (
    <div className="text-center py-12">
      <h2 className="text-xl font-semibold">No customer selected</h2>
      <p className="text-muted-foreground mt-2">
        Enter a customer ID to see tariff recommendations.
      </p>
    </div>
  );
}
```

**Phase 8 file pattern (D-14 + D-16 + D-17):** same shape — zero props, one element, `export function`, file-header comment referencing the decision IDs. Reads the build-time `__GIT_SHA__` global (typed by `vite-env.d.ts`):
```tsx
// Bottom-right fixed build marker (UI-07, D-14–D-17). Embedded at build time
// via `define: { __GIT_SHA__ }` in vite.config.ts; renders `v2.0 · <7-char-sha>`
// so the presenter can verify at demo time which bundle is live. Uses middle-dot
// U+00B7 (matches the persona chip label convention from personas.ts).
export function VersionIndicator() {
  return (
    <span className="fixed bottom-2 right-2 z-50 text-xs text-muted-foreground opacity-60">
      v2.0 · {__GIT_SHA__}
    </span>
  );
}
```

**Watch-outs:**
- `z-50` is required (Tailwind `fixed` has no default z-index; future modals/toasts would occlude the marker — see CONTEXT.md external/upstream docs note).
- Separator is U+00B7 MIDDLE DOT (matches `personas.ts` label convention line 18 and ROADMAP success criterion 4 verbatim).
- Bottom-right, NOT top-right (D-14: DevTools docked-right at 1280px collide with top-right).

---

### `ui/src/components/RecommendationCard.test.tsx` (test) — NEW FILE

**Status:** net-new — no existing `*.test.tsx` component test in the codebase (verified by `find ui/src -name "*.test.*"`: only `personas.test.ts`, `useRecommendations.test.ts`, `validate.test.ts`).

**Analogs for setup/structure:**
1. `ui/src/hooks/useRecommendations.test.ts` lines 1–21 — test imports + `beforeEach` / `vi.restoreAllMocks` / `vi.unstubAllGlobals` pattern.
2. `ui/src/personas.test.ts` lines 1–28 — describe/it structure with `import { describe, it, expect } from 'vitest';` and `it.each` for parametrized cases.

**Imports block to combine (net-new for this project: adds `@testing-library/react`'s `render` + `screen` — deps already in package.json):**
```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RecommendationCard } from './RecommendationCard';
import type { TrackInfo } from '@/lib/types';
```

**Fixture builder pattern (small local factory, mirrors `MOCK_SUCCESS` in `useRecommendations.test.ts` lines 10–13):**
```typescript
const trackFixture = (overrides: Partial<TrackInfo> = {}): TrackInfo => ({
  plan_id: 'ECO',
  plan_name: 'EcoFlex 100',
  saving_monthly: 30.0,
  saving_annual: 360.0,
  usage_narrative: 'Strong cool-season usage with a family-sized load across the year.',
  call_script: 'Ask about EcoFlex — it suits a strong winter-heating profile like yours.',
  ...overrides,
});
```

**beforeEach reset pattern (copied from useRecommendations.test.ts lines 15–21):**
```typescript
beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.resetModules();
});
```

**Query patterns for the 4 required assertions (D-21):**
- Presence of narrative text: `expect(screen.getByText(/strong cool-season/i)).toBeInTheDocument();`
- Presence of call_script text: `expect(screen.getByText(/ask about ecoflex/i)).toBeInTheDocument();`
- DOM ORDER assertion (narrative between savings-grid and methodology): use `render(...).container.textContent` OR query all `<p>` / `<blockquote>` and assert index ordering. Suggested pattern:
  ```typescript
  const { container } = render(<RecommendationCard track="green" data={trackFixture()} />);
  const text = container.textContent ?? '';
  const savingsIdx = text.indexOf('/mo');
  const narrativeIdx = text.indexOf('Strong cool-season');
  const methodologyIdx = text.indexOf('Based on your 12-month');
  const scriptIdx = text.indexOf('Ask about EcoFlex');
  expect(savingsIdx).toBeLessThan(narrativeIdx);
  expect(narrativeIdx).toBeLessThan(methodologyIdx);
  expect(methodologyIdx).toBeLessThan(scriptIdx);
  ```
- Track-accent class assertion: `expect(container.querySelector('blockquote')).toHaveClass('border-l-emerald-600');` (for track=green) or `'border-l-blue-600'` (for track=cheapest). `toHaveClass` comes from `@testing-library/jest-dom`, already wired via `src/test-setup.ts`.

**`?narrative=off` suppression test — module-reset pattern (D-09 testability hook + D-21):**
```typescript
it('hides narrative and call_script when ?narrative=off is in the URL', async () => {
  // 1. Stub window.location BEFORE importing flags.ts or RecommendationCard.
  vi.stubGlobal('location', { search: '?narrative=off' } as Location);
  // 2. Reset the module registry so flags.ts re-evaluates on next import.
  vi.resetModules();
  // 3. Dynamic import — picks up the stubbed window.location.
  const { RecommendationCard: FreshCard } = await import('./RecommendationCard');
  render(<FreshCard track="green" data={trackFixture()} />);
  expect(screen.queryByText(/strong cool-season/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/ask about ecoflex/i)).not.toBeInTheDocument();
});
```

---

### `ui/src/components/RecommendationSkeletons.test.tsx` (test) — NEW FILE

**Same analog + import pattern** as `RecommendationCard.test.tsx` above.

**Default-render assertion pattern:**
```typescript
it('renders narrative + call_script placeholder rows by default', () => {
  const { container } = render(<RecommendationSkeletons />);
  // 2 placeholder-group selectors: narrative's `.space-y-2` block + call_script's `border-l-4` shell.
  const narrativeGroup = container.querySelector('.space-y-2');
  const scriptShell = container.querySelector('.border-l-muted');
  expect(narrativeGroup).toBeInTheDocument();
  expect(scriptShell).toBeInTheDocument();
});
```

**Flag-off pattern:** identical `vi.stubGlobal('location', …)` + `vi.resetModules()` + dynamic import as the card test. Assert `container.querySelector('.border-l-muted')` returns null.

---

### `ui/src/components/VersionIndicator.test.tsx` (test) — NEW FILE

**Analog:** `ui/src/hooks/useRecommendations.test.ts` lines 15–21 — the `vi.stubGlobal` + `beforeEach` reset pattern, plus `vi.restoreAllMocks()`.

**Globalthis-mock pattern (D-21):** `__GIT_SHA__` is a compile-time Vite `define` — at test time it's NOT defined by Vite (the `define` only runs during `vite build` / `vite dev`, not under `vitest run` by default). The test must set it on `globalThis` BEFORE `import`-ing the component. Two options:

**Option A — inline stub with `vi.stubGlobal` (matches `useRecommendations.test.ts` line 37 pattern):**
```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.resetModules();
});

it('renders "v2.0 · <sha>" using the injected __GIT_SHA__ global', async () => {
  vi.stubGlobal('__GIT_SHA__', 'abc1234');
  vi.resetModules();
  const { VersionIndicator } = await import('./VersionIndicator');
  render(<VersionIndicator />);
  expect(screen.getByText(/v2\.0 · abc1234/)).toBeInTheDocument();
});
```

**Option B — `vite.config.ts::test.define`:** add a matching `define` under the `test` key so `__GIT_SHA__` is present during vitest. Lower-ceremony but less explicit per-test. Planner decides; recommend Option A to keep the test self-contained and matching the existing `vi.stubGlobal` convention.

---

### `ui/src/lib/mock/recommendations.test.ts` (test) — NEW FILE

**Analog:** `ui/src/personas.test.ts` lines 1–28 — iterate-a-const + assert-shape-and-rules pattern. Direct match for "iterate every entry, assert regex/word-count rules."

**Personas pattern to mirror:**
```typescript
import { describe, it, expect } from 'vitest';
import { PERSONAS } from './personas';
import { CUSTOMER_ID_PATTERN } from './lib/validate';

describe('PERSONAS', () => {
  it('has exactly 3 entries (matches Phase 1 seed data)', () => {
    expect(PERSONAS).toHaveLength(3);
  });

  it('all IDs satisfy CUSTOMER_ID_PATTERN', () => {
    for (const p of PERSONAS) {
      expect(CUSTOMER_ID_PATTERN.test(p.id)).toBe(true);
    }
  });
  /* ... */
});
```

**Phase 8 file pattern (D-21 last bullet — UI-layer mirror of `test_fallbacks_pass_validator`):**
```typescript
import { describe, it, expect } from 'vitest';
import { MOCK_RECOMMENDATIONS } from './recommendations';

// Mirrors agent/tests/test_fallbacks_pass_validator.py: every committed
// narrative + call_script string must pass the Phase 6 validator rules
// (no digit, no currency/percent, word-count cap). Catches mock-authoring
// drift if someone pastes a `$` or a digit into the fixture during rehearsal.

const FORBIDDEN = /[\d$£€%]/;
const countWords = (s: string) => s.trim().split(/\s+/).length;

describe('MOCK_RECOMMENDATIONS narrative + call_script validator rules', () => {
  for (const [customerId, response] of Object.entries(MOCK_RECOMMENDATIONS)) {
    for (const track of ['green', 'cheapest'] as const) {
      const info = response[track];
      describe(`${customerId} / ${track}`, () => {
        it('usage_narrative is present and non-empty', () => {
          expect(info.usage_narrative.length).toBeGreaterThan(0);
        });
        it('usage_narrative contains no digit, currency, or percent', () => {
          expect(FORBIDDEN.test(info.usage_narrative)).toBe(false);
        });
        it('usage_narrative is ≤ 20 words', () => {
          expect(countWords(info.usage_narrative)).toBeLessThanOrEqual(20);
        });
        it('call_script is present and non-empty', () => {
          expect(info.call_script.length).toBeGreaterThan(0);
        });
        it('call_script contains no digit, currency, or percent', () => {
          expect(FORBIDDEN.test(info.call_script)).toBe(false);
        });
        it('call_script is ≤ 22 words', () => {
          expect(countWords(info.call_script)).toBeLessThanOrEqual(22);
        });
      });
    }
  }
});
```

**Naming convention:** file sits adjacent to its source per the "test adjacent to source" convention (Phase 4 lineage). Location: `ui/src/lib/mock/recommendations.test.ts` (NOT the alternative `recommendations-rules.test.ts` — adjacency + `.test.ts` suffix matches every existing test file).

---

### `ui/src/lib/flags.test.ts` (test) — NEW FILE

**Analog:** `ui/src/hooks/useRecommendations.test.ts` — the `vi.stubEnv` / `vi.stubGlobal` / `vi.restoreAllMocks` / `vi.unstubAllGlobals` pattern. No existing `window.location` mock in the codebase, so this is partially net-new; the idiom below is the standard vitest pattern for module-level init guarded by `window.location.search`.

**beforeEach reset block (copy from useRecommendations.test.ts lines 15–21):**
```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest';

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.resetModules();
});
```

**Per-test pattern (D-13 + D-09):** stub `window.location`, reset modules, dynamic import, assert:
```typescript
it('NARRATIVE_ENABLED is true when the query param is absent', async () => {
  vi.stubGlobal('location', { search: '' } as Location);
  vi.resetModules();
  const { NARRATIVE_ENABLED } = await import('./flags');
  expect(NARRATIVE_ENABLED).toBe(true);
});

it('NARRATIVE_ENABLED is false when ?narrative=off is present', async () => {
  vi.stubGlobal('location', { search: '?narrative=off' } as Location);
  vi.resetModules();
  const { NARRATIVE_ENABLED } = await import('./flags');
  expect(NARRATIVE_ENABLED).toBe(false);
});

it.each([
  ['?narrative=on',    true],
  ['?narrative=0',     true],
  ['?narrative=false', true],
  ['?narrative=OFF',   true], // D-13: case-sensitive; OFF != off
  ['?other=off',       true],
])('NARRATIVE_ENABLED is true for non-exact match "%s"', async (search, expected) => {
  vi.stubGlobal('location', { search } as Location);
  vi.resetModules();
  const { NARRATIVE_ENABLED } = await import('./flags');
  expect(NARRATIVE_ENABLED).toBe(expected);
});
```

**Why `vi.stubGlobal('location', …)`:** jsdom's `window.location` is normally read-only on assignment but `vi.stubGlobal` handles the writable-flag dance. `vi.resetModules()` is mandatory — without it, the `flags.ts` module is cached with its first-evaluation const value and subsequent imports return the stale value.

---

## Shared Patterns

### Module-level single-const init

**Sources:**
- `ui/src/lib/validate.ts` lines 4, 8 — `CUSTOMER_ID_PATTERN`, `DASHLESS_PATTERN` (module-level RegExp consts).
- `ui/src/personas.ts` lines 15–19 — `PERSONAS` (module-level frozen array).

**Apply to:** `ui/src/lib/flags.ts` (new `NARRATIVE_ENABLED`), `ui/src/components/VersionIndicator.tsx` (consumes `__GIT_SHA__` module-global), `ui/vite.config.ts` (module-level `gitSha` const computed once at config load).

**Pattern:** constant evaluated exactly once on module load, consumed directly by importers. No React state, no hooks, no lazy init, no singleton boxing. Testable via `vi.resetModules()` + dynamic `import()` for re-evaluation.

---

### File-header comment with decision references

**Sources:**
- `ui/src/components/RecommendationCard.tsx` lines 1–7 (references UI-SPEC §Color lines 88–94, REC-03).
- `ui/src/components/RecommendationSkeletons.tsx` lines 1–6 (references UI-SPEC grid contract).
- `ui/src/App.tsx` lines 1–21 (references UI-SPEC §Interaction States, §Specifics, §Color, §Typography, §Spacing, plus CONTEXT.md D-08, D-12).
- `ui/src/lib/validate.ts` lines 1–3 (references `api_lambda/handler.py:27` + `lambda/handler.py:39`).
- `ui/src/lib/mock/recommendations.ts` lines 1–14 (references `tests/conftest.py:47-100`, DEMO-02, `tests/test_agent_smoke.py:81-85`).
- `ui/src/hooks/useRecommendations.ts` lines 6–43 (references D-01, D-03, D-04, UI-SPEC "Re-query", T-04-06, handler.py).

**Apply to:** every new file (`flags.ts`, `VersionIndicator.tsx`, all 4 new test files, `vite-env.d.ts`). Minimum: one-paragraph opening comment citing the governing decision IDs (D-09, D-14, D-18, etc.) from `08-CONTEXT.md` and the upstream source (Phase 6 `fallbacks.py`, Phase 7 API contract) where relevant.

---

### Snake-case wire contract, snake-case TS fields

**Source:** `ui/src/lib/types.ts` lines 1–3 header comment + lines 4–9 `TrackInfo` interface.

**Apply to:** extended `TrackInfo` in Phase 8 (`usage_narrative`, `call_script` — NOT `usageNarrative` / `callScript`). Tests, mocks, and component render sites all reference the snake-case fields.

---

### vitest imports block convention

**Sources:**
- `ui/src/personas.test.ts` line 1 — `import { describe, it, expect } from 'vitest';`
- `ui/src/hooks/useRecommendations.test.ts` line 2 — `import { beforeEach, describe, expect, it, vi } from 'vitest';`
- `ui/src/lib/validate.test.ts` line 1 — `import { describe, it, expect } from 'vitest';`

**Apply to:** all 4 new test files. Import only what the file uses. `@testing-library/react`'s `render` / `screen` / `renderHook` are imported from `@testing-library/react` (see `useRecommendations.test.ts` line 1) — already in `package.json::devDependencies`.

---

### Module-reset + dynamic-import for module-level-init testing

**Source partial:** `ui/src/hooks/useRecommendations.test.ts` lines 15–21 (`vi.restoreAllMocks() / vi.unstubAllGlobals() / vi.unstubAllEnvs()` beforeEach). No existing module-reset test, so the `vi.resetModules()` + `await import(...)` pattern is net-new but idiomatic vitest usage.

**Apply to:** `flags.test.ts` (re-evaluate `NARRATIVE_ENABLED` after each `window.location` stub), `RecommendationCard.test.tsx` flag-off case, `RecommendationSkeletons.test.tsx` flag-off case, `VersionIndicator.test.tsx` (re-evaluate after `vi.stubGlobal('__GIT_SHA__', …)`).

**Pattern:**
```typescript
beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.resetModules();
});

it('…', async () => {
  vi.stubGlobal('location', { search: '?narrative=off' } as Location);
  vi.resetModules();
  const { Thing } = await import('./module-under-test');
  // … assertions
});
```

---

### `space-y-4` content rhythm + track-agnostic component

**Source:** `ui/src/components/RecommendationCard.tsx` line 59 — `<CardContent className="space-y-4">` sets the vertical rhythm, and the same class is repeated on the skeleton (`RecommendationSkeletons.tsx` line 22).

**Apply to:** new narrative + call_script rows in both files. Default to the same `space-y-4` — the parent class already provides vertical gap; individual rows do NOT add `mt-*` except where D-01 visual grouping demands tightening (e.g., narrative tight-under savings; the default `space-y-4` gap is acceptable). "Claude's Discretion" allows visual tightening during D-23 UAT.

---

### Track-agnostic component, data-driven per-track styling

**Source:** `ui/src/components/RecommendationCard.tsx` lines 13–32 — `TRACK_CONFIG` map with one entry per track key; JSX references `config.*` rather than branching on `track === 'green'`.

**Apply to:** Phase 8's new `accentBorderLeft` token. Add as a sibling key on `TRACK_CONFIG`; do NOT add a track-ternary in JSX. Preserves the equal-cards contract audit surface (REC-03).

---

## No Analog Found (net-new patterns for this codebase)

| File | Role | Reason | What fills the gap |
|------|------|--------|--------------------|
| `ui/src/vite-env.d.ts` | type-declaration | File does not currently exist | Canonical Vite template boilerplate: `/// <reference types="vite/client" />` + `declare const __GIT_SHA__: string;` |
| `ui/src/components/*.test.tsx` (3 files) | `.test.tsx` component tests | No component test exists yet in the project — all existing tests are `.test.ts` (pure-function or hook tests) | Combine `@testing-library/react` `render` + `screen` imports (already used by `useRecommendations.test.ts` via `renderHook`) with the describe/it structure from `personas.test.ts` |
| `window.location` mocking (across 4 test files) | test setup idiom | No existing test mocks `window.location` | Idiomatic vitest pattern: `vi.stubGlobal('location', { search: '…' } as Location)` + `vi.resetModules()` before dynamic `import()` |

## Metadata

**Analog search scope:** `ui/src/` (all 20 `.ts`/`.tsx` files), `ui/*.ts` (vite.config.ts, tsconfig*.json), `agent/narrative/fallbacks.py` (source of truth for mock strings).
**Files scanned:** 14 source files read; filesystem traversal of `ui/src/`, `ui/src/components/`, `ui/src/components/ui/`, `ui/src/lib/`, `ui/src/lib/mock/`, `ui/src/hooks/`, `agent/narrative/`.
**Pattern extraction date:** 2026-04-26

---

## PATTERN MAPPING COMPLETE

**Phase:** 08 — UI Integration + Feature Flag + Version Indicator
**Files classified:** 13
**Analogs found:** 13 / 13

### Coverage
- Files with exact analog (self-modify or direct match): 9
- Files with role-match analog: 3
- Files with partial / net-new pattern: 1 (`window.location` mocking idiom)

### Key Patterns Identified
- **Data-driven per-track styling via `TRACK_CONFIG` map** — new `accentBorderLeft` joins the existing `accentBorder` / `accentText` / `methodologyTemplate` keys rather than inline JSX ternaries. Preserves the equal-cards (REC-03) audit surface.
- **Skeleton mirrors final card shape inline** — `RecommendationSkeletons` stays a single file; new placeholder rows slot into the exact grid position of the final rendered rows, with the same `border-l-4` shell where the final render has one. No sub-component extraction (D-07).
- **Module-level single-const init** — `flags.ts::NARRATIVE_ENABLED` and the `__GIT_SHA__` Vite define both evaluate once at module/config load. Tests re-evaluate via `vi.resetModules()` + dynamic `import()`.
- **vitest + testing-library + jsdom**, no new deps — all `@testing-library/react` primitives (`render`, `screen`, `renderHook`) are already available; component tests are net-new to this project but use the library's standard patterns.
- **Snake-case wire contract preserved** — `usage_narrative` / `call_script` on the TS `TrackInfo` match the JSON body byte-for-byte (Phase 6 → Phase 7 → Phase 8).
- **File-header comment with decision references** — every new file opens with a paragraph citing the governing decision IDs (D-09, D-14, D-18) plus upstream sources.

### File Created
`/Users/drewtaylor/Documents/Cevo/Customer-Tariff/.planning/phases/08-ui-integration-feature-flag-version-indicator/08-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns in PLAN.md files — every new file has a concrete imports block, structural template, and either an exact or role-match source to copy from.
