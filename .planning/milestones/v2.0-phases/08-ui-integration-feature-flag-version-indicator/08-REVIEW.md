---
phase: 08-ui-integration-feature-flag-version-indicator
reviewed: 2026-04-26T00:00:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - ui/src/App.tsx
  - ui/src/components/RecommendationCard.test.tsx
  - ui/src/components/RecommendationCard.tsx
  - ui/src/components/RecommendationSkeletons.test.tsx
  - ui/src/components/RecommendationSkeletons.tsx
  - ui/src/components/VersionIndicator.test.tsx
  - ui/src/components/VersionIndicator.tsx
  - ui/src/lib/flags.test.ts
  - ui/src/lib/flags.ts
  - ui/src/lib/mock/recommendations.test.ts
  - ui/src/lib/mock/recommendations.ts
  - ui/src/lib/types.ts
  - ui/src/vite-env.d.ts
  - ui/vite.config.ts
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-04-26
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Phase 8 lands a tight, minimally invasive set of UI changes that faithfully implement the decisions recorded in `08-CONTEXT.md`:

- `TrackInfo` is extended with required `usage_narrative` / `call_script` (D-18), so TypeScript catches any forgotten field at the call-site.
- `flags.ts` is a one-line module-level read of `window.location.search`, case-sensitive on the literal `"off"` (D-09, D-13). Tests use the documented `vi.stubGlobal('location', …)` + `vi.resetModules()` + dynamic-import idiom consistently across the three places that consume it.
- `RecommendationCard.tsx` renders the narrative row between the savings grid and methodology line, and the `❝ … ❞` bordered quote block after the methodology line, with track-accent left border (emerald for Green, blue for Cheapest). Matches D-01/D-02/D-03 exactly, and the U+275D/U+275E quote marks are inline text per planner recommendation.
- `RecommendationSkeletons.tsx` mirrors the card shape in-place (D-06/D-07), and both the narrative and call_script placeholders are gated on `NARRATIVE_ENABLED`.
- `vite.config.ts` injects `__GIT_SHA__` via `execSync('git rev-parse --short HEAD')` inside a try/catch falling back to `"unknown"` — exactly the D-15 contract.
- `VersionIndicator.tsx` renders `v2.0 · <sha>` with U+00B7 MIDDLE DOT at `fixed bottom-2 right-2 z-50`, outside `<main>` in `App.tsx` (D-14, D-16, D-17).
- Mock fixtures are extended with all 6 persona narrative strings, and a new vitest mirrors the Phase 6 validator (no digit, no currency, word caps).

The D-10 "UI is byte-equivalent to v1.0 when flag is off" non-negotiable is correctly enforced: both the card (lines 83-85, 87-91 in `RecommendationCard.tsx`) and the skeleton (lines 38-43, 45-51 in `RecommendationSkeletons.tsx`) gate their respective v2.0 rows on the same `NARRATIVE_ENABLED` const, and both component tests exercise the `?narrative=off` path.

Two warnings and three info items follow. None are blockers; all are correctness-adjacent rough edges that are cheap to tighten before freeze.

## Warnings

### WR-01: Skeleton test selector over-matches — does not actually pin the narrative placeholder

**File:** `ui/src/components/RecommendationSkeletons.test.tsx:25-33, 54-59`

**Issue:** The "flag on" tests rely on `container.querySelector('.space-y-2')` / `container.querySelectorAll('.space-y-2')` to locate the narrative placeholder group. But `RecommendationSkeletons.tsx` line 46 also applies `space-y-2` to the call_script shell wrapper (`<div className="border-l-4 border-l-muted pl-4 py-2 space-y-2">`). As a result:

1. The comment at line 30-31 (`Two cards, each with a .space-y-2 narrative group`) is inaccurate — `querySelectorAll('.space-y-2')` actually returns 4 elements under flag-on (2 narrative groups + 2 call_script shells), not 2. The test still passes because it only checks `>= 2`.
2. The test at line 54-59 picks up the *first* `.space-y-2` — which happens to be the narrative group because it appears earlier in DOM order. Fragile: any future reordering of the skeleton children silently inverts the selection without failing the test loudly.
3. The flag-off test at line 81 (`expect(container.querySelector('.space-y-2')).toBeNull()`) currently passes only because BOTH groups are suppressed together. If a regression ever kept one and dropped the other, the assertion would still fail — which is OK — but a selector that actually pins the *narrative* group by its role would make failures easier to diagnose.

**Fix:** Use a more specific selector that distinguishes the narrative placeholder from the call_script shell. Either:

```tsx
// Option A: unique marker class on the narrative placeholder
// in RecommendationSkeletons.tsx
{NARRATIVE_ENABLED && (
  <div className="space-y-2" data-testid="narrative-skeleton">
    <Skeleton className="h-4 w-full" />
    <Skeleton className="h-4 w-4/5" />
  </div>
)}

// in RecommendationSkeletons.test.tsx
const narrativeGroups = container.querySelectorAll('[data-testid="narrative-skeleton"]');
expect(narrativeGroups.length).toBe(2);
```

```tsx
// Option B: scope via the wrapper that only wraps the narrative lines
// Select only .space-y-2 groups that are NOT inside a .border-l-muted shell:
const narrativeGroups = Array.from(
  container.querySelectorAll('.space-y-2')
).filter((el) => !el.closest('.border-l-muted'));
expect(narrativeGroups.length).toBe(2);
```

Option A is cheaper and survives future refactors. The test comment at line 30-31 should be updated to match reality either way.

### WR-02: `RecommendationCard.tsx` falls back to `"selected"` in methodology but still renders the raw empty `plan_name` in the "Recommended plan" row

**File:** `ui/src/components/RecommendationCard.tsx:48-49, 65`

**Issue:** Line 48 guards against an empty `plan_name` for the methodology template substitution (`const planName = data.plan_name || 'selected';`), but line 65 (`<p ...>{data.plan_name}</p>`) prints `data.plan_name` raw. Under the current Phase 6/7 contract the field is always non-empty, so this is not reachable in practice — but the asymmetric handling is misleading and a latent bug if the contract ever weakens (e.g. a future API field-renaming incident). Either both sites need the fallback, or neither does.

Worth noting that `TrackInfo.plan_name` is `string` (not `string | undefined`), so the `data.plan_name || 'selected'` guard on line 48 is already defensive-only — TypeScript cannot produce `undefined` here, only empty string. If you want the defensive branch, keep it; if you don't, drop it. Mixed is the worst of both worlds.

**Fix:** Pick one policy and apply it consistently.

```tsx
// Preferred: drop the fallback entirely — trust the Phase 6/7 non-empty contract (D-04).
const methodology = config.methodologyTemplate.replace('{plan_name}', data.plan_name);
```

Or, if belt-and-braces is worth keeping:

```tsx
const planName = data.plan_name || 'selected';
const methodology = config.methodologyTemplate.replace('{plan_name}', planName);
// ...
<p className={`text-lg font-semibold ${config.accentText}`}>{planName}</p>
```

## Info

### IN-01: `VersionIndicator` references the `__GIT_SHA__` global without a `typeof`-guard; vitest tests must always stub it

**File:** `ui/src/components/VersionIndicator.tsx:12`

**Issue:** The component renders `{__GIT_SHA__}` directly. Under `vite build` this is replaced by the `define` substitution, so production and dev are fine. Under vitest, `__GIT_SHA__` is NOT auto-injected, so every test has to stub it (`vi.stubGlobal('__GIT_SHA__', 'abc1234')`) before `vi.resetModules()` + dynamic import. `VersionIndicator.test.tsx` does this correctly in all three cases, but any future test that imports `VersionIndicator` statically (e.g. an App-level snapshot test) will ReferenceError.

No action required for Phase 8 (the current test file stubs it faithfully and no other import site exists), but worth a one-line safety net if you want to harden against future test authoring mistakes.

**Fix:** Either leave a comment on the export pointing to the test pattern, or add a typeof-guard default:

```tsx
export function VersionIndicator() {
  const sha = typeof __GIT_SHA__ !== 'undefined' ? __GIT_SHA__ : 'unknown';
  return (
    <span className="fixed bottom-2 right-2 z-50 text-xs text-muted-foreground opacity-60">
      v2.0 · {sha}
    </span>
  );
}
```

Minor tradeoff: this adds a tiny branch to the production bundle to protect a test-only failure mode. A test-setup-level `globalThis.__GIT_SHA__ ??= 'test'` in `src/test-setup.ts` is cheaper and keeps prod lean. Either is fine; the current code is acceptable.

### IN-02: `flags.ts` uses the bare `window` global, not `globalThis` — works under jsdom but slightly couples the module to the browser

**File:** `ui/src/lib/flags.ts:8-9`

**Issue:** The test file stubs `location` via `vi.stubGlobal('location', …)`, which sets `globalThis.location`. In jsdom (and real browsers) `window === globalThis`, so `window.location.search` resolves to the stubbed value and the tests pass. This is fine for the demo. However, if `flags.ts` is ever imported from a non-browser context (SSR, Node test harness without jsdom, future node-based prewarm script reusing the UI lib), it will hard-crash at module-load.

This is explicitly out of scope per the phase — Phase 8 is UI-only and there is no SSR — so this is purely a future-proofing note, not a Phase 8 defect.

**Fix (optional, not required to ship):**

```ts
export const NARRATIVE_ENABLED =
  typeof window === 'undefined'
    ? true
    : new URLSearchParams(window.location.search).get('narrative') !== 'off';
```

### IN-03: `VersionIndicator` comment references `personas.ts line 18` for the U+00B7 convention, but the callout is stale / unverifiable

**File:** `ui/src/components/VersionIndicator.tsx:5-6`

**Issue:** The comment reads "same convention as personas.ts line 18 and ROADMAP success criterion 4 verbatim." Line-number references in source comments are a known-fragile cross-reference pattern — a future unrelated edit to `personas.ts` can slide line 18 without anyone noticing, and the comment silently lies thereafter. The ROADMAP reference is better (cites the section, not the line).

**Fix:** Either drop the line number ("same convention as `personas.ts` persona labels"), or replace with the literal string being referenced:

```tsx
// Uses U+00B7 MIDDLE DOT as separator — same convention as personas.ts
// persona labels (e.g. "CUST-001 · Sarah") and ROADMAP success criterion 4 verbatim.
```

Same pattern risk is also in `types.ts` line 1 (`agent/agent.py::TrackInfo (lines 32-37)`) but that file is out of Phase 8's scope of change so it's not a new regression.

---

_Reviewed: 2026-04-26_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
