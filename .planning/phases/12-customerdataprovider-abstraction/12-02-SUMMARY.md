---
phase: 12-customerdataprovider-abstraction
plan: 02
subsystem: tools-lambda
tags: [lambda, dispatcher, cdk, action-routing, D-02, D-05]
requirements_completed: [PROD-01a]
dependency_graph:
  requires:
    - "agent/providers.py::ToolsLambdaProvider (Plan 12-01) sends {action, customer_id} payloads to this dispatcher"
    - "lambda/handler.py pure helpers (simulate_savings_pure Phase 1/11, get_hardship_flag_pure Phase 11 D-10) unchanged, reused"
    - "Existing lambda/handler.py entry points (get_billing_history, simulate_savings) unchanged, reused"
  provides:
    - "lambda/handler.py::handler(event, context) action dispatcher routing on event['action'] (D-02)"
    - "D-05 back-compat: action-less events default to simulate_savings (v2.0 shape)"
    - "CDK Lambda construct entry point = handler.handler (get_hardship_flag + get_customer actions now dispatchable)"
  affects:
    - "infrastructure/constructs/tools_lambda.py handler string change forces a Lambda property diff in cdk synth"
    - "Lambda asset hash: adding handler() function body forces an asset-code diff in cdk synth"
    - "Plan 12-06 (live deploy) reconciles both diffs under the stack-policy lift ceremony"
tech_stack:
  added: []
  patterns:
    - "Action-dispatch handler: single top-level entry point routes on event['action']; unknown/missing action falls through to D-05 back-compat default"
    - "Chesterton's Fence (PITFALLS.md C7): append-only modification, existing pure helpers and entry points byte-unchanged"
    - "Validation-before-dispatch: _validate_customer_id runs in both the get_hardship_flag and get_customer branches before any handler work"
key_files:
  created: []
  modified:
    - "lambda/handler.py: appended top-level handler(event, context) dispatcher at end of file; all pre-existing code byte-unchanged"
    - "infrastructure/constructs/tools_lambda.py: handler string changed from handler.simulate_savings to handler.handler (line 29)"
    - "tests/test_cdk_synth.py: test_has_tools_lambda assertion updated to expect Handler='handler.handler' (Rule 3 auto-fix: test was asserting on the CDK construct's old handler string)"
decisions:
  - "get_customer returns a minimal {customer_id} stub rather than fabricating billing data. Phase 13/14 may extend the shape per CONTEXT Claude's Discretion. Validation still runs (_validate_customer_id) so invalid IDs fail before dispatch."
  - "get_hardship_flag branch raises RuntimeError('TABLE_NAME env var not set') when table is None, matching the pattern at line 174 (get_billing_history). get_customer does NOT check table because it never reads DynamoDB in the Phase 12 stub."
  - "test_cdk_synth.py::test_has_tools_lambda assertion was updated inline with the CDK change (Rule 3: directly caused by this plan's CDK edit). Treated as part of Task 2 rather than a separate deviation because the test's purpose is to lock the CDK construct's handler property to whatever the plan just declared."
metrics:
  duration_minutes: 12
  completed_at: "2026-04-28T21:50:22Z"
  tasks_completed: 2
  files_modified: 3
---

# Phase 12 Plan 02: Tools Lambda Action Dispatcher Summary

Grew `lambda/handler.py` with a top-level `handler(event, context)` action dispatcher routing on `event["action"]`, and updated the CDK Tools Lambda construct entry point to `handler.handler` so Phase 12's `ToolsLambdaProvider` (Plan 12-01) can address `get_billing_history`, `get_hardship_flag`, `get_customer`, and `simulate_savings` through a single Lambda, without disturbing any pure helper (SAV-03 byte-exact math) or existing entry-point body.

## What Shipped

### Task 1: action dispatcher in `lambda/handler.py` (commit `b30ce54`)

Appended a new top-level function at the end of the file (after `simulate_savings`):

```python
def handler(event, context):
    action = event.get("action")
    if action == "get_billing_history":
        return get_billing_history(event, context)
    if action == "get_hardship_flag":
        customer_id = _validate_customer_id(event.get("customer_id"))
        if table is None:
            raise RuntimeError("TABLE_NAME env var not set - Lambda misconfigured")
        return get_hardship_flag_pure(customer_id, table)
    if action == "get_customer":
        customer_id = _validate_customer_id(event.get("customer_id"))
        return {"customer_id": customer_id}
    if action == "simulate_savings":
        return simulate_savings(event, context)
    # D-05 back-compat: action-less event -> simulate_savings (v2.0 shape).
    return simulate_savings(event, context)
```

### Task 2: CDK entry-point string (commit `bdf438a`)

Single-line change in `infrastructure/constructs/tools_lambda.py`:

```diff
-            handler="handler.simulate_savings",
+            handler="handler.handler",
```

All other Lambda properties (runtime, function_name, code asset, environment, timeout, memory_size) preserved byte-for-byte. Also updated `tests/test_cdk_synth.py::test_has_tools_lambda` assertion to match, directly caused by the CDK edit (Rule 3 auto-fix, treated as part of Task 2 because the test's purpose is to lock the construct's handler property).

## Dispatcher Action Routing Table

| event["action"]         | Branch body                                                                  | DynamoDB?                              | Returns                                    |
| ----------------------- | ---------------------------------------------------------------------------- | -------------------------------------- | ------------------------------------------ |
| `"get_billing_history"` | `get_billing_history(event, context)`                                        | yes (query)                            | `List[Dict]` — 12 months, PROFILE filtered |
| `"get_hardship_flag"`   | `_validate_customer_id(...)` + `get_hardship_flag_pure(customer_id, table)`  | yes (GetItem PROFILE)                  | `{"hardship": bool, "customer_id": str}`   |
| `"get_customer"`        | `_validate_customer_id(...)` + literal `{"customer_id": customer_id}`        | no (stub)                              | `{"customer_id": str}`                     |
| `"simulate_savings"`    | `simulate_savings(event, context)`                                           | yes (indirect via get_billing_history) | `{"green": {...}, "cheapest": {...}}`      |
| (none) / unknown        | `simulate_savings(event, context)` (D-05 back-compat default)                | yes (indirect)                         | `{"green": {...}, "cheapest": {...}}`      |

## Chesterton's-Fence Verification (PITFALLS.md C7)

The following are byte-identical pre/post-plan, confirmed by git diff:

- `simulate_savings_pure` body: byte-unchanged.
- `get_hardship_flag_pure` body: byte-unchanged.
- `_validate_customer_id`: byte-unchanged; reused by the dispatcher.
- `TARIFF_PLANS` / `table` module-level init: byte-unchanged.
- `get_billing_history(event, context)` entry point: byte-unchanged; retained for back-compat and also called by the dispatcher.
- `simulate_savings(event, context)` entry point: byte-unchanged; retained for back-compat and called by the dispatcher in two branches.

No pure helper was touched. No existing entry-point body was touched. The dispatcher is purely additive.

## Verification Results

### Task 1 acceptance gates

- `grep -q "^def handler(event" lambda/handler.py` — pass
- `grep -c "event\.get(.action.)" lambda/handler.py` — 1 (≥1 required)
- All four action string literals present (`get_billing_history`, `get_hardship_flag`, `get_customer`, `simulate_savings`) — pass
- `grep -q "D-05 back-compat\|action-less event" lambda/handler.py` — pass
- Existing function-definition counts unchanged: 1x `simulate_savings_pure`, 1x `get_hardship_flag_pure`, 1x `get_billing_history`, 1x `simulate_savings` (non-pure) — pass
- Inline dispatcher gate (`get_customer` routing + bogus-id ValueError) — OK
- `pytest tests/test_simulate_savings.py tests/test_get_hardship_flag_pure.py tests/test_get_billing_history.py` — 37 passed

### Task 2 acceptance gates

- `grep -q 'handler="handler.handler"' infrastructure/constructs/tools_lambda.py` — pass
- `! grep -q 'handler="handler.simulate_savings"' infrastructure/constructs/tools_lambda.py` — pass
- All other construct properties preserved — pass
- `pytest tests/test_cdk_synth.py` — 8 passed

### Plan-level verification block (all gates green)

- `pytest tests/test_simulate_savings.py tests/test_get_hardship_flag_pure.py tests/test_get_billing_history.py tests/test_cdk_synth.py` — 45 passed in 10.73s
- Ad-hoc dispatcher routing test — OK
- Ad-hoc back-compat callability test — OK

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking test] Updated `tests/test_cdk_synth.py::test_has_tools_lambda` assertion to match new handler string**

- **Found during:** Task 2
- **Issue:** The CDK synth test asserted `"Handler": "handler.simulate_savings"`. Once the construct switched to `handler.handler`, the test naturally failed.
- **Fix:** Updated the assertion to `"Handler": "handler.handler"` with a comment tying the change to Phase 12 D-02.
- **Files modified:** `tests/test_cdk_synth.py`
- **Commit:** `bdf438a` (bundled with the CDK construct change)
- **Why auto-fix was correct:** Directly caused by this plan's explicit CDK edit. The test's purpose is to lock the CDK construct's handler property to whatever the plan just declared.

## Deferred / Out-of-Scope (logged only)

**`tests/test_frontend_synth.py` pre-existing failures (33 errors + 4 failed)**

Observed during a full offline regression `pytest -m "not smoke"`. All failures live in `TestSpaRedirectRulePresence` and `TestStaticPlatformConfiguration` under `tests/test_frontend_synth.py`, tied to `infrastructure/frontend_stack.py` (CustomerTariffFrontend Amplify), which Plan 12-02 does not touch. Per SCOPE BOUNDARY rule: not fixed, not in Plan 12-02 scope, logged here.

## CDK Diff Preview Expectation for Plan 12-06

When `cdk synth CustomerTariff` runs in Plan 12-06 against the deployed v2.0 frozen stack, expect two diffs on the `tariff-tools` Lambda resource:

1. **Handler property diff:** `"Handler": "handler.simulate_savings"` → `"Handler": "handler.handler"`.
2. **Asset code diff:** The Lambda asset bundle's content hash changes because `lambda/handler.py` now contains the appended `handler(event, context)` function body.

Both diffs will be picked up by Plan 12-06's stack-policy lift ceremony.

## Self-Check: PASSED

- [x] `lambda/handler.py` modified: `def handler(event, context)` present at end of file
- [x] `infrastructure/constructs/tools_lambda.py` modified: `handler="handler.handler"` present
- [x] `tests/test_cdk_synth.py` assertion updated: `"Handler": "handler.handler"` present
- [x] Commit `b30ce54` (Task 1) present
- [x] Commit `bdf438a` (Task 2) present
- [x] 45 success-criteria tests passing
