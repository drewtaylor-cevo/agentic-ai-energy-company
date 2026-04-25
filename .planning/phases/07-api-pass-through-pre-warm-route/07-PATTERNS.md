# Phase 7: API Pass-Through + Pre-Warm Route - Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 6 (4 modified, 1 possibly modified, 1 optional)
**Analogs found:** 6/6 — every target file has a strong in-repo analog because Phase 7 extends Phase 3 artefacts that already ship

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `api_lambda/handler.py` | Lambda handler / HTTP controller | request-response (API Gateway v2 → Lambda → AgentCore proxy) | `api_lambda/handler.py` itself (Phase 3, in place) | **self-extension** — exact file, additive edits only |
| `infrastructure/constructs/backend_api.py` | CDK L3 construct | synth-time (CloudFormation generation) | `infrastructure/constructs/backend_api.py` itself (Phase 3, in place) | **self-extension** — adds alias + conditional PC to existing construct |
| `infrastructure/backend_api_stack.py` | CDK stack | synth-time | `infrastructure/backend_api_stack.py` itself (Phase 3, in place) | **self-extension** — possibly unchanged (planner decides whether to route context through stack or read at construct level) |
| `tests/test_backend_api_handler.py` | pytest offline unit tests | test (mock boto3 → handler → assert) | `tests/test_backend_api_handler.py` itself (Phase 3, in place) | **self-extension** — +6 functions, reuses existing helpers (`_make_event`, `_make_agent_response`, `@patch("api_lambda.handler._agentcore_client")`) |
| `tests/test_backend_api_synth.py` | pytest CDK synth assertions | test (stack → Template → assert) | `tests/test_backend_api_synth.py` itself (Phase 3, in place) | **self-extension** — +4 functions, reuses `synth_template` fixture pattern but needs a per-test `_synth_with_context()` helper for `-c demo_pc=N` |
| `tests/test_backend_api_smoke.py` | pytest live HTTP smoke | test (requests → live endpoint → assert) | `tests/test_backend_api_smoke.py` itself (Phase 3, in place) | **self-extension** — OPTIONAL per D-15 (runbook is authoritative); if extended, copy `@pytest.mark.parametrize("customer_id", …)` pattern |

**Match quality legend.** All six files are "self-extension" — the existing file IS the analog. This is ideal: the planner references the same-file line ranges and knows exactly where the new code slots in. No cross-module pattern hunting required.

## Pattern Assignments

### `api_lambda/handler.py` (Lambda handler, request-response)

**Analog:** `api_lambda/handler.py` (same file; Phase 3 baseline, 107 lines total)

**Imports pattern (lines 13-21) — already present, NO NEW IMPORTS NEEDED for Phase 7:**

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

Planner note: `ClientError` + `ReadTimeoutError` are already imported, which is exactly what the prewarm branch's `except Exception` + `isinstance(exc, ClientError)` path needs. `uuid` + `json` already imported. No `import` additions required by Phase 7.

**Module-level client construction (lines 23-43) — unchanged, shared by both paths per D-05:**

```python
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# D-13: identical regex to lambda/handler.py line 39 — defense in depth.
_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")

# Injected by CDK (BackendApiConstruct). Empty string fallback keeps import
# working during offline unit tests that patch _agentcore_client.
_AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Module-level client — reused across warm invocations.
# Config(read_timeout=25, connect_timeout=5): fire ReadTimeoutError at 25s,
# leaving a 5s buffer before Lambda's 30s timeout kills the process (D-03).
_agentcore_client = boto3.client(
    "bedrock-agentcore",
    region_name=_REGION,
    config=Config(read_timeout=25, connect_timeout=5),
)
```

**CRITICAL for Phase 7:** Do NOT add any new module-level state (no second client, no additional regex, no helper lambdas at module scope). Pitfall 7 from RESEARCH.md: module-init errors block Provisioned Concurrency initialisation. Every Phase 7 addition lives INSIDE `handler()`.

**Existing `_error()` helper (lines 46-52) — unchanged, NOT USED BY PREWARM:**

```python
def _error(status_code: int, message: str) -> dict:
    """Consistent JSON error body (D-12)."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }
```

Planner note: prewarm branch builds its 204 response inline (`return {"statusCode": 204, "headers": {}, "body": ""}` per Pattern 2) — the 204 response family is intentionally separate from the 400/404/502/504/500 taxonomy owned by `_error()`.

**Existing `handler()` entry + customer_id validation (lines 55-63) — unchanged:**

```python
def handler(event: dict, context) -> dict:
    """API Lambda entry point — GET /recommendations/{customer_id}."""
    # Extract customer_id from HTTP API v2 payload format (pathParameters).
    path_params = event.get("pathParameters") or {}
    customer_id = path_params.get("customer_id", "")

    # D-13: fast-fail on bad format — avoids wasting a 3-5s agent invocation.
    if not _CUSTOMER_ID_PATTERN.match(customer_id):
        return _error(400, "Invalid customer ID format. Use CUST-NNN (3-6 digits).")
```

**→ Phase 7 insertion point #1: AFTER line 63 (`return _error(400, ...)` close), BEFORE line 68 (`session_id = str(uuid.uuid4())`).** The prewarm branch dispatch lives here. A stray `?prewarm=1` with a malformed customer_id still returns 400 because the regex runs first (D-01 / Pitfall 4).

**Existing structured logging style (line 69, 79, 85-87, 90, 97) — JSON-in-message vs `extra=`:**

Phase 3 uses **positional `%s` format strings** for non-structured logs, e.g.:

```python
logger.info("Invoking agent customer_id=%s session_id=%s", customer_id, session_id)
logger.warning("Agent timeout customer_id=%s", customer_id)
logger.error("AgentCore ClientError customer_id=%s code=%s: %s", customer_id, error_code, error_msg)
logger.error("Unexpected error customer_id=%s: %s", customer_id, exc, exc_info=True)
logger.info("Customer not found customer_id=%s body=%s", customer_id, body)
```

Phase 7's new **structured** log lines (`narrative_source`, `prewarm_failed`) use `logger.info(json.dumps({...}))` per RESEARCH.md Pattern 1 rationale + Pitfall 8:

```python
# Phase 7 NEW style for structured logs queryable by Phase 9 eval harness:
logger.info(json.dumps({
    "event": "narrative_source",
    "customer_id": customer_id,
    "narrative_source": narrative_source,
}))
```

**Rationale for JSON-in-message (not `extra=` kwarg):** no Lambda JSON log formatter exists; `extra=` fields are silently dropped. CloudWatch Logs Insights parses JSON-in-`@message` natively. Two log styles coexisting is fine — don't mix within a single event.

**Existing normal-path invoke + body parse (lines 71-77) — receives the marker-strip insertion:**

```python
try:
    response = _agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=_AGENT_RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=json.dumps({"customer_id": customer_id}).encode(),
    )
    body = json.loads(response["response"].read())
except ReadTimeoutError:
    ...
```

**→ Phase 7 insertion point #2: AFTER line 77 (`body = json.loads(...)`), BEFORE the existing line 96 (`if "green" not in body or "cheapest" not in body:` 404 check).** Order matters (Pitfall 3): pop THEN log THEN 404-check. Open Question 2 in RESEARCH.md resolves to "log BEFORE 404 check" — invoke succeeded, narrative_source is observable, log it.

**Existing error taxonomy catches (lines 78-91) — unchanged for normal path:**

```python
except ReadTimeoutError:
    logger.warning("Agent timeout customer_id=%s", customer_id)
    return _error(504, "Recommendation service timed out. Please try again.")
except ClientError as exc:
    error_code = exc.response.get("Error", {}).get("Code", "Unknown")
    error_msg = exc.response.get("Error", {}).get("Message", str(exc))
    logger.error(
        "AgentCore ClientError customer_id=%s code=%s: %s",
        customer_id, error_code, error_msg,
    )
    return _error(502, "Recommendation service error. Please try again.")
except Exception as exc:  # pylint: disable=broad-except
    logger.error("Unexpected error customer_id=%s: %s", customer_id, exc, exc_info=True)
    return _error(500, "Internal server error.")
```

**Pattern the prewarm branch REUSES from this block:**

- `error_code = exc.response.get("Error", {}).get("Code", "Unknown")` — exact ClientError code extraction shape for the `prewarm_failed` log.
- `pylint: disable=broad-except` comment pattern for the broad `except Exception:` (prewarm uses `# noqa: BLE001` per RESEARCH.md Pattern 2; either lint-suppression style is acceptable — planner decides).

**Pattern the prewarm branch INTENTIONALLY DIVERGES from:**

- Does NOT call `_error()` (204 is not an error family).
- Does NOT distinguish `ReadTimeoutError` / `ClientError` / `Exception` into separate `except` clauses — single `except Exception` (D-04 swallow-all). `isinstance(exc, ClientError)` inside that block extracts the error_code when present.

**Existing pass-through return (lines 100-106) — unchanged, narrative fields flow verbatim:**

```python
return {
    "statusCode": 200,
    "headers": {"Content-Type": "application/json"},
    "body": json.dumps(body),
}
```

Planner note: D-08 invariant — after `body.pop("_narrative_source", None)`, `json.dumps(body)` emits the narrative fields (`green.usage_narrative`, `green.call_script`, `cheapest.usage_narrative`, `cheapest.call_script`) byte-identically to what the agent produced. No validation, no reshaping.

**Prewarm 204 response shape (net new — RESEARCH.md Pattern 2):**

```python
return {"statusCode": 204, "headers": {}, "body": ""}
```

Planner note: explicitly include empty `headers` dict and empty `body: ""` to match API Gateway HTTP API v2 proxy integration contract (Anti-Patterns section in RESEARCH.md — some API Gateway contracts reject responses missing `body`). Consistency with `_error()` helper shape (which always includes `headers` + `body`) is the guiding principle.

**Drift between analog and new code:**

1. **New structured-log style** — Phase 3 uses `logger.info("msg customer_id=%s", cid)`; Phase 7 adds `logger.info(json.dumps({"event": ..., "customer_id": ..., ...}))` for the two new queryable events. The planner should call this out in the plan docs so reviewers don't flag it as inconsistency.
2. **New `except Exception` with error_code extraction** — Phase 3's `except Exception` path (line 89) uses `logger.error(..., exc_info=True)`; Phase 7's prewarm `except Exception` uses `logger.warning(json.dumps({...}))` WITHOUT `exc_info` (traceback would bloat the log record and isn't Phase 9-queryable). Intentional divergence.
3. **New branch dispatch** — the only control-flow addition. Every other change is an inline insertion into the existing linear flow.

---

### `infrastructure/constructs/backend_api.py` (CDK L3 construct, synth-time)

**Analog:** `infrastructure/constructs/backend_api.py` (same file; Phase 3 baseline, 116 lines total)

**Imports pattern (lines 15-21) — one likely addition:**

```python
import aws_cdk as cdk
from aws_cdk import BundlingOptions, Duration
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integ
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct
```

**Phase 7 addition:** may need `from aws_cdk import aws_lambda as lambda_` to expose `lambda_.VersionOptions` if the planner chooses to set `current_version_options` explicitly (RESEARCH.md Pattern 3 shows this). The `lambda_` alias is already imported, so no new top-level import is required — just `lambda_.VersionOptions(...)`.

**Existing Lambda function construction (lines 43-67) — unchanged, gains optional `current_version_options` per RESEARCH.md Pattern 3:**

```python
fn = lambda_.Function(
    self,
    "TariffApiLambda",
    function_name="tariff-api",
    runtime=lambda_.Runtime.PYTHON_3_12,
    handler="handler.handler",
    code=lambda_.Code.from_asset(
        "api_lambda",
        bundling=BundlingOptions(
            image=lambda_.Runtime.PYTHON_3_12.bundling_image,
            command=[
                "bash", "-c",
                "pip install -r requirements.txt -t /asset-output"
                " && cp -au . /asset-output",
            ],
        ),
    ),
    timeout=Duration.seconds(30),
    memory_size=256,
    environment={
        "AGENT_RUNTIME_ARN": agent_runtime_arn,
        "LOG_LEVEL": "INFO",
    },
    description="Phase 3: proxies GET /recommendations/{customer_id} to AgentCore",
)
```

Planner note: `current_version_options` is OPTIONAL. The default (`RemovalPolicy.DESTROY`) is correct for Phase 7 — old versions cleaned up on supersession, avoiding the 75 GB code-storage account limit (RESEARCH.md Pattern 3 gotcha). Setting it explicitly is documentation, not functional. Recommend NOT setting it to minimise diff surface unless the planner wants an audit-trail description.

**→ Phase 7 insertion point #1: AFTER line 86 (`fn.add_to_role_policy(...)` closing paren), BEFORE line 88 (`# HTTP API v2 with allow-all CORS (D-09).`).** The `demo_pc` context read + `fn.add_alias("live", ...)` block lives here. IAM policy is unchanged — alias inherits the function's execution role.

**Existing IAM policy statement (lines 77-86) — UNCHANGED, reused by the alias:**

```python
fn.add_to_role_policy(
    iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        actions=["bedrock-agentcore:InvokeAgentRuntime"],
        resources=[
            agent_runtime_arn,
            cdk.Fn.join("/", [agent_runtime_arn, "*"]),
        ],
    )
)
```

Planner note: `cdk.Fn.join("/", [agent_runtime_arn, "*"])` produces the sub-resource ARN (`.../runtime/{id}/*` — covers `runtime-endpoint/DEFAULT`). The alias uses the same execution role as `fn`, so this statement is sufficient for both normal and prewarm paths. No IAM change in Phase 7 (confirmed by RESEARCH.md Security Domain + CONTEXT.md Integration Points).

**Existing CDK context reading — NONE IN CURRENT CODEBASE:**

`grep -rn "try_get_context" infrastructure/` is empty (I verified via the three infrastructure files loaded). Phase 7's `self.node.try_get_context("demo_pc")` is a NET NEW pattern in this repo. The planner should follow RESEARCH.md Pattern 4 exactly:

```python
# D-11: read CDK context flag; cast to int with default 0.
# Invalid values (non-numeric, negative) fail at synth with readable error.
raw_pc = self.node.try_get_context("demo_pc")
if raw_pc is None:
    demo_pc = 0
else:
    try:
        demo_pc = int(raw_pc)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid -c demo_pc value: {raw_pc!r}. "
            "Must be a non-negative integer."
        ) from exc
    if demo_pc < 0:
        raise ValueError(
            f"Invalid -c demo_pc value: {demo_pc}. Must be >= 0."
        )
```

**Alias construction — NONE IN CURRENT CODEBASE:**

`grep -rn "add_alias\|ProvisionedConcurrency\|CfnAlias" infrastructure/` is empty. Phase 7's `fn.add_alias("live", provisioned_concurrent_executions=N)` is NET NEW:

```python
# D-09 + D-10: alias ALWAYS created. When demo_pc == 0, add_alias is called
# without provisioned_concurrent_executions (no PC config in CFN).
if demo_pc > 0:
    live_alias = fn.add_alias(
        "live",
        provisioned_concurrent_executions=demo_pc,
    )
else:
    live_alias = fn.add_alias("live")
```

Planner note: `fn.add_alias("live")` defaults `version=fn.current_version` — RESEARCH.md Pattern 3 confirms this is the idiomatic form. Equivalent to `lambda_.Alias(self, "LiveAlias", alias_name="live", version=fn.current_version)` but terser.

**Existing HTTP API + route wiring (lines 89-108) — integration target changes from `fn` to `live_alias`:**

```python
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

# Route: GET /recommendations/{customer_id} (D-10).
api.add_routes(
    path="/recommendations/{customer_id}",
    methods=[apigwv2.HttpMethod.GET],
    integration=integ.HttpLambdaIntegration("RecoIntegration", fn),  # ← CHANGES to live_alias
)
```

**→ Phase 7 modification point: line 107** — change `integ.HttpLambdaIntegration("RecoIntegration", fn)` to `integ.HttpLambdaIntegration("RecoIntegration", live_alias)`. `Alias` extends `IFunction`, accepted directly (RESEARCH.md Pattern 3 CITED reference). This is the ONE existing line that changes; all other construct edits are additions.

**Property accessor + `self._api_endpoint` (lines 110-115) — unchanged:**

```python
self._api_endpoint = api.url

@property
def api_endpoint(self) -> str:
    """API endpoint URL (includes trailing slash)."""
    return self._api_endpoint
```

**Drift between analog and new code:**

1. **Net-new `try_get_context` pattern** — no prior use in the repo. Planner pins the shape exactly as RESEARCH.md Pattern 4 shows; failure messages must match test expectations.
2. **Net-new alias construction** — no prior `add_alias` / `ProvisionedConcurrency` usage. All test assertions in `test_backend_api_synth.py` additions rely on these being present with exact property shapes (`AWS::Lambda::Alias` `Name: "live"`, `ProvisionedConcurrencyConfig.ProvisionedConcurrentExecutions: <N>`).
3. **One-line integration target swap** — the only EXISTING line modified; all other edits are insertions.

---

### `infrastructure/backend_api_stack.py` (CDK stack, synth-time)

**Analog:** `infrastructure/backend_api_stack.py` (same file; Phase 3 baseline, 30 lines total)

**Full existing file — possibly UNCHANGED in Phase 7:**

```python
"""Phase 3 CDK stack — Backend API (Lambda + HTTP API v2).

Reads AgentCore runtime ARN from SSM (written by AgentCoreStack) to avoid
hard CloudFormation export dependencies between stacks (Pitfall 5).
"""
from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from infrastructure.constructs.backend_api import BackendApiConstruct


class BackendApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Read AgentCore runtime ARN from SSM (D-07: avoids CfnOutput export lock).
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

**Planner decision point (Claude's Discretion, CONTEXT.md):** Where does `self.node.try_get_context("demo_pc")` live?

| Option | Stack-level read | Construct-level read |
|--------|------------------|----------------------|
| Where | `BackendApiStack.__init__` reads, passes via kwarg | `BackendApiConstruct.__init__` reads directly |
| Impact on stack | Adds kwarg threading + 5–8 lines | **Zero change — stack stays 30 lines** |
| Impact on construct | Takes new kwarg, no CDK context call | Calls `self.node.try_get_context("demo_pc")` |
| Recommendation | — | **Construct-level** (CONTEXT.md Claude's Discretion + RESEARCH.md Anti-Pattern against thread-through state) |

**Recommendation:** `infrastructure/backend_api_stack.py` is UNMODIFIED. The construct reads context directly. This keeps the stack thin and matches CONTEXT.md's stated preference + RESEARCH.md's anti-pattern against state threading.

**Existing cross-stack wiring pattern (lines 20-22) — carry forward:**

```python
agent_runtime_arn = ssm.StringParameter.value_for_string_parameter(
    self, "/customer-tariff/agent-runtime-arn"
)
```

Planner note: this is the only CDK pattern in this file worth highlighting — SSM-based cross-stack reference avoids `CfnOutput` export locks (D-07, preserved by Phase 7).

**Drift between analog and new code:**

- **Zero drift if construct-level context read is chosen.** File is untouched.
- If stack-level context read is chosen (NOT recommended): `BackendApiStack.__init__` would need `demo_pc = self.node.try_get_context("demo_pc")` + validation + pass via `BackendApiConstruct(..., demo_pc=demo_pc)` kwarg. Adds a second thread of validation surface; rejected.

---

### `tests/test_backend_api_handler.py` (pytest offline unit tests, test data flow)

**Analog:** `tests/test_backend_api_handler.py` (same file; Phase 3 baseline, 178 lines)

**Imports pattern (lines 1-11) — Phase 7 additions noted inline:**

```python
import io
import json
from unittest.mock import MagicMock, patch

import pytest

try:
    from api_lambda.handler import handler
    _CAN_IMPORT = True
    _IMPORT_ERROR = ""
except ImportError as e:
    _CAN_IMPORT = False
    _IMPORT_ERROR = str(e)
```

**Phase 7 test-level imports (inside each new test function, matching Phase 3 style for `ReadTimeoutError` / `ClientError` in lines 113 and 129):**

```python
# Phase 3 existing style — imports INSIDE test functions, not top-level:
from botocore.exceptions import ReadTimeoutError   # inside test_timeout_returns_504
from botocore.exceptions import ClientError         # inside test_client_error_returns_502
```

Phase 7's new tests should follow the SAME style — import `ReadTimeoutError`/`ClientError` inside the test function body, not at module top. Also add `import logging` at module top (needed for `caplog.at_level(logging.INFO, ...)` in narrative_source tests) — this is a new module-level import.

**Existing `pytestmark` skip guard (lines 21-24) — Phase 7 new tests inherit automatically:**

```python
pytestmark = pytest.mark.skipif(
    not _CAN_IMPORT,
    reason="api_lambda.handler import failed: {}".format(_IMPORT_ERROR),
)
```

**Existing event + response helpers (lines 27-38) — REUSED VERBATIM by all 6 new tests:**

```python
def _make_event(customer_id: str) -> dict:
    """Build a minimal HTTP API v2 event with pathParameters."""
    return {"pathParameters": {"customer_id": customer_id}}


def _make_agent_response(body: dict) -> dict:
    """Construct a mock invoke_agent_runtime response (StreamingBody via BytesIO)."""
    return {
        "response": io.BytesIO(json.dumps(body).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }
```

**CRITICAL for Phase 7 prewarm tests:** `_make_event(...)` returns `{"pathParameters": {...}}` with NO `queryStringParameters` key. The prewarm tests must extend this:

```python
# Phase 7 pattern — add queryStringParameters to the base event:
event = _make_event("CUST-001")
event["queryStringParameters"] = {"prewarm": "1"}
```

Do NOT modify `_make_event()` signature (would ripple into 8+ existing tests). Extend on a per-test basis.

**Existing mock client patch decorator pattern (line 44, 57, 86, 97, 110, 126, 143, 155) — ALL 6 Phase 7 tests use this exact decorator:**

```python
@patch("api_lambda.handler._agentcore_client")
def test_valid_customer_success(mock_client, mock_savings_response):
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        mock_savings_response
    )
    result = handler(_make_event("CUST-001"), None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert "green" in body
    assert "cheapest" in body
```

**Existing ReadTimeoutError raise pattern (lines 110-120) — the prewarm ReadTimeoutError test copies this shape:**

```python
@patch("api_lambda.handler._agentcore_client")
def test_timeout_returns_504(mock_client):
    """D-03/D-12: ReadTimeoutError -> 504."""
    from botocore.exceptions import ReadTimeoutError

    mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(
        endpoint_url="https://example.com"
    )
    result = handler(_make_event("CUST-001"), None)
    assert result["statusCode"] == 504
    assert "timed out" in json.loads(result["body"])["error"]
```

**Phase 7 copies the `ReadTimeoutError(endpoint_url="https://example.com")` constructor literally.** Verified by RESEARCH.md — `inspect.signature(ReadTimeoutError.__init__)` accepts `endpoint_url` via `**kwargs`. No signature changes.

**Existing ClientError raise pattern (lines 126-137) — the prewarm ClientError test copies this shape:**

```python
@patch("api_lambda.handler._agentcore_client")
def test_client_error_returns_502(mock_client):
    """D-12: ClientError -> 502."""
    from botocore.exceptions import ClientError

    mock_client.invoke_agent_runtime.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "InvokeAgentRuntime",
    )
    result = handler(_make_event("CUST-001"), None)
    assert result["statusCode"] == 502
    assert "service error" in json.loads(result["body"])["error"]
```

**Phase 7 copies `ClientError({"Error": {"Code": "...", "Message": "..."}}, "InvokeAgentRuntime")` literally.** For the prewarm test, the assertion changes to `statusCode == 204` + `prewarm_logs[0]["error_code"] == "ThrottlingException"` (from `exc.response["Error"]["Code"]`).

**Existing parametrised invalid-id test (lines 70-80) — the prewarm-invalid-id test PIGGYBACKS on the same regex behaviour:**

```python
@pytest.mark.parametrize(
    "bad_id",
    ["NOTVALID", "cust-001", "CUST-1", "CUST-1234567", ""],
)
def test_invalid_customer_id_returns_400(bad_id):
    """D-13: malformed customer_id returns 400 without calling agent."""
    result = handler(_make_event(bad_id), None)
    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "error" in body
    assert "Invalid customer ID format" in body["error"]
```

**Phase 7's `test_prewarm_invalid_customer_id_returns_400` copies this shape** but adds `event["queryStringParameters"] = {"prewarm": "1"}` — the assertion that a `?prewarm=1` + bad customer_id returns 400 (regex runs BEFORE prewarm dispatch per D-01 / Pitfall 4).

**Missing pattern — `caplog` fixture usage:** Phase 3 tests do NOT use `caplog` anywhere. Phase 7 introduces it as a net-new test dependency (provided by pytest core; no new install). RESEARCH.md §Code Examples provides the canonical shape:

```python
# Phase 7 NEW pattern — caplog + structured log filter:
with caplog.at_level(logging.INFO, logger="api_lambda.handler"):
    result = handler(_make_event("CUST-001"), None)

# Filter: JSON-in-message logs start with "{" and contain the event keyword.
narrative_source_logs = [
    json.loads(r.message) for r in caplog.records
    if r.message.startswith("{") and "narrative_source" in r.message
]
assert len(narrative_source_logs) == 1
assert narrative_source_logs[0] == {
    "event": "narrative_source",
    "customer_id": "CUST-001",
    "narrative_source": {"usage_narrative": "model", "call_script": "model"},
}
```

**Logger name:** `"api_lambda.handler"` — verified against line 23 `logger = logging.getLogger(__name__)` where `__name__ == "api_lambda.handler"` in the test harness (`from api_lambda.handler import handler`).

**Existing `conftest.py` fixtures Phase 7 can reuse (tests/conftest.py lines 46-101):**

- `mock_savings_response` — baseline Sarah Chen response WITHOUT narrative fields; Phase 7 `test_narrative_pass_through_marker_absent` can use this as-is.
- `mock_marcus_response`, `mock_elena_response` — other personas; useful for parametrised variants if planner adds them.
- `mock_agent_invoke_response` — pre-wrapped BytesIO; less useful than inline `_make_agent_response()` because it's fixture-bound to `mock_savings_response` (no narrative fields).
- `mock_trackinfo` (lines 131-145) — Phase 6 fixture with narrative fields; baseline text the Phase 7 planner can borrow for the `test_narrative_pass_through` body construction but may also inline the exact body per the test's expected shape.

**Fixture reuse decision (planner):** For `test_narrative_pass_through`, inline the test body (agent body with `_narrative_source` marker) — matches RESEARCH.md Code Example and keeps the test self-documenting. For `test_narrative_pass_through_marker_absent`, reuse `mock_savings_response` fixture (already marker-free). For prewarm happy-path, reuse `mock_savings_response`.

**Drift between analog and new code:**

1. **Net-new `caplog` dependency** — Phase 3 tests never use it; Phase 7 introduces it for 3 of the 6 new tests (the ones asserting log shape). `caplog` is pytest-native, no `requirements-dev.txt` change.
2. **Net-new `logging` import at module top** — needed for `caplog.at_level(logging.INFO, ...)`. Tiny addition.
3. **Net-new `queryStringParameters` event key** — 4 of the 6 new tests add this key. `_make_event()` helper signature stays untouched.

---

### `tests/test_backend_api_synth.py` (pytest CDK synth assertions, test data flow)

**Analog:** `tests/test_backend_api_synth.py` (same file; Phase 3 baseline, 149 lines)

**Imports pattern (lines 1-22) — Phase 7 adds `Match` if needed, otherwise unchanged:**

```python
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

try:
    from infrastructure.backend_api_stack import BackendApiStack
    _CAN_IMPORT = True
    _IMPORT_ERROR = ""
except ImportError as e:
    _CAN_IMPORT = False
    _IMPORT_ERROR = str(e)

pytestmark = pytest.mark.skipif(
    not _CAN_IMPORT,
    reason="BackendApiStack import failed: {}".format(_IMPORT_ERROR),
)
```

RESEARCH.md Code Example imports `Match` (`from aws_cdk.assertions import Template, Match`). Phase 7 may or may not need `Match` depending on the planner's assertion strategy. If using `has_resource_properties` with dict literals only, `Match` is unneeded. If using `Match.object_like(...)` for partial matches on nested dicts, add the import. Recommend keeping minimal — the four Phase 7 assertions in D-14 all work with dict literals and raw-template traversal.

**Existing `synth_template` fixture pattern (lines 25-33) — needs a Phase 7 variant:**

```python
@pytest.fixture(scope="module")
def synth_template():
    app = cdk.App()
    stack = BackendApiStack(
        app,
        "TestBackendApiStack",
        env=cdk.Environment(region="us-east-1", account="123456789012"),
    )
    return Template.from_stack(stack)
```

**Phase 7 NEW helper — per-test variant that accepts `demo_pc` context (RESEARCH.md Code Example):**

```python
# Phase 7: module-scope fixture doesn't work because demo_pc varies per test.
# Use a plain helper function called inside each test, not a fixture.
def _synth_with_context(demo_pc: int | None = None) -> Template:
    """Synth BackendApiStack with optional -c demo_pc=N context override."""
    ctx = {"demo_pc": demo_pc} if demo_pc is not None else {}
    app = cdk.App(context=ctx)
    stack = BackendApiStack(
        app, "TestBackendApiStack",
        env=cdk.Environment(region="us-east-1", account="123456789012"),
    )
    return Template.from_stack(stack)
```

**Key drift:** the existing `synth_template` fixture is `scope="module"` (synthesised ONCE per module). Phase 7 needs per-test synth because `demo_pc` differs. The helper is a plain function, not a fixture — called inside each PC-related test. The existing fixture stays for non-PC-dependent tests.

**Existing `has_resource_properties` assertion shape (lines 51-56, 59-68, 71-76, 79-88, 91-100, 103-112) — Phase 7 copies this literal shape:**

```python
def test_has_route(synth_template):
    """Route key must be GET /recommendations/{customer_id} (D-10)."""
    synth_template.has_resource_properties(
        "AWS::ApiGatewayV2::Route",
        {"RouteKey": "GET /recommendations/{customer_id}"},
    )

def test_lambda_runtime_and_handler(synth_template):
    """Lambda must use Python 3.12, handler.handler entry point, tariff-api name."""
    synth_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.12",
            "Handler": "handler.handler",
            "FunctionName": "tariff-api",
        },
    )
```

**Phase 7 `test_alias_live_exists` copies this pattern** with `"AWS::Lambda::Alias"` + `{"Name": "live"}`. Per RESEARCH.md Code Example:

```python
def test_alias_live_exists():
    """D-09/D-10: alias named 'live' tracking the Lambda's current version."""
    template = _synth_with_context(demo_pc=0)
    template.has_resource_properties(
        "AWS::Lambda::Alias",
        {"Name": "live"},
    )

def test_pc_present_when_demo_pc_set():
    """D-11: demo_pc=1 attaches ProvisionedConcurrencyConfig(1)."""
    template = _synth_with_context(demo_pc=1)
    template.has_resource_properties(
        "AWS::Lambda::Alias",
        {
            "Name": "live",
            "ProvisionedConcurrencyConfig": {
                "ProvisionedConcurrentExecutions": 1,
            },
        },
    )
```

**Existing `to_json()` raw-template traversal pattern (lines 115-128) — reused for `test_integration_targets_alias` + `test_pc_absent_when_demo_pc_zero`:**

```python
def test_has_iam_policy_with_invoke_agent_runtime(synth_template):
    """IAM policy must include bedrock-agentcore:InvokeAgentRuntime."""
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

**Phase 7's `test_integration_targets_alias` and `test_pc_absent_when_demo_pc_zero` follow this `to_json()` + loop idiom** (RESEARCH.md Code Example). The `has_resource_properties` API only asserts properties are PRESENT, not ABSENT — hence the raw traversal for the absence assertion:

```python
def test_pc_absent_when_demo_pc_zero():
    """D-11: demo_pc=0 leaves alias without ProvisionedConcurrencyConfig."""
    template = _synth_with_context(demo_pc=0)
    template_json = template.to_json()
    aliases = [
        r for r in template_json["Resources"].values()
        if r.get("Type") == "AWS::Lambda::Alias"
    ]
    assert len(aliases) == 1
    assert "ProvisionedConcurrencyConfig" not in aliases[0]["Properties"], (
        "Expected no PC config when demo_pc=0"
    )

def test_integration_targets_alias():
    """D-09: HttpLambdaIntegration IntegrationUri references the alias ARN, not $LATEST."""
    template = _synth_with_context(demo_pc=0)
    template_json = template.to_json()
    integrations = [
        r for r in template_json["Resources"].values()
        if r.get("Type") == "AWS::ApiGatewayV2::Integration"
    ]
    assert len(integrations) == 1
    integ_uri = integrations[0]["Properties"].get("IntegrationUri")
    alias_logical_ids = [
        logical_id
        for logical_id, r in template_json["Resources"].items()
        if r.get("Type") == "AWS::Lambda::Alias"
    ]
    assert alias_logical_ids, "No AWS::Lambda::Alias in template"
    import json as _json
    assert any(
        alias_id in _json.dumps(integ_uri)
        for alias_id in alias_logical_ids
    ), f"IntegrationUri does not reference alias: {integ_uri}"
```

**Existing cross-stack test pattern (lines 131-148) — reference for re-synthesising a stack inside a test:**

```python
def test_agentcore_stack_has_ssm_parameter():
    """AgentCoreStack must write /customer-tariff/agent-runtime-arn to SSM (D-07)."""
    from infrastructure.agentcore_stack import AgentCoreStack

    app = cdk.App()
    stack = AgentCoreStack(
        app,
        "TestAgentCoreSSM",
        env=cdk.Environment(region="us-east-1", account="123456789012"),
    )
    template = Template.from_stack(stack)
    template.has_resource_properties(
        "AWS::SSM::Parameter",
        {
            "Name": "/customer-tariff/agent-runtime-arn",
            "Type": "String",
        },
    )
```

**Planner note:** this is the existing prior-art for "synthesise a fresh stack inside a test function" — exactly what `_synth_with_context()` does for Phase 7. The pattern already exists in the file; Phase 7's helper is a parameterised extraction of it.

**Drift between analog and new code:**

1. **Net-new per-test context helper `_synth_with_context()`** — existing module-scope `synth_template` fixture can't carry `demo_pc` variance. Helper is additive; existing fixture stays for non-PC tests.
2. **Net-new `cdk.App(context={"demo_pc": N})` kwarg usage** — no prior use in this file. Verified by RESEARCH.md as the correct CDK API shape.
3. **Net-new `AWS::Lambda::Alias` + `ProvisionedConcurrencyConfig` resource types** — tests are defensive against CFN schema changes; assertions use dict-literal shapes that match CFN documented property names exactly.

---

### `tests/test_backend_api_smoke.py` (pytest live HTTP smoke, test data flow) — OPTIONAL

**Analog:** `tests/test_backend_api_smoke.py` (same file; Phase 3 baseline, 85 lines)

**Per D-15:** Live smoke closeout gate is a DOCUMENTED RUNBOOK (`curl` + `aws logs filter-log-events` + `jq`), NOT pytest. Extending `test_backend_api_smoke.py` with a prewarm smoke test is OPTIONAL.

**If the planner chooses to add a prewarm smoke test, the analog to copy is (lines 25-38):**

```python
@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_all_personas_return_recommendations(customer_id):
    """SC-1: GET /recommendations/{customer_id} returns 200 with green + cheapest."""
    r = requests.get(
        f"{BACKEND_API_URL}/recommendations/{customer_id}", timeout=60
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "green" in body, f"Missing green track for {customer_id}"
    assert "cheapest" in body, f"Missing cheapest track for {customer_id}"
```

**Phase 7 optional smoke test shape:**

```python
@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_prewarm_returns_204_live(customer_id):
    """D-15 step 2: ?prewarm=1 per persona returns 204."""
    r = requests.get(
        f"{BACKEND_API_URL}/recommendations/{customer_id}?prewarm=1",
        timeout=60,
    )
    assert r.status_code == 204, f"Expected 204 for {customer_id}, got {r.status_code}: {r.text}"
```

**Planner recommendation:** SKIP this optional test. D-15 runbook is authoritative; pytest-ification tempts mocking that hides real prewarm timing. Phase 9's `scripts/prewarm.py` is the eventual automation home.

**Drift between analog and new code:**

- If the smoke test is added: copies the parametrize + `requests.get` + status-code-assert pattern verbatim.
- If skipped (recommended): zero drift; file is untouched in Phase 7.

---

## Shared Patterns

### Pattern S-1: Structured CloudWatch logging via `logger.info(json.dumps({...}))`

**Source (anti-analog, net new in this file):** no prior use in `api_lambda/handler.py`. Phase 3 uses `logger.info("msg %s=%s", a, b)` positional-format style.

**Apply to:** the two new Phase 7 log lines in `api_lambda/handler.py`:
1. `narrative_source` INFO log (D-07, normal-path ONLY, before the 404 check).
2. `prewarm_failed` WARNING log (D-04, prewarm-path only, inside `except Exception`).

**Canonical shape:**

```python
logger.info(json.dumps({
    "event": "narrative_source",
    "customer_id": customer_id,
    "narrative_source": narrative_source,  # {"usage_narrative": ..., "call_script": ...} OR None
}))

logger.warning(json.dumps({
    "event": "prewarm_failed",
    "customer_id": customer_id,
    "error_code": error_code,   # from exc.response["Error"]["Code"] if ClientError, else type(exc).__name__
    "error": str(exc),          # secondary field — v3.0 PII review flag (Pitfall 5)
}))
```

**Rationale (carry forward into plan):**

- CloudWatch Logs Insights parses JSON-in-`@message` natively: `filter @message like /narrative_source/` + `fields @message`.
- Phase 3 positional-format logs stay unchanged — don't retrofit.
- Don't mix `extra=` kwarg style with JSON-in-message for the same log event (Pitfall 8).

### Pattern S-2: Phase 3 pass-through invariant (D-02) + Phase 7 one-line deviation (D-06)

**Source:** `api_lambda/handler.py` lines 100-106 (return block).

**Apply to:** `api_lambda/handler.py` normal-path return — the only line added between invoke and return is `body.pop("_narrative_source", None)`.

**Canonical shape:**

```python
body = json.loads(response["response"].read())              # existing line 77
narrative_source = body.pop("_narrative_source", None)      # NEW line (D-06)
logger.info(json.dumps({                                     # NEW lines (D-07)
    "event": "narrative_source",
    "customer_id": customer_id,
    "narrative_source": narrative_source,
}))
# ... existing 404 check at line 96 ...
return {
    "statusCode": 200,
    "headers": {"Content-Type": "application/json"},
    "body": json.dumps(body),                                # existing line 105, narrative fields flow verbatim
}
```

**Rationale:** Phase 3 D-02 locks "API Lambda never enriches, wraps, or reshapes the agent response." Phase 7 D-06 adds exactly one exception — stripping an internal marker. `json.dumps(body)` on the remaining dict preserves narrative fields byte-identically.

### Pattern S-3: Offline test isolation via `@patch("api_lambda.handler._agentcore_client")`

**Source:** every Phase 3 offline test in `tests/test_backend_api_handler.py` (lines 44, 57, 86, 97, 110, 126, 143, 155).

**Apply to:** all 5 of the 6 Phase 7 tests that need `invoke_agent_runtime` mocked. Only `test_prewarm_invalid_customer_id_returns_400` skips the patch (regex rejects before invoke).

**Canonical shape:**

```python
@patch("api_lambda.handler._agentcore_client")
def test_xxx(mock_client, ...):
    # Happy path:
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_body)
    # OR error paths (Phase 7 reuses these literal shapes):
    mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(endpoint_url="https://example.com")
    mock_client.invoke_agent_runtime.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "InvokeAgentRuntime",
    )
    result = handler(event, None)
```

**Rationale:** the `_agentcore_client` module-level variable is the dependency-injection seam. Patching it isolates the handler from AWS. The Phase 3 fixture pattern (`_make_event`, `_make_agent_response`, `mock_*_response` fixtures in `conftest.py`) covers every Phase 7 need without extension.

### Pattern S-4: CDK synth test via `Template.from_stack(stack)` + `has_resource_properties`

**Source:** `tests/test_backend_api_synth.py` — Phase 3 pattern for assertion (lines 51-56) and fixture (lines 25-33).

**Apply to:** all 4 Phase 7 CDK synth assertions (D-14).

**Canonical shape (positive assertion):**

```python
template = _synth_with_context(demo_pc=N)  # per-test helper (Phase 7 new)
template.has_resource_properties(
    "AWS::Lambda::Alias",
    {
        "Name": "live",
        "ProvisionedConcurrencyConfig": {"ProvisionedConcurrentExecutions": N},
    },
)
```

**Canonical shape (negative / structural traversal):**

```python
template_json = template.to_json()
aliases = [r for r in template_json["Resources"].values() if r.get("Type") == "AWS::Lambda::Alias"]
assert "ProvisionedConcurrencyConfig" not in aliases[0]["Properties"]
```

**Rationale:** `has_resource_properties` can't assert absence of a property. The `to_json()` traversal is Phase 3's prior-art (line 117) and extends cleanly.

### Pattern S-5: Skip-guard on failed import (defensive)

**Source:** `tests/test_backend_api_handler.py` lines 13-24 and `tests/test_backend_api_synth.py` lines 11-22.

**Apply to:** no changes — Phase 7 tests inherit the module-level `pytestmark` guard automatically.

**Canonical shape:**

```python
try:
    from api_lambda.handler import handler       # OR from infrastructure.backend_api_stack import BackendApiStack
    _CAN_IMPORT = True
    _IMPORT_ERROR = ""
except ImportError as e:
    _CAN_IMPORT = False
    _IMPORT_ERROR = str(e)

pytestmark = pytest.mark.skipif(
    not _CAN_IMPORT,
    reason="api_lambda.handler import failed: {}".format(_IMPORT_ERROR),
)
```

**Rationale:** keeps the test suite green on developer machines missing Python path setup. Phase 7 adds tests to these files; the existing guard covers them.

## No Analog Found

| Target Behaviour | Role | Data Flow | Reason |
|------------------|------|-----------|--------|
| `self.node.try_get_context("demo_pc")` + int/range validation | CDK context read | synth-time | Net new — no prior `try_get_context` use anywhere in `infrastructure/`. Follow RESEARCH.md Pattern 4 verbatim. |
| `fn.add_alias("live", provisioned_concurrent_executions=N)` | CDK alias + PC | synth-time | Net new — no prior `add_alias` / `Alias` / `ProvisionedConcurrencyConfiguration` use. Follow RESEARCH.md Pattern 3 + Standard Stack §Alternatives Considered. |
| `caplog.at_level(logging.INFO, logger="api_lambda.handler")` + JSON-in-message filter | pytest log assertion | test-time | Net new — Phase 3 tests never assert on log output. Follow RESEARCH.md §Code Examples → `test_narrative_pass_through`. |
| `event["queryStringParameters"] = {"prewarm": "1"}` event builder extension | test fixture variant | test-time | Net new — `_make_event` only builds `pathParameters`. Extend per-test; do not modify the shared helper. |
| `cdk.App(context={"demo_pc": N})` kwarg in synth tests | CDK app context override | synth-time / test-time | Net new — Phase 3 synth tests use bare `cdk.App()`. Wrap in `_synth_with_context()` helper. |
| `_synth_with_context()` per-test helper | pytest helper | test-time | Net new — existing `synth_template` fixture is module-scoped; PC tests need per-test synth. |

All six "no analog" gaps are covered by explicit code excerpts in RESEARCH.md (Patterns 1–4 + §Code Examples). The planner can copy those excerpts directly into `<action>` blocks with high confidence — they are all [VERIFIED] against the botocore service model or [CITED] against AWS CDK v2 Python docs.

## Metadata

**Analog search scope:** `api_lambda/`, `infrastructure/`, `tests/` — all Phase 3 carry-forward files read in full.
**Files scanned:** 7 (handler.py, backend_api.py, backend_api_stack.py, test_backend_api_handler.py, test_backend_api_synth.py, test_backend_api_smoke.py, conftest.py).
**Pattern extraction date:** 2026-04-25.

**Key finding:** every Phase 7 target file IS its own analog — Phase 7 extends Phase 3 artefacts rather than introducing new files. The 6 "no analog" rows are all for narrow NET-NEW sub-patterns (alias + PC, context reading, caplog log assertions) — all covered by RESEARCH.md verbatim excerpts.

**Planner directive:** every Phase 7 code block references these analog line ranges. When writing `<action>` blocks, link directly to the line numbers here to keep the implementation traceable back to the Phase 3 baseline.

---

*Phase: 07-api-pass-through-pre-warm-route*
*Patterns mapped: 2026-04-25*
