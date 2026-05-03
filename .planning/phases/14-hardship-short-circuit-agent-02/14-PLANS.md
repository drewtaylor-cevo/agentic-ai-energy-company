# Phase 14 Plan Decomposition — Hardship Short-Circuit (AGENT-02)

## Plan overview

| Plan | Name | Wave | Depends on | Files |
|------|------|------|------------|-------|
| 14-01 | HardshipResponse model + pre-LLM guard + fallback strings | 1 | — | `agent/agent.py`, `agent/narrative/fallbacks.py`, `tests/conftest.py` |
| 14-02 | Offline agent tests (adversarial + invariant) | 1 | — | `tests/test_hardship.py`, `tests/test_bill_shock_flow.py` |
| 14-03 | API Lambda surgical update + handler tests | 1 | — | `api_lambda/handler.py`, `tests/test_backend_api_handler.py` |
| 14-04 | UI HardshipBanner + mock fixture + `?narrative=off` | 2 | 14-01 | `ui/src/components/HardshipBanner.tsx`, `ui/src/App.tsx`, `ui/src/hooks/useRecommendations.ts`, `ui/src/lib/mock/` |
| 14-05 | Stack-policy lift ceremony (2-3 stacks) + close-gates | 3 | 14-01..04 | ceremony artifacts, `autonomous: false` |

## Plan details

### 14-01: HardshipResponse model + pre-LLM guard + fallback strings

**Goal:** The agent-side hardship short-circuit is code-complete and offline-testable.

**Changes:**
1. Add `HardshipResponse` Pydantic model to `agent/agent.py` with fields: `kind: Literal["hardship"]`, `customer_id: str`, `reason: str`, `routing_target: str`, `call_script: str`. Apply D-15 validators to `reason` and `call_script`.
2. Add pre-LLM guard at the top of `invoke()`, after `customer_id` extraction but BEFORE `_agent()` call:
   - Call `get_provider().get_hardship_flag(customer_id)` directly (no LLM)
   - If `hardship: true`, return `HardshipResponse` shape immediately
   - Attach `_narrative_source` marker for observability
   - Skip `_four_tool_cap.reset()` and `_agent()` entirely
3. Add CUST-006 hardship fallback strings to `agent/narrative/fallbacks.py` — dignity-preserving copy passing D-15 validators.
4. Add `mock_hardship_response` fixture to `tests/conftest.py`.

**Success criteria:**
- `HardshipResponse` model validates with D-15 rules (no digits, no currency, no banned terms)
- `invoke({"customer_id": "CUST-006"})` returns `kind: "hardship"` with no `green`/`cheapest` keys
- `invoke({"customer_id": "CUST-001"})` still returns `kind: "recommendation"` with both tracks (REC-03)
- Fallback strings pass `_reject_forbidden` (import-time assertion)
- No plan IDs anywhere in the hardship response body

### 14-02: Offline agent tests (adversarial + invariant)

**Goal:** Hardship enforcement is locked by offline tests that don't require AWS.

**Changes:**
1. Create `tests/test_hardship.py` with:
   - `TestHardshipGuard`: mock provider returns `hardship: true` → assert `kind: "hardship"`, no `green`/`cheapest`
   - `TestHardshipNarrative`: 10-seed adversarial test on hardship branch — zero plan-ID leak, zero recommend/suggest/best-for verbs, zero banned-term violations in `call_script` and `reason`
   - `TestHardshipCodeSide`: remove hardship system-prompt instructions, re-run 10-seed adversarial → still zero plan-ID leaks (proves code-side guard, not prompt-side)
   - `TestRecommendationBranchPreserved`: `kind: "recommendation"` responses always carry both `green` and `cheapest` (REC-03 regression guard)
2. Extend `tests/test_bill_shock_flow.py::TestCrossPersonaCanary` to include CUST-006 hardship shape assertion.

**Success criteria:**
- All adversarial tests pass with zero plan-ID leaks
- REC-03 regression guard passes for CUST-001/002/003
- Code-side enforcement test proves the guard fires without prompt help

### 14-03: API Lambda surgical update + handler tests

**Goal:** `api_lambda/handler.py` correctly routes hardship responses as HTTP 200 and doesn't false-positive on 404.

**Changes:**
1. Surgical update to the D-12 detection block:
   ```python
   if "green" not in body or "cheapest" not in body:
       if body.get("kind") == "hardship":
           # Hardship is a valid 200 response — pass through
           return {
               "statusCode": 200,
               "headers": {"Content-Type": "application/json"},
               "body": json.dumps(body),
           }
       logger.info("Customer not found customer_id=%s body=%s", customer_id, body)
       return _error(404, f"Customer {customer_id} not found.")
   ```
2. UNKNOWN sentinel check stays below — only fires on recommendation-shaped responses.
3. Add tests to `tests/test_backend_api_handler.py`:
   - `test_hardship_response_returns_200`: mock agent returns hardship body → HTTP 200
   - `test_hardship_response_has_no_green_cheapest`: body has `kind: "hardship"`, no tracks
   - `test_recommendation_still_returns_200`: existing recommendation path unchanged
   - `test_unknown_customer_still_returns_404`: existing 404 path unchanged
   - `test_unknown_sentinel_still_returns_404`: UNKNOWN sentinel path unchanged

**Success criteria:**
- Hardship response → HTTP 200 with `kind: "hardship"` body
- Missing tracks without `kind: "hardship"` → HTTP 404 (unchanged)
- UNKNOWN sentinel → HTTP 404 (unchanged)
- All existing handler tests still pass

### 14-04: UI HardshipBanner + mock fixture + `?narrative=off`

**Goal:** The UI renders a dignity-preserving hardship banner when the API returns `kind: "hardship"`, and `?narrative=off` collapses it.

**Changes:**
1. Create `ui/src/components/HardshipBanner.tsx` — renders routing message + call script, no tariff info, no savings figures. Accessible, uses shadcn Alert variant.
2. Update `ui/src/hooks/useRecommendations.ts` to handle the `kind: "hardship"` response shape (new state variant).
3. Update `ui/src/App.tsx` to route `kind: "hardship"` to `HardshipBanner` instead of the card grid.
4. `?narrative=off` collapses `HardshipBanner` to v2.0 shape (no banner rendered — same as if the customer wasn't found, or show a minimal non-narrative version).
5. Add CUST-006 hardship mock to `ui/src/lib/mock/recommendations.ts`.
6. Add CUST-006 to `ui/src/personas.ts` persona chips.
7. Vitest tests for HardshipBanner rendering, `?narrative=off` collapse, and mock fixture.

**Success criteria:**
- HardshipBanner renders at 1280×800 without breaking above-the-fold layout (UI-01)
- `?narrative=off` collapses the banner (D-10 single-flag contract)
- Mock mode serves CUST-006 with hardship shape
- All existing UI tests pass (no regression on recommendation rendering)

### 14-05: Stack-policy lift ceremony (autonomous: false)

**Goal:** Deploy Phase 14 changes to the live stack and verify end-to-end.

**Changes:**
1. Pre-capture baseline for CUST-001/002/003/006
2. Lift deny-Update:* on CustomerTariffAgent + CustomerTariffApi (+ CustomerTariffFrontend if UI changes deploy via Amplify)
3. `cdk deploy` target stacks
4. Close-gates:
   - SAV-03 byte-equivalence on CUST-001/002/003 (existing personas unchanged)
   - CUST-006 returns HTTP 200 with `kind: "hardship"` body
   - CUST-006 body has no `green`/`cheapest` keys, no plan IDs
   - CUST-999 still returns HTTP 404
   - `pytest -m smoke -x` green
5. Re-apply freeze + termination protection
6. Final sweep

**Success criteria:**
- All close-gates pass
- Stacks re-frozen with byte-equal policies
- Ceremony log committed
