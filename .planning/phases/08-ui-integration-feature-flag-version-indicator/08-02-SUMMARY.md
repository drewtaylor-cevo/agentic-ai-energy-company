---
phase: 08-ui-integration-feature-flag-version-indicator
plan: 02
subsystem: ui
tags: [typescript, vitest, testing-library, react-component, feature-flag, skeleton-first, tdd]

# Dependency graph
requires:
  - phase: 08-ui-integration-feature-flag-version-indicator
    plan: 01
    provides: "Extended TrackInfo (usage_narrative + call_script required strings), NARRATIVE_ENABLED module-level flag, MOCK_RECOMMENDATIONS with 6 verbatim fallback strings"
provides:
  - "Extended RecommendationCard — narrative row (italic/muted/text-sm between savings grid and methodology) + call_script bordered quote block (track-accent left border, inline U+275D/U+275E) after methodology, both flag-gated (D-01, D-02, D-03, D-10, D-12)"
  - "Extended RecommendationSkeletons — 2-line narrative placeholder + 3-line call_script shell placeholder, flag-gated, inline (no sub-component extraction per D-07)"
  - "RecommendationCard.test.tsx — 7 tests (5 flag-on rendering + 2 flag-off suppression) covering DOM order, track-accent class, quote-mark inlining, italic/muted typography, prop-interface preservation"
  - "RecommendationSkeletons.test.tsx — 7 tests (4 flag-on placeholders + 3 flag-off suppression + base-shape preservation) using `vi.stubGlobal('location') + vi.resetModules + dynamic import` idiom"
  - "Net-new project convention: `.test.tsx` component tests via `@testing-library/react` render + screen queries — first component tests in the project (prior tests were all `.test.ts` pure-function or hook)"
affects: [08-03-wave-2-app-composition, 08-04-closeout-visual-uat]

# Tech tracking
tech-stack:
  added: []  # Zero new runtime or dev deps — package.json unchanged
  patterns:
    - "TDD RED → GREEN cycle enforced per task (test commit precedes implementation commit)"
    - "`data-driven per-track styling via TRACK_CONFIG map` extended with accentBorderLeft — no track ternaries in JSX (REC-03 preserved)"
    - "`vi.stubGlobal('location', …) + vi.resetModules() + dynamic await import()` idiom propagated from Wave 1's flags.test.ts to both new component tests"
    - "Inline U+275D / U+275E quote marks (not CSS pseudo-elements) — matches D-21 'stable DOM under flag off' contract"
    - "Skeleton shell matches final card shell shape (border-l-4 pl-4 py-2) with border-l-muted in loading state — visual continuity under the skeleton → content transition"

key-files:
  created:
    - "ui/src/components/RecommendationCard.test.tsx"
    - "ui/src/components/RecommendationSkeletons.test.tsx"
  modified:
    - "ui/src/components/RecommendationCard.tsx"
    - "ui/src/components/RecommendationSkeletons.tsx"

key-decisions:
  - "Inline `❝ ❞` quote-mark text chosen over CSS pseudo-elements (Claude's Discretion honoured per CONTEXT.md): preserves render-time stability with zero CSS state; the flag-off DOM is byte-equivalent to v1.0 with no leftover quote-mark CSS artefacts"
  - "`accentBorderLeft` added as a sibling key on `TRACK_CONFIG` rather than extracting a `TrackAccentBorder` utility (Claude's Discretion — recommended default): keeps per-track visual variance confined to the existing 4-key config pattern (accentBorder / accentText / methodologyTemplate / accentBorderLeft) so REC-03's equal-cards audit surface is one grep away"
  - "Default `space-y-4` preserved on CardContent — no per-row `mt-*` tightening added (Claude's Discretion — recommended default): D-01 row order enforces grouping; visual tightening deferred to the D-23 human UAT"
  - "No REFACTOR step taken after GREEN: implementation matches the PATTERNS.md snippets byte-for-byte; no code smells to resolve"

requirements-completed: [UI-03, UI-04, UI-06, UI-08]

# Metrics
duration: 6min
completed: 2026-04-26
---

# Phase 8 Plan 02: Component Layer — Extended RecommendationCard + Skeletons Summary

**Wave 2 core visible work landed: the two narrative rows render on every recommendation card (narrative italic/muted between savings and methodology; call_script as a track-accent bordered quote below methodology), matching skeleton placeholders carry the layout through the loading → success transition, and both the cards AND the skeletons collapse to their v1.0 shape when `?narrative=off` is in the URL. 14 new tests (7 card + 7 skeleton); full suite 87/87 green; zero new deps; RED → GREEN TDD cycle committed atomically per task.**

## Performance

- **Duration:** 6 min (339 s)
- **Started:** 2026-04-26T04:30:32Z
- **Completed:** 2026-04-26T04:36:11Z
- **Tasks:** 2 / 2
- **Files modified:** 4 (2 created, 2 extended)

## Accomplishments

- `RecommendationCard` extended in place: `accentBorderLeft` key added to both tracks of `TRACK_CONFIG` (`border-l-emerald-600` for Green, `border-l-blue-600` for Cheapest) — data-driven per-track styling preserved (no `track === 'green'` ternaries in JSX, REC-03 equal-cards contract unchanged).
- Usage narrative rendered as `<p className="text-sm italic text-muted-foreground">` BETWEEN the savings grid and the methodology line (D-01, D-02).
- Call script rendered as a `<blockquote className="border-l-4 ${config.accentBorderLeft} pl-4 py-2 text-base">` AFTER the methodology line, with inline `❝ … ❞` (U+275D / U+275E) quote marks (D-03, D-16-adjacent middle-dot-style character choice).
- Both rows wrapped in `NARRATIVE_ENABLED && (...)` short-circuits — `?narrative=off` suppresses both the narrative paragraph and the blockquote on both tracks (D-10 primary runtime rollback lever).
- `RecommendationSkeletons` extended in place with a 2-line narrative placeholder (`.space-y-2` group containing `h-4 w-full` + `h-4 w-4/5`) between savings grid and methodology bar, plus a 3-line call_script shell placeholder (`border-l-4 border-l-muted pl-4 py-2 space-y-2` containing `h-5 w-full` + `h-5 w-5/6` + `h-5 w-3/5`) after the methodology bar.
- Both skeleton placeholders wrapped in `NARRATIVE_ENABLED && (...)` — D-10 non-negotiable ("UI is byte-equivalent to v1.0 in BOTH loading and success states" when the flag is off). v1.0 base skeleton shape preserved byte-for-byte when `?narrative=off` is active.
- No sub-component extraction on the skeleton side (D-07 honoured) — `RecommendationSkeletons.tsx` still has exactly one `export function`. Entire skeleton tree remains auditable in one file against the final card shape.
- `RecommendationCard.test.tsx` (net-new): 7 tests covering (a) Green track narrative + emerald-600 bordered quote, (b) Cheapest track blue-600 bordered quote, (c) DOM order savings → narrative → methodology → call_script via `container.textContent.indexOf(…)`, (d) inline U+275D / U+275E quote marks present in the rendered blockquote, (e) narrative paragraph has `italic text-muted-foreground text-sm` classes, (f+g) `?narrative=off` hides both rows on Green AND Cheapest.
- `RecommendationSkeletons.test.tsx` (net-new): 7 tests covering (a) narrative `.space-y-2` group present in both cards, (b) call_script `.border-l-muted` shell present in both cards with `border-l-4`, (c) narrative placeholder contains `.h-4.w-full` + `.h-4.w-4/5`, (d) call_script shell contains `.h-5.w-full` + `.h-5.w-5/6` + `.h-5.w-3/5`, (e) `?narrative=off` suppresses `.space-y-2`, (f) `?narrative=off` suppresses `.border-l-muted`, (g) `?narrative=off` preserves outer grid + `.border-t-muted` card top borders (v1.0 base shape).
- First `.test.tsx` component tests in the project — prior test files were all `.test.ts` pure-function or hook tests. Uses `@testing-library/react` `render` + `screen` queries already present in `package.json::devDependencies`; no new deps added.
- TDD cycle enforced per task: RED commit (failing tests) precedes GREEN commit (implementation). Each commit compiles + type-checks cleanly.

## Task Commits

Each task committed atomically as two gates (RED + GREEN):

1. **Task 1 RED: failing RecommendationCard tests for narrative + call_script** — `b3293e4` (test)
2. **Task 1 GREEN: extend RecommendationCard with narrative + call_script rows** — `70a395c` (feat)
3. **Task 2 RED: failing RecommendationSkeletons tests for narrative + call_script placeholders** — `3c918c4` (test)
4. **Task 2 GREEN: extend RecommendationSkeletons with narrative + call_script placeholders** — `2469ab9` (feat)

No REFACTOR commits — implementations matched the PATTERNS.md snippets with no code smells to address.

**Plan metadata commit:** pending — orchestrator-managed in worktree mode (orchestrator commits SUMMARY.md only; STATE.md / ROADMAP.md writes are deferred to after all worktree agents in the wave complete).

## TDD Gate Compliance

Plan-level TDD gate sequence verified in `git log --oneline`:

```
2469ab9 feat(08-02): extend RecommendationSkeletons ...    ← Task 2 GREEN
3c918c4 test(08-02): add failing RecommendationSkeletons ...  ← Task 2 RED
70a395c feat(08-02): extend RecommendationCard ...          ← Task 1 GREEN
b3293e4 test(08-02): add failing RecommendationCard ...     ← Task 1 RED
```

Both tasks have a `test(...)` commit strictly preceding the `feat(...)` commit. RED phase verified to fail before GREEN was attempted:

- Task 1 RED run: 5 failed / 2 passed (7 total) — the 2 passing tests were the `?narrative=off` suppression cases that trivially passed because the narrative rows had not yet been added to the component at that point (the query for "Strong cool-season" genuinely finds no element; this is not a false-positive — the test is correctly asserting absence, and absence was correctly achieved).
- Task 2 RED run: 4 failed / 3 passed (7 total) — same pattern: the 3 flag-off tests trivially passed because the skeleton placeholder rows had not yet been added.

No "test passes unexpectedly during RED" fail-fast trigger occurred. The tests that pre-passed are correctness-preserving absence assertions, not feature assertions.

## Files Created/Modified

### Created

- `ui/src/components/RecommendationCard.test.tsx` (148 lines) — 7 tests in 2 describe blocks (flag-on default + `?narrative=off` suppression). Imports `@testing-library/react` `render` + `screen` and the component under test dynamically via `await import('./RecommendationCard')`. Uses the `trackFixture(overrides?)` local factory mirroring `MOCK_SUCCESS` in `useRecommendations.test.ts`.
- `ui/src/components/RecommendationSkeletons.test.tsx` (102 lines) — 7 tests in 2 describe blocks (flag-on default placeholders + `?narrative=off` suppression with base-shape preservation).

### Modified

- `ui/src/components/RecommendationCard.tsx` — added `import { NARRATIVE_ENABLED } from '@/lib/flags';`, added `accentBorderLeft: 'border-l-emerald-600'` / `'border-l-blue-600'` to each track in `TRACK_CONFIG`, inserted narrative paragraph (italic/muted/text-sm) between the savings grid and methodology paragraph, appended call_script blockquote (border-l-4 with track-accent left, pl-4 py-2, text-base, inline ❝ ❞) as the final `CardContent` child. Both new rows wrapped in `NARRATIVE_ENABLED && (...)`. +11 lines. File-header comment, props interface, icon/badge/plan-name/savings-grid/methodology rendering all byte-for-byte unchanged.
- `ui/src/components/RecommendationSkeletons.tsx` — added `import { NARRATIVE_ENABLED } from '@/lib/flags';`, inserted 2-line narrative placeholder `<div className="space-y-2">` between savings grid and existing methodology `<Skeleton h-4 w-full>`, appended 3-line call_script shell `<div className="border-l-4 border-l-muted pl-4 py-2 space-y-2">` as the final `CardContent` child. Both wrapped in `NARRATIVE_ENABLED && (...)`. +14 lines. Outer grid (`grid grid-cols-1 md:grid-cols-2 gap-8`), `CardHeader` block, existing savings-grid, and existing methodology `Skeleton h-4 w-full` all byte-for-byte unchanged.

## Decisions Made

All decisions matched the Plan's `<action>` blocks and PATTERNS.md snippets. The three "Claude's Discretion" defaults listed in CONTEXT.md under §Claude's Discretion were applied exactly as the plan recommended:

1. **Inline `❝ ❞` text** over CSS pseudo-elements or a `lucide Quote` icon (CONTEXT.md Claude's Discretion): preserves flag-off = v1.0-DOM-shape contract with zero CSS state. Unicode characters: U+275D (HEAVY DOUBLE TURNED COMMA QUOTATION MARK ORNAMENT) and U+275E (HEAVY DOUBLE COMMA QUOTATION MARK ORNAMENT). Both literally present in the source file (`grep -cP '\x{275D}'` returns 1; same for U+275E).
2. **`accentBorderLeft` added as a sibling TRACK_CONFIG key** rather than extracting a `TrackAccentBorder` utility or using inline track ternaries (CONTEXT.md Claude's Discretion + PATTERNS.md): mirrors the existing `accentBorder` / `accentText` / `methodologyTemplate` pattern. REC-03 equal-cards contract remains a single-grep audit ("what varies between Green and Cheapest → exactly these 4 keys").
3. **Default `space-y-4` preserved** on both `CardContent` blocks — no per-row `mt-*` tightening added (CONTEXT.md Claude's Discretion): D-01 enforces row order; tighter visual grouping is deferred to the D-23 human UAT where real layout measurements apply (jsdom can't validate this).

## Deviations from Plan

One low-severity acceptance-criterion phrasing refinement. No scope creep, no action-block violations, no behavioural deviations.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `node_modules/` missing in fresh worktree**
- **Found during:** Baseline suite check before Task 1 RED.
- **Issue:** Worktrees don't copy `node_modules`; `npx vitest run` would fail with `Cannot find package 'vite'`.
- **Fix:** Symlinked `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/ui/node_modules` into the worktree's `ui/node_modules`. Symlink is worktree-local and not tracked by git (matches existing `.gitignore` rule). Same deviation recorded in Plan 01's SUMMARY; confirms the root cause is the worktree-provisioning step, not a plan issue.
- **Files modified:** none (symlink only; worktree-local).
- **Verification:** Baseline `npx vitest run` → `Test Files 5 passed (5)`, `Tests 73 passed (73)` — matches the post-Wave-1 baseline exactly.
- **Committed in:** not a code change — no commit needed.

**2. [Rule 1 - Acceptance-criterion refinement] Task 2 `grep -cF "grid grid-cols-1 md:grid-cols-2 gap-8"` expects 1, actual is 2**
- **Found during:** Task 2 acceptance-criteria verification.
- **Issue:** Plan acceptance criterion reads `grep -cF "grid grid-cols-1 md:grid-cols-2 gap-8" ui/src/components/RecommendationSkeletons.tsx returns 1 (outer grid preserved)`. Actual count is 2 because the pre-existing file-header comment on line 5 ("The grid class `grid grid-cols-1 md:grid-cols-2 gap-8` MUST match the layout used by App.tsx's success state") literally contains the grid class string as documentation prose. The substantive invariant — "exactly one `<div>` using this grid class in the rendered tree" — is satisfied: `grep -cF 'className="grid grid-cols-1 md:grid-cols-2 gap-8"'` returns `1` (the actual JSX element on line 13).
- **Fix:** No code change. The header comment was already present in the v1.0 baseline and is the canonical audit-trail pointer to the App.tsx grid contract (see file lines 1-6). The criterion phrasing underspecifies the match (comment prose vs. JSX element); the grid-rendering intent is satisfied exactly.
- **Files modified:** none.
- **Verification:** `grep -nF "grid grid-cols-1 md:grid-cols-2 gap-8" ui/src/components/RecommendationSkeletons.tsx` returns:
  - line 5: `// The grid class `grid grid-cols-1 md:grid-cols-2 gap-8` MUST match the` (header comment — preserved from v1.0)
  - line 13: `    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">` (the actual JSX element — the acceptance target)
- **Committed in:** `2469ab9` (Task 2 GREEN commit) — no fix commit needed.

---

**Total deviations:** 2 auto-fixed (1 blocking environment setup, 1 acceptance-criterion phrasing). **Zero** `action`-block or `done`-clause violations. **Zero** behavioural deviations.

## Plan-level verification (required by `<verification>` block)

```
cd ui
npx tsc -b --noEmit                                                       # exit 0 — clean
npx vitest run src/components/RecommendationCard.test.tsx                # 7 passed (1 file, 7 tests)
npx vitest run src/components/RecommendationSkeletons.test.tsx           # 7 passed (1 file, 7 tests)
npx vitest run                                                           # 87 passed (7 files) — 73 pre-existing baseline + 14 new
```

Grep confirmations (per plan's `<verification>` bottom paragraph):
```
grep -cF "import { NARRATIVE_ENABLED } from '@/lib/flags';" ui/src/components/RecommendationCard.tsx        # 1
grep -cF "import { NARRATIVE_ENABLED } from '@/lib/flags';" ui/src/components/RecommendationSkeletons.tsx   # 1
grep -cF "NARRATIVE_ENABLED && ("                           ui/src/components/RecommendationCard.tsx        # 2 (narrative + call_script gates — both flag-off-contract sites covered)
grep -cF "NARRATIVE_ENABLED && ("                           ui/src/components/RecommendationSkeletons.tsx   # 2 (skeleton narrative + skeleton call_script gates)
grep -cF "border-l-emerald-600"                             ui/src/components/RecommendationCard.tsx        # 1 (Green track only)
grep -cF "border-l-blue-600"                                ui/src/components/RecommendationCard.tsx        # 1 (Cheapest track only)
grep -cP '\x{275D}'                                         ui/src/components/RecommendationCard.tsx        # 1 (U+275D ❝)
grep -cP '\x{275E}'                                         ui/src/components/RecommendationCard.tsx        # 1 (U+275E ❞)
grep -c "narrativeEnabled"                                  ui/src/components/RecommendationCard.tsx        # 0 (D-12 prohibition — no prop plumbing)
grep -c "^export function"                                  ui/src/components/RecommendationSkeletons.tsx   # 1 (D-07 — single exported component, no sub-extraction)
```

## Output-Block Confirmations (per plan's `<output>` directive)

- **Vitest pass count BEFORE this plan:** 73 / 73 (5 test files) — matches Wave 1 SUMMARY's post-plan count exactly.
- **Vitest pass count AFTER this plan:** 87 / 87 (7 test files) — +14 new (7 card + 7 skeleton), +2 test files. Zero pre-existing Phase 4 tests regressed (personas / validate / useRecommendations / flags / mock-recommendations all untouched).
- **DOM order assertion holds:** Task 1 test "orders narrative between savings grid and methodology, call_script after methodology" asserts `savingsIdx < narrativeIdx < methodologyIdx < scriptIdx` via `container.textContent.indexOf(...)` on a rendered Green track. Test passes.
- **Both files gate narrative + call_script on `NARRATIVE_ENABLED`:** confirmed above — `grep -cF "NARRATIVE_ENABLED && ("` returns `2` in both `RecommendationCard.tsx` AND `RecommendationSkeletons.tsx`. Two gates per file (narrative row + call_script row), four gates total — the D-10 contract is enforced in both the success state AND the loading state.
- **Claude's Discretion calls made (exact list, matches recommendations in CONTEXT.md §Claude's Discretion):**
  1. Inline `❝ ❞` text (not CSS pseudo-elements, not lucide Quote icon). [D-21 first bullet, recommended default — applied.]
  2. `accentBorderLeft` as a sibling TRACK_CONFIG key (not a `TrackAccentBorder` utility, not inline JSX ternary). [Planner-decides, recommended default — applied.]
  3. Default `space-y-4` rhythm preserved (no per-row `mt-*` tightening). [Planner-decides, recommended default — applied.]

## Known Stubs

None. No `TODO`, `FIXME`, empty-array-flowing-to-UI, or hardcoded placeholder-text stubs introduced in any of the 4 plan-scoped files. The word "placeholder" appears in both files and both tests, but every occurrence is domain vocabulary for skeleton-loader placeholder rows — the Wave 2 feature itself, not a stub.

## Issues Encountered

None during planned work. The two deviations listed above were handled inline without blocking progress. No auth gates, no architectural checkpoints, no Rule-4 stop-and-ask events.

## User Setup Required

None — no external service configuration, no env vars, no new deps. The `?narrative=off` flag is URL-only (D-11); operators add it to the URL at demo time.

## Threat Flags

None. Phase 8's `<threat_model>` (inherited from Plan 01) explicitly states this phase introduces NO new runtime attack surface. Plan 02's additions are pure render-time guards (React short-circuit expressions reading a boolean const); all rendered text originates from `data.usage_narrative` / `data.call_script` supplied via the `TrackInfo` prop, which is already content-sanitized upstream by Phase 6's Pydantic validator. No new endpoints, no auth paths, no file access, no schema changes.

## Next Phase Readiness

**Wave 2 plan 08-03 is unblocked.** `App.tsx` can now safely render `<RecommendationCard>` for both tracks and the `<RecommendationSkeletons>` tree knowing:

- Both components honour `NARRATIVE_ENABLED` automatically — no prop plumbing required in App.tsx (D-12 contract preserved).
- The extended `TrackInfo` prop shape (required `usage_narrative` + `call_script`) is compile-time-enforced; App.tsx doesn't need defensive optional-chaining.
- The skeleton → success transition is visually continuous at default `text-sm` / `text-base` line heights — the card's narrative + blockquote rows match the skeleton's placeholder rows 1:1 (D-06 shell-matched contract).

Wave 2 plan 08-03 (`App.tsx` composition — add `VersionIndicator` sibling to `<main>`, no other App-level change per PATTERNS.md) is the next work item.

**No blockers.** All `files_modified` in Plan 02's frontmatter were touched exactly as specified; no additional files coupled to this plan.

## Self-Check: PASSED

Verified before return:

- `ui/src/components/RecommendationCard.tsx` extended (FOUND). `grep -cF "import { NARRATIVE_ENABLED }" ...` returns `1`. `grep -cF "accentBorderLeft: 'border-l-emerald-600'"` returns `1`. `grep -cF "accentBorderLeft: 'border-l-blue-600'"` returns `1`. `grep -cF "NARRATIVE_ENABLED && ("` returns `2`. Unicode ❝ + ❞ literally present (`grep -cP '\x{275D}'` and `\x{275E}` each return `1`).
- `ui/src/components/RecommendationCard.test.tsx` exists (FOUND). `grep -F "'border-l-emerald-600'"` and `'border-l-blue-600'` both present as assertions. `grep -F "?narrative=off"` returns matches.
- `ui/src/components/RecommendationSkeletons.tsx` extended (FOUND). `grep -cF "import { NARRATIVE_ENABLED }" ...` returns `1`. `grep -cF "NARRATIVE_ENABLED && ("` returns `2`. `grep -cF 'border-l-4 border-l-muted pl-4 py-2 space-y-2'` returns `1`. `grep -c "^export function"` returns `1` (D-07 honoured).
- `ui/src/components/RecommendationSkeletons.test.tsx` exists (FOUND). Flag-off suppression assertions present for both `.space-y-2` and `.border-l-muted`.
- Commits: `b3293e4`, `70a395c`, `3c918c4`, `2469ab9` — all present in `git log --oneline -6` (FOUND).
- `npx tsc -b --noEmit` exit 0. `npx vitest run` → `Test Files 7 passed (7)`, `Tests 87 passed (87)`.

---

*Phase: 08-ui-integration-feature-flag-version-indicator*
*Plan: 02*
*Completed: 2026-04-26*
