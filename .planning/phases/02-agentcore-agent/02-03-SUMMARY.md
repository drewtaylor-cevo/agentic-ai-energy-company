---
phase: 02-agentcore-agent
plan: 03
subsystem: deploy/verification
status: complete
tags:
  - deploy
  - smoke-test
  - agentcore
dependency_graph:
  requires:
    - 02-01 (agent/ directory)
    - 02-02 (CDK stacks)
  provides:
    - Deployed AgentCore runtime (tariff_agent-O2Hai86N8V) in us-east-1
    - tests/test_agent_smoke.py (13 live smoke tests)
  affects:
    - Phase 3 (Backend API): agent runtime ARN is the invocation target
key_files:
  created:
    - tests/test_agent_smoke.py
  modified:
    - agent/agent.py (model ID fix + fallback fix)
    - infrastructure/constructs/agent_runtime.py (IAM cross-region fix)
decisions:
  - "Model ID changed from anthropic.claude-3-7-sonnet-20250219-v1:0 to us.anthropic.claude-3-7-sonnet-20250219-v1:0 — Bedrock requires cross-region inference profile for on-demand access"
  - "IAM bedrock:InvokeModel* resources changed from region-specific to arn:aws:bedrock:*:: — cross-region inference profile routes to multiple US regions"
  - "Fallback in entrypoint changed from simulate_savings.tool_function() to direct Lambda invoke — Strands DecoratedFunctionTool doesn't expose tool_function attribute"
metrics:
  completed: "2026-04-23"
  tasks_completed: 2
  files_created: 1
  files_modified: 2
  deploy_iterations: 3
---

# Phase 2 Plan 3: Deploy + Live Smoke Tests Summary

**One-liner:** AgentCore runtime deployed and verified — 13/13 smoke tests pass across all 3 personas in 22 seconds.

## What Was Built

### Task 1: Smoke Test File

**`tests/test_agent_smoke.py`** — 13 parametrized live tests:
- `test_both_tracks_present` × 3 personas (SC-1)
- `test_savings_fields_present` × 3 personas (SC-2)
- `test_correct_plan_selection` × 3 personas (SC-3)
- `test_cheapest_gte_green` × 3 personas (SC-4)
- `test_sarah_flagship_values` (DEMO-02)

Skip guard on `AGENT_RUNTIME_ARN` env var. Marked `@pytest.mark.smoke`.

### Task 2: Deploy + Verification (Human Checkpoint)

**Deploy completed successfully** after 3 iterations:

| Attempt | Issue | Fix |
|---------|-------|-----|
| 1 | `docker-credential-osxkeychain` not found during ECR push | Removed `credsStore` from `~/.docker/config.json` |
| 2 | `ValidationException: Invocation of model ID anthropic.claude-3-7-sonnet-20250219-v1:0 with on-demand throughput isn't supported` | Changed model ID to `us.anthropic.claude-3-7-sonnet-20250219-v1:0` (cross-region inference profile) |
| 3a | `AccessDeniedException: bedrock:InvokeModelWithResponseStream on us-east-2` | IAM resources changed from `arn:aws:bedrock:{region}::` to `arn:aws:bedrock:*::` for cross-region routing |
| 3b | `'DecoratedFunctionTool' object has no attribute 'tool_function'` | Fallback changed to direct `_lambda_client.invoke()` instead of Strands internal API |

**Final deploy output:**
- Runtime ARN: `arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V`
- Runtime status: READY
- All 13 smoke tests: PASSED (21.97s)

## Phase 2 Success Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| SC-1: Both Green and Cheapest returned simultaneously | VERIFIED | `test_both_tracks_present` passes for all 3 personas |
| SC-2: Monthly + annual savings present, computed by tool | VERIFIED | `test_savings_fields_present` passes; numbers match Phase 1 tool output |
| SC-3: Green = ECO, Cheapest = VAL for all personas | VERIFIED | `test_correct_plan_selection` passes for all 3 personas |
| SC-4: cheapest >= green for all personas | VERIFIED | `test_cheapest_gte_green` passes for all 3 personas |
| DEMO-02: Sarah ~$30 Green, ~$55 Cheapest | VERIFIED | `test_sarah_flagship_values` passes within ±$0.50 tolerance |

## Deviations from Plan

1. **Model ID**: `anthropic.claude-3-7-sonnet-20250219-v1:0` → `us.anthropic.claude-3-7-sonnet-20250219-v1:0`. Bedrock requires cross-region inference profiles for on-demand access (not documented in Phase 2 research).

2. **IAM scope widened**: `arn:aws:bedrock:{region}::foundation-model/*` → `arn:aws:bedrock:*::foundation-model/*`. Cross-region inference profiles route to multiple US regions; single-region IAM blocks the routed requests.

3. **Fallback code fixed**: `simulate_savings.tool_function()` → direct `_lambda_client.invoke()`. Strands `@tool` decorator wraps functions in `DecoratedFunctionTool` which doesn't expose `tool_function`. Direct Lambda call is cleaner anyway.

## Self-Check: PASSED

- 13/13 smoke tests pass
- Runtime status: READY
- All 4 Phase 2 success criteria verified
- Phase 2 complete — ready for Phase 3
