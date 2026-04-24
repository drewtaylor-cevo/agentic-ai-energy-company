---
phase: 05-demo-hardening
plan: 02
type: execute
status: complete
completed: 2026-04-25
---

# Plan 05-02 Summary — Live AWS deploy + curl smoke

All 3 CDK stacks are deployed and healthy in us-east-1. CfnOutputs captured and committed. Live smoke tests pass against the real AgentCore runtime and HTTP API Gateway: 10/10 backend API cases + 13/13 agent runtime cases, including DEMO-02 flagship ($30/$55 for CUST-001).

## Outcome

Phase 5 has a live, working demo environment. `ApiEndpoint` can now be consumed by Plan 05-03 as `VITE_API_URL` for the production UI bundle.

## Evidence

### Task 1 — Live deployment (human checkpoint)

User deployed stacks one-at-a-time (mandatory for SSM cross-stack resolution):

1. `npx aws-cdk@latest deploy CustomerTariff --require-approval never` → `✅  CustomerTariff`
2. `npx aws-cdk@latest deploy CustomerTariffAgent --require-approval never` → `✅  CustomerTariffAgent`
3. `npx aws-cdk@latest deploy CustomerTariffApi --require-approval never` → `✅  CustomerTariffApi`

User typed `approved` after confirming all 3 stacks `CREATE_COMPLETE` via `describe-stacks`, no rollbacks. `ApiEndpoint` and `AgentRuntimeArn` visible in outputs.

### Task 2 — CfnOutputs captured

Written to `.planning/phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md` (commit `7863863`):

| Stack | Output | Value |
|-------|--------|-------|
| CustomerTariff | BillingTableName | `tariff-billing` |
| CustomerTariff | BillingTableArn | `arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing` |
| CustomerTariff | ToolsLambdaName | `tariff-tools` |
| CustomerTariff | ToolsLambdaArn | `arn:aws:lambda:us-east-1:588738606436:function:tariff-tools` |
| CustomerTariffAgent | AgentRuntimeArn | `arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V` |
| CustomerTariffAgent | AgentRuntimeId | `tariff_agent-O2Hai86N8V` |
| CustomerTariffApi | ApiEndpoint | `https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/` |

**SSM cross-stack parameter:** `/customer-tariff/agent-runtime-arn` exactly equals `CustomerTariffAgent.AgentRuntimeArn` — cross-stack wiring verified at capture time.

**Tool versions recorded for Plan 07 Environment Lock:** CDK 2.1119.0, Node v24.12.0, Python 3.9.6, Docker 29.2.1.

**Git SHA at capture:** `1ac43c1ea2504479d3c7658597674c1e787b5f77` (will be tagged `demo-v1.0` in Plan 07).

### Task 3 — Live smoke tests

Env var extraction from `05-DEPLOY-OUTPUTS.md` worked cleanly:

```
BACKEND_API_URL=https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/
AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V
```

Test results against the live environment:

| Suite | Command | Result |
|-------|---------|--------|
| Backend API (curl-level, D-03 gate) | `python3 -m pytest tests/test_backend_api_smoke.py -v -m smoke` | **10 passed in 19.97s** |
| AgentCore runtime (bedrock-agentcore invoke) | `python3 -m pytest tests/test_agent_smoke.py -v -m smoke` | **13 passed, 1 warning in 32.04s** |

**All DEMO-02 flagship invariants verified on live infra:**
- CUST-001 Sarah: green.saving_monthly ≈ $30.00 (±$0.50) and cheapest.saving_monthly ≈ $55.00 (±$0.50) — `test_sarah_flagship_values` passed
- Fresh session isolation holds: CUST-001 ≠ CUST-002 savings — `test_fresh_session_no_bleed` passed
- Error paths: invalid format → 400, unknown customer → 404 — all parametrized cases passed
- Both tracks > 0 and cheapest >= green for all 3 personas — verified

## Self-Check: PASSED

- [x] 3 stacks `CREATE_COMPLETE` in us-east-1 (user-confirmed)
- [x] `05-DEPLOY-OUTPUTS.md` exists, all 7 CfnOutputs recorded
- [x] Tool versions captured (CDK, Node, Python, Docker)
- [x] Git SHA recorded in frontmatter
- [x] SSM parameter == AgentRuntimeArn invariant verified
- [x] Backend API smoke: 10/10 passed
- [x] Agent runtime smoke: 13/13 passed (DEMO-02 flagship within tolerance)
- [x] ApiEndpoint noted for Plan 05-03 consumption: `https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/`

## Key files

### Created
- `.planning/phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md` (commit `7863863`)
- `.planning/phases/05-demo-hardening/05-02-SUMMARY.md` — this file

### Modified
None. Source tree unchanged; this plan captures live cloud state only.

## What this unblocks

- **Plan 05-03** can set `VITE_API_URL=https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/` for the production `ui/dist/` bundle.
- **Plan 05-05** rehearsals have a live endpoint to benchmark warm latency against (<3s target for D-10).
- **Plan 05-07** Environment Lock already has the tool versions and stack identifiers it needs.

## Reference values for downstream plans

| Consumer | Value | Source |
|----------|-------|--------|
| Plan 03 `VITE_API_URL` | `https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/` | `ApiEndpoint` CfnOutput |
| Plan 05 rehearsal | same URL | "" |
| Plan 07 lock | Git SHA `1ac43c1ea2504479d3c7658597674c1e787b5f77` | `git rev-parse HEAD` at capture |
