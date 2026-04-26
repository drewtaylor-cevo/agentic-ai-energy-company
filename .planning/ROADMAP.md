# Roadmap: Customer Tariff & Billing Optimisation Agent

## Milestones

- ✅ **v1.0 MVP** — Phases 1–5 (shipped 2026-04-25, tagged `demo-v1.0`) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- 🚧 **v2.0 Demo Polish & LLM Narrative** — Phases 6–10 (started 2026-04-25, rollback target `demo-v1.0`)

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

### v2.0 Demo Polish & LLM Narrative

- [x] **Phase 6: Agent Narrative + Guardrail** — Extend `TrackInfo` schema with `usage_narrative` + `call_script` plus the Pydantic validator that hard-rejects digits and currency symbols
- [x] **Phase 7: API Pass-Through + Pre-Warm Route** — Forward narrative fields verbatim and add the `?prewarm=1` branch on the existing Lambda behind an alias with Provisioned Concurrency (completed 2026-04-26)
- [x] **Phase 8: UI Integration + Feature Flag + Version Indicator** — Render narrative rows with skeleton shimmer, wire `?narrative=off` URL flag, bake in `v2.0 · <git-sha>` corner indicator (completed 2026-04-26)
- [x] **Phase 9: Pre-Warm Tooling + Eval Harness + Keep-Alive** — Ship `scripts/prewarm.py`, `scripts/demo-keepalive.sh`, and the end-to-end narrative eval harness (completed 2026-04-26)
- [x] **Phase 10: Freeze + Rollback Drill** — Pin hashes, apply CFN stack policies, cut `demo-v2.0` tag, drill `demo-v1.0` rollback on a scratch DynamoDB restore (completed 2026-04-26)

## Phase Details

### Phase 6: Agent Narrative + Guardrail
**Goal**: The agent returns per-card narrative text that is provably free of numeric and currency contradictions against the deterministic savings output.
**Depends on**: v1.0 shipped stack (AgentCore + Strands + Claude 3.7 Sonnet)
**Requirements**: UI-03 (backend half), UI-04 (backend half), UI-05
**Success Criteria** (what must be TRUE):
  1. For every persona, a live agent invocation returns both a `usage_narrative` (≤20 words, third-person descriptive) and a `call_script` (≤22 words, second-person) on each card.
  2. Any narrative string containing a digit, `$`, `£`, `€`, or `%` is rejected at the Pydantic layer and replaced by the committed per-persona × per-card fallback string — verified by a pytest that injects poisoned strings.
  3. Banned-terms list (switch/action verbs, named competitors, environmental superlatives) rejects offending outputs and triggers the same fallback path.
  4. Eval pytest runs 10 invocations per persona × both cards with zero numeric tokens observed and 100% validator pass-or-fallback behaviour.
  5. Deployed AgentCore image in `us-east-1` serves the extended schema and the v1.0 locked $30/$55 DEMO-02 deltas remain unchanged in tool output.
**Plans**: 3 plans
- [ ] 06-01-PLAN.md — Narrative foundations (agent/narrative package, regex, shape-tokens, fallbacks, prompt.txt + Wave 0 offline tests)
- [ ] 06-02-PLAN.md — Agent integration (Pydantic validator, retry-once-then-per-field-fallback in invoke(), _narrative_source marker, mocked-Strands + corpus tests)
- [ ] 06-03-PLAN.md — Container fix + CDK deploy + live smoke + sample capture (autonomous: false — human checkpoint on prose + CloudWatch)

### Phase 7: API Pass-Through + Pre-Warm Route
**Goal**: Narrative fields traverse API Gateway → Lambda → client without transformation, and a dedicated warm-up route exercises the full hot path behind an always-aliased Lambda.
**Depends on**: Phase 6
**Requirements**: DEMO-03 (plumbing half)
**Success Criteria** (what must be TRUE):
  1. A live `GET` against the deployed API endpoint for each persona returns JSON containing both `usage_narrative` and `call_script` on both cards, byte-identical to what the agent produced.
  2. `GET /?prewarm=1` returns HTTP 204 within the handler budget after exercising one minimal agent turn, and never returns 5xx even when the downstream warm-up fails.
  3. API Gateway is wired to a named Lambda alias (not `$LATEST`) with Provisioned Concurrency configurable via `cdk deploy -c demo_pc=1`.
  4. UI-01 (both cards above the fold at 1280px) and UI-02 (<3s lookup-to-rendered) still hold on live smoke with narratives included.
**Plans**: 2 plans
- [x] 07-01-PLAN.md — Handler marker-strip + narrative_source log + ?prewarm=1 branch (D-01/D-02/D-04/D-05/D-06/D-07/D-08) + 6 pytest additions (D-13)
- [x] 07-02-PLAN.md — CDK alias `live` + conditional Provisioned Concurrency + integration swap + demo_pc context read (D-09/D-10/D-11) + 4 synth assertions (D-14); D-15 live-smoke runbook captured in 07-01 SUMMARY

### Phase 8: UI Integration + Feature Flag + Version Indicator
**Goal**: Call centre agents see the narrative rows on each card with stable layout, and operators have a URL-level kill switch plus a visible build marker to defend against stale-bundle risk at demo time.
**Depends on**: Phase 7
**Requirements**: UI-03 (UI half), UI-04 (UI half), UI-06, UI-07, UI-08
**Success Criteria** (what must be TRUE):
  1. On every persona lookup, each recommendation card renders one usage-narrative row and one call-script row with no layout shift (skeleton → content transition matches the final row heights).
  2. Both cards remain above the fold at 1280×800 when the narratives are at maximum generated length, validated against the longest committed fallback strings.
  3. Appending `?narrative=off` to the URL hides both narrative rows without any redeploy and without collapsing the card layout.
  4. A `v2.0 · <git-sha>` indicator is visible in a corner of the UI and matches the SHA of the deployed build.
  5. `build:mock` regenerates a dist that still renders correctly with the extended `TrackInfo` shape, preserving the <10s emergency swap path.
**Plans**: 4 plans
- [x] 08-01-PLAN.md — TrackInfo + mock fixture (verbatim fallbacks) + flags.ts + vite-env.d.ts + vite.config __GIT_SHA__ define (Wave 1 foundation)
- [x] 08-02-PLAN.md — RecommendationCard narrative row + call_script blockquote + RecommendationSkeletons matching placeholders, all flag-gated (Wave 2, depends on 01)
- [x] 08-03-PLAN.md — VersionIndicator component + App.tsx render-as-sibling-of-main (Wave 2, depends on 01)
- [x] 08-04-PLAN.md — D-23 closeout gate: npm test + build + build:mock + 9-screenshot UAT at 1280×800 → 08-SAMPLES.md (Wave 3, autonomous: false, depends on 02+03)

### Phase 9: Pre-Warm Tooling + Eval Harness + Keep-Alive
**Goal**: Operator tooling makes the demo cold-start-free from T-30m through end of Q&A, and narrative correctness is assertable end-to-end from a single command.
**Depends on**: Phase 7 (pre-warm route); complements Phase 8 (shares no files, non-blocking)
**Requirements**: DEMO-03 (complete), DEMO-05
**Success Criteria** (what must be TRUE):
  1. `npm run prewarm` (invoking `scripts/prewarm.py`) warms all 3 personas × both cards through the full API Gateway → Lambda → AgentCore → Bedrock chain in under 30 seconds, with `set -euo pipefail` + `curl -f` semantics and per-call latency printed.
  2. The pre-warm script exits non-zero if warm median ≥ 3000ms on any persona, and a subsequent lookup within 5 minutes measures warm median ≤ 2.5s on all personas.
  3. `scripts/demo-keepalive.sh` pings the hot path every 10 minutes and continues through termination, beating AgentCore's 15-minute microVM idle timeout.
  4. The end-to-end eval harness asserts every persona × card narrative passes the Phase 6 validator when driven through the live endpoint — run green before the phase closes.
**Plans**: 4 plans
- [x] 09-01-PLAN.md — scripts/prewarm.py (stdlib-only two-pass warm + measurement CLI with 0/1/2 exit taxonomy) + ui/package.json prewarm script (wave 1)
- [x] 09-02-PLAN.md — tests/test_prewarm_script.py (7 offline pytest cases mocking urllib.urlopen; runs under pytest -m "not smoke") (wave 2, depends on 09-01)
- [x] 09-03-PLAN.md — scripts/demo-keepalive.sh (bash 10-min rotating-persona ping loop with trap on INT/TERM/HUP; shellcheck-clean) (wave 1)
- [x] 09-04-PLAN.md — tests/test_narrative_eval_live.py (smoke-gated live eval harness; 3 HTTP calls asserting Phase 6 validator rules + Phase 7 _narrative_source marker-absence invariant) (wave 1)

### Phase 10: Freeze + Rollback Drill
**Goal**: The production stack is locked at T-48h against drift, and the rollback mechanism is proven before it is depended on at presentation time.
**Depends on**: Phase 6, Phase 7, Phase 8, Phase 9 (all upstream phases green)
**Success Criteria** (what must be TRUE):
  1. `pip-compile --generate-hashes` produces pinned `requirements.txt` and `requirements-dev.txt` that rebuild byte-identical Lambda bundles from a clean venv; `npm ci` reproduces the UI build against the committed `package-lock.json`.
  2. CloudFormation stack policies deny `Update:*` on FoundationStack, AgentCoreStack, and BackendApiStack; FoundationStack is termination-protected; `cdk diff` is empty against the deployed stack at freeze time.
  3. A DynamoDB on-demand backup is taken and the `FREEZE-MANIFEST.md` captures SHA-256 hashes of lockfiles + dist bundles + CloudFormation stack IDs + pinned Bedrock model ID as YAML inside a Markdown code fence.
  4. An annotated `demo-v2.0` tag is cut on `main` and the reproducibility gate (`pytest -m "not smoke"` green from a clean tree) holds.
  5. The rollback drill — executed against a scratch DynamoDB restore at T-48h — proves that reverting to `demo-v1.0` works from a clean tree, `?narrative=off` toggles narrative off without redeploy, and `build:mock` regenerates the <10s emergency UI swap dist.
**Requirements**: DEMO-04, DEMO-06
**Plans**: 3 plans
- [x] 10-01-PLAN.md — Stack-policy JSON bodies + content-manifest hashers + cross-rebuild determinism gate (Wave 1, autonomous)
- [x] 10-02-PLAN.md — Hash-pinned requirements via pip-compile + FREEZE-MANIFEST.md scaffold + 10-DRILL-LOG.md skeleton + DEMO-RUNBOOK.md §7-§10 (Wave 2, autonomous, depends on 10-01)
- [x] 10-03-PLAN.md — T-48h ceremony execution: reproducibility gate + cdk diff + rollback drill + stack lock + DynamoDB backup + manifest population + demo-v2.0 tag + origin push (Wave 3, autonomous: false, depends on 10-02)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation + Dummy Data | v1.0 | 3/3 | ✓ Complete | 2026-04-23 |
| 2. AgentCore Agent | v1.0 | 3/3 | ✓ Complete | 2026-04-23 |
| 3. Backend API | v1.0 | 3/3 | ✓ Complete | 2026-04-24 |
| 4. Agent-Assist UI | v1.0 | 5/5 | ✓ Complete | 2026-04-24 |
| 5. Demo Hardening | v1.0 | 7/7 | ✓ Complete | 2026-04-25 |
| 6. Agent Narrative + Guardrail | v2.0 | 3/3 | ✓ Complete | 2026-04-25 |
| 7. API Pass-Through + Pre-Warm Route | v2.0 | 2/2 | Complete    | 2026-04-26 |
| 8. UI Integration + Feature Flag + Version Indicator | v2.0 | 4/4 | Complete    | 2026-04-26 |
| 9. Pre-Warm Tooling + Eval Harness + Keep-Alive | v2.0 | 4/4 | Complete    | 2026-04-26 |
| 10. Freeze + Rollback Drill | v2.0 | 3/3 | Complete    | 2026-04-26 |

---
*Roadmap created: 2026-04-23*
*Last updated: 2026-04-26 — Phase 10 plans committed (3 plans, 3 waves: 01 stack-policy JSONs + hashers → 02 pip-compile + manifest scaffold + DEMO-RUNBOOK §7-§10 → 03 T-48h ceremony execution, autonomous: false)*
