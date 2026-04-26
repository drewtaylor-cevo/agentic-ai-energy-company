# Milestones: Customer Tariff & Billing Optimisation Agent

## v2.0 Demo Polish & LLM Narrative (Shipped: 2026-04-26)

**Phases completed:** 5 phases, 16 plans, 47 tasks

**Key accomplishments:**

- Pure-Python narrative foundation package delivering the LLM-isolation layer: compiled banned-terms regex (6 competitors, 28 switch verbs, 12 env superlatives), structural no-numerics shape-tokens, 12 validator-passing fallback strings, externalised prompt with 3 exemplars, and 67 Wave 0 offline tests.
- Retry-once-then-per-field-fallback wired into invoke() via lenient salvage schema; TrackInfo extended with two validated narrative fields (max 20/22 words, 140/180 chars) gating the structured_output call; `_narrative_source` per-field marker emitted on every response path; 120 per-field offline corpus assertions prove zero numeric leakage across 3 personas × 10 invocations × 2 tracks × 2 fields.
- Dockerfile Pitfall 1 fixed and deployed. Two follow-on bugs found and fixed during live deploy: (a) bi-mode module-layout imports for `/app/narrative/` runtime vs `agent/narrative/` repo, and (b) `agent/narrative/validators.py` had the same module-layout bug. Bedrock rejected Claude 3.7 Sonnet as Legacy+unused; upgraded to Claude Sonnet 4.6 (ACTIVE) per user decision. Live smoke now passes 18/19 with narrative extended-schema green across all 3 personas. `test_sarah_flagship_values` FAILS — Claude Sonnet 4.6 is fabricating savings numbers instead of honouring the `simulate_savings` tool output, violating v1.0 DEMO-02 preservation (success criterion 5). System-prompt tightening did not resolve it; root cause is a Strands+Claude-4.6 tool-use regression (`Agent.structured_output` is deprecated and may not wire tools correctly to 4.6). Phase 6 is PARTIAL — a decimal phase (6.1) is needed to migrate Strands usage to `structured_output_model` and/or restore Claude 3.7 access.
- `_narrative_source` marker stripped, narrative fields flow byte-identically, and `?prewarm=1` returns HTTP 204 with swallow-all exception handling — all additive edits to `api_lambda/handler.py` plus 6 new pytest functions in `tests/test_backend_api_handler.py`.
- Foundation layer for Phase 8: TrackInfo extended with required usage_narrative + call_script strings, MOCK_RECOMMENDATIONS synced byte-for-byte with Phase 6 fallbacks, NARRATIVE_ENABLED flag module shipped, __GIT_SHA__ wired end-to-end from vite.config.ts through a TypeScript global — zero consumer surface, zero new runtime deps.
- Wave 2 core visible work landed: the two narrative rows render on every recommendation card (narrative italic/muted between savings and methodology; call_script as a track-accent bordered quote below methodology), matching skeleton placeholders carry the layout through the loading → success transition, and both the cards AND the skeletons collapse to their v1.0 shape when `?narrative=off` is in the URL. 14 new tests (7 card + 7 skeleton); full suite 87/87 green; zero new deps; RED → GREEN TDD cycle committed atomically per task.
- Ships the UI-07 bottom-right corner build marker — trivial zero-prop <span> reading the Plan-01-injected `__GIT_SHA__` global, rendered as a sibling of `<main>` in App.tsx per D-17 so it does not participate in the max-w-4xl card layout. Full vitest suite 76/76 green; net +2 lines in App.tsx, 2 new files, zero runtime dep additions.
- D-23 closeout gate passed: all 3 automated gates green (tsc, vitest 90/90, build + build:mock with `fe39971` embedded), operator attested all 5 Phase 8 success criteria hold at 1280×800 against the live API.
- Stdlib-only Python pre-warm CLI (`scripts/prewarm.py`) that warms all three demo personas via Phase 7's `?prewarm=1` route, settles 30s, runs 9 timed measurement GETs, and enforces <3000ms warm-median gate per persona with strict 0/1/2 exit taxonomy — invokable as `npm run prewarm` from `ui/`.
- `scripts/demo-keepalive.sh` rotates CUST-001→CUST-002→CUST-003 every 10 minutes to beat AgentCore's 15-minute microVM idle timeout; smoke-gated `tests/test_narrative_eval_live.py` asserts Phase 6 validator rules + Phase 7 `_narrative_source` stripping against the live stack.
- Six CFN stack-policy JSON bodies (3 freeze + 3 break-glass) committed under `infrastructure/stack-policies/`, plus two shellcheck-clean content-manifest sha256 hashers (`scripts/hash_dist.sh` and `scripts/hash_synth_assets.sh`), with empirical proof that `hash_dist.sh` produces an identical hash across a full `rm -rf ui/dist && npm run build` cycle (H1 == H2 = `4237523128d37fd5da4c0947db192d03a4e2613a2ad2de7fb2123d04bbe3a0a4`).
- Two `.in` files + two hash-pinned `.txt` files + FREEZE-MANIFEST.md template (8 D-10 keys, bedrock_model_id pre-filled, break-glass block referencing the 10-01 allow-all JSON bodies) + 10-DRILL-LOG.md skeleton (5 speed-first drill steps + copy-paste Commands appendix) + DEMO-RUNBOOK.md extended with §7-§10 ceremony sections (renumbered from D-20 §3-§6 per PATTERNS.md collision resolution) — all T-48h operator-ready, fresh-venv `pip install --require-hashes` verified exit 0 on both prod and dev lockfiles.
- T-48h freeze ceremony executed end-to-end: stack policies locked on all 3 CFN stacks (`Deny Update:*` + termination protection), `cdk diff == 0` post-reconciliation deploy of Phase 7-02 alias, DynamoDB freeze backup AVAILABLE, rollback drill 5/5 PASS (`?narrative=off` + `build:mock` 0.95s + `demo-v1.0` fresh-clone pytest + restore-from-backup 36 items + scratch teardown), `demo-v2.0` annotated tag cut with WN-2 two-commit self-consistency and pushed to origin. D-22 closeout 15/15 PASS. Final verdict: PASS.

**Known deferred items at close:** 5 items (see STATE.md §v2.0 Close Deferrals) — 2 HUMAN-UAT gaps (Phase 07, Phase 09; 6 pending scenarios total) + 3 VERIFICATION files in `human_needed` state (Phase 07, 08, 09). All to be resolved at T-24h rehearsal via `/gsd-verify-work`.

**Stats:** 157 commits in range `demo-v1.0..v2.0-close`; +4,392 / −29 insertions/deletions across 63 source files (excluding `.planning/`); timeline 2026-04-25 → 2026-04-26 (5 phases, 16 plans, 47 tasks).

**Archives:**
- Roadmap: [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md)
- Requirements: [`milestones/v2.0-REQUIREMENTS.md`](milestones/v2.0-REQUIREMENTS.md)
- Git tags: `demo-v2.0` (freeze-ceremony target, signs `a09c086`); `v2.0` (milestone close, on milestone-close commit)

---

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
