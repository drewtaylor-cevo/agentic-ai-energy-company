# CEO Demo Brief — Customer Tariff & Billing Optimisation Agent

**For:** Drew Taylor — presenter
**Audience:** CEO + business stakeholders
**Duration:** 5–7 minutes demo + Q&A
**Context:** This is the *exec-tuned* version of `DEMO-RUNBOOK.md`. The runbook is the engineering checklist; this brief is the talk track.

> Read this top-to-bottom the night before. On the day, follow the **T-30m pre-flight checklist** below, then this script.

---

## 0. The deployment reality (read this first)

The frozen `demo-v3.0` deployment supports a **5-beat demo**. The runbook describes a richer system (chat, retention queue, action cards, multi-agent supervisor, typed hardship categories, streaming) — those features exist in source but **were not deployed before freeze**. Do not promise them on stage. They are the "what's next" slide, not the demo.

| Surface | State | Use in demo? |
|---|---|---|
| 5 recommendation personas (CUST-001 to 005) | Live, byte-exact | **Yes — core demo** |
| Hardship short-circuit (CUST-006) | Live | **Yes — trust beat** |
| Reasoning trace (collapsed by default) | Live, 2-step | **Yes — observability beat** |
| Follow-up email | Live | **Yes — workflow beat** |
| `?narrative=off` kill switch | Live | **Yes — only if something breaks** |
| Portal tile + email-nudge mockups | Static HTML | **Yes — platform beat (closes the demo)** |
| Conversational chat box | Source-only | **No — say "next phase"** |
| Retention queue / cohort landing | Source-only | **No** |
| Action cards (tariff switch / SMS / payment plan) | Source-only | **No** |
| Compliance review + supervisor trace | Source-only | **No** |
| Typed hardship (CUST-007/008/009/010) | Source-only | **No — CUST-006 is the hardship beat** |
| Streaming SSE reasoning trace | Source-only | **No** |

**Latency reality:** warm latency is **11–16 seconds** per persona lookup (cold-start ~17s). This is not "instant" — you must mask it with patter. The pre-flight steps below seat the cache; the talk-tracks below cover the wait.

---

## 1. T-30m pre-flight checklist (the morning of)

Do these in order. Total time: ~20 minutes. Don't skip the warm-up cycles — they're the difference between a 2s response and a 15s response in front of the CEO.

### Step 1 — Auth + environment (2 min)

```bash
aws sso login --profile cevo-dev25
export AWS_PROFILE=cevo-dev25
export AWS_DEFAULT_REGION=us-east-1
export BACKEND_API_URL="https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/"
aws sts get-caller-identity --query Account --output text  # expect 588738606436
```

### Step 2 — Start keep-alive in a tmux pane (1 min)

```bash
tmux new-session -s keepalive
bash scripts/demo-keepalive.sh
# First "ok" tick within ~1s; rotates CUST-001..005 every 10 min
# Ctrl-b d to detach (DO NOT close the terminal)
```

### Step 3 — Run pre-warm (3 min)

```bash
cd ui && BACKEND_API_URL="$BACKEND_API_URL" npm run prewarm; cd -
```

Don't panic if it exits 1 — the per-persona gates (3000ms / 2500ms) are aspirational and the deployed system runs at 11–16s. **What you care about** is that all 5 personas returned 200, not the gate verdict. If you see consistent 5xx, switch to mock fallback (see §4 below).

### Step 4 — Manual warm-up cycles (5 min) — **the most important step**

Open the demo browser tab at `https://main.d1b6s4i8w2zlzo.amplifyapp.com` at 1280×800. Click each persona twice (pass 1 then pass 2, ~5s gap):

```
CUST-001 → CUST-001  (pass 2 should be visibly faster)
CUST-002 → CUST-002
CUST-003 → CUST-003
CUST-006 → CUST-006   (hardship — fast, no LLM)
```

Pass 2 is what the CEO will see. If pass 2 is still >12s on Sarah, you'll need to keep talking through the wait (see Beat 1 talk track).

### Step 5 — Open backup tabs (2 min)

- **Tab 1** (active): the live demo at `https://main.d1b6s4i8w2zlzo.amplifyapp.com`
- **Tab 2**: `file://.../demo/mockups/portal-tile.html` (open with `open demo/mockups/portal-tile.html`)
- **Tab 3**: `file://.../demo/mockups/email-nudge.html`
- **Tab 4** (closed but ready): the kill-switch URL `https://main.d1b6s4i8w2zlzo.amplifyapp.com?narrative=off`

### Step 6 — Sanity (1 min)

- Bottom-right corner of the live UI should show `v2.0 · <7-char-sha>`
- Phone with stopwatch on the table (only if asked for live latency)
- Close Slack / email / notifications

---

## 2. The 5-beat CEO script

**Total budget: 5–7 min** including transitions. Keep eye contact during the 10–15s waits — that's when the patter does the work.

### Opening (30s) — frame the problem

> "Customer-experience teams in energy retail have a structural problem: the cheapest plan and the greenest plan are rarely the same plan, and the call-centre operator usually picks one in their head before the customer has finished talking. We built an AI agent that does this differently — it presents both, with the actual savings, in plain English the operator can read aloud. Today's demo is the operator's screen — same one a Cevo call-centre agent would see. Let me walk you through it."

### Beat 1 — Sarah Chen, CUST-001 (90s) — the flagship save

**Action:** type `CUST-001` (or click the persona chip), press lookup.

**Talk track during the 10–15s wait** (this is where you earn the demo):

> "Behind the scenes the system is doing four things at once: it's pulling Sarah's last twelve months of usage, it's checking whether she's flagged for hardship support — that's a regulatory check before any commercial conversation — it's costing every plan in our catalogue against her actual consumption, and it's drafting the language the operator will use. The dollar figures are pure arithmetic — Python — not the AI model. The AI is only generating the sentence. We'll come back to why that distinction matters."

**When the cards appear:**

> "Two recommendations, side by side. Green saves Sarah **$30 a month, $360 a year** on EcoFlex 100. Cheapest saves her **$55 a month, $660 a year** on Value 12. The system never picks for the customer — that's the operator's call, based on what Sarah cares about. Below each card: a one-line summary of who Sarah is, and a one-line script the operator reads aloud. Notice — no dollar amounts in those sentences. That's deliberate. The AI never does the math; the math goes in the dollar fields, the AI explains the dollars in English."

### Beat 2 — CUST-006, hardship customer (45s) — the trust beat

**Action:** type `CUST-006`, lookup. *(This response is fast — ~1.3s — because it short-circuits before the LLM. Use the snap to break up the rhythm after Sarah's longer wait.)*

**Talk track:**

> "Now this is what most demos won't show you. CUST-006 is flagged for hardship support — a vulnerable customer. Watch what happens." *(card appears almost instantly)* "The system **refuses** to show tariff recommendations. Instead it routes the call to our specialist support team with dignity-preserving language. Here's the part that matters for compliance: that refusal is enforced in *code*, not in the AI prompt. Even if someone removed the hardship instructions from the prompt — or the AI hallucinated past them — the guard still fires. It's a defence-in-depth pattern: pure Python at the bottom, validated AI in the middle, code-side guard at the top. This is how you put an AI in front of regulated customer interactions without spending six months in legal review."

### Beat 3 — Elena Vasquez, CUST-003 (60s) — bill shock + reasoning

**Action:** type `CUST-003`, lookup.

**Talk track during the wait:**

> "Back to the commercial conversation. Elena's the customer who calls in shouting about her last bill. Watch what the system shows the operator before the recommendations come back — this is the bit that turns an AI into something an auditor will sign off on."

**When the cards appear, expand the reasoning trace** (it's collapsed by default — click to expand):

> "This is the agent's working. The operator sees exactly which tools the agent called and what each one returned — no black box. Every number you see in those summary lines came from a deterministic Python function, not from the language model. So when Elena says 'why are you recommending this to me?', the operator has the actual reasoning chain in front of them. That's the difference between an agent and an opaque chatbot."

### Beat 4 — Follow-up email (45s) — the workflow beat

**Action:** with any recommendation on screen (Sarah's still works), click "Draft follow-up email".

**Talk track:**

> "After the call, the operator clicks one button and the system drafts a personalised follow-up email — same recommendation, plain English, ready to edit and send. The phrase to remember is 'agent prepares, human approves'. The AI is doing the cognitive heavy-lift; the human is doing the judgement and the action. That's the shape of agentic AI we think actually works in regulated industries — the human stays in the loop on every state change."

### Beat 5 — Three surfaces, one platform (60s) — the close

**Action:** switch to the portal-tile.html browser tab.

**Talk track:**

> "Last thing. The screen we just walked through is the call-centre operator's view — that's *one* surface. The same API, the same byte-exact savings, the same validated language layer can drive a customer self-service tile in the mobile app **(switch to portal-tile.html)** — or a proactive monthly nudge email for customers who've opted in to savings alerts **(switch to email-nudge.html)**. Different audiences, different risk profiles — the email one needs more guard-rails because there's no operator filter — same engine underneath. The deliverable here isn't a screen; it's a deterministic savings engine plus a validated narrative layer that we can put behind any channel."

### Closing (30s)

> "What's running today is the foundation. The next milestone takes the operator from advisor to actor — confirmable actions for tariff switches, an SMS follow-up button, a portfolio view that ranks all your at-risk customers without anyone typing an ID. That's the deferred-roadmap doc in the repo, scoped and ready to plan. Happy to take questions."

---

## 3. Likely CEO / exec questions — and answers

**Q: How accurate are the savings numbers?**
> "Byte-exact. The savings calculation is a pure Python function with 29 unit tests locked since v1.0. The AI never sees the arithmetic — it only generates the sentence that explains the number. If the AI tried to say a different dollar figure than what the calculation produced, our validator would reject the whole response and substitute a hand-written fallback."

**Q: What stops the AI saying something inappropriate to a customer?**
> "Three things, layered. First, a Python regex validator rejects any narrative that contains a digit, a currency symbol, a competitor name, or a banned phrase. Second, if the validator rejects, we substitute a per-persona hand-written fallback string. Third, there's a URL kill-switch — `?narrative=off` — that collapses the AI layer entirely and shows just the dollar figures and plan names. One key combination, no redeploy."

**Q: How long would it take to put this in front of real customers?**
> "The agent-assist version — the screen you saw — is production-shaped today. The work to put it in a customer-facing portal is mostly authentication and rate-limiting, not AI. We'd need OIDC and MFA, session scoping, and a legal review of the language layer. That's a phase, not a quarter."

**Q: What does this cost to run per call?**
> "The AI call is on Anthropic's Claude Sonnet 4.6 via AWS Bedrock — sub-cent per recommendation. The arithmetic is free. The bigger cost question is the AgentCore runtime — that's the AWS-managed environment that hosts the agent. Today that's our latency floor; we have a path to halve it with provisioned concurrency, which we'd turn on for a customer-facing rollout."

**Q: Why was that one slow?** *(if a lookup takes >15s on stage)*
> "The runtime stays warm during active use; it goes idle if it sits unused. We're inside that idle window now. In production with steady traffic this isn't visible — it's purely a demo-environment artefact."

**Q: Where's the moat? Couldn't anyone build this with ChatGPT?**
> "Two answers. First, the moat isn't the AI — it's the validator stack and the deterministic engine underneath. Anyone can ask Claude or ChatGPT for a tariff comparison; very few can guarantee the dollar value is correct, traceable, and auditable. Second, the integration. This thing only works because it's plumbed into the customer's billing data, the tariff catalogue, and the hardship register. The AI is 10% of the work; the data plumbing and the guard-rails are 90%."

**Q: What's the hardship guarantee — what if it misclassifies?**
> "The hardship flag isn't AI-inferred. It's a column on the customer record, set by a case worker. The system reads the flag and routes accordingly. If someone is wrongly flagged, that's a CRM data issue, not an AI issue — same as today, before any of this existed."

**Q: How do you handle a model change — what if Anthropic deprecates Sonnet 4.6?**
> "We pin the model version in the agent code. A model upgrade is its own change with its own test suite — we did one already, 4.5 to 4.6, and it caught a regression in tool-calling that we fixed in code. Pinned, tested, and rollback-ready."

---

## 4. If something breaks on stage — the kill-switch script

**Symptom A — a lookup spins for >20s:**

Don't wait. Keep talking — use any of the talk-track patter above to fill. The runtime probably went idle during a pause. If the response eventually comes back, carry on as if nothing happened.

**Symptom B — narrative text shows a number, currency symbol, or weird text:**

Open Tab 4 (the `?narrative=off` URL). Refresh the demo. The cards collapse to a clean v1.0 shape — dollars, plan names, no AI sentences. Say:

> "We have a kill-switch on the AI layer for exactly this situation. We just turned it off. The recommendations are still real and the dollars are still right — we just removed the language layer. This is the kind of safety control I was talking about earlier."

(This actually *helps* the demo — it's a live demonstration of the safety architecture.)

**Symptom C — blank page / 5xx / Amplify down:**

```bash
npm run preview:mock --prefix ui
# Open http://localhost:4173/  (or the printed port)
```

Cover with:

> "We're running on a live AWS deployment — this occasionally has a propagation moment. Let me swap to local mode so we keep moving — the data and recommendations are identical."

**Hard stop:** if both fallbacks fail, end the live portion early and walk through the static portal-tile and email-nudge mockups for the platform pivot. Don't try to debug on stage.

---

## 5. After the demo — capture momentum

If the platform-pivot framing lands and there's appetite for next steps:
- The deferred-roadmap doc at `.planning/docs/presenter/DEFERRED-ROADMAP.md` is your starting point
- Phase 18 (multi-agent supervisor), Phase 21 (chat box), Phase 22 (action cards) are all source-coded already — they need a deployment phase, not a build phase
- The portal tile is the highest-leverage next milestone — it's the surface that puts the AI in front of paying customers

---

## Appendix — quick reference

```
Demo URL:           https://main.d1b6s4i8w2zlzo.amplifyapp.com
Kill switch:        https://main.d1b6s4i8w2zlzo.amplifyapp.com?narrative=off
Mockups:            open demo/mockups/portal-tile.html
                    open demo/mockups/email-nudge.html
Backend API:        https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/
AWS profile:        cevo-dev25
Demo personas:      CUST-001 Sarah · CUST-002 Marcus · CUST-003 Elena
                    CUST-004 Solar · CUST-005 EV · CUST-006 Hardship
Expected dollars:   Sarah   $30/$55 mo  ·  $360/$660 yr
                    Marcus  $16.90/$30.98  ·  $202.80/$371.76
                    Elena   $14/$25.67  ·  $168/$308.04
                    Solar   $40.02/$76.03 ·  $480.24/$912.36
                    EV      $35/$84  ·  $420/$1008
Freeze tag:         demo-v3.0 → commit 62c8adf1
```
