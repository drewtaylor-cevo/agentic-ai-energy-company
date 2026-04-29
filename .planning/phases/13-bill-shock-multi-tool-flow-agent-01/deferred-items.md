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
