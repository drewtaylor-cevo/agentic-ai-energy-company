# Phase 14 Plan 01 Summary — HardshipResponse model + pre-LLM guard + fallback strings

**Status:** Complete
**Date:** 2026-05-03

## Changes

### agent/agent.py
1. **`HardshipResponse` Pydantic model** — `kind: "hardship"`, `customer_id`, `reason`, `routing_target`, `call_script`. D-15 validators on `reason` (via `@field_validator`) and `call_script` enforce no digits, no currency, no banned terms.
2. **`kind` field on `RecommendationResponse`** — `kind: str = Field(default="recommendation")` added for discriminated union routing.
3. **Pre-LLM guard in `invoke()`** — after `customer_id` extraction, calls `get_provider().get_hardship_flag()` directly. If `hardship: true`, returns `HardshipResponse` immediately — LLM never sees tariff context. D-04 preserved: if the hardship check itself fails, logs warning and falls through to normal recommendation path.
4. **`_build_hardship_response()`** — builds validated `HardshipResponse` from FALLBACKS or defaults. Attaches `_narrative_source` marker.
5. **`kind: "recommendation"` on D-04 fallback path** — raw dict fallback now includes `kind` for API Lambda routing consistency.
6. **`field_validator` import** added to pydantic imports.

### agent/narrative/fallbacks.py
1. **CUST-006 entry** — green/cheapest tracks (for simulate_savings_pure compatibility) + hardship track with `reason` and `call_script` strings.
2. **Import-time assertions updated** — 4 personas, hardship track has `reason` + `call_script`.

### tests/conftest.py
1. **`mock_hardship_response` fixture** — full HardshipResponse shape for handler tests.

### tests/test_fallbacks_pass_validator.py
1. **Persona set updated** — CUST-006 added to parametrized tests.
2. **Tracks/fields assertion updated** — handles hardship track shape.
3. **Two new tests** — `test_hardship_fallback_reason_passes` and `test_hardship_fallback_call_script_passes`.

## Test results

313 passed, 0 failed, 37 deselected (excluding Docker-dependent synth test + AWS-dependent seeder smoke).

## Invariants preserved

- **SAV-03:** No arithmetic on hardship branch
- **REC-03:** `kind: "recommendation"` responses still carry both green + cheapest
- **D-04:** Hardship check failure falls through to recommendation path (never 500)
- **D-15:** `reason` and `call_script` validated via `_reject_forbidden` with same caps
- **SC-3:** Hardship branch skips `_agent()` entirely — no session state touched
