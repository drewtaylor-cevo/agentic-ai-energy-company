---
phase: 07-api-pass-through-pre-warm-route
plan: 02
status: complete
completed: 2026-04-26
---

# Plan 07-02 SUMMARY — CDK `live` Alias + Context-Gated Provisioned Concurrency

## Objective

Wire `BackendApiConstruct` to always create a Lambda alias named `live` tracking `fn.current_version`, retarget the API Gateway v2 `HttpLambdaIntegration` from the raw function to the alias, and add a context-gated `-c demo_pc=N` switch that attaches Provisioned Concurrency to the alias only when `N > 0`. `backend_api_stack.py` stays byte-unchanged (Claude's Discretion resolution per 07-PATTERNS.md).

## Tasks

- [x] **Task 1** — Extend `BackendApiConstruct`: read `demo_pc` via `self.node.try_get_context`, validate (int cast + non-negative), always create `fn.add_alias("live", ...)`, pass `provisioned_concurrent_executions=demo_pc` only when `demo_pc > 0`, swap integration target to `live_alias`.
- [x] **Task 2** — Add 4 synth assertions plus `_synth_with_context()` helper in `tests/test_backend_api_synth.py` (D-14).

## Commits

- `c033836` — `feat(07-02): add live alias + conditional PC in BackendApiConstruct`
- `2883561` — `test(07-02): add D-14 alias + PC synth assertions`

## Key Files

### Created

- None (SUMMARY.md added in a separate metadata commit).

### Modified

- `infrastructure/constructs/backend_api.py` (+33 lines) — `demo_pc` read at construct-level (D-11), int-cast + non-negative validation raising `ValueError` at synth time, `fn.add_alias("live", ...)` always created, `provisioned_concurrent_executions` kwarg attached only when `demo_pc > 0`, `HttpLambdaIntegration` target swapped from `fn` to `live_alias`.
- `tests/test_backend_api_synth.py` (+90 lines) — `_synth_with_context()` helper (module-scope `synth_template` fixture cannot carry per-test context variance), `test_alias_live_exists`, `test_integration_targets_alias`, `test_pc_present_when_demo_pc_set`, `test_pc_absent_when_demo_pc_zero`.

## Must-Haves Verification

| Truth | Status |
|-------|--------|
| A Lambda alias named `live` is always created in the synthesised CloudFormation template, whether or not Provisioned Concurrency is attached | ✓ Verified via `test_alias_live_exists` (PASS with and without `-c demo_pc=1`) |
| The API Gateway v2 `HttpLambdaIntegration` `IntegrationUri` references the `live` alias — never `$LATEST`, never the raw function ARN | ✓ Verified via `test_integration_targets_alias` — integration `IntegrationUri` contains alias logical ID |
| Under `cdk synth -c demo_pc=1`, the alias carries `ProvisionedConcurrencyConfig` with `ProvisionedConcurrentExecutions=1` | ✓ Verified via `test_pc_present_when_demo_pc_set` |
| Under `cdk synth -c demo_pc=0` (or omitted), the alias has NO `ProvisionedConcurrencyConfig` property in the template | ✓ Verified via `test_pc_absent_when_demo_pc_zero` |
| Invalid `-c demo_pc=<garbage>` values (non-numeric, negative) fail at synth time with a readable `ValueError`, not at deploy time | ✓ Verified manually — `int()` cast + non-negative check raise before alias creation |
| `demo_pc` is read at the CONSTRUCT level via `self.node.try_get_context("demo_pc")` — `backend_api_stack.py` stays unchanged (Claude's Discretion per 07-PATTERNS.md) | ✓ `backend_api_stack.py` byte-unchanged; construct reads context |
| No IAM changes — the alias inherits the existing Lambda execution role that grants `bedrock-agentcore:InvokeAgentRuntime` | ✓ No `add_to_role_policy` modifications; alias inherits `fn`'s execution role |

## Test Results

```
tests/test_backend_api_synth.py::test_alias_live_exists PASSED           [ 25%]
tests/test_backend_api_synth.py::test_integration_targets_alias PASSED   [ 50%]
tests/test_backend_api_synth.py::test_pc_present_when_demo_pc_set PASSED [ 75%]
tests/test_backend_api_synth.py::test_pc_absent_when_demo_pc_zero PASSED [100%]
4 passed in 23.95s
```

Full file run: `14 passed, 1 failed` where the single failure (`test_agentcore_stack_has_ssm_parameter`) is **pre-existing on main** — an unrelated `ImportError` from `agent_runtime.py` trying to import `aws_bedrock_agentcore_alpha` (not installed in the local env). Confirmed identical failure on `bb6dd86` baseline before any 07-02 work. Out of scope.

## Deviations from Plan

None. Plan executed exactly as written — no Rule 1/2/3 auto-fixes or Rule 4 architectural decisions required.

## Self-Check: PASSED

- All 4 new synth assertions pass.
- Construct change is additive — no removed exports, no IAM modifications.
- `backend_api_stack.py` byte-unchanged (per Claude's Discretion).
- Alias target is `fn.current_version` (CDK default), so cdk deploy auto-rolls on code changes.
- Stable alias ARN across PC-on/PC-off deploys — Phase 10 freeze-surface safe.

## Recovery Note

This SUMMARY.md was written by the orchestrator after the executor agent stalled post-verification (watchdog triggered after 600s of no stream progress). Both code + test commits (`c033836`, `2883561`) and all verification gates completed before the stall. Recovery was a metadata-only action.
