# Requirements Document

## Introduction

Split the monolithic `agent/agent.py` into a multi-agent supervisor pattern with three specialist agents — TariffSpecialist, HardshipSpecialist, and ComplianceReviewer — orchestrated by a Supervisor. The Supervisor routes incoming requests to the appropriate specialist based on customer context (hardship flag, request action). The ComplianceReviewer signs off on every outbound response before it leaves the system, checking against AER NECF-aligned rules: reference-period disclosure, no upsell-to-disadvantage, and hardship-flag cross-check. This is the strongest "why AgentCore" story for the Energy & Utilities demo — a visible compliance reviewer is the difference between a chatbot and an agent a utility would actually deploy.

Builds on Phase 12's `CustomerDataProvider` Protocol (same strangler-fig seam pattern, applied to agent roles). Must preserve all existing invariants: SAV-03 (LLM never does arithmetic), REC-03 (both tracks always returned on recommendation branch), D-15 (narrative dual-gate), D-04 (never-500 contract), and LD-4 (latency budget).

## Glossary

- **Supervisor**: The top-level orchestrating agent that receives incoming payloads, determines routing (tariff recommendation, hardship, or follow-up email), dispatches to the appropriate Specialist, collects the Specialist's response, submits it to the ComplianceReviewer for sign-off, and returns the final response. The Supervisor does not generate recommendations or narrative — it routes and coordinates.
- **TariffSpecialist**: The specialist agent responsible for tariff recommendation logic — the current `invoke()` recommendation path extracted into its own agent. Owns tool calls (`get_hardship_flag`, `detect_bill_shock`, `get_billing_history`, `simulate_savings`), structured output via `RecommendationResponse`, narrative generation, and the D-15 dual-gate fallback chain.
- **HardshipSpecialist**: The specialist agent responsible for hardship-flagged customers. Extracted from the current pre-LLM guard in `invoke()`. Produces `HardshipResponse` with dignity-preserving routing copy. Owns no tariff tools — never sees savings data.
- **ComplianceReviewer**: A new specialist agent that inspects every outbound response before it leaves the system. Checks three AER NECF-aligned rules: (1) reference-period disclosure — the response references the billing period the savings are calculated from, (2) no upsell-to-disadvantage — the recommendation does not steer the customer toward a plan that would increase their costs, (3) hardship-flag cross-check — if the customer is hardship-flagged, no tariff recommendation is present. Returns a pass/fail verdict with a reason string.
- **AgentRole_Protocol**: A `typing.Protocol` defining the minimum interface each specialist agent must satisfy, following the same `@runtime_checkable` pattern as `CustomerDataProvider` from Phase 12.
- **Compliance_Verdict**: A Pydantic model representing the ComplianceReviewer's pass/fail decision, including the rule checked, the verdict, and a reason string.
- **AER_NECF**: Australian Energy Regulator National Energy Customer Framework — the regulatory framework governing energy retail customer protections. Referenced here as an architectural alignment target, not a legal compliance claim.
- **Reference_Period_Disclosure**: The requirement that any savings claim discloses the billing period (12-month window) from which the savings figure was derived.
- **Upsell_To_Disadvantage**: A regulatory anti-pattern where a recommendation steers a customer toward a plan that would cost them more than their current arrangement.
- **Latency_Budget**: The LD-4 constraint — warm p95 under 2500ms for multi-tool flows, under 3000ms for single-tool flows. The supervisor routing + compliance review loop adds latency that must fit within this budget.

## Requirements

### Requirement 1: Supervisor Agent Routing

**User Story:** As a call-centre system, I want a Supervisor agent that routes incoming requests to the correct specialist, so that each agent handles only its domain of expertise.

#### Acceptance Criteria

1. WHEN a payload with `action: "recommend"` is received, THE Supervisor SHALL dispatch the request to the TariffSpecialist
2. WHEN a payload with `action: "follow_up"` is received, THE Supervisor SHALL dispatch the request to the existing `draft_follow_up` handler
3. WHEN the TariffSpecialist returns a response, THE Supervisor SHALL submit the response to the ComplianceReviewer before returning it to the caller
4. WHEN the HardshipSpecialist returns a response, THE Supervisor SHALL submit the response to the ComplianceReviewer before returning it to the caller
5. IF the Supervisor receives a payload without a `customer_id`, THEN THE Supervisor SHALL return an error dict with key `error` and a descriptive message
6. THE Supervisor SHALL preserve the existing `@app.entrypoint` contract — the `invoke()` function signature and return shape are unchanged from the caller's perspective

### Requirement 2: Hardship Routing via Supervisor

**User Story:** As a call-centre system, I want the Supervisor to detect hardship-flagged customers and route them to the HardshipSpecialist, so that vulnerable customers are handled by a dedicated agent that never sees tariff data.

#### Acceptance Criteria

1. WHEN a recommendation request is received, THE Supervisor SHALL check the hardship flag via `CustomerDataProvider.get_hardship_flag` before dispatching to any specialist
2. WHEN the hardship flag is `true`, THE Supervisor SHALL dispatch the request to the HardshipSpecialist instead of the TariffSpecialist
3. THE HardshipSpecialist SHALL produce a `HardshipResponse` with `kind: "hardship"` containing a dignity-preserving `reason` and `call_script`
4. THE HardshipSpecialist SHALL have no access to tariff tools (`simulate_savings`, `detect_bill_shock`, `get_billing_history`) — the specialist is constructed without these tools
5. IF the hardship flag check itself fails, THEN THE Supervisor SHALL fall back to the TariffSpecialist path and log a warning, preserving the D-04 never-500 contract

### Requirement 3: TariffSpecialist Agent

**User Story:** As a call-centre system, I want the existing tariff recommendation logic extracted into a TariffSpecialist agent, so that recommendation generation is isolated from routing and compliance concerns.

#### Acceptance Criteria

1. THE TariffSpecialist SHALL produce a `RecommendationResponse` with both `green` and `cheapest` tracks present, preserving the REC-03 invariant
2. THE TariffSpecialist SHALL use the same four tools (`simulate_savings`, `detect_bill_shock`, `get_billing_history`, `get_hardship_flag`) with the same system prompt and D-15 narrative dual-gate
3. THE TariffSpecialist SHALL preserve the existing FourToolCapHook budget enforcement — the 4-tool cap remains a code-side Strands HookProvider, not a prompt instruction
4. THE TariffSpecialist SHALL preserve the existing D-01 retry-once-then-per-field-fallback chain: structured output validation, lenient salvage, and FALLBACKS bank
5. THE TariffSpecialist SHALL attach `_narrative_source` and `reasoning_trace` to the response body, preserving the existing observability contract

### Requirement 4: ComplianceReviewer Agent

**User Story:** As a compliance stakeholder, I want every outbound response reviewed by a dedicated ComplianceReviewer agent before it reaches the caller, so that regulatory-aligned checks are enforced independently of the generating specialist.

#### Acceptance Criteria

1. WHEN a `RecommendationResponse` is submitted for review, THE ComplianceReviewer SHALL verify that the response references the billing period from which savings were calculated (reference-period disclosure)
2. WHEN a `RecommendationResponse` is submitted for review, THE ComplianceReviewer SHALL verify that neither track recommends a plan that would increase the customer's costs compared to their current arrangement (no upsell-to-disadvantage check, using the `saving_monthly` field — a non-negative value confirms no disadvantage)
3. WHEN a `HardshipResponse` is submitted for review, THE ComplianceReviewer SHALL verify that no `plan_id`, `saving_monthly`, or `saving_annual` fields are present in the response (hardship-flag cross-check)
4. THE ComplianceReviewer SHALL return a Compliance_Verdict containing the verdict (`pass` or `fail`), the rule that was checked, and a reason string
5. IF the ComplianceReviewer returns a `fail` verdict, THEN THE Supervisor SHALL log the failure reason and return the response with a compliance warning attached, rather than blocking the response entirely — the D-04 never-500 contract takes precedence over compliance gating
6. IF the ComplianceReviewer itself raises an exception, THEN THE Supervisor SHALL log the error and return the original specialist response unchanged, preserving the D-04 never-500 contract

### Requirement 5: AgentRole Protocol

**User Story:** As a developer, I want a typed Protocol defining the specialist agent interface, so that new specialists can be added with compile-time shape guarantees following the same pattern as `CustomerDataProvider`.

#### Acceptance Criteria

1. THE AgentRole_Protocol SHALL be defined as a `typing.Protocol` with `@runtime_checkable` decorator, following the `CustomerDataProvider` pattern from `agent/providers.py`
2. THE AgentRole_Protocol SHALL define a `handle(payload: dict) -> dict` method as the single entry point for specialist invocation
3. THE TariffSpecialist, HardshipSpecialist, and ComplianceReviewer SHALL each satisfy the AgentRole_Protocol at runtime, verified by `isinstance` checks
4. THE AgentRole_Protocol SHALL be defined in a dedicated module (`agent/roles.py`) with bi-mode import support (container `/app/roles.py` and repo `agent/roles.py`), matching the `agent/providers.py` precedent

### Requirement 6: Latency Budget Compliance

**User Story:** As a demo operator, I want the multi-agent supervisor loop to fit within the existing latency budget, so that the LD-4 warm p95 targets are not regressed.

#### Acceptance Criteria

1. THE Supervisor routing overhead (dispatch to specialist + collect response) SHALL add no more than one additional LLM call beyond the current single-agent path — the Supervisor is a code-side router, not an LLM-based planner
2. THE ComplianceReviewer SHALL execute as a deterministic code-side check (Pydantic validation + field inspection), not as an LLM agent turn, to avoid adding LLM latency to every request
3. WHILE the multi-agent supervisor is active, THE system SHALL maintain warm p95 latency under 3000ms for single-tool flows and under 2500ms for multi-tool flows, preserving the LD-4 contract
4. THE Supervisor SHALL reuse the existing module-level `_agent` instance and `_model` instance rather than constructing new Strands Agent objects per invocation, preserving the current warm-start behaviour

### Requirement 7: Invariant Preservation

**User Story:** As a developer, I want the multi-agent refactor to preserve all existing critical invariants, so that the demo's trust architecture is not regressed.

#### Acceptance Criteria

1. THE multi-agent refactor SHALL preserve SAV-03 — all savings arithmetic remains in the Tools Lambda; no specialist agent performs, estimates, or rounds any calculation
2. THE multi-agent refactor SHALL preserve REC-03 — every `RecommendationResponse` contains both `green` and `cheapest` tracks
3. THE multi-agent refactor SHALL preserve D-15 — the narrative dual-gate (`validate_usage_narrative`, `validate_call_script`, banned-terms regex, fallback bank) applies to all narrative surfaces across all specialists
4. THE multi-agent refactor SHALL preserve D-04 — the `invoke()` entrypoint never raises an unhandled exception; every code path returns HTTP 200 (or 404 for unknown customers, 504 for timeouts)
5. THE multi-agent refactor SHALL preserve the `_narrative_source` stripping contract — `api_lambda/handler.py` continues to strip internal markers before returning to the client
6. THE multi-agent refactor SHALL preserve the bi-mode import pattern — all new modules support both container (`/app/`) and repo (`agent/`) import paths
7. THE multi-agent refactor SHALL preserve the `runtimeSessionId` isolation contract — session IDs are generated inside `handler()`, never at module scope

### Requirement 8: Compliance Review Observability

**User Story:** As a presenter, I want the ComplianceReviewer's verdict visible in the response, so that demo audiences can see the compliance gate in action — this is the key "why AgentCore" differentiator.

#### Acceptance Criteria

1. WHEN the ComplianceReviewer passes a response, THE Supervisor SHALL attach a `compliance_review` field to the response body containing the verdict, rules checked, and timestamp
2. WHEN the ComplianceReviewer fails a response, THE Supervisor SHALL attach a `compliance_review` field with the `fail` verdict, the failing rule, and the reason string
3. THE `compliance_review` field SHALL be a public field (not stripped by `api_lambda/handler.py`) — it is part of the demo's trust-architecture story and is surfaced in the UI
4. THE `compliance_review` field SHALL follow a Pydantic schema (`ComplianceReview`) with fields: `verdict` (pass/fail), `rules_checked` (list of rule names), `failures` (list of failure reasons, empty on pass), and `reviewed_at` (ISO 8601 timestamp)

### Requirement 9: Supervisor Trace Surface

**User Story:** As a presenter, I want the Supervisor's routing decision visible in the response, so that demo audiences can see the multi-agent orchestration pattern.

#### Acceptance Criteria

1. THE Supervisor SHALL attach a `supervisor_trace` field to the response body containing the routing decision (which specialist was selected and why)
2. THE `supervisor_trace` field SHALL include: `routed_to` (specialist name), `routing_reason` (brief explanation), `hardship_checked` (boolean), and `compliance_reviewed` (boolean)
3. THE `supervisor_trace` field SHALL be a public field surfaced in the UI, following the same pattern as `reasoning_trace`
4. WHEN `?narrative=off` is active, THE `supervisor_trace` and `compliance_review` fields SHALL be omitted from the response, preserving the DEMO-07 kill-switch contract that collapses all post-v2.0 surfaces
