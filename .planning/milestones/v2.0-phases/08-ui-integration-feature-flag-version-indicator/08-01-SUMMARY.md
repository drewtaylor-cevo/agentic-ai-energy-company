---
phase: 08-ui-integration-feature-flag-version-indicator
plan: 01
subsystem: ui
tags: [typescript, vite, vitest, feature-flag, build-time-injection, snake-case-wire, mock-fixture]

# Dependency graph
requires:
  - phase: 06-agent-narrative-guardrail
    provides: "agent/narrative/fallbacks.py — the 6 canonical fallback strings the Phase 8 mock copies verbatim (D-19)"
  - phase: 07-api-pass-through-pre-warm-route
    provides: "extended RecommendationResponse wire contract passed through verbatim by the API Lambda (D-18)"
provides:
  - "TrackInfo extended with required usage_narrative + call_script strings (D-18)"
  - "MOCK_RECOMMENDATIONS carrying 6 fallback strings byte-identical to fallbacks.py (D-19)"
  - "recommendations.test.ts — iterate-const mock validator-rules regression (mirrors Phase 6 test_fallbacks_pass_validator at the UI layer)"
  - "ui/src/lib/flags.ts — NARRATIVE_ENABLED single-const module, evaluated once at load (D-09, D-12, D-13)"
  - "ui/src/lib/flags.test.ts — covers absent / exact-off / case-sensitive non-match probes via vi.stubGlobal + vi.resetModules + dynamic import"
  - "ui/src/vite-env.d.ts — triple-slash vite/client reference plus `declare const __GIT_SHA__: string;` global"
  - "ui/vite.config.ts — build-time __GIT_SHA__ injection via execSync + try/catch `unknown` fallback (D-15)"
affects: [08-02-wave-2-components, 08-03-wave-2-app-composition, 08-04-closeout-visual-uat]

# Tech tracking
tech-stack:
  added: []  # Zero new runtime deps — package.json unchanged
  patterns:
    - "Module-level single-const init (NARRATIVE_ENABLED) + vi.resetModules re-evaluation for testability"
    - "Vite define with JSON.stringify() for build-time string-literal injection"
    - "ESM `import { execSync } from 'node:child_process'` matching existing `import path from 'node:path'` convention"
    - "Iterate-const mock validator-rules test mirroring Phase 6 test_fallbacks_pass_validator at the UI layer"

key-files:
  created:
    - "ui/src/lib/flags.ts"
    - "ui/src/lib/flags.test.ts"
    - "ui/src/lib/mock/recommendations.test.ts"
    - "ui/src/vite-env.d.ts"
  modified:
    - "ui/src/lib/types.ts"
    - "ui/src/lib/mock/recommendations.ts"
    - "ui/vite.config.ts"

key-decisions:
  - "Required (not optional) usage_narrative + call_script on TrackInfo per D-18 — tsc catches any site that forgets them"
  - "Byte-for-byte verbatim copy of the 6 Phase 6 fallback strings into MOCK_RECOMMENDATIONS per D-19; sync-rule comment added per D-20"
  - "Case-sensitive match on the literal `off` for NARRATIVE_ENABLED per D-13; case variants like `?narrative=OFF` leave narrative ON"
  - "ESM import of execSync matching existing node:path convention (Claude's Discretion)"
  - "flags.ts kept narrow — no GIT_SHA re-export; VersionIndicator will reference __GIT_SHA__ directly (Claude's Discretion — recommended default)"
  - "__GIT_SHA__ declaration placed in vite-env.d.ts not a separate file (Claude's Discretion — recommended default; tsconfig.app.json::include=['src'] auto-picks it up)"

patterns-established:
  - "Snake-case wire contract preserved — usage_narrative / call_script not camelCased; matches Phase 4 convention"
  - "File-header comment with decision references (D-18, D-19, D-09–D-13, D-15) on every new or extended file"
  - "Module-reset + dynamic-import test idiom for module-level-init testability: vi.stubGlobal → vi.resetModules → `await import()`"

requirements-completed: [UI-03, UI-04, UI-06, UI-07]

# Metrics
duration: 9min
completed: 2026-04-26
---

# Phase 8 Plan 01: UI Foundation (Types, Mock, Flag, SHA Wiring) Summary

**Foundation layer for Phase 8: TrackInfo extended with required usage_narrative + call_script strings, MOCK_RECOMMENDATIONS synced byte-for-byte with Phase 6 fallbacks, NARRATIVE_ENABLED flag module shipped, __GIT_SHA__ wired end-to-end from vite.config.ts through a TypeScript global — zero consumer surface, zero new runtime deps.**

## Performance

- **Duration:** 9 min (535 s)
- **Started:** 2026-04-26T04:15:22Z
- **Completed:** 2026-04-26T04:24:17Z
- **Tasks:** 3 / 3
- **Files modified:** 7 (4 created, 3 extended)

## Accomplishments

- `TrackInfo` extended with required `usage_narrative: string` and `call_script: string` fields (D-18). Fields are NOT optional — `tsc -b` now catches any component, test, or mock site that forgets them.
- `MOCK_RECOMMENDATIONS` carries all 6 Phase 6 fallback strings copied byte-for-byte from `agent/narrative/fallbacks.py` (D-19). Grep against both files returns `fallback=1 mock=1` for all 12 canonical strings. Em-dash is U+2014 (U+00 94 0xE2 80 94) in both files; no normalization drift.
- New `ui/src/lib/mock/recommendations.test.ts` (36 new tests — 3 personas × 2 tracks × 6 assertions) — the UI-layer mirror of `agent/tests/test_fallbacks_pass_validator.py`. Asserts non-empty, no forbidden chars (digit, `$`, `£`, `€`, `%`), word-count caps (≤20 narrative / ≤22 call_script) for every persona × track.
- `ui/src/lib/flags.ts` — single-const module exporting `NARRATIVE_ENABLED` evaluated once at module load from `window.location.search` (D-09, D-12). Zero imports, zero React state, zero hooks. Case-sensitive match on the literal `"off"` per D-13 — `?narrative=OFF` / `?narrative=false` / `?narrative=0` / `?other=off` all leave narrative ON.
- `ui/src/lib/flags.test.ts` — 7 new tests (2 explicit + 5 `it.each` case-sensitivity probes). Uses the `vi.stubGlobal('location', …)` + `vi.resetModules()` + dynamic `await import('./flags')` idiom to re-evaluate the module-level const per test.
- `ui/src/vite-env.d.ts` (net-new file) — triple-slash `<reference types="vite/client" />` plus `declare const __GIT_SHA__: string;`. `tsconfig.app.json::include = ["src"]` auto-picks it up with zero tsconfig changes.
- `ui/vite.config.ts` — build-time SHA injection via `define: { __GIT_SHA__: JSON.stringify(gitSha) }` where `gitSha` comes from `execSync('git rev-parse --short HEAD').toString().trim()` inside a try/catch that falls back to `"unknown"` (D-15). Both `npm run build` and `npm run build:mock` share this config so both dists get the same SHA automatically.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend TrackInfo + mock fixture with all 6 fallback strings verbatim** — `07967ae` (feat)
2. **Task 2: Add flags.ts module + test, plus vite-env.d.ts global declaration** — `c83cbe1` (feat)
3. **Task 3: Wire __GIT_SHA__ build-time injection in vite.config.ts** — `ca21fa2` (feat)

**Plan metadata commit:** pending — orchestrator-managed in worktree mode (orchestrator commits SUMMARY.md only; STATE.md / ROADMAP.md writes are deferred to after all worktree agents in the wave complete).

## Files Created/Modified

### Created

- `ui/src/lib/flags.ts` — single-const `NARRATIVE_ENABLED` module (9 lines including header comment). Zero imports.
- `ui/src/lib/flags.test.ts` — 7 tests exercising the absent / exact-off / case-sensitive non-match probes via `vi.stubGlobal('location')` + `vi.resetModules()` + dynamic `await import('./flags')`.
- `ui/src/lib/mock/recommendations.test.ts` — iterate-const validator-rules regression. 36 tests (3 personas × 2 tracks × 6 assertions).
- `ui/src/vite-env.d.ts` — 6 lines: triple-slash vite/client reference, `declare const __GIT_SHA__: string;`, + a 2-line decision-reference comment.

### Modified

- `ui/src/lib/types.ts` — extended `TrackInfo` with required `usage_narrative: string` and `call_script: string`; preserved existing snake-case header comment and appended a D-18 extension note. `RecommendationResponse` / `ApiError` unchanged.
- `ui/src/lib/mock/recommendations.ts` — extended every `green` and `cheapest` entry with the 2 new string fields; appended the D-19/D-20 sync-rule comment to the existing header. Pre-existing savings numbers preserved byte-for-byte.
- `ui/vite.config.ts` — added `import { execSync } from 'node:child_process'`, the `gitSha` resolution block inside try/catch, and the `define: { __GIT_SHA__: JSON.stringify(gitSha) }` entry between `resolve` and `test`. No change to `plugins`, `alias`, or `test`.

## Decisions Made

All decisions honoured the phase's locked choices in `08-CONTEXT.md` without user-level modifications. Three Claude's Discretion defaults were applied exactly as recommended by the plan / PATTERNS.md:

1. **`flags.ts` kept narrowly scoped** — does NOT re-export `GIT_SHA`. `VersionIndicator` (Wave 2) will reference `__GIT_SHA__` directly.
2. **ESM `import { execSync } from 'node:child_process'`** (not `require('child_process')`) — matches existing `import path from 'node:path'` convention on line 2 of vite.config.ts.
3. **`__GIT_SHA__` TS declaration in `vite-env.d.ts`** — not a separate `build-info.d.ts`. `tsconfig.app.json::include=["src"]` picks it up automatically; no tsconfig edit needed.

## Deviations from Plan

Two auto-tracked deviations — both are plan/acceptance-criterion refinements, not functional changes. The implementation matches the plan's `<action>` blocks and `<done>` conditions exactly.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing `node_modules/` in fresh worktree**
- **Found during:** Baseline-suite check before Task 1.
- **Issue:** Worktrees don't copy `node_modules`; `npx vitest run` failed with `Cannot find package 'vite'`.
- **Fix:** Symlinked `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/ui/node_modules` into the worktree's `ui/node_modules`. The symlink is not tracked by git (matches existing `.gitignore` rule `node_modules` on line 11 of the project-root `.gitignore`).
- **Files modified:** none (symlink only; worktree-local).
- **Verification:** `npx vitest run` succeeded with 30/30 baseline tests passing.
- **Committed in:** not a code change — no commit needed.

**2. [Rule 1 - Acceptance-criterion refinement] Plan's `grep -c "—"` expectation of 6 mismatched actual file count of 9**
- **Found during:** Task 1 verification.
- **Issue:** Plan acceptance criterion reads `grep -c "—" ui/src/lib/mock/recommendations.ts returns 6`. Actual count is 9 because the pre-existing header comment uses em-dashes in 2 places (lines 8, 13), and the new D-19 comment I added per Step 2 of the plan's `<action>` introduces a 3rd comment-line em-dash. The substantive invariant — "one em-dash per `call_script` string, 6 `call_script` strings" — is satisfied exactly: `grep -c "call_script:.*—"` returns `6`. The total-file count is inflated by explanatory comments the acceptance criterion didn't anticipate.
- **Fix:** No code change. The call_script data rows contain exactly 6 em-dashes (one per string, byte-matching `fallbacks.py`). The plan's `<done>` clause for Task 1 — "mock fixture carries all 6 fallback strings byte-identical to `fallbacks.py`; 6 em-dashes present, zero hyphen-minus substitutions" — is satisfied when evaluated against the fixture data, which is what the criterion intended.
- **Files modified:** none.
- **Verification:** `grep -c "call_script:.*—" ui/src/lib/mock/recommendations.ts` returns `6`. Byte-exact match with `fallbacks.py` verified individually for all 12 canonical strings (`grep -F` returns `fallback=1 mock=1` for each).
- **Committed in:** `07967ae` (Task 1 commit); no fix commit needed.

**3. [Rule 1 - Acceptance-criterion refinement] Task 3's "SHA embedded in dist" check is unsatisfiable in Wave 1 alone**
- **Found during:** Task 3 verification (`grep -r "$(git rev-parse --short HEAD)" ui/dist/assets/`).
- **Issue:** Plan acceptance criterion asks the built bundle under `ui/dist/assets/` to contain the current short SHA. But Vite's `define` only substitutes the `__GIT_SHA__` identifier where compiled source code references it. In Wave 1, the only reference to `__GIT_SHA__` is the `declare const` in `vite-env.d.ts` — a type-declaration file that produces no emitted JS. `VersionIndicator` (the first actual consumer) ships in Wave 2 (plan 08-02). So the bundle correctly contains neither the SHA nor the `"unknown"` fallback; there's no substitution target.
- **Fix:** No code change — the define is correctly wired. To prove it resolves to the right literal, I evaluated the config via Vite's `loadConfigFromFile` API and confirmed `config.define.__GIT_SHA__` is `"c83cbe1"` byte-exact with `git rev-parse --short HEAD` at commit time. Wave 2 (08-02) will add `VersionIndicator.tsx` which references `__GIT_SHA__`; at that point the built bundle will carry the SHA end-to-end and the closeout plan (08-04) will exercise the full visual check.
- **Files modified:** none.
- **Verification:**
  - `node --input-type=module -e "import { loadConfigFromFile } from 'vite'; const r = await loadConfigFromFile({ command: 'build', mode: 'production' }, './vite.config.ts'); console.log(r.config.define.__GIT_SHA__);"` → `"c83cbe1"`.
  - `git rev-parse --short HEAD` at Task 2 completion → `c83cbe1` (matches).
  - `npx vite build` exits 0 (config loads cleanly).
- **Committed in:** `ca21fa2` (Task 3 commit) — commit body documents the Wave-2 dependency explicitly.

---

**Total deviations:** 3 auto-fixed (1 blocking environment setup, 2 acceptance-criterion refinements). **Zero** `action`-block or `done`-clause violations.

**Impact on plan:** No scope creep. All three deviations are either environment plumbing (node_modules symlink) or surface-level acceptance-criterion phrasing that would have been better written at planning time. The substantive contracts — byte-for-byte string matches, required TypeScript fields, case-sensitive flag, JSON.stringify'd define — are all satisfied exactly as specified.

## Plan-level verification (required by `<verification>` block)

```
cd ui
npx tsc -b --noEmit                             # exit 0 — clean
npx vitest run                                  # 73 passed (5 test files) — 30 baseline + 43 new
npx vite build                                  # exit 0 — dist/assets/index-HnP_rwno.js emitted
grep -q "usage_narrative: string;" src/lib/types.ts   # OK
grep -q "call_script: string;" src/lib/types.ts       # OK
grep -c "call_script:.*—" src/lib/mock/recommendations.ts  # 6 (one per call_script data row)
grep -qF "NARRATIVE_ENABLED" src/lib/flags.ts         # OK
grep -qF "declare const __GIT_SHA__: string;" src/vite-env.d.ts  # OK
grep -qF "__GIT_SHA__: JSON.stringify(gitSha)" vite.config.ts    # OK
```

## Evidence for Closeout Plan (08-04) — D-23 Requirements

- **Build-time SHA at plan close:** `c83cbe1` (verified via `loadConfigFromFile` + `git rev-parse --short HEAD`). Wave 2's `VersionIndicator.tsx` will be the first emitted code to reference `__GIT_SHA__`; at that point `dist/assets/*.js` will carry the SHA string end-to-end. The 08-04 closeout plan can diff the build-time SHA against the committed SHA directly once Wave 2 + Wave 3 land.
- **Byte-for-byte mock-vs-fallbacks confirmation:** for each of the 12 canonical strings, both `grep -cF "<string>" agent/narrative/fallbacks.py` and `grep -cF "<string>" ui/src/lib/mock/recommendations.ts` return `1`. Recorded in the Deviation-2 log above.
- **Full-suite test count:** `npx vitest run` → `Test Files 5 passed (5)`, `Tests 73 passed (73)`. New tests contributed: 43 (36 mock-rules + 7 flag-module). v1.0 baseline preserved: 30 tests untouched.

## Known Stubs

None. No stub patterns (`TODO`, `FIXME`, `placeholder`, empty arrays flowing to UI) exist in any of the 7 plan-scoped files. The one `placeholder` grep hit in `flags.ts` is the word used inside a comment describing skeleton placeholders — a Wave 2 concept — not a code stub.

## Issues Encountered

None during planned work. The three deviations listed above were handled inline without blocking progress.

## User Setup Required

None — no external service configuration required. No new deps added to `package.json`; no env vars introduced (the `?narrative=off` flag is URL-only per D-11).

## Next Phase Readiness

**Wave 2 (plans 08-02 + 08-03) is unblocked.** Consumers can now import:

- `import type { TrackInfo } from '@/lib/types';` — carries `usage_narrative` + `call_script`.
- `import { NARRATIVE_ENABLED } from '@/lib/flags';` — case-sensitive `?narrative=off` boolean.
- `__GIT_SHA__` — build-time string global, typed at TS level via `vite-env.d.ts`.
- `MOCK_RECOMMENDATIONS` — extended fixture used by `useRecommendations` in mock mode; `build:mock` regeneration covers all 3 personas with extended TrackInfo.

**No blockers.** All 3 Wave 1 plan files in the `files_modified` frontmatter were touched exactly as specified; no additional coupling introduced.

## Self-Check: PASSED

Verified before return:

- `ui/src/lib/types.ts` exists — extended (FOUND). `grep -c "usage_narrative: string;"` returns `1`.
- `ui/src/lib/mock/recommendations.ts` exists — extended (FOUND). `grep -cF "Strong cool-season usage with a family-sized load across the year."` returns `1`.
- `ui/src/lib/mock/recommendations.test.ts` exists (FOUND).
- `ui/src/lib/flags.ts` exists (FOUND). `grep -cF "export const NARRATIVE_ENABLED"` returns `1`.
- `ui/src/lib/flags.test.ts` exists (FOUND). `grep -F "?narrative=OFF"` returns a match.
- `ui/src/vite-env.d.ts` exists (FOUND). `grep -F "declare const __GIT_SHA__: string;"` returns a match.
- `ui/vite.config.ts` — `grep -cF "__GIT_SHA__: JSON.stringify(gitSha)"` returns `1`.
- Commits: `07967ae`, `c83cbe1`, `ca21fa2` — all present in `git log --oneline -5` (FOUND).

---

*Phase: 08-ui-integration-feature-flag-version-indicator*
*Plan: 01*
*Completed: 2026-04-26*
