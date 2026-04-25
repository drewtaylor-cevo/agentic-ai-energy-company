---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Demo Polish & LLM Narrative
status: Phase 06.1 Plan 02 complete — Strands 1.37.0 migrated agent deployed to us-east-1; stable AgentRuntimeArn preserved; READY for Plan 03 live canaries
stopped_at: Phase 06.1 Plan 02 deployed — awaiting Plan 03 live canary runs
last_updated: "2026-04-25T10:54:31Z"
last_activity: 2026-04-25 -- Phase 06.1 Plan 02 executed; D-10 Gate 1 + Gate 2 passed locally; cdk deploy CustomerTariffAgent succeeded (24.95s); stable ARN preserved; runtime READY
agent_runtime_arn: arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V
agent_runtime_region: us-east-1
agent_runtime_aws_profile: cevo-dev25
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-25 at v2.0 milestone start)

**Core value:** A call centre agent can open any customer account and immediately see exactly how much that customer could save and on which plan — making every retention conversation data-driven.
**Current focus:** Phase 06.1 — resolve Sonnet 4.6 tool-use regression (DEMO-02)

## Current Position

Phase: 06.1 (resolve-sonnet-4-6-tool-use-regression-demo-02) — Plan 02 complete
Plan: 2 of 4 complete (01 ✓ Strands 1.37.0 migration; 02 ✓ D-10 gates + cdk deploy; 03 pending live canaries; 04 pending closeout)
Next: Plan 06.1-03 — run three persona live canaries (Sarah / Marcus / Elena) against deployed runtime to prove DEMO-02 $30/$55 preservation on Claude Sonnet 4.6
Status: Phase 06.1 Plan 02 complete — Strands 1.37.0 migrated agent deployed to us-east-1; stable AgentRuntimeArn preserved; READY for Plan 03 live canaries
Last activity: 2026-04-25 -- Phase 06.1 Plan 02 executed; D-10 Gate 1 + Gate 2 passed locally in <5s; cdk deploy CustomerTariffAgent succeeded (24.95s); image digest sha256:08b140a9...99d48 live; runtime READY at 2026-04-25T10:52:53Z

**AgentRuntime (for Plan 03 live canaries):**
- ARN: `arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V` (stable; preserved from Phase 06-03)
- Region: us-east-1
- AWS profile: `cevo-dev25` (account 588738606436)
- Log group: `/aws/bedrock-agentcore/runtimes/tariff_agent-O2Hai86N8V-DEFAULT` (plural `runtimes`, `-DEFAULT` suffix — plan docs had stale singular path; see 06.1-02-SUMMARY.md Deviation 2)

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

### Roadmap Evolution

- Phase 06.1 inserted after Phase 6: Resolve Sonnet 4.6 tool-use regression (DEMO-02) (URGENT)

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. v1.0-era decisions preserved there with ✓ Good / ⚠️ Revisit markers. Full v1.0 decision log: see `.planning/milestones/v1.0-ROADMAP.md` Key Decisions section.

v2.0-specific decisions locked at requirements stage (see REQUIREMENTS.md):

- Narrative generation strategy: same-turn Claude 3.7 Sonnet (Option A) — single Bedrock call, smallest freeze surface (amended by Phase 06.1: strategic model pin is now Claude Sonnet 4.6 per D-01/D-02)
- Keep-alive: ship `scripts/demo-keepalive.sh`; honest-framing recovery is the secondary net
- Rollback mechanism: `?narrative=off` flag + `demo-v1.0` tag + `build:mock` dist (drilled at T-48h)
- No interim `demo-v1.1` tag — feature flag covers the common failure mode

Phase 06.1 Plan 02 execution decisions (2026-04-25):

- Verified stable AgentRuntimeArn preserved across deploy (`tariff_agent-O2Hai86N8V`) — Phase 7 plumbing assumption holds; no stack recreation.
- Used AWS_PROFILE=cevo-dev25 for deploy after the shell's `AWS_PROFILE=cevo-25` env var was found to reference a non-existent profile; cevo-dev25 returned account 588738606436 (Customer Tariff stack owner per Phase 06-03 Deviation 1).
- D-10 Gate 2 (Strands 1.37.0 wiring check inside container) confirmed `_agent.tool_registry.registry.keys()` attribute path is correct in the built image (RESEARCH assumption A4, LOW risk, now verified).
- CloudWatch log group for the runtime is `/aws/bedrock-agentcore/runtimes/tariff_agent-O2Hai86N8V-DEFAULT` (plural `runtimes`, `-DEFAULT` suffix); Plan 02 plan docs had the stale singular path. Durable signal for Plan 03/04.

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

Last session: 2026-04-25T10:54:31Z
Stopped at: Phase 06.1 Plan 02 deployed — awaiting Plan 03 live canary runs
Resume file: .planning/phases/06.1-resolve-sonnet-4-6-tool-use-regression-demo-02/06.1-03-PLAN.md

**Environment lock (v1.0 carry-forward):** `demo-v1.0` annotated git tag on main

- Tagged commit: `aba3a99c67994f39d9d496ddfd29c9116b756928`
- Tag object: `3bb0f51380176deedd1712d5dee17a70ccd94887`
- Push to origin: skipped (local-only, no origin configured)

**Suggested next commands:**

- `/gsd-execute-plan 06.1-03` — run three persona live canaries (Sarah / Marcus / Elena) against the deployed runtime (AGENT_RUNTIME_ARN already stable and captured above)
- Before Plan 03: export env for live smokes: `export AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V AWS_DEFAULT_REGION=us-east-1 AWS_PROFILE=cevo-dev25`

**Planned Phase:** 06.1 (Resolve Sonnet 4.6 Tool-Use Regression — DEMO-02) — 4 plans (01 ✓, 02 ✓, 03 pending, 04 pending) — 2026-04-25T10:54:31Z
