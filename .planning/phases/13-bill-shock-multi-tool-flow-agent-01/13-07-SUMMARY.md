---
phase: 13-bill-shock-multi-tool-flow-agent-01
plan: 07
subsystem: per-flow-prewarm-gate-and-live-fabrication-detectors
tags:
  - per-flow-prewarm-gate
  - sighting-shot
  - latency-floor
  - cloudwatch-counter
  - d-18-d-19-d-21
  - a-01-cust003-rotation
  - a-03-break-glass
  - phase-13
  - agent-01a

# Dependency graph
requires:
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plan 02)
    provides: reasoning_trace extractor + RecommendationResponse.reasoning_trace field — makes multi-tool traffic discernible from single-tool traffic at the response body, which the sighting shot + canary rely on for flow classification
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plan 03)
    provides: 4 @tool wrappers + preference-ordered _BASE_SYSTEM_PROMPT — the tool set the CUST-003 multi-tool gate actually exercises at the deployed stack
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plan 04)
    provides: FourToolCapHook + stop_reason=="cancelled" D-04 routing + reasoning_trace attach on both happy and fallback paths — the cap surface the sighting shot validates against
provides:
  - scripts/prewarm.py — per-flow gate map (GATE_MS dict, not scalar), 3-pass warming (A-03 promotion), CUST-003 rotation (A-01), preserved 0/1/2 exit taxonomy
  - tests/test_prewarm_script.py — 4 new unit tests locking the per-flow gate map + rotation + warming-pass count; 4 existing tests updated for new 2-persona × 3-pass shape
  - tests/test_narrative_eval_live.py — 2 new smoke-marked tests: test_agent01_latency_floor (D-19, CUST-003 > 1000ms) + test_agent01_tools_actually_invoked (D-21, CloudWatch Invocations >= 2)
  - A-03 sighting-shot operator gate — documented in this SUMMARY with decision tree; operator-runnable against deployed dev-alias stack before Plan 08 lift
affects:
  - Plan 13-08 (pre-deploy smoke + CDK diff gate — prewarm.py changes do not affect CDK-synth asset hashes because scripts/ is not in any Lambda bundle; API Lambda diff still expected zero)
  - Plan 13-09 (CLAUDE.md addendum — documents the per-flow gate rationale, Pitfall 5 CloudWatch-lag invariant, and A-03 break-glass decision tree for future presenter rehearsals)
  - DEMO-RUNBOOK §T-24h rehearsal — now automated (per-flow prewarm gate) rather than operator-judged; Marcus → Elena persona swap documented
  - Phase 16 DEMO-09 (future 5-persona rotation will extend the GATE_MS map to CUST-004 + CUST-005 + CUST-006 without restructuring)

# Tech tracking
tech-stack:
  added: []  # ZERO new dependencies — CONTEXT.md §Out of scope commitment upheld
  patterns:
    - "Per-flow gate map with aggregation exit-0-iff-all-pass — D-18 canonical shape. Future phases extending the rotation add entries to GATE_MS without touching the gate loop."
    - "Timeout sentinel = max(GATE_MS.values()) — timeouts reliably push the median over whichever per-flow gate applies; preserves the D-08 intent without coupling to any single scalar."
    - "Warming-pass promotion (2 → 3) as break-glass insurance on zero-headroom gates — A-03 pattern reusable for future latency-tight flows."
    - "Smoke-gated fabrication detectors layered in three independent dimensions: D-19 latency floor (temporal), D-20 cross-persona byte-diff (offline), D-21 CloudWatch counter (external observability). Any ONE signal turning red is strong evidence of C5 regression."

key-files:
  created:
    - .planning/phases/13-bill-shock-multi-tool-flow-agent-01/13-07-SUMMARY.md
  modified:
    - scripts/prewarm.py (+per-flow GATE_MS map, +WARMING_PASSES=3, CUST-002→CUST-003 rotation, preserved 0/1/2 exit taxonomy)
    - tests/test_prewarm_script.py (+4 new unit tests + 4 existing tests updated for 2-persona × 3-pass shape)
    - tests/test_narrative_eval_live.py (+test_agent01_latency_floor + test_agent01_tools_actually_invoked, both smoke-marked)

key-decisions:
  - "GATE_MS defined as dict[str, int] rather than TypedDict or dataclass — minimum ceremony, direct indexing in the gate loop, matches the existing module-level-constant style of prewarm.py. Adding a persona = adding a dict key; no restructuring."
  - "Timeout sentinel explicitly set to max(GATE_MS.values()) not a hardcoded 3000 — the value auto-tracks whichever gate is highest, so if a future phase tightens CUST-001 to 2800ms the timeout semantics still work without code change."
  - "Warming-loop restructure wraps the existing URL-hit body in an inner `for pass_idx in range(WARMING_PASSES)` loop rather than duplicating the body. Preserves the error-handling fingerprint (HTTPError → exit 1; URLError on persona[0] pass 0 → exit 2 setup error, else exit 1 runtime) without drift."
  - "Existing test mock side_effect lists updated in Task 7.1 GREEN as a Rule 1 auto-fix — the tests were shaped for 3 personas × 1 warming pass = 3 + 9 = 12 responses; new shape is 2 personas × 3 warming passes = 6 + 6 = 12 responses. Same total, different distribution; log-line assertions switched to the 'pass N/3' format."
  - "Task 7.3 smoke tests' pytestmark relies on module-level `pytestmark = [pytest.mark.smoke, pytest.mark.skipif(...)]` AND explicit @pytest.mark.smoke decorators (belt-and-braces). `-m 'not smoke'` collects zero tests from the module (verified)."
  - "Task 7.4 A-03 sighting shot is documented as an OPERATOR-RUNNABLE gate in this SUMMARY — the worktree executor cannot run it (no deployed stack reachable from a parallel-executor context), and Plan 08 explicitly owns the lift ceremony. The decision tree + break-glass options are pinned here so the operator can execute against the pre-lift dev-alias with full rationale available."

patterns-established:
  - "Per-flow gate shape (GATE_MS dict) + exit-0-iff-all-pass — canonical for any future multi-persona warm-median check. Phase 16 5-persona extension adds 3 keys; no other change."
  - "CloudWatch Invocations query pattern with SSM fallback — the env-var primary + SSM secondary resolution for TOOLS_LAMBDA_NAME is the canonical pattern for any future AWS/Lambda-namespace smoke-marked assertion (Phase 14 hardship-tool counter, Phase 16 5-persona canary)."
  - "Prose discipline for acceptance-criteria greps — planner pins exact integer match on literal-string greps (e.g. `grep -c 'time.sleep(90)' == 1`). Executor MUST avoid incidentally matching the literal string in comments/docstrings; describe the invariant in English when paraphrasing."

requirements-completed: []
  # AGENT-01a (warm p95 < 2500ms multi-tool) + AGENT-01 (bill-shock multi-tool flow)
  # are NOT fully complete at this plan — the offline mechanism is in place, but the
  # live sighting-shot measurement (A-03) is operator-pending and Plan 08's stack-lift
  # ceremony has not executed. Orchestrator completes both requirements at Wave 3
  # (Plan 13-13 cross-persona live canary) per the phase plan.

# Metrics
duration: ~18min
completed: 2026-04-29
---

# Phase 13 Plan 07: Per-Flow Prewarm Gate + D-19/D-21 Live Fabrication Detectors Summary

**`scripts/prewarm.py` gains a per-flow gate map + 3-pass warming + CUST-003 rotation; 2 new smoke-marked tests (D-19 CUST-003 > 1000ms latency floor + D-21 CloudWatch Invocations >= 2) layer onto the existing live eval harness; the A-03 sighting-shot gate is documented as an operator-runnable pre-lift decision tree — Phase 13's fabrication-detection surface is now three-dimensional (temporal + offline byte-diff + external observability) and Plan 08's lift ceremony has the measurement instrument it needs.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-04-29T~16:14Z (worktree re-based to 4039aa1)
- **Completed:** 2026-04-29T~16:32Z
- **Tasks:** 4 of 4 completed (3 auto-runnable + 1 operator-deferred) — 3 commits (1 TDD RED + 1 TDD GREEN + 1 single)
- **Files modified:** 3 (`scripts/prewarm.py`, `tests/test_prewarm_script.py`, `tests/test_narrative_eval_live.py`)
- **Files created:** 1 (`13-07-SUMMARY.md`)

## Accomplishments

- **`scripts/prewarm.py` — per-flow gate + A-01 rotation + A-03 3-pass warming:**
  - `PERSONAS = ["CUST-001", "CUST-003"]` — Marcus deprecated (A-01), Elena is the multi-tool target.
  - `GATE_MS: dict[str, int] = {"CUST-001": 3000, "CUST-003": 2500}` — per-flow map replaces the `MEDIAN_GATE_MS` scalar; the gate evaluation loop reads `gate_ms = GATE_MS[persona]` per iteration and aggregates exit-0-iff-all-pass. Pitfall 1 (silent scalar collapse) explicitly documented in an inline comment.
  - `WARMING_PASSES = 3` — A-03 promotion from 2. The warming loop wraps the existing URL-hit body in an inner `for pass_idx in range(WARMING_PASSES)` loop, preserving the per-hit error-handling fingerprint (HTTPError / URLError / status != 204 all route to the right exit).
  - `_TIMEOUT_SENTINEL_MS = max(GATE_MS.values())` — D-08 timeout behaviour preserved and auto-tracks the highest gate without a hardcoded `3000`.
  - **0/1/2 exit taxonomy preserved**: URLError on `PERSONAS[0]`'s FIRST warming pass → exit 2 (setup error, cannot reach API). Any other URLError, HTTPError, non-204 warm response, or median-over-gate → exit 1 (runtime failure). All gates clear → exit 0.
- **`tests/test_prewarm_script.py` — 4 new unit tests + 4 existing updated (Rule 1):**
  - `test_personas_rotation_is_cust001_and_cust003` — A-01 rotation assertion.
  - `test_gate_ms_is_per_flow_map_not_scalar` — D-18 per-flow map; Pitfall 1 regression guard asserting `MEDIAN_GATE_MS` scalar is GONE (`assert not hasattr(module, 'MEDIAN_GATE_MS')`).
  - `test_warming_passes_is_three` — A-03 promotion assertion.
  - `test_measurement_samples_and_settle_wait_unchanged` — load-bearing Phase 9 SC-2 constants (SETTLE_WAIT_S=30, MEASUREMENT_SAMPLES=3, HTTP_TIMEOUT_S=30) locked against accidental retune.
  - Existing tests (`test_prewarm_happy_path_exit_0`, `test_prewarm_gate_fail_exit_1`, `test_prewarm_measurement_timeout_pushes_median`, `test_prewarm_per_call_log_format`) updated for the new 2-persona × 3-pass shape: side_effect lists resized from 3+9=12 to 6+6=12 responses; log-line assertions switched to the 'prewarm CUST-XXX pass N/3:' format + per-flow 'PASS (<3000ms)' / 'PASS (<2500ms)' summary tokens.
- **`tests/test_narrative_eval_live.py` — 2 new smoke tests for live AGENT-01a gates:**
  - `test_agent01_latency_floor` (D-19): fires `GET /recommendations/CUST-003` and asserts elapsed > 1000ms. Sub-1s on a 2-3 tool turn is a C5 fabrication signature — each Tools Lambda round-trip costs >=400ms so real multi-tool is comfortably above 1000ms.
  - `test_agent01_tools_actually_invoked` (D-21): fires CUST-003 lookup, sleeps 90s (CloudWatch emission lag), queries `AWS/Lambda` `Invocations` metric via `get_metric_statistics` with `Dimensions=[{"Name": "FunctionName", "Value": <tools-lambda-name>}]`, asserts `total_invocations >= 2`. TOOLS_LAMBDA_NAME env var primary + SSM parameter `/customer-tariff/tools-lambda-name` fallback; `pytest.skip` if neither resolves (no silent false-positive). Pitfall 5 comment + docstring flag the 90s sleep as load-bearing.
  - Both tests inherit module-level `pytestmark = [pytest.mark.smoke, pytest.mark.skipif(not BACKEND_API_URL, ...)]` AND carry explicit `@pytest.mark.smoke` decorators. `pytest -m "not smoke"` collects zero tests from the module (verified).

## Task Commits

Tasks 7.1 + 7.2 are functionally combined into one TDD RED/GREEN cycle — the plan's Task 7.2 tests ARE the RED commit that fails before Task 7.1's implementation lands. Task 7.3 is a single test-only commit. Task 7.4 is operator-deferred (see §A-03 Sighting Shot).

1. **Task 7.2 RED (serves as Task 7.1 RED too):** failing `test_personas_rotation_is_cust001_and_cust003` + `test_gate_ms_is_per_flow_map_not_scalar` + `test_warming_passes_is_three` + `test_measurement_samples_and_settle_wait_unchanged` — `8be441f` (test)
2. **Task 7.1 GREEN:** `scripts/prewarm.py` per-flow GATE_MS map + 3-pass warming + CUST-003 rotation + existing-test mock side_effect updates — `5c030f7` (feat)
3. **Task 7.3:** `test_agent01_latency_floor` + `test_agent01_tools_actually_invoked` (both smoke-marked) — `69e44d6` (test)

_No refactor commits. No deviations beyond the Rule 1 auto-fix on existing prewarm tests' mock shape (documented in §Deviations below)._

## Post-edit line positions (for Plans 08 + 09 + 16 reference)

Plan 08 pre-deploy gate reads `GATE_MS` + `WARMING_PASSES` as the prewarm mechanism under test; Plan 09 CLAUDE.md addendum cites the module-level constants; Plan 16 5-persona extension adds dict keys to `GATE_MS`.

| Symbol                                            | File                              | Line  |
| ------------------------------------------------- | --------------------------------- | ----- |
| `PERSONAS = ["CUST-001", "CUST-003"]`             | scripts/prewarm.py                | 39    |
| `GATE_MS: dict[str, int] = {`                     | scripts/prewarm.py                | 46    |
| `WARMING_PASSES = 3`                              | scripts/prewarm.py                | 55    |
| `_TIMEOUT_SENTINEL_MS = max(GATE_MS.values())`    | scripts/prewarm.py                | 64    |
| `for pass_idx in range(WARMING_PASSES):`          | scripts/prewarm.py                | 82    |
| gate loop `gate_ms = GATE_MS[persona]`            | scripts/prewarm.py                | 166   |
| `def test_personas_rotation_is_cust001_and_cust003` | tests/test_prewarm_script.py    | 257   |
| `def test_gate_ms_is_per_flow_map_not_scalar`       | tests/test_prewarm_script.py    | 267   |
| `def test_warming_passes_is_three`                  | tests/test_prewarm_script.py    | 282   |
| `def test_measurement_samples_and_settle_wait_unchanged` | tests/test_prewarm_script.py | 291 |
| `def test_agent01_latency_floor`                  | tests/test_narrative_eval_live.py | 133   |
| `def test_agent01_tools_actually_invoked`         | tests/test_narrative_eval_live.py | 154   |

## A-03 Sighting Shot

**Status: OPERATOR-PENDING (deferred from Plan 07 executor scope to pre-Plan-08 operator action).**

Per amendment A-03, the 2500ms CUST-003 gate has ZERO headroom against PITFALLS.md C1's 2600-5400ms training-knowledge estimate. The sighting shot is BLOCKING before Plan 08's stack-policy lift — if CUST-003 warm median exceeds 2500ms on the pre-lift dev-alias deployment, the operator invokes a break-glass pivot and Plan 08 does NOT proceed until the gate passes.

This worktree executor **cannot** run the sighting shot:
1. The parallel executor runs inside a git worktree without access to AWS credentials or a deployed dev-alias stack.
2. Plan 08 explicitly owns the stack-policy lift ceremony — the first deployment of the AGENT-01 code to the frozen stacks happens in Plan 08.
3. Running against the pre-lift deployed dev-alias (if one exists) is an operator-judgement call about Bedrock / AgentCore cost.

**Operator runbook (for execution before Plan 08 lift):**

### Setup

```bash
# 1. Confirm AGENT-01 code is built + deployable.
#    Options: (a) dev AgentCore runtime alias if one exists; (b) local docker build.
cd agent && docker build . -t tariff-agent:phase13-sighting

# 2. Export env against the DEV / pre-lift stack (NOT prod demo-v2.0 frozen).
export BACKEND_API_URL=https://<your-dev-api-id>.execute-api.us-east-1.amazonaws.com
export AWS_PROFILE=cevo-dev25
```

### Sighting run

```bash
# Fire prewarm 3 times back-to-back; record the CUST-003 median from each run.
for i in 1 2 3; do
  echo "=== Sighting shot run $i ==="
  python3 scripts/prewarm.py
done
```

### Decision tree

Record the 3 CUST-003 medians below before proceeding to Plan 08.

| Run | CUST-003 median (ms) | Exit code |
| --- | -------------------- | --------- |
| 1   | `<pending>`          | `<pending>` |
| 2   | `<pending>`          | `<pending>` |
| 3   | `<pending>`          | `<pending>` |

**Branches:**

- **GREEN — all 3 runs exit 0 (CUST-003 median < 2500ms on each):** Proceed to Plan 08 lift ceremony. Record the 3 medians + `prewarm` total runtime in the Plan 08 capture logs.

- **AMBER — any run exits 1 with CUST-003 median 2500–3499ms:** First-tool-cold is a likely cause (Bedrock microVM + Tools Lambda both cold).
  1. Apply keepalive: `BACKEND_API_URL=... bash scripts/demo-keepalive.sh` for ~10 minutes in a separate terminal.
  2. Re-shoot the 3-run sighting while keepalive is running.
  3. If median now < 2500ms consistently → Proceed with caution. Record keepalive duration in Plan 08 capture.
  4. If still ≥ 2500ms → escalate to BREAK-GLASS (below).

- **BREAK-GLASS — any run exits 1 with CUST-003 median ≥ 3500ms OR 3 runs confirm > 2500ms:** Apply one of the A-03 mitigations below. **Option 1 is recommended.**
  - **Option 1 (recommended):** Edit `_BASE_SYSTEM_PROMPT` in `agent/agent.py` — change the preference-ordered tool graph to REMOVE `detect_bill_shock` from the CUST-003 demo path. The `@tool detect_bill_shock` wrapper stays registered (Phase 14 hardship short-circuit reuses the dispatcher branch), but the prompt no longer suggests calling it on the bill-shock persona. This drops to a 2-tool flow (`get_hardship_flag` + `simulate_savings`) and still satisfies AGENT-01 "2–3 tool composition" because hardship check + recommendation = 2 tools. **Commit the prompt edit + re-run Plan 05's `TestCrossPersonaCanary` offline to confirm Elena's reasoning_trace now carries 2 entries, not 3.**
  - **Option 2:** Accept a single-tool CUST-003 demo (just `simulate_savings`). AGENT-01 loses the "visible reasoning" demo beat. Last resort; flag to user for milestone-level decision.
  - **Option 3 (NOT RECOMMENDED):** Swap `ConcurrentToolExecutor` → `SequentialToolExecutor`. This is a LATENCY REGRESSION, not a fix (sequential tool execution is strictly slower than concurrent). Documented here as a known footgun so a future developer doesn't reach for it.

### Exit condition for Plan 08 go-ahead

Section above populated with 3 median readings AND a recorded decision (GREEN / AMBER+keepalive / BREAK-GLASS option N). If BREAK-GLASS option 1 applied, the `_BASE_SYSTEM_PROMPT` edit is committed and Plan 05's TestCrossPersonaCanary passes against the new 2-entry trace shape.

**Rationale for pre-lift timing:** The sighting shot uses the pre-lift dev-alias because the frozen-prod stack is under `deny-Update:*` until Plan 08's lift. Running the shot against the frozen stack is possible only if it ALREADY has the AGENT-01 code, which it cannot until Plan 08 deploys — ordering makes pre-lift dev-alias the only viable target.

## Pre-computed grep-acceptance evidence

```
$ grep -c '^PERSONAS = \["CUST-001", "CUST-003"\]$' scripts/prewarm.py
1
$ grep -c '^GATE_MS' scripts/prewarm.py
1
$ grep -c '"CUST-001": 3000' scripts/prewarm.py
1
$ grep -c '"CUST-003": 2500' scripts/prewarm.py
1
$ grep -c 'WARMING_PASSES = 3' scripts/prewarm.py
1
$ grep -c 'for pass_idx in range(WARMING_PASSES)' scripts/prewarm.py
1
$ grep -c 'MEDIAN_GATE_MS' scripts/prewarm.py
0   # scalar removed; per-flow GATE_MS map replaces it
$ grep -c 'CUST-002' scripts/prewarm.py
0   # Marcus removed from rotation (A-01) — prose tightened so no incidental matches
```

```
$ grep -c 'def test_personas_rotation_is_cust001_and_cust003' tests/test_prewarm_script.py
1
$ grep -c 'def test_gate_ms_is_per_flow_map_not_scalar' tests/test_prewarm_script.py
1
$ grep -c 'def test_warming_passes_is_three' tests/test_prewarm_script.py
1
$ grep -c 'def test_measurement_samples_and_settle_wait_unchanged' tests/test_prewarm_script.py
1
```

```
$ grep -c 'def test_agent01_latency_floor' tests/test_narrative_eval_live.py
1
$ grep -c 'def test_agent01_tools_actually_invoked' tests/test_narrative_eval_live.py
1
$ grep -c '@pytest.mark.smoke' tests/test_narrative_eval_live.py
2   # explicit decorators on both new tests
$ grep -c 'pytest.mark.smoke' tests/test_narrative_eval_live.py
3   # 2 decorators + module-level pytestmark = [pytest.mark.smoke, ...]
$ grep -c 'time.sleep(90)' tests/test_narrative_eval_live.py
1   # single call-site; comment/docstring paraphrase to satisfy literal-grep acceptance
$ grep -cE 'Dimensions=\[\{"Name": "FunctionName"' tests/test_narrative_eval_live.py
1
$ grep -c 'CUST-003' tests/test_narrative_eval_live.py
9   # both new tests target CUST-003 per A-01 (existing parametrized test also hits CUST-003)
$ grep -c 'Pitfall 5' tests/test_narrative_eval_live.py
3   # header comment + docstring + inline comment — all flag the 60-90s CloudWatch lag
```

## TOOLS_LAMBDA_NAME resolution evidence (Plan 09 CLAUDE.md addendum reference)

The D-21 smoke test resolves the Tools Lambda function name via two mechanisms in order:

1. **Env var `TOOLS_LAMBDA_NAME`** (primary): `os.environ.get("TOOLS_LAMBDA_NAME")`. If set, use directly.
2. **SSM parameter `/customer-tariff/tools-lambda-name`** (fallback): `boto3.client("ssm").get_parameter(Name="/customer-tariff/tools-lambda-name")["Parameter"]["Value"]`.
3. **`pytest.skip` if neither resolves** — no silent false-positive; the test is explicitly declared unrunnable when the resolution chain is exhausted.

**Canonical pattern for Plan 09 addendum:**
> Any AWS/Lambda-namespace metric query in `pytest -m smoke` should use env-var-primary + SSM-parameter-fallback + `pytest.skip`-on-exhaustion. The SSM parameter provides a deploy-time source of truth; the env var provides a CI-/local-test override without requiring AWS credentials.

**cevo-dev25 IAM action required:** `cloudwatch:GetMetricStatistics` on `AWS/Lambda` namespace. Likely already granted via the dev-admin policy attached to `cevo-dev25` (verified in Plan 12 D-06 live-diff ceremony — the same profile ran boto3 queries against CloudWatch-adjacent APIs without IAM denials). If a future plan discovers the grant absent, the boto3 call returns `ClientError: AccessDeniedException` at test time — add the grant then.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing prewarm tests' mock side_effect lists updated for new 2-persona × 3-pass shape**

- **Found during:** Task 7.1 GREEN verification — after updating `scripts/prewarm.py` to the new shape, 4 of 7 existing tests failed because their mock `side_effect` lists were sized for the OLD 3-persona × 1-pass shape (3 warm 204s + 9 measurement 200s = 12 responses total). The NEW shape is 2-persona × 3-pass (6 warm 204s + 6 measurement 200s = 12 responses total — same count, different distribution).
- **Issue:** `test_prewarm_happy_path_exit_0`, `test_prewarm_gate_fail_exit_1`, `test_prewarm_measurement_timeout_pushes_median`, `test_prewarm_per_call_log_format` all tripped on (a) mock exhaustion (wrong distribution of 204s vs 200s), (b) log-line format asserts that expected the OLD `prewarm CUST-001: 204 Xms ok` shape but the new code emits `prewarm CUST-001 pass 1/3: 204 Xms ok`, (c) summary-line asserts for `PASS (<3000ms)` only (now also emits `PASS (<2500ms)` for CUST-003).
- **Fix:** Rewrote the 4 failing tests' mock side_effect lists to match the new 6+6 distribution; switched CUST-002 references to CUST-003; updated log-line asserts to the `pass N/3` format; added per-flow PASS-token asserts. Zero test-intent change; the tests still exercise the same contract (happy-path / gate-fail / timeout-pushes-median / log-format) against the updated implementation.
- **Files modified:** `tests/test_prewarm_script.py` — 4 existing tests' bodies rewritten; 4 new tests appended (Task 7.2 spec).
- **Commit:** `5c030f7` (Task 7.1 GREEN — test + script updates folded into the single GREEN commit to keep the diff greppable).
- **Why Rule 1 (not Rule 4):** pure mock-shape adjustment following a deliberate behaviour change. No architectural modification; no new fixture plumbing; no cross-module coupling.

**2. [Rule 1 - Bug] Prose tightening in `scripts/prewarm.py` to satisfy literal-grep acceptance**

- **Found during:** Task 7.1 acceptance-criteria grep verification.
- **Issue:** Plan acceptance pins `grep -c "MEDIAN_GATE_MS" scripts/prewarm.py == 0` and `grep -c "CUST-002" scripts/prewarm.py == 0`. Initial implementation mentioned both symbols in docstring + Pitfall-1 comment as traceability breadcrumbs for future developers — grep returned 1 for MEDIAN_GATE_MS and 2 for CUST-002.
- **Fix:** Reworded the module docstring and the inline Pitfall-1 comment to describe the deprecated symbol in English ("single scalar", "Marcus") rather than citing its literal name. Semantic intent preserved; acceptance greps now return 0 / 0.
- **Files modified:** `scripts/prewarm.py` — module docstring + 2 inline comments.
- **Commit:** `5c030f7` (Task 7.1 GREEN — rewording happened pre-commit, included in the single GREEN diff).
- **Why Rule 1 (not Rule 4):** pure prose tightening to satisfy acceptance-criteria literal-greps; zero semantic change; zero test deltas.

**3. [Rule 1 - Bug] Task 7.3 comment/docstring paraphrase to satisfy `time.sleep(90)` literal-grep acceptance**

- **Found during:** Task 7.3 acceptance-criteria grep verification.
- **Issue:** Plan acceptance pins `grep -c "time.sleep(90)" tests/test_narrative_eval_live.py == 1` (single occurrence — the actual call-site). Initial implementation had the literal string `time.sleep(90)` in the module header comment AND in the `test_agent01_tools_actually_invoked` docstring as cross-references; grep returned 3.
- **Fix:** Reworded both references to describe the invariant in English ("90-second post-call sleep", "90-second post-lookup sleep") without citing the function literally. Pitfall-5 rationale preserved verbatim; the actual `time.sleep(90)` call-site is unique.
- **Files modified:** `tests/test_narrative_eval_live.py` — module header comment + function docstring.
- **Commit:** `69e44d6` (Task 7.3 — folded into the single commit pre-commit).
- **Why Rule 1 (not Rule 4):** pure prose tightening to satisfy acceptance-criteria literal-greps; zero semantic change.

### Auth Gates

None — Plan 07 is fully offline from the parallel-executor worktree. The smoke tests added in Task 7.3 require BACKEND_API_URL + (TOOLS_LAMBDA_NAME OR SSM parameter) at runtime, but those are documented operator-provided env vars, NOT planning-time auth gates. The A-03 sighting shot (Task 7.4) is operator-deferred with a full setup runbook in §A-03 Sighting Shot above.

## Verification Evidence

```
pytest tests/test_prewarm_script.py                                       11/11 pass  (0.07s)
  - 7 existing tests (happy-path, gate-fail, bad-prewarm, missing-env, timeout-pushes-median, per-call-log-format, median-computation)
  - 4 new tests (personas-rotation, gate_ms-per-flow-map, warming-passes-is-three, measurement-samples-unchanged)

pytest tests/test_narrative_eval_live.py --collect-only                   5 tests collected
  - 3 existing parametrized test_narrative_eval_live[CUST-001/002/003]
  - 2 new test_agent01_latency_floor + test_agent01_tools_actually_invoked

pytest tests/test_narrative_eval_live.py -m "not smoke" --collect-only    0 tests collected (5 deselected)
  - smoke-marker gating verified — entire module excluded under "not smoke"

pytest -m "not smoke" --ignore=tests/test_frontend_synth.py               292 passed, 12 skipped,
                                                                          34 deselected (smoke),
                                                                          0 failures
                                                                          (Plan 05 baseline 288 + 4 new Task 7.1/7.2 = 292 exact)
```

**Module-level sanity (offline):**

```
$ python3 -c "
> import importlib.util
> spec = importlib.util.spec_from_file_location('pw', 'scripts/prewarm.py')
> m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
> assert m.PERSONAS == ['CUST-001', 'CUST-003']
> assert m.GATE_MS == {'CUST-001': 3000, 'CUST-003': 2500}
> assert m.WARMING_PASSES == 3
> assert not hasattr(m, 'MEDIAN_GATE_MS')
> assert m._TIMEOUT_SENTINEL_MS == 3000  # max of {3000, 2500}
> print('prewarm OK')"
prewarm OK
```

## Deferred Issues

**Task 7.4 A-03 Sighting Shot — operator-deferred (intentional, documented above).** This is NOT an unresolved issue; it is a pre-lift gate that can only be executed by an operator with AWS credentials against a pre-lift dev-alias deployment. The plan's `type="checkpoint:human-verify"` on Task 7.4 explicitly acknowledges this; the parallel-executor environment (worktree, no AWS, no dev-alias) cannot run the shot. §A-03 Sighting Shot above provides the full runbook + decision tree; Plan 08 MUST block on operator completion of that runbook before the stack-policy lift.

**No other deferred issues within Plan 07 scope.** `test_agent01_tools_actually_invoked` smoke test cannot run in CI without TOOLS_LAMBDA_NAME env var OR SSM parameter — this is by design (the `pytest.skip` branch ensures no silent false-positive); CLAUDE.md §Tests or `.planning/phases/13-*/13-09-PLAN.md` is the documentation target for wiring the env-var into the smoke-test env (not Plan 07's scope).

## Threat Flags

None — Plan 07 adds:
- NO new network endpoints (the 2 new smoke tests hit existing `GET /recommendations/{customer_id}` endpoints and query existing `AWS/Lambda` CloudWatch metrics).
- NO new auth paths (existing `cevo-dev25` IAM covers `cloudwatch:GetMetricStatistics` per §TOOLS_LAMBDA_NAME resolution evidence above).
- NO new file access patterns (no new env vars at deploy time; test-time TOOLS_LAMBDA_NAME is developer-provided).
- NO schema changes (prewarm.py is a standalone CLI; no Pydantic or API surface touched).

All threats in the plan's `<threat_model>` (T-13-07-01..05) remain correctly mitigated:

- **T-13-07-01 Tampering (2500ms gate silently fails because MEDIAN_GATE_MS scalar defaulted to 3000)** — mitigated: `test_gate_ms_is_per_flow_map_not_scalar` asserts `not hasattr(module, 'MEDIAN_GATE_MS')` + Pitfall 1 inline comment explicit in `scripts/prewarm.py`.
- **T-13-07-02 DoS (sighting-shot against frozen prod stack exhausts Bedrock budget)** — accepted with operator awareness: §A-03 Sighting Shot explicitly recommends dev-alias first; frozen-stack sighting is accepted only if operator approves. Break-glass option 3 (`SequentialToolExecutor`) is explicitly flagged as NOT RECOMMENDED to prevent misapplication.
- **T-13-07-03 Information Disclosure (D-21 queries CloudWatch on wrong Lambda name)** — mitigated: env-var primary + SSM fallback + `pytest.skip` if neither resolves. No silent false-positive.
- **T-13-07-04 DoS (90s sleep shortens under CI pressure)** — mitigated: Pitfall 5 annotation in 3 places (header comment, function docstring, inline comment); literal `time.sleep(90)` call at a single site so grep-based acceptance catches any retune.
- **T-13-07-05 Business Logic (break-glass option 3 misapplied)** — mitigated via documentation: §A-03 Sighting Shot decision tree explicitly flags option 3 as "NOT RECOMMENDED" with the rationale ("sequential tool execution is strictly slower than concurrent") so a future operator reading this SUMMARY.md understands why not to reach for it.

## TDD Gate Compliance

Plan 07 is mixed-type. Task 7.1 is `tdd="true"`; Task 7.2 is `tdd="true"` but functionally serves as the RED commit for Task 7.1's implementation; Task 7.3 is `tdd="true"` but is test-only (no separate implementation to gate). Task 7.4 is `type="checkpoint:human-verify"` (no RED/GREEN).

**Combined Task 7.1 + Task 7.2 gate sequence:**

- ✅ **RED** — `8be441f` `test(13-07): add failing tests for per-flow gate map + 3-pass warming + CUST-003 rotation (RED)`. Test `test_personas_rotation_is_cust001_and_cust003` fails with `AssertionError: assert ['CUST-001', ..., 'CUST-003'] == ['CUST-001', 'CUST-003']`. Confirmed RED on the per-flow gate + rotation + warming-pass tests; pre-existing tests still green.
- ✅ **GREEN** — `5c030f7` `feat(13-07): per-flow gate map + 3-pass warming + CUST-003 rotation (GREEN)`. 11/11 prewarm tests pass (7 pre-existing + 4 new). Full offline suite: 292 passed, 0 failures.
- **REFACTOR** — not required. Implementation was clean on first GREEN; test-mock-shape adjustments on existing tests landed as Rule 1 auto-fixes in the GREEN commit.

**Task 7.3 (test-only):**

- `69e44d6` `test(13-07): add D-19 latency-floor + D-21 CloudWatch-counter smoke tests`. No RED/GREEN cycle — the tests exercise behaviour that already ships (Plan 03 @tool wiring + Plan 04 FourToolCapHook). Both tests are smoke-marked and collect-only-pass offline (they skip in absence of `BACKEND_API_URL`).

## Self-Check: PASSED

- [x] `scripts/prewarm.py` has `PERSONAS = ["CUST-001", "CUST-003"]` at line 39.
- [x] `scripts/prewarm.py` has `GATE_MS: dict[str, int] = {"CUST-001": 3000, "CUST-003": 2500}` at lines 46-49.
- [x] `scripts/prewarm.py` has `WARMING_PASSES = 3` at line 55.
- [x] `scripts/prewarm.py` has `for pass_idx in range(WARMING_PASSES):` at line 82.
- [x] `scripts/prewarm.py` gate loop reads `gate_ms = GATE_MS[persona]` per iteration.
- [x] `scripts/prewarm.py` grep returns 0 for `MEDIAN_GATE_MS` (scalar removed).
- [x] `scripts/prewarm.py` grep returns 0 for `CUST-002` (Marcus removed from rotation; prose tightened).
- [x] `tests/test_prewarm_script.py` has 4 new Task-7.2 tests; `pytest tests/test_prewarm_script.py` exits 0 (11/11 pass).
- [x] `tests/test_narrative_eval_live.py` has `test_agent01_latency_floor` and `test_agent01_tools_actually_invoked` at lines 133 and 154.
- [x] `tests/test_narrative_eval_live.py` has `time.sleep(90)` at a single call-site (line 189).
- [x] `tests/test_narrative_eval_live.py` has `Dimensions=[{"Name": "FunctionName", "Value": ...}]` canonical shape.
- [x] `pytest tests/test_narrative_eval_live.py -m "not smoke" --collect-only` collects 0 tests (module gated by marker).
- [x] Full offline suite: 292 passed, 12 skipped, 34 deselected (smoke), 0 failures (+4 vs Plan 05 baseline 288).
- [x] A-03 sighting-shot operator runbook + decision tree + break-glass options written above.
- [x] Commits `8be441f`, `5c030f7`, `69e44d6` all present in `git log --oneline 4039aa1..HEAD`.

---

*Plan: 13-07 (Phase 13 Bill-Shock Multi-Tool Flow)*
*Completed: 2026-04-29*
*Executor: parallel worktree agent-a7daf3b53ba61a61a*
