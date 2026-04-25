---
plan: 01-02
phase: 01-foundation-dummy-data
status: complete
completed: 2026-04-23
requirements_covered:
  - DATA-01
  - DATA-03
  - DEMO-02
key-files:
  created:
    - lambda/handler.py
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_simulate_savings.py
    - tests/test_get_billing_history.py
    - tests/test_schema.py
---

# Plan 01-02 Summary: TDD Handler + Test Suite

## What Was Built

### lambda/handler.py
Lambda module with two entry points and one pure arithmetic helper:

- `simulate_savings_pure(billing_history, plans)` — deterministic savings calculator (SAV-03 compliant, no LLM in math path). Algorithm: computes avg kWh across billing history, projects monthly cost for each candidate plan, selects green (highest green_score among `plan_type == "green_premium"`) and cheapest (lowest projected cost).
- `get_billing_history(event, context)` — DynamoDB read with V5 input validation. Enforces `^CUST-\d{3,6}$` regex on customer_id before any query is issued.
- `simulate_savings(event, context)` — Lambda wrapper that chains the two above.
- `TARIFF_PLANS` — module-level constant loaded from bundled `tariff_plans.json` at cold start.
- `_validate_customer_id(customer_id)` — raises ValueError on invalid input (non-string, empty, mismatched pattern, injection-shaped strings).

boto3 import is guarded behind `if os.environ.get("TABLE_NAME")` so the module imports cleanly in unit tests without AWS credentials.

### Test Suite (29 tests)

**tests/conftest.py** — shared fixtures: `tariff_plans`, `sarah_billing`, `marcus_billing`, `elena_billing`, `all_billing`.

**tests/test_simulate_savings.py** (11 tests):
- `test_flagship_persona_green_saving` — Sarah @ avg 500 kWh → green saving_monthly = $30.00 ± $0.01 ✓
- `test_flagship_persona_cheapest_saving` — Sarah @ avg 500 kWh → cheapest saving_monthly = $55.00 ± $0.01 ✓
- `test_flagship_persona_annual_savings` — saving_annual == saving_monthly × 12 (both tracks) ✓
- `test_green_plan_is_eco` — green.plan_id == "ECO" ✓
- `test_cheapest_plan_is_val` — cheapest.plan_id == "VAL" ✓
- `test_green_cheapest_diverge` — green.plan_id != cheapest.plan_id ✓
- `test_result_shape` — result has exactly {"green","cheapest"}, each with {"plan_id","plan_name","saving_monthly","saving_annual"} ✓
- `test_cheapest_always_gte_green` — for all 3 personas, cheapest.saving_monthly >= green.saving_monthly ✓
- `test_tou_never_selected` — TOU (rate 0.36, highest) is never chosen for either track ✓
- `test_marcus_savings_approximate` — Marcus ~$16.92 Green, ~$31.02 Cheapest (±$0.10) ✓
- `test_elena_savings_approximate` — Elena ~$13.98 Green, ~$25.63 Cheapest (±$0.10) ✓

**tests/test_get_billing_history.py** (9 tests — DynamoDB mocked via pytest-mock):
- `test_returns_12_months` — 12 items returned from mocked query ✓
- `test_sorted_by_month` — output sorted ascending by month string ✓
- `test_empty_result_returns_empty_list` — empty Items → [] (no exception) ✓
- `test_rejects_missing_customer_id` — event without key → ValueError ✓
- `test_rejects_non_string_customer_id` — customer_id=123 → ValueError ✓
- `test_rejects_malformed_customer_id` — SQL-injection string → ValueError ✓
- `test_rejects_empty_string_customer_id` — "" → ValueError ✓
- `test_raises_when_table_not_configured` — TABLE_NAME unset, table is None → RuntimeError ✓
- `test_passes_customer_id_to_query` — parameterised ExpressionAttributeValues, no string concatenation ✓

**tests/test_schema.py** (9 tests — DATA-02 + DATA-03 invariants):
- `test_all_records_have_required_fields` — all 5 fields present on every record ✓
- `test_usage_kwh_is_numeric` — every usage_kwh is `int` (DATA-03) ✓
- `test_three_customers_present` — {CUST-001, CUST-002, CUST-003} ✓
- `test_twelve_months_per_customer` — exactly 12 records per customer ✓
- `test_months_are_yyyy_mm_format` — regex `\d{4}-\d{2}` matches every month ✓
- `test_months_are_unique_per_customer` — no duplicate (customer_id, month) pairs ✓
- `test_dynamo_records_wire_format` — {"S":...} / {"N":...} wrappers, N values are strings ✓
- `test_dynamo_records_count_matches_all_records` — 36 == 36 ✓
- `test_all_current_plan_is_std` — every seed record's plan_id == "STD" ✓

## DEMO-02 Arithmetic Proof

Sarah Chen runs at exactly 500 kWh/month average (verified by Plan 01 module-level assert).

| Track | Formula | Result |
|-------|---------|--------|
| Current (STD) | 500 × 0.32 + 1.10 × 30.44 | $193.48/mo |
| Green (ECO) | 500 × 0.26 + 1.10 × 30.44 | $163.48/mo |
| Cheapest (VAL) | 500 × 0.21 + 1.10 × 30.44 | $138.48/mo |
| **Green saving** | 193.48 − 163.48 | **$30.00/mo** |
| **Cheapest saving** | 193.48 − 138.48 | **$55.00/mo** |

Supply charge (1.10 × 30.44 = $33.48/mo) is identical on all plans and cancels out — savings are purely rate-driven.

## Requirements Coverage

| Requirement | Test | Status |
|-------------|------|--------|
| DATA-01: 12-month billing history per customer | test_returns_12_months, test_twelve_months_per_customer | ✓ |
| DATA-03: usage stored in kWh (numeric) | test_usage_kwh_is_numeric | ✓ |
| DEMO-02: Green=$30, Cheapest=$55 for Sarah | test_flagship_persona_green_saving, test_flagship_persona_cheapest_saving | ✓ |
| SAV-03: no LLM in savings math path | simulate_savings_pure is pure Python, covered by unit tests | ✓ |
| V5 (STRIDE Tampering): input validation | test_rejects_malformed_customer_id (+ 3 more rejection tests) | ✓ |

## API Surface for Phase 2 (Agent Tools)

```python
# Pure helper — Phase 2 agent can call this offline for testing:
simulate_savings_pure(billing_history: list[dict], plans: list[dict]) -> dict
# Returns: {"green": {"plan_id", "plan_name", "saving_monthly", "saving_annual"},
#           "cheapest": {"plan_id", "plan_name", "saving_monthly", "saving_annual"}}

# Lambda entry points (Phase 2 agent tool wrappers):
get_billing_history(event: {"customer_id": str}, context) -> list[dict]  # 12 records sorted by month
simulate_savings(event: {"customer_id": str}, context) -> dict  # chains billing + savings
```

## Deviations

- **importlib used for test imports**: `from lambda.handler import ...` is a SyntaxError in Python because `lambda` is a keyword. Tests use `importlib.import_module("lambda.handler")` and access functions via the module object. This is documented in the plan's NOTE and is the expected fallback.
- No other deviations — all 29 tests pass, all acceptance criteria met.

## Self-Check: PASSED

- `pytest tests/ -v` → 29 passed, 0 failed
- `pytest tests/test_simulate_savings.py` → 11 passed
- `pytest tests/test_get_billing_history.py` → 9 passed
- `pytest tests/test_schema.py` → 9 passed
- DEMO-02 math verified: Green=$30.00, Cheapest=$55.00 for Sarah Chen (500 kWh avg)
- SAV-03: no LLM involvement in savings arithmetic path
- V5 input validation: 4 rejection paths tested (missing, non-string, malformed, empty)
- No AWS credentials required to run test suite
