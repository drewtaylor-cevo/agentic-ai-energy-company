# Requirements: Customer Tariff & Billing Optimisation Agent — Milestone v3.0

**Defined:** 2026-04-28
**Milestone:** v3.0 Agentic Depth & Workflow Assist
**Core Value:** A call centre agent can open any customer account and immediately see exactly how much that customer could save and on which plan — making every retention conversation data-driven.
**Milestone Goal:** Move the demo from "structured-output formatting" to a credible AI-agent showcase by adding multi-tool reasoning, regulatory-aware autonomy boundaries, rep-side workflow surfaces, and a production-shaped CRM adapter — while staying on engineered dummy data and shipping the trust-architecture story as committed presenter artefacts.

---

## v3.0 Requirements (in scope)

Continues numbering from v1.0 and v2.0. All validated requirements from v1.0/v2.0 live in `.planning/PROJECT.md` under `## Requirements → Validated`.

### Personas & Data (DATA / REC)

- [ ] **DATA-04**: Seed Solar PV persona (CUST-004) with realistic 12-month billing profile including net-metering (consumption_kwh + export_kwh → net_kwh) shape
- [ ] **DATA-05**: Seed EV persona (CUST-005) with realistic 12-month billing profile reflecting off-peak EV charging time-of-use (TOU) usage shape
- [ ] **DATA-06**: Mark one existing or new persona with `hardship_flag: true` in the customer record so AGENT-02 has a deterministic trigger for the demo
- [ ] **REC-04**: Add Solar Feed-in tariff archetype to `tariff_plans.json` (both `lambda/` and `infrastructure/seed_data/` — byte-equality test must pass)
- [ ] **REC-05**: Add EV Time-of-Use tariff archetype to `tariff_plans.json` (both locations)
- [ ] **DATA-07**: New personas round-trip through existing `simulate_savings_pure` with byte-exact engineered savings figures locked in `tests/conftest.py` fixtures — existing persona figures (Sarah $30/$55, Marcus $16.90/$30.98, Elena $14.00/$25.67) must remain unchanged

### Agentic Depth (AGENT)

- [ ] **AGENT-01**: Bill-shock multi-tool agent flow — agent composes 2-3 tool calls in one turn to explain an engineered bill spike on a designated persona (fetch billing history + fetch rate history + simulate savings); reasoning trace is surfaced to the UI
- [ ] **AGENT-01a**: Warm p95 latency for the multi-tool flow stays under 2500ms target on the deployed runtime (UI-02 <3s lookup-to-rendered contract must not regress for single-tool flows and must hold for multi-tool flows)
- [ ] **AGENT-01b**: Tool-call cap of 4 per agent turn enforced in code (not prompt) — hard limit that short-circuits infinite loops
- [ ] **AGENT-02**: Hardship short-circuit branch — when `hardship_flag` is true, agent returns a hardship response (discriminated union `kind: "recommendation" | "hardship"`) without a tariff recommendation; enforcement is code-side (pre-LLM guard), not prompt-side
- [ ] **AGENT-02a**: `api_lambda/handler.py:152` customer-not-found detection updated to NOT false-positive on hardship responses (missing `green`/`cheapest` keys is expected on `kind: "hardship"`)
- [ ] **AGENT-02b**: D-04 never-500 contract holds for hardship responses — HTTP 200 with hardship body, not 404 or 500

### Workflow Assist (WF)

- [ ] **WF-01**: Draft follow-up email workflow — rep-side action that triggers a second agent turn, using AgentCore Memory to recall the prior turn's recommendations, and returns a draft email body the rep can edit and send
- [ ] **WF-01a**: AgentCore Memory scoped to short-term only for v3.0 — `actorId = f"customer:{customer_id}"`, deterministic `session_id = f"{customer_id}-{UTC-ISO-day}"`, TTL 8–12h (no long-term cross-session retention in v3.0)
- [ ] **WF-01b**: Memory session isolation — cross-customer PII leakage canary test passes (lookup customer A then customer B; customer B turn must not contain any customer A data)
- [ ] **WF-01c**: Deterministic-session invariant preserved — `runtimeSessionId` still generated INSIDE `handler()` (Pitfall 2 / SC-3); the new Memory `session_id` is a separate key and does not conflate with `runtimeSessionId`

### Production Shape (PROD)

- [ ] **PROD-01**: `CustomerDataProvider` Protocol defined at `agent/providers.py` with methods `get_customer`, `get_billing_history`, `get_hardship_flag` (three methods only — no consent/audit/circuit-breaker in v3.0)
- [ ] **PROD-01a**: DynamoDB implementation of the Protocol replaces direct table access in the agent-side call path (tool-side Tools Lambda stays DynamoDB-direct — bi-mode import pattern preserved)
- [ ] **PROD-01b**: InMemory test-double implementation of the Protocol exists and is used by offline tests; existing byte-exact persona savings fixtures in `tests/conftest.py` continue to pass unchanged
- [ ] **PROD-01c**: `NotImplementedError` Salesforce-shaped stub implementation committed as presenter artefact (referenced by DOC-03)

### Presenter Artefacts (DOC)

- [ ] **DOC-01**: Trust-Architecture one-pager committed to repo — framing is "regulatory-aware architecture"; describes LLM-bounding patterns (SAV-03 no-arithmetic invariant, D-15 narrative gauntlet, fallback bank, AGENT-02 hardship short-circuit, `_narrative_source` observability) as patterns the architecture supports; does NOT cite specific AER/Ofgem/state PUC clauses (keeps demo legal-review-free)
- [ ] **DOC-02**: Narrative-tradeoff acknowledgement section — owns the cost-vs-value of LLM-generated narrative honestly; explicit "what you give up when the LLM writes the copy" discussion
- [ ] **DOC-03**: Deferred-roadmap doc — architecture-with-stubs view showing PROD-01 Protocol in-flight with DynamoDB impl live + Salesforce-shaped `NotImplementedError` stub, with PROD-02 (customer-facing portal) framed as "next"

### Demo Operations (DEMO)

- [ ] **DEMO-07**: `?narrative=off` URL kill switch extended to collapse ALL v3.0 UI surfaces (reasoning trace, hardship branch, follow-up email panel) to v2.0 shape — single flag, single rehearsal contract
- [ ] **DEMO-08**: v3.0 freeze ceremony — lift deny-Update:* stack policies on `CustomerTariff` / `CustomerTariffAgent` / `CustomerTariffApi`, redeploy v3.0, re-apply policies, tag `demo-v3.0`, capture fresh FREEZE-MANIFEST
- [ ] **DEMO-09**: Pre-warm and keep-alive scripts extended to cover new personas (CUST-004, CUST-005), the multi-tool flow path (AGENT-01), and the follow-up-email route (WF-01) — warm-median gate still 3000ms on the updated surface
- [ ] **DEMO-10**: Live eval harness (smoke-gated) extended — new canaries for AGENT-01 3-tool flow determinism, AGENT-02 hardship refusal shape, WF-01 memory isolation across customers

---

## Deferred to v3.1 or later

Tracked but not in the v3.0 roadmap.

### Production (PROD)

- **PROD-02**: Customer-facing self-service portal — re-evaluate after v3.0 lands (previously deferred; remains deferred)

### Workflow Assist (WF)

- **WF-02**: Long-term / cross-session AgentCore Memory — retention strategies, TTL configuration, user deletion flow, production consent/PII model. v3.0 uses short-term only
- **WF-03**: Multi-rep handoff Memory — one rep starts a call, another rep picks it up. v3.0 is single-rep

### Agentic (AGENT)

- **AGENT-03**: Typed hardship categories (`payment_difficulty` / `medical` / `family_violence` / `other`) with per-category routing copy. v3.0 uses monolithic `hardship_flag: bool`
- **AGENT-04**: Proactive agent actions (draft-email auto-send, tariff-switch preparation). v3.0 remains rep-confirmed

### Production Shape (PROD)

- **PROD-03**: `CustomerDataProvider` consent flags (`consent_marketing`, `consent_data_share`)
- **PROD-04**: `CustomerDataProvider` audit trail (who accessed what when)
- **PROD-05**: `CustomerDataProvider` circuit breaker for downstream CRM failures

---

## Out of Scope (explicit exclusions)

| Feature | Reason |
|---------|--------|
| Auto-executing tariff switches | Same as v1.0/v2.0 — recommendation only; call centre agent confirms every change. Validated invariant. |
| Third-party / competitor plan comparison | Same as v1.0/v2.0 — internal plan portfolio only |
| Mobile / responsive layout | Same as v1.0/v2.0 — desktop-first (1280px) for call-centre context |
| OAuth / authentication | Still not needed for demo; PROD-02 deferred so this stays out |
| Real-time tariff price feeds | Same as v1.0/v2.0 — static dummy tariff rates sufficient for demo |
| LLM-generated numeric values (savings, dates, percentages) | SAV-03 invariant — code does math, LLM narrates only. Extends to AGENT-01: the multi-tool flow must cite dates and event timestamps sourced from tool output, not LLM-estimated |
| AER/Ofgem/state-PUC compliance claims in presenter docs | DOC-01 framing is "regulatory-aware architecture" only — no specific regulation cited to avoid legal-review gate |
| Bedrock Guardrails as the hardship enforcement primitive | Guardrails is a content filter, not a routing primitive. Hardship short-circuit is code-side (AGENT-02), same reason SAV-03 lives in code not prompt |
| Long-term AgentCore Memory across sessions | Deferred to WF-02. v3.0 is same-day short-term only |
| Typed hardship categories | Deferred to AGENT-03. v3.0 uses monolithic flag |

---

## Locked Decisions (from SUMMARY.md synthesis)

These are load-bearing decisions that ripple into multiple requirements. Changing any forces a requirements re-scope.

| Decision | Value | Rationale |
|----------|-------|-----------|
| **LD-1 Build order** | DATA-04 → PROD-01 → AGENT-01 → AGENT-02 → WF-01 → DOC-* → Freeze | Data-first unblocks tests; adapter-second so new tools land through the abstraction; freeze last |
| **LD-2 Hardship shape** | Pydantic discriminated union `kind: "recommendation" \| "hardship"` | Preserves D-04 (200 not 500) and REC-03 (both tracks on recommendation branch); surgical update to `api_lambda/handler.py:152` required |
| **LD-3 Memory scope** | Short-term only, `actorId = f"customer:{id}"`, `session_id = f"{id}-{UTC-ISO-day}"`, TTL 8–12h | Smallest Memory surface that demonstrates the primitive; cross-customer isolation prevents the session-bleed failure class (Pitfall 2) |
| **LD-4 Latency target** | Warm p95 < 2500ms for AGENT-01; hard 4-tool cap in code | UI-02 <3s contract must not regress; Strands 1.37 `ConcurrentToolExecutor` default on Sonnet 4.6 |
| **LD-5 PROD-01 scope** | Protocol + DynamoDB impl + InMemory impl + NotImplementedError Salesforce stub; 3 methods | Interface-only would be Chesterton's Fence; dual-impl from day 1 forces abstraction to generalise |
| **LD-6 Freeze ceremony** | Dedicated phase; scripted lift → deploy → verify → re-apply; new `demo-v3.0` tag + FREEZE-MANIFEST | 3 of 4 stacks have deny-Update:* — v2.0 ceremony is re-executed, not new territory |
| **LD-7 `?narrative=off`** | Kill switch collapses every v3.0 UI surface to v2.0 shape | Single flag, single rehearsal, single emergency-swap contract extended from v2.0 |

---

## Traceability

Which phases cover which requirements. Filled by gsd-roadmapper during Step 10.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-04 | Phase TBD | Pending |
| DATA-05 | Phase TBD | Pending |
| DATA-06 | Phase TBD | Pending |
| DATA-07 | Phase TBD | Pending |
| REC-04 | Phase TBD | Pending |
| REC-05 | Phase TBD | Pending |
| PROD-01 | Phase TBD | Pending |
| PROD-01a | Phase TBD | Pending |
| PROD-01b | Phase TBD | Pending |
| PROD-01c | Phase TBD | Pending |
| AGENT-01 | Phase TBD | Pending |
| AGENT-01a | Phase TBD | Pending |
| AGENT-01b | Phase TBD | Pending |
| AGENT-02 | Phase TBD | Pending |
| AGENT-02a | Phase TBD | Pending |
| AGENT-02b | Phase TBD | Pending |
| WF-01 | Phase TBD | Pending |
| WF-01a | Phase TBD | Pending |
| WF-01b | Phase TBD | Pending |
| WF-01c | Phase TBD | Pending |
| DOC-01 | Phase TBD | Pending |
| DOC-02 | Phase TBD | Pending |
| DOC-03 | Phase TBD | Pending |
| DEMO-07 | Phase TBD | Pending |
| DEMO-08 | Phase TBD | Pending |
| DEMO-09 | Phase TBD | Pending |
| DEMO-10 | Phase TBD | Pending |

**Coverage:**
- v3.0 requirements (top-level IDs): 12 (DATA-04, DATA-05, DATA-06, DATA-07, REC-04, REC-05, PROD-01, AGENT-01, AGENT-02, WF-01, DOC-01, DOC-02, DOC-03, DEMO-07, DEMO-08, DEMO-09, DEMO-10 — counting grouped IDs as one)
- Sub-requirements (letter-suffixed): 11
- Total checkboxes: 27
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 27 ⚠️ (expected — roadmap step fills these)

---
*Requirements defined: 2026-04-28 at v3.0 milestone start*
*Research synthesized: `.planning/research/SUMMARY.md` (commit `3bc08ab`)*
*Next step: `/gsd-roadmapper` produces ROADMAP.md and back-fills the traceability table.*
