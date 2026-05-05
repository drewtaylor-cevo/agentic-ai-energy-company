# Tasks: Expanded Tool Gallery

## Task 1: Create Seed Data Module

- [x] 1.1 Create `infrastructure/seed_data/tool_seed_data.py` with outage data for at least 3 suburbs (one planned, one unplanned, one no-outage)
- [x] 1.2 Add concession seed data per persona: CUST-001 (one active), CUST-002 (none), CUST-003 (eligible but not applied)
- [x] 1.3 Add outstanding balance data per persona: CUST-006 ($890), CUST-001 ($0), CUST-002 ($45.50), CUST-003 ($120)
- [x] 1.4 Add suburb-to-customer mapping (SUBURB_MAP) for outage lookups
- [x] 1.5 Add solar constants (cost_per_kw, daily_generation_per_kw, self_consumption_ratio, feed_in_tariff, retail_rate)
- [x] 1.6 Add import-time assertions validating seed data invariants (at least 3 suburbs, persona differentiation, CUST-004 has solar)

## Task 2: Implement Pure Functions in Lambda Handler

- [x] 2.1 Implement `check_outage_status_pure(suburb: str)` — validates suburb is non-empty string, returns outage data from seed or no-outage default
- [x] 2.2 Implement `decompose_bill_shock_pure(billing_history, threshold=0.30, rate_per_kwh=0.32, daily_supply=1.10)` — extends existing `detect_bill_shock_pure` with rate/usage/seasonal component attribution
- [x] 2.3 Implement `lookup_concessions_pure(customer_id: str)` — validates customer_id, returns concession list and total_annual_value from seed data
- [x] 2.4 Implement `estimate_solar_payback_pure(customer_id: str, billing_history)` — checks solar eligibility (export_kwh > 0 means ineligible), computes system size, generation, savings, payback, recommendation
- [x] 2.5 Implement `propose_payment_plan_pure(customer_id: str, instalments: int, outstanding_balance: float)` — validates instalments 2–12, computes schedule with rounding remainder on final instalment
- [x] 2.6 Implement `schedule_callback_pure(customer_id: str, when: str, reason: str)` — validates ISO datetime and non-empty reason, generates deterministic UUID5 callback_id

## Task 3: Extend Lambda Action Dispatcher

- [x] 3.1 Add action routes for `check_outage_status`, `decompose_bill_shock`, `lookup_concessions`, `estimate_solar_payback`, `propose_payment_plan`, `schedule_callback` in `lambda/handler.py::handler()`
- [x] 3.2 Alias existing `detect_bill_shock` route to the new `decompose_bill_shock` handler (backward compatibility)
- [x] 3.3 Add top-level error handling in dispatcher to catch ValueError and return `{"error": True, "message": str(e)}` for all routes

## Task 4: Register New Tools in Agent

- [x] 4.1 Add `@tool` wrapper for `check_outage_status(suburb: str)` with clear docstring describing purpose, params, and return shape
- [x] 4.2 Add `@tool` wrapper for `decompose_bill_shock(customer_id: str)` — replaces the existing `detect_bill_shock` tool registration
- [x] 4.3 Add `@tool` wrapper for `lookup_concessions(customer_id: str)` with docstring
- [x] 4.4 Add `@tool` wrapper for `estimate_solar_payback(customer_id: str)` with docstring
- [x] 4.5 Add `@tool` wrapper for `propose_payment_plan(customer_id: str, instalments: int)` with docstring
- [x] 4.6 Add `@tool` wrapper for `schedule_callback(customer_id: str, when: str, reason: str)` with docstring
- [x] 4.7 Update the Agent `tools=[...]` list to include all new tools

## Task 5: Raise Tool Cap Budget

- [x] 5.1 Change `FourToolCapHook(budget=4)` to `FourToolCapHook(budget=8)` in `agent/agent.py`
- [x] 5.2 Update any tests that assert budget=4 to expect budget=8

## Task 6: Add Reasoning Trace Summaries

- [x] 6.1 Add `summary_check_outage_status(result)` to `agent/reasoning/summaries.py`
- [x] 6.2 Add `summary_decompose_bill_shock(result)` to `agent/reasoning/summaries.py`
- [x] 6.3 Add `summary_lookup_concessions(result)` to `agent/reasoning/summaries.py`
- [x] 6.4 Add `summary_estimate_solar_payback(result)` to `agent/reasoning/summaries.py`
- [x] 6.5 Add `summary_propose_payment_plan(result)` to `agent/reasoning/summaries.py`
- [x] 6.6 Add `summary_schedule_callback(result)` to `agent/reasoning/summaries.py`
- [x] 6.7 Extend `_TRACE_TOOLS` set in `agent/agent.py` to include all new tool names
- [x] 6.8 Extend `_summarise_tool_result()` dispatch in `agent/agent.py` to call the new formatters

## Task 7: Property-Based Tests

- [x] 7.1 Write property test: `test_bill_shock_decomposition_sum` — for any billing history (2–12 months, usage 50–1000 kWh), verify rate + usage + seasonal == total_delta within $0.01
- [x] 7.2 Write property test: `test_bill_shock_backward_compat` — for any billing history, verify is_shock and shock_month match existing detect_bill_shock_pure
- [x] 7.3 Write property test: `test_solar_payback_arithmetic` — for eligible customers, verify payback_years == round(system_cost / annual_savings, 1)
- [x] 7.4 Write property test: `test_solar_recommendation_threshold` — for eligible customers, verify recommendation matches threshold rules
- [x] 7.5 Write property test: `test_payment_plan_conservation` — for any balance (1–10000) and instalments (2–12), verify sum(schedule.amount) == balance exactly
- [x] 7.6 Write property test: `test_payment_plan_structure` — verify schedule length == instalment_count, interest_free == True, dates monthly-spaced
- [x] 7.7 Write property test: `test_callback_deterministic_id` — same inputs produce same callback_id, different inputs produce different callback_id
- [x] 7.8 Write property test: `test_tool_cap_budget_enforcement` — hook allows exactly 8 calls then cancels; reset restores budget
- [x] 7.9 Write property test: `test_invalid_input_errors` — invalid inputs to each tool produce error responses

## Task 8: Unit Tests

- [x] 8.1 Write unit tests for each persona's outage status (Sarah suburb=no outage, Elena suburb=planned outage)
- [x] 8.2 Write unit tests for concession lookup per persona (Marcus=none, Elena=eligible-not-applied, Sarah=active)
- [x] 8.3 Write unit test for solar ineligibility of CUST-004 (already has solar)
- [x] 8.4 Write unit tests for payment plan with CUST-006 (hardship, $890 balance, various instalment counts)
- [x] 8.5 Write unit tests for callback confirmation shape and deterministic ID
- [x] 8.6 Write unit tests for all new summary formatters (verify output contains key data points)
- [x] 8.7 Write unit tests for action dispatcher routing of all new actions
- [x] 8.8 Write integration test verifying ToolCapHook + StreamingTraceHook coexistence
