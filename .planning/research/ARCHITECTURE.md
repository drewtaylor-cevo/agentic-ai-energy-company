# Architecture Research — v3.0 Agentic Depth Integration

**Domain:** AWS Bedrock AgentCore agent-assist — Energy & Utilities call centre (subsequent milestone, additive to frozen `demo-v2.0`)
**Platform:** AWS Bedrock AgentCore (Strands SDK + `BedrockAgentCoreApp`) — **4-stack split LOCKED**
**Researched:** 2026-04-28
**Confidence:** HIGH on existing-stack shape (read from source of truth); HIGH on AgentCore Memory + Strands multi-tool semantics (docs confirm); MEDIUM on UI surfacing of tool-chain trace (requires Strands agent_result inspection)

> **Scope discipline.** This document extends the frozen 4-stack v2.0 architecture. It does **not** redesign v2.0. Layer boundaries, the fresh-`uuid4()` runtimeSessionId rule, the SAV-03 no-arithmetic invariant, the REC-03 two-tracks-always contract, the D-04 never-500 guarantee, the D-15 narrative dual-gate, the `_narrative_source` strip at the API Lambda, and the "customer-not-found = missing green/cheapest keys" detection are **load-bearing** inherited invariants. Each recommendation below names explicitly which invariants it preserves or risks.

---

## Standard Architecture — v3.0 Delta Over v2.0

The four-stack CDK layout is preserved exactly. v3.0 adds:

- New methods/actions on the existing Tools Lambda (no new Lambdas)
- New `@tool` functions on the existing Strands agent
- A new Pydantic response **discriminated union** (existing `RecommendationResponse` + new `HardshipRoutingResponse`)
- A new API route `GET /recommendations/{customer_id}/follow-up` on the existing API Gateway
- New data rows in the existing DynamoDB `tariff-billing` table (no new tables, no schema migration)
- One new DynamoDB item shape for the hardship flag (attribute on the customer profile item, stored alongside existing billing rows via a different sort key prefix)
- One new AgentCore Memory resource (independent AWS resource; wired via SSM like the existing runtime ARN)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                  CALL CENTRE UI (Amplify — unfrozen)                     │
│   React/Vite — 1280px, shadcn/ui, skeleton-first                         │
│                                                                          │
│   RecommendationCard (existing — renders green + cheapest)              │
│   HardshipBanner (NEW v3.0 — renders when response.kind=="hardship")    │
│   ReasoningTrace (NEW v3.0 — collapsed-by-default "what the agent did") │
│   FollowUpEmailDrawer (NEW v3.0 — rep-side action, second API call)     │
└────────┬───────────────────────────────┬────────────────────────────────┘
         │ GET /recommendations/{id}     │ GET /recommendations/{id}/follow-up
         │ (existing route)              │ (NEW v3.0 route on same API GW)
         ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│          API GATEWAY HTTP v2 + API LAMBDA (Phase 3 stack — UNFROZEN    │
│          at route level; stack policy denies Update:* but route add     │
│          requires policy lift, see §Stack Policy Impact below)          │
│                                                                          │
│   handler.handler  (existing — GET /recommendations/{customer_id})      │
│   handler.follow_up (NEW v3.0 — GET /recommendations/{id}/follow-up)    │
│                                                                          │
│   • runtimeSessionId generation: UNCHANGED in existing handler          │
│     (fresh uuid4 inside handler — SC-3 invariant preserved)             │
│   • Follow-up handler uses DETERMINISTIC session_id derived from        │
│     {customer_id} + ISO-day (so turn 1 and turn 2 land in same         │
│     AgentCore Memory session without leaking across personas/days)     │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │  bedrock-agentcore.invoke_agent_runtime
                           │   payload: {"customer_id", "action"}
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│            BEDROCK AGENTCORE RUNTIME (Phase 2 stack — frozen container) │
│            ARM64 Python 3.12 Docker container                           │
│                                                                          │
│   BedrockAgentCoreApp.entrypoint  (existing invoke() dispatcher)        │
│     ├── action == "recommend" (default — UNCHANGED)                     │
│     │     └── existing tool simulate_savings                            │
│     ├── action == "bill_shock_flow" (NEW v3.0 — AGENT-01)               │
│     │     ├── get_billing_history    (tool — NEW wrapper)               │
│     │     ├── detect_bill_shock      (tool — NEW)                       │
│     │     ├── get_hardship_flag      (tool — NEW)                       │
│     │     └── simulate_savings       (tool — existing)                  │
│     └── action == "draft_follow_up" (NEW v3.0 — WF-01)                  │
│           ├── AgentCore Memory: session.get_last_k_turns(k=5)           │
│           └── Structured output: FollowUpEmailResponse (NEW schema)     │
│                                                                          │
│   MemorySessionManager (NEW v3.0 — bedrock_agentcore.memory)            │
│   Environment: MEMORY_ID (injected by CDK — NEW SSM parameter)          │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │  lambda:Invoke (existing IAM)
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│            TOOLS LAMBDA (Phase 1 stack — frozen — LITERALLY FROZEN)     │
│            /app/handler.py                                              │
│                                                                          │
│   Existing entrypoints (unchanged):                                     │
│     simulate_savings(event, context)      SAV-03 authoritative          │
│     get_billing_history(event, context)   already exists                │
│                                                                          │
│   NEW v3.0 — action-dispatch entrypoint (RECOMMENDED):                  │
│     handler(event, context):                                            │
│       action = event.get("action", "simulate_savings")                  │
│       dispatch → simulate_savings | get_billing_history |               │
│                  detect_bill_shock | get_hardship_flag |                │
│                  get_customer_profile                                    │
│                                                                          │
│   New pure helpers (testable offline):                                  │
│     detect_bill_shock_pure(billing_history) → {is_shock, delta}         │
│     get_hardship_flag_pure(profile_item)    → {hardship, reason}        │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │  dynamodb.query
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│            DYNAMODB (Phase 1 stack — frozen table)                      │
│   Table: tariff-billing                                                 │
│                                                                          │
│   Existing rows (CUST-001 / 002 / 003):                                 │
│     PK: customer_id (S) — e.g. "CUST-001"                               │
│     SK: month        (S) — e.g. "2025-12"                               │
│                                                                          │
│   NEW v3.0 rows:                                                        │
│     CUST-004, CUST-005  → 12 months each (solar PV, EV persona)        │
│     Hardship-flag item:                                                 │
│       PK: customer_id    SK: "PROFILE"   attrs: hardship_flag, reason   │
└─────────────────────────────────────────────────────────────────────────┘

NEW side resource (not on the hot path):

┌──────────────────────────────────────────────────────────┐
│  AgentCore Memory resource (standalone — via bedrock-    │
│  agentcore-control)                                      │
│    - short-term: last-k turns per session_id             │
│    - actor_id: customer_id                               │
│    - session_id: {customer_id}-{ISO-day}  (per §3 below) │
└──────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities (v3.0 — incremental)

| Component | Existing responsibility | v3.0 addition |
|-----------|------------------------|----------------|
| UI `RecommendationCard` | Render green + cheapest track | **None** (card itself unchanged) |
| UI `HardshipBanner` (NEW) | — | Render when response `kind == "hardship"`; replaces card grid with hardship routing stub |
| UI `ReasoningTrace` (NEW) | — | Collapsed-by-default disclosure showing ordered tool-call list from agent payload |
| UI `FollowUpEmailDrawer` (NEW) | — | Slide-over showing draft email; fires second API call |
| API Lambda `handler.handler` | GET recommendations proxy, strip `_narrative_source`, customer-not-found detection | **Discriminated union branch** — when response has `kind=="hardship"`, still return 200 with hardship body (NOT a 404) |
| API Lambda `handler.follow_up` (NEW) | — | GET follow-up; deterministic session_id; proxy to agent with `action=draft_follow_up` |
| Agent `invoke()` entrypoint | Single path: structured_output RecommendationResponse | **Action dispatch**: `recommend` (default), `bill_shock_flow`, `draft_follow_up` |
| Agent tools | `simulate_savings` | **NEW**: `get_billing_history` (wrapper on Tools Lambda action), `detect_bill_shock`, `get_hardship_flag`, `get_customer_profile` |
| Tools Lambda `handler` | Two module-level functions (`simulate_savings`, `get_billing_history`) with direct DynamoDB access | **Action dispatcher** with the same two functions plus 3 new pure helpers |
| `CustomerDataProvider` (NEW) | — | Protocol (agent-side `@tool` layer) that wraps all Tools-Lambda invocations — see §4 |
| DynamoDB `tariff-billing` | 3 personas × 12 months billing rows | **+2 personas × 12 months** + **5 PROFILE items** (one per persona) carrying hardship_flag |
| AgentCore Memory (NEW resource) | — | Store turn history; enable follow-up turn to reason about recent recommendation |

---

## Integration Points — Per v3.0 Feature

### 1. AGENT-01 — Bill-Shock Multi-Tool Flow

**Decision: Option (c) — Single Tools Lambda with `action=...` dispatch.**

Three options compared:

| # | Strategy | IAM surface | Deploy cadence | SAV-03 invariant | Bi-mode imports | Cold starts |
|---|----------|-------------|----------------|------------------|-----------------|-------------|
| **(a)** New `@tool` functions on agent calling existing Tools Lambda methods | Unchanged | Container rebuild only | Preserved — all arithmetic stays in Tools Lambda | Works — new tools live in `agent/` module | One (existing Tools Lambda) |
| **(b)** Separate Lambda per tool (bill-shock Lambda, hardship Lambda) | New IAM grant per Lambda; agent's `lambda:InvokeFunction` policy widens; each new Lambda gets its own DynamoDB read grant | **New CDK construct per Lambda + SSM parameter wiring per Lambda** — 2-3× the freeze surface | Preserved | Works | 2-3 new cold-start surfaces |
| **(c)** Single Tools Lambda, action dispatch | Unchanged | Tools Lambda asset rebuild + agent container rebuild | Preserved — new helpers are pure Python co-located with `simulate_savings_pure` | Works — same module | One |

**Why (c):**

- **SAV-03 invariant preserved byte-exact.** All deterministic logic stays in `lambda/handler.py`. `detect_bill_shock_pure(billing_history)` sits next to `simulate_savings_pure` and shares the same `DAYS_PER_MONTH` constant. Agent system prompt can say "ALL arithmetic (savings, bill-shock delta, averages) comes from the `simulate_savings` and `detect_bill_shock` tools. NEVER compute numbers yourself" — the same rule generalises naturally.
- **Minimal freeze surface expansion.** Tools Lambda is in the frozen `CustomerTariff` stack. Adding functions to `lambda/handler.py` ships in the same Lambda asset — one asset diff, one deploy. Option (b) would add 2-3 new CDK constructs, 2-3 new SSM parameters, and 2-3 new lines in `agent_runtime.py`'s IAM policy. Every one of those is a lift-stack-policy operation.
- **Agent-side tool registry stays compact.** Strands `@tool` decorators stay in one file (`agent/agent.py` or a new `agent/tools.py`). Each `@tool` is a thin wrapper that marshals `{"action": "...", ...}` into the existing `_lambda_client.invoke()` call.

**UI surfacing of the tool chain (UI-01 preservation):**

Strands `agent_result.message` already contains the full tool-call trace in `content[].toolUse` blocks (we already use this for narrative salvage at `agent/agent.py:214-236`). To surface reasoning without breaking UI-01 (both cards above the fold at 1280px):

1. **Agent collects trace into payload.** After `agent_result` returns, iterate `agent_result.message["content"]` collecting all `toolUse` blocks into a simple list `[{"tool": "detect_bill_shock", "args": {...}, "summary": "bill shock detected: +$47 Dec vs 11-month avg"}]`. Attach as a NEW optional `_reasoning_trace` field on the response body, mirroring the `_narrative_source` pattern.
2. **API Lambda strips `_reasoning_trace` OR passes through.** Recommend **pass-through** (contra `_narrative_source`), because the UI needs to render it. Adds a field to the public API contract — acceptable because UI-01 treats it as optional/collapsed.
3. **UI renders as collapsed-by-default disclosure.** A `<details>` block below the card grid labelled "Agent reasoning (3 steps)". Zero vertical cost above the fold when collapsed. Matches the demo story "visible reasoning" without breaking UI-01.

**Integration points:**

| Surface | Change type | Risk to invariants |
|---------|-------------|---------------------|
| `lambda/handler.py` | **MODIFY** — add `handler(event, context)` action dispatcher on top of existing functions (keep the old entrypoints for backwards compat during migration) | Low — pure helpers are offline-testable (mirrors `simulate_savings_pure` pattern) |
| `lambda/tariff_plans.json` | **NO CHANGE** | — |
| `infrastructure/constructs/tools_lambda.py` | **NO CHANGE** — same asset, same handler path, same env vars | Zero — Tools Lambda CDK construct is not touched |
| `agent/agent.py` (or new `agent/tools.py`) | **MODIFY** — add 3 new `@tool` wrappers | Low — each tool is a ~15-line wrapper over `_lambda_client.invoke()` |
| Agent system prompt | **MODIFY** — extend SAV-03 language to cover new arithmetic tools; add "call tools as needed; don't call unnecessary tools" guidance | Medium — this is the AGENT-01 "visible reasoning" prompt tuning |
| Agent container | **REBUILD** — Dockerfile `COPY . /app` picks up new tools; SSM-wired ARN unchanged | Low — frozen runtime identity (ARN) preserved; only the image digest changes |
| API Lambda | **NO CHANGE** to the route itself; passes `_reasoning_trace` through | Low — extending pass-through is additive |
| UI `RecommendationCard` | **NO CHANGE** | — |
| UI `ReasoningTrace` (new component) | **NEW** | None — collapsed by default preserves UI-01 |

**Invariants preserved:** SAV-03 (all math in Tools Lambda), REC-03 (still emits both tracks on the default `recommend` action), UI-01 (collapsed trace = zero vertical cost), bi-mode imports (new tools live in same `agent/` module tree).

**Invariants at risk:** None structurally. One behavioural risk: the multi-tool flow extends the agent turn budget by ~400–900ms (3 extra tool invocations at 50–150ms Lambda cold call each, plus extra LLM thinking tokens). UI-02 (<3s lookup-to-render) needs re-measurement in the AGENT-01 rehearsal. This is a measurement risk, not a correctness risk.

---

### 2. AGENT-02 — Hardship Short-Circuit

**Decision: Option (a) — Pydantic discriminated union on response.**

Three options compared:

| # | Strategy | D-04 never-500 | Customer-not-found detection | Schema clarity | UI coupling |
|---|----------|----------------|-------------------------------|-----------------|--------------|
| **(a)** Discriminated union — `RecommendationResponse` OR `HardshipRoutingResponse` keyed on `kind` field | Preserved — hardship IS a success response | **Breaks** `"green" not in body or "cheapest" not in body` detection (line 152) | Cleanest — two coherent shapes, no optional fields | UI branches on `kind` |
| **(b)** Extend existing shape with optional `hardship_routing` field; both tracks still present | Preserved | Preserved (tracks always present) | Muddy — agent must still generate tracks it shouldn't recommend | UI has to decide: render tracks + banner, or just banner? |
| **(c)** Return 200 with empty tracks + explicit `hardship=true` flag | Preserved | **Breaks** the same detection — either rewrite detection or accept 404 on hardship | Medium — requires contract addendum | UI branches on flag |

**Why (a):**

- **REC-03 (two tracks always returned, never ranked) survives philosophically**, because REC-03 applies specifically to the **recommendation** flow. Hardship is a different response type — it does not rank anything, so REC-03 doesn't apply. Option (b) violates the spirit of REC-03: you'd be returning two tracks you're telling the rep NOT to recommend.
- **D-04 (never-500) preserved.** Hardship is still a 200 from the API Lambda — just with a different body shape. Nothing about the never-500 contract changes.
- **Customer-not-found detection needs a surgical fix.** Currently: `if "green" not in body or "cheapest" not in body: return 404`. This fires on hardship responses (they don't have `green`/`cheapest`). Fix: change detection to `if body.get("kind") == "not_found" or ("green" not in body and "kind" not in body): return 404`. Still robust against the agent's tool-failure fallback path returning `{"errorMessage": "..."}` (no `kind` field, no tracks → matches the fallback branch).

**Schema:**

```python
# agent/agent.py — NEW
class HardshipRoutingResponse(BaseModel):
    kind: Literal["hardship"] = "hardship"
    customer_id: str
    reason: str = Field(max_length=200)  # human-readable; D-15 banned terms apply
    routing_target: Literal["hardship_team"] = "hardship_team"
    call_script: str = Field(max_length=CALL_SCRIPT_MAX_CHARS)  # rep reads verbatim
    _validate_call_script = validate_call_script  # REUSE D-15 validator

class RecommendationResponse(BaseModel):
    kind: Literal["recommendation"] = "recommendation"  # NEW — required for discriminator
    green: TrackInfo
    cheapest: TrackInfo

# Discriminated union — agent returns ONE of these
AgentResponse = Annotated[
    Union[RecommendationResponse, HardshipRoutingResponse],
    Field(discriminator="kind"),
]
```

**Backwards compatibility note:** Adding `kind: Literal["recommendation"]` to the existing schema is a **breaking change** for the frozen UI — the UI currently parses `RecommendationResponse` without a `kind` field. Two mitigations:

1. Make `kind` optional on the Python side with default `"recommendation"` — serialises to `"kind": "recommendation"`, which the Zod/TS schema on the UI side can ignore (the existing `RecommendationResponse` TS interface doesn't declare `kind`, and TypeScript structurally-typed JSON.parse doesn't care about extra fields).
2. Update the UI TS type to make `kind?: "recommendation" | "hardship"` optional — same backwards-compat, but gives the UI the branch point.

Recommend **both** — emit `kind` on the backend always (future-proofs the API); UI adds optional `kind` and branches on `kind === "hardship"`.

**Integration points:**

| Surface | Change type | Risk to invariants |
|---------|-------------|---------------------|
| `lambda/handler.py` | **MODIFY** — add `get_hardship_flag(event, context)` action reading DynamoDB SK=`"PROFILE"` item | Low — new helper, offline-testable, no impact on existing `simulate_savings_pure` |
| `infrastructure/seed_data/billing_records.py` | **MODIFY** — add `PROFILE` items for existing personas (hardship_flag=False) + new personas (CUST-004 false, CUST-005 true if we want a demo hardship persona) | Low — additive |
| `agent/agent.py` schema | **MODIFY** — add `HardshipRoutingResponse`, discriminated union, new `kind` field on `RecommendationResponse` | **Medium** — schema change; narrative validators still apply to hardship's `call_script`; tests must cover both branches |
| Agent system prompt | **MODIFY** — add "FIRST check hardship_flag; if true, emit HardshipRoutingResponse and STOP (do NOT recommend plans)" | Medium — this is the AGENT-02 correctness prompt; needs offline test coverage |
| Agent fallback bank | **MODIFY** — `narrative/fallbacks.py::FALLBACKS` extended to cover hardship response salvage (different shape; simpler — just `call_script` field) | Low — additive |
| API Lambda `handler.handler` line 152 | **MODIFY** — customer-not-found detection now checks `kind` field | **High attention** — this is the detection logic; all existing tests for 404-on-missing-tracks still need to pass, plus new tests for 200-on-hardship |
| UI `RecommendationResponse` TS type | **MODIFY** — add `kind?: "recommendation" \| "hardship"` | Low — backwards-compat optional |
| UI `HardshipBanner` (new component) | **NEW** — renders when `data.kind === "hardship"` | None |
| UI App routing | **MODIFY** — `<RecommendationCard />` vs `<HardshipBanner />` branch | Low — single conditional |

**Invariants preserved:** D-04 (200 not 500), REC-03 (still holds on recommendation branch), D-15 (narrative validators still apply to hardship `call_script`), bi-mode imports.

**Invariants at risk:**
- **Customer-not-found detection (api_lambda/handler.py:152)** — MUST be updated in lockstep with the schema change. Risk is a regression where a real "customer not in DynamoDB" response (which comes back with `{"errorMessage": ...}` from the agent's fallback path) starts returning 200 instead of 404. Mitigation: the updated check is `if "green" not in body and body.get("kind") != "hardship": return 404` — still fires on the fallback error, passes hardship.
- **`_narrative_source` strip (api_lambda/handler.py:121)** — if hardship response doesn't carry `_narrative_source`, the `.pop(..., None)` already handles it; no change needed.

---

### 3. WF-01 — Follow-Up Email via AgentCore Memory

**Decision: NEW API route `GET /recommendations/{customer_id}/follow-up` + deterministic session_id derived from `{customer_id}-{ISO-day}`.**

**Key question: does this break the "runtimeSessionId generated INSIDE handler()" invariant (SC-3 / Pitfall 2)?**

Answer: **No, but it requires a narrow exception documented at the call site.** The SC-3 invariant reads in full: "runtimeSessionId generated INSIDE `handler()`, not at module scope. Module-level caching causes session bleed between persona lookups." The invariant is about **preventing session bleed between personas**, not about forbidding reuse across turns for the *same* persona. A deterministic session_id scoped to `{customer_id}-{ISO-day}` has two properties:

1. Generated inside `handler()` (or `follow_up()`) per invocation — satisfies the "not module scope" clause.
2. Identical across turn 1 (recommend) and turn 2 (follow-up) for the same customer on the same day — enables AgentCore Memory to retrieve prior turns.
3. Different for different customers (hash key includes customer_id) — prevents bleed.
4. Different for the same customer on different days (ISO-day suffix) — prevents stale context leaking into tomorrow's demo (and satisfies D-15 / demo-day freshness).

Effectively: the fresh-uuid4 in the existing `handler()` is intentional because turn 1 has no history to reuse; the deterministic ID in `follow_up()` is intentional because turn 2 DOES have history and wants to reuse it.

**Route vs same-endpoint-with-action:**

| # | Route strategy | API Gateway change | Session scoping | D-12 taxonomy reuse |
|---|----------------|--------------------|-----------------|---------------------|
| **(a)** New route `GET /recommendations/{id}/follow-up` | Additive route on existing API GW | Clean — URL itself scopes turn | Reuses `_error()` helper |
| **(b)** Same endpoint with `?action=draft_email` query | No new route — query param only | Same URL both turns; handler branches on query | Reuses `_error()` helper |
| **(c)** Same route, POST with body `{"action":"draft_email"}` | Route method change (GET → POST? or add POST?) | Same as (b) | Reuses `_error()` helper |

**Why (a):**

- **Freeze surface discipline.** `CustomerTariffApi` stack has the deny-Update:* policy. Adding a new route requires a policy lift anyway (it's a `UpdateRestApi` operation), so we might as well do it cleanly. Option (b) also requires a Lambda code deploy, which touches the same stack.
- **Clearer IAM / observability.** API Gateway access logs distinguish the two routes naturally. Turn 1 and turn 2 show as separate log lines — useful for the demo story.
- **REST semantics.** GET `/recommendations/{id}/follow-up` reads naturally as "give me the follow-up for this customer's recommendation."

**Session correlation — how turn 1 and turn 2 land in the same Memory session:**

```
Turn 1 (recommend):
  UI: GET /recommendations/CUST-001
  API Lambda:
    session_id = str(uuid.uuid4())           # EXISTING — unchanged
    invoke_agent_runtime(runtimeSessionId=session_id, ...)
    → agent runs; writes turn to Memory via session.add_turns()
      where Memory session = {"customer_id": "CUST-001", "date": "2026-04-28"}
                              ^^^ AgentCore Memory session_id ≠ runtimeSessionId!

Turn 2 (draft follow-up):
  UI: GET /recommendations/CUST-001/follow-up
  API Lambda follow_up():
    runtime_session_id = str(uuid.uuid4())   # fresh per invocation (SC-3)
    memory_session_id  = f"CUST-001-2026-04-28"  # deterministic, derived in handler
    invoke_agent_runtime(
        runtimeSessionId=runtime_session_id,  # fresh — microVM routing concern
        payload=json.dumps({
            "action": "draft_follow_up",
            "customer_id": "CUST-001",
            "memory_session_id": memory_session_id,  # passed to agent
        }),
    )
    → agent reads session.get_last_k_turns(memory_session_id, k=5)
       gets turn 1's recommendation context
       emits FollowUpEmailResponse
```

**Critical distinction — these are two different session concepts:**

- **AgentCore `runtimeSessionId`** — scopes the microVM routing. Fresh uuid4 per invocation (SC-3). Controls which warm microVM serves the request.
- **AgentCore Memory `session_id`** — scopes the conversation history. Deterministic `{customer_id}-{ISO-day}`. Controls which turns are retrievable.

The Memory session_id is **just a string key in the Memory store**, not tied to the runtime session. This is the key insight: Memory sessions and runtime sessions are orthogonal. The SC-3 invariant only applies to runtime sessions.

**Stateless UI note:** The UI does not carry cookies. The UI holds `customer_id` in React state from turn 1's form submit; turn 2's API call passes the same `customer_id` in the URL. The API Lambda deterministically computes the Memory session_id from `{customer_id}-{today}`. Truly stateless request/response.

**Does the API Lambda need Memory reads too?** No — **the agent reads Memory, not the API Lambda**. The API Lambda's job is to invoke the agent and return the response. Pushing Memory reads into the API Lambda would duplicate a concern that belongs in the agent container (the LLM needs to *reason over* the memory, not just have it JSON-serialised into the payload).

**New Pydantic schema:**

```python
# agent/agent.py — NEW
class FollowUpEmailResponse(BaseModel):
    kind: Literal["follow_up_email"] = "follow_up_email"
    customer_id: str
    subject: str = Field(max_length=100)   # email subject
    body: str = Field(max_length=800)      # email body (longer than call_script — this is rep-side)
    plan_reference: str                    # which plan was discussed (from memory)
    _validate_body = validate_call_script  # D-15 validator scaled up; or new validator
```

**Integration points:**

| Surface | Change type | Risk to invariants |
|---------|-------------|---------------------|
| NEW AWS resource: AgentCore Memory | **NEW CDK construct** `infrastructure/constructs/agent_memory.py` — creates Memory, writes ID to SSM `/customer-tariff/memory-id` | Low — additive infrastructure; mirrors existing SSM-wiring pattern (Pitfall 5 resolved) |
| `infrastructure/agentcore_stack.py` | **MODIFY** — instantiate `AgentMemoryConstruct`, pass `MEMORY_ID` to agent runtime env | **Stack policy lift required** — `CustomerTariffAgent` has deny-Update:* |
| Agent container | **REBUILD** — import `bedrock_agentcore.memory.MemorySessionManager`, wire into both the existing `invoke()` (write turn) and new `draft_follow_up` branch (read turns) | Medium — new dependency in `agent/requirements.txt`; must stay reproducible under `--require-hashes` |
| Agent IAM role | **MODIFY** — add `bedrock-agentcore:CreateEvent`, `bedrock-agentcore:ListEvents`, `bedrock-agentcore:GetMemoryRecord` on the Memory ARN | Low — scoped to specific resource |
| `api_lambda/handler.py` | **MODIFY** — add `follow_up()` function; new route dispatch | **Stack policy lift required** — `CustomerTariffApi` has deny-Update:* |
| `infrastructure/constructs/backend_api.py` | **MODIFY** — add second route `/recommendations/{customer_id}/follow-up` | Same |
| UI `FollowUpEmailDrawer` | **NEW** | None |
| UI state | **MODIFY** — React state holds turn 1 result; "Draft follow-up email" button fires second GET | None — same stateless pattern |

**Invariants preserved:** SC-3 (runtimeSessionId still fresh uuid4 inside handler), D-04 (still 200 or handled 4xx/5xx taxonomy), D-12 error taxonomy (reused), REC-03 (doesn't apply — follow-up is its own shape).

**Invariants at risk:**
- **Stack policy on `CustomerTariffAgent` and `CustomerTariffApi`** — both require policy lift to redeploy. This is an operational risk (freeze ceremony must be repeated on demo day — v3.0 essentially cuts a new `demo-v3.0` tag and a new freeze manifest).
- **Memory freshness across demo days** — ISO-day in the session_id means if you rehearse at 23:59 and demo at 00:01, the session_id changes and memory from rehearsal is invisible. Mitigation: rehearsal must be same calendar day as demo (already in the runbook implicitly; make it explicit). Alternative: use `{customer_id}-{demo-run-id}` and inject `demo-run-id` from the presenter's env — more control, more complexity.
- **`--require-hashes` pinning** — adding `bedrock-agentcore.memory` may pull in new dependencies. Regenerate `requirements.txt` with pip-compile and update the freeze manifest.

---

### 4. PROD-01 — `CustomerDataProvider` Abstraction

**Decision: Option (a) — `agent/providers.py` (agent-side Protocol injected into tools).**

Three options compared:

| # | Location | Who implements it | Tool-side change | Bi-mode imports | Container rebuild needed for tool-side change |
|---|----------|-------------------|------------------|-----------------|------------------------------------------------|
| **(a)** `agent/providers.py` — agent-side Protocol wrapping Tools Lambda calls | Agent `@tool` wrappers | None — Tools Lambda stays DynamoDB-direct | Works — new file in `agent/` | **NO** — tool-side changes don't trigger rebuild; only the abstraction layer |
| **(b)** `lambda/providers.py` — tool-side Protocol replacing direct DynamoDB in Tools Lambda | Tools Lambda | Tools Lambda refactor — `table.query()` replaced with `provider.get_billing_history()` | N/A (tool-side only) | Tools Lambda rebuild per change |
| **(c)** Shared `common/providers.py` — shared package imported by both | Both layers | Requires shared-package deployment model | **Breaks** bi-mode pattern — container layout has `common/` only if Dockerfile COPIES it | Both rebuild per change |

**Why (a):**

- **Bi-mode imports preserved cleanly.** Put `providers.py` in `agent/` — container Dockerfile already COPYs `agent/` contents; repo pytest imports via `agent.providers`. Same pattern as `narrative/`.
- **Tool-side (Tools Lambda) stays unchanged.** The abstraction is about **swapping where the agent gets customer data** — not about swapping DynamoDB inside Tools Lambda. In a real CRM deployment, you'd replace the Tools Lambda entirely (with a CRM-adapter Lambda) OR the agent would call the CRM directly (bypassing Tools Lambda). Either way, the abstraction lives **above** Tools Lambda, not inside it.
- **Option (c) shared package is overkill for demo scope.** It requires packaging discipline (pyproject, editable installs, container Dockerfile COPY semantics) that v3.0 doesn't need. Plus it breaks the bi-mode pattern: the container only has what `Dockerfile COPY` puts there, so `common/` would need its own COPY line.
- **Option (b) would mean rebuilding Tools Lambda on every provider change** — more freeze-surface churn.

**The Protocol:**

```python
# agent/providers.py — NEW
from typing import Protocol, List, Dict, Any, runtime_checkable

@runtime_checkable
class CustomerDataProvider(Protocol):
    """Production-shaped adapter. DynamoDB impl is the demo; a CRM impl is the target."""

    def get_billing_history(self, customer_id: str) -> List[Dict[str, Any]]:
        """Return list of monthly billing records sorted ascending by month."""

    def get_customer_profile(self, customer_id: str) -> Dict[str, Any]:
        """Return customer profile including hardship_flag."""

    def get_tariff_catalog(self) -> List[Dict[str, Any]]:
        """Return available tariff plans."""


# Concrete impl for demo — wraps Tools Lambda invocations
class ToolsLambdaProvider:
    def __init__(self, lambda_client, tools_lambda_arn: str):
        self._client = lambda_client
        self._arn = tools_lambda_arn

    def get_billing_history(self, customer_id):
        return self._invoke({"action": "get_billing_history", "customer_id": customer_id})

    def get_customer_profile(self, customer_id):
        return self._invoke({"action": "get_customer_profile", "customer_id": customer_id})

    def get_tariff_catalog(self):
        return self._invoke({"action": "get_tariff_catalog"})

    def _invoke(self, payload):
        resp = self._client.invoke(
            FunctionName=self._arn,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode(),
        )
        return json.loads(resp["Payload"].read())


# In-memory impl for offline pytest (DOC-03 stub visibility)
class InMemoryProvider:
    def __init__(self, billing, profiles, tariffs):
        self._billing = billing
        self._profiles = profiles
        self._tariffs = tariffs
    ...
```

Agent `@tool` wrappers then take a provider:

```python
# agent/agent.py
_provider = ToolsLambdaProvider(_lambda_client, _TOOLS_LAMBDA_ARN)

@tool
def get_billing_history(customer_id: str) -> list:
    return _provider.get_billing_history(customer_id)
```

Tests inject `InMemoryProvider` via a setter or module-level mock — preserves the existing pytest offline pattern without AWS.

**Integration points:**

| Surface | Change type | Risk to invariants |
|---------|-------------|---------------------|
| `agent/providers.py` | **NEW FILE** | None — additive |
| `agent/agent.py` | **MODIFY** — module-level `_provider = ToolsLambdaProvider(...)`; `@tool` wrappers delegate to provider | Low — preserves bi-mode imports (try `from providers import ...`, fallback `from agent.providers import ...`) |
| `agent/Dockerfile` | **NO CHANGE** — `COPY . /app` already picks up `providers.py` | — |
| `lambda/handler.py` | **NO CHANGE** directly — but **MODIFY** to add `action` dispatcher as per §1 (bill-shock flow). The provider calls into the new actions. | Low |
| Tests | **NEW test file** `tests/test_providers.py` — Protocol contract tests; swap in InMemoryProvider | None — additive |

**Invariants preserved:** Bi-mode imports, SAV-03 (arithmetic still in Tools Lambda, provider is just a wrapper), the agent's Strands SDK pattern.

**Invariants at risk:** None. This is the cleanest of the v3.0 changes.

---

### 5. DATA-04 + REC-04 — New Personas + New Tariff Archetype

**Decision: extend existing seed data files; no new table; new tariff plan rows in BOTH `tariff_plans.json` files.**

Duplicated tariff catalogue reality: `lambda/tariff_plans.json` (Lambda asset) and `infrastructure/seed_data/tariff_plans.json`. The existing CLAUDE.md note says `tests/conftest.py` treats `lambda/tariff_plans.json` as source of truth. New tariff archetype (e.g. `TOU-PV` for time-of-use with feed-in tariff) needs to live in **both** files.

**New persona billing shape:**

- **CUST-004 Solar PV:** negative net usage in summer months (feed-in > consumption), positive in winter. Simplest schema delta: add optional `feed_in_kwh` field to billing records (defaults to 0). `simulate_savings_pure` modification: net_usage = `usage_kwh - feed_in_kwh`. This is a **schema extension**, not a breaking change — existing records without `feed_in_kwh` default to 0.
- **CUST-005 EV:** higher baseline usage (EV charging), overnight TOU pattern. No new billing field needed — just higher `usage_kwh`. The TOU archetype is a new plan type in `tariff_plans.json`.

**`tariff_plans.json` schema extension:**

Existing shape (inferred from `simulate_savings_pure`):
```json
{
  "plan_id": "ECO",
  "plan_name": "EcoFlex100",
  "plan_type": "green_premium",
  "rate_per_kwh": 0.235,
  "daily_supply_charge": 1.15,
  "green_score": 95
}
```

New TOU archetype:
```json
{
  "plan_id": "TOU-PV",
  "plan_name": "SunSaver TOU",
  "plan_type": "time_of_use",
  "rate_per_kwh_peak": 0.41,      // NEW — replaces rate_per_kwh for TOU plans
  "rate_per_kwh_offpeak": 0.12,   // NEW
  "feed_in_rate_per_kwh": 0.08,   // NEW — solar PV exports
  "daily_supply_charge": 1.15,
  "green_score": 80
}
```

This **does break** `simulate_savings_pure` if it's called on a TOU plan with its existing single-rate formula. Two options:

- **(a)** Extend `simulate_savings_pure` to handle TOU plans via a conditional branch on `plan_type`. Ugly but keeps one function.
- **(b)** Add a new pure helper `simulate_tou_savings_pure` invoked when agent detects TOU-eligible customer (solar PV or EV).

**Recommend (a) with a clean dispatch:**

```python
def simulate_savings_pure(billing_history, plans):
    # ... existing avg_kwh + current_plan logic ...
    def projected_monthly_cost(plan):
        if plan["plan_type"] == "time_of_use":
            return _projected_tou_cost(billing_history, plan)
        return avg_kwh * plan["rate_per_kwh"] + plan["daily_supply_charge"] * DAYS_PER_MONTH
    # ... rest unchanged
```

Preserves SAV-03 (arithmetic still deterministic Python), keeps the numeric invariant mockable in tests (mock_cust004_response fixture pins byte-exact savings for solar PV persona).

**Integration points:**

| Surface | Change type | Risk to invariants |
|---------|-------------|---------------------|
| `infrastructure/seed_data/billing_records.py` | **MODIFY** — add `CUST004_RECORDS`, `CUST005_RECORDS`, `PROFILE_ITEMS` (with hardship_flag) | None — additive |
| `infrastructure/seed_data/tariff_plans.json` + `lambda/tariff_plans.json` | **MODIFY** — add TOU-PV plan (both files in same commit; conftest treats lambda/ as source of truth) | **Medium** — drift between the two files was a v1.0 pitfall; committed-in-same-commit discipline required |
| `lambda/handler.py::simulate_savings_pure` | **MODIFY** — plan_type dispatch for TOU | **Medium** — SAV-03 depends on this staying deterministic. New pure helper `_projected_tou_cost` must be offline-testable with byte-exact assertions |
| `tests/conftest.py` | **MODIFY** — add `mock_cust004_response`, `mock_cust005_response` fixtures with pinned savings figures | None — additive |
| `ui/src/personas.ts` + `ui/src/components/PersonaChips.tsx` | **MODIFY** — add CUST-004 and CUST-005 chips | Low — UI list additive |
| `ui/src/lib/mock/*` | **MODIFY** — add mock fallbacks for two new personas; mirror Phase 6 fallback strings byte-exact | Medium — mock fixtures are a freeze-critical emergency-swap artefact |

**Invariants preserved:** SAV-03 (arithmetic remains in pure Python).

**Invariants at risk:**
- **`tariff_plans.json` duplication drift** — already noted in CLAUDE.md as a known risk. Mitigation: a pytest that asserts byte-equivalence of the two files (already exists per CLAUDE.md conftest note; re-run on every v3.0 PR).
- **Mock fixture parity** — `ui/src/lib/mock/` must mirror the Phase 6 fallback strings byte-exact. New personas require new fallback strings in `agent/narrative/fallbacks.py::FALLBACKS` AND corresponding mock fixtures. Freeze ceremony artefact.

---

### 6. DOC-01 / DOC-02 / DOC-03 — Presenter Docs

**Decision: `.planning/docs/presenter/` with cross-links from README and DEMO-RUNBOOK.**

- `.planning/docs/presenter/TRUST-ARCHITECTURE.md` (DOC-01) — one-pager, LLM-bounding patterns (SAV-03, narrative gauntlet, fallback bank, `_narrative_source` observability)
- `.planning/docs/presenter/NARRATIVE-TRADEOFFS.md` (DOC-02) — cost-vs-value of LLM narrative
- `.planning/docs/presenter/DEFERRED-ROADMAP.md` (DOC-03) — architecture-with-stubs, PROD-01 in-flight, PROD-02 next

**Not in `docs/` at repo root** because:
- `.planning/` is the GSD workflow state; presenter docs are milestone artefacts
- Repo root `docs/` collides with customer-visible docs if there ever are any
- Cross-links: top-level `README.md` adds "Presenter artefacts" section linking into `.planning/docs/presenter/`; `DEMO-RUNBOOK.md` links to each doc in its "Background reading" section

**Integration points:** None in code. Pure documentation. DOC-* tasks are last in the build order because they summarise design decisions from AGENT-01 / AGENT-02 / WF-01 / PROD-01 — writing them earlier means rewriting them.

---

## Recommended Project Structure

Existing 4-stack repo layout preserved. New files highlighted.

```
Customer-Tariff/
├── .planning/
│   ├── docs/                                # NEW v3.0
│   │   └── presenter/
│   │       ├── TRUST-ARCHITECTURE.md        # NEW (DOC-01)
│   │       ├── NARRATIVE-TRADEOFFS.md       # NEW (DOC-02)
│   │       └── DEFERRED-ROADMAP.md          # NEW (DOC-03)
│   └── milestones/
│       └── v3.0-*/                          # NEW — roadmap + research artefacts
├── agent/
│   ├── agent.py                             # MODIFY — action dispatch, discriminated union
│   ├── providers.py                         # NEW (PROD-01)
│   ├── tools.py                             # NEW — @tool definitions (extracted from agent.py)
│   ├── narrative/                           # existing + new fallbacks for CUST-004/5 + hardship
│   ├── Dockerfile                           # NO CHANGE
│   └── requirements.txt                     # MODIFY — add bedrock-agentcore (for memory)
├── api_lambda/
│   └── handler.py                           # MODIFY — follow_up() function; kind branch on 404
├── lambda/
│   ├── handler.py                           # MODIFY — action dispatcher + new pure helpers
│   ├── tariff_plans.json                    # MODIFY — TOU-PV plan
│   └── requirements.txt                     # NO CHANGE
├── infrastructure/
│   ├── agentcore_stack.py                   # MODIFY — wire AgentCore Memory
│   ├── backend_api_stack.py                 # NO CHANGE at stack level
│   ├── constructs/
│   │   ├── agent_memory.py                  # NEW (WF-01)
│   │   ├── agent_runtime.py                 # MODIFY — MEMORY_ID env var
│   │   └── backend_api.py                   # MODIFY — second route
│   └── seed_data/
│       ├── billing_records.py               # MODIFY — CUST-004, CUST-005, PROFILE items
│       └── tariff_plans.json                # MODIFY — TOU-PV plan (mirrors lambda/)
├── ui/src/
│   ├── components/
│   │   ├── HardshipBanner.tsx               # NEW (AGENT-02)
│   │   ├── ReasoningTrace.tsx               # NEW (AGENT-01 surface)
│   │   ├── FollowUpEmailDrawer.tsx          # NEW (WF-01)
│   │   └── RecommendationCard.tsx           # NO CHANGE
│   ├── lib/
│   │   ├── types.ts                         # MODIFY — discriminated union types
│   │   └── mock/*                           # MODIFY — new personas, new response shapes
│   └── personas.ts                          # MODIFY — CUST-004, CUST-005
└── tests/
    ├── test_providers.py                    # NEW (PROD-01)
    ├── test_bill_shock_flow.py              # NEW (AGENT-01)
    ├── test_hardship_short_circuit.py       # NEW (AGENT-02)
    ├── test_follow_up_email.py              # NEW (WF-01)
    ├── test_tou_savings.py                  # NEW (REC-04)
    └── test_narrative_eval_live.py          # MODIFY — extend to cover new personas
```

---

## Data Flow — NEW v3.0 Flows

### Flow A — Bill-Shock Multi-Tool (AGENT-01)

```
UI GET /recommendations/CUST-002
    │ (body request for the demo "bill-shock" persona)
    ▼
API Lambda: validate, fresh uuid4, invoke_agent_runtime(payload)
    │
    ▼
Agent invoke():
    │ action = "recommend" (default)
    │ System prompt primes: "Before recommending, check if this is a
    │   bill-shock scenario. Call detect_bill_shock; if true, also fetch
    │   hardship_flag before proceeding."
    │
    ├── Tool call: detect_bill_shock(CUST-002)
    │     → Tools Lambda {action: "detect_bill_shock"}
    │     → pure helper: compares Nov-Dec usage delta to 11-month avg
    │     → returns {is_shock: true, delta_dollars: 47.20, month: "2025-12"}
    │
    ├── Tool call: get_hardship_flag(CUST-002)
    │     → Tools Lambda {action: "get_hardship_flag"}
    │     → returns {hardship_flag: false}
    │
    ├── Tool call: simulate_savings(CUST-002)       (existing)
    │     → as today
    │
    │ Agent composes RecommendationResponse with:
    │   - kind: "recommendation"
    │   - green + cheapest tracks (REC-03 preserved)
    │   - call_script mentions bill-shock context ("Your December bill was $47
    │     higher than usual — here are two ways to reduce next month…")
    │   - _reasoning_trace: [{tool: "detect_bill_shock", summary: "+$47 Dec"},
    │                        {tool: "get_hardship_flag", summary: "no flag"},
    │                        {tool: "simulate_savings", summary: "green $X, cheapest $Y"}]
    │
    ▼
API Lambda: strip _narrative_source, PASS THROUGH _reasoning_trace, return 200
    │
    ▼
UI: RecommendationCard (existing) + ReasoningTrace (collapsed "3 steps" button)
```

### Flow B — Hardship Short-Circuit (AGENT-02)

```
UI GET /recommendations/CUST-005            (hardship persona)
    │
    ▼
API Lambda (unchanged path)
    │
    ▼
Agent invoke():
    │ action = "recommend" (default)
    │ System prompt: "FIRST call get_hardship_flag. If true, emit
    │   HardshipRoutingResponse and STOP."
    │
    ├── Tool call: get_hardship_flag(CUST-005)
    │     → returns {hardship_flag: true, reason: "customer self-declared"}
    │
    │ Agent emits HardshipRoutingResponse (NOT RecommendationResponse):
    │   - kind: "hardship"
    │   - customer_id: "CUST-005"
    │   - reason: "Customer flagged for hardship support"
    │   - routing_target: "hardship_team"
    │   - call_script: "Thanks for calling. Before we discuss plans, I want to
    │                   make sure we get you connected with our hardship team…"
    │     (D-15 narrative validators still apply)
    │
    ▼
API Lambda: strip _narrative_source, check kind:
    - if body.get("kind") == "hardship": return 200 with body
    - elif "green" not in body and "kind" not in body: return 404  (existing fallback detection)
    - else: return 200 with recommendation
    │
    ▼
UI: branches on data.kind
    - "recommendation" → RecommendationCard (existing)
    - "hardship"       → HardshipBanner (NEW)
```

### Flow C — Follow-Up Email (WF-01)

```
(Continuation of Flow A — same call, same rep, same persona)

UI GET /recommendations/CUST-002/follow-up
    │
    ▼
API Lambda follow_up():
    │ runtime_session_id = uuid4() (fresh per invocation — SC-3 preserved)
    │ memory_session_id  = f"CUST-002-{date.today().isoformat()}"  (deterministic)
    │
    ▼
bedrock-agentcore.invoke_agent_runtime(
    agentRuntimeArn, runtimeSessionId=runtime_session_id,
    payload={"action": "draft_follow_up", "customer_id": "CUST-002",
             "memory_session_id": memory_session_id}
)
    │
    ▼
Agent invoke():
    │ action = "draft_follow_up"
    │
    ├── MemorySessionManager.get_last_k_turns(memory_session_id, k=5)
    │     → returns prior RecommendationResponse from Flow A
    │
    │ Agent composes FollowUpEmailResponse:
    │   - kind: "follow_up_email"
    │   - subject: "Your personalised tariff recommendations from today's call"
    │   - body: "Hi there, following our conversation this afternoon…"
    │   - plan_reference: "EcoFlex100"
    │
    │ MemorySessionManager.add_turns(
    │   messages=[ConversationalMessage(follow_up_email_body, ASSISTANT)]
    │ )
    │   (append the follow-up turn so a future lookup can reason about it)
    │
    ▼
API Lambda: pass through FollowUpEmailResponse (no _narrative_source strip
             needed if the schema doesn't use it)
    │
    ▼
UI: FollowUpEmailDrawer renders; rep copies to clipboard
```

---

## Architectural Patterns

### Pattern 1: Action Dispatch on Existing Lambda (AGENT-01 enabler)

**What:** Single Lambda with an `action` field in the event; dispatcher routes to specific pure helpers.

**When to use:** When adding N related tools that share data access (DynamoDB read in this case). Avoids N Lambdas × N IAM policies × N freeze surfaces.

**Trade-offs:**
- Pro: One asset, one IAM policy, one cold-start surface, one log group
- Pro: Pure helpers stay co-located — shared helper code doesn't cross Lambda boundaries
- Con: All tools share Lambda memory/timeout/IAM — if one tool needs more, all get it
- Con: Single failure surface — a bug in one action can crash shared module init

```python
# lambda/handler.py
def handler(event, context):
    action = event.get("action", "simulate_savings")  # backwards-compat default
    if action == "simulate_savings":
        return simulate_savings(event, context)
    if action == "get_billing_history":
        return get_billing_history(event, context)
    if action == "detect_bill_shock":
        return detect_bill_shock(event, context)
    if action == "get_hardship_flag":
        return get_hardship_flag(event, context)
    if action == "get_customer_profile":
        return get_customer_profile(event, context)
    raise ValueError(f"Unknown action: {action!r}")
```

### Pattern 2: Discriminated Union Response Schema (AGENT-02 enabler)

**What:** Pydantic `Union[TypeA, TypeB]` with a literal `kind` discriminator; caller branches on `kind`.

**When to use:** When the server can return structurally different responses that are still semantically "success" (not errors).

**Trade-offs:**
- Pro: Each shape is coherent — no "both tracks present but please ignore them" optional-field ambiguity
- Pro: Customer-not-found detection stays a separate concern (404 error) from hardship (200 with alt shape)
- Con: Every consumer branches on `kind` — more code paths for the UI
- Con: Adding a new `kind` is a breaking change to consumers that don't handle it

### Pattern 3: Deterministic Memory Session ID (WF-01 enabler)

**What:** Derive a session key from stable inputs (customer_id + ISO-day); identical across correlated turns.

**When to use:** When you need to correlate multiple agent invocations into one conversation AND you cannot rely on the caller to carry session state.

**Trade-offs:**
- Pro: Stateless caller — no session cookies, no correlation IDs to thread through
- Pro: Scoping by day gives a natural reset boundary
- Con: Timezone fragility — `date.today()` uses process timezone; production use should pin UTC explicitly
- Con: Cross-day conversation impossible; for a call-centre demo this is fine; for customer-facing chat it's not

### Pattern 4: Protocol-Based Provider Abstraction (PROD-01 enabler)

**What:** Python `Protocol` defining a provider contract; demo impl wraps current data source; production swap is a constructor change.

**When to use:** When you want to show "production-shaped" code without building the production integration. Presenter-artefact story (DOC-03).

**Trade-offs:**
- Pro: `@runtime_checkable` enables `isinstance()` tests; structural typing means swapping implementations needs no inheritance
- Pro: In-memory impl makes offline tests trivial — no DynamoDB local, no moto
- Con: Too many providers = layered indirection; stay ruthless about keeping the surface small (3-4 methods max for this demo)

---

## Anti-Patterns to Avoid (v3.0-specific)

### AP-1: Per-tool Lambda for "clean IAM isolation"

**What people do:** Spin up a new Lambda per agent tool, each with its own DynamoDB grant.

**Why it's wrong:** Multiplies freeze surface (each Lambda has a CDK construct, a stack policy lift, an SSM parameter). Demo doesn't need the isolation because all tools are read-only against one table.

**Do this instead:** Option (c) — action dispatch on existing Tools Lambda. One Lambda, one policy, one freeze lift.

### AP-2: Letting the follow-up endpoint share the fresh-uuid4 runtime session rule

**What people do:** "SC-3 says always fresh uuid4, so the follow-up uses fresh uuid4 for Memory session_id too." Result: no memory retrievable; follow-up has no turn 1 context to reason about; feature silently broken.

**Why it's wrong:** Confuses runtimeSessionId (fresh — microVM routing) with Memory session_id (deterministic — conversation key). They are orthogonal AWS concepts.

**Do this instead:** Two separate IDs per follow-up invocation. `runtime_session_id = uuid4()` AND `memory_session_id = f"{customer_id}-{isoday}"`. Document this distinction in a code comment at the call site.

### AP-3: Shared `common/` package for provider abstraction

**What people do:** Put `CustomerDataProvider` in a shared `common/` directory imported by both agent container and Tools Lambda.

**Why it's wrong:** Breaks the bi-mode import pattern (container COPY is explicit; repo pytest uses namespace packages). Adds a build-time packaging concern that demo scope doesn't need.

**Do this instead:** Option (a) — `agent/providers.py`. Tools Lambda stays DynamoDB-direct. The abstraction is explicitly agent-side.

### AP-4: Mutating `tariff_plans.json` in only one location

**What people do:** Edit `lambda/tariff_plans.json` for a new plan; forget `infrastructure/seed_data/tariff_plans.json`. Seeder and tool disagree.

**Why it's wrong:** Demo seed data ≠ tool catalogue; simulate_savings fails on personas seeded from the other file.

**Do this instead:** PR hook or explicit pytest asserting byte-equivalence. Both files updated in the same commit. Already a known pitfall in v1.0; keep the discipline.

### AP-5: Hardship persona returned as 404

**What people do:** Don't update `api_lambda/handler.py:152` detection; hardship response has no `green`/`cheapest` so it falls through to the 404 branch.

**Why it's wrong:** UI shows "customer not found" for a hardship-flagged real customer. Wrong semantic; wrong UX.

**Do this instead:** Update detection to `if "green" not in body and body.get("kind") != "hardship": return 404`. Cover with a dedicated pytest.

### AP-6: Skipping the freeze-manifest regenerate for v3.0

**What people do:** Ship v3.0 without cutting a new `demo-v3.0` tag and a new freeze manifest; assume the v2.0 freeze covers v3.0.

**Why it's wrong:** v3.0 touches AgentCore runtime (new image), API Lambda (new route), FoundationStack (Memory resource, new SSM param), seed data (new personas). All three originally-frozen stacks gain new state. Without a new manifest, the rollback-to-known-good path is gone.

**Do this instead:** v3.0 ends with a new freeze ceremony: new tag, new manifest, fresh stack-policy lift-apply-reapply cycle, fresh DynamoDB backup. Treat the freeze as milestone-scoped, not project-scoped.

---

## Stack Policy Impact — Which Stacks Need Lifting

| Stack | Policy state | Lift required for v3.0? | Which requirements trigger the lift |
|-------|--------------|-------------------------|---------------------------------------|
| `CustomerTariff` (Foundation) | deny-Update:* + termination protection | **YES** | DATA-04 (seed data), AGENT-02 (hardship PROFILE items), AGENT-01 (Tools Lambda asset update for action dispatch) |
| `CustomerTariffAgent` (AgentCore) | deny-Update:* + termination protection | **YES** | AGENT-01 (container rebuild), WF-01 (new MEMORY_ID env var; new IAM grant), any `agent/requirements.txt` change |
| `CustomerTariffApi` (API Lambda) | deny-Update:* + termination protection | **YES** | WF-01 (new route), AGENT-02 (API Lambda code change for kind detection) |
| `CustomerTariffFrontend` (Amplify) | unfrozen | No lift needed | All UI changes |

**Operational consequence:** v3.0 is a major freeze lift. Pragmatically, the v3.0 build sequence ends with:

1. Lift policies on all three frozen stacks
2. Deploy changes (dependency order: Foundation → AgentCore → API)
3. Re-apply deny-Update:* policies
4. Re-enable termination protection (if CDK drops it during update)
5. Cut `demo-v3.0` tag
6. Write new freeze manifest
7. New DynamoDB backup

This is the same ceremony as v2.0 — not new territory, just re-executed. Budget time for it in the roadmap.

---

## Suggested Build Order

Dependencies determine sequence. Phase-numbering follows GSD convention (flat per-feature rather than nested sub-phases).

### Phase 1: DATA-04 — Seed new personas + tariff archetype

**Why first:** Everything else tests against personas. Without CUST-004/005 and TOU-PV, the agent and UI tests for AGENT-01/02/WF-01 can't run end-to-end.

**Deliverables:**
- Billing rows for CUST-004 (solar PV) and CUST-005 (EV) in `infrastructure/seed_data/billing_records.py`
- PROFILE items for all 5 personas in the same file (hardship_flag on CUST-005 only, to give AGENT-02 a demo path)
- TOU-PV plan in both `tariff_plans.json` files
- `simulate_savings_pure` extended for TOU
- Fixtures `mock_cust004_response`, `mock_cust005_response` with byte-exact savings
- Offline tests green

**Unblocks:** Everything else.

**Invariants at risk:** `tariff_plans.json` duplication drift (AP-4). SAV-03 correctness for TOU math (new pure helper).

### Phase 2: PROD-01 — CustomerDataProvider abstraction

**Why second:** Lands before new tools so those tools call through the provider from day 1. Refactoring after the fact would mean rewriting every tool.

**Deliverables:**
- `agent/providers.py` with Protocol + ToolsLambdaProvider + InMemoryProvider
- Existing `simulate_savings` @tool refactored to use provider (backwards compat: same behaviour, new indirection)
- `tests/test_providers.py` with Protocol contract tests
- Agent container rebuild; live smoke: existing `recommend` path still works byte-exact

**Unblocks:** AGENT-01, AGENT-02, WF-01 — all their new tools use the provider.

**Invariants at risk:** Bi-mode imports (the `providers.py` import pattern must have both container and repo branches).

### Phase 3: AGENT-01 — Bill-shock multi-tool flow

**Why third:** AGENT-02 depends on the `get_hardship_flag` tool, which is cleanest to land alongside `detect_bill_shock` (both are Tools Lambda actions; both are agent-side `@tool` wrappers via the provider).

**Deliverables:**
- `lambda/handler.py` action dispatcher + `detect_bill_shock_pure` + `get_hardship_flag_pure` + `get_customer_profile_pure`
- Agent @tool wrappers for each (via provider)
- System prompt updated for bill-shock flow (when to call which tools)
- `_reasoning_trace` collection in agent invoke()
- API Lambda passes through `_reasoning_trace`
- UI `ReasoningTrace` component (collapsed by default — UI-01 verified)
- Live smoke: CUST-002 invocation shows 3-tool trace; UI renders collapsed disclosure

**Unblocks:** AGENT-02 (hardship tool already landed).

**Invariants at risk:** UI-02 latency (3 tool calls add ~400-900ms to agent turn; re-measure with prewarm).

### Phase 4: AGENT-02 — Hardship short-circuit

**Why fourth:** Depends on `get_hardship_flag` (landed in Phase 3). Depends on the discriminated-union schema change in API Lambda, which has to happen after Phase 3's API Lambda changes stabilise (same file, avoid rebase churn).

**Deliverables:**
- `HardshipRoutingResponse` Pydantic schema + discriminated union
- `kind` field on `RecommendationResponse` (backwards-compat optional with default)
- Agent system prompt updated: hardship branch
- `_narrative_fallback_salvage` extended for hardship shape
- `api_lambda/handler.py:152` customer-not-found detection updated
- UI `HardshipBanner` + types.ts discriminated union
- Live smoke: CUST-005 returns 200 with hardship banner (not 404 regression)

**Unblocks:** WF-01.

**Invariants at risk:** Customer-not-found detection regression (test coverage mandatory). Backwards-compat of existing UI against new `kind` field.

### Phase 5: WF-01 — Follow-up email via AgentCore Memory

**Why fifth:** Depends on the agent producing memorable turns (Phase 3/4 recommendations are the turn 1 input). AgentCore Memory is a new AWS resource and a new API route — largest freeze-lift of the milestone; do it after the smaller changes are green.

**Deliverables:**
- `infrastructure/constructs/agent_memory.py` + agentcore_stack wiring
- `MEMORY_ID` env var on agent runtime
- `agent/requirements.txt` includes `bedrock-agentcore` (memory) — lockfile regenerated under `--require-hashes`
- Agent `draft_follow_up` action + MemorySessionManager integration
- Agent writes turn 1 to memory on every `recommend` invocation (side-effect; no change to response shape)
- API Lambda new route `follow_up()` with deterministic Memory session_id derivation
- UI `FollowUpEmailDrawer`
- Live smoke: end-to-end two-turn flow; presenter "Draft follow-up email" clicks after recommendation

**Unblocks:** DOC-* (presenter docs need final architecture to describe).

**Invariants at risk:** SC-3 conceptual expansion (runtime vs memory session clarity — document at call site). `--require-hashes` reproducibility with new dependency.

### Phase 6: DOC-01 / DOC-02 / DOC-03 — Presenter artefacts

**Why last:** Writing them earlier means rewriting them. Architecture decisions crystallise in Phase 1-5; DOC-* summarises.

**Deliverables:**
- `.planning/docs/presenter/TRUST-ARCHITECTURE.md`
- `.planning/docs/presenter/NARRATIVE-TRADEOFFS.md`
- `.planning/docs/presenter/DEFERRED-ROADMAP.md`
- README + DEMO-RUNBOOK cross-links

**Unblocks:** `demo-v3.0` freeze.

### Phase 7: v3.0 Freeze Ceremony

**Deliverables:**
- Re-apply stack policies (lifted during Phase 3-5)
- Re-enable termination protection
- New DynamoDB backup
- Cut `demo-v3.0` tag
- Write `.planning/milestones/v3.0-phases/FREEZE-MANIFEST.md`
- T-24h rehearsal with new personas

### Dependency Graph

```
Phase 1 (DATA-04) ──┐
                    ├─▶ Phase 2 (PROD-01) ──▶ Phase 3 (AGENT-01) ──▶ Phase 4 (AGENT-02) ──▶ Phase 5 (WF-01) ──▶ Phase 6 (DOC-*) ──▶ Phase 7 (Freeze)
                    │                                                                            ▲
                    └─────────────────────────────────────────────────────────────────────────────┘
                    (DATA-04 also directly unblocks WF-01 via CUST-002 bill-shock memory turn)
```

---

## Scaling Considerations

This is a demo stack — scaling is not a requirement. The integration decisions above are optimised for **freeze-surface minimisation** and **invariant preservation**, not for production-scale concerns.

That said, three notes for DOC-03 (deferred roadmap):

| Scale dimension | v3.0 posture | Production evolution |
|-----------------|---------------|-----------------------|
| Tool-call fan-out | Sequential (Strands default) | Parallel via Strands `ainvoke` once all tools are idempotent reads |
| Memory volume | Ephemeral short-term only | Long-term Memory with SEMANTIC strategy; retention policy; per-customer namespace |
| Provider backend | DynamoDB demo | Real CRM (Salesforce, Dynamics) via the same Protocol — that's the PROD-01 story |

---

## Integration Points Summary

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Bedrock Sonnet 4.6 | `BedrockModel(model_id="us.anthropic.claude-sonnet-4-6")` | Unchanged; multi-tool flow stresses it more — monitor tool-use regression per Phase 06.1 fix |
| AgentCore Runtime | `bedrock-agentcore.invoke_agent_runtime` | Unchanged; new `action` dispatch in payload |
| AgentCore Memory | `MemorySessionManager` (SDK) via `bedrock-agentcore` boto3 | NEW — control-plane via `bedrock-agentcore-control` (create memory); data-plane via `bedrock-agentcore` (add_turns, get_last_k_turns) |
| DynamoDB | boto3 resource in Tools Lambda | Unchanged; new sort-key prefix `PROFILE` for hardship |

### Internal Boundaries

| Boundary | Communication | v3.0 change |
|----------|---------------|--------------|
| API Lambda ↔ AgentCore runtime | `invoke_agent_runtime` sync | Extended payload (`action` field) |
| AgentCore container ↔ Tools Lambda | `lambda:Invoke` sync | Extended payload (`action` field); all IAM unchanged |
| Agent @tool ↔ CustomerDataProvider | In-process Python call | NEW abstraction layer |
| AgentCore container ↔ AgentCore Memory | `MemorySessionManager` | NEW |
| UI ↔ API Gateway | HTTPS GET | Second route `/follow-up` — additive |

---

## Confidence & Open Questions

| Area | Confidence | Notes |
|------|------------|-------|
| Action-dispatch pattern on Tools Lambda (§1) | HIGH | Standard pattern; preserves SAV-03 byte-exact |
| Discriminated union for hardship (§2) | HIGH | Pydantic native feature; clean with customer-not-found detection fix |
| Memory vs runtime session distinction (§3) | HIGH | Confirmed via AgentCore Memory docs — two different concepts, different API surfaces |
| Protocol-based provider location (§4) | HIGH | Preserves bi-mode imports exactly |
| DATA-04 tariff schema extension (§5) | MEDIUM-HIGH | TOU math is offline-testable but is new — byte-exact fixtures required |
| DOC-* location (§6) | MEDIUM | Judgement call; `.planning/docs/presenter/` feels right but isn't load-bearing |
| `_reasoning_trace` UI pattern | MEDIUM | Collapsed-by-default preserves UI-01 in principle; needs visual verification at 1280×800 |
| AgentCore Memory dependency reproducibility | MEDIUM | `bedrock-agentcore` must pin cleanly under `--require-hashes`; regenerate lockfile + re-verify |
| `demo-v3.0` freeze ceremony scope | HIGH | Same shape as v2.0; already a known procedure |

### Open questions for roadmap

1. **Bill-shock detection threshold.** `detect_bill_shock_pure` needs a numeric definition of "bill shock" — e.g. `|monthly_delta| > 30% of 11-month mean`. Define in Phase 3 design spec; pin in pytest.
2. **Hardship-flag source of truth.** Does the PROFILE item live in the existing `tariff-billing` table (same PK, new SK prefix — recommended for freeze-surface minimisation) or a new table? Recommendation: same table. Confirm in Phase 1.
3. **`_reasoning_trace` in public API contract or internal-only?** `_narrative_source` is stripped (internal); `_reasoning_trace` is the whole point of AGENT-01 so it must be public. Confirm naming: drop the underscore (`reasoning_trace` as a public field)? Recommend yes — leading underscore implies internal; drop it.
4. **Follow-up email retention.** Does AgentCore Memory need a TTL (e.g. 24 hours) to prevent stale context? Default long-term Memory stores indefinitely. For demo, short-term (last-k turns) is sufficient; long-term not needed.
5. **Backwards-compat of existing UI against v3.0 API.** The frozen `demo-v2.0` UI is still served from Amplify. If v3.0 API adds `kind` field, does it break v2.0 UI? Answer: no — TS structural typing ignores extra fields. But the v2.0 UI has no `HardshipBanner`, so CUST-005 would render incorrectly. Recommendation: v3.0 UI must be rebuilt and deployed to Amplify BEFORE v3.0 API is swapped in. Amplify is unfrozen; this is low risk.

---

## Sources

- Existing codebase — `agent/agent.py`, `lambda/handler.py`, `api_lambda/handler.py`, `infrastructure/constructs/agent_runtime.py`, `infrastructure/constructs/backend_api.py`, `infrastructure/foundation_stack.py`, `infrastructure/agentcore_stack.py`, `infrastructure/backend_api_stack.py` — **authoritative for current 4-stack shape** (HIGH)
- `CLAUDE.md` — critical invariants (SAV-03, REC-03, D-04, D-15, SC-3, `_narrative_source` strip, `Config(read_timeout=25)`, customer-not-found detection, bi-mode imports, region pin) (HIGH)
- `.planning/milestones/v2.0-research/ARCHITECTURE.md` — v2.0 architecture baseline inherited (HIGH)
- `.planning/PROJECT.md` — v3.0 target features: AGENT-01, AGENT-02, WF-01, DATA-04, REC-04, PROD-01, DOC-01/02/03 (HIGH)
- AWS AgentCore Memory developer guide — MemorySessionManager API, session scoping, boto3 client names (`bedrock-agentcore-control`, `bedrock-agentcore`), `add_turns`, `get_last_k_turns` semantics (HIGH — confirmed via docs fetch 2026-04-28)
- AWS Bedrock AgentCore developer guide — runtime session model (v2.0 research artefact; inherited) (HIGH)
- Strands SDK v1.37.0+ `agent_result.message.content[].toolUse` inspection pattern — already used in `agent/agent.py::_extract_lenient_from_agent_result` (HIGH — evidenced in working v2.0 code)
- Pydantic v2 discriminated union — standard feature via `Annotated[Union[...], Field(discriminator=...)]` (HIGH — official Pydantic docs)

---
*Architecture research for: v3.0 Agentic Depth & Workflow Assist milestone*
*Researched: 2026-04-28*
