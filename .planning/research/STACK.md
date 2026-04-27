# Technology Stack — v3.0 Agentic Depth & Workflow Assist

**Project:** Customer Tariff & Billing Optimisation Agent
**Milestone:** v3.0 — AGENT-01 (bill-shock multi-tool flow), AGENT-02 (hardship short-circuit), WF-01 (draft-email workflow with AgentCore Memory), DATA-04 / REC-04 (solar PV + EV personas + new tariff archetype), PROD-01 (`CustomerDataProvider` abstraction), DOC-01/02/03 (presenter artefacts)
**Researched:** 2026-04-28
**Confidence:** MEDIUM-HIGH overall. HIGH on carry-forward surface (unchanged from v2.0). HIGH on the AgentCore Memory integration path via `bedrock-agentcore==1.6.3+`'s own `bedrock_agentcore.memory.integrations.strands` adapter — verified in current Strands docs. HIGH on Strands 1.37's `ConcurrentToolExecutor` being the default and `stream_async` event shapes for reasoning-trace UX. MEDIUM on CDK L2 `Memory` construct ergonomics in `aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0` (the alpha line is unstable; fallback is L1 `CfnMemory` or imperative boto3 inside a `CustomResource`). LOW on specific CfnMemory property names — verify at Phase 1.

> **Deltas-only document.** The v1.0 and v2.0 stacks are still correct and carried forward verbatim — see [`../milestones/v2.0-research/STACK.md`](../milestones/v2.0-research/STACK.md) and transitively [`../milestones/v1.0-research/STACK.md`](../milestones/v1.0-research/STACK.md). This file lists **only the additions, pins, and patterns needed for v3.0**. Where a v3.0 feature reuses an existing library unchanged, that is noted but not re-researched.

---

## What's Carried Forward Unchanged from v2.0 (Frozen `demo-v2.0`)

These are the v2.0 pins already in `requirements.in` (and hash-locked in `requirements.txt`). **Do not bump majors** — the freeze contract is that `--require-hashes` installs produce byte-identical artefacts. New top-level deps require a coordinated `pip-compile` + fresh hashes + re-validation of the test suite.

| Component | Current Pin (`requirements.in`) | v3.0 Usage |
|-----------|-------------------------------|------------|
| `aws-cdk-lib` | `==2.251.0` | Unchanged. Carries the L2 `Memory` construct via the alpha module below. |
| `aws-cdk.aws-bedrock-agentcore-alpha` | `==2.250.0a0` | Now also used for the `Memory` L2 construct (WF-01). Same pin; no bump. |
| `aws-cdk-aws-amplify-alpha` | `==2.250.0a0` | Unchanged — hosts `ui/dist/` for the Frontend stack. |
| `constructs` | `==10.6.0` | Unchanged. |
| `boto3` | `==1.42.96` | Unchanged for the live runtime path. `bedrock-agentcore` / `bedrock-agentcore-control` service models are present in 1.42.x (verified against the v2.0 pre-warm script already calling `invoke_agent_runtime`). |
| `strands-agents` | `==1.37.0` | Unchanged. Provides `ConcurrentToolExecutor` (default), `stream_async` event iterator, and **accepts an external `session_manager=` kwarg** on `Agent(...)` that the `bedrock-agentcore` SDK plugs into. Verified in the Strands community-session-managers docs at research time. |
| `bedrock-agentcore` | `==1.6.3` | **Bumped in v3.0** — see below. Latest on PyPI is `1.6.4` (released 2026-04-23). The memory integration subpackage `bedrock_agentcore.memory.integrations.strands` is the load-bearing import. |
| `pydantic` | Transitive via `strands-agents` | Unchanged. Still the right place for `CustomerDataProvider`'s data contract (see PROD-01 below). |
| `pip-tools` | Dev-only, already installed | Used again to regenerate `requirements.txt` hashes for the single bumped dep below. No freeze-ceremony-scale re-lock needed; this is a targeted bump inside the v3.0 development cycle, not a demo-freeze. |
| `aws-cdk-lib==2.251.0` Lambda + DynamoDB + API Gateway HTTP v2 | Unchanged | Tools Lambda grows 2–3 new sibling tool functions (AGENT-01); DynamoDB grows 2 new persona partitions + 1 new tariff archetype (DATA-04 / REC-04) — **table schema unchanged**, only new items. |
| React 18 + Vite + shadcn/ui New York/Slate + Tailwind | Unchanged (per `ui/package.json`) | Gains a collapsible "Thinking…" reasoning-trace strip (AGENT-01), a hardship-refusal card (AGENT-02), and a "Draft follow-up email" panel (WF-01). All composable from existing shadcn primitives — `Card`, `Collapsible`, `Button`, `Textarea`, `Skeleton`. No new shadcn components. |
| `?narrative=off` URL-level kill switch | Unchanged | **Must be extended** to also collapse AGENT-01 reasoning strip, AGENT-02 hardship card, and WF-01 email panel to v2.0 shape. This is a UI-side change, not a dep change — no new libraries. |

**Everything else in `v2.0-research/STACK.md` applies. Do not re-install, do not bump majors outside this document.**

---

## Recommended Stack — v3.0 Additions

### Core Technologies (NEW or BUMPED)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `bedrock-agentcore` | **bump `==1.6.3` → `==1.6.4`** | Brings the `bedrock_agentcore.memory.integrations.strands.session_manager.AgentCoreMemorySessionManager` + `AgentCoreMemoryConfig` classes that wire an existing AgentCore Memory resource into a Strands `Agent(session_manager=...)` in ~3 lines. Also exposes `bedrock_agentcore.memory` data-plane helpers (`MemorySessionManager`, `add_turns`, `search_long_term_memories`) for programmatic access outside the Strands loop. | **This is the single load-bearing v3.0 dep.** WF-01 requires "a second-turn continuation against AgentCore Memory" — rolling that manually against the raw `bedrock-agentcore` / `bedrock-agentcore-control` boto3 clients is 200+ lines of ceremony (CreateEvent / GetEvent / namespace handling). The `integrations.strands` adapter is the supported path as of the April 2026 release. Version pin is exact because `--require-hashes` refuses floating ranges. Verified: `1.6.4` is on PyPI (latest at research time), release date 2026-04-23. |
| AWS Bedrock AgentCore **Memory resource** | Service — GA | Persists session events (WF-01 second-turn continuation) and, optionally, longer-lived workflow context via built-in strategies (SEMANTIC / SUMMARIZATION / USER_PREFERENCE). Two-plane API: `bedrock-agentcore-control` (CreateMemory, UpdateMemory — control plane) + `bedrock-agentcore` (CreateEvent, ListEvents, RetrieveMemoryRecords — data plane). | AWS-native, same region as the existing runtime (`us-east-1`), same IAM trust boundary. The alternative — putting DynamoDB behind the agent for conversation state — reimplements a managed service badly and doesn't demo the point of v3.0 ("exercise AgentCore Memory as a production-shaped primitive"). For WF-01 we need **short-term (session-scoped) memory only** — the two turns are "give me recommendations" then "draft the follow-up email" in the same session. Long-term strategies are out of scope for v3.0; keep the `memoryStrategies` empty on the CreateMemory call and use raw event storage. |
| `aws-cdk.aws-bedrock-agentcore-alpha.Memory` L2 construct | Already pinned at `==2.250.0a0` | CDK-native Memory resource provisioning. L2 exists: `Memory`, `MemoryBase`, `MemoryProps`, `MemoryAttributes`. Backed by `ManagedMemoryStrategy` + `SelfManagedMemoryStrategy` helpers. | Matches the v1.0/v2.0 "provision everything from `cdk synth`" pattern. **Fallback if L2 ergonomics bite** (alpha is unstable): drop to the L1 `CfnMemory` construct from `aws-cdk-lib.aws_bedrockagentcore`, or (last resort) call `boto3.client('bedrock-agentcore-control').create_memory(...)` from a `CustomResource` Lambda. All three work. L2 is the cleanest, L1 is a known fallback, boto3-in-CustomResource is the break-glass. |
| Lambda Provisioned Concurrency on Tools Lambda | Already on `api_lambda` via `live` alias (v2.0) | **NEW: add the same `live`-alias + conditional PC pattern to the Tools Lambda** for the multi-tool AGENT-01 flow | AGENT-01's multi-tool turn does 2–3 Tools-Lambda invocations per agent turn. If the Tools Lambda is cold, the first call eats a ~500ms cold start; the subsequent calls reuse the warm container. Warming only the API Lambda leaves the Tools Lambda cold on every fresh session. PC=1 during the demo window, gated by the existing `-c demo_pc=1` context flag. Cost: negligible. |

### Supporting Libraries (NEW — zero new third-party Python deps)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `abc.ABC` + `typing.Protocol` (stdlib) | Python 3.13 stdlib | `CustomerDataProvider` abstraction for PROD-01 | **Use `typing.Protocol`, not `ABC`.** The `Protocol` form gives a structural-typing contract that production implementations can satisfy without inheriting — critical for the "real-CRM swap" story which will import a vendor SDK class that we don't own. A concrete `DynamoDBCustomerDataProvider` in `lambda/providers/dynamodb.py` implements it; a future `SalesforceCustomerDataProvider` in a v3+ milestone implements it structurally. Zero new dep; zero freeze impact. |
| `pydantic.BaseModel` (already transitively pinned) | v2.x (via `strands-agents==1.37.0`) | Data contract on the return shape of `CustomerDataProvider.get_billing_history(customer_id)` and `get_customer_profile(customer_id)` | Re-uses the Pydantic version the agent already relies on. The provider returns `BillingMonth` and `CustomerProfile` models — the Tools Lambda unpacks them the same way it unpacks the current raw-dict DynamoDB item. No schema-drift risk: one contract, two call sites (DynamoDB adapter + real-CRM stub). **Do NOT introduce a new DTO library** (attrs, dataclasses-json, marshmallow) — Pydantic is already load-bearing at the narrative gauntlet and is the natural home for this. |
| `strands.tools.executors.ConcurrentToolExecutor` | Shipped in `strands-agents==1.37.0` | Concurrent tool execution for AGENT-01's multi-tool turn | **Already the default** in Strands 1.37. No config change required. Claude Sonnet 4.6 supports parallel tool use natively and the Strands default executor processes multiple `toolUse` blocks in one response concurrently. Important caveat: if AGENT-01 needs strict sequential tool ordering for the "Thinking…" UX to read naturally (step 1 → step 2 → step 3), swap to `SequentialToolExecutor` for that agent instance only. **Decision for v3.0: start with the default `ConcurrentToolExecutor`**; if the UI reasoning-strip looks incoherent because the tool names arrive out of narrative order, flip to sequential. Document the choice in AGENT-01's roadmap phase. |
| `strands.Agent.stream_async(...)` | Shipped in 1.37.0 | Reasoning-trace event stream for the AGENT-01 "Thinking…" UI strip | Emits `tool_use_stream` events with `{toolUseId, name, input}`; the API Lambda can map `name` → a narrative-altitude label ("Pulling billing history", "Checking rate history") and stream those to the UI via SSE or buffer them and return inline with the final response. **Decision for v3.0**: buffer-and-return inside the existing HTTP-API-v2 response shape, not SSE. Rationale: v2.0 API Lambda deliberately returns a single JSON body and the `Config(read_timeout=25, connect_timeout=5)` invariant is tuned for that. Introducing streaming would require API Gateway v2 WebSocket or Lambda response streaming, both of which are meaningful stack additions. Buffer-and-return preserves the invariant. The UI then replays the buffered trace with short CSS animation delays so it *looks* live — a deliberate demo affordance, flagged explicitly in DOC-01. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `pytest` (existing) | Offline tests grow by ~30–50 cases | New cases: provider Protocol conformance, AGENT-01 multi-tool fallback, AGENT-02 hardship refusal, WF-01 memory round-trip (mocked). Stays within the `-m "not smoke"` default; **WF-01 live round-trip is smoke-only** because it requires a real AgentCore Memory resource. |
| `vitest` (existing) | UI tests for new components | Reasoning-strip collapse/expand, hardship-card render, email draft panel. No new testing library. |
| `pip-tools` (already dev-pinned) | Regenerate `requirements.txt` for the `bedrock-agentcore` bump | One round of `pip-compile --generate-hashes requirements.in` to pick up `1.6.3 → 1.6.4`. |
| AWS CLI (existing) | Verifying `CreateMemory` / `ListMemories` outside CDK during Phase 1 debugging | `aws bedrock-agentcore-control list-memories --region us-east-1` is the sanity-check if CDK synth hangs or the L2 construct misbehaves. |

## Installation

```bash
# Bump ONE pinned top-level dep — everything else is carried forward.
# Edit requirements.in:
#   bedrock-agentcore==1.6.3   →   bedrock-agentcore==1.6.4
# Then regenerate hashes (pip-tools already in dev deps):
pip-compile --generate-hashes --output-file requirements.txt requirements.in

# Reinstall against the frozen lockfile:
pip install --require-hashes -r requirements.txt
pip install --require-hashes -r requirements-dev.txt

# Verify the Strands integration subpackage is importable:
python -c "from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager; print('ok')"
python -c "from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig; print('ok')"

# No UI deps added. No new dev tools. No new top-level Python packages beyond the version bump.
```

**Lockfile impact note (freeze contract):** Bumping `bedrock-agentcore` changes the SHA256 hash for that one wheel. All other wheels in `requirements.txt` keep their existing hashes because `pip-compile` is deterministic. The freeze-ceremony reproducibility gate (`pip install --require-hashes` from a fresh `.venv`) must pass cleanly before v3.0's own freeze tag is cut. The `demo-v2.0` tag and its stack policies are unaffected — v3.0 will get its own freeze ceremony at milestone end with its own `demo-v3.0` tag.

---

## Integration Points with Existing Stack

| v3.0 Change | Existing File (v1.0 / v2.0) | What Changes | Why It Plays Nicely |
|-------------|------------------------------|--------------|---------------------|
| Add `AgentCoreMemorySessionManager` to the Strands `Agent(...)` instance | `agent/agent.py` | Optional `session_manager=` kwarg, gated by a new `ENABLE_MEMORY` env var from CDK. When absent → behaves exactly as v2.0 (no memory, no state). When present → second-turn calls reuse the session. | **Preserves the `_narrative_source` marker contract.** The session manager is a side-channel to Memory; it doesn't mutate the `RecommendationResponse` Pydantic model. The marker still gets attached by the agent and stripped by the API Lambda (`body.pop("_narrative_source", None)`). WF-01's email draft attaches a **parallel** `_workflow_source` marker (`"model"` or `"fallback"`) the same way. |
| Add 2–3 sibling tools to the Tools Lambda (AGENT-01) | `lambda/handler.py` | New Python functions: `fetch_billing_history_pure`, `fetch_rate_history_pure`, `explain_anomaly_pure` (names TBD by roadmapper). Each is a pure function over persona fixtures + DynamoDB. | **Preserves SAV-03 — LLM never does arithmetic.** Each new tool returns structured numbers from data; the LLM copies them byte-for-byte in the narrative. Same invariant, expanded surface area. |
| Add `CustomerDataProvider` Protocol + `DynamoDBCustomerDataProvider` impl | new `lambda/providers/__init__.py`, `lambda/providers/dynamodb.py` | Move DynamoDB-specific reads out of `lambda/handler.py` into the adapter. `handler.py` imports the Protocol and calls `provider.get_billing_history(customer_id)`. | **Preserves the tariff-catalog-duplication invariant** (`lambda/tariff_plans.json` stays source-of-truth for tests). Only data reads move — tariff catalog stays bundled. The adapter returns `list[BillingMonth]` (Pydantic models), not raw DynamoDB items, so the `handler.py` math is unchanged. |
| Add Memory L2 construct to `agentcore_stack.py` | `infrastructure/agentcore_stack.py` | One `aws_bedrock_agentcore_alpha.Memory(...)` declaration + IAM grant to the AgentCore runtime's execution role + SSM parameter for the memory ID | **Cross-stack wiring stays on SSM parameters** (per the existing CLAUDE.md invariant). The memory ID is written to `/customer-tariff/memory/id`; the agent runtime reads it at container start via env var injected by CDK. Stack remains independently redeployable. |
| Hardship short-circuit for AGENT-02 | `agent/agent.py` or `lambda/handler.py` | Either: (a) a new `check_hardship_flag` tool the agent always calls first, which short-circuits with a refusal payload when `hardship_flag=True`; OR (b) a pre-agent-call guard inside `agent/agent.py::invoke()` that inspects the customer record and bypasses the agent entirely when hardship is set. **Recommended: (b)**. | **Pattern (b) keeps the demo deterministic.** The agent doesn't have to be trusted to refuse — the refusal is wired in before the LLM sees the prompt. This is the same reason SAV-03 puts math outside the LLM: bounding the LLM at the code boundary, not the prompt boundary. AGENT-02's pitch (regulatory-aware autonomy) is strongest when the refusal cannot be prompt-jailbroken. Bedrock Guardrails is the wrong primitive here (see anti-rec below). |
| Extend `?narrative=off` kill switch | `ui/src/**` | Also collapses AGENT-01 reasoning strip, AGENT-02 hardship card, WF-01 email panel to v2.0 shape in both loading and success states | **Preserves the D-10 byte-equivalence contract** from v2.0. The v3.0 features are additive UI surfaces, all feature-flagged behind the same URL param. Single kill switch; single rehearsal. |

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `AgentCoreMemorySessionManager` via `bedrock_agentcore.memory.integrations.strands` | Raw `boto3.client('bedrock-agentcore').create_event(...)` / `list_events(...)` inside `agent/agent.py` | **Never for v3.0.** Only if the Strands integration subpackage is pulled from the SDK (not indicated). The raw-boto3 path requires hand-rolling namespace handling, event pagination, and turn-vs-event semantics that the adapter encapsulates. |
| AgentCore Memory (short-term events, no strategies) | DynamoDB table for conversation state | If v3.0 scope changed to "cross-session workflow continuity across days," DynamoDB becomes competitive because its query patterns are simpler. For single-session two-turn continuity (WF-01 as specified), AgentCore Memory is the right tool — it's what it's for. |
| L2 `Memory` construct from `aws-cdk.aws-bedrock-agentcore-alpha` | L1 `CfnMemory` from `aws-cdk-lib.aws_bedrockagentcore` | **If the L2 construct has shape issues** (alpha modules occasionally rename properties between patches). L1 is slightly more verbose but stable. |
| L2 `Memory` construct | `CustomResource` Lambda calling `boto3.client('bedrock-agentcore-control').create_memory(...)` | Last-resort break-glass. Only if both L2 and L1 fail. Mentioned here because the v1.0 seeder Lambda already uses the `CustomResource` pattern (`infrastructure/seed_data/...`) — precedent exists in-repo. |
| `ConcurrentToolExecutor` (Strands default) | `SequentialToolExecutor` | **If the AGENT-01 reasoning strip looks incoherent** because the tool narrative order doesn't match the arrival order. Decision: default to concurrent; flip to sequential if the T-24h rehearsal exposes ordering issues in the strip. |
| Pre-agent-call hardship short-circuit (code-level refusal) | Bedrock Guardrails with a "deny tariff-switching" topic + custom refusal message | Only if AGENT-02's pitch shifts from "deterministic, code-audited refusal" to "policy-layer defense in depth." For a demo where the claim is "regulatory-aware," code-level is the stronger demo story. Guardrails is the right backstop in a production deployment but not load-bearing for v3.0. |
| Buffered reasoning trace returned inside the existing JSON response | SSE or Lambda response streaming | Only if the UI "Thinking…" strip needs genuinely live updates. For a demo where timing is scripted, buffer-and-replay is simpler, preserves the API Lambda `Config(read_timeout=25, connect_timeout=5)` invariant, and doesn't require API Gateway rearchitecting. |
| `typing.Protocol` for `CustomerDataProvider` | `abc.ABC` with `@abstractmethod` decorators | Only if a future impl needs runtime `isinstance` checks. Structural typing matches the "real-CRM SDK we don't own" story better; `ABC` forces subclassing. |
| `pydantic.BaseModel` for provider return shapes | `dataclasses.dataclass` + `dataclasses_json` | Never for v3.0 — Pydantic is already the agent's schema boundary and already load-bearing in the narrative gauntlet. Adding a second DTO library fragments the freeze. |
| DynamoDB: add new items for CUST-004 / CUST-005 + one tariff archetype | Re-model the DynamoDB schema with composite sort keys, GSI, etc. | Never for v3.0. New personas are 2 × 12 = 24 new billing records + 2 profile rows + 1 tariff plan. The existing single-table layout handles it. Schema drift would break the `tests/conftest.py` byte-exact savings fixtures. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **A separate LLM for AGENT-01's "intent" phase** (e.g. Haiku for intent → Sonnet for final answer) | Doubles the warm-path count, doubles IAM grants, doubles the freeze pin surface. Sonnet 4.6 handles intent + orchestration in one model call on the v2.0 path — no evidence v3.0 needs a smaller cheaper model for intent. | One Sonnet 4.6 invocation per turn, as v2.0. |
| **Bedrock Guardrails as the AGENT-02 refusal primitive** | Guardrails is a reactive content filter, not an orchestration/routing primitive. It blocks content; it doesn't bypass the LLM entirely with a deterministic refusal payload that the UI can render as a hardship card. Using it would dilute the "autonomy boundary is code-enforced" claim into "autonomy boundary is a filter the model could probe around." | Code-level short-circuit in `agent/agent.py::invoke()` (or a pre-tool in the agent graph). Guardrails is still available as an orthogonal backstop in production — out of scope for the v3.0 demo. |
| **LangChain / LangGraph for multi-tool orchestration** | Same reason as v2.0: Strands + `ConcurrentToolExecutor` + `@tool` decorator already does multi-tool orchestration with the right execution model and streaming events. LangGraph is a second orchestrator with a second agent loop and a second IAM surface. | Strands 1.37's default `ConcurrentToolExecutor`; swap to `SequentialToolExecutor` if narrative order matters. |
| **A new memory-layer library (Zep, MemGPT, Letta, mem0)** | WF-01 says "exercise AgentCore Memory" specifically — swapping to a third-party memory store defeats the point of the feature, and also means a new client lib in the freeze, a new credential, and a new region boundary. | AgentCore Memory via the `bedrock-agentcore` SDK's `AgentCoreMemorySessionManager`. |
| **SSE / Lambda response streaming for the reasoning trace** | Would require replacing the HTTP-API-v2 integration with WebSocket API or enabling Lambda response streaming — both non-trivial stack changes during a freeze-sensitive milestone. Doesn't materially improve the demo (timing is scripted). Breaks the `Config(read_timeout=25, connect_timeout=5)` invariant. | Buffer the `stream_async` events inside the API Lambda; return them in a `reasoning_trace: []` field on the JSON response; UI replays with CSS animation. |
| **A new testing framework or fixture library** (e.g. `hypothesis` for property tests on the provider Protocol) | The existing `pytest` + `conftest.py` fixture pattern already locks byte-exact persona outputs. Property testing is overkill for a 2-persona addition. | Extend `tests/conftest.py` with `mock_solar_response` / `mock_ev_response` fixtures using the same byte-exact pattern as `mock_sarah_response` / `mock_marcus_response` / `mock_elena_response`. |
| **A new UI state-management library** (`zustand`, `jotai`, `redux`) for the reasoning strip / email draft / hardship card | v2.0 ships without any, using plain React hooks. Three small additive surfaces don't justify a state lib. | `useState` + `useReducer` local to the relevant components. |
| **`react-query` / TanStack Query** for the WF-01 second-turn fetch | Same as v2.0 — adding a data-fetching lib for one extra call isn't justified. | Plain `fetch` + `useState`, matching the existing v2.0 pattern. |
| **Poetry / `uv` / Hatch migration** during v3.0 | Mid-milestone tool switch is pure drift. v2.0 already proved `pip-tools` + `--require-hashes` works for the freeze. | Stay on `pip-tools`. Revisit if/when PROD-02 is scoped. |
| **Customer-facing auth (Cognito, Amplify Auth)** | v3.0 keeps PROD-02 deferred; no customer-facing surface is being built. Adding auth plumbing for the rep-side workflow surface is over-engineering — the rep is already authenticated into the call-centre app in the target deployment. | No auth in v3.0. Deferred to a future milestone if/when PROD-02 moves in. |
| **Per-turn telemetry / `?observe=on` overlay** beyond the existing `_narrative_source` + new `_workflow_source` markers | Every observability knob added is a freeze pin. | Reuse the `_narrative_source` pattern for the new surfaces; if v3.0 phases find they need more, add it inside the `?narrative=off` kill-switch contract, not as a new lib. |

---

## Stack Patterns by Variant

**If WF-01 scope expands to cross-session memory (e.g. "remember the rep's last 10 drafted emails across days"):**
- Keep the `AgentCoreMemorySessionManager`, but enable a `ManagedMemoryStrategy` of type `USER_PREFERENCE` or `SUMMARIZATION` on the Memory resource at CDK provisioning time.
- Add a second data-plane call via `session.search_long_term_memories(query=..., top_k=3)` in a new agent tool.
- Out of scope for v3.0 as defined — WF-01 as written is two-turn, same-session.

**If AGENT-01 needs more than ~4 tool calls per turn:**
- Hard-cap the Strands `Agent(max_iterations=...)` parameter (exists on `Agent.__init__` as of 1.37).
- Add a fallback narrative for the "loop exceeded" case, same pattern as the existing narrative-fallback-salvage in `agent/agent.py`.
- PITFALLS.md already flags this as the runaway-agent risk.

**If the L2 `Memory` construct in `aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0` has shape issues:**
- Fall back to L1 `CfnMemory` in `aws-cdk-lib.aws_bedrockagentcore`.
- If that also misbehaves, drop to a `CustomResource` Lambda calling `boto3.client('bedrock-agentcore-control').create_memory(...)` — precedent exists in the v1.0 seeder.

**If CUST-004 / CUST-005 personas want hourly usage (solar export curves, EV overnight charging):**
- Do NOT change the `tariff-billing` table schema.
- Add an auxiliary `customer-usage-profile` DynamoDB item keyed by `CUST-ID#PROFILE` with a JSON blob containing the hourly shape.
- Expose it via a new provider method `get_hourly_profile(customer_id)` on the Protocol.
- Cheaper than re-modelling the monthly-billing schema.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `bedrock-agentcore==1.6.4` | `strands-agents==1.37.0` | **Verified in Strands community-session-managers docs at research time.** The `AgentCoreMemorySessionManager` signature `(config: AgentCoreMemoryConfig, region_name: str)` matches what Strands 1.37's `Agent(session_manager=...)` expects. If the next `bedrock-agentcore` patch changes the adapter shape, the pin prevents surprise. |
| `aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0` | `aws-cdk-lib==2.251.0` | Mixed versions. Known-good in v2.0 production; carried forward unchanged. The alpha module is pinned to `2.250.0a0` deliberately — **do not** bump to `2.251.0a0` without a full `cdk diff` and fresh smoke test (alpha modules occasionally rename L2 props between patches). |
| AgentCore Memory resource | `bedrock-agentcore` service model in `boto3==1.42.96` | Verified indirectly — the v2.0 `scripts/prewarm.py` already calls `client = boto3.client("bedrock-agentcore", region_name="us-east-1")` successfully. The same client instance handles `invoke_agent_runtime` (runtime) and `create_event` / `list_events` (memory data plane). Control-plane operations (`CreateMemory`, `UpdateMemory`, `ListMemories`) are on the separate `bedrock-agentcore-control` service model, also in 1.42.x. |
| Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6`) | Strands `ConcurrentToolExecutor` | Sonnet 4.6 supports parallel tool use natively (Anthropic's tool-use v2 contract). Phase 06.1 of v2.0 resolved the Sonnet 4.6 tool-use regression against `simulate_savings`; the same fix applies to multi-tool turns. |
| Python 3.13 (developer venv) | Python 3.12 (AgentCore container runtime) | Unchanged from v2.0 — `agent/` imports are bi-mode (`from narrative.X` vs `from agent.narrative.X`) to survive the container vs repo layout difference. New providers module must follow the same bi-mode pattern: `lambda/providers/` ships to the Tools Lambda asset, where it's a top-level import; in the repo it's under `lambda.providers`. `lambda/handler.py` already uses this pattern implicitly (zip-bundle layout) so the new module just joins the bundle. No bi-mode gymnastics needed for providers — only the agent side has the Dockerfile COPY gotcha. |
| Tariff catalog in `lambda/tariff_plans.json` + `infrastructure/seed_data/tariff_plans.json` | `tests/conftest.py` fixtures | Adding one new tariff archetype (REC-04) means **both** JSON files update, and `tests/conftest.py`'s byte-exact fixtures grow to cover CUST-004 / CUST-005 + the new archetype. Invariant unchanged: `lambda/tariff_plans.json` is source of truth for tests. |

---

## Sources

### Verified (HIGH confidence)
- Strands Agents docs via Context7 — `https://strandsagents.com/docs/community/session-managers/agentcore-memory` — `AgentCoreMemorySessionManager` + `AgentCoreMemoryConfig` signature and usage pattern (2026-04-28)
- Strands Agents docs via Context7 — `https://strandsagents.com/docs/user-guide/concepts/tools/executors` — `ConcurrentToolExecutor` is the default; `SequentialToolExecutor` available as an override (2026-04-28)
- Strands Agents docs via Context7 — `https://strandsagents.com/docs/user-guide/concepts/streaming/async-iterators` — `agent.stream_async(...)` event iterator with `tool_use_stream` event shape (2026-04-28)
- PyPI — `bedrock-agentcore` current version `1.6.4` released 2026-04-23 — https://pypi.org/project/bedrock-agentcore/
- AWS Docs — `https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html` — short-term vs long-term memory, two-plane API architecture
- AWS Docs — `https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-get-started.html` — `bedrock-agentcore-control` control plane + `bedrock-agentcore` data plane split, `MemorySessionManager` / `add_turns` / `search_long_term_memories` helpers
- AWS CDK docs — `aws-cdk.aws-bedrock-agentcore-alpha` — L2 `Memory` construct exists alongside `MemoryBase`, `MemoryProps`, `MemoryAttributes`, `ManagedMemoryStrategy`, `SelfManagedMemoryStrategy`
- Existing repo — `requirements.in`, `agent/agent.py`, `api_lambda/handler.py`, `CLAUDE.md` (locked invariants: SAV-03, REC-03, D-15, D-04, bi-mode imports, region hardcoded, model literal, `Config(read_timeout=25, connect_timeout=5)`)
- v2.0 research — `.planning/milestones/v2.0-research/STACK.md` (carry-forward baseline)

### Verified (MEDIUM confidence — authoritative but not fetched at full fidelity)
- AWS Docs — `https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html` — Bedrock Guardrails covers denied topics / word filters / PII / content filters with customisable refusal messages, but does not provide routing/orchestration. Basis for the anti-recommendation against using Guardrails for AGENT-02 routing.
- AgentCore Memory strategies (SEMANTIC / SUMMARIZATION / USER_PREFERENCE) — docs confirm the three-category split (built-in / built-in-overrides / self-managed) but full strategy names require a second docs page not fetched. v3.0 uses **no strategies** (short-term events only), so this is non-blocking.

### Training-knowledge (LOW-to-MEDIUM — flagged for Phase 1 verification)
- CDK `aws_bedrock_agentcore_alpha.Memory` L2 construct exact property names (`name`, `description`, `memoryStrategies`, `eventExpiryDuration`) — verify against `cdk synth` output before committing. Fallback paths (L1 `CfnMemory`, `CustomResource`) are both viable.
- Exact IAM action names for the AgentCore runtime role to publish events to its own Memory resource (`bedrock-agentcore:CreateEvent`, `bedrock-agentcore:ListEvents`, `bedrock-agentcore:RetrieveMemoryRecords` — inferred from the boto3 examples but not cross-checked against an IAM policy simulator).

### Sources that could not be fetched during this research run
- Several Strands user-guide URLs returned 404 (old site structure); Context7 `ctx7 docs` recovered the content via the aggregated `llms-full.txt` export. The aggregated source is authoritative-equivalent for documentation content but not for exact URL citations.
- Strands `Agent(max_iterations=...)` and `Agent(session_manager=...)` constructor signatures are described in the community-session-managers doc and the concurrent-executor doc respectively, but were not cross-verified against the SDK source. Phase 1 of v3.0 should pin-check against the installed wheel.

---

## Summary of v3.0 Stack Deltas

**Bumped:** `bedrock-agentcore==1.6.3` → `==1.6.4` (1 pinned top-level dep; regenerates one line of `requirements.txt` hashes).

**Added (AWS resources):** 1 × AgentCore Memory resource, provisioned via the `aws-cdk.aws-bedrock-agentcore-alpha` L2 `Memory` construct already in the pin. No new Python top-level deps. No new UI deps.

**Added (code patterns):** `typing.Protocol` for `CustomerDataProvider` (stdlib); Pydantic models for provider return shapes (already transitively pinned); `AgentCoreMemorySessionManager` wired into the existing `Agent(...)` instance (from the bumped `bedrock-agentcore`).

**Explicitly NOT added:** LangChain/LangGraph, Zep/MemGPT/mem0, Bedrock Guardrails for AGENT-02 routing, a second LLM for intent, SSE/Lambda response streaming, `react-query`, any new state-management lib, any new testing lib, Poetry/`uv`, Cognito/Amplify Auth.

**Freeze contract:** One pinned dep bump. One regenerated hash. One round of `pip install --require-hashes` validation. v3.0 will earn its own `demo-v3.0` tag with its own stack-policy ceremony at milestone end. The `demo-v2.0` frozen stacks are untouched throughout v3.0 development (new Memory resource lands in the unfrozen Frontend-pattern way: via a new or extended stack, not by mutating `CustomerTariff` / `CustomerTariffAgent` / `CustomerTariffApi` under their `deny-Update:*` policies — **verify at Phase 1 whether AgentCore Memory cleanly attaches via a new stack or forces a lift-and-update on `CustomerTariffAgent`**).
