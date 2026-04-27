# Feature Research — v3.0 Agentic Depth & Workflow Assist

**Domain:** Call-centre agent-assist for an Energy & Utilities retailer — multi-tool agentic reasoning, regulatory autonomy boundaries, rep-side workflow surfaces, production-shaped data adapter
**Milestone:** v3.0 (extends v1.0 + v2.0 — this file does NOT re-research v1.0 / v2.0 features)
**Researched:** 2026-04-28
**Confidence:** HIGH on agent-assist UX patterns, solar/EV billing shape, adapter pattern; MEDIUM on specific AER/Ofgem regulatory clauses (training-knowledge + one corroborating web source, not the primary regulation text — flagged for legal review); MEDIUM on AgentCore Memory operational behaviour (verified via AWS docs but the service is relatively young and behaviour under sustained load is not field-tested in this project).

**Confidence note on web research:** Several authoritative sources (AER hardship guideline v2 March 2024, Ofgem Consumer Vulnerability Strategy 2025) returned 404 / socket-closed / timeout during this research pass. The regulatory framing below draws on training knowledge of those frameworks plus corroborating references; treat specific clause numbers as indicative, not legally binding. For v3.0 this is acceptable — the demo claim is "regulatory-aware autonomy boundary," not "certified AER-compliant." A legal review is flagged as an open question for DOC-01.

---

## Scope Reminder

**Already shipped (v1.0 + v2.0) — NOT re-researched:**
- Customer-ID lookup → two recommendation cards (Green + Cheapest)
- Deterministic `simulate_savings` tool with byte-exact $ preservation
- 3 residential personas (Sarah/Marcus/Elena) × 12 months billing history
- LLM usage narrative + call script per card, gauntlet-validated
- `?narrative=off` kill switch, `_narrative_source` observability marker
- Pre-warm + keep-alive scripts
- Frozen `demo-v2.0` stack with deny-Update stack policies

**v3.0 adds five feature categories** — each researched below as its own sub-section with table-stakes / differentiators / anti-features, complexity ratings, and dependencies on existing v1.0/v2.0 invariants.

---

## Category 1 — Multi-Tool Agentic Reasoning (AGENT-01 "Bill-Shock Flow")

**The pitch:** "Customer says 'why is my bill so high last month?' — agent reaches for 2–3 tools in one turn, visibly reasons, and comes back with an explanation grounded in real data."

**What "good" looks like in production agent-assist:**
- Rep sees the agent's **intent**, not its raw tool-call JSON. Typical UX: a collapsing "Thinking…" line ("Pulling your billing history… Checking for outages in your area… Comparing rate history…"), then a clean answer. The reasoning is visible at a **narrative altitude**, not a debugger altitude.
- Tools compose in a **fixed graph** for this scenario, not arbitrary free-form. Amazon Connect Contact Lens, Salesforce Einstein Service Cloud, and Forethought all scope agent autonomy to pre-defined workflows in regulated contexts — the "agent decides everything" model is reserved for low-stakes domains.
- The answer **always cites its sources** ("last month's usage jumped 28% vs your 12-month average, and there was a 14-hour outage on the 15th which typically causes post-outage heating catch-up"). The rep can defend it on the call.

### 1.1 Table Stakes

| Feature | Why Expected | Complexity | Depends On (v1.0 / v2.0) | Notes |
|---------|--------------|------------|---------------------------|-------|
| **Visible tool-call trace in UI** — collapsible "Thinking…" strip showing each tool as it runs | The entire v3.0 pitch is "the agent is visibly reasoning." Hidden reasoning = looks like v2.0 with extra latency | MEDIUM | Existing card render path (v1.0), skeleton shimmer pattern (v2.0) | Display at narrative altitude: "Pulling billing history" not `fetch_billing_history(customer_id="CUST-006")`. Each tool gets a line; on completion the strip collapses into a single summary. |
| **2–3 composed tools minimum** — e.g. `fetch_billing_history` → `fetch_rate_history` → `explain_anomaly` | One tool = v2.0. Two tools chained deterministically = scripted. Three tools with real branching = agentic | MEDIUM | Existing `simulate_savings` Tools-Lambda pattern (v1.0) | Add sibling tools to the same Tools Lambda. Keep the deterministic-math invariant — tools return numbers, LLM narrates |
| **Tool-call budget cap** | Runaway agent making 15 calls is a cost/latency disaster on stage. Also a regulated-industry concern | LOW | AgentCore runtime config | Hard cap at 4 tool calls per agent turn. Exceed → fallback narrative "I wasn't able to fully analyse this — please check the billing history manually" |
| **Sourced answer** — every claim in the narrative traces to a tool output | Trust. The agent is visibly reasoning; if the answer doesn't cite its evidence, the demo looks like confabulation | MEDIUM | v2.0 narrative-gauntlet pattern | Same pattern as SAV-03: numbers from tools are copied, LLM only narrates. Extend to "dates from tools are copied, event counts from tools are copied" |
| **Deterministic fallback for AGENT-01** — if any tool errors or LLM misbehaves | v2.0 established the never-500 contract (D-04). v3.0 multi-tool flow has more failure points, not fewer | LOW | v2.0 `FALLBACKS` bank, `_narrative_fallback_salvage` pattern | Per-persona hand-authored fallback explanation. Commit as part of the freeze |
| **Happy-path persona with a clean bill-shock story** — engineered usage spike that maps cleanly to 2–3 tool outputs | Demo needs a persona where the agent's reasoning *actually works* — not a persona where it has to say "I don't know" | LOW-MEDIUM | DATA-04 (new persona seeding) | Engineer one of CUST-004/005 to have a visible Jan 2026 usage spike + a seeded outage event + a seeded rate change. Demo story writes itself |
| **Latency budget** — the full multi-tool turn completes inside the UI-02 3-second gate **with pre-warm** | v1.0 UI-02 / DEMO-02 commitment. If multi-tool takes 8 seconds on stage, the demo is dead | MEDIUM | v2.0 pre-warm tooling, v1.0 UI-02 | Warm path target ≤ 3000ms. Cold path fails the gate — pre-warm script must exercise the multi-tool flow, not just the single-tool v2.0 path |

**Confidence: HIGH** on feature list and rationale. Production agent-assist products (Amazon Q in Connect, Salesforce Einstein) all surface reasoning at narrative altitude, cap tool calls, and enforce source-grounded answers.

### 1.2 Differentiators

| Feature | Value Proposition | Complexity | Depends On | Notes |
|---------|-------------------|------------|------------|-------|
| **Streaming tool-call strip** — tool name appears the moment it starts, not after it finishes | The "live agent thinking" feeling. Especially strong on a 3–5s multi-tool turn | MEDIUM-HIGH | SSE / incremental JSON path, doesn't exist in v2.0 | Same demo-risk caveat as v2.0 streaming narrative — if it breaks mid-stream on stage, it's worse than not streaming. Rehearsal must prove it reliable |
| **Confidence indicator on the final narrative** ("high confidence", "partial data") | Sets up DOC-02 (narrative tradeoff acknowledgement) visually. Honest UX | LOW | Existing `_narrative_source` marker (v2.0) | Extend the marker: `_narrative_source: "live_full"` / `"live_partial"` / `"fallback"`. Surface as a subtle UI pill. Invisible unless examined |
| **Re-ask guard** — if rep lookups the same customer twice in 30 seconds, cache the multi-tool result | Prevents repeated pre-warm-cost on-stage if the presenter needs to re-open a card | LOW | Session ID handling (v2.0 D-04 / PITFALL 2) | Session-scoped cache in the API Lambda. Keyed on `customer_id + intent`. TTL 30s. Must NOT cross sessions |
| **Presenter tooltip revealing raw tool I/O** | Extends v2.0 alt-click tooltip pattern. Useful for Q&A and trust-story demo | LOW | v2.0 tooltip pattern | Shift-click surfaces the tool-call trace with inputs, outputs, latencies |
| **Parallel tool execution where safe** | 3 independent fetches in parallel = ~1× latency not 3× | MEDIUM | Strands SDK / AgentCore tool orchestration | Only for tools that don't depend on each other's output. Risk: increases LLM planning complexity. Defer unless rehearsal latency demands it |

**Confidence: HIGH** on differentiator list. Streaming is MEDIUM on execution risk (as in v2.0).

### 1.3 Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|--------------------|
| **Free-form tool catalogue** ("agent can call any tool in any order") | Scope creep magnet; regulatory risk; demo-fragility risk. Each new tool is a new failure mode | Fixed intent graph. AGENT-01 = bill-shock intent = `fetch_history + fetch_rate_changes + fetch_outages` in that preference order, with a max of 4 calls |
| **Exposing raw tool-call JSON in the UI** | Looks like debugger output, not agent thinking. Undermines the "visibly reasoning" pitch; also leaks internal field names to the rep | Narrative-altitude strip only. Raw JSON lives behind the shift-click tooltip for presenter use |
| **Multi-turn conversation within AGENT-01** ("customer asked a follow-up…") | WF-01 (follow-up email) is the multi-turn feature. AGENT-01 is single-turn multi-tool. Mixing these = scope explosion | Hard separation: AGENT-01 is one request → one multi-tool turn → one answer. Follow-ups go through WF-01 |
| **Generating NEW billing-history data on the fly** | "The agent fetched 12 months of billing" only works because we seeded 12 months. Generating synthetic values mid-turn invalidates the source-grounded answer | Tools read from DynamoDB / seeded data only. If data isn't there, the fallback fires |
| **Letting the LLM pick which tool to call next, unconstrained** | High latency variance, demo surprises, regulated-industry unsafe | System prompt scripts the tool preference order for AGENT-01 intent; LLM can short-circuit but cannot re-order or invent |
| **Tool-call retry on failure** | Exploding latency on stage (a 2s tool → 2s retry → 2s second retry = UI-02 gate breach) | Fail fast to deterministic fallback. One attempt per tool. `never-500` contract (v2.0 D-04) is the net |
| **"Agent decides the intent itself"** (natural language routing) | Out of scope for v3.0. Customer-facing NLU is PROD-02 territory. Call-centre rep already knows the intent | Rep selects intent via UI ("Why is the bill high?" / "Recommend a tariff" buttons). Agent executes the intent, doesn't classify it |

### 1.4 Complexity / Dependency Summary

- **Complexity: MEDIUM-HIGH.** 2–3 new tools in Tools Lambda, tool-call tracing plumbed API → UI, latency budget tighter than v2.0, new persona (DATA-04) must be engineered for this flow
- **Dependencies:** Extends v1.0 `simulate_savings` Tools-Lambda pattern; extends v2.0 narrative-gauntlet and `_narrative_source` marker; introduces new API Gateway response shape (tool trace array) that must be backward-compatible with v2.0 clients if possible
- **Highest-risk item:** Latency budget. If warm 3-tool turn exceeds 3s median, either tighten the tool-call cap or widen UI-02 to 4s (requires PROJECT.md amendment)

---

## Category 2 — Hardship Short-Circuit / Vulnerable-Customer Flow (AGENT-02)

**The pitch:** "When `hardship_flag = true` on a customer, the agent DECLINES to recommend switching tariffs and routes to a hardship specialist workflow. Regulatory-aware autonomy boundary as a demoable story."

**What "good" looks like in regulated energy retail:**

Australian and UK energy retailers operate under statutory hardship frameworks that materially constrain what a rep (and therefore agent-assist tooling) is allowed to do with a customer in financial difficulty. The agent's job is **not** to recommend a new tariff — it is to **not do harm** and **route to a trained human**.

**Regulatory anchors (MEDIUM confidence — sources partially inaccessible during research; training knowledge of the frameworks):**
- **AER Customer Hardship Policy Guideline (AU, v2 March 2024):** Retailers must have a board-approved hardship policy; identify customers in payment difficulty early (missed payments, customer self-identification, referrals); offer payment plans, concession/grant information, and field officer support; avoid enforcement actions (disconnection, debt collection) while hardship review is active; **tariff-switching must genuinely benefit the customer** (retailers cannot upsell, cannot churn a hardship customer onto a worse-value plan, cannot exit-fee them out of an existing arrangement).
- **Ofgem Consumer Vulnerability Principles (UK):** Similar thrust — identify vulnerability (financial, health, mental health, life-event); provide Priority Services Register access; **must not recommend products that would worsen the customer's position**; escalation to specialist teams is expected.
- **US state utility commissions:** More fragmented but the common theme is **LIHEAP eligibility check + payment plan first, tariff advice last**.

**Common thread:** agent-assist tooling in a hardship context should **refuse to recommend a switch, surface the hardship flag prominently, and hand off to a trained specialist.** This is exactly AGENT-02's shape.

### 2.1 Table Stakes

| Feature | Why Expected | Complexity | Depends On (v1.0 / v2.0) | Notes |
|---------|--------------|------------|---------------------------|-------|
| **`hardship_flag` field on customer record** | The trigger. Without it, no short-circuit | LOW | DynamoDB schema extension; PROD-01 adapter interface | Boolean + `hardship_identified_date` + `hardship_category` ({payment_difficulty, medical, family_violence, other}). Category matters — different specialist queues |
| **Agent refuses to recommend tariff switch when flag is true** | The entire AGENT-02 feature. LLM prompt must hard-refuse | MEDIUM | v2.0 narrative gauntlet pattern | Two layers: (1) system-prompt instruction "if tool returns hardship=true, respond ONLY with the hardship template"; (2) deterministic guard in API Lambda — if customer has hardship flag, bypass the agent entirely and return the hardship template. Defence in depth |
| **Dedicated refusal UI** — distinct from error / fallback UI | A hardship refusal is NOT an error. Rendering it as "Oops, something went wrong" loses the demo story | MEDIUM | UI card component (v1.0), skeleton pattern (v2.0) | Replace the two recommendation cards with a single full-width "Hardship specialist workflow" card. Different colour treatment (amber/warm, not red/error). Dignified copy |
| **Specialist-routing CTA** | Rep needs to know *what to do next*. "The agent refused" is not enough | LOW | UI routing pattern (existing) | Single button: "Open hardship specialist workflow". In demo, it can open a modal / route to a stub page. Must feel like an action, not a dead-end |
| **Hardship persona (CUST-004 or CUST-005 flagged)** | Demo requires a flagged customer. No flagged customer = no demo | LOW | DATA-04 | One of the new personas carries `hardship_flag=true`. Recommendation: solar-PV persona is the "happy" demo, EV persona is the "wait, this one's in hardship" demo — maximises story contrast |
| **Audit log of hardship short-circuit events** | Regulated-industry table stake. Every hardship interaction is evidence | LOW | CloudWatch Logs (v1.0) | Structured log: `{event: "hardship_short_circuit", customer_id, timestamp, agent_id (rep), outcome}`. Demo-time: show the log line in the presenter tooltip |
| **Copy reviewed for dignity and tone** | Hardship framing that sounds algorithmic ("Customer flagged. Escalating.") is a PR risk | LOW | Fallback-strings review pattern (v2.0) | Human copy review of refusal + routing text. Committed as locked strings. First-person not third-person: "Let's get a specialist on this" not "Customer requires escalation" |

**Confidence: HIGH** on the feature list. **MEDIUM** on which exact regulatory clauses to cite in DOC-01 — flag for legal review before the demo.

### 2.2 Differentiators

| Feature | Value Proposition | Complexity | Depends On | Notes |
|---------|-------------------|------------|------------|-------|
| **Hardship category routing** — different CTAs for payment difficulty vs medical vs family violence | Sophistication; shows the architecture understands that "hardship" isn't monolithic | LOW-MEDIUM | Table-stakes `hardship_category` field | Map each category to a specialist queue / help-line number. Family violence in particular needs distinct handling (no callback, customer-initiated contact only) |
| **"Why did this refuse?" presenter tooltip** | Supports DOC-01 trust-architecture story on-demand | LOW | v2.0 tooltip pattern | Shift-click reveals: the flag value, the regulatory rationale, the defence-in-depth guard chain |
| **Payment-plan snapshot** — if the customer has an active payment plan, surface its status (not a recommendation, a fact) | Genuinely useful for the rep; regulation-friendly (factual, not prescriptive) | MEDIUM | Extra DynamoDB field; adapter interface (PROD-01) | Information-only card: "Active payment plan: 12 weeks, $45/fortnight, next due 2026-05-12." No action buttons |
| **Concession / grant eligibility indicator** (AU: LIHEAP-equivalent, Energy Accounts Payment Assistance) | Extends the "what the rep should actually do" picture beyond "escalate" | MEDIUM | State/region field on customer record | Boolean indicators: "Eligible for [state] energy concession?", "EAPA eligible?". Sources the rep to the correct referral. Do NOT auto-apply anything |
| **Auto-mute narrative generation for hardship cases** | Avoids the LLM generating any narrative at all for hardship customers — removes an entire class of demo risk | LOW | v2.0 `?narrative=off` pattern, narrative generation path | Hardcoded: if `hardship_flag=true`, `_narrative_source: "hardship_suppressed"`. Never invoke the LLM for narrative on these records |

### 2.3 Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|--------------------|
| **LLM deciding whether the customer is in hardship** | Regulatory catastrophe. Hardship identification is a deliberate business process with legal weight. LLM misclassification = real harm | `hardship_flag` is a data field, set by the business. Agent reads it, doesn't infer it |
| **"Helpful" soft-sell in the refusal** ("we can't recommend a switch, but here's a deal…") | Undermines the entire regulatory-boundary story. Also trains the wrong behaviour in the rep | Refusal is refusal. No recommendations, no alternatives, no "but" clauses |
| **Auto-unflagging** when rep clicks "customer confirmed they're okay" | Hardship is a formal status — only a trained specialist / back-office process can clear it. A UI button to "unflag" is a compliance breach | No UI path to clear the flag. Read-only in agent-assist |
| **Detailed financial-advice narrative** ("consider contacting a financial counsellor, applying for X grant, negotiating Y…") | The rep is not a financial counsellor. The agent must not act as one. Also legally risky | Route to specialist. The specialist is trained and authorised |
| **Showing the refusal as an error / 500-style state** | Loses the regulatory-boundary story; signals "our system is broken" instead of "our system is protecting a vulnerable customer" | Dignified, distinct UI state with its own colour/iconography |
| **Time-based hardship expiry** ("flag auto-expires after 90 days") | Same class as auto-unflagging. Regulated lifecycle, not an app-side timer | Flag persists until cleared by the specialist process, externally |
| **Proxying hardship-flag changes through the agent-assist UI** | Keeps scope narrow and matches regulatory practice | Agent-assist is read-only on hardship status. Updating it is a separate back-office workflow (out of scope for v3.0) |
| **Exposing the customer's hardship category in the narrative text** (even if correctly flagged) | Privacy leak onto the rep's screen — category (especially family violence) is highly sensitive. Need-to-know only | Refusal + routing UI surfaces category only to the specialist queue, not as narrative text on the card |

### 2.4 Complexity / Dependency Summary

- **Complexity: MEDIUM.** Mostly data-shape work + a new UI state. Low LLM complexity (we're actively *suppressing* the LLM). Real complexity is in the copy review and regulatory framing for DOC-01
- **Dependencies:** DATA-04 must seed a flagged persona; PROD-01 adapter must surface the flag; v2.0 fallback-strings + observability patterns extend naturally. Independent of AGENT-01 multi-tool work
- **Highest-risk item:** Regulatory framing in DOC-01. If the trust-architecture one-pager makes compliance claims that can't be backed up, it's a bigger presentation risk than any technical failure. Flag for legal review before DOC-01 ships

---

## Category 3 — Rep-Side "Draft Follow-Up Email" Workflow (WF-01)

**The pitch:** "After the rep walks the customer through the recommendation, the agent offers a draft follow-up email summarising the conversation. This is a second turn that reuses the context of the first turn — exercising AgentCore Memory."

**What "good" looks like in production agent-assist:**

Draft-reply is the most mature agent-assist surface in market. Amazon Connect Contact Lens + Amazon Q in Connect, Salesforce Einstein Service Cloud ("draft reply"), Zendesk generative AI, Forethought, and Ada all surface an AI-drafted reply as a **suggested text the agent can edit and send** — never an auto-sent message. The defining characteristics:

1. **Human always in the loop.** Draft appears in an editable field. The agent edits, approves, sends.
2. **Short-term memory is table stakes.** The reply references the current conversation by default.
3. **Long-term memory is a differentiator.** "Remember the customer previously mentioned they work night shifts" is an upsell feature, not a minimum.
4. **Tone / template lock.** Retailers lock the tone (warm, plain English, brand voice); AI fills in specifics.
5. **No over-promise.** The reply does not commit to things the agent hasn't explicitly agreed to.

### 3.1 Table Stakes

| Feature | Why Expected | Complexity | Depends On (v1.0 / v2.0) | Notes |
|---------|--------------|------------|---------------------------|-------|
| **Draft email area in the UI** | Without the surface, no feature | LOW | v1.0 card layout | Position: below the two recommendation cards. Read-only-looking preview with a "Copy" / "Edit" affordance. Not auto-focused — rep chooses to engage |
| **"Generate follow-up email" button** | Explicit action, not automatic. Gives the rep control and makes the second-turn-memory story visible | LOW | Existing UI patterns | Button disabled until a recommendation has rendered (you can't summarise what hasn't happened yet). Loading state uses v2.0 skeleton pattern |
| **Second-turn context from the first turn** — email references the specific recommendation the rep just saw | The entire "memory" pitch. If the email is generic ("here's a summary of your recent inquiry") the feature is pointless | HIGH | AgentCore Memory (short-term), session ID threading, v2.0 narrative generation path | Session-scoped memory. Same session ID must flow from the initial recommendation call into the email-draft call. **Session-ID bleed is the known pitfall (v2.0 PITFALL 2 / SC-3) — apply the same handler-scope generation rule** |
| **Validator on the email output** — same gauntlet as v2.0 UI-03/UI-04 | Draft will land in the rep's outbox. LLM hallucinating a $30 figure as $40 is the same SAV-03 risk, now in email form | MEDIUM | v2.0 `agent/narrative/validators.py`, banned-terms list | Extend validator for long-form: no dollar figures unless pulled verbatim from the tool output, no competitor names, no environmental superlatives, no switch-commit verbs ("I've switched you…"), no made-up dates |
| **Deterministic fallback template** | Validator rejection / LLM timeout / Memory service unavailable must still produce an editable draft | LOW | v2.0 `FALLBACKS` pattern | Skeleton template with {{placeholders}} hand-filled from the recommendation data. Indistinguishable to the rep from a poor LLM output — they'll edit either way |
| **Human edit + send flow (stubbed)** | The whole point is the rep is in the loop. Showing "Sent!" auto-confirmation is a trust violation | LOW | UI stub | Edit textarea + "Copy to clipboard" (real) + "Send" (stubbed with toast "Email queued — not actually sent in demo"). Do NOT integrate SES or real email in v3.0 |
| **Clearly marked as draft** | Legally and UX-wise, the rep owns the outgoing message | LOW | UI copy | Header: "Draft — you edit and send". Amber / info-coloured banner |

**Confidence: HIGH** on table-stakes list. Draft-reply agent-assist pattern is extremely well-established across 5+ major vendors.

### 3.2 Differentiators

| Feature | Value Proposition | Complexity | Depends On | Notes |
|---------|-------------------|------------|------------|-------|
| **Tone selector** — "formal / standard / friendly" chips above the draft | Lets the rep tune the output without editing. Shows agent sophistication | MEDIUM | Prompt template injection | Three canned prompts. Regenerates draft on chip click. Caveat: each regenerate = an LLM call + a validator pass — can become latency-chatty |
| **Long-term memory across sessions** — "this is the third time we've spoken about tariffs" | Exercises AgentCore Memory's long-term store. Big brand feature | HIGH | AgentCore Memory long-term, cross-session customer binding | Risk: demo persona has to be set up with a plausible "prior session" history. Contrived for a one-shot demo. Suggest: FAKE prior sessions by seeding AgentCore Memory at deploy-time for the new personas |
| **Attach the recommendation data as a PDF / structured block** | Removes the "LLM might paraphrase the numbers wrong" risk entirely | MEDIUM | PDF / structured-email rendering | Deterministic block ("Green Plan — $30/mo savings, Cheapest Plan — $55/mo savings") appended to the LLM narrative. The tool-output is canonical; the LLM only writes the prose around it. Same SAV-03 invariant in email form |
| **Language selector** — en-AU / en-US | Cevo-Australia context suggests localised voice matters | LOW | Prompt templating | If Australian English is locked (v2.0 persona-of-voice), this is a dial on that. Bigger story: shows the brand voice is pluggable |
| **"Why this recommendation?" bullet block** (auto-generated) | Supports DOC-01 trust story in the actual artefact the customer receives | MEDIUM | AGENT-01 tool trace | Surface the multi-tool reasoning from AGENT-01 as bullets in the follow-up email. Ties the two v3.0 features together |
| **Regenerate button (with soft warning)** | Power-user feature; mitigates the "if first draft is bad, I'm stuck" failure mode | LOW | Existing button pattern | Unlike v2.0 (where we banned the regenerate button), email is **before send** not **before audience** — a second try is safe. Cap at 3 regenerates per session to avoid demo variance on stage |

**Confidence: HIGH** on differentiators. Long-term memory is **MEDIUM** on demo feasibility — seeding AgentCore Memory at deploy-time is doable but not yet proven in this stack.

### 3.3 Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|--------------------|
| **Auto-send the email** | Breaks the human-in-the-loop invariant. Also a real compliance issue (CAN-SPAM, Spam Act 2003 AU, ePrivacy) | Always draft → edit → rep-clicks-send. Even "send" in v3.0 is a stub |
| **Remember everything across every session forever** | Privacy / retention issue + demo-data-pollution issue. AgentCore Memory long-term without a retention policy = compliance debt | Short-term (session) memory in demo; long-term memory only for the one seeded "prior session" on the EV persona, if we ship that differentiator |
| **LLM quoting dollar figures from memory** ("last time we spoke, your savings were $30…") | Memory of a number that was true yesterday may not be true today (rates change). Same SAV-03 risk, new surface | Any dollar figure in the email must come from the current tool call, not from memory. Validator enforces |
| **Draft more than one email at a time** (Green + Cheapest variants) | Presentation overload + latency | Single draft that covers both recommendations. If the rep wants variants, they edit |
| **"Personalised greeting" inferred from customer name** | LLM sometimes Latin-flips "Elena Vasquez" to "Señor Vasquez" or over-familiarises. Gender/cultural guessing risk | Greeting template is fixed: "Hi {{customer_first_name}}," — deterministic substitution, not LLM |
| **Attachments the LLM generates autonomously** (PDFs, bill breakdowns) | Authenticity / liability issue | Attach a deterministic PDF ONLY if the differentiator is scoped in. Otherwise text-only email |
| **Send history displayed in the UI** ("previously sent 3 emails") | Needs a real CRM integration + retention policy. Out of scope for v3.0 | Drafted-only count, if any. No send history |
| **Memory-based recommendations** ("based on your previous preference for Green plans…") | Bypasses the recommendation engine. Conflicts with REC-03 (both tracks, never ranked) | Memory informs email wording, NOT the recommendation. Recommendation is always derived fresh from the billing data |
| **Subject line drift** — LLM generates a new subject every regenerate | Professional emails have stable subject lines. Subject line changing is a trust smell | Subject line deterministic: `"Your {{retailer}} tariff review — [date]"`. LLM fills body only |

### 3.4 Complexity / Dependency Summary

- **Complexity: MEDIUM-HIGH.** Biggest unknowns are (a) AgentCore Memory integration depth and (b) long-form LLM output validation. Each is a meaningful sub-project
- **Dependencies:** Strong coupling to v2.0 narrative-gauntlet (same validator, same fallback pattern, same observability marker); coupling to AGENT-01 if the "why this recommendation" differentiator ships; new dependency on AgentCore Memory service (short-term mandatory, long-term optional)
- **Highest-risk item:** Session-ID threading. The existing codebase has a documented pitfall (v2.0 PITFALL 2) where `runtimeSessionId` at module scope causes cross-persona bleed. The same failure mode at larger scale — cross-customer email-memory bleed — would be catastrophic. **Flag as a required test gate for WF-01**
- **Scoping question for orchestrator:** Does WF-01 scope include long-term memory or just short-term? Short-term is straightforward; long-term is a 2–3x complexity multiplier. Recommendation: **short-term only in MVP, long-term as a differentiator if time permits.**

---

## Category 4 — Solar PV + EV Personas and Tariff Archetypes (DATA-04, REC-04)

**The pitch:** "Two new personas (CUST-004 solar PV, CUST-005 EV) with realistic billing shapes, and at least one new tariff archetype that maps to them."

**What "good" looks like in energy-retail data modelling:**

**Solar PV households:**
- Export electricity to the grid when generation exceeds load (midday most of the year, shoulder seasons especially)
- Typical 12-month shape: negative net kWh in spring/autumn (credit months), positive in winter + evening-heavy months
- Net metering structures vary by state/country, but the dominant shape is: **`consumption_kwh + export_kwh + feed_in_credit` per bill**. A single `usage_kwh` field is NOT enough
- Typical installed-system profile: 6.6 kW residential. Annual generation ~9,000–10,500 kWh (Sydney/Melbourne latitude); ~11,000+ kWh Queensland/Perth
- Typical self-consumption rate: 30–40% of generation used on-site (higher with batteries, much lower without)

**EV households:**
- Additional ~3,000–4,000 kWh/year for a single EV (15,000 km/year at ~20 kWh/100km)
- Strong time-of-use skew: overnight off-peak charging is the dominant pattern for cost-optimising households
- Winter usage higher due to cold-battery efficiency loss + cabin heating
- Peak day-of-week: weekend/Sunday-night charging (after road-trip recovery) + weekday-nightly trickle

**Tariff archetypes that match:**
- **Solar Feed-In Tariff (FiT):** exports compensated at a per-kWh rate (typically 4–10c/kWh — much below the import rate). "Solar Smart" plan variants bundle FiT with a daytime-peak import penalty
- **EV Time-of-Use (ToU) plan:** very cheap overnight rate (~10–14c/kWh 00:00–06:00), standard daytime, expensive evening peak. Some retailers offer "EV Plan" as a named variant
- **Solar Sponge:** combines FiT with a mid-day cheap-import window so the customer is encouraged to shift load into their own solar production window. Ambitious but increasingly common

**Source confidence:** HIGH on solar shape (verified via web research on net metering); HIGH on EV shape (training knowledge + corroborating references); MEDIUM on specific c/kWh rates (these vary enormously by state/retailer — use indicative values for the demo).

### 4.1 Table Stakes

| Feature | Why Expected | Complexity | Depends On (v1.0 / v2.0) | Notes |
|---------|--------------|------------|---------------------------|-------|
| **Billing record schema extension** — `usage_kwh` → `{consumption_kwh, export_kwh, net_kwh}` | Existing schema can't represent a solar household | MEDIUM | DynamoDB schema (v1.0), `billing_records.py`, seeder | **Breaking change for downstream code.** Add fields; keep `usage_kwh` as net for backwards compatibility. Tools Lambda must be updated. Test fixtures (`tests/conftest.py`) expect byte-exact — all new assertions needed |
| **Realistic 12-month profile for solar (CUST-004)** | Story falls flat if the numbers look wrong to anyone who knows solar | MEDIUM | Schema extension | Suggested: 6.6 kW system, sydney-latitude monthly generation curve (Apr ~700 kWh → Dec ~1,100 kWh), 35% self-consumption. Net bill shape: 2–3 credit months, 9 non-credit months, winter peak |
| **Realistic 12-month profile for EV (CUST-005)** | Same | MEDIUM | Schema extension | Suggested: ~+3,500 kWh/year EV load overlaid on a mid-usage baseline. TOU skew: 70% of EV kWh in off-peak. Winter months 15–20% higher due to battery efficiency |
| **At least one new tariff archetype (REC-04)** | PROJECT.md requirement. Both personas need a plan that fits them | MEDIUM | `tariff_plans.json` (v1.0) | Recommendation: add both an EV ToU plan and a Solar FiT plan. Minimum one — but shipping both closes the persona story. See tariff table below |
| **`simulate_savings_pure` extended for net metering** | Existing function assumes `usage_kwh × rate = cost`. Solar breaks that | HIGH | v1.0 `lambda/handler.py::simulate_savings_pure`, SAV-03 invariant | `cost = consumption_kwh × import_rate + supply_charge – export_kwh × fit_rate`. Tests `tests/test_simulate_savings.py` need new fixtures. **Do NOT let the LLM do this math (SAV-03).** Extend the tool, extend the tests, byte-exact values for new personas |
| **Green + Cheapest still applicable to new personas** (REC-03 invariant) | REC-03 says both tracks always returned. Must hold for solar/EV | MEDIUM | REC-03 (v1.0), new tariff archetype | For solar: Green = existing ECO, Cheapest = SOL (new FiT plan). For EV: Green = existing ECO (or EVG if we add a green EV plan), Cheapest = EV (new ToU plan). Both must be genuinely better than the existing STD baseline for the new personas, otherwise DEMO-02-style engineered-delta story fails |
| **Engineered savings delta for new personas** (DEMO-02 parallel) | v1.0 flagship has $30/$55 delta engineered. New personas need similar clarity | MEDIUM | Engineered-delta pattern (v1.0 Phase 1) | Suggest: CUST-004 solar ~ $40/$70 (solar-plan savings are usually larger), CUST-005 EV ~ $35/$60. Locked in tests same way as existing personas |

**Confidence: HIGH** on the feature list. **MEDIUM** on specific kWh/rate numbers — these should be reviewed by someone with recent AU retail-market knowledge before the demo.

### 4.2 Differentiators

| Feature | Value Proposition | Complexity | Depends On | Notes |
|---------|-------------------|------------|------------|-------|
| **Usage profile chart per persona** (12-month bar chart on the card) | Makes the "realistic shape" instantly visible. Solar credit months as negative bars is a striking visual | MEDIUM | UI charting lib (not currently in stack) | Adds a new frontend dependency (recharts / visx). Bundle size consideration. Worth it ONLY if time permits |
| **Battery persona (CUST-006)** | Adds a third-axis story: solar + storage households are the growth segment in AU residential | HIGH | Schema further extended with `battery_discharge_kwh` | Out of scope recommendation — defer. Adds a whole persona + data model without a matching tariff structure in the current catalogue |
| **Generator / backup-power persona** (rural context) | AU rural-retail angle | HIGH | Separate usage pattern | Defer. Adds complexity without a clear tariff story |
| **Seasonal-adjusted savings** ("these savings are biggest in summer") | Makes the recommendation more credible; lets the narrative be richer | MEDIUM | Extended `simulate_savings` return shape | Additional fields on the return, not breaking. UI surfaces a sub-narrative line. **Careful with SAV-03** — the math must stay in Python, LLM only writes the phrase |
| **Tariff eligibility pre-check** — EV plans sometimes require smart-meter confirmation | Production-realistic adapter behaviour | LOW | PROD-01 adapter | Boolean field on customer: `has_smart_meter`. EV ToU plan surfaces a caveat: "Requires smart meter — we see yours is installed." Or: "Smart meter check required before activation." Doesn't block recommendation, adds nuance |

### 4.3 Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|--------------------|
| **Real-time solar generation estimate based on weather** | Infinite scope creep; not what the demo is about; weather-API dependency | Seeded 12-month profile only. "Last August your system generated X kWh" is a fact from seed data |
| **Customer-facing solar forecast** | PROD-02 territory (customer-facing portal) — explicitly deferred | Agent-assist only in v3.0 |
| **Battery optimisation recommendations** | Requires battery data + discharge modelling + load-shift logic. Huge scope | Defer. If battery persona ships, it ships as a tariff match only (same as solar), no optimisation advice |
| **Novel tariff archetype beyond FiT + EV-ToU** (e.g. demand-response, virtual power plant) | Emerging product space — not table stakes, too early to demo | Stick to FiT and EV-ToU. Well-understood, well-priced, well-regulated |
| **Per-interval usage data (30-min intervals)** | Smart-meter data is available but a 10–100× data volume increase. Demo doesn't need it | Monthly aggregates only. TOU story is told via rate structure on the tariff, not interval usage on the customer |
| **LLM-generated narrative explaining how net metering works** | Regulatory / accuracy risk. Net metering rules vary by state | Short, factual narrative (≤20 words per v2.0 UI-04 gauntlet). Keep the solar mechanics out of the LLM prompt scope |
| **Tariff switching advice that ignores export value** — "Switch to a cheap flat-rate and lose your FiT" | Real-world bad recommendation. Solar customers get wrecked by this in production | `simulate_savings` for solar personas must include FiT value in the baseline. Otherwise the "Cheapest" plan may recommend losing money on lost exports |

### 4.4 Complexity / Dependency Summary

- **Complexity: MEDIUM-HIGH.** Schema change is the biggest lift — it ripples through seed data, Tools Lambda, simulate_savings, test fixtures, and recommendation logic. Net-metering math alone is a self-contained subproject
- **Dependencies:** Upstream for every other v3.0 feature — AGENT-01 (multi-tool flow) needs interesting personas to reason about, AGENT-02 needs a persona to flag hardship on, WF-01 needs a persona to generate an email for. **DATA-04 / REC-04 must land before any of the others can demo properly**
- **Highest-risk item:** Breaking the SAV-03 invariant during net-metering math refactor. The existing byte-exact test fixtures (Sarah $30/$55, Marcus $16.90/$30.98, Elena $14.00/$25.67) MUST continue to pass — v2.0 regression check is the bar

---

## Category 5 — CustomerDataProvider Adapter (PROD-01)

**The pitch:** "Production-shaped customer-data abstraction. DynamoDB demo implementation behind an interface that a real CRM (Salesforce, Dynamics, SAP IS-U, Oracle Utilities CC&B) could slot into."

**What "good" looks like in energy-retail CRM integration:**

The industry-standard pattern for customer-data access in utilities SaaS is a **repository interface** that:
1. Speaks business-domain language (`get_customer`, `get_billing_history`, `get_hardship_status`) — not CRM-vendor language
2. Returns plain domain objects (dataclasses / Pydantic models) — not vendor SDK types
3. Hides network failures behind explicit result types (found / not-found / temporary-unavailable / permanently-unavailable)
4. Is **consent-aware** and **PII-aware** at the interface level — some fields require additional checks to read
5. Is **synchronous at the call-site** from the agent's perspective — the adapter internally handles retries, rate limiting, caching

Major CRMs in this space and their adapter shapes:
- **Salesforce Energy & Utilities Cloud:** SObjects (Account, Contact, Service Point, Billing Account, Premise, Usage Point). Heavy — a real Salesforce adapter maps ~20 objects
- **SAP IS-U:** Business partner / contract account / contract / installation / device hierarchy
- **Oracle Utilities CC&B:** Person → Account → Premise → Service Agreement → Service Point
- **Generic REST/GraphQL SaaS backends** (Kraken Technologies, Gentrack Junifer): simpler, roughly (Customer → Account → Contract → Meter)

**Common-denominator fields the adapter should expose for v3.0:**
- Identity: `customer_id`, `account_id`, `email`, `phone`, display name
- State: `active`, `hardship_flag`, `hardship_category`, `consent_marketing`, `consent_tariff_recommendations`
- Billing: `current_plan_id`, `billing_history_months[]`, `active_payment_plan` (optional)
- Service: `premise_id`, `has_smart_meter`, `has_solar_pv`, `has_ev`
- Metadata: `last_sync_at`, `source` (which CRM / which adapter impl)

### 5.1 Table Stakes

| Feature | Why Expected | Complexity | Depends On (v1.0 / v2.0) | Notes |
|---------|--------------|------------|---------------------------|-------|
| **`CustomerDataProvider` interface (ABC / Protocol)** | The whole point of PROD-01. Without the interface, nothing is decoupled | LOW | Existing Python 3.13 environment | Define as `Protocol` (duck-typed) or `ABC`. Methods: `get_customer`, `get_billing_history`, `get_hardship_status`, `list_personas` (demo-only — flagged with a note) |
| **`DynamoDbCustomerDataProvider` implementation** | The existing DynamoDB access becomes the reference implementation — not the default path | LOW-MEDIUM | Existing Tools Lambda (v1.0), DynamoDB schema (v1.0) | Refactor Tools Lambda to call `provider.get_customer(customer_id)` instead of direct DynamoDB. All existing tests must still pass (byte-exact regression) |
| **Plain domain types for returns** (dataclasses / Pydantic) | Vendor type leakage is the anti-pattern. Domain purity is the whole point | LOW | Pydantic already in stack (v1.0) | `Customer`, `BillingRecord`, `HardshipStatus` dataclasses. Match the DynamoDB wire format shape for 1:1 field mapping at the adapter boundary |
| **Not-found is explicit, not an exception** | Half the real-world CRM integrations confuse "not found" with "service down." Adapter shape must disambiguate | LOW | — | Return `Optional[Customer]` or `Result[Customer, NotFound \| Unavailable]`. Do NOT raise on "customer doesn't exist" — that's a valid response (the v2.0 path already handles this via "no green/cheapest keys in body") |
| **Consent / access flags read first, data read second** | Regulatory table-stake. "Can I look at this customer's recommendations?" is a different question from "get me the recommendations" | MEDIUM | New `consent_*` fields on customer record | Interface method: `can_recommend_tariff(customer_id) -> bool`. Wraps a check for hardship_flag + consent_tariff_recommendations. Called before the agent invokes any tool |
| **Logging and tracing at the adapter boundary** | Every production CRM integration needs to say "X ms on call Y to CRM". Demo-era parity with that expectation | LOW | CloudWatch Logs (v1.0), `_narrative_source`-style markers (v2.0) | Log `{adapter_op, customer_id, duration_ms, result_type}` per call. Use structured logging (JSON lines) |
| **Test double implementation** (`InMemoryCustomerDataProvider`) | Tests shouldn't hit DynamoDB. Adapter abstraction is the natural seam | LOW | Pytest (v1.0), fixtures in `tests/conftest.py` | In-memory dict-backed. Uses the same domain types. Speeds up the ~200 offline test suite |
| **Demo-time docs showing a second implementation signature** (`SalesforceCustomerDataProvider(NotImplementedError)`) | The pitch is "a real CRM could slot in." Showing the signature — without implementing it — makes the story concrete for DOC-03 | LOW | — | A file with just the method signatures, docstrings referencing Salesforce SObjects, and `raise NotImplementedError`. Committed as presenter artefact |

**Confidence: HIGH** on adapter pattern and table-stakes list. Adapter / repository pattern is the textbook answer for this abstraction.

### 5.2 Differentiators

| Feature | Value Proposition | Complexity | Depends On | Notes |
|---------|-------------------|------------|------------|-------|
| **Circuit breaker on the adapter** | Real CRMs are flaky. Demoable story: "if Salesforce is down, we degrade to last-known state, not crash" | MEDIUM | — | Python `pybreaker` or custom. Demo value is the *shape*, not the real operation. Can be stubbed to show state transitions in unit tests |
| **Read-through cache layer** | Same demoable story, plus real latency value | MEDIUM | Redis / in-memory LRU | In-memory `functools.lru_cache` is enough for demo. TTL-bound. Shows the seam where a real implementation would add ElastiCache |
| **PII-aware field redaction** | Regulatory-compliance table-stake in a production integration | MEDIUM | New `Redacted[T]` wrapper type | Fields like `email` / `phone` return as redacted unless the adapter is called with an explicit authorisation context. Demoable as "see how the rep sees the customer — masked unless they've clicked 'reveal contact'" |
| **Pagination for billing history** | Real CRMs don't return 12 months in one call. Production adapter shape must support it | LOW-MEDIUM | Existing `get_billing_history` | `get_billing_history(customer_id, limit=12, cursor=None)`. Demo path returns everything; production path paginates |
| **Source-tagging on returned data** | When both DynamoDB and a real CRM coexist ("dual-write period"), knowing which implementation served each query matters | LOW | Existing observability pattern (v2.0 `_narrative_source`) | Every returned `Customer` has `_source="dynamodb"` or `"salesforce"`. Consistent with the v2.0 marker naming |
| **Read-only-ness lock** | Adapter cannot write to the CRM in v3.0. Demoable as part of the regulatory-boundary story | LOW | — | Interface has NO `update_*` methods. Writes are a separate concern, deferred to PROD-02 or beyond |

**Confidence: HIGH** on all of these. They are all well-established production-adapter patterns.

### 5.3 Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|--------------------|
| **Full CRM integration** (real Salesforce / Dynamics SDK wired in) | Massive scope creep; out of v3.0 goal; requires real creds and real data | Demoable interface + DynamoDB impl + `NotImplementedError` Salesforce stub. "Ready to slot in" is the message, not "slotted in" |
| **Write-back capability** | Auto-updating customer records from the agent-assist tool is huge regulatory + architectural risk | Read-only interface. No update methods |
| **Vendor SDK types leaking into domain code** | Kills the abstraction. One `sforce.SObject` in a domain function and the adapter is academic | All return types are the plain dataclasses. Adapters translate at their boundary only |
| **Synchronous-only interface** (no async option) | Python ecosystem is bimodal; a synchronous-only adapter makes async agent frameworks painful. But… | Keep synchronous for v3.0 (matches current Lambda + Strands SDK shape). Document the async version as a v4 extension, not v3 |
| **Generic `get_field(customer_id, field_name)` API** | Opens the door to tight coupling between caller and CRM field names. Breaks the "speaks business domain" rule | Named methods only (`get_customer`, `get_billing_history`, `get_hardship_status`). If a caller needs a new field, it gets a new method |
| **Inferring consent from the absence of a flag** | Regulatory anti-pattern. "Null consent" is not "consent granted" | Consent flags must be explicitly true. Adapter defaults to false on missing data |
| **Silent failures on adapter errors** | Violates v2.0 D-04 never-500 contract at the adapter layer rather than the API layer | Adapter errors surface as explicit `Unavailable` results, NOT exceptions bubbling to the agent. The agent handles them the same way as "not found" — fallback narrative, routable to human |
| **Per-field consent fetched on every call** | Real CRMs throttle. A chatty consent-check pattern will trip rate limits | Cache consent per-session. Invalidate on explicit cache-clear only (not on time — consent changes are rare in a call window) |
| **Cross-customer batch methods** (`get_customers([id1, id2, ...])`) | Not needed for a call-centre agent-assist flow (one customer per call). Adds surface area for privacy/leak bugs | Single-customer operations only. If a future use-case needs batching, adds a new method later |
| **"Impersonate customer" capability** for testing | Security anti-pattern; demo confusion; accidental real-data access | Use the test-double adapter. Never mix real and test in the same adapter instance |

### 5.4 Complexity / Dependency Summary

- **Complexity: MEDIUM.** Mostly refactoring (DynamoDB access already works; we're moving it behind an interface). Real work is in the domain-type design and the test fixture migration
- **Dependencies:** All other v3.0 features read customer data; PROD-01 is their natural dependency — but the refactor can be sequenced *after* DATA-04 if phased as "add new data fields first, then wrap in adapter". No hard ordering constraint
- **Highest-risk item:** Test fixture regression. The existing `tests/conftest.py` fixtures (`mock_savings_response`, `mock_marcus_response`, `mock_elena_response`) lock byte-exact DynamoDB-shaped data. Refactoring to adapter types while preserving byte-exact output through the whole pipeline is fiddly. **Flag a regression pass as a required phase gate**

---

## Cross-Cutting: Committed Presenter Artefacts (DOC-01, DOC-02, DOC-03)

The PROJECT.md lists three documents as v3.0 features. These are **committed artefacts**, not research subjects — but they do have table-stakes / anti-features worth surfacing for scoping.

### DOC-01: Trust-architecture one-pager

- **Table stakes:** the 4 LLM bounding patterns (SAV-03 no-arithmetic, narrative gauntlet, fallback bank, `_narrative_source` observability). AGENT-02 as the regulatory autonomy boundary. Short (one page), visual, presenter-ready
- **Differentiator:** Diagram showing the defence-in-depth chain for each invariant
- **Anti-feature:** Compliance claims ("AER-certified", "Ofgem-compliant") — legal review required before anything that specific

### DOC-02: Narrative-tradeoff acknowledgement

- **Table stakes:** Honest acknowledgement that LLM narrative adds (a) latency, (b) variance, (c) failure modes — and why those tradeoffs were worth it. Links DOC-01 invariants to the narrative surface specifically
- **Differentiator:** Specific case studies from v2.0 (Sonnet 4.6 tool-use regression; salvage path activation rate; fallback-bank hits)
- **Anti-feature:** Defensive framing ("the LLM is mostly accurate") — be honest, not salesy

### DOC-03: Deferred-roadmap doc

- **Table stakes:** Architecture diagram with PROD-01 in-flight + PROD-02 boxed-and-deferred. Visible stubs for the unbuilt work. Honest about what's demo-only vs production-shaped
- **Differentiator:** Call out the re-evaluation trigger for PROD-02 (post-v3.0 ship)
- **Anti-feature:** Promising dates. "PROD-02 in Q2" commits the team to a number. Instead: "PROD-02 re-evaluated after v3.0 ships"

---

## Feature Dependencies (v3.0)

```
v2.0 — already shipped
├── LLM narrative + gauntlet + fallback bank
├── `_narrative_source` observability marker
├── Session-ID generated in handler (PITFALL 2 fix)
├── Pre-warm + keep-alive tooling
├── `demo-v2.0` freeze + deny-Update stack policies
└── `?narrative=off` kill switch

v3.0 additions
│
├── DATA-04 (solar + EV personas) ◄── UPSTREAM of everything else
│   ├── Schema extension (consumption / export / net kWh)
│   ├── Billing profile for CUST-004 (solar)
│   ├── Billing profile for CUST-005 (EV, possibly hardship-flagged)
│   └── Engineered savings delta for both personas
│
├── REC-04 (new tariff archetype) ──requires──> DATA-04 schema
│   ├── Solar Feed-In Tariff plan (SOL)
│   ├── EV Time-of-Use plan (EVP)
│   └── Updated `simulate_savings_pure` for net metering (CRITICAL — SAV-03 invariant)
│
├── PROD-01 (adapter) ──can-parallelise-with──> DATA-04
│   ├── CustomerDataProvider interface
│   ├── DynamoDbCustomerDataProvider impl
│   ├── InMemoryCustomerDataProvider test double
│   ├── NotImplementedError Salesforce stub
│   └── Consent-aware access methods
│
├── AGENT-01 (multi-tool bill-shock flow) ──requires──> DATA-04 (rich persona), PROD-01 (adapter)
│   ├── 2-3 composable tools (fetch_billing, fetch_rate_history, fetch_outages)
│   ├── Tool-call trace in UI response shape
│   ├── Tool-call budget cap (4 max)
│   ├── Fallback narrative per persona × intent
│   └── Pre-warm script extended for multi-tool path
│
├── AGENT-02 (hardship short-circuit) ──requires──> DATA-04 (flagged persona), PROD-01 (adapter)
│   ├── hardship_flag field on customer record
│   ├── System-prompt hard-refusal instruction
│   ├── Deterministic pre-LLM guard in API Lambda (defence in depth)
│   ├── Dedicated refusal UI state (distinct from error)
│   ├── Specialist-routing CTA (stub)
│   └── Audit log of short-circuit events
│
├── WF-01 (draft follow-up email) ──requires──> AGENT-01 (first turn) + AgentCore Memory
│   ├── Email draft UI area + generate button
│   ├── Short-term memory binding to session ID
│   ├── Validator (extension of v2.0 gauntlet for long-form)
│   ├── Deterministic fallback template
│   ├── Subject-line deterministic + body LLM
│   └── Edit + copy-to-clipboard flow (send is stubbed)
│
├── DOC-01 (trust one-pager) ──depends-on──> AGENT-02 framing, DOC-02 alignment
├── DOC-02 (narrative tradeoff) ──depends-on──> v2.0 operational artefacts (logs, telemetry)
└── DOC-03 (deferred roadmap) ──depends-on──> PROD-01 shipped (shows "in-flight")
```

### Critical-path summary

**Serial dependencies:**
- DATA-04 (schema + personas) → REC-04 (new tariffs) → AGENT-01/02 (flows using new personas)
- AGENT-01 (first turn) → WF-01 (second turn / email)

**Parallelisable:**
- PROD-01 adapter work can run alongside DATA-04 (same repo, different files)
- DOC-01/02/03 can draft in parallel with the code work; final review after

**Shortest critical path to demo:** DATA-04 → REC-04 → AGENT-02 (hardship short-circuit — least LLM complexity) → DOC-01. Covers the regulatory-boundary story without needing multi-tool reasoning.

**Richest demo:** DATA-04 → REC-04 → AGENT-01 → AGENT-02 → WF-01 → DOC-01/02/03 (everything). Highest risk; highest payoff.

---

## MVP Definition for v3.0

Being ruthless about minimum — "agentic depth" as an honest word, not feature bloat.

### Must ship (v3.0 headline)

1. **DATA-04** — solar + EV personas with realistic 12-month profiles
2. **REC-04** — at least one new tariff archetype matching the new personas
3. **AGENT-01** — bill-shock multi-tool flow, 2–3 tool calls visible in UI, source-grounded narrative
4. **AGENT-02** — hardship short-circuit on a flagged persona, dedicated refusal UI, specialist-routing CTA
5. **PROD-01** — `CustomerDataProvider` interface + DynamoDB impl + stub Salesforce signature
6. **DOC-01** — trust-architecture one-pager, presenter-ready
7. **`simulate_savings_pure` net-metering extension** — byte-exact parity with v2.0 personas + new values locked for CUST-004/005

### Should ship (meaningfully improves v3.0)

8. **WF-01** — draft follow-up email, short-term memory only
9. **DOC-02** — narrative-tradeoff acknowledgement
10. **DOC-03** — deferred-roadmap doc
11. **Tool-call budget cap + parallel tool execution** (AGENT-01 differentiator)
12. **Consent-aware access methods** on the adapter (PROD-01 differentiator)

### Defer past v3.0

- **WF-01 long-term memory across sessions** — demo-contrivance cost too high for marginal story gain
- **Battery persona (CUST-006)** — no tariff archetype matches
- **Usage-profile charts** — bundle-size + learning curve; card-text narrative is enough
- **Write-back / update capability on the adapter** — PROD-02 territory
- **Real-time solar forecasting / weather integration** — scope explosion
- **Multi-turn conversation beyond email draft** — WF-01 is already two-turn; three-turn is out
- **Streaming tool-call trace in UI** — demo-fragile in the same way as v2.0 streaming; defer unless rehearsal proves reliable
- **LLM-driven intent classification** — rep selects intent in UI; PROD-02 territory
- **Circuit breaker / cache on the adapter** — production-shaped is the message, not production-built

---

## Feature Prioritization Matrix

| Feature | User (Rep) Value | Implementation Cost | Demo Value | Priority |
|---------|------------------|---------------------|------------|----------|
| DATA-04 solar + EV personas | MEDIUM | MEDIUM | HIGH (everything downstream needs this) | P1 |
| REC-04 new tariff archetypes | MEDIUM | MEDIUM (net-metering math) | HIGH | P1 |
| PROD-01 adapter interface | LOW (invisible) | MEDIUM | HIGH (for DOC-03 story) | P1 |
| AGENT-01 multi-tool flow | HIGH | HIGH | HIGH | P1 |
| AGENT-02 hardship short-circuit | HIGH | MEDIUM | HIGH (regulatory story) | P1 |
| DOC-01 trust one-pager | LOW (audience artefact) | LOW | HIGH | P1 |
| WF-01 draft email (short-term memory) | HIGH | HIGH | MEDIUM | P2 |
| DOC-02 narrative tradeoff | LOW | LOW | MEDIUM | P2 |
| DOC-03 deferred roadmap | LOW | LOW | MEDIUM | P2 |
| Consent-aware adapter methods | MEDIUM | LOW | MEDIUM | P2 |
| Tool-call budget cap (AGENT-01) | LOW (infra) | LOW | LOW (invisible if working) | P2 |
| WF-01 long-term memory | LOW | HIGH | MEDIUM | P3 |
| Tone selector / regenerate on WF-01 | MEDIUM | MEDIUM | LOW | P3 |
| Usage-profile chart per persona | MEDIUM | MEDIUM | MEDIUM | P3 |

**Priority key:** P1 = must ship. P2 = should ship, cut if overrun. P3 = defer without guilt.

---

## Open Scoping Questions (route to REQUIREMENTS.md)

Ranked by downstream impact — questions that change the shape of v3.0 if answered differently:

1. **WF-01 memory depth — short-term only, or long-term too?** 2–3× complexity swing. Recommendation: short-term MVP, long-term defer. **Highest scoping leverage of the 5 categories.**
2. **AGENT-02 regulatory posture — training knowledge or legal-reviewed?** Flag for legal review. DOC-01 copy should not make AER-/Ofgem-compliance claims unless reviewed. Shape of the DOC-01 artefact depends on this answer.
3. **REC-04 — one new tariff archetype or two?** PROJECT.md says "at least one". Shipping only FiT (solar) strands the EV persona; shipping only EV-ToU strands the solar persona. Recommendation: ship both, commit to the scope up-front.
4. **AGENT-01 tool count — strict 2, or up-to-3-with-budget-cap?** Affects latency budget, demo story strength ("reaches for 3 tools" > "reaches for 2 tools"), and rehearsal variance. Recommendation: design for 3, hard-cap at 4, require warm median <3s in rehearsal.
5. **PROD-01 scope — interface only, or interface + consent + audit + circuit-breaker?** Each added concern is a small addition individually but compounds. Recommendation: interface + consent for MVP; audit log reuses v2.0 CloudWatch pattern; circuit-breaker deferred.
6. **Hardship persona placement — CUST-005 EV (flagged) or CUST-006 (new)?** Affects DATA-04 size. Recommendation: flag CUST-005 EV. Story contrast with CUST-004 solar is stronger; avoids a 6th persona.
7. **Does `?narrative=off` also disable AGENT-01 tool-call trace and WF-01 email draft?** Kill-switch semantics. Recommendation: yes — `?narrative=off` collapses to v1.0 behaviour end-to-end. `?mode=v2` as a new kill-switch for "v2.0 behaviour" may be worth adding to avoid overloading the v1.0 flag.
8. **Freeze timing — `demo-v3.0` tag + new stack policies?** Existing deny-Update:* policies on 3 stacks must be lifted to redeploy. Plan the lift + re-apply as a phase gate. Defer to the roadmap but flag now.

---

## Sources

### Web-verified (MEDIUM–HIGH confidence)

- AWS Bedrock AgentCore Memory documentation — verified via WebFetch: short-term vs long-term memory types, session-scoped vs cross-session, fully-managed service, use cases (conversational agents, workflow agents, multi-agent systems, autonomous planning)
- Wikipedia: Net Metering — verified via WebFetch: bi-directional meter mechanism, monthly credit rollover, annual settlement, typical TOU and FiT tariff structures, seasonal shape
- AWS Machine Learning Blog: Intelligent Email Automation using Amazon Bedrock — verified via WebFetch: three-tier pattern (automated / retrieval / human handoff), human-in-the-loop escalation via SNS, misclassification / missing-context / out-of-scope failure modes
- AWS Prescriptive Guidance: Adapter Pattern — partial (fetched structure + common fields + failure modes, not the specific page content)

### Sources attempted, unavailable (flagged MEDIUM confidence, training-knowledge primary)

- AER Customer Hardship Policy Guideline v2 March 2024 — socket-closed repeatedly; training knowledge substituted
- Ofgem Consumer Vulnerability Strategy 2025 — 404; training knowledge substituted
- AER customers-experiencing-payment-difficulty — socket-closed; training knowledge substituted
- Amazon Connect Agent Assist product page — socket-closed; training knowledge of product surfaces substituted

**Action item flagged for DOC-01 phase:** Regulatory claims in DOC-01 need legal review. This research file draws on training knowledge of AER and Ofgem frameworks, corroborated by a single external reference — not sufficient for compliance claims in a presenter artefact.

### Training knowledge (MEDIUM confidence)

- Agent-assist UX patterns (Amazon Connect Contact Lens, Q in Connect; Salesforce Einstein Service Cloud / draft-reply; Google CCAI; Forethought; Ada; Zendesk generative AI) — pattern-level observations, not feature-list citations
- Solar PV residential billing shape — typical 6.6 kW system generation curves, self-consumption rates, Australian-state FiT structures
- EV household usage overlay — ~3,000–4,000 kWh/year additional load, TOU skew, winter battery-efficiency impact
- CRM integration patterns — Salesforce Energy & Utilities Cloud object model, SAP IS-U, Oracle CC&B, Kraken Technologies, Gentrack

### Existing project artefacts (HIGH confidence, source of truth for scope)

- `.planning/PROJECT.md` — v3.0 goal, active requirements AGENT-01/02, WF-01, DATA-04, REC-04, PROD-01, DOC-01/02/03
- `.planning/milestones/v2.0-research/FEATURES.md` — v2.0 table-stakes frame extended here
- `infrastructure/seed_data/billing_records.py` — existing persona shape, byte-exact invariants
- `lambda/tariff_plans.json` — existing tariff catalog (STD, ECO, VAL, TOU) to extend
- `CLAUDE.md` — v1.0 + v2.0 invariants (SAV-03, D-04, D-15, session-ID bleed pitfall, `_narrative_source` marker, `?narrative=off` kill switch)

---

*Feature research for: v3.0 Agentic Depth & Workflow Assist*
*Researched: 2026-04-28*
