---
phase: 07-api-pass-through-pre-warm-route
plan: 01
subsystem: api

tags: [aws-lambda, api-gateway, bedrock-agentcore, boto3, pytest, structured-logging, caplog, prewarm]

# Dependency graph
requires:
  - phase: 06-agent-narrative-guardrail
    provides: "Extended TrackInfo schema with usage_narrative + call_script on both green/cheapest tracks, plus top-level _narrative_source marker contract (Phase 6 D-03) produced by the agent and expected to be stripped by the API Lambda."
  - phase: 06.1-resolve-sonnet-4-6-tool-use-regression-demo-02
    provides: "Stable AgentRuntimeArn (tariff_agent-O2Hai86N8V) + byte-exact DEMO-02 savings values — the upstream Phase 7 proxies through unchanged."
provides:
  - "Marker-strip: body.pop('_narrative_source', None) immediately after json.loads on the normal path so the UI never sees the internal marker (D-06)."
  - "narrative_source structured INFO log emitted on every successful (non-prewarm) invocation with zero-PII payload (D-07) — queryable by Phase 9 eval harness."
  - "?prewarm=1 query branch that runs a full real agent turn, swallows every exception via except Exception, and returns HTTP 204 (never 5xx — SC-2) — the Lambda-side target for Phase 9 scripts/prewarm.py (D-01/D-02/D-04/D-05)."
  - "prewarm_failed structured WARNING log on any prewarm exception path with error_code extracted from ClientError.response when present, else type(exc).__name__ (D-04)."
  - "Narrative fields (usage_narrative + call_script on both green/cheapest tracks) flow byte-identically through json.dumps(body) on the normal path (D-08)."
  - "D-13 regex runs BEFORE prewarm dispatch — a stray ?prewarm=1 with malformed customer_id still returns 400 (fast-fail invariant preserved)."
  - "6 new pytest functions (D-13) covering narrative pass-through + marker-absent tolerance + prewarm happy-path + prewarm ClientError + prewarm ReadTimeoutError + prewarm-invalid-id-400."
affects:
  - "Phase 07-02: CDK alias + Provisioned Concurrency wiring — relies on the handler surface shipped here (no module-level state added, keeping PC init safe — Pitfall 7)."
  - "Phase 08: UI integration — will receive the narrative fields on both tracks byte-identically via this handler, with _narrative_source guaranteed absent."
  - "Phase 09: scripts/prewarm.py + eval harness — will curl ?prewarm=1 per persona expecting 204, and query the narrative_source log for end-to-end model-vs-fallback coverage."
  - "Phase 10: DEMO-04 freeze — no freeze surface added at the handler layer (no env vars, no IAM, no module-level state); all new behaviour is function-local."

# Tech tracking
tech-stack:
  added:
    - "python logging.caplog fixture pattern in pytest (net-new for this repo — 3 of the 6 new tests use it to assert log shape)"
  patterns:
    - "Structured CloudWatch logging via logger.info(json.dumps({event: ..., customer_id: ..., ...})) — JSON-in-message so CloudWatch Logs Insights can parse with `filter @message like /event/` natively (no Lambda JSON formatter layer needed). Sits alongside existing positional-format Phase 3 logs; do not mix styles within a single log event (Pitfall 8)."
    - "?prewarm=1 query-flag dispatch pattern — additive branch AFTER the D-13 regex check and BEFORE normal-path session_id mint. Uses literal string compare `== \"1\"` (Pitfall 4)."
    - "Swallow-all except Exception in the prewarm branch with error_code extracted from exc.response['Error']['Code'] when isinstance(exc, ClientError), else type(exc).__name__ — covers ClientError subclasses AND transport-level botocore.exceptions (ReadTimeoutError, EndpointConnectionError, SSLError) in one catch."
    - "Per-test queryStringParameters extension: event = _make_event(\"CUST-001\"); event[\"queryStringParameters\"] = {\"prewarm\": \"1\"} — avoids modifying the shared _make_event() helper signature."

key-files:
  created: []
  modified:
    - "api_lambda/handler.py — +56 lines, two additive blocks inside handler(): prewarm branch (lines 65-104) and marker-strip+narrative_source log (lines 119-133). No new imports, no new module-level state."
    - "tests/test_backend_api_handler.py — +199 lines: 1 import (logging), 6 new test functions appended to the end of the file."

key-decisions:
  - "Prewarm branch inserted AFTER D-13 regex check and BEFORE normal-path uuid4 mint, so stray ?prewarm=1 + bad customer_id still returns 400 (D-01 fast-fail invariant)."
  - "Marker-strip placed INSIDE the existing try/except block, immediately after body = json.loads(...) and BEFORE the except ReadTimeoutError clause — body is only bound after the successful json.loads, so the pop cannot move above line 118."
  - "narrative_source log fires BEFORE the 404 green/cheapest check (Open Question 2 in RESEARCH.md resolution) — invoke succeeded, marker is observable; 404 is a handler-side decision not an invocation failure. Test test_narrative_pass_through_marker_absent locks this behaviour even when marker absent (log field = null)."
  - "Prewarm path does NOT emit narrative_source — body is discarded, no popped marker to log. test_prewarm_returns_204_happy_path asserts len(narrative_source_logs) == 0."
  - "Broad except Exception in prewarm branch (swallow-all per D-04/SC-2) uses `# pylint: disable=broad-except` comment — matches the existing Phase 3 style on line 145 rather than adopting `# noqa: BLE001` (both acceptable per RESEARCH.md; consistency with adjacent code chosen)."
  - "Literal string compare query_params.get(\"prewarm\") == \"1\" — not truthy coercion (Pitfall 4: ?prewarm=0 must NOT trigger)."
  - "No new module-level state (no second boto3 client, no new regex, no module-scope helpers) — Pitfall 7 Provisioned-Concurrency init risk. All new code lives inside handler()."
  - "No new top-level imports — ClientError, ReadTimeoutError, json, uuid, logging, os, re, boto3 all pre-existing from Phase 3; ClientError + ReadTimeoutError imports already cover the prewarm branch's isinstance check."

patterns-established:
  - "Pattern: Structured log emission via logger.{info,warning}(json.dumps({event: ..., customer_id: ..., ...})) — the zero-PII event stream that Phase 9 eval harness will query. narrative_source is INFO (success signal), prewarm_failed is WARNING (presenter-action trigger)."
  - "Pattern: Query-param flag dispatch AFTER input validation but BEFORE normal-path state setup — preserves the D-13 regex fast-fail while keeping the prewarm branch self-contained."
  - "Pattern: Offline-test caplog filter via [json.loads(r.message) for r in caplog.records if r.message.startswith('{') and '<event_key>' in r.message] — robust selection of the JSON-in-message structured logs from the caplog stream, ignoring Phase 3 positional-format logs that coexist."

requirements-completed:
  - DEMO-03  # plumbing half — handler-side target shipped. Phase 9 scripts/prewarm.py completes the tooling half. Live-smoke D-15 runbook still required at Phase 7 close.

# Metrics
duration: ~32min
completed: 2026-04-25
---

# Phase 7 Plan 01: Handler Pass-Through + Pre-Warm Branch Summary

**`_narrative_source` marker stripped, narrative fields flow byte-identically, and `?prewarm=1` returns HTTP 204 with swallow-all exception handling — all additive edits to `api_lambda/handler.py` plus 6 new pytest functions in `tests/test_backend_api_handler.py`.**

## Performance

- **Duration:** ~32 min (includes baseline regression run of full offline suite, two task commits, SUMMARY authoring)
- **Started:** 2026-04-25T21:31:00Z (approximate — worktree branch reset + context read)
- **Completed:** 2026-04-25T22:03:07Z
- **Tasks:** 2/2 (Task 1 + Task 2, both `tdd="true"`)
- **Files modified:** 2 (`api_lambda/handler.py`, `tests/test_backend_api_handler.py`)

## Accomplishments

- Handler now pops `_narrative_source` from the parsed agent body immediately after `json.loads(...)` and emits a structured `narrative_source` INFO log with `{event, customer_id, narrative_source}` on every successful invocation — zero-PII, CloudWatch Logs Insights queryable.
- `?prewarm=1` branch runs a full real agent turn against the shared `_agentcore_client` (no second client per D-05), catches every exception in a broad `except Exception`, and returns `{"statusCode": 204, "headers": {}, "body": ""}` — SC-2 (never 5xx) enforced by test coverage across ClientError and ReadTimeoutError paths.
- D-13 customer_id regex check retained as the first gate in `handler()`, so `?prewarm=1` + malformed customer_id still returns 400 — invariant locked by `test_prewarm_invalid_customer_id_returns_400`.
- 6 new pytest functions added (9 pre-existing → 15 total; 13 → 19 collected with parametrize) — the full handler test file passes in 0.37s.
- Full offline suite: 164 passed (+6 from baseline 158), 7 skipped, 31 deselected, 7 pre-existing environmental failures (AWS-credential-dependent; NOT Phase 7 scope — see "Deferred Issues" below).

## Task Commits

Each task was committed atomically:

1. **Task 1: Handler marker-strip + narrative_source log + prewarm branch** — `074d2d3` (feat)
2. **Task 2: Add 6 pytest functions for pass-through + prewarm (D-13)** — `eb20e4b` (test)

_Note: plan frontmatter declares `tdd="true"` on both tasks. Plan-level task ordering places the handler change (Task 1) BEFORE the test additions (Task 2) — per plan author's explicit sequencing. Task 1 is self-validating via grep invariants + preservation of the 9 pre-existing handler tests (which never exercised the new paths); Task 2 then adds the 6 behavioural tests that exercise the Phase 7 code paths. Both tests + handler landed green on first try; no RED→GREEN iteration loop required._

## Files Created/Modified

### `api_lambda/handler.py` — line ranges of changes

| Block | Lines (new file) | Description |
|-------|------------------|-------------|
| Prewarm branch block | 65–104 | Inserted after D-13 regex (line 63) and before normal-path `session_id = str(uuid.uuid4())` (line 109). Literal `prewarm == "1"` compare, fresh uuid4 per call, shared `_agentcore_client`, broad `except Exception` with `error_code` extraction, structured `prewarm_failed` WARNING log, `{"statusCode": 204, "headers": {}, "body": ""}` return. |
| Marker-strip + narrative_source log | 119–133 | Inserted inside existing normal-path try-block immediately after `body = json.loads(response["response"].read())` (line 118) and before `except ReadTimeoutError:` (line 134). `body.pop("_narrative_source", None)` (idempotent) + `logger.info(json.dumps({event: "narrative_source", customer_id, narrative_source}))`. |

### `tests/test_backend_api_handler.py` — line ranges of changes

| Block | Lines (new file) | Description |
|-------|------------------|-------------|
| `import logging` added at module top | 3 | Alphabetical placement adjacent to `import json` — needed for `caplog.at_level(logging.INFO/WARNING, ...)`. |
| 6 new test functions appended | 181–376 | `test_narrative_pass_through`, `test_narrative_pass_through_marker_absent`, `test_prewarm_returns_204_happy_path`, `test_prewarm_returns_204_on_client_error`, `test_prewarm_returns_204_on_read_timeout`, `test_prewarm_invalid_customer_id_returns_400`. All use `@patch("api_lambda.handler._agentcore_client")` decorator per Phase 3 convention; per-test imports of `ClientError` / `ReadTimeoutError` inside function bodies; `_make_event()` extended per-test by assigning `event["queryStringParameters"]` (shared helper signature untouched). |

## Decision Traceability

Every Phase 7 decision from CONTEXT.md that touches this plan maps to a grep-verifiable anchor in the shipped code:

| D-XX | Anchor | Verification |
|------|--------|--------------|
| D-01 | `query_params.get("prewarm") == "1"` in `api_lambda/handler.py` line 70 | `grep -n 'query_params.get("prewarm") == "1"' api_lambda/handler.py` → 1 match |
| D-02 | `_agentcore_client.invoke_agent_runtime(...)` inside prewarm branch at `api_lambda/handler.py` line 79 | `awk '/# D-01\/D-02: Prewarm branch/,/^    # D-11/' api_lambda/handler.py \| grep -c '_agentcore_client.invoke_agent_runtime'` → 1 |
| D-04 | `except Exception as exc` inside prewarm branch at `api_lambda/handler.py` line 86 + 204 return at line 104 + `prewarm_failed` log at lines 94–101 | `grep -n '"event": "prewarm_failed"' api_lambda/handler.py` → 1 match; `grep -c '"statusCode": 204' api_lambda/handler.py` → 1 |
| D-05 | Single `boto3.client(` instantiation at `api_lambda/handler.py` line 39 (the docstring on line 9 is a pre-existing prose reference, not a call) | `grep -n 'boto3.client(' api_lambda/handler.py` → 1 real call; no second client introduced |
| D-06 | `body.pop("_narrative_source", None)` at `api_lambda/handler.py` line 121 | `grep -n 'body.pop("_narrative_source", None)' api_lambda/handler.py` → 1 match |
| D-07 | `"event": "narrative_source"` at `api_lambda/handler.py` line 130 | `grep -n '"event": "narrative_source"' api_lambda/handler.py` → 1 match |
| D-08 | `test_narrative_pass_through` asserts byte-identical narrative fields (`tests/test_backend_api_handler.py` lines 181–243) | `pytest tests/test_backend_api_handler.py::test_narrative_pass_through -q` → PASS |
| D-13 | 6 pytest functions present in `tests/test_backend_api_handler.py` | 6× `grep -c 'def test_...' tests/test_backend_api_handler.py` → each 1 match |

Supporting invariants verified:

- No new module-level state added (Pitfall 7): `grep -c 'boto3.client' api_lambda/handler.py` baseline count preserved; no new top-level imports (`grep -cE '^import \|^from ' api_lambda/handler.py` = 8, same as Phase 3 baseline).
- `_error(` is NOT called inside the prewarm branch block: `awk '/# D-01\/D-02: Prewarm branch/,/^    # D-11/' api_lambda/handler.py | grep -c '_error('` → 0 (prewarm deliberately does not participate in 4xx/5xx taxonomy per D-04/D-12).
- Handler is syntactically valid and imports cleanly: `python3 -c "from api_lambda.handler import handler; print(handler.__name__)"` → `handler`.

## D-15 Live-Smoke Closeout Gate — Runbook (to be executed at Phase 7 close)

**This is NOT a pytest.** The warm-median gate requires real HTTP timing against the deployed endpoint with Provisioned-Concurrency warm-up latency baked in. Reproduced verbatim from 07-RESEARCH.md §"D-15 Live-Smoke Closeout Gate — Runbook" — captured here so the Phase 7 close has a single authoritative checklist. Plan 07-02 ships the CDK alias + PC wiring that step 1 requires; this plan (07-01) does not close the gate on its own.

Phase 7 does **not close** until all six steps pass end-to-end. Evidence (timing table, CloudWatch counts, representative `jq` output) captured in the Phase-close artefact.

1. **Deploy:** `cdk deploy -c demo_pc=1 BackendApiStack` succeeds idempotently (requires Plan 07-02 shipped). Capture CFN `UPDATE_COMPLETE` timestamp.

2. **Wait for PC READY:** Either sleep ≥180s OR poll:
   ```bash
   aws lambda get-provisioned-concurrency-config \
     --function-name tariff-api --qualifier live \
     --query 'Status' --output text
   # Expected: READY (initially: IN_PROGRESS)
   ```

3. **Prewarm all 3 personas:**
   ```bash
   for p in CUST-001 CUST-002 CUST-003; do
     curl -sS -o /dev/null -w "prewarm %{http_code} %{time_total}s\n" \
       "$BACKEND_API_URL/recommendations/$p?prewarm=1"
     sleep 2
   done
   # Expected: all three "prewarm 204 ..." lines, completing <25s each
   ```

4. **Warm-median per persona:** 3 lookups per persona, median across 9 total:
   ```bash
   for p in CUST-001 CUST-002 CUST-003; do
     for i in 1 2 3; do
       curl -sS -o /tmp/p${p}_$i.json \
         -w "%{http_code} %{time_total}\n" \
         "$BACKEND_API_URL/recommendations/$p"
     done
   done
   # Compute median from the 9 time_total values.
   # Gate: median per persona < 3000ms (SC-4 / UI-02).
   # Optional tighter floor for CUST-001 Sarah: <2500ms (Claude's Discretion).
   ```

5. **CloudWatch log checks:**
   ```bash
   # narrative_source present on every successful warm lookup (3 personas × 3 lookups = 9 expected)
   aws logs filter-log-events \
     --log-group-name /aws/lambda/tariff-api \
     --filter-pattern '"narrative_source"' \
     --start-time $(date -d '10 minutes ago' +%s)000 \
     | jq '.events | length'
   # Expected: ≥ 9

   # prewarm_failed absent across the 3 prewarm calls
   aws logs filter-log-events \
     --log-group-name /aws/lambda/tariff-api \
     --filter-pattern '"prewarm_failed"' \
     --start-time $(date -d '10 minutes ago' +%s)000 \
     | jq '.events | length'
   # Expected: 0
   ```

6. **Response body content:**
   ```bash
   jq '.green.usage_narrative, .green.call_script, .cheapest.usage_narrative, .cheapest.call_script, ._narrative_source' /tmp/pCUST-001_1.json
   # Expected: 4 non-empty strings + null (marker absent from response body).
   ```

**Evidence to capture at Phase-close:** CFN `UPDATE_COMPLETE` timestamp, PC `Status: READY` timestamp, 3× prewarm curl output, 9× warm lookup `time_total` values + computed median per persona, `narrative_source` event count, `prewarm_failed` event count (should be 0), one representative `jq` output of a lookup body.

## Decisions Made

See "key-decisions" in frontmatter above — the 8 load-bearing decisions are repeated there. No surprises, no divergence from CONTEXT.md D-01/D-02/D-04/D-05/D-06/D-07/D-08/D-13.

## Deviations from Plan

**None — plan executed exactly as written.** Both tasks landed on first try; no Rule 1/2/3 auto-fixes required. No architectural decisions (Rule 4) needed.

Operational note (not a plan deviation): the shell inherited `AWS_PROFILE=cevo-25` which points at a non-existent profile — a known condition already documented in `.planning/STATE.md` §"Phase 06.1 Plan 02 execution decisions". All test runs were executed with `unset AWS_PROFILE` prefixed, which is safe because this plan's code paths are fully mocked via `@patch("api_lambda.handler._agentcore_client")` and never touch real AWS credentials. This is an environment concern, not a code change.

## Issues Encountered

None during planned work.

## Deferred Issues (out of Phase 7 scope — pre-existing)

The full offline suite baseline shows 7 pre-existing failures that are NOT introduced by Phase 7 and NOT part of this plan's scope (per `<deviation_rules>` SCOPE BOUNDARY). Recording here for Phase-close traceability:

- `tests/test_backend_api_synth.py::test_agentcore_stack_has_ssm_parameter` — fails in the worktree because CDK synth of `AgentCoreStack` requires bootstrapped account context. Unrelated to the API Lambda.
- `tests/test_seeder_smoke.py::*` (6 tests: `test_table_exists`, `test_table_has_36_items`, `test_sarah_has_12_months`, `test_marcus_has_12_months`, `test_elena_has_12_months`, `test_lambda_invokes_sarah_savings_match_demo02`) — all `botocore.exceptions.Cl...` truncated to `ClientError`; need real AWS credentials + live DynamoDB `tariff-billing` table. Belong under the `smoke` marker but currently collect under the default `-m "not smoke"` selection.

These failures exist on the base commit `bb6dd86` (before Phase 7 work started) and are environmental; none are caused by the changes in this plan. Attempting to fix them would exceed scope and blow the fix-attempt limit without benefit.

**Delta introduced by Phase 7:** 158 passed → 164 passed (+6 new tests, zero regressions). Same 7 pre-existing failures, 7 skipped, 31 deselected.

## User Setup Required

None — no external service configuration required. All changes are handler-local + test-only; no env vars added, no IAM changes, no new AWS resources.

## Next Phase Readiness

**Plan 07-02 (CDK alias + PC) can start immediately.** Plan 07-02 rewires `infrastructure/constructs/backend_api.py` to add `fn.add_alias("live", ...)` with conditional `-c demo_pc=N` PC config, and changes the `HttpLambdaIntegration` target from `fn` to the alias. It does **not** modify `api_lambda/handler.py` — the handler surface shipped in this plan is the final Phase 7 handler.

**Phase 8 (UI) can consume the narrative fields** once deployed: the handler now guarantees `_narrative_source` is absent from responses and the 4 narrative strings (`green.usage_narrative`, `green.call_script`, `cheapest.usage_narrative`, `cheapest.call_script`) flow byte-identically via `json.dumps(body)`.

**Phase 9 (prewarm tooling + eval harness) has a stable target:** `GET /recommendations/{customer_id}?prewarm=1` → 204 (never 5xx — SC-2), and every successful normal-path invocation emits a queryable `narrative_source` CloudWatch log with zero-PII payload.

**Phase 10 freeze has zero new surface at the handler layer:** no new env vars, no new IAM permissions, no new module-level boto3 clients, no new imports. All Phase 7 handler behaviour is function-local.

## Self-Check: PASSED

Verified before SUMMARY finalisation:

- **Files exist as claimed:**
  - `api_lambda/handler.py` — FOUND (162 lines after changes; 107 before). `grep` anchors for D-01/D-04/D-06/D-07 all match exactly once.
  - `tests/test_backend_api_handler.py` — FOUND (376 lines after changes; 178 before). All 6 new `def test_...` functions present.

- **Commits exist on branch:**
  - `074d2d3` — FOUND: `feat(07-01): add handler marker-strip + narrative_source log + prewarm branch`
  - `eb20e4b` — FOUND: `test(07-01): add 6 pytest functions for narrative pass-through + prewarm (D-13)`

- **Automated verification (plan `<verification>` block):**
  1. `pytest tests/test_backend_api_handler.py -q` → 19 passed in 0.37s (9 pre-existing test functions → 13 collected with parametrize; 6 new → 19 total).
  2. `pytest -m "not smoke" -q` → 164 passed, 7 failed (pre-existing env failures), 7 skipped, 31 deselected. No regressions introduced by this plan.
  3. `python3 -c "import ast; ast.parse(open('api_lambda/handler.py').read())"` → exit 0.
  4. `python3 -c "from api_lambda.handler import handler; print(handler.__name__)"` → `handler` (module imports cleanly — Pitfall 7 PC-init risk check).
  5. `grep -c '"statusCode": 204' api_lambda/handler.py` → `1` (single prewarm return).
  6. `grep -n 'boto3.client(' api_lambda/handler.py` → 1 real instantiation at line 39 (pre-existing Phase 3 line). No second client introduced.

---
*Phase: 07-api-pass-through-pre-warm-route*
*Plan: 01*
*Completed: 2026-04-25*
