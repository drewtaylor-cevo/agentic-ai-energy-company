# Feature Landscape: v2.0 Demo Polish & LLM Narrative

**Domain:** Call centre agent-assist — LLM narrative on pre-computed recommendations + live on-stage AWS demo hardening
**Milestone:** v2.0 (extends v1.0 — UI-03, UI-04, DEMO-03, DEMO-04)
**Researched:** 2026-04-25
**Confidence note:** Web research tools restricted in this environment. Findings draw on training knowledge of agent-assist LLM UX patterns (Amazon Connect Agent Assist, Salesforce Einstein, Google CCAI), AWS Bedrock AgentCore and Lambda operational characteristics, and live on-stage demo hardening practices. Core patterns are HIGH confidence; specific AgentCore warmup timings are MEDIUM and flagged for rehearsal validation. This file **extends** `.planning/milestones/v1.0-research/FEATURES.md` — v1.0 table stakes (customer lookup, billing display, two-card layout, savings headline, current plan display) are assumed shipped and not re-researched here.

---

## Scope Reminder

v1.0 (already shipped) established:
- Customer-ID lookup → two recommendation cards (Green + Cheapest) with deterministic $/mo and $/yr savings
- Skeleton-first render, both cards above the fold at 1280px, lookup-to-rendered <3s
- `simulate_savings` pure-Python tool locks $30/$55 deltas per persona
- Live AWS stack in `us-east-1` (Bedrock AgentCore Runtime + Lambda + API Gateway HTTP v2 + React/Vite)
- DEMO-RUNBOOK with T-24h/T-2h/T-0 checklist and `demo-v1.0` reproducibility tag

v2.0 adds narrative text **around** the already-shipped numbers (never replacing them) and hardens the environment for a single live on-stage presentation. The v1.0 FEATURES.md flagged "usage pattern narrative" and "call script snippet" as **differentiators** — v2.0 promotes both to scope and nails down the quality bar, failure modes, and demo-hardening playbook.

---

## Table Stakes (v2.0)

Features without which the v2.0 narrative demo falls flat or becomes risky on stage.

| Feature | Why Expected | Complexity | Depends On (v1.0) | Notes |
|---------|--------------|------------|-------------------|-------|
| **LLM call-script snippet per card (UI-03)** — one short sentence the agent can read verbatim | The entire v2.0 pitch is "LLM puts words in the agent's mouth." Without it there is no demo | Medium | Both cards rendered (v1.0), deterministic `$X/mo` figure available pre-narration | Target ≤22 words (≈130 chars). Second-person ("you"), warm retail tone, never opens with "Our AI recommends…" |
| **LLM usage-narrative per card (UI-04)** — one short sentence summarising the customer's usage profile | Makes the recommendation feel personalised rather than generic; justifies "why this plan for this customer" | Medium | 12-month billing history in agent context (v1.0 DATA-01), `simulate_savings` tool output | Target ≤20 words. Descriptive not prescriptive — talks about *customer*, not plan |
| **Deterministic fallback string per card** | LLM can return too-long / on-topic-but-wrong / empty string / PII-adjacent output. Card must still render something safe, always | Low | Card component + both narrative slots present in DOM | Hardcoded per-persona + per-card fallbacks. Must be indistinguishable to the audience if the LLM is suppressed |
| **Output validator (length + number-guard + banned-terms)** | Must reject bad LLM output *before* it reaches the DOM. This is the guardrail that makes UI-03/UI-04 demoable | Medium | API response path (v1.0), card render path | Validate length, strip/replace if dollar figure appears that disagrees with the tool figure, reject on banned-terms list |
| **Skeleton shimmer on narrative slots during generation** | Cards render instantly (v1.0 skeleton-first), narrative streams in after. Empty text slot looks broken; shimmer looks intentional | Low | v1.0 skeleton-first render pattern | Two skeleton rows per card — one for usage narrative, one for call script |
| **Pre-warm script — personas + model path (DEMO-03)** | v1.0 smoke showed ≲2s warm; cold AgentCore + Lambda can be 5–15s. On stage, one cold request is fatal | Medium | Live API endpoint, 3 persona IDs, `demo-v1.0` deployed stack | Pre-warm each persona through the full UI path, not just the Lambda. Runs T-5min before go-live |
| **Pinned deps + locked AWS state @ T-48h (DEMO-04)** | The worst demo failure mode is "it worked yesterday." Freeze everything the moment rehearsal passes | Low | `requirements.txt`, `requirements-dev.txt`, `ui/package-lock.json` already committed (v1.0) | Freeze = tag + changelog entry + a deploy-freeze note on the stack. No deploys between T-48h and T-0 |
| **Rollback to v1.0 narrative-off path** | If v2.0 LLM path is flaky during final rehearsal, agent must be able to ship the v1.0 demo instead. v2.0 must degrade gracefully, not catastrophically | Low | `demo-v1.0` tag, v1.0 mock-fallback dist | Feature-flag UI-03/UI-04 so narrative can be disabled without redeploy |

**Confidence: HIGH** — these are the minimum gates for (a) an LLM-in-the-loop UI on a regulated-industry demo and (b) a single-shot on-stage AWS demo with paying customers watching. Missing any one of these items turns a predictable demo into a gamble.

---

## Differentiators (v2.0)

Features that meaningfully raise the v2.0 demo quality beyond the minimum. Ship if time permits; defer without guilt if not.

| Feature | Value Proposition | Complexity | Depends On | Notes |
|---------|-------------------|------------|------------|-------|
| **Streaming narrative render** | Narrative appears token-by-token (not all-at-once after 2s). Makes the LLM *feel* live on stage | High | Lambda response shape, React fetch/stream plumbing | Use server-sent events or incremental JSON. Optional — deterministic fallback never streams. Only valuable if rehearsal shows it reliably reaches the end of the string. **If streaming breaks mid-sentence on stage, it's worse than no streaming** |
| **Persona-of-voice lock** — "warm retail agent, Australian English, no jargon" | Consistency across personas + across runs. Avoids one card sounding formal and another sounding chatty | Low | System prompt, validator | Encode as a frozen system prompt + 2–3 few-shot examples. Check in as a locked file, treat as a requirement artefact |
| **LLM warm-path eval harness** | A tiny pytest that invokes the agent end-to-end for each persona and asserts the narrative passes the validator. Runs pre-demo | Medium | Pytest infra (v1.0), Bedrock credentials | Not a unit test — a "does the live stack still produce acceptable strings" check. Runs as the last step of the DEMO-03 pre-warm |
| **Narrative-only feature flag (runtime)** | Toggle UI-03/UI-04 off from the browser URL (`?narrative=off`) at the podium without redeploy | Low | UI routing/query-param plumbing | Insurance. If narrative misfires in the middle of a demo, the presenter can continue with v1.0-shaped cards |
| **Pre-computed narrative cache for demo personas** | Generate all 6 strings (3 personas × 2 cards) offline, commit the canonical versions, serve them fast via the normal API path | Medium | 3 seeded personas, `simulate_savings` output | Controversial — blurs "the LLM is live" message. Worth it if Bedrock output variance is high. Can coexist with a live-generation path behind a flag |
| **Presenter tooltip: show the raw LLM response** | Alt-click on a card reveals the raw LLM output + validation verdict, for Q&A and post-demo debugging | Low | Validator output available to UI | Invisible to audience; useful for the presenter if challenged on "is this really the LLM?" |
| **Narrative telemetry — capture every generated string** | Write each prompt/response pair to S3 (or CloudWatch Logs) with persona + timestamp. Invaluable for post-demo debrief and the v3 pitch | Low | Existing CloudWatch log path | Write-only; no UI |
| **Graceful LLM timeout budget** | Hard cap narrative generation at e.g. 1500ms from Lambda start. If not back by then, fall back silently | Low | Existing Lambda botocore timeout (25s v1.0) + in-Lambda timer | Separate from the 25s Lambda ceiling. The UI already has skeleton shimmer — this lets it resolve to the fallback instead of a long spinner |

**Confidence: HIGH** on persona-of-voice lock, eval harness, feature flag, telemetry, timeout budget — these are well-established agent-assist productionisation patterns. **MEDIUM** on streaming (genuine demo risk — can be worse than no streaming if it breaks mid-sentence) and pre-computed cache (philosophical tradeoff against the "live LLM" message).

---

## Anti-Features (v2.0)

Explicit "do not build" list — each has a named failure mode that would damage the demo, the product, or both.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|--------------------|
| **LLM quoting dollar figures** (e.g. "could save you $32.14/month") | The deterministic tool is the source of truth for all numbers. If LLM says $32 and the card says $30, the demo is dead. Numbers on the card are a matter of trust; LLM narrative only adds flavour | Prompt explicitly forbids numerics; validator strips any `$\d+` or `\d+%` pattern and logs it as a violation. Card renders the tool-computed number; narrative refers only to "your savings" or "these savings" |
| **LLM making switch/action claims** (e.g. "I'll move you to Green now", "switching now") | Recommendation-only is a v1.0 validated constraint. Compliance / regulated-utility issue; also trains the wrong behaviour in call centre agents | Banned-terms list in validator: "switch you", "move you", "change your plan", "I'll", "let me just". System prompt enforces "agent reads this *to* customer"  |
| **LLM referencing competitors or other retailers** | Out of scope per PROJECT.md; legally hazardous; dilutes the retention message | System prompt forbids named utilities; validator checks against a banned-list of the 5–6 AU retailer names (Origin, AGL, EnergyAustralia, Red Energy, Alinta, Momentum) |
| **LLM making green/environmental claims beyond the plan's literal attributes** | "Green" plan attributes (% renewable, certification) are in plan data. LLM inventing "carbon-negative" or "100% wind" is a regulatory issue (greenwashing) | Usage narrative must not discuss environmental attributes. If Green card script mentions green-ness, it must use plan-portfolio-provided phrasing only |
| **Second LLM to critique the first LLM's output** | Adds latency, adds failure modes, still doesn't guarantee correctness, and is not demoable on a 3-day sprint | Deterministic rule-based validator only. Regex + length + banned-terms. Ship-the-known-good |
| **Streaming character-by-character for effect alone** | Fake-typing animation when the LLM response is actually already returned in full. Looks cool; wastes seconds; confuses audience when combined with actual streaming | If you stream, stream the real tokens. Otherwise render instantly |
| **Re-generating narrative on every lookup for the seeded demo personas** | Variance across runs is demo risk. The third time a presenter runs PERSONA-A during rehearsal, a different-sounding narrative shakes confidence | Either (a) pre-compute canonical strings and cache per persona, or (b) pin temperature to 0 and set deterministic sampling, or (c) both |
| **Provisioned Concurrency on the production Lambda for the demo window** | Expensive and the wrong tool. Lambda warmth lasts ~5–15 min idle; pre-warm covers the demo. Provisioned concurrency stays on forever and bills accordingly | Pre-warm script 5 min before go-live. Accept that the 24-hour demo window is covered by natural invocations + rehearsal traffic |
| **Changing AWS stack during the T-48h freeze window** | The primary demo failure mode is "I just tweaked one thing." Zero-change window is the entire point of the freeze | If a genuine bug is discovered inside the freeze, the rollback is `git checkout demo-v1.0` and present v1.0. Do not fix-forward under pressure |
| **Live model swaps / model A/B during the demo** | Any narrative variance during the presentation is a risk. Pin the exact Bedrock model ID + version + region in CDK | Model ID is a CDK constant. If future experimentation needs a swap, it happens in a parallel stack, not the demo stack |
| **Free-text chat with the AI** (re-confirmed from v1.0) | Scope creep; agents won't use it under call pressure | Pre-defined flow only — lookup → cards |
| **"Regenerate narrative" button in the UI** | Tempting but a demo trap. If the presenter clicks it on stage and it produces a worse result, there's no way back | No regenerate button in v2.0. If needed for debug, it's in the alt-click presenter tooltip |

**Confidence: HIGH** across the anti-feature list. Each item either maps to a named compliance or demo-risk failure mode, or is a well-documented LLM UX anti-pattern.

---

## UI-03 (Call Script Snippet) — Quality Bar

What "good" looks like, enforced via prompt + validator.

### Shape
- **Length:** target 14–22 words, hard cap 30 words (≈180 chars). Agent must be able to read it in one breath, mid-call, without breaking eye contact with their screen
- **Reading level:** Year 8 / Grade 8 equivalent (plain English, no jargon, no "optimise", "utilise", "portfolio")
- **Person:** second person to the customer ("you", "your") — the agent reads it *to* the customer
- **Tone:** warm, professional, retail — Australian English (but avoid slang)
- **Structure:** single sentence. Optionally ends on a soft question (*"...want me to set that up?"*)
- **Forbidden content:** dollar figures (any `$\d+`), percentages (`\d+%`), competitor names, switch/commit verbs ("switching you", "I'll change"), environmental superlatives

### Worked examples (acceptable)
- Green card: *"Mrs Chen, based on your usage, our Green plan could bring your bill down noticeably — want me to walk you through the details?"*
- Cheapest card: *"Mr Patel, looking at the last twelve months, our Value plan would be a better fit — would you like me to set that up?"*

### Worked examples (reject)
- ~~"Mrs Chen, I can save you $30 a month on Green — let me switch you now."~~ → contains `$30`, contains `switch you now`
- ~~"Our AI recommends Green Plus for optimal value optimisation."~~ → third person, jargon, no customer-you
- ~~"Compared to AGL's basic tariff..."~~ → competitor reference

### Failure modes the validator catches
| Failure | Detection | Response |
|---------|-----------|----------|
| >30 words or >200 chars | Length check | Fallback string |
| Contains `\$\d+` or `\d+%` | Regex | Fallback string |
| Contains banned switch verbs | Substring match on list | Fallback string |
| Contains any competitor name | Substring match on list | Fallback string |
| Empty / whitespace only | Length check | Fallback string |
| Tool timeout / Bedrock error | Exception | Fallback string |
| Prompt-injection style content (agent instructions, role references, "as an AI...") | Substring match + sentinel phrases | Fallback string + log |

### Fallback hierarchy
```
1. Valid LLM output              → render
2. LLM output that fails validator → deterministic per-persona × per-card fallback
3. LLM call errored or timed out  → deterministic per-persona × per-card fallback
4. No persona match (shouldn't happen) → generic card-type fallback
```

The fallback strings are committed to source, reviewed for quality once, then frozen.

**Confidence: HIGH** on the shape and validator rules (these are agent-assist UX conventions). **MEDIUM** on the exact length cap — worth calibrating against the rehearsal clip of a presenter reading the string aloud.

---

## UI-04 (Usage Narrative) — Quality Bar

### Shape
- **Length:** target 10–20 words, hard cap 25 words
- **Reading level:** same as UI-03 (Grade 8)
- **Person:** third person *about* the customer ("high evening usage", "peaks in winter") — this is for the agent to read *before* engaging, not to read aloud
- **Tone:** descriptive analyst, not prescriptive recommender
- **Structure:** noun phrase or short declarative. No call to action
- **Forbidden content:** all of UI-03's forbidden list, plus **any prescription** ("should switch", "would save") — UI-04 is diagnosis, UI-03 is pitch
- **Separation of concerns:** UI-04 describes the customer; UI-03 addresses the customer. Validator should enforce that UI-04 contains no second-person pronouns

### Worked examples (acceptable)
- *"High evening and weekend usage, with clear winter heating peaks."*
- *"Moderate, even usage year-round — typical for a single-occupant apartment."*
- *"Seasonal cottage pattern — very low usage from April to September."*

### Worked examples (reject)
- ~~"This customer should switch to Green to save money."~~ → prescription (UI-03 territory)
- ~~"Your usage is high in evenings."~~ → second person (UI-03 territory)
- ~~"Customer uses lots of power."~~ → too vague, not diagnostic, reading-level regression

### Fallback strategy
Same hierarchy as UI-03. Each of the 3 seeded personas has a canonical hand-written usage narrative as the fallback. These are safe defaults even if no LLM is invoked.

**Confidence: HIGH**.

---

## DEMO-03 (Pre-Warm) — Playbook

### What a "pre-warm" does
Takes each component in the hot path from cold to warm so the *first* on-stage lookup doesn't pay cold-start cost. Must cover:

| Component | Cold state | Warm state | Warm window (typical) |
|-----------|------------|------------|------------------------|
| Lambda (API handler) | New container, imports not loaded | Imports loaded, boto3 client cached | ~5–15 min idle, AWS-discretionary |
| Bedrock AgentCore Runtime | Agent session may not exist / stale session | Active session, system prompt + tools loaded | Session-scoped; fresh `uuid4` per invocation in v1.0 — each new session pays init cost |
| Bedrock model endpoint | Model not recently invoked in this region | Model recently invoked; reduced first-token latency | Minutes, AWS-discretionary |
| API Gateway | Always warm (managed) | N/A | N/A |
| DynamoDB | Always warm; on-demand scales automatically | N/A | First PITR / scale event is not on hot path |
| CloudFront / UI static assets | Edge cache may be cold at a location | Edge cache warm | Hours |

### Checklist (pre-demo)

**T-30 min:**
- [ ] Confirm `demo-v1.0` + `demo-v2.0` tags match deployed stack — no drift since freeze
- [ ] Confirm AgentCore Runtime ID matches CDK output
- [ ] Presenter's browser: hard reload (Cmd-Shift-R) to refresh the UI assets
- [ ] Presenter's browser: confirm `?narrative=off` fallback still works (flip flag, flip back)

**T-10 min:**
- [ ] Run pre-warm script `scripts/pre_warm_demo.py` (or equivalent) which:
    - POSTs to `/recommendations` for each persona ID (×3)
    - Waits for response (fails loudly on any non-200 or >3s warm response)
    - Repeats once (second pass confirms warm)
    - Runs the eval harness — asserts each narrative passes the validator
- [ ] Capture the response latencies; fail the checklist if any is >3000ms warm
- [ ] Confirm CloudWatch Logs received one log entry per persona with no ERROR level events

**T-5 min:**
- [ ] Final warm ping through the UI (not just the API) — open presenter laptop, lookup each persona, eyeball the cards. **If this step fails, do NOT go live — switch to v1.0 `?narrative=off`**
- [ ] Do not touch anything after this step

**T-0 (go live):**
- [ ] Presenter drives the demo from the already-warmed UI tab. Do not open new tabs/windows mid-demo

### Anti-patterns in pre-warm
- **Warming only the Lambda** — AgentCore session init and Bedrock model init are the expensive parts; a single Lambda invocation that short-circuits before calling AgentCore warms nothing useful
- **Warming with a "test" persona ID** that isn't one of the 3 demo personas — each persona has different billing history → different tool output → different prompt → different Bedrock response path. Warm *the exact personas you will demo*
- **Pre-warm too early** — 30+ minutes before go-live is probably past the warm window. 5–15 minutes is the sweet spot
- **Running pre-warm from inside the presentation laptop** without also confirming network — if the venue's WiFi fails between T-5 and T-0, warm containers don't help. Keep a mobile hotspot as a backup network

### Fallback if pre-warm fails
- If any persona returns >3s warm or validator rejects a narrative, the fallback strings are already in place — narrative just looks hand-authored instead of LLM-generated. Demo continues, message is still intact
- If the whole API is unreachable: `?narrative=off` + `build:mock` UI fallback = the v1.0 demo. Presenter acknowledges "we're showing the v1.0 cards today; v2.0 narrative is a live system and we're not rolling that dice"

**Confidence: HIGH** on the playbook structure and anti-patterns. **MEDIUM** on specific warm-window durations for AgentCore (AWS does not publish firm SLAs; the 5–15 min figure is a widely reported Lambda characteristic). Rehearsal timing is the source of truth.

---

## DEMO-04 (Environment Freeze) — Playbook

The principle: **nothing changes after the rehearsal passes, except the things that change naturally.**

### What gets locked (and how)

| Item | Lock mechanism | Lock timing | Unlock conditions |
|------|----------------|-------------|-------------------|
| Python deps | `requirements.txt` + `requirements-dev.txt` pinned to exact versions (already committed v1.0) | T-48h | Never during demo window |
| Node deps | `ui/package-lock.json` committed (already v1.0) + npm ci not npm install | T-48h | Never |
| Bedrock model ID + version | CDK constant, not a parameter | T-48h | Never |
| AgentCore agent ID | CDK output captured in DEMO-RUNBOOK | T-48h | Never |
| Lambda code | Deployed + tagged `demo-v2.0`; CDK diff must be empty against deployed stack | T-48h | Never |
| UI build | Tagged dist from `demo-v2.0`, hosted on CloudFront with cache-control set for the demo window | T-48h | Never |
| IAM roles / policies | Snapshot ARNs in DEMO-RUNBOOK; no policy edits | T-48h | Never |
| AWS account / region | `us-east-1` only, documented | Always | Never |
| DNS / API Gateway custom domain | If any — pinned | T-48h | Never |
| System prompt + few-shot examples for UI-03/UI-04 | Committed as a locked file; changes require re-tag | T-48h | Never |
| Validator regex + banned-terms list | Committed; same lock | T-48h | Never |
| Fallback strings | Committed; same lock | T-48h | Never |

### What gets monitored (and how)

| Item | Monitor | Action if abnormal |
|------|---------|---------------------|
| AWS service health (`us-east-1`) | AWS Health Dashboard check T-24h and T-1h | If Bedrock or Lambda degraded: brief presenter, consider v1.0 fallback |
| Bedrock model availability | `aws bedrock list-foundation-models` smoke at T-24h | If target model missing: regenerate with pinned alternate, re-rehearse |
| CloudWatch error rate for Lambda | Dashboard watch at T-24h, T-6h, T-1h | Spike → investigate; do not deploy fix unless unambiguous |
| API Gateway 5xx rate | Same | Same |
| Live endpoint reachability | Continuous ping every 5 min from T-24h onwards | Outage → re-warm when recovered |
| Presenter laptop clock + battery + network | T-0 | Obvious but recorded |

### T-48h → T-0 timeline

**T-48h — Freeze moment:**
- [ ] Tag the final commit `demo-v2.0` (annotated, co-signed)
- [ ] Confirm `cdk diff` against deployed stack is empty
- [ ] Capture and commit CDK outputs (agent ARN, API URL, Lambda ARN) in DEMO-RUNBOOK
- [ ] Run full pytest suite — must be green from clean virtualenv
- [ ] Run the narrative-eval harness end-to-end against live stack — all 3 personas × 2 cards pass validator
- [ ] Commit: "freeze v2.0 — no changes until T-0"
- [ ] Announce freeze to team — code-freeze is real

**T-24h — Final rehearsal:**
- [ ] Presenter runs the full demo script on presentation laptop, venue network if possible
- [ ] Visual DevTools rehearsal per DEMO-RUNBOOK — warm median across all personas (carries over from v1.0 UI-02 commitment)
- [ ] Record the run (screen + audio) as the gold reference
- [ ] If any issue: **fix-forward is forbidden**; either accept the issue, disable the narrative feature flag, or fall back to `demo-v1.0`

**T-6h — Health check:**
- [ ] AWS Health Dashboard check
- [ ] Bedrock model availability smoke
- [ ] Endpoint reachability confirm

**T-1h — Pre-game:**
- [ ] Presenter laptop: WiFi confirmed, hotspot ready, battery full, screen resolution 1280px confirmed
- [ ] Final health check
- [ ] Hard reload of all browser tabs

**T-10 min — Pre-warm:**
- See DEMO-03 checklist above

**T-0 — Go live:**
- [ ] Do nothing. Present.

### Anti-patterns in environment freeze
- **"Just one more tweak"** — the top cause of on-stage demo failures. Freeze means freeze
- **Freezing without a tag** — git tag is the source of truth for "this is what's deployed". No tag → no freeze
- **Freezing code but not AWS state** — the stack is as much a deliverable as the repo; `cdk diff` empty against deployed is the proof
- **Not rehearsing after freeze** — the rehearsal *is* what validates the frozen state. Freezing without rehearsing is hope
- **No rollback plan** — the rollback *is* part of the demo plan, even if you never use it. `demo-v1.0` tag + `?narrative=off` flag are the rollback
- **Fixing a bug inside the freeze window** — if v2.0 is broken in a way that can't be flag-toggled, the answer is "present v1.0" not "hotfix and pray"

**Confidence: HIGH** — this is standard on-stage demo hardening; the specifics (`cdk diff` empty, annotated tag, narrative feature flag, mock-fallback dist) are shaped to the v1.0 shipping pattern.

---

## Feature Dependencies (v2.0)

```
v1.0 — already shipped
├── Two recommendation cards rendered
├── Deterministic $/mo + $/yr per card
├── 12-month billing history in agent context
├── Skeleton-first render
├── Mock-fallback dist
└── `demo-v1.0` tag + DEMO-RUNBOOK

v2.0 additions
├── UI-03 call-script snippet
│   ├── Persona-of-voice locked system prompt
│   ├── Few-shot examples (checked in)
│   ├── Validator (length + numerics + banned-terms)
│   ├── Fallback strings (per persona × per card)
│   └── Skeleton shimmer slot in card
│
├── UI-04 usage narrative
│   ├── Same system prompt + few-shot (different slot)
│   ├── Same validator (plus no-second-person rule)
│   ├── Fallback strings (per persona × per card)
│   └── Skeleton shimmer slot in card
│
├── DEMO-03 pre-warm
│   ├── pre_warm_demo.py script
│   ├── Eval harness (all personas × both cards pass validator)
│   ├── Latency budget assertion (warm <3s)
│   └── DEMO-RUNBOOK updates (T-30 / T-10 / T-5 / T-0)
│
└── DEMO-04 environment freeze
    ├── `demo-v2.0` annotated tag
    ├── CDK diff-empty proof against deployed stack
    ├── Locked system prompt + fallback strings (committed)
    ├── AWS Health + model-availability smokes at T-24h / T-6h / T-1h
    └── Narrative feature flag for runtime rollback

Shared guardrails
├── Feature flag `?narrative=off` (UI-03 + UI-04 off → v1.0 behaviour)
├── Per-persona × per-card fallback strings (committed)
├── Timeout budget (narrative generation <1500ms or fallback)
└── LLM telemetry to CloudWatch (every prompt/response logged)
```

---

## MVP Recommendation for v2.0

Given the 48-hour-freeze constraint and the single-shot nature of the demo, ship in this order:

**Must ship (narrative demo fails without these):**
1. UI-03 call-script snippet — system prompt + few-shot + one happy-path Bedrock invocation per card
2. UI-04 usage narrative — same plumbing, different slot
3. Validator — length + numerics + banned-terms, with per-card fallbacks as the rejection path
4. Per-persona × per-card fallback strings, committed and reviewed
5. Skeleton shimmer on narrative slots
6. `?narrative=off` feature flag
7. Pre-warm script covering all 3 personas × both cards, plus eval harness
8. `demo-v2.0` freeze tag with `cdk diff`-empty proof

**Should ship (significantly de-risks the demo):**
9. Narrative telemetry to CloudWatch
10. Hard timeout budget inside Lambda (narrative generation <1500ms)
11. T-24h / T-6h / T-1h health-check smokes
12. Presenter tooltip (alt-click reveals raw LLM output)

**Defer past v2.0 (interesting, not worth risking the demo):**
- Streaming narrative render (mid-sentence break worse than no streaming)
- Pre-computed narrative cache (undermines "live LLM" message; revisit if rehearsal shows unacceptable variance)
- Second-LLM critic pattern
- Regenerate-narrative UI button

---

## Open Questions Flagged for REQUIREMENTS.md

- **Exact Bedrock model ID + version** to pin: v1.0 didn't lock a specific narrative model. v2.0 must pick one and freeze it in CDK. Expect this to become REQ-UI-03-MODEL or similar
- **Temperature / sampling settings** to use for narrative generation. Low temperature + fixed seed where available = fewer rehearsal surprises. Flag: pin these in REQUIREMENTS.md
- **Whether narrative is computed inside the existing Lambda or a separate path**. v1.0 already runs inside a 25s botocore-timeout Lambda → simplest is to extend that path. Worth a one-line REQUIREMENTS decision
- **Where the system prompt + fallback strings live in the repo**. Suggestion: `agent/narrative/prompt.txt`, `agent/narrative/fallbacks.json` — co-located with the tool code, committed, frozen as part of `demo-v2.0`
- **Fallback strings copy review** — fallback quality is on-screen quality in the failure mode. Needs a copy-review pass, not just engineer-authored
- **Pre-warm script location and runner** — `scripts/pre_warm_demo.py`? A Make target? A CI job? Pick one and document in DEMO-RUNBOOK
- **Whether `demo-v1.0` remains the fallback tag or a `demo-v1.1` is cut** that includes v2.0 infra (e.g. skeleton slots) without the LLM — simpler rollback story, but more scope. Flag for REQUIREMENTS

---

## Sources

- Training knowledge: agent-assist LLM UX patterns (Amazon Connect Agent Assist, Salesforce Einstein Agent, Google CCAI Agent Assist)
- Training knowledge: AWS Lambda cold-start / warm-container characteristics; Provisioned vs Reserved concurrency tradeoffs (partially web-verified — AWS docs on Provisioned Concurrency confirmed reserved vs provisioned distinction)
- Training knowledge: AWS Bedrock AgentCore Runtime session lifecycle and model-endpoint warmup characteristics — **MEDIUM confidence**, worth validating in rehearsal
- Training knowledge: on-stage AWS demo hardening practices (re:Invent breakout pre-flight patterns, solution-architect rehearsal playbooks)
- Training knowledge: LLM guardrail patterns — output validation, banned-terms lists, deterministic fallback hierarchies
- Existing project artefact: `.planning/milestones/v1.0-research/FEATURES.md` — v1.0 table stakes and differentiator framing extended here
- Existing project artefact: `.planning/PROJECT.md` — scope (UI-03/UI-04/DEMO-03/DEMO-04), out-of-scope constraints (recommendation-only, no competitors)
- Existing project artefact: `.planning/MILESTONES.md` — v1.0 delivery context and smoke-derived latency evidence
- **Confidence overall: HIGH on feature categorisation, quality bars, failure modes, freeze playbook. MEDIUM on specific AgentCore warm-window timings and exact per-model latency — validate in rehearsal, not in research.**
