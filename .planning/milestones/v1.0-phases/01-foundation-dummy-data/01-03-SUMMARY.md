---
phase: 01-foundation-dummy-data
plan: 03
subsystem: infrastructure/cdk
status: checkpoint-pending
tags:
  - cdk
  - dynamodb
  - lambda
  - seeder
  - infrastructure
dependency_graph:
  requires:
    - 01-01 (billing_records.DYNAMO_RECORDS, tariff_plans.json, app.py scaffold)
    - 01-02 (lambda/handler.py with simulate_savings + get_billing_history)
  provides:
    - infrastructure/constructs/billing_table.py (BillingTableConstruct)
    - infrastructure/constructs/tools_lambda.py (ToolsLambdaConstruct)
    - infrastructure/constructs/seeder.py (SeederConstruct)
    - infrastructure/foundation_stack.py (FoundationStack)
    - app.py (updated — FoundationStack uncommented, region=us-east-1)
    - tests/test_cdk_synth.py (8 offline synth tests)
    - tests/test_seeder_smoke.py (6 post-deploy smoke tests)
  affects:
    - Phase 2 (AgentCore Agent): CDK stack must be deployed before agent wiring begins
tech_stack:
  added:
    - aws-cdk-lib>=2.250.0 (already in requirements.txt — constructs now used)
    - aws_cdk.assertions (Template.from_stack for offline synth tests)
  patterns:
    - CDK Construct pattern (one class per file, self.table / self.function attributes)
    - AwsCustomResource for one-shot seeding (on_create only, BatchWriteItem)
    - Template.from_stack offline synthesis for infrastructure contract tests
    - custom_resources (not aws_custom_resources) — CDK v2 module naming
key_files:
  created:
    - infrastructure/constructs/billing_table.py
    - infrastructure/constructs/tools_lambda.py
    - infrastructure/constructs/seeder.py
    - infrastructure/foundation_stack.py
    - tests/test_cdk_synth.py
    - tests/test_seeder_smoke.py
  modified:
    - app.py (uncommented FoundationStack block, removed placeholder comments)
decisions:
  - "custom_resources not aws_custom_resources: CDK v2 exposes the AwsCustomResource construct at aws_cdk.custom_resources, not aws_cdk.aws_custom_resources — plan had wrong module name; corrected on import"
  - "on_create only in SeederConstruct: no on_update or on_delete to prevent re-seeding on every cdk deploy"
  - "IAM scoped to dynamodb:BatchWriteItem on table.table_arn (no wildcards) — T-01-03-01 mitigated"
  - "Lambda grant_read_data (not grant_read_write_data) — T-01-03-02 mitigated"
  - "Region hardcoded to us-east-1 in app.py — T-01-03-04 mitigated"
metrics:
  duration: "14m"
  completed: "2026-04-23 (checkpoint pending — awaiting human deploy)"
  tasks_completed: 2
  tasks_pending: 1
  files_created: 6
  files_modified: 1
---

# Phase 1 Plan 3: CDK Stack — BillingTable, ToolsLambda, Seeder Summary

**One-liner:** Python CDK v2 stack synthesizing DynamoDB table + Python 3.12 Lambda + 2-batch AwsCustomResource seeder; 8 offline synth tests pass; deploy awaiting human AWS credentials.

## Status: CHECKPOINT PENDING

Task 3 (human-verify deploy) is blocked on human action. Tasks 1 and 2 are fully complete and committed. The checkpoint details are returned in the executor message.

## What Was Built

### Task 1: CDK Constructs (commit 623ff35)

Three CDK construct files, one per AWS resource:

**`infrastructure/constructs/billing_table.py`** — `BillingTableConstruct`
- DynamoDB table `tariff-billing`, partition key `customer_id` (S), sort key `month` (S)
- `PAY_PER_REQUEST` billing mode, `RemovalPolicy.DESTROY`, no GSI

**`infrastructure/constructs/tools_lambda.py`** — `ToolsLambdaConstruct`
- Lambda function `tariff-tools`, `Runtime.PYTHON_3_12`
- `Code.from_asset("lambda")` bundles handler.py + tariff_plans.json
- `table.grant_read_data(self.function)` — read-only IAM, no wildcards

**`infrastructure/constructs/seeder.py`** — `SeederConstruct`
- Reads `DYNAMO_RECORDS` (36 items) from `billing_records.py`
- `math.ceil(36 / 25) = 2` batches: BillingSeeder0 (25 items) + BillingSeeder1 (11 items)
- `on_create` only — no `on_update` or `on_delete` to prevent re-seeding
- IAM: `dynamodb:BatchWriteItem` on `table.table_arn` only

### Task 2: FoundationStack + app.py + Synth Tests (commit d2b716b)

**`infrastructure/foundation_stack.py`** — `FoundationStack(Stack)`
- Wires `BillingTableConstruct`, `ToolsLambdaConstruct`, `SeederConstruct`
- 4 `CfnOutput` values: BillingTableName, BillingTableArn, ToolsLambdaName, ToolsLambdaArn

**`app.py`** (updated)
- `FoundationStack` import active (previously commented out)
- `env=cdk.Environment(region="us-east-1")` hardcoded
- `description="Phase 1: Foundation + Dummy Data"`

**`tests/test_cdk_synth.py`** — 8 offline CDK synth tests (all pass, no AWS creds needed):

| Test | What it asserts |
|------|----------------|
| test_has_one_dynamodb_table | 1 DynamoDB table in template |
| test_table_has_composite_key | customer_id HASH + month RANGE |
| test_table_billing_mode_is_on_demand | BillingMode: PAY_PER_REQUEST |
| test_table_removal_policy_is_destroy | DeletionPolicy: Delete |
| test_has_tools_lambda | tariff-tools, python3.12, handler.simulate_savings |
| test_lambda_has_table_name_env | TABLE_NAME env var present |
| test_seeder_creates_two_batches | Custom::AWS count == 2 |
| test_seeder_iam_scoped_to_batchwriteitem | BatchWriteItem, no wildcard |

**Full suite: 37/37 tests pass** (29 from Plan 02 + 8 synth)

### Task 3: Smoke Test File Created (commit 3614495)

**`tests/test_seeder_smoke.py`** — 6 post-deploy smoke tests with skip guard:
- Skips when `AWS_DEFAULT_REGION` unset or `SKIP_AWS_SMOKE=1`
- `test_table_exists` — describe_table returns ACTIVE
- `test_table_has_36_items` — scan COUNT == 36
- `test_sarah_has_12_months` — CUST-001 query returns 12 items
- `test_marcus_has_12_months` — CUST-002 query returns 12 items
- `test_elena_has_12_months` — CUST-003 query returns 12 items
- `test_lambda_invokes_sarah_savings_match_demo02` — Green=$30 (ECO), Cheapest=$55 (VAL)

**Deploy itself is awaiting human action** (requires AWS credentials + account confirmation).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed aws_custom_resources import path**
- **Found during:** Task 1 verification
- **Issue:** Plan specified `from aws_cdk import aws_custom_resources as cr` but CDK v2 (aws-cdk-lib 2.250.0) exposes this module as `aws_cdk.custom_resources`, not `aws_cdk.aws_custom_resources`. The import would fail at runtime and also at synth time.
- **Fix:** Changed to `from aws_cdk import custom_resources as cr` — all `cr.AwsCustomResource`, `cr.AwsSdkCall`, `cr.PhysicalResourceId`, `cr.AwsCustomResourcePolicy` references remain identical.
- **Files modified:** `infrastructure/constructs/seeder.py`
- **Commit:** 623ff35

## Known Stubs

None — all wiring is complete for Tasks 1 and 2. Task 3 (deploy verification) is pending human action, not a code stub.

## Threat Surface Scan

All T-01-03-xx mitigations implemented as planned:
- **T-01-03-01** (SeederConstruct IAM): `from_statements` with `BatchWriteItem` on `table.table_arn` — asserted by `test_seeder_iam_scoped_to_batchwriteitem`
- **T-01-03-02** (ToolsLambda IAM): `grant_read_data` — CDK emits read-only actions on specific table ARN
- **T-01-03-04** (wrong region): `region="us-east-1"` hardcoded in app.py — asserted by `test_cdk_synth` fixture setup

No new unplanned security surface introduced.

## Post-Deploy Phase 1 Gate (pending)

| Gate | Criterion | Status |
|------|-----------|--------|
| DATA-01 | 12 months billing per customer in DynamoDB | Pending deploy |
| DATA-02 | Schema correct (customer_id, month, usage_kwh, cost_usd, plan_id) | Pending deploy |
| DEMO-02 | Lambda returns Green=$30, Cheapest=$55 for Sarah Chen | Pending deploy |
| Synth | CDK template passes 8 offline assertions | PASSED |

## Self-Check: PASSED (pre-deploy)

- `infrastructure/constructs/billing_table.py` confirmed present
- `infrastructure/constructs/tools_lambda.py` confirmed present
- `infrastructure/constructs/seeder.py` confirmed present
- `infrastructure/foundation_stack.py` confirmed present
- `tests/test_cdk_synth.py` confirmed present (8 tests pass)
- `tests/test_seeder_smoke.py` confirmed present (6 tests skip without AWS creds)
- `app.py` confirmed updated (FoundationStack active, region=us-east-1)
- Commits 623ff35, d2b716b, 3614495 verified in git log
