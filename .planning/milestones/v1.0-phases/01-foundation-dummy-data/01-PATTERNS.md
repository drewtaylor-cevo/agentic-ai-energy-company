# Phase 1: Foundation + Dummy Data - Pattern Map

**Mapped:** 2026-04-23
**Files analyzed:** 12 (new files — all greenfield)
**Analogs found:** 0 / 12 — confirmed greenfield, no existing source code

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `app.py` | config | request-response | Greenfield — no analog | none |
| `cdk.json` | config | — | Greenfield — no analog | none |
| `requirements.txt` | config | — | Greenfield — no analog | none |
| `requirements-dev.txt` | config | — | Greenfield — no analog | none |
| `infrastructure/foundation_stack.py` | infrastructure / CDK stack | batch | Greenfield — no analog | none |
| `infrastructure/constructs/billing_table.py` | infrastructure / CDK construct | CRUD | Greenfield — no analog | none |
| `infrastructure/constructs/tools_lambda.py` | infrastructure / CDK construct | request-response | Greenfield — no analog | none |
| `infrastructure/constructs/seeder.py` | infrastructure / CDK construct | batch | Greenfield — no analog | none |
| `infrastructure/seed_data/billing_records.py` | utility / data | batch | Greenfield — no analog | none |
| `lambda/tariff_plans.json` | config / data | — | Greenfield — no analog | none |
| `lambda/handler.py` | service | CRUD + request-response | Greenfield — no analog | none |
| `tests/test_simulate_savings.py` | test | transform | Greenfield — no analog | none |
| `tests/conftest.py` | test | — | Greenfield — no analog | none |
| `tests/test_get_billing_history.py` | test | CRUD | Greenfield — no analog | none |
| `tests/test_schema.py` | test | transform | Greenfield — no analog | none |
| `tests/test_seeder_smoke.py` | test | batch | Greenfield — no analog | none |
| `pytest.ini` | config | — | Greenfield — no analog | none |

---

## Pattern Assignments

All patterns sourced from `01-RESEARCH.md` (verified against official CDK and AWS docs). No codebase analogs exist — planner must use these research-derived patterns directly.

---

### `app.py` (config, CDK entry point)

**Analog:** Greenfield — no analog
**Source:** RESEARCH.md §Code Examples / app.py Entry Point

**Core pattern:**
```python
#!/usr/bin/env python3
import aws_cdk as cdk
from infrastructure.foundation_stack import FoundationStack

app = cdk.App()
FoundationStack(app, "CustomerTariff",
    env=cdk.Environment(region="us-east-1"),
    description="Phase 1: Foundation + Dummy Data"
)
app.synth()
```

**Critical:** `region="us-east-1"` must be hardcoded. The local AWS profile defaults to `ap-southeast-2`, which does NOT support AgentCore Agent Registry (required for Phase 2+). Never rely on environment default.

---

### `infrastructure/foundation_stack.py` (CDK stack, batch)

**Analog:** Greenfield — no analog
**Source:** RESEARCH.md §Code Examples / CDK Stack Structure

**Imports pattern:**
```python
import aws_cdk as cdk
from aws_cdk import Stack
from constructs import Construct
from infrastructure.constructs.billing_table import BillingTableConstruct
from infrastructure.constructs.tools_lambda import ToolsLambdaConstruct
from infrastructure.constructs.seeder import SeederConstruct
```

**Core pattern — stack wires three constructs together:**
```python
class FoundationStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        billing = BillingTableConstruct(self, "BillingTable")
        tools = ToolsLambdaConstruct(self, "ToolsLambda",
            table=billing.table)
        seeder = SeederConstruct(self, "Seeder",
            table=billing.table)
```

**Rule:** Stack only wires constructs together — no resource definitions inline. All resource logic belongs in construct classes under `infrastructure/constructs/`.

---

### `infrastructure/constructs/billing_table.py` (CDK construct, CRUD)

**Analog:** Greenfield — no analog
**Source:** RESEARCH.md §Architecture Patterns / Pattern 1: DynamoDB Single-Table Billing Records

**Imports pattern:**
```python
from aws_cdk import aws_dynamodb as dynamodb, RemovalPolicy
from constructs import Construct
```

**Core pattern — DynamoDB table with composite key:**
```python
table = dynamodb.Table(
    self, "TariffBillingTable",
    table_name="tariff-billing",
    partition_key=dynamodb.Attribute(
        name="customer_id",
        type=dynamodb.AttributeType.STRING
    ),
    sort_key=dynamodb.Attribute(
        name="month",
        type=dynamodb.AttributeType.STRING
    ),
    billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
    removal_policy=RemovalPolicy.DESTROY,  # demo stack — clean up on cdk destroy
)
```

**Rules:**
- `PAY_PER_REQUEST` not `PROVISIONED` — no capacity planning needed for demo
- `DESTROY` not `RETAIN` — demo stacks must clean up completely on `cdk destroy`
- No GSI required — the only access pattern is `PK = "CUST-XXX"` which returns all 12 SK values

**DynamoDB item schema:**
```json
{
    "customer_id": "CUST-001",
    "month": "2025-04",
    "usage_kwh": 425,
    "cost_usd": 169.48,
    "plan_id": "STD"
}
```

---

### `infrastructure/constructs/tools_lambda.py` (CDK construct, request-response)

**Analog:** Greenfield — no analog
**Source:** RESEARCH.md §Architecture Patterns / Pattern 3: Lambda with Bundled JSON Data File

**Imports pattern:**
```python
from aws_cdk import aws_lambda as lambda_
from constructs import Construct
```

**Core pattern — Lambda with bundled JSON asset:**
```python
tools_fn = lambda_.Function(
    self, "TariffTools",
    runtime=lambda_.Runtime.PYTHON_3_12,
    handler="handler.get_billing_history",
    code=lambda_.Code.from_asset("lambda"),  # zips entire lambda/ dir, includes tariff_plans.json
    environment={"TABLE_NAME": table.table_name},
)
table.grant_read_data(tools_fn)
```

**Rules:**
- `Code.from_asset("lambda")` bundles the entire `lambda/` directory — `tariff_plans.json` is included automatically
- `table.grant_read_data(fn)` is the CDK method for scoped read-only IAM grant — do NOT use `*` actions
- Always pass `TABLE_NAME` as environment variable, never hardcode table names or ARNs

---

### `infrastructure/constructs/seeder.py` (CDK construct, batch)

**Analog:** Greenfield — no analog
**Source:** RESEARCH.md §Architecture Patterns / Pattern 2: CDK Custom Resource for One-Command Seeding

**Imports pattern:**
```python
import math
from aws_cdk import aws_custom_resources as cr, aws_iam as iam
from constructs import Construct
```

**Core pattern — AwsCustomResource batched seeder:**
```python
def seed_table(self, table, records):
    """Create AwsCustomResource instances to seed DynamoDB in batches of 25."""
    batch_size = 25
    num_batches = math.ceil(len(records) / batch_size)

    for i in range(num_batches):
        batch = records[i * batch_size : (i + 1) * batch_size]
        request_items = [
            {"PutRequest": {"Item": record}} for record in batch
        ]
        cr.AwsCustomResource(
            self, f"BillingSeeder{i}",
            on_create=cr.AwsSdkCall(
                service="DynamoDB",
                action="batchWriteItem",
                parameters={
                    "RequestItems": {table.table_name: request_items}
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    f"BillingSeeder{i}"
                ),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["dynamodb:BatchWriteItem"],
                    resources=[table.table_arn],
                )
            ]),
        )
```

**Critical rules:**
- Use `on_create` ONLY — never `on_update`. `on_update` re-runs on every `cdk deploy`, overwriting data.
- BatchWriteItem maximum is 25 items per call — 36 records (3 personas × 12 months) requires 2 batches.
- IAM policy scoped to `table.table_arn` and `dynamodb:BatchWriteItem` only — no wildcards.
- To force a re-seed, change the `physical_resource_id` string to trigger CloudFormation replacement.

---

### `infrastructure/seed_data/billing_records.py` (utility / data, batch)

**Analog:** Greenfield — no analog
**Source:** RESEARCH.md §Common Pitfalls / Pitfall 1: DynamoDB Wire Format + §Engineered Dummy Data

**Wire format helper — DynamoDB `batchWriteItem` requires wire format, not Python types:**
```python
def to_dynamo(record):
    return {
        "customer_id": {"S": record["customer_id"]},
        "month": {"S": record["month"]},
        "usage_kwh": {"N": str(record["usage_kwh"])},
        "cost_usd": {"N": str(record["cost_usd"])},
        "plan_id": {"S": record["plan_id"]},
    }
```

**Core pattern — persona records list (Python source-of-truth):**
```python
# Define in Python dict format, convert to wire format for seeder
SARAH_CHEN_RECORDS = [
    # Apr=425 May=400 Jun=450 Jul=500 Aug=550 Sep=600
    # Oct=625 Nov=600 Dec=550 Jan=475 Feb=450 Mar=375
    # avg = 500 kWh/month → Green saving = $30.00, Cheapest = $55.00
    {"customer_id": "CUST-001", "month": "2025-04", "usage_kwh": 425,
     "cost_usd": round(425 * 0.32 + 1.10 * 30.44, 2), "plan_id": "STD"},
    # ... 11 more months
]

MARCUS_WEBB_RECORDS = [
    # avg = 282 kWh/month → Green saving = $16.92, Cheapest = $31.02
    {"customer_id": "CUST-002", "month": "2025-04", "usage_kwh": 250,
     "cost_usd": round(250 * 0.32 + 1.10 * 30.44, 2), "plan_id": "STD"},
    # ... 11 more months
]

ELENA_VASQUEZ_RECORDS = [
    # avg = 233 kWh/month → Green saving = $13.98, Cheapest = $25.63
    {"customer_id": "CUST-003", "month": "2025-04", "usage_kwh": 110,
     "cost_usd": round(110 * 0.32 + 1.10 * 30.44, 2), "plan_id": "STD"},
    # ... 11 more months
]

ALL_RECORDS = SARAH_CHEN_RECORDS + MARCUS_WEBB_RECORDS + ELENA_VASQUEZ_RECORDS
DYNAMO_RECORDS = [to_dynamo(r) for r in ALL_RECORDS]  # 36 items in wire format
```

**Critical:** `cost_usd` must be computed as `usage_kwh * 0.32 + 1.10 * 30.44` at definition time, not stored as a literal. This ensures consistency. Savings calculations in the Lambda always use `usage_kwh`, never `cost_usd`.

**Monthly usage values (from RESEARCH.md §Engineered Dummy Data):**
- Sarah Chen (CUST-001): Apr=425, May=400, Jun=450, Jul=500, Aug=550, Sep=600, Oct=625, Nov=600, Dec=550, Jan=475, Feb=450, Mar=375
- Marcus Webb (CUST-002): Apr=250, May=235, Jun=265, Jul=280, Aug=300, Sep=320, Oct=340, Nov=325, Dec=305, Jan=275, Feb=255, Mar=230
- Elena Vasquez (CUST-003): Apr=110, May=95, Jun=130, Jul=160, Aug=290, Sep=380, Oct=420, Nov=395, Dec=310, Jan=230, Feb=155, Mar=125

---

### `lambda/tariff_plans.json` (config / data, static)

**Analog:** Greenfield — no analog
**Source:** RESEARCH.md §Engineered Dummy Data / Tariff Plans

**Complete schema (rates verified by calculation — do not change without re-running savings formula):**
```json
[
  {
    "plan_id": "STD",
    "plan_name": "Standard Rate",
    "rate_per_kwh": 0.32,
    "daily_supply_charge": 1.10,
    "green_score": 0,
    "plan_type": "flat_rate",
    "renewable_pct": 0,
    "description": "Standard variable rate. No fixed term."
  },
  {
    "plan_id": "ECO",
    "plan_name": "EcoFlex 100",
    "rate_per_kwh": 0.26,
    "daily_supply_charge": 1.10,
    "green_score": 100,
    "plan_type": "green_premium",
    "renewable_pct": 100,
    "description": "100% GreenPower accredited. Variable rate. No exit fee."
  },
  {
    "plan_id": "VAL",
    "plan_name": "Value 12",
    "rate_per_kwh": 0.21,
    "daily_supply_charge": 1.10,
    "green_score": 0,
    "plan_type": "flat_rate",
    "renewable_pct": 0,
    "description": "Lowest unit rate. Fixed 12-month term. $75 exit fee."
  },
  {
    "plan_id": "TOU",
    "plan_name": "Flex Time",
    "rate_per_kwh": 0.36,
    "daily_supply_charge": 1.10,
    "green_score": 20,
    "plan_type": "time_of_use",
    "renewable_pct": 20,
    "description": "Time-of-use: peak rate shown. Off-peak 0.14/kWh. Variable."
  }
]
```

**Design invariants to preserve:**
- ECO is the ONLY `plan_type: "green_premium"` entry — this makes the Green track selection unambiguous
- VAL rate (0.21) < ECO rate (0.26) → cheapest and green tracks always diverge for all personas
- All plans share `daily_supply_charge: 1.10` → savings are purely rate-driven, easy to explain
- TOU is a decoy (highest rate at 0.36) — agent must not recommend it in Phase 2

**This file must also be copied to `infrastructure/seed_data/tariff_plans.json`** — that copy is the source-of-truth used by the seeder construct if the catalog is ever needed at deploy time.

---

### `lambda/handler.py` (service, CRUD + request-response)

**Analog:** Greenfield — no analog
**Source:** RESEARCH.md §Architecture Patterns / Pattern 3 + Pattern 4

**Imports and module-level init (load JSON once at cold start):**
```python
import json
import os
import boto3
from decimal import Decimal

with open("tariff_plans.json") as f:
    TARIFF_PLANS = json.load(f)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])
```

**`get_billing_history` function pattern:**
```python
def get_billing_history(event, context):
    customer_id = event["customer_id"]
    response = table.query(
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": customer_id},
    )
    return sorted(response["Items"], key=lambda x: x["month"])
```

**`simulate_savings` function pattern (full algorithm — SAV-03 compliant, no LLM arithmetic):**
```python
def simulate_savings(event, context):
    customer_id = event["customer_id"]
    billing_history = get_billing_history({"customer_id": customer_id}, context)

    avg_kwh = sum(float(r["usage_kwh"]) for r in billing_history) / len(billing_history)
    current_plan_id = billing_history[0]["plan_id"]
    current_plan = next(p for p in TARIFF_PLANS if p["plan_id"] == current_plan_id)
    days_per_month = 30.44

    def projected_monthly_cost(plan):
        return avg_kwh * float(plan["rate_per_kwh"]) + float(plan["daily_supply_charge"]) * days_per_month

    current_avg_cost = projected_monthly_cost(current_plan)
    candidate_plans = [p for p in TARIFF_PLANS if p["plan_id"] != current_plan_id]

    green_plans = [p for p in candidate_plans if p["plan_type"] == "green_premium"]
    green_plan = max(green_plans, key=lambda p: p["green_score"])
    green_saving = current_avg_cost - projected_monthly_cost(green_plan)

    cheapest_plan = min(candidate_plans, key=projected_monthly_cost)
    cheapest_saving = current_avg_cost - projected_monthly_cost(cheapest_plan)

    return {
        "green": {
            "plan_id": green_plan["plan_id"],
            "plan_name": green_plan["plan_name"],
            "saving_monthly": round(green_saving, 2),
            "saving_annual": round(green_saving * 12, 2),
        },
        "cheapest": {
            "plan_id": cheapest_plan["plan_id"],
            "plan_name": cheapest_plan["plan_name"],
            "saving_monthly": round(cheapest_saving, 2),
            "saving_annual": round(cheapest_saving * 12, 2),
        },
    }
```

**Critical rules:**
- Load `tariff_plans.json` at module level (cold start) — not inside the handler function
- Always read `TABLE_NAME` from `os.environ` — never hardcode
- Savings computed from `avg_kwh * rate_per_kwh` — never from stored `cost_usd` (DATA-03)
- DynamoDB `boto3.resource` (DocumentClient-style) is used here — Python dict format works at runtime; wire format is only required for the seeder's `AwsSdkCall`
- Use `float()` on Decimal values from DynamoDB — `boto3.resource` returns `Decimal` for numeric attributes

---

### `tests/conftest.py` (test fixture, shared)

**Analog:** Greenfield — no analog
**Source:** RESEARCH.md §Code Examples / Unit Test Pattern

**Core pattern — shared fixtures:**
```python
import pytest

TARIFF_PLANS = [
    {"plan_id": "STD", "plan_name": "Standard Rate", "rate_per_kwh": 0.32,
     "daily_supply_charge": 1.10, "green_score": 0, "plan_type": "flat_rate"},
    {"plan_id": "ECO", "plan_name": "EcoFlex 100", "rate_per_kwh": 0.26,
     "daily_supply_charge": 1.10, "green_score": 100, "plan_type": "green_premium"},
    {"plan_id": "VAL", "plan_name": "Value 12", "rate_per_kwh": 0.21,
     "daily_supply_charge": 1.10, "green_score": 0, "plan_type": "flat_rate"},
    {"plan_id": "TOU", "plan_name": "Flex Time", "rate_per_kwh": 0.36,
     "daily_supply_charge": 1.10, "green_score": 20, "plan_type": "time_of_use"},
]

@pytest.fixture
def tariff_plans():
    return TARIFF_PLANS

@pytest.fixture
def sarah_billing():
    months = [4,5,6,7,8,9,10,11,12,1,2,3]
    usages = [425,400,450,500,550,600,625,600,550,475,450,375]
    return [
        {"customer_id": "CUST-001", "month": f"2025-{m:02d}",
         "usage_kwh": u, "cost_usd": round(u * 0.32 + 1.10 * 30.44, 2), "plan_id": "STD"}
        for m, u in zip(months, usages)
    ]
```

---

### `tests/test_simulate_savings.py` (test, transform)

**Analog:** Greenfield — no analog
**Source:** RESEARCH.md §Code Examples / Unit Test Pattern for simulate_savings

**Core test pattern:**
```python
import pytest
from lambda.handler import simulate_savings

def test_flagship_persona_green_saving(sarah_billing, tariff_plans):
    result = simulate_savings(sarah_billing, tariff_plans)
    assert abs(result["green"]["saving_monthly"] - 30.00) < 0.01

def test_flagship_persona_cheapest_saving(sarah_billing, tariff_plans):
    result = simulate_savings(sarah_billing, tariff_plans)
    assert abs(result["cheapest"]["saving_monthly"] - 55.00) < 0.01

def test_cheapest_always_gte_green(sarah_billing, tariff_plans):
    result = simulate_savings(sarah_billing, tariff_plans)
    assert result["cheapest"]["saving_monthly"] >= result["green"]["saving_monthly"]

def test_green_plan_is_eco(sarah_billing, tariff_plans):
    result = simulate_savings(sarah_billing, tariff_plans)
    assert result["green"]["plan_id"] == "ECO"

def test_cheapest_plan_is_val(sarah_billing, tariff_plans):
    result = simulate_savings(sarah_billing, tariff_plans)
    assert result["cheapest"]["plan_id"] == "VAL"

def test_green_cheapest_diverge(sarah_billing, tariff_plans):
    result = simulate_savings(sarah_billing, tariff_plans)
    assert result["green"]["plan_id"] != result["cheapest"]["plan_id"]
```

**Tolerance:** Use `abs(actual - expected) < 0.01` (1 cent) for monetary comparisons — not exact equality, which is fragile against floating-point rounding.

---

### `tests/test_get_billing_history.py` (test, CRUD)

**Analog:** Greenfield — no analog
**Source:** RESEARCH.md §Validation Architecture

**Core pattern — mock DynamoDB with pytest-mock:**
```python
import pytest

def test_returns_12_months(mocker, sarah_billing):
    mock_table = mocker.patch("lambda.handler.table")
    mock_table.query.return_value = {"Items": sarah_billing}

    from lambda.handler import get_billing_history
    result = get_billing_history({"customer_id": "CUST-001"}, None)

    assert len(result) == 12

def test_sorted_by_month(mocker, sarah_billing):
    mock_table = mocker.patch("lambda.handler.table")
    mock_table.query.return_value = {"Items": list(reversed(sarah_billing))}

    from lambda.handler import get_billing_history
    result = get_billing_history({"customer_id": "CUST-001"}, None)

    months = [r["month"] for r in result]
    assert months == sorted(months)
```

---

### `tests/test_schema.py` (test, transform)

**Analog:** Greenfield — no analog
**Source:** RESEARCH.md §Validation Architecture / DATA-03

**Core pattern — validate all seed records have required fields:**
```python
from infrastructure.seed_data.billing_records import ALL_RECORDS

REQUIRED_FIELDS = {"customer_id", "month", "usage_kwh", "cost_usd", "plan_id"}

def test_all_records_have_required_fields():
    for record in ALL_RECORDS:
        missing = REQUIRED_FIELDS - set(record.keys())
        assert not missing, f"Record {record.get('customer_id')} missing: {missing}"

def test_usage_kwh_is_numeric():
    for record in ALL_RECORDS:
        assert isinstance(record["usage_kwh"], (int, float)), \
            f"usage_kwh must be numeric for {record}"

def test_three_customers_present():
    customer_ids = {r["customer_id"] for r in ALL_RECORDS}
    assert customer_ids == {"CUST-001", "CUST-002", "CUST-003"}

def test_twelve_months_per_customer():
    for cust_id in ["CUST-001", "CUST-002", "CUST-003"]:
        months = [r for r in ALL_RECORDS if r["customer_id"] == cust_id]
        assert len(months) == 12, f"{cust_id} has {len(months)} records, expected 12"
```

---

### `pytest.ini` (config)

**Analog:** Greenfield — no analog

**Minimal configuration:**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

---

## Shared Patterns

### IAM Least Privilege
**Apply to:** `tools_lambda.py`, `seeder.py`

CDK provides grant methods on constructs — use these instead of writing `PolicyStatement` manually:
```python
# For Lambda reading DynamoDB — use CDK grant method
table.grant_read_data(tools_fn)  # grants dynamodb:GetItem, Query, Scan on this table only

# For seeder custom resource — must use explicit statement (grant_read_data doesn't cover BatchWriteItem)
iam.PolicyStatement(
    actions=["dynamodb:BatchWriteItem"],
    resources=[table.table_arn],
)
```

### Environment Variable Pattern
**Apply to:** `handler.py`, any future Lambda
**Source:** RESEARCH.md §Anti-Patterns

Always read config from environment variables at module level:
```python
import os
TABLE_NAME = os.environ["TABLE_NAME"]  # raises KeyError immediately if missing — fail fast
```

Never hardcode table names, ARNs, or region strings inside Lambda handler code.

### DynamoDB Wire Format vs Resource Format
**Apply to:** `seeder.py`, `billing_records.py` (seeder path) vs `handler.py` (Lambda path)

Two different contexts require different formats:

| Context | Client | Format Required | Example |
|---------|--------|-----------------|---------|
| `AwsSdkCall` (seeder) | Raw `DynamoDB` service | Wire format | `{"N": "425"}` |
| `boto3.resource("dynamodb")` (Lambda) | DocumentClient-style | Python native | `425` (int) |

The seeder and the Lambda handler use different clients — this is intentional and correct.

### Python Compatibility Guard
**Apply to:** All Python files (`handler.py`, `foundation_stack.py`, constructs, tests)

Lambda runtime is Python 3.12 (cloud). Local Python is 3.9.6. Avoid 3.10+ syntax:
- No `match` statement (3.10+)
- No `typing.ParamSpec` (3.10+)
- No `typing.TypeAlias` (3.10+)
- Use `Union[X, Y]` not `X | Y` for type hints (3.10+)

---

## No Analog Found

All 17 files in this phase have no codebase analog — this is a confirmed greenfield project. All patterns sourced from `01-RESEARCH.md`.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| All files (17 total) | various | various | Greenfield — no source code exists in the repository |

The planner must use the RESEARCH.md patterns in the Pattern Assignments above as the primary reference for all implementation actions.

---

## Metadata

**Analog search scope:** Entire repository (all non-planning, non-git files)
**Files scanned:** 1 (only `.claude/settings.local.json` exists — no source code)
**Pattern extraction date:** 2026-04-23
**Pattern source:** `01-RESEARCH.md` exclusively (verified against CDK docs, boto3 docs, and AWS DynamoDB API reference)
