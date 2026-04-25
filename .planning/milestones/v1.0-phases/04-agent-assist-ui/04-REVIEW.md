---
phase: 04-agent-assist-ui
reviewed: 2026-04-24T00:00:00Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - ui/src/App.tsx
  - ui/src/index.css
  - ui/src/test-setup.ts
  - ui/src/components/EmptyState.tsx
  - ui/src/components/ErrorAlert.tsx
  - ui/src/components/LookupForm.tsx
  - ui/src/components/PersonaChips.tsx
  - ui/src/components/RecommendationCard.tsx
  - ui/src/components/RecommendationSkeletons.tsx
  - ui/src/hooks/useRecommendations.ts
  - ui/src/hooks/useRecommendations.test.ts
  - ui/src/lib/errors.ts
  - ui/src/lib/mock/recommendations.ts
  - ui/src/lib/types.ts
  - ui/src/lib/utils.ts
  - ui/src/lib/validate.ts
  - ui/src/lib/validate.test.ts
  - ui/src/personas.ts
  - ui/src/personas.test.ts
  - ui/vite.config.ts
  - ui/index.html
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-04-24
**Depth:** standard
**Files Reviewed:** 21
**Status:** issues_found

## Summary

Phase 4 implementation is high-quality, well-commented, and closely tracks the UI-SPEC and CONTEXT decisions. The XSS threat model (T-04-09 / T-04-12) is satisfied — every server-controlled string (`plan_name`, methodology substitution, `customerId` echo in error copy) is rendered through React JSX text nodes only; no `dangerouslySetInnerHTML`, `innerHTML`, `eval`, or `new Function` appears anywhere in the reviewed code. The no-retry decision (D-04) is respected. Client-side normalization (D-10) is correct and covered by tests. The hook's AbortController pattern prevents stale-data paints on re-query, and the status-first parse path (T-04-06-adjacent) avoids trusting non-200 bodies.

One warning is worth flagging: response-shape validation is weaker than the threat-model wording ("fail gracefully on malformed payloads", T-04-04). `await response.json() as RecommendationResponse` is a compile-time type assertion, not a runtime schema check, and `RecommendationCard` invokes `data.saving_monthly.toFixed(2)` and `data.saving_annual.toFixed(2)` without null-safety. A malformed 200 response (missing field, wrong type) will throw at render time and show a blank screen instead of the error alert. Two smaller ergonomic items are called out at Info level.

## Warnings

### WR-01: Runtime shape of 200 response is not validated — malformed payload crashes card render

**File:** `ui/src/hooks/useRecommendations.ts:99-100`, `ui/src/components/RecommendationCard.tsx:68,75`

**Issue:** The hook parses the 200 body with a TypeScript type assertion only:

```ts
const data = (await response.json()) as RecommendationResponse;
setState({ status: 'success', data, customerId });
```

There is no runtime check that `data.green` / `data.cheapest` exist, or that `saving_monthly` / `saving_annual` are numbers. `RecommendationCard` then calls `data.saving_monthly.toFixed(2)` (line 68) and `data.saving_annual.toFixed(2)` (line 75) directly. If the backend returns a 200 with a malformed body — for example `{ "green": { "plan_name": "EcoFlex 100" } }` (missing numeric fields) or a non-object — `.toFixed` is called on `undefined` and throws `TypeError: Cannot read properties of undefined (reading 'toFixed')`. Because this happens inside React render and there is no Error Boundary at any level (App.tsx wraps the tree only in `<div>`/`<main>`), the entire operator panel goes blank rather than surfacing the spec's error alert.

This is a weak spot on threat T-04-04 ("fail gracefully on malformed payloads"). It is a low-likelihood issue for the current fixed backend, but it is the kind of failure a live-call operator has no recovery path for (F5 reload is the only option).

**Fix:** Add a lightweight runtime shape check in the hook; treat a shape failure as `httpStatus: 500`-equivalent so it flows through the existing error alert path. No schema library needed:

```ts
function isValidTrack(t: unknown): t is TrackInfo {
  return typeof t === 'object' && t !== null
    && typeof (t as TrackInfo).plan_id === 'string'
    && typeof (t as TrackInfo).plan_name === 'string'
    && typeof (t as TrackInfo).saving_monthly === 'number'
    && typeof (t as TrackInfo).saving_annual === 'number'
    && Number.isFinite((t as TrackInfo).saving_monthly)
    && Number.isFinite((t as TrackInfo).saving_annual);
}

// inside lookup(), replacing lines 99-100:
const data = (await response.json()) as unknown;
if (
  typeof data !== 'object' || data === null
  || !isValidTrack((data as RecommendationResponse).green)
  || !isValidTrack((data as RecommendationResponse).cheapest)
) {
  setState({ status: 'error', httpStatus: 500, customerId });
  return;
}
setState({ status: 'success', data: data as RecommendationResponse, customerId });
```

This keeps the existing error-alert path intact (the 500 copy "Something went wrong on our end. Try again — if it persists, contact support." is the right operator-facing copy for a malformed payload) and costs ~10 lines.

An alternative lighter fix — defensive `Number(data.saving_monthly ?? 0).toFixed(2)` at render — is cheaper but silently renders `$0.00` for a broken payload, which is worse for operator trust on a live call. Prefer the hook-level guard.

## Info

### IN-01: Disabled PersonaChips still have `cursor-pointer` and `hover:bg-accent` styles

**File:** `ui/src/components/PersonaChips.tsx:31`

**Issue:** The chip's className is `"cursor-pointer hover:bg-accent px-3 py-1 text-sm"` unconditionally. When `disabled` is true, the click and keydown handlers correctly no-op (lines 19, 32), but the pointer cursor and hover color still apply, so during a loading lookup the chips look clickable even though they aren't. Minor UX inconsistency, not a bug.

**Fix:** Tie the visual affordance to the `disabled` prop:

```tsx
className={`px-3 py-1 text-sm ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:bg-accent'}`}
```

### IN-02: `abortRef.current` is never cleared after a completed lookup

**File:** `ui/src/hooks/useRecommendations.ts:84`

**Issue:** After a successful or error-returning fetch, `abortRef.current` still holds the completed `AbortController`. The next lookup calls `abortRef.current?.abort()` on an already-resolved controller — this is a harmless no-op in every browser AbortController implementation, but it does mean the ref holds a small amount of non-garbage-collectible state between lookups. Not a correctness issue; flagged for future cleanup.

**Fix (optional):** Clear the ref after the fetch resolves (or in a `finally`):

```ts
try {
  // ...existing fetch + setState logic
} catch (err: unknown) {
  // ...
} finally {
  if (abortRef.current === ctrl) abortRef.current = null;
}
```

The guard ensures a newer request that has already replaced `abortRef.current` is not accidentally cleared.

---

_Reviewed: 2026-04-24_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
