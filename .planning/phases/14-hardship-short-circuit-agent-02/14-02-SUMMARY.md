# Phase 14 Plan 02 Summary — Offline agent tests (adversarial + invariant)

**Status:** Complete
**Date:** 2026-05-03

## New test file: tests/test_hardship.py (18 tests)

### TestHardshipGuard (4 tests)
- `test_cust006_returns_hardship_kind` — CUST-006 → kind: "hardship", no green/cheapest
- `test_cust006_has_narrative_source_marker` — _narrative_source present for observability
- `test_cust001_still_returns_recommendation` — non-hardship → kind: "recommendation" with both tracks
- `test_hardship_guard_failure_falls_through_to_recommendation` — D-04: broken provider → falls through

### TestHardshipNarrative (9 tests)
- D-15 validators: no digits, no currency, no banned terms in reason + call_script
- No plan IDs anywhere in hardship body
- No recommend verbs in reason or call_script
- Word caps: reason ≤20, call_script ≤22

### TestHardshipCodeSide (2 tests)
- `test_agent_never_called_for_hardship_customer` — _agent mock not called (code-side proof)
- `test_hardship_response_has_no_tariff_context` — no plan names or IDs in body

### TestRecommendationBranchPreserved (3 tests, parametrized)
- CUST-001/002/003 all return kind: "recommendation" with both green + cheapest (REC-03)

## Key finding
Module-level imports of `agent.agent` must happen BEFORE the `_provider_swap` autouse fixture runs, otherwise the module-level `set_provider(ToolsLambdaProvider(...))` overwrites the fixture's InMemoryProvider swap. Fixed by importing at module level in the test file.
