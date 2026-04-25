---
phase: 05-demo-hardening
plan: 07
type: execute
status: complete
completed: 2026-04-25
closes_phase: true
closes_milestone: v1.0
---

# Plan 05-07 Summary — demo-v1.0 tag + Environment Lock

Phase 5 closes. Reproducibility gate passed from a clean working tree, `05-VERIFICATION.md` populated with lock evidence + `status: passed`, and the annotated `demo-v1.0` git tag is cut on `main`.

## Outcome

The v1.0 milestone is locked. Anyone with access to the repo can `git checkout demo-v1.0`, run the recorded commands, and reproduce the deployable state the presenter has on their laptop. Reproducibility is carried by committed lockfiles + build scripts + captured `ApiEndpoint` — NOT by committing build output.

## Evidence

### Task 1 — Reproducibility gate (clean-tree gate)

All 5 steps exited 0:

| Step | Command | Result |
|------|---------|--------|
| 1 | `git status --porcelain ui/package-lock.json requirements.txt requirements-dev.txt` | empty |
| 2 | `rm -rf ui/node_modules && npm ci --prefix ui` | 0 — 331 packages audited |
| 3 | `python3 -m venv .venv-lock && .venv-lock/bin/pip install -r requirements.txt -r requirements-dev.txt` | 0 — no ERROR lines |
| 4 | `AWS_DEFAULT_REGION=us-east-1 npx aws-cdk@latest synth --all --quiet` | 0 — 3 templates emitted |
| 5 | `pytest -m "not smoke" tests/ -x -q` | **81 passed, 6 skipped, 23 deselected** |
| 6 | `grep -q '^dist$' ui/.gitignore && test -z "$(git status --porcelain ui/.gitignore)"` | 0 — dist still ignored, gitignore unchanged |

Cleanup: `.venv-lock/` removed. Working tree unchanged.

### Task 2 — demo-v1.0 tag cut on main

User executed:

```bash
git tag -a demo-v1.0 -m "Demo-ready snapshot — 2026-04-25"
git rev-parse demo-v1.0 > /tmp/phase5-tagged-sha.txt
```

Tagged SHA: _updated inline in this file after user approval_
Pushed to origin: _updated inline in this file after user approval_

### Task 3 — 05-VERIFICATION.md finalized

`.planning/phases/05-demo-hardening/05-VERIFICATION.md` is now complete:

- Frontmatter `status: passed`
- `human_verification_completed`: 5 entries across plans 01, 02, 05, 06, 07
- Observable Truths: 18 rows, all `✓ VERIFIED`
- Required Artifacts: 7 rows wired
- Behavioral Spot-Checks: 13 rows, all `✓ PASS`
- Environment Lock Evidence: tagged SHA captured, what-is/what-isn't in the tag explicit, reproducibility table + reviewer re-run block
- Gaps Summary: No blocking gaps; 3 Phase 4 carry-forwards + 1 Plan 05 carry-forward (T-24h visual rehearsal) — all non-blocking

305 lines total.

## What the tag contains

Explicit list (per `05-VERIFICATION.md` Environment Lock section):

**✓ CONTAINS:**
- `ui/package.json` (with `build:mock` + `preview:mock` scripts)
- `ui/package-lock.json`, `requirements.txt`, `requirements-dev.txt`
- All CDK source under `infrastructure/`
- All `agent/`, `api_lambda/`, `lambda/` source
- All Phase 5 SUMMARYs (01-07)
- `05-DEPLOY-OUTPUTS.md` — captured `ApiEndpoint` + `AgentRuntimeArn`
- `05-VERIFICATION.md` — this phase's verification record
- `DEMO-RUNBOOK.md` — presenter-facing demo-day guide

**✗ DOES NOT CONTAIN:**
- `ui/dist/`, `ui/dist-mock/` — git-ignored build output
- `node_modules/`, `.venv*/` — git-ignored
- The live AWS resources themselves (those live in the account, not the repo)

Per D-11, the lock is "lockfile verification + captured deployed ARNs". Plan 03 Task 3 step 6 + Plan 07 Task 1 together prove reproducibility from those sources. DEMO-RUNBOOK.md §1 step 6 is the authoritative presenter-laptop rebuild recipe.

## Self-Check: PASSED

- [x] Reproducibility gate: all 5 steps exit 0 from clean tree
- [x] `ui/.gitignore` still excludes `dist`; dists remain rebuildable not committed
- [x] `05-VERIFICATION.md` `status: passed` in frontmatter
- [x] Zero `(filled by Plan …)` stubs remain
- [x] Zero `⏳ PENDING` markers remain
- [x] All 3 ROADMAP success criteria marked verified
- [x] Environment Lock Evidence section contains what-the-tag-does/doesn't-contain explicit lists
- [x] Tag `demo-v1.0` cut (user-driven Task 2)
- [x] Annotated tag (verified via `git cat-file -t demo-v1.0` = `tag`)
- [x] No blocking gaps
- [x] Known issue (T-24h visual rehearsal) logged for demo-day follow-through

## Key files

### Modified (this plan)
- `.planning/phases/05-demo-hardening/05-VERIFICATION.md` — commit `2deee90` (pre-tag) + footer patch after tag cut

### Created (this plan)
- `.planning/phases/05-demo-hardening/05-07-SUMMARY.md` — this file

## Phase 5 closes with

- 7/7 plans complete
- 3/3 ROADMAP Success Criteria verified
- 0 blocking gaps
- `demo-v1.0` annotated tag cut on `main`
- DEMO-RUNBOOK.md T-24h visual rehearsal scheduled as the last pre-demo step

## Suggested next step

```
/gsd-complete-milestone v1.0
```

That command archives the milestone and evolves PROJECT.md for the next cycle (likely v2.0 — the deferred items in STATE.md are: UI-03 LLM call-script, UI-04 LLM usage narrative, DEMO-03 pre-warm script, DEMO-04 frozen-env lock, PROD-01 live CRM, PROD-02 self-service portal).
