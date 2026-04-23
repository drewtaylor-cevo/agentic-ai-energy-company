# Phase 3: Backend API — Research

**Researched:** 2026-04-24
**Domain:** AWS Lambda + API Gateway HTTP API v2 + boto3 bedrock-agentcore
**Confidence:** HIGH (all critical claims verified against installed packages and live service model introspection)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Synchronous JSON response — no HTTP streaming.
- **D-02:** Pass-through response shape — `{"green": {...}, "cheapest": {...}}` verbatim from agent.
- **D-03:** Lambda timeout 30s, surface 504 on agent timeout.
- **D-04:** Accept cold-start latency for demo — no provisioned concurrency.
- **D-05:** API Gateway HTTP API (v2, not REST).
- **D-06:** New `BackendApiStack` — stack-per-phase pattern.
- **D-07:** SSM Parameter for cross-stack ARN wiring — `AgentCoreStack` writes `/customer-tariff/agent-runtime-arn`; `BackendApiStack` reads via `ssm.StringParameter.value_for_string_parameter`.
- **D-08:** No authentication — open endpoint.
- **D-09:** CORS allow-all — `*` origin, methods GET/POST/OPTIONS, headers Content-Type.
- **D-10:** `GET /recommendations/{customer_id}`.
- **D-11:** Fresh `runtimeSessionId = str(uuid.uuid4())` per invocation.
- **D-12:** Standard HTTP error mapping with `{"error": "<message>"}` body: 400 bad format, 404 not found, 504 timeout, 502 agent failure, 500 server error.
- **D-13:** Validate customer_id against `^CUST-\d{3,6}$` before calling agent.

### Claude's Discretion
- CloudWatch log group name and retention period.
- X-Ray tracing on the API Lambda.
- Lambda memory (match Phase 1 default: 256 MB).
- Python runtime version (match Phase 1: PYTHON_3_12).
- Exact CDK construct layout (`BackendApiConstruct` or inline).
- Test structure (offline unit + smoke, mirroring Phase 2 pattern).
- Whether to fold AgentCoreStack SSM amendment into Phase 3 prereq step or amend stack directly.

### Deferred Ideas (OUT OF SCOPE)
- DEMO-03 pre-warm script (v2-deferred).
- DEMO-04 frozen environment lock (Phase 5).
- API key / WAF / usage plans.
- Observability polish beyond basic logging.
- Multiple deploy stages.
- Custom domain / CloudFront.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEMO-01 | End-to-end demo runs on dummy data with no live CRM connectivity required — fully self-contained | Confirmed by: API Lambda calls `invoke_agent_runtime` with customer_id; agent returns Green + Cheapest from DynamoDB dummy data; no external data source in call path |
</phase_requirements>

---

## Summary

**Key findings:**

- `aws_cdk.aws_apigatewayv2` (stable, not alpha) and `aws_cdk.aws_apigatewayv2_integrations` are both present in the installed `aws-cdk-lib==2.250.0`. `HttpApi`, `HttpLambdaIntegration`, `HttpRouteKey`, and `CorsPreflightOptions` are all available with verified signatures. The route `GET /recommendations/{customer_id}` is expressed as `path='/recommendations/{customer_id}'` in `api.add_routes(...)` and the synthesised route key is `GET /recommendations/{customer_id}`. CORS allow-all is built into `HttpApi` directly — no explicit OPTIONS route needed.

- `boto3.client("bedrock-agentcore")` is the confirmed client name (verified via live service model). `invoke_agent_runtime` requires `agentRuntimeArn` (string) and `payload` (blob). The response `response` field is a streaming blob (`streaming: True` in service model) but is consumed with `.read()` — confirmed by the deployed Phase 2 smoke test at `tests/test_agent_smoke.py` line 50: `json.loads(response["response"].read())`. `statusCode` (integer) and `contentType` are also returned.

- The `@app.entrypoint` return value from `BedrockAgentCoreApp` is returned **verbatim** as the binary body of `invoke_agent_runtime`'s `response` field. The Phase 2 smoke tests confirm: `json.loads(response["response"].read())` yields `{"green": {...}, "cheapest": {...}}` — no outer wrapper. D-02 pass-through is a direct `json.loads(response["response"].read())` return.

- The IAM action for invoke is `bedrock-agentcore:InvokeAgentRuntime` (service prefix `bedrock-agentcore`, confirmed from AWS IAM reference). Resource ARN pattern: `arn:aws:bedrock-agentcore:{region}:{account}:runtime/{runtimeId}`. The API Lambda role also needs `ssm:GetParameter` to read the runtime ARN at cold start (if read at init time) — or the ARN is injected as an env var by CDK at deploy time (preferred, no SSM call at runtime).

- The botocore default read timeout is 60s — longer than the Lambda timeout of 30s. This means if `invoke_agent_runtime` hangs, the Lambda is killed by the execution environment before boto can surface the `ReadTimeoutError`. The fix is `Config(read_timeout=25, connect_timeout=5)` on the boto3 client creation, giving 5s buffer before Lambda dies.

**Primary recommendation:** New directory `api_lambda/handler.py` (separate from `lambda/`) for the API Lambda code; new `infrastructure/constructs/backend_api.py` construct following the `AgentRuntimeConstruct` pattern; `BackendApiStack` in `infrastructure/backend_api_stack.py`; registered in `app.py`. Amend `AgentCoreStack` to write SSM parameter before deploying Phase 3.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP routing + CORS | API Gateway HTTP API (v2) | — | D-05 locked; APIGW handles CORS natively |
| Request validation (customer_id format) | API Lambda | — | D-13: fail fast before invoking agent |
| Session ID generation | API Lambda | — | D-11: fresh uuid4() per invocation |
| Agent invocation | API Lambda | AgentCore Runtime | Lambda calls `invoke_agent_runtime` |
| Recommendations computation | AgentCore Runtime (Phase 2) | ToolsLambda (Phase 1) | Existing; Phase 3 does not modify |
| Error taxonomy mapping | API Lambda | — | D-12: map boto3/response errors to HTTP codes |
| Cross-stack ARN wiring (write) | AgentCoreStack (Phase 2 amendment) | — | D-07: SSM write happens in producer stack |
| Cross-stack ARN wiring (read) | BackendApiStack | — | D-07: SSM read at CDK synth/deploy time |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aws-cdk-lib | 2.250.0 | CDK constructs (HttpApi, HttpLambdaIntegration, SSM, Lambda) | Already installed; project standard |
| aws_cdk.aws_apigatewayv2 | (in aws-cdk-lib 2.250.0) | HTTP API v2 — HttpApi, CorsPreflightOptions, HttpRouteKey | Stable (not alpha); all required classes present |
| aws_cdk.aws_apigatewayv2_integrations | (in aws-cdk-lib 2.250.0) | HttpLambdaIntegration binding Lambda to routes | Stable; verified `HttpLambdaIntegration` present |
| boto3 | 1.42.11 | `bedrock-agentcore` client for `invoke_agent_runtime` | Installed; service model confirmed present |
| botocore | 1.42.11 | `Config(read_timeout=25)` for timeout control; `ReadTimeoutError` | Installed; exception hierarchy verified |
| constructs | 10.6.0 | CDK Construct base class | Project standard |

[VERIFIED: pip3 show / live Python import inspection, 2026-04-24]

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uuid (stdlib) | Python 3.12 stdlib | `uuid.uuid4()` for runtimeSessionId | Every API Lambda invocation |
| json (stdlib) | Python 3.12 stdlib | Encode payload, decode response | Every API Lambda invocation |
| re (stdlib) | Python 3.12 stdlib | `^CUST-\d{3,6}$` validation (D-13) | Input validation gate |
| logging (stdlib) | Python 3.12 stdlib | `logging.getLogger(__name__)` — matches Phase 2 pattern | Lambda handler |
| pytest | 8.4.2 | Test runner (already installed) | All test types |
| pytest-mock | (installed) | `mocker` fixture for boto3 mocking | Offline unit tests |

[VERIFIED: pip3 show / Python 3.9.6 host, deployed environment is Python 3.12]

### No New Pip Dependencies Required
Phase 3 API Lambda uses only stdlib + boto3 (present in Lambda runtime). CDK infrastructure uses `aws-cdk-lib` already installed. No `pip install` needed beyond what already exists.

---

## Architecture Patterns

### System Architecture Diagram

```
curl/Postman/React UI
        |
        | GET /recommendations/{customer_id}
        v
[API Gateway HTTP API v2]
  - CORS: allow-all (D-09)
  - Route: GET /recommendations/{customer_id}
  - Timeout: 30s hard limit
        |
        | Lambda Payload Format 2.0 event
        v
[API Lambda — tariff-api]
  1. Extract customer_id from event["pathParameters"]["customer_id"]
  2. Regex validate ^CUST-\d{3,6}$ -> 400 if fail (D-13)
  3. Generate runtimeSessionId = str(uuid.uuid4()) (D-11)
  4. Read AGENT_RUNTIME_ARN from env var (set by CDK)
  5. boto3.client("bedrock-agentcore", config=Config(read_timeout=25))
  6. call invoke_agent_runtime(agentRuntimeArn, runtimeSessionId, payload)
        |
        | binary payload: {"customer_id": "CUST-001"}
        v
[AgentCore Runtime — tariff_agent (Phase 2)]
  - @app.entrypoint -> invoke()
  - Calls ToolsLambda via simulate_savings tool
  - Returns {"green": {...}, "cheapest": {...}}
        |
        | response["response"] StreamingBody
        v
[API Lambda — continued]
  7. json.loads(response["response"].read()) -> body dict
  8. Detect errors in body (no green/cheapest keys) -> 404
  9. Return 200 with body verbatim (D-02 pass-through)
        |
        v
curl/Postman/React UI receives {"green": {...}, "cheapest": {...}}
```

**Error paths:**
```
Invalid customer_id format -> 400 {"error": "Invalid customer ID format. Expected CUST-NNN."}
Agent timeout (ReadTimeoutError) -> 504 {"error": "Recommendation service timed out. Please try again."}
ClientError (ValidationException/Throttling/etc.) -> 502 {"error": "Recommendation service error. Please try again."}
Missing green/cheapest in response -> 404 {"error": "Customer CUST-999 not found."}
Unexpected exception -> 500 {"error": "Internal server error."}
```

### Recommended Project Structure
```
api_lambda/
├── handler.py           # API Lambda entry point (main research subject)
infrastructure/
├── backend_api_stack.py # New BackendApiStack (adds BackendApiConstruct)
├── constructs/
│   └── backend_api.py   # New BackendApiConstruct (HttpApi + Lambda + routes)
tests/
├── test_backend_api_unit.py   # Offline: mock bedrock-agentcore client
├── test_backend_api_synth.py  # CDK synth: BackendApiStack template assertions
└── test_backend_api_smoke.py  # Live: requests.get(ENDPOINT/recommendations/CUST-001)
```

**Naming rationale:** `api_lambda/` avoids collision with `lambda/` (Phase 1 tools Lambda). `BackendApiStack` / `BackendApiConstruct` follows `AgentCoreStack` / `AgentRuntimeConstruct` naming convention.

### Pattern 1: API Gateway HTTP API v2 with CORS and Lambda Integration
**What:** Single-file construct wires `HttpApi` + `HttpLambdaIntegration` + route + CfnOutput.
**When to use:** All Phase 3 HTTP API work.

```python
# Source: verified via Python import inspection of aws-cdk-lib==2.250.0
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integ
from aws_cdk import CfnOutput

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

# api.url includes trailing slash: https://{id}.execute-api.us-east-1.amazonaws.com/
CfnOutput(self, "ApiEndpoint", value=api.url)
```

**Verified:** CDK synth of the pattern above produces:
- Route key: `GET /recommendations/{customer_id}` [VERIFIED: local synth, 2026-04-24]
- CORS in CloudFormation: `{'AllowHeaders': ['Content-Type'], 'AllowMethods': ['GET', 'OPTIONS'], 'AllowOrigins': ['*']}` [VERIFIED: local synth]
- CORS handles OPTIONS preflight automatically — no explicit OPTIONS route needed [VERIFIED: HTTP API v2 CORS spec]

**Default payload format:** `PayloadFormatVersion.VERSION_2_0` (HTTP API v2 default). Lambda receives event with `pathParameters.customer_id`. [VERIFIED: CDK source `payload_format_version: Default: PayloadFormatVersion.VERSION_2_0`]

### Pattern 2: API Lambda Handler Structure
**What:** Lambda entry point for API Gateway HTTP API v2.

```python
# api_lambda/handler.py
import json
import logging
import os
import re
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError

logger = logging.getLogger(__name__)

_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")  # D-13: mirror lambda/handler.py
_AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Module-level client: reused across warm invocations.
# Config(read_timeout=25): fire ReadTimeoutError at 25s, giving Lambda 5s buffer
# before the 30s Lambda timeout kills the process (D-03).
_agentcore_client = boto3.client(
    "bedrock-agentcore",
    region_name=_REGION,
    config=Config(read_timeout=25, connect_timeout=5),
)


def _error(status_code: int, message: str) -> dict:
    """Consistent error response body (D-12)."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }


def handler(event: dict, context) -> dict:
    """API Lambda entry point. GET /recommendations/{customer_id}."""
    # Step 1: Extract customer_id from path params (HTTP API v2 payload format)
    path_params = event.get("pathParameters") or {}
    customer_id = path_params.get("customer_id", "")

    # Step 2: Validate format (D-13)
    if not _CUSTOMER_ID_PATTERN.match(customer_id):
        return _error(400, "Invalid customer ID format. Use CUST-NNN (3-6 digits).")

    # Step 3: Fresh session ID per invocation (D-11)
    session_id = str(uuid.uuid4())  # 36 chars, satisfies AgentCore 33-char minimum

    logger.info("Invoking agent for %s session=%s", customer_id, session_id)

    try:
        # Step 4: Invoke AgentCore runtime (D-01: synchronous read)
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

    # Step 5: Detect customer-not-found in agent response body (D-12: 404)
    if "green" not in body or "cheapest" not in body:
        msg = body.get("error", body.get("errorMessage", f"Customer {customer_id} not found."))
        logger.info("Customer not found response for %s: %s", customer_id, msg)
        return _error(404, f"Customer {customer_id} not found.")

    # Step 6: Pass-through verbatim (D-02)
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
```

### Pattern 3: BackendApiStack CDK Stack
**What:** Stack-per-phase pattern for Phase 3 infrastructure.

```python
# infrastructure/backend_api_stack.py
from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ssm as ssm
from constructs import Construct
from infrastructure.constructs.backend_api import BackendApiConstruct


class BackendApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Read AgentCore runtime ARN from SSM (D-07: avoids CfnOutput export lock)
        # value_for_string_parameter returns a CloudFormation dynamic reference
        # token (resolves at deploy time, NOT synth time).
        agent_runtime_arn = ssm.StringParameter.value_for_string_parameter(
            self, "/customer-tariff/agent-runtime-arn"
        )

        backend = BackendApiConstruct(
            self,
            "BackendApi",
            agent_runtime_arn=agent_runtime_arn,
        )

        CfnOutput(self, "ApiEndpoint", value=backend.api_endpoint)
```

### Pattern 4: AgentCoreStack Amendment (SSM Write)
**What:** Minimal diff to add SSM parameter write to Phase 2's existing `AgentCoreStack`.
**Mirrors:** `infrastructure/foundation_stack.py` SSM write pattern (lines 31-37). [VERIFIED: read foundation_stack.py]

```python
# Add to infrastructure/agentcore_stack.py (after existing CfnOutput lines):
ssm.StringParameter(
    self,
    "AgentRuntimeArnParam",
    parameter_name="/customer-tariff/agent-runtime-arn",
    string_value=runtime.agent_runtime_arn,
    description="AgentCore runtime ARN for BackendApiStack cross-stack wiring",
)
```

**Note:** SSM parameters created via CDK are deleted on `cdk destroy` of `AgentCoreStack`. This is correct behaviour — if the runtime is destroyed, the ARN is stale. No conflict with existing `CfnOutput` (both can coexist).

### Pattern 5: SSM Read — `value_for_string_parameter` vs `value_from_lookup`

| Method | When Resolves | Requires AWS creds at synth? | Use for Phase 3? |
|--------|--------------|------------------------------|------------------|
| `value_for_string_parameter` | Deploy time (CloudFormation dynamic reference) | No | **YES** |
| `value_from_lookup` | Synth time (context lookup) | Yes | No |

`value_for_string_parameter` returns a CDK token (`${Token[TOKEN.12]}`) that CloudFormation resolves at deploy time. This is the correct cross-stack pattern: CDK synth works offline, only real AWS calls happen at `cdk deploy`. [VERIFIED: local Python inspection, token repr confirmed]

### Pattern 6: app.py Registration
```python
# Add to app.py after AgentCoreStack instantiation:
from infrastructure.backend_api_stack import BackendApiStack

BackendApiStack(
    app,
    "CustomerTariffApi",
    env=cdk.Environment(region="us-east-1"),
    description="Phase 3: Backend API",
)
```

### Anti-Patterns to Avoid
- **Module-level `runtimeSessionId`:** Never set session ID at module level or reuse across invocations. Must be `str(uuid.uuid4())` inside `handler()`. Module-level ID causes session bleed (violates D-11 and success criterion 3).
- **Default botocore timeout:** Never use `boto3.client("bedrock-agentcore")` without `Config(read_timeout=25)`. The default 60s read timeout outlasts the 30s Lambda timeout — the Lambda dies before boto surfaces `ReadTimeoutError`, making 504 unreachable.
- **CfnOutput cross-stack import for ARN:** Never use `Fn.import_value(AgentCoreStack.export("AgentRuntimeArn"))`. This creates a CloudFormation export lock preventing independent redeployment of either stack (Pitfall 5, established Phase 2).
- **Moto for `bedrock-agentcore`:** moto 5.1.20 does NOT have a `mock_bedrock_agentcore` backend. Use `unittest.mock` / `pytest-mock` instead. [VERIFIED: `from moto import mock_bedrock_agentcore` raises ImportError]
- **Reading ARN from SSM at Lambda cold start:** Prefer env var injection (CDK sets `AGENT_RUNTIME_ARN` as Lambda env var from SSM token). Avoid boto3 SSM call inside the handler — adds latency and requires extra IAM permission.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CORS preflight | Custom OPTIONS route + response headers | `HttpApi(cors_preflight=CorsPreflightOptions(...))` | HTTP API v2 handles OPTIONS automatically when `cors_preflight` is set; hand-roll misses headers for complex preflights |
| Route-to-Lambda wiring | Direct CFN resource `AWS::ApiGatewayV2::Integration` | `HttpLambdaIntegration` + `api.add_routes()` | CDK L2 handles permission grants (Lambda resource policy) automatically |
| Timeout config on boto3 | `try/finally` with threading timer | `Config(read_timeout=25)` on client init | botocore Config is the correct mechanism; threading adds complexity and races |
| Mock response body | String concatenation | `io.BytesIO(json.dumps(body).encode())` | `response["response"].read()` expects a file-like object; BytesIO is the exact type |

---

## Q&A: All 13 Research Questions

### Q1: AWS CDK HTTP API v2 construct path

**Answer:** Both `aws_cdk.aws_apigatewayv2` (stable) and `aws_cdk.aws_apigatewayv2_integrations` (stable) are present in `aws-cdk-lib==2.250.0`. The alpha package is NOT needed for HTTP API. [VERIFIED: live Python import, 2026-04-24]

Key classes:
- `apigwv2.HttpApi` — main construct, accepts `cors_preflight` kwarg
- `apigwv2.CorsPreflightOptions` — `allow_origins`, `allow_methods`, `allow_headers`
- `apigwv2.CorsHttpMethod` — enum: `GET`, `POST`, `OPTIONS`, `ANY`, etc.
- `apigwv2.HttpMethod` — enum for route binding: `GET`, `POST`, etc.
- `apigwv2.HttpRouteKey.with_(path, method)` — static method for route key construction
- `integ.HttpLambdaIntegration(id, fn)` — default payload format: `VERSION_2_0`
- `api.add_routes(path=..., methods=[...], integration=...)` — binds route to integration

CORS is built into the API construct — no explicit OPTIONS route needed. [VERIFIED: synth confirmed `AllowMethods: [GET, OPTIONS]` in CloudFormation template]

### Q2: boto3 `bedrock-agentcore` client and `invoke_agent_runtime` signature

**Answer:** [VERIFIED: live service model introspection, boto3==1.42.11]

```python
client = boto3.client("bedrock-agentcore", region_name="us-east-1", config=Config(read_timeout=25))
response = client.invoke_agent_runtime(
    agentRuntimeArn="arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/...",
    runtimeSessionId=str(uuid.uuid4()),
    payload=json.dumps({"customer_id": "CUST-001"}).encode(),
)
```

**Required parameters:** `agentRuntimeArn` (string, required), `payload` (blob, required).
**Optional parameters:** `qualifier`, `accountId`, `contentType`, `accept`, `runtimeSessionId`, `runtimeUserId`, and several tracing headers.
**Response keys:** `response` (blob, streaming=True), `statusCode` (integer), `contentType` (string), `runtimeSessionId` (string), plus tracing fields.

**Regional constraints:** Only us-east-1 confirmed (AgentCore Registry constraint established in Phase 2). [ASSUMED from Phase 2 context; not re-verified in this session]

### Q3: AgentCore response parsing — bare dict vs wrapped

**Answer:** `invoke_agent_runtime` `response["response"].read()` returns the **bare bytes** of what `@app.entrypoint` returned — no outer wrapper. [VERIFIED: Phase 2 smoke test `_invoke_agent()` at `tests/test_agent_smoke.py:50` checks `body["green"]` and `body["cheapest"]` directly after `json.loads(response["response"].read())`]

`@app.entrypoint` returns `result.model_dump()` → `{"green": {...}, "cheapest": {...}}`.
`invoke_agent_runtime` passes this through as the response body.
API Lambda: `body = json.loads(response["response"].read())` then returns `body` verbatim (D-02).

`response["response"]` is a `StreamingBody` (service model: `type=blob, streaming=True, sensitive=True`) but supports `.read()` to consume all bytes at once. For D-01 (synchronous), `.read()` is correct — do not use `.iter_lines()`. [VERIFIED: service model introspection]

### Q4: Timeout handling

**Answer:** [VERIFIED: botocore.exceptions inspection]

The botocore default `read_timeout=60` **outlasts** the Lambda timeout of 30s. The Lambda execution environment kills the process at 30s — `ReadTimeoutError` is never raised because botocore's 60s timer hasn't fired yet. The fix:

```python
from botocore.config import Config
config = Config(read_timeout=25, connect_timeout=5)
client = boto3.client("bedrock-agentcore", config=config)
```

With `read_timeout=25`: if `invoke_agent_runtime` hasn't responded in 25s, botocore raises `botocore.exceptions.ReadTimeoutError`. The Lambda handler catches this and returns 504. The remaining ~5s Lambda budget is enough for the error response.

API Gateway HTTP API hard limit is 29s (not 30s — the 30s is the Lambda timeout D-03). Both limits align: Lambda raises 504 at 25s, Lambda exits at 30s, API Gateway drops at 29s in the worst case. The 25s boto timeout ensures 504 is surfaced cleanly. [ASSUMED: 29s API Gateway hard limit — AWS docs state 29s for HTTP API integration timeout; confirm against current docs]

### Q5: Error taxonomy mapping (D-12)

**Answer:** [VERIFIED: service model for error shapes; Phase 2 agent code for customer-not-found path]

| Condition | Exception / Signal | HTTP Code | Response Body |
|-----------|-------------------|-----------|---------------|
| Bad customer_id format | Regex mismatch (before boto call) | 400 | `{"error": "Invalid customer ID format..."}` |
| Customer not found | Agent body missing `green`/`cheapest` keys | 404 | `{"error": "Customer CUST-999 not found."}` |
| Agent timeout | `botocore.exceptions.ReadTimeoutError` | 504 | `{"error": "Recommendation service timed out..."}` |
| AgentCore ClientError | `botocore.exceptions.ClientError` (ValidationException, ThrottlingException, ResourceNotFoundException, ServiceQuotaExceededException, AccessDeniedException, RuntimeClientError, InternalServerException) | 502 | `{"error": "Recommendation service error..."}` |
| Unexpected | Any other `Exception` | 500 | `{"error": "Internal server error."}` |

**Customer-not-found detection detail:** When `CUST-999` is looked up, the ToolsLambda `simulate_savings` raises `ValueError("No billing history for 'CUST-999'")`. The agent's `simulate_savings` tool raises `RuntimeError("ToolsLambda error: ...")`. The agent may handle this and return an error body, or the fallback path in `agent.py` runs `json.loads(resp["Payload"].read())` which returns the Lambda error object `{"errorMessage": "...", "errorType": "ValueError"}`. Either way, `"green"` and `"cheapest"` are absent from the response body. Checking for absent tracks is the most robust detection. [VERIFIED: agent.py source + lambda/handler.py ValueError line 144]

### Q6: IAM policy for API Lambda execution role

**Answer:** [VERIFIED: AWS IAM reference https://docs.aws.amazon.com/IAM/latest/UserGuide/list_amazonbedrockagentcore.html]

IAM action: `bedrock-agentcore:InvokeAgentRuntime`
Resource ARN format: `arn:aws:bedrock-agentcore:{region}:{account}:runtime/{runtimeId}`

The API Lambda execution role needs:
1. `bedrock-agentcore:InvokeAgentRuntime` on the runtime ARN resource (and optionally runtime-endpoint ARN)
2. Basic Lambda execution permissions (CloudWatch Logs) — auto-granted by CDK `lambda_.Function`
3. **No SSM permission needed** — if the runtime ARN is injected as an env var by CDK at deploy time (the recommended pattern), the Lambda never calls SSM at runtime.

```python
fn.add_to_role_policy(
    iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        actions=["bedrock-agentcore:InvokeAgentRuntime"],
        resources=[agent_runtime_arn],  # token from SSM, resolves to actual ARN at deploy
    )
)
```

**Note:** `agent_runtime_arn` is a CDK token (`value_for_string_parameter` result). CDK resolves this to the actual ARN in the CloudFormation template. The IAM policy will contain the resolved ARN at deploy time.

### Q7: SSM Parameter read in CDK — `value_for_string_parameter` vs alternatives

**Answer:** [VERIFIED: Python import inspection + token repr inspection]

| Method | Resolution | AWS creds at synth? | Recommendation |
|--------|-----------|---------------------|----------------|
| `value_for_string_parameter(scope, param_name)` | Deploy time | No | **Use this** |
| `value_from_lookup(scope, param_name)` | Synth time | Yes | Avoid for cross-stack |
| `from_string_parameter_name(scope, param_name)` | Returns IStringParameter object | No | Use when you need the object, not the value |

`value_for_string_parameter` is correct for cross-stack ARN reads. It returns a CloudFormation dynamic reference token (`${Token[TOKEN.12]}`). The actual SSM value is looked up by CloudFormation during deployment. No AWS credentials required at `cdk synth`. This is exactly how `AgentCoreStack` already reads `/customer-tariff/tools-lambda-arn`. [VERIFIED: agentcore_stack.py line 18]

### Q8: AgentCoreStack amendment for SSM write

**Answer:** Minimal one-block addition mirroring `foundation_stack.py` lines 31-37. [VERIFIED: foundation_stack.py source]

```python
# Add to infrastructure/agentcore_stack.py, after the existing CfnOutputs:
ssm.StringParameter(
    self,
    "AgentRuntimeArnParam",
    parameter_name="/customer-tariff/agent-runtime-arn",
    string_value=runtime.agent_runtime_arn,
    description="AgentCore runtime ARN for BackendApiStack cross-stack wiring",
)
```

**Lifecycle:** SSM parameter is created and managed by CloudFormation. It is deleted when `cdk destroy CustomerTariffAgent` is run. This is correct — if the agent stack is destroyed, the ARN parameter should not exist.

**Conflict with existing CfnOutput:** None. `CfnOutput` and `ssm.StringParameter` are independent CloudFormation resources; both can coexist in the same stack.

**Deploy order:** `AgentCoreStack` must be deployed (or re-deployed to pick up the SSM write amendment) before `BackendApiStack` is deployed. CDK does not auto-detect this dependency because the stacks are independent (by design — SSM wiring avoids the hard dependency). The Phase 3 plan must sequence: amend + deploy AgentCoreStack first, then deploy BackendApiStack.

### Q9: API Lambda packaging

**Answer:** New directory `api_lambda/handler.py`. [VERIFIED: no `api_lambda/` directory exists yet]

The Phase 1 tools Lambda is in `lambda/` with `function_name="tariff-tools"`. The API Lambda should be in `api_lambda/` with `function_name="tariff-api"` to avoid naming collision.

```python
# In BackendApiConstruct:
fn = lambda_.Function(
    self, "TariffApiLambda",
    function_name="tariff-api",
    runtime=lambda_.Runtime.PYTHON_3_12,  # Match Phase 1 (verified: tools_lambda uses PYTHON_3_12)
    handler="handler.handler",
    code=lambda_.Code.from_asset("api_lambda"),
    timeout=Duration.seconds(30),         # D-03: Lambda timeout 30s
    memory_size=256,                       # Match Phase 1 default
    environment={
        "AGENT_RUNTIME_ARN": agent_runtime_arn,
        "AWS_REGION": cdk.Stack.of(self).region,
    },
)
```

**Why separate directory:** `Code.from_asset("api_lambda")` packages only that directory. Sharing `lambda/` would bundle unrelated Phase 1 code into the API Lambda zip.

### Q10: CORS on HTTP API v2

**Answer:** [VERIFIED: CDK synth produced correct CORS config; HTTP API v2 handles OPTIONS]

```python
cors_preflight=apigwv2.CorsPreflightOptions(
    allow_origins=["*"],
    allow_methods=[
        apigwv2.CorsHttpMethod.GET,
        apigwv2.CorsHttpMethod.OPTIONS,
    ],
    allow_headers=["Content-Type"],
)
```

This produces CloudFormation: `AllowOrigins: ["*"], AllowMethods: ["GET", "OPTIONS"], AllowHeaders: ["Content-Type"]`.

**OPTIONS preflight:** HTTP API v2 handles OPTIONS preflight automatically when `cors_preflight` is set. No explicit `OPTIONS` route in `add_routes()` is needed. The API Gateway itself responds to OPTIONS with the CORS headers before the request reaches Lambda. [CITED: AWS HTTP API CORS documentation pattern]

### Q11: Testing approach

**Offline unit tests (mock `bedrock-agentcore`):**

```python
# tests/test_backend_api_unit.py
import io, json
from unittest.mock import MagicMock, patch

def _make_agent_response(body: dict) -> dict:
    """Construct a mock invoke_agent_runtime response."""
    return {
        "response": io.BytesIO(json.dumps(body).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }

def test_valid_customer_success(monkeypatch):
    mock_client = MagicMock()
    mock_client.invoke_agent_runtime.return_value = _make_agent_response({
        "green": {"plan_id": "ECO", "plan_name": "EcoFlex 100", "saving_monthly": 30.0, "saving_annual": 360.0},
        "cheapest": {"plan_id": "VAL", "plan_name": "Value 12", "saving_monthly": 55.0, "saving_annual": 660.0},
    })
    with patch("api_lambda.handler._agentcore_client", mock_client):
        from api_lambda.handler import handler
        event = {"pathParameters": {"customer_id": "CUST-001"}}
        result = handler(event, None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert "green" in body and "cheapest" in body
```

**Note:** `moto` does NOT support `bedrock-agentcore` (confirmed). Use `unittest.mock` / `pytest-mock` with `io.BytesIO` for the response blob. [VERIFIED: moto 5.1.20 has no mock_bedrock_agentcore]

**CDK synth test:** Mirror `tests/test_agentcore_synth.py` pattern. [VERIFIED: test_agentcore_synth.py source]

```python
# tests/test_backend_api_synth.py
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template
from infrastructure.backend_api_stack import BackendApiStack

@pytest.fixture(scope="module")
def synth_template():
    app = cdk.App()
    stack = BackendApiStack(
        app, "TestBackendApiStack",
        env=cdk.Environment(region="us-east-1", account="123456789012"),
    )
    return Template.from_stack(stack)

def test_has_http_api(synth_template):
    synth_template.resource_count_is("AWS::ApiGatewayV2::Api", 1)

def test_has_lambda(synth_template):
    synth_template.resource_count_is("AWS::Lambda::Function", 1)

def test_has_route(synth_template):
    synth_template.has_resource_properties(
        "AWS::ApiGatewayV2::Route",
        {"RouteKey": "GET /recommendations/{customer_id}"},
    )
```

**Smoke tests:** Mirror `tests/test_agent_smoke.py` `@pytest.mark.smoke` / `pytest.mark.skipif` pattern.

```python
# tests/test_backend_api_smoke.py
import os, json, pytest, requests

API_ENDPOINT = os.environ.get("API_ENDPOINT", "")

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(not API_ENDPOINT, reason="API_ENDPOINT not set"),
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

def test_unknown_customer_returns_404():
    r = requests.get(f"{API_ENDPOINT}recommendations/CUST-999999", timeout=60)
    assert r.status_code == 404

def test_fresh_session_no_bleed():
    """Two consecutive calls must return consistent results (session isolation)."""
    r1 = requests.get(f"{API_ENDPOINT}recommendations/CUST-001", timeout=60)
    r2 = requests.get(f"{API_ENDPOINT}recommendations/CUST-002", timeout=60)
    assert r1.json()["green"]["plan_id"] == r2.json()["green"]["plan_id"] == "ECO"
    # Different personas have different savings — not bleed
    assert r1.json()["green"]["saving_monthly"] != r2.json()["green"]["saving_monthly"]
```

### Q12: Logging conventions

**Answer:** Phase 1 (`lambda/handler.py`) has NO logging module — it uses no structured logging. Phase 2 (`agent/agent.py`) uses `logger = logging.getLogger(__name__)` with standard Python `logging`. For consistency with Phase 2, API Lambda should use the same pattern:

```python
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
```

No `python-json-logger` or structured JSON logging — neither phase uses it. Plain text CloudWatch log output is sufficient for the demo. [VERIFIED: lambda/handler.py and agent/agent.py source inspection]

Claude's discretion: set `LOG_LEVEL` env var to allow runtime log level override.

### Q13: Validation Architecture (see dedicated section below)

---

## Common Pitfalls

### Pitfall 1: botocore Default Timeout Outlasts Lambda Timeout
**What goes wrong:** `boto3.client("bedrock-agentcore")` created without `Config(read_timeout=25)`. The Lambda execution environment kills the process at 30s. botocore's 60s timer hasn't fired — `ReadTimeoutError` is never raised. The 504 branch is unreachable; the API Gateway returns a 502 or connection reset.
**Why it happens:** botocore defaults: `connect_timeout=60, read_timeout=60`.
**How to avoid:** Always create the client with `Config(read_timeout=25, connect_timeout=5)` at module level.
**Warning signs:** API never returns 504 in tests; only 502 or empty response on long invocations.

### Pitfall 2: Module-Level Session ID Causes Bleed
**What goes wrong:** `_SESSION_ID = str(uuid.uuid4())` set at module level or in the client init block is reused across warm Lambda invocations. All requests from the same container share one session, causing session state bleed between persona lookups.
**Why it happens:** Module-level code runs once per cold start and is reused across invocations.
**How to avoid:** `session_id = str(uuid.uuid4())` must be the FIRST line inside `handler()`, not outside it.
**Warning signs:** Consecutive calls for different customer IDs return identical results.

### Pitfall 3: CfnOutput Import for AgentRuntimeArn (Export Lock)
**What goes wrong:** Using `Fn.import_value()` to pull `AgentRuntimeArn` from `AgentCoreStack` output. CloudFormation prevents deleting or modifying the exporting stack while an import exists. Independent redeployment of `AgentCoreStack` becomes impossible.
**Why it happens:** Appears to be the obvious cross-stack reference pattern.
**How to avoid:** SSM Parameter store only (D-07). Both stacks already follow this pattern for ToolsLambdaArn; AgentRuntimeArn must follow the same convention.

### Pitfall 4: OPTIONS Route Not Handled → CORS Preflight Failure
**What goes wrong:** Adding only `GET /recommendations/{customer_id}` route without CORS config on `HttpApi`. Browser-based UI (Phase 4) sends preflight OPTIONS — receives no CORS headers — blocks the request.
**Why it happens:** Developers forget that browsers send OPTIONS before GET for cross-origin requests.
**How to avoid:** Set `cors_preflight` on `HttpApi` constructor. No explicit OPTIONS route in `add_routes()` needed — HTTP API v2 handles it.
**Warning signs:** curl works; browser fetch fails with CORS error.

### Pitfall 5: 404 Detection Misses Error Body Variants
**What goes wrong:** API Lambda checks only for `body.get("error")` key to detect customer not found. But when the agent fallback path runs, the Lambda error payload is `{"errorMessage": "...", "errorType": "ValueError"}` — no `"error"` key.
**Why it happens:** The agent has two code paths (structured_output and direct Lambda fallback) with different error shapes.
**How to avoid:** Check for absent `green`/`cheapest` keys as the primary detection. The presence of the recommendation tracks is the success signal; anything else is an error.

### Pitfall 6: AgentCoreStack Not Re-Deployed Before BackendApiStack
**What goes wrong:** Phase 3 adds SSM write to AgentCoreStack but only deploys BackendApiStack. The SSM parameter `/customer-tariff/agent-runtime-arn` does not exist. BackendApiStack deploys, but the Lambda env var `AGENT_RUNTIME_ARN` is a CloudFormation dynamic reference that resolves to an empty or missing SSM value.
**Why it happens:** The two stacks are intentionally decoupled — CDK does not auto-sequence them.
**How to avoid:** Plan must sequence: (1) amend `agentcore_stack.py` with SSM write, (2) `cdk deploy CustomerTariffAgent`, (3) `cdk deploy CustomerTariffApi`.

### Pitfall 7: API Lambda `handler` string Mismatch
**What goes wrong:** CDK sets `handler="handler.handler"` but file is named `api_handler.py` or function is named `main`. Lambda returns `Runtime.ImportModuleError`.
**Why it happens:** `handler="handler.handler"` means `<module_name>.<function_name>` = `handler.py` + `def handler(event, context)`.
**How to avoid:** Confirm file is `api_lambda/handler.py` and function is `def handler(event, context)`. CDK `handler` kwarg must be `"handler.handler"`.

---

## Runtime State Inventory

This is a greenfield phase (new Lambda + new API Gateway). No rename/refactor. No runtime state to migrate.

**SKIPPED** — not applicable to Phase 3 (new resource creation, no string substitution).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.x (local) | CDK synth + offline tests | ✓ | 3.9.6 (host), 3.12 (Lambda target) | — |
| aws-cdk-lib | CDK stack + synth tests | ✓ | 2.250.0 | — |
| aws_cdk.aws_apigatewayv2 | HTTP API construct | ✓ | (in 2.250.0) | — |
| aws_cdk.aws_apigatewayv2_integrations | HttpLambdaIntegration | ✓ | (in 2.250.0) | — |
| boto3 / botocore | API Lambda + smoke tests | ✓ | 1.42.11 / 1.42.11 | — |
| requests | HTTP smoke tests | ✓ | 2.32.5 | curl (manual) |
| pytest / pytest-mock | All tests | ✓ | 8.4.2 / installed | — |
| moto | bedrock-agentcore mocking | ✗ | 5.1.20 (no agentcore backend) | unittest.mock + io.BytesIO |
| AWS account (us-east-1) | Deploy smoke tests | Required at deploy time | — | — |

**Missing dependencies with no fallback:** None that block offline work.
**Missing dependencies with fallback:** moto → unittest.mock (fully viable).

---

## Validation Architecture

> nyquist_validation = true in `.planning/config.json` — this section is required.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 |
| Config file | `pytest.ini` (exists: `testpaths = tests`, markers: `smoke`) |
| Quick run command | `pytest tests/test_backend_api_unit.py -x` |
| Full suite command | `pytest tests/ -x -m "not smoke"` |
| Smoke run command | `API_ENDPOINT=https://... pytest tests/test_backend_api_smoke.py -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEMO-01 / SC-1 | curl to endpoint with any demo persona returns `{green, cheapest}` | smoke | `pytest tests/test_backend_api_smoke.py::test_all_personas_return_recommendations -v` | ❌ Wave 0 |
| DEMO-01 / SC-2 | Invalid customer_id returns 400 with error body | unit | `pytest tests/test_backend_api_unit.py::test_invalid_format_returns_400 -x` | ❌ Wave 0 |
| DEMO-01 / SC-2 | Unknown customer returns 404 with error body | unit + smoke | `pytest tests/test_backend_api_unit.py::test_customer_not_found_returns_404 -x` | ❌ Wave 0 |
| DEMO-01 / SC-2 | Agent timeout returns 504 with friendly message | unit | `pytest tests/test_backend_api_unit.py::test_timeout_returns_504 -x` | ❌ Wave 0 |
| DEMO-01 / SC-3 | Fresh session ID per invocation (uuid4, no module-level state) | unit | `pytest tests/test_backend_api_unit.py::test_fresh_session_id_per_call -x` | ❌ Wave 0 |
| D-13 | Regex `^CUST-\d{3,6}$` rejects malformed IDs | unit | `pytest tests/test_backend_api_unit.py::test_invalid_customer_id_formats -x` | ❌ Wave 0 |
| D-02 | Response body is verbatim pass-through (no envelope) | unit | `pytest tests/test_backend_api_unit.py::test_response_passthrough_shape -x` | ❌ Wave 0 |
| CDK | BackendApiStack synthesises with correct resources | synth | `pytest tests/test_backend_api_synth.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_backend_api_unit.py -x` (~2s)
- **Per wave merge:** `pytest tests/ -x -m "not smoke"` (~10s)
- **Phase gate:** Full suite including smoke: `API_ENDPOINT=... pytest tests/ -v`

### Wave 0 Gaps
- [ ] `tests/test_backend_api_unit.py` — covers SC-2, SC-3, D-13, D-02
- [ ] `tests/test_backend_api_synth.py` — covers CDK template assertions
- [ ] `tests/test_backend_api_smoke.py` — covers SC-1, SC-2 (404), live integration
- [ ] `api_lambda/handler.py` — main deliverable (not test infrastructure, but Wave 0 must create this before Wave 1 tests run)

---

## Security Domain

> `security_enforcement` not explicitly set to false; treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | D-08: no auth for demo |
| V3 Session Management | Yes (limited) | D-11: fresh uuid4() per invocation; no session persistence |
| V4 Access Control | No | Open endpoint by design (D-08) |
| V5 Input Validation | Yes | `^CUST-\d{3,6}$` regex on customer_id before any downstream call (D-13) |
| V6 Cryptography | No | No secrets handled; ARN passed via env var |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Customer ID injection / path traversal | Tampering | `^CUST-\d{3,6}$` regex (D-13) — rejects anything other than digits after CUST- |
| Session fixation / bleed | Tampering / Info Disclosure | Fresh `uuid.uuid4()` per invocation (D-11) |
| Unbounded agent invocation cost | DoS | No auth + open endpoint; mitigated by Lambda concurrency limits at account level; API keys deferred |
| Verbose error messages exposing internals | Info Disclosure | Error bodies use friendly messages only; no stack traces, no raw exception strings in responses |
| IAM over-privilege | Elevation of Privilege | `bedrock-agentcore:InvokeAgentRuntime` scoped to specific runtime ARN only |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | API Gateway HTTP API integration timeout is 29s (not 30s) | Q4 / Timeout handling | If limit is 30s, the 25s boto timeout gives correct 5s buffer regardless; low risk |
| A2 | `BedrockAgentCoreApp` always returns 200 HTTP status from the container; customer-not-found manifests as body content, not HTTP error | Q3 / Q5 | If AgentCore returns non-200 for agent errors, the `response["response"]` may be empty; must add `statusCode != 200` check in handler |
| A3 | AgentCore Runtime is only available in us-east-1 for this account | Environment / Regional | Already established in Phase 2 — carried forward |
| A4 | `response["response"].read()` is safe for up to ~100 KB JSON bodies | Q3 | Agent response is small JSON (~200 bytes); no risk in practice |

**If this table is empty:** All claims were verified. The 4 entries above are minor edge cases documented for awareness.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `aws-cdk-lib/aws_apigatewayv2_alpha` (alpha package) | `aws-cdk-lib/aws_apigatewayv2` (stable) | CDK v2 GA | No alpha package needed; import path changed |
| REST API (v1) for Lambda proxy | HTTP API (v2) with `HttpLambdaIntegration` | CDK v2 era | Cheaper, faster cold start, built-in CORS; payload format v2.0 |
| `Fn.import_value` cross-stack | SSM Parameter cross-stack | Phase 2 decision | Avoids CloudFormation export lock (Pitfall 5) |

---

## Open Questions

1. **Agent response `statusCode` for customer-not-found**
   - What we know: `invoke_agent_runtime` response includes `statusCode` (integer) from the agent container. The agent always returns Python dict from `@app.entrypoint`. `BedrockAgentCoreApp` wraps this into an HTTP response.
   - What's unclear: If the agent's fallback path encounters an exception, does `BedrockAgentCoreApp` return a non-200 statusCode, or always 200 with error body?
   - Recommendation: The plan should add an explicit check: `if response.get("statusCode", 200) != 200: -> 502`. Belt-and-suspenders with the body key check.

2. **Whether `qualifier` parameter is needed for `invoke_agent_runtime`**
   - What we know: `qualifier` is optional in the service model. Phase 2 smoke test does not pass it.
   - What's unclear: Whether a specific qualifier is needed for the default endpoint.
   - Recommendation: Omit `qualifier` (consistent with Phase 2 smoke test pattern). If invocation fails with ResourceNotFoundException, add `qualifier="DEFAULT"`.

---

## Sources

### Primary (HIGH confidence — verified via tool)
- Live Python import: `aws_cdk.aws_apigatewayv2`, `aws_cdk.aws_apigatewayv2_integrations` — class signatures, CDK synth output
- Live botocore service model: `invoke_agent_runtime` input/output shapes, error shapes, service prefix
- Live botocore: exception class MRO for `ReadTimeoutError`, `Config` defaults
- `tests/test_agent_smoke.py` — Phase 2 authoritative invocation pattern
- `agent/agent.py` — `@app.entrypoint` return semantics
- `lambda/handler.py` — validation regex, ValueError cases
- `infrastructure/agentcore_stack.py`, `infrastructure/foundation_stack.py` — SSM pattern
- AWS IAM reference: `list_amazonbedrockagentcore.html` — `bedrock-agentcore:InvokeAgentRuntime` action + ARN format

### Secondary (MEDIUM confidence — official docs)
- AWS docs: `API_InvokeAgentRuntime.html` — HTTP error codes for InvokeAgentRuntime
- AWS docs: `runtime-invoke-agent.html` — response reading pattern (streaming vs JSON)

### Tertiary (LOW confidence — noted as ASSUMED)
- API Gateway HTTP API 29s integration timeout (A1)
- AgentCore always returns 200 for container-level HTTP status (A2)

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all libraries verified via live Python import
- API Gateway CDK pattern: HIGH — CDK synth executed locally, output inspected
- boto3 invoke_agent_runtime: HIGH — service model introspected + Phase 2 smoke test pattern
- Error taxonomy: MEDIUM — boto3 exceptions verified; customer-not-found body inspection is inferred from agent.py code path analysis
- IAM actions: HIGH — AWS IAM reference page fetched and confirmed

**Research date:** 2026-04-24
**Valid until:** 2026-06-01 (stable CDK + boto3; AgentCore API unlikely to change for established operations)

---

## RESEARCH COMPLETE
