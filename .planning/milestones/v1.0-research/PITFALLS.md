# Domain Pitfalls

**Domain:** AI Agent-Assist Demo — Energy & Utilities Tariff Recommendation on AWS Bedrock AgentCore
**Researched:** 2026-04-23
**Confidence:** MEDIUM (official AWS docs confirmed; demo and energy-domain pitfalls from high-confidence domain knowledge)

---

## Critical Pitfalls

Mistakes that cause demo failure, rewrites, or audience trust collapse.

---

### Pitfall C1: Model Access Not Enabled Before Demo Day

**What goes wrong:** Claude (Anthropic) models require a First-Time-Use form to be submitted per AWS account, plus up to 15 minutes for the background subscription to complete after the first invocation attempt. On demo day, the first call returns `AccessDeniedException`. The room watches the screen hang.

**Why it happens:** Bedrock model access for Anthropic models is not automatic. It requires `aws-marketplace:Subscribe` permissions on the IAM role AND completion of the Anthropic FTU form. AWS silently initiates the subscription on first invocation — meaning the form must have been submitted in advance.

**Consequences:** Demo cannot proceed. No fallback. The "instant personalised savings plan" hook is dead on arrival.

**Prevention:**
- Enable model access for the chosen Claude model at least 24 hours before any demo rehearsal.
- Verify with a live test invocation (not just console "Access granted" status).
- Confirm the agent execution role has `AmazonBedrockFullAccess` or the minimal `bedrock:InvokeModel` scoped to the chosen model ARN.

**Detection:** The AWS Bedrock console shows model access status. Run a smoke test `InvokeAgent` call in the target account/region before any rehearsal.

**Phase:** Foundation setup (first phase). Do not defer model access enablement.

---

### Pitfall C2: Forgetting to Prepare the Agent After Every Change

**What goes wrong:** The Bedrock console allows changes to instructions, action groups, and knowledge bases without re-preparing. The agent silently runs the previous version. Developers spend hours debugging behaviour that was fixed an hour ago.

**Why it happens:** Bedrock agents require an explicit "Prepare" step to package the latest working draft. Changes to action groups, prompt instructions, or schemas do not take effect until preparation completes. The console shows the "Last prepared" timestamp but it is easy to miss.

**Consequences:** Debugging against a stale agent. Incorrect demo results that look like recommendation logic bugs but are actually stale prompt bugs. Wasted time in the build phase.

**Prevention:**
- Always check the "Last prepared" timestamp before testing.
- Treat Prepare as a required step in every dev loop, not an optional deployment action.
- When using the API, always invoke against `TSTALIASID` (the DRAFT alias) for testing — never a static version alias that points to an older prepared snapshot.

**Detection:** If agent behaviour does not change after a prompt or schema edit, check the Last prepared timestamp first before investigating code.

**Phase:** Every phase that touches agent configuration.

---

### Pitfall C3: Lambda Resource Policy Missing on Action Group Functions

**What goes wrong:** The agent action group is configured, but the Lambda function does not have a resource-based policy allowing `bedrock.amazonaws.com` to invoke it. Every tool call returns `DependencyFailedException`. The agent either loops, hallucinates a response, or returns an error.

**Why it happens:** AWS Bedrock cannot invoke a Lambda function without an explicit resource-based policy on the Lambda side. The agent execution role's identity policy alone is not sufficient — Lambda also validates who can invoke it from the resource policy direction.

**Consequences:** All tool calls fail silently from the demo UI perspective. The agent may hallucinate savings figures instead of computing them, which is worse than an error — incorrect numbers in front of a prospect.

**Prevention:**
- Add the resource-based policy to every Lambda immediately when creating the action group.
- Policy must include `aws:SourceAccount` and `AWS:SourceArn` condition keys scoped to the specific agent ARN (not `*`).
- Test each action group in isolation in the Bedrock console before wiring together.

**Detection:** Enable agent tracing (`enableTrace: true`) in `InvokeAgent` calls. `DependencyFailedException` in the trace indicates a Lambda permission problem, not a logic problem.

**Phase:** Phase that wires action groups to Lambda functions.

---

### Pitfall C4: Savings Numbers That Do Not Add Up Under Scrutiny

**What goes wrong:** A stakeholder or sceptical call centre manager asks "how did you get $55/month savings?" The agent cannot explain its arithmetic. Or: the Green plan is shown as saving more than the Cheapest plan, which is logically incoherent and destroys credibility.

**Why it happens:** Dummy data is crafted to tell a compelling story, but the savings calculation logic and dummy tariff rates are not kept internally consistent. Green savings > Cheapest savings is the most common inversion error. Implausible savings (>40% of average bill) also trigger disbelief.

**Consequences:** The demo's core value proposition — data-driven savings — collapses. Audience distrusts all numbers. The "instant personalised savings plan" becomes "made-up numbers in a UI."

**Prevention:**
- Define the savings formula explicitly before designing any dummy data: `savings = (avg_12m_bill / avg_12m_kWh) × projected_kWh_on_new_plan × new_rate_per_kWh` — or equivalent.
- Enforce the invariant: `cheapest_savings >= green_savings` always. Green can tie with Cheapest but never exceed it.
- Keep savings in the 10–30% range of the current average bill. Savings above 35% will be questioned; savings below 8% feel uncompelling.
- Build a simple spreadsheet that validates dummy data against the formula before hardcoding anything.

**Detection:** Run the calculation manually for every test customer persona before the demo. If the numbers feel "too good," they are too good.

**Phase:** Dummy data design phase. Lock this before building the recommendation engine.

---

### Pitfall C5: Agent Latency Kills the Live-Call Demo Narrative

**What goes wrong:** The call centre agent-assist opens a customer account. The Bedrock agent takes 8–15 seconds to return a recommendation. In a real call centre context, this is an eternity. The stakeholder loses confidence that this could ever work in production.

**Why it happens:** Bedrock Agent invocations involve multiple round trips: pre-processing → orchestration LLM call → tool invocation → observation → post-processing. Each hop adds latency. A chain of two tool calls (fetch billing history, compute recommendation) can produce 6–12s end-to-end, especially on the first invocation after an idle period.

**Consequences:** The demo feels slow and unusable for a live-call context even if the logic is correct. The "while the customer is on the line" value proposition becomes implausible.

**Prevention:**
- Pre-warm the agent: trigger a dummy `InvokeAgent` call 30–60 seconds before any live demo to eliminate cold start latency from the first visible invocation.
- Design the demo script so the agent query is triggered while the "call centre agent pulls up the account" (a natural 3–5s UI action), masking latency.
- Use streaming responses (`InvokeAgent` returns a streaming event) so the UI shows progressive output rather than a blank screen.
- Minimise tool call count: the recommendation should require at most 2 tool calls (fetch data, compute result). Three or more tool calls in a chain will visibly lag.
- Target: first visible token within 2s, full response within 5s for demo conditions.

**Detection:** Measure end-to-end latency in staging before any rehearsal. Use CloudWatch metrics on `InvokeAgent` duration.

**Phase:** Agent integration phase. Build streaming response handling from day one, not as a retrofit.

---

### Pitfall C6: Dummy Data That Tells No Story

**What goes wrong:** The demo customer's billing history is flat, uniform, and shows no seasonal variation. The savings delta between Green and Cheapest is tiny ($3/month vs $4/month). There is no emotional hook — no "this customer is paying $120/month and could save $55." The stakeholder is unmoved.

**Why it happens:** Dummy data is generated to be "realistic" in the statistical sense (plausible kWh figures) without being designed to tell a compelling narrative for a sales demo.

**Consequences:** The demo technically works but fails to generate excitement. No one champions the project internally after the meeting.

**Prevention:**
- Design personas, not just data. Create 3–5 named test customers with distinct stories: high-usage household on a legacy rate (large savings), solar household with feed-in credits (Green track wins clearly), price-sensitive renter (Cheapest track wins clearly).
- The flagship demo customer should have: 12 months of billing showing seasonal peaks, a current plan that is clearly suboptimal, and a savings delta of at least $40–60/month.
- Give the call centre agent a "script hook": "Mrs. Chen, I can see you've been on our Standard Rate for 3 years — I'm looking at your usage right now and I can see a way to save you around $52 a month."
- Avoid perfectly uniform monthly bills — they look fake. Add ±15% seasonal variation.

**Detection:** Show the dummy data to a non-technical colleague and ask "does this feel like a real customer?" If they shrug, the data is not compelling enough.

**Phase:** Dummy data design phase. Do this before building any UI.

---

### Pitfall C7: Recommendation Logic Does Not Handle Edge Cases in Dummy Data

**What goes wrong:** A test customer has zero usage in one month (e.g., they were away). The average calculation divides incorrectly or produces a negative savings figure. Or: a customer is already on the Green plan, and the agent recommends switching to the Green plan — the same plan they are on.

**Why it happens:** Demo recommendation logic is often written for the happy path only. Edge cases in the dummy data expose gaps that look like bugs during a live walkthrough.

**Consequences:** During the demo, a stakeholder clicks on a second customer persona and the system either crashes, returns nonsense, or recommends the current plan — all of which undermine confidence.

**Prevention:**
- Define guard rails explicitly:
  - If customer is already on the recommended plan → show "Already on best plan" not a recommendation to switch.
  - If any month has zero usage → exclude from average or treat as an anomaly with a note.
  - Savings must always be >= $0. Negative savings means the current plan is better — surface this as "Your current plan is already optimal."
- Test every persona against every edge guard before the demo.
- Limit demo personas to 3–5, all of which have been manually verified.

**Detection:** Walk through the agent flow for every planned demo persona in the staging environment. Do not assume the happy path covers all personas.

**Phase:** Recommendation logic phase and dummy data design phase together.

---

## Moderate Pitfalls

---

### Pitfall M1: Wrong AWS Region Breaks AgentCore Features

**What goes wrong:** The team builds in `ap-southeast-2` (Sydney) and discovers that the AWS Agent Registry and AgentCore harness (preview) are only available in 4–5 regions (`us-east-1`, `us-east-2`, `us-west-2`, `eu-central-1`, `eu-west-1`). Features referenced in the architecture cannot be used.

**Why it happens:** AgentCore features have uneven regional availability. Core runtime, memory, gateway, identity, and observability are available in 15 regions. Agent Registry is available in 5 regions only. AgentCore harness (preview) is in 4 regions only.

**Consequences:** Having to rebuild infrastructure in a different region mid-project, or demo with reduced feature set.

**Prevention:**
- Confirm the target AWS region supports all required AgentCore features before writing infrastructure code.
- For a demo targeting Australian clients, `ap-southeast-2` supports core runtime and memory but not the Agent Registry. Choose `us-east-1` or `eu-west-1` if Registry is needed, or scope the demo to avoid Registry.
- Check the AgentCore regional availability table at project start and record the decision in PROJECT.md.

**Phase:** Foundation/infrastructure phase.

---

### Pitfall M2: Agent Instruction Token Budget Exhausted

**What goes wrong:** The agent instruction field is limited to 20,000 characters. Developers write verbose instructions trying to cover every edge case, exhaust the budget, and then cannot add further refinements.

**Why it happens:** The 20,000 character limit on `agentInstruction` is a hard non-adjustable quota. Complex multi-step reasoning instructions, examples, and edge case guidance can approach this limit faster than expected.

**Consequences:** Cannot add new instructions without removing existing ones. Recommendation quality degrades as nuance is stripped out.

**Prevention:**
- Keep instructions concise and behavioural ("When the customer is already on the recommended plan, respond with: Already on optimal plan").
- Move examples and detailed reasoning into the action group schema descriptions, not the agent instruction.
- Reserve at least 5,000 characters of headroom for iteration during the build phase.

**Phase:** Agent configuration phase.

---

### Pitfall M3: OpenAPI Schema Descriptions Are Too Thin

**What goes wrong:** Action group tool calls fail or produce wrong results because the agent cannot understand when to call which tool. The agent hallucinates parameters or calls tools in the wrong order.

**Why it happens:** Bedrock Agents use the OpenAPI schema `description` fields to understand what each operation does and what each parameter means. Thin descriptions ("Gets billing data") provide insufficient signal for the orchestrating LLM to make correct tool selection decisions.

**Consequences:** The agent calls the compute-recommendation tool before the fetch-billing tool, fails, then loops. Or it passes `customerId` as a string integer when the tool expects a format like `CUST-1234`. Both look like bugs but are schema communication failures.

**Prevention:**
- Write descriptions as if explaining to a new developer who cannot see the code: "Retrieves the 12-month billing history for a customer by their CRM customer ID (format: CUST-NNNN). Must be called before compute_recommendation. Returns monthly kWh usage and billed amounts."
- Mark required parameters as required, with example values in the description.
- Test schema descriptions by asking Claude directly (outside of Bedrock Agents) whether it would call the tools in the right order given a user prompt.

**Phase:** Action group design phase.

---

### Pitfall M4: Session State Not Threaded Through the Demo UI

**What goes wrong:** The call centre agent opens a customer account, gets a recommendation, then navigates to a second customer. The Bedrock agent session still has the first customer's context loaded. The second recommendation is wrong (applied to the wrong customer's data).

**Why it happens:** Bedrock agents maintain session state across `InvokeAgent` calls using `sessionId`. If the UI reuses the same `sessionId` across different customers, or fails to start a new session when switching accounts, session state bleeds between customers.

**Consequences:** During a demo where the presenter shows multiple customer personas, the second and third customers get contaminated recommendations. This is extremely visible and hard to explain.

**Prevention:**
- Use a new `sessionId` for every customer account lookup. The session ID should be scoped to `(userId, customerId, timestamp)` or similar.
- The default idle session TTL is 30 minutes — a new session per customer lookup is cleaner than relying on expiry.
- Test the exact demo flow (open customer A, get recommendation, open customer B, get recommendation) in staging before any rehearsal.

**Phase:** Frontend integration phase.

---

### Pitfall M5: Information Overload in the Agent-Assist UI

**What goes wrong:** The agent response is a wall of text with full billing breakdowns, tariff terms, footnotes, and caveats. The call centre agent cannot scan it in the 10 seconds before the customer expects a response. They stumble, lose confidence, and the demo fails the "usability" test.

**Why it happens:** LLMs default to comprehensive answers. Without explicit output formatting constraints, the agent will produce thorough responses that are unsuitable for a live-call scanning context.

**Consequences:** Stakeholders say "that's too complicated for our agents." Even if the logic is correct, an unusable UI kills adoption.

**Prevention:**
- Specify output format explicitly in agent instructions: two recommendation cards, each with plan name, monthly savings figure, and one-sentence pitch. No more.
- Use structured output (JSON) from the agent and render it as a card UI — do not display raw agent text.
- The entire visible output must be scannable in 5 seconds: plan name, dollar savings, one-line why.
- Test with a non-technical person role-playing as a call centre agent. If they hesitate, it is too complex.

**Phase:** UI design phase and agent instruction tuning phase.

---

### Pitfall M6: IAM Trust Policy Missing Source Condition Keys

**What goes wrong:** The agent execution role trust policy allows `bedrock.amazonaws.com` to assume the role without `aws:SourceAccount` and `aws:SourceArn` conditions. This is a security misconfiguration that AWS security reviewers will flag, and it can cause confused-deputy issues.

**Why it happens:** Quick-start tutorials and auto-generated roles sometimes omit condition keys from the trust policy to reduce setup friction.

**Consequences:** Security findings in the demo environment that require remediation before showing to a customer's security team — an embarrassing last-minute scramble.

**Prevention:**
- Always include both condition keys in the trust policy from the start (see the IAM permissions documentation pattern).
- Use specific agent ARNs in conditions once the agent ID is known (replace `*` after creation).

**Phase:** Foundation/IAM setup phase.

---

## Minor Pitfalls

---

### Pitfall m1: Streaming Permission Missing After March 2025

**What goes wrong:** Agents created after March 31, 2025 have streaming enabled by default. The agent execution role must include `bedrock:InvokeModelWithResponseStream`. Without it, all `InvokeAgent` calls fail with `AccessDeniedException`.

**Prevention:** Include `bedrock:InvokeModelWithResponseStream` in the agent execution role from the start. Do not copy IAM policies from pre-March-2025 examples.

**Phase:** Foundation/IAM setup.

---

### Pitfall m2: Agent Trace Not Enabled During Development

**What goes wrong:** The agent returns wrong results and the team has no visibility into which tool was called, with what parameters, and what it returned. Debugging becomes guesswork.

**Prevention:** Enable `enableTrace: true` on all `InvokeAgent` calls in development and staging. Log trace output to CloudWatch. Disable or reduce in production for cost, but never in dev.

**Phase:** Every phase that invokes the agent.

---

### Pitfall m3: Green vs Cheapest Plans Not Clearly Differentiated in Data

**What goes wrong:** The tariff portfolio has a Green plan that happens to also be the cheapest option. The two recommendation tracks are the same plan. The demo's core design (two differentiated tracks) collapses.

**Prevention:** Design the dummy tariff portfolio so Green and Cheapest are always different plans. Explicitly verify this invariant for all demo personas. If a customer's cheapest plan happens to be Green, show the Green card with a "bonus: this is also our greenest plan" note — do not collapse the two tracks.

**Phase:** Dummy data and tariff portfolio design phase.

---

### Pitfall m4: No Fallback When Agent Returns No Recommendation

**What goes wrong:** For a particular customer profile, the agent returns "I cannot determine a recommendation based on the available data." The demo UI shows a blank card. The presenter has to say "that's a bug, let me try another customer."

**Prevention:** Design the dummy data so all planned demo personas return valid recommendations. Add a UI fallback state that shows a friendly "Analysing billing history..." skeleton rather than a blank. Never let the UI show an empty recommendation panel in a demo context.

**Phase:** UI implementation phase.

---

### Pitfall m5: Demo Environment Is the Development Environment

**What goes wrong:** A developer makes a mid-demo code change to fix something, the agent is re-prepared, and the prepared timestamp changes mid-presentation. Or: a test invocation pollutes the session history of the demo customer.

**Prevention:** Maintain a separate, frozen demo environment (separate AWS account or at minimum separate agent alias pointing to a fixed version). Demo runs against the stable alias, never `TSTALIASID`. Lock the demo environment 48 hours before any presentation.

**Phase:** Pre-demo hardening phase.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|----------------|------------|
| AWS/Infrastructure setup | Model access not enabled, streaming permission missing, wrong region for Registry | Enable model access day 1; confirm region capabilities; use IAM policy template from docs |
| Dummy data design | Flat data with no story; savings delta too small; savings calculation inconsistency; Green > Cheapest inversion | Design personas first; validate formula in spreadsheet; enforce `cheapest >= green` invariant |
| Tariff portfolio design | Green and Cheapest collapse to same plan | Always verify the two tracks are distinct for all test personas |
| Action group / Lambda wiring | Lambda resource policy missing; schema descriptions too thin; tool call order ambiguous | Add resource policy immediately; write rich schema descriptions; test tool ordering with direct Claude calls |
| Agent instruction authoring | Instruction budget exhausted; output format not constrained | Keep instructions behavioural; mandate structured JSON output |
| Frontend integration | Session state bleeds between customers; streaming not implemented; UI shows too much text | New sessionId per customer; implement streaming from day one; render cards not raw text |
| Demo rehearsal | Agent not re-prepared after changes; model cold start; demo environment not frozen | Always check Last prepared timestamp; pre-warm before demo; freeze demo environment 48h before |
| Live demo | Second persona shows contaminated recommendation; savings numbers questioned | Test full persona sequence in staging; be ready to explain the calculation formula |

---

## Sources

- AWS Bedrock Agents IAM Permissions documentation (HIGH confidence) — confirmed resource policy requirements, trust policy condition keys, feature-specific permissions
- AWS Bedrock Agents Testing documentation (HIGH confidence) — confirmed Prepare requirement, TSTALIASID usage, streaming permission change post-March 2025
- AWS Bedrock Model Access documentation (HIGH confidence) — confirmed FTU form requirement, 15-minute subscription delay, marketplace permissions
- AWS Bedrock InvokeAgent API Reference (HIGH confidence) — confirmed error codes: `DependencyFailedException`, `AccessDeniedException`, `ThrottlingException`, `ModelNotReadyException`
- AWS Bedrock AgentCore Regional Availability documentation (HIGH confidence) — confirmed 15-region core availability, 5-region Registry, 4-region harness preview
- AWS Bedrock Agents Create documentation (HIGH confidence) — confirmed 30-minute idle session TTL default, 20,000 character instruction limit
- AWS Bedrock Agent quotas (HIGH confidence) — confirmed 20 action groups per agent, 11 APIs per agent, 2 knowledge bases per agent limits
- Energy/utilities tariff domain pitfalls (MEDIUM confidence) — domain knowledge, savings plausibility ranges, seasonal variation patterns
- Demo design failure modes (MEDIUM confidence) — applied from general AI demo experience specific to this project context
