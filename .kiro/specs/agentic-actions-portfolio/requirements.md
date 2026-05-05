# Requirements Document

## Introduction

Evolve the Customer Tariff demo from a read-only advisor into an agentic actor with portfolio awareness. This spec covers three thematically connected features:

1. **Agent-as-Actor (AGENT-04):** Promote the agent from advisor to actor by adding confirmable actions (tariff switch, SMS follow-up, payment-plan offer) that the rep approves with one click. Frame as "agent prepares, human approves."

2. **Bill-Shock Root-Cause Decomposition:** Replace the current `detect_bill_shock` → `{is_shock, delta_dollars}` surface with a multi-tool chain that returns a human-readable breakdown attributing the bill increase to rate changes, usage spikes, seasonal variation, and billing-day differences. This is what energy customers actually want explained.

3. **Retention Queue / Cohort Landing Page:** Replace the empty state with a portfolio-level view ("5 customers at risk today") ranked by churn probability or bill-shock signal across all seed personas. Click → full agent flow. Demonstrates the agent works at portfolio scale, not just on a known ID.

All changes preserve existing invariants: SAV-03 (LLM never does arithmetic), REC-03 (both tracks always returned), D-04 (never-500), D-15 (narrative dual-gate), and the frozen `demo-v2.0` lockfiles. Changes build on top of the existing stacks, not modify them.

## Glossary

- **Action_Queue**: A pending-actions data structure (DynamoDB or in-memory) that stores agent-prepared actions awaiting rep confirmation. Each entry has a type, payload, status (pending/confirmed/rejected), and expiry.
- **Confirmable_Action**: An action the agent prepares and queues for the rep to approve with a single click. Types include tariff_switch, send_sms, and payment_plan_offer.
- **Action_Card**: A UI component rendered below the recommendation cards that displays a pending Confirmable_Action with a one-click "Confirm" button and a "Dismiss" button.
- **Bill_Shock_Decomposition**: The enriched output of the bill-shock analysis chain that attributes the total dollar delta to named contributing factors with percentage weights and human-readable explanations.
- **Contributing_Factor**: A single named component of a bill-shock decomposition (e.g., rate_increase, usage_spike, seasonal_variation, billing_day_difference) with a dollar amount and percentage of total.
- **Decomposition_Chain**: The multi-tool sequence (get_billing_history → detect_bill_shock → decompose_bill_shock) that produces the full Bill_Shock_Decomposition.
- **Retention_Queue**: A portfolio-level view showing all seed personas ranked by risk signal (churn probability or bill-shock magnitude), displayed when no customer is selected.
- **Risk_Signal**: A composite score derived from bill-shock detection, usage trend, and hardship flag that ranks customers by retention urgency.
- **Cohort_Card**: A UI component in the Retention_Queue that shows one customer's ID, risk signal summary, and a click-to-investigate affordance.
- **Tools_Lambda**: The existing deterministic computation Lambda (`lambda/handler.py`) that handles all arithmetic (SAV-03).
- **Agent**: The Strands SDK agent (`agent/agent.py`) running in the Bedrock AgentCore container.
- **FourToolCapHook**: The existing Strands HookProvider that enforces a per-invocation tool-call budget.
- **API_Lambda**: The API Gateway proxy Lambda (`api_lambda/handler.py`) that routes requests to the AgentCore runtime.

## Requirements

### Requirement 1: Agent-Prepared Tariff Switch Action

**User Story:** As a call-centre rep, I want the agent to prepare a tariff switch so that I can confirm it with one click instead of navigating a separate system.

#### Acceptance Criteria

1. WHEN the agent produces a recommendation for a customer, THE Agent SHALL also produce a `tariff_switch` Confirmable_Action containing the recommended plan_id, customer_id, effective_date, and estimated_saving_monthly.
2. THE Tools_Lambda SHALL expose a `queue_action` pure function that validates and stores a Confirmable_Action in the Action_Queue with status `pending` and a TTL of 24 hours.
3. WHEN the rep clicks "Confirm" on a tariff_switch Action_Card, THE API_Lambda SHALL invoke the Tools_Lambda `confirm_action` endpoint, transitioning the action status from `pending` to `confirmed`.
4. WHEN the rep clicks "Dismiss" on an Action_Card, THE API_Lambda SHALL invoke the Tools_Lambda `dismiss_action` endpoint, transitioning the action status from `pending` to `rejected`.
5. IF a Confirmable_Action has expired (past TTL), THEN THE API_Lambda SHALL return an error indicating the action is no longer valid and THE UI SHALL display an expiry notice.
6. THE Confirmable_Action payload SHALL contain only data already produced by the deterministic savings engine — the LLM SHALL NOT generate or modify any numeric fields in the action payload (SAV-03 preserved).

### Requirement 2: Agent-Prepared SMS Follow-Up Action

**User Story:** As a call-centre rep, I want the agent to draft an SMS follow-up message so that I can send it to the customer with one click after our call.

#### Acceptance Criteria

1. WHEN the agent produces a recommendation, THE Agent SHALL produce a `send_sms` Confirmable_Action containing the customer_id, a draft message body (≤160 characters), and the referenced plan_name.
2. THE draft SMS message body SHALL be generated by the LLM but SHALL NOT contain digits, currency symbols, percentages, competitor names, or switch verbs (D-15 narrative rules apply).
3. WHEN the rep clicks "Confirm" on a send_sms Action_Card, THE API_Lambda SHALL transition the action to `confirmed` status.
4. IF the LLM-generated SMS body fails D-15 validation, THEN THE Agent SHALL substitute a pre-approved fallback message from the FALLBACKS registry.

### Requirement 3: Agent-Prepared Payment Plan Offer

**User Story:** As a call-centre rep, I want the agent to prepare a payment plan offer for bill-shocked customers so that I can present it immediately during the call.

#### Acceptance Criteria

1. WHEN the Bill_Shock_Decomposition indicates `is_shock: true` AND the total_delta_dollars exceeds $50, THE Agent SHALL produce a `payment_plan_offer` Confirmable_Action containing the customer_id, proposed_installments (integer), installment_amount (computed by Tools_Lambda), and total_owed.
2. THE installment_amount and total_owed fields SHALL be computed by the Tools_Lambda `propose_payment_plan` pure function — the LLM SHALL NOT perform this arithmetic (SAV-03).
3. WHEN the rep clicks "Confirm" on a payment_plan_offer Action_Card, THE API_Lambda SHALL transition the action to `confirmed` status.
4. IF the bill-shock total_delta_dollars is $50 or less, THEN THE Agent SHALL NOT produce a payment_plan_offer action.

### Requirement 4: Action Card UI Component

**User Story:** As a call-centre rep, I want to see pending actions clearly displayed with one-click confirm/dismiss buttons so that I can act quickly during a live call.

#### Acceptance Criteria

1. WHEN the recommendation response includes one or more Confirmable_Actions, THE UI SHALL render an Action_Card for each action below the recommendation cards.
2. THE Action_Card SHALL display the action type as a human-readable label (e.g., "Switch to EcoFlex Green", "Send SMS follow-up", "Offer payment plan").
3. THE Action_Card SHALL display a "Confirm" button (primary style) and a "Dismiss" button (secondary/ghost style).
4. WHEN the rep clicks "Confirm", THE Action_Card SHALL transition to a confirmed state showing a success indicator and disable both buttons.
5. WHEN the rep clicks "Dismiss", THE Action_Card SHALL transition to a dismissed state and collapse from view.
6. WHILE an action confirmation request is in flight, THE Action_Card SHALL disable both buttons and show a loading indicator on the clicked button.
7. IF the confirmation request fails, THEN THE Action_Card SHALL display an inline error message and re-enable the buttons.
8. WHEN `?narrative=off` is active, THE UI SHALL NOT render Action_Cards (LD-7 kill-switch preserved).

### Requirement 5: Bill-Shock Root-Cause Decomposition — Enriched Output

**User Story:** As a call-centre rep, I want to see exactly why a customer's bill spiked — broken down by cause — so that I can explain it clearly during the call.

#### Acceptance Criteria

1. WHEN the Decomposition_Chain executes for a bill-shocked customer, THE Tools_Lambda SHALL return a Bill_Shock_Decomposition containing: total_delta_dollars, shock_month, and a list of Contributing_Factors each with a factor_name, dollar_amount, and percentage_of_total.
2. THE sum of all Contributing_Factor dollar_amounts SHALL equal total_delta_dollars within a tolerance of $0.01 (decomposition sum invariant).
3. THE sum of all Contributing_Factor percentage_of_total values SHALL equal 100 within a tolerance of 1 percentage point.
4. THE Contributing_Factor list SHALL support at least these factor types: `rate_increase`, `usage_spike`, `seasonal_variation`, and `billing_day_difference`.
5. WHEN no rate change has occurred, THE `rate_increase` Contributing_Factor SHALL have a dollar_amount of $0.00 and SHALL be omitted from the explanation_factors list.
6. FOR ALL valid billing histories with at least 2 months, decomposing then summing the Contributing_Factor dollar_amounts then comparing to total_delta_dollars SHALL produce a difference of at most $0.01 (round-trip sum property).

### Requirement 6: Bill-Shock Human-Readable Explanation

**User Story:** As a call-centre rep, I want a plain-English sentence explaining the bill shock breakdown so that I can read it to the customer without interpreting raw numbers.

#### Acceptance Criteria

1. THE Tools_Lambda SHALL produce an `explanation_sentence` field that summarises the decomposition in the format: "$X over baseline — Y% from [cause A], Z% from [cause B], W% from [cause C]."
2. THE explanation_sentence SHALL be code-composed by the Tools_Lambda from the Contributing_Factors — the LLM SHALL NOT generate or modify this sentence (SAV-03).
3. THE explanation_sentence SHALL appear in the reasoning_trace summary for the decompose_bill_shock tool (D-11 exemption: digits, currency, and percentages are permitted in trace summaries).
4. WHEN the UI renders the reasoning trace, THE ReasoningTrace_Component SHALL display the explanation_sentence as the summary for the decomposition step.

### Requirement 7: Bill-Shock Decomposition Tool Budget

**User Story:** As a system operator, I want the multi-tool bill-shock chain to work within the tool budget so that the agent does not exceed its invocation limits.

#### Acceptance Criteria

1. THE Decomposition_Chain (get_billing_history → detect_bill_shock → decompose_bill_shock) SHALL count as the actual number of tool calls made against the FourToolCapHook budget.
2. WHEN the agent uses the Decomposition_Chain for a bill-shocked customer, THE FourToolCapHook budget SHALL be increased from 4 to 6 tool calls to accommodate the additional decomposition step plus the action-preparation step.
3. THE FourToolCapHook SHALL remain configurable — the budget increase SHALL be implemented as a parameter change, not a structural change to the hook.
4. WHEN the customer is NOT bill-shocked, THE tool budget SHALL remain sufficient for the standard 2-tool path (get_hardship_flag → simulate_savings) plus action preparation.

### Requirement 8: Retention Queue Landing Page

**User Story:** As a call-centre rep, I want to see which customers are at risk today when I open the tool so that I can prioritise my outbound calls.

#### Acceptance Criteria

1. WHEN no customer is selected (idle state), THE UI SHALL display the Retention_Queue instead of the current EmptyState.
2. THE Retention_Queue SHALL show all seed personas (CUST-001 through CUST-006) ranked by Risk_Signal in descending order (highest risk first).
3. THE Retention_Queue SHALL display a header: "N customers at risk today" where N is the count of personas with a non-zero Risk_Signal.
4. EACH Cohort_Card SHALL display: customer_id, a one-line risk summary (e.g., "Bill shock: +$45 over baseline"), and the Risk_Signal score.
5. WHEN the rep clicks a Cohort_Card, THE UI SHALL trigger the full recommendation lookup for that customer_id (same as clicking a PersonaChip).
6. THE Risk_Signal computation SHALL be performed by the Tools_Lambda — the LLM SHALL NOT compute risk scores (SAV-03).
7. WHEN `?narrative=off` is active, THE Retention_Queue SHALL still be displayed (it contains no LLM-generated content).

### Requirement 9: Risk Signal Computation

**User Story:** As a system operator, I want risk signals computed deterministically from billing data so that the retention queue is reproducible and auditable.

#### Acceptance Criteria

1. THE Tools_Lambda SHALL expose a `compute_risk_signals` pure function that accepts a list of customer_ids and returns a ranked list of Risk_Signal objects.
2. THE Risk_Signal for each customer SHALL be computed from: bill-shock magnitude (delta_dollars from detect_bill_shock_pure), usage trend direction (increasing/decreasing/stable over last 3 months), and hardship_flag status.
3. THE Risk_Signal score SHALL be a numeric value between 0 and 100 where higher values indicate greater retention risk.
4. WHEN a customer has `hardship_flag: true`, THE Risk_Signal SHALL be capped at 0 (hardship customers are routed to the specialist team, not the retention queue).
5. FOR ALL valid combinations of bill-shock magnitude, usage trend, and hardship flag, THE compute_risk_signals function SHALL produce a score in the range [0, 100] (range invariant).
6. FOR ALL customer lists, THE output of compute_risk_signals SHALL be sorted in descending order by score (sort invariant).

### Requirement 10: Retention Queue API Endpoint

**User Story:** As a frontend developer, I want an API endpoint that returns the ranked retention queue so that the UI can display it on page load.

#### Acceptance Criteria

1. THE API_Lambda SHALL expose a `GET /retention-queue` endpoint that returns the ranked list of Risk_Signal objects for all known personas.
2. WHEN the endpoint is called, THE API_Lambda SHALL invoke the Tools_Lambda `compute_risk_signals` function with all known customer_ids.
3. THE response SHALL include for each customer: customer_id, risk_score, risk_summary (human-readable one-liner), and bill_shock_detected (boolean).
4. THE risk_summary field SHALL be code-composed by the Tools_Lambda from the risk signal components — the LLM SHALL NOT generate this text (SAV-03).
5. IF the Tools_Lambda invocation fails, THEN THE API_Lambda SHALL return HTTP 502 with a JSON error body (D-04 never-500 preserved at the API layer).
6. THE `GET /retention-queue` endpoint SHALL validate no path parameters and return HTTP 200 on success.

### Requirement 11: Action Response Schema Extension

**User Story:** As a backend developer, I want the recommendation response schema to include pending actions so that the UI can render Action_Cards without a separate API call.

#### Acceptance Criteria

1. THE RecommendationResponse Pydantic model SHALL include an optional `pending_actions` field (list of Confirmable_Action objects, default empty list).
2. EACH Confirmable_Action in the response SHALL include: action_id (uuid), action_type (enum: tariff_switch, send_sms, payment_plan_offer), payload (dict), and status (literal "pending").
3. THE Agent SHALL populate pending_actions by calling the Tools_Lambda `queue_action` function after producing the recommendation — action preparation SHALL NOT block or delay the recommendation response.
4. IF action preparation fails, THEN THE Agent SHALL return the recommendation with an empty pending_actions list (D-04: action failure never blocks the primary recommendation).
5. THE API_Lambda SHALL pass through the pending_actions field without modification (same pass-through contract as the existing response body).

### Requirement 12: Backward Compatibility

**User Story:** As a system operator, I want all existing API contracts and UI behaviours preserved so that the demo remains stable for presentations.

#### Acceptance Criteria

1. THE existing `GET /recommendations/{customer_id}` endpoint SHALL continue to return valid responses for all existing personas without requiring the new pending_actions field.
2. THE existing SSE streaming contract (trace_step, result, error, done events) SHALL remain unchanged — pending_actions SHALL be included in the `result` event payload.
3. THE existing `GET /recommendations/{customer_id}/follow-up` endpoint SHALL remain unchanged.
4. THE `?prewarm=1` path SHALL continue to return HTTP 204 with an empty body.
5. THE existing PersonaChips component SHALL remain functional alongside the new Retention_Queue — both provide paths to trigger a customer lookup.
6. WHEN the UI transitions from the Retention_Queue to a customer lookup, THE UI SHALL replace the Retention_Queue with the standard loading/result states (same state machine as today).
