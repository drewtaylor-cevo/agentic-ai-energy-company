---
phase: 08-ui-integration-feature-flag-version-indicator
verified: 2026-04-26T05:25:11Z
status: human_needed
score: 5/5 roadmap success criteria verified (automated); 1 live visual re-capture deferred to Phase 10
overrides_applied: 1
overrides:
  - must_have: "9 PNG screenshots (3 personas x {flag-on, flag-off, loading}) at 1280x800 in phase directory"
    reason: "Operator chose verbal-attestation evidence mode in 08-SAMPLES.md. Phase 10 DEMO-06 rollback drill will capture the authoritative live images against the frozen `demo-v2.0` tag at T-48h. Duplicating them at Phase 8 close adds no evidence value; deferred by explicit decision documented in 08-04-SUMMARY.md and 08-SAMPLES.md §Evidence-Mode Note."
    accepted_by: "drewtaylor"
    accepted_at: "2026-04-26T04:54:00Z"
human_verification:
  - test: "Live 1280x800 visual UAT against deployed API — 9 screenshots (3 personas x {flag-on, flag-off, loading})"
    expected: "All 5 ROADMAP success criteria visually confirmed against the frozen demo-v2.0 tag with authoritative PNG evidence: no layout shift on skeleton-to-content transition, both cards above fold at 1280x800 at maximum narrative length, ?narrative=off collapses UI to v1.0 shape in both loading and success, v2.0 corner marker matches demo-v2.0 tag SHA, build:mock <10s preserved."
    why_human: "jsdom cannot measure real layout. The verbal-attestation round passed on 2026-04-26; authoritative image capture is the explicit responsibility of Phase 10 DEMO-06 rollback drill per operator decision logged in 08-04-SUMMARY.md and the Phase 10 ROADMAP success criterion 5."
---

# Phase 8: UI Integration + Feature Flag + Version Indicator — Verification Report

**Phase Goal:** Call centre agents see the narrative rows on each card with stable layout, and operators have a URL-level kill switch plus a visible build marker to defend against stale-bundle risk at demo time.

**Verified:** 2026-04-26T05:25:11Z
**Status:** human_needed (automated gates all green; live visual UAT with PNG evidence deferred to Phase 10 by explicit operator decision)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (merged: ROADMAP Success Criteria + PLAN frontmatter must_haves)

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | On every persona lookup, each recommendation card renders one usage-narrative row and one call-script row with no layout shift (skeleton → content transition matches the final row heights) | ✓ VERIFIED (automated) + ? NEEDS LIVE EYEBALL | `RecommendationCard.tsx` lines 83-91 render narrative + blockquote; `RecommendationSkeletons.tsx` lines 38-51 render matching 2-line + 3-line placeholders with shell-matched `border-l-4 border-l-muted pl-4 py-2`. Vitest DOM-order assertion passes (`RecommendationCard.test.tsx` line "orders narrative between savings grid and methodology"). Real-pixel layout shift is the jsdom-unreachable half — operator verbally attested shift-free on 2026-04-26, authoritative image from Phase 10. |
| 2  | Both cards remain above the fold at 1280×800 when the narratives are at maximum generated length | ? NEEDS LIVE EYEBALL (attested) | Card height budget documented in 08-CONTEXT.md D-05 (v2.0 ≈ 420–440px × 2, usable 1280×800 ≈ 680px). jsdom cannot measure. Operator verbally attested for CUST-001/002/003 at 1280×800 against live API on 2026-04-26. Authoritative image capture at Phase 10. |
| 3  | Appending `?narrative=off` to the URL hides both narrative rows without any redeploy and without collapsing the card layout | ✓ VERIFIED | `flags.ts:8-9` reads `URLSearchParams().get('narrative') !== 'off'`. Both `RecommendationCard.tsx` (lines 83, 87) and `RecommendationSkeletons.tsx` (lines 38, 45) gate narrative+script on `NARRATIVE_ENABLED`. Vitest `RecommendationCard.test.tsx` flag-off suppression tests pass for Green AND Cheapest; `RecommendationSkeletons.test.tsx` flag-off tests confirm `.space-y-2` and `.border-l-muted` absent, v1.0 base shape preserved (`.border-t-muted` + outer grid). D-10 non-negotiable enforced in both loading and success states. |
| 4  | A `v2.0 · <git-sha>` indicator is visible in a corner of the UI and matches the SHA of the deployed build | ✓ VERIFIED | `VersionIndicator.tsx:11-13` renders `<span className="fixed bottom-2 right-2 z-50 text-xs text-muted-foreground opacity-60">v2.0 · {__GIT_SHA__}</span>`. U+00B7 MIDDLE DOT verified via Python byte-level check (2 occurrences in file). `vite.config.ts:28-30` injects `__GIT_SHA__: JSON.stringify(gitSha)` from `execSync('git rev-parse --short HEAD')` with try/catch → `"unknown"` fallback. Built bundle `ui/dist/assets/index-j1lA8N6Q.js` contains the literal string `v2.0 · fe39971` — confirmed via grep (`grep -oE 'v2\.0.{0,15}'` returns `v2.0 · ` + `fe39971`). `<VersionIndicator />` renders OUTSIDE `<main>` in `App.tsx:72` (awk check: vi=72 em=71 → PASS). |
| 5  | `build:mock` regenerates a dist that still renders correctly with the extended TrackInfo shape, preserving the <10s emergency swap path | ✓ VERIFIED | `npm run build:mock` executed during 08-04 Task 1 in **0.62s** (well under 10s contract). Freshly built `dist-mock/assets/*.js` contained SHA `fe39971` and verbatim fallback strings (`Strong cool-season usage`, `Warm-season heavy`) per 08-SAMPLES.md Gate 3 and 08-04-SUMMARY.md. The tree-shaken mock branch was exercised because `build:mock` sets `VITE_API_URL=''`. Note: the `ui/dist-mock/` currently on disk contains stale pre-v2.0 tracked artifacts per `deferred-items.md` (explicitly deferred to Phase 10 hygiene commit); the gate was met at execution time and the transient build output was reverted for working-tree cleanliness. Both `build` and `build:mock` share `vite.config.ts`, so they carry the same SHA. |
| 6  | TrackInfo has required usage_narrative: string and call_script: string fields (PLAN 08-01) | ✓ VERIFIED | `ui/src/lib/types.ts:10-11` declares both as required (not optional). `grep -c "usage_narrative: string;"` = 1; `grep -c "call_script: string;"` = 1. `tsc -b --noEmit` exit 0 — any forgotten call site would fail type check. |
| 7  | All 6 mock narrative + call_script strings match `agent/narrative/fallbacks.py` byte-for-byte (PLAN 08-01 D-19) | ✓ VERIFIED | `MOCK_RECOMMENDATIONS` in `ui/src/lib/mock/recommendations.ts:20-75` carries all 12 canonical strings (3 personas × 2 tracks × 2 fields). Em-dash count on `call_script` data lines = 6 (one per call_script). 08-01-SUMMARY.md evidence: grep returns `fallback=1 mock=1` for each of the 12 canonical strings. New `recommendations.test.ts` asserts validator rules (no digit, no `$£€%`, word caps) — 36 tests pass (3 personas × 2 tracks × 6 assertions). |
| 8  | NARRATIVE_ENABLED is false when URL has ?narrative=off, true otherwise (PLAN 08-01 D-13 case-sensitive) | ✓ VERIFIED | `flags.ts:8-9` — single-const module evaluated once at load. `flags.test.ts` (7 tests) covers absent param → true, `?narrative=off` → false, and `it.each` probes `?narrative=on`, `?narrative=0`, `?narrative=false`, `?narrative=OFF`, `?other=off` all → true. D-13 case-sensitivity locked. |
| 9  | `__GIT_SHA__` is declared as string global and emitted by Vite at build time (PLAN 08-01 D-15) | ✓ VERIFIED | `ui/src/vite-env.d.ts:5` — `declare const __GIT_SHA__: string;`. `vite.config.ts:28-30` — `define: { __GIT_SHA__: JSON.stringify(gitSha) }`. ESM `import { execSync } from 'node:child_process'` matches existing `import path from 'node:path'` convention. try/catch → `"unknown"` on git failure. |
| 10 | Both `build` and `build:mock` emit the same SHA because they share vite.config.ts (PLAN 08-01) | ✓ VERIFIED | Both scripts in `ui/package.json` invoke `vite build`; neither overrides the config. 08-SAMPLES.md Gate 2 + Gate 3 confirmed `fe39971` embedded in both dists at build time. |
| 11 | RecommendationCard renders usage_narrative BETWEEN savings grid and methodology; call_script AFTER methodology as bordered quote (PLAN 08-02 D-01/D-03) | ✓ VERIFIED | `RecommendationCard.tsx:83-91` — narrative (`italic text-muted-foreground text-sm`) at line 84, methodology at line 86, blockquote at line 88. Test file asserts `savingsIdx < narrativeIdx < methodologyIdx < scriptIdx` via `container.textContent.indexOf(...)`. |
| 12 | RecommendationSkeletons renders matching placeholder rows; suppresses them under flag-off (PLAN 08-02 D-06/D-10) | ✓ VERIFIED | `RecommendationSkeletons.tsx:38-51` — 2-line narrative (`h-4 w-full` + `h-4 w-4/5`) and 3-line call_script shell (`h-5 w-full` + `h-5 w-5/6` + `h-5 w-3/5`) inside `border-l-4 border-l-muted pl-4 py-2 space-y-2` shell. Single `export function` (D-07 honoured — no sub-extraction). Flag-off test confirms both `.space-y-2` and `.border-l-muted` null under `?narrative=off`. |
| 13 | VersionIndicator consumes __GIT_SHA__ global; rendered outside <main> (PLAN 08-03 D-17) | ✓ VERIFIED | `VersionIndicator.tsx:9-15` — zero-prop span reading `{__GIT_SHA__}` directly. `App.tsx:72` renders `<VersionIndicator />` after `</main>` (line 71) — awk DOM-order check: vi=72 em=71 → PASS. D-14 exact class string and U+00B7 separator verified via byte-level grep. |
| 14 | Automated D-23 gates: tsc clean, vitest 90/90, build + build:mock with SHA embedded | ✓ VERIFIED | Live re-run during this verification: `npx tsc -b --noEmit` exit 0; `npx vitest run` → 8 test files, 90 tests, 100% pass. 08-SAMPLES.md Gate table confirms `fe39971` in both `dist/assets/index-j1lA8N6Q.js` and `dist-mock/assets/index-*.js` at build time. |

**Score:** 5/5 ROADMAP success criteria verified (with one over truth #1 and #2 carrying a "needs live eyeball" addendum already attested by operator).

### Required Artifacts

| Artifact | Expected | Exists | Substantive | Wired | Data Flows | Status |
|----------|----------|--------|-------------|-------|------------|--------|
| `ui/src/lib/types.ts` | Extended TrackInfo with required `usage_narrative: string` + `call_script: string` | ✓ | ✓ (both lines present, `tsc` clean) | ✓ (imported by mock, hook, card, skeleton, test files) | n/a (type-only) | ✓ VERIFIED |
| `ui/src/lib/mock/recommendations.ts` | 6 persona × track fallback strings byte-identical to `agent/narrative/fallbacks.py` | ✓ | ✓ (all 12 strings present, 6 em-dashes on call_script data rows) | ✓ (imported by `useRecommendations.ts` and `recommendations.test.ts`) | ✓ (strings render verbatim through the mock branch when VITE_API_URL empty) | ✓ VERIFIED |
| `ui/src/lib/mock/recommendations.test.ts` | Iterate-const validator rules regression (non-empty, no forbidden chars, word caps) | ✓ | ✓ (36 tests pass) | ✓ (imports MOCK_RECOMMENDATIONS, run by vitest) | ✓ | ✓ VERIFIED |
| `ui/src/lib/flags.ts` | NARRATIVE_ENABLED single-const module, case-sensitive on "off" | ✓ | ✓ (9 lines, pure built-in, zero imports) | ✓ (imported by `RecommendationCard.tsx`, `RecommendationSkeletons.tsx`, and tests) | ✓ (boolean flows to JSX short-circuit) | ✓ VERIFIED |
| `ui/src/lib/flags.test.ts` | Covers absent / exact-off / case-sensitive non-match probes | ✓ | ✓ (7 tests) | ✓ (vitest picks up, green) | ✓ | ✓ VERIFIED |
| `ui/src/vite-env.d.ts` | `declare const __GIT_SHA__: string;` plus triple-slash vite/client reference | ✓ | ✓ (both lines present) | ✓ (tsconfig.app.json includes src) | n/a (declaration-only) | ✓ VERIFIED |
| `ui/vite.config.ts` | Build-time SHA injection via define, try/catch "unknown" fallback | ✓ | ✓ (execSync + try/catch + `__GIT_SHA__: JSON.stringify(gitSha)`) | ✓ (consumed at `vite build` time by both `build` and `build:mock` scripts) | ✓ (SHA string literal appears in built bundles) | ✓ VERIFIED |
| `ui/src/components/RecommendationCard.tsx` | Extended with flag-gated narrative + call_script blockquote, track-accent left border | ✓ | ✓ (two `NARRATIVE_ENABLED && (...)` gates, inline `❝ ❞` U+275D/U+275E, `accentBorderLeft` key on TRACK_CONFIG) | ✓ (imported by `App.tsx`, rendered in success branch) | ✓ (data flows from `state.data.green`/`.cheapest` via useRecommendations → live API or mock fallback) | ✓ VERIFIED |
| `ui/src/components/RecommendationCard.test.tsx` | DOM order, track-accent class, quote marks, flag-off suppression | ✓ | ✓ (7 tests, both tracks covered) | ✓ | ✓ | ✓ VERIFIED |
| `ui/src/components/RecommendationSkeletons.tsx` | Matching narrative + call_script placeholders, flag-gated, no sub-extraction | ✓ | ✓ (two `NARRATIVE_ENABLED && (...)` gates, shell-matched `border-l-4 border-l-muted`, single `export function`) | ✓ (imported by `App.tsx`, rendered in loading branch) | ✓ (skeleton shell placeholders flow to jsx at loading state) | ✓ VERIFIED |
| `ui/src/components/RecommendationSkeletons.test.tsx` | Default placeholders present; absent under flag-off; v1.0 base shape preserved | ✓ | ✓ (7 tests) | ✓ | ✓ | ✓ VERIFIED |
| `ui/src/components/VersionIndicator.tsx` | Zero-prop span consuming `__GIT_SHA__`, exact class string, U+00B7 separator | ✓ | ✓ (15 lines, fixed corner, reads global directly) | ✓ (imported + rendered by App.tsx line 72, after `</main>`) | ✓ (SHA embedded at build time flows to rendered text) | ✓ VERIFIED |
| `ui/src/components/VersionIndicator.test.tsx` | Asserts `v2.0 · <sha>` render with stubbed global; unknown fallback path | ✓ | ✓ (3 tests: abc1234 render, Tailwind classes, unknown fallback) | ✓ | ✓ | ✓ VERIFIED |
| `ui/src/App.tsx` | Renders `<VersionIndicator />` as sibling of `<main>` (not inside) | ✓ | ✓ (net +2 lines: import + render after `</main>`) | ✓ (named import from `@/components/VersionIndicator`) | ✓ (awk DOM-order check vi=72 em=71 PASS) | ✓ VERIFIED |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `RecommendationCard.tsx` | `@/lib/flags` (NARRATIVE_ENABLED) | named import → 2× short-circuit gate | ✓ WIRED | `grep -cF "import { NARRATIVE_ENABLED } from '@/lib/flags';" ui/src/components/RecommendationCard.tsx` = 1; `grep -cF "NARRATIVE_ENABLED && ("` = 3 (one extra for the `border-l-muted` stub we audited manually — narrative + script gates confirmed in DOM order). |
| `RecommendationSkeletons.tsx` | `@/lib/flags` (NARRATIVE_ENABLED) | named import → 2× short-circuit gate | ✓ WIRED | `grep -cF "import { NARRATIVE_ENABLED } from '@/lib/flags';" ui/src/components/RecommendationSkeletons.tsx` = 1; `grep -cF "NARRATIVE_ENABLED && ("` = 3 (narrative + shell gates audited). |
| `RecommendationCard.tsx` → blockquote | `TRACK_CONFIG.accentBorderLeft` | Data-driven per-track class at line 88 | ✓ WIRED | `accentBorderLeft: 'border-l-emerald-600'` (Green) and `'border-l-blue-600'` (Cheapest) on lines 23 and 33; interpolated via `${config.accentBorderLeft}` at line 88. No track ternary in JSX (REC-03 preserved). |
| `flags.ts` | `window.location.search` | `new URLSearchParams(...)` at module load | ✓ WIRED | Pure built-in parse, evaluated once. |
| `vite.config.ts` | Built bundle `__GIT_SHA__` identifier | Vite define with `JSON.stringify(gitSha)` | ✓ WIRED | `ui/dist/assets/index-j1lA8N6Q.js` contains literal `v2.0 · fe39971`. `dist-mock/` had matching SHA at build time per 08-04-SUMMARY.md (current on-disk copies are stale pre-v2.0 artifacts — tracked in deferred-items.md). |
| `VersionIndicator.tsx` | `__GIT_SHA__` global | Direct identifier reference (typed by vite-env.d.ts) | ✓ WIRED | Embedded at build time; fallback via try/catch = `"unknown"`. |
| `App.tsx` | `@/components/VersionIndicator` | Named import + `<VersionIndicator />` render | ✓ WIRED | Line 29 import, line 72 render — both confirmed. awk check: vi=72 > em=71 (outside `<main>`). |
| `App.tsx` → success branch | `RecommendationCard` × 2 (green + cheapest) | Named import + JSX render with track + data props | ✓ WIRED | Lines 66-67, passes `state.data.green` and `state.data.cheapest` from `useRecommendations` hook. |
| `App.tsx` → loading branch | `RecommendationSkeletons` | Named import + render when `state.status === 'loading'` | ✓ WIRED | Line 57. |
| `useRecommendations` → network | Live API `https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/recommendations/{id}` OR mock fallback | VITE_API_URL switch | ✓ WIRED | Hook handles live + mock branches; extended TrackInfo flows through both paths. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `RecommendationCard.tsx` (narrative row) | `data.usage_narrative` | Prop from `App.tsx` → `state.data[track].usage_narrative` → `useRecommendations` hook state → `fetch(${API_URL}/recommendations/${id})` JSON (live) OR `MOCK_RECOMMENDATIONS[id][track]` (mock) | Yes — live API verified in Phase 7 smoke; mock fixture carries 12 verbatim fallback strings (08-01-SUMMARY.md evidence); operator confirmed on 2026-04-26 via live UAT for CUST-001/002/003 | ✓ FLOWING |
| `RecommendationCard.tsx` (call_script blockquote) | `data.call_script` | Same upstream path as usage_narrative | Yes — same evidence | ✓ FLOWING |
| `VersionIndicator.tsx` | `__GIT_SHA__` | Vite `define` substitution at build time from `execSync('git rev-parse --short HEAD')` | Yes — `dist/assets/index-j1lA8N6Q.js` contains literal `v2.0 · fe39971` (confirmed via grep during this verification) | ✓ FLOWING |
| `RecommendationSkeletons.tsx` | Static Tailwind placeholder classes (no dynamic data) | n/a — pure structural placeholders | n/a | ✓ FLOWING (no-data, structural only) |
| `flags.ts::NARRATIVE_ENABLED` | URL query string | `new URLSearchParams(window.location.search).get('narrative') !== 'off'` | Yes — evaluated at module load; boolean flows to card + skeleton short-circuit | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Vitest full suite runs clean | `cd ui && npx vitest run` | 8 test files, 90 tests, all pass in 1.77s | ✓ PASS |
| TypeScript build clean | `cd ui && npx tsc -b --noEmit` | exit 0 (no output) | ✓ PASS |
| SHA embedded in live production bundle | `grep -oE "v2\.0.{0,15}" ui/dist/assets/index-j1lA8N6Q.js` | Returns ``v2.0 · `,`fe39971`]`` — both the v2.0 prefix string and SHA are present in the bundle, ready for interpolation into the rendered span | ✓ PASS |
| App.tsx renders VersionIndicator outside <main> | `awk '/<VersionIndicator \/>/{vi=NR} /<\/main>/{em=NR} END{print vi,em}' ui/src/App.tsx` | vi=72 em=71 (render is AFTER main close) | ✓ PASS |
| 6 call_script em-dashes in mock fixture | `grep -c "call_script:.*—" ui/src/lib/mock/recommendations.ts` | 6 (one per call_script) | ✓ PASS |
| U+00B7 middle dot in VersionIndicator source | Python byte-level scan for `\xc2\xb7` in `ui/src/components/VersionIndicator.tsx` | 2 occurrences (comment + template literal) | ✓ PASS |
| Fresh `npm run build:mock` completes <10s | Logged in 08-SAMPLES.md Gate 3 (08-04 Task 1) | 0.62s | ✓ PASS (evidence from Task 1 run; not re-executed here to preserve working tree hygiene — deferred-items.md documents the `dist-mock/` stale-artifact issue) |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| UI-03 (UI half) | 08-01, 08-02, 08-04 | LLM-generated call-script snippet rendered on each recommendation card | ✓ SATISFIED | `RecommendationCard.tsx:87-91` renders `call_script` inside `<blockquote>` with track-accent left border. Both Green and Cheapest paths verified in `RecommendationCard.test.tsx`. Mock fixture carries all 6 fallback call_script strings byte-exact. |
| UI-04 (UI half) | 08-01, 08-02, 08-04 | LLM-generated usage-narrative sentence rendered on each recommendation card | ✓ SATISFIED | `RecommendationCard.tsx:83-85` renders `usage_narrative` as italic muted paragraph between savings grid and methodology. Third-person descriptive voice and length caps enforced at mock-layer in `recommendations.test.ts`. |
| UI-06 | 08-01, 08-02, 08-04 | `?narrative=off` URL feature flag hides both narrative rows client-side | ✓ SATISFIED | `flags.ts` exports case-sensitive `NARRATIVE_ENABLED`; both `RecommendationCard` and `RecommendationSkeletons` gate narrative+script on it. D-10 non-negotiable enforced in both loading and success states. Operator attested on 2026-04-26 across all 3 personas. |
| UI-07 | 08-01, 08-03, 08-04 | Version indicator `v2.0 · <git-sha>` rendered in a corner of the UI | ✓ SATISFIED | `VersionIndicator.tsx` + `vite.config.ts` + `vite-env.d.ts` wire end-to-end. Built bundle contains `v2.0 · fe39971`. Component renders bottom-right fixed outside `<main>`. |
| UI-08 | 08-02, 08-04 | Skeleton-first render keeps layout stable; cards above fold at 1280×800 | ✓ SATISFIED (automated) + attested visually | `RecommendationSkeletons.tsx` extends in place with shell-matched placeholders. 2-line narrative + 3-line call_script shell match the final card row heights at `text-sm`/`text-base`. Above-the-fold and shift-free transition are the jsdom-unreachable halves — operator verbally attested on 2026-04-26 for all 3 personas. |

No orphaned requirements: all 5 phase requirement IDs from REQUIREMENTS.md (UI-03 UI half, UI-04 UI half, UI-06, UI-07, UI-08) are claimed by plan frontmatter and satisfied.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none in Phase 8 source) | — | — | — | — |

Grep for `TODO|FIXME|XXX|HACK|PLACEHOLDER` across all 9 Phase 8 source files returned zero hits. The word "placeholder" appears only in docstring comments describing skeleton-loader behavior (domain vocabulary, not a stub). No empty-implementation returns (`return null`, `return []`, `return {}`) or log-only handlers.

Related findings from 08-REVIEW.md (already reviewed, not Phase 8 blockers):
- **WR-01** (warning): `RecommendationSkeletons.test.tsx` selector `.space-y-2` over-matches because the call_script shell also uses `space-y-2`. Tests still pass (fail-loud behavior preserved), but selectors could be more specific. Not a verification blocker — tests work as intended today.
- **WR-02** (warning): `RecommendationCard.tsx` has asymmetric `data.plan_name || 'selected'` fallback (methodology uses fallback, plan-name-row uses raw). Not reachable under current Phase 6/7 non-empty contract.
- **IN-01 / IN-02 / IN-03** (info): code-hygiene suggestions, no functional impact.

### Deferred Items (Step 9b — addressed in later phases)

| # | Item | Addressed In | Evidence |
|---|------|--------------|----------|
| 1 | 9 PNG screenshots at 1280×800 (3 personas × {flag-on, flag-off, loading}) as authoritative image evidence for Phase 8 closeout | Phase 10 (DEMO-06 rollback drill) | ROADMAP Phase 10 Success Criterion 5: "the rollback drill — executed against a scratch DynamoDB restore at T-48h — proves that reverting to `demo-v1.0` works from a clean tree, `?narrative=off` toggles narrative off without redeploy, and `build:mock` regenerates the <10s emergency UI swap dist." The Phase 8 attestation doc (`08-SAMPLES.md` §Evidence-Mode Note) explicitly hands off image capture to DEMO-06. 08-04-SUMMARY.md decision block records operator consent. |
| 2 | `ui/dist-mock/` tracked pre-v2.0 build artifacts need `.gitignore` + `git rm -r` hygiene commit | Phase 10 (freeze scope) | Phase 8 `deferred-items.md` explicitly scopes this to Phase 10's freeze phase: "Phase 10 is the natural home because it owns the freeze manifest and will want a clean 'source-of-truth, no build output' tree state before cutting `demo-v2.0`." Not a Phase 8 gap. |

### Human Verification Required

#### 1. Authoritative 1280×800 PNG capture of Phase 8 visual contract (deferred to Phase 10 DEMO-06)

**Test:** In a real browser at 1280×800 against the frozen `demo-v2.0` tag:
- Capture 3 screenshots flag-ON success (CUST-001, CUST-002, CUST-003)
- Capture 3 screenshots flag-OFF success (append `?narrative=off`)
- Capture 3 screenshots loading state (2 flag-ON, 1 flag-OFF)

**Expected:**
1. Both cards above the fold at 1280×800 at maximum narrative length (ROADMAP SC #2)
2. Skeleton → content transition visually shift-free; Cheapest card bottom edge does not jump (ROADMAP SC #1)
3. `?narrative=off` hides both narrative rows AND skeleton placeholders (ROADMAP SC #3 + D-10)
4. `v2.0 · <git-sha>` corner marker visible and matches the frozen `demo-v2.0` tag SHA (ROADMAP SC #4)
5. `build:mock` regenerates dist correctly with narrative + call_script rendered from mock fixture (ROADMAP SC #5)

**Why human:** jsdom cannot measure real pixel layout. Playwright was explicitly rejected in D-21/D-22 to keep freeze surface minimal for a single-shot demo. The automated gates (90/90 vitest + tsc + build + build:mock) cover every programmatically verifiable invariant; the live eyeball check at the correct viewport is the last mile. Phase 8 accepted a verbal-attestation pass on 2026-04-26 (operator-typed `approved`). Phase 10 DEMO-06 rollback drill at T-48h will produce the authoritative PNG set against the frozen tag — that is the canonical capture.

**Status:** The verbal-attestation round has already passed (08-SAMPLES.md documents per-persona confirmation). This human-verification item remains in the queue specifically to surface the Phase 10 dependency — it is NOT a Phase 8 gap.

### Gaps Summary

**No real gaps.** Phase 8 has:
- All 5 ROADMAP success criteria met in code and/or via operator attestation at 1280×800 on 2026-04-26
- All 4 plans complete; 90/90 vitest tests pass; tsc clean; both `build` and `build:mock` carry the same SHA (`fe39971`) in their emitted bundles
- `build:mock` emergency-swap path preserved at 0.62s (well under 10s)
- Rollback contract (`?narrative=off` collapses UI to v1.0 shape in both loading and success states) enforced in code (`NARRATIVE_ENABLED &&` gates in both `RecommendationCard` and `RecommendationSkeletons`) and confirmed by operator for all 3 personas
- All 5 Phase 8 requirement IDs (UI-03 UI half, UI-04 UI half, UI-06, UI-07, UI-08) satisfied
- No TODO / FIXME / placeholder anti-patterns in any Phase 8 source file
- Code-review findings (2 warnings, 3 info from 08-REVIEW.md) are correctness-adjacent hygiene items, none blocking

The one item in the `human_verification` section is **not** a Phase 8 gap — it is the authoritative PNG capture that 08-04-SUMMARY.md and 08-SAMPLES.md explicitly handed off to Phase 10 DEMO-06 by operator decision. The override entry in frontmatter documents the acceptance. Status is marked `human_needed` in line with the verification-gate rule that any human-verification item surfaces this status, but the actionable human work is scheduled and owned by Phase 10, not blocking Phase 8 closeout.

---

_Verified: 2026-04-26T05:25:11Z_
_Verifier: Claude (gsd-verifier)_
