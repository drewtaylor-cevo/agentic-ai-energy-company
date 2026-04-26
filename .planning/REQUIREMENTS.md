# Requirements: Customer Tariff & Billing Optimisation Agent — v2.0

**Defined:** 2026-04-25
**Milestone:** v2.0 Demo Polish & LLM Narrative
**Rollback target:** `demo-v1.0` tag (shipped 2026-04-25)
**Core Value:** A call centre agent can open any customer account and immediately see exactly how much that customer could save and on which plan — making every retention conversation data-driven. v2.0 adds the *words around the numbers* — LLM-generated call-script snippets and usage narratives per recommendation — and hardens the environment for a live on-stage AWS demo.

## v2.0 Requirements

### Agent-Assist LLM Narrative (UI)

- [x] **UI-03**: LLM-generated call-script snippet rendered on each recommendation card (Green and Cheapest) — a one-liner the call centre agent can read verbatim. Second-person voice. ≤22 words. Contains no digits, `$`, `£`, `€`, or `%`. No switch/action verbs, no competitor references, no environmental superlatives.
- [x] **UI-04**: LLM-generated usage-narrative sentence rendered on each recommendation card — a one-sentence customer profile (e.g. "High evening and weekend usage, peaks during winter heating months"). Third-person descriptive voice. ≤20 words. Contains no digits, `$`, `£`, `€`, or `%`. No prescription, no second-person pronouns.
- [x] **UI-05**: Narrative-output validator enforces `max_length` caps and rejects any string containing `$`, `£`, `€`, `%`, or any digit, plus a banned-terms list (switch verbs, competitor names, environmental superlatives). Validation failure or timeout falls back to a per-persona × per-card committed fallback string. Validator is a Pydantic `field_validator` — a hard code-level gate, not a prompt-level nudge.
- [x] **UI-06**: `?narrative=off` URL feature flag hides both narrative rows client-side without a redeploy. Primary runtime rollback lever.
- [x] **UI-07**: Version indicator `v2.0 · <git-sha>` rendered in a corner of the UI — proves which build is live in the browser at demo time (defends against stale-bundle risk).
- [x] **UI-08**: Skeleton-first render keeps layout stable — narrative slots render a matching Skeleton during fetch with no layout shift on load. Both cards must remain above the fold at 1280×800 with narratives at maximum generated length.

### Demo Hardening — Pre-warm (DEMO)

- [x] **DEMO-03**: `scripts/prewarm.py` (invokable as `npm run prewarm`) warms all 3 personas × both cards through the full API Gateway → Lambda → AgentCore → Bedrock chain. `set -euo pipefail` plus `curl -f` semantics; non-zero exit if warm median ≥ 3000ms on any persona.
- [x] **DEMO-05**: `scripts/demo-keepalive.sh` pings the hot path every 10 minutes from T-30m through end of Q&A to beat AgentCore's 15-minute microVM idle timeout. Honest-framing recovery rehearsed as secondary net.

### Demo Hardening — Freeze & Rollback (DEMO)

- [x] **DEMO-04**: Frozen demo environment 48h pre-presentation:
  - `pip-compile --generate-hashes` on both `requirements.txt` and `requirements-dev.txt` → byte-identical Lambda bundles
  - `npm ci` reproducibility against existing `ui/package-lock.json`
  - CloudFormation stack policies deny `Update:*` on FoundationStack, AgentCoreStack, BackendApiStack
  - FoundationStack termination-protected
  - DynamoDB on-demand backup taken
  - `FREEZE-MANIFEST.md` captures SHA-256 of lockfiles + dist bundles + CloudFormation stack IDs + pinned Bedrock model ID (YAML in a Markdown code fence)
  - Annotated git tag `demo-v2.0` cut on `main`
  - `cdk diff` empty against deployed stack at freeze time
- [x] **DEMO-06**: Rollback drill rehearsed at T-48h against a scratch DynamoDB restore. Drill covers:
  - Revert to `demo-v1.0` tag works from a clean tree
  - `?narrative=off` feature flag toggles narrative rows off without redeploy
  - `build:mock` UI dist still regeneratable for <10s emergency UI swap
  - Drill must complete before freeze is declared.

## v3.0 Requirements — Deferred

Carried forward into the production-path milestone (v3.0). Covered in `STATE.md` Deferred Items.

- **PROD-01**: Live CRM integration replacing dummy data source
- **PROD-02**: Customer-facing self-service portal (v2 of the agent-assist tool)

## Out of Scope — v2.0

| Feature | Reason |
|---------|--------|
| Streaming narrative | Mid-sentence break on stage is worse than no streaming |
| Second LLM to critique the first | Blows UI-02 <3s budget; doubles freeze / failure surface |
| Regenerate-narrative button | Demo trap — presenter can't recover if retry returns worse output |
| Live model A/B or model swap | Bedrock model ID pinned to exact date-stamped version in CDK |
| Haiku fallback narrative path | Keep Claude 3.7 Sonnet same-turn (Option A); only revisit if T-24h warm median > 2.5s |
| Interim `demo-v1.1` rollback tag | `?narrative=off` flag is the faster lever; `demo-v1.0` remains the outer safety net |
| Custom API Gateway domain / Amplify / Cognito / SnapStart / uv / Poetry | Every new dep is a freeze pin for zero v2.0 feature value |

### Still-valid v1.0 exclusions (carried forward)

| Feature | Reason | Post-v2.0 review |
|---------|--------|------------------|
| Auto-switching plans | Recommendation only — human confirms | ✓ Still valid |
| Competitor / third-party plan comparison | Internal plan portfolio only for demo | ✓ Still valid |
| Mobile / responsive layout | Desktop-first (1280px) for call centre context | ✓ Still valid |
| OAuth / authentication | Not needed for demo | ✓ Still valid — re-evaluate if PROD-02 lands in v3.0 |
| Real-time tariff price feeds | Static dummy tariff rates sufficient for demo | ✓ Still valid — re-evaluate with PROD-01 |

## Key Decisions Locked at Requirements Stage

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Narrative generation strategy | Same turn, Claude 3.7 Sonnet (Option A) | Best grounding in deterministic tool output; single Bedrock call; smallest freeze surface. Only revisit if T-24h warm median fails. |
| In-Q&A keep-alive | Ship `scripts/demo-keepalive.sh` | Beats AgentCore's 15-min microVM idle timeout cheaply (~$3–12 total). Honest-framing recovery is a secondary net. |
| Rollback mechanism | Feature flag + `demo-v1.0` tag + `build:mock` dist, drilled at T-48h | Three independent levers — URL flag (fastest), tag revert (authoritative), UI mock dist (emergency). Drill proves the mechanism before it is depended on. |
| Interim `demo-v1.1` tag | Not cut | Feature flag covers the common failure mode without redeploy; extra tag adds freeze surface for no new safety. |

## Traceability

Phases assigned by `gsd-roadmapper` on 2026-04-25.

| Requirement | Phase | Status |
|-------------|-------|--------|
| UI-03 | Phase 6 (backend) + Phase 8 (UI render) | Not started |
| UI-04 | Phase 6 (backend) + Phase 8 (UI render) | Not started |
| UI-05 | Phase 6 | Not started |
| UI-06 | Phase 8 | Not started |
| UI-07 | Phase 8 | Not started |
| UI-08 | Phase 8 | Not started |
| DEMO-03 | Phase 7 (plumbing) + Phase 9 (tooling) | Not started |
| DEMO-04 | Phase 10 | Not started |
| DEMO-05 | Phase 9 | Not started |
| DEMO-06 | Phase 10 | Not started |

**Coverage:**
- v2.0 requirements: 10 total
- Mapped to phases: 10 ✓
- Unmapped: 0

**Phase distribution:**
- Phase 6 (Agent Narrative + Guardrail): UI-03 (backend half), UI-04 (backend half), UI-05
- Phase 7 (API Pass-Through + Pre-Warm Route): DEMO-03 (plumbing half)
- Phase 8 (UI Integration + Feature Flag + Version Indicator): UI-03 (UI half), UI-04 (UI half), UI-06, UI-07, UI-08
- Phase 9 (Pre-Warm Tooling + Eval Harness + Keep-Alive): DEMO-03 (complete), DEMO-05
- Phase 10 (Freeze + Rollback Drill): DEMO-04, DEMO-06

Note: UI-03, UI-04, and DEMO-03 span two phases by design — the backend/transport half lands first (Phase 6 / Phase 7) and the operator- or user-visible half lands later (Phase 8 / Phase 9). Each requirement closes only when both halves ship.

---
*Requirements defined: 2026-04-25 (v2.0 start)*
*Traceability mapped: 2026-04-25 (v2.0 roadmap)*
