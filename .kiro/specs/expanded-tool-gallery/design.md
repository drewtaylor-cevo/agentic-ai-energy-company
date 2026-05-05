# Design Document: Expanded Tool Gallery

## Overview

This feature expands the agent's tool gallery from 4 tariff-math-centric tools to 10 tools representing a real Energy & Utilities CRM/OSS toolkit. The new tools cover outage awareness, bill-shock decomposition (replacing the boolean `detect_bill_shock`), AU-specific concession lookups, solar payback estimation, payment plan proposals, and callback scheduling.

Each tool is deterministic and demo-safe — hardcoded/seeded data, no external API calls. The existing "code does math, LLM narrates" contract (SAV-03) is preserved. The ToolCapHook budget is raised from 4 to 8 to accommodate richer multi-tool traces.

### Design Decisions

1. **Pure functions in Tools_Lambda** — All new tool logic lives as pure functions in `lambda/handler.py` (or imported modules), invoked via the existing action dispatcher. This preserves SAV-03 and keeps the agent's `@tool` wrappers thin.
2. **Seed data embedded in Lambda** — New tool seed data is embedded in a new module (`infrastructure/seed_data/tool_seed_data.py`) and imported by the Lambda handler at cold-start. No DynamoDB reads for the new tools — determinism by construction.
3. **Backward-compatible `detect_bill_shock` route** — The existing `detect_bill_shock` action route is aliased to the new `decompose_bill_shock` handler, so existing agent code continues to work during migration.
4. **Budget=8 is a constructor parameter change** — The `FourToolCapHook` class already accepts a `budget` parameter; the agent instantiation simply changes `budget=4` to `budget=8`. The class name remains `FourToolCapHook` for git-blame continuity (renaming is cosmetic and deferred).

## Architecture

```mermaid
graph TD
    A[Strands Agent] -->|@tool wrappers| B[_lambda_client.invoke]
    B --> C[Tools Lambda handler]
    C -->|action dispatcher| D{Route by action}
    D --> E[check_outage_status_pure]
    D --> F[decompose_bill_shock_pure]
    D --> G[lookup_concessions_pure]
    D --> H[estimate_solar_payback_pure]
    D --> I[propose_payment_plan_pure]
    D --> J[schedule_callback_pure]
    D --> K[simulate_savings_pure - existing]
    D --> L[get_billing_history - existing]
    D --> M[get_hardship_flag_pure - existing]
    
    E --> N[Outage Seed Data]
    F --> O[Billing History + Decomposition Logic]
    G --> P[Concession Seed Data]
    H --> Q[Solar Constants + Billing History]
    I --> R[Balance Seed Data + Schedule Logic]
    J --> S[UUID5 Deterministic ID]
```

### Request Flow (New Tools)

```
Agent @tool wrapper → _lambda_client.invoke({"action": "<tool_name>", ...})
    → Tools Lambda handler() → action dispatcher → pure function
    → structured dict response → agent narrates result
```

## Components and Interfaces

### 1. New Pure Functions (lambda/handler.py or imported modules)

| Function | Action Route | Inputs | Output Shape |
|----------|-------------|--------|--------------|
| `check_outage_status_pure` | `check_outage_status` | `suburb: str` | `{suburb, has_outage, outage_type, affected_postcodes, estimated_restoration, customers_affected}` |
| `decompose_bill_shock_pure` | `decompose_bill_shock` | `customer_id: str` | `{customer_id, is_shock, shock_month, total_delta_dollars, rate_change_component, usage_change_component, seasonal_component, explanation_factors}` |
| `lookup_concessions_pure` | `lookup_concessions` | `customer_id: str` | `{customer_id, eligible_concessions: [{name, type, annual_value, applied, description}], total_annual_value}` |
| `estimate_solar_payback_pure` | `estimate_solar_payback` | `customer_id: str` | `{customer_id, eligible, avg_monthly_usage_kwh, estimated_system_size_kw, estimated_daily_generation_kwh, annual_savings_dollars, system_cost_dollars, payback_years, recommendation}` |
| `propose_payment_plan_pure` | `propose_payment_plan` | `customer_id: str, instalments: int` | `{customer_id, outstanding_balance, instalment_count, instalment_amount, total_payable, interest_free, schedule: [{due_date, amount}]}` |
| `schedule_callback_pure` | `schedule_callback` | `customer_id: str, when: str, reason: str` | `{customer_id, callback_id, scheduled_time, reason, status}` |

### 2. New @tool Wrappers (agent/agent.py)

Each new tool follows the existing pattern:

```python
@tool
def check_outage_status(suburb: str) -> dict:
    """Check current outage status for a suburb..."""
    resp = _lambda_client.invoke(
        FunctionName=_TOOLS_LAMBDA_ARN,
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "check_outage_status", "suburb": suburb}).encode(),
    )
    return json.loads(resp["Payload"].read())
```

### 3. Seed Data Module (infrastructure/seed_data/tool_seed_data.py)

New module providing hardcoded data for the new tools:
- `OUTAGE_DATA`: dict keyed by suburb name → outage info
- `CONCESSION_DATA`: dict keyed by customer_id → concession list
- `BALANCE_DATA`: dict keyed by customer_id → outstanding balance
- `SUBURB_MAP`: dict keyed by customer_id → suburb name
- Solar constants (AU-average irradiance, system cost per kW, etc.)

### 4. Reasoning Trace Summaries (agent/reasoning/summaries.py)

Six new summary formatters following the existing pattern:
- `summary_check_outage_status(result)` → e.g. "Planned outage in Marrickville: ~500 customers, restoration 2025-07-15T14:00"
- `summary_decompose_bill_shock(result)` → e.g. "Bill shock +$45.20 (2025-10): rate +$12.00, usage +$28.00, seasonal +$5.20"
- `summary_lookup_concessions(result)` → e.g. "3 concessions eligible, $420.00/yr total (1 not yet applied)"
- `summary_estimate_solar_payback(result)` → e.g. "Solar: 6.5kW system, $1,200/yr savings, 5.2yr payback (moderate_candidate)"
- `summary_propose_payment_plan(result)` → e.g. "Payment plan: $450.00 over 6 instalments ($75.00/mo), interest-free"
- `summary_schedule_callback(result)` → e.g. "Callback confirmed: 2025-07-20T10:00 (billing query)"

### 5. ToolCapHook Budget Change

In `agent/agent.py`, the instantiation changes from:
```python
_four_tool_cap = FourToolCapHook(budget=4)
```
to:
```python
_four_tool_cap = FourToolCapHook(budget=8)
```

## Data Models

### Outage Seed Data Structure

```python
OUTAGE_DATA = {
    "Marrickville": {
        "has_outage": True,
        "outage_type": "planned",
        "affected_postcodes": ["2204", "2205"],
        "estimated_restoration": "2025-07-15T14:00:00+10:00",
        "customers_affected": 450,
    },
    "Parramatta": {
        "has_outage": True,
        "outage_type": "unplanned",
        "affected_postcodes": ["2150", "2151", "2152"],
        "estimated_restoration": "2025-07-12T18:00:00+10:00",
        "customers_affected": 1200,
    },
    "Bondi": {
        "has_outage": False,
        "outage_type": "none",
        "affected_postcodes": [],
        "estimated_restoration": None,
        "customers_affected": 0,
    },
    # ... additional suburbs
}
```

### Concession Data Structure

```python
CONCESSION_DATA = {
    "CUST-001": {
        "eligible_concessions": [
            {
                "name": "NSW Energy Rebate",
                "type": "energy_concession",
                "annual_value": 285.00,
                "applied": True,
                "description": "Annual rebate for eligible NSW households",
            }
        ],
    },
    "CUST-002": {"eligible_concessions": []},
    "CUST-003": {
        "eligible_concessions": [
            {
                "name": "Low Income Household Rebate",
                "type": "low_income",
                "annual_value": 315.00,
                "applied": False,
                "description": "Rebate for Health Care Card holders",
            },
            # ...
        ],
    },
}
```

### Balance Data Structure

```python
BALANCE_DATA = {
    "CUST-001": 0.00,
    "CUST-002": 45.50,
    "CUST-003": 120.00,
    "CUST-006": 890.00,  # Hardship persona — significant balance
}
```

### Solar Constants

```python
SOLAR_CONSTANTS = {
    "cost_per_kw": 1200.00,          # AUD per kW installed
    "daily_generation_per_kw": 4.2,  # kWh/kW/day (AU average irradiance)
    "self_consumption_ratio": 0.70,  # 70% self-consumed, 30% exported
    "feed_in_tariff": 0.05,          # $/kWh export credit
    "retail_rate": 0.32,             # $/kWh avoided grid purchase (matches STD_RATE)
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Bill Shock Decomposition Sum Invariant

*For any* valid billing history with at least 2 months, when `decompose_bill_shock_pure` is invoked, the sum `rate_change_component + usage_change_component + seasonal_component` SHALL equal `total_delta_dollars` within a tolerance of $0.01.

**Validates: Requirements 2.2, 2.6**

### Property 2: Bill Shock Backward Compatibility

*For any* valid customer_id with billing history, the `is_shock` and `shock_month` fields returned by `decompose_bill_shock_pure` SHALL match the corresponding fields returned by the existing `detect_bill_shock_pure` function when given the same billing history.

**Validates: Requirements 2.5**

### Property 3: Solar Payback Arithmetic

*For any* customer where `estimate_solar_payback_pure` returns `eligible: true`, the `payback_years` field SHALL equal `round(system_cost_dollars / annual_savings_dollars, 1)`.

**Validates: Requirements 4.3, 4.6**

### Property 4: Solar Recommendation Threshold Classification

*For any* customer where `estimate_solar_payback_pure` returns `eligible: true`, the `recommendation` field SHALL be "strong_candidate" when `payback_years <= 5.0`, "moderate_candidate" when `5.0 < payback_years <= 8.0`, and "not_recommended" when `payback_years > 8.0`.

**Validates: Requirements 4.4**

### Property 5: Payment Plan Conservation of Money

*For any* valid payment plan (customer with outstanding balance > 0, instalments in range 2–12), the sum of all `schedule[].amount` values SHALL equal `outstanding_balance` exactly (zero tolerance — no money created or destroyed).

**Validates: Requirements 5.6**

### Property 6: Payment Plan Schedule Structure

*For any* valid payment plan request with `instalment_count` N, the response SHALL contain exactly N schedule entries, `interest_free` SHALL be `true`, and schedule dates SHALL be spaced exactly one month apart starting from the hardcoded "today" date.

**Validates: Requirements 5.1, 5.3, 5.4**

### Property 7: Callback Deterministic ID

*For any* set of valid inputs (customer_id, when, reason), calling `schedule_callback_pure` twice with identical inputs SHALL produce identical `callback_id` values. Furthermore, changing any single input SHALL produce a different `callback_id`.

**Validates: Requirements 6.3**

### Property 8: Tool Cap Budget Enforcement

*For any* sequence of tool calls on an agent with `FourToolCapHook(budget=8)`, the hook SHALL allow exactly 8 calls before cancelling the agent. After `reset()`, the budget SHALL be fully restored.

**Validates: Requirements 7.1, 7.2**

### Property 9: Invalid Input Error Handling

*For any* non-string or empty suburb passed to `check_outage_status_pure`, *for any* string not matching `^CUST-\d{3,6}$` passed to `lookup_concessions_pure`, *for any* instalment count outside 2–12 passed to `propose_payment_plan_pure`, and *for any* non-ISO-datetime string passed to `schedule_callback_pure`, the respective function SHALL return an error response (or raise ValueError) rather than a success payload.

**Validates: Requirements 1.5, 3.5, 5.5, 6.4**

## Error Handling

### Input Validation

All new pure functions validate inputs before processing:
- **Customer ID**: Reuse existing `_validate_customer_id()` regex (`^CUST-\d{3,6}$`)
- **Suburb**: Must be a non-empty string; unknown suburbs return the "no outage" response (not an error)
- **Instalments**: Must be an integer in range 2–12
- **ISO datetime**: Validated via `datetime.fromisoformat()` — raises on invalid format
- **Reason string**: Must be non-empty after stripping whitespace

### Error Response Shape

Errors follow the existing Lambda pattern — raise `ValueError` with a descriptive message. The Lambda handler's top-level `try/except` (to be added) catches these and returns:

```python
{"error": True, "message": str(e)}
```

### Agent-Level Error Handling

The agent's `@tool` wrappers do not catch exceptions — errors propagate to the Strands framework which surfaces them as tool-result errors. The existing D-04 `except Exception` in `invoke()` catches any unhandled failure and routes through the fallback path.

## Testing Strategy

### Property-Based Tests (Hypothesis)

The project already uses Hypothesis (`.hypothesis/` directory present). Each correctness property maps to a single Hypothesis test with `@settings(max_examples=100)`.

**Library**: `hypothesis` (already in requirements-dev.txt)

**Configuration**: Minimum 100 iterations per property test.

**Tag format**: Each test includes a comment: `# Feature: expanded-tool-gallery, Property N: <property_text>`

Properties to implement:
1. `test_bill_shock_decomposition_sum` — Generate random billing histories (2–12 months, usage 50–1000 kWh), verify component sum == total_delta within $0.01
2. `test_bill_shock_backward_compat` — Generate billing histories, verify is_shock/shock_month match detect_bill_shock_pure
3. `test_solar_payback_arithmetic` — For eligible customers, verify payback_years == round(cost/savings, 1)
4. `test_solar_recommendation_threshold` — For eligible customers, verify recommendation matches threshold rules
5. `test_payment_plan_conservation` — Generate balance (1–10000) and instalments (2–12), verify sum(schedule.amount) == balance
6. `test_payment_plan_structure` — Verify schedule length, interest_free, and date spacing
7. `test_callback_deterministic_id` — Generate random inputs, verify idempotence and uniqueness
8. `test_tool_cap_budget` — Simulate N tool calls, verify cancellation at exactly 8
9. `test_invalid_input_errors` — Generate invalid inputs per tool, verify error responses

### Unit Tests (pytest)

Example-based tests for:
- Each persona's expected outage status (Sarah=no outage, Elena=planned outage)
- Concession lookup per persona (Marcus=none, Elena=eligible)
- Solar ineligibility for CUST-004 (already has solar)
- Payment plan for CUST-006 (hardship, significant balance)
- Callback confirmation shape
- Summary formatter output for each tool
- Action dispatcher routing for all new actions

### Integration Tests

- End-to-end Lambda handler invocation with each new action
- Agent tool registration verification (all tools discoverable)
- StreamingTraceHook emits trace_step for new tools
- ToolCapHook + StreamingTraceHook coexistence on same Agent instance
