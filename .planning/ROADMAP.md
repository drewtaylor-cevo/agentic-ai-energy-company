# Roadmap: Customer Tariff & Billing Optimisation Agent

## Overview

Build a call centre agent-assist demo that turns a customer account lookup into an instant, personalised tariff savings recommendation. The work proceeds strictly bottom-up: dummy data designed before the agent is written, the agent verified before the API is wired, the API proven before the UI is built, and the full stack rehearsed before any live presentation. Five phases, each with a hard gate before the next begins.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation + Dummy Data** - AWS infrastructure, CDK skeleton, and engineered dummy data for 3+ customer personas (completed 2026-04-23)
- [x] **Phase 2: AgentCore Agent** - Strands SDK agent with deterministic savings tools, verified against all demo personas (completed 2026-04-23)
- [x] **Phase 3: Backend API** - Lambda + API Gateway proxy that serves the full self-contained demo stack (completed 2026-04-24; live deploy deferred to Phase 5)
- [x] **Phase 4: Agent-Assist UI** - React + Vite call centre panel with two recommendation cards above the fold (completed 2026-04-24)
- [x] **Phase 5: Demo Hardening** - End-to-end persona rehearsal, performance validation, and environment lock (completed 2026-04-25; tagged `demo-v1.0`)

## Phase Details

### Phase 1: Foundation + Dummy Data
**Goal**: AWS infrastructure is standing and engineered dummy data drives correct, defensible savings calculations without any AI involvement
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DEMO-02
**Success Criteria** (what must be TRUE):
  1. Given a customer ID, `get_billing_history` returns 12 months of kWh usage and cost data for that customer with no AI in the call path
  2. `simulate_savings` computes correct Green and Cheapest savings figures in code — the Green track saves ~$30/month and Cheapest saves ~$55/month for the flagship persona, verified against a spreadsheet
  3. At least 3 customer personas exist in S3 with meaningfully different usage profiles (high-usage, mid-usage, low-usage or seasonal-heavy)
  4. All billing records store usage in kWh so that a savings figure can be independently recalculated and defended on a call
**Plans**: 3 plans
- [x] 01-01-PLAN.md — CDK scaffold, tariff catalog JSON (4 plans at verified rates), and 36-record billing seed module (3 personas x 12 months, Python + DynamoDB wire format)
- [x] 01-02-PLAN.md — Lambda handler with simulate_savings_pure + get_billing_history, TDD pytest suite (29 tests) proving DEMO-02 flagship targets $30/$55 and V5 input validation
- [x] 01-03-PLAN.md — CDK constructs (BillingTable, ToolsLambda, Seeder) + FoundationStack wiring + offline synth tests + post-deploy smoke tests with human-verified cdk deploy

### Phase 2: AgentCore Agent
**Goal**: The Strands SDK agent orchestrates tool calls correctly and returns accurate Green and Cheapest recommendations for every demo persona
**Depends on**: Phase 1
**Requirements**: REC-01, REC-02, REC-03, SAV-01, SAV-02, SAV-03
**Success Criteria** (what must be TRUE):
  1. A direct `invoke_agent_runtime` call for any demo persona returns both a Green recommendation and a Cheapest recommendation simultaneously — neither is ranked above the other
  2. Each recommendation card carries a projected monthly saving in dollars and an annual equivalent figure, both computed by the deterministic `simulate_savings` tool (not by the LLM)
  3. The agent selects the most energy-efficient plan as Green and the lowest projected cost plan as Cheapest for each persona's usage pattern
  4. Savings figures for all 3+ personas pass manual verification — cheapest savings are always greater than or equal to green savings
**Plans**: 3 plans
- [x] 02-01-PLAN.md — Agent source code (Strands @tool + BedrockAgentCoreApp + Pydantic schema), Dockerfile (linux/arm64), and offline test suite (tool shape + savings invariants)
- [x] 02-02-PLAN.md — CDK infrastructure (SSM cross-stack wiring, AgentCoreStack with L2 Runtime construct, IAM policies, offline synth tests)
- [x] 02-03-PLAN.md — Deploy both stacks + live smoke tests via invoke_agent_runtime for all 3 personas (human-verify checkpoint)

### Phase 3: Backend API
**Goal**: A Lambda + API Gateway endpoint accepts a customer ID and returns streaming recommendations, making the demo fully self-contained with no live CRM dependency
**Depends on**: Phase 2
**Requirements**: DEMO-01
**Success Criteria** (what must be TRUE):
  1. A curl or Postman call to the API endpoint with any demo persona's customer ID returns the correct streaming recommendation — no live CRM, no external data source required
  2. Error cases are handled gracefully: customer not found returns a clear error; agent timeout surfaces a user-friendly message rather than a raw exception
  3. Each customer lookup generates a fresh session ID — no recommendation bleed between consecutive persona lookups
**Plans**: 3 plans
- [x] 03-01-PLAN.md — API Lambda handler (D-12 error taxonomy, D-11 fresh uuid4 session, botocore 25s timeout) + 24-case offline unit test suite
- [x] 03-02-PLAN.md — CDK infrastructure (AgentCoreStack SSM amendment, BackendApiConstruct: Lambda + HTTP API v2 + CORS + IAM, BackendApiStack, 11 synth tests)
- [x] 03-03-PLAN.md — Smoke test file written; live cdk deploy deferred to Phase 5 demo hardening

### Phase 4: Agent-Assist UI
**Goal**: A call centre agent can open the panel, enter a customer ID, and read both recommendation cards within a single screen without scrolling
**Depends on**: Phase 3
**Requirements**: UI-01, UI-02
**Success Criteria** (what must be TRUE):
  1. Both the Green recommendation card and the Cheapest recommendation card are visible above the fold on a 1280px desktop display — a call centre agent does not need to scroll during a live call
  2. From entering a customer ID to both cards fully rendered takes under 3 seconds (loading skeleton states are shown immediately so the screen is never blank)
  3. Each card displays the plan name, projected monthly saving, annual equivalent, and a one-line savings methodology note
**Plans**: 5 plans
Plans:
- [x] 04-01-PLAN.md — Toolchain setup: shadcn/ui New York/Slate init, Tailwind, Vitest + testing-library, 7 shadcn components, scaffold cleanup, env files, UI-SPEC D-11 amendment
- [x] 04-02-PLAN.md — Foundation modules: TypeScript types (mirror backend schema), validate.ts (regex + normalize), errors.ts (status-to-copy map), personas.ts, mock fixture + unit tests
- [x] 04-03-PLAN.md — Data layer hook: useRecommendations with fetch/mock-fallback/abort/validation + comprehensive unit tests
- [x] 04-04-PLAN.md — UI components: RecommendationCard, LookupForm, PersonaChips, ErrorAlert, EmptyState, RecommendationSkeletons
- [x] 04-05-PLAN.md — App.tsx composition wiring all components + production build + 1280px smoke verification (human checkpoint)

### Phase 5: Demo Hardening
**Goal**: The end-to-end demo runs cleanly for all planned personas under realistic conditions and the environment is locked before any presentation
**Depends on**: Phase 4
**Requirements**: (covered by DEMO-01 already delivered in Phase 3 — this phase validates the integrated whole)
**Success Criteria** (what must be TRUE):
  1. The full persona sequence (all 3+ customers) can be walked end-to-end in the demo environment without a single failure, blank screen, or incorrect savings figure
  2. Total latency from customer ID entry to cards rendered is measured and confirmed under 3 seconds for all personas — not just the flagship customer
  3. The demo environment runs on dummy data with no live CRM connectivity confirmed by disabling any external data access and re-running all personas
**Plans**: 7 plans
Plans:
- [x] 05-01-PLAN.md — Pre-deploy readiness: blocker confirmation, SSM amendment verification, lockfile+synth dry-run
- [x] 05-02-PLAN.md — Live deploy all 3 stacks + CfnOutput capture into 05-DEPLOY-OUTPUTS.md + live curl+AgentCore smoke
- [x] 05-03-PLAN.md — Dual production dists (primary ui/dist/ against live endpoint + fallback ui/dist-mock/ for emergency swap)
- [x] 05-04-PLAN.md — No-CRM structural audit + 05-VERIFICATION.md skeleton (D-16 code-path audit, grep commands re-runnable)
- [x] 05-05-PLAN.md — Rehearsal (smoke-derived; visual T-24h scheduled) + latency evidence appended to 05-VERIFICATION.md
- [x] 05-06-PLAN.md — DEMO-RUNBOOK.md (D-17 six sections + D-19 T-24h/T-2h/T-0 checklist + presenter cheat sheet)
- [x] 05-07-PLAN.md — Environment lock: reproducibility gate + git tag demo-v1.0 + final VERIFICATION.md lock section

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation + Dummy Data | 3/3 | Complete | 2026-04-23 |
| 2. AgentCore Agent | 3/3 | Complete | 2026-04-23 |
| 3. Backend API | 3/3 | Complete (deploy deferred) | 2026-04-24 |
| 4. Agent-Assist UI | 5/5 | Complete | 2026-04-24 |
| 5. Demo Hardening | 7/7 | Complete (tagged demo-v1.0) | 2026-04-25 |

---
*Roadmap created: 2026-04-23*
*Last updated: 2026-04-25 after phase 5 execution complete (tagged demo-v1.0)*
