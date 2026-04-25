---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Demo Polish & LLM Narrative
status: executing
stopped_at: Phase 6 context gathered
last_updated: "2026-04-25T06:08:28.894Z"
last_activity: 2026-04-25 -- Phase 06 execution started
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 3
  completed_plans: 2
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-25 at v2.0 milestone start)

**Core value:** A call centre agent can open any customer account and immediately see exactly how much that customer could save and on which plan — making every retention conversation data-driven.
**Current focus:** Phase 06 — agent-narrative-guardrail

## Current Position

Phase: 06 (agent-narrative-guardrail) — EXECUTING
Plan: 1 of 3
Next: `/gsd-plan-phase 6`
Status: Executing Phase 06
Last activity: 2026-04-25 -- Phase 06 execution started

Progress: [          ] 0% (0/5 phases complete)

## v2.0 Phase Structure

| Phase | Name | Requirements | Depends on |
|-------|------|--------------|------------|
| 6 | Agent Narrative + Guardrail | UI-03 (backend), UI-04 (backend), UI-05 | v1.0 shipped stack |
| 7 | API Pass-Through + Pre-Warm Route | DEMO-03 (plumbing) | Phase 6 |
| 8 | UI Integration + Feature Flag + Version Indicator | UI-03 (UI), UI-04 (UI), UI-06, UI-07, UI-08 | Phase 7 |
| 9 | Pre-Warm Tooling + Eval Harness + Keep-Alive | DEMO-03 (complete), DEMO-05 | Phase 7 |
| 10 | Freeze + Rollback Drill | DEMO-04, DEMO-06 | Phases 6–9 |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. v1.0-era decisions preserved there with ✓ Good / ⚠️ Revisit markers. Full v1.0 decision log: see `.planning/milestones/v1.0-ROADMAP.md` Key Decisions section.

v2.0-specific decisions locked at requirements stage (see REQUIREMENTS.md):

- Narrative generation strategy: same-turn Claude 3.7 Sonnet (Option A) — single Bedrock call, smallest freeze surface
- Keep-alive: ship `scripts/demo-keepalive.sh`; honest-framing recovery is the secondary net
- Rollback mechanism: `?narrative=off` flag + `demo-v1.0` tag + `build:mock` dist (drilled at T-48h)
- No interim `demo-v1.1` tag — feature flag covers the common failure mode

### Pending Todos

None.

### Blockers/Concerns

**Pre-demo (carry-forward from v1.0, required before any live presentation):**

- **T-24h visual rehearsal:** Chrome DevTools-measured 2-pass rehearsal per DEMO-RUNBOOK §2 T-24h. Every persona warm median must stay <3000ms; if not, treat as a gap against UI-02.
- **Discipline commitment (D-13):** AWS resources are "don't touch" between the `demo-v2.0` tag and the demo.

**v2.0-specific (must remain true through the milestone):**

- UI-01 (both cards above fold at 1280px) must stay satisfied with narratives at max generated length.
- UI-02 (<3s lookup-to-rendered) must stay satisfied — primary risk is latency stacking from the extra ~80 output tokens per card.
- Narrative outputs must never contain digits or currency symbols — enforced by the Pydantic `field_validator` delivered in Phase 6.

## Deferred Items

v1.0-close carry-forwards, resolved at v2.0 start:

| Category | Item | Status | Resolved At |
|----------|------|--------|-------------|
| v2.0 | UI-03: LLM-generated call script snippet | In scope (Phase 6/8) | 2026-04-25 (v2.0 roadmap) |
| v2.0 | UI-04: LLM-generated usage narrative | In scope (Phase 6/8) | 2026-04-25 (v2.0 roadmap) |
| v2.0 | UI-05: Narrative-output validator | In scope (Phase 6) | 2026-04-25 (v2.0 roadmap) |
| v2.0 | UI-06: `?narrative=off` feature flag | In scope (Phase 8) | 2026-04-25 (v2.0 roadmap) |
| v2.0 | UI-07: Version indicator | In scope (Phase 8) | 2026-04-25 (v2.0 roadmap) |
| v2.0 | UI-08: Skeleton-first narrative render | In scope (Phase 8) | 2026-04-25 (v2.0 roadmap) |
| v2.0 | DEMO-03: Pre-warm script | In scope (Phase 7/9) | 2026-04-25 (v2.0 roadmap) |
| v2.0 | DEMO-04: Frozen environment lock (48hr pre-presentation) | In scope (Phase 10) | 2026-04-25 (v2.0 roadmap) |
| v2.0 | DEMO-05: Keep-alive script | In scope (Phase 9) | 2026-04-25 (v2.0 roadmap) |
| v2.0 | DEMO-06: Rollback drill | In scope (Phase 10) | 2026-04-25 (v2.0 roadmap) |
| v3.0 | PROD-01: Live CRM integration | Deferred to v3.0 | 2026-04-25 (v2.0 start) |
| v3.0 | PROD-02: Customer-facing self-service portal | Deferred to v3.0 | 2026-04-25 (v2.0 start) |

Non-blocking carry-forwards from v1.0 phase VERIFICATIONs (see `milestones/v1.0-phases/05-demo-hardening/05-VERIFICATION.md` Gaps Summary):

- Phase 4 WR-01 / IN-01 / IN-02 — orchestrator-accepted non-blockers
- Phase 5 visual rehearsal — scheduled at T-24h per DEMO-RUNBOOK

## Session Continuity

Last session: --stopped-at
Stopped at: Phase 6 context gathered
Resume file: --resume-file

**Environment lock (v1.0 carry-forward):** `demo-v1.0` annotated git tag on main

- Tagged commit: `aba3a99c67994f39d9d496ddfd29c9116b756928`
- Tag object: `3bb0f51380176deedd1712d5dee17a70ccd94887`
- Push to origin: skipped (local-only, no origin configured)

**Suggested next commands:**

- `/gsd-plan-phase 6` — decompose Phase 6 (Agent Narrative + Guardrail) into executable plans
- `/gsd-research-phase 6` — optional deeper research flagged by SUMMARY.md (Strands `structured_output` retry-on-`ValidationError` behaviour, Pydantic v2 confirmation)

**Planned Phase:** 6 (Agent Narrative + Guardrail) — 3 plans — 2026-04-25T05:12:35.322Z
