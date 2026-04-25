# Architecture Patterns: Customer Tariff & Billing Optimisation Agent

**Domain:** AI agent-assist recommendation system — Energy & Utilities call centre
**Platform:** AWS Bedrock AgentCore (Strands SDK + BedrockAgentCoreApp runtime)
**Researched:** 2026-04-23
**Confidence:** HIGH (Context7 AgentCore devguide + official AWS Bedrock docs)

---

## Recommended Architecture

The system has four distinct layers. Boundaries are hard — no layer reaches across two layers to talk to a third.

```
┌─────────────────────────────────────────────────┐
│              CALL CENTRE UI (Layer 4)           │
│   React/Next.js agent-assist panel              │
│   Customer lookup → recommendation display      │
└───────────────────┬─────────────────────────────┘
                    │  HTTP POST (customerId, prompt)
                    │  ← streaming text response
                    ▼
┌─────────────────────────────────────────────────┐
│         API GATEWAY / BACKEND (Layer 3)         │
│   Thin HTTP adapter — passes customerId into    │
│   sessionAttributes, forwards to AgentCore      │
└───────────────────┬─────────────────────────────┘
                    │  invoke_agent_runtime(agentRuntimeArn,
                    │    runtimeSessionId, payload)
                    │  ← streaming response chunks
                    ▼
┌─────────────────────────────────────────────────┐
│       BEDROCK AGENTCORE RUNTIME (Layer 2)       │
│   BedrockAgentCoreApp + Strands Agent           │
│   Foundation model: Claude 3.5 Sonnet           │
│   Tools: @tool-decorated Python functions       │
│   ┌───────────────┐  ┌───────────────────────┐  │
│   │ get_billing_  │  │ get_tariff_plans()    │  │
│   │ history()     │  │ simulate_savings()    │  │
│   │ (CRM tool)    │  │ (calculation tool)    │  │
│   └───────┬───────┘  └──────────┬────────────┘  │
└───────────┼──────────────────────┼───────────────┘
            │                      │
            ▼                      ▼
┌─────────────────────────────────────────────────┐
│           DATA LAYER (Layer 1)                  │
│   ┌──────────────────┐  ┌─────────────────────┐ │
│   │  Billing Store   │  │   Tariff Catalogue  │ │
│   │  (DynamoDB or    │  │   (S3 JSON or       │ │
│   │   S3 JSON)       │  │    DynamoDB)        │ │
│   │  customer_id →   │  │  plan_id, rate,     │ │
│   │  12 months data  │  │  green_flag         │ │
│   └──────────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **UI Panel** | Customer lookup form, renders two recommendation cards (Green / Cheapest), displays monthly savings delta | Backend API only |
| **Backend API** | Validates request, injects `customerId` into `sessionAttributes`, calls AgentCore Runtime, streams response to UI | UI Panel, AgentCore Runtime |
| **AgentCore Runtime** | Orchestrates the agentic loop via Claude; invokes tools; composes the recommendation response | Backend API (receives invocation), Data Layer tools (calls them) |
| **CRM Tool (`get_billing_history`)** | Retrieves 12-month billing records for a given `customerId`; returns structured monthly totals and usage | AgentCore Runtime only |
| **Tariff Tool (`get_tariff_plans`)** | Returns the current tariff plan catalogue with rates, tier structures, and green flags | AgentCore Runtime only |
| **Savings Tool (`simulate_savings`)** | Accepts billing history + plan parameters; calculates projected monthly cost and delta vs current spend | AgentCore Runtime only |
| **Billing Store** | Authoritative source of per-customer billing history (dummy data in v1) | CRM Tool only |
| **Tariff Catalogue** | Authoritative source of available plans (dummy data in v1) | Tariff Tool only |

---

## Data Flow (End-to-End)

```
1. Call centre agent opens customer account in UI
   → UI sends POST { customerId: "C-001", prompt: "Show recommendations" }

2. Backend API receives request
   → Wraps customerId in sessionAttributes
   → Calls invoke_agent_runtime(payload, sessionAttributes: { customerId })

3. AgentCore Runtime starts agentic loop (Claude orchestrating)
   → Claude decides to call get_billing_history(customerId)
   → CRM Tool queries Billing Store → returns 12 months of { month, kwh, cost }
   → Claude receives billing data

4. Claude decides to call get_tariff_plans()
   → Tariff Tool reads catalogue → returns list of { planId, name, ratePerKwh, greenFlag }

5. Claude decides to call simulate_savings(billingHistory, plans)
   → Savings Tool calculates:
       current_avg_monthly = mean(billing_history.cost)
       green_plan_cost = projected cost on greenest plan
       cheapest_plan_cost = projected cost on lowest-rate plan
       green_saving = current_avg - green_plan_cost
       cheapest_saving = current_avg - cheapest_plan_cost
   → Returns { green: { planName, saving }, cheapest: { planName, saving } }

6. Claude composes recommendation response (structured text or JSON)
   → AgentCore streams response back to Backend API

7. Backend API streams response to UI
   → UI renders two recommendation cards side-by-side:
       [Green Plan: EcoFlex100 — save $32/month]
       [Cheapest Plan: ValueRate — save $55/month]
```

---

## Bedrock AgentCore-Specific Patterns

### Pattern 1: BedrockAgentCoreApp + Strands @tool decorator

The recommended AgentCore v2 pattern (as of 2026) is the **Strands SDK** running inside a `BedrockAgentCoreApp` container. Tools are Python functions decorated with `@tool`. This is simpler than the classic Bedrock Agents action-groups-plus-Lambda approach and better suited to a demo.

```python
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@tool
def get_billing_history(customer_id: str) -> dict:
    """Retrieve 12-month billing history for a customer from the CRM store."""
    # query DynamoDB or S3 JSON with customer_id
    ...

@tool
def get_tariff_plans() -> list:
    """Return all available tariff plans from the catalogue."""
    ...

@tool
def simulate_savings(billing_history: list, plans: list) -> dict:
    """Calculate projected monthly savings for Green and Cheapest plans."""
    ...

model = BedrockModel(model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0")
agent = Agent(model=model, tools=[get_billing_history, get_tariff_plans, simulate_savings])

@app.entrypoint
def handle_request(payload):
    customer_id = payload.get("customer_id")
    response = agent(f"Analyse billing history for customer {customer_id} and recommend the best Green and Cheapest plans with projected monthly savings.")
    return {"response": response.message["content"][0]["text"]}

if __name__ == "__main__":
    app.run()
```

### Pattern 2: Session isolation via runtimeSessionId

Each call centre session gets a unique `runtimeSessionId`. AgentCore provisions a dedicated microVM per session. Idle sessions are cleaned up automatically. The `customerId` travels via the payload (not session state in this simpler pattern).

```python
# Backend API — one session per call centre conversation
import uuid
response = client.invoke_agent_runtime(
    agentRuntimeArn=AGENT_ARN,
    runtimeSessionId=str(uuid.uuid4()),   # unique per call
    payload=json.dumps({"customer_id": "C-001", "prompt": "..."}).encode()
)
```

### Pattern 3: Classic Bedrock Agents (alternative, not recommended for demo)

The older pattern uses `InvokeAgent` / `InvokeInlineAgent` with action groups defined via OpenAPI schemas and Lambda functions. It requires more AWS resource configuration (agent creation, action group registration, Lambda permissions). Return-of-Control variant lets the UI handle tool execution itself. This pattern is valid for production but adds setup overhead that slows a demo — use Strands + AgentCore Runtime instead.

---

## Dummy Data Schema

Structure dummy data to make the recommendation delta compelling and clearly differentiated between the two tracks.

### Billing Store (DynamoDB or S3 JSON)

```json
{
  "customer_id": "C-001",
  "name": "Sarah Mitchell",
  "current_plan": "StandardRate",
  "current_rate_per_kwh": 0.28,
  "billing_history": [
    { "month": "2025-04", "kwh": 410, "cost": 114.80 },
    { "month": "2025-05", "kwh": 380, "cost": 106.40 },
    { "month": "2025-06", "kwh": 320, "cost":  89.60 },
    { "month": "2025-07", "kwh": 295, "cost":  82.60 },
    { "month": "2025-08", "kwh": 310, "cost":  86.80 },
    { "month": "2025-09", "kwh": 355, "cost":  99.40 },
    { "month": "2025-10", "kwh": 420, "cost": 117.60 },
    { "month": "2025-11", "kwh": 490, "cost": 137.20 },
    { "month": "2025-12", "kwh": 540, "cost": 151.20 },
    { "month": "2026-01", "kwh": 510, "cost": 142.80 },
    { "month": "2026-02", "kwh": 470, "cost": 131.60 },
    { "month": "2026-03", "kwh": 430, "cost": 120.40 }
  ]
}
```

Design note: 12-month average should be ~$115/month. Green plan saves ~$30, Cheapest saves ~$55. This makes the demo narrative work — Green is meaningfully different from Cheapest, not noise.

### Tariff Catalogue (S3 JSON or DynamoDB)

```json
[
  {
    "plan_id": "STD",
    "name": "StandardRate",
    "rate_per_kwh": 0.28,
    "daily_supply_charge": 1.10,
    "green": false,
    "renewable_pct": 0,
    "description": "Standard variable rate"
  },
  {
    "plan_id": "ECO",
    "name": "EcoFlex100",
    "rate_per_kwh": 0.235,
    "daily_supply_charge": 1.20,
    "green": true,
    "renewable_pct": 100,
    "description": "100% renewable energy — GreenPower accredited"
  },
  {
    "plan_id": "VAL",
    "name": "ValueRate",
    "rate_per_kwh": 0.195,
    "daily_supply_charge": 1.35,
    "green": false,
    "renewable_pct": 20,
    "description": "Lowest unit rate, fixed 12-month term"
  },
  {
    "plan_id": "FLEX",
    "name": "FlexTime",
    "rate_per_kwh_peak": 0.32,
    "rate_per_kwh_offpeak": 0.14,
    "daily_supply_charge": 1.15,
    "green": false,
    "renewable_pct": 30,
    "description": "Time-of-use: cheaper off-peak"
  }
]
```

Design note: EcoFlex100 is the Green recommendation (only 100% renewable). ValueRate is Cheapest (lowest unit rate). FlexTime is deliberately ambiguous — agent should not recommend it without usage-time data.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Knowledge Base for structured billing data

Bedrock Knowledge Bases use vector embeddings (RAG) for unstructured document retrieval. They are not designed for structured tabular queries like "return 12 monthly rows for customer C-001." Using a Knowledge Base for billing history would result in imprecise retrieval and incorrect savings calculations.

Use a Lambda-backed tool (or Strands @tool function) that does a direct DynamoDB/S3 lookup by customer ID instead.

### Anti-Pattern 2: Putting savings calculation inside the Claude prompt

Instructing Claude to "calculate the projected monthly cost" in the system prompt and relying on the LLM to do arithmetic is unreliable. Use a deterministic `simulate_savings` tool for the arithmetic. Claude decides when to call it; the tool does the math exactly.

### Anti-Pattern 3: One monolithic Lambda for all tools

Bundling CRM retrieval, tariff lookup, and savings simulation into a single Lambda with a routing switch creates tight coupling and makes the system hard to test in isolation. Keep tools as separate functions (or separate Lambdas if using classic action groups).

### Anti-Pattern 4: Blocking UI waiting for full response

The agentic loop (multiple tool calls + LLM reasoning) takes several seconds. The UI must use streaming (`response.body` event stream from `invoke_agent_runtime`) and show a loading state per recommendation card, not a full-page spinner. AgentCore Runtime supports streaming natively.

### Anti-Pattern 5: Hardcoding customer context in the system prompt

Do not bake `customerId` into the agent's system prompt at deployment time. Pass it per-invocation via the payload, so the same deployed agent handles all customers.

---

## Suggested Build Order

Dependencies flow bottom-up: data layer must exist before tools, tools before agent, agent before API, API before UI.

### Phase 1: Data Foundation
Build and validate the dummy data files before writing a single line of agent code.

1. Design the 3-5 customer profiles (billing histories crafted to produce compelling deltas)
2. Design the tariff catalogue (ensure Green and Cheapest are clearly differentiated)
3. Load into DynamoDB (or S3 JSON for lowest setup friction in demo)
4. Write and manually test the `get_billing_history` lookup function in isolation
5. Write and manually test the `simulate_savings` calculation function in isolation

Checkpoint: given a `customerId`, you can retrieve billing history and compute savings without any AI involved.

### Phase 2: Agent Core
Wrap the validated functions in the AgentCore Runtime pattern.

1. Create the Strands `@tool` decorators for the three tools
2. Write the `BedrockAgentCoreApp` entrypoint with system prompt
3. Deploy to AgentCore (ECR container or zip deployment)
4. Test via `invoke_agent_runtime` directly (boto3 / AWS CLI) — verify the agent calls the right tools in the right order

Checkpoint: a curl / Python test call returns structured Green and Cheapest recommendations with correct savings figures for a known customer.

### Phase 3: Backend API
Thin wrapper so the UI has something to call.

1. Lambda + API Gateway (or FastAPI on Lambda) that accepts `{ customerId }` and calls AgentCore
2. Stream the response back to the caller
3. Handle errors (customer not found, agent timeout)

Checkpoint: Postman or curl to the API endpoint returns a streaming recommendation for a known customer.

### Phase 4: Agent-Assist UI
Build against the working API.

1. Customer ID lookup / search field
2. "Get Recommendations" trigger button
3. Two recommendation cards (Green / Cheapest) with savings figure
4. Loading states per card (streaming-aware)
5. Polish for call centre context: large text, scannable, no extraneous chrome

Checkpoint: Call centre agent can open the panel, enter a customer ID, and read both recommendations within 5-8 seconds.

---

## Scalability Considerations (Post-Demo)

| Concern | Demo (dummy data) | Production |
|---------|------------------|------------|
| Data store | S3 JSON or single DynamoDB table | CRM API integration via secure tool |
| Auth | IAM role on the backend service | Amazon Cognito for call centre agents |
| Concurrency | One session per test | AgentCore scales sessions via microVM isolation |
| Latency | 5-8s acceptable for demo | Cache tariff catalogue; pre-warm agent runtime |
| Auditability | None needed | Log every recommendation with agent trace ID |

---

## Sources

- Amazon Bedrock AgentCore Developer Guide (Context7 ID: `/websites/aws_amazon_bedrock-agentcore_devguide`) — HIGH confidence
- Bedrock Agents Lambda event/response structure: `https://docs.aws.amazon.com/bedrock/latest/userguide/agents-lambda.html` — HIGH confidence
- Bedrock Agents session state: `https://docs.aws.amazon.com/bedrock/latest/userguide/agents-session-state.html` — HIGH confidence
- Return of Control pattern: `https://docs.aws.amazon.com/bedrock/latest/userguide/agents-returncontrol.html` — HIGH confidence
- Multi-agent energy workshop (AWS Samples, Context7 ID: `/aws-samples/bedrock-multi-agents-collaboration-workshop`) — MEDIUM confidence (supervisor/sub-agent pattern is overkill for this demo but validates energy domain feasibility)
- Knowledge Bases structured data limitation: `https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-create.html` — HIGH confidence
