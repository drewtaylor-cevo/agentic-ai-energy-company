# Customer Tariff & Billing Optimisation Agent

## What This Is

An AI-powered call centre agent-assist tool for an Energy & Utilities provider. It analyses a customer's 12-month billing history, recommends the two most optimal tariff plans (Green and Cheapest), and surfaces projected monthly and annual savings — giving call centre agents an instant, personalised savings plan to present while the customer is on the line.

**Current State:** v1.0 MVP shipped 2026-04-25 as `demo-v1.0`. Live AWS stack deployed in `us-east-1` (Bedrock AgentCore Runtime + Lambda + API Gateway HTTP v2 + React/Vite UI) running on engineered dummy data for 3 customer personas. Call centre agent-assist UI renders both recommendation cards above the fold at 1280px with skeleton-first loading.

## Core Value

A call centre agent can open any customer account and immediately see exactly how much that customer could save and on which plan — making every retention conversation data-driven.

**v1.0 review:** Still the right priority. Shipping validated the core value end-to-end — every persona lookup returns two differentiated savings recommendations grounded in the customer's own 12-month usage profile.

## Requirements

### Validated (v1.0)

- ✓ Retrieve and analyse 12 months of billing history per customer — v1.0 (DATA-01)
- ✓ Dummy dataset covers 3+ customer personas with distinct usage profiles — v1.0 (DATA-02)
- ✓ Usage stored in kWh for defensible savings calculations — v1.0 (DATA-03)
- ✓ Recommend the most energy-efficient (Green) tariff plan — v1.0 (REC-01)
- ✓ Recommend the lowest projected cost (Cheapest) tariff plan — v1.0 (REC-02)
- ✓ Surface Green and Cheapest simultaneously, neither ranked above the other — v1.0 (REC-03)
- ✓ Display projected monthly savings against 12-month average — v1.0 (SAV-01)
- ✓ Display annual equivalent saving alongside monthly figure — v1.0 (SAV-02)
- ✓ Savings calculated by deterministic tool function (arithmetic in code, not LLM) — v1.0 (SAV-03)
- ✓ Both cards above the fold at 1280px — v1.0 (UI-01)
- ✓ Lookup-to-rendered under 3 seconds — v1.0 smoke-derived (UI-02); visual T-24h rehearsal confirms at presentation time
- ✓ End-to-end demo runs on dummy data with no live CRM — v1.0 (DEMO-01)
- ✓ Engineered savings delta: Green ~$30/mo, Cheapest ~$55/mo — v1.0 (DEMO-02)

### Active (v2.0 candidates)

Carried forward from v1 Out-of-Scope / v2 requirements in archived REQUIREMENTS.md. Scope to be confirmed at `/gsd-new-milestone`.

- [ ] LLM-generated call script snippet — a one-liner the agent can use verbatim (UI-03)
- [ ] LLM-generated usage narrative — one-sentence customer profile on each card (UI-04)
- [ ] Pre-warm script to avoid cold-start latency on the live demo (DEMO-03)
- [ ] Frozen demo environment with pinned deps + locked AWS state 48h pre-presentation (DEMO-04)
- [ ] Live CRM integration replacing the dummy data source (PROD-01)
- [ ] Customer-facing self-service portal (v2 of the agent-assist tool) (PROD-02)

### Out of Scope

- Auto-switching plans without human confirmation — recommendation only; validated v1.0 (call centre agent confirms before any plan change)
- Third-party / competitor plan comparison — internal plan portfolio only; validated v1.0
- Mobile / responsive layout — desktop-first (1280px) for call centre context; validated v1.0
- OAuth / authentication — not needed for demo; re-evaluate if PROD-02 (customer-facing portal) moves in
- Real-time tariff price feeds — static dummy tariff rates sufficient for demo; re-evaluate with PROD-01

## Context

**Engagement type:** Customer demo / proof of concept for an Energy & Utilities provider.

**Current shipped state (v1.0):**
- ~15.5K LOC total (≈11.5K Python for CDK + Lambda + agent tools, ≈4.0K TypeScript/React for the UI)
- Tech stack: AWS CDK (Python), AWS Bedrock AgentCore Runtime, Strands SDK, Lambda, DynamoDB, API Gateway HTTP v2, React 18 + Vite + shadcn/ui (New York / Slate) + Tailwind
- Live endpoint: `https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/`
- Reproducibility: committed lockfiles (`ui/package-lock.json`, `requirements.txt`, `requirements-dev.txt`) + `build:mock` fallback + captured `ApiEndpoint` — build output is not committed
- 3 personas seeded: high-usage residential, medium-usage, low-usage/seasonal
- Test suite: 81 passed, 6 skipped from a clean virtualenv (`pytest -m "not smoke"`)

**Platform:** AWS Bedrock AgentCore — Personalisation + Decision agent pattern using Strands SDK with `BedrockAgentCoreApp` (chosen over classic Bedrock Agents action groups for simpler iteration and less IAM wiring).

**Data source:** Internal CRM billing history in the target deployment; dummy S3/DynamoDB-backed dataset for the demo. Utility already holds this data — no customer upload required.

**Recommendation design:** Two tracks always presented together — **Green** (most energy-efficient in the portfolio) and **Cheapest** (lowest projected cost). Neither is ranked above the other. The call centre agent (and ultimately the customer) chooses based on their priority.

**Savings simulation:** Projected as ~$X/month against the customer's 12-month billing average, plus annual equivalent. 12 months smooths seasonal variation and is easy to explain to the customer. Arithmetic is deterministic Python; LLM orchestrates and narrates only.

**Demo approach:** Working demo on carefully engineered dummy data — Green $30/mo and Cheapest $55/mo per flagship persona so the delta tells a clear story.

**Demo hook:** "Customer bill → instant personalised savings plan."

**Known pre-presentation work:** DEMO-RUNBOOK §2 T-24h visual presenter rehearsal (DevTools-measured warm-median across all personas) still required. Smoke-derived latency evidence exists (≲2s per request) but is not a substitute for the visual rehearsal.

## Constraints

- **Platform:** AWS Bedrock AgentCore — agent architecture must fit Bedrock's patterns
- **Demo scope:** Dummy data only — no live CRM connectivity in v1.0 (re-evaluated in v2 if PROD-01 is scoped in)
- **Autonomy:** No autonomous plan switching — recommendations surface, humans decide
- **Audience:** Call centre agents are the end user — UX must work within a call context (fast, scannable, actionable)
- **Region:** `us-east-1` locked (Bedrock + AgentCore model availability)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Call centre agent-assist first (not customer-facing) | Reduces scope, controls UX, faster to demo | ✓ Good (v1.0) — panel delivered against UI-01/UI-02 |
| Two fixed recommendation tracks (Green / Cheapest) | Keeps the recommendation scannable; avoids decision paralysis | ✓ Good (v1.0) — both cards above the fold, neither ranked |
| 12-month billing window for savings simulation | Smooths seasonal variation; easy to explain to the customer | ✓ Good (v1.0) — pytest locks DEMO-02 deltas across personas |
| Recommendation-only (no auto-switching) | Trust and compliance — human confirms before any plan change | ✓ Good (v1.0) — matches call centre workflow |
| Dummy data for demo | Controls the narrative; no integration risk for the POC | ✓ Good (v1.0) — no-CRM structural audit (05-04) passed |
| Strands SDK / `BedrockAgentCoreApp` pattern | Simpler iteration, fewer IAM wiring steps than classic Bedrock Agents | ✓ Good (v1.0) — single AgentCore stack, live smoke passes |
| kWh-based billing records (not dollars) | Defensible savings that survive customer scrutiny on a call | ✓ Good (v1.0) — savings independently recalculable |
| 5-phase bottom-up build order | Data → tools → agent → API → UI; every gate held | ✓ Good (v1.0) |
| DEMO-02 assigned to Phase 1 | Savings delta engineered into dummy data before any agent work | ✓ Good (v1.0) — flagship $30/$55 locked pre-agent |
| Phase 3 live deploy deferred to Phase 5 | Stack lands on AWS once, cleanly, behind the `demo-v1.0` tag | ✓ Good (v1.0) — single `cdk deploy` in 05-02, no thrash |
| Dual production dists (primary + mock fallback) | D-07 <10s emergency swap gate without network dependency | ✓ Good (v1.0) — both dists regeneratable from committed sources |
| Don't commit build output (`ui/dist/`) | Reproducibility from sources, not artefacts | ✓ Good (v1.0) — reproducibility gate validates regeneration |
| Smoke-derived rehearsal substituted for D-14/D-15 visual rehearsal at phase close | Avoided fabricating DevTools numbers; scheduled visual at T-24h per DEMO-RUNBOOK | ⚠️ Revisit at T-24h — if warm median exceeds 3000ms on any persona, it becomes a gap against UI-02 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

## Previous Milestones

<details>
<summary>v1.0 MVP — shipped 2026-04-25</summary>

See [`.planning/MILESTONES.md`](MILESTONES.md#v10-mvp--shipped-2026-04-25) for full summary and archived artefacts:
- [`.planning/milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md)
- [`.planning/milestones/v1.0-REQUIREMENTS.md`](milestones/v1.0-REQUIREMENTS.md)
- [`.planning/milestones/v1.0-phases/`](milestones/v1.0-phases/)
- Git tag: `demo-v1.0` (commit `aba3a99`)

</details>

---
*Last updated: 2026-04-25 after v1.0 MVP milestone close (tagged `demo-v1.0`)*
