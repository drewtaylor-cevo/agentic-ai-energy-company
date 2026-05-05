# Tasks

## Task 1: Create AgentRole Protocol and Pydantic schemas (`agent/roles.py`)

- [x] 1.1 Create `agent/roles.py` with `AgentRole` Protocol (`@runtime_checkable`, single `handle(payload: dict) -> dict` method)
- [x] 1.2 Add `ComplianceCheckResult` Pydantic model (rule, verdict, reason fields)
- [x] 1.3 Add `ComplianceReview` Pydantic model (verdict, rules_checked, failures, reviewed_at fields)
- [x] 1.4 Add `SupervisorTrace` Pydantic model (routed_to, routing_reason, hardship_checked, compliance_reviewed fields)
- [x] 1.5 Add bi-mode import support (try/except block for container `/app/roles` vs repo `agent.roles`)
- [x] 1.6 Write unit tests in `tests/test_roles.py`: AgentRole is runtime_checkable, has handle method, ComplianceReview and SupervisorTrace schemas have required fields

## Task 2: Create HardshipSpecialist (`agent/specialists/hardship.py`)

- [x] 2.1 Create `agent/specialists/__init__.py` and `agent/specialists/hardship.py`
- [x] 2.2 Implement `HardshipSpecialist` class with `handle(payload: dict) -> dict` method — extract `_build_hardship_response()` call and `_narrative_source` attachment from current `invoke()` hardship path
- [x] 2.3 Ensure HardshipSpecialist has no tariff tool references (no simulate_savings, detect_bill_shock, get_billing_history)
- [x] 2.4 Add bi-mode import support for the specialists package
- [x] 2.5 Write unit tests in `tests/test_specialists.py`: HardshipSpecialist returns HardshipResponse shape, has no tariff tools, satisfies AgentRole Protocol

## Task 3: Create TariffSpecialist (`agent/specialists/tariff.py`)

- [x] 3.1 Create `agent/specialists/tariff.py` with `TariffSpecialist` class
- [x] 3.2 Extract the recommendation logic from `invoke()` into `TariffSpecialist.handle()` — includes: FourToolCapHook reset, message snapshot, agent call, structured output handling, StructuredOutputException fallback, general Exception fallback, _narrative_source and reasoning_trace attachment
- [x] 3.3 TariffSpecialist constructor receives existing module-level `_agent` and `_four_tool_cap` instances (no new Agent construction)
- [x] 3.4 Verify TariffSpecialist satisfies AgentRole Protocol via isinstance check
- [x] 3.5 Write unit tests in `tests/test_specialists.py`: TariffSpecialist attaches _narrative_source and reasoning_trace, satisfies AgentRole Protocol, reuses module-level agent instance

## Task 4: Create ComplianceReviewer (`agent/specialists/compliance.py`)

- [x] 4.1 Create `agent/specialists/compliance.py` with `ComplianceReviewer` class implementing `handle()` and `review()` methods
- [x] 4.2 Implement reference-period disclosure check: verify reasoning_trace contains simulate_savings or get_billing_history entry
- [x] 4.3 Implement no-upsell-to-disadvantage check: verify saving_monthly >= 0 on both tracks
- [x] 4.4 Implement hardship-flag cross-check: verify no plan_id, saving_monthly, or saving_annual in hardship responses
- [x] 4.5 ComplianceReviewer returns ComplianceReview Pydantic model with verdict, rules_checked, failures, reviewed_at
- [x] 4.6 Verify ComplianceReviewer satisfies AgentRole Protocol and is deterministic code (no Agent, no BedrockModel)
- [x] 4.7 Write property-based tests in `tests/test_supervisor_properties.py` for Properties 2, 3, and 4 (no-upsell, hardship-no-tariff, reference-period) — minimum 100 iterations each, tagged with feature/property references

## Task 5: Refactor `invoke()` into Supervisor dispatcher

- [x] 5.1 Instantiate module-level `_tariff_specialist`, `_hardship_specialist`, `_compliance_reviewer` in `agent/agent.py`
- [x] 5.2 Refactor `invoke()` to use Supervisor routing: extract hardship check → dispatch to specialist → compliance review → attach supervisor_trace
- [x] 5.3 Preserve `action == "follow_up"` dispatch to existing `draft_follow_up()` handler
- [x] 5.4 Implement DEMO-07 kill-switch: strip `compliance_review` and `supervisor_trace` when `narrative=off` in payload
- [x] 5.5 Ensure D-04 never-500 contract: wrap hardship check, specialist dispatch, and compliance review in try/except with appropriate fallbacks
- [x] 5.6 Write unit tests in `tests/test_supervisor.py`: routing dispatch (recommend → TariffSpecialist, follow_up → draft_follow_up, hardship → HardshipSpecialist), missing customer_id error, compliance review integration, narrative=off stripping, compliance failure attaches warning, compliance exception returns response unchanged, hardship check failure falls back to tariff

## Task 6: Update Dockerfile and verify bi-mode imports

- [x] 6.1 Update `agent/Dockerfile` to COPY `specialists/` and `roles.py` into the container image
- [x] 6.2 Verify all new modules have bi-mode import blocks (try container layout, except repo layout)
- [x] 6.3 Write smoke tests for bi-mode imports of `roles` and `specialists` modules

## Task 7: Property-based test for TariffSpecialist REC-03 guarantee

- [x] 7.1 Write property-based test `test_tariff_specialist_always_returns_both_tracks` in `tests/test_supervisor_properties.py` — for any valid customer_id and mocked agent result shape, TariffSpecialist.handle() returns both green and cheapest keys or errorMessage (Property 1, minimum 100 iterations)

## Task 8: Verify existing test suite passes (invariant preservation)

- [x] 8.1 Run full offline test suite (`pytest -m "not smoke"`) and verify all existing tests pass
- [x] 8.2 Verify api_lambda/handler.py does not strip compliance_review or supervisor_trace fields — add tests in `tests/test_observability.py`
- [x] 8.3 Verify _narrative_source is still stripped by api_lambda/handler.py (existing contract preserved)
