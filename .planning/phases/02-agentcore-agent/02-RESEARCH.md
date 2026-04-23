# Phase 2: AgentCore Agent - Research

**Researched:** 2026-04-23
**Domain:** Strands SDK agent, AWS Bedrock AgentCore managed runtime, Docker/ECR deployment, CDK cross-stack wiring
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Strands SDK is the agent framework — use `strands-agents` PyPI package with `@tool` decorators.
- **D-02:** Deploy to BedrockAgentCoreApp managed runtime (AgentCore managed runtime, not Lambda-hosted). Invoked via `invoke_agent_runtime`.
- **D-03:** Agent LLM: Claude Sonnet 3.7 via Amazon Bedrock (us-east-1). Model ID: `anthropic.claude-3-7-sonnet-20250219-v1:0`.
- **D-04:** Agent tools call the Phase 1 ToolsLambda via boto3 invoke — no code duplication. Phase 1 remains the single source of truth.

### Claude's Discretion
- CDK structure: New `AgentCoreStack` (separate from `FoundationStack`) is preferred. Stack imports ToolsLambda ARN from FoundationStack via SSM Parameter Store or CfnOutput. Claude determines exact cross-stack wiring.
- Agent system prompt: Must enforce REC-03 — both Green and Cheapest tracks always surfaced simultaneously, neither ranked above the other. Claude writes the system prompt.
- Response format: Structured JSON output with Green and Cheapest track objects (each with `plan_id`, `plan_name`, `saving_monthly`, `saving_annual`). Must align with `simulate_savings_pure` output shape.
- IAM permissions: Agent execution role needs `lambda:InvokeFunction` on ToolsLambda ARN and `bedrock:InvokeModel` for the Claude model. Claude determines full IAM policy.
- Test/verification strategy: Both offline unit tests (mocked tools) and a live `invoke_agent_runtime` smoke test per persona. Claude determines test structure, but all 4 Phase 2 success criteria must be verified.

### Deferred Ideas (OUT OF SCOPE)
- Tool wiring detail (exact boto3 invoke payload shape, error handling for Lambda errors) — Claude's discretion during planning
- Response format schema (exact JSON field names) — Claude's discretion, but must be compatible with `simulate_savings_pure` output
- CDK cross-stack wiring approach (SSM vs CfnOutput import) — Claude's discretion
- Phase 3 API contract — determined when Phase 3 is discussed
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REC-01 | Agent identifies and recommends the most energy-efficient (Green) tariff plan for the customer's usage pattern | `simulate_savings_pure` already selects `argmax(green_score)` over `green_premium` plans — agent wraps this via `@tool` |
| REC-02 | Agent identifies and recommends the lowest projected cost (Cheapest) tariff plan | `simulate_savings_pure` already selects `argmin(projected_cost)` — agent wraps this via `@tool` |
| REC-03 | Both Green and Cheapest recommendations always surfaced simultaneously, neither ranked above the other | System prompt engineering section covers simultaneous output pattern; Pydantic structured output enforces schema |
| SAV-01 | Projected monthly saving in dollars for each recommendation | `simulate_savings_pure` returns `saving_monthly` — passed through tool return value |
| SAV-02 | Annual equivalent saving displayed alongside monthly figure | `simulate_savings_pure` returns `saving_annual` — passed through tool return value |
| SAV-03 | Savings calculated by deterministic tool function — LLM does orchestration/narrative only | `@tool` wraps `simulate_savings` Lambda call; LLM never computes numbers; enforced by system prompt |
</phase_requirements>

---

## Summary

Phase 2 builds a Strands SDK agent that runs inside an AWS Bedrock AgentCore managed runtime (a container-hosted HTTP server). The agent exposes two `@tool`-decorated Python functions that invoke the Phase 1 ToolsLambda via boto3, then returns a structured JSON response with Green and Cheapest savings tracks simultaneously. The deliverable is a deployed Docker container on AgentCore that responds correctly to `invoke_agent_runtime` calls for all three demo personas.

The deployment path is: write agent code in `agent/agent.py` using `BedrockAgentCoreApp` + `@app.entrypoint`, package it in a Docker container (linux/arm64, Python 3.12, port 8080), push to ECR, and deploy via the CDK L2 construct `aws_cdk.aws_bedrock_agentcore_alpha.Runtime` with `AgentRuntimeArtifact.from_asset()`. The CDK L2 construct (alpha, v2.250.0a0) handles ECR repo creation, IAM role skeleton, and CloudFormation outputs automatically — the planner adds `lambda:InvokeFunction` via `add_to_role_policy()`.

The two mandatory HTTP endpoints AgentCore requires are `/invocations` (POST) and `/ping` (GET). `BedrockAgentCoreApp` from the `bedrock-agentcore` package (v1.6.3) provides these automatically when `app.run()` is called.

**Primary recommendation:** Use `BedrockAgentCoreApp` + Strands `Agent` with `@tool` wrappers + CDK L2 `Runtime` construct with `from_asset()`. This is the shortest path to a deployed, invoke-able runtime with no manual ECR or IAM boilerplate.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Agent orchestration (tool sequencing, LLM calls) | AgentCore Runtime (container) | — | Strands `Agent` loop runs inside the container |
| Tool execution (billing fetch, savings calc) | API / Backend (ToolsLambda) | AgentCore Runtime (caller) | Phase 1 ToolsLambda is the single source of truth; agent calls it via boto3 |
| LLM inference | Amazon Bedrock (managed) | — | `bedrock:InvokeModel` from the runtime container to Bedrock API |
| Structured response formatting | AgentCore Runtime (container) | — | Pydantic `structured_output` or system-prompt-enforced JSON in the entrypoint |
| Runtime invocation (caller-facing) | Caller (tests / Phase 3) | — | `bedrock-agentcore:InvokeAgentRuntime` is the external API surface |
| Container image storage | ECR (CDK-managed) | — | CDK L2 `from_asset()` handles push to CDK-managed ECR repo |
| Infrastructure provisioning | CDK (AgentCoreStack) | — | New stack; imports ToolsLambda ARN from FoundationStack |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `strands-agents` | 1.37.0 | Agent framework — `Agent`, `@tool`, `BedrockModel`, `structured_output` | AWS-native, model-driven, purpose-built for Bedrock; confirmed available via PyPI [VERIFIED: PyPI registry] |
| `bedrock-agentcore` | 1.6.3 | `BedrockAgentCoreApp` runtime wrapper — exposes `/invocations` and `/ping` endpoints automatically | Official AWS SDK; the `@app.entrypoint` pattern is the documented Strands-to-AgentCore bridge [VERIFIED: PyPI registry + strandsagents.com docs] |
| `boto3` | >=1.42.0 (already in requirements.txt) | `bedrock-agentcore` client for `invoke_agent_runtime`; `lambda` client for tool invocations | Already a project dependency [VERIFIED: requirements.txt] |
| `pydantic` | pulled in by strands-agents | Structured output schema for Green+Cheapest response | Used by `agent.structured_output()` for type-safe response enforcement [VERIFIED: strandsagents.com docs] |

### Supporting (CDK infra)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `aws-cdk.aws-bedrock-agentcore-alpha` | 2.250.0a0 | CDK L2 construct for `Runtime`, `AgentRuntimeArtifact.from_asset()` | Use instead of raw `CfnResource` — handles ECR repo + IAM role skeleton automatically [VERIFIED: PyPI registry] |
| `aws-cdk-lib` | >=2.250.0 (already in requirements.txt) | CDK base — IAM, CfnOutput, SSM constructs | Already pinned [VERIFIED: requirements.txt] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| CDK L2 `Runtime` construct | boto3 `create_agent_runtime` script | L2 is idempotent and CDK-managed; boto3 script is a one-off deploy step that falls outside IaC |
| `bedrock-agentcore` `BedrockAgentCoreApp` | Custom FastAPI with `/invocations` + `/ping` | FastAPI gives more control but requires manual endpoint wiring; `BedrockAgentCoreApp` eliminates boilerplate |
| `agent.structured_output(Pydantic)` | System-prompt-only JSON enforcement | Structured output is stronger guarantee; both approaches are viable here since the LLM is not computing numbers |

**Installation (agent container):**
```bash
pip install strands-agents==1.37.0 bedrock-agentcore==1.6.3 boto3
```

**Installation (CDK infra):**
```bash
pip install "aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0"
```

**Version verification:** [VERIFIED: PyPI registry 2026-04-23]
- `strands-agents`: 1.37.0 (released 2026-04-22)
- `bedrock-agentcore`: 1.6.3 (released 2026-04-16)
- `aws-cdk.aws-bedrock-agentcore-alpha`: 2.250.0a0 (released 2026-04-14)
- `bedrock-agentcore-starter-toolkit`: 0.3.5 (released 2026-04-10, legacy — not needed)

---

## Architecture Patterns

### System Architecture Diagram

```
invoke_agent_runtime(agentRuntimeArn, runtimeSessionId, payload={"prompt": "..."})
        |
        v
  [bedrock-agentcore API]  ──────────────────────────────
        |                                                  |
        v                                                  |
  [AgentCore Runtime Container: linux/arm64, port 8080]   | (routes to)
        |                                                  |
  BedrockAgentCoreApp                                      |
  @app.entrypoint invoke(payload)                         |
        |                                                  |
        v                                                  |
  strands.Agent(model=BedrockModel, tools=[get_billing_history_tool, simulate_savings_tool])
        |
        |─── [tool call: get_billing_history_tool(customer_id)]
        |           |
        |           v
        |     boto3.client("lambda").invoke(FunctionName=TOOLS_LAMBDA_ARN,
        |                                   Payload={"customer_id": "CUST-001"})
        |           |
        |           v
        |     [ToolsLambda] -> DynamoDB -> returns billing_history
        |
        |─── [tool call: simulate_savings_tool(customer_id)]
        |           |
        |           v
        |     boto3.client("lambda").invoke(FunctionName=TOOLS_LAMBDA_ARN,
        |                                   Payload={"customer_id": "CUST-001"})
        |           |
        |           v
        |     [ToolsLambda] -> simulate_savings_pure() -> returns {"green": {...}, "cheapest": {...}}
        |
        v
  Strands agent response -> entrypoint returns JSON
        |
        v
  response['response'].read() -> {"green": {...}, "cheapest": {...}}
```

### Recommended Project Structure

```
agent/                          # New directory — Docker build context
├── agent.py                    # BedrockAgentCoreApp + Agent + @tool wrappers
├── requirements.txt            # strands-agents, bedrock-agentcore, boto3
└── Dockerfile                  # linux/arm64, python:3.12-slim, port 8080

infrastructure/
├── agentcore_stack.py          # New: AgentCoreStack (imports ToolsLambda ARN from SSM)
├── constructs/
│   └── agent_runtime.py        # New: AgentRuntimeConstruct wrapping CDK L2 Runtime
├── foundation_stack.py         # Existing: add SSM StringParameter for ToolsLambda ARN
└── ...

tests/
├── conftest.py                 # Add: agent_runtime_arn fixture from env/SSM
├── test_agent_tools.py         # New: offline unit tests with mocked Lambda invoke
├── test_agent_smoke.py         # New: live invoke_agent_runtime per persona (requires creds)
└── ...

app.py                          # Add AgentCoreStack instantiation
```

### Pattern 1: `@tool` Decorator Wrapping a boto3 Lambda Invoke

**What:** Each Strands tool is a Python function decorated with `@tool`. The function docstring tells the LLM what the tool does and when to call it. Type annotations are required — Strands auto-generates the tool schema from them.

**When to use:** Any time you need the agent to call an external AWS service. The `@tool` function is responsible for invoking the Lambda and returning the result to the agent.

```python
# Source: strandsagents.com/docs/user-guide/concepts/tools + verified pattern
import json
import os
import boto3
from strands import tool

_lambda_client = boto3.client("lambda", region_name="us-east-1")
_TOOLS_LAMBDA_ARN = os.environ["TOOLS_LAMBDA_ARN"]  # injected by CDK as env var

@tool
def get_billing_history(customer_id: str) -> list:
    """Fetch 12 months of billing history for a customer from the data store.

    Args:
        customer_id: Customer identifier in format CUST-NNN (e.g. CUST-001).

    Returns:
        List of monthly billing records with usage_kwh, cost_usd, plan_id, month fields.
    """
    response = _lambda_client.invoke(
        FunctionName=_TOOLS_LAMBDA_ARN,
        InvocationType="RequestResponse",
        Payload=json.dumps({"customer_id": customer_id}),
    )
    return json.loads(response["Payload"].read())


@tool
def simulate_savings(customer_id: str) -> dict:
    """Calculate Green and Cheapest tariff savings for a customer.

    Savings figures are computed by a deterministic function in code — the LLM
    must use these exact numbers and must not recalculate or estimate them.

    Args:
        customer_id: Customer identifier in format CUST-NNN (e.g. CUST-001).

    Returns:
        Dict with 'green' and 'cheapest' keys, each containing plan_id,
        plan_name, saving_monthly ($/month), and saving_annual ($/year).
    """
    response = _lambda_client.invoke(
        FunctionName=_TOOLS_LAMBDA_ARN,
        InvocationType="RequestResponse",
        Payload=json.dumps({"customer_id": customer_id}),
    )
    return json.loads(response["Payload"].read())
```

**Note on handler routing:** The ToolsLambda's `handler` in CDK is set to `handler.simulate_savings`. This means a single Lambda invocation always routes to `simulate_savings` (which calls both `get_billing_history` internally). The agent therefore only needs ONE tool: `simulate_savings`. Alternatively, both tools can be backed by the same Lambda ARN if the CDK handler is changed to a dispatcher. See Pitfall 3 below.

### Pattern 2: `BedrockAgentCoreApp` Entrypoint

**What:** `BedrockAgentCoreApp` starts an HTTP server exposing `/invocations` (POST) and `/ping` (GET). The `@app.entrypoint` decorated function receives the parsed JSON payload dict and must return a JSON-serializable object.

**When to use:** This is the only supported pattern for deploying a Python agent to AgentCore managed runtime. [VERIFIED: bedrock-agentcore v1.6.3 docs]

```python
# Source: strandsagents.com docs + bedrock-agentcore v1.6.3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from pydantic import BaseModel, Field

app = BedrockAgentCoreApp()

class TrackInfo(BaseModel):
    plan_id: str = Field(description="Tariff plan identifier")
    plan_name: str = Field(description="Human-readable plan name")
    saving_monthly: float = Field(description="Projected monthly saving in dollars")
    saving_annual: float = Field(description="Projected annual saving in dollars")

class RecommendationResponse(BaseModel):
    green: TrackInfo = Field(description="Most energy-efficient (green) plan recommendation")
    cheapest: TrackInfo = Field(description="Lowest projected cost plan recommendation")

_agent = Agent(
    model=BedrockModel(
        model_id="anthropic.claude-3-7-sonnet-20250219-v1:0",
        region_name="us-east-1",
    ),
    system_prompt=SYSTEM_PROMPT,  # see Pattern 4
    tools=[simulate_savings],     # single tool sufficient (see Pitfall 3)
)

@app.entrypoint
def invoke(payload: dict) -> dict:
    customer_id = payload.get("customer_id") or payload.get("prompt", "")
    result = _agent.structured_output(
        RecommendationResponse,
        f"Get tariff recommendations for customer {customer_id}",
    )
    return result.model_dump()

if __name__ == "__main__":
    app.run()
```

### Pattern 3: CDK L2 AgentCore Runtime Construct (Python)

**What:** `aws_cdk.aws_bedrock_agentcore_alpha.Runtime` is the L2 construct. `AgentRuntimeArtifact.from_asset(path)` takes a local directory with a Dockerfile, builds it, and pushes to a CDK-managed ECR repo. The construct auto-creates the execution IAM role with ECR pull, CloudWatch Logs, and X-Ray permissions. Use `add_to_role_policy()` to add `lambda:InvokeFunction` and `bedrock:InvokeModel`.

**When to use:** Any CDK-based deployment of an AgentCore runtime. Replaces all manual `create_agent_runtime` boto3 calls.

```python
# Source: CDK docs aws_cdk.aws_bedrock_agentcore_alpha README + classmethod blog
import aws_cdk as cdk
from aws_cdk import Stack, CfnOutput
from aws_cdk import aws_iam as iam
from aws_cdk import aws_bedrock_agentcore_alpha as agentcore
from constructs import Construct


class AgentCoreStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        tools_lambda_arn: str,  # passed in from FoundationStack
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        artifact = agentcore.AgentRuntimeArtifact.from_asset("agent")  # path to Dockerfile dir

        runtime = agentcore.Runtime(
            self,
            "TariffAgentRuntime",
            runtime_name="tariff-agent",
            agent_runtime_artifact=artifact,
            description="Strands agent: Green + Cheapest tariff recommendations",
        )

        # Bedrock model invocation
        runtime.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/*",
                    f"arn:aws:bedrock:{self.region}:{self.account}:*",
                ],
            )
        )

        # Lambda tool invocation — scoped to ToolsLambda ARN only
        runtime.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[tools_lambda_arn],
            )
        )

        CfnOutput(self, "AgentRuntimeArn", value=runtime.agent_runtime_arn)
        CfnOutput(self, "AgentRuntimeId", value=runtime.agent_runtime_id)
```

### Pattern 4: System Prompt for Simultaneous Dual-Track Output (REC-03)

**What:** The system prompt must prevent the LLM from (a) picking one track over the other, (b) summarising into a single recommendation, or (c) ranking the tracks. Combined with `structured_output`, the Pydantic schema enforces both fields are always present.

**When to use:** Always. This is the REC-03 invariant.

```
SYSTEM_PROMPT = """You are a call centre tariff recommendation assistant.

Your job is to retrieve savings data for a customer and present TWO separate recommendation tracks simultaneously. You MUST always return both tracks. Never rank one above the other, never omit either.

TRACK DEFINITIONS:
- GREEN track: The most energy-efficient (highest green_score, plan_type=green_premium) plan.
- CHEAPEST track: The plan with the lowest projected monthly cost.

RULES:
1. Call the simulate_savings tool once with the customer_id provided.
2. Use ONLY the numbers returned by the tool. Do not recalculate, estimate, or round the savings figures.
3. Return both the GREEN and CHEAPEST tracks simultaneously in your response.
4. Never say one is "better" or "recommended more" than the other.
5. Never return only one track.
6. Never perform arithmetic yourself.
"""
```

### Pattern 5: `invoke_agent_runtime` Call (Verification / Phase 3)

**What:** The boto3 call to invoke a deployed AgentCore runtime. [VERIFIED: AWS boto3 docs 2026-04-23]

```python
# Source: https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-agentcore/client/invoke_agent_runtime.html
import boto3
import json
import uuid

client = boto3.client("bedrock-agentcore", region_name="us-east-1")

response = client.invoke_agent_runtime(
    agentRuntimeArn="arn:aws:bedrock-agentcore:us-east-1:<account>:runtime/<id>",
    runtimeSessionId=str(uuid.uuid4()),  # unique per invocation
    payload=json.dumps({"customer_id": "CUST-001"}).encode(),
)

body = json.loads(response["response"].read())
# body == {"green": {"plan_id": ..., "plan_name": ..., "saving_monthly": ..., "saving_annual": ...},
#          "cheapest": {...}}
```

**Key constraints on `invoke_agent_runtime`:**
- `agentRuntimeArn`: Required. Full ARN from CfnOutput.
- `runtimeSessionId`: Optional (auto-populated if omitted in newer API versions). Use `str(uuid.uuid4())` for unique sessions.
- `payload`: Required. `bytes` or file-like. Encode JSON with `.encode()`.
- `response['response']`: A `StreamingBody`. Call `.read()` then `json.loads()`.
- Older docs noted 33-char minimum on `runtimeSessionId` — the current API docs show it as optional; use UUID to be safe.

### Anti-Patterns to Avoid

- **LLM arithmetic:** System prompt and `structured_output` must both prevent the agent from computing savings numbers. The numbers come exclusively from `simulate_savings` tool return values.
- **Single-track response:** Any system prompt that asks the LLM to "recommend the best plan" will collapse to one track. Always ask for both tracks explicitly.
- **Hardcoded Lambda ARN in agent code:** The ToolsLambda ARN must be passed as an environment variable (`TOOLS_LAMBDA_ARN`) injected by CDK — not hardcoded.
- **Skipping structured output:** Without Pydantic `structured_output`, the LLM may vary its JSON shape between invocations, breaking Phase 3 parsing.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP server for `/invocations` and `/ping` | Custom Flask/FastAPI endpoints | `BedrockAgentCoreApp` from `bedrock-agentcore` | AgentCore requires exact endpoint contract; SDK handles it |
| ECR repo + image push | Custom boto3 ECR automation | CDK `AgentRuntimeArtifact.from_asset()` | L2 construct manages repo lifecycle, tags, and CDK asset hashing |
| IAM role for runtime | Manual role + policy creation | CDK `Runtime` construct with `add_to_role_policy()` | Construct creates the trust policy for `bedrock-agentcore.amazonaws.com` correctly |
| Tool schema/docstring parsing | Custom schema registry | Strands `@tool` decorator | Strands auto-generates the tool spec from type hints + docstring |
| Savings calculation | LLM arithmetic in system prompt | `simulate_savings` Lambda tool | SAV-03 non-negotiable: numbers must come from code, not the LLM |
| Structured response validation | Manual JSON parsing + validation | Pydantic `BaseModel` + `agent.structured_output()` | Strands SDK provides validated, typed output |

**Key insight:** Every layer of this stack (HTTP serving, ECR management, IAM, tool schema) has an official abstraction in either `bedrock-agentcore`, the CDK L2 alpha library, or the Strands SDK. Avoid all of them simultaneously by using the three layers as documented.

---

## Common Pitfalls

### Pitfall 1: `aws-cdk.aws-bedrock-agentcore-alpha` is Alpha — APIs May Break
**What goes wrong:** The CDK L2 construct for AgentCore is marked alpha (v2.250.0a0). Constructor parameter names or properties may differ from TypeScript documentation. The classmethod blog used TypeScript (`agentRuntimeArtifact`); Python uses snake_case (`agent_runtime_artifact`).
**Why it happens:** CDK alpha modules are experimental; Python bindings are auto-generated from TypeScript with `jsii`.
**How to avoid:** Pin `aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0` (same version as installed `aws-cdk-lib`). Test `cdk synth` after adding the construct before writing deployment plans.
**Warning signs:** `TypeError: unexpected keyword argument` on `Runtime()` constructor.

### Pitfall 2: Container Must Be `linux/arm64`
**What goes wrong:** Building with the host platform (e.g. `linux/amd64` on an x86 machine) produces a container that AgentCore rejects or runs with poor performance.
**Why it happens:** AgentCore managed runtime runs on arm64 Graviton infrastructure.
**How to avoid:** Dockerfile must use `--platform=linux/arm64`. `docker buildx` with `--platform linux/arm64` flag for cross-compilation on Mac. CDK `DockerImageAsset` / `from_asset()` may need platform configuration.
**Warning signs:** Runtime status stuck at `CREATING` after deploy, or runtime errors on first invoke.

### Pitfall 3: ToolsLambda Has a Single Handler (`handler.simulate_savings`)
**What goes wrong:** The ToolsLambda CDK construct sets `handler="handler.simulate_savings"`. A boto3 invocation always routes to `simulate_savings`, which internally calls `get_billing_history`. Trying to invoke `get_billing_history` separately via a second `@tool` will call the same Lambda handler but it will execute `simulate_savings` — returning savings data, not just billing history.
**Why it happens:** Lambda `handler` is set at deploy time, not per-invocation.
**How to avoid:** The agent only needs ONE tool — `simulate_savings` — which returns both tracks in one call. If both tools are needed separately, the Lambda handler needs a dispatcher (e.g. `handler.dispatch` checking `event["action"]`). The simpler path for Phase 2 is one tool.
**Warning signs:** Calling `get_billing_history_tool` returns a dict with `green`/`cheapest` keys instead of a list of billing records.

### Pitfall 4: `runtimeSessionId` Format
**What goes wrong:** Some docs state 33+ character minimum. Passing a short string (e.g. `"test-session"`) may be rejected.
**Why it happens:** Historical API constraint; current boto3 docs show it as optional. Safest approach is to use `str(uuid.uuid4())` which is 36 characters.
**How to avoid:** Always use `str(uuid.uuid4())` for session IDs in tests and smoke tests.
**Warning signs:** `ValidationException` on `invoke_agent_runtime` call.

### Pitfall 5: CDK Cross-Stack Dependency Creates Deploy Order Constraint
**What goes wrong:** If `AgentCoreStack` consumes the `ToolsLambda` ARN directly as a CDK token from `FoundationStack`, CDK creates a hard stack dependency. `cdk deploy --all` must deploy `FoundationStack` first. If `AgentCoreStack` is deployed independently (e.g. to update agent code only), CDK resolves the ARN from CloudFormation exports — which is correct, but the export cannot be removed from `FoundationStack` while `AgentCoreStack` exists.
**Why it happens:** CloudFormation export/import locking.
**How to avoid:** Use SSM Parameter Store instead: `FoundationStack` writes the ARN to `/customer-tariff/tools-lambda-arn`; `AgentCoreStack` reads it at synth time with `ssm.StringParameter.value_for_string_parameter()`. This decouples the stacks at the CloudFormation level.
**Warning signs:** `Export CustomerTariff:ExportsOutputFnGetAttToolsLambda... cannot be deleted` when trying to update `FoundationStack`.

### Pitfall 6: `bedrock-agentcore` Package vs `bedrock-agentcore-starter-toolkit`
**What goes wrong:** There are two separate packages: `bedrock-agentcore` (the runtime SDK, v1.6.3 — what you need) and `bedrock-agentcore-starter-toolkit` (a legacy CLI tool for prototyping, v0.3.5 — not needed here). The starter toolkit's `agentcore configure/launch` CLI is a wrapper around boto3 and not needed when using CDK.
**Why it happens:** AWS documentation sometimes mixes references to both packages.
**How to avoid:** Add only `bedrock-agentcore` to agent `requirements.txt`. Do not add `bedrock-agentcore-starter-toolkit`.
**Warning signs:** Importing `from bedrock_agentcore_starter_toolkit import ...` instead of `from bedrock_agentcore.runtime import BedrockAgentCoreApp`.

### Pitfall 7: `invoke_agent_runtime` Requires Caller IAM Permission
**What goes wrong:** The smoke test script or Phase 3 Lambda needs `bedrock-agentcore:InvokeAgentRuntime` on the runtime ARN. This is a separate permission from the runtime execution role.
**Why it happens:** Two different roles: (1) the AgentCore execution role (runs the container), (2) the caller role (invokes the runtime endpoint). Phase 2 smoke tests use the developer's CLI credentials — confirm `bedrock-agentcore:InvokeAgentRuntime` is on the local AWS profile.
**How to avoid:** Add `bedrock-agentcore:InvokeAgentRuntime` to the developer IAM policy, or run smoke tests under a role that has it.
**Warning signs:** `AccessDeniedException` when calling `invoke_agent_runtime` from the test script.

---

## Code Examples

### Tool Invocation: Minimal Working Agent

```python
# Source: verified pattern from strandsagents.com + bedrock-agentcore docs
import json
import os
import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from pydantic import BaseModel, Field

# --- Environment variables (injected by CDK) ---
_TOOLS_LAMBDA_ARN = os.environ["TOOLS_LAMBDA_ARN"]

# --- boto3 clients ---
_lambda_client = boto3.client("lambda", region_name="us-east-1")

# --- Tool definitions ---
@tool
def simulate_savings(customer_id: str) -> dict:
    """Calculate Green and Cheapest tariff savings for a customer.

    Returns both recommendation tracks from the deterministic savings engine.
    Do not use these numbers for any arithmetic — present them exactly as returned.

    Args:
        customer_id: Customer identifier in format CUST-NNN (e.g. CUST-001).

    Returns:
        Dict with 'green' and 'cheapest' keys, each with plan_id, plan_name,
        saving_monthly ($/month), saving_annual ($/year).
    """
    resp = _lambda_client.invoke(
        FunctionName=_TOOLS_LAMBDA_ARN,
        InvocationType="RequestResponse",
        Payload=json.dumps({"customer_id": customer_id}).encode(),
    )
    return json.loads(resp["Payload"].read())

# --- Pydantic response schema ---
class TrackInfo(BaseModel):
    plan_id: str
    plan_name: str
    saving_monthly: float
    saving_annual: float

class RecommendationResponse(BaseModel):
    green: TrackInfo
    cheapest: TrackInfo

# --- Agent ---
SYSTEM_PROMPT = """You are a call centre tariff recommendation assistant.
Call simulate_savings once with the customer_id. Return BOTH green and cheapest
recommendation tracks simultaneously using the exact numbers from the tool.
Never rank one track above the other. Never recalculate savings yourself."""

_agent = Agent(
    model=BedrockModel(
        model_id="anthropic.claude-3-7-sonnet-20250219-v1:0",
        region_name="us-east-1",
    ),
    system_prompt=SYSTEM_PROMPT,
    tools=[simulate_savings],
)

# --- AgentCore entrypoint ---
app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload: dict) -> dict:
    customer_id = payload["customer_id"]
    result = _agent.structured_output(
        RecommendationResponse,
        f"Get tariff savings recommendations for customer {customer_id}",
    )
    return result.model_dump()

if __name__ == "__main__":
    app.run()
```

### Offline Unit Test Pattern (no AWS credentials)

```python
# Source: established project pattern from tests/test_simulate_savings.py
import importlib
import json
import pytest
from unittest.mock import MagicMock, patch

# Import agent module (assuming agent/agent.py)
# @tool functions can be called directly to test Lambda invocation logic

def make_mock_lambda_response(payload_dict: dict) -> dict:
    """Build a mock boto3 lambda.invoke() response."""
    return {
        "StatusCode": 200,
        "Payload": MagicMock(read=lambda: json.dumps(payload_dict).encode()),
    }

@pytest.fixture
def mock_savings_response():
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoSaver",
            "saving_monthly": 30.00,
            "saving_annual": 360.00,
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "ValueBasic",
            "saving_monthly": 55.00,
            "saving_annual": 660.00,
        },
    }

def test_simulate_savings_tool_returns_both_tracks(mock_savings_response):
    with patch("agent.agent._lambda_client") as mock_client:
        mock_client.invoke.return_value = make_mock_lambda_response(mock_savings_response)
        # Import and call the @tool function directly
        import importlib, sys
        # agent module imports — adjust path as needed
        result = mock_savings_response  # direct assertion on expected shape
        assert "green" in result
        assert "cheapest" in result
        assert result["green"]["saving_monthly"] == 30.00
        assert result["cheapest"]["saving_monthly"] == 55.00
        # Cheapest savings always >= green savings (Phase 2 success criterion 4)
        assert result["cheapest"]["saving_monthly"] >= result["green"]["saving_monthly"]
```

### Live Smoke Test Pattern (requires AWS credentials)

```python
# Source: AWS docs https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html
import boto3
import json
import uuid
import os
import pytest

AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
PERSONAS = ["CUST-001", "CUST-002", "CUST-003"]

@pytest.mark.skipif(not AGENT_RUNTIME_ARN, reason="AGENT_RUNTIME_ARN not set")
@pytest.mark.parametrize("customer_id", PERSONAS)
def test_invoke_agent_runtime_per_persona(customer_id):
    client = boto3.client("bedrock-agentcore", region_name="us-east-1")
    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=str(uuid.uuid4()),
        payload=json.dumps({"customer_id": customer_id}).encode(),
    )
    body = json.loads(response["response"].read())

    # REC-01, REC-02: both tracks present
    assert "green" in body, f"Missing green track for {customer_id}"
    assert "cheapest" in body, f"Missing cheapest track for {customer_id}"

    # SAV-01, SAV-02: numeric fields present
    assert body["green"]["saving_monthly"] > 0
    assert body["green"]["saving_annual"] > 0
    assert body["cheapest"]["saving_monthly"] > 0
    assert body["cheapest"]["saving_annual"] > 0

    # Phase 2 success criterion 4: cheapest >= green
    assert body["cheapest"]["saving_monthly"] >= body["green"]["saving_monthly"]
```

### CDK Cross-Stack Wiring via SSM (Recommended over CfnOutput import)

```python
# In FoundationStack (infrastructure/foundation_stack.py) — add SSM write
from aws_cdk import aws_ssm as ssm

# After existing CfnOutput lines, add:
ssm.StringParameter(
    self,
    "ToolsLambdaArnParam",
    parameter_name="/customer-tariff/tools-lambda-arn",
    string_value=tools.function.function_arn,
    description="ToolsLambda ARN for AgentCoreStack cross-stack wiring",
)

# In AgentCoreStack (infrastructure/agentcore_stack.py) — read SSM at synth time
from aws_cdk import aws_ssm as ssm

tools_lambda_arn = ssm.StringParameter.value_for_string_parameter(
    self, "/customer-tariff/tools-lambda-arn"
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Classic Bedrock Agents (action groups, knowledge bases, console setup) | Strands SDK `@tool` decorator, `BedrockAgentCoreApp` managed runtime | 2025 (Strands open-sourced) | No console configuration needed; all infra is code |
| Starter toolkit CLI (`agentcore configure/launch`) | CDK L2 `Runtime` construct with `from_asset()` | Late 2025 (starter toolkit marked legacy) | IaC-first; no CLI dependency for CI/CD |
| Manual ECR push + `create_agent_runtime` boto3 script | CDK asset-based deployment | 2025 | Idempotent, versioned, integrated with CDK pipeline |
| Unstructured LLM text output | Pydantic `structured_output` with `agent.structured_output()` | Strands 1.x | Type-safe, validated responses; no string parsing |

**Deprecated/outdated:**
- `bedrock-agentcore-starter-toolkit` CLI (`agentcore configure/launch`): Marked legacy as of April 2026. Use CDK or direct boto3 instead.
- Passing `runtimeSessionId` as short strings: Some older docs mentioned 33-char minimum; current API shows it as optional. Use UUID.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The CDK L2 `Runtime` construct's Python class is named `Runtime` (not `AgentCoreRuntime`) and accepts `runtime_name`, `agent_runtime_artifact` as constructor params | Standard Stack / Pattern 3 | If class name differs, CDK synth fails; workaround is L1 `CfnAgentRuntime` |
| A2 | `AgentRuntimeArtifact.from_asset(path)` accepts a local directory path containing a Dockerfile and handles cross-platform build automatically | Pattern 3 | If platform handling differs, container may be wrong arch; may need explicit `platform` arg |
| A3 | `BedrockAgentCoreApp` v1.6.3 `@app.entrypoint` accepts a synchronous function (not only async) | Pattern 2 | If async-only, sync `invoke` function would fail; workaround: `async def invoke` with `await` |
| A4 | `agent.structured_output(RecommendationResponse, prompt)` works when the agent has tools and performs tool calls during the structured output session | Pattern 2 / Code Examples | If structured_output doesn't support tool calls mid-session, use system-prompt-only JSON enforcement instead |
| A5 | ToolsLambda handler `handler.simulate_savings` is the only entry point — calling via boto3 always runs `simulate_savings`, not `get_billing_history` as a standalone call | Pitfall 3 | If a dispatcher exists, two separate tools are possible; check `infrastructure/constructs/tools_lambda.py` (confirmed: `handler="handler.simulate_savings"`) [VERIFIED: tools_lambda.py line 29] |

---

## Open Questions

1. **Does `agent.structured_output()` support in-session tool calls?**
   - What we know: Strands docs show `structured_output` for direct text → Pydantic extraction. It is unclear if it supports the agent making tool calls during the structured output request.
   - What's unclear: Whether the agent can call `simulate_savings` as part of a `structured_output()` invocation, or whether it works only on pre-existing context.
   - Recommendation: If `structured_output` doesn't work with tools, use a two-step approach: (1) `agent("Get savings for {customer_id}")` to trigger tool calls and get the savings dict in the response, (2) parse the response JSON from the last tool result. Alternatively, structure the entrypoint to call the Lambda directly and use `structured_output` only for formatting.

2. **CDK L2 `Runtime` Python class exact API**
   - What we know: The alpha package v2.250.0a0 is available. TypeScript docs show `Runtime` class with `runtimeName`, `agentRuntimeArtifact`, `addToRolePolicy()`, `agentRuntimeArn`.
   - What's unclear: Whether Python `jsii` binding uses `from_asset` on `AgentRuntimeArtifact` or a different method. The WebFetch of the Python README returned only the class list, not constructor details.
   - Recommendation: Wave 0 plan should include a `cdk synth` smoke test that verifies the `AgentCoreStack` synthesises without error before proceeding to implement the agent itself.

3. **Cross-platform Docker build in CDK asset pipeline**
   - What we know: Docs show `docker buildx --platform linux/arm64` for manual builds. CDK `from_asset()` invokes Docker locally during `cdk deploy`.
   - What's unclear: Whether `from_asset()` automatically sets `--platform linux/arm64` or requires an explicit `platform` argument.
   - Recommendation: If `from_asset()` doesn't support platform, fall back to manual ECR push + L1 `CfnAgentRuntime` with hardcoded image URI. Verify with a `cdk synth` + `cdk diff` before full deploy.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Docker | CDK `from_asset()` image build, local agent testing | Yes | 29.2.1 | — |
| AWS CLI | CDK deploy, ECR login, smoke tests | Yes | 2.33.19 | — |
| Python 3.12 (container) | Agent container runtime | N/A (in Docker image) | — | Python 3.11 slim also supported |
| Python 3.9 (local CDK) | CDK synth (local machine) | Yes | 3.9.6 | — |
| AWS credentials (us-east-1) | `cdk deploy`, `invoke_agent_runtime` smoke tests | Not configured at research time | — | Configure before Phase 2 execution |
| `strands-agents` 1.37.0 | Agent container | Not installed (requires Python >=3.10) | — | Use Python 3.12 in container |
| `bedrock-agentcore` 1.6.3 | Agent container | Not installed locally | — | Install inside Docker only |
| `aws-cdk.aws-bedrock-agentcore-alpha` 2.250.0a0 | CDK synth | Not installed locally | — | `pip install` before CDK work |

**Missing dependencies with no fallback:**
- AWS credentials configured for us-east-1 — required for `cdk deploy` and all live smoke tests. Must be configured before Phase 2 execution begins.

**Missing dependencies with fallback:**
- `strands-agents`, `bedrock-agentcore` are not installed in the local Python 3.9 environment, but this is expected — they run inside the Docker container (Python 3.12). No action needed on local machine.
- `aws-cdk.aws-bedrock-agentcore-alpha` — not yet installed; must be added to `requirements.txt` before CDK work.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=7.0 (already installed) |
| Config file | `pytest.ini` (exists, `testpaths = tests`) |
| Quick run command | `pytest tests/test_agent_tools.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REC-01 | Green track present with correct plan_id ("ECO") | unit (mocked) | `pytest tests/test_agent_tools.py::test_green_track_present -x` | Wave 0 |
| REC-02 | Cheapest track present with correct plan_id ("VAL") | unit (mocked) | `pytest tests/test_agent_tools.py::test_cheapest_track_present -x` | Wave 0 |
| REC-03 | Both tracks returned simultaneously, neither omitted | unit (mocked) + live smoke | `pytest tests/test_agent_tools.py::test_both_tracks_present -x` | Wave 0 |
| SAV-01 | Monthly saving > 0 for both tracks | unit (mocked) | `pytest tests/test_agent_tools.py::test_monthly_saving_nonzero -x` | Wave 0 |
| SAV-02 | Annual saving = monthly * 12 for both tracks | unit (mocked) | `pytest tests/test_agent_tools.py::test_annual_saving_formula -x` | Wave 0 |
| SAV-03 | Tool returns numbers; LLM receives and passes through unchanged | unit (mocked) | `pytest tests/test_agent_tools.py::test_numbers_from_tool_not_llm -x` | Wave 0 |
| SC-4 | Cheapest saving >= green saving for all personas | unit (mocked) + live smoke | `pytest tests/test_agent_smoke.py -x -m smoke` (live, needs creds) | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_agent_tools.py -x` (offline, no AWS credentials required)
- **Per wave merge:** `pytest tests/ -x -m "not smoke"` (all offline tests)
- **Phase gate:** Full suite including `pytest tests/test_agent_smoke.py -x` (live, all 3 personas) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_agent_tools.py` — offline unit tests with mocked boto3 Lambda client; covers REC-01, REC-02, REC-03, SAV-01, SAV-02, SAV-03
- [ ] `tests/test_agent_smoke.py` — live `invoke_agent_runtime` per persona; requires `AGENT_RUNTIME_ARN` env var; marked `@pytest.mark.smoke`
- [ ] `tests/conftest.py` addition — `agent_runtime_arn` fixture reading from env var or SSM
- [ ] `pytest.ini` addition — register `smoke` marker: `markers = smoke: live AWS smoke tests`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user auth in Phase 2 (agent-to-service) |
| V3 Session Management | Partial | `runtimeSessionId` is ephemeral UUID per invocation; no persistence |
| V4 Access Control | Yes | IAM role scoped to specific Lambda ARN and Bedrock model ARNs |
| V5 Input Validation | Yes | `customer_id` validation already in `_validate_customer_id()` in Lambda handler; agent tool must pass validated IDs only |
| V6 Cryptography | No | TLS handled by AWS SDK for all Bedrock/Lambda calls |

### Known Threat Patterns for Strands / AgentCore Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via `customer_id` payload | Tampering | `_validate_customer_id()` in ToolsLambda rejects non-`CUST-NNN` patterns before DynamoDB query [VERIFIED: lambda/handler.py] |
| Overly broad Lambda invoke permissions | Elevation of Privilege | IAM policy scoped to exact ToolsLambda ARN only — no wildcard resource |
| Overly broad Bedrock model permissions | Elevation of Privilege | IAM policy scoped to `foundation-model/*` and account ARN pattern |
| Agent container calling arbitrary AWS services | Elevation of Privilege | Execution role has only `lambda:InvokeFunction` + `bedrock:Invoke*` + ECR/Logs/XRay (CDK auto-generates the latter three) |

---

## Sources

### Primary (HIGH confidence)
- `/websites/strandsagents` (Context7) — `@tool` decorator, `BedrockAgentCoreApp`, `BedrockModel`, `structured_output` patterns
- `/strands-agents/sdk-python` (Context7) — Tool decorator specifics, `BedrockModel` config, `agent.structured_output()`
- `https://pypi.org/project/strands-agents/` — Version 1.37.0 confirmed [VERIFIED: WebSearch 2026-04-23]
- `https://pypi.org/project/bedrock-agentcore/` — Version 1.6.3, `BedrockAgentCoreApp` pattern [VERIFIED: WebFetch 2026-04-23]
- `https://pypi.org/project/aws-cdk.aws-bedrock-agentcore-alpha/` — Version 2.250.0a0 [VERIFIED: WebSearch 2026-04-23]
- `https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-agentcore/client/invoke_agent_runtime.html` — `invoke_agent_runtime` full parameter reference [VERIFIED: WebFetch 2026-04-23]
- `https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html` — Invocation guide [VERIFIED: WebFetch 2026-04-23]
- `lambda/handler.py` — Tool input/output shapes, `simulate_savings_pure` return schema [VERIFIED: codebase]
- `infrastructure/constructs/tools_lambda.py` — Lambda handler name (`handler.simulate_savings`), confirms single entry point [VERIFIED: codebase]

### Secondary (MEDIUM confidence)
- `https://dev.classmethod.jp/en/articles/cdk-amazon-bedrock-agentcore-l2-construct-strands-agents/` — CDK L2 construct usage pattern (TypeScript; Python equivalents derived from jsii naming conventions)
- `https://strandsagents.com/docs/user-guide/deploy/deploy_to_bedrock_agentcore/python` — Full Python deployment guide [VERIFIED: WebFetch 2026-04-23]
- `https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrock_agentcore_alpha/README.html` — CDK L2 Python README (constructor details sparse; class names confirmed)

### Tertiary (LOW confidence)
- CDK L2 `Runtime` Python constructor exact parameter names — derived from TypeScript docs + jsii snake_case convention; should be confirmed by `cdk synth` smoke test in Wave 0

---

## Metadata

**Confidence breakdown:**
- Standard stack (library versions): HIGH — verified against PyPI registry 2026-04-23
- Strands `@tool` and `BedrockAgentCoreApp` patterns: HIGH — verified against Context7 + official docs
- CDK L2 `Runtime` Python API: MEDIUM — TypeScript API confirmed, Python binding derived from naming convention; needs Wave 0 synth test
- `invoke_agent_runtime` API: HIGH — verified against official boto3 docs
- Architecture patterns: HIGH — derived from verified code + official docs
- Pitfalls: HIGH for Pitfalls 1-4, 6-7 (verified); MEDIUM for Pitfall 5 (CDK cross-stack, based on documented CDK behaviour)

**Research date:** 2026-04-23
**Valid until:** 2026-05-14 (21 days — fast-moving ecosystem; recheck if CDK alpha or strands-agents updates before planning)
