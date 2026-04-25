# Project Research Summary — v2.0 Demo Polish & LLM Narrative

**Project:** Customer Tariff & Billing Optimisation Agent
**Milestone:** v2.0 (extends `demo-v1.0` — shipped 2026-04-25)
**Domain:** AI agent-assist (Energy & Utilities call centre) — adds short-form LLM narrative on top of a deterministic tool-driven recommendation; single-shot live on-stage AWS demo
**Researched:** 2026-04-25
**Confidence:** MEDIUM-HIGH

## Executive Summary

v2.0 is an **additive** milestone over a fully shipped v1.0 stack (AWS Bedrock AgentCore + Strands + Lambda + API Gateway HTTP v2 + React/Vite, `us-east-1`, tagged `demo-v1.0`). All four v2.0 requirements (UI-03 call-script, UI-04 usage-narrative, DEMO-03 pre-warm, DEMO-04 48h freeze) reuse existing layer boundaries — no new services, no new runtime components, no v1.0 regressions. The narrative work is a **Pydantic schema extension** on the existing `Agent.structured_output()` call; demo hardening is **Provisioned Concurrency + pre-warm script + pip-compile hashes + CloudFormation stack policy + annotated tag**. Every piece is off-the-shelf.

The single load-bearing design rule is **numbers come from `simulate_savings`, words come from the LLM, and the two must never meet in the prompt**. This is enforced as a Pydantic `field_validator` that rejects any narrative string containing `$`, `£`, `€`, or a digit — a hard code-level gate, not a prompt-level nudge — plus per-field `max_length` caps (140 chars for `usage_narrative`, 180 for `call_script`). That validator is what makes the v1.0 locked $30/$55 savings deltas un-contradictable by the new narrative surface. Without it, UI-03/UI-04 can drift into hallucinated figures the moment the prompt is edited.

The primary demo risks are (1) latency stacking — v1.0 smoke warm was ~2s; adding ~80 output tokens × 2 cards puts the UI-02 <3s budget into tail-risk territory, mitigated by DEMO-03 pre-warm + hard length caps + T-24h rehearsal; (2) AgentCore's **15-minute microVM idle timeout** re-colds during Q&A, mitigated by a background keep-alive from the presenter laptop; and (3) any post-freeze "just one tweak" — mitigated by CloudFormation stack policy denying `Update:*` on all three stacks for the 48h window and a rehearsed rollback to the `demo-v1.0` tag + `?narrative=off` feature flag. The five bottom-up phases (Agent → API → UI → Pre-warm → Freeze) follow the v1.0 pattern and reuse its reproducibility gate.

## Key Findings

### Recommended Stack

No major version bumps. The v1.0 stack is carried forward verbatim; v2.0 adds one dev tool (`pip-tools`), three new runtime artefacts (Pydantic validators, `scripts/prewarm.py`, CFN stack policies) and one build-time tightening (exact `==` pins with `--generate-hashes` for freeze). Detail in [STACK.md](STACK.md).

**Carried forward (unchanged from v1.0):**
- AWS Bedrock AgentCore Runtime + Strands SDK + `BedrockAgentCoreApp` — same agent container, extended schema
- Claude 3.7 Sonnet `us.anthropic.claude-3-7-sonnet-20250219-v1:0` — same model, ~80 extra output tokens per card
- AWS Lambda + API Gateway HTTP v2 — same handler, **pass-through** (no API logic change)
- DynamoDB billing + tariff tables — unchanged; seeder idempotent
- React 19 + Vite 8 + Tailwind 4 + shadcn/ui — two new `<p>` rows per card, two new Skeleton rows

**Added (v2.0):**
- `pydantic` `field_validator` + `Field(max_length=…)` — **the load-bearing "no dollar figures" gate** on `usage_narrative` and `call_script`
- `pip-tools >=7.4.0` (dev dep) — `pip-compile --generate-hashes` for byte-identical Lambda bundles
- AWS Lambda Provisioned Concurrency (`pc=1` via CDK context, ~$0.05 per demo) — warms the API Lambda
- Custom `scripts/prewarm.py` — warms AgentCore microVM pool + Bedrock inference path (PC does not warm AgentCore)
- CloudFormation Stack Policy JSON — `Update:*` deny on FoundationStack / AgentCoreStack / BackendApiStack for the 48h window
- Annotated git tag `demo-v2.0` + DynamoDB on-demand snapshot for rollback

**Version pins tighten from `>=` to `==` at freeze:** `aws-cdk-lib==2.250.<patch>`, `boto3==1.42.<patch>`, UI deps frozen via `npm ci` against existing `package-lock.json`.

### Expected Features

Detail in [FEATURES.md](FEATURES.md).

**Must ship (table stakes — demo fails without these):**
- **UI-03 call-script snippet** — ≤22 words, second-person, no jargon, no `$\d` or `\d%`
- **UI-04 usage narrative** — ≤20 words, third-person descriptive, no prescription, no second-person pronouns
- **Output validator** — length cap + numerics ban + banned-terms list (switch verbs, competitor names, environmental superlatives)
- **Deterministic fallback strings** — per-persona × per-card, committed to source, frozen; card renders these if LLM output fails validation or times out
- **Skeleton shimmer on narrative slots** — layout doesn't shift on load
- **Pre-warm script covering all 3 personas × both cards** — T-10min, fail-loud on >3s warm
- **Pinned deps + locked AWS state @ T-48h** — tag + `cdk diff` empty + stack policy applied
- **Rollback to v1.0** — `?narrative=off` flag + `demo-v1.0` tag + `build:mock` fallback

**Should ship (significantly de-risks):**
- Persona-of-voice lock (frozen system prompt + few-shot examples checked in)
- LLM eval harness (pytest asserting narrative passes validator for all 3 personas × 2 cards)
- Narrative feature flag (`?narrative=off` at the URL — no redeploy needed)
- Narrative telemetry to CloudWatch (every prompt/response pair for debrief)
- Hard in-Lambda timeout budget (narrative <1500ms else fallback)
- Presenter tooltip (alt-click reveals raw LLM + verdict)

**Anti-features — do not build (each has a named failure mode):**
- **LLM quoting dollar figures** — hard-flag: validator rejects `[$£€]` or any digit. Non-negotiable per milestone brief
- **LLM making switch/action claims** — "switch you", "I'll move you" — banned-terms list
- **Competitor references** — Origin, AGL, EnergyAustralia, Red Energy, Alinta, Momentum — banned-terms list
- **Environmental claims beyond plan attributes** — greenwashing risk, regulator-visible
- **Second LLM to critique the first** — latency + failure modes, not demoable in the window
- **Streaming narrative** — mid-sentence break is worse than no streaming
- **Regenerate-narrative button** — demo trap; use presenter tooltip for debug
- **Live model A/B or model swap** — pin exact date-stamped model ID in CDK
- **Custom domain / Amplify / Cognito / react-query / Markdown renderer / SnapStart / uv / Poetry** — every dep is a freeze pin for zero v2.0 feature value

### Architecture Approach

Four-layer architecture from v1.0 preserved exactly. Two narrative string fields added to the `TrackInfo` Pydantic model in **Layer 2 (Bedrock AgentCore)**; pass-through in **Layer 3 (Lambda/API)**; two new `<p>` rows + skeleton rows in **Layer 4 (UI)**. Layer 1 (DynamoDB) untouched. Detail in [ARCHITECTURE.md](ARCHITECTURE.md).

**Major components:**
1. **Extended agent schema (Layer 2)** — `TrackInfo` gains `usage_narrative` + `call_script` as validated string fields; single `Agent.structured_output()` call (**Option A**, not a second Bedrock call), grounded in `simulate_savings` tool return. The agent has the exact numbers in-context → lowest hallucination risk.
2. **Pass-through Lambda handler (Layer 3)** — existing `body = json.loads(response["response"].read())` already forwards unknown fields verbatim; adds `?prewarm=1` branch that invokes a minimal agent turn and returns 204.
3. **Render + skeleton updates (Layer 4)** — two `<p>` rows inside `CardContent` above the methodology line; two Skeleton rows to match; React default escaping handles XSS (no Markdown).
4. **Pre-warm tool (operational, not runtime)** — `scripts/prewarm.py` curls `?prewarm=1` × 3 personas + `boto3 invoke_agent_runtime` direct ping; exits non-zero if warm median ≥ 3000ms.
5. **Freeze artefacts (no runtime component)** — `demo-v2.0` tag + CloudFormation stack policy (JSON) + DynamoDB on-demand snapshot + `FREEZE-MANIFEST.md` (SHA-256 of lockfiles, dist bundles, stack IDs, model ID).

**Generation strategy — Option A chosen over B/C:**
- Option A (extend existing agent turn) adds +200–600ms, grounds numbers in-context, one schema edit, one prompt edit
- Option B (second Bedrock call) adds +800–1500ms, doubles IAM/retry/freeze surface — rejected
- Option C (UI-side second request) decouples but adds second endpoint + hook + loading state + freeze path — rejected

**Latency budget (v2.0 warm with Option A + pre-warm):** 1470–3150ms. Median inside UI-02 <3s; tail can tip over. Mitigated by strict `max_length` caps and T-24h DevTools rehearsal gate.

### Critical Pitfalls

Detail (8 Critical, 9 Moderate, 6 Minor) in [PITFALLS.md](PITFALLS.md). Top items ranked by demo impact:

1. **LLM re-quotes or contradicts the locked $30/$55 deltas (C1)** — prevented by Pydantic `field_validator` rejecting `[$£€\d]`, plus never passing raw numbers into the narrative prompt (shape tokens only), plus pytest asserting zero numeric tokens in 10× invocations per persona
2. **Latency stacking pushes lookup-to-rendered past 3s (C4)** — prevented by single-turn generation (Option A, not parallel/series second call), strict `max_length` caps, hard in-Lambda 1500ms timeout with fallback to canned string, pre-warm, T-24h DevTools gate
3. **Pre-warm script warms the wrong path (C6)** — prevented by covering all 3 personas × both cards, warming the full API Gateway → Lambda → AgentCore → Bedrock chain (not just Lambda), `set -euo pipefail` + `curl -f`, per-call latency assertions
4. **AgentCore 15-min microVM idle timeout re-colds during Q&A (C7)** — mitigated by background keep-alive pinging every 10 min from T-30min onwards (cheap: ~$3–12 total); script honest framing if it bites anyway
5. **Length / voice drift breaks 1280px above-the-fold (C3)** — prevented by Pydantic `max_length` (140/180), CSS `max-height` + ellipsis, CI test against longest-plausible narratives, T-24h 1280×800 visual rehearsal
6. **Silent LLM retries double latency invisibly (C5)** — prevented by `retries=1` (not 3), CloudWatch alarm on `retry_count > 0`, Claude native JSON mode
7. **Browser cache serves stale v1.0 bundle on demo day (C8)** — prevented by version indicator baked in (`v2.0 · <sha>`), cold-browser rehearsal in a fresh Chrome guest profile, DevTools "Disable cache"
8. **Post-freeze "just one tweak"** — prevented by CFN stack policy (AWS-side deny, not just discipline), termination protection on FoundationStack, rehearsed rollback to `demo-v1.0` + `?narrative=off`, fix-forward explicitly forbidden in runbook

## Implications for Roadmap

Research converges on a **5-phase bottom-up sequence** (mirrors v1.0's proven shape) with 4.3 + 4.4 parallelisable. Dependencies flow strictly forward: schema → pass-through → render → pre-warm → freeze.

### Phase 2.1: Agent Narrative + Guardrail
**Rationale:** Schema is the contract. Every downstream phase depends on the shape and validator behaviour. Ship the numeric-exclusion gate **first** — it is the single load-bearing invariant for the whole milestone.
**Delivers:** Extended `TrackInfo` Pydantic model with `usage_narrative` + `call_script` fields, `field_validator` enforcing no currency/digits, `max_length` caps, updated system prompt + 3 few-shot exemplars, deployed AgentCore image.
**Addresses:** UI-03, UI-04 (backend half), persona-of-voice lock
**Avoids:** C1 (dollar contradictions), C2 (prompt injection via persona free-text), C3 (length drift via `max_length`), M7 (PII in logs — log shape not content)
**Stack:** Strands `Agent.structured_output()` extension; Pydantic `field_validator` + `Field(max_length=…)`; Claude 3.7 Sonnet unchanged
**Gate:** Offline pytest — 10 invocations per persona, all pass validator, zero numeric tokens; live smoke on all 3 personas returns schema-valid JSON with narrative caps honoured

### Phase 2.2: API Pass-Through + Pre-Warm Route
**Rationale:** Lambda handler is v1.0 pass-through — extra fields forward verbatim with zero logic change. Adding `?prewarm=1` here (not a new Lambda) keeps the hot path identical between warm-up and live and keeps the freeze surface minimal.
**Delivers:** `?prewarm=1` branch in the existing handler (returns 204 after minimal agent turn), optional-field-tolerant response parsing, Provisioned Concurrency alias wiring (`demo_pc=1` CDK context).
**Addresses:** DEMO-03 (plumbing half), UI-03/UI-04 transport
**Avoids:** M1 (alias/version mismatch — bind API Gateway to alias, not `$LATEST`)
**Stack:** Existing API Lambda + CDK `lambda_.Alias` + `provisioned_concurrent_executions`
**Gate:** Unit tests — happy path forwards extra fields; `?prewarm=1` returns 204; pre-warm failure still returns 204 (never 5xx from warm-up); live curl confirms narrative fields reach the client

### Phase 2.3: UI Integration + Feature Flag
**Rationale:** UI depends on Phase 2.2 being deployed so cards fetch real narrative from the live endpoint. Feature flag (`?narrative=off`) lands here so runtime rollback is ready before freeze.
**Delivers:** Extended `TrackInfo` TS type (optional fields), two `<p>` rows + two Skeleton rows per `RecommendationCard`, mock fixture updated (`build:mock` still regeneratable), `?narrative=off` URL flag toggles narrative off without redeploy, version indicator (`v2.0 · <sha>`) in corner.
**Addresses:** UI-03 (UI half), UI-04 (UI half), narrative feature flag, version visibility
**Avoids:** C3 (CSS test against longest-plausible strings; above-the-fold 1280×800), C8 (version indicator + fresh browser profile rehearsal)
**Stack:** No new deps; React default escaping; existing shadcn `CardContent`; existing Zod-adjacent validator
**Gate:** Visual rehearsal at 1280×800 — both cards above the fold for all 3 personas with longest-generated narratives baked in; `?narrative=off` hides narrative rows cleanly

### Phase 2.4: Pre-Warm Tooling + Eval Harness
**Rationale:** Depends only on Phase 2.2's `?prewarm=1` route; parallelisable with Phase 2.3. Warming tool must warm what the demo hits — full chain, all personas, with real UI-shaped calls.
**Delivers:** `scripts/prewarm.py` (or `npm run prewarm`) covering all 3 personas × both cards, per-call latency print, non-zero exit on warm median ≥ 3000ms, boto3 direct AgentCore ping, eval harness asserting every narrative passes the validator end-to-end.
**Addresses:** DEMO-03 (complete)
**Avoids:** C6 (wrong-path warming), m3 (silent failures — `set -euo pipefail` + `curl -f`), m5 (call-shape mismatch — headers match UI), M1 (alias-pinned warming)
**Stack:** Existing `requests`, `boto3`, pytest; no new deps
**Gate:** `npm run prewarm` completes <30s; subsequent lookup within 5 min measures warm median ≤2.5s on all personas; eval harness green

### Phase 2.5: Freeze + Rollback Drill
**Rationale:** Must be last — requires everything else green. Two locks in parallel: source (tag) and AWS state (stack policy + termination protection + DynamoDB snapshot). Rollback path rehearsed **before** the freeze, not during the demo.
**Delivers:** `pip-compile --generate-hashes` applied to both `requirements*.txt`, `cdk diff` empty against deployed stack, three CFN stack policies applied, FoundationStack termination-protected, DynamoDB on-demand backup taken, `FREEZE-MANIFEST.md` with SHA-256 of lockfiles/dists/stack IDs/model ID, annotated `demo-v2.0` tag pushed, rollback to `demo-v1.0` + `?narrative=off` drilled once.
**Addresses:** DEMO-04 (complete), rollback readiness
**Avoids:** M3 (transitive dep drift — hash pins), M2 (cdk.context.json drift), M4 (Lambda layer ARN pins), M9 (date-stamped model ID), m1 (uncommitted config), m2 (missing/un-rehearsed rollback), C7 (keep-alive decision captured in runbook)
**Stack:** `pip-tools`, `npm ci`, CloudFormation Stack Policy JSON, AWS CLI, git tag
**Gate:** Reproducibility test from clean venv (`pytest -m "not smoke"` green) + `cdk synth` matches `cdk.out.frozen.json` + T-24h DevTools warm-median rehearsal inside UI-02 budget for all personas + rollback drill completes on a scratch DynamoDB restore

### Phase Ordering Rationale

- **Schema before transport before render before tooling before freeze.** This is the same bottom-up order that worked for v1.0 (data → tools → agent → API → UI), scaled to v2.0's smaller surface.
- **2.1 must precede 2.2/2.3** — the Pydantic validator is the authoritative numeric-exclusion gate; UI and API are downstream consumers.
- **2.4 parallelisable with 2.3** — both depend only on 2.2's `?prewarm=1` branch; 2.4 is operator tooling and 2.3 is user-visible render, different files, no conflict.
- **2.5 strictly last** — freezing requires green on everything upstream; drilling rollback inside the freeze is too late.
- **Parallelism limited by freeze risk, not by dependency graph.** Even where two phases could run fully in parallel, sequencing them reduces the diff exposure during the 48h pre-freeze.

### Research Flags

**Phases likely needing deeper research during planning (`/gsd-research-phase`):**
- **Phase 2.1 (Agent Narrative):** confirm that Strands' `Agent.structured_output()` retries on Pydantic `ValidationError` (v1.0 has a fallback but behaviour under `field_validator` raises is unverified); confirm Pydantic v2 is what Strands pulls (not v1) — both flagged MEDIUM in STACK.md. **Model choice** (same Claude 3.7 Sonnet vs. a faster Haiku for narrative) is still open — see Gaps below.
- **Phase 2.4 (Pre-Warm):** confirm `CfnOutput` names for `ApiEndpoint` + `AgentRuntimeArn` in the v1.0 stack; confirm AgentCore microVM pool warming semantics (warming one persona vs. warming three — behaviour is MEDIUM confidence per ARCHITECTURE.md); decide whether `?prewarm=1` runs a full agent turn or a stripped-down "hello" turn.
- **Phase 2.5 (Freeze):** confirm CDK ↔ manual `aws cloudformation set-stack-policy` interaction (MEDIUM per STACK.md — CDK may fight the manual policy on re-synth); decide machine-readable vs. Markdown FREEZE-MANIFEST (recommend YAML for CI diffing per ARCHITECTURE.md open question); decide whether rollback drill runs against real stack or scratch copy.

**Phases with standard patterns (skip research-phase):**
- **Phase 2.2 (API Pass-Through):** existing v1.0 handler already does pass-through; pattern proven
- **Phase 2.3 (UI Integration):** plain render change, no new libraries, no streaming

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Core carry-forward is HIGH (v1.0 shipped). New surface (Pydantic `field_validator`, PC, pip-tools, stack policy) is composed of well-documented primitives. Specific patch versions for `aws-cdk-lib` / `boto3` need snap-at-freeze-time. Strands' retry-on-`ValidationError` behaviour is LOW — needs Phase 2.1 sanity test. |
| Features | HIGH | Table stakes / differentiators / anti-features are agent-assist LLM UX conventions grounded in training knowledge of Amazon Connect Agent Assist, Salesforce Einstein, Google CCAI. Hard-flag "no $ in narrative" is explicit in the milestone brief and enforceable at the Pydantic layer. |
| Architecture | HIGH | Four-layer shape carries forward verbatim from v1.0. Option A (same-turn generation) is the standard Strands pattern. AgentCore 15-min idle timeout confirmed in AWS docs. Stack policy semantics confirmed. Latency math is MEDIUM on tail risk — must be validated at T-24h. |
| Pitfalls | MEDIUM-HIGH | C1/C3/C4 (the big three — dollar contradiction, length drift, latency stacking) are prevented by code-level gates that can be tested pre-freeze. C7 (AgentCore re-cold during Q&A) is a demo-day mitigation, not a pre-freeze fix. C8 (browser cache) is freeze-day posture. Specific AgentCore warm-window numbers are MEDIUM — rehearsal is the source of truth. |

**Overall confidence:** MEDIUM-HIGH. The milestone is additive over a proven stack, the risk surface is small and well-enumerated, and every critical risk has a named pre-freeze mitigation that can be gate-tested. Residual uncertainty is demo-day performance variance (AgentCore microVM routing, Bedrock tail latency) — handled by pre-warm, feature flag, and rollback tag, not by additional engineering.

### Gaps to Address

Explicit open questions the roadmapper/planner must resolve before or during Phase 2.1/2.4/2.5:

- **Narrative model choice** — same Claude 3.7 Sonnet (HIGH grounding, +~500ms) or fast Haiku on a second path (LOW grounding, +~300ms, new IAM/freeze surface). STACK.md recommends **same-turn Option A with Sonnet**; FEATURES.md flags Haiku as an alternative for the narrative call specifically. **Recommendation:** resolve in Phase 2.1 via live warm-median measurement. If Option A median fits <2.5s with pre-warm, keep Sonnet. If not, re-evaluate.
- **Parallel vs. series narrative calls** — moot if Option A is kept (single call). Becomes a real question only if Option A blows UI-02 and we fall back to Option B (separate Bedrock call). Plan: **only revisit during Phase 2.1 if latency gate fails**.
- **Provisioned Concurrency gating** — leave PC=1 always-on during the demo week, or flip it on at T-30m? STACK.md recommends CDK context flag (`cdk deploy -c demo_pc=1`) applied T-5min. **Recommendation:** apply at T-30m to give the Lambda alias time to warm; turn off next-day (~$0.05 total).
- **Keep-alive during Q&A** — background script from presenter laptop every 10 min vs. accept-and-script-the-recovery. PITFALLS.md C7 documents both. **Recommendation:** ship the keep-alive (trivial — `curl` every 10 min) but rehearse the honest-framing recovery as a second safety net.
- **System prompt + fallback strings location** — FEATURES.md suggests `agent/narrative/prompt.txt` + `agent/narrative/fallbacks.json` co-located with tool code. **Recommendation:** decide in Phase 2.1 and commit as part of the locked freeze artefacts. Copy review (not engineer-authored) on fallbacks is a separate pass.
- **FREEZE-MANIFEST format** — YAML (machine-diffable in CI) vs. Markdown (human-readable). **Recommendation:** YAML embedded in a Markdown code fence — CI diffs the YAML, humans read the Markdown.
- **Rollback drill target** — real stack (honest test, risks freeze) vs. scratch DynamoDB restore (proves mechanism, not state). **Recommendation:** scratch restore at T-48h, accept residual risk on real-stack state (covered by `demo-v1.0` tag + `build:mock` fallback as the outer safety net).
- **Whether `demo-v1.0` remains the rollback tag or a `demo-v1.1` is cut** — FEATURES.md flagged this. **Recommendation:** keep `demo-v1.0` as rollback tag; `?narrative=off` flag is the faster lever and covers the primary failure mode without redeploy.

## Sources

### Primary (HIGH confidence)
- v1.0 shipped codebase — `agent/agent.py`, `infrastructure/constructs/*.py`, `ui/src/components/RecommendationCard.tsx`, `api_lambda/handler.py`, `requirements*.txt`, `ui/package-lock.json`
- v1.0 research carry-forward — `.planning/milestones/v1.0-research/{STACK,FEATURES,ARCHITECTURE,PITFALLS}.md`
- v1.0 `PROJECT.md` + `MILESTONES.md` — shipped state, Key Decisions (D-07 mock fallback, D-11 fresh session, D-12 error taxonomy, D-13 don't touch, D-14/D-15 visual rehearsal)
- v1.0 `DEMO-RUNBOOK.md` — T-24h / T-2h / T-0 structure (extended, not rewritten)
- AWS Bedrock AgentCore Developer Guide — 15-min microVM idle timeout, runtime session lifecycle (verified 2026-04-25)
- AWS CloudFormation Protecting Stack Resources — stack policy semantics, termination protection (verified 2026-04-25)
- AWS Lambda Provisioned Concurrency docs — alias-targeting requirement, `$LATEST` exclusion (verified 2026-04-25)
- Pydantic v2 `field_validator` + `Field(max_length=…)` — stable public API
- npm `ci` and `pip-compile --generate-hashes` — documented reproducibility primitives

### Secondary (MEDIUM confidence)
- Specific patch versions for `aws-cdk-lib==2.250.x`, `boto3==1.42.x`, `pip-tools>=7.4.0` — training-data baseline; snap to newest-at-freeze-time during DEMO-04
- AgentCore microVM pool warming semantics (warm-one vs. warm-three persona coverage) — pragmatic inference from 15-min idle timeout + v1.0 fresh-uuid4 pattern; validate in Phase 2.4 rehearsal
- Strands `structured_output()` retry-on-Pydantic-ValidationError behaviour — assumed retry-or-fallback; sanity-check in Phase 2.1
- Latency delta of +200–600ms for ~80 extra output tokens on Claude 3.7 Sonnet — estimate from similar prompt sizes; T-24h DevTools rehearsal is the source of truth
- Agent-assist LLM UX patterns — Amazon Connect Agent Assist, Salesforce Einstein, Google CCAI (training knowledge)

### Tertiary (LOW confidence — needs validation during planning)
- Exact `CfnOutput` names for `ApiEndpoint` and `AgentRuntimeArn` in deployed stack — verify against live stack before wiring `scripts/prewarm.py`
- CDK `add_stack_policy` ergonomics vs. raw CloudFormation `set-stack-policy` — small risk CDK re-synth fights the manual policy
- Specific Bedrock quota headroom for burst Q&A clicks — check at T-2h via `aws service-quotas get-service-quota`
- Whether any v2.0 CDK change introduces a lazy-loaded SDK client that the pre-warm script doesn't cover — audit during Phase 2.4

### Documentation that could not be fetched during research
- `https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/structured-output/` — confirm `structured_output` behaviour under Pydantic `field_validator` exceptions
- `https://pip-tools.readthedocs.io/en/stable/` — snap to latest version number
- `pypi.org/project/bedrock-agentcore/` — confirm the runtime SDK version in the Strands agent container is still current

If any of those show unexpected drift at Phase 2.1 / 2.4 / 2.5 kickoff, escalate before proceeding.

---
*Research completed: 2026-04-25*
*Ready for roadmap: yes*
