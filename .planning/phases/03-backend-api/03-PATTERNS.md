# Phase 3: Backend API - Pattern Map

**Mapped:** 2026-04-24
**Files analyzed:** 10 (new/modified)
**Analogs found:** 10 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `api_lambda/handler.py` | handler | request-response | `lambda/handler.py` | role-match (same validation, different flow) |
| `infrastructure/backend_api_stack.py` | stack | request-response | `infrastructure/agentcore_stack.py` | exact |
| `infrastructure/constructs/backend_api.py` | construct | request-response | `infrastructure/constructs/tools_lambda.py` | role-match (Lambda construct + IAM) |
| `infrastructure/agentcore_stack.py` (modify) | stack | CRUD | `infrastructure/foundation_stack.py` | exact (SSM write pattern) |
| `app.py` (modify) | config | — | `app.py` itself | exact (add third stack entry) |
| `tests/test_backend_api_unit.py` | test | request-response | `tests/test_agent_tools.py` | role-match (offline unit, mock boto3) |
| `tests/test_backend_api_synth.py` | test | — | `tests/test_agentcore_synth.py` | exact |
| `tests/test_backend_api_smoke.py` | test | request-response | `tests/test_agent_smoke.py` | exact |
| `tests/conftest.py` (modify) | config | — | `tests/conftest.py` itself | exact (add Phase 3 fixtures) |
| `requirements.txt` (no change) | config | — | — | no-op; all deps already present |

---

## Pattern Assignments

### `api_lambda/handler.py` (handler, request-response)

**Analog:** `lambda/handler.py`

**Imports pattern** (`lambda/handler.py` lines 1-14 — take only what's needed):
```python
import json
import logging
import os
import re
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError
```
Delta: Phase 1 handler imports `typing` and loads tariff JSON at module level — omit both. Add `logging`, `uuid`, `boto3`/`botocore` instead.

**Validation pattern** (`lambda/handler.py` lines 39-52):
```python
_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")

def _validate_customer_id(customer_id: Any) -> str:
    if not isinstance(customer_id, str):
        raise ValueError(f"customer_id must be a string, got {type(customer_id).__name__}")
    if not _CUSTOMER_ID_PATTERN.match(customer_id):
        raise ValueError(f"customer_id must match CUST-<digits>; got {customer_id!r}")
    return customer_id
```
Delta: The API Lambda uses the same `^CUST-\d{3,6}$` regex (D-13), but raises no exception — instead returns an HTTP `_error(400, ...)` dict directly. No `isinstance` check needed (path params are always strings). Inline the regex check rather than calling a helper.

**Module-level client init** (no analog in Phase 1 — sourced from RESEARCH.md Q2):
```python
logger = logging.getLogger(__name__)

_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")
_AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Module-level client reused across warm invocations.
# Config(read_timeout=25): fires ReadTimeoutError at 25s, giving Lambda
# 5s buffer before the 30s execution limit kills the process (D-03).
_agentcore_client = boto3.client(
    "bedrock-agentcore",
    region_name=_REGION,
    config=Config(read_timeout=25, connect_timeout=5),
)
```
Anti-pattern to avoid: NEVER set `runtimeSessionId` at module level. It MUST be `str(uuid.uuid4())` inside `handler()` on every call (D-11, Pitfall 2).

**Error helper** (no analog — new pattern for this phase):
```python
def _error(status_code: int, message: str) -> dict:
    """Consistent error response body (D-12)."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }
```

**Core handler pattern** (no analog in Phase 1 — API Gateway HTTP API v2 payload format):
```python
def handler(event: dict, context) -> dict:
    path_params = event.get("pathParameters") or {}
    customer_id = path_params.get("customer_id", "")

    if not _CUSTOMER_ID_PATTERN.match(customer_id):
        return _error(400, "Invalid customer ID format. Use CUST-NNN (3-6 digits).")

    session_id = str(uuid.uuid4())  # MUST be inside handler(), never module-level
    logger.info("Invoking agent for %s session=%s", customer_id, session_id)

    try:
        response = _agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=_AGENT_RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=json.dumps({"customer_id": customer_id}).encode(),
        )
        body = json.loads(response["response"].read())  # StreamingBody.read() -> bytes
    except ReadTimeoutError:
        logger.warning("Agent timeout for %s", customer_id)
        return _error(504, "Recommendation service timed out. Please try again.")
    except ClientError as exc:
        logger.error("AgentCore ClientError: %s", exc)
        return _error(502, "Recommendation service error. Please try again.")
    except Exception as exc:
        logger.error("Unexpected error: %s", exc, exc_info=True)
        return _error(500, "Internal server error.")

    # Detect customer-not-found: absent tracks, not HTTP error code (Pitfall 5)
    if "green" not in body or "cheapest" not in body:
        logger.info("Customer not found response for %s: %s", customer_id, body)
        return _error(404, f"Customer {customer_id} not found.")

    # D-02: pass-through verbatim — no envelope
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
```
Delta from Phase 1: Phase 1 handler has no try/except (exceptions propagate to Lambda runtime). Phase 3 handler catches all exceptions and maps them to HTTP responses.

---

### `infrastructure/backend_api_stack.py` (stack, request-response)

**Analog:** `infrastructure/agentcore_stack.py` (lines 1-29)

**Full structure to mirror** (`infrastructure/agentcore_stack.py` lines 1-29):
```python
"""Phase 2 CDK stack — AgentCore Runtime for the Strands agent.

Reads ToolsLambda ARN from SSM (written by FoundationStack) to avoid
hard CloudFormation export dependencies between stacks (Pitfall 5).
"""
from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from infrastructure.constructs.agent_runtime import AgentRuntimeConstruct


class AgentCoreStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        tools_lambda_arn = ssm.StringParameter.value_for_string_parameter(
            self, "/customer-tariff/tools-lambda-arn"
        )

        runtime = AgentRuntimeConstruct(
            self,
            "AgentRuntime",
            tools_lambda_arn=tools_lambda_arn,
        )

        CfnOutput(self, "AgentRuntimeArn", value=runtime.agent_runtime_arn)
        CfnOutput(self, "AgentRuntimeId", value=runtime.agent_runtime_id)
```

Delta for `backend_api_stack.py`:
- Docstring: "Phase 3: Backend API — Lambda + HTTP API v2"
- Import `BackendApiConstruct` from `infrastructure.constructs.backend_api`
- SSM read: `"/customer-tariff/agent-runtime-arn"` (not tools-lambda-arn)
- Pass `agent_runtime_arn` kwarg to `BackendApiConstruct`
- Single `CfnOutput`: `"ApiEndpoint"` → `backend.api_endpoint`
- Class name: `BackendApiStack`

Anti-pattern: Do NOT use `Fn.import_value()` to get the runtime ARN from AgentCoreStack. SSM only (D-07, Pitfall 3).

---

### `infrastructure/constructs/backend_api.py` (construct, request-response)

**Primary analog:** `infrastructure/constructs/tools_lambda.py` (lines 1-36) — Lambda Function wiring pattern.
**Secondary analog:** `infrastructure/constructs/agent_runtime.py` (lines 1-83) — IAM scoping pattern.

**Constructor signature pattern** (`infrastructure/constructs/tools_lambda.py` lines 14-36):
```python
class ToolsLambdaConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        table: dynamodb.Table,
    ) -> None:
        super().__init__(scope, construct_id)

        self.function = lambda_.Function(
            self,
            "TariffTools",
            function_name="tariff-tools",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.simulate_savings",
            code=lambda_.Code.from_asset("lambda"),
            environment={"TABLE_NAME": table.table_name},
            timeout=Duration.seconds(10),
            memory_size=256,
        )
        table.grant_read_data(self.function)
```

**IAM scoping pattern** (`infrastructure/constructs/agent_runtime.py` lines 67-74):
```python
self._runtime.add_to_role_policy(
    iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        actions=["lambda:InvokeFunction"],
        resources=[tools_lambda_arn],
    )
)
```

**Full construct to build** — combine the above two patterns plus new HTTP API imports:
```python
"""BackendApiConstruct — API Lambda + HTTP API v2 with CORS and route."""
import aws_cdk as cdk
from aws_cdk import Duration
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integ
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class BackendApiConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        agent_runtime_arn: str,
    ) -> None:
        super().__init__(scope, construct_id)

        fn = lambda_.Function(
            self,
            "TariffApiLambda",
            function_name="tariff-api",
            runtime=lambda_.Runtime.PYTHON_3_12,   # Match Phase 1 default
            handler="handler.handler",              # api_lambda/handler.py :: def handler
            code=lambda_.Code.from_asset("api_lambda"),
            timeout=Duration.seconds(30),           # D-03: 30s Lambda timeout
            memory_size=256,                        # Match Phase 1 default
            environment={
                "AGENT_RUNTIME_ARN": agent_runtime_arn,
                "AWS_REGION": cdk.Stack.of(self).region,
            },
        )

        # IAM: scoped to this runtime ARN only (Q6 from RESEARCH.md)
        fn.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[agent_runtime_arn],
            )
        )

        api = apigwv2.HttpApi(
            self,
            "TariffApi",
            api_name="customer-tariff-api",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[
                    apigwv2.CorsHttpMethod.GET,
                    apigwv2.CorsHttpMethod.OPTIONS,
                ],
                allow_headers=["Content-Type"],
            ),
        )

        api.add_routes(
            path="/recommendations/{customer_id}",
            methods=[apigwv2.HttpMethod.GET],
            integration=integ.HttpLambdaIntegration("RecoIntegration", fn),
        )

        self._api_endpoint = api.url

    @property
    def api_endpoint(self) -> str:
        return self._api_endpoint
```
Delta from tools_lambda construct: adds `aws_apigatewayv2` + `integ` imports, adds `add_to_role_policy` with `bedrock-agentcore:InvokeAgentRuntime`, adds `HttpApi` + `add_routes`, exposes `api_endpoint` property. No `grant_*` helper exists for agentcore — must use raw `PolicyStatement`.

---

### `infrastructure/agentcore_stack.py` (modify — add SSM write)

**Analog:** `infrastructure/foundation_stack.py` lines 29-37 — the canonical SSM write pattern in this codebase.

**Exact pattern to copy** (`infrastructure/foundation_stack.py` lines 29-37):
```python
# Cross-stack wiring: write ToolsLambda ARN to SSM so AgentCoreStack
# can read it without a hard CloudFormation export dependency (Pitfall 5).
ssm.StringParameter(
    self,
    "ToolsLambdaArnParam",
    parameter_name="/customer-tariff/tools-lambda-arn",
    string_value=tools.function.function_arn,
    description="ToolsLambda ARN for AgentCoreStack cross-stack wiring",
)
```

**Minimal diff for `agentcore_stack.py`** — append after the two existing `CfnOutput` lines (currently lines 28-29):
```python
# Cross-stack wiring: write AgentRuntime ARN to SSM so BackendApiStack
# can read it without a hard CloudFormation export dependency (Pitfall 5).
ssm.StringParameter(
    self,
    "AgentRuntimeArnParam",
    parameter_name="/customer-tariff/agent-runtime-arn",
    string_value=runtime.agent_runtime_arn,
    description="AgentCore runtime ARN for BackendApiStack cross-stack wiring",
)
```
Note: `ssm` is already imported at line 7 of `agentcore_stack.py` — no new import needed.

---

### `app.py` (modify — register BackendApiStack)

**Analog:** `app.py` lines 22-27 — the AgentCoreStack registration block.

**Pattern to mirror** (`app.py` lines 22-27):
```python
AgentCoreStack(
    app,
    "CustomerTariffAgent",
    env=cdk.Environment(region="us-east-1"),
    description="Phase 2: AgentCore Agent Runtime",
)
```

**Addition to append before `app.synth()`:**
```python
from infrastructure.backend_api_stack import BackendApiStack

BackendApiStack(
    app,
    "CustomerTariffApi",
    env=cdk.Environment(region="us-east-1"),
    description="Phase 3: Backend API",
)
```
Delta: Add the import at the top of `app.py` alongside the other stack imports (lines 10-11), then add the instantiation block before `app.synth()`.

---

### `tests/test_backend_api_unit.py` (test, request-response)

**Analog:** `tests/test_agent_tools.py` (offline unit tests that mock boto3 calls).

**Mock response helper pattern** (sourced from RESEARCH.md Q11 — no direct analog for `bedrock-agentcore` mocking since moto does not support it):
```python
import io
import json
from unittest.mock import MagicMock, patch

def _make_agent_response(body: dict) -> dict:
    """Construct a mock invoke_agent_runtime response (StreamingBody via BytesIO)."""
    return {
        "response": io.BytesIO(json.dumps(body).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }
```
Key detail: `response["response"]` must be a file-like object (`io.BytesIO`), not a raw `bytes` or `str`. The handler calls `.read()` on it. This is the correct mock for `StreamingBody`.

**Test structure pattern** (`tests/test_agentcore_synth.py` lines 12-23 — import guard for optional deps):
```python
try:
    from infrastructure.agentcore_stack import AgentCoreStack
    _CAN_IMPORT = True
    _IMPORT_ERROR = ""
except ImportError as e:
    _CAN_IMPORT = False
    _IMPORT_ERROR = str(e)

pytestmark = pytest.mark.skipif(
    not _CAN_IMPORT,
    reason="AgentCoreStack import failed: {}".format(_IMPORT_ERROR),
)
```
Apply the same try/import guard for `api_lambda.handler` — the module will not exist until Wave 0 creates it, and offline tests should skip gracefully in the interim.

**Test cases required** (mapping from RESEARCH.md Validation Architecture):

| Test name | What to assert |
|-----------|----------------|
| `test_valid_customer_success` | `patch("api_lambda.handler._agentcore_client", mock_client)` → status 200, body has `green`/`cheapest` |
| `test_invalid_customer_id_formats` | `parametrize` with `["NOTVALID", "cust-001", "CUST-1", "CUST-1234567", ""]` → status 400 |
| `test_customer_not_found_returns_404` | mock returns body without `green`/`cheapest` keys → status 404 |
| `test_timeout_returns_504` | mock raises `ReadTimeoutError` → status 504 |
| `test_client_error_returns_502` | mock raises `ClientError` → status 502 |
| `test_unexpected_error_returns_500` | mock raises `Exception("boom")` → status 500 |
| `test_fresh_session_id_per_call` | call handler twice; capture `runtimeSessionId` kwarg via `mock_client.invoke_agent_runtime.call_args_list`; assert they differ |
| `test_response_passthrough_shape` | assert `json.loads(result["body"])` equals the exact dict returned by mock (no envelope) |

---

### `tests/test_backend_api_synth.py` (test, CDK synth)

**Analog:** `tests/test_agentcore_synth.py` — exact structural mirror.

**Full pattern to copy** (`tests/test_agentcore_synth.py` lines 1-34):
```python
"""Offline CDK synth test for AgentCoreStack — no AWS credentials needed."""
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

try:
    from infrastructure.agentcore_stack import AgentCoreStack
    _CAN_IMPORT = True
    _IMPORT_ERROR = ""
except ImportError as e:
    _CAN_IMPORT = False
    _IMPORT_ERROR = str(e)

pytestmark = pytest.mark.skipif(
    not _CAN_IMPORT,
    reason="AgentCoreStack import failed: {}".format(_IMPORT_ERROR),
)

@pytest.fixture(scope="module")
def synth_template():
    app = cdk.App()
    stack = AgentCoreStack(
        app,
        "TestAgentCoreStack",
        env=cdk.Environment(region="us-east-1", account="123456789012"),
    )
    return Template.from_stack(stack)

def test_stack_synthesises(synth_template):
    assert synth_template.to_json().get("Resources")
```

Delta for `test_backend_api_synth.py`:
- Import `BackendApiStack` from `infrastructure.backend_api_stack`
- Stack ID: `"TestBackendApiStack"`
- Test assertions replace AgentCore-specific checks:

```python
def test_has_http_api(synth_template):
    synth_template.resource_count_is("AWS::ApiGatewayV2::Api", 1)

def test_has_lambda(synth_template):
    synth_template.resource_count_is("AWS::Lambda::Function", 1)

def test_has_route(synth_template):
    synth_template.has_resource_properties(
        "AWS::ApiGatewayV2::Route",
        {"RouteKey": "GET /recommendations/{customer_id}"},
    )

def test_lambda_runtime_and_handler(synth_template):
    synth_template.has_resource_properties(
        "AWS::Lambda::Function",
        {"Runtime": "python3.12", "Handler": "handler.handler", "FunctionName": "tariff-api"},
    )

def test_cors_allow_all(synth_template):
    # CorsConfiguration on the HttpApi resource
    synth_template.has_resource_properties(
        "AWS::ApiGatewayV2::Api",
        {"CorsConfiguration": {"AllowOrigins": ["*"]}},
    )

def test_has_iam_policy_with_invoke_agent_runtime(synth_template):
    template_json = synth_template.to_json()
    found = False
    for resource in template_json.get("Resources", {}).values():
        if resource.get("Type") == "AWS::IAM::Policy":
            doc = resource["Properties"].get("PolicyDocument", {})
            for statement in doc.get("Statement", []):
                actions = statement.get("Action")
                if isinstance(actions, str):
                    actions = [actions]
                if actions and "bedrock-agentcore:InvokeAgentRuntime" in actions:
                    found = True
    assert found, "No IAM policy found with bedrock-agentcore:InvokeAgentRuntime"
```
Note: The IAM policy walk pattern (`test_has_iam_policy_with_lambda_invoke` in `test_agentcore_synth.py` lines 52-65) is the exact template to copy for `test_has_iam_policy_with_invoke_agent_runtime`.

---

### `tests/test_backend_api_smoke.py` (test, live HTTP)

**Analog:** `tests/test_agent_smoke.py` — exact structural mirror.

**Module-level skip guard pattern** (`tests/test_agent_smoke.py` lines 23-31):
```python
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not AGENT_RUNTIME_ARN,
        reason="AGENT_RUNTIME_ARN not set — skip live agent smoke tests",
    ),
]
```

Delta for `test_backend_api_smoke.py`:
- Guard var: `API_ENDPOINT = os.environ.get("API_ENDPOINT", "")`
- Skip reason: `"API_ENDPOINT not set — skip live API smoke tests"`
- Use `requests.get(...)` instead of boto3 `invoke_agent_runtime`
- Tests use `@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])` — same three personas
- The `@pytest.fixture scope="module"` for `agentcore_client` is replaced by a simple `requests` call (no fixture needed)

**Smoke test cases required:**

```python
import os
import pytest
import requests

API_ENDPOINT = os.environ.get("API_ENDPOINT", "")

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(not API_ENDPOINT, reason="API_ENDPOINT not set — skip live API smoke tests"),
]

@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_all_personas_return_recommendations(customer_id):
    r = requests.get(f"{API_ENDPOINT}recommendations/{customer_id}", timeout=60)
    assert r.status_code == 200
    body = r.json()
    assert "green" in body and "cheapest" in body

def test_invalid_format_returns_400():
    r = requests.get(f"{API_ENDPOINT}recommendations/NOTVALID", timeout=10)
    assert r.status_code == 400
    assert "error" in r.json()

def test_unknown_customer_returns_404():
    r = requests.get(f"{API_ENDPOINT}recommendations/CUST-999999", timeout=60)
    assert r.status_code == 404
    assert "error" in r.json()

def test_fresh_session_no_bleed():
    """SC-3: Two consecutive calls for different customers must not share session state."""
    r1 = requests.get(f"{API_ENDPOINT}recommendations/CUST-001", timeout=60)
    r2 = requests.get(f"{API_ENDPOINT}recommendations/CUST-002", timeout=60)
    assert r1.status_code == 200 and r2.status_code == 200
    # Different customers have different saving amounts — confirms no bleed
    assert r1.json()["green"]["saving_monthly"] != r2.json()["green"]["saving_monthly"]
```
Note: `API_ENDPOINT` from CDK output includes trailing slash (e.g., `https://xxx.execute-api.us-east-1.amazonaws.com/`). The URL construction `f"{API_ENDPOINT}recommendations/..."` is correct as-is.

---

### `tests/conftest.py` (modify — add Phase 3 fixtures)

**Analog:** `tests/conftest.py` lines 44-99 — the Phase 2 fixture block structure.

**Pattern to mirror** (`tests/conftest.py` lines 44-61):
```python
# --- Phase 2 agent fixtures ---

@pytest.fixture
def mock_savings_response():
    """Canonical savings response matching simulate_savings_pure output for Sarah Chen."""
    return {
        "green": {...},
        "cheapest": {...},
    }
```

**Phase 3 additions — append at end of conftest.py:**
```python
import io

# --- Phase 3 API Lambda fixtures ---

@pytest.fixture
def mock_agent_invoke_response(mock_savings_response):
    """Mock invoke_agent_runtime response wrapping savings body in StreamingBody-like BytesIO."""
    return {
        "response": io.BytesIO(json.dumps(mock_savings_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }

@pytest.fixture
def mock_agent_invoke_not_found():
    """Mock invoke_agent_runtime response for an unknown customer (no green/cheapest keys)."""
    return {
        "response": io.BytesIO(json.dumps({"errorMessage": "No billing history for 'CUST-999'"}).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }
```
Delta: Existing `mock_savings_response` fixture (line 46) already provides the canonical body dict — `mock_agent_invoke_response` should reference it via fixture injection to avoid duplicating the response shape. Note `io` is not currently imported in conftest.py — add to imports.

---

## Shared Patterns

### SSM Cross-Stack ARN Wiring (read side)
**Source:** `infrastructure/agentcore_stack.py` lines 17-19
**Apply to:** `infrastructure/backend_api_stack.py`
```python
agent_runtime_arn = ssm.StringParameter.value_for_string_parameter(
    self, "/customer-tariff/agent-runtime-arn"
)
```
Use `value_for_string_parameter` (deploy-time resolution, no AWS creds at synth). Never use `value_from_lookup` (requires creds at synth) or `Fn.import_value` (export lock).

### SSM Cross-Stack ARN Wiring (write side)
**Source:** `infrastructure/foundation_stack.py` lines 31-37
**Apply to:** `infrastructure/agentcore_stack.py` (amendment)
```python
ssm.StringParameter(
    self,
    "ToolsLambdaArnParam",
    parameter_name="/customer-tariff/tools-lambda-arn",
    string_value=tools.function.function_arn,
    description="ToolsLambda ARN for AgentCoreStack cross-stack wiring",
)
```

### Input Validation Regex
**Source:** `lambda/handler.py` lines 39, 50-51
**Apply to:** `api_lambda/handler.py`
```python
_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")
# ...
if not _CUSTOMER_ID_PATTERN.match(customer_id):
    raise ValueError(...)  # Phase 3: return _error(400, ...) instead
```

### CDK Synth Test Skip Guard
**Source:** `tests/test_agentcore_synth.py` lines 12-23
**Apply to:** `tests/test_backend_api_synth.py` and `tests/test_backend_api_unit.py`
```python
try:
    from infrastructure.backend_api_stack import BackendApiStack
    _CAN_IMPORT = True
    _IMPORT_ERROR = ""
except ImportError as e:
    _CAN_IMPORT = False
    _IMPORT_ERROR = str(e)

pytestmark = pytest.mark.skipif(not _CAN_IMPORT, reason="...")
```

### Smoke Test Module-Level Skip Guard
**Source:** `tests/test_agent_smoke.py` lines 23-31
**Apply to:** `tests/test_backend_api_smoke.py`
```python
API_ENDPOINT = os.environ.get("API_ENDPOINT", "")
pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(not API_ENDPOINT, reason="API_ENDPOINT not set — skip live API smoke tests"),
]
```

### Lambda Construct Defaults
**Source:** `infrastructure/constructs/tools_lambda.py` lines 24-34
**Apply to:** `infrastructure/constructs/backend_api.py`
- `runtime=lambda_.Runtime.PYTHON_3_12` — match Phase 1
- `memory_size=256` — match Phase 1
- `code=lambda_.Code.from_asset("api_lambda")` — new directory to avoid Phase 1 collision
- `timeout=Duration.seconds(30)` — D-03 (Phase 3 differs from Phase 1's 10s)

### IAM Policy Statement (no wildcard)
**Source:** `infrastructure/constructs/agent_runtime.py` lines 67-74
**Apply to:** `infrastructure/constructs/backend_api.py`
```python
fn.add_to_role_policy(
    iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        actions=["bedrock-agentcore:InvokeAgentRuntime"],
        resources=[agent_runtime_arn],   # scoped to specific runtime, not "*"
    )
)
```

### CDK Template IAM Walk (synth test)
**Source:** `tests/test_agentcore_synth.py` lines 52-65
**Apply to:** `tests/test_backend_api_synth.py::test_has_iam_policy_with_invoke_agent_runtime`
```python
template_json = synth_template.to_json()
found = False
for resource in template_json.get("Resources", {}).values():
    if resource.get("Type") == "AWS::IAM::Policy":
        doc = resource["Properties"].get("PolicyDocument", {})
        for statement in doc.get("Statement", []):
            actions = statement.get("Action")
            if isinstance(actions, str):
                actions = [actions]
            if actions and "lambda:InvokeFunction" in actions:
                found = True
assert found, "..."
```

---

## No Analog Found

All 10 files have analogs. The following patterns have no direct codebase analog but are fully specified in RESEARCH.md:

| Pattern | Where Specified | Notes |
|---------|----------------|-------|
| HTTP API v2 CDK construct (`apigwv2.HttpApi`, `CorsPreflightOptions`, `add_routes`) | RESEARCH.md Pattern 1 | No existing HTTP API in codebase — use verified code from RESEARCH.md Q1 |
| `boto3.client("bedrock-agentcore")` with `Config(read_timeout=25)` | RESEARCH.md Q2/Q4 | Phase 2 smoke test invokes without timeout config; API Lambda MUST add `Config` |
| `io.BytesIO` mock for `StreamingBody` | RESEARCH.md Q11 | No existing `bedrock-agentcore` unit tests; moto unavailable for this service |

---

## Metadata

**Analog search scope:** `lambda/`, `infrastructure/`, `infrastructure/constructs/`, `tests/`, `app.py`
**Files read:** 11 source files
**Pattern extraction date:** 2026-04-24

---

## PATTERN MAPPING COMPLETE
