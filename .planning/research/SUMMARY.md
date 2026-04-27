# v3.0 Research Summary — Agentic Depth & Workflow Assist

**Project:** Customer Tariff & Billing Optimisation Agent
**Milestone:** v3.0 — extends frozen `demo-v2.0` with multi-tool reasoning, regulatory autonomy boundary, rep-side workflow surface, two new personas, a new tariff archetype, a production-shaped data adapter, and three committed presenter artefacts
**Researched:** 2026-04-28
**Confidence:** MEDIUM-HIGH overall (HIGH on everything carried forward from v2.0; HIGH on Strands 1.37 + AgentCore Memory integration shape; MEDIUM on AgentCore Memory operational behaviour under load; MEDIUM on regulatory clause specifics in AGENT-02 copy)

> **Deltas-only milestone.** v1.0 and v2.0 are shipped behind `demo-v2.0` with deny-Update:* stack policies on three stacks. This synthesis covers ONLY what v3.0 adds on top. The 15 locked invariants from CLAUDE.md (SAV-03, REC-03, D-04, D-15, SC-3 `runtimeSessionId`, `_narrative_source` strip, `customer-not-found` detection at `api_lambda/handler.py:152`, bi-mode imports, region pin, model literal, `Config(read_timeout=25, connect_timeout=5)`, `?narrative=off` kill switch, `?prewarm=1` 204 contract, `tariff_plans.json` duplication source-of-truth, frozen-lockfile `--require-hashes` contract) are load-bearing inputs, not subjects of re-research.

---

## Executive Summary

v3.0 moves the demo from "structured-output formatting" (v2.0) to a credible agentic-depth showcase by adding four capability categories on top of the frozen v2.0 base: (1) **multi-tool reasoning** on a new bill-shock persona-flow (AGENT-01), (2) a **code-enforced regulatory autonomy boundary** that refuses tariff recommendations for hardship-flagged customers (AGENT-02), (3) a **second-turn workflow-assist surface** — "draft follow-up email" powered by AgentCore Memory (WF-01), and (4) **two new personas + one new tariff archetype** (DATA-04 / REC-04) plus a **production-shaped data adapter** (PROD-01) that makes DOC-03's "deferred roadmap" story concrete. All four dimensions of research converge on the same conclusion: the technical approach is well-understood, the primary risk is **freeze-surface expansion** against three stacks under deny-Update:* policies, not novel engineering.

The **recommended approach** is strangler-fig-shaped throughout: keep v2.0 behaviour intact and byte-exact, add new capabilities behind explicit `action` dispatch, deterministic Memory session keys scoped to `customer:{id}`, a `typing.Protocol`-based adapter seamed at the agent layer (not inside the frozen Tools Lambda), and a Pydantic **discriminated union** (`kind: "recommendation" | "hardship"`) on the agent response so the existing `customer-not-found` detection gets a surgical update rather than a rewrite. Only one Python dep bumps (`bedrock-agentcore 1.6.3 → 1.6.4`); zero new UI deps; one new AWS resource (AgentCore Memory). The largest operational cost is the **stack-policy lift-and-reapply ceremony** — DATA-04/REC-04/AGENT-01/AGENT-02/WF-01 all touch at least one of the three frozen stacks, so v3.0 ends with its own `demo-v3.0` tag and fresh freeze manifest (same shape as v2.0, not new territory).

The **key risks** cluster into three buckets. **Invariant collision:** the hardship branch returns no `green`/`cheapest` keys, which trips the existing `customer-not-found` detection — mitigated by the discriminated union and a surgical update to `api_lambda/handler.py:152`. **Latency stacking:** AGENT-01's 2–3 sequential tool calls add ~400–900ms over the v2.0 single-tool warm path, potentially breaching the UI-02 <3s gate — mitigated by Strands 1.37's `ConcurrentToolExecutor` default, a 4-tool hard cap in prompt, per-flow prewarm gates, and a buffered (not streamed) reasoning-trace UX. **Cross-customer bleed via Memory:** AgentCore Memory's isolation unit is `actorId`, not `runtimeSessionId`; WF-01 must commit to `actorId = f"customer:{customer_id}"` before any Memory wiring, with live cross-customer isolation smoke tests — this is the single most catastrophic failure mode if missed (PII bleed on stage). Each of these is preventable with decisions that must lock *before* phase planning, hence the seven locked decisions below.

---

## Locked Decisions (Cross-Cutting)

These seven decisions resolve where the four research files diverged. Each is a pre-plan commit so the roadmapper can phase around them without re-litigating.

| # | Decision | Driver | Why This Shape |
|---|----------|--------|----------------|
| **LD-1** | **Build order: DATA-04 → PROD-01 → AGENT-01 → AGENT-02 → WF-01 → DOC-01/02/03 → v3.0 freeze.** PROD-01 lands *before* AGENT-01/02 as the strangler-fig seam; DATA-04 goes first because every other feature tests against the new personas. | ARCHITECTURE primary; FEATURES validates parallelism; PITFALLS argues for strangler-fig | Resolves the FEATURES vs ARCHITECTURE vs PITFALLS ordering conflict. PITFALLS flagged PROD-01 as a Chesterton's-Fence refactor risk and recommended either "dual-impl from day 1" or defer. We choose **dual-impl from day 1** (DynamoDB + InMemory providers land together in Phase 2, making the abstraction actually generalise). This requires PROD-01 *before* AGENT-01/02 so the new tools use the provider from first commit rather than being refactored later. FEATURES' "DATA-04 + PROD-01 parallel" is discarded because parallel work on the same frozen stack (`CustomerTariff`) multiplies lift ceremonies and merge friction for no critical-path gain. |
| **LD-2** | **AGENT-02 response shape: Pydantic discriminated union** `Annotated[Union[RecommendationResponse, HardshipRoutingResponse], Field(discriminator="kind")]` with `kind: Literal["recommendation"] \| Literal["hardship"]`. Customer-not-found detection at `api_lambda/handler.py:152` updates to: `if "green" not in body and body.get("kind") != "hardship": return 404`. | ARCHITECTURE recommended; PITFALLS C2 lockstep-requires | Resolves the "hardship → 404 false-positive" collision with the v2.0 detection invariant. Option (b) — "optional `hardship_routing` field, both tracks still present" — violates the *spirit* of REC-03 (you'd return two tracks you're telling the rep not to recommend). Option (c) — "200 with empty tracks + hardship flag" — requires the same surgical detection update anyway, with muddier schema. Union is cleaner, Pydantic-native, and the `kind` field future-proofs for WF-01's `FollowUpEmailResponse` shape too (a third discriminator branch). UI gets `kind?: "recommendation" \| "hardship"` as backwards-compat optional TS type. |
| **LD-3** | **WF-01 Memory scope: short-term only** (last-k session events, no `SEMANTIC`/`SUMMARIZATION`/`USER_PREFERENCE` strategies). `actorId = f"customer:{customer_id}"`. Memory session key derived as `f"{customer_id}-{date.today().isoformat()}"` (UTC-pinned). TTL set to hours (~8-12h) not days. `scripts/memory-reset.sh` runs at T-24h and T-2h per updated DEMO-RUNBOOK. | FEATURES highest-leverage question; STACK confirmed path; PITFALLS C4 critical | FEATURES flagged short-vs-long-term as a 2–3× complexity swing and recommended short-term for MVP. Long-term memory requires demo-contrived "prior session" seeding and opens PII/retention questions not worth the marginal story gain for a 45-min presentation. `actorId=customer:{id}` is NOT negotiable — it's the structural prevention for PITFALL C4 (cross-customer bleed via Memory). Runtime session distinction: `runtimeSessionId` stays fresh-uuid4-per-invocation (SC-3 unchanged); Memory `session_id` is deterministic — these are orthogonal AWS concepts, documented at the call site to prevent AP-2 confusion. |
| **LD-4** | **AGENT-01 latency target: warm p95 < 2500ms** (500ms headroom against UI-02 <3000ms gate). Tool execution via Strands 1.37 `ConcurrentToolExecutor` (default) with **hard cap of 4 tool calls per turn** via `Agent(max_iterations=...)`. Reasoning-trace UX uses **buffered return**, not SSE — trace is collected into `reasoning_trace: []` on the JSON response and replayed client-side with CSS animation. Escape valve: if rehearsal shows concurrent-tool narrative order is incoherent, swap to `SequentialToolExecutor` for AGENT-01 only. | FEATURES + PITFALLS C1 both flagged; STACK confirmed default | Resolves UI-02 regression risk. Sonnet 4.6 supports parallel tool-use natively; Strands 1.37 ships it as the default executor. Buffered-vs-streaming avoids the `Config(read_timeout=25, connect_timeout=5)` invariant collision and the API-Gateway-v2-WebSocket rearchitect. 4-tool cap prevents runaway ReAct loops. Per-flow prewarm gate (not the v2.0 global 3000ms gate) enforces the budget pre-freeze. |
| **LD-5** | **PROD-01 scope: `CustomerDataProvider` Protocol + `ToolsLambdaProvider` (DynamoDB-backed demo impl) + `InMemoryProvider` (test double)** — three concrete pieces, one location (`agent/providers.py`). Pydantic BaseModel return types. No consent layer, no circuit breaker, no cache, no PII redaction wrapper, no audit log in v3.0 scope — all documented in DOC-03 as deferred. A `NotImplementedError` `SalesforceCustomerDataProvider` stub file lands as DOC-03 evidence. | ARCHITECTURE recommended location; PITFALLS recommended dual-impl; FEATURES recommended interface-only MVP | Resolves the three-way scope split. PROD-01 scoped too narrowly (interface-only, one impl) is Chesterton's-Fence refactor risk per PITFALLS C7; scoped too broadly (interface + consent + audit + circuit-breaker) fragments the freeze budget per FEATURES. The middle path — **two implementations from day one, three methods max** — forces the abstraction to generalise (structural-typing proof via `@runtime_checkable` Protocol), keeps surface small, and ships with the byte-exact SAV-03 canary gate on BOTH impls. Location is `agent/providers.py` (not `lambda/providers.py` or `common/providers.py`) to preserve bi-mode imports and keep the frozen Tools Lambda untouched. |
| **LD-6** | **Stack-policy lift ceremony is a dedicated phase gate.** v3.0 touches all three frozen stacks: `CustomerTariff` (DATA-04 seeder + Tools Lambda asset), `CustomerTariffAgent` (container rebuild + new IAM + MEMORY_ID env var), `CustomerTariffApi` (new route + `kind`-aware detection). Scripted lift (`scripts/stack-policy-lift.sh <stack>`) + apply (`scripts/stack-policy-apply.sh <stack>`) paired with marker-file invariant. Post-deploy `get-stack-policy` byte-equality verification. Termination protection re-check. v3.0 ends with its own `demo-v3.0` tag + fresh freeze manifest + new DynamoDB backup. `CustomerTariffFrontend` (Amplify) is unfrozen; UI changes bypass this ceremony entirely. | ALL FOUR researchers flagged; STACK noted Frontend exception; PITFALLS C6 critical | Same shape as the v2.0 freeze ceremony — not new territory, re-executed. Scripted lift+apply prevents Pitfall C6 (lift-and-forget). Verification gate is mandatory before phase close. This is a ceremony, not a deploy step. |
| **LD-7** | **`?narrative=off` kill switch extends to collapse AGENT-01 reasoning strip, AGENT-02 hardship card, and WF-01 email drawer to v2.0 shape in BOTH loading and success states.** Single URL-level kill switch for the entire v3.0 surface — no new `?mode=v2` flag. `_reasoning_trace`, `_workflow_source` markers follow the `_narrative_source` pattern: agent attaches, API Lambda either passes through (reasoning trace — public for UI) or strips (workflow source — internal, like `_narrative_source`). | ARCHITECTURE + STACK confirmed pattern; FEATURES question 7 | Single rehearsal, single kill switch, single freeze ceremony. D-10 byte-equivalence contract from v2.0 Phase 8 extends naturally. The `?narrative=off` → collapse-to-v1.0 semantics become `?narrative=off` → collapse-to-v2.0 semantics in v3.0 (the presenter can still escape to an earlier-milestone UI shape). Avoids flag proliferation. |

---

## Recommended Feature Scope (REQ-ID In/Out for v3.0)

Derived from FEATURES.md priority matrix, filtered through the locked decisions.

### In scope — P1 (must ship)

| REQ-ID | Feature | Source FEATURES section | Scope notes |
|--------|---------|-------------------------|-------------|
| **DATA-04** | Solar PV (CUST-004) + EV (CUST-005) personas, 12-month billing profiles, `consumption_kwh` + `export_kwh` + `net_kwh` schema extension, `PROFILE` items (hardship_flag for CUST-005 only), byte-exact `mock_cust004_response` / `mock_cust005_response` fixtures | §4 Table Stakes | Engineered savings: CUST-004 ~$40/$70, CUST-005 ~$35/$60 (DEMO-02 parallel). Solar FiT value included in baseline so "Cheapest" doesn't inadvertently recommend losing FiT credits. |
| **REC-04** | At least one new tariff archetype. **Ship BOTH** a Solar FiT plan (`SOL`) and an EV Time-of-Use plan (`TOU-PV` or `EVP`). Extend `simulate_savings_pure` with a `plan_type` dispatcher for TOU math (`_projected_tou_cost` pure helper). Both `lambda/tariff_plans.json` + `infrastructure/seed_data/tariff_plans.json` updated in same commit. | §4 Table Stakes | Shipping only one archetype strands one of the two new personas. SAV-03 invariant strictly preserved — all math in Python, LLM narrates only. |
| **PROD-01** | `CustomerDataProvider` `typing.Protocol`, `ToolsLambdaProvider` (DynamoDB), `InMemoryProvider` (test double), `SalesforceCustomerDataProvider(NotImplementedError)` stub. Three methods max: `get_billing_history`, `get_customer_profile`, `get_tariff_catalog`. Pydantic BaseModel returns. | §5 Table Stakes, filtered by LD-5 | Consent/audit/circuit-breaker deferred to DOC-03. Bi-mode imports honoured. SAV-03 byte-exact canary green on BOTH implementations before phase close. |
| **AGENT-01** | Bill-shock multi-tool flow. 2–3 composed tools (`detect_bill_shock`, `get_billing_history`, `simulate_savings`). Action dispatch on existing Tools Lambda. Tool-call budget cap at 4. Collapsed-by-default `ReasoningTrace` UI (preserves UI-01). Per-persona deterministic fallback narrative. Warm p95 < 2500ms via per-flow prewarm gate. | §1 Table Stakes | Rep-selected intent (NOT LLM-classified). Fixed preference-ordered graph, not free-form. `ConcurrentToolExecutor` default per LD-4. |
| **AGENT-02** | Hardship short-circuit. Code-side pre-LLM guard (refusal is wired before model sees tariff context). `HardshipRoutingResponse` Pydantic schema with `kind` discriminator (per LD-2). Dedicated `HardshipBanner` UI state (amber/warm, not red/error), distinct from 404. Specialist-routing CTA stub. D-15 banned terms extended for hardship: no plan IDs, no recommend-verbs, no "suggest"/"best for". Audit log of short-circuit events. Adversarial test across 10 seeds asserting no plan-ID leak. | §2 Table Stakes | `hardship_flag` is a DATA field, never LLM-inferred. `api_lambda/handler.py:152` detection updated surgically per LD-2. Copy reviewed for dignity before freeze. |
| **DOC-01** | Trust-architecture one-pager — 4 LLM-bounding patterns (SAV-03 no-arithmetic, D-15 narrative gauntlet, fallback bank, `_narrative_source` observability) + AGENT-02 as regulatory autonomy boundary. Every claim backed by a pytest or CloudWatch metric. Legal review flagged for AER/Ofgem clauses before freeze. | §DOC-01 | Claim-check each sentence against live evidence (Pitfall M7 prevention). |
| **v3.0 Freeze Ceremony** | New `demo-v3.0` annotated tag, fresh freeze manifest, new DynamoDB backup, re-applied stack policies (verification via byte-equal `get-stack-policy`), termination-protection re-check. Rollback drill (`?narrative=off` + `build:mock` + `git checkout demo-v2.0` fresh-clone) green. | STACK §Summary + PITFALLS C6 | Same ceremony as v2.0, re-executed. Budgeted as its own phase. |

### In scope — P2 (should ship; cut if overrun)

| REQ-ID | Feature | Source FEATURES section | Scope notes |
|--------|---------|-------------------------|-------------|
| **WF-01** | Draft follow-up email. Second API route `GET /recommendations/{customer_id}/follow-up`. AgentCore Memory short-term only per LD-3. `FollowUpEmailResponse` Pydantic schema (discriminated-union third branch). Deterministic subject line, LLM body only, D-15-extended long-form validator. Deterministic fallback template. Edit + copy-to-clipboard (send is stubbed). | §3 Table Stakes | P2 because it's the largest freeze-lift and the most cross-cutting (Memory + new API route + UI drawer + long-form validator). If rehearsal budget tight, ship DOC-* before WF-01 and defer WF-01 to v3.1. |
| **DOC-02** | Narrative-tradeoff acknowledgement. Honest cost-vs-value of LLM narrative with specific v2.0 case studies (Sonnet 4.6 tool-use regression, salvage path activation rate, fallback-bank hits). No marketing adjectives. | §DOC-02 | Depends on v2.0 operational artefacts already in repo. |
| **DOC-03** | Deferred-roadmap doc. Architecture diagram with PROD-01 in-flight + PROD-02 boxed-and-deferred. Visible `NotImplementedError` stub references. Distinguishes "in-flight" from "planned" from "aspirational". No dates. | §DOC-03 | Depends on PROD-01 shipped to describe "in-flight" accurately. |

### Out of scope for v3.0 (explicit anti-features or deferred)

| Item | Why out | From |
|------|---------|------|
| WF-01 long-term memory (`SEMANTIC`/`USER_PREFERENCE` strategies, cross-session recall) | 2–3× complexity swing per LD-3; demo-contrivance cost too high for marginal story gain | LD-3, FEATURES §3.3 |
| LLM-driven intent classification ("customer asks free-form, agent routes") | Customer-facing NLU is PROD-02 territory; rep selects intent via buttons in v3.0 | FEATURES §1.3 |
| SSE / Lambda response streaming for reasoning trace | Breaks `Config(read_timeout=25)` invariant; API-Gateway-v2-WebSocket rearchitect during freeze-sensitive milestone | LD-4, STACK §"What NOT to Use" |
| Streaming tool-call strip (live character-by-character) | Demo-fragile same as v2.0 streaming narrative; buffer-and-replay with CSS animation looks equivalent | FEATURES §1.2 differentiator deferred |
| Auto-send email, auto-unflag hardship, memory-based recommendations | Regulatory/compliance anti-patterns | FEATURES §3.3, §2.3 |
| Battery persona (CUST-006), generator persona, real-time weather/solar forecasting, per-interval (30-min) usage data | Scope explosion without a tariff archetype to match | FEATURES §4.3 |
| Real Salesforce/Dynamics CRM integration, write-back capability, full PROD-02 customer-facing portal | PROD-02 territory, re-evaluated after v3.0 ships | PROJECT.md, FEATURES §5.3 |
| Bedrock Guardrails as AGENT-02 primitive | Reactive filter, not routing primitive; dilutes code-enforced-boundary story | STACK §"What NOT to Use" |
| LangChain/LangGraph, Zep/MemGPT/mem0, second LLM for intent, new UI state-mgmt lib, react-query, Poetry/uv migration, Cognito/Amplify Auth, per-turn telemetry overlay | All explicitly avoided — no new Python top-level deps beyond the one `bedrock-agentcore` bump | STACK §"What NOT to Use" |
| Tone selector, language selector, regenerate button, usage-profile charts, circuit breaker on adapter, PII-redaction wrapper, pagination for billing history, source-tagging, cross-customer batch methods | Differentiators deferred to v3.1+ | FEATURES §3.2, §4.2, §5.2 |

---

## Recommended Build Order

Per LD-1. Seven phases; dependency-ordered; each phase names which pitfalls it owns preventing and which invariants it preserves.

### Phase 1 — DATA-04 + REC-04: new personas + tariff archetype + net-metering math

- **Rationale:** Every other feature tests against these personas. Without CUST-004/005 and `TOU-PV`/`SOL`, AGENT-01/02/WF-01 can't run end-to-end. Shipping DATA-04 and REC-04 together avoids two separate lift ceremonies on the `CustomerTariff` stack.
- **Delivers:** CUST-004/005 billing rows, `PROFILE` items (hardship_flag), `TOU-PV` + `SOL` plans in both `tariff_plans.json` files, `simulate_savings_pure` extended with `plan_type` dispatcher, `mock_cust004_response` / `mock_cust005_response` fixtures with byte-exact savings.
- **Stack policy:** Lift `CustomerTariff` (deny-Update:*) → deploy → verify → re-apply + termination protection check.
- **Unblocks:** Everything else.
- **Owns prevention for:** PITFALL M1 (`tariff_plans.json` drift — byte-equality pytest gate), PITFALL M2 (non-reproducible seed — `cdk destroy+deploy` on scratch stack), PITFALL m3 (hardship_flag default=False on existing personas), PITFALL C6 (scripted lift+reapply ceremony).
- **Invariants at risk:** SAV-03 byte-exact continuity for CUST-001/002/003 through the TOU dispatcher refactor; `tariff_plans.json` duplication source-of-truth.

### Phase 2 — PROD-01: `CustomerDataProvider` abstraction (dual-impl from day 1)

- **Rationale:** Lands before new tools so those tools call through the provider from first commit, per LD-1 and LD-5. Refactoring after the fact would mean rewriting every tool. Dual-impl (DynamoDB + InMemory) forces the abstraction to generalise before it ships.
- **Delivers:** `agent/providers.py` with `typing.Protocol` + `ToolsLambdaProvider` + `InMemoryProvider`. Existing `simulate_savings` `@tool` refactored to call through provider. Byte-exact SAV-03 canary green on BOTH impls. `SalesforceCustomerDataProvider(NotImplementedError)` stub. Live smoke: existing recommend path produces unchanged bytes.
- **Stack policy:** Lift `CustomerTariffAgent` (container rebuild) → deploy → verify → re-apply.
- **Owns prevention for:** PITFALL C7 (Chesterton's-Fence adapter refactor — strangler-fig + dual-impl + byte-exact gate + bi-mode container smoke).
- **Invariants at risk:** Bi-mode imports (new `providers.py` needs `try: from providers import ... except: from agent.providers import ...`), SAV-03 byte-exact through the provider indirection.

### Phase 3 — AGENT-01: bill-shock multi-tool flow

- **Rationale:** AGENT-02 depends on `get_hardship_flag` tool, which is cleanest to land alongside `detect_bill_shock` (both are new Tools Lambda actions, both agent-side `@tool` wrappers via the provider). Landing AGENT-01 first also proves the reasoning-trace UX and the latency budget before AGENT-02's schema churn.
- **Delivers:** `lambda/handler.py` action dispatcher + `detect_bill_shock_pure` + `get_billing_history_pure` + `get_hardship_flag_pure` + `get_customer_profile_pure`. Agent `@tool` wrappers via provider. System prompt updated for bill-shock flow (preference-ordered tool graph, 4-tool hard cap). `reasoning_trace` collection in agent `invoke()`. API Lambda passes through `reasoning_trace`. UI `ReasoningTrace` component (collapsed by default — UI-01 verified at 1280×800). Per-flow prewarm gate added to `scripts/prewarm.py` asserting warm p95 < 2500ms.
- **Stack policy:** `CustomerTariff` lift (Tools Lambda asset) + `CustomerTariffAgent` lift (container rebuild).
- **Owns prevention for:** PITFALL C1 (multi-tool latency stacking — per-flow prewarm gate, `ConcurrentToolExecutor`, 4-tool cap), PITFALL C5 (Strands multi-tool fabrication — cross-persona canary across CUST-002/004/005, CloudWatch tool-invocation counter, latency-floor witness), PITFALL M4 (D-04 fallback for new response shape with `reasoning_trace`), PITFALL M5 (prewarm extended per-flow).
- **Invariants at risk:** UI-02 <3s, SAV-03 (every new arithmetic tool must stay pure Python), UI-01 (collapsed trace preserves vertical).

### Phase 4 — AGENT-02: hardship short-circuit

- **Rationale:** Depends on `get_hardship_flag` tool (landed Phase 3). Depends on the discriminated-union schema change in API Lambda, which happens after Phase 3's API Lambda changes stabilise (avoid rebase churn on the same file).
- **Delivers:** `HardshipRoutingResponse` Pydantic schema + discriminated union. `kind` field on `RecommendationResponse` (backwards-compat optional with `"recommendation"` default). Code-side pre-LLM guard in `agent/agent.py::invoke()`. Agent system prompt: hardship branch with different prompt (no tariff context). `_narrative_fallback_salvage` extended. `api_lambda/handler.py:152` updated to `if "green" not in body and body.get("kind") != "hardship": return 404`. UI `HardshipBanner` + `types.ts` discriminated union. Audit log of short-circuit events. Adversarial test across 10 seeds.
- **Stack policy:** `CustomerTariffAgent` lift (container) + `CustomerTariffApi` lift (handler code change).
- **Owns prevention for:** PITFALL C2 (hardship → 404 false-positive — surgical detection update + both branches tested), PITFALL C3 (soft-decline leak — code-side short-circuit + extended D-15 banned terms + adversarial test), PITFALL M4 (D-04 fallback for hardship shape).
- **Invariants at risk:** `customer-not-found` detection regression (non-negotiable test coverage), REC-03 applicability (amended to condition on `hardship_flag=false`), D-15 banned terms (extended for hardship).

### Phase 5 — WF-01: draft follow-up email via AgentCore Memory

- **Rationale:** Depends on Phase 3/4 agent producing memorable turn-1 context. AgentCore Memory is a new AWS resource + new API route + new Pydantic schema — the largest freeze-lift of the milestone; do it after the smaller changes are green. P2 per scope — ship if phase budget allows, defer to v3.1 if not.
- **Delivers:** `infrastructure/constructs/agent_memory.py` (L2 `Memory` construct with fallback paths to L1 `CfnMemory` or `CustomResource`/boto3). `MEMORY_ID` env var on agent runtime. `bedrock-agentcore==1.6.4` bumped in `requirements.in` + lockfile regenerated under `--require-hashes`. `AgentCoreMemorySessionManager` wired into Strands `Agent(session_manager=...)`. `draft_follow_up` action in agent `invoke()`. New route `GET /recommendations/{customer_id}/follow-up` on `CustomerTariffApi`. Deterministic Memory session_id `f"{customer_id}-{UTC-ISO-day}"` derived inside `follow_up()` (NOT module scope — SC-3 preserved). `FollowUpEmailResponse` schema. `FollowUpEmailDrawer` UI. `scripts/memory-reset.sh` (idempotent). Cross-customer isolation smoke test.
- **Stack policy:** `CustomerTariff` lift (if Memory resource lands there) OR new stack / extension of `CustomerTariffAgent` lift + `CustomerTariffApi` lift (new route). Research flag: verify at Phase 5 start whether Memory attaches cleanly via a new stack or forces `CustomerTariffAgent` update.
- **Owns prevention for:** PITFALL C4 (Memory cross-customer bleed — `actorId=customer:{id}` + live isolation smoke + cleanup script), PITFALL M3 (Memory TTL unset — hours not days + reset script + runbook step), AP-2 (runtime vs Memory session confusion — documented at call site), PITFALL M4 (D-04 fallback for email shape), PITFALL M5 (prewarm extended to follow-up endpoint).
- **Invariants at risk:** SC-3 `runtimeSessionId` fresh-uuid4-per-invocation (preserved — Memory session_id is a *different* concept); `--require-hashes` reproducibility (one dep bump, one hash regen); `?narrative=off` kill switch (extended to email drawer).

### Phase 6 — DOC-01 / DOC-02 / DOC-03 + operational consolidation

- **Rationale:** Writing docs earlier means rewriting them. Architecture decisions crystallise in Phase 1–5; DOC-* summarises with live evidence. Operational consolidation (`scripts/demo-keepalive.sh` rotating all 5 personas, DEMO-RUNBOOK v3.0 update, Memory reset runbook step, 7-minute presentation script) lands here too.
- **Delivers:** `.planning/docs/presenter/TRUST-ARCHITECTURE.md` (DOC-01), `NARRATIVE-TRADEOFFS.md` (DOC-02), `DEFERRED-ROADMAP.md` (DOC-03) with every claim backed by pytest/metric/code reference. README + DEMO-RUNBOOK cross-links. Legal review of AER/Ofgem clauses completed. Extended keep-alive. Updated runbook with Memory reset + all-5-personas T-24h rehearsal.
- **Stack policy:** No lift required — docs + scripts only. Frontend stack may redeploy freely (unfrozen).
- **Owns prevention for:** PITFALL M6 (keep-alive misses new personas — rotation updated), PITFALL M7 (docs over-promise — claim-check against live evidence + `make docs-check` drift gate), PITFALL m5 (persona overload — 7-min script).

### Phase 7 — v3.0 Freeze Ceremony

- **Rationale:** Same shape as v2.0 Phase 10 freeze, re-executed with v3.0-shaped manifest.
- **Delivers:** Re-applied deny-Update:* stack policies on all three frozen stacks with byte-equality verification. Termination protection re-check. New DynamoDB backup. `demo-v3.0` annotated tag cut with `manifest.freeze_commit_sha` self-consistency. Fresh freeze lockfiles. Rollback drill (5/5 PASS per v2.0 pattern: `?narrative=off`, `build:mock` <1s, `git checkout demo-v2.0` fresh-clone pytest green, DynamoDB restore spot-check, scratch teardown). T-24h visual rehearsal with DevTools latency measurement.
- **Owns prevention for:** PITFALL C6 (final stack-policy reapplication with byte-equality gate), PITFALL m2 (frontend stale dist — SHA match at T-2h), AP-6 (fresh freeze manifest — reject skip-the-freeze shortcut).

### Dependency graph

```
Phase 1 (DATA-04+REC-04) ──▶ Phase 2 (PROD-01) ──▶ Phase 3 (AGENT-01) ──▶ Phase 4 (AGENT-02) ──▶ Phase 5 (WF-01) ──▶ Phase 6 (DOC-* + ops) ──▶ Phase 7 (Freeze)
```

Phase 5 is the P2 cut point — if WF-01 is deferred to v3.1, Phase 5 skips and Phase 6 absorbs DOC-03's "PROD-01 in-flight; WF-01 next" framing.

---

## Stack Additions

One row per new dep / resource. Everything else in v1.0/v2.0 lockfiles carries forward unchanged.

| Item | Type | Version / Pin | Purpose | Integration | Fallback |
|------|------|---------------|---------|-------------|----------|
| `bedrock-agentcore` | Python dep BUMP | `==1.6.3 → ==1.6.4` | `AgentCoreMemorySessionManager` + `AgentCoreMemoryConfig` — wires Strands `Agent(session_manager=...)` into Memory in ~3 lines | Strands 1.37 accepts external session manager kwarg | Raw `boto3.client('bedrock-agentcore').create_event(...)` — 200+ lines of ceremony, not chosen |
| AWS Bedrock AgentCore **Memory resource** | AWS service (GA) | n/a | Short-term session events (WF-01 turn-1 → turn-2 continuity). No strategies — `memoryStrategies=[]` on CreateMemory | L2 `Memory` construct in `aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0` (already pinned) | L1 `CfnMemory` from `aws-cdk-lib.aws_bedrockagentcore`; last-resort `CustomResource` Lambda calling `bedrock-agentcore-control.create_memory` (precedent: v1.0 seeder) |
| Lambda Provisioned Concurrency on Tools Lambda | AWS config | `-c demo_pc=N` extended to Tools Lambda | AGENT-01's 2-3 tool invocations per turn — warm first-call path | `live` alias + conditional PC pattern from v2.0 API Lambda | Accept cold first-tool-call latency; not chosen |
| `typing.Protocol` (stdlib, already available) | Python stdlib | Python 3.13 | `CustomerDataProvider` structural typing contract | New file `agent/providers.py` | `abc.ABC` — rejected (forces inheritance, wrong for "real-CRM SDK we don't own" story) |
| `Pydantic BaseModel` (already transitively pinned via `strands-agents`) | Python dep (no bump) | v2.x | Data contract on provider return shapes; `HardshipRoutingResponse` + `FollowUpEmailResponse` schemas + discriminated-union `Annotated[Union[...], Field(discriminator="kind")]` | Reuse existing agent schema boundary | None needed; single schema library |
| `ConcurrentToolExecutor` (Strands default, no config needed) | Strands feature | 1.37.0 default | Parallel tool-use for AGENT-01 multi-tool turn | Already default; no config change | `SequentialToolExecutor` if rehearsal shows narrative-order incoherence |
| `Agent.stream_async(...)` (already in Strands 1.37) | Strands feature | 1.37.0 | Reasoning-trace event collection (buffered return, not SSE) | Event iterator already used by v2.0 narrative salvage path | Buffer the tool-use blocks from `agent_result.message.content[]` directly; redundant safety net |
| No new UI deps | n/a | n/a | `ReasoningTrace`, `HardshipBanner`, `FollowUpEmailDrawer` all compose from existing shadcn primitives (`Card`, `Collapsible`, `Button`, `Textarea`, `Skeleton`) | Plain `useState`/`useReducer` + `fetch` | n/a |

**Explicitly NOT added** (all 4 researchers agreed): LangChain/LangGraph, Zep/MemGPT/mem0, Bedrock Guardrails for routing, second LLM for intent, SSE / Lambda response streaming, `react-query`, Zustand/Jotai/Redux, `hypothesis` property testing, Poetry/`uv`, Cognito/Amplify Auth, any new testing/DTO library.

---

## Top Pitfalls & Mitigations

Five critical + two moderate, linked to phase and prevention strategy. Full list in [`PITFALLS.md`](PITFALLS.md).

| # | Pitfall | Prevention | Phase | Owns-the-gate |
|---|---------|-----------|-------|----------------|
| **C4** | **AgentCore Memory cross-customer bleed** — `actorId` not scoped to customer; Sarah's persona context bleeds into Marcus's follow-up email. **Most catastrophic failure mode** (PII on stage vapourises trust). | `actorId = f"customer:{customer_id}"` (structural, non-negotiable). Live cross-customer isolation smoke test (invoke CUST-001 recommend, then CUST-002 follow-up, assert zero CUST-001 tokens in CUST-002 output). `scripts/memory-reset.sh` at T-24h + T-2h. Memory TTL 8–12h not days. Shape tokens only in Memory events, no customer free text. | Phase 5 (WF-01) | Live isolation smoke test as mandatory phase-close gate |
| **C2** | **Hardship response trips `customer-not-found` 404** — no `green`/`cheapest` keys → `api_lambda/handler.py:152` falls through to 404 branch; hardship-flagged customers render as errors; AGENT-02 story dead. | LD-2 discriminated union + surgical detection update: `if "green" not in body and body.get("kind") != "hardship": return 404`. Both branches tested offline + live smoke. `kind` field on `RecommendationResponse` with default `"recommendation"` for backwards-compat. | Phase 4 (AGENT-02) | Detection test covering both branches |
| **C3** | **Hardship soft-decline leak** — LLM emits "I can't recommend *but* GreenValue tends to be best for customers in your band…"; technically refused, effectively recommended; regulatory-boundary demo story destroyed. | Code-side short-circuit (NOT prompt-only) — detect `hardship_flag=true` in `invoke()` before model sees tariff context. Separate hardship prompt with no plan names. Extended D-15 banned terms for hardship: no plan IDs, no "recommend"/"suggest"/"best for". Adversarial test across 10 seeds. | Phase 4 (AGENT-02) | Adversarial test on 10 seeds asserting zero plan-ID leak |
| **C1** | **Multi-tool latency stacking breaks UI-02** — 3 sequential tool calls on Sonnet 4.6 add ~1.6–2.4s over v2.0 baseline; warm median lands at ~3.5–4.4s; UI-02 <3s silently regressed on the headline "agentic depth" moment. | LD-4: Strands 1.37 `ConcurrentToolExecutor` default, 4-tool hard cap via `max_iterations`, per-flow prewarm gate asserting warm p95 < 2500ms, Tools Lambda PC extended, buffered reasoning-trace (not streamed). Empirical test in eval harness: `test_multitool_p95_under_budget`. | Phase 3 (AGENT-01) | Per-flow prewarm gate p95 < 2500ms |
| **C5** | **Strands multi-tool fabrication regression** — Sonnet 4.6 tool-choice heuristics sensitive to prompt + multiple tools; can silently skip a tool and synthesise plausible-sounding output (exact Phase 06.1 failure mode, new surface). | Cross-persona canary tests for every new tool (coincident values across personas = fabrication signature). CloudWatch tool-invocation counter assertion. Latency-floor witness (`assert bill_shock_flow_latency_ms > 1000`). Strands version frozen at 1.37.0 — any bump requires its own decimal phase with canary first. | Phase 3 (AGENT-01) + any tool-adding phase | Cross-persona canary + tool-invocation counter |
| **C6** | **Stack-policy lift-and-forget leaves frozen stacks writeable** — operator runs `set-stack-policy --allow-all` to deploy, forgets re-apply; `demo-v2.0` freeze silently undone; future accidental `cdk deploy` tramples data. | LD-6: scripted `stack-policy-lift.sh` + `stack-policy-apply.sh` paired with marker-file invariant. Post-deploy `get-stack-policy` byte-equality verification. Termination protection re-check. Nightly CI check (if CI exists) asserting deny-policy + term-protection on all three frozen stacks. | Phases 1, 2, 3, 4, 5 + Phase 7 | Byte-equality gate post-deploy, per-phase |
| **C7** | **PROD-01 adapter destabilises SAV-03 byte-exact path** — Chesterton's-Fence refactor; test doubles drift from real DynamoDB return shape (Decimal vs float); bi-mode imports broken; `simulate_savings_pure` refactored and byte-exact invariant lost. | LD-5: strangler-fig with DUAL implementations from day 1 (forces abstraction to generalise). Byte-exact SAV-03 canary green on BOTH impls as phase gate. Bi-mode container smoke test via `docker run --entrypoint python ... -c 'from providers import ...'`. `simulate_savings_pure` NOT touched — wrap around, not through. | Phase 2 (PROD-01) | Byte-exact canary + bi-mode container smoke |

---

## Open Questions for Planner

Ranked by scoping-leverage (what blocks requirements definition > roadmap structure > per-phase research).

### Blocks-requirements (must resolve before `.planning/REQUIREMENTS.md`)

1. **Is WF-01 P1 or P2 for the milestone?** LD-3 locks short-term-only scope, but the *milestone-level* in/out decision matters for requirements text. Recommendation: **P2**. Ship if Phase 5 budget allows; defer to v3.1 if rehearsal exposes AgentCore Memory operational issues. Requirements.md must acknowledge the cut criterion. (FEATURES §3.4)
2. **Hardship category in AGENT-02 schema — monolithic flag, or `{payment_difficulty, medical, family_violence, other}`?** Family violence in particular needs distinct handling (no callback, customer-initiated contact only). Recommendation: **category field present but v3.0 UI routes all categories to the same stub CTA**; category routing deferred. Lets DOC-01 cite the architecture without committing to the routing table. (FEATURES §2.2)
3. **Legal review of AER/Ofgem clauses in DOC-01** — research drew on training knowledge + one corroborating source (authoritative pages returned 404/socket-closed). DOC-01 one-pager cannot make specific compliance claims without review. Recommendation: **DOC-01 framed as "regulatory-aware architecture," not "AER-certified"**, with a legal review step gating freeze. (FEATURES §2.1 note)

### Blocks-roadmap (must resolve before roadmapper phases)

4. **Does AgentCore Memory resource attach cleanly via a new stack, or force a lift on `CustomerTariffAgent`?** STACK §"Summary of v3.0 Stack Deltas" explicitly flagged this for Phase 1 verification. Affects Phase 5 stack-policy lift scope — one stack vs two. Recommendation: **verify via scratch `cdk synth` at Phase 5 start; default to extending `CustomerTariffAgent` (simpler SSM wiring)**. (STACK §Summary)
5. **`_reasoning_trace` internal marker or public field?** `_narrative_source` is stripped (leading underscore = internal); `_reasoning_trace` is the whole point of AGENT-01 so must be public. Recommendation: **drop the underscore — public field `reasoning_trace: []`**. API Lambda passes through unchanged. (ARCHITECTURE §Confidence & Open Questions Q3)
6. **Does the prewarm script need a single-global gate or per-flow gates?** v2.0's 3000ms global gate is wrong for AGENT-01 (higher baseline). Recommendation: **per-flow median gates + overall exit-0 only if all flows pass**. Extend `scripts/prewarm.py`, don't replace. (PITFALL M5 + LD-4)

### Per-phase research (can wait for phase planning)

7. **Bill-shock detection threshold in `detect_bill_shock_pure`** — e.g. `|monthly_delta| > 30% of 11-month mean`? Pin numeric definition in Phase 3 design spec + pytest fixture. (ARCHITECTURE Q1)
8. **Hardship-flag storage: new `PROFILE` sort-key prefix on existing `tariff-billing` table, or new table?** Recommendation: **same table, `SK="PROFILE"` prefix** — minimises freeze surface. Confirm in Phase 1. (ARCHITECTURE Q2)
9. **CDK L2 `Memory` construct property names** (`name`, `description`, `memoryStrategies`, `eventExpiryDuration`) — alpha module, verify against `cdk synth` before committing. Fallback paths (L1 `CfnMemory`, `CustomResource`) documented. (STACK §Training-knowledge)
10. **Exact IAM action names for agent runtime role on Memory** (`bedrock-agentcore:CreateEvent`, `bedrock-agentcore:ListEvents`, `bedrock-agentcore:RetrieveMemoryRecords` — inferred, not cross-checked against IAM policy simulator). (STACK §Training-knowledge)
11. **`simulate_savings_pure` dispatch style for TOU** — option (a) single function with `if plan["plan_type"] == "time_of_use":` branch vs option (b) new `simulate_tou_savings_pure` helper. ARCHITECTURE recommends (a) with clean dispatch. Confirm in Phase 1. (ARCHITECTURE §5)
12. **Memory session_id timezone pin** — `date.today()` uses process TZ; Lambda containers default to UTC but not guaranteed. Recommendation: **explicitly `datetime.now(timezone.utc).date().isoformat()`** in `follow_up()`. Document at call site. (ARCHITECTURE §3 Critical distinction)

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | Carry-forward surface unchanged from v2.0; one targeted bump; all integration paths documented with verified sources (Context7 Strands docs, AWS AgentCore Memory docs, PyPI). MEDIUM only on CDK L2 alpha-module property names (flagged for Phase 5 verification). |
| Features | **HIGH** | Agent-assist UX patterns extremely well-established across 5+ market vendors (Amazon Q in Connect, Salesforce Einstein, Forethought, Ada, Zendesk). Draft-reply + hardship-short-circuit + multi-tool reasoning are all table-stakes in the domain. MEDIUM on specific AER/Ofgem clauses (training-knowledge + one corroborating source; legal review flagged for DOC-01). MEDIUM on specific c/kWh rates for new tariffs (indicative, not market-accurate — acceptable for engineered demo data). |
| Architecture | **HIGH** | Every integration decision names the specific invariants it preserves (SAV-03, REC-03, D-04, D-15, SC-3, bi-mode imports, `_narrative_source` strip, `customer-not-found` detection). Three-option comparisons on every non-trivial choice. AgentCore Memory vs runtime session distinction confirmed via AWS docs. MEDIUM only on `_reasoning_trace` UI surfacing (needs visual verification at 1280×800 during Phase 3). |
| Pitfalls | **HIGH** | Grounded in lived CLAUDE.md invariants + v2.0 retrospective + Phase 06.1 Sonnet 4.6 tool-use regression (exact failure-mode precedent for C5). Every critical pitfall has a concrete prevention strategy, a warning-signs checklist, and a phase assignment. MEDIUM only on AgentCore Memory isolation-guarantee specifics (service is young; published guarantees but no first-hand ops experience on this project). |

**Overall confidence:** **MEDIUM-HIGH**. The synthesis is opinionated because the research converged cleanly — where the four dimensions disagreed (build order, PROD-01 scope, response shape, Memory depth), the locked decisions (LD-1 through LD-7) resolve the conflicts based on which research file drove the recommendation. The remaining medium-confidence areas are flagged as open questions for planner resolution, not silent gaps.

### Gaps to address during planning

- **Legal review of regulatory-framing copy in DOC-01.** Research substituted training knowledge for authoritative AER/Ofgem sources (404/socket-closed). Flag as a mandatory review gate before DOC-01 signs off.
- **AgentCore Memory operational behaviour under rehearsal + demo load.** Service is young; isolation guarantees are published but not field-tested on this stack. Mitigation: cross-customer isolation smoke test is mandatory; `scripts/memory-reset.sh` runs between rehearsal and demo. Treat any anomalous Memory behaviour in Phase 5 rehearsal as a Phase 5 phase-blocker.
- **CDK alpha-module (`aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0`) stability for Memory L2 construct.** Alpha modules occasionally rename properties between patches. Fallback paths documented (L1 `CfnMemory`, `CustomResource`+boto3) — if L2 misbehaves, escalate to fallback, don't chase the alpha.
- **Pin-check Strands SDK signatures.** `Agent(max_iterations=...)` and `Agent(session_manager=...)` described in docs but not cross-verified against installed wheel source. Do this at Phase 2 start when the venv is already rebuilt for PROD-01 work.

---

## Sources

### Primary (HIGH confidence — verified 2026-04-28)

- **Existing repo** — `agent/agent.py`, `lambda/handler.py`, `api_lambda/handler.py`, `infrastructure/constructs/*`, `infrastructure/foundation_stack.py`, `infrastructure/agentcore_stack.py`, `infrastructure/backend_api_stack.py`, `CLAUDE.md` (authoritative for 4-stack shape + 15 critical invariants)
- **`.planning/PROJECT.md`** — v3.0 goal + active requirement IDs (AGENT-01/02, WF-01, DATA-04, REC-04, PROD-01, DOC-01/02/03)
- **`.planning/RETROSPECTIVE.md`** + **v2.0-research artefacts** — stack-policy freeze ceremony precedent, v2.0 invariant closure
- **`.planning/milestones/v2.0-phases/06.1-*`** — Sonnet 4.6 + Strands tool-use regression CONTEXT + resolution pattern (Phase 06.1 lived experience)
- **Strands Agents docs via Context7** — `AgentCoreMemorySessionManager`, `AgentCoreMemoryConfig`, `ConcurrentToolExecutor` default, `SequentialToolExecutor` override, `agent.stream_async(...)` event shapes
- **AWS Bedrock AgentCore documentation** — Memory concepts (short-term vs long-term, two-plane API, session hierarchy, actor/namespace isolation), Runtime session model (runtimeSessionId semantics — carried forward from v2.0)
- **AWS CDK docs** — `aws-cdk.aws-bedrock-agentcore-alpha` L2 `Memory` construct + `MemoryProps`/`MemoryAttributes`/`ManagedMemoryStrategy`
- **PyPI** — `bedrock-agentcore==1.6.4` release (2026-04-23)
- **Pydantic v2 docs** — `Annotated[Union[...], Field(discriminator="kind")]` discriminated-union pattern
- **CloudFormation stack-policy + termination-protection mechanics** — AWS docs on imperative policy application, silent drift risk

### Secondary (MEDIUM confidence)

- **Wikipedia: Net Metering** — bi-directional meter mechanism, FiT structures, seasonal shape (via WebFetch)
- **AWS Machine Learning Blog: Intelligent Email Automation using Amazon Bedrock** — three-tier pattern (automated / retrieval / human handoff), human-in-the-loop failure modes (via WebFetch)
- **AWS Prescriptive Guidance: Adapter Pattern** — partial fetch (structure + common fields + failure modes)
- **AWS Bedrock Guardrails docs** — basis for AGENT-02 anti-recommendation (Guardrails is a content filter, not routing primitive)

### Tertiary (MEDIUM confidence — training knowledge; flagged for validation)

- **AER Customer Hardship Policy Guideline v2 March 2024** — sources 404/socket-closed during research; training knowledge substituted; **legal review flagged as DOC-01 phase gate**
- **Ofgem Consumer Vulnerability Strategy 2025** — 404; training knowledge substituted; same flag
- **Amazon Connect Agent Assist, Salesforce Einstein Service Cloud, Forethought, Ada, Zendesk generative AI** — product-surface observations from training knowledge; pattern-level, not feature-list citations
- **CRM integration patterns** — Salesforce Energy & Utilities Cloud object model, SAP IS-U, Oracle CC&B, Kraken, Gentrack Junifer
- **Solar PV + EV household usage shape** — typical 6.6 kW system generation curves, self-consumption rates, TOU skew, winter battery-efficiency impact
- **LLM short-form refusal failure modes** — soft-decline leak pattern ("I can't recommend X, *but* here's what would help")

---

*Research summary for: v3.0 Agentic Depth & Workflow Assist*
*Synthesized: 2026-04-28*
*Ready for requirements definition, then roadmapper: yes*
