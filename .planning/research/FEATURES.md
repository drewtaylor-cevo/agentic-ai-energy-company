# Feature Landscape: Customer Tariff & Billing Optimisation Agent

**Domain:** Call centre agent-assist — energy & utilities tariff recommendation
**Researched:** 2026-04-23
**Confidence note:** Web research tools unavailable. Findings draw on training knowledge of call centre UX patterns, energy tariff tools (Ofgem, AEMO, network pricing models), and AWS Bedrock agent-assist deployments. Confidence levels noted per section.

---

## Table Stakes

Features that must be present or the demo falls flat. These are the minimum credible bar for any agent-assist tariff tool in a call centre context.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Customer lookup by account ID / name | Agent needs a single entry point — anything slower breaks call flow | Low | Dummy data: pre-load 5–10 accounts with distinct usage profiles |
| 12-month billing history display | Establishes the analytical basis — agents must be able to say "based on your usage over the past year" | Low | Show total spend, avg monthly, seasonal shape — not just raw numbers |
| Two recommendation tracks side-by-side | The two-card layout (Green vs Cheapest) must be immediately scannable at a glance | Low | Never make agent scroll to compare — both cards visible without scroll on a 1080p screen |
| Projected monthly savings per track | The headline number — "$X/month" — is what the agent says first on retention calls | Low | Must show annual equivalent too ("that's ~$Y per year") |
| Current plan clearly shown | Agent must know what the customer is on before pitching a change | Low | Show plan name, unit rate, daily charge, contract end date if applicable |
| Recommended plan details | Plan name, rate structure, key terms — agent needs to speak to the plan, not just the savings number | Low | Green plan: surface renewable percentage or certification; Cheapest: surface total cost projection |
| Savings calculation methodology visible | Call centre agents get challenged — "how did you calculate that?" must have an answer | Medium | "Based on your average monthly usage of X kWh at current rates vs new plan rates" |
| Confidence / data quality indicator | If 12 months of data is incomplete (new customer, gaps), the agent must know | Low | Simple flag: "Based on 8 of 12 months — estimate may vary" |
| Reset / new customer button | Call flow continuity — agent closes one call, opens next | Trivial | Clear state without page reload |

**Confidence: HIGH** — These are structural requirements derivable from call centre UX first principles. Any agent-assist tool missing these items would fail in the first live call.

---

## Differentiators

Features beyond the basics that make the demo compelling and the tool genuinely useful in production.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Usage pattern narrative | Auto-generated one-sentence framing: "This customer is a heavy morning user with above-average winter peaks" — gives the agent something to say that sounds personal | Medium | Bedrock LLM generates from billing history; 1–2 sentences max |
| Seasonal savings breakdown | Show savings aren't just average — show summer vs winter variance. Builds trust in the number | Medium | Requires month-by-month projection; relevant where seasonal rates exist |
| Call script snippet | A short, editable paragraph the agent can read verbatim or adapt: "I can see you've been spending around $X/month. I've found two options that could reduce that..." | Medium | Bedrock generates from recommendation output; must be plain English, no jargon |
| Objection-handling hints | If Green is more expensive, surface "Green is $8/month more but locks in a fixed rate — useful if you're worried about price rises" | High | Rule-based initially; LLM-assisted in production |
| Contract end date awareness | Flag if customer is mid-contract (switching penalty warning) or near end (ideal switch window) | Medium | Requires contract metadata in CRM — plan for this field in dummy data |
| Usage anomaly flag | "This customer's usage spiked significantly in March — worth asking if circumstances changed" | Medium | Simple statistical: month > 1.5x rolling average triggers flag |
| Green credential details | For the Green track: what makes it green — renewable percentage, certification body (GreenPower, REC), carbon offset claim | Low | Copy from plan portfolio data; just surface it — agents can't answer "why is it green?" without this |
| Savings confidence band | Instead of "$45/month", show "$40–$50/month depending on usage" — more honest, fewer call-backs | Medium | Derive from ±10% usage variance; builds credibility with sophisticated customers |
| Plan comparison table (on demand) | Full rate table expandable beneath the two cards — agents sometimes face customers who want to interrogate the numbers | Medium | Hidden by default; one click to expand — does not clutter the primary view |
| Audit log of recommendation shown | Record which recommendations were shown, when, and to which account — needed for compliance in regulated utilities | Low | Write-only log; no UI needed in v1 |

**Confidence: HIGH** for usage narrative, call script snippet, and objection hints — these are well-established patterns from financial services and telco agent-assist tools applied to the utility context. MEDIUM for seasonal breakdown and confidence band — complexity depends on rate structure of the dummy plans.

---

## Anti-Features

Things to explicitly NOT build in v1. Each has a reason.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Auto-switch / one-click plan change | Compliance and trust. Regulated utilities require customer consent recorded separately. Even in a demo, this trains the wrong expectation | Show a clear "Agent confirms with customer — switch initiated via [system]" placeholder CTA |
| Competitor plan comparison | Out of scope per PROJECT.md; adds legal/data complexity; dilutes the retention message | Internal portfolio only — "the best plans we offer" framing |
| Multi-recommendation list (more than two options) | Decision paralysis. More than two choices increases call handle time and reduces conversion. Research on paradox of choice is clear | Hard cap at two tracks. If a third track is ever needed (e.g. "Flex" plan), replace one, don't add a third card |
| Free-text chat with the AI | Tempting on Bedrock but scope-creep for v1. Agents won't use it under call pressure; it slows the lookup | Pre-defined recommendation flow only — the agent has one job: retrieve account, see recommendations |
| Plan recommendation history / "last time you called" | Valuable in production but adds state management complexity; dummy data doesn't support it cleanly | Log what was shown (audit log) but don't surface it in the UI for v1 |
| Real-time pricing feed | Live tariff rates from a market feed add integration complexity with no demo benefit when dummy plans are static | Hardcode plan rates in the demo data layer; design the data model so rates are config-driven (easy to swap to live feed post-demo) |
| Customer satisfaction / NPS capture | Not the agent's job mid-call; creates workflow friction | Post-call survey is a separate system concern |
| Accessibility deep-dive | Important in production, but polishing WCAG compliance is a demo timesink | Basic semantic HTML + sufficient colour contrast; no keyboard-only testing in v1 |
| Mobile / responsive layout | Call centre agents use desktop workstations — a 1280px fixed layout is fine | Desktop-first; responsive is a post-demo concern |

---

## Data Inputs Required

What the system needs to produce credible recommendations. Beyond billing history.

| Input | Source | Required for Demo? | Notes |
|-------|--------|--------------------|-------|
| 12-month billing history (monthly totals in $) | CRM / dummy data | Yes — core | Include month label, amount billed, usage in kWh if available |
| Current plan details (name, unit rate $/kWh, daily supply charge, type) | Plan portfolio / dummy data | Yes — core | Agent cannot speak to "what you're on now" without this |
| Plan portfolio (all available plans with rates) | Internal / dummy data | Yes — core | Minimum: plan name, unit rate, supply charge, green flag, fixed vs variable flag |
| Customer tenure / account start date | CRM / dummy data | Recommended | Enables "new customer" data-quality flag; useful for retention context |
| Contract end date / exit fee | CRM / dummy data | Recommended | Critical for objection handling; determines switch window |
| Usage in kWh (not just $ spend) | CRM / dummy data | Recommended | Enables rate-independent savings simulation; much more accurate |
| Customer segment / property type | CRM / dummy data | Optional | Enables "typical for a 3-bedroom home" framing — adds credibility |
| State / distribution zone | CRM / dummy data | Optional | Rate structures vary by network zone in Australia; needed for production accuracy |

**Confidence: HIGH** — these are the standard data fields in any utility CRM and the minimum needed to calculate a credible savings figure. The kWh vs dollar distinction is important: dollar-based comparison is affected by rate changes mid-year; kWh-based is more stable.

---

## Output / Presentation Patterns That Work in Call Centre Context

These are the UX principles, not the UI implementation. Based on call centre agent-assist design research from financial services, telco, and utility contexts.

### Information hierarchy (what agents see first)
1. Customer name + account number (confirmation this is the right account)
2. Current monthly spend (average) — the reference point
3. Two savings cards side-by-side: [Green: save $X/month] [Cheapest: save $Y/month]
4. Below each card: plan name, key rate, one differentiating fact
5. Expandable: usage chart, full plan details, methodology

**Rule: the answer must be above the fold.** Agents cannot scroll while talking. The savings number and two plan names must be visible without any interaction after account load.

### Language and framing
- Dollar amounts, not percentages — "$45/month" lands better than "18% reduction"
- Annual equivalent surfaces the emotional impact — "$540/year" triggers action
- Plain English plan names — if the internal name is "TOU-RESVP-2024-GRN", the UI must map this to "Green Home" or similar
- Avoid "our system recommends" — prefer "based on your usage" — makes it feel personalised, not automated

### Speed expectations
- Account lookup to recommendations: target under 3 seconds. Agents will not tolerate a spinner mid-call
- This is achievable with Bedrock if the agent invokes a pre-computed analysis or runs a lightweight inference — full deep analysis on every call is not realistic
- For the demo: pre-compute all dummy accounts at startup; lookup is a fetch, not a compute

### Call to action
- Not "Switch Now" (compliance issue)
- Preferred pattern: "Would you like me to start the switch process?" — agent reads this, customer confirms verbally, agent initiates in separate system
- CTA should be non-destructive and non-committal in the tool itself

---

## Feature Dependencies

```
Customer lookup
  └── Billing history display
        └── Usage pattern narrative (LLM)
        └── Usage anomaly flag
        └── Seasonal savings breakdown
              └── Savings confidence band

Current plan display
  └── Two recommendation cards (Green / Cheapest)
        └── Savings calculation methodology
        └── Projected monthly savings
              └── Annual equivalent
        └── Call script snippet (LLM)
              └── Objection-handling hints (LLM + rules)

Plan portfolio (config)
  └── Current plan display
  └── Two recommendation cards
  └── Green credential details
  └── Plan comparison table (expandable)

Contract metadata (optional input)
  └── Contract end date awareness
```

---

## MVP Recommendation

For the demo, prioritise in this order:

**Must ship (demo fails without these):**
1. Customer lookup (dummy accounts)
2. 12-month billing history display (chart + table)
3. Two recommendation cards side-by-side (Green / Cheapest) with savings headline
4. Current plan display
5. Savings methodology line (one sentence under each card)
6. Data quality / completeness flag

**High-value additions (makes demo compelling):**
7. Usage pattern narrative (Bedrock-generated, 1–2 sentences)
8. Call script snippet (Bedrock-generated, editable text block)
9. Annual savings equivalent ("$540/year")
10. Green credential detail line (e.g. "100% GreenPower accredited")

**Defer post-demo:**
- Objection-handling hints (rules engine needed)
- Seasonal savings breakdown (rate structure complexity)
- Contract end date awareness (needs additional dummy data field)
- Savings confidence band (adds complexity for limited demo payoff)
- Audit log (production concern, not demo concern)

---

## Sources

- Training knowledge: call centre agent-assist UX patterns (financial services, telco, utility analogues)
- Training knowledge: Ofgem tariff comparison tool design principles and Australian energy retail market (AEMO, AER)
- Training knowledge: AWS Bedrock AgentCore patterns and latency characteristics
- Training knowledge: Barry Schwartz paradox of choice research applied to call centre recommendation UX
- **Confidence overall: MEDIUM-HIGH** — web research tools unavailable; findings are domain-reasoning-based, not web-verified. Core UX principles (above-the-fold rule, dollar vs percentage framing, two-card layout) are well-established and HIGH confidence. Specific AWS Bedrock latency claims are MEDIUM confidence pending architecture validation.
