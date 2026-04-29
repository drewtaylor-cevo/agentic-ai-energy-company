# Phase 13 Plan 08 — Ceremony Log

Started: 2026-04-29T12:19:57Z
Operator: drew.taylor@cevo.com.au (via Claude Code interactive ceremony)
Account: cevo-dev25 (588738606436) / us-east-1
Pre-ceremony HEAD: b45b843881f33e5c7ae4cfde7adb23a40bab82d6

## Pre-flight (Task 8.1)
- [x] Plan 07 A-03 sighting decision: **deferred-to-in-situ** — operator chose to measure CUST-003 median during Task 8.7 post-freeze prewarm rather than pre-emptive dev-alias sighting (no dev-alias exists; only `tariff_agent-O2Hai86N8V` v10 serves Phase 12 code). Break-glass option-1 (drop `detect_bill_shock` from CUST-003 prompt path) will be applied reactively if Task 8.7 median ≥ 2500ms.
- [x] Dockerfile COPY directives present: `COPY narrative/`, `COPY reasoning/`, `COPY hooks/` — verified (lines 10-12).
- [x] Local bi-mode smoke (linux/arm64): PASS — `from reasoning.summaries import summary_simulate_savings; from hooks.four_tool_cap import FourToolCapHook; print('bi-mode OK')` → `bi-mode OK`.
- [x] Deny-Update:* confirmed on CustomerTariff / CustomerTariffAgent / CustomerTariffApi (get-stack-policy showed `"Effect": "Deny", "Action": "Update:*"` on all 3).
- [x] Termination protection confirmed `True` on all 3 stacks (describe-stacks query).

## Lift Decision (Task 8.2)
- Timestamp: 2026-04-29T12:24:30Z
- `cdk diff CustomerTariffApi` output at `/tmp/cdk-diff-api.txt`; summary: **no differences** (Number of stacks with differences: 0). Plan 05 added tests only, not API Lambda code — confirms D-31 Case A.
- Decision: **2-stack-lift** (CustomerTariff + CustomerTariffAgent; CustomerTariffApi stays frozen).

## Pre-capture (Task 8.2)
- Backend: `https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com` (frozen v2.0/v3.0-Phase-12 stack)
- Script: `scripts/capture_live_recommendations.py --mode pre` (Phase 12 D-06 script)
- Deviation: script hardcodes output to `.planning/phases/12-customerdataprovider-abstraction/baseline/pre/`; captured 5 personas there then `cp`'d CUST-001/002/003 into `.planning/phases/13-bill-shock-multi-tool-flow-agent-01/baseline/pre/` (Plan 08 expectation). No `--customers` or `--output-dir` flag on the actual script — Plan 08 plan text was aspirational.
- [x] baseline/pre/CUST-001.json saved (green ECO $30.0 / $360.0, cheapest VAL $55.0 / $660.0) — byte-match Phase 11 D-13
- [x] baseline/pre/CUST-002.json saved (green ECO $16.9 / $202.8, cheapest VAL $30.98 / $371.76) — byte-match Phase 11 D-13
- [x] baseline/pre/CUST-003.json saved (green ECO $14.0 / $168.0, cheapest VAL $25.67 / $308.04) — byte-match Phase 11 D-13
- [x] `reasoning_trace` key absent in all 3 pre-captures (expected — pre-Phase-13 baseline)

## Lift (Task 8.3)
- Timestamp: 2026-04-29T12:27:00Z
- Stacks lifted: CustomerTariff, CustomerTariffAgent (2-stack lift per Task 8.2 decision)
- [x] CustomerTariff policy: `Allow: Update:*` (verified via get-stack-policy)
- [x] CustomerTariff termination protection: disabled (`False`)
- [x] CustomerTariffAgent policy: `Allow: Update:*` (verified)
- [x] CustomerTariffAgent termination protection: disabled (`False`)
- [x] CustomerTariffApi: skipped (cdk diff==0); still `Deny: Update:*` + termination protection `True`

## Deploy (Task 8.4)
- Timestamp: 2026-04-29T12:28:00Z → 2026-04-29T12:30:00Z
- [x] `cdk deploy CustomerTariff --require-approval never`: deployed in 26.29s; stack status `UPDATE_COMPLETE`. Tools Lambda asset `current_account-us-east-1-91672bef` rebuilt (includes Plan 01 `detect_bill_shock_pure` + `"detect_bill_shock"` handler branch). Log: `/tmp/deploy-tariff.log`. Stack ARN: `arn:aws:cloudformation:us-east-1:588738606436:stack/CustomerTariff/642a1730-3f11-11f1-b95c-0e3dd0f0bb6b`.
- [x] `cdk deploy CustomerTariffAgent --require-approval never`: deployed in 25.25s; stack status `UPDATE_COMPLETE`. Runtime `tariff_agent-O2Hai86N8V` version `10` → `11` (READY). New container image digest `sha256:c84b5e7c82c93d40966f629d6ab8b8849858c2cf4df731debd6b5e2050601f7f`. Log: `/tmp/deploy-agent.log`. Stack ARN: `arn:aws:cloudformation:us-east-1:588738606436:stack/CustomerTariffAgent/9b4763d0-3f1b-11f1-9085-0affd0ba2291`.
- [x] Container bi-mode smoke against ECR image: **PASS** — `from reasoning.summaries import summary_simulate_savings; from hooks.four_tool_cap import FourToolCapHook; print('bi-mode OK')` → `bi-mode OK` (ECR URI: `588738606436.dkr.ecr.us-east-1.amazonaws.com/cdk-hnb659fds-container-assets-588738606436-us-east-1:76f629faf89aafbafe440fed9ec15c4219d6559007dff80181cc75d6e0627874`). Pitfall 4 gate: CLEAR.
- [x] CustomerTariffApi: skipped (cdk diff==0; stack remains frozen).

## Post-capture + Byte-Equivalence Gate (Task 8.5)
- Timestamp: 2026-04-29T12:34Z (initial post-capture) → 2026-04-29T12:55Z (post-fix re-capture)
- [x] baseline/post/CUST-001.json saved
- [x] baseline/post/CUST-002.json saved
- [x] baseline/post/CUST-003.json saved

### Initial capture — SAV-03 PASS, but `reasoning_trace` regression discovered

Initial byte-equivalence gate PASSED on SAV-03-sensitive fields (green/cheapest plan_id, plan_name, saving_monthly, saving_annual all byte-equal across CUST-001/002/003 pre vs post). BUT `reasoning_trace: []` on all 3 personas despite narrative marked `"model"` (happy path, no D-04 fallback).

Diagnosis (inline debug during lift window):
- Tools Lambda CloudWatch `Invocations` showed 12/min during capture — tools ARE being called.
- Direct `_extract_reasoning_trace` review: iterates `agent_result.message['content']`, but Strands 1.37's `AgentResult.message` is documented as "the LAST message" only. With `structured_output_model=` set, intermediate tool-use/tool-result turns live in the Agent's conversation history (`_agent.messages`), NOT on `agent_result.message`.
- Offline tests in `tests/test_bill_shock_flow.py` masked the defect: they build synthetic `AgentResult` objects with pre-populated tool-use blocks in `.message`, which is not how Strands actually populates that field at runtime.

### Inline fix (commit `5644003`)
- Added `messages: list | None = None` parameter to `_extract_reasoning_trace`; when provided, iterates across all messages; when None, preserves the offline-test contract by falling back to `agent_result.message['content']`.
- `invoke()` snapshots `_messages_start = len(_agent.messages)` BEFORE the `_agent(...)` call; passes `_agent.messages[_messages_start:]` to all 4 extractor call sites. SC-3 mirror — cross-invocation bleed would otherwise leak prior tool uses.
- All 315 offline tests pass.
- Redeployed `cdk deploy CustomerTariffAgent` at 12:52Z; runtime v11 → v12 (READY). New image digest `sha256:15bb94c16f8f55bb70954da9f0fe3bcd235c855cadd3f369c9dbb77d47bc618d`.

### Post-fix re-capture gate

- [x] CUST-001 savings byte-equal pre vs post: **PASS**; reasoning_trace length=3 tools=[get_hardship_flag, detect_bill_shock, simulate_savings]; middle entry "No bill shock"
- [x] CUST-002 savings byte-equal pre vs post: **PASS**; reasoning_trace length=3 same shape; middle entry "No bill shock"
- [x] CUST-003 savings byte-equal pre vs post: **PASS**; reasoning_trace length=3; middle entry **"Bill shock detected: +$65.16 2025-10 vs 11-month avg ($167.88 vs $102.72)"** — Elena's shock flagged as designed
- [x] Cross-persona fabrication signal intact: Elena's middle trace entry is byte-different from Sarah/Marcus (C5 canary green)

### Latency observations (in-lift, not yet gate-checked)
- curl `/recommendations/CUST-003` end-to-end total: **16.9s cold** (includes AgentCore microVM cold-start + 3 tool calls). Warm-turn median measurement deferred to Task 8.7's `prewarm.py` run.
- Agent runtime log: `Invocation completed successfully (13.802s)` for an earlier shot.
- This is consistent with PITFALLS.md C1 estimate (2600-5400ms for full multi-tool warm) — cold-start is ~10-13s above that.

## Re-apply Freeze (Task 8.6)
- Timestamp: 2026-04-29T12:57Z
- Byte-equality methodology: CloudFormation `get-stack-policy` returns the policy body with an extra trailing `\n\n` vs the source `*-freeze.json` files (CFN-side serialisation artefact). Applied Phase 12 precedent — normalise trailing whitespace + strip empty lines for comparison. Policy STATEMENTS are byte-equal; this is a "no drift" outcome (Pitfall 6 not triggered).
- [x] CustomerTariff policy re-applied; byte-equal (normalised) to `foundation-freeze.json`
- [x] CustomerTariff termination protection: re-enabled (`True`)
- [x] CustomerTariffAgent policy re-applied; byte-equal (normalised) to `agentcore-freeze.json`
- [x] CustomerTariffAgent termination protection: re-enabled (`True`)
- [x] CustomerTariffApi: skipped (never lifted). Final state: `Deny` + `TP=True`.
- [x] Final freeze-state sweep — all 3 stacks `Deny` / `TP=True` / `UPDATE_COMPLETE`.

## Post-freeze Live Sanity (Task 8.7)

**Result: partial — two P0 regressions surfaced. Ceremony closed with documented gaps; Phase 13.1 will own remediation.**

### Prewarm per-flow gate (D-18): FAIL
`scripts/prewarm.py` against frozen stack, 3-pass warming + 3-sample measurement:

| Persona | Warm pass medians | Measurement median | Gate | Verdict |
|---------|-------------------|--------------------|------|---------|
| CUST-001 (single-tool expected) | 17847/16229/17138 ms | **17203ms** | 3000ms | FAIL (~5.7× over) |
| CUST-003 (multi-tool) | 13437/19116/14278 ms | **19733ms** | 2500ms | FAIL (~7.9× over) |

Exit 1 from prewarm (gate aggregation). Log: `/tmp/prewarm-post-freeze.log`.

Secondary spot-check (3 warm CUST-001 calls after prewarm): 14286 / 17936 / 14965 ms — latency is sustained, not cold-start alone.

Root cause hypothesis (Phase 13.1 will verify):
- Plan 03's preference-ordered 4-tool graph in `_BASE_SYSTEM_PROMPT` now induces Claude Sonnet 4.6 to call all 3 pre-tools (`get_hardship_flag` → `detect_bill_shock` → `simulate_savings`) on **every** customer, not just bill-shock candidates. Evidence: all 3 captured personas (001/002/003) show identical 3-entry reasoning_trace shape.
- 3 × ~400-900ms per tool round-trip + Bedrock think time puts this in the 10-20s band (consistent with PITFALLS.md C1 high-end estimate).
- AGENT-01a (warm p95 < 2500ms) is violated across the board — not just on multi-tool persona.

### 404 detection (REC-03 / D-12): FAIL
`tests/test_backend_api_smoke.py::test_unknown_customer_returns_404` — Expected 404 for CUST-999, got HTTP 200 with a synthetic track response:

```json
{
  "green": {"plan_id": "UNKNOWN", "plan_name": "UNKNOWN", "saving_monthly": 0.0, ...},
  "cheapest": {"plan_id": "UNKNOWN", "plan_name": "UNKNOWN", "saving_monthly": 0.0, ...},
  "reasoning_trace": [
    {"tool": "get_hardship_flag", "summary": "hardship_flag=False"},
    {"tool": "detect_bill_shock", "summary": "No bill shock: monthly usage within 11-month envelope"}
  ]
}
```

Manual probe: `curl /recommendations/CUST-999` → HTTP 200.

Root cause: `api_lambda/handler.py:152` detects customer-not-found via "no `green` or `cheapest` keys in body" — designed around the v1.0/v2.0 agent fallback path returning `{"errorMessage": "..."}`. Plan 03's new multi-tool prompt now has the LLM COMPOSE a full RecommendationResponse with `UNKNOWN` placeholder track data when `get_billing_history` comes back empty, so the detection never fires. D-12 contract violated.

### Smoke suite: FAIL
`pytest -m smoke -x` failed on `test_unknown_customer_returns_404` (above). Remaining 8 non-skipped smoke tests passed (21 skipped due to missing env var gates). Full log: `/tmp/smoke-post-freeze.log`. The D-19 latency-floor test (CUST-003 > 1000ms) would PASS — the issue is the ceiling, not the floor. D-21 CloudWatch counter probably passes (we saw 12 invocations/min of `tariff-tools` during capture).

### Sighting decision reconciled
The A-03 sighting-shot was deferred-to-in-situ (Task 8.1). Task 8.7 IS the in-situ measurement — and it failed the gate. Break-glass option-1 (drop `detect_bill_shock` from CUST-003 path) would have helped Elena's trace but would NOT fix the CUST-001 latency miss, since CUST-001 is also now triggering the 3-tool flow. Phase 13.1 needs a broader prompt fix than A-03 anticipated.

## Ceremony Close (with gaps)
- Finished: 2026-04-29T13:04Z
- Duration: ~45 min wall clock
- Stacks updated: CustomerTariff (v2.0→v3.0/Phase13), CustomerTariffAgent (runtime v10 → v12, includes extractor fix)
- Byte-equivalence gate: **PASS** — SAV-03 preserved on CUST-001/002/003 green.plan_id, green.plan_name, green.saving_monthly, green.saving_annual, cheapest.plan_id, cheapest.plan_name, cheapest.saving_monthly, cheapest.saving_annual. 24/24 fields byte-equal pre vs post.
- reasoning_trace contract: **PASS** — all 3 personas return 3-entry trace; C5 cross-persona fabrication signal green (Elena's middle entry byte-different from Sarah/Marcus).
- Freeze re-apply: **PASS** — byte-equal to *-freeze.json on both lifted stacks (normalised for CFN trailing-whitespace artefact); termination protection re-enabled.
- Smoke suite + latency gate: **FAIL** — two P0 regressions documented above.
- **Decision: close ceremony with gaps; Phase 13.1 owns remediation.**
- Phase 13.1 scope:
  - P0: fix `api_lambda/handler.py:152` 404 detection (detect `plan_id=="UNKNOWN"` or `saving_monthly==0` as additional sentinel), OR update agent system prompt to short-circuit to an errorMessage shape when billing_history is empty.
  - P0: latency remediation — either (a) prompt-edit to cap non-shock personas at `simulate_savings` only (2-tool cap), (b) keepalive always-on for demos, or (c) accept 4x gate overrun and revise AGENT-01a SLO.
  - P1: add offline test that asserts CUST-999 / unknown-customer path returns handler 404 (regression guard against C3).

## Commit SHA for Phase 17 freeze manifest
- Pre-ceremony HEAD: b45b843881f33e5c7ae4cfde7adb23a40bab82d6
- Mid-ceremony fix commit: 5644003 (extractor reads `_agent.messages` slice)
- Final deployed HEAD (as of ceremony close): will capture at summary-write time via `git rev-parse HEAD`
