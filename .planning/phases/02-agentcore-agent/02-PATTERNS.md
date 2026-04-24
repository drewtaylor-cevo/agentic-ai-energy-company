# Phase 2: AgentCore Agent - Pattern Map

**Mapped:** 2026-04-23
**Files analyzed:** 8 (new files for Phase 2)
**Analogs found:** 3 / 8 — Phase 1 constructs provide partial analogs for CDK patterns

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `agent/agent.py` | service / agent entrypoint | request-response | Greenfield — no analog (new pattern: Strands + BedrockAgentCoreApp) | none |
| `agent/requirements.txt` | config / container deps | — | `requirements.txt` (project root) | low (different deps, same format) |
| `agent/Dockerfile` | config / container build | — | Greenfield — no analog | none |
| `infrastructure/agentcore_stack.py` | infrastructure / CDK stack | request-response | `infrastructure/foundation_stack.py` | medium (same Stack pattern, different resources) |
| `infrastructure/constructs/agent_runtime.py` | infrastructure / CDK construct | request-response | `infrastructure/constructs/tools_lambda.py` | medium (same Construct pattern, different L2 construct) |
| `tests/test_agent_tools.py` | test | transform | `tests/test_simulate_savings.py` | medium (same pytest pattern, mocked boto3 instead of pure function) |
| `tests/test_agent_smoke.py` | test | integration | `tests/test_seeder_smoke.py` | high (same skip-guard pattern, live AWS calls) |
| `tests/test_agentcore_synth.py` | test | infrastructure | `tests/test_cdk_synth.py` | high (same Template.from_stack pattern) |

---

## Pattern Assignments

Patterns sourced from `02-RESEARCH.md` (verified against Strands SDK docs, bedrock-agentcore docs, and CDK L2 alpha docs). Codebase analogs from Phase 1 where applicable.

---

### `agent/agent.py` (service, agent entrypoint)

**Analog:** Greenfield — no analog
**Source:** RESEARCH.md §Pattern 1 (@tool decorator), §Pattern 2 (BedrockAgentCoreApp entrypoint), §Pattern 4 (system prompt), §Code Examples (minimal working agent)

**Imports pattern:**
```python
import json
import os
import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from pydantic import BaseModel, Field
```

**Core pattern — environment + boto3 client (module-level):**
```python
_TOOLS_LAMBDA_ARN = os.environ["TOOLS_LAMBDA_ARN"]
_lambda_client = boto3.client("lambda", region_name="us-east-1")
```

**Core pattern — @tool wrapper calling Phase 1 Lambda:**
```python
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
```

**Core pattern — Pydantic response schema:**
```python
class TrackInfo(BaseModel):
    plan_id: str = Field(description="Tariff plan identifier")
    plan_name: str = Field(description="Human-readable plan name")
    saving_monthly: float = Field(description="Projected monthly saving in dollars")
    saving_annual: float = Field(description="Projected annual saving in dollars")

class RecommendationResponse(BaseModel):
    green: TrackInfo = Field(description="Most energy-efficient (green) plan recommendation")
    cheapest: TrackInfo = Field(description="Lowest projected cost plan recommendation")
```

**Core pattern — Agent + BedrockAgentCoreApp entrypoint:**
```python
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

**Critical rules:**
- Only ONE tool (`simulate_savings`) — ToolsLambda handler is `handler.simulate_savings`, so all invocations route there (Pitfall 3)
- `TOOLS_LAMBDA_ARN` from environment variable — never hardcoded (Anti-Pattern from RESEARCH.md)
- System prompt must enforce REC-03: both tracks, never ranked, never omit either
- `structured_output` with Pydantic enforces response shape — prevents LLM from varying JSON structure
- If `structured_output` doesn't support in-session tool calls (Open Question 1), fall back to: (1) `agent(prompt)` to trigger tool calls, (2) parse tool result directly from the response

**Open question fallback pattern (if structured_output + tools doesn't work):**
```python
@app.entrypoint
def invoke(payload: dict) -> dict:
    customer_id = payload["customer_id"]
    response = _agent(
        f"Get tariff savings recommendations for customer {customer_id}"
    )
    # Extract the tool result directly — simulate_savings returns the exact shape we need
    # Parse from agent response or from the last tool call result
    # Fallback: call Lambda directly and skip agent orchestration for structured data
    ...
```

---

### `agent/requirements.txt` (config, container dependencies)

**Analog:** `requirements.txt` (project root) — low match (different deps)
**Source:** RESEARCH.md §Standard Stack

**Core pattern:**
```
strands-agents==1.37.0
bedrock-agentcore==1.6.3
boto3>=1.42.0
```

**Rules:**
- Pin `strands-agents` and `bedrock-agentcore` to exact versions — alpha ecosystem, breaking changes likely
- `boto3` uses range pin (already a project dependency)
- Do NOT include `bedrock-agentcore-starter-toolkit` (Pitfall 6)
- Do NOT include `aws-cdk-lib` or CDK deps — this is the container, not the CDK project

---

### `agent/Dockerfile` (config, container build)

**Analog:** Greenfield — no analog
**Source:** RESEARCH.md §Pattern 2 (BedrockAgentCoreApp), §Pitfall 2 (linux/arm64)

**Core pattern:**
```dockerfile
FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py .

EXPOSE 8080

CMD ["python", "agent.py"]
```

**Critical rules:**
- `--platform=linux/arm64` is mandatory — AgentCore runs on Graviton (Pitfall 2)
- Port 8080 — `BedrockAgentCoreApp` listens on 8080 by default
- `python:3.12-slim` — matches Lambda runtime version; slim reduces image size
- `CMD ["python", "agent.py"]` — `app.run()` in agent.py starts the HTTP server

---

### `infrastructure/agentcore_stack.py` (CDK stack)

**Analog:** `infrastructure/foundation_stack.py` — medium match (same Stack pattern)
**Source:** RESEARCH.md §Pattern 3 (CDK L2 Runtime construct), §Pattern 5 (cross-stack wiring via SSM)

**Imports pattern:**
```python
import aws_cdk as cdk
from aws_cdk import Stack, CfnOutput
from aws_cdk import aws_iam as iam
from aws_cdk import aws_ssm as ssm
from constructs import Construct
from infrastructure.constructs.agent_runtime import AgentRuntimeConstruct
```

**Core pattern — stack reads ToolsLambda ARN from SSM:**
```python
class AgentCoreStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        tools_lambda_arn = ssm.StringParameter.value_for_string_parameter(
            self, "/customer-tariff/tools-lambda-arn"
        )

        runtime = AgentRuntimeConstruct(
            self, "AgentRuntime",
            tools_lambda_arn=tools_lambda_arn,
        )

        CfnOutput(self, "AgentRuntimeArn", value=runtime.agent_runtime_arn)
        CfnOutput(self, "AgentRuntimeId", value=runtime.agent_runtime_id)
```

**Rules:**
- Stack only wires constructs — no resource definitions inline (same pattern as FoundationStack)
- SSM parameter read decouples from FoundationStack at CloudFormation level (Pitfall 5)
- CfnOutputs for runtime ARN and ID — needed by smoke tests and Phase 3

---

### `infrastructure/constructs/agent_runtime.py` (CDK construct)

**Analog:** `infrastructure/constructs/tools_lambda.py` — medium match (same Construct pattern, different L2)
**Source:** RESEARCH.md §Pattern 3 (CDK L2 Runtime construct)

**Imports pattern:**
```python
from aws_cdk import CfnOutput
from aws_cdk import aws_iam as iam
from aws_cdk import aws_bedrock_agentcore_alpha as agentcore
from constructs import Construct
```

**Core pattern — Runtime construct with IAM:**
```python
class AgentRuntimeConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        tools_lambda_arn: str,
    ) -> None:
        super().__init__(scope, construct_id)

        artifact = agentcore.AgentRuntimeArtifact.from_asset("agent")

        self._runtime = agentcore.Runtime(
            self,
            "TariffAgentRuntime",
            runtime_name="tariff-agent",
            agent_runtime_artifact=artifact,
            description="Strands agent: Green + Cheapest tariff recommendations",
        )

        # Bedrock model invocation
        self._runtime.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    f"arn:aws:bedrock:{cdk.Stack.of(self).region}::foundation-model/*",
                    f"arn:aws:bedrock:{cdk.Stack.of(self).region}:{cdk.Stack.of(self).account}:*",
                ],
            )
        )

        # Lambda tool invocation — scoped to ToolsLambda ARN only
        self._runtime.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[tools_lambda_arn],
            )
        )

    @property
    def agent_runtime_arn(self) -> str:
        return self._runtime.agent_runtime_arn

    @property
    def agent_runtime_id(self) -> str:
        return self._runtime.agent_runtime_id
```

**Critical rules:**
- `from_asset("agent")` points to the `agent/` directory containing the Dockerfile
- IAM: `bedrock:InvokeModel` + `bedrock:InvokeModelWithResponseStream` for Claude model access
- IAM: `lambda:InvokeFunction` scoped to exact ToolsLambda ARN — no wildcards
- CDK L2 auto-creates ECR repo, trust policy for `bedrock-agentcore.amazonaws.com`, CloudWatch Logs, X-Ray permissions
- Expose `agent_runtime_arn` and `agent_runtime_id` as properties for stack-level CfnOutputs

**Note (Pitfall 1):** CDK L2 is alpha — if constructor params differ from TypeScript docs, fall back to L1 `CfnAgentRuntime`. Verify with `cdk synth` before proceeding.

---

### `infrastructure/foundation_stack.py` (modification — add SSM parameter)

**Analog:** Self (existing file)
**Source:** RESEARCH.md §CDK Cross-Stack Wiring via SSM

**Addition pattern — after existing CfnOutput lines:**
```python
from aws_cdk import aws_ssm as ssm

# In __init__, after existing CfnOutput lines:
ssm.StringParameter(
    self,
    "ToolsLambdaArnParam",
    parameter_name="/customer-tariff/tools-lambda-arn",
    string_value=tools.function.function_arn,
    description="ToolsLambda ARN for AgentCoreStack cross-stack wiring",
)
```

**Rules:**
- SSM parameter name `/customer-tariff/tools-lambda-arn` is the contract between FoundationStack and AgentCoreStack
- Must be deployed (FoundationStack update) before AgentCoreStack can synth

---

### `tests/test_agent_tools.py` (test, unit with mocked boto3)

**Analog:** `tests/test_simulate_savings.py` — medium match (same pytest pattern)
**Source:** RESEARCH.md §Offline Unit Test Pattern

**Core pattern — mock Lambda invoke, test tool return shape:**
```python
import json
import pytest
from unittest.mock import MagicMock, patch

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
            "plan_name": "EcoFlex 100",
            "saving_monthly": 30.00,
            "saving_annual": 360.00,
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 55.00,
            "saving_annual": 660.00,
        },
    }
```

**Test patterns:**
```python
def test_both_tracks_present(mock_savings_response):
    # Verify tool returns both green and cheapest keys
    assert "green" in mock_savings_response
    assert "cheapest" in mock_savings_response

def test_green_track_present(mock_savings_response):
    assert mock_savings_response["green"]["plan_id"] == "ECO"

def test_cheapest_track_present(mock_savings_response):
    assert mock_savings_response["cheapest"]["plan_id"] == "VAL"

def test_monthly_saving_nonzero(mock_savings_response):
    assert mock_savings_response["green"]["saving_monthly"] > 0
    assert mock_savings_response["cheapest"]["saving_monthly"] > 0

def test_annual_saving_formula(mock_savings_response):
    for track in ("green", "cheapest"):
        expected_annual = round(mock_savings_response[track]["saving_monthly"] * 12, 2)
        assert abs(mock_savings_response[track]["saving_annual"] - expected_annual) < 0.01

def test_cheapest_gte_green(mock_savings_response):
    assert mock_savings_response["cheapest"]["saving_monthly"] >= mock_savings_response["green"]["saving_monthly"]
```

---

### `tests/test_agent_smoke.py` (test, integration / live AWS)

**Analog:** `tests/test_seeder_smoke.py` — high match (same skip-guard + live AWS pattern)
**Source:** RESEARCH.md §Live Smoke Test Pattern

**Core pattern — skip guard + parametrized personas:**
```python
import boto3
import json
import uuid
import os
import pytest

AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
PERSONAS = ["CUST-001", "CUST-002", "CUST-003"]

pytestmark = pytest.mark.skipif(
    not AGENT_RUNTIME_ARN,
    reason="AGENT_RUNTIME_ARN not set — skip live smoke tests",
)

@pytest.mark.smoke
@pytest.mark.parametrize("customer_id", PERSONAS)
def test_invoke_agent_runtime_per_persona(customer_id):
    client = boto3.client("bedrock-agentcore", region_name="us-east-1")
    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=str(uuid.uuid4()),
        payload=json.dumps({"customer_id": customer_id}).encode(),
    )
    body = json.loads(response["response"].read())

    assert "green" in body
    assert "cheapest" in body
    assert body["green"]["saving_monthly"] > 0
    assert body["cheapest"]["saving_monthly"] > 0
    assert body["cheapest"]["saving_monthly"] >= body["green"]["saving_monthly"]
```

**Rules:**
- `@pytest.mark.smoke` marker — registered in pytest.ini
- `AGENT_RUNTIME_ARN` from environment — skip if not set
- `runtimeSessionId` uses `uuid.uuid4()` (36 chars, avoids Pitfall 4)
- `response["response"].read()` — StreamingBody pattern from boto3

---

### `tests/test_agentcore_synth.py` (test, CDK synth)

**Analog:** `tests/test_cdk_synth.py` — high match (same Template.from_stack pattern)
**Source:** Phase 1 established pattern

**Core pattern:**
```python
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template
from infrastructure.agentcore_stack import AgentCoreStack

@pytest.fixture(scope="module")
def synth_template():
    app = cdk.App()
    stack = AgentCoreStack(
        app, "TestAgentCoreStack",
        env=cdk.Environment(region="us-east-1", account="123456789012"),
    )
    return Template.from_stack(stack)

def test_has_agentcore_runtime(synth_template):
    # Verify the AgentCore Runtime resource exists in the template
    ...

def test_runtime_iam_has_lambda_invoke(synth_template):
    # Verify IAM policy includes lambda:InvokeFunction
    ...

def test_runtime_iam_has_bedrock_invoke(synth_template):
    # Verify IAM policy includes bedrock:InvokeModel
    ...
```

---

## Shared Patterns

### Environment Variable Pattern
**Apply to:** `agent/agent.py`, any future agent code
**Source:** Phase 1 established pattern (RESEARCH.md §Anti-Patterns)

Always read config from environment variables at module level:
```python
_TOOLS_LAMBDA_ARN = os.environ["TOOLS_LAMBDA_ARN"]  # raises KeyError immediately if missing
```

### IAM Least Privilege
**Apply to:** `agent_runtime.py`
**Source:** RESEARCH.md §Pattern 3, Phase 1 established pattern

- `lambda:InvokeFunction` scoped to exact ToolsLambda ARN
- `bedrock:InvokeModel` scoped to foundation-model ARN pattern
- No `*` actions anywhere

### Skip-Guard Pattern for Live Tests
**Apply to:** `test_agent_smoke.py`
**Source:** Phase 1 `test_seeder_smoke.py` established pattern

```python
pytestmark = pytest.mark.skipif(
    not os.environ.get("REQUIRED_ENV_VAR"),
    reason="...",
)
```

### CDK Stack Wiring Pattern
**Apply to:** `agentcore_stack.py`
**Source:** Phase 1 `foundation_stack.py` established pattern

Stack only wires constructs — no resource definitions inline. All resource logic in construct classes.

---

## Metadata

**Analog search scope:** Entire repository (all non-planning, non-git files)
**Files scanned:** 17 source files from Phase 1
**Pattern extraction date:** 2026-04-23
**Pattern sources:** `02-RESEARCH.md` (primary), Phase 1 codebase (analogs)
