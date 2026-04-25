# Technology Stack

**Project:** Customer Tariff & Billing Optimisation Agent
**Researched:** 2026-04-23
**Confidence:** MEDIUM-HIGH — AWS Bedrock Agents APIs are well-documented; AgentCore branding is recent and docs are sparse/gated; frontend recommendations draw on established patterns.

---

## Recommended Stack

### Core Agent Platform

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| AWS Bedrock Agents | GA (2025) | Orchestration layer for the personalisation + decision agent | Native AWS managed service; built-in ReAct orchestration, session state, action groups, knowledge bases — no custom orchestrator to maintain |
| Claude Sonnet 3.7 (or 3.5 v2) | `us.anthropic.claude-3-7-sonnet-20250219-v1:0` (cross-region) | Foundation model for agent reasoning | Best balance of reasoning depth and latency for structured recommendation tasks; supports tool use / function calling natively; cross-region inference profile increases availability |
| AWS Lambda (Python 3.12) | Runtime: python3.12 | Action group executors — business logic for billing retrieval and savings calculation | Stateless, event-driven; Bedrock calls Lambda directly per the action group contract; Python 3.12 is the current recommended runtime |

**Confidence:** HIGH — Lambda + Bedrock Agents is the documented AWS pattern. Claude 3.7 Sonnet model ID confirmed from inference profile docs (cross-region prefix `us.`).

**Note on "AgentCore" branding:** The project spec references "AWS Bedrock AgentCore." As of April 2026, this appears to be a rebranding/umbrella term AWS uses for the full Bedrock Agents + Memory + Identity + Gateway suite, announced at re:Invent 2024 / early 2025. The underlying APIs are still `bedrock-agent` and `bedrock-agent-runtime` in boto3. Build against those APIs — they are stable and GA. Do not wait for an "AgentCore-specific" SDK; it does not exist separately.

---

### Python SDK Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| boto3 | `>=1.35.0` (pin to latest at project start) | AWS SDK — both management plane (create agent/alias) and runtime plane (invoke agent) | Official AWS SDK; two relevant clients: `bedrock-agent` for management, `bedrock-agent-runtime` for invocation |
| botocore | Follows boto3 | Low-level HTTP/auth for all boto3 calls | Transitive dependency; pin boto3, botocore follows |
| langchain-aws | `>=0.2.0` | Optional wrapper: `BedrockAgentsRunnable`, `BedrockInlineAgentsRunnable`, `AmazonKnowledgeBasesRetriever` | Useful if agent invocation needs to be embedded in a LangChain chain or if Knowledge Base retrieval needs filtering; skip if calling `invoke_agent` directly via boto3 |

**boto3 client split — critical detail:**

```python
# Management plane: create/update/delete agents, aliases, knowledge bases, action groups
mgmt = boto3.client("bedrock-agent", region_name="us-east-1")

# Runtime plane: invoke an agent, retrieve from knowledge base
runtime = boto3.client("bedrock-agent-runtime", region_name="us-east-1")

# Invoke the agent — response is a streaming EventStream
response = runtime.invoke_agent(
    agentId="AGENT_ID",
    agentAliasId="ALIAS_ID",
    sessionId="session-customer-12345",
    inputText="Analyse this customer's billing and recommend plans.",
    sessionState={
        "sessionAttributes": {
            "customer_id": "12345",
            "account_number": "ACC-9876"
        }
    }
)

# Stream the response chunks
for event in response["completion"]:
    if "chunk" in event:
        text = event["chunk"]["bytes"].decode("utf-8")
        print(text, end="", flush=True)
```

**Confidence:** HIGH — boto3 client names and InvokeAgent signature confirmed from official API reference.

---

### Agent Architecture: Personalisation + Decision Pattern

For this project, use a **single Bedrock Agent with two action groups**. Multi-agent collaboration is not warranted — the task is deterministic (retrieve billing history → compute savings → rank plans), not a complex routing problem.

**Agent structure:**

```
Bedrock Agent: "tariff-optimisation-agent"
  Foundation model: us.anthropic.claude-3-7-sonnet-20250219-v1:0
  Instruction: [Prompt that describes the two-track recommendation task]
  │
  ├── Action Group: "BillingDataRetrieval"
  │     Executor: Lambda function (tariff-billing-retrieval)
  │     Schema: Function schema (not OpenAPI) — simpler for this use case
  │     Functions:
  │       - get_customer_billing_history(customer_id: str) → 12-month billing data
  │       - get_available_tariff_plans() → current plan portfolio
  │
  └── Action Group: "SavingsCalculation"
        Executor: Lambda function (tariff-savings-calc)
        Functions:
          - calculate_savings(customer_id: str, plan_id: str) → monthly_saving, annual_saving
          - recommend_plans(customer_id: str) → {green: Plan, cheapest: Plan}
```

**Why function schema over OpenAPI schema:** OpenAPI requires maintaining a YAML/JSON spec file in S3. Function schema is defined inline in the CDK/CloudFormation construct and is simpler to iterate on for a demo. Use OpenAPI only if you need to expose an actual REST API from the action group.

**Session state pattern for customer_id injection:**

The call centre agent UI must pass `customer_id` as a `sessionAttribute` on every `invoke_agent` call. Lambda action group handlers receive it in `event["sessionAttributes"]["customer_id"]`. This is how the agent stays personalised to the open account without the agent having to ask.

```python
# Backend API call from frontend
runtime.invoke_agent(
    agentId=AGENT_ID,
    agentAliasId=ALIAS_ID,
    sessionId=f"cc-session-{customer_id}-{uuid4()}",
    inputText="Generate tariff recommendations for this customer.",
    sessionState={
        "sessionAttributes": {"customer_id": customer_id},
        "promptSessionAttributes": {"agent_name": agent_name}
    }
)
```

**Confidence:** HIGH — session state propagation to Lambda confirmed from official docs.

---

### Backend API (Agent Invocation Wrapper)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| AWS Lambda (Python 3.12) | Runtime: python3.12 | HTTP API handler — frontend calls this, it calls `invoke_agent` and streams back | Keeps AWS credentials server-side; thin proxy is all that's needed |
| AWS API Gateway (HTTP API) | v2 | REST endpoint the frontend calls | HTTP API (v2) is cheaper and lower-latency than REST API (v1); sufficient for this use case |
| Mangum | `>=0.17.0` | ASGI adapter if using FastAPI inside Lambda | Optional — only if you want FastAPI locally for dev ergonomics; pure Lambda handler is simpler |

**Alternative — skip Lambda wrapper entirely:** For the demo, the frontend can call `invoke_agent` directly via Amplify or a cognito-authenticated SDK call. This removes one hop. Recommended only if the frontend uses AWS Amplify with Cognito auth (see Frontend section). For a production call centre tool, always proxy through a backend.

**Confidence:** MEDIUM — this wrapper pattern is standard; the direct Amplify approach is also valid and documented but less common in enterprise deployments.

---

### Data Layer (Demo / POC)

For the POC, there is no live CRM. Use structured dummy data stored as static JSON files in S3 or embedded in the Lambda function packages.

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Amazon S3 | GA | Dummy billing data storage | Simple, cheap, Lambda can read it directly; also the source for Knowledge Base documents if needed |
| DynamoDB (optional) | GA | Customer billing records if queryable structure is needed | Only needed if the demo needs to look realistic for multiple customers dynamically; S3 JSON is sufficient for a fixed demo dataset |

**Recommendation:** Start with S3 JSON. If the demo needs to pull different data per customer_id in a clean way, use DynamoDB with a customer_id partition key. Do not use RDS for a demo — setup overhead is not justified.

**Confidence:** HIGH — this is a demo/POC constraint, not an architecture opinion.

---

### Frontend / UI Layer

The call centre agent UI needs to: (1) open a customer account, (2) trigger the Bedrock agent, (3) display the two-track recommendation clearly and fast.

**Recommended approach: React SPA + AWS Amplify**

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| React | 18.x | UI framework | Industry standard; fast to scaffold; works with Amplify Gen 2 |
| Vite | 5.x | Build tooling | Faster than Create React App; standard for new React projects in 2025 |
| AWS Amplify (Gen 2) | latest | Auth (Cognito), hosting, and optionally direct SDK calls to Bedrock | Handles auth boilerplate; can call `invoke_agent` directly from browser with Cognito federated credentials, eliminating the API Gateway hop for the demo |
| Tailwind CSS | 3.x | Styling | Fast to produce a clean, scannable agent-assist card UI without custom CSS |
| React Query (TanStack Query) | 5.x | Async state management for agent response | Handles loading/error states cleanly; streaming responses can be handled with `useQuery` + event source |

**Why not Next.js:** Next.js adds SSR complexity that provides no value here. This is a pure client-side agent-assist panel embedded in (or adjacent to) a CRM screen. React + Vite is simpler and faster to demo.

**Why not Vue or Angular:** No strong reason to avoid them, but React has the widest Amplify ecosystem and most AWS sample code. Stick with React to maximise reusable patterns.

**Streaming the agent response to UI:**

Bedrock's `invoke_agent` returns an EventStream. The backend Lambda must buffer and forward chunks, or use SSE (Server-Sent Events) to the frontend. For the demo, a non-streaming approach (wait for full response, display at once) is acceptable and simpler.

```
Option A (demo-appropriate): Lambda buffers full response → JSON response → React displays
Option B (production-quality): Lambda SSE → React EventSource hook → streaming display
```

Use Option A for the POC. It removes streaming complexity and the response is short (two plan cards + savings figures).

**Confidence:** MEDIUM — React + Amplify is well-established; the streaming choice is pragmatic for demo scope.

---

### Infrastructure as Code

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| AWS CDK (Python) | `>=2.150.0` | Deploy all AWS resources | Python throughout the stack; CDK v2 is stable and GA; better than Terraform for AWS-native resources because construct library understands IAM relationships |
| aws-cdk-lib | `>=2.150.0` | All L1 constructs including `CfnAgent`, `CfnKnowledgeBase`, `CfnDataSource`, `CfnAgentAlias` | L1 Cfn constructs are stable; use these over the alpha `aws_bedrock_alpha` L2 constructs |
| cdklabs.generative-ai-cdk-constructs | check latest | Higher-level Bedrock constructs | This community-maintained CDK construct library (from AWS Labs) has L2 Bedrock constructs that wrap agents and knowledge bases more ergonomically — evaluate but don't depend on if its API is unstable |

**Key CDK pattern for this project:**

```python
from aws_cdk import aws_bedrock as bedrock, aws_iam as iam, aws_lambda as lambda_

# IAM role for the agent
agent_role = iam.Role(self, "AgentRole",
    assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
    managed_policies=[
        iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess")
    ]
)

# Lambda for billing retrieval action group
billing_lambda = lambda_.Function(self, "BillingRetrieval",
    runtime=lambda_.Runtime.PYTHON_3_12,
    handler="handler.lambda_handler",
    code=lambda_.Code.from_asset("lambdas/billing_retrieval"),
)
billing_lambda.add_permission("BedrockInvoke",
    principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
    action="lambda:InvokeFunction"
)

# Agent using L1 CfnAgent
agent = bedrock.CfnAgent(self, "TariffAgent",
    agent_name="tariff-optimisation-agent",
    foundation_model="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    agent_resource_role_arn=agent_role.role_arn,
    instruction="You are a tariff optimisation assistant for energy customers...",
    auto_prepare=True,
    action_groups=[
        bedrock.CfnAgent.AgentActionGroupProperty(
            action_group_name="BillingDataRetrieval",
            action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                lambda_=billing_lambda.function_arn
            ),
            function_schema=bedrock.CfnAgent.FunctionSchemaProperty(
                functions=[
                    bedrock.CfnAgent.FunctionProperty(
                        name="get_customer_billing_history",
                        description="Retrieve 12 months of billing data for a customer",
                        parameters={
                            "customer_id": bedrock.CfnAgent.ParameterDetailProperty(
                                type="string", description="The customer identifier", required=True
                            )
                        }
                    )
                ]
            )
        )
    ]
)

# Alias for stable invocation
agent_alias = bedrock.CfnAgentAlias(self, "TariffAgentAlias",
    agent_id=agent.attr_agent_id,
    agent_alias_name="live"
)
```

**Why CDK Python over Terraform:** Terraform's AWS provider has limited Bedrock Agent resource support and requires HCL. CDK uses Python (same language as the Lambdas), has official CloudFormation Bedrock resources, and handles IAM grants more cleanly. For a demo, CDK is faster to iterate.

**Why L1 (Cfn) over L2 alpha:** `aws_bedrock_alpha` L2 constructs exist but are in alpha — breaking changes are likely. Use L1 CfnAgent constructs directly; they are stable.

**Confidence:** HIGH for CDK approach; MEDIUM for specific version numbers (verify at project start).

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Orchestrator | AWS Bedrock Agents | LangGraph + Bedrock Converse API | LangGraph gives more control but requires managing your own orchestration loop, state machine, and hosting (Lambda or container). Bedrock Agents manages this for you — right choice for a platform-aligned demo. |
| Orchestrator | AWS Bedrock Agents | Bedrock Flows | Flows are deterministic DAG workflows — good for fixed pipelines but less flexible than agents when the model needs to reason about which data to fetch. Use Flows only if the recommendation pipeline is fully linear and never needs conditional branching. |
| Foundation model | Claude Sonnet 3.7 | Claude Haiku 3.5 | Haiku is faster/cheaper but weaker reasoning for structured multi-step tasks. For a demo with a small customer dataset, cost is irrelevant — use Sonnet for better output quality. |
| Foundation model | Claude Sonnet 3.7 | Amazon Nova Pro | Nova Pro is cheaper on Bedrock and AWS-native, but Anthropic Claude has superior instruction-following for agent tasks. Claude is the de facto standard for Bedrock Agents in 2025. |
| Action group schema | Function schema | OpenAPI schema | OpenAPI requires maintaining a YAML file in S3 and is overkill unless you're exposing a real REST API. Function schema is defined inline in CDK. |
| Action executor | Lambda | Return Control pattern | Return Control is useful when the business logic lives in the calling application. For this demo, Lambda is simpler — all logic stays in the agent backend. |
| Frontend | React + Vite | Streamlit | Streamlit is faster to scaffold but produces a data-science UI, not a call centre tool. A React app can be styled to look embedded in a CRM panel. |
| Frontend | React + Vite | Next.js | SSR adds complexity with no benefit for a client-side agent-assist panel. |
| IaC | AWS CDK (Python) | Terraform | Terraform AWS provider has immature Bedrock Agent support. CDK uses Python (matching the Lambda runtimes) and has official CloudFormation resources. |
| IaC | AWS CDK (Python) | AWS SAM | SAM is Lambda-focused and doesn't support Bedrock Agent resources. CDK covers the full stack. |
| Data store | S3 JSON (demo) | Aurora PostgreSQL | No live CRM in v1. Aurora adds cost and setup overhead unjustified for dummy data. |

---

## Installation

```bash
# CDK project setup
pip install aws-cdk-lib==2.150.0 constructs>=10.0.0

# Lambda dependencies (per function)
pip install boto3>=1.35.0

# Optional: LangChain AWS if using higher-level agent wrappers
pip install langchain-aws>=0.2.0 langchain-core>=0.3.0

# Frontend
npm create vite@latest agent-ui -- --template react-ts
cd agent-ui && npm install
npm install @tanstack/react-query tailwindcss @aws-amplify/ui-react aws-amplify
npx tailwindcss init -p
```

---

## Key Limits to Design Around

From AWS documentation (confirmed):

| Limit | Value | Impact |
|-------|-------|--------|
| Action groups per agent | 20 (adjustable) | No issue — 2 action groups planned |
| Knowledge bases per agent | 2 (adjustable) | No issue — no KB needed for demo (dummy data in Lambda) |
| Characters in agent instruction | 20,000 | Keep system prompt under 20K chars |
| Lambda response payload | Standard Lambda sync limit (6 MB) | Keep billing data response compact (JSON, not full raw data) |
| Concurrent agent sessions | Region quota — default adequate for demo | Not a concern at demo scale |

---

## Sources

- AWS Bedrock Agents overview: https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html
- InvokeAgent API reference: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeAgent.html
- Lambda action group payload format: https://docs.aws.amazon.com/bedrock/latest/userguide/agents-lambda.html
- Session state documentation: https://docs.aws.amazon.com/bedrock/latest/userguide/agents-session-state.html
- Return control pattern: https://docs.aws.amazon.com/bedrock/latest/userguide/agents-returncontrol.html
- Multi-agent collaboration: https://docs.aws.amazon.com/bedrock/latest/userguide/agents-multi-agent-collaboration.html
- CDK CfnAgent construct: https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrock/CfnAgent.html
- Service limits: https://docs.aws.amazon.com/general/latest/gr/bedrock.html
- Knowledge Base creation: https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-create.html
- Agent memory: https://docs.aws.amazon.com/bedrock/latest/userguide/agents-memory.html
- LangChain AWS (Context7, HIGH confidence): /langchain-ai/langchain-aws
- Boto3 changelog (Context7, HIGH confidence): /boto/boto3
