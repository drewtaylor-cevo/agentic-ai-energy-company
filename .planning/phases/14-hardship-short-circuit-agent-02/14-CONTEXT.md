# Phase 14 Context — Hardship Short-Circuit (AGENT-02)

## Goal

When a customer record carries `hardship_flag: true`, the agent refuses tariff recommendations via a code-enforced pre-LLM guard and returns a dignity-preserving routing response, without regressing customer-not-found detection or the D-04 never-500 contract.

## Requirements

- **AGENT-02:** Hardship short-circuit branch — discriminated union `kind: "recommendation" | "hardship"`
- **AGENT-02a:** `api_lambda/handler.py:152` updated so missing green/cheapest doesn't false-positive on hardship
- **AGENT-02b:** D-04 never-500 preserved — hardship returns HTTP 200, not 404 or 500

## Dependencies

- Phase 13 (complete): Tools Lambda action dispatcher, `get_hardship_flag` tool, reasoning trace
- Phase 13.1 (complete): UNKNOWN sentinel at `api_lambda/handler.py`, SHORT-CIRCUIT RULE in prompt
- Phase 11 (complete): CUST-006 persona with `hardship_flag: true` PROFILE row in DynamoDB

## Key Design Decisions

### D-14-01: Pre-LLM guard location
The hardship check fires in `invoke()` BEFORE the `_agent()` call. It calls `get_provider().get_hardship_flag(customer_id)` directly — no LLM involvement. If `hardship: true`, return immediately with the hardship response shape. The LLM never sees tariff context for hardship customers.

### D-14-02: Response shape (LD-2)
Pydantic discriminated union on `kind` field:
```python
class HardshipResponse(BaseModel):
    kind: Literal["hardship"]
    customer_id: str
    reason: str  # dignity-preserving, D-15 validated
    routing_target: str  # "hardship_team"
    call_script: str  # D-15 validated, ≤22 words

class RecommendationResponseV2(BaseModel):
    kind: Literal["recommendation"]
    green: TrackInfo
    cheapest: TrackInfo
    reasoning_trace: list[ReasoningTraceEntry]
```

### D-14-03: API Lambda surgical update
```python
# Phase 14: hardship responses legitimately lack green/cheapest
if "green" not in body or "cheapest" not in body:
    if body.get("kind") == "hardship":
        # Pass through — hardship is a valid 200 response
        pass
    else:
        return _error(404, f"Customer {customer_id} not found.")
```
The UNKNOWN sentinel check stays below this — it only applies to recommendation-shaped responses.

### D-14-04: Narrative validators on hardship surface
Both `reason` and `call_script` on the hardship response must pass D-15 validators (no digits, no currency, no banned terms, no plan IDs). Hardship fallback strings committed to `agent/narrative/fallbacks.py`.

### D-14-05: UI HardshipBanner
New component replaces the card grid when `kind === "hardship"`. Collapsed by `?narrative=off` to v2.0 shape (no hardship banner, no cards — just the error-like state).

## Invariants to preserve

- **SAV-03:** No arithmetic on hardship branch (no savings computed)
- **REC-03:** Both tracks always present on `kind: "recommendation"` branch (unchanged)
- **D-04:** Never 500 — hardship returns HTTP 200
- **D-12:** Customer-not-found detection updated, not broken
- **D-15:** Narrative validators apply to hardship `reason` + `call_script`
- **SC-3:** `runtimeSessionId` fresh per invocation (hardship branch skips agent call entirely)

## Existing code touchpoints

| File | What changes |
|------|-------------|
| `agent/agent.py` | Pre-LLM guard in `invoke()`, `HardshipResponse` model |
| `api_lambda/handler.py` | Surgical update to D-12 detection + UNKNOWN sentinel ordering |
| `agent/narrative/fallbacks.py` | Add CUST-006 hardship fallback strings |
| `tests/conftest.py` | Add hardship response fixtures |
| `tests/test_backend_api_handler.py` | Both-branch pytest for hardship vs 404 |
| `ui/src/components/HardshipBanner.tsx` | New component |
| `ui/src/App.tsx` | Route `kind: "hardship"` to HardshipBanner |
| `ui/src/hooks/useRecommendations.ts` | Handle hardship response shape |
| `ui/src/lib/mock/recommendations.ts` | Add CUST-006 hardship mock |
