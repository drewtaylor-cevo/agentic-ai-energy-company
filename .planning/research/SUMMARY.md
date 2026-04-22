# Research Summary: Customer Tariff & Billing Optimisation Agent

**Synthesised:** 2026-04-23
**Feeds into:** Roadmap creation
**Reading time:** ~2 minutes

---

## Executive Summary

This is a call centre agent-assist demo for an energy & utilities provider. A call centre agent opens a customer account, the system retrieves 12 months of billing history, and an AI agent returns two ranked tariff recommendations — the greenest plan and the cheapest plan — with projected monthly savings. The core value proposition is "customer bill → instant personalised savings plan" while the customer is on the line.

The recommended build path is: dummy data first, Bedrock AgentCore (Strands SDK + @tool pattern) for agent logic, a thin Lambda/API Gateway backend, and a React + Vite frontend styled as a CRM-adjacent panel. The entire stack is AWS-native and deployable end-to-end with AWS CDK (Python). The architecture is deliberately shallow — two tool calls in the agentic loop (fetch billing, calculate savings), deterministic arithmetic, LLM used only for narrative and recommendation composition.

The primary risks are not technical complexity but demo hygiene: model access not enabled before rehearsal, savings numbers that do not survive scrutiny, agent latency perceived as unusable, and dummy data that tells no story. All three are design-time decisions, not build-time problems.

---

## Recommended Stack

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Agent runtime | AWS Bedrock AgentCore (Strands SDK) | GA 2025/2026 | BedrockAgentCoreApp + @tool pattern — simpler than classic action groups + Lambda |
| Foundation model | Claude 3.5 Sonnet (cross-region) | us.anthropic.claude-3-5-sonnet-20241022-v2:0 | Best reasoning/latency balance; Claude 3.7 also valid |
| Agent tools | Strands @tool-decorated Python functions | — | Three tools: get_billing_history, get_tariff_plans, simulate_savings |
| Backend API | AWS Lambda (Python 3.12) + API Gateway HTTP v2 | python3.12 | Thin proxy: injects customerId, calls AgentCore, streams response |
| AWS SDK | boto3 | >=1.35.0 | Two clients: bedrock-agent (management) and bedrock-agent-runtime (invocation) |
| Data layer | S3 JSON (demo) | — | Start here; DynamoDB if multi-customer dynamic lookup needed |
| Frontend | React 18 + Vite 5 + Tailwind CSS 3 | 18.x / 5.x / 3.x | CRM-panel aesthetic; TanStack Query 5.x for async state |
| Auth / hosting | AWS Amplify Gen 2 + Cognito | latest | Handles auth boilerplate; optional direct browser-to-AgentCore for demo |
| IaC | AWS CDK (Python) | >=2.150.0 | Use stable L1 CfnAgent constructs — NOT the alpha L2 aws_bedrock_alpha |

**Note on AgentCore vs classic Bedrock Agents:** STACK.md describes the classic action groups + Lambda pattern; ARCHITECTURE.md describes the newer Strands SDK BedrockAgentCoreApp pattern. Use the Strands/AgentCore pattern — it is simpler for demo iteration (no action group registration, no OpenAPI YAML in S3, fewer IAM wiring steps). The classic pattern is the documented fallback if Strands is unavailable in the target region.

---

## Table Stakes Features

Must be present or the demo fails on first call.

1. Customer lookup by account ID — single entry point; pre-load 5 named personas
2. 12-month billing history display — chart + monthly totals; establishes the analytical basis
3. Two recommendation cards side-by-side (Green / Cheapest) — both visible without scrolling on 1080p
4. Monthly savings headline per card — "$X/month" first; annual equivalent ("~$Y/year") below it
5. Current plan display — name, rate, daily charge; agent cannot pitch a change without this
6. Savings methodology line — one sentence under each card; survives "how did you calculate that?"
7. Data quality flag — "Based on 8 of 12 months — estimate may vary" when history is incomplete
8. Reset / new customer button — call flow continuity without page reload
9. Usage pattern narrative (Bedrock-generated) — 1-2 sentences; makes it feel personalised not automated
10. Call script snippet (Bedrock-generated) — editable paragraph the agent can read verbatim

Items 9 and 10 are trivial to add once the agent is running — include in MVP scope, not a defer.

**Defer post-demo:** objection-handling hints, seasonal savings breakdown, savings confidence band, audit log, contract end date awareness.

---

## Architecture Overview

Four layers with hard boundaries — no layer reaches across two layers to call a third.

```
UI Panel (React)
    |  HTTP POST { customerId, prompt }
    v
Backend API (Lambda + API Gateway)
    |  invoke_agent_runtime(agentRuntimeArn, runtimeSessionId, payload)
    v
Bedrock AgentCore Runtime (Strands Agent + Claude)
    |  @tool calls
    |-- get_billing_history(customer_id)  -->  Billing Store (S3 JSON / DynamoDB)
    |-- get_tariff_plans()               -->  Tariff Catalogue (S3 JSON)
    +-- simulate_savings(history, plans) -->  deterministic arithmetic (no LLM math)
    |  streaming response
    v
Backend API streams to UI --> renders two cards
```

**Key patterns:**
- customerId passed via invocation payload per call — never baked into system prompt at deploy time
- simulate_savings is a deterministic tool — Claude decides when to call it; the tool does the exact arithmetic
- runtimeSessionId is unique per customer account lookup — enforces no session bleed between customers
- Output is structured JSON from the agent; UI renders cards, never displays raw agent text
- Stream responses from day one — first visible token target: <=2s, full response: <=5s

**Dummy data constraints (pre-engineered for demo narrative):**
- Flagship customer: ~$115/month average, Green saves ~$30/month, Cheapest saves ~$55/month
- 3-5 personas with distinct stories (high-usage legacy, solar household, price-sensitive renter)
- Enforce invariant in code: cheapest_savings >= green_savings always
- Add +-15% seasonal variation — flat uniform bills look fake

---

## Top 5 Critical Pitfalls

**C1 — Model access not enabled:** Claude models require a First-Time-Use form per AWS account plus up to 15 minutes for subscription. Do this on Day 1. Verify with a live invocation, not just the console status indicator. Demo cannot proceed without it.

**C4 — Savings numbers that do not add up:** The most trust-destroying demo failure. Define the savings formula before designing dummy data. Enforce cheapest_savings >= green_savings always. Keep savings in the 10-30% range of the average bill. Validate every persona in a spreadsheet before hardcoding.

**C6 — Dummy data that tells no story:** Flat, uniform billing history with a $3/month delta generates no excitement. Design personas first. The flagship customer needs seasonal peaks, a clearly suboptimal current plan, and a $40-60/month savings delta with a quotable hook ("Mrs. Chen, I can see you've been on Standard Rate for 3 years...").

**C5 — Agent latency perceived as unusable:** Multiple tool calls + LLM = 6-12s without care. Pre-warm 30-60 seconds before any demo. Design UX so the query triggers while the "account is loading" (masks 3-5s naturally). Stream responses — never show a blank screen.

**M1 — Wrong AWS region:** AgentCore harness (preview) is available in only 4 regions; Agent Registry in 5. ap-southeast-2 (Sydney) does NOT support Registry. Confirm target region before writing a single CDK line. For maximum feature availability: us-east-1.

**Also watch:** Lambda resource policy missing (bedrock.amazonaws.com must explicitly be allowed to invoke tool Lambdas — C3); agent not re-prepared after every change (C2); session state bleeding between demo personas (M4).

---

## Build Order

Dependencies are strictly bottom-up: data before tools, tools before agent, agent before API, API before UI.

**Phase 1 — Foundation + Dummy Data**
- Enable Claude model access in target AWS account (Day 1)
- Confirm AWS region supports all required AgentCore features
- CDK project skeleton; IAM roles with correct trust policy and source condition keys (include bedrock:InvokeModelWithResponseStream)
- Design 3-5 customer personas and tariff portfolio — validate savings formula in a spreadsheet first
- Load dummy data into S3 JSON
- Write and unit-test get_billing_history and simulate_savings in isolation (no AI)
- Gate: given a customerId, retrieve billing history and compute correct savings without any AI

**Phase 2 — AgentCore Agent**
- Write Strands @tool decorators for three tools
- Write BedrockAgentCoreApp entrypoint with system prompt (keep under 15,000 chars; reserve headroom)
- Deploy to AgentCore; enable enableTrace: true on all dev invocations
- Verify correct tool call sequence and savings accuracy for all demo personas
- Gate: direct invoke_agent_runtime call returns correct Green/Cheapest recommendations for all planned personas

**Phase 3 — Backend API + Streaming**
- Lambda + API Gateway (HTTP v2) accepting { customerId }, calling AgentCore, streaming response
- Enforce new runtimeSessionId per customer lookup here
- Error handling: customer not found, agent timeout, no recommendation returned
- Gate: curl/Postman to API returns correct streaming recommendation for any demo persona

**Phase 4 — Agent-Assist UI**
- Customer ID lookup + Get Recommendations trigger
- Two recommendation cards with savings headline, methodology line, plan details
- Loading skeleton states (never show blank cards)
- Usage pattern narrative and call script snippet above the fold
- Desktop-first, 1280px fixed layout; scannable in 5 seconds without scrolling
- Gate: call centre agent opens panel, enters customer ID, reads both recommendations within 5-8 seconds

**Phase 5 — Demo Hardening**
- Separate frozen demo environment (separate alias pointing to fixed version)
- Pre-warm script to run 30-60 seconds before presentation
- Walk full persona sequence in staging (not just the flagship customer)
- Lock demo environment 48 hours before any presentation

---

## Open Questions (Resolve Before or During Phase 1)

1. **Which AWS region?** If not constrained to ap-southeast-2, use us-east-1 for maximum AgentCore feature availability. Confirm before writing CDK.

2. **Strands SDK vs classic Bedrock Agents?** This summary recommends Strands/AgentCore. Confirm it is available and stable in the target region/account before Phase 2.

3. **Savings formula denominator: kWh-based or dollar-based?** kWh-based is more accurate but requires kWh data in every billing record. Dollar-based is simpler. Lock this before designing dummy data schema.

4. **How many demo personas?** Minimum 3 (high-usage, solar, price-sensitive). Confirm before building dummy data — each persona must be manually verified before any rehearsal.

5. **Streaming or buffered UI response?** Streaming reduces perceived latency risk (C5) but adds frontend complexity. Buffered is simpler for demo scope. Decision affects Phase 3 and 4 planning.

6. **Demo authentication?** Amplify + Cognito adds setup overhead. A hardcoded API key on API Gateway is sufficient for a locked-down internal demo. Decide before Phase 3.

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|-----------|-------|
| Stack | HIGH | boto3 API signatures, CDK constructs, model IDs confirmed from official AWS docs |
| Features | HIGH | Call centre UX principles well-established; features derive from first principles |
| Architecture | HIGH | AgentCore developer guide (Context7) + official Bedrock docs; data flow well-documented |
| Pitfalls | MEDIUM-HIGH | AWS pitfalls confirmed from official docs; demo design pitfalls from domain knowledge |
| Strands SDK pattern | MEDIUM | Newer (2026); documented but less battle-tested than classic Bedrock Agents action groups |

**Key gap:** If Strands/BedrockAgentCoreApp proves unavailable or unstable in the target region, the fallback is classic Bedrock Agents (action groups + Lambda). STACK.md covers the fallback pattern in full detail including CDK constructs and session state injection.

---

## Sources

- AWS Bedrock Agents official docs (HIGH): agents.html, InvokeAgent API, agents-lambda.html, agents-session-state.html, agents-returncontrol.html
- Amazon Bedrock AgentCore Developer Guide (HIGH): Context7 /websites/aws_amazon_bedrock-agentcore_devguide
- AWS CDK CfnAgent construct (HIGH): docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrock/CfnAgent.html
- AWS Bedrock IAM Permissions, Model Access, Regional Availability, Quotas docs (HIGH)
- boto3 changelog (HIGH): Context7 /boto/boto3
- LangChain AWS (MEDIUM): Context7 /langchain-ai/langchain-aws
- Call centre agent-assist UX patterns, energy/utility domain knowledge (MEDIUM — training knowledge)
