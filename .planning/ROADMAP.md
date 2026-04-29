# Roadmap: Customer Tariff & Billing Optimisation Agent

## Milestones

- ✅ **v1.0 MVP** — Phases 1–5 (shipped 2026-04-25, tagged `demo-v1.0`) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 Demo Polish & LLM Narrative** — Phases 6–10 (shipped 2026-04-26, tagged `demo-v2.0` + `v2.0`) — see [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)
- 🚧 **v3.0 Agentic Depth & Workflow Assist** — Phases 11–17 (defined 2026-04-28, target tag `demo-v3.0`)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–5) — SHIPPED 2026-04-25</summary>

- [x] Phase 1: Foundation + Dummy Data (3/3 plans) — completed 2026-04-23
- [x] Phase 2: AgentCore Agent (3/3 plans) — completed 2026-04-23
- [x] Phase 3: Backend API (3/3 plans) — completed 2026-04-24
- [x] Phase 4: Agent-Assist UI (5/5 plans) — completed 2026-04-24
- [x] Phase 5: Demo Hardening (7/7 plans) — completed 2026-04-25

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v2.0 Demo Polish & LLM Narrative (Phases 6–10) — SHIPPED 2026-04-26</summary>

- [x] Phase 6: Agent Narrative + Guardrail (3/3 plans) — completed 2026-04-25
- [x] Phase 6.1: Resolve Sonnet 4.6 tool-use regression (DEMO-02) (4/4 plans) — completed 2026-04-25
- [x] Phase 7: API Pass-Through + Pre-Warm Route (2/2 plans) — completed 2026-04-26
- [x] Phase 8: UI Integration + Feature Flag + Version Indicator (4/4 plans) — completed 2026-04-26
- [x] Phase 9: Pre-Warm Tooling + Eval Harness + Keep-Alive (4/4 plans) — completed 2026-04-26
- [x] Phase 10: Freeze + Rollback Drill (3/3 plans) — completed 2026-04-26

Full details: [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)

</details>

### 🚧 v3.0 Agentic Depth & Workflow Assist (Phases 11–17)

- [x] **Phase 11: New Personas + Tariff Archetypes** — CUST-004 (solar PV) + CUST-005 (EV) seeded, two new tariff plans (Solar Feed-in + EV TOU), TOU-dispatched savings math, hardship_flag PROFILE items (completed 2026-04-28)
- [x] **Phase 12: CustomerDataProvider Abstraction** — `agent/providers.py` Protocol + DynamoDB impl + InMemory test double + Salesforce NotImplementedError stub; strangler-fig around existing agent tools with SAV-03 byte-exact preservation (completed 2026-04-29)
- [x] **Phase 13: Bill-Shock Multi-Tool Flow (AGENT-01)** — action dispatcher on Tools Lambda, 2-3 tool composition per turn, 4-tool code-enforced cap, reasoning trace surfaced to UI, warm p95 < 2500ms per-flow prewarm gate (completed 2026-04-29)
- [ ] **Phase 14: Hardship Short-Circuit (AGENT-02)** — code-side pre-LLM guard, Pydantic discriminated union `kind: recommendation | hardship`, surgical update to `api_lambda/handler.py:152`, dignity-preserving hardship narrative passing D-15 validators
- [ ] **Phase 15: Draft Follow-Up Email via AgentCore Memory (WF-01)** — new API route, short-term Memory with `actorId=customer:{id}` + deterministic `session_id={id}-{UTC-ISO-day}`, cross-customer isolation canary, bedrock-agentcore 1.6.4 + lockfile regen
- [ ] **Phase 16: Presenter Artefacts + Operational Consolidation** — DOC-01/02/03 committed, `?narrative=off` kill switch extended, prewarm + keep-alive + eval harness extended to new personas and multi-tool + follow-up routes
- [ ] **Phase 17: v3.0 Freeze Ceremony** — lift deny-Update:* policies on 3 frozen stacks, redeploy v3.0 surface, re-apply policies with byte-equality verification, fresh DynamoDB backup, `demo-v3.0` annotated tag + FREEZE-MANIFEST, 5/5 rollback drill

## Phase Details

### Phase 11: New Personas + Tariff Archetypes
**Goal**: Engineered dummy data supports the full v3.0 demo surface — two new personas with realistic billing shapes round-trip through the existing savings engine with byte-exact figures, without regressing the three v2.0 personas.
**Depends on**: v2.0 frozen stack (`demo-v2.0`)
**Requirements**: DATA-04, DATA-05, DATA-06, DATA-07, REC-04, REC-05
**Success Criteria** (what must be TRUE):
  1. Lookup of CUST-004 returns a recommendation card pair that references the Solar Feed-in tariff, with engineered savings figures locked byte-exact in `tests/conftest.py` via `mock_cust004_response`.
  2. Lookup of CUST-005 returns a recommendation card pair that references the EV Time-of-Use tariff, with engineered savings figures locked byte-exact in `tests/conftest.py` via `mock_cust005_response`.
  3. Pytest `test_tariff_plans_byte_equivalence` (or equivalent) asserts `lambda/tariff_plans.json == infrastructure/seed_data/tariff_plans.json` and passes after both archetypes are added.
  4. The three v2.0 persona savings invariants (Sarah $30/$55, Marcus $16.90/$30.98, Elena $14.00/$25.67) remain byte-exact after the `plan_type` dispatcher refactor inside `simulate_savings_pure`.
  5. The customer flagged with `hardship_flag: true` in the PROFILE items is discoverable via a pure helper (`get_hardship_flag_pure` or equivalent) and returns the expected `{hardship: true, ...}` shape offline — no new LLM wiring required at this phase.
**Plans**: 6 plans
  - [x] 11-01-PLAN.md — Extend tariff_plans.json with SOL + EV-TOU + NEW byte-equality gate test (M1 mitigation)
  - [x] 11-02-PLAN.md — Extend simulate_savings_pure with plan_type dispatcher; preserve v2.0 byte-exact
  - [x] 11-03-PLAN.md — Seed CUST-004/005/006 records + PROFILE item in billing_records.py (73 items total)
  - [x] 11-04-PLAN.md — Add get_hardship_flag_pure helper + PROFILE filter in get_billing_history
  - [x] 11-05-PLAN.md — Add 7 conftest fixtures + 7 byte-exact/invariant tests for new personas
  - [x] 11-06-PLAN.md — Extend smoke tests + live CDK deploy ceremony (LIFT → DEPLOY → REAPPLY → VERIFY)
**Invariant ownership**: SAV-03 (byte-exact carry-forward for v2.0 personas through TOU dispatch), `tariff_plans.json` duplication source-of-truth (byte-equality gate), frozen-lockfile contract (no dep bump this phase).

### Phase 12: CustomerDataProvider Abstraction
**Goal**: Agent-side customer-data access flows through a production-shaped adapter interface (`agent/providers.py`) with two working implementations (DynamoDB + InMemory) and a visible Salesforce-shaped stub, preserving byte-exact SAV-03 savings on the deployed runtime.
**Depends on**: Phase 11
**Requirements**: PROD-01, PROD-01a, PROD-01b, PROD-01c
**Success Criteria** (what must be TRUE):
  1. Calling the deployed agent's existing `recommend` action for CUST-001/002/003/004/005 returns savings figures byte-identical to the pre-refactor values (SAV-03 invariant held through the provider indirection).
  2. `agent/providers.py` exposes a `@runtime_checkable` Protocol with exactly three methods (`get_customer`, `get_billing_history`, `get_hardship_flag`); offline `isinstance()` tests confirm both `ToolsLambdaProvider` and `InMemoryProvider` satisfy it.
  3. `tests/test_providers.py` swaps in `InMemoryProvider` and drives the full savings fixture set offline (no AWS), and the five persona fixtures in `tests/conftest.py` continue to pass unchanged.
  4. `SalesforceCustomerDataProvider` file exists under `agent/providers.py` (or adjacent), raises `NotImplementedError` on all three methods, and is referenced by the DOC-03 placeholder text so the presenter artefact can be drafted later without a rewrite.
  5. Bi-mode import pattern verified: `docker run --entrypoint python ... -c "from providers import CustomerDataProvider"` succeeds inside the container AND `python -c "from agent.providers import CustomerDataProvider"` succeeds in the repo pytest venv.
**Plans**: 6 plans
  - [x] 12-01-PLAN.md — Create agent/providers.py (Protocol + ToolsLambdaProvider + InMemoryProvider + SalesforceCustomerDataProvider + set_provider/get_provider)
  - [x] 12-02-PLAN.md — Add lambda/handler.py action dispatcher + update CDK handler string to handler.handler
  - [x] 12-03-PLAN.md — Create scripts/capture_live_recommendations.py + capture baseline/pre/ JSONs from live v2.0 runtime
  - [x] 12-04-PLAN.md — Add tests/test_providers.py + _provider_swap autouse fixture (D-09 pre-deploy gate)
  - [x] 12-05-PLAN.md — Wire agent/agent.py (bi-mode imports + _provider singleton + @tool refactor) + Dockerfile COPY providers.py
  - [x] 12-06-PLAN.md — Stack-policy lift → deploy CustomerTariff+CustomerTariffAgent → post-capture + byte-equality gate → re-apply freeze + termination protection + bi-mode container smoke
**Invariant ownership**: SAV-03 byte-exact preservation through the new indirection layer, bi-mode imports pattern (`try: from providers … except: from agent.providers …`), Chesterton's-Fence risk on `simulate_savings_pure` (wrap around, never through).

### Phase 13: Bill-Shock Multi-Tool Flow (AGENT-01)
**Goal**: The agent visibly reasons — composing 2-3 deterministic tool calls in one turn on a designated bill-shock persona — and the rep can see the ordered trace in the UI without breaking UI-01 above-the-fold or the UI-02 <3s contract.
**Depends on**: Phase 11 (new personas) + Phase 12 (provider seam)
**Requirements**: AGENT-01, AGENT-01a, AGENT-01b
**Success Criteria** (what must be TRUE):
  1. Lookup of the designated bill-shock persona (CUST-002 recommended) produces a recommendation response whose `reasoning_trace` array contains ordered tool-use entries from at least two distinct tools (e.g. `get_billing_history` + `simulate_savings`, optionally `detect_bill_shock`), each entry sourced from Strands `agent_result.message.content[].toolUse` blocks rather than LLM estimation.
  2. All numeric content inside the reasoning trace and call script (dates, dollar deltas, event timestamps) originates from tool output — SAV-03 extension canary test asserts zero arithmetic or rounding performed by the LLM across 10 seeds on two personas.
  3. Per-flow prewarm gate in `scripts/prewarm.py` measures warm p95 for the multi-tool route and exits 0 only when median lands under 2500ms; AGENT-01a gate is observable and automated, not operator-judged.
  4. Code-enforced 4-tool cap (e.g. `Agent(max_iterations=4)` or equivalent Strands configuration) short-circuits runaway tool loops — pytest asserts the cap triggers on a crafted "infinite delegator" prompt and returns a graceful fallback, never a 500 (D-04 preserved).
  5. UI `ReasoningTrace` component renders the trace collapsed by default; at 1280×800 viewport both recommendation cards remain above the fold (UI-01 preserved, measurable via vitest snapshot or operator rehearsal).
**Plans**: 9 plans
  - [x] 13-01-PLAN.md — Tools Lambda: detect_bill_shock_pure + dispatcher branch + offline unit tests
  - [x] 13-02-PLAN.md — Agent schema: ReasoningTraceEntry + reasoning_trace field + _extract_reasoning_trace + agent/reasoning/summaries.py + Dockerfile COPY + D-11 counter-pytest
  - [x] 13-03-PLAN.md — 3 new @tool wrappers (detect_bill_shock, get_billing_history, get_hardship_flag) + extended _BASE_SYSTEM_PROMPT (D-23 preference-ordered graph)
  - [x] 13-04-PLAN.md — FourToolCapHook (Strands HookProvider, A-02 amendment — NOT max_iterations) + stop_reason=cancelled branch + reasoning_trace happy-path + partial-trace on D-04 fallback
  - [x] 13-05-PLAN.md — Cross-persona canary (D-20: Elena shock vs Marcus non-shock foil per A-01) + api_lambda pass-through tests (D-12)
  - [x] 13-06-PLAN.md — UI ReasoningTrace.tsx + 6 vitest D-30 cases + App.tsx insertion + mock byte-sync with Python formatters
  - [x] 13-07-PLAN.md — scripts/prewarm.py per-flow gate map + 3-pass warming (A-03) + D-19 latency floor + D-21 CloudWatch counter + A-03 sighting-shot operator gate
  - [x] 13-08-PLAN.md — Stack-policy lift ceremony (2-3 stacks per cdk diff) + baseline/pre+post capture + byte-equivalence gate + re-apply freeze (autonomous: false)
  - [x] 13-09-PLAN.md — CLAUDE.md addendum (D-11 exemption, D-15 cap routing, D-22 Strands pin) + DEMO-RUNBOOK.md Marcus→Elena swap
**Invariant ownership**: SAV-03 (extended — every new arithmetic tool stays pure Python in Tools Lambda), UI-01 (collapsed trace = zero vertical cost), UI-02 (per-flow prewarm gate replaces v2.0 global 3000ms gate), D-04 (4-tool-cap fallback path), `_narrative_source` pattern extension (`_reasoning_trace` or public `reasoning_trace` — API Lambda pass-through contract must be explicit).

### Phase 13.1: AGENT-01 Gap Closure — Latency Short-Circuit + 404 Detection (INSERTED)

**Goal:** Close the two P0 regressions surfaced in 13-VERIFICATION.md — (Gap 1) non-shock personas drop to a 2-tool flow via a prompt SHORT-CIRCUIT RULE in `_BASE_SYSTEM_PROMPT` so warm-p95 for CUST-001/002 lands under the 3000ms per-flow gate (mechanism fix only per D-13.1-02; 2500ms Elena multi-tool gate may remain a verification finding); and (Gap 2) customer-not-found detection restored via a prompt EMPTY BILLING STOP RULE plus a defence-in-depth `plan_id == "UNKNOWN"` sentinel at `api_lambda/handler.py:152`. Ceremony is a scoped 2-stack lift (`CustomerTariffAgent` + `CustomerTariffApi`); `CustomerTariff` foundation untouched per D-13.1-11.
**Requirements**: AGENT-01a, LD-4, D-12 (per CONTEXT.md; ROADMAP entry originally marked TBD)
**Depends on:** Phase 13
**Plans:** 2/5 plans executed

Plans:
- [x] 13.1-01-PLAN.md — Amend `_BASE_SYSTEM_PROMPT` with SHORT-CIRCUIT + EMPTY BILLING STOP clauses (D-13.1-12, D-13.1-14)
- [ ] 13.1-02-PLAN.md — Offline regression guards: `MockedModelProvider(Model)` + `TestShortCircuit` + `TestEmptyBillingStop` + `TestCrossPersonaCanary` shape extension (D-13.1-03/04/09/15)
- [x] 13.1-03-PLAN.md — `api_lambda/handler.py:152` UNKNOWN sentinel + offline handler tests + live 2-tool smoke canary (D-13.1-06/08/13/16)
- [ ] 13.1-04-PLAN.md — 2-stack lift-deploy-refreeze ceremony + byte-equivalence gate + close-gate smokes + prewarm (D-13.1-05/11/17/18/19; autonomous: false)
- [ ] 13.1-05-PLAN.md — CLAUDE.md + DEMO-RUNBOOK.md addenda with post-ceremony latency numbers (D-13.1-20/21)

### Phase 14: Hardship Short-Circuit (AGENT-02)
**Goal**: When a customer record carries `hardship_flag: true`, the agent refuses tariff recommendations via a code-enforced pre-LLM guard and returns a dignity-preserving routing response, without regressing the customer-not-found detection or the D-04 never-500 contract.
**Depends on**: Phase 13 (shares Tools Lambda action dispatcher + `get_hardship_flag` tool)
**Requirements**: AGENT-02, AGENT-02a, AGENT-02b
**Success Criteria** (what must be TRUE):
  1. Lookup of a `hardship_flag: true` customer returns HTTP 200 with a body matching the discriminated-union shape `{ "kind": "hardship", "customer_id": "...", "reason": "...", "routing_target": "hardship_team", "call_script": "..." }` and contains no `green`/`cheapest` keys and no tariff plan IDs anywhere in the body.
  2. `api_lambda/handler.py` customer-not-found detection (current line 152 region) is updated so missing `green`/`cheapest` keys only trigger 404 when `body.get("kind") != "hardship"`; pytest covers both branches — hardship stays 200, genuine fallback stays 404.
  3. Adversarial 10-seed test on the hardship branch asserts zero plan-ID leak, zero recommend/suggest/best-for verbs, and zero banned-term violations in the call_script — D-15 validators apply equally to the hardship narrative surface.
  4. REC-03 contract is preserved on the recommendation branch: pytest asserts `kind: "recommendation"` responses always carry both `green` and `cheapest` tracks; the hardship branch is exempt by schema, not by runtime omission.
  5. Hardship enforcement is code-side: removing the relevant system-prompt hardship instructions and re-running the 10-seed adversarial test still produces zero plan-ID leaks because the pre-LLM guard fires before the model sees tariff context.
**Plans**: TBD
**Invariant ownership**: D-04 never-500 (hardship path returns 200, fallback path still returns 404 via updated detection), REC-03 (amended to condition on `kind == "recommendation"`; non-negotiable on that branch), D-15 banned-terms extended for hardship, `api_lambda/handler.py:152` customer-not-found detection (surgical update, both-branch pytest coverage mandatory).

### Phase 15: Draft Follow-Up Email via AgentCore Memory (WF-01)
**Goal**: Rep can click "Draft follow-up email" after a recommendation and receive an editable draft that references the prior turn's recommendation for the same customer, with zero cross-customer bleed and no breakage of the SC-3 runtimeSessionId invariant.
**Depends on**: Phase 13 + Phase 14 (memorable turn-1 context for same-session continuation)
**Requirements**: WF-01, WF-01a, WF-01b, WF-01c
**Success Criteria** (what must be TRUE):
  1. Second API call `GET /recommendations/{customer_id}/follow-up` within 8 hours of a recommendation lookup for the same customer returns HTTP 200 with a `FollowUpEmailResponse`-shaped body whose `plan_reference` and narrative content clearly reflect the prior turn's recommendation persona (validated via string-match pytest against the Phase 13 fixture recommendation).
  2. Cross-customer isolation smoke test passes: lookup CUST-001 → follow-up CUST-002 → follow-up body for CUST-002 contains zero tokens from the CUST-001 recommendation (no plan IDs, no customer name, no dollar figures from CUST-001).
  3. Code inspection + test confirms `runtimeSessionId = str(uuid.uuid4())` is generated INSIDE `handler()` and `follow_up()` on every invocation (SC-3 preserved), while Memory `session_id = f"{customer_id}-{datetime.now(timezone.utc).date().isoformat()}"` is a separate deterministic key — the two are never conflated.
  4. AgentCore Memory resource is provisioned with TTL in the 8–12h range and no long-term strategies (`memoryStrategies=[]`); same-session turn-1 → turn-2 retrieval works; next-calendar-day retrieval returns empty context.
  5. `requirements.txt` regeneration under `--require-hashes` succeeds with `bedrock-agentcore==1.6.4`; fresh-venv `pip install --require-hashes -r requirements.txt` + full pytest suite both green; FREEZE-MANIFEST lockfile-hash placeholder documented for Phase 17 update.
**Plans**: TBD
**Invariant ownership**: SC-3 runtimeSessionId fresh-uuid4-per-invocation (non-negotiable; Memory session_id is a separate concept, documented at the call site to prevent AP-2 confusion), frozen-lockfile contract (this phase owns the one permitted dep bump — `bedrock-agentcore` 1.6.3 → 1.6.4 — with lockfile regen and freeze evidence update), `_narrative_source` marker contract extended to `_workflow_source` (strip in API Lambda, parallel pattern), `?narrative=off` kill switch extended to collapse the follow-up drawer.

### Phase 16: Presenter Artefacts + Operational Consolidation
**Goal**: Trust-architecture and deferred-roadmap stories are committed to the repo as presenter-ready documents backed by live evidence; demo operations (prewarm, keep-alive, eval harness, `?narrative=off` kill switch) extend to cover the full v3.0 surface with one rehearsal contract.
**Depends on**: Phases 11–15 (architecture decisions must be shipped before they can be documented; operational tooling must exercise the real surface)
**Requirements**: DOC-01, DOC-02, DOC-03, DEMO-07, DEMO-09, DEMO-10
**Success Criteria** (what must be TRUE):
  1. `DOC-01` trust-architecture one-pager exists at `.planning/docs/presenter/TRUST-ARCHITECTURE.md`, cites the SAV-03 / D-15 / fallback-bank / `_narrative_source` / AGENT-02 short-circuit patterns as regulatory-aware architecture (no specific AER/Ofgem clauses cited), and every claim links to a pytest file, CloudWatch metric path, or code reference.
  2. `DOC-02` narrative-tradeoff doc and `DOC-03` deferred-roadmap doc exist under the same directory; DOC-03 references `SalesforceCustomerDataProvider(NotImplementedError)` from Phase 12 as a concrete "in-flight" artefact and frames PROD-02 (customer-facing portal) as "next".
  3. `?narrative=off` in the URL collapses reasoning trace, hardship banner, AND follow-up email drawer to v2.0 shape in both loading and success states — single flag, verified via vitest snapshot at 1280×800 on all three new surfaces.
  4. `scripts/prewarm.py` rotates all five personas (CUST-001 through CUST-005) and exercises the multi-tool route (AGENT-01) plus the follow-up route (WF-01); warm-median gate passes per-flow at 3000ms (single-tool) and 2500ms (multi-tool) with strict 0/1/2 exit taxonomy preserved.
  5. `scripts/demo-keepalive.sh` 10-minute rotation includes the two new personas; `tests/test_narrative_eval_live.py` smoke-gated suite adds canaries for AGENT-01 3-tool determinism, AGENT-02 hardship refusal shape, and WF-01 cross-customer memory isolation — all three pass against the live stack.
**Plans**: TBD
**Invariant ownership**: `?narrative=off` single-flag contract (extended from v2.0 D-10 byte-equivalence), eval-harness smoke marker discipline, DEMO-RUNBOOK cross-links to new presenter artefacts, docs-vs-code drift prevention (claim-check against live evidence).

### Phase 17: v3.0 Freeze Ceremony
**Goal**: v3.0 surface is locked behind a `demo-v3.0` annotated tag with re-applied deny-Update:* stack policies, a fresh FREEZE-MANIFEST with self-consistent commit SHAs, a new DynamoDB backup, and a 5/5 rollback drill — mirroring the v2.0 Phase 10 ceremony exactly.
**Depends on**: Phase 16 (all features shipped, all docs committed, all operational tooling green)
**Requirements**: DEMO-08
**Success Criteria** (what must be TRUE):
  1. `aws cloudformation get-stack-policy` returns byte-equivalent deny-Update:* policies on `CustomerTariff`, `CustomerTariffAgent`, and `CustomerTariffApi`; termination protection re-enabled on all three; verification gate pytest-asserts byte-equality before tag cut.
  2. `demo-v3.0` annotated git tag exists on `main` with WN-2 self-consistency (`git rev-list -n 1 demo-v3.0^ == manifest.freeze_commit_sha`); tag pushed to origin.
  3. `FREEZE-MANIFEST.md` committed under `.planning/milestones/v3.0-phases/` with all D-10-equivalent keys populated: freeze_commit_sha, bedrock_model_id (`us.anthropic.claude-sonnet-4-6`), memory_id, agent_runtime_arn, api_endpoint, lockfile hashes (62+ prod / 33+ dev entries including `bedrock-agentcore==1.6.4`), break-glass block referencing allow-all policy JSON.
  4. DynamoDB freeze backup AVAILABLE (status verified via `aws dynamodb describe-backup`); single-backup-per-milestone invariant held; restore drill spot-check confirms 60 items (5 personas × 12 months) + 5 PROFILE items.
  5. 5/5 rollback drill PASS: `?narrative=off` collapses all v3.0 surfaces to v2.0 shape; `npm run build:mock` produces a dist-mock in <10s; `git checkout demo-v2.0` fresh-clone pytest returns green; DynamoDB restore-from-backup + spot-check passes; scratch teardown clean. T-24h visual rehearsal DevTools-measured warm median per persona under the relevant per-flow gate.
**Plans**: TBD
**Invariant ownership**: Stack-policy freeze ceremony (scripted lift → deploy → verify → re-apply; AP-6 prevention), frozen-lockfile reproducibility gate (post-bedrock-agentcore bump), `--require-hashes` contract, rollback drill as mandatory phase-close gate, atomic commit discipline for FREEZE-MANIFEST updates.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation + Dummy Data | v1.0 | 3/3 | ✓ Complete | 2026-04-23 |
| 2. AgentCore Agent | v1.0 | 3/3 | ✓ Complete | 2026-04-23 |
| 3. Backend API | v1.0 | 3/3 | ✓ Complete | 2026-04-24 |
| 4. Agent-Assist UI | v1.0 | 5/5 | ✓ Complete | 2026-04-24 |
| 5. Demo Hardening | v1.0 | 7/7 | ✓ Complete | 2026-04-25 |
| 6. Agent Narrative + Guardrail | v2.0 | 3/3 | ✓ Complete | 2026-04-25 |
| 6.1. Resolve Sonnet 4.6 tool-use regression | v2.0 | 4/4 | ✓ Complete | 2026-04-25 |
| 7. API Pass-Through + Pre-Warm Route | v2.0 | 2/2 | ✓ Complete | 2026-04-26 |
| 8. UI Integration + Feature Flag + Version Indicator | v2.0 | 4/4 | ✓ Complete | 2026-04-26 |
| 9. Pre-Warm Tooling + Eval Harness + Keep-Alive | v2.0 | 4/4 | ✓ Complete | 2026-04-26 |
| 10. Freeze + Rollback Drill | v2.0 | 3/3 | ✓ Complete | 2026-04-26 |
| 11. New Personas + Tariff Archetypes | v3.0 | 6/6 | Complete    | 2026-04-28 |
| 12. CustomerDataProvider Abstraction | v3.0 | 6/6 | Complete    | 2026-04-29 |
| 13. Bill-Shock Multi-Tool Flow (AGENT-01) | v3.0 | 9/9 | Complete   | 2026-04-29 |
| 14. Hardship Short-Circuit (AGENT-02) | v3.0 | 0/? | Not started | — |
| 15. Draft Follow-Up Email via AgentCore Memory (WF-01) | v3.0 | 0/? | Not started | — |
| 16. Presenter Artefacts + Operational Consolidation | v3.0 | 0/? | Not started | — |
| 17. v3.0 Freeze Ceremony | v3.0 | 0/? | Not started | — |

---
*Roadmap created: 2026-04-23*
*Last updated: 2026-04-28 — v3.0 roadmap derived from REQUIREMENTS.md + research/SUMMARY.md. 7 phases (11–17) mapped from 27 requirement checkboxes per LD-1 build order. Next step: `/gsd-plan-phase 11`.*
