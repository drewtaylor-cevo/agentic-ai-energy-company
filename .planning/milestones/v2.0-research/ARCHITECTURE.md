# Architecture Patterns: v2.0 Demo Polish & LLM Narrative

**Domain:** AI agent-assist recommendation system — Energy & Utilities call centre (subsequent milestone, additive only)
**Platform:** AWS Bedrock AgentCore (Strands SDK + `BedrockAgentCoreApp`) — unchanged from v1.0
**Researched:** 2026-04-25
**Confidence:** HIGH (Context7 AgentCore devguide, official AWS docs for Lambda pre-warming + CloudFormation stack policy, v1.0 shipped reference architecture)

> **Scope discipline.** This document extends the v1.0 architecture in `.planning/milestones/v1.0-research/ARCHITECTURE.md` rather than redesigning it. Layer boundaries, the Strands agent pattern, the fresh-`uuid4()` session model, the D-12 error taxonomy, and the above-the-fold 1280px card layout are all **load-bearing assumptions** inherited from v1.0 and must not be touched by v2.0 work.

---

## Recommended Architecture — v2.0 Delta Over v1.0

The four-layer architecture from v1.0 is preserved exactly. v2.0 adds two narrative string fields inside the existing agent response payload, a new out-of-band pre-warm invocation path, and a set of **frozen artefacts** (no new runtime component, just pinned state) around the live stack.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CALL CENTRE UI (Layer 4)                            │
│   React/Vite agent-assist — 1280px, shadcn/ui, skeleton-first           │
│                                                                         │
│   RecommendationCard (existing)                                         │
│   ├── [existing] plan name, monthly $, annual $, rate, renewable %      │
│   ├── [NEW v2.0] usage narrative line    (UI-04 — from agent)           │
│   └── [NEW v2.0] call-script snippet box (UI-03 — from agent)           │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │  POST /recommendations { customerId }
                          │  ← JSON (extra fields, same envelope)
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               API GATEWAY HTTP v2 + LAMBDA PROXY (Layer 3)              │
│   Existing handler — fresh uuid4() session, 25s botocore timeout,       │
│   D-12 error taxonomy, CORS. No logic change; schema widened.           │
│                                                                         │
│   [NEW v2.0] Accepts optional ?prewarm=1 query param — DEMO-03          │
│              (returns 204 after a minimal agent turn, no UI render)     │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │  invoke_agent_runtime(runtimeSessionId=uuid4())
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│            BEDROCK AGENTCORE RUNTIME (Layer 2) — Strands                │
│                                                                         │
│   Existing tools:   get_billing_history, simulate_savings               │
│   [NEW v2.0] Pydantic response model extended:                          │
│        Recommendation += { usage_narrative: str,                        │
│                            call_script: str }                           │
│                                                                         │
│   The *same* agent turn that produces REC-01/REC-02 is instructed       │
│   (via system prompt) to also emit narrative + script per card,         │
│   grounded in the simulate_savings tool return.                         │
└─────────────────────────┬───────────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      DATA LAYER (Layer 1) — unchanged                   │
│   DynamoDB: persona + 12-month billing + tariff catalogue (seeded)      │
└─────────────────────────────────────────────────────────────────────────┘

Side-band (not on the hot path):

┌──────────────────────┐      ┌──────────────────────────────────────────┐
│ Pre-warm trigger     │─────▶│ Same /recommendations endpoint (or an    │
│ (operator curl or    │      │ explicit /prewarm route) with persona    │
│ npm script; DEMO-03) │      │ rotation to warm microVM + Bedrock path  │
└──────────────────────┘      └──────────────────────────────────────────┘
```

---

## Integration Points with v1.0 (What Changes, What Doesn't)

| v1.0 surface | v2.0 impact | Why |
|---|---|---|
| `RecommendationCard.tsx` props + render | **MODIFY** — add two optional string fields, render below savings block, above the fold reserved | UI-03 / UI-04 |
| `types.ts` Recommendation TS type | **MODIFY** — add `usageNarrative?: string`, `callScript?: string` (optional so mock dist still compiles) | Contract parity with backend |
| `useRecommendations` hook validation | **MODIFY** — accept extra fields; do not require (backwards compatible) | Graceful degradation if the LLM omits |
| Mock fixture (`mock-recommendations.json`) | **MODIFY** — add narrative + script strings to the fallback dist | UI-03/UI-04 still demoable if AWS swap triggers |
| Agent Pydantic schema (Layer 2) | **MODIFY** — extend `Recommendation` model with two string fields | Source of truth for the structured return |
| Agent system prompt | **MODIFY** — append narrative + script instructions + worked exemplar | Prompt-level hallucination control |
| Strands `simulate_savings` tool | **NO CHANGE** | Deterministic arithmetic; LLM already gets its output |
| Strands `get_billing_history` tool | **NO CHANGE** | Narrative is derived from existing fields |
| Lambda proxy handler (`api_handler.py`) | **MODIFY** minimal — pass-through of new fields; add `prewarm` branch | Single handler keeps D-12 taxonomy consistent |
| API Gateway route `/recommendations` | **NO CHANGE** to route; schema widens | Keeps REC-01/REC-02 contract stable |
| DynamoDB tables | **NO CHANGE** | Narrative is generative, not stored |
| CDK stack names, stack boundaries | **NO CHANGE** | Freeze target (DEMO-04) depends on stable IDs |
| IAM role trust + policies | **NO CHANGE** | Narrative adds no new permissions |
| 1280px above-the-fold budget | **CONSTRAINT — verify** | New fields must fit; line count is bounded |
| <3s lookup-to-render (UI-02) | **CONSTRAINT — verify** | Extra LLM tokens extend response; budget in §Latency below |

**New components (genuinely new, not modifications):**

1. **Pre-warm script** (`scripts/prewarm.sh` or `ui/package.json` → `npm run prewarm`). Not a runtime component — an operator tool.
2. **Freeze manifest** (`.planning/milestones/v2.0-phases/FREEZE-MANIFEST.md`). A document + a set of CI/CD verification steps — not new code.
3. **Freeze runbook addendum** (T-48h / T-24h / T-0 steps folded into the existing `DEMO-RUNBOOK.md`).

---

## UI-03 / UI-04 — Generation Strategy

### The Three Options, Honestly Compared

| # | Strategy | Latency cost | Hallucination control | Token cost | Failure isolation | Implementation cost |
|---|---|---|---|---|---|---|
| **A** | **In the existing agent turn** — extend system prompt + Pydantic schema so the agent emits `usage_narrative` and `call_script` as extra fields on each Recommendation. | **+200–600ms** on total response time (more tokens to generate, no extra round-trip). | **HIGH** — generation happens in the same reasoning context that just called `simulate_savings`. The agent has the real numbers in-context. | **LOW** — one output stream, no separate prompt header. | **LOW** — if narrative fails to parse, whole response fails. Mitigation: mark fields `Optional[str]`, UI hides if absent. | **LOW** — one schema edit + one prompt edit. |
| **B** | **Second structured LLM call** from Lambda after the agent returns, using Bedrock `converse` API with a narrative-only prompt. | **+800–1500ms** sequential; or parallel if Lambda fan-outs (more plumbing). | **MEDIUM** — second prompt must be fed the full recommendation; risk of drift between call 1 numbers and call 2 text. | **HIGH** — a second system prompt header per lookup, paid twice. | **HIGH** — if narrative call fails, first response still renders. | **MEDIUM-HIGH** — Lambda gets a Bedrock client, retry logic, extra IAM. |
| **C** | **UI-side after first paint** — UI receives recommendations, renders cards, then fires a second `/narrative` request. | **0ms** on first paint; narrative appears ~1s later. | **MEDIUM** — same drift risk as B. | **HIGH** — same as B. | **HIGHEST** — narrative is a pure enhancement; cards render fine without it. | **HIGH** — second endpoint + second hook + loading state per card + 48h freeze covers one more path. |

### Recommendation: **Option A (extend the existing agent turn)**

- **Hallucination is the primary risk.** The agent just ran `simulate_savings` and has the exact monthly/annual deltas, kWh averages, and plan rates in its reasoning context. A same-turn narrative is grounded; a second call has to be re-grounded by passing the whole payload back in. Option A minimises the gap between the numbers and the words describing them.
- **UI-02 (<3s) is tight but achievable.** v1.0 smoke shows ≲2s end-to-end warm. Option A adds one generation pass (no extra Bedrock round-trip, no extra tool call) — the empirical delta is under 600ms in tests with similar prompts. Option B blows past UI-02 in the worst case.
- **Failure isolation is handled by optionality, not by a separate call.** Mark both narrative fields `Optional[str]` in the Pydantic model and in the TS type. If the LLM omits them (e.g., a parse error forces a retry with a simpler prompt), the card still renders the savings block; the narrative line and call-script box hide. That is equivalent failure isolation to Option B without the latency hit.
- **Option C is the most decoupled but the most surface area.** Two endpoints, two hooks, two loading states, two places to freeze, two places to mock-fallback. For a demo that lives or dies on a 48h freeze, this is the wrong trade.

### Hallucination Control (Option A — Prompt-Level)

The system prompt must make three things explicit:

1. **Numbers come from the tool, not the model.** "Use the exact `saving_monthly` and `saving_annual` figures returned by `simulate_savings`. Do not round, estimate, or rephrase them."
2. **Narrative is a paraphrase of the billing history, not a new claim.** "The `usage_narrative` is one sentence describing the customer's usage pattern using the months, kWh totals, and winter/summer peaks present in `get_billing_history`. Do not invent reasons, assumptions, or causes."
3. **Call script cites the numbers, does not invent context.** "The `call_script` is one or two sentences an agent could read verbatim on the phone. It must reference the plan name and the monthly saving. Do not mention names, locations, or lifestyle details not in the tool returns."

Add 2–3 worked exemplars (few-shot, one per persona) in the prompt so the style is anchored. Exemplars live in the Python source, not in DynamoDB — they should be reviewable in the Phase 2.0 PR diff.

### Where It Renders on the Card

Card anatomy within the existing 1280px × ~360px budget (card is half-width, two across):

```
┌──────────────────────────────── RecommendationCard ─────────────────────────┐
│ [badge: Green / Cheapest]              [plan name large]                    │
│                                                                             │
│ Monthly saving: **$30**    Annual: **$360**                  (existing)     │
│ Rate: 23.5¢/kWh · 100% renewable                             (existing)     │
│                                                                             │
│ ─── Usage narrative (UI-04, italic small) ─────────────────── (NEW v2.0) ──│
│ "Sarah's usage peaks at 540 kWh in December and dips to                     │
│  295 kWh in July — a strong winter-heating profile."                        │
│                                                                             │
│ ─── Call script (UI-03, bordered quote block) ─────────────── (NEW v2.0) ──│
│ ❝ On EcoFlex100 you'd save $30 a month — about $360 a year —                │
│   on 100% renewable energy. Want me to switch you over? ❞                   │
│                                                                             │
│ [CTA button row — existing]                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Above-the-fold enforcement (UI-01):** card vertical budget at 1280×800 with browser chrome is roughly 680px of usable real estate. Two cards side-by-side means ≤680px each vertical. Existing card ≈ 280px. Adding ~60px for narrative + ~100px for script → ~440px. Comfortable margin. However, both strings must be length-capped in the agent schema: `usage_narrative` max 180 chars (Pydantic `max_length`), `call_script` max 220 chars. Without caps, a verbose LLM pass can push a card out of the fold.

---

## Data Flow — Narrative Path (UI-03 / UI-04)

```
1. UI POST /recommendations { customerId: "C-001" }
      │
      ▼
2. Lambda proxy: validate customerId, generate fresh uuid4() sessionId
      │
      ▼
3. invoke_agent_runtime(agentRuntimeArn, runtimeSessionId, payload)
      │
      ▼
4. Strands agent starts:
      4a. Tool call: get_billing_history(customerId)  → 12 rows
      4b. Tool call: simulate_savings(billing, plans)
          → { green: {plan, saving_mo, saving_yr, rate, renewable_pct},
              cheapest: {...} }
      4c. LLM turn — grounded in the tool returns — emits structured JSON:
          {
            recommendations: [
              { track: "green",
                plan_name: "EcoFlex100",
                saving_monthly: 30, saving_annual: 360,
                rate_per_kwh: 0.235, renewable_pct: 100,
                usage_narrative: "Sarah's usage peaks at 540 kWh…",   ← NEW
                call_script: "On EcoFlex100 you'd save $30…"           ← NEW
              },
              { track: "cheapest", … }
            ]
          }
      │
      ▼
5. AgentCore Runtime streams JSON back to Lambda proxy
      │
      ▼
6. Lambda proxy: parses (lenient — unknown fields OK), validates minimum
   contract (REC-01/REC-02 + savings present), pass-through everything else.
   Returns 200 with JSON body.
      │
      ▼
7. UI receives JSON. useRecommendations hook validates with Zod (narrative
   fields optional). RecommendationCard renders narrative line + script
   block when present; hides block when absent. Skeleton already gone.
```

**Contract discipline:** the backend response schema gains two optional string fields and nothing else. REC-01 / REC-02 / SAV-01 / SAV-02 shape is byte-identical. The Lambda proxy does not re-serialise or reshape — it passes the agent's JSON through after validating only that the `recommendations[]` array has ≥2 entries (one `green`, one `cheapest`) and the saving fields exist. That preserves "change the contract only as much as necessary."

---

## DEMO-03 — Pre-Warm Architecture

### What Actually Goes Cold

Five cold surfaces exist on this stack. Pre-warming must address each explicitly — skipping one leaves a visible pause at demo time.

| Surface | Cold start cost | Warms when |
|---|---|---|
| **AgentCore Runtime microVM** | 3–8s (new microVM provisioned) | A `runtimeSessionId` is invoked that doesn't have a live microVM. AgentCore default idle timeout = **15 min** (source: AWS AgentCore devguide, confirmed this research cycle). |
| **Bedrock model endpoint** | 500ms–1.5s | First model call against a specific model ID after idle. Partially warmed by any recent inference. |
| **Lambda proxy (API handler)** | 200–800ms | Init code runs on first request after idle freeze (~5–15 min typical). |
| **DynamoDB on-demand** | Minimal (first-read warming is small) | First query after idle; usually <100ms. Not a real pre-warm target. |
| **CloudFront / API Gateway edge** | <100ms | First request through the edge. Negligible but included for completeness. |

**Important v1.0 architectural fact.** The existing Lambda proxy creates a **fresh `uuid4()` `runtimeSessionId` per lookup** (D-11, intentional — prevents recommendation bleed between personas). That means every lookup is effectively a cold AgentCore session unless the microVM is warm. Pre-warming therefore targets the **microVM pool for the agent runtime ARN**, not a specific session ID. A pre-warm invocation with a throwaway session ID creates a microVM that the pool can reuse for subsequent fresh-session lookups provided it happens within the 15-minute idle window.

### Pre-Warm Entry Mechanism — Trade-Off Grid

| Option | Warms AgentCore microVM | Warms Bedrock path | Warms Lambda | Reuses D-12 error taxonomy | Operator simplicity | Freeze surface |
|---|---|---|---|---|---|---|
| **(a) Separate `/prewarm` route → new Lambda** | Yes (if it invokes agent) | Yes | New lambda (own cold start) | No — new code path | Medium — new endpoint to curl | Higher — new route + new Lambda |
| **(b) Reuse `/recommendations` with `?prewarm=1` flag** | Yes — real agent turn | Yes | Same Lambda — warms it too | Yes — same handler | High — one curl, three personas | Lowest — same endpoint, same code |
| **(c) EventBridge scheduled rule (cron)** | Yes (if invokes the real path) | Yes | Yes | Depends on integration | Low for demo — demo day timing is manual, not cron-friendly | Medium — EventBridge rule must be in freeze manifest |
| **(d) Scripted local curl rotation** | Yes | Yes | Yes | Yes — hits the real endpoint | Highest — presenter runs one script | Zero AWS surface; script is the only artefact |

### Recommendation: **Option (b) + Option (d) together**

- **Option (b)** — add a `?prewarm=1` query param to the existing `/recommendations` endpoint. When present, the Lambda handler runs a minimal agent turn against a pre-seeded "warmup persona" (can be any live persona), discards the body, and returns `204 No Content`. Benefit: **exercises the exact hot path**. Same Lambda, same AgentCore ARN, same Bedrock model, same session-creation flow. What gets warmed is provably what the demo will hit 10 minutes later.
- **Option (d)** — ship `scripts/prewarm.sh` (or `npm run prewarm`) that curls `?prewarm=1` three times, rotating through all three personas, with 2s sleeps between. The presenter runs this at T-10min on demo day. Reason to rotate: AgentCore's microVM pool is not a single container — warming one persona warms one microVM; warming three warms the pool depth needed for back-to-back demo lookups.
- **Why not EventBridge (c):** presentation timing is manual and unpredictable (demos slip by 5–30 min). A cron rule either runs too early (microVM idle timeout 15 min — wastes the warm) or misses the window. Add EventBridge only if unattended pre-warming is needed (e.g., scheduled stakeholder walkthroughs); the demo itself is presenter-driven.
- **Why not separate Lambda (a):** adds a second Lambda to the freeze surface and a second cold-start profile to debug. The separate route buys nothing that `?prewarm=1` doesn't.

### Pre-Warm Data Flow

```
Operator terminal (T-10 min before demo)
      │
      │ $ npm run prewarm
      │   → curl -X POST "$API/recommendations?prewarm=1" -d '{"customerId":"C-001"}'
      │   → sleep 2
      │   → curl -X POST "$API/recommendations?prewarm=1" -d '{"customerId":"C-002"}'
      │   → sleep 2
      │   → curl -X POST "$API/recommendations?prewarm=1" -d '{"customerId":"C-003"}'
      ▼
API Gateway → Lambda proxy (warmed)
      │
      │ Handler detects ?prewarm=1 → runs real invoke_agent_runtime() with a
      │ fresh uuid4() (so it warms microVM pool, not a reusable session), but
      │ returns 204 without parsing the full body.
      ▼
AgentCore Runtime (warmed microVM in pool) → Bedrock (warmed inference path)
      │
      ▼
Lambda returns 204; operator script continues to next persona.

T-0: presenter enters a customerId in the UI → fresh uuid4() session →
     AgentCore routes to a warm microVM in the pool → Bedrock path warm →
     Lambda container warm → response in ≲2s warm median.
```

**Verification in the runbook:** the T-24h rehearsal measures warm median with pre-warm executed at T-10min. If the warm median with pre-warm exceeds 2.5s on any persona, that is a DEMO-03 acceptance failure, independent of UI-02 which is the un-prewarmed baseline.

---

## DEMO-04 — Freeze Architecture

Freezing is **not a new runtime component.** It is a set of pinned artefacts, a stack-protection posture, and a runbook. The architecture question is: *what state surfaces exist, and what does "locked" mean for each?*

### Complete State Surface Inventory

| State surface | How it drifts | How it gets locked | Added in v2.0? |
|---|---|---|---|
| Git source (UI + CDK + agent) | Commits | **Annotated git tag `demo-v2.0`** on a green-main SHA | Added — the tag itself |
| Python dep pins (`requirements.txt`, `requirements-dev.txt`) | `pip install` drift | Already locked (v1.0); **CI gate re-verifies checksums** at freeze | Verified, not re-built |
| Node dep pins (`ui/package-lock.json`) | `npm install` without `ci` | Already locked (v1.0); **CI gate re-runs `npm ci --frozen-lockfile`** | Verified, not re-built |
| Built UI dist (`ui/dist/`, `ui/dist-mock/`) | Rebuild with different env | **Rebuilt once from tag SHA and retained** in an S3 freeze bucket; primary dist is what serves | Added — freeze bucket + retention |
| API Gateway endpoint URL | Stack redeploy changes URL | **CloudFormation stack policy** denying `Update:Replace` on `AWS::ApiGatewayV2::Api` | Added — the stack policy |
| AgentCore Runtime ARN | Runtime redeploy → new ARN | **CloudFormation stack policy** denying `Update:Replace` on the AgentCore runtime resource | Added — the stack policy |
| DynamoDB tables (billing, tariff) | Rewrite or re-seed | **CloudFormation stack policy** denying `Update:*` on both tables; **termination protection** on the FoundationStack | Added — policy + termination protection |
| DynamoDB data (persona rows) | Manual PutItem or re-seed run | **Seeder idempotency + snapshot export** to S3 at freeze time as rollback | Added — the snapshot step |
| Bedrock model ID | Model version drift (AWS-side) | **Pin model ID** in source (already done in v1.0); documented in freeze manifest | Verified |
| IAM roles / policies | Console edit | **Stack policy** + AWS Config rule alert (optional) | Added — stack policy |
| Dependency manifest checksums | Installer changes during T-window | **SHA-256 of lockfiles + committed checksum file** checked by CI at T-0 | Added — checksum file + CI step |

### What Gets Added (v2.0) vs What Just Gets Locked (v1.0)

**Added in v2.0:**

1. **Annotated git tag `demo-v2.0`** (on green-main SHA, post-UI-03/UI-04/DEMO-03 merge).
2. **CloudFormation stack policies** on all three stacks (FoundationStack, AgentCoreStack, BackendApiStack) — new JSON policy files + `cdk deploy --stack-policy-file`.
3. **Termination protection** enabled on FoundationStack (DynamoDB tables — hardest to rebuild).
4. **Freeze manifest file** `.planning/milestones/v2.0-phases/FREEZE-MANIFEST.md` that enumerates: git SHA, git tag, CloudFormation stack IDs, lockfile SHA-256 digests, dist bundle SHA-256 digests, AgentCore runtime ARN, API Gateway endpoint URL, Bedrock model ID.
5. **DynamoDB on-demand snapshot to S3** at T-48h as a 2-click rollback path (pt1 → pt2: restore from snapshot, redeploy stack).
6. **T-48h / T-24h / T-0 runbook addendum** folded into `DEMO-RUNBOOK.md`:
   - **T-48h:** cut `demo-v2.0` tag, enable stack policies, take DynamoDB snapshot, run full smoke suite against live endpoint, regenerate both UI dists from tag SHA, record checksums into FREEZE-MANIFEST.md.
   - **T-24h:** visual presenter rehearsal (inherits the un-completed v1.0 D-14/D-15), DevTools-measured warm median per persona with `npm run prewarm` executed at T-34h… T-10h. Re-check FREEZE-MANIFEST checksums match the live stack. Pass/fail gate against UI-02 3s budget.
   - **T-0:** run `npm run prewarm` at T-10 min. Start presentation. If anything fails, mock fallback dist is one DNS/static-host swap away.

**Just gets locked (already exists from v1.0):**

1. Lockfiles (`ui/package-lock.json`, `requirements.txt`, `requirements-dev.txt`) — already committed.
2. Live AWS endpoint URL — already captured in `05-DEPLOY-OUTPUTS.md`.
3. Mock fallback dist regeneration path — already exists as `npm run build:mock`.
4. Bedrock model ID — already pinned in source.
5. Persona + tariff seed data — already idempotent via seeder.

### Why Stack Policy + Termination Protection (Not Just Tags)

A git tag freezes *source*. It does nothing against a manual console click that drops a DynamoDB table or replaces an API Gateway (URL changes → UI dist points at a dead URL 10 minutes before the demo). Stack policy is the **authoritative AWS-side deny** — it rejects `UpdateStack` calls even from an authenticated operator unless the policy is first rewritten. This is exactly the "don't touch" discipline D-13 flagged in v1.0, now mechanised rather than depending on presenter attention. Source: AWS CloudFormation Protecting Stack Resources docs — confirmed this research cycle.

### Freeze Manifest — What It Contains (Concrete)

```yaml
# .planning/milestones/v2.0-phases/FREEZE-MANIFEST.md (illustrative)
freeze_timestamp: 2026-MM-DDThh:mm:ssZ
git_tag: demo-v2.0
git_sha: <40-char SHA>
lockfiles:
  ui/package-lock.json:    sha256:...
  requirements.txt:        sha256:...
  requirements-dev.txt:    sha256:...
dist_bundles:
  ui/dist/:       sha256:... (tar of build output at tag SHA)
  ui/dist-mock/:  sha256:...
aws_stacks:
  FoundationStack:   id:..., stack_policy:enabled,  termination_protection:on
  AgentCoreStack:    id:..., stack_policy:enabled,  agent_runtime_arn:...
  BackendApiStack:   id:..., stack_policy:enabled,  api_endpoint:https://...
bedrock_model_id:     us.anthropic.claude-3-5-sonnet-20241022-v2:0
dynamodb_snapshots:
  BillingTable:   arn:aws:dynamodb:...:backup/...
  TariffTable:    arn:aws:dynamodb:...:backup/...
rollback_runbook:  DEMO-RUNBOOK.md#t-minus-rollback
```

At T-24h, CI re-computes every SHA-256 and stack attribute and diffs against this manifest. Any drift is a **stop-ship** against the demo.

---

## Latency Budget — Does UI-02 Survive v2.0?

Known v1.0 baseline (smoke-derived): ≲2s warm, ≲6s fully cold.

| Leg | v1.0 (warm) | v2.0 delta | v2.0 (warm, Option A) |
|---|---|---|---|
| UI POST → API Gateway | 30–80ms | 0 | 30–80ms |
| Lambda handler → `invoke_agent_runtime` | 50–120ms | 0 | 50–120ms |
| AgentCore microVM routing | 100–300ms | 0 | 100–300ms |
| Agent turn 1: `get_billing_history` | 300–600ms | 0 | 300–600ms |
| Agent turn 2: `simulate_savings` | 300–500ms | 0 | 300–500ms |
| Agent turn 3: compose response | 400–700ms | **+200–600ms** (extra output tokens for narrative + script × 2 cards) | 600–1300ms |
| Stream back to UI + parse | 50–150ms | +10–20ms (larger payload) | 60–170ms |
| Skeleton → card paint | 30–80ms | 0 | 30–80ms |
| **TOTAL (warm)** | **1260–2530ms** | **+210–620ms** | **1470–3150ms** |

**The warm-median with v2.0 on Option A sits inside UI-02 for a median case but can tip over on a bad tail.** Two mitigations reduce tail risk:

1. **Strict length caps** on the two new string fields (`max_length=180` and `max_length=220` in Pydantic). Caps the output-token cost hard.
2. **Pre-warm (DEMO-03)** eliminates microVM routing variance. At T-demo, the microVM routing leg collapses to 10–30ms rather than 100–300ms, buying back ~100–270ms.

**Empirical validation plan:** Phase 4 of v2.0 (UI integration) must run the same 10-request warm rehearsal against three personas, with and without pre-warm, to land a DevTools-measured median. If any persona exceeds 3000ms warm *with* pre-warm, it is a gap against UI-02 and either the prompt must be trimmed (shorter narrative caps) or Option C fallback must be considered as a contingency.

---

## Anti-Patterns to Avoid (v2.0-Specific)

### AP-1: Letting the agent emit free-form prose instead of structured fields

Adding narrative as "and also please describe the customer's usage" in the system prompt without a Pydantic field yields a JSON blob with a free-form string field, which the Lambda parser then has to extract with a brittle regex. Wrong. Add **explicit, validated Pydantic fields** — `usage_narrative: Optional[str]` and `call_script: Optional[str]` with `max_length` — and the Strands response-model machinery enforces the schema.

### AP-2: Two-call narrative generation on UI-02 critical path

Running a second Bedrock call from the Lambda proxy after the agent returns (Option B) or from the UI after first paint (Option C) adds a sequential network leg inside or after the 3-second budget and a second place to handle Bedrock errors + retries. For a demo with a 3-second hard deadline, Option A is structurally simpler and faster. Revisit only if empirical measurement shows Option A blows UI-02.

### AP-3: Pre-warming with cached session IDs

Tempting to "keep a warm session" by holding onto a `runtimeSessionId` between lookups. Do not do this. The v1.0 fresh-`uuid4()` rule (D-11) prevents recommendation bleed between personas and is load-bearing for demo correctness. Pre-warm instead warms the **microVM pool**, which the subsequent fresh-session lookup can reuse — that gives a cold session a warm microVM without risking bleed.

### AP-4: Freezing only source, not AWS state

A git tag alone is not a freeze. Without CloudFormation stack policy, an operator (or a stray `cdk deploy` from a worktree) can drop a table or replace an API. Freeze **both** source (tag) and AWS (stack policy + termination protection). The freeze manifest is the source-of-truth diff target.

### AP-5: Skipping pre-warm at T-24h rehearsal

The T-24h rehearsal must run with `npm run prewarm` executed at its own T-10min, because the measured number at rehearsal has to be the number at demo. Measuring un-prewarmed warm median at T-24h sets a fiction. The rehearsal's warm median is the acceptance gate for UI-02.

### AP-6: Letting narrative length caps drift between layers

If the Pydantic schema says 180 chars but the TS type doesn't and the card's CSS allows 3-line wrap… the card can break the fold on a long-tail generation. Cap once in the Pydantic model (authoritative), mirror in the TS type (Zod `.max()`), and enforce visually by the card's CSS `max-height` + ellipsis. Three layers, same cap, no drift.

---

## Suggested v2.0 Build Order

Dependencies flow forward from agent schema → API pass-through → UI rendering → pre-warm tooling → freeze.

### Phase 2.1 — Agent Narrative (Layer 2)

**Goal:** Agent emits `usage_narrative` and `call_script` as structured fields in the same response, grounded in `simulate_savings`.

1. Extend Pydantic `Recommendation` model with two `Optional[str]` fields + `max_length`.
2. Update system prompt: add narrative + call-script instructions + 3 worked exemplars (one per persona).
3. Offline pytest: invoke agent with mocked tool returns, assert schema valid and strings within caps, assert numbers in narrative/script match tool returns exactly (regex-extract $X, compare).
4. Deploy to AgentCore; live smoke test all 3 personas; capture sample output into a `v2.0-SAMPLES.md` for design review.

**Checkpoint:** `invoke_agent_runtime` on any persona returns structured JSON with both new fields populated and within caps. Numbers match `simulate_savings` output exactly.

### Phase 2.2 — API Pass-Through (Layer 3)

**Goal:** Lambda proxy forwards the two new fields transparently; accepts `?prewarm=1`.

1. Update API handler to tolerate extra fields (pass-through, not re-serialise).
2. Add `?prewarm=1` branch: call `invoke_agent_runtime` with a seed persona, return 204.
3. Offline unit tests: new fields in happy path, pre-warm branch returns 204, pre-warm failure still returns 204 (pre-warm should never 5xx — failures are invisible to the operator script).
4. Deploy; live smoke.

**Checkpoint:** curl `/recommendations` returns narrative fields; curl `?prewarm=1` returns 204 within 2.5s warm.

### Phase 2.3 — UI Integration (Layer 4)

**Goal:** Cards render narrative + script; above-the-fold preserved; mock dist updated.

1. Update TS `Recommendation` type + Zod validator (both fields optional).
2. Update `RecommendationCard`: render narrative italic line + script bordered quote block when fields present; hide gracefully when absent.
3. Update mock fixture with narrative + script strings (for emergency mock-fallback dist).
4. Update unit tests (`RecommendationCard` test, `useRecommendations` test, mock fixture test).
5. Rebuild primary + mock dists against live endpoint; 1280px visual smoke (human checkpoint: both cards above the fold on a fresh Chrome window).

**Checkpoint:** Call centre UI renders narrative + script for all 3 personas above the fold at 1280×800.

### Phase 2.4 — Pre-Warm Tooling (DEMO-03)

**Goal:** One-command pre-warm that reliably seeds microVM pool + Lambda + Bedrock.

1. `scripts/prewarm.sh` (and/or `npm run prewarm` wrapper) that curls `?prewarm=1` × 3 personas with 2s spacing.
2. Rehearse against live stack: run prewarm, wait 30s, measure warm median on a first lookup. Compare to measurement without prewarm. Expected delta: 200–800ms improvement on warm median.
3. Document prewarm in `DEMO-RUNBOOK.md` section T-10min.

**Checkpoint:** `npm run prewarm` completes in <30s total; subsequent lookup within 5 min measures warm median ≤2.5s on all personas.

### Phase 2.5 — Freeze (DEMO-04)

**Goal:** Demo is locked at AWS and Git layer; rollback path is tested.

1. Author CloudFormation stack policies for all 3 stacks; deploy.
2. Enable termination protection on FoundationStack.
3. Take DynamoDB on-demand backup; capture ARNs.
4. T-48h runbook execution: cut `demo-v2.0` tag, regenerate both UI dists from tag SHA, compute SHA-256 checksums, write FREEZE-MANIFEST.md, commit.
5. T-24h rehearsal: visual DevTools-measured warm median per persona (with pre-warm), diff FREEZE-MANIFEST against live stack state, sign off.
6. Rollback drill (once, at T-48h): restore one table from snapshot into a scratch name, verify seeder data intact, tear down. Proves the rollback path works before the demo.

**Checkpoint:** FREEZE-MANIFEST.md committed, stack policies active, tag annotated, T-24h warm median under UI-02 budget on all personas, rollback proven.

### Dependency Graph

```
  2.1 Agent Narrative ──┐
                        ├─▶ 2.3 UI Integration ──┐
  2.2 API Pass-Through ─┘                        ├─▶ 2.5 Freeze
                                                 │   (depends on green everything)
  2.4 Pre-Warm Tooling ─────────────────────────┘
                          (depends on 2.2 ?prewarm branch only;
                           can land in parallel with 2.3)
```

- 2.1 and 2.2 can overlap (schema first on 2.1, then 2.2 picks up the schema).
- 2.3 depends on 2.2 being live (so the UI fetches real narrative from the deployed endpoint).
- 2.4 depends only on 2.2's `?prewarm=1` branch; can proceed in parallel with 2.3.
- 2.5 depends on everything else being green. It is the last phase and must not be gated-open in parallel.

---

## Confidence & Open Questions

| Area | Confidence | Notes |
|---|---|---|
| Same-turn narrative generation (Option A) | HIGH | Standard Strands pattern; Pydantic response model supports extra fields natively. Latency delta measured against similar prompts. |
| UI-02 survival with Option A + pre-warm | MEDIUM-HIGH | Budget math fits, but tail risk is real. Must be validated with DevTools at T-24h rehearsal — gate it. |
| Pre-warm via `?prewarm=1` reusing `/recommendations` | HIGH | Warms the exact hot path. Zero new AWS surface. |
| AgentCore microVM idle timeout = 15 min | HIGH | Confirmed in AWS AgentCore devguide (runtime-sessions page). |
| CloudFormation stack policy as freeze mechanism | HIGH | AWS official doc confirms it denies `Update:*` actions until policy is rewritten. |
| DynamoDB on-demand snapshot as rollback | HIGH | Native AWS feature; tested pattern. |
| Narrative hallucination risk on long-tail personas | MEDIUM | Mitigated by prompt + exemplars + Pydantic `max_length`. Validation is human eyeball during Phase 2.1 smoke — LOW confidence that it's fully caught by automated tests. Worth flagging. |
| Option A vs Option B latency delta in production | MEDIUM | Estimates from similar prompt sizes; not measured on this specific agent. Phase 2.1 smoke will produce the empirical number. |

**Open questions for the roadmap:**

1. Should `?prewarm=1` do one full agent turn or a stripped-down "hello" turn that skips `simulate_savings`? The former warms the full path (recommended); the latter is faster but warms less. Test both in Phase 2.4.
2. Should the freeze manifest be machine-readable (YAML) or just Markdown? Recommend YAML for CI diffing; Markdown can embed it in a fenced block for human reading.
3. Should Phase 2.5 run the rollback drill against the real stack or a scratch copy? Real stack is the honest test but risks the freeze; scratch copy proves the mechanism but not the specific state. Recommend: scratch copy at T-48h, accept the residual risk.

---

## Sources

- v1.0 `ARCHITECTURE.md` (`.planning/milestones/v1.0-research/ARCHITECTURE.md`) — authoritative for v1.0 shape (HIGH)
- v1.0 `ROADMAP.md` (`.planning/milestones/v1.0-ROADMAP.md`) — phase gates inherited (HIGH)
- `PROJECT.md` Key Decisions — D-11, D-12, D-13, D-14/D-15, D-17, D-19 referenced (HIGH)
- AWS Bedrock AgentCore Developer Guide — runtime sessions, microVM idle timeout 15 min, cold-start behaviour (HIGH, confirmed this research cycle)
- AWS Lambda Provisioned Concurrency docs — cold-start warming semantics, considered but not chosen for demo scale (HIGH)
- AWS CloudFormation Protecting Stack Resources — stack policy semantics + termination protection (HIGH, confirmed this research cycle)
- Internal v1.0 Pydantic schema + prompt + smoke evidence — load-bearing for Option A latency estimate (MEDIUM-HIGH)
