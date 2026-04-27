# Domain Pitfalls — v3.0 Agentic Depth & Workflow Assist

**Domain:** Adding multi-tool agentic reasoning, hardship short-circuit, AgentCore Memory, new personas + tariff archetype, `CustomerDataProvider` adapter, and presenter artefacts to a **frozen Bedrock AgentCore demo** (Strands SDK + Claude Sonnet 4.6 + Lambda + API Gateway + DynamoDB + React/Vite) carrying 15 critical invariants from v1.0/v2.0 that must NOT break.
**Researched:** 2026-04-28
**Confidence:** HIGH on pitfalls grounded in CLAUDE.md invariants and Phase 06.1 / v2.0 retrospective (these are lived-experience failure modes on this exact system). MEDIUM on AgentCore Memory specifics — the Memory surface is new; isolation guarantees are published but this project has no first-hand ops experience with it yet. HIGH on adapter-refactor, stack-policy, and seed-data-drift pitfalls — each is directly observable in the repo today.

> **How this relates to v1.0 / v2.0:**
> v1.0's `PITFALLS.md` covered foundational risks (model access, agent preparation, Lambda resource policies, savings coherence, session bleed, region lock). v2.0's `PITFALLS.md` covered the narrative + freeze surface (number hallucination, length drift, latency stacking, pre-warm, browser cache, AgentCore 15-min idle, rollback). **All of those are shipped and locked inside `demo-v2.0`.**
>
> This document covers ONLY the *new* risk surface introduced by v3.0 features, **with particular focus on integration pitfalls where v3.0 behaviour collides with a pre-existing invariant** (e.g. how a regulatory short-circuit interacts with `customer-not-found detection`; how AgentCore Memory interacts with the `runtimeSessionId` placement rule).
>
> **Freeze posture is different for v3.0.** The three original stacks (`CustomerTariff`, `CustomerTariffAgent`, `CustomerTariffApi`) are under `deny-Update:*` CFN stack policies + termination protection. Seed-data and schema changes require lifting the policy, deploying, and re-applying. Any v3.0 pitfall that touches a frozen stack is escalated — ceremony, not just code.

---

## Critical Pitfalls

Mistakes that either (a) break a locked v1.0/v2.0 invariant, (b) leak customer context across sessions, or (c) silently violate the demo's autonomy promise.

---

### Pitfall C1: Multi-tool latency stacking pushes warm median past UI-02 (<3s) 🟥 PRE-FREEZE

**What goes wrong:** AGENT-01 adds a second persona flow (bill-shock) that exercises 2–3 tools in one agent turn (e.g. `fetch_bill`, `detect_anomaly`, `simulate_savings`). Each additional tool call adds: **model turn token cost** (the model emits a tool-use block, reads the tool-result block, and re-reasons) + **tool execution latency** (Lambda invoke ~400-900ms cold, 50-200ms warm for the existing Tools Lambda) + **output-token cost** (the final JSON is longer). Sonnet 4.6 typical tool-use overhead is ~800-1200ms *per additional tool turn* once input/output tokens + model "think" time is totalled. Three tools in one turn = roughly **+1.6-2.4s vs the single-tool v2.0 baseline**. v2.0 warm median was ≲2s; v3.0 with three tools lands at **~3.5-4.4s warm median** — a silent UI-02 regression.

**Why it happens:** "Multi-tool flow" sounds orthogonal to latency, but Bedrock AgentCore + Strands runs tool turns *sequentially* by default (model → tool → model → tool → model → final). Each turn is a full round-trip to Bedrock + a round-trip to the tool. There is no built-in parallelism. Teams adding multi-tool patterns underestimate this because they think of "one agent call" rather than N+1 model round-trips.

**Consequences:** UI-02 regression on a feature that the v3.0 story *depends* on visibly showing agentic reasoning. Worse: the second persona flow is the headline "agentic depth" moment — if it's also the slow moment, the whole narrative inverts ("look at the agent reason… [4 seconds of spinner]…").

**Prevention:**
- **Empirical latency budget per tool, measured pre-freeze.** In the eval harness (reuse `tests/test_narrative_eval_live.py` scaffold), add a **smoke-gated** `test_multitool_p95_under_budget` that invokes the bill-shock flow 10× warm and asserts `p95 < 2500ms`. 500ms headroom against UI-02.
- **Parallelise tools where the call graph allows.** If two tools are independent (e.g. `fetch_bill` + `fetch_weather_for_region`), use Strands' parallel tool-use if available on Sonnet 4.6, or expose a single *compound* tool (`fetch_bill_with_context`) that does the parallel fan-out inside one Lambda. Avoid sequential chains of independent fetches.
- **Bound total tool turns** — the system prompt should explicitly say "you may call at most 3 tools per user turn". Without this, some prompts induce ReAct-style over-planning where the model calls the same tool twice or adds a self-check tool turn.
- **Tool-result payload size discipline.** Every extra KB of tool output = extra input tokens next turn = latency. Strip fields from Lambda responses that the model doesn't need (e.g. the full 12-month billing array when the model just needs the anomaly month).
- **Pre-warm the new bill-shock path specifically.** v2.0's `scripts/prewarm.py` warms `/recommendations/{cust}`. v3.0's new flow is a different code path — it needs its own warm-up call or a multi-persona warm that covers both single-tool and multi-tool flows. Copy `prewarm.py` rather than extending it; the 3000ms median gate is wrong for a multi-tool path (the gate should be persona-flow-specific).

**Warning signs (planner should detect early):**
- Plan for AGENT-01 proposes >3 sequential tools in one turn with no parallelism rationale.
- No eval-harness test added that asserts a per-flow latency budget.
- The plan reuses v2.0's single-persona warm-up without adding bill-shock coverage.
- CloudWatch Bedrock metrics during plan execution show per-invocation duration >2000ms on warm calls. Action: halt and re-scope.

**Phase:** AGENT-01 Lambda/agent integration phase. Latency budget must be proven before the phase closes, not at demo T-24h.

---

### Pitfall C2: Hardship short-circuit returns empty tracks → `customer-not-found` false-positive 🟥 PRE-FREEZE

**What goes wrong:** AGENT-02 says "when `hardship_flag` is set, the agent refuses to recommend a tariff and routes to hardship workflow stub". Naive implementation: agent returns `{"hardship": true, "workflow_ref": "HSP-001"}` — no `green`, no `cheapest`. In `api_lambda/handler.py:152` the customer-not-found detection is literally `if "green" not in body or "cheapest" not in body: return 404`. The hardship response **trips the 404 branch**. UI shows "customer not found". Hardship routing invisible.

**Why it happens:** The `customer-not-found` invariant (CLAUDE.md) was designed in v1.0 when the agent's *only* failure mode was tool-call failure (which produced `{"errorMessage": "..."}` with no tracks). REC-03 locks "both tracks always returned". A new legitimate case of "no tracks" (hardship) wasn't in the original domain model. Discriminated-union responses are a clean fix — but they require coordinated changes across Pydantic (`RecommendationResponse`), API Lambda (detection), and the UI.

**Consequences:** Hardship customers (a flagship v3.0 regulatory-trust story) render as 404 errors. Or, if detection is patched incorrectly, tariff customers get misrouted into hardship workflow. Either way the short-circuit doesn't do the thing it was built to demonstrate — and the demo claims "regulatory autonomy boundary" that doesn't exist on screen.

**Prevention:**
- **Design the response as a discriminated union up front.** Two response variants: `TariffRecommendation { kind: "tariff", green, cheapest }` and `HardshipRoute { kind: "hardship", workflow_ref, rationale_line }`. Pydantic `Union` with `Field(discriminator='kind')`.
- **Update the customer-not-found detection to key on `kind`, not on `green`/`cheapest` presence.** Specifically: `not_found = "kind" not in body and "green" not in body and "cheapest" not in body` (preserves backwards compatibility with the v1.0 tool-failure `{"errorMessage"}` shape). Then: `is_tariff = body.get("kind") == "tariff"`, `is_hardship = body.get("kind") == "hardship"`.
- **REC-03 must be updated in the system prompt.** The current prompt forbids saying "one plan is better than the other"; it also implicitly expects both tracks. Amend: "When `hardship_flag` is true, emit the hardship variant; do NOT emit `green` or `cheapest`. When `hardship_flag` is false, emit both tracks as always (REC-03 unchanged)."
- **Test both branches in offline pytest.** (a) hardship persona → assert response has `kind=="hardship"` and no green/cheapest. (b) normal persona → assert response has both tracks, no `kind` field (or `kind=="tariff"`). (c) API Lambda: hardship response → 200 OK with hardship body, not 404.
- **Add a live smoke test** that invokes a hardship persona via the API and asserts the UI-visible response is the hardship route, not 404.

**Warning signs:**
- Plan proposes adding a `hardship_flag` field to `RecommendationResponse` rather than a discriminated union — this is the "retrofit not refactor" signal. It fails, because the Pydantic validator that makes `green` + `cheapest` required still fires.
- Plan does not touch `api_lambda/handler.py:152`. 100% certain this is broken.
- Plan does not update the system prompt's REC-03 language.
- Plan has one test case for hardship but not one for "normal tariff response still works after the schema refactor" (the regression surface).

**Phase:** AGENT-02 planning + implementation phase. The discriminated-union schema decision is a pre-plan D-decision; skipping it guarantees rework.

---

### Pitfall C3: Hardship short-circuit soft-declines and leaks a recommendation anyway 🟥 PRE-FREEZE

**What goes wrong:** The agent receives a hardship customer. The system prompt says "refuse to recommend a tariff". The model, trained to be helpful, emits: *"I can't recommend a specific plan given your hardship status — **but the GreenValue plan tends to be best for customers in your usage band**, I suggest the agent discusses that."* Technically it refused. Effectively it recommended. The autonomy-boundary demo goal is dead.

**Why it happens:** Soft declines are the most common LLM refusal failure mode. Instruction-tuned models (Claude included) optimise for "provide useful information" and route around hard refusals by hedging. "I can't recommend X but here's information that could help you think about X" is the canonical leak pattern. Pydantic schemas do not enforce semantic refusal — only shape.

**Consequences:** The flagship v3.0 regulatory-trust talking point is undermined by its own implementation. Worse: on a live demo, an audience member catches the leak and the trust-architecture story (DOC-01) looks aspirational rather than delivered.

**Prevention:**
- **Code-side short-circuit, NOT prompt-side.** Detect `hardship_flag == true` in the Python code path (either in a pre-tool guard or in `_narrative_source` equivalent logic) BEFORE the model is invoked with the full recommendation prompt. Return the hardship response *without calling the model for tariff reasoning*. The agent may be called for the hardship narrative — but it never sees tariff context in that branch.
- **If the agent must be involved for the hardship narrative, use a different system prompt.** The hardship prompt should contain: (a) no tariff plan data, (b) no usage-band shape tokens that imply tariff suitability, (c) an explicit "the customer's tariff suitability is NOT to be discussed — you are writing a handoff note only". Input shape discipline: the model cannot recommend a plan it does not know exists.
- **Extend the D-15 narrative gauntlet** with hardship-specific banned terms: no plan names, no `GreenValue` / `Value12` / any tariff ID, no "recommend", no "suggest", no "best for". Apply to `usage_narrative` and `call_script` in the hardship branch.
- **Regression test:** seed a hardship persona with deliberately tempting shape tokens (e.g. high usage + seasonal pattern that normally maps to GreenValue) and assert the response (a) has `kind="hardship"`, (b) contains no tariff plan ID in any string field, (c) contains no banned recommend-verbs.
- **Add an adversarial test** that runs hardship personas 10× with diverse seeds; fail if any run leaks a plan ID or recommend-verb. This is a **cheap-to-run regression gate** that catches model-behaviour drift over Bedrock model rotations (see M9 from v2.0 which carries forward).

**Warning signs:**
- Plan relies on the system prompt alone to enforce the refusal. System prompts are suggestions, not contracts — same logic as SAV-03 (the arithmetic gate is code, not prompt; the hardship boundary must be code, not prompt).
- Plan includes tariff data in the hardship path "in case the model needs context". It doesn't; context is the leak vector.
- Plan adds only happy-path hardship tests, no adversarial tests.

**Phase:** AGENT-02 planning phase — commit to code-side short-circuit as a D-decision. Implementation phase — write the adversarial tests before wiring the prompt.

---

### Pitfall C4: AgentCore Memory retains customer context across `runtimeSessionId` rotations 🟥 PRE-FREEZE

**What goes wrong:** WF-01 adds "draft follow-up email" — a second agent turn referencing the first turn's recommendation. To make this work, the team introduces AgentCore Memory. The current invariant says `runtimeSessionId` is **generated inside `handler()`**, per-request, so there is NO cross-request session bleed (CLAUDE.md / Pitfall 2 / SC-3). AgentCore Memory operates at a *higher scope* — it's keyed on an `actorId` + `memoryId`, not the `runtimeSessionId`. If WF-01 uses a fixed `actorId` (e.g. `"demo-rep"`) or derives it from the rep's identity without also scoping to the customer, **Memory persists customer-A's usage profile and becomes context on customer-B's follow-up email request**. Sarah Chen's "large-family high-usage" pattern appears in Marcus Webb's draft email.

**Why it happens:** The `runtimeSessionId`-per-request invariant solved one layer (the Bedrock invocation session). AgentCore Memory is a different layer that operates across sessions by design — that's its *purpose*. Teams porting the "new session per request" discipline to Memory assume Memory inherits the isolation, but Memory's isolation unit is the `actorId` + namespace, not the `runtimeSessionId`. Namespaces are typically configured as templates like `/strategies/{strategyId}/actors/{actorId}` — if `{actorId}` isn't customer-scoped, customers share a namespace.

**Consequences:** **Cross-customer PII leak on stage.** A hostile outcome for a demo that positions itself as trust-first. On a call-centre demo, this is the single most catastrophic failure mode — one audience member noticing "wait, did the draft email just reference another customer's child?" vapourises the deal.

**Prevention:**
- **Scope `actorId` to the customer_id, not the rep.** `actor_id = f"customer:{customer_id}"`. One Memory actor per customer. Cross-customer bleed becomes structurally impossible.
- **TTL everything short.** For a demo with 3-5 personas and a ~45-minute presentation window, set Memory event retention to hours, not days. No reason to accumulate.
- **No customer free-text into Memory.** Same rule as Pitfall C2 from v2.0 (prompt injection). Memory entries should be shape tokens (`usage_band`, `plan_code`) not names, addresses, or notes. If the rep workflow needs a name in the email body, render it client-side from the persona fetch (as v2.0 established for UI-03), do not round-trip it through Memory.
- **Test cross-customer isolation explicitly.** Live smoke: (a) invoke recommendation for CUST-001. (b) invoke follow-up email draft for CUST-002 in the same process/session. (c) assert the CUST-002 email body contains zero CUST-001 persona attributes (name tokens, usage tokens, plan tokens). Run this offline with mocked Memory first, then live.
- **Pre-demo cleanup command.** Add a script (or Make target) `scripts/memory-reset.sh` that wipes AgentCore Memory for all demo actor IDs. Run at T-2h per updated DEMO-RUNBOOK. Prevents cross-rehearsal bleed polluting the live run.
- **Monitoring during rehearsal:** log every Memory read/write with `actor_id` + `session_id`. Grep the logs after rehearsal for "actor_id=customer:CUST-001" appearing in a response served for CUST-002.

**Warning signs:**
- WF-01 plan uses a constant/module-level `actorId`. Guaranteed bleed.
- WF-01 plan derives `actorId` from rep identity alone. Also bleed (one rep serves many customers).
- Plan does not include a cross-customer isolation test in the VALIDATION section.
- Plan does not include a pre-rehearsal Memory-reset step.

**Phase:** WF-01 research + planning phase. The `actorId` scoping decision is a D-decision that must be committed before any Memory API calls are wired.

---

### Pitfall C5: Strands multi-tool regression recurs on Sonnet 4.6 (Phase 06.1 precedent) 🟥 PRE-FREEZE

**What goes wrong:** v2.0 Phase 06.1 resolved a Claude Sonnet 4.6 + Strands `structured_output` regression where the model silently *fabricated* tool-output numbers instead of actually calling `simulate_savings`. The fix was migrating to the `Agent.structured_output_model` constructor API. v3.0 adds 2-3 new tools. **Every new tool is a fresh surface for the same failure mode** — Sonnet 4.6's tool-choice heuristics are sensitive to prompt construction, tool-spec naming, and the interaction between multiple tools. A plausible regression: with multiple available tools, the model calls `simulate_savings` correctly but skips `fetch_bill_anomaly` and synthesises a plausible-sounding anomaly string from context.

**Why it happens:** Strands + AgentCore + Sonnet 4.6 tool-use has a complex contract (tool_spec generation, tool_result formatting, discriminated-output wiring). Phase 06.1's resolution was API-version-specific (Strands 1.37.0+). Any Strands version bump OR any change to the model inference profile OR any change to tool-spec naming can regress. The "silent fabrication" failure mode is pernicious because the response schema validates — nothing raises.

**Consequences:** Savings math regression (SAV-03 violation — LLM doing arithmetic again), or bill-shock anomaly is hallucinated instead of tool-fetched, or the hardship flag is fabricated off the usage band. Any of these is fatal if unnoticed. The v2.0 fix was caught only because a *cross-persona canary test* (Sarah $30/$55 vs Marcus $16.90/$30.98) showed coincident $18.50/$30.00 pairs — the fabrication signature.

**Prevention:**
- **Cross-persona canary tests for every new tool.** For each new tool (bill-shock anomaly detector, hardship classifier if implemented, etc.), write a test that invokes the flow across 3+ personas and asserts the tool-emitted values are *distinct per persona*. Coincident values across personas = fabrication signature.
- **CloudWatch tool-invocation counters.** Emit a structured log entry on every tool call: `{"tool_called": "<name>", "customer_id": "...", "latency_ms": N}`. Before declaring a phase done, grep logs for the smoke test run and count tool invocations; assert N tools × M invocations expected.
- **Latency floor as tool-invocation witness.** A tool call that round-trips to Lambda takes ≥400ms. If per-invocation total latency drops below ~600ms with a multi-tool flow expected, the tool wasn't called — fabrication likely. Add as a smoke assertion, e.g. `assert bill_shock_flow_latency_ms > 1000` (two tools × Lambda round-trip baseline).
- **Pin the Sonnet 4.6 inference profile** as CLAUDE.md does today (`us.anthropic.claude-sonnet-4-6` — model literal at `agent/agent.py:309`). Do NOT let a v3.0 plan "upgrade to the latest" without running the full canary suite.
- **Run canary tests post-deploy, not pre-deploy only.** The Phase 06.1 failure was invisible locally (mocked agent) and only surfaced on the deployed runtime. Live smoke is mandatory.
- **If adding a new tool, add it in isolation first** (tool + single-persona canary + cross-persona canary) BEFORE wiring it into a multi-tool flow. Debugging a multi-tool fabrication is much harder than a single-tool fabrication.

**Warning signs:**
- Plan has no cross-persona canary test. Reading this out loud should be uncomfortable.
- Plan relies on mocked-agent offline tests only. They cannot catch fabrication on the deployed runtime.
- Plan proposes a Strands version bump "while we're in the agent file". Refuse until canary passes on new version.
- CloudWatch logs for a smoke run show zero `ToolUse` events but the response contains what look like tool-emitted values. Immediate halt.

**Phase:** AGENT-01 (bill-shock multi-tool flow) planning + implementation. Also WF-01 if WF-01 introduces a tool (e.g. `load_previous_recommendation`).

---

### Pitfall C6: Stack-policy lift-and-forget leaves frozen stacks writeable 🟥 PRE-FREEZE / 🟨 DURING DEPLOY

**What goes wrong:** DATA-04 / REC-04 requires seeding 2 new personas and a new tariff archetype into DynamoDB. The `CustomerTariff` stack (foundation — DynamoDB + seeder custom resource + Tools Lambda) is frozen with a `deny-Update:*` stack policy and termination protection. To deploy the update, the operator runs `aws cloudformation set-stack-policy --stack-name CustomerTariff --stack-policy-body file://allow-all.json`, deploys, then is supposed to re-apply the deny-policy. **Common failure: forget to re-apply.** The stack is now silently writeable. A bad `cdk deploy` weeks later (or a `--force` someone else types) tramples the DynamoDB table or the Tools Lambda asset bundle. The `demo-v2.0` freeze is effectively undone without anyone noticing.

**Why it happens:** Stack policies are set via an API call that's visually tiny — a single `set-stack-policy` invocation with a JSON body. There's no CDK-native linkage (CDK doesn't track stack policies in the synth output). Humans forget invisible state. The retro (`.planning/RETROSPECTIVE.md`) already notes three `AWS_PROFILE=cevo-25` (wrong) vs `cevo-dev25` (right) incidents — stack-policy state management has the same invisible-state character.

**Consequences:** Frozen stacks aren't actually frozen after the v3.0 deploy. A post-v3.0 accident can damage the demo's DynamoDB table (including the v1.0/v2.0 persona data the demo depends on). Termination protection is a separate control (slightly safer), but updates still go through.

**Prevention:**
- **Scripted lift-and-reapply.** `scripts/stack-policy-lift.sh <stack>` and `scripts/stack-policy-apply.sh <stack>` that pair cleanly. `lift` writes a marker file `/tmp/stack-policy-lifted-<stack>` to signal pending re-apply. `apply` refuses unless the marker exists (catches "apply without lift" and "lift without apply").
- **Lift only the one stack that needs it.** DATA-04 / REC-04 needs `CustomerTariff` only. Do NOT lift `CustomerTariffAgent` or `CustomerTariffApi` as a precaution — doing so expands the blast radius for no gain. If the plan needs multiple stacks unfrozen, it should be split.
- **Verification step after re-apply.** `aws cloudformation get-stack-policy --stack-name CustomerTariff` and assert the returned body equals the expected deny-Update:* JSON (byte-equal). Add to the phase's VALIDATION.
- **Termination protection re-check.** Separate control, separate verification: `aws cloudformation describe-stacks --stack-name CustomerTariff --query 'Stacks[0].EnableTerminationProtection'` == `True`. Script it.
- **Add a nightly CI check (if CI exists) or a pre-v3.0-demo check:** iterate over the 3 frozen stacks and assert each has (a) termination protection ON, (b) deny-Update:* stack policy present. Catches drift.
- **Commit both policy bodies to `infrastructure/stack-policies/`** (CLAUDE.md says they already live there). The lift-script uses the `allow-all` body; the apply-script uses the `deny-update` body. Bodies are source-controlled; policy application is auditable.

**Warning signs:**
- Plan says "lift stack policies" (plural) without naming exactly one stack and exactly one reason.
- Plan does not include a re-apply + verification step as a mandatory gate.
- Operator runs the lift interactively without using the scripted lift-and-reapply helper.
- Post-deploy `get-stack-policy` output differs from the source-controlled deny-policy body.

**Phase:** DATA-04 / REC-04 execution phase. The lift-and-reapply is a ceremony, not a deploy step — treat it like the v2.0 freeze ceremony (Phase 10), not like a normal `cdk deploy`.

---

### Pitfall C7: `CustomerDataProvider` adapter refactor destabilises the happy path (Chesterton's Fence) 🟥 PRE-FREEZE

**What goes wrong:** PROD-01 introduces a `CustomerDataProvider` Protocol/ABC with a DynamoDB demo implementation, "production-shaped for a real CRM swap". The refactor changes how Tools Lambda fetches billing records — previously a direct boto3 DynamoDB call, now through an adapter interface. Seemingly harmless, but:
- **Test doubles drift from the real thing.** Offline tests mock `CustomerDataProvider`. The mock returns `List[BillingRecord]` dataclasses. The DynamoDB impl returns dicts with Decimal-typed fields. `simulate_savings_pure` was written against dicts. Offline tests pass; deployed code returns TypeError on the Decimal arithmetic.
- **Bi-mode import pattern (CLAUDE.md) is violated.** `agent/agent.py` has the bi-mode `narrative.X` vs `agent.narrative.X` import pattern because `agent/` gets COPYed flat into the container. The adapter Protocol, if placed at `agent/providers/provider.py`, needs the same bi-mode treatment. Easy to miss; container import fails at deploy.
- **The abstraction *was* the point.** The direct DynamoDB call is simple, typed, tested, and has a locked byte-exact savings contract. Wrapping it in a Protocol doesn't remove the DynamoDB code — it adds layers. If the abstraction doesn't *actually* let a second implementation land (in v3.0 or v3.1), it's pure overhead. Chesterton's Fence: the direct call was working; wrapping it costs cognitive load and code paths.

**Why it happens:** "CRM-shaped adapter" sounds architecturally important, and it *is* on the deferred roadmap for PROD-02. But PROD-01 (per PROJECT.md scope) is *partial* — DynamoDB demo implementation only, no real CRM swap. The adapter is speculative — the canonical sign of a Chesterton's Fence risk on shipped code.

**Consequences:** Either (a) the refactor breaks the DEMO-02 byte-exact savings invariant during execution and must be reverted mid-phase, or (b) the refactor ships but adds a layer that nobody else needs, slowing v3.1/PROD-02 planning because the "right" abstraction wasn't visible until a second implementation existed.

**Prevention:**
- **Strangler-fig, not big-bang.** Keep the existing DynamoDB call intact. Introduce `CustomerDataProvider` with two implementations from day one: (a) `DynamoDBCustomerDataProvider` delegating to the existing code verbatim, (b) `InMemoryCustomerDataProvider` seeded from `tests/conftest.py` fixtures. Two implementations force the abstraction to actually generalise — if it doesn't accommodate both cleanly, the shape is wrong *before* it ships.
- **Byte-exact savings regression gate.** Run `test_sarah/marcus/elena_flagship_values` against both providers on every commit in this phase. If the DynamoDB provider breaks the flagship deltas (SAV-03 / DEMO-02), the refactor is wrong. Non-negotiable.
- **Honour the bi-mode import pattern.** Any new module placed under `agent/` needs the `try: from X import ... except ImportError: from agent.X import ...` dance. Test container imports locally with the pre-deploy gate from Phase 06.1 D-10: `docker run --rm --entrypoint python <image> -c 'from providers.customer import CustomerDataProvider; print("OK")'`. Catches module-layout bugs in <1 second.
- **Keep the adapter shallow.** Two methods: `fetch_billing_records(customer_id) -> List[BillingRecord]` and `fetch_customer_profile(customer_id) -> CustomerProfile`. No generic "run-a-query" surface. The narrower the Protocol, the less surface area for mock-vs-real drift.
- **Type the return dataclass, not just the Protocol.** `BillingRecord` and `CustomerProfile` are dataclasses with explicit types (e.g. `Decimal` for dollars, not `float`). The DynamoDB impl converts at the boundary; the mock impl builds dataclasses directly; `simulate_savings_pure` receives well-typed input either way.
- **Do not refactor `simulate_savings_pure`.** The SAV-03 contract lives inside that function. Wrap around it, not through it. If the refactor touches `lambda/handler.py::simulate_savings_pure` at all, a stop-and-review.

**Warning signs:**
- Plan refactors `simulate_savings_pure` as part of PROD-01 scope. Stop — that function is the SAV-03 byte-exact math; refactoring it is a different, larger phase.
- Plan has one adapter implementation. Either add a second at design time, or defer PROD-01 to when PROD-02 needs it (the real test of the abstraction).
- Plan does not test container imports with the pre-deploy gate. Bi-mode import bugs will surface at `cdk deploy`, which is the expensive way to find them.
- Tests use one set of fixtures for offline and a different set for live smoke. Mock-vs-real drift waiting to happen.

**Phase:** PROD-01 planning (D-decision on strangler-fig + dual-implementation) + implementation. Byte-exact DEMO-02 gate is mandatory across every commit.

---

## Moderate Pitfalls

---

### Pitfall M1: Seed-data drift between `lambda/tariff_plans.json` and `infrastructure/seed_data/tariff_plans.json` 🟥 PRE-FREEZE

**What goes wrong:** REC-04 introduces at least one new tariff archetype matching the solar/EV personas. The tariff catalog is **duplicated** (CLAUDE.md): `lambda/tariff_plans.json` (bundled into the Tools Lambda asset) and `infrastructure/seed_data/tariff_plans.json` (used by the seeder + referenced elsewhere). The plan updates one file but not the other. `tests/conftest.py` treats `lambda/tariff_plans.json` as source of truth — tests pass. But the deployed Lambda (which imports from `lambda/tariff_plans.json`, correct) and the live DynamoDB seed (which came from `infrastructure/seed_data/tariff_plans.json`, stale) now disagree on the archetype's rate values. Savings math produces nonsense on the new personas.

**Why it happens:** Duplicated source-of-truth files are a classic v1 shortcut that accumulates interest in v2+. The duplication is historical — the Lambda needs the file bundled, and the seeder needed a separate copy for CDK asset isolation. The fix is either (a) a single canonical file + symlink / build-time copy, or (b) a test that asserts byte-equality between the two files.

**Consequences:** New personas (solar/EV) produce wrong savings deltas. Either the demo engineers the *wrong* numbers (and the mismatch between the two files is invisible until you look at the live table), or the regression is caught late at a live smoke and forces a re-deploy of the frozen `CustomerTariff` stack — triggering Pitfall C6 (stack policy lift).

**Prevention:**
- **Add a pytest that asserts byte-equality** (or structural equality if dict ordering is an issue) between `lambda/tariff_plans.json` and `infrastructure/seed_data/tariff_plans.json`. Run in offline suite. Fails CI on any drift.
- **REC-04 plan updates BOTH files in the same commit.** Review gate on the plan: if the commit touches one path, it touches the other.
- **Document the canonical-source choice.** CLAUDE.md already says `lambda/tariff_plans.json` is source of truth for `tests/conftest.py`. Extend: "When adding tariff plans, update `lambda/tariff_plans.json` first, then `cp` to `infrastructure/seed_data/`." Mechanical discipline.
- **Consider consolidating.** If Phase scope allows, update `infrastructure/foundation_stack.py` to read `lambda/tariff_plans.json` as the seeder source too, eliminating the duplication. This is a freeze-risk change (touches CustomerTariff stack), so only attempt if the stack is already being updated for DATA-04 / REC-04 anyway.

**Warning signs:**
- Plan updates one path only.
- No byte-equality test in the plan VALIDATION.
- Commit that closes REC-04 has one JSON diff, not two. Review flag.

**Phase:** REC-04 implementation. Add the byte-equality test first (red), then update both files, then green. Test-first catches the exact failure.

---

### Pitfall M2: New persona seeding lands outside the frozen seeder custom resource 🟥 PRE-FREEZE

**What goes wrong:** DATA-04 adds CUST-004 (solar PV) and CUST-005 (EV). The existing seeder is a **CloudFormation custom resource** in the frozen `CustomerTariff` stack (CLAUDE.md). To avoid the stack-policy lift ceremony (Pitfall C6), a shortcut: write a one-shot `scripts/seed-new-personas.py` that inserts directly into DynamoDB. It works. Demo ships. But the seed is now **non-reproducible** — a `cdk destroy` + `cdk deploy` of `CustomerTariff` re-runs the seeder custom resource, which only knows the original 3 personas. The new 2 vanish. Demo dies on re-provisioning.

**Why it happens:** The stack-policy lift ceremony feels heavy for "just adding two rows to DynamoDB". Scripted inserts are faster in the moment. The consequence (non-reproducibility) is invisible until someone re-provisions — which typically happens in the worst-possible scenario (demo-day recovery, new AWS account, etc.).

**Consequences:** Reproducibility gate from v2.0 (fresh-clone + fresh-account) no longer holds. The freeze contract is technically intact (stacks aren't updated) but the *data* state isn't captured in the freeze. Demo recovery is harder if `CustomerTariff` ever needs to be re-deployed.

**Prevention:**
- **Update the seeder custom resource** (`infrastructure/seed_data/billing_records.py` — add SOLAR_PERSONA_RECORDS and EV_PERSONA_RECORDS, extend `ALL_RECORDS`). Accept the stack-policy lift ceremony from Pitfall C6 — it's the right tool for this job.
- **Explicit reject of the one-shot-script approach** in the plan's decision section. Document why (reproducibility).
- **Reproducibility gate as phase exit criterion.** Run a `cdk destroy CustomerTariff` + `cdk deploy CustomerTariff` on a *scratch* account / stack name and confirm all 5 personas land via the seeder. This is the v2.0 reproducibility pattern carried forward.

**Warning signs:**
- Plan includes a `scripts/seed-new-personas.py` that inserts directly via boto3. Big red flag.
- Plan does not update `infrastructure/seed_data/billing_records.py::ALL_RECORDS`.
- Plan's VALIDATION section does not include a `destroy + deploy` reproducibility check.

**Phase:** DATA-04 execution. Pair with Pitfall C6 — same ceremony.

---

### Pitfall M3: Memory TTL / retention not set → cross-rehearsal state bleed 🟥 PRE-FREEZE

**What goes wrong:** WF-01's AgentCore Memory is configured with default retention (days or unset). Between T-24h rehearsal and T-0 demo, the Memory layer has accumulated *rehearsal* events. On live demo, the first "draft follow-up email" pulls in rehearsal-era context (which might include scratch personas, unfinished test strings, "test-persona-123" leftovers). The email is subtly weird.

**Why it happens:** Memory retention configuration is easy to defer ("we'll figure it out later"). Defaults are typically long (days, weeks) because the production use case values long context. Demo use case is the opposite — short, fresh state every time.

**Consequences:** Rehearsal noise in live demo output. Not catastrophic but corrodes trust in the tooling.

**Prevention:**
- **Set Memory TTL short — hours, not days.** For a ~45-min presentation with ~6-hour rehearsal window, 8-12 hour TTL is ample.
- **Pre-rehearsal + pre-demo Memory reset script.** `scripts/memory-reset.sh` wipes all actor memories for the demo namespace. Run at T-24h (pre-rehearsal) and T-2h (pre-demo). Idempotent — safe to re-run.
- **Document in DEMO-RUNBOOK update** — the v3.0 runbook must add the Memory reset step.

**Warning signs:**
- WF-01 plan does not specify TTL / retention.
- No Memory reset script exists.
- T-24h rehearsal output references any T-48h rehearsal state. Investigate before declaring rehearsal pass.

**Phase:** WF-01 implementation + DEMO-RUNBOOK update.

---

### Pitfall M4: Never-500 contract (D-04) broken by new failure modes 🟥 PRE-FREEZE

**What goes wrong:** The `except Exception` at the end of `invoke()` stitches a fallback response when the agent fails. v3.0 adds new tools (AGENT-01), new branches (AGENT-02 hardship), new Memory calls (WF-01). Each is a fresh failure site. Specific failure modes NOT covered by the current fallback:
- A Memory read fails in the follow-up email path. Current fallback doesn't have a "follow-up email failed → render what?" branch.
- The hardship classifier (if implemented as a tool) returns a malformed response. Current fallback assumes a tariff response with `green`/`cheapest`.
- A bill-shock anomaly tool times out. Current fallback doesn't have an anomaly equivalent.

If any of these surfaces a 5xx to the UI, D-04 is violated.

**Why it happens:** Fallback paths are written for the failure modes known at the time. New features add new failure modes. The existing `except Exception` is a catch-all, but it only knows how to produce a *tariff* fallback (via a direct Tools Lambda call + hardcoded narrative). New response shapes (hardship, follow-up email) need their own fallback.

**Consequences:** UI shows a 500 on a new v3.0 branch. D-04 silently broken. The demo's "never errors, always recovers" talking point is a lie on a specific flow.

**Prevention:**
- **Extend the fallback hierarchy per response variant.** If `kind=="hardship"`, fallback is a canned "we'll connect you with a specialist" hardship response (keyed on customer_id, like D-15 narrative fallbacks). If `kind=="followup_email"`, fallback is a generic "draft unavailable, please write manually" string.
- **Test each fallback.** Inject each failure mode in offline pytest and assert the response is non-error and kind-appropriate. Reuse the D-04 test pattern from v2.0.
- **Verify the API Lambda's customer-not-found detection still works after fallback shape changes.** See Pitfall C2 — detection is fragile.
- **Maintain the `_narrative_source` marker discipline for all new narrative-like fields.** The email body, any hardship rationale line, etc. Each gets a marker; API Lambda strips all markers; live tests read them via direct `boto3.invoke_agent_runtime`.

**Warning signs:**
- Plan introduces a new response shape without a corresponding fallback section.
- Plan's VALIDATION does not enumerate "what if tool X fails" for each new tool.
- Catch-all `except` swallows new failure modes without translating them — D-04 has the swallow, but the translation step is missing.

**Phase:** AGENT-01 + AGENT-02 + WF-01 implementation. Each phase owns its fallback. Integration gate: end-to-end test that pessimistically fails each new component and asserts never-500.

---

### Pitfall M5: Prewarm script becomes stale relative to v3.0 flows 🟥 PRE-FREEZE

**What goes wrong:** v2.0's `scripts/prewarm.py` warms `/recommendations/{customer_id}` with the 3 existing personas. v3.0 adds (a) bill-shock flow (maybe a different endpoint, maybe the same endpoint with a different persona), (b) hardship flow (new persona class), (c) follow-up email flow (likely a new endpoint entirely — `/followup/{customer_id}` or similar). **The prewarm script as-is warms ~40% of the live demo surface.** First invocation of the cold paths is slow on stage.

**Why it happens:** Extending prewarm is easy to forget because the v2.0 script works (its tests pass, its 3000ms gate passes) — it's just warming the *old* paths. The new paths are silently cold.

**Consequences:** Exactly the v2.0 Pitfall C6 pattern repeating (wrong-path warming), now with three new paths instead of one. Cold starts on new flows.

**Prevention:**
- **Inventory every new invocation path.** New API endpoints, new Lambda functions (if WF-01 introduces one for email drafting), new Bedrock tool invocations, new boto3 clients (AgentCore Memory client).
- **Extend `prewarm.py` with per-flow warm passes.** The 3000ms gate needs a per-flow variant — bill-shock's baseline is higher (multi-tool), hardship's is lower (code-side short-circuit), follow-up-email's is its own value.
- **Per-flow median gate in prewarm exit code logic.** Exit 0 only if all gates pass.
- **Live prewarm rehearsal pre-freeze.** Run it against the v3.0 stack, assert all gates pass, capture the output as freeze evidence.

**Warning signs:**
- Plan introduces a new backend path without touching `scripts/prewarm.py`.
- Prewarm still uses the v2.0 3000ms global gate.
- Rehearsal shows first-of-day latency significantly higher than subsequent-of-day latency on any flow — the prewarm didn't land for that flow.

**Phase:** AGENT-01 / AGENT-02 / WF-01 each extend prewarm. Final consolidation phase (analog to v2.0 Phase 9) owns the overall prewarm + keep-alive update.

---

### Pitfall M6: Keep-alive script stops rotating through enough personas 🟨 DURING DEMO

**What goes wrong:** `scripts/demo-keepalive.sh` rotates CUST-001 → CUST-002 → CUST-003 every 10 minutes (v2.0 implementation). v3.0 adds CUST-004 + CUST-005. The keep-alive script isn't updated. AgentCore Runtime keeps CUST-001/002/003 paths warm but CUST-004/005 paths go idle. Live demo hits CUST-004 for the solar story — cold start.

**Why it happens:** Keep-alive is "background plumbing" and gets forgotten. The v2.0 script was shellcheck-clean and working — it's unsentimental to update it.

**Consequences:** First solar or EV persona lookup is cold. The exact moment v3.0 shows off its new-persona story.

**Prevention:**
- **Update `scripts/demo-keepalive.sh` to rotate all 5 personas.** Interval can stay at 10min — with 5 personas + 10min interval, each persona gets pinged once every 50min, still well under the 15-min-per-session idle timeout (each ping re-warms that persona's session).
- **If follow-up email flow is a different endpoint**, add a rotation through that too.
- **Verify with the full-duration rehearsal.** Run a 60-minute "pretend demo" where the presenter interleaves Q&A with persona lookups. Any cold start caught at rehearsal, not at demo.

**Warning signs:**
- `demo-keepalive.sh` still references CUST-001/002/003 only.
- Demo flow plans include all 5 personas but rehearsal only exercises 3.

**Phase:** DEMO-RUNBOOK update phase (analog to v2.0 Phase 10 DEMO-04).

---

### Pitfall M7: Presenter docs (DOC-01/02/03) over-promise or drift post-v3.0 🟨 DURING REHEARSAL

**What goes wrong:**
- **DOC-01 (trust-architecture one-pager)** describes capabilities that are *designed* but not *built*. E.g. "CloudWatch alarm on `retry_count > 0`" from the v2.0 deferred list — if this is in the doc but not in the stack, the doc is aspirational.
- **DOC-02 (narrative-tradeoff acknowledgement)** swings too far to "LLMs are great" or too far to "LLMs are unreliable" — neither serves the demo narrative.
- **DOC-03 (deferred-roadmap)** commits to PROD-02 delivery timelines that the team isn't actually planning against.
- **Drift:** All three docs capture v3.0's state at freeze time. Any post-v3.0 change (e.g. a hotfix that changes a tool behaviour) invalidates the docs silently.

**Why it happens:** Presenter docs are written after the code and feel low-risk. "Over-promising" specifically happens when writers describe the architecture they *wish* existed (clean, patterned, fully-hardened) rather than the one that shipped.

**Consequences:** Audience member reads the one-pager and asks a question about a feature that isn't actually live. Presenter either bluffs (trust damage) or admits the doc is ahead of reality (trust damage). Either way, the doc becomes a liability.

**Prevention:**
- **Claim-check every sentence against the live stack.** For DOC-01: each trust-pattern claim gets a pytest or a CloudWatch metric that proves it. No claim without a proof.
- **DOC-02 should cite specifics, not platitudes.** "The narrative may be wrong; here are the 4 gates (Pydantic max_length, validators, salvage, FALLBACKS) and here is exactly what each catches" rather than "LLMs can hallucinate".
- **DOC-03 should distinguish "in-flight" from "planned" from "aspirational".** PROD-01 partial = in-flight, named by phase. PROD-02 = planned for vN.0, not committed.
- **Freeze-time proof bundle.** At v3.0 freeze, capture the CloudWatch dashboard snapshot + pytest green output + key manifest hashes in the phase directory. Docs reference this evidence.
- **Drift gate:** DOC-01/02/03 rendered via a `make docs-check` that re-verifies each live claim. Fail loudly on drift.

**Warning signs:**
- DOC-01 references a feature not in the phase plan.
- DOC-02 contains marketing adjectives (industry-leading, best-in-class, etc.).
- DOC-03 lists a roadmap date.
- No test / metric backs a trust-pattern claim.

**Phase:** DOC-01 / DOC-02 / DOC-03 phase. The docs phase must come *after* feature phases land, not before. Freeze evidence must be captured before docs are signed off.

---

## Minor Pitfalls

---

### Pitfall m1: Strands version drift during v3.0 development 🟥 PRE-FREEZE

**What goes wrong:** A phase plan casually adds "upgrade Strands from 1.37.0 to 1.4x.x" as a side-effect of adding a tool (e.g. because the new tool uses a new Strands utility). This is exactly the Phase 06.1 failure mode — Strands API surface changed between minor versions and broke tool-use wiring.

**Prevention:**
- **Strands version is frozen at 1.37.0** unless a plan explicitly scopes an upgrade with a canary test suite.
- **Lockfile contract** (`--require-hashes`) catches accidental upgrades — the install itself will fail. But a plan can legitimately update `requirements.in` and regenerate; the trap is doing this without running the full DEMO-02 canary.
- **If upgrade is needed, isolate it in its own decimal phase** (like Phase 06.1 did) with canary-first gating.

**Phase:** Cross-cutting; any agent phase.

---

### Pitfall m2: Frontend stack deploy without rebuilding `ui/dist` after `__GIT_SHA__` change 🟨 FREEZE-DAY

**What goes wrong:** v2.0 `FrontendStack` deploys whatever's in `ui/dist`. `__GIT_SHA__` is a Vite build-time define. If the operator deploys the Frontend stack without running `npm run build` first (e.g. after a git rebase or checkout), the `ui/dist` has the *previous* commit's SHA. Version indicator shows the wrong build on stage.

**Prevention:**
- **CDK-level check: Frontend stack deploy fails if `ui/dist/index.html` does not match the current HEAD SHA.** Simple post-build marker file or manifest check.
- **DEMO-RUNBOOK: "always `npm run build` before `cdk deploy CustomerTariffFrontend`"** — document explicitly.
- **Verify at T-2h:** view the deployed UI, confirm `v3.0 · <git-sha>` matches `git rev-parse --short HEAD`.

**Phase:** Frontend deploy step, DEMO-RUNBOOK v3.0 update.

---

### Pitfall m3: AGENT-02 hardship flag plumbing leaks to non-hardship personas 🟥 PRE-FREEZE

**What goes wrong:** Adding `hardship_flag` to the persona schema (DynamoDB) means every persona row needs the field, not just the hardship one. Missing field on existing personas → KeyError or silent `None` → undefined short-circuit behaviour. Worst case: a non-hardship persona is evaluated as hardship because `None` is truthy in a badly-written check (it isn't, but `"None"` string is).

**Prevention:**
- **Add `hardship_flag: bool = False`** as a default on the dataclass; all existing persona records default to `False`.
- **Migration path:** a `scripts/backfill-hardship-flag.py` that sets `False` on existing rows if the seeder can't cleanly re-run. Prefer re-seeding via Pitfall M2's reproducibility gate.
- **Test:** all v1.0/v2.0 personas still return non-hardship responses after the schema change.

**Phase:** DATA-04 schema change phase.

---

### Pitfall m4: CloudWatch log bloat from multi-tool flows 🟦 OBSERVATIONAL

**What goes wrong:** Each new tool logs its invocation + payload + result. Multi-tool flows multiply log volume. Log Insights queries during rehearsal get slow. Cost creeps.

**Prevention:**
- **Structured logs only; no free-text dumps of tool payloads.** Log shape: `{tool, customer_id, latency_ms, result_size_bytes}` — not the full payload.
- **PII boundary (Pitfall M7 from v2.0) carries forward** — no raw customer-derived strings in logs.
- **Log retention: 7-30 days on dev, not "Never Expire".** Cost control.

**Phase:** Observability phase for v3.0.

---

### Pitfall m5: Presenter cognitive load from too many personas on stage 🟨 DURING DEMO

**What goes wrong:** v3.0 has 5 personas (Sarah, Marcus, Elena, Solar, EV) + hardship. Presenter tries to demo all of them in a 10-minute window. Audience loses the thread. The agentic-depth story is replaced by a persona tour.

**Prevention:**
- **Select 2-3 personas for the linear demo flow** — usually Sarah (flagship savings), Solar (new persona archetype for agentic depth), Hardship (regulatory boundary). Save others for Q&A.
- **Rehearse a 7-minute presentation script** that hits agentic depth, hardship, and workflow assist — not a full persona tour.
- **DEMO-RUNBOOK update reflects this.**

**Phase:** DEMO-RUNBOOK v3.0 update.

---

## Technical Debt Patterns

Shortcuts that might seem reasonable in v3.0 but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Direct boto3 DynamoDB inserts for DATA-04 (skip seeder custom resource) | Avoids stack-policy lift ceremony | Non-reproducible seed; `cdk destroy`+`deploy` loses new personas | **Never** for v3.0 — reproducibility gate from v2.0 is a hard contract |
| Mock-only testing of AgentCore Memory | Faster iteration in dev | Cross-customer bleed only surfaces on live — catastrophic on stage | Only during initial wiring; switch to live smoke before phase close |
| Single adapter implementation for `CustomerDataProvider` | Ships PROD-01 scope faster | Abstraction doesn't generalise; rework at PROD-02 | Never — if only one impl is needed, don't add the Protocol |
| Keep v2.0 prewarm script unchanged | "It still passes its gate" | New v3.0 cold paths not warmed | Never — extend per-flow before freeze |
| Inline `hardship_flag` check in system prompt only | Prompt engineering is fast | Soft-decline leak vector (Pitfall C3) | Never — short-circuit is code |
| Reuse existing `runtimeSessionId` for Memory `actorId` | Simpler wiring | Bleed across customers — session scope is per-request, Memory scope is cross-request | Never — `actorId` scoping is a load-bearing design decision |
| Skip byte-equality test on `tariff_plans.json` duplicates | Fewer tests to write | Silent drift; savings math wrong on new tariffs | Never — mechanical test, high leverage |

---

## Integration Gotchas

Common mistakes when connecting v3.0 features to the frozen stack.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| AgentCore Memory × `runtimeSessionId` invariant | Assume `runtimeSessionId` isolation carries to Memory | Scope `actorId=customer:{customer_id}`; Memory isolation is actor-level, not session-level |
| Hardship short-circuit × `customer-not-found` detection | Empty response with no `green`/`cheapest` keys | Discriminated union with `kind` field; update API Lambda detection to check `kind` |
| Hardship short-circuit × REC-03 | Prompt still says "both tracks always" | Amend prompt to condition REC-03 on `hardship_flag==false` |
| Multi-tool flow × SAV-03 | Assume adding a new tool can't re-fabricate savings | Cross-persona canary + CloudWatch tool-invocation counter |
| Multi-tool flow × UI-02 (<3s) | Sequential tool calls; no latency budget | Per-flow budget + eval harness test + parallel tools where graph allows |
| New tool × D-04 never-500 | Catch-all swallows but doesn't translate | Per-response-variant fallback + test each failure mode |
| Seed data change × frozen `CustomerTariff` stack | Direct boto3 insert | Lift policy → update seeder → deploy → re-apply policy |
| `tariff_plans.json` change × duplication | Edit one file | Byte-equality pytest + update both in same commit |
| `CustomerDataProvider` × bi-mode imports | Place module under `agent/` without bi-mode fallback | Apply existing pattern: `try: from providers.X import ... except: from agent.providers.X import ...` |
| AgentCore Memory × PII | Store customer free-text in Memory | Shape tokens only; render names client-side (v2.0 Pitfall C2 carries forward) |
| DOC-01/02/03 × live stack | Describe architectural intent | Claim-check each sentence against a pytest / CloudWatch metric |

---

## Performance Traps

v3.0 operates at demo scale (5 personas, 1 presenter, ~45min window). Performance pitfalls are *latency* not *throughput* — Bedrock throttling quotas are not at risk.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Sequential multi-tool chains | Warm median creeps past 3000ms | Parallel tools or compound tool Lambda | 3 tools sequential on Sonnet 4.6 warm path |
| New cold paths not in prewarm | First-of-day latency ≫ second-of-day | Per-flow prewarm + median gate | Every fresh demo session |
| AgentCore Runtime 15-min idle on new personas | Cold start mid-Q&A | Extended keep-alive covering 5 personas | Q&A runs past 15 min without persona lookups |
| Memory read on every invocation | Sub-100ms latency add per call | Cache within-session; evict on `handler()` return | N Memory calls × N tools = NxM latency |
| Tool result payload inflation | Input tokens on next turn grow → latency | Trim Lambda responses to fields the model needs | Billing record array returned in full |
| Per-invocation `actorId` lookups | DynamoDB read latency per request | `actorId = f"customer:{customer_id}"` — no lookup needed | N/A — prevent with naming |

---

## Security Mistakes

Beyond v2.0's PII-in-prompts boundary (still applies to v3.0). v3.0-specific concerns.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Memory `actorId` not scoped to customer | Cross-customer PII leak | `actor_id = f"customer:{customer_id}"`; live isolation smoke |
| Memory retains raw prompt/response content | Persistent PII in long-lived store | Shape tokens only in Memory events; no free text |
| Hardship flag in CloudWatch logs alongside customer_id | Sensitive attribute in logs | Log `is_hardship: bool` only when explicitly needed; never log the flag's true value alongside identifiable fields |
| Follow-up email draft logged in full | Generated content may echo persona context | Log email metadata (length, send-readiness) only; not body |
| CRM adapter (PROD-01 partial) logs raw queries | Future CRM integration risk pattern | Establish logging discipline now; document in DOC-01 |
| Memory TTL unset or default-long | Rehearsal state in live demo | TTL in hours for demo; documented in DEMO-RUNBOOK |
| Stack policies lifted and left lifted | Demo stacks no longer immutable | Scripted lift + apply + verification gate |

---

## UX Pitfalls

v3.0 call-centre-agent UX specifics.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Hardship response visually indistinguishable from 404 | Rep thinks the system failed | Distinct hardship card component; unmistakable "hardship workflow" label + icon |
| Multi-tool flow shows nothing during tool turns | 3-4s blank screen | Streaming tool-invocation surface ("Checking billing history… Checking for anomalies… Calculating savings…") — gives agentic-depth story visual weight |
| Draft follow-up email appears instantly with no provenance | Rep doesn't know if it's safe to send | Display "AI-drafted — review before sending" badge + `_narrative_source` equivalent transparency |
| Bill-shock anomaly rendered without context | Rep reads a number with no story | Anomaly UI cites "your September bill was $X higher than your 12-month average" — numbers from tool, narrative from LLM, same SAV-03 discipline |
| Hardship rationale line triggers D-15 validators (digits, %) | Fallback fires; rationale is stale canned text | Extend D-15 banned terms for hardship-specific rationale; hand-write 3-5 fallback rationale strings per hardship class |
| Persona switcher adds CUST-004/005 but no visual affordance for their archetype | Rep can't tell Solar from Residential at a glance | Small icon/badge per persona card — shape the scan, not just the label |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces. Use during phase execution.

- [ ] **AGENT-01 bill-shock flow:** Warm median measured live — appears complete. Check: Is there a per-flow (not global) latency gate in prewarm? Is the eval harness asserting p95 < 2500ms, not just p50?
- [ ] **AGENT-02 hardship short-circuit:** Refuses tariff recommendation — appears complete. Check: Does it refuse *code-side* (before the model sees tariff data)? Adversarial test for leaked plan IDs run? `api_lambda/handler.py:152` customer-not-found detection updated? Pydantic schema discriminated union?
- [ ] **WF-01 follow-up email + Memory:** Exercises Memory across turns — appears complete. Check: `actorId` scoped to customer? Cross-customer isolation smoke written? Memory TTL set? Reset script exists?
- [ ] **DATA-04 new personas:** Seeded to DynamoDB — appears complete. Check: Via seeder custom resource (not one-shot script)? Stack-policy re-applied after deploy? `cdk destroy+deploy` reproducibility gate passed?
- [ ] **REC-04 new tariff archetype:** Plans file updated — appears complete. Check: BOTH `lambda/tariff_plans.json` AND `infrastructure/seed_data/tariff_plans.json` updated? Byte-equality test green?
- [ ] **PROD-01 adapter:** `CustomerDataProvider` Protocol shipped — appears complete. Check: Two implementations exist (DynamoDB + InMemory)? Bi-mode import pattern honoured? SAV-03 byte-exact canary green on BOTH impls?
- [ ] **D-04 never-500:** `except Exception` catches all — appears complete. Check: Each new response variant (hardship, follow-up email) has a fallback? Each fallback is tested via injected failure?
- [ ] **D-15 narrative gauntlet:** New fields pass validators — appears complete. Check: Hardship rationale + email body subject to the same (or extended) banned-terms gauntlet? Fallback strings for each new field per customer_id?
- [ ] **Prewarm:** Script exits 0 — appears complete. Check: Covers every new flow (bill-shock, hardship, follow-up email)? Per-flow median gates? CUST-004/005 warmed?
- [ ] **Keep-alive:** Script running — appears complete. Check: Rotates all 5 personas? Covers any new endpoints?
- [ ] **Stack policies:** Deploys completed — appears complete. Check: `aws cloudformation get-stack-policy` on all 3 frozen stacks returns deny-Update:* body byte-equal to source-controlled JSON?
- [ ] **DOC-01 trust-architecture:** Document drafted — appears complete. Check: Every claim backed by a pytest / CloudWatch metric / code reference?
- [ ] **`_narrative_source` marker:** Works on tariff path — appears complete. Check: Extended to hardship rationale + email body? API Lambda strips ALL marker variants? Live eval harness reads the new markers via `boto3.invoke_agent_runtime`?
- [ ] **Bi-mode imports:** Tests pass offline — appears complete. Check: Docker container smoke (`docker run --entrypoint python ... -c 'from providers.X import ...'`) executed before `cdk deploy`?

---

## Recovery Strategies

When pitfalls occur despite prevention.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| C1 latency stacking | MEDIUM | Fall back to v2.0 single-tool persona flow for the bill-shock story; collapse the multi-tool visual; demo the feature as "coming in v3.1"; keep v2.0 polish story |
| C2 hardship → 404 | LOW | Hot-patch `api_lambda/handler.py` detection logic; redeploy API stack; rehearse before freeze |
| C3 hardship soft-decline | MEDIUM | Move short-circuit code-side (won't ship in time if caught at freeze); rehearse with "we disabled hardship for this rehearsal" presenter framing |
| C4 Memory cross-customer bleed | HIGH | If caught pre-freeze: redesign `actorId` scope; post-freeze: disable WF-01 via feature flag, demo follow-up email from canned templates |
| C5 Strands multi-tool regression | HIGH | Revert to v2.0 single-tool path; run canary suite; if fabrication signature present, reopen Phase 06.1-style resolution as 06.2 |
| C6 stack policy not re-applied | LOW | `aws cloudformation set-stack-policy` with deny-body; verify via `get-stack-policy`; document as incident |
| C7 adapter refactor breaks byte-exact savings | MEDIUM | Revert the refactor commit; keep v1.0 direct DynamoDB call; defer PROD-01 to v3.1 |
| M1 tariff_plans.json drift | LOW | Re-sync files; re-seed DynamoDB via seeder re-run (or one-shot script for emergency); add byte-equality test |
| M2 non-reproducible seed | MEDIUM | Add new personas to seeder custom resource; next deploy re-seeds cleanly; until then, document the manual insert as freeze evidence |
| M4 never-500 broken | LOW | Add the missing fallback translation; hot-patch + redeploy API stack |
| M5 prewarm stale | LOW | Extend `prewarm.py` with new flows; rerun; gate on all flows |
| M7 doc over-promises | LOW | Edit doc pre-presentation; remove or soften any claim not backed by evidence |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls. Assumes a v3.0 phase breakdown roughly matching the milestone features.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| **C1** Multi-tool latency stacking | AGENT-01 (bill-shock flow) | Eval harness p95 < 2500ms per flow; per-flow prewarm gate |
| **C2** Hardship → customer-not-found false-positive | AGENT-02 (hardship short-circuit) | API Lambda `kind`-aware detection; offline + live tests for both branches |
| **C3** Hardship soft-decline leak | AGENT-02 | Adversarial test for plan IDs in hardship response across 10 seeds |
| **C4** Memory cross-customer bleed | WF-01 (follow-up email + Memory) | `actorId=customer:{id}` smoke; reset script; TTL documented |
| **C5** Strands multi-tool regression | AGENT-01 (and any tool-adding phase) | Cross-persona canary; CloudWatch tool-invocation counter; latency floor assertion |
| **C6** Stack policy lift-and-forget | DATA-04 / REC-04 deploy | `get-stack-policy` byte-equality gate post-deploy |
| **C7** Adapter refactor destabilises | PROD-01 | SAV-03 byte-exact canary on both impls; bi-mode container smoke |
| **M1** tariff_plans.json drift | REC-04 | Byte-equality pytest |
| **M2** Non-reproducible seed | DATA-04 | `cdk destroy+deploy` on scratch stack |
| **M3** Memory TTL unset | WF-01 | Retention config review + reset script + runbook step |
| **M4** D-04 broken by new variants | AGENT-01 / AGENT-02 / WF-01 integration | Injected-failure test per variant; end-to-end never-500 |
| **M5** Prewarm stale | Consolidation phase | Live prewarm with per-flow gates green |
| **M6** Keep-alive misses personas | DEMO-RUNBOOK update phase | 60-min rehearsal, all personas hot |
| **M7** Presenter docs over-promise | DOC-01 / DOC-02 / DOC-03 (after feature phases) | Claim-check each sentence against live evidence |
| **m1** Strands version drift | Cross-cutting | Lockfile hash-pin contract; upgrade only in decimal phase with canary |
| **m2** Frontend stale dist | Frontend deploy + DEMO-RUNBOOK | SHA match check at T-2h |
| **m3** Hardship flag on existing personas | DATA-04 schema change | Default=False on existing rows; regression test on CUST-001/002/003 |
| **m4** CloudWatch log bloat | Observability phase | Log retention config + structured-log audit |
| **m5** Persona overload on stage | DEMO-RUNBOOK v3.0 | Rehearsal with 7-min script |

---

## Sources

- **CLAUDE.md** (HIGH confidence, verified 2026-04-28) — All critical invariants cited by name (SAV-03, REC-03, D-04, D-15, Pitfall 2 / SC-3 `runtimeSessionId`, `?narrative=off`, `?prewarm=1`, `customer-not-found` detection at `api_lambda/handler.py:152`, bi-mode imports, `_narrative_source` marker stripping, Config(read_timeout=25), region lock, model literal pin). Drives Pitfalls C2, C3, C4, C5, C7, M1, M4, m2.
- **`.planning/milestones/v2.0-research/PITFALLS.md`** (HIGH confidence, 2026-04-25) — v2.0 pitfalls and the pre-freeze/freeze-day/post-freeze taxonomy adapted here. v2.0 C1/C2/C3/C4/C6 treated as shipped and closed; v3.0 extends the pattern to new surfaces.
- **`.planning/milestones/v2.0-phases/06.1-resolve-sonnet-4-6-tool-use-regression-demo-02/06.1-CONTEXT.md`** (HIGH confidence, 2026-04-25) — Sonnet 4.6 + Strands tool-use fabrication failure mode. Cross-persona canary test pattern. API migration (`Agent.structured_output_model`) as durable fix. Drives Pitfall C5 prevention strategy including the coincident-values fabrication signature.
- **`.planning/RETROSPECTIVE.md`** (HIGH confidence, 2026-04-27) — v2.0 retro lessons: `cdk diff == 0` as undeployed-code witness; stack-policy freeze ceremony (6 policy bodies, 3 stacks); `AWS_PROFILE=cevo-25` vs `cevo-dev25` recurring trap; lockfile scope mismatch (test-runtime imports). Drives Pitfalls C6, m1.
- **`agent/agent.py`** (HIGH confidence, inspected 2026-04-28) — Current `Agent(model=_model, system_prompt=SYSTEM_PROMPT, tools=[simulate_savings])` construction. `invoke()` happy-path + retry-path + `except Exception` fallback structure. Verifies D-04 contract surface that v3.0 must extend.
- **`api_lambda/handler.py`** (HIGH confidence, inspected 2026-04-28) — `runtimeSessionId` generated inside `handler()`; `Config(read_timeout=25, connect_timeout=5)` override; customer-not-found detection at line 152; `_narrative_source` stripping. Verifies integration surfaces Pitfalls C2, C4 touch.
- **AWS Bedrock AgentCore documentation** (MEDIUM confidence, 2026-04-28) — Memory concepts page confirms existence of short-term / long-term memory, session isolation in Runtime (distinct from Memory scope), namespace/actor/session hierarchy for Memory. Specific namespace template syntax and cross-actor isolation guarantees under-documented on public pages; MEDIUM-confidence recommendations in Pitfall C4 reflect this and should be validated against current AWS Memory docs when the WF-01 plan is drafted.
- **Strands SDK behaviour on Claude Sonnet 4.6** (MEDIUM-HIGH confidence, domain knowledge + Phase 06.1 lived experience) — Tool-use wire format sensitivity, structured_output vs structured_output_model API surface, silent fabrication failure mode. Drives Pitfall C5.
- **General LLM short-form refusal failure modes** (MEDIUM confidence, domain knowledge) — Soft-decline leak pattern ("I can't recommend X, *but* here's what would help"). Drives Pitfall C3's code-side-not-prompt-side recommendation.
- **CloudFormation stack-policy + termination-protection mechanics** (HIGH confidence, AWS docs, 2026-04-28) — Stack policies are mutable via `set-stack-policy`; no CDK-native tracking; applied imperatively; lost silently if not re-applied. Drives Pitfall C6.
- **Adapter / Protocol refactor failure modes on shipped code** (MEDIUM-HIGH confidence, domain knowledge) — Chesterton's Fence; test-double drift; speculative abstraction; bi-mode import disruption. Drives Pitfall C7.

---

*Pitfalls research for: v3.0 Agentic Depth & Workflow Assist on the frozen `demo-v2.0` Bedrock AgentCore stack*
*Researched: 2026-04-28*
