# Requirements Document

## Introduction

Expand the agent's tool gallery from 4 tariff-math-centric tools to 8–10 tools that represent the breadth of a real Energy & Utilities CRM/OSS toolkit. The new tools cover outage awareness, bill-shock decomposition (replacing the boolean `detect_bill_shock`), AU-specific concession lookups, solar payback estimation, payment plan proposals, and callback scheduling. Each tool is deterministic and demo-safe (hardcoded/seeded data, no external API calls), preserving the "code does math, LLM narrates" contract (SAV-03). The richer tool set produces dramatically more informative reasoning traces and demonstrates the agent's ability to orchestrate multi-step workflows.

The existing `simulate_savings` and `get_billing_history` tools remain unchanged. The current boolean `detect_bill_shock` is replaced by `decompose_bill_shock` which provides a richer breakdown of bill-shock causes. The `get_hardship_flag` tool is retained but complemented by `lookup_concessions`. The `schedule_callback` tool is the first "action" tool (simulates a write) but remains demo-safe by returning a confirmation without persisting state.

The FourToolCapHook budget is raised to accommodate richer multi-tool traces (6–8 tool calls per invocation).

## Glossary

- **Tools_Lambda**: The Lambda function (`lambda/handler.py`) that handles all deterministic tool computations, invoked by the agent via `_lambda_client.invoke`.
- **Agent**: The Strands SDK agent (`agent/agent.py`) that orchestrates tool calls and composes narrative responses.
- **Persona**: A seeded customer profile with 12 months of billing history in DynamoDB (Sarah Chen CUST-001, Marcus Webb CUST-002, Elena Vasquez CUST-003, plus v3.0 personas CUST-004 through CUST-006).
- **Outage_Service**: The deterministic outage-status lookup module within Tools_Lambda that returns hardcoded outage data keyed by suburb.
- **Bill_Decomposer**: The pure-function module within Tools_Lambda that decomposes a bill-shock delta into rate-change, usage-change, and seasonal components.
- **Concession_Registry**: The deterministic lookup module within Tools_Lambda that returns AU-specific energy concessions and rebates for a customer.
- **Solar_Estimator**: The pure-function module within Tools_Lambda that estimates solar PV payback period and savings for a customer based on their usage profile.
- **Payment_Planner**: The pure-function module within Tools_Lambda that computes instalment amounts and schedules for hardship/payment-difficulty customers.
- **Callback_Scheduler**: The demo-safe action module within Tools_Lambda that returns a confirmation payload without persisting any state.
- **ToolCapHook**: The Strands `HookProvider` (currently `FourToolCapHook`) that enforces a per-invocation tool-call budget, to be raised from 4 to 8.
- **Reasoning_Trace**: The ordered list of `ReasoningTraceEntry` objects (tool name + deterministic summary) surfaced to the UI for observability.
- **Seed_Data**: Hardcoded persona-specific data embedded in the Tools_Lambda or seed data module, enabling deterministic tool responses without external dependencies.

## Requirements

### Requirement 1: Outage Status Lookup

**User Story:** As a call-centre agent, I want to check current outages near a customer's suburb, so that I can proactively inform them about supply disruptions affecting their area.

#### Acceptance Criteria

1. WHEN `check_outage_status` is invoked with a valid suburb name, THE Outage_Service SHALL return a structured response containing: `suburb` (string), `has_outage` (boolean), `outage_type` (string, one of "planned", "unplanned", "none"), `affected_postcodes` (list of strings), `estimated_restoration` (ISO datetime string or null), and `customers_affected` (integer).
2. WHEN `check_outage_status` is invoked with a suburb that has no active outage in the seed data, THE Outage_Service SHALL return `has_outage: false` and `outage_type: "none"` with empty `affected_postcodes` and null `estimated_restoration`.
3. THE Outage_Service SHALL provide hardcoded outage seed data for at least 3 suburbs, with at least one planned outage and one unplanned outage scenario.
4. THE Outage_Service SHALL be deterministic — identical inputs SHALL always produce identical outputs regardless of invocation time.
5. IF `check_outage_status` is invoked with an empty or non-string suburb parameter, THEN THE Tools_Lambda SHALL return an error response with a descriptive message.

### Requirement 2: Bill Shock Decomposition

**User Story:** As a call-centre agent, I want to understand why a customer's bill spiked, so that I can explain the specific contributing factors (rate change vs usage change vs seasonal pattern) rather than just flagging a binary anomaly.

#### Acceptance Criteria

1. WHEN `decompose_bill_shock` is invoked with a valid customer_id, THE Bill_Decomposer SHALL return a structured response containing: `customer_id` (string), `is_shock` (boolean), `shock_month` (string, YYYY-MM), `total_delta_dollars` (float), `rate_change_component` (float), `usage_change_component` (float), `seasonal_component` (float), and `explanation_factors` (list of strings describing each non-zero component).
2. THE Bill_Decomposer SHALL compute the decomposition such that `rate_change_component + usage_change_component + seasonal_component` equals `total_delta_dollars` within a tolerance of $0.01.
3. WHEN the customer has no bill-shock anomaly (delta below threshold), THE Bill_Decomposer SHALL return `is_shock: false` with all component values set to their computed amounts and `total_delta_dollars` reflecting the actual (sub-threshold) delta.
4. THE Bill_Decomposer SHALL replace the existing boolean `detect_bill_shock` tool — the old tool's action route in the Lambda dispatcher SHALL be removed or aliased to the new decomposition.
5. THE Bill_Decomposer SHALL use the same billing history and threshold logic as the existing `detect_bill_shock_pure` function for identifying the shock month, extending it with component attribution.
6. FOR ALL valid billing histories with at least 2 months, decomposing the bill shock and summing the three components SHALL equal the total delta (round-trip property: `rate + usage + seasonal == total_delta` within $0.01).

### Requirement 3: Concession Lookup

**User Story:** As a call-centre agent, I want to see which AU-specific energy concessions and rebates a customer is eligible for, so that I can ensure they are receiving all available financial support.

#### Acceptance Criteria

1. WHEN `lookup_concessions` is invoked with a valid customer_id, THE Concession_Registry SHALL return a structured response containing: `customer_id` (string), `eligible_concessions` (list of concession objects), and `total_annual_value` (float, sum of all concession annual values).
2. THE Concession_Registry SHALL model each concession object with: `name` (string), `type` (string, one of "energy_concession", "life_support", "low_income", "medical_cooling", "veterans"), `annual_value` (float), `applied` (boolean indicating if already active on account), and `description` (string).
3. THE Concession_Registry SHALL provide persona-specific concession seed data: at least one persona with active concessions, at least one with eligible-but-not-applied concessions, and at least one with no eligible concessions.
4. THE Concession_Registry SHALL be deterministic — identical customer_id inputs SHALL always produce identical concession lists.
5. IF `lookup_concessions` is invoked with a customer_id that does not match the `^CUST-\d{3,6}$` pattern, THEN THE Tools_Lambda SHALL return an error response with a descriptive message.

### Requirement 4: Solar Payback Estimation

**User Story:** As a call-centre agent, I want to estimate the solar PV payback period for high-usage non-solar customers, so that I can have an informed conversation about whether solar investment makes sense for their household.

#### Acceptance Criteria

1. WHEN `estimate_solar_payback` is invoked with a valid customer_id, THE Solar_Estimator SHALL return a structured response containing: `customer_id` (string), `eligible` (boolean), `avg_monthly_usage_kwh` (float), `estimated_system_size_kw` (float), `estimated_daily_generation_kwh` (float), `annual_savings_dollars` (float), `system_cost_dollars` (float), `payback_years` (float), and `recommendation` (string, one of "strong_candidate", "moderate_candidate", "not_recommended").
2. WHEN the customer already has solar (identified by non-zero `export_kwh` in billing history), THE Solar_Estimator SHALL return `eligible: false` with a `reason` field explaining the customer already has solar installed.
3. THE Solar_Estimator SHALL compute `payback_years` as `system_cost_dollars / annual_savings_dollars`, rounded to one decimal place.
4. THE Solar_Estimator SHALL determine `recommendation` based on payback period: "strong_candidate" for payback ≤ 5 years, "moderate_candidate" for 5–8 years, "not_recommended" for > 8 years.
5. THE Solar_Estimator SHALL use the customer's average monthly usage from billing history to size the system and estimate generation, using hardcoded AU-average solar irradiance constants.
6. FOR ALL customers with `eligible: true`, THE Solar_Estimator SHALL produce `payback_years` equal to `system_cost_dollars / annual_savings_dollars` rounded to one decimal place (round-trip arithmetic property).

### Requirement 5: Payment Plan Proposal

**User Story:** As a call-centre agent, I want to propose a payment plan for customers experiencing payment difficulty, so that I can offer concrete instalment options during the call.

#### Acceptance Criteria

1. WHEN `propose_payment_plan` is invoked with a valid customer_id and instalments count (integer, 2–12), THE Payment_Planner SHALL return a structured response containing: `customer_id` (string), `outstanding_balance` (float), `instalment_count` (integer), `instalment_amount` (float), `total_payable` (float), `interest_free` (boolean), and `schedule` (list of objects with `due_date` (string, YYYY-MM-DD) and `amount` (float)).
2. THE Payment_Planner SHALL compute `instalment_amount` as `outstanding_balance / instalment_count`, rounded to 2 decimal places, with any rounding remainder added to the final instalment.
3. THE Payment_Planner SHALL set `interest_free: true` for all plans (demo-safe — no interest calculation complexity).
4. THE Payment_Planner SHALL generate `schedule` entries with monthly due dates starting from a hardcoded "today" date (demo determinism).
5. IF `propose_payment_plan` is invoked with an instalments value outside the range 2–12, THEN THE Tools_Lambda SHALL return an error response with a descriptive message.
6. FOR ALL valid payment plans, summing all `schedule[].amount` values SHALL equal `outstanding_balance` exactly (conservation-of-money invariant).
7. THE Payment_Planner SHALL use persona-specific outstanding balance seed data (e.g., hardship persona CUST-006 has a balance, low-usage personas have zero or small balances).

### Requirement 6: Callback Scheduling

**User Story:** As a call-centre agent, I want to schedule a callback for a customer, so that I can commit to a follow-up action during the call without leaving the agent interface.

#### Acceptance Criteria

1. WHEN `schedule_callback` is invoked with a valid customer_id, `when` (ISO datetime string), and `reason` (string), THE Callback_Scheduler SHALL return a structured confirmation containing: `customer_id` (string), `callback_id` (string, deterministic UUID based on inputs), `scheduled_time` (string, echoing the `when` input), `reason` (string, echoing the input), and `status` (string, always "confirmed").
2. THE Callback_Scheduler SHALL NOT persist any state — the confirmation is a demo-safe no-op that simulates a successful scheduling action.
3. THE Callback_Scheduler SHALL generate a deterministic `callback_id` from the input parameters (e.g., UUID5 from customer_id + when + reason) so that identical inputs always produce the same confirmation.
4. IF `schedule_callback` is invoked with a `when` value that is not a valid ISO datetime string, THEN THE Tools_Lambda SHALL return an error response with a descriptive message.
5. IF `schedule_callback` is invoked with an empty `reason` string, THEN THE Tools_Lambda SHALL return an error response with a descriptive message.

### Requirement 7: Tool Cap Adjustment

**User Story:** As a system operator, I want the per-invocation tool-call budget raised to accommodate richer multi-tool traces, so that the agent can orchestrate 6–8 tool calls in a single turn without hitting the cap.

#### Acceptance Criteria

1. THE ToolCapHook SHALL enforce a budget of 8 tool calls per invocation (raised from 4).
2. WHEN the tool budget is exhausted at 8 calls, THE ToolCapHook SHALL cancel the agent via the existing `event.agent.cancel()` mechanism.
3. THE ToolCapHook SHALL continue to use instance-level state with a `reset()` method called at the start of each invocation.
4. THE ToolCapHook SHALL coexist with the StreamingTraceHook on the same Agent instance without interference.

### Requirement 8: Tool Registration and Agent Integration

**User Story:** As a backend developer, I want all new tools registered with the Strands agent using the `@tool` decorator pattern, so that the LLM can discover and invoke them based on intent.

#### Acceptance Criteria

1. THE Agent SHALL register all new tools (`check_outage_status`, `decompose_bill_shock`, `lookup_concessions`, `estimate_solar_payback`, `propose_payment_plan`, `schedule_callback`) using the Strands `@tool` decorator with clear docstrings.
2. EACH tool's docstring SHALL describe its purpose, parameters, and return shape clearly enough for the LLM to select the correct tool based on customer intent.
3. THE Agent SHALL invoke each new tool via `_lambda_client.invoke` to the Tools_Lambda (same pattern as existing `detect_bill_shock`, `get_billing_history`, `get_hardship_flag` tools).
4. THE Tools_Lambda action dispatcher SHALL route each new action name to its corresponding pure-function handler.
5. EACH new tool SHALL follow the SAV-03 contract — all arithmetic and data lookup happens in the Tools_Lambda; the LLM narrates the structured result without performing any computation.

### Requirement 9: Reasoning Trace Integration

**User Story:** As a call-centre operator, I want to see summaries of all new tool calls in the reasoning trace, so that I can follow the agent's multi-step investigation.

#### Acceptance Criteria

1. THE Reasoning_Trace system SHALL include deterministic summary formatters for each new tool in `agent/reasoning/summaries.py`.
2. EACH new tool's summary formatter SHALL produce a human-readable one-liner containing the key data points from the tool result (digits, currency, dates permitted per D-11 exemption).
3. THE `_TRACE_TOOLS` set in `agent/agent.py` SHALL be extended to include all new tool names.
4. WHEN a new tool completes during agent execution, THE StreamingTraceHook SHALL emit a `trace_step` event with the tool's deterministic summary.

### Requirement 10: Seed Data for New Tools

**User Story:** As a developer, I want persona-specific seed data for all new tools, so that each tool produces meaningful, differentiated responses across the 3 core personas.

#### Acceptance Criteria

1. THE Seed_Data SHALL provide outage data for suburbs associated with each persona (e.g., Sarah's suburb has no outage, Elena's suburb has a planned outage).
2. THE Seed_Data SHALL provide concession eligibility per persona: Elena (CUST-003, seasonal/low-income) SHALL have eligible concessions, Marcus (CUST-002) SHALL have no concessions, Sarah (CUST-001) SHALL have one active concession.
3. THE Seed_Data SHALL provide outstanding balance data per persona for payment plan proposals: CUST-006 (hardship) SHALL have a significant balance, CUST-001 and CUST-002 SHALL have zero or minimal balances.
4. THE Seed_Data SHALL provide suburb mappings per persona for the outage lookup tool.
5. THE Seed_Data SHALL be embedded within the Tools_Lambda module (not requiring DynamoDB reads) to maintain demo-safety and determinism.
6. THE Seed_Data SHALL be consistent with existing persona characteristics (e.g., CUST-004 already has solar so `estimate_solar_payback` returns `eligible: false`).

