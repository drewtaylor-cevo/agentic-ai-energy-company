---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Agentic Depth & Workflow Assist
status: executing
stopped_at: Phase 14 planning complete
last_updated: "2026-05-03T00:00:00.000Z"
last_activity: 2026-05-03 -- Phase 13.1 verified complete; Phase 14 planned (5 plans)
progress:
  total_phases: 8
  completed_phases: 4
  total_plans: 31
  completed_plans: 26
  percent: 84
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-28 at v3.0 milestone start)

**Core value:** A call centre agent can open any customer account and immediately see exactly how much that customer could save and on which plan — making every retention conversation data-driven.
**Current focus:** Phase 13.1 — agent-01-gap-closure-latency-short-circuit-404-detection

## Current Position

Phase: 14 (hardship-short-circuit-agent-02) — PLANNED
Plan: 0 of 5
Status: Plans decomposed, ready for execution
Last activity: 2026-05-03 -- Phase 14 planned (5 plans: model+guard, tests, API lambda, UI, ceremony)

### Phase 13 Outstanding Gaps (for Phase 13.1)

- **Gap 1 (P0, AGENT-01a):** Warm latency gate fails 5.7-7.9× — CUST-001 17.2s vs 3000ms, CUST-003 19.7s vs 2500ms. Root cause: Plan 03 preference-ordered prompt causes 3-tool flow on all personas.
- **Gap 2 (P0, D-12):** 404 unknown-customer detection broken — curl /recommendations/CUST-999 returns HTTP 200 with synthetic UNKNOWN tracks. `api_lambda/handler.py:152` detection no longer fires because agent composes full RecommendationResponse with UNKNOWN placeholder tracks.

### Phase 13 Deployed State

- Runtime: `tariff_agent-O2Hai86N8V` v12 (container `sha256:15bb94c16f8f55bb70954da9f0fe3bcd235c855cadd3f369c9dbb77d47bc618d`)
- Pre-ceremony HEAD: b45b843 | Final HEAD: 56440032e9f45a73097d9392744e608f0a2e34ae
- All 3 stacks back to Deny + TP=True; SAV-03 byte-equivalence preserved.

## v3.0 Phase Structure

| Phase | Name | Requirements | Depends on |
|-------|------|--------------|------------|
| 11 | New Personas + Tariff Archetypes | DATA-04, DATA-05, DATA-06, DATA-07, REC-04, REC-05 | v2.0 frozen stack (`demo-v2.0`) |
| 12 | CustomerDataProvider Abstraction | PROD-01, PROD-01a, PROD-01b, PROD-01c | Phase 11 |
| 13 | Bill-Shock Multi-Tool Flow (AGENT-01) | AGENT-01, AGENT-01a, AGENT-01b | Phase 11 + Phase 12 |
| 14 | Hardship Short-Circuit (AGENT-02) | AGENT-02, AGENT-02a, AGENT-02b | Phase 13 (shares Tools Lambda action dispatcher + `get_hardship_flag` tool) |
| 15 | Draft Follow-Up Email via AgentCore Memory (WF-01) | WF-01, WF-01a, WF-01b, WF-01c | Phase 13 + Phase 14 (memorable turn-1 context) |
| 16 | Presenter Artefacts + Operational Consolidation | DOC-01, DOC-02, DOC-03, DEMO-07, DEMO-09, DEMO-10 | Phases 11–15 (docs summarise shipped architecture; ops tooling exercises real surface) |
| 17 | v3.0 Freeze Ceremony | DEMO-08 | Phase 16 |

## v2.0 Phase Structure

| Phase | Name | Requirements | Depends on |
|-------|------|--------------|------------|
| 6 | Agent Narrative + Guardrail | UI-03 (backend), UI-04 (backend), UI-05 | v1.0 shipped stack |
| 7 | API Pass-Through + Pre-Warm Route | DEMO-03 (plumbing) | Phase 6 |
| 8 | UI Integration + Feature Flag + Version Indicator | UI-03 (UI), UI-04 (UI), UI-06, UI-07, UI-08 | Phase 7 |
| 9 | Pre-Warm Tooling + Eval Harness + Keep-Alive | DEMO-03 (complete), DEMO-05 | Phase 7 |
| 10 | Freeze + Rollback Drill | DEMO-04, DEMO-06 | Phases 6–9 |

## Accumulated Context

### Roadmap Evolution

- Phase 06.1 inserted after Phase 6: Resolve Sonnet 4.6 tool-use regression (DEMO-02) (URGENT)
- v3.0 roadmap added 2026-04-28: 7 phases (11–17) derived from 27 requirement checkboxes per LD-1 build order
- Phase 13.1 inserted after Phase 13: AGENT-01 Gap Closure — Latency Short-Circuit + 404 Detection (URGENT)

### Locked Decisions (v3.0)

Load-bearing decisions from REQUIREMENTS.md §Locked Decisions + research/SUMMARY.md. Changing any forces a requirements re-scope.

- **LD-1 Build order:** DATA-04 → PROD-01 → AGENT-01 → AGENT-02 → WF-01 → DOC-* → Freeze. Data-first unblocks tests; adapter-second so new tools land through the abstraction; freeze last.
- **LD-2 Hardship shape:** Pydantic discriminated union `kind: "recommendation" | "hardship"`. Preserves D-04 (200 not 500) and REC-03 (both tracks on recommendation branch); surgical update to `api_lambda/handler.py:152` required.
- **LD-3 Memory scope:** Short-term only, `actorId = f"customer:{id}"`, `session_id = f"{id}-{UTC-ISO-day}"`, TTL 8–12h.
- **LD-4 Latency target:** Warm p95 < 2500ms for AGENT-01; hard 4-tool cap in code (not prompt).
- **LD-5 PROD-01 scope:** Protocol + DynamoDB impl + InMemory impl + NotImplementedError Salesforce stub; 3 methods only (no consent/audit/circuit-breaker).
- **LD-6 Freeze ceremony:** Dedicated phase; scripted lift → deploy → verify → re-apply; new `demo-v3.0` tag + FREEZE-MANIFEST.
- **LD-7 `?narrative=off`:** Kill switch collapses every v3.0 UI surface to v2.0 shape — single flag, single rehearsal.

### Invariants the v3.0 roadmap must preserve

Every phase owns preventing specific invariant regressions (see ROADMAP.md Phase Details "Invariant ownership" lines):

- **SAV-03** LLM never does arithmetic — extended in Phase 13 to cover every new arithmetic tool (`detect_bill_shock_pure`, `get_hardship_flag_pure`, TOU math). Cross-persona canary + latency-floor witness mandatory.
- **REC-03** both tracks always returned on recommendation branch — amended in Phase 14 to condition on `kind == "recommendation"`; non-negotiable on that branch.
- **D-04** never-500 — Phase 14 hardship branch returns HTTP 200, not 404 or 500; Phase 13 4-tool-cap fallback path returns graceful fallback, not 500.
- **D-15** narrative dual-gate (≤20 word / ≤22 word validators + salvage + fallback bank) — extended in Phases 13/14/15 to cover reasoning-trace surface (Phase 13), hardship narrative (Phase 14), and follow-up email body (Phase 15; longer-form validator acceptable if pre-committed).
- **`_narrative_source` marker contract** — stripped by API Lambda; extended in Phase 13 (`reasoning_trace` — public, pass-through) and Phase 15 (`_workflow_source` — internal, strip).
- **`runtimeSessionId` generated INSIDE `handler()`** (SC-3) — Phase 15 preserves this; Memory `session_id` is a SEPARATE deterministic key, never conflated. Documented at the call site per AP-2 prevention.
- **Bi-mode imports in `agent/agent.py`** — Phase 12 `agent/providers.py` must follow the same `try: from providers … except: from agent.providers …` pattern.
- **`api_lambda/handler.py:152` customer-not-found detection** — Phase 14 surgical update: `if "green" not in body and body.get("kind") != "hardship": return 404`. Both branches pytest-covered mandatory.
- **Frozen lockfile contract (`--require-hashes`)** — Phase 15 owns the single permitted dep bump (`bedrock-agentcore` 1.6.3 → 1.6.4) with lockfile regen and FREEZE-MANIFEST hash-update evidence for Phase 17.
- **Stack-policy lift ceremony** — Phases 11, 12, 13, 14, 15 each touch at least one of the three frozen stacks (`CustomerTariff`, `CustomerTariffAgent`, `CustomerTariffApi`). Phase 17 re-executes the full v2.0 Phase 10 freeze pattern (scripted lift → verify deploy → byte-equality re-apply).

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. v1.0/v2.0-era decisions preserved there with ✓ Good / ⚠️ Revisit markers. Full v2.0 decision log: see `.planning/milestones/v2.0-ROADMAP.md` Key Decisions section.

v3.0-specific decisions locked at requirements stage (see REQUIREMENTS.md):

- LD-1 through LD-7 (above) — load-bearing cross-cutting decisions
- Phase 15 owns the `bedrock-agentcore` 1.6.3 → 1.6.4 dependency bump; lockfile regeneration via `pip-compile` + `--require-hashes` verification gate; FREEZE-MANIFEST lockfile-hash placeholder handed to Phase 17 for final freeze evidence
- DOC-01 framing deliberately avoids citing specific AER/Ofgem/state-PUC clauses ("regulatory-aware architecture" framing) to keep the demo legal-review-free per SUMMARY.md open-question 3

### Pending Todos

None. Awaiting `/gsd-plan-phase 11` to begin Phase 11 decomposition.

### Blockers/Concerns

**Pre-demo (carry-forward from v1.0/v2.0, required before any live presentation):**

- **T-24h visual rehearsal:** Chrome DevTools-measured 2-pass rehearsal per DEMO-RUNBOOK §2 T-24h. Every persona warm median must stay under the relevant per-flow gate (3000ms single-tool, 2500ms multi-tool AGENT-01). If not, treat as a gap against UI-02 / AGENT-01a.
- **Discipline commitment (D-13):** AWS resources are "don't touch" between the `demo-v3.0` tag (once cut) and the demo.

**v3.0-specific (must remain true through the milestone):**

- UI-01 (both cards above fold at 1280px) must stay satisfied with `ReasoningTrace` collapsed by default and `HardshipBanner` replacing (not stacking above) the card grid.
- UI-02 (<3s lookup-to-rendered) must stay satisfied — primary risk is AGENT-01 multi-tool latency stacking (~400–900ms over v2.0 single-tool path). Mitigated by Strands 1.37 `ConcurrentToolExecutor` default + per-flow prewarm gate + 4-tool cap.
- Cross-customer memory bleed (Pitfall C4) is the single most catastrophic failure mode — live isolation smoke test is a mandatory Phase 15 close gate.
- Narrative outputs on hardship + follow-up surfaces must pass the same D-15 gauntlet (no digits, no currency symbols, no switch verbs, no plan IDs on hardship branch).

## Deferred Items

v2.0-close carry-forwards resolved at v3.0 start:

| Category | Item | Status | Resolved At |
|----------|------|--------|-------------|
| v3.0 | PROD-01: Live CRM integration | In scope (Phase 12 — Protocol + DynamoDB demo impl + Salesforce NotImplementedError stub) | 2026-04-28 (v3.0 roadmap) |
| v3.0 | DATA-04 Solar PV persona | In scope (Phase 11) | 2026-04-28 (v3.0 roadmap) |
| v3.0 | DATA-05 EV persona | In scope (Phase 11) | 2026-04-28 (v3.0 roadmap) |
| v3.0 | REC-04 Solar Feed-in tariff | In scope (Phase 11) | 2026-04-28 (v3.0 roadmap) |
| v3.0 | REC-05 EV TOU tariff | In scope (Phase 11) | 2026-04-28 (v3.0 roadmap) |
| v3.0 | AGENT-01 Bill-shock multi-tool flow | In scope (Phase 13) | 2026-04-28 (v3.0 roadmap) |
| v3.0 | AGENT-02 Hardship short-circuit | In scope (Phase 14) | 2026-04-28 (v3.0 roadmap) |
| v3.0 | WF-01 Draft follow-up email | In scope (Phase 15) | 2026-04-28 (v3.0 roadmap) |
| v3.0 | DOC-01/02/03 Presenter artefacts | In scope (Phase 16) | 2026-04-28 (v3.0 roadmap) |
| v3.0 | DEMO-07 `?narrative=off` extended | In scope (Phase 16) | 2026-04-28 (v3.0 roadmap) |
| v3.0 | DEMO-08 Freeze ceremony | In scope (Phase 17) | 2026-04-28 (v3.0 roadmap) |
| v3.0 | DEMO-09 Prewarm + keep-alive extensions | In scope (Phase 16) | 2026-04-28 (v3.0 roadmap) |
| v3.0 | DEMO-10 Eval harness extensions | In scope (Phase 16) | 2026-04-28 (v3.0 roadmap) |
| v3.1+ | PROD-02: Customer-facing self-service portal | Remains deferred | 2026-04-28 (v3.0 requirements) |
| v3.1+ | WF-02/03, AGENT-03/04, PROD-03/04/05 | Deferred (see REQUIREMENTS.md §Deferred to v3.1 or later) | 2026-04-28 |

### v2.0 Close Deferrals (acknowledged 2026-04-26 at milestone close)

User acknowledged and deferred during `/gsd-complete-milestone v2.0`:

| Category | Item | Status | Rationale |
|----------|------|--------|-----------|
| UAT gap | 07-HUMAN-UAT.md | partial (3 pending scenarios) | Demo-day visual checks — operator will perform at T-24h rehearsal per DEMO-RUNBOOK §2 |
| UAT gap | 09-HUMAN-UAT.md | partial (3 pending scenarios) | Live-stack D-22 gates — Phase 10 D-22 closeout PASSED 15/15 VALIDATION rows live against AWS, effectively satisfying these |
| Verification gap | 07-VERIFICATION.md | human_needed | Demo-day UI + API observation; freeze-ceremony reconciliation deploy exercised the Phase 7-02 alias path live |
| Verification gap | 08-VERIFICATION.md | human_needed | Demo-day visual rehearsal per DEMO-RUNBOOK §2 |
| Verification gap | 09-VERIFICATION.md | human_needed | Live-stack gates validated by Phase 10 ceremony pytest 189/34 + `cdk diff==0` |

Total: 5 items (2 UAT gaps, 3 verification gaps). Resolution path: `/gsd-verify-work 07`, `/gsd-verify-work 08`, `/gsd-verify-work 09` during T-24h rehearsal.

## Session Continuity

Last session: 2026-04-29T13:45:47.825Z
Stopped at: Phase 13.1 context gathered
Resume file: .planning/phases/13.1-agent-01-gap-closure-latency-short-circuit-404-detection/13.1-CONTEXT.md

**Environment lock (v2.0 carry-forward):** `demo-v2.0` annotated git tag on main (3 stacks frozen via deny-Update:* + termination protection; `CustomerTariffFrontend` / Amplify is unfrozen).

**Suggested next commands:**

- `/gsd-plan-phase 11` — Decompose Phase 11 (New Personas + Tariff Archetypes) into executable plans
- Before Phase 11 live work, export env: `export AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V AWS_DEFAULT_REGION=us-east-1 AWS_PROFILE=cevo-dev25`

**Planned Phase:** 11 (New Personas + Tariff Archetypes) — plans TBD — awaiting `/gsd-plan-phase 11`
