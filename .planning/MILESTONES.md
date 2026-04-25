# Milestones: Customer Tariff & Billing Optimisation Agent

Historical record of shipped versions. Each entry links to the archived milestone ROADMAP and REQUIREMENTS.

---

## v1.0 MVP — shipped 2026-04-25

**Tag:** `demo-v1.0` (commit `aba3a99c67994f39d9d496ddfd29c9116b756928`)
**Phases:** 5 (Phases 1–5)
**Plans:** 21
**Timeline:** 2026-04-23 → 2026-04-25 (3 days)
**Git range:** `473f4ce` → `3df5851` (89 commits on main)
**Scale:** 165 files changed, +33,989 / -4 lines; ~15.5K LOC (≈11.5K Python CDK/Lambda, ≈4.0K TypeScript/React)

### Delivered

A working call centre agent-assist demo: enter a customer ID, get two personalised tariff recommendations (Green and Cheapest) with projected monthly and annual savings, rendered above the fold at 1280px in under 3 seconds, running on a live AWS Bedrock AgentCore + Lambda + API Gateway stack with no live CRM dependency.

### Key Accomplishments

1. **Deterministic savings engine** — `simulate_savings` pure function with 29 pytest cases locks the DEMO-02 flagship deltas (Green ~$30/mo, Cheapest ~$55/mo) across 3 personas. Arithmetic in code; LLM handles orchestration and narrative only.
2. **Strands/AgentCore agent deployed live** — Bedrock AgentCore Runtime serves both Green and Cheapest recommendations simultaneously per persona via tool calls. Cheapest saving ≥ Green saving invariant asserted in tests.
3. **Self-contained backend API** — API Gateway HTTP v2 + Lambda proxy with fresh `uuid4` sessions (no recommendation bleed between lookups), D-12 error taxonomy, 25s botocore timeout, CORS.
4. **Agent-assist UI at 1280px** — React + Vite + shadcn/ui (New York / Slate). Both cards above the fold, skeleton-first render so the screen is never blank, mock-fallback dist built for <10s emergency swap.
5. **Demo hardening + environment lock** — live AWS deploy across all 3 stacks in `us-east-1`, no-CRM structural audit, DEMO-RUNBOOK with T-24h/T-2h/T-0 checklist, annotated `demo-v1.0` tag cut on `main` with reproducibility gate passing (81 tests, 6 skipped, clean synth from clean tree).

### Requirements Coverage

All 13 v1 requirements shipped. See [`milestones/v1.0-REQUIREMENTS.md`](milestones/v1.0-REQUIREMENTS.md).

### Known Gaps / Deferred

None on v1 scope. One documented departure: the visual DevTools presenter rehearsal (D-14/D-15) is scheduled at T-24h per DEMO-RUNBOOK rather than performed at phase close. Smoke-derived latency evidence (Plan 05-02 live pytest ≲2s per request) substituted. If the T-24h visual warm median exceeds 3000ms, it becomes a gap against UI-02.

v2 requirements (UI-03, UI-04, DEMO-03, DEMO-04, PROD-01, PROD-02) carried forward per `STATE.md` Deferred Items — picked up in the next milestone.

### Archives

- Roadmap: [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md)
- Requirements: [`milestones/v1.0-REQUIREMENTS.md`](milestones/v1.0-REQUIREMENTS.md)
- Phase directories: [`milestones/v1.0-phases/`](milestones/v1.0-phases/)

---
