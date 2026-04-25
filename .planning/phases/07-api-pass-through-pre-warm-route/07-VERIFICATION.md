---
phase: 07-api-pass-through-pre-warm-route
verified: 2026-04-25T22:36:48Z
status: human_needed
score: 13/15 must-haves verified (2 require live-smoke)
overrides_applied: 0
requirements_coverage:
  - id: DEMO-03
    source_plans: [07-01-PLAN, 07-02-PLAN]
    scope_in_phase: "plumbing half"
    status: satisfied
    evidence: "handler pass-through + ?prewarm=1 → 204 + alias-always + conditional PC shipped and verified offline; tooling half (scripts/prewarm.py) is Phase 9"
human_verification:
  - test: "SC-1 live byte-identical narratives"
    expected: |
      For each persona (CUST-001, CUST-002, CUST-003), GET $BACKEND_API_URL/recommendations/$p
      returns HTTP 200 with green.usage_narrative, green.call_script, cheapest.usage_narrative,
      cheapest.call_script as non-empty strings, and ._narrative_source ABSENT.
    command: |
      for p in CUST-001 CUST-002 CUST-003; do
        curl -sS "$BACKEND_API_URL/recommendations/$p" | \
          jq '{status: "ok",
               green_un: .green.usage_narrative, green_cs: .green.call_script,
               cheap_un: .cheapest.usage_narrative, cheap_cs: .cheapest.call_script,
               marker: ._narrative_source}'
      done
      # Expected: 4 non-empty strings per persona + marker == null
    why_human: |
      Requires a deployed API endpoint. No CI-accessible deployed endpoint exists during
      verification. Phase 7 ships the plumbing; the live smoke is the D-15 closeout gate
      that must be run by the operator post `cdk deploy`.
  - test: "SC-2 prewarm returns 204 live (happy path + downstream failure)"
    expected: |
      GET $BACKEND_API_URL/recommendations/$p?prewarm=1 returns HTTP 204 for all 3 personas,
      completing in under 25s each; a forced-failure scenario also returns 204, never 5xx.
    command: |
      for p in CUST-001 CUST-002 CUST-003; do
        curl -sS -o /dev/null -w "prewarm %{http_code} %{time_total}s\n" \
          "$BACKEND_API_URL/recommendations/$p?prewarm=1"
        sleep 2
      done
      # Expected: three lines of "prewarm 204 <t>s" with <t> under 25
    why_human: |
      Offline tests prove the 204-on-failure contract via mocked ClientError + ReadTimeoutError.
      Live confirmation still needs a deployed endpoint to rule out deploy-time wiring bugs
      (alias-qualifier routing, API Gateway route binding).
  - test: "SC-4 UI-01 + UI-02 live-smoke with narratives"
    expected: |
      Warm-median lookup per persona < 3000ms (SC-4/UI-02) and both cards remain above the
      fold at 1280×800 with narratives present (UI-01). CloudWatch narrative_source log
      fires ≥ 9 times (3 personas × 3 warm lookups) with zero prewarm_failed events.
    command: |
      # (1) Prewarm all 3 personas first, then 3 warm lookups each, 9 total
      for p in CUST-001 CUST-002 CUST-003; do
        for i in 1 2 3; do
          curl -sS -o /tmp/p${p}_$i.json -w "%{http_code} %{time_total}\n" \
            "$BACKEND_API_URL/recommendations/$p"
        done
      done
      # (2) Compute median per persona — gate: each median < 3.000s
      # (3) CloudWatch counts:
      aws logs filter-log-events --log-group-name /aws/lambda/tariff-api \
        --filter-pattern '"narrative_source"' \
        --start-time $(date -d '10 minutes ago' +%s)000 | jq '.events | length'
      # Expected: ≥ 9
      aws logs filter-log-events --log-group-name /aws/lambda/tariff-api \
        --filter-pattern '"prewarm_failed"' \
        --start-time $(date -d '10 minutes ago' +%s)000 | jq '.events | length'
      # Expected: 0
      # (4) UI-01: open browser at 1280×800 to a front-end build hitting this API
      #     and visually confirm both cards fit above the fold with narratives.
    why_human: |
      Requires deployed infrastructure + running browser at 1280×800 for UI-01 layout.
      UI-01 is explicitly a visual-layout gate (above-the-fold at a specific viewport
      size) and UI-02 needs real-network timings against a warm, PC-backed Lambda.
      The D-15 runbook captured in 07-01-SUMMARY.md is the executable checklist.
---

# Phase 7: API Pass-Through + Pre-Warm Route — Verification Report

**Phase Goal:** Narrative fields traverse API Gateway → Lambda → client without transformation, and a dedicated warm-up route exercises the full hot path behind an always-aliased Lambda.

**Verified:** 2026-04-25T22:36:48Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (merged from ROADMAP Success Criteria + PLAN must-haves)

| # | Source | Truth | Status | Evidence |
|---|--------|-------|--------|----------|
| 1 | SC-1 | Live GET per persona returns byte-identical `usage_narrative` + `call_script` on both cards | ? HUMAN | Offline behaviour proven (tests pass); live smoke requires deployed endpoint |
| 2 | SC-2 | `?prewarm=1` returns 204 within handler budget, never 5xx on downstream failure | ? HUMAN (live) / ✓ VERIFIED (offline) | 5 pytest functions cover 204 happy path, 204-on-ClientError, 204-on-ReadTimeoutError, 400-on-bad-id. Live confirmation still needed |
| 3 | SC-3 | API Gateway wired to named alias `live` (not `$LATEST`) with PC configurable via `-c demo_pc=1` | ✓ VERIFIED | 4 synth assertions pass: alias exists, integration targets alias, PC present when demo_pc=1, PC absent when demo_pc=0 |
| 4 | SC-4 | UI-01 (both cards above fold at 1280px) + UI-02 (<3s lookup-to-rendered) still hold with narratives | ? HUMAN | Visual-layout + real-network timing gate — requires deployed endpoint + browser |
| 5 | 07-01 T1 | `_narrative_source` marker stripped before `json.dumps()` | ✓ VERIFIED | `body.pop("_narrative_source", None)` at handler.py:121; `test_narrative_pass_through` asserts `"_narrative_source" not in body` |
| 6 | 07-01 T2 | Every successful (non-prewarm) invoke emits structured `narrative_source` INFO log | ✓ VERIFIED | handler.py:129–133; asserted by 2 tests (model + marker-absent paths) |
| 7 | 07-01 T3 | `?prewarm=1` happy-path runs full agent turn + returns 204 | ✓ VERIFIED | handler.py:79–85, 104; `test_prewarm_returns_204_happy_path` passes |
| 8 | 07-01 T4 | `?prewarm=1` returns 204 on EVERY downstream failure + emits `prewarm_failed` WARNING | ✓ VERIFIED | `except Exception` at handler.py:86; tests cover ClientError + ReadTimeoutError |
| 9 | 07-01 T5 | Stray `?prewarm=1` with malformed customer_id still returns 400 | ✓ VERIFIED | D-13 regex at handler.py:62 runs BEFORE prewarm dispatch; `test_prewarm_invalid_customer_id_returns_400` passes |
| 10 | 07-01 T6 | Prewarm branch does NOT emit `narrative_source` log (body discarded) | ✓ VERIFIED | `test_prewarm_returns_204_happy_path` asserts `len(narrative_source_logs) == 0` |
| 11 | 07-02 T1 | Lambda alias `live` always created whether PC attached or not | ✓ VERIFIED | `fn.add_alias("live", ...)` 2 occurrences at backend_api.py:116, 118; `test_alias_live_exists` passes with `demo_pc=0` |
| 12 | 07-02 T2 | `HttpLambdaIntegration` `IntegrationUri` references `live` alias (never `$LATEST`, never raw fn) | ✓ VERIFIED | backend_api.py:139 — `HttpLambdaIntegration("RecoIntegration", live_alias)`; `test_integration_targets_alias` asserts alias logical ID appears in IntegrationUri |
| 13 | 07-02 T3 | With `-c demo_pc=1`, alias carries `ProvisionedConcurrencyConfig.ProvisionedConcurrentExecutions=1` | ✓ VERIFIED | `test_pc_present_when_demo_pc_set` passes |
| 14 | 07-02 T4 | With `-c demo_pc=0` (or omitted), alias has NO `ProvisionedConcurrencyConfig` | ✓ VERIFIED | `test_pc_absent_when_demo_pc_zero` passes via raw-JSON traversal |
| 15 | 07-02 T5 | Invalid `-c demo_pc=<garbage>` fails at synth time with readable `ValueError` | ✓ VERIFIED | 2× `raise ValueError` at backend_api.py:99, 104; manual repro confirmed: "ValueError raised: Invalid -c demo_pc value: 'abc'. Must be a non-negative integer." |

**Score:** 13/15 truths verified offline. 2 require live-smoke (SC-1, SC-4). SC-2 passes offline; live confirmation also human-gated.

**Note on numbering:** Offline-verifiable truths are fully green. The 2 items requiring human testing are SC-1 (live byte-identical narratives) and SC-4 (UI-01 + UI-02 live smoke). SC-2 is marked human alongside its offline ✓ because the SC explicitly says "live" — the contract is already proven offline, but operators must still exercise it against the deployed endpoint as the D-15 runbook specifies.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api_lambda/handler.py` | Prewarm branch + marker-strip + narrative_source log, no new module-level state | ✓ VERIFIED | 163 lines; all 6 anchor greps return exactly 1 match; module imports cleanly; AST parses |
| `tests/test_backend_api_handler.py` | 6 new pytest functions, `import logging` added | ✓ VERIFIED | All 6 function names present (line 185, 244, 272, 306, 335, 363); `import logging` at line 9; 19 tests pass (0.76s) |
| `infrastructure/constructs/backend_api.py` | `fn.add_alias("live", ...)` conditional on `demo_pc`; integration target swapped to `live_alias` | ✓ VERIFIED | 148 lines; `add_alias` 2× (conditional pair); `HttpLambdaIntegration(..., live_alias)` 1×; `HttpLambdaIntegration(..., fn)` 0×; `raise ValueError` 2× |
| `tests/test_backend_api_synth.py` | 4 new D-14 synth assertions + `_synth_with_context` helper | ✓ VERIFIED | All 4 test functions present; `_synth_with_context` helper at line 154; 14/15 tests pass (1 pre-existing env failure unrelated to Phase 7) |
| `infrastructure/backend_api_stack.py` | UNCHANGED at Phase 3 baseline | ✓ VERIFIED | 30 lines; 0 occurrences of `try_get_context` (Claude's Discretion: construct-level read chosen) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `handler.py::handler` | `body.pop("_narrative_source", None)` | After `json.loads(...)`, inside try block, before 404 check | ✓ WIRED | Line 121, between line 118 `body = json.loads(...)` and line 134 `except ReadTimeoutError:` |
| `handler.py::handler` | `narrative_source` CloudWatch INFO log | `logger.info(json.dumps({"event": "narrative_source", ...}))` after pop | ✓ WIRED | Lines 129–133; `test_narrative_pass_through` asserts log shape exactly |
| `handler.py::handler` | Prewarm branch → 204 return | `if query_params.get("prewarm") == "1": ... return {"statusCode": 204, ...}` | ✓ WIRED | Lines 70–104; D-13 regex at line 62 runs first; prewarm block cleanly delimited |
| `handler.py::prewarm branch` | `_agentcore_client.invoke_agent_runtime(...)` (shared client, no second instance) | Inside try/except inside prewarm block | ✓ WIRED | Line 79; `grep -c boto3.client` in handler.py = 1 (only the Phase 3 module-level instance at line 39 — D-05 satisfied) |
| `handler.py::prewarm branch` | `prewarm_failed` WARNING log on ANY exception | `except Exception as exc: logger.warning(json.dumps({...}))` | ✓ WIRED | Lines 86–101; error_code extracted from `ClientError.response["Error"]["Code"]` when `isinstance(exc, ClientError)`, else `type(exc).__name__` |
| `backend_api.py::BackendApiConstruct` | `self.node.try_get_context("demo_pc")` (construct-level read) | Between IAM policy (line 86) and HTTP API construction (line 121) | ✓ WIRED | Line 92; `backend_api_stack.py` confirmed byte-unchanged (0 `try_get_context` calls) |
| `backend_api.py::BackendApiConstruct` | `fn.add_alias("live", ...)` with conditional PC kwarg | Immediately after demo_pc validation | ✓ WIRED | Lines 115–118; `if demo_pc > 0: ... provisioned_concurrent_executions=demo_pc` |
| `api.add_routes` | `live_alias` as integration target | `integ.HttpLambdaIntegration("RecoIntegration", live_alias)` | ✓ WIRED | Line 139; `Alias` class extends `IFunction` so accepted directly; 0 occurrences of `HttpLambdaIntegration(..., fn)` — swap complete |
| `tests/test_backend_api_synth.py` | `cdk.App(context={"demo_pc": N})` per-test context override | `_synth_with_context(demo_pc=N)` plain helper | ✓ WIRED | Line 154–167; used by all 4 new tests; module-scope `synth_template` fixture preserved untouched for 10 pre-existing tests |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `handler.py` (normal path) | `body` | `json.loads(response["response"].read())` where `response` comes from `_agentcore_client.invoke_agent_runtime` | Upstream (agent) produces real data; Phase 6 confirmed narrative fields flow through | ✓ FLOWING (offline-verified via mocked response) |
| `handler.py` (response return) | Response body | `json.dumps(body)` where `body` has marker popped | Body is the agent's dict minus `_narrative_source` — byte-identical narrative fields preserved | ✓ FLOWING |
| `handler.py` (prewarm path) | Response | Literal `{"statusCode": 204, "headers": {}, "body": ""}` | Intentionally empty — contract-specified | ✓ FLOWING (by design) |
| `backend_api.py` (integration) | `live_alias` | `fn.add_alias("live", ...)` — tracks `fn.current_version` by default | CDK auto-publishes new version on each code change; alias rolls forward on deploy | ✓ FLOWING (CDK default behaviour) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Handler module imports cleanly (Pitfall 7 — PC init risk) | `python3.13 -c "from api_lambda.handler import handler; print(handler.__name__)"` | `handler` | ✓ PASS |
| Handler AST parses | `python3.13 -c "import ast; ast.parse(open('api_lambda/handler.py').read())"` | exit 0 | ✓ PASS |
| Construct AST parses | `python3.13 -c "import ast; ast.parse(open('infrastructure/constructs/backend_api.py').read())"` | exit 0 | ✓ PASS |
| Handler pytest suite | `python3.13 -m pytest tests/test_backend_api_handler.py -q` | `19 passed in 0.76s` | ✓ PASS |
| Synth pytest suite | `python3.13 -m pytest tests/test_backend_api_synth.py -q` | `14 passed, 1 failed` (failure is pre-existing `aws_bedrock_agentcore_alpha` ImportError on `test_agentcore_stack_has_ssm_parameter`) | ✓ PASS (Phase 7 tests all green; unrelated env failure) |
| Invalid `-c demo_pc=abc` raises `ValueError` at synth time | `python3.13 -c "import aws_cdk as cdk; from infrastructure.backend_api_stack import BackendApiStack; app = cdk.App(context={'demo_pc': 'abc'}); BackendApiStack(app, 'T', env=cdk.Environment(region='us-east-1', account='123456789012'))"` | `ValueError: Invalid -c demo_pc value: 'abc'. Must be a non-negative integer.` | ✓ PASS |
| Live API lookup with narratives (SC-1) | `curl -sS "$BACKEND_API_URL/recommendations/CUST-001"` | Not runnable in verifier env — deferred to human | ? SKIP |
| Live prewarm → 204 (SC-2) | `curl -sS -w "%{http_code}" "$BACKEND_API_URL/recommendations/CUST-001?prewarm=1"` | Not runnable in verifier env — deferred to human | ? SKIP |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| DEMO-03 (plumbing half) | 07-01-PLAN, 07-02-PLAN | `scripts/prewarm.py` warms 3 personas × both cards through API Gateway → Lambda → AgentCore → Bedrock | ✓ SATISFIED (phase scope) | Handler-side `?prewarm=1` → 204 contract shipped; CDK alias + conditional PC shipped. Tooling half (`scripts/prewarm.py`) is Phase 9 per REQUIREMENTS.md line 91 ("DEMO-03 \| Phase 7 (plumbing) + Phase 9 (tooling)"). No orphan requirements. |

No orphan requirements — `grep -E "Phase 7" .planning/REQUIREMENTS.md` maps DEMO-03 to "Phase 7 (plumbing) + Phase 9 (tooling)" and both plans declare `requirements: [DEMO-03]` in frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | No TODO/FIXME/placeholder markers found in any of the 4 modified files |

- 0 `TODO|FIXME|XXX|HACK|PLACEHOLDER` matches across `api_lambda/handler.py`, `infrastructure/constructs/backend_api.py`, `tests/test_backend_api_handler.py`, `tests/test_backend_api_synth.py`.
- 0 "placeholder/coming soon/not yet implemented" prose markers.
- 0 `return None` or empty-implementation patterns in handler (stub-return contract at `{"statusCode": 204, ...}` is the intentional SC-2 contract, not a stub).
- Pre-existing environmental failures (not Phase 7 regressions, documented in both SUMMARY.md files):
  - `tests/test_agentcore_stack_has_ssm_parameter` — `ImportError: aws_bedrock_agentcore_alpha` (alpha module not in local env)
  - `tests/test_seeder_smoke.py::*` (6 tests) — require real AWS credentials + live DynamoDB table

### Human Verification Required

**Three live-smoke test scripts needed post-deployment** — reproduced in YAML frontmatter above. Summary:

1. **SC-1: Live byte-identical narratives** — `curl` each persona, verify 4 non-empty narrative strings + marker absent.
2. **SC-2: Live prewarm → 204** — `curl ?prewarm=1` each persona, verify HTTP 204 with time_total < 25s.
3. **SC-4: UI-01 + UI-02 live smoke** — Deploy with `cdk deploy -c demo_pc=1`, wait for PC=READY (~3min), run 9 warm lookups (3 personas × 3), compute median per persona (gate: < 3000ms), verify CloudWatch `narrative_source` count ≥ 9 and `prewarm_failed` count = 0, open browser at 1280×800 to confirm UI-01 above-fold layout with narratives.

Full D-15 runbook with timings, CloudWatch queries, and `jq` output expectations is captured verbatim in `.planning/phases/07-api-pass-through-pre-warm-route/07-01-SUMMARY.md` §"D-15 Live-Smoke Closeout Gate — Runbook" — use that as the authoritative checklist.

### Gaps Summary

**No code-level gaps.** All offline-provable must-haves (13 of 15) are shipped, wired, and tested:

- The full DEMO-03 plumbing half — handler `?prewarm=1` → 204 contract (SC-2 behavioural half) and CDK alias + conditional PC (SC-3) — is complete and green.
- All 10 new pytest functions pass (6 handler + 4 synth) under `/opt/homebrew/bin/python3.13`.
- No new module-level state in the handler (Pitfall 7 — PC init risk mitigated).
- `backend_api_stack.py` is byte-unchanged (Claude's Discretion: construct-level context read).
- 0 TODO/placeholder anti-patterns.

**Remaining work is human-gated live smoke only** — SC-1 (live byte-identical narratives), SC-2 (live 204 confirmation, offline already proven), and SC-4 (UI-01 visual + UI-02 warm-median). These cannot close in CI because they require a deployed endpoint and a browser at 1280×800. The D-15 runbook in 07-01-SUMMARY.md is the operator checklist.

---

*Verified: 2026-04-25T22:36:48Z*
*Verifier: Claude (gsd-verifier)*
*Python interpreter used for tests: `/opt/homebrew/bin/python3.13` (per STATE.md line 78)*
