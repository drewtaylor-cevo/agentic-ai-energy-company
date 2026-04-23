# Phase 1: Foundation + Dummy Data - Research

**Researched:** 2026-04-23
**Domain:** AWS CDK (Python), DynamoDB single-table design, Lambda packaging, dummy data engineering
**Confidence:** HIGH

---

## Summary

Phase 1 establishes the data foundation the entire demo rests on. The core deliverables are a DynamoDB billing table seeded with 3 customer personas, a tariff plan catalog bundled inside the Lambda package as JSON, and a Python CDK stack that deploys and seeds everything in a single `cdk deploy` command. No AI is in the call path during this phase — all outputs are deterministic and independently verifiable.

The savings math has been verified by calculation in this research session: by setting the current plan (STD) at $0.32/kWh and engineering the Green plan (ECO) at $0.26/kWh and Cheapest plan (VAL) at $0.21/kWh, the flagship persona (Sarah Chen, 500 kWh/month average) yields exactly Green = $30.00/month and Cheapest = $55.00/month savings. These figures are baked into the dummy data design below and must not be changed without re-running the verification.

The key CDK seeding pattern is `AwsCustomResource` with `AwsSdkCall(action="batchWriteItem")`. At 36 total records (3 personas × 12 months) across 2 batches of 25, the seed fits comfortably within DynamoDB's BatchWriteItem limit and CloudFormation's template size constraint.

**Primary recommendation:** Use `cdk init app --language python` for the scaffold, build one CDK stack with three constructs (DynamoDB table, Lambda functions, seeder custom resource), and verify savings figures against the formula spreadsheet before Phase 2 begins.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Customer billing history lives in **DynamoDB** — single table, `customer_id` (PK) + `month` (SK), one item per month per customer (12 items per customer). Not S3, not Lambda-local.
- **D-02:** Tariff plan catalog is **not** in DynamoDB. It lives as a `tariff_plans.json` file bundled inside the Lambda package — zero latency, no extra AWS resources, easy to edit between demo runs.
- **D-03:** Dummy data is seeded via a **CDK custom resource** — one `cdk deploy` command stands up the table and populates it. No separate seed script required.

### Claude's Discretion
- **CDK language:** Python CDK preferred for consistency with the Strands SDK / agent code (one language across the stack). Switch to TypeScript only if a specific L3 construct requires it.
- **DynamoDB billing record schema:** Each item should include at minimum: `customer_id`, `month` (YYYY-MM), `usage_kwh` (kWh usage), `cost_usd` (billed amount), `plan_id` (current tariff plan). Claude determines the exact attribute names.
- **Tariff plan catalog schema:** Each plan entry should include: `plan_id`, `plan_name`, `rate_per_kwh`, `daily_supply_charge`, `green_score` (for ranking Green plans), `plan_type` (e.g., flat_rate, time_of_use, green_premium). Claude determines exact structure.
- **Customer personas:** 3+ personas covering meaningfully different usage profiles. Claude engineers the data so that the flagship persona yields Green savings ~$30/month and Cheapest savings ~$55/month (DEMO-02 requirement). Names and archetypes at Claude's discretion.
- **AWS Region:** us-east-1 strongly recommended — ap-southeast-2/Sydney does NOT support AgentCore Registry. CDK should default to us-east-1 unless the user confirms otherwise before deployment.

### Deferred Ideas (OUT OF SCOPE)
- AWS Region: Not locked in this discussion — flagged as a pre-deployment decision. Research agent should surface whether us-east-1 is the correct choice given the client's location and AgentCore feature requirements.
- Strands SDK vs classic Bedrock Agents: Open question for Phase 2 — verify Strands availability and stability in the target region before Phase 2 begins.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | System retrieves 12 months of billing history per customer including monthly kWh usage, monthly cost, and current tariff plan details | DynamoDB single-table design with `customer_id` (PK) + `month` (SK); `get_billing_history` Lambda reads all 12 items for a given customer |
| DATA-02 | Dummy dataset covers at least 3 customer personas with meaningfully different usage profiles | Three engineered personas verified by calculation: Sarah Chen (high-usage, 500 kWh/month), Marcus Webb (mid-usage, 282 kWh/month), Elena Vasquez (seasonal-heavy, 233 kWh/month) |
| DATA-03 | Usage data stored in kWh (not dollars) so savings calculations are independently recalculable | Every DynamoDB record includes `usage_kwh` as a top-level attribute; `cost_usd` is also stored but savings are always computed from `usage_kwh × rate_per_kwh`, not from stored cost figures |
| DEMO-02 | Dummy data intentionally designed so Green track saves ~$30/month and Cheapest track saves ~$55/month for the flagship persona | Mathematically verified: STD plan @ $0.32/kWh, ECO plan @ $0.26/kWh, VAL plan @ $0.21/kWh, Sarah Chen at 500 kWh average yields exactly Green = $30.00/month and Cheapest = $55.00/month |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Billing history storage | Database / Storage (DynamoDB) | — | Persistent, queryable by customer + month; Phase 2 agent tools read from here |
| Tariff plan catalog | Lambda (bundled file) | — | Static config with zero runtime latency; JSON bundled into Lambda zip via `Code.from_asset` |
| Data seeding on deploy | CDK custom resource (Lambda-backed) | — | Runs once at stack creation; eliminates separate seed scripts |
| `get_billing_history` tool stub | API / Backend (Lambda) | DynamoDB | Reads DynamoDB; returns structured 12-month list; no AI in path |
| `simulate_savings` tool stub | API / Backend (Lambda) | tariff_plans.json | Pure arithmetic; reads tariff catalog from bundled JSON + billing data; no AI |
| Infrastructure deployment | CDK stack | — | Python CDK; single `cdk deploy` command covers table + Lambda + seeder |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aws-cdk-lib | 2.250.0 | All CDK constructs (DynamoDB, Lambda, custom resources, IAM) | GA and stable; CDK v2 consolidates all L1/L2 into a single package; verified npm registry 2026-04-14 |
| constructs | >=10.0.0 | CDK base construct model | Required peer dependency of aws-cdk-lib |
| aws-cdk (CLI) | 2.1118.4 | `cdk deploy`, `cdk synth`, `cdk bootstrap` commands | CLI version matches lib version; verified npm registry |
| boto3 | 1.42.11 | AWS SDK inside Lambda functions — DynamoDB reads | Installed locally; current stable release; DynamoDB client is the primary interface |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| aws_cdk.custom_resources | (part of aws-cdk-lib 2.250.0) | `AwsCustomResource` + `AwsSdkCall` for seeder | Use for DynamoDB BatchWriteItem calls triggered at stack creation |
| pytest | >=7.0 | Unit tests for `simulate_savings` arithmetic | Validate savings formula output before Phase 2 integration |
| pytest-mock | >=3.0 | Mock DynamoDB calls in unit tests | Decouple Lambda logic from AWS SDK in test suite |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| AwsCustomResource for seeding | aws-cdk-dynamodb-seeder (PyPI) | Third-party package; uses S3 for large datasets; unnecessary complexity for 36 records — use native AwsCustomResource |
| tariff_plans.json in Lambda | DynamoDB table | Extra AWS resource + read latency; catalog never changes at runtime; bundled JSON is simpler and faster |
| Python CDK | TypeScript CDK | TypeScript has marginally earlier access to new L2 constructs; Python is consistent with agent code language — no L3 constructs required in Phase 1 |

**Installation:**
```bash
npm install -g aws-cdk
pip install aws-cdk-lib constructs boto3 pytest pytest-mock
```

**Version verification:** aws-cdk-lib 2.250.0 confirmed via `npm view aws-cdk-lib version` (published 2026-04-14). boto3 1.42.11 confirmed via local `pip3 list`.

---

## Architecture Patterns

### System Architecture Diagram

```
cdk deploy
    │
    ├─► DynamoDB Table (tariff-billing)
    │       PK: customer_id (S)
    │       SK: month (S, YYYY-MM)
    │       attrs: usage_kwh, cost_usd, plan_id
    │
    ├─► Lambda Package (tariff-tools)
    │       handler.py
    │       tariff_plans.json  ← bundled, zero-latency
    │       functions:
    │         get_billing_history(customer_id) → reads DynamoDB
    │         simulate_savings(customer_id)    → reads JSON + DynamoDB
    │
    └─► CDK Custom Resource (seeder)
            AwsCustomResource (onCreate only)
              Batch 1: 25 records → DynamoDB BatchWriteItem
              Batch 2: 11 records → DynamoDB BatchWriteItem

Phase 1 output (no AI):
  get_billing_history("CUST-001")
    → DynamoDB Query → 12 items → structured list

  simulate_savings("CUST-001")
    → DynamoDB Query → avg_kwh
    → tariff_plans.json → plan rates
    → arithmetic: savings = avg_kwh * (current_rate - plan_rate)
    → { green: {plan_id, saving_monthly, saving_annual},
        cheapest: {plan_id, saving_monthly, saving_annual} }
```

### Recommended Project Structure
```
customer-tariff/
├── app.py                          # CDK app entry point
├── cdk.json                        # CDK config (app = "python app.py")
├── requirements.txt                # CDK + Lambda shared deps
├── requirements-dev.txt            # pytest, pytest-mock
├── infrastructure/
│   ├── __init__.py
│   ├── foundation_stack.py         # Main CDK stack
│   ├── constructs/
│   │   ├── billing_table.py        # DynamoDB construct
│   │   ├── tools_lambda.py         # Lambda construct
│   │   └── seeder.py              # Custom resource seeder construct
│   └── seed_data/
│       ├── billing_records.py      # Python list of 36 DynamoDB items
│       └── tariff_plans.json       # Tariff catalog (copied to Lambda)
├── lambda/
│   ├── handler.py                  # get_billing_history + simulate_savings
│   └── tariff_plans.json           # Bundled catalog (source of truth)
└── tests/
    ├── conftest.py
    └── test_simulate_savings.py    # Arithmetic verification tests
```

### Pattern 1: DynamoDB Single-Table Billing Records

**What:** One table, `customer_id` as partition key, `month` as sort key. One item per customer per month. No GSI required — the only access pattern is "give me all 12 months for customer X."

**When to use:** When access patterns are known and simple. For this demo, the only query is `PK = "CUST-001"` which returns all 12 SK values sorted by month automatically.

**Example:**
```python
# Source: CDK docs aws_cdk.aws_dynamodb (CDK 2.250.0)
from aws_cdk import aws_dynamodb as dynamodb, RemovalPolicy

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

### Pattern 2: CDK Custom Resource for One-Command Seeding

**What:** `AwsCustomResource` backed by a Lambda (auto-created by CDK) that calls `DynamoDB.batchWriteItem` once at stack creation. Does not re-run on update unless `physical_resource_id` changes.

**When to use:** Seed data that must be in place before the application can function. The seeder runs during `cdk deploy` and is complete before the stack finishes.

**Critical detail:** DynamoDB BatchWriteItem accepts a maximum of 25 items per call. With 36 records (3 personas × 12 months), two `AwsCustomResource` instances are required.

**Example:**
```python
# Source: CDK custom_resources README (aws-cdk-lib 2.250.0)
import math
from aws_cdk import aws_custom_resources as cr, aws_iam as iam

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

**DynamoDB AttributeValue format for seeder** — values must use DynamoDB wire format:
```python
# Correct: DynamoDB wire format required by batchWriteItem
{"customer_id": {"S": "CUST-001"}, "month": {"S": "2025-04"},
 "usage_kwh": {"N": "425"}, "cost_usd": {"N": "169.48"}, "plan_id": {"S": "STD"}}

# Wrong: Python dict format (only works with DocumentClient, not raw DynamoDB)
{"customer_id": "CUST-001", "month": "2025-04", "usage_kwh": 425}
```

Note: `AwsSdkCall` uses the raw DynamoDB API (not DocumentClient), so numeric values must be `{"N": "425"}` not `425`.

### Pattern 3: Lambda with Bundled JSON Data File

**What:** `Code.from_asset("lambda/")` zips the entire `lambda/` directory including `tariff_plans.json`. Inside the handler, `open("tariff_plans.json")` loads the catalog.

**When to use:** Static reference data that never changes at runtime and has no external dependency.

**Example:**
```python
# CDK side: bundle the entire lambda/ directory as a zip asset
from aws_cdk import aws_lambda as lambda_

tools_fn = lambda_.Function(
    self, "TariffTools",
    runtime=lambda_.Runtime.PYTHON_3_12,
    handler="handler.get_billing_history",  # or separate handlers
    code=lambda_.Code.from_asset("lambda"),  # includes tariff_plans.json
    environment={"TABLE_NAME": table.table_name},
)
table.grant_read_data(tools_fn)

# Lambda handler side: load JSON at cold start (module level for efficiency)
import json, os, boto3

with open("tariff_plans.json") as f:
    TARIFF_PLANS = json.load(f)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

def get_billing_history(event, context):
    customer_id = event["customer_id"]
    response = table.query(
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": customer_id},
    )
    return sorted(response["Items"], key=lambda x: x["month"])
```

**File path note:** Lambda's working directory is `/var/task/` at runtime. Files bundled via `Code.from_asset` are available at the root — `open("tariff_plans.json")` works without path manipulation.

### Pattern 4: simulate_savings — Deterministic Savings Algorithm

**What:** Pure arithmetic function. Reads billing history to compute average kWh, reads tariff plans to get rates, computes savings per plan, returns Green and Cheapest recommendations.

**The formula (verified against spreadsheet):**
```python
def simulate_savings(billing_history: list, plans: list) -> dict:
    """
    Savings formula (SAV-03 compliant — no LLM arithmetic):
    
    current_plan = plans where plan_id == billing_history[0]["plan_id"]
    avg_kwh = mean(record["usage_kwh"] for record in billing_history)
    
    for each candidate plan:
        projected_cost = avg_kwh * plan["rate_per_kwh"] + plan["daily_supply_charge"] * 30.44
    
    current_avg_cost = avg_kwh * current_plan["rate_per_kwh"] + current_plan["daily_supply_charge"] * 30.44
    saving = current_avg_cost - projected_cost
    
    green_plans = [p for p in plans if p["plan_type"] == "green_premium"]
    cheapest_plan = min(non_current_plans, key=projected_cost)
    green_plan = max(green_plans, key=saving)
    """
    avg_kwh = sum(r["usage_kwh"] for r in billing_history) / len(billing_history)
    current_plan_id = billing_history[0]["plan_id"]
    current_plan = next(p for p in plans if p["plan_id"] == current_plan_id)
    days_per_month = 30.44

    def projected_monthly_cost(plan):
        return avg_kwh * float(plan["rate_per_kwh"]) + float(plan["daily_supply_charge"]) * days_per_month

    current_avg_cost = projected_monthly_cost(current_plan)

    # Filter to plans the customer is NOT already on
    candidate_plans = [p for p in plans if p["plan_id"] != current_plan_id]

    # Green: highest green_score among plan_type == "green_premium"
    green_plans = [p for p in candidate_plans if p["plan_type"] == "green_premium"]
    green_plan = max(green_plans, key=lambda p: p["green_score"])
    green_saving = current_avg_cost - projected_monthly_cost(green_plan)

    # Cheapest: lowest projected cost regardless of green status
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

**Invariant:** `cheapest_saving >= green_saving` must always hold. Verified for all 3 personas by calculation in this research session.

### Anti-Patterns to Avoid

- **Seeding with `boto3` in a standalone script:** Requires separate execution step and AWS credentials outside CDK context. Use `AwsCustomResource` — it runs atomically inside `cdk deploy`.
- **DynamoDB wire format confusion:** `AwsSdkCall` uses the raw `DynamoDB` service (not `DynamoDB.DocumentClient`). All attribute values must be wrapped: `{"N": "425"}` not `425`. Using Python bare types silently fails or raises a serialization error.
- **`on_update` instead of `on_create`:** Setting `on_update` on the seeder causes it to re-run on every `cdk deploy`, overwriting existing data. Use `on_create` only.
- **Storing `cost_usd` as the savings calculation input:** Savings must be computed from `usage_kwh × rate_per_kwh` so the math is defensible when a customer challenges the figure. Never compute savings as `current_cost - projected_cost_stored` — stored costs are at historical rates, not current plan rates.
- **Module-level DynamoDB client without environment variable:** Always read `TABLE_NAME` from `os.environ` so the Lambda can be tested without hardcoded ARNs.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Seeder CloudFormation trigger | Custom Lambda + CloudFormation custom resource boilerplate | `aws_cdk.custom_resources.AwsCustomResource` | CDK creates the provider Lambda automatically; handles retry, rollback, and idempotency |
| DynamoDB query pagination | Custom pagination loop | `table.query()` + `ExclusiveStartKey` pattern (or use boto3 paginator) | BatchWriteItem and Query both paginate; missing pagination drops records silently |
| Savings arithmetic | LLM prompt with "calculate X" | Pure Python arithmetic in `simulate_savings` | LLM arithmetic is non-deterministic; SAV-03 explicitly requires deterministic code |
| JSON schema validation | Custom validators | Standard Python `json.load()` + assertions in tests | For 36 records the risk is hand-entry errors — unit tests catch these better than runtime validators |

**Key insight:** The CDK `AwsCustomResource` construct eliminates the most common greenfield mistake (writing a separate seed script that diverges from infrastructure). The construct is the infrastructure and the seed operation — they deploy together or not at all.

---

## Engineered Dummy Data

### Tariff Plans (tariff_plans.json)

This structure is verified by calculation. Rates must not be changed without re-running the savings formula.

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

**Design rationale:**
- All plans share the same `daily_supply_charge` (1.10) so savings are purely rate-driven and easy to explain.
- ECO is the only `plan_type: "green_premium"` plan → unambiguous Green selection.
- TOU is a decoy — its effective rate depends on usage timing data the demo doesn't have, so the agent should not recommend it. Including it makes the catalog realistic.
- ECO and VAL are always different plans → the two-track demo invariant holds for all personas.

### Customer Personas (DynamoDB seed data)

**Savings formula (verified):** `avg_monthly_saving = avg_usage_kwh × (current_rate - plan_rate)`

All supply charges are uniform at $1.10/day → savings are purely from the rate delta.

#### Persona 1: Sarah Chen (CUST-001) — Flagship
- **Archetype:** High-usage family household on legacy standard rate for 3+ years.
- **Avg usage:** 500 kWh/month | **Current plan:** STD @ $0.32/kWh
- **Green saving:** 500 × (0.32 - 0.26) = **$30.00/month** ($360/year) [VERIFIED by calculation]
- **Cheapest saving:** 500 × (0.32 - 0.21) = **$55.00/month** ($660/year) [VERIFIED by calculation]
- **Demo hook:** "Sarah, I can see your family has been on our Standard Rate for years. Based on your usage I've found two plans that could save you up to $55 a month — that's $660 a year."

```
Monthly usage (kWh): Apr=425 May=400 Jun=450 Jul=500 Aug=550 Sep=600
                     Oct=625 Nov=600 Dec=550 Jan=475 Feb=450 Mar=375
Seasonal pattern: Peaks in spring/summer (Oct-Nov in Southern Hemisphere), troughs in autumn.
```

#### Persona 2: Marcus Webb (CUST-002) — Mid-usage
- **Archetype:** Apartment dweller, steady consumption, lower bills but still meaningful savings.
- **Avg usage:** 282 kWh/month | **Current plan:** STD @ $0.32/kWh
- **Green saving:** 282 × 0.06 = **$16.92/month** ($203/year)
- **Cheapest saving:** 282 × 0.11 = **$31.02/month** ($372/year)
- **Demo hook:** Demonstrates the recommendation works at lower usage volumes.

```
Monthly usage (kWh): Apr=250 May=235 Jun=265 Jul=280 Aug=300 Sep=320
                     Oct=340 Nov=325 Dec=305 Jan=275 Feb=255 Mar=230
```

#### Persona 3: Elena Vasquez (CUST-003) — Seasonal-heavy
- **Archetype:** Part-time resident or holiday house; near-zero winter usage, dramatic spring/summer peaks.
- **Avg usage:** 233 kWh/month | **Current plan:** STD @ $0.32/kWh
- **Green saving:** 233 × 0.06 = **$13.98/month** ($168/year)
- **Cheapest saving:** 233 × 0.11 = **$25.63/month** ($308/year)
- **Demo hook:** Seasonal variation tells a clear visual story on a usage chart.

```
Monthly usage (kWh): Apr=110 May=95 Jun=130 Jul=160 Aug=290 Sep=380
                     Oct=420 Nov=395 Dec=310 Jan=230 Feb=155 Mar=125
```

**All personas:** Invariant `cheapest_saving >= green_saving` holds. Savings as percentage of current bill: Green ~13-16%, Cheapest ~23-28% — within the credibility band (8–35%) from PITFALLS.md C4.

---

## Common Pitfalls

### Pitfall 1: DynamoDB Wire Format vs DocumentClient Format
**What goes wrong:** `AwsSdkCall` uses the raw DynamoDB service API, not the DocumentClient abstraction. Numeric attributes passed as Python `int` or `float` are not accepted — they must be `{"N": "425"}` (a string inside an N type wrapper). Booleans must be `{"BOOL": True}`. Passing bare Python types causes a `SerializationException` at deploy time.

**Why it happens:** CDK's `AwsSdkCall` calls the underlying boto3 `DynamoDB` client (not `dynamodb.resource` or the DocumentClient pattern). The distinction is invisible from Python.

**How to avoid:** Build seed records in DynamoDB wire format from the start:
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

**Warning signs:** `SerializationException` or `ValidationException` during `cdk deploy` at the custom resource step.

### Pitfall 2: Seeder Re-runs on Every cdk deploy
**What goes wrong:** Using `on_update` instead of `on_create` causes the seeder to re-run every time `cdk deploy` is executed, causing duplicate records or overwrite on tables where records have been modified.

**How to avoid:** Use `on_create` only. If re-seeding is needed (e.g., adding a new persona), change the `physical_resource_id` string to force CloudFormation to treat it as a new resource.

**Warning signs:** Running `cdk deploy` twice inserts duplicate items (DynamoDB PutRequest is idempotent by key, so this is safe but wasteful — catch it early).

### Pitfall 3: savings Formula Uses Stored cost_usd Instead of usage_kwh
**What goes wrong:** The `simulate_savings` function divides `cost_usd` by the current rate to infer usage, rather than reading `usage_kwh` directly. This introduces compounding errors when the customer was on a different rate mid-year.

**Why it happens:** Tempting to "compute savings by comparing old bills to new plan costs" but stored `cost_usd` reflects historical billing rates, not necessarily the current plan rate.

**How to avoid:** Always use `usage_kwh × rate_per_kwh` for both current and projected costs. The `usage_kwh` field is the authoritative source (DATA-03).

**Warning signs:** Savings figures diverge from spreadsheet by more than rounding (< $0.10).

### Pitfall 4: us-east-1 vs ap-southeast-2 Region Selection
**What goes wrong:** AWS default profile is set to `ap-southeast-2` (confirmed on this machine). If CDK deploys to the default profile without an explicit region override, infrastructure lands in Sydney. The AWS Agent Registry (AgentCore feature required for Phase 2+) is NOT available in `ap-southeast-2`.

**Verified from official docs (2026-04-23):** Agent Registry is available in 5 regions: us-east-1, us-east-2, us-west-2, eu-central-1, eu-west-1. ap-southeast-2 (Sydney) supports AgentCore Runtime and Memory but NOT Agent Registry.

**How to avoid:** Set region explicitly in CDK:
```python
# app.py
env = cdk.Environment(region="us-east-1")
FoundationStack(app, "CustomerTariff", env=env)
```

**Also required:** Enable Claude model access in us-east-1 (not ap-southeast-2) — model access is per-region.

**Warning signs:** `cdk deploy` succeeds but Phase 2 AgentCore Registry features unavailable; "Feature not available in this region" errors.

### Pitfall 5: Green and Cheapest Plans Collapse to Same Plan
**What goes wrong:** If the cheapest plan in the portfolio happens to be the Green plan, both recommendation tracks point to the same plan and the demo's two-track narrative collapses.

**How to avoid:** EcoFlex100 (ECO) rate is $0.26/kWh, Value12 (VAL) rate is $0.21/kWh — VAL is always cheaper. The selection logic uses `plan_type == "green_premium"` for the Green track, so ECO and VAL are always distinct. Verified for all 3 personas.

**Warning signs:** `green.plan_id == cheapest.plan_id` in any `simulate_savings` output.

### Pitfall 6: CloudFormation Template Size with Large Seed Datasets
**What goes wrong:** CloudFormation templates have a 1MB limit (when uploaded via S3, otherwise 51KB). Embedding large seed datasets as inline parameters in `AwsCustomResource` can approach this limit.

**Why not a concern here:** 36 records × ~5 attributes each = well under 10KB. No risk. If personas are added later (>200 records), consider switching to an S3-sourced seeder.

**Warning signs:** `TemplateTooBig` error during `cdk deploy`.

---

## Code Examples

### CDK Stack Structure
```python
# Source: CDK Python working guide (docs.aws.amazon.com/cdk/v2/guide/work-with-cdk-python.html)
# infrastructure/foundation_stack.py
import aws_cdk as cdk
from aws_cdk import Stack
from constructs import Construct
from infrastructure.constructs.billing_table import BillingTableConstruct
from infrastructure.constructs.tools_lambda import ToolsLambdaConstruct
from infrastructure.constructs.seeder import SeederConstruct

class FoundationStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        billing = BillingTableConstruct(self, "BillingTable")
        tools = ToolsLambdaConstruct(self, "ToolsLambda",
            table=billing.table)
        seeder = SeederConstruct(self, "Seeder",
            table=billing.table)
```

### app.py Entry Point
```python
# Source: CDK Python getting started (docs.aws.amazon.com/cdk/v2/guide/hello-world.html)
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

### Unit Test Pattern for simulate_savings
```python
# tests/test_simulate_savings.py
import pytest
from lambda.handler import simulate_savings

TARIFF_PLANS = [
    {"plan_id": "STD", "plan_name": "Standard Rate", "rate_per_kwh": 0.32,
     "daily_supply_charge": 1.10, "green_score": 0, "plan_type": "flat_rate"},
    {"plan_id": "ECO", "plan_name": "EcoFlex 100", "rate_per_kwh": 0.26,
     "daily_supply_charge": 1.10, "green_score": 100, "plan_type": "green_premium"},
    {"plan_id": "VAL", "plan_name": "Value 12", "rate_per_kwh": 0.21,
     "daily_supply_charge": 1.10, "green_score": 0, "plan_type": "flat_rate"},
]

SARAH_BILLING = [
    {"customer_id": "CUST-001", "month": f"2025-{m:02d}",
     "usage_kwh": u, "cost_usd": round(u * 0.32 + 1.10 * 30.44, 2), "plan_id": "STD"}
    for m, u in zip(
        [4,5,6,7,8,9,10,11,12,1,2,3],
        [425,400,450,500,550,600,625,600,550,475,450,375]
    )
]

def test_flagship_persona_green_saving():
    result = simulate_savings(SARAH_BILLING, TARIFF_PLANS)
    assert abs(result["green"]["saving_monthly"] - 30.00) < 0.01

def test_flagship_persona_cheapest_saving():
    result = simulate_savings(SARAH_BILLING, TARIFF_PLANS)
    assert abs(result["cheapest"]["saving_monthly"] - 55.00) < 0.01

def test_cheapest_always_gte_green():
    result = simulate_savings(SARAH_BILLING, TARIFF_PLANS)
    assert result["cheapest"]["saving_monthly"] >= result["green"]["saving_monthly"]

def test_green_plan_is_eco():
    result = simulate_savings(SARAH_BILLING, TARIFF_PLANS)
    assert result["green"]["plan_id"] == "ECO"

def test_cheapest_plan_is_val():
    result = simulate_savings(SARAH_BILLING, TARIFF_PLANS)
    assert result["cheapest"]["plan_id"] == "VAL"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate seed scripts (`python seed.py`) | CDK custom resource (AwsCustomResource) | CDK v2 matured ~2023 | Seed is atomically part of infrastructure — no drift between stack state and data state |
| S3 JSON files for all demo data | DynamoDB for queryable records + Lambda-bundled JSON for static config | Project decision | Appropriate separation: DynamoDB for per-customer data, JSON for shared catalog |
| OpenAPI schema for action groups | Function schema (inline CDK) | Bedrock Agents update 2023 | Simpler, no S3 YAML file required; Phase 2 will use function schema |
| Classic Bedrock Agents | Strands SDK + BedrockAgentCoreApp | 2025 (Strands GA) | Simpler for demo iteration; Phase 2 concern — not Phase 1 |

**Deprecated/outdated:**
- `aws_cdk.core` module: Replaced by `aws_cdk` (CDK v2). Do not use `from aws_cdk import core`.
- `RemovalPolicy.RETAIN` for demo stacks: Use `DESTROY` so `cdk destroy` cleans up completely.
- `BillingMode.PROVISIONED` for demo: Use `PAY_PER_REQUEST` — no capacity planning needed.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Supply charge is uniform across all plans at $1.10/day | Dummy Data / Tariff Plans | If supply charges differ, the savings formula changes and the $30/$55 targets shift. The current design deliberately uses uniform supply charges to keep the math simple — this is a deliberate design choice, not a real-world constraint. |
| A2 | CDK CLI is not currently installed globally; user will install it | Environment Availability | User needs `npm install -g aws-cdk` before first `cdk deploy` |
| A3 | strands-agents 1.26.0 is stable and available in us-east-1 | State of the Art | Phase 2 concern only — Phase 1 does not use Strands SDK. Verify before Phase 2 begins. |

---

## Open Questions

1. **Region confirmation before cdk deploy**
   - What we know: CONTEXT.md recommends us-east-1; AWS profile on this machine defaults to ap-southeast-2; Agent Registry confirmed NOT available in ap-southeast-2.
   - What's unclear: Has the user confirmed they will deploy to us-east-1? A typo or misconfigured profile could silently deploy to Sydney.
   - Recommendation: CDK `app.py` should hardcode `region="us-east-1"` and output a reminder. User should also run `aws configure` or `AWS_DEFAULT_REGION=us-east-1 cdk deploy` explicitly.

2. **AWS model access enablement**
   - What we know: Claude model access requires a First-Time-Use form + up to 15 minutes (from PITFALLS.md C1). This is not Phase 1 work but blocks Phase 2.
   - What's unclear: Has model access been enabled in the target account in us-east-1?
   - Recommendation: Include a verification step in Phase 1 exit criteria — run `aws bedrock list-foundation-models --region us-east-1` and confirm Claude 3.x appears. This takes zero implementation effort and catches the blocker before Phase 2 starts.

3. **CDK bootstrap status**
   - What we know: `cdk deploy` requires `cdk bootstrap` to have been run in the target account/region (creates S3 bucket, ECR repo for CDK assets).
   - What's unclear: Whether the target AWS account has been bootstrapped in us-east-1.
   - Recommendation: Include `cdk bootstrap aws://ACCOUNT/us-east-1` as Wave 0 of the plan.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | CDK app, Lambda | ✓ | 3.9.6 (system) / 3.13.12 (in aws-cli) | — |
| Node.js | CDK CLI | ✓ | v24.12.0 | — |
| AWS CLI | CDK deploy, profile management | ✓ | 2.33.19 | — |
| boto3 | Lambda functions (local test) | ✓ | 1.42.11 | — |
| CDK CLI (aws-cdk npm package) | `cdk deploy`, `cdk synth` | ✗ | Not installed | `npm install -g aws-cdk` |
| aws-cdk-lib (Python) | CDK stack code | ✗ | Not installed | `pip install aws-cdk-lib constructs` |
| pytest | Unit tests | ✗ | Not installed | `pip install pytest pytest-mock` |
| AWS account bootstrapped (us-east-1) | CDK deploy | Unknown | — | `cdk bootstrap aws://ACCOUNT/us-east-1` |
| Claude model access (us-east-1) | Phase 2 only | Unknown | — | Enable via Bedrock console before Phase 2 |
| Python >=3.10 for Lambda | Lambda runtime 3.12 (cloud) | ✓ (cloud) | 3.12 in Lambda | Lambda runtime is separate from local Python |

**Missing dependencies with no fallback (block Phase 1):**
- CDK CLI: `npm install -g aws-cdk@latest`
- aws-cdk-lib: `pip install "aws-cdk-lib>=2.250.0" constructs`

**Missing dependencies with fallback:**
- pytest: `pip install pytest pytest-mock` — unit tests can be deferred but are recommended before Phase 2
- CDK bootstrap: `cdk bootstrap aws://ACCOUNT/us-east-1` — one-time setup, clearly documented in plan

**Note on local Python version:** Lambda runtime uses Python 3.12 (cloud). Local Python is 3.9.6. Handler code must not use syntax or stdlib features from 3.10+ (e.g., `match` statement, `typing.ParamSpec`). Use a `python3.12` virtualenv locally or rely on `aws-lambda-python-alpha` bundling with Docker.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=7.0 |
| Config file | `pytest.ini` — Wave 0 gap |
| Quick run command | `pytest tests/test_simulate_savings.py -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | `get_billing_history` returns 12 months for CUST-001 | unit | `pytest tests/test_get_billing_history.py -x` | ❌ Wave 0 |
| DATA-02 | All 3 persona records present after deploy | smoke | `pytest tests/test_seeder_smoke.py -x` | ❌ Wave 0 |
| DATA-03 | Every record has `usage_kwh` as numeric attribute | unit | `pytest tests/test_schema.py -x` | ❌ Wave 0 |
| DEMO-02 | Sarah Chen yields Green=$30, Cheapest=$55 | unit | `pytest tests/test_simulate_savings.py -x` | ❌ Wave 0 |
| DEMO-02 | Invariant cheapest >= green for all personas | unit | `pytest tests/test_simulate_savings.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_simulate_savings.py -x` (savings math, < 5 seconds)
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green + manual DynamoDB verification before Phase 2

### Wave 0 Gaps
- [ ] `tests/test_simulate_savings.py` — covers DEMO-02 (template provided above in Code Examples)
- [ ] `tests/test_get_billing_history.py` — covers DATA-01, needs DynamoDB mock
- [ ] `tests/test_schema.py` — covers DATA-03, validates each record has `usage_kwh`
- [ ] `tests/test_seeder_smoke.py` — covers DATA-02, post-deploy DynamoDB scan smoke test
- [ ] `tests/conftest.py` — shared fixtures (TARIFF_PLANS, billing records per persona)
- [ ] `pytest.ini` — basic config
- [ ] `pip install pytest pytest-mock` — framework install

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Phase 1 has no user-facing endpoints |
| V3 Session Management | No | No sessions in Phase 1 |
| V4 Access Control | Yes — IAM | AwsCustomResource policy scoped to specific table ARN; Lambda role grants `dynamodb:Query` only |
| V5 Input Validation | Yes | `customer_id` path parameter validated in Lambda before DynamoDB query |
| V6 Cryptography | No | No secrets or credentials stored in Phase 1 |

### Known Threat Patterns for CDK + DynamoDB

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Seeder custom resource with overly broad IAM | Elevation of privilege | Scope `AwsCustomResourcePolicy` to table ARN; use `dynamodb:BatchWriteItem` only, not `*` |
| Lambda accessing arbitrary DynamoDB tables | Tampering | Use `table.grant_read_data(fn)` CDK method — grants read-only to specific table ARN only |
| DynamoDB table with `RemovalPolicy.RETAIN` in demo | Availability (cost) | Use `RemovalPolicy.DESTROY` for demo stacks — prevents orphaned tables and ongoing billing |

**IAM pattern for seeder (from PITFALLS.md M6):**
- Trust policy must include `aws:SourceAccount` condition — CDK's `AwsCustomResource` handles this automatically.
- Lambda execution role for seeder is auto-created by CDK with minimum permissions.

---

## Sources

### Primary (HIGH confidence)
- npm registry `aws-cdk-lib` — version 2.250.0, published 2026-04-14 [VERIFIED: npm view]
- npm registry `aws-cdk` CLI — version 2.1118.4 [VERIFIED: npm view]
- boto3 — version 1.42.11 [VERIFIED: local pip3 list]
- docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.custom_resources/README.html — AwsCustomResource + AwsSdkCall pattern [CITED]
- docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_dynamodb/Table.html — DynamoDB table construct [CITED]
- docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html — Agent Registry region availability; ap-southeast-2 NOT supported [VERIFIED: WebFetch 2026-04-23]
- savings formula — verified by Python calculation in this research session (see arithmetic above) [VERIFIED: computed]

### Secondary (MEDIUM confidence)
- aws.amazon.com/blogs/developer/recommended-aws-cdk-project-structure-for-python-applications/ — CDK Python project structure [CITED]
- jeremyritchie.com/posts/3/ — CDK custom resource DynamoDB batch seeder pattern [CITED]
- docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_BatchWriteItem.html — 25-item limit confirmed [CITED]

### Tertiary (LOW confidence)
- pypi.org/project/strands-agents/ — version 1.26.0 as of April 2026 (Phase 2 concern) [CITED]
- pypi.org/project/bedrock-agentcore/ — version 1.6.3 (Phase 2 concern) [CITED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — npm registry verified for CDK; boto3 verified locally
- Architecture: HIGH — DynamoDB + Lambda + CDK custom resource is the documented AWS seeding pattern
- Savings math: HIGH — verified by Python arithmetic in this session; formula is deterministic
- Region availability: HIGH — verified from official AgentCore regions page
- Pitfalls: HIGH — sourced from project PITFALLS.md (already researched with official docs)

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (CDK versions update frequently; verify before deploy)
