# Tasks: Typed Hardship Categories (AGENT-03)

## Task 1: Category Configuration Registry

- [x] 1.1 Create `agent/specialists/hardship_config.py` with `HardshipCategory` Literal type and `HARDSHIP_CATEGORIES` dict containing routing_target, permitted_tools (frozenset), permitted_actions (list), and financial_terms_forbidden (bool) for each of the four categories: `payment_difficulty`, `medical_equipment`, `family_violence`, `other`.
- [x] 1.2 Add `FINANCIAL_TERMS` frozenset to `hardship_config.py` containing the forbidden financial terminology list: dollar, payment, bill, tariff, plan, cost, price, save, switch, account, balance, debt, arrears, overdue.
- [x] 1.3 Add bi-mode import support (try container layout first, fall back to repo layout) following the existing pattern in `agent/specialists/hardship.py`.
- [x] 1.4 Write unit tests in `tests/test_hardship_config.py` verifying: all four categories present, each has required keys, permitted_tools are frozensets, family_violence has financial_terms_forbidden=True.

## Task 2: Data Model — Lambda Pure Helper Extension

- [x] 2.1 Modify `get_hardship_flag_pure` in `lambda/handler.py` to read `hardship_category` from the PROFILE row Item and include it in the return dict (value is `None` when attribute is absent).
- [x] 2.2 Update existing tests for `get_hardship_flag_pure` in `tests/test_simulate_savings.py` (or relevant test file) to assert `hardship_category` is present in the response — `None` for non-hardship customers, string value for hardship customers.
- [x] 2.3 Write a property-based test (CP-4 partial): for any customer with `hardship_flag: true` and no `hardship_category` attribute, the response has `hardship_category: None`.

## Task 3: Seed Data — Hardship Personas

- [x] 3.1 Add four new persona record sets to `infrastructure/seed_data/billing_records.py`: CUST-007 (payment_difficulty), CUST-008 (medical_equipment), CUST-009 (family_violence), CUST-010 (other). Each with 12 months of low-usage billing records and a PROFILE row containing `hardship_flag: True` and `hardship_category: "<category>"`.
- [x] 3.2 Add the new personas to the `ALL_RECORDS` export list.
- [x] 3.3 Verify `infrastructure/foundation_stack.py` seeder custom resource iterates `ALL_RECORDS` (no code change expected — just confirm the new personas will be seeded automatically).

## Task 4: Category-Specific Call Scripts

- [x] 4.1 Add category-keyed hardship fallback entries to `agent/narrative/fallbacks.py` for CUST-007 through CUST-010. Each persona's `"hardship"` key becomes a dict keyed by category with `reason` and `call_script` sub-keys.
- [x] 4.2 Write the `family_violence` scripts using ONLY safety-first language — zero financial terms, zero account references. Verify against `FINANCIAL_TERMS` set.
- [x] 4.3 Write the `medical_equipment` scripts referencing priority service guarantees without plan details.
- [x] 4.4 Write the `payment_difficulty` scripts acknowledging difficulty and offering flexible arrangements without figures.
- [x] 4.5 Update the import-time assertion block in `fallbacks.py` to validate the new nested hardship dict structure.
- [x] 4.6 Write tests verifying all new scripts pass `_reject_forbidden` (D-15 validation) and family_violence scripts pass the financial terms check.

## Task 5: Typed HardshipResponse Schema

- [x] 5.1 Add `category: Literal["payment_difficulty", "medical_equipment", "family_violence", "other"]` field to `HardshipResponse` in `agent/agent.py`.
- [x] 5.2 Add `permitted_actions: list[str] = Field(default_factory=list)` field to `HardshipResponse`.
- [x] 5.3 Refactor `_build_hardship_response` into `_build_typed_hardship_response(customer_id, category, config)` that uses the category config registry to populate `routing_target`, `permitted_actions`, and select the correct category-keyed script from FALLBACKS.
- [x] 5.4 Preserve the existing `_build_hardship_response(customer_id)` as a thin wrapper that calls `_build_typed_hardship_response` with category `"other"` for backward compatibility.
- [x] 5.5 Write property-based test CP-1: for any valid HardshipCategory, `_build_typed_hardship_response` produces a response that passes Pydantic validation and D-15 content rules.
- [x] 5.6 Write property-based test CP-5: `routing_target` is a pure function of category — same category always produces same routing_target regardless of customer_id.

## Task 6: HardshipSpecialist Refactor

- [x] 6.1 Modify `HardshipSpecialist.handle()` in `agent/specialists/hardship.py` to read `hardship_category` from payload, default to `"other"` if missing or unrecognised, and call `_build_typed_hardship_response`.
- [x] 6.2 Add `_narrative_source` category field to the response metadata.
- [x] 6.3 Update `invoke()` in `agent/agent.py` to pass `hardship_category` from the `get_hardship_flag` result into the payload before calling `_hardship_specialist.handle()`.
- [x] 6.4 Wrap category extraction in try/except with fallback to `"other"` (D-04 preservation).
- [x] 6.5 Write integration test: invoke with a `payment_difficulty` customer returns correct routing_target, permitted_actions, and category-specific call_script.
- [x] 6.6 Write integration test: invoke with `hardship_flag: true` but no `hardship_category` returns the generic `"other"` response (backward compat — CP-4).

## Task 7: Compliance Reviewer Extension

- [x] 7.1 Add `_check_hardship_tool_restriction` method to `ComplianceReviewer` in `agent/specialists/compliance.py` — verifies all tools in `reasoning_trace` are within the category's `permitted_tools` set.
- [x] 7.2 Add `_check_family_violence_no_financial` method — for `family_violence` responses, checks `reason`, `call_script`, and `permitted_actions` against `FINANCIAL_TERMS`.
- [x] 7.3 Update `review()` method to call the new checks when `kind == "hardship"` — both new rules run alongside existing `hardship_no_tariff_data`.
- [x] 7.4 Write property-based test CP-2: for any `family_violence` response with reasoning_trace, no tool outside `{"schedule_callback"}` passes the tool restriction check.
- [x] 7.5 Write property-based test CP-3: for any `family_violence` response, concatenation of reason + call_script + str(permitted_actions) contains zero tokens from FINANCIAL_TERMS.
- [x] 7.6 Write unit test: `payment_difficulty` response with `propose_payment_plan` in reasoning_trace passes tool restriction; same response with `simulate_savings` fails.

## Task 8: End-to-End Integration & Backward Compatibility

- [x] 8.1 Write end-to-end test: full `invoke()` call with CUST-009 (family_violence) returns `category: "family_violence"`, `routing_target: "family_violence_team"`, compliance_review passes all rules, and no financial terms in any narrative field.
- [x] 8.2 Write end-to-end test: full `invoke()` call with CUST-001 (non-hardship) is completely unchanged — recommendation path unaffected.
- [x] 8.3 Write end-to-end test: full `invoke()` call with CUST-006 (existing hardship persona, no category) returns category `"other"` with backward-compatible response.
- [x] 8.4 Verify `?narrative=off` kill-switch strips `compliance_review` and `supervisor_trace` from typed hardship responses.
- [x] 8.5 Run full existing test suite (`pytest`) and confirm zero regressions.
