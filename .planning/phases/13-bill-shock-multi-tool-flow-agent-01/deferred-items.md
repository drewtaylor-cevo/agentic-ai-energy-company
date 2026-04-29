# Deferred Items — Phase 13 Plan 01

## Out-of-scope discoveries during execution

### tests/test_frontend_synth.py — 23 ERRORS (worktree env artifact)

**Discovered:** Plan 13-01 execution, 2026-04-29.
**Trigger:** Full offline suite run at plan close.
**Error:** `RuntimeError: Cannot find asset at .../ui/dist` (jsii kernel).
**Root cause:** `ui/dist/` is gitignored (per CLAUDE.md "Build output is gitignored").
In the main repo the directory exists from prior `npm run build`; in parallel
executor worktrees created fresh from the feature branch HEAD, it does NOT.
The `FrontendStack` construct at `infrastructure/frontend_stack.py` uses an
`aws_s3_assets.Asset(path='ui/dist')` which fails jsii synth when the path
is absent.
**Impact:** None on Plan 13-01 deliverables. All 23 errors are the same
`Cannot find asset` failure; none touch `lambda/handler.py` or
`tests/test_bill_shock_flow.py`.
**Pre-existing:** Yes — reproducible on a clean worktree without `ui/dist`,
and unrelated to any Plan 13-01 code change.
**Status:** Not fixed. Tracked here per executor SCOPE BOUNDARY rule.
**Resolution path:** Either (a) run `cd ui && npm ci && npm run build:mock`
before `pytest -m "not smoke"` in worktree CI, or (b) add an
`autouse skip` in `tests/test_frontend_synth.py::conftest` that sys-skips
if `ui/dist` is missing. Either is a tooling / test-infra task for a
future phase.

**Plan 01 regression surface that DID pass (no flaky results):**
  - tests/test_bill_shock_flow.py                  17/17
  - tests/test_simulate_savings.py                 22/22
  - tests/test_get_hardship_flag_pure.py            4/4
  - tests/test_get_billing_history.py              11/11
  - tests/test_providers.py                        14/14
  - Full non-smoke suite (excluding frontend_synth): 236 passed, 12 skipped.

### ui — 6 pre-existing lint errors (Plan 13-06 discovery)

**Discovered:** Plan 13-06 execution, 2026-04-29.
**Trigger:** `npm run lint` as part of Task 6.5 verification gate.
**Errors:**
  - `ui/src/components/ui/badge.tsx:48:17` — `react-refresh/only-export-components`
  - `ui/src/components/ui/button.tsx:64:18` — `react-refresh/only-export-components`
  - `ui/src/hooks/useRecommendations.test.ts:57,133` — `@typescript-eslint/no-unused-vars` on `_url` / `_init` (intentional unused-args prefix but not matching lint ignore pattern)
**Root cause:** shadcn/ui badge.tsx and button.tsx export both a component and
a variant-builder constant (`badgeVariants`, `buttonVariants`) from the same
file — the eslint-plugin-react-refresh rule prefers single-export-per-file.
The test file uses the `_` prefix convention for unused function params but
the project's `@typescript-eslint/no-unused-vars` rule is not configured to
honour it.
**Impact:** None on Plan 13-06 deliverables. The 5 files this plan created
or modified all pass `npx eslint src/components/ReasoningTrace.tsx
src/components/ReasoningTrace.test.tsx src/lib/types.ts
src/lib/mock/recommendations.ts src/App.tsx` with zero warnings.
**Pre-existing:** Yes — reproducible on the base commit `4039aa1` without any
Plan 13-06 change.
**Status:** Not fixed. Tracked here per executor SCOPE BOUNDARY rule.
**Resolution path:** Either (a) refactor shadcn/ui files to split the variant
constants into sibling `*.variants.ts` files and extend the test-file eslint
config with `argsIgnorePattern: "^_"`, or (b) relax the rules for
`src/components/ui/**` and `**/*.test.ts`. Tooling task for a future phase
(not a Plan 13-06 regression).
