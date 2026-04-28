---
phase: 12-customerdataprovider-abstraction
plan: 05
subsystem: agent
tags:
  - PROD-01
  - PROD-01a
  - D-03
  - D-04
  - D-16
  - SAV-03
dependency-graph:
  requires:
    - phase-12-plan-01  # agent/providers.py exports (ToolsLambdaProvider, set_provider, get_provider)
    - phase-12-plan-02  # lambda/handler.py dispatcher (action-routed invokes from ToolsLambdaProvider)
    - phase-12-plan-04  # tests/conftest.py _provider_swap autouse fixture + tests/test_providers.py gate
  provides:
    - agent.agent.simulate_savings: "routes through get_provider().simulate_savings(customer_id)"
    - agent.agent._provider: "module-level ToolsLambdaProvider singleton registered via set_provider"
    - agent/Dockerfile: "container /app/providers.py via COPY providers.py ."
  affects:
    - phase-12-plan-06  # deploy — stack-policy lift ceremony can now proceed
tech-stack:
  added: []
  patterns:
    - "Bi-mode import (D-16): try container `from providers import ...`; fallback repo `from agent.providers import ...`"
    - "Module-level singleton (D-03): construct production ToolsLambdaProvider once, register via set_provider(); tests swap via autouse fixture"
    - "Strangler-fig seam completion (PROD-01): @tool body reduced from 16 lines of direct boto3 to 1-line provider delegation"
key-files:
  created: []
  modified:
    - agent/agent.py
    - agent/Dockerfile
decisions:
  - "Option B preserved at agent/agent.py:396-418 — the except-Exception fallback retains its raw `_lambda_client.invoke(...)` as an orthogonal D-04 defensive rail. Rationale: a bug in ToolsLambdaProvider cannot corrupt the never-500 guarantee. Cost: duplicated invoke shape (acceptable per 12-CONTEXT.md §Reusable Assets third bullet)."
metrics:
  duration: "~10 minutes"
  completed: "2026-04-28T23:07:46Z"
  tasks-completed: 3
  commits: 3
  files-modified: 2
  lines-added: 27
  lines-removed: 16
---

# Phase 12 Plan 05: Wire Strands Agent to Provider Singleton — Summary

Three surgical edits to the agent module complete the PROD-01 strangler-fig rewiring. The `simulate_savings` @tool now delegates to `get_provider().simulate_savings(customer_id)` while the D-04 never-500 fallback path retains its orthogonal raw `_lambda_client.invoke` — and the Dockerfile now COPYs `providers.py` into `/app/` so the bi-mode first branch resolves inside the production container.

## Tasks completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add bi-mode provider import block + module-level `_provider` singleton | `1628eb0` | agent/agent.py |
| 2 | Refactor @tool simulate_savings to route through `get_provider()` | `e5d72fb` | agent/agent.py |
| 3 | Add `COPY providers.py .` to agent/Dockerfile | `83a3370` | agent/Dockerfile |

## Invariant audit — all held

- **SAV-03 (LLM no arithmetic)**: `_BASE_SYSTEM_PROMPT` at `agent/agent.py:285-311` is byte-unchanged. The "TOOL OUTPUT IS THE SOURCE OF TRUTH" + "byte-for-byte" + "MUST equal the tool output exactly" language stays intact. `ToolsLambdaProvider._invoke` (`agent/providers.py:55-73`) reproduces the identical `FunctionName / InvocationType / Payload` invoke shape, so byte-exact numbers still flow from Tools Lambda's `simulate_savings_pure` to the model response.
- **D-04 (never-500 contract)**: The `except Exception:` fallback at `agent/agent.py:396-418` is BYTE-UNCHANGED from pre-plan state. Raw `_lambda_client.invoke(...)` + FALLBACKS stitching preserved as an orthogonal defensive rail (Option B per 12-PATTERNS.md line 337). `grep -c "_lambda_client.invoke" agent/agent.py` returns 1 — the fallback path only.
- **D-15 (narrative dual-gate)**: `RecommendationResponse` + `TrackInfo` Pydantic schema + `validate_usage_narrative` / `validate_call_script` validators + `_narrative_fallback_salvage` + `FALLBACKS` bank — all untouched.
- **D-16 (bi-mode imports)**: New providers import block mirrors the narrative template at `agent/agent.py:26-51` exactly — same `try / except ImportError / # pragma: no cover - hit only in offline test repo layout` structure. Dockerfile `COPY providers.py .` makes the container-side first branch resolvable at runtime.
- **`_narrative_source` marker**: internal attach/strip logic at `agent/agent.py:394,417,427,432` untouched. `api_lambda/handler.py` still strips it via `body.pop("_narrative_source", None)`.
- **`runtimeSessionId` scope**: lives in `api_lambda/handler.py` — not touched by this plan.
- **`?prewarm=1` / `?narrative=off`**: API-Lambda-layer concerns — not touched by this plan.

## Pre-deploy test gate

### What ran in the worktree

The execution sandbox blocks access to the repo's frozen `.venv` (Python 3.13 with strands + boto3 + pydantic + simple_salesforce-free lockfile). Only the system python3.9 interpreter is available, which has pytest + boto3 + pydantic but lacks `strands`. This means any test module that does `from agent.agent import ...` raises `ModuleNotFoundError: strands` at collection time and cannot execute under python3.9.

The following offline suites ran and passed under python3.9:

| Suite | Result |
|-------|--------|
| `tests/test_providers.py` | **14/14 PASSED** — Wave 2 gate held |
| `tests/test_simulate_savings.py` + `tests/test_get_billing_history.py` + `tests/test_get_hardship_flag_pure.py` + `tests/test_tariff_plans_byte_equal.py` | 40/40 PASSED |
| `tests/test_agent_tools.py` | 13/13 PASSED |
| `tests/test_prewarm_script.py` + `tests/test_backend_api_handler.py` | 26/26 PASSED |
| **Runnable subset aggregate** | **146 passed, 12 skipped (smoke), 0 failed** |

### Suites deferred to the ceremony-time python3.13 run

The following require `strands` at import and must be confirmed by the deploy orchestrator on python3.13 before `cdk deploy CustomerTariffAgent`:

- `tests/test_agent_construction.py` — imports `from agent.agent import simulate_savings, _agent, ...`; verifies `simulate_savings` is in `_agent.tool_registry` (contract held statically: @tool decorator preserved, symbol name unchanged)
- `tests/test_agent_narrative.py` + `tests/test_agent_narrative_corpus.py` + `tests/test_narrative_validator.py` — exercise TrackInfo / RecommendationResponse validators (not touched by this plan)

### Pre-existing collection/execution errors (NOT caused by this plan)

- `tests/test_backend_api_synth.py` — collection error `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` on line 154 (PEP 604 syntax `int | None` at module scope; needs py3.10+). Pre-existing under py3.9.
- `tests/test_frontend_synth.py` — 23 errors requiring Docker bundling for Amplify CDK synth. Pre-existing.

### Static verification of agent.py structure (AST-level)

```
simulate_savings decorators: ['tool']
Non-docstring body count: 1
Return: get_provider().simulate_savings(customer_id)
@tool decorators: 1
from providers: True
from agent.providers: True
Module-level calls: ['set_provider']
```

Confirms: exactly one `@tool` decorator, exactly one `return get_provider().simulate_savings(customer_id)` body statement, both bi-mode import branches present, `set_provider(_provider)` called at module scope.

### Bash/grep acceptance matrix

| Check | Result |
|-------|--------|
| `grep -q "from providers import" agent/agent.py` | PASS (line 55) |
| `grep -q "from agent.providers import" agent/agent.py` | PASS (line 64) |
| `grep -c "# pragma: no cover - hit only in offline test repo layout" agent/agent.py` | 2 (narrative + providers) |
| `grep -q "_provider = ToolsLambdaProvider(_lambda_client, _TOOLS_LAMBDA_ARN)" agent/agent.py` | PASS (line 83) |
| `grep -q "set_provider(_provider)" agent/agent.py` | PASS (line 84) |
| `grep -c "boto3.client(" agent/agent.py` | 1 (only `_lambda_client = boto3.client(...)` on line 80; no duplicate instantiation) |
| `grep -q "return get_provider().simulate_savings(customer_id)" agent/agent.py` | PASS (line 280) |
| `grep -q "# D-04: provider wraps the Lambda invoke" agent/agent.py` | PASS |
| `grep -c "_lambda_client.invoke" agent/agent.py` | 1 (fallback path at :404 — Option B preserved) |
| `grep -c "Calculate Green and Cheapest tariff savings" agent/agent.py` | 1 (docstring unchanged) |
| `grep -q "^COPY providers.py \." agent/Dockerfile` | PASS (line 9) |
| `python3 -c "import py_compile; py_compile.compile('agent/agent.py', doraise=True)"` | PASS |
| `python3 -c "from agent.providers import CustomerDataProvider, ToolsLambdaProvider, InMemoryProvider, SalesforceCustomerDataProvider, set_provider, get_provider"` | PASS |

## Deviations from Plan

None — plan executed exactly as written.

## Deploy readiness

Plan 06 can now proceed to the stack-policy lift ceremony:
1. `aws cloudformation set-stack-policy` to enable updates on `CustomerTariff` + `CustomerTariffAgent`
2. `cdk diff CustomerTariffAgent` — expect Docker image hash change (new `/app/providers.py` in layer), no stateful resource changes
3. `cdk deploy CustomerTariffAgent`
4. Container-side verification: `docker run --entrypoint python <new-image> -c "from providers import CustomerDataProvider; print('OK')"` — ROADMAP SC #5
5. Re-lock with `set-stack-policy` deny-Update:* after successful deploy

Before that ceremony runs, the orchestrator should execute `pytest -m "not smoke"` under the project's python3.13 venv to confirm the three strands-dependent suites (`test_agent_construction`, `test_agent_narrative`, `test_agent_narrative_corpus`, `test_narrative_validator`) are also green — these are the suites this worktree's python3.9 environment could not load. Static analysis + AST inspection + the already-passing `test_providers.py` gate give high confidence they will pass, because:

- `test_agent_construction.py` checks `"simulate_savings" in _agent.tool_registry` — symbol name and @tool decorator are preserved byte-exact.
- Narrative tests never touch `simulate_savings` or the provider layer — pure schema/validator exercise.
- `_provider_swap` autouse fixture means any test entering the @tool now routes through InMemoryProvider in place of the former direct `_lambda_client.invoke` — the switch is already exercised green by `test_providers.py`.

## Self-Check: PASSED

Verified the following claims:

```
[ -f "agent/agent.py" ] && echo FOUND      → FOUND
[ -f "agent/Dockerfile" ] && echo FOUND    → FOUND
git log --oneline | grep 1628eb0           → FOUND
git log --oneline | grep e5d72fb           → FOUND
git log --oneline | grep 83a3370           → FOUND
```

All three plan commits present on branch, both target files modified, static verification clean.
