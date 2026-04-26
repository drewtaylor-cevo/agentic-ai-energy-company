---
phase: 09-pre-warm-tooling-eval-harness-keep-alive
plan: 04
subsystem: tests
tags: [eval-harness, smoke-gated, phase-9, demo-03, closeout-gate, sc-4]
requires:
  - agent.narrative.banned_terms (BANNED_REGEX, NUMERIC_REGEX — frozen Phase 6)
  - tests/test_fallbacks_pass_validator.py (_fails_rules shape + cap constants — D-12 mirror)
  - Live deployed API at $BACKEND_API_URL returning Phase 6/7 narrative shape
provides:
  - tests/test_narrative_eval_live.py (3 parametrized smoke tests per persona)
  - ROADMAP SC-4 closeout gate (DEMO-03 completion evidence when live-green)
  - D-14 Phase 10 DEMO-RUNBOOK T-48h / T-24h / T-10min invocation target
affects:
  - Offline non-smoke baseline: +0 tests (collect 0 under `-m "not smoke"`)
  - Smoke bucket: +3 tests (one per persona under `-m smoke`)
tech-stack:
  added: []
  patterns:
    - "pytestmark = [pytest.mark.smoke, pytest.mark.skipif(not BACKEND_API_URL, …)]"
    - "Module-level `BACKEND_API_URL = os.environ.get(...).rstrip('/')` (mirrors test_backend_api_smoke.py line 11)"
    - "requests.get + timeout=60 (mirrors test_backend_api_smoke.py line 29 byte-for-byte)"
    - "Direct regex import from banned_terms — no copy-paste drift (D-12)"
    - "Single-parametrize persona × inner for-loop (track, field) — 3 HTTP calls, 12 field checks per call"
key-files:
  created:
    - tests/test_narrative_eval_live.py (113 LOC)
  modified: []
decisions:
  - "Kept single @parametrize over customer_id; looped inside over (green, cheapest) × (usage_narrative, call_script) — D-11 collapses 6 potential HTTP calls into 3"
  - "Added `if not value: return 'empty string'` guard to _fails_rules — small tightening over the fallback-focused analog (the live API must never return empty narratives; Phase 6 fallbacks guarantee non-empty but the harness catches the regression)"
  - "Did NOT add a second AgentCore-direct test function — D-10 explicit rejection (HTTP-only, no boto3, no AWS creds requirement)"
  - "Did NOT chain with `?prewarm=1` — D-14 orthogonality (harness hits the normal path; Plan 01 prewarm.py validates the pre-warm route separately)"
metrics:
  duration: 14m
  completed_date: "2026-04-26"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
---

# Phase 09 Plan 04: Smoke-Gated Live Narrative Eval Harness Summary

## One-liner

Shipped `tests/test_narrative_eval_live.py` — a 113-line smoke-gated live eval harness that asserts every persona × card narrative passes Phase 6 validator rules (regex + word/char caps) and that the Phase 7 `_narrative_source` marker never leaks to the client, serving as the ROADMAP SC-4 closeout gate for DEMO-03.

## Tasks Executed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create `tests/test_narrative_eval_live.py` — smoke-gated live narrative eval harness | `ce9ac9b` | tests/test_narrative_eval_live.py |

## Verification Evidence

### File Shape

- Line count: **113** (target: ~90-110; 3 over due to module docstring length — inside acceptable tolerance per plan's "~90-110" soft target).
- AST parse: ✓ valid Python
- Imports: `os`, `pytest`, `requests`, `from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX` (D-12 direct-import contract)

### Structural Assertions (all plan greps satisfied)

| Check | Result |
|-------|--------|
| `from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX` | PASS |
| `BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "").rstrip("/")` (exact) | PASS |
| `pytestmark = [ ... pytest.mark.smoke, pytest.mark.skipif(...) ]` list form | PASS |
| Skip reason contains `BACKEND_API_URL not set` | PASS |
| `_USAGE_NARRATIVE_MAX_WORDS = 20` | PASS |
| `_CALL_SCRIPT_MAX_WORDS = 22` | PASS |
| `_USAGE_NARRATIVE_MAX_CHARS = 140` | PASS |
| `_CALL_SCRIPT_MAX_CHARS = 180` | PASS |
| `def _fails_rules(` helper with `if not value: return "empty string"` guard | PASS |
| `NUMERIC_REGEX.search(value)` + `BANNED_REGEX.search(value)` | PASS |
| `"_narrative_source" not in body` (Phase 7 D-06) | PASS |
| `requests.get(...)` + `timeout=60` | PASS |
| `["CUST-001", "CUST-002", "CUST-003"]` parametrize | PASS |
| Exactly ONE `@pytest.mark.parametrize` (NO track double-parametrize) | PASS |
| No `FALLBACKS` / `boto3` / `?prewarm=1` / `saving_monthly` / `saving_annual` | PASS (all 5 forbidden strings absent) |

### Collection Contract

**`pytest --collect-only -q -m "not smoke" tests/test_narrative_eval_live.py`:**

```
no tests collected (3 deselected) in 0.84s
```

Expected: 0 collected, 3 deselected. ✓ Matches D-09 (module is smoke-marked so it's deselected under `-m "not smoke"`).

**`pytest --collect-only -q -m smoke tests/test_narrative_eval_live.py`:**

```
tests/test_narrative_eval_live.py::test_narrative_eval_live[CUST-001]
tests/test_narrative_eval_live.py::test_narrative_eval_live[CUST-002]
tests/test_narrative_eval_live.py::test_narrative_eval_live[CUST-003]

3 tests collected in 0.11s
```

Expected: 3 collected. ✓ Matches D-11 (one HTTP GET per persona).

### Offline Full-Suite Baseline Preservation

**`AWS_PROFILE=cevo-dev25 SKIP_AWS_SMOKE=1 pytest -m "not smoke"`:**

```
= 1 failed, 168 passed, 13 skipped, 34 deselected, 1 warning in 206.27s (0:03:26) =
```

- **168 passed** — well above the plan's `≥88 passed` baseline bar (plan text: "baseline 81 + Plan 02's 7").
- 34 deselected = the 3 new smoke tests from this plan + 31 pre-existing smoke tests from other files.
- The single failure (`test_backend_api_synth.py::test_agentcore_stack_has_ssm_parameter`) is a **pre-existing environment issue** (aws_cdk version mismatch — `aws_bedrock_agentcore_alpha` module renamed). **Verified pre-existing by re-running the failing test with this plan's file removed from `tests/` — same `ImportError` reproduces.** Out of scope per Rule 4 scope boundary (unrelated to `tests/test_narrative_eval_live.py`). Logged here for transparency; fixing the CDK alpha-construct import is not a narrative-eval concern.

### Files Unchanged (per plan contract)

- `tests/conftest.py` — `git diff` empty (verified)
- `pytest.ini` — `git diff` empty (`smoke:` marker was already registered)
- `agent/narrative/banned_terms.py` — `git diff` empty (frozen Phase 6 source-of-truth)
- No changes to `agent/`, `api_lambda/`, `infrastructure/`, `ui/`, or `scripts/` (verified via `git status`)

## Threat Model Coverage

All dispositions from the plan's threat register are preserved:

| Threat ID | Disposition | How preserved |
|-----------|-------------|---------------|
| T-09-11 (Info disclosure via assertion messages) | mitigate | `_fails_rules` returns truncated `value!r` repr in failure messages; no auth tokens in response bodies; acceptable for pytest failure output on non-production demo endpoint |
| T-09-12 (Spoofing via `BACKEND_API_URL`) | accept | Read-only GETs to operator-supplied URL; no writes, no side effects |
| T-09-13 (Tampering via banned_terms import) | accept | Read-only import; `banned_terms.py` has no side effects at import time (only compiles regexes) |

No new threat surface introduced. Test-only delta; inherits Phase 7 trust boundaries unchanged.

## Claude's-Discretion Calls

1. **Kept single-parametrize over persona** with inner for-loop over `(green, cheapest) × (usage_narrative, call_script)`. This matches D-11 (3 HTTP calls total) while still covering all 12 narrative-field combinations.
2. **Added `if not value: return "empty string"` guard to `_fails_rules`** — small tightening over `test_fallbacks_pass_validator.py::_fails_rules` (which trusts FALLBACKS to be non-empty by construction). The live harness catches the regression if the agent ever returns an empty narrative.
3. **Did NOT add a second AgentCore-direct test** — D-10 explicit rejection (HTTP-only; no boto3; no AWS creds requirement for marginal observability).
4. **Did NOT chain with `?prewarm=1`** — D-14 orthogonality. This harness hits the normal path; `scripts/prewarm.py` from Plan 01 validates the pre-warm route separately.
5. **Did NOT write a `09-EVAL-SAMPLES.md`** — D-15 rejection (`scripts/capture_samples.py` already covers the sample-capture artefact).

## Deviations from Plan

None. Plan executed exactly as written — every constant, import, assertion, and forbidden pattern specified in the plan body is present/absent per spec.

## Live Execution (Deferred)

Live invocation is **Phase 9 closeout gate D-22 step 2** — not part of this plan's automated verify:

```bash
BACKEND_API_URL=https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com pytest tests/test_narrative_eval_live.py -m smoke
```

Expected: `3 passed` when the live stack is warm and narrative generation is healthy.

## Self-Check: PASSED

**Created file exists:**
- `tests/test_narrative_eval_live.py` — FOUND (113 LOC, AST-parseable)

**Commit exists in git log:**
- `ce9ac9b` — FOUND (`feat(09-04): add smoke-gated live narrative eval harness`)

**SUMMARY file self-reference:**
- `.planning/phases/09-pre-warm-tooling-eval-harness-keep-alive/09-04-SUMMARY.md` — this file, about to be committed.
