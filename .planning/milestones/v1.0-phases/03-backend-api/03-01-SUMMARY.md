---
phase: 03-backend-api
plan: 01
subsystem: api-lambda
status: complete
tags:
  - lambda
  - api
  - pytest
  - bedrock-agentcore
dependency_graph:
  requires: []
  provides:
    - api_lambda/handler.py (AgentCore runtime proxy, D-12 error taxonomy, fresh uuid4 per invocation)
    - api_lambda/__init__.py (package marker)
    - tests/test_backend_api_handler.py (9 offline unit tests, 24 collected with parametrize)
  affects:
    - "Plan 03-02 (CDK): packaged via Code.from_asset('api_lambda')"
    - "Plan 03-03 (deploy + smoke): handler behaviour proven offline before live invocation"
key_files:
  created:
    - api_lambda/handler.py
    - api_lambda/__init__.py
    - tests/test_backend_api_handler.py
  modified:
    - tests/conftest.py (added mock_agent_invoke_response, mock_agent_invoke_not_found)
metrics:
  completed: "2026-04-24"
  tasks_completed: 4
  files_created: 3
  files_modified: 1
  tests_added: 24
---

# Phase 3 Plan 1: API Lambda Handler + Offline Tests Summary

**One-liner:** API Lambda handler with full D-12 error taxonomy, fresh uuid4 session per call, botocore 25s timeout, and 24-case offline suite.

## What Was Built

### Task 1.1: Handler Module

**`api_lambda/handler.py`** — API Gateway HTTP API v2 -> AgentCore runtime proxy:
- `_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")` — D-13 regex, mirrors `lambda/handler.py`
- Module-level `_agentcore_client` with `Config(read_timeout=25, connect_timeout=5)` — Pitfall 1 mitigation (default 60s outlasts Lambda 30s)
- `def handler(event, context)` — fast-fail regex validation, then `_agentcore_client.invoke_agent_runtime(...)` with fresh `str(uuid.uuid4())` per call (D-11, T-03-02)
- Error taxonomy (D-12):
  - 400 on invalid `customer_id` format
  - 404 on missing `green`/`cheapest` keys in agent response (Pitfall 5)
  - 504 on `ReadTimeoutError`
  - 502 on `ClientError`
  - 500 on any other `Exception`
- 200 response is verbatim pass-through of agent body (D-02 — no envelope, no meta)

**`api_lambda/__init__.py`** — empty Python package marker so tests can import `api_lambda.handler`.

### Task 1.2: Phase 3 Fixtures

**`tests/conftest.py`** — extended with two Phase 3 fixtures:
- `mock_agent_invoke_response` — wraps Sarah's canonical body in `io.BytesIO` to match StreamingBody shape
- `mock_agent_invoke_not_found` — `{"errorMessage": "..."}` with no `green`/`cheapest` keys to simulate 404 path

### Task 1.3: Offline Unit Tests

**`tests/test_backend_api_handler.py`** — 9 test functions, 24 cases collected (with parametrize):

| Test | Requirement | What it verifies |
|------|-------------|-----------------|
| test_valid_customer_returns_200_and_passes_through_body | SC-1, D-02 | Handler returns pass-through shape with `{green, cheapest}` |
| test_invalid_customer_id_returns_400 (parametrized ×5) | SC-2, D-13, T-03-01 | NOTVALID / cust-001 / CUST-1 / CUST-1234567 / "" all rejected before client call |
| test_missing_green_returns_404 | SC-2 | Agent response missing `green` -> 404 |
| test_missing_cheapest_returns_404 | SC-2 | Agent response missing `cheapest` -> 404 |
| test_timeout_returns_504 | SC-2, T-03-03 | `ReadTimeoutError` -> 504 with friendly message |
| test_client_error_returns_502 | SC-2 | `ClientError(ThrottlingException)` -> 502 |
| test_unexpected_error_returns_500 | SC-2, T-03-04 | Any other `Exception` -> 500 |
| test_fresh_session_id_per_call | SC-3, D-11, T-03-02 | Two invocations produce two distinct uuid4 session IDs, each >= 33 chars |

## Test Results

```
tests/test_backend_api_handler.py: 24 passed
Full offline suite: 81 passed, 6 skipped (smoke), 23 deselected
```

No Phase 1 or Phase 2 regressions.

## Deviations

None — plan executed as written. Handler structure, error taxonomy, and test cases match the 03-01-PLAN.md contract byte-for-byte.

## Self-Check: PASSED

- `api_lambda/handler.py` parses as valid Python
- `_CUSTOMER_ID_PATTERN`, `Config(read_timeout=25, connect_timeout=5)`, `str(uuid.uuid4())` inside `handler()` body all present
- 9 test functions, 24 parametrized cases, all green
- Phase 1/2 fixtures preserved in conftest.py
