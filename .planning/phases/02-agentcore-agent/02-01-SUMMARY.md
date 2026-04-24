---
phase: 02-agentcore-agent
plan: 01
subsystem: agent
status: complete
tags:
  - strands-sdk
  - bedrock-agentcore
  - docker
  - pytest
dependency_graph:
  requires: []
  provides:
    - agent/agent.py (Strands agent with @tool + BedrockAgentCoreApp entrypoint)
    - agent/requirements.txt (container deps: strands-agents, bedrock-agentcore, boto3)
    - agent/Dockerfile (linux/arm64, Python 3.12, port 8080)
    - tests/test_agent_tools.py (13 offline tests for tool contract + savings invariants)
  affects:
    - "Plan 02-02 (CDK infrastructure): agent/ directory is the Docker build context for from_asset()"
    - "Plan 02-03 (deploy + smoke): agent code runs inside the deployed container"
key_files:
  created:
    - agent/agent.py
    - agent/requirements.txt
    - agent/Dockerfile
    - tests/test_agent_tools.py
  modified:
    - tests/conftest.py (added mock_savings_response, mock_marcus_response, mock_elena_response fixtures)
    - pytest.ini (added smoke marker registration)
metrics:
  completed: "2026-04-23"
  tasks_completed: 2
  files_created: 4
  files_modified: 2
---

# Phase 2 Plan 1: Agent Code + Offline Tests Summary

**One-liner:** Strands SDK agent with @tool wrapper invoking Phase 1 ToolsLambda, Pydantic dual-track response schema, linux/arm64 Dockerfile, and 13 offline tests covering REC-01/02/03, SAV-01/02/03, SC-4.

## What Was Built

### Task 1: Agent Source Code

**`agent/agent.py`** — Complete Strands agent module:
- `@tool simulate_savings(customer_id)` — invokes ToolsLambda via `boto3.client("lambda").invoke()`, reads `TOOLS_LAMBDA_ARN` from environment
- `RecommendationResponse(BaseModel)` — Pydantic schema with `green: TrackInfo` and `cheapest: TrackInfo` fields, enforcing both tracks always present (REC-03)
- `SYSTEM_PROMPT` — 6 rules enforcing dual-track output, no LLM arithmetic, no ranking
- `_agent = Agent(model=BedrockModel(...), system_prompt=..., tools=[simulate_savings])` — Claude 3.7 Sonnet
- `@app.entrypoint invoke(payload)` — BedrockAgentCoreApp handler with `structured_output` + direct-tool-call fallback
- Error handling: checks `FunctionError` in Lambda response, validates `TOOLS_LAMBDA_ARN` is set

**`agent/requirements.txt`** — Pinned container dependencies:
- `strands-agents==1.37.0`
- `bedrock-agentcore==1.6.3`
- `boto3>=1.42.0`

**`agent/Dockerfile`** — AgentCore container:
- `FROM --platform=linux/arm64 python:3.12-slim` (Pitfall 2: Graviton)
- `EXPOSE 8080` (BedrockAgentCoreApp default)
- `CMD ["python", "agent.py"]`

### Task 2: Offline Test Suite

**`tests/test_agent_tools.py`** — 13 tests, all passing:

| Test | Requirement | What it verifies |
|------|-------------|-----------------|
| test_both_tracks_present | REC-03 | Both green and cheapest keys in response |
| test_green_track_present | REC-01 | Green plan_id == ECO, plan_name == EcoFlex 100 |
| test_cheapest_track_present | REC-02 | Cheapest plan_id == VAL, plan_name == Value 12 |
| test_tracks_diverge | REC-03 | Green != Cheapest plan_id |
| test_monthly_saving_nonzero | SAV-01 | Both tracks saving_monthly > 0 |
| test_annual_saving_formula | SAV-02 | saving_annual == saving_monthly * 12 |
| test_result_shape | REC-01..03 | Exact key set: {plan_id, plan_name, saving_monthly, saving_annual} |
| test_numbers_from_tool_not_llm | SAV-03 | Sarah: green=$30.00, cheapest=$55.00 |
| test_cheapest_gte_green_sarah | SC-4 | cheapest >= green for CUST-001 |
| test_cheapest_gte_green_marcus | SC-4 | cheapest >= green for CUST-002 |
| test_cheapest_gte_green_elena | SC-4 | cheapest >= green for CUST-003 |
| test_tool_invokes_lambda_with_customer_id | SAV-03 | Mocked Lambda call passes customer_id correctly |
| test_tool_handles_lambda_error | — | FunctionError detected in Lambda response |

**`tests/conftest.py`** — 3 new fixtures added:
- `mock_savings_response` — Sarah Chen canonical response ($30/$55)
- `mock_marcus_response` — Marcus Webb ($16.90/$30.98)
- `mock_elena_response` — Elena Vasquez ($14.00/$25.67)

**`pytest.ini`** — `smoke` marker registered for live tests in Plan 03.

## Test Results

```
tests/test_agent_tools.py: 13 passed
Full offline suite: 50 passed, 6 skipped (seeder smoke)
```

All Phase 1 tests remain green. No regressions.

## Deviations

None — plan executed as written.

## Self-Check: PASSED

- agent/agent.py: @tool, BedrockAgentCoreApp, RecommendationResponse, SYSTEM_PROMPT all present
- agent/Dockerfile: linux/arm64, port 8080, python:3.12-slim
- agent/requirements.txt: strands-agents==1.37.0, bedrock-agentcore==1.6.3
- 13/13 offline tests pass
- 50/50 offline suite tests pass (Phase 1 + Phase 2)
- pytest.ini smoke marker registered
