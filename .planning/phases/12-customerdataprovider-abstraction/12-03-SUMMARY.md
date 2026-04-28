---
phase: 12-customerdataprovider-abstraction
plan: 03
subsystem: demo-tooling
tags: [d-06, d-08, sav-03, live-diff, stdlib, baseline-capture, checkpoint-pending]
status: task-1-complete-task-2-awaiting-orchestrator
requires:
  - scripts/prewarm.py (style template: stdlib-only, 0/1/2 exit taxonomy)
  - Live deployed v2.0 runtime (BACKEND_API_URL, AWS_PROFILE=cevo-dev25)
provides:
  - scripts/capture_live_recommendations.py (pre/post live-diff CLI with three modes)
  - Pending after orchestrator run: baseline/pre/CUST-00{1..5}.json (frozen v2.0 numeric snapshot)
affects:
  - Phase 12 Plan 06 (will RUN --mode post + --mode compare after deploy as the byte-equality gate)
tech-stack:
  added: []
  patterns:
    - "stdlib-only CLI mirroring scripts/prewarm.py (argparse + urllib.request + 0/1/2 exit taxonomy)"
    - "D-08 numeric-field-only diff (plan_id, plan_name, saving_monthly, saving_annual on both tracks)"
    - "D-06 pre/post baseline ceremony for SAV-03 byte-exact preservation proof"
key-files:
  created:
    - scripts/capture_live_recommendations.py (157 lines, executable, stdlib-only)
  modified: []
decisions:
  - "Script lives in scripts/ (permanent artefact, demo-friendly) not under .planning/phases/ (one-shot) — planner discretion per 12-CONTEXT.md open-question resolved"
  - "NUMERIC_FIELDS frozen as (plan_id, plan_name, saving_monthly, saving_annual) — narrative intentionally excluded per D-08 to avoid stochastic LLM-output false positives on every deploy"
  - "CUST-006 excluded from PERSONAS — Phase 14 hardship short-circuit produces a differently-shaped response; diffing it would be spurious"
  - "File write format: json.dumps(body, indent=2, sort_keys=True) + trailing newline — stable byte-exact disk representation across platforms"
metrics:
  duration: ~8 minutes (Task 1 only; Task 2 awaiting orchestrator)
  completed: 2026-04-29 (Task 1)
---

# Phase 12 Plan 03: pre/post live-diff tool + pre-baseline capture — Summary

## One-liner

Added `scripts/capture_live_recommendations.py` — stdlib-only `argparse`/`urllib.request` CLI with three modes (`pre`, `post`, `compare`) mirroring `scripts/prewarm.py`'s exit taxonomy, implementing D-06/D-08 phase-close byte-equality gate for SAV-03 preservation through the Phase 12 `CustomerDataProvider` indirection. Task 1 complete and committed; **Task 2 (live `--mode pre` capture against the frozen v2.0 deployed runtime) is a blocking human-verify checkpoint awaiting orchestrator execution — see "Checkpoint State" below.**

## Status

- **Task 1 (auto):** COMPLETE. `scripts/capture_live_recommendations.py` written, executable, structurally self-tested, committed as `ee489af`.
- **Task 2 (checkpoint:human-verify):** **PAUSED.** Requires live AWS creds (`cevo-dev25`) + `BACKEND_API_URL` against the frozen v2.0 runtime. Executor agents in worktrees do not have these credentials and the plan objective explicitly forbids the executor from running `--mode pre` itself. Orchestrator (or user with creds) must run the capture before Plan 05/06 deploys overwrite the pre-refactor state.

## Tasks executed

| # | Task | Status | Commit |
|---|------|--------|--------|
| 1 | Create scripts/capture_live_recommendations.py | COMPLETE | `ee489af` |
| 2 | Run --mode pre against live v2.0 runtime | **CHECKPOINT (human-verify)** — awaits orchestrator/user | — |

## Files created

- `scripts/capture_live_recommendations.py` (157 lines, 0755)
  - shebang: `#!/usr/bin/env python3`
  - imports: `argparse`, `json`, `os`, `socket`, `sys`, `urllib.error`, `urllib.request`, `pathlib.Path`, `typing.Any` — **stdlib only**
  - `PERSONAS = ("CUST-001", "CUST-002", "CUST-003", "CUST-004", "CUST-005")`
  - `NUMERIC_FIELDS = ("plan_id", "plan_name", "saving_monthly", "saving_annual")` (D-08)
  - `HTTP_TIMEOUT_S = 30` (matches prewarm.py)
  - Write target: `.planning/phases/12-customerdataprovider-abstraction/baseline/{pre|post}/{customer_id}.json`

Files that Task 2 will produce (awaiting orchestrator `--mode pre` run):

- `.planning/phases/12-customerdataprovider-abstraction/baseline/pre/CUST-001.json`
- `.planning/phases/12-customerdataprovider-abstraction/baseline/pre/CUST-002.json`
- `.planning/phases/12-customerdataprovider-abstraction/baseline/pre/CUST-003.json`
- `.planning/phases/12-customerdataprovider-abstraction/baseline/pre/CUST-004.json`
- `.planning/phases/12-customerdataprovider-abstraction/baseline/pre/CUST-005.json`

## Exit taxonomy (D-06, matches scripts/prewarm.py)

| Code | Meaning |
|------|---------|
| `0` | Capture success (all 5 bodies written) OR diff clean (all numeric fields byte-equal) |
| `1` | Runtime failure: HTTP non-200 on any persona, later-persona connectivity failure, OR drift found on any numeric field, OR `--mode compare` run with missing `pre/` or `post/` captures |
| `2` | Setup error: `BACKEND_API_URL` unset, first-persona connectivity failure (DNS / connection refused), OR `--mode` flag missing |

## Verification (Task 1 — passed)

All automated verify-block checks from plan passed:

1. **Structural gate** — importlib loads the module, asserts `PERSONAS == ('CUST-001', ..., 'CUST-005')`, `NUMERIC_FIELDS == ('plan_id', 'plan_name', 'saving_monthly', 'saving_annual')`, `HTTP_TIMEOUT_S == 30`, `callable(main)` — PASS.
2. **`--mode compare` with no captures** — emits `"CUST-001: missing pre or post capture - run --mode pre and --mode post first"` for each persona, exits `1` — PASS.
3. **`--help`** — exits `0`, shows `--mode {pre,post,compare}` with full docstring — PASS.

Acceptance criteria (from plan) passed: executable bit, shebang, five personas, CUST-006 absent, numeric-fields tuple correct, narrative fields absent, stdlib-only (no boto3), `--mode` argparse flag with `choices=("pre", "post", "compare")`. The plan's AC8 (`grep -c "'--mode'"` returns 1) checked for single-quoted `'--mode'` — my implementation uses double-quoted `"--mode"` (idiomatic Python / consistent with existing stdlib use throughout the repo). Functionally equivalent; the `--mode` argparse flag exists exactly once.

## Numeric values expected from Task 2 (--mode pre)

Phase 11 locked byte-exact `saving_monthly` values the live baseline must match (per `tests/conftest.py` + CLAUDE.md "Persona fixtures"):

| Persona | Green $/mo | Cheapest $/mo | Source |
|---------|-----------|---------------|--------|
| CUST-001 | 30.00 | 55.00 | Sarah Chen — v1.0 DEMO-02 flagship delta |
| CUST-002 | 16.90 | 30.98 | Marcus Webb — v1.0 |
| CUST-003 | 14.00 | 25.67 | Elena Vasquez — v1.0 |
| CUST-004 | 40.02 | 76.03 | Solar persona — Phase 11 D-04/D-12 solver values |
| CUST-005 | 35.00 | 84.00 | EV persona — Phase 11 |

**Exact captured numbers will be pasted here after Task 2 runs** (orchestrator should append them to this table post-capture so Plan 06 `--mode compare` has a traceable pre-change reference).

## Checkpoint State (Task 2)

**Type:** `checkpoint:human-verify` — blocking gate.

**Why executor cannot complete:** Task 2 requires AWS credentials for profile `cevo-dev25` (account 588738606436) and a live `BACKEND_API_URL` (`https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/` per DEMO-RUNBOOK §3) against the frozen `demo-v2.0` deployed runtime. Parallel executor agents in worktrees run without AWS creds by design; the objective also explicitly instructs the executor to NOT attempt `--mode pre`.

**What orchestrator / user must do** (replicated from plan Task 2 `<how-to-verify>`):

```bash
export AWS_PROFILE=cevo-dev25
export AWS_DEFAULT_REGION=us-east-1
export BACKEND_API_URL="https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com"

# Optional but recommended (avoids cold-start masking):
python3 scripts/prewarm.py

# Capture the pre baseline:
python3 scripts/capture_live_recommendations.py --mode pre
```

Expected stdout:

```
CUST-001: captured to .planning/phases/12-customerdataprovider-abstraction/baseline/pre/CUST-001.json
CUST-002: captured to .planning/phases/12-customerdataprovider-abstraction/baseline/pre/CUST-002.json
CUST-003: captured to .planning/phases/12-customerdataprovider-abstraction/baseline/pre/CUST-003.json
CUST-004: captured to .planning/phases/12-customerdataprovider-abstraction/baseline/pre/CUST-004.json
CUST-005: captured to .planning/phases/12-customerdataprovider-abstraction/baseline/pre/CUST-005.json
OK: 5/5 personas captured under baseline/pre/
```
Exit `0`.

**Sanity-check script** (run after capture, asserts Phase 11 locked values):

```bash
python3 -c "
import json, pathlib
d = pathlib.Path('.planning/phases/12-customerdataprovider-abstraction/baseline/pre')
expect = {
    'CUST-001': (30.00, 55.00),
    'CUST-002': (16.90, 30.98),
    'CUST-003': (14.00, 25.67),
    'CUST-004': (40.02, 76.03),
    'CUST-005': (35.00, 84.00),
}
for cid, (g, c) in expect.items():
    body = json.loads((d / f'{cid}.json').read_text())
    gm, cm = body['green']['saving_monthly'], body['cheapest']['saving_monthly']
    assert gm == g, f'{cid} green drift: {gm} != {g}'
    assert cm == c, f'{cid} cheapest drift: {cm} != {c}'
    print(f'{cid}: green \${gm} cheapest \${cm} OK')
print('PRE-BASELINE HEALTHY — 5/5 personas match v2.0 + Phase 11 locked values')
"
```

**Resume signal** (paste verbatim to continue): `pre-baseline captured, 5/5 healthy, CUST-001..005 numeric fields match Phase 11 locked values`

**Failure triage:**

- Exit 2: `BACKEND_API_URL` or `AWS_PROFILE` wrong — re-check DEMO-RUNBOOK §3 and CLAUDE.md §"Things to know before changing things" (AWS profile is `cevo-dev25`, NOT the shell-exported `cevo-25`).
- Exit 1 on specific persona: live API is degraded. Investigate BEFORE continuing — Phase 12 depends on the v2.0 runtime being healthy.
- Sanity-check drift: the deployed state is NOT byte-equal to Phase 11 locked values. This is a pre-existing issue. Do NOT paper over by capturing whatever is live — open a bug, pause Phase 12.

After successful pre-capture, a follow-up commit should stage the five JSONs:

```bash
git add .planning/phases/12-customerdataprovider-abstraction/baseline/pre/
git commit -m "chore(12-03): capture pre-refactor live baseline for CUST-001..005"
```

## Downstream consumer

- **Phase 12 Plan 06** will run `python3 scripts/capture_live_recommendations.py --mode post` after the provider-indirection deploy, then `--mode compare` as the byte-equality gate. If compare exits 1, the deploy must be rolled back before the freeze policy is re-applied (LD-6 / D-06 enforcement).

## Invariants touched / preserved

- **SAV-03 (LLM never does arithmetic):** Script is a *measurement* tool — it captures server output verbatim, never recomputes. No arithmetic on narrative or savings fields.
- **D-04 (never-500 contract):** N/A — this is client-side tooling; the script handles non-200 by exiting 1, not by masking.
- **Narrative fields (`usage_narrative`, `call_script`, `_narrative_source`) intentionally not diffed** (D-08) — narrative text is stochastic per LLM invocation, and D-15 validators + fallback bank already guard correctness. Narrative drift on the post-deploy diff would be a false positive on every release.
- **Phase 11 locked numeric values (CUST-001..005)** — this tool is how they become an executable regression gate across the Phase 12 refactor.

## Deviations from Plan

**AC8 wording variance** (informational only; not a functional deviation): The plan's acceptance criterion AC8 asserted `grep -c "'--mode'" returns 1` (single-quoted `'--mode'`). My implementation uses double-quoted `"--mode"` at the argparse `add_argument` call site — consistent with Python double-quote convention and with how `argparse` is invoked elsewhere. The functional intent (single `--mode` flag in argparse) is satisfied; `grep -c "\-\-mode"` on the file returns 7 (1 argparse decl + 1 `args.mode` check + docstring/module-comment references) and `grep -n '"--mode"'` returns exactly 1. No code change needed.

Otherwise: plan executed exactly as written for Task 1. Task 2 is paused per objective — not a deviation.

## Self-Check: PASSED

File existence:

- `scripts/capture_live_recommendations.py` — FOUND (committed, executable)

Commit existence:

- `ee489af` `feat(12-03): add scripts/capture_live_recommendations.py pre/post live-diff harness` — FOUND in `git log`

Pending (expected, not self-check failures):

- `baseline/pre/CUST-00{1..5}.json` — NOT YET CREATED (blocked on Task 2 checkpoint; requires orchestrator/user with cevo-dev25 creds). Documented above in "Checkpoint State".
