---
phase: 01-foundation-dummy-data
plan: 01
subsystem: infrastructure/data
tags:
  - python-cdk
  - dynamodb
  - dummy-data
  - aws-bedrock
dependency_graph:
  requires: []
  provides:
    - app.py CDK entry point (stub, uncommented by Plan 03)
    - lambda/tariff_plans.json tariff catalog bundled with Lambda
    - infrastructure/seed_data/tariff_plans.json tariff catalog for infrastructure code
    - infrastructure.seed_data.billing_records module with ALL_RECORDS + DYNAMO_RECORDS
  affects:
    - "Plan 01-02 (handler + tests): imports billing_records and tariff_plans.json for test fixtures"
    - "Plan 01-03 (CDK constructs): imports app.py scaffold, billing_records.DYNAMO_RECORDS for seeder"
tech_stack:
  added:
    - aws-cdk-lib>=2.250.0
    - constructs>=10.0.0
    - boto3>=1.42.0
    - pytest>=7.0
    - pytest-mock>=3.0
  patterns:
    - "Python CDK app.py entry point pattern (region hardcoded to us-east-1)"
    - "DynamoDB wire format via to_dynamo() converter"
    - "Module-level sanity assertions for data integrity"
key_files:
  created:
    - app.py
    - cdk.json
    - requirements.txt
    - requirements-dev.txt
    - pytest.ini
    - .gitignore
    - infrastructure/__init__.py
    - infrastructure/constructs/__init__.py
    - infrastructure/seed_data/__init__.py
    - lambda/tariff_plans.json
    - infrastructure/seed_data/tariff_plans.json
    - infrastructure/seed_data/billing_records.py
  modified: []
decisions:
  - "app.py has FoundationStack import commented — Plan 03 uncomments it; stub allows scaffold verification without CDK CLI installed"
  - "lambda/__init__.py intentionally absent — lambda/ is a Lambda asset directory, not a Python package"
  - "tariff_plans.json maintained in two locations (lambda/ and infrastructure/seed_data/) — lambda/ is what gets bundled into the zip, infrastructure/ is the reference copy"
  - "billing_records.py uses type-annotated DYNAMO_RECORDS assignment — type annotation preserves static analysis benefit while satisfying functional contract"
metrics:
  duration: "3m"
  completed: "2026-04-23"
  tasks_completed: 3
  files_created: 12
  files_modified: 0
---

# Phase 1 Plan 1: CDK Scaffold + Tariff Catalog + Billing Seed Data Summary

**One-liner:** Python CDK scaffold with verified tariff rates (STD=0.32, ECO=0.26, VAL=0.21) and 36-record billing seed data yielding Sarah Chen's DEMO-02 targets of Green=$30/mo and Cheapest=$55/mo.

## What Was Built

### Task 1: CDK Project Scaffold (commit 7d231de)

Created the complete Python CDK project skeleton required by Plans 02 and 03:

- **app.py** — CDK entry point with `import aws_cdk as cdk`, `cdk.App()`, and `app.synth()`. Region us-east-1 hardcoded as a comment in the commented FoundationStack block. Plan 03 uncomments the block.
- **cdk.json** — CDK config with `"app": "python app.py"` and standard watch excludes.
- **requirements.txt** — aws-cdk-lib>=2.250.0, constructs>=10.0.0, boto3>=1.42.0
- **requirements-dev.txt** — extends requirements.txt; adds pytest>=7.0 and pytest-mock>=3.0
- **pytest.ini** — test discovery: testpaths=tests, test_*.py, Test*, test_* conventions
- **.gitignore** — Python, CDK (cdk.out/), pytest, IDE patterns
- **infrastructure/__init__.py** — empty package marker
- **infrastructure/constructs/__init__.py** — empty package marker
- **infrastructure/seed_data/__init__.py** — empty package marker

No `lambda/__init__.py` was created — the `lambda/` directory is a Lambda asset, not a Python package.

### Task 2: Tariff Plan Catalog JSON (commit 38d2ad0)

Created `lambda/tariff_plans.json` and byte-for-byte copy at `infrastructure/seed_data/tariff_plans.json`:

| Plan ID | Plan Name | Rate ($/kWh) | Plan Type | Green Score | Renewable % |
|---------|-----------|-------------|-----------|-------------|-------------|
| STD | Standard Rate | 0.32 | flat_rate | 0 | 0% |
| ECO | EcoFlex 100 | 0.26 | green_premium | 100 | 100% |
| VAL | Value 12 | 0.21 | flat_rate | 0 | 0% |
| TOU | Flex Time | 0.36 | time_of_use | 20 | 20% |

All plans share `daily_supply_charge: 1.10` — savings are purely rate-driven.

**Invariants enforced:**
- ECO is the ONLY `plan_type: "green_premium"` — unambiguous Green selection
- VAL (0.21) < ECO (0.26) — Green and Cheapest always select different plans
- TOU (0.36) is a decoy — never selected as cheapest or green

**Savings math verification (DEMO-02):**
```
avg_kwh = 500 (Sarah Chen flagship persona)
Green saving  = 500 × (0.32 - 0.26) = $30.00/month  ($360/year) [VERIFIED]
Cheapest saving = 500 × (0.32 - 0.21) = $55.00/month ($660/year) [VERIFIED]
```

### Task 3: Billing Seed Data Module (commit a477e13)

Created `infrastructure/seed_data/billing_records.py` with:

**Module exports available to downstream plans:**
```python
from infrastructure.seed_data.billing_records import (
    SARAH_CHEN_RECORDS,    # list[dict], 12 items, CUST-001
    MARCUS_WEBB_RECORDS,   # list[dict], 12 items, CUST-002
    ELENA_VASQUEZ_RECORDS, # list[dict], 12 items, CUST-003
    ALL_RECORDS,           # list[dict], 36 items, Python-native format
    DYNAMO_RECORDS,        # list[dict], 36 items, DynamoDB wire format
    to_dynamo,             # (record: dict) -> dict converter
)
```

**Persona summary:**

| Persona | Customer ID | Avg kWh/mo | Green Saving | Cheapest Saving |
|---------|-------------|-----------|-------------|----------------|
| Sarah Chen | CUST-001 | 500.0 | $30.00/mo | $55.00/mo |
| Marcus Webb | CUST-002 | ~282 | $16.92/mo | $31.02/mo |
| Elena Vasquez | CUST-003 | ~233 | $13.98/mo | $25.63/mo |

**Month range:** April 2025 – March 2026 (`2025-04` to `2026-03`)

**Wire format example (DYNAMO_RECORDS[0]):**
```json
{
  "customer_id": {"S": "CUST-001"},
  "month": {"S": "2025-04"},
  "usage_kwh": {"N": "425"},
  "cost_usd": {"N": "169.48"},
  "plan_id": {"S": "STD"}
}
```

**Module-level assertions (fire at import time):**
- 12 records per persona, 36 total
- Sarah's average exactly 500.0 kWh

## Exports for Downstream Plans

**Plan 01-02 (handler + tests):**
- Import billing_records for test fixtures: `SARAH_CHEN_RECORDS`, `ALL_RECORDS`
- Load tariff catalog: `json.load(open("lambda/tariff_plans.json"))`

**Plan 01-03 (CDK constructs):**
- Import scaffold: `app.py`, `cdk.json` for CDK context
- Seeder data: `from infrastructure.seed_data.billing_records import DYNAMO_RECORDS`
- Tariff catalog for seeder: `infrastructure/seed_data/tariff_plans.json`

## Deviations from Plan

None — plan executed exactly as written.

Minor note: The acceptance criterion `grep -c "DYNAMO_RECORDS = \[to_dynamo"` does not match the type-annotated form `DYNAMO_RECORDS: List[Dict[str, Dict[str, str]]] = [to_dynamo(r) for r in ALL_RECORDS]` specified verbatim by the plan. The type annotation form was kept because the plan's verbatim code explicitly includes the type annotation, and all functional verification passes. The pattern `DYNAMO_RECORDS.*\[to_dynamo` correctly matches. This is a plan-internal inconsistency, not a deviation from intent.

## Threat Surface Scan

No new security-relevant surface introduced beyond what the plan's threat model covers. All data is synthetic (CUST-001/002/003, fictional names). No credentials, API keys, or real PII in any committed file. Threat register (T-01-01-01 through T-01-01-05) is fully addressed.

## Known Stubs

- **app.py lines 14-18:** FoundationStack import and instantiation are commented out. Plan 03 (01-03-PLAN) uncomments this block. The stub is intentional and documented — `cdk synth` currently produces an empty cloud assembly, which is expected until Plan 03 wires in the stack.

## Self-Check: PASSED

All 12 created files confirmed present on disk. All 3 task commits verified in git log:
- 7d231de: feat(01-01): CDK project scaffold and dependency manifests
- 38d2ad0: feat(01-01): tariff plan catalog JSON in both locations
- a477e13: feat(01-01): billing seed data — 36 records, 3 personas, Python + DynamoDB wire format
