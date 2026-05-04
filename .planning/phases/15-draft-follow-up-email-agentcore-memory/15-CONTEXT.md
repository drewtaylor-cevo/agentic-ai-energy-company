# Phase 15 Context — Draft Follow-Up Email via AgentCore Memory (WF-01)

## Goal

Rep can click "Draft follow-up email" after a recommendation and receive an editable draft that references the prior turn's recommendation for the same customer, with zero cross-customer bleed and no breakage of the SC-3 runtimeSessionId invariant.

## Requirements

- **WF-01:** Draft follow-up email workflow — rep-side action that triggers a second agent turn, using AgentCore Memory to recall the prior turn's recommendations, and returns a draft email body the rep can edit and send
- **WF-01a:** AgentCore Memory scoped to short-term only — `actorId = f"customer:{customer_id}"`, deterministic `session_id = f"{customer_id}-{UTC-ISO-day}"`, TTL 8–12h (no long-term cross-session retention)
- **WF-01b:** Memory session isolation — cross-customer PII leakage canary test passes (lookup customer A then customer B; customer B turn must not contain any customer A data)
- **WF-01c:** Deterministic-session invariant preserved — `runtimeSessionId` still generated INSIDE `handler()` (SC-3); the new Memory `session_id` is a separate key and does not conflate with `runtimeSessionId`

## Dependencies

- Phase 13 (complete): Multi-tool reasoning, reasoning trace, 4-tool cap hook
- Phase 13.1 (complete): SHORT-CIRCUIT RULE, UNKNOWN sentinel, latency gates
- Phase 14 (complete): Hardship short-circuit, discriminated union `kind: "recommendation" | "hardship"`, HardshipResponse model, API Lambda surgical update

## Key Design Decisions

### D-15-01: Memory resource provisioning (LD-3)
AgentCore Memory provisioned via CDK L2 `agentcore.Memory` construct in `AgentCoreStack` (extends existing stack — avoids new stack). Short-term only: `memory_strategies=[]` (no long-term strategies). `expiration_duration=Duration.hours(12)` for TTL. Memory ID written to SSM parameter `/customer-tariff/memory-id` for cross-stack wiring. Agent runtime gets `MEMORY_ID` env var.

### D-15-02: Memory session model (LD-3, WF-01a)
- `actorId = f"customer:{customer_id}"` — structural isolation per customer (C4 prevention)
- `session_id = f"{customer_id}-{datetime.now(timezone.utc).date().isoformat()}"` — deterministic, same-day scoped
- `runtimeSessionId = str(uuid.uuid4())` — UNCHANGED, fresh per invocation (SC-3 preserved)
- These are orthogonal concepts: `runtimeSessionId` is the AgentCore runtime session; `session_id` is the Memory session. Documented at call site per AP-2 prevention.

### D-15-03: Agent-side Memory integration
Use `bedrock_agentcore.memory.integrations.strands.session_manager.AgentCoreMemorySessionManager` with `AgentCoreMemoryConfig`. Wire into `Agent(session_manager=...)`. The session manager handles automatic event creation and retrieval.

For the follow-up turn, the agent receives a different system prompt (`_FOLLOW_UP_SYSTEM_PROMPT`) that instructs it to draft an email referencing the prior recommendation context retrieved from Memory.

### D-15-04: Follow-up response schema
```python
class FollowUpEmailResponse(BaseModel):
    kind: Literal["follow_up"]
    customer_id: str
    subject: str  # deterministic, code-composed (not LLM)
    body: str  # LLM-generated, D-15 extended validator (longer form)
    plan_reference: str  # plan_name from prior recommendation
    _workflow_source: str  # internal marker, stripped by API Lambda
```

### D-15-05: API route
New route: `GET /recommendations/{customer_id}/follow-up` on the same API Gateway HTTP API v2. Same Lambda handler, routed by path. The handler detects the `/follow-up` suffix from the path and dispatches to a `follow_up()` function.

### D-15-06: API Lambda routing
```python
# In handler():
raw_path = event.get("rawPath", "")
if raw_path.endswith("/follow-up"):
    return follow_up(customer_id, event, context)
# ... existing recommendation path
```

### D-15-07: `_workflow_source` marker
Follows the `_narrative_source` pattern: agent attaches it, API Lambda strips it before returning to client. Internal observability marker.

### D-15-08: `?narrative=off` kill switch (LD-7)
Collapses the follow-up email drawer to v2.0 shape (not rendered). Single flag, single rehearsal contract.

### D-15-09: Fallback path (D-04)
If Memory is unavailable or the follow-up agent turn fails, return a deterministic fallback email template from `agent/narrative/fallbacks.py` (keyed by customer_id). Never 500.

### D-15-10: Dependency bump
`bedrock-agentcore==1.6.3 → ==1.6.4` in `requirements.in`. Lockfile regenerated via `pip-compile --generate-hashes`. Fresh-venv `pip install --require-hashes -r requirements.txt` + full pytest suite must both pass. FREEZE-MANIFEST lockfile-hash placeholder documented for Phase 17.

### D-15-11: Container layout
New `memory/` directory under `agent/` with `__init__.py` and `config.py`. Dockerfile COPYs `memory/` to `/app/memory/`. Bi-mode imports: `try: from memory.config import ... except: from agent.memory.config import ...`.

## Invariants to preserve

- **SAV-03:** No arithmetic in follow-up path (email body is narrative only, no savings recalculation)
- **REC-03:** Not applicable to follow-up (no tracks returned)
- **D-04:** Never 500 — Memory failures caught and fallback template returned
- **D-15:** Extended validator for email body (longer form acceptable — up to 100 words, but same banned-terms gauntlet: no digits, no currency, no switch verbs, no competitor names, no environmental superlatives)
- **SC-3:** `runtimeSessionId` fresh uuid4 per invocation — Memory `session_id` is separate
- **`_workflow_source` marker:** Stripped by API Lambda (parallel to `_narrative_source`)
- **`?narrative=off`:** Collapses follow-up drawer
- **Bi-mode imports:** New `memory/` module follows container-first pattern
- **Frozen lockfile:** One permitted dep bump (`bedrock-agentcore` 1.6.3 → 1.6.4)

## Existing code touchpoints

| File | What changes |
|------|-------------|
| `requirements.in` | `bedrock-agentcore==1.6.3` → `==1.6.4` |
| `requirements.txt` | Regenerated with new hashes |
| `agent/requirements.txt` | Updated for container build |
| `agent/Dockerfile` | Add `COPY memory/ ./memory/` |
| `agent/agent.py` | Add `FollowUpEmailResponse` model, `draft_follow_up()` function, Memory session manager wiring, follow-up system prompt, follow-up fallback path |
| `agent/memory/__init__.py` | New module |
| `agent/memory/config.py` | `build_memory_config()` + `build_session_manager()` helpers |
| `agent/narrative/fallbacks.py` | Add follow-up email fallback templates per persona |
| `api_lambda/handler.py` | Add `follow_up()` function, route detection for `/follow-up`, `_workflow_source` stripping |
| `infrastructure/agentcore_stack.py` | Add Memory construct, SSM parameter, MEMORY_ID env var on runtime, IAM for Memory |
| `infrastructure/constructs/agent_runtime.py` | Accept `memory_id` kwarg, add to env vars |
| `infrastructure/constructs/backend_api.py` | Add `/recommendations/{customer_id}/follow-up` route |
| `tests/conftest.py` | Add follow-up response fixtures |
| `tests/test_follow_up.py` | New: offline follow-up tests |
| `tests/test_backend_api_handler.py` | Add follow-up route handler tests |
| `ui/src/lib/types.ts` | Add `FollowUpEmailResponse` type |
| `ui/src/components/FollowUpDrawer.tsx` | New component |
| `ui/src/App.tsx` | Wire follow-up button + drawer |
| `ui/src/hooks/useFollowUp.ts` | New hook for follow-up API call |
| `ui/src/lib/mock/recommendations.ts` | Add follow-up mock responses |

## Risk register

| Risk | Severity | Mitigation |
|------|----------|------------|
| C4: Cross-customer Memory bleed | CRITICAL | `actorId=customer:{id}` structural isolation + live cross-customer smoke test as mandatory close gate |
| Memory service unavailable | HIGH | D-04 fallback template — never 500 |
| CDK L2 alpha Memory construct breaks | MEDIUM | Fallback to L1 `CfnMemory` or boto3 `CustomResource` |
| `bedrock-agentcore` 1.6.4 breaks existing invoke() | MEDIUM | Full pytest suite as dep-bump gate; rollback to 1.6.3 if any regression |
| Memory TTL too short for demo rehearsal | LOW | 12h TTL + `scripts/memory-reset.sh` at T-24h/T-2h |
| Follow-up latency exceeds UI-02 budget | MEDIUM | Memory retrieval adds ~200-400ms; per-flow prewarm gate extended |
