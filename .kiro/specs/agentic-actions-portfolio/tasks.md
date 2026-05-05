# Tasks

## Task 1: Action Queue — Tools Lambda Pure Functions

- [x] 1.1 Implement `queue_action` pure function in `lambda/handler.py` that validates a Confirmable_Action payload (action_type enum, valid customer_id, well-formed payload dict) and stores it in DynamoDB with status=pending, a generated action_id (uuid4), created_at timestamp, and expires_at (24h TTL)
- [x] 1.2 Implement `confirm_action` pure function in `lambda/handler.py` that reads an action by action_id, validates it is pending and not expired, and transitions status to confirmed
- [x] 1.3 Implement `dismiss_action` pure function in `lambda/handler.py` that reads an action by action_id, validates it is pending and not expired, and transitions status to rejected
- [x] 1.4 Add action dispatcher routes in `lambda/handler.py::handler` for actions: `queue_action`, `confirm_action`, `dismiss_action`
- [x] 1.5 Write property-based tests for action state machine (Properties 1-3, 14): generate random valid actions, verify confirm→confirmed, dismiss→rejected, expired→error, queue validates correctly (minimum 100 iterations each)

## Task 2: Bill-Shock Decomposition v2 — Enriched Output

- [x] 2.1 Extend `decompose_bill_shock_pure` in `lambda/handler.py` to return `contributing_factors` list with `{factor_name, dollar_amount, percentage_of_total}` for each component (rate_increase, usage_spike, seasonal_variation, billing_day_difference)
- [x] 2.2 Add `explanation_sentence` field to `decompose_bill_shock_pure` output, code-composed from Contributing_Factors in format: "$X over baseline — Y% from [cause A], Z% from [cause B], ..."
- [x] 2.3 Ensure zero-value factors (e.g., rate_increase when no rate change) have dollar_amount=$0.00 and are omitted from explanation_factors and explanation_sentence
- [x] 2.4 Update `summary_decompose_bill_shock` in `agent/reasoning/summaries.py` to include the explanation_sentence in the trace summary
- [x] 2.5 Write property-based tests for decomposition (Properties 7-10): sum invariant ($0.01 tolerance), percentage sum (1pp tolerance), zero-rate omission, explanation format (minimum 100 iterations each)

## Task 3: Risk Signal Computation

- [x] 3.1 Implement `compute_risk_signals` pure function in `lambda/handler.py` that accepts a list of customer_ids, computes risk_score (0-100) from bill-shock magnitude + usage trend + hardship flag, and returns a descending-sorted list of RiskSignal objects
- [x] 3.2 Implement risk_summary code-composition in `compute_risk_signals` (e.g., "Bill shock: +$45 over baseline" or "Usage trending up, no shock detected")
- [x] 3.3 Implement hardship cap: customers with hardship_flag=true get risk_score=0
- [x] 3.4 Add `compute_risk_signals` dispatcher route in `lambda/handler.py::handler`
- [x] 3.5 Write property-based tests for risk signals (Properties 11-13): range [0,100], hardship→0, sort descending (minimum 100 iterations each)

## Task 4: Agent Action Preparation

- [x] 4.1 Add `ConfirmableAction` Pydantic model to `agent/agent.py` with fields: action_id, action_type, customer_id, payload, status
- [x] 4.2 Add optional `pending_actions: list[ConfirmableAction] = []` field to `RecommendationResponse`
- [x] 4.3 Implement action preparation logic in `invoke()` that calls `queue_action` via Tools Lambda after producing the recommendation — prepares tariff_switch action for all customers, send_sms action with D-15 validated body, and payment_plan_offer when bill-shock delta > $50
- [x] 4.4 Implement D-04 guard: wrap action preparation in try/except so failures return recommendation with empty pending_actions
- [x] 4.5 Implement SMS body D-15 validation with fallback substitution from FALLBACKS registry when validation fails
- [x] 4.6 Write property-based test for SAV-03 compliance (Property 4): verify action numeric fields match deterministic engine output
- [x] 4.7 Write property-based test for SMS validation (Property 5): verify message_body ≤160 chars and passes D-15
- [x] 4.8 Write property-based test for payment plan conditional (Property 6): verify offer produced iff is_shock=true AND delta > $50

## Task 5: API Lambda Extensions

- [x] 5.1 Add `GET /retention-queue` route in `api_lambda/handler.py` that invokes Tools Lambda `compute_risk_signals` with all known customer_ids and returns the ranked list with HTTP 200
- [x] 5.2 Add `POST /actions/{action_id}/confirm` route that invokes Tools Lambda `confirm_action` and returns the updated action
- [x] 5.3 Add `POST /actions/{action_id}/dismiss` route that invokes Tools Lambda `dismiss_action` and returns the updated action
- [x] 5.4 Implement error mapping: 404 (not found), 410 (expired), 409 (already processed), 502 (upstream failure), 400 (invalid action_id)
- [x] 5.5 Ensure `pending_actions` field passes through in recommendation response without modification
- [x] 5.6 Add API Gateway routes in CDK `infrastructure/backend_api_stack.py` for the new endpoints
- [x] 5.7 Write unit tests for new API Lambda routes (happy path + error cases)

## Task 6: Retention Queue UI

- [x] 6.1 Create `RetentionQueue` component in `ui/src/components/RetentionQueue.tsx` that fetches `GET /retention-queue` on mount and displays ranked Cohort_Cards
- [x] 6.2 Create `CohortCard` component in `ui/src/components/CohortCard.tsx` displaying customer_id, risk_summary, and risk_score with click-to-investigate handler
- [x] 6.3 Add "N customers at risk today" header to RetentionQueue where N = count of customers with non-zero risk_score
- [x] 6.4 Replace `EmptyState` with `RetentionQueue` in `App.tsx` when `state.status === 'idle'`
- [x] 6.5 Wire CohortCard click to trigger `handleLookup(customer_id)` (same flow as PersonaChips)
- [x] 6.6 Ensure RetentionQueue still displays when `?narrative=off` is active (no LLM content)
- [x] 6.7 Write vitest unit tests for RetentionQueue and CohortCard components

## Task 7: Action Card UI

- [x] 7.1 Create `ActionCard` component in `ui/src/components/ActionCard.tsx` with human-readable label, Confirm button (primary), Dismiss button (ghost)
- [x] 7.2 Implement confirm/dismiss click handlers that POST to `/actions/{id}/confirm` or `/actions/{id}/dismiss`
- [x] 7.3 Implement loading state: disable both buttons, show spinner on clicked button during in-flight request
- [x] 7.4 Implement success state: show success indicator, disable both buttons after confirm
- [x] 7.5 Implement dismiss state: collapse card from view after dismiss
- [x] 7.6 Implement error state: show inline error message, re-enable buttons on failure
- [x] 7.7 Render ActionCard list below recommendation cards in App.tsx success state when pending_actions is non-empty
- [x] 7.8 Hide ActionCards when `?narrative=off` is active (LD-7 kill-switch)
- [x] 7.9 Update `ui/src/lib/types.ts` with ConfirmableAction interface and extend RecommendationResponse
- [x] 7.10 Write vitest unit tests for ActionCard component (all states + kill-switch)

## Task 8: Backward Compatibility Verification

- [x] 8.1 Verify existing `GET /recommendations/{customer_id}` returns valid responses without requiring pending_actions
- [x] 8.2 Verify SSE streaming contract unchanged — pending_actions included in result event payload
- [x] 8.3 Verify `GET /recommendations/{customer_id}/follow-up` endpoint unchanged
- [x] 8.4 Verify `?prewarm=1` still returns HTTP 204
- [x] 8.5 Verify PersonaChips remains functional alongside RetentionQueue
- [x] 8.6 Write integration tests confirming all existing persona flows (CUST-001 through CUST-006) still produce valid responses
