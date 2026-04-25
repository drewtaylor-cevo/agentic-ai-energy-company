---
phase: 01-foundation-dummy-data
reviewed: 2026-04-23T00:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - lambda/handler.py
  - infrastructure/seed_data/billing_records.py
  - infrastructure/constructs/billing_table.py
  - infrastructure/constructs/tools_lambda.py
  - infrastructure/constructs/seeder.py
  - infrastructure/foundation_stack.py
  - app.py
  - tests/conftest.py
  - tests/test_simulate_savings.py
  - tests/test_get_billing_history.py
  - tests/test_schema.py
  - tests/test_cdk_synth.py
  - tests/test_seeder_smoke.py
findings:
  critical: 0
  warning: 4
  info: 5
  total: 9
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-23
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Reviewed the Phase 1 foundation: Lambda handler with two entry points, DynamoDB billing table CDK construct, AwsCustomResource seeder, CDK stack wiring, and the full pytest suite. The overall structure is solid — input validation is correctly applied before DynamoDB access, the savings arithmetic is deterministic and well-tested, the seeder IAM is correctly scoped to `dynamodb:BatchWriteItem` on a specific table ARN, and the CDK synth tests provide good infrastructure regression coverage.

Four warnings were found: IAM over-privilege on the tools Lambda (Scan granted when only Query is used), silent data truncation risk from an unhandled DynamoDB pagination boundary, stale docstring savings figures that could mislead future developers, and a fragile smoke test skip condition that fails non-cleanly for developers with a region env var but invalid credentials.

No critical security vulnerabilities were found.

---

## Warnings

### WR-01: Lambda IAM grants Scan and DescribeTable — only Query is needed

**File:** `infrastructure/constructs/tools_lambda.py:36`

**Issue:** `table.grant_read_data(self.function)` grants the Lambda seven permissions: `BatchGetItem`, `GetRecords`, `GetShardIterator`, `Query`, `GetItem`, `Scan`, and `DescribeTable`. The Lambda only calls `table.query(...)` (handler.py:132). Granting `Scan` is an IAM over-privilege violation: any compromise of this Lambda or its execution role allows a full table dump. The docstring comment on line 5 acknowledges Scan is included but does not flag it as a concern.

**Fix:** Replace `grant_read_data` with a scoped policy statement granting only `dynamodb:Query` on this table ARN:

```python
from aws_cdk import aws_iam as iam

self.function.add_to_role_policy(
    iam.PolicyStatement(
        actions=["dynamodb:Query"],
        resources=[table.table_arn],
    )
)
```

If `GetItem` is needed in Phase 2, add it explicitly rather than reinstating `grant_read_data`.

---

### WR-02: DynamoDB Query result is not paginated — silent truncation if result exceeds 1 MB

**File:** `lambda/handler.py:132-137`

**Issue:** `table.query(...)` returns at most 1 MB of data per call. If `LastEvaluatedKey` is present in the response, there are more pages. The current code calls `.get("Items", [])` directly and discards any continuation token. For the demo's 12 records per customer (~1.2 KB total) this never triggers, but the code has no guard against it. If a real deployment adds more records, the handler silently returns a partial result and the savings calculation runs on incomplete history without any error signal.

**Fix:** Add a pagination loop:

```python
items = []
kwargs = {
    "KeyConditionExpression": "customer_id = :cid",
    "ExpressionAttributeValues": {":cid": customer_id},
}
while True:
    response = table.query(**kwargs)
    items.extend(response.get("Items", []))
    last_key = response.get("LastEvaluatedKey")
    if not last_key:
        break
    kwargs["ExclusiveStartKey"] = last_key
return sorted(items, key=lambda x: x["month"])
```

---

### WR-03: Docstring savings figures in billing_records.py are incorrect

**File:** `infrastructure/seed_data/billing_records.py:6-7`

**Issue:** The module docstring states:

```
- Marcus Webb (CUST-002): avg 282 kWh -> Green $16.92/mo, Cheapest $31.02/mo
- Elena Vasquez (CUST-003): avg 233 kWh -> Green $13.98/mo, Cheapest $25.63/mo
```

The actual computed values (using `DAYS_PER_MONTH = 30.44` and the plan rates in `tariff_plans.json`) are:

- Marcus: avg 281.67 kWh, Green **$16.90**/mo, Cheapest **$30.98**/mo
- Elena: avg 233.33 kWh, Green **$14.00**/mo, Cheapest **$25.67**/mo

The test tolerance in `test_simulate_savings.py` is ±$0.10, so the tests pass, but the docstring would mislead a developer cross-checking numbers manually. The figures appear to have been computed with a rounded average (e.g., 282 kWh) rather than the true mean of the usage array.

**Fix:** Update the docstring to reflect the values the code actually produces:

```python
"""
- Marcus Webb (CUST-002): avg 281.67 kWh -> Green $16.90/mo, Cheapest $30.98/mo
- Elena Vasquez (CUST-003): avg 233.33 kWh -> Green $14.00/mo, Cheapest $25.67/mo
"""
```

---

### WR-04: Smoke test skip condition does not detect missing credentials — fails with boto3 exception instead of a clean skip

**File:** `tests/test_seeder_smoke.py:12-16`

**Issue:** The `pytestmark` skip condition only checks whether `AWS_DEFAULT_REGION` is set in the environment:

```python
pytestmark = pytest.mark.skipif(
    not os.environ.get("AWS_DEFAULT_REGION")
    or os.environ.get("SKIP_AWS_SMOKE") == "1",
    reason="...",
)
```

A developer who has `AWS_DEFAULT_REGION` set in their shell profile (common for general AWS development) but has no valid credentials for this account will not be skipped. The tests will run and fail with `botocore.exceptions.NoCredentialsError` or `ClientError`, producing confusing output rather than a clean skip message.

**Fix:** Add a credential pre-check in the `dynamodb_client` fixture (which already uses `pytest.importorskip`), or add a session-level autouse fixture that skips the whole module if `boto3.Session().get_credentials()` returns `None`:

```python
@pytest.fixture(scope="module", autouse=True)
def require_aws_credentials():
    boto3 = pytest.importorskip("boto3")
    creds = boto3.Session().get_credentials()
    if creds is None:
        pytest.skip("No AWS credentials available")
```

---

## Info

### IN-01: Unhandled exception propagation — Lambda returns FunctionError instead of structured JSON

**File:** `lambda/handler.py:123-145`

**Issue:** Both `get_billing_history` and `simulate_savings` raise `ValueError` and `RuntimeError` directly. When a Lambda handler raises an unhandled exception, the AWS Lambda service wraps it in a `FunctionError` response. Callers (and the future Bedrock AgentCore agent) must handle both a structured JSON response and an opaque error envelope. The smoke test at `test_seeder_smoke.py:76` checks `assert "FunctionError" not in resp` but does not verify a structured error body.

This is not a bug today (Phase 2 will define the agent tool contract), but the error surface should be considered before Phase 2 integration.

**Suggestion:** Wrap handler bodies in try/except and return a structured error dict, or document the expected error contract for Phase 2 tool wrappers.

---

### IN-02: Missing avg-value assertions for Marcus and Elena in billing_records.py

**File:** `infrastructure/seed_data/billing_records.py:94-99`

**Issue:** The module-level assertions verify record counts and Sarah's exact average (`sum(_SARAH_USAGE) / 12 == 500.0`), but Marcus and Elena have no equivalent numerical assertion. Because their averages are not whole numbers (`281.666...` and `233.333...`), an exact float comparison is not possible, but an approximate check would still catch accidental edits to the usage arrays.

**Suggestion:** Add approximate assertions to fail fast if usage arrays are accidentally modified:

```python
assert abs(sum(_MARCUS_USAGE) / 12 - 281.667) < 0.01, "Marcus avg must be ~281.667 kWh"
assert abs(sum(_ELENA_USAGE) / 12 - 233.333) < 0.01, "Elena avg must be ~233.333 kWh"
```

---

### IN-03: test_simulate_savings.py imports lambda.handler at module level — creates implicit test ordering dependency

**File:** `tests/test_simulate_savings.py:13`

**Issue:** `handler = importlib.import_module("lambda.handler")` runs at collection time (module level). If `test_get_billing_history.py` is collected first and its `handler_module` fixture has already loaded the module with `TABLE_NAME` set, then `test_simulate_savings.py` receives the cached version from `sys.modules` — which includes a live `boto3.Table` reference. The pure-function tests (`simulate_savings_pure`) are unaffected because they never access `handler.table`, but the implicit dependency on collection order is a maintenance hazard.

**Suggestion:** Move the import inside a `@pytest.fixture` or into each test function so import state is explicit:

```python
@pytest.fixture
def simulate_savings_pure():
    handler = importlib.import_module("lambda.handler")
    return handler.simulate_savings_pure
```

---

### IN-04: handler_module fixture does not clean up sys.modules on teardown

**File:** `tests/test_get_billing_history.py:9-15`

**Issue:** The `handler_module` fixture deletes `sys.modules["lambda.handler"]` before importing (to force a fresh module with `TABLE_NAME` set), but does not restore `sys.modules` after the test. `monkeypatch` restores the env var, but the loaded module object — including its `table` attribute bound to a `boto3.Table` — stays in `sys.modules` until the next test that explicitly deletes it. This is safe today because every fixture and test that cares about the module state re-deletes it, but adding a new test file that does `from lambda.handler import table` without the delete step would silently get the contaminated module.

**Suggestion:** Add an explicit cleanup yield in the fixture:

```python
@pytest.fixture
def handler_module(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "tariff-billing-test")
    sys.modules.pop("lambda.handler", None)
    mod = importlib.import_module("lambda.handler")
    yield mod
    sys.modules.pop("lambda.handler", None)
```

---

### IN-05: Only simulate_savings is registered as the Lambda handler — get_billing_history is not independently invocable

**File:** `infrastructure/constructs/tools_lambda.py:29`

**Issue:** The CDK construct registers `handler="handler.simulate_savings"` as the single Lambda entry point. `get_billing_history` is only callable indirectly through `simulate_savings`. If Phase 2 needs to expose `get_billing_history` as a separate Bedrock tool (to allow an agent to fetch raw billing data without computing savings), the current single-handler setup requires a second Lambda or a dispatch layer. This is a design note for Phase 2 planning, not a current defect.

**Suggestion:** Either document this design decision explicitly in the construct docstring, or consider a dispatcher pattern (`event["tool"]` routing) now before Phase 2 integration adds complexity.

---

_Reviewed: 2026-04-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
