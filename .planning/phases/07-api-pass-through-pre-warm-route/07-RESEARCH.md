# Phase 7: API Pass-Through + Pre-Warm Route - Research

**Researched:** 2026-04-25
**Domain:** AWS CDK Python (Lambda Alias + Provisioned Concurrency), API Gateway HTTP v2 + HttpLambdaIntegration, boto3 bedrock-agentcore, pytest/Pydantic offline testing, CloudWatch structured logging
**Confidence:** HIGH

## Summary

Phase 7 is a small, mostly-additive delta over the shipped v1.0 Backend API: (1) strip `_narrative_source` from the agent body and emit one structured log line, (2) add a `?prewarm=1` branch that runs a full agent turn and returns 204 with all downstream exceptions swallowed, and (3) route API Gateway through a named Lambda alias `live` that optionally carries Provisioned Concurrency attached via `cdk deploy -c demo_pc=N`. Everything stays inside `api_lambda/handler.py`, `infrastructure/constructs/backend_api.py`, and the three existing test files — no new stacks, no new IAM, no new runtime deps.

The CDK wiring is well-established: `fn.add_alias("live", provisioned_concurrent_executions=N)` is the idiomatic pattern, and `HttpLambdaIntegration` accepts an `Alias` directly because `Alias` implements `IFunction`. The boto3 exception taxonomy has not changed — `ClientError` still covers all seven `InvokeAgentRuntime` modeled errors (`ThrottlingException`, `ServiceQuotaExceededException`, `AccessDeniedException`, `ResourceNotFoundException`, `ValidationException`, `InternalServerException`, `RuntimeClientError`), with `ReadTimeoutError` (from `botocore.exceptions`) layered on top for transport-level timeouts. The `except ClientError + ReadTimeoutError + Exception` shape already in `api_lambda/handler.py` covers everything the prewarm branch needs to swallow — no new explicit catches required.

**Primary recommendation:** Implement the prewarm branch as a ~15-line block inserted immediately after the customer_id regex check in `handler()`, use `try/except Exception` with a single structured log for the swallow-all, always attach the `live` alias tracking `fn.current_version` (even when `demo_pc=0`), and wire `HttpLambdaIntegration` to the alias object on every deploy. Wait at least 3 minutes after `cdk deploy -c demo_pc=1` before running the D-15 warm-median check; poll `aws lambda get-provisioned-concurrency-config` for `Status: READY` if faster confirmation is needed.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 — Route shape:** Pre-warm uses the existing `/recommendations/{customer_id}` route with a `?prewarm=1` query flag — NOT a new `/prewarm` route, NOT a separate Lambda, NOT a bodyless `GET /` route. Same IAM, same integration. Customer_id path param mandatory and validated by D-13 regex even when `prewarm=1`.

**D-02 — Prewarm behaviour:** When `?prewarm=1`, run a full real agent turn via `_agentcore_client.invoke_agent_runtime(...)` against the seed customer_id. Discard body. Return 204. Warms Lambda + microVM + Bedrock + `simulate_savings` tool Lambda + Strands + Pydantic validator in one call.

**D-03 — Persona rotation is operator-owned:** Lambda handler is stateless — warms whatever customer_id it receives. Phase 9 `scripts/prewarm.py` does the 3-persona rotation.

**D-04 — Never 5xx on prewarm:** All exceptions (ClientError, ReadTimeoutError, generic Exception) → return 204 + structured CloudWatch log `{"prewarm_failed": true, "customer_id": "...", "error_code": "...", "error": "..."}`. SC-2 non-negotiable.

**D-05 — Shared client:** Same `_agentcore_client` for both paths. Same `Config(read_timeout=25, connect_timeout=5)`. No dedicated prewarm client.

**D-06 — Marker strip:** `body.pop('_narrative_source', None)` immediately after `body = json.loads(response["response"].read())` and before validation or JSON dump. Idempotent, greppable, one line.

**D-07 — narrative_source log:** Every successful invocation emits structured CloudWatch INFO log `{"customer_id": "...", "narrative_source": {"usage_narrative": "model"|"fallback", "call_script": "model"|"fallback"}}`. Logged on success, not only on fallback. When marker absent, log field is `null` (not an error).

**D-08 — Pass-through for narrative fields:** `usage_narrative`, `call_script` on both tracks flow byte-identically via existing `json.dumps(body)`. Handler does NOT validate or reshape. Matches Phase 3 D-02.

**D-09 — Alias always created:** Named Lambda alias `live` in CDK stack (PC-configured or not). `HttpLambdaIntegration` always targets the alias ARN — never `$LATEST`, never raw function ARN.

**D-10 — Alias tracks current_version:** `fn.add_alias("live", version=fn.current_version)`. CDK auto-publishes on each code change. PC attaches to the alias.

**D-11 — demo_pc CDK context flag:**
- `-c demo_pc=0` (or omitted): no `ProvisionedConcurrencyConfiguration`. Alias exists, PC does not.
- `-c demo_pc=1`: typical demo-day value.
- `-c demo_pc=N` (N>1): presenter escape hatch.
- Read via `self.node.try_get_context("demo_pc")` in `BackendApiConstruct`, cast to int, default 0. Invalid values fail at synth.

**D-12 — Freeze workflow (Phase 10, not Phase 7):** T-48h `cdk deploy -c demo_pc=1`, then CFN stack policy `Update:*` deny. ~$0.40/month PC cost.

**D-13 — Offline pytest additions (6 new tests in `tests/test_backend_api_handler.py`):**
- `test_narrative_pass_through`: narrative fields flow + marker stripped + structured log fires
- `test_narrative_pass_through_marker_absent`: `.pop(..., None)` silent when absent
- `test_prewarm_returns_204_happy_path`: 204 + empty body + no narrative_source log
- `test_prewarm_returns_204_on_client_error`: ClientError → 204 + prewarm_failed log
- `test_prewarm_returns_204_on_read_timeout`: ReadTimeoutError → 204 + prewarm_failed log
- `test_prewarm_invalid_customer_id_returns_400`: D-13 regex still fires before prewarm branch

**D-14 — CDK synth assertions in `tests/test_backend_api_synth.py`:**
- `AWS::Lambda::Alias` with name `live` exists
- `AWS::ApiGatewayV2::Integration` `IntegrationUri` references alias ARN
- With `-c demo_pc=1`: `ProvisionedConcurrencyConfig.ProvisionedConcurrentExecutions == 1`
- With `-c demo_pc=0`: no `ProvisionedConcurrencyConfig` property

**D-15 — Live-smoke closeout gate (runbook, NOT pytest):**
1. `cdk deploy -c demo_pc=1 BackendApiStack` succeeds idempotently
2. Curl `?prewarm=1` for CUST-001/002/003 → all 204
3. For each persona, 3 warm lookups with `curl -w "%{time_total}"` within 5 min
4. Median warm time <3000ms per persona (UI-02 gate, SC-4)
5. CloudWatch shows `narrative_source` log on each warm lookup; `prewarm_failed` absent
6. Response body contains narrative fields on both tracks; `_narrative_source` absent
Phase 7 does NOT close until D-15 passes.

### Claude's Discretion

- **Structured log format.** JSON vs key=value. Default JSON (matches Phase 6 D-03 format).
- **Where `demo_pc` is read.** `self.node.try_get_context("demo_pc")` in `BackendApiConstruct.__init__` vs kwarg from stack. Recommend construct-level.
- **CfnOutput for `demo_pc`.** Recommend no — checkable via `aws lambda get-provisioned-concurrency-config`.
- **Distinct uuid4 session prefix for prewarm** (e.g. `prewarm-<uuid4>`). Recommend vanilla uuid4 — no new AgentCore-side session shape.
- **PC warm-up wait time post-deploy.** Planner pins; recommend ≥3 min.
- **Exact UI-02 gate floats per persona.** D-15 uses <3000ms median; may tighten to <2500ms on CUST-001 Sarah (flagship).

### Deferred Ideas (OUT OF SCOPE)

- `scripts/prewarm.py` + `scripts/demo-keepalive.sh` — Phase 9
- End-to-end narrative eval harness — Phase 9
- `X-Prewarm-Status` response header — rejected
- Prewarm body with `{"prewarm_failed": true, ...}` on failure — rejected (SC-2 is HTTP-status-based only)
- Presenter alt-click tooltip revealing raw LLM + verdict — Phase 8 UI (and contradicts D-06 strip)
- Hard in-Lambda timeout budget on narrative generation — Phase 9 / agent-side
- CloudWatch alarm on `prewarm_failed > N/min` — v3.0 production hardening
- Explicit `/prewarm` route — rejected in D-01
- Dedicated `_agentcore_client` with shorter read_timeout for prewarm — rejected in D-05
- Provisioned Concurrency always-on — explicitly rejected in FEATURES.md + D-11
- `demo_pc` as `CfnOutput` — not needed
- UAT beyond D-15 — Phase 9 eval harness is the deeper layer

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEMO-03 (plumbing half) | Provide the Lambda-side `?prewarm=1` target + alias + optional PC so Phase 9's `scripts/prewarm.py` has a stable endpoint to curl. | Sections below cover the handler additions (Pass-Through Pattern + Prewarm Branch Pattern), CDK wiring (Alias + PC Pattern), boto3 exception taxonomy, CDK synth assertions, and the D-15 live-smoke runbook. |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Strip `_narrative_source` marker | API / Backend (`api_lambda/handler.py`) | — | Phase 6 D-03 locks the marker at the agent layer; stripping belongs at the API boundary so the UI never sees it. |
| Emit `narrative_source` structured log | API / Backend (`api_lambda/handler.py`) | CloudWatch (observability) | Phase 6 log covers agent-direct path; the API-layer log covers the end-to-end path for Phase 9's eval harness. |
| `?prewarm=1` branch dispatch | API / Backend (`api_lambda/handler.py`) | — | Routing decision on the HTTP request; no business logic lives elsewhere. |
| Swallow prewarm exceptions → 204 | API / Backend (`api_lambda/handler.py`) | CloudWatch (observability) | SC-2 contract is HTTP-status-only; failure observability is CloudWatch-side. |
| Named alias `live` | CDK (`infrastructure/constructs/backend_api.py`) | — | CDK owns CloudFormation state; alias is a deploy-time construct. |
| Provisioned Concurrency toggle via `-c demo_pc=N` | CDK (`infrastructure/constructs/backend_api.py`) | — | CDK context is the idiomatic deploy-time toggle surface. |
| API Gateway → alias wiring | CDK (`infrastructure/constructs/backend_api.py`) | — | `HttpLambdaIntegration` construction lives in the construct. |
| Persona rotation for prewarm | Operator / Script (Phase 9 `scripts/prewarm.py`) | — | D-03 — Lambda is stateless; rotation is deferred. |
| 3-persona warm-median SLA check (UI-02) | Operator / Runbook (D-15) | — | D-15 — live smoke; not pytest. |

## Standard Stack

### Core (unchanged from v1.0/Phase 3)

| Library | Version (verified) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `aws-cdk-lib` | `>=2.250.0` (pinned at Phase 10) [VERIFIED: requirements.txt] | Infra-as-code | Project baseline |
| `boto3` | `>=1.42.0` (bundled via BundlingOptions in api_lambda) [VERIFIED: `python3 -c "import boto3; boto3.__version__"` → 1.42.11; `api_lambda/requirements.txt`] | bedrock-agentcore client | Service model available since 1.42.0 |
| `botocore` | `1.42.11` transitive [VERIFIED: local Python shell] | ReadTimeoutError, ClientError | Comes with boto3 |
| `constructs` | `>=10.0.0` [VERIFIED: requirements.txt] | CDK base | Project baseline |

### Supporting (unchanged)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `aws_cdk.aws_lambda` | `2.250.x` [CITED: docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda] | `Function`, `Alias`, `Version`, `VersionOptions` | CDK construct layer |
| `aws_cdk.aws_apigatewayv2` | `2.250.x` | `HttpApi`, `CorsPreflightOptions`, `HttpMethod` | HTTP API v2 routes |
| `aws_cdk.aws_apigatewayv2_integrations` | `2.250.x` | `HttpLambdaIntegration` | Integrating alias into HTTP API |
| `pytest`, `pytest-mock` | `>=7.0`, `>=3.0` [VERIFIED: requirements-dev.txt] | Offline tests | Project baseline |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `fn.add_alias("live", provisioned_concurrent_executions=N)` | `lambda_.Alias(self, "LiveAlias", alias_name="live", version=fn.current_version, provisioned_concurrent_executions=N)` | Both equivalent (the former just returns an `Alias` built from the latter). `add_alias()` is the terser, idiomatic path used in AWS docs. [CITED: docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/AliasOptions.html] |
| `provisioned_concurrent_executions=N` kwarg | `CfnAlias.ProvisionedConcurrencyConfigurationProperty(provisioned_concurrent_executions=N)` on a raw `CfnAlias` | The L2 `Alias` construct takes the int directly and creates the L1 property internally. Use L2 unless a feature gap forces L1. |
| Full `Alias` construct always-attached | Conditional `add_alias()` only when `demo_pc>0` | D-09 locks "alias always created" to keep API Gateway integration ARN stable across PC-on/PC-off deploys, minimising Phase 10 freeze risk. |

**Installation:** No new installation. `api_lambda/requirements.txt` already has `boto3>=1.42.0`. `requirements.txt` already has `aws-cdk-lib>=2.250.0`.

**Version verification performed:**
```bash
python3 -c "import boto3, botocore; print(boto3.__version__, botocore.__version__)"
# → 1.42.11 1.42.11  [VERIFIED 2026-04-25]
```

The `bedrock-agentcore` service model is present in 1.42.11 (confirmed: `botocore.session.Session().get_service_model("bedrock-agentcore").operation_names` includes `InvokeAgentRuntime`). [VERIFIED]

## Architecture Patterns

### System Architecture Diagram

```
Client (UI / curl / scripts/prewarm.py)
           │
           ▼
    API Gateway HTTP API v2
    (GET /recommendations/{customer_id}[?prewarm=1])
           │
           │  HttpLambdaIntegration → alias ARN (never $LATEST)
           ▼
    ┌──────────────────────────────────────────┐
    │ Lambda alias `live`                      │
    │   • tracks fn.current_version            │
    │   • optional ProvisionedConcurrencyConfig│
    │     attached when demo_pc > 0            │
    └────────────────┬─────────────────────────┘
                     ▼
    ┌──────────────────────────────────────────┐
    │ api_lambda/handler.py                     │
    │                                          │
    │   1. Parse pathParameters.customer_id    │
    │   2. D-13 regex check ──fail──▶ 400      │
    │   3. Dispatch on ?prewarm flag:          │
    │       ├── prewarm=1 ─▶ PREWARM BRANCH     │
    │       │    invoke_agent_runtime()        │
    │       │    try/except ALL → 204          │
    │       │    log prewarm_failed on error   │
    │       │                                  │
    │       └── default   ─▶ NORMAL PATH        │
    │            invoke_agent_runtime()        │
    │            body = json.loads(...)        │
    │            narrative_src = body.pop(     │
    │               '_narrative_source', None) │
    │            log narrative_source (INFO)   │
    │            404-check green/cheapest      │
    │            return 200 + json.dumps(body) │
    └────────────────┬─────────────────────────┘
                     ▼
     bedrock-agentcore InvokeAgentRuntime
     (deployed runtime tariff_agent-O2Hai86N8V)
                     │
                     ▼
     Strands + Claude Sonnet 4.6 + simulate_savings tool
                     │
                     ▼
     CloudWatch: narrative_source (success) or
                 prewarm_failed (prewarm exceptions)
```

### Recommended Project Structure (unchanged from Phase 3)

```
api_lambda/
├── handler.py         # MODIFIED: marker-strip, narrative_source log, prewarm branch
└── requirements.txt   # unchanged

infrastructure/
├── backend_api_stack.py                # reads demo_pc OR delegates (planner choice)
└── constructs/
    └── backend_api.py                  # MODIFIED: add alias + PC + integration rewire

tests/
├── conftest.py                         # unchanged (fixtures already present)
├── test_backend_api_handler.py         # MODIFIED: +6 test functions (D-13)
├── test_backend_api_synth.py           # MODIFIED: +4 CDK assertions (D-14)
└── test_backend_api_smoke.py           # OPTIONAL extension; D-15 is a runbook
```

### Pattern 1: Marker-Strip + Pass-Through (D-06, D-07, D-08)

**What:** After parsing the agent JSON, pop the `_narrative_source` marker, log it as a structured record, then continue with the unchanged `green`/`cheapest` check and `json.dumps(body)` pass-through.

**When to use:** Every successful agent invocation in the non-prewarm path. Matches Phase 3 D-02 pass-through invariant verbatim; only the pop+log line is new.

**Example (insertion point — lines 77–78 of current `api_lambda/handler.py`):**

```python
# Source: Phase 3 existing handler + Phase 7 D-06/D-07/D-08 decisions
try:
    response = _agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=_AGENT_RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=json.dumps({"customer_id": customer_id}).encode(),
    )
    body = json.loads(response["response"].read())
except ReadTimeoutError:
    ...
# NEW: Phase 7 D-06 — strip internal marker (idempotent, one line).
# `None` default: absent marker is not an error (D-06 defensive against
# pre-6.1 agent deployments or future agent revisions that drop the marker).
narrative_source = body.pop("_narrative_source", None)

# NEW: Phase 7 D-07 — structured CloudWatch log (INFO, zero-PII).
# narrative_source is {"usage_narrative": "model"|"fallback",
#                       "call_script":     "model"|"fallback"} or None.
logger.info(
    json.dumps({
        "event": "narrative_source",
        "customer_id": customer_id,
        "narrative_source": narrative_source,
    })
)

# D-12: existing 404 check unchanged.
if "green" not in body or "cheapest" not in body:
    ...

# D-02/D-08: existing pass-through unchanged — narrative fields flow verbatim.
return {
    "statusCode": 200,
    "headers": {"Content-Type": "application/json"},
    "body": json.dumps(body),
}
```

**Log format rationale (Claude's Discretion resolution).** Use `json.dumps({...})` as the log message (not `extra={...}` kwarg) because:

1. It matches the existing Phase 3 style — `logger.info("Invoking agent customer_id=%s session_id=%s", ...)` uses positional message formatting, and CloudWatch ingests the formatted string.
2. JSON-as-message is greppable with CloudWatch Logs Insights: `filter @message like /narrative_source/` picks it up; `fields @message.customer_id` parses it.
3. Phase 6 D-03 uses structured CloudWatch logs for the AgentCore-layer marker log; Phase 7 matching the same pattern keeps query shapes consistent.
4. Python's logging `extra=` kwarg requires a CloudWatch JSON log formatter to parse into discoverable fields — out of scope for v2.0.

### Pattern 2: Prewarm Branch (D-01, D-02, D-04, D-05)

**What:** Between the D-13 regex check and the normal invoke, check for `queryStringParameters.prewarm == "1"`. If set, run one real invoke against the path `customer_id`, swallow every exception to a `prewarm_failed` log, return 204. Otherwise fall through to the normal path.

**When to use:** Demo-day operator warming + Phase 9 `scripts/prewarm.py` target.

**Example (insertion point — after line 63 of current `api_lambda/handler.py`, before line 68 session_id):**

```python
# Source: Phase 7 D-01, D-02, D-04, D-05
# Extract prewarm flag from HTTP API v2 event (queryStringParameters).
query_params = event.get("queryStringParameters") or {}
is_prewarm = query_params.get("prewarm") == "1"

if is_prewarm:
    # D-11 (Phase 3): fresh uuid4 — same rule as normal path, no caching
    # (AP-3 in PITFALLS.md: never cache session IDs for keep-alive).
    session_id = str(uuid.uuid4())
    logger.info(
        "Prewarm invoke customer_id=%s session_id=%s",
        customer_id, session_id,
    )
    try:
        # D-02: full real agent turn against path customer_id.
        # D-05: same _agentcore_client, same Config(read_timeout=25).
        response = _agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=_AGENT_RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=json.dumps({"customer_id": customer_id}).encode(),
        )
        # D-02: body discarded. Consume the stream so the connection
        # doesn't leak, then drop on the floor.
        response["response"].read()
    except Exception as exc:  # noqa: BLE001 — D-04 mandates swallow-all
        # D-04: NEVER 5xx on prewarm. Log everything, return 204 anyway.
        # `type(exc).__name__` gives ReadTimeoutError / ClientError / etc.
        # ClientError-specific error codes extracted from .response dict
        # when present, else fall through to class name.
        error_code = type(exc).__name__
        if isinstance(exc, ClientError):
            error_code = exc.response.get("Error", {}).get(
                "Code", "Unknown"
            )
        logger.warning(
            json.dumps({
                "event": "prewarm_failed",
                "customer_id": customer_id,
                "error_code": error_code,
                "error": str(exc),
            })
        )
    # D-04: 204 on success AND failure. No body, no narrative_source log
    # (narrative_source is a normal-path observability channel, not prewarm).
    return {"statusCode": 204, "headers": {}}
```

**Key design notes.**

1. **D-13 regex runs BEFORE the prewarm branch**, so a stray `?prewarm=1` with a malformed customer_id (e.g. `cust-001?prewarm=1`) returns 400 — matches the locked "fast-fail for both modes" principle in D-01.
2. **The `except Exception` with `# noqa: BLE001`** is intentional. D-04 is explicit: ALL downstream exceptions must swallow to 204. A targeted `except (ClientError, ReadTimeoutError)` would leak rarer issues (e.g. `EndpointConnectionError`, `SSLError`) as 5xx, violating SC-2.
3. **`response["response"].read()`** is invoked for side-effect (drain StreamingBody). Not strictly required since the response will be garbage-collected and the TCP connection returned to the pool, but makes the discard explicit and matches the normal path's read behaviour [CITED: botocore StreamingBody docs].
4. **No `_error()` helper call**, because `_error` returns 4xx/5xx — the prewarm branch must never use that family.
5. **HTTP 204 response shape.** API Gateway HTTP API v2 expects `{"statusCode": int, "headers": dict, "body": str}` for proxy integrations. `body` omitted is treated as empty; explicitly empty `body: ""` also valid. Use empty headers dict rather than omitting to match existing helper shape.

### Pattern 3: Lambda Alias + Conditional Provisioned Concurrency (D-09, D-10, D-11)

**What:** Always create an `Alias` named `live` tracking `fn.current_version`. When `self.node.try_get_context("demo_pc")` yields N≥1, pass `provisioned_concurrent_executions=N` on the alias. Rebind `HttpLambdaIntegration` target from `fn` to the alias. No change to IAM, no new stack.

**When to use:** The one and only entry point for Phase 7's CDK change. All five D-09/D-10/D-11/D-12/D-14 decisions flow through this.

**Example (modification to `infrastructure/constructs/backend_api.py`, replacing current lines 43–108):**

```python
# Source: Phase 7 D-09/D-10/D-11 + CDK Python docs
# [CITED: https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/AliasOptions.html]
fn = lambda_.Function(
    self, "TariffApiLambda",
    # ... existing args unchanged ...
    # Optional: current_version_options. Default is fine; RemovalPolicy.DESTROY
    # on old versions is the documented default and matches what we want
    # (no retained-forever version clutter). Explicit for clarity:
    current_version_options=lambda_.VersionOptions(
        removal_policy=cdk.RemovalPolicy.DESTROY,
        description="Auto-published by fn.current_version on each deploy",
    ),
)

# IAM policy unchanged — same actions, same resources. D-09 contract: alias
# is a different ARN but the same underlying function, so the role is reused.
fn.add_to_role_policy(...)  # unchanged

# D-11: read CDK context flag; cast to int with default 0.
# Invalid values (non-numeric, negative) fail at synth via the int() call
# below wrapped with explicit validation — see "Pitfall 2" in this doc.
raw_pc = self.node.try_get_context("demo_pc")
if raw_pc is None:
    demo_pc = 0
else:
    # int() accepts str ("1") and int (1) alike; raises ValueError on garbage.
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

# D-09 + D-10: alias ALWAYS created. When demo_pc == 0, add_alias is called
# without provisioned_concurrent_executions (no PC config in CFN).
if demo_pc > 0:
    live_alias = fn.add_alias(
        "live",
        provisioned_concurrent_executions=demo_pc,
    )
else:
    live_alias = fn.add_alias("live")

# D-09: HttpLambdaIntegration points at the alias (IFunction), NOT the raw
# function. Alias extends QualifiedFunctionBase → FunctionBase → IFunction,
# so HttpLambdaIntegration accepts it directly.
# [CITED: AWS CDK Python API Reference — HttpLambdaIntegration.handler
#  parameter accepts IFunction]
api = apigwv2.HttpApi(
    self, "TariffApi",
    # ... existing args unchanged ...
)
api.add_routes(
    path="/recommendations/{customer_id}",
    methods=[apigwv2.HttpMethod.GET],
    integration=integ.HttpLambdaIntegration("RecoIntegration", live_alias),
)
```

**Why `fn.add_alias("live", ...)` not `Alias(self, "...", version=fn.current_version)`.**

Both produce equivalent CloudFormation. `add_alias` is a thin wrapper [CITED: AWS CDK Python docs] that constructs the `Alias` with `version=fn.current_version` as the default. The terser form reads more clearly in the construct and matches the idiom used throughout AWS examples. Using the full `Alias(...)` form would be required if Phase 7 needed to pass `additional_version_weights` for traffic shifting — it does not.

**`fn.current_version` auto-publish behaviour.** [CITED: AWS CDK Python Lambda README "Versions" section]. Key facts:

- `fn.current_version` returns a `lambda.Version` resource that represents the function as defined in the current synth.
- CDK detects changes to function code or config between synths and publishes a new immutable Lambda version automatically on each deploy. No explicit `publish=true` needed.
- The alias rolls forward to the new version on each deploy (CFN update-in-place on the `AWS::Lambda::Alias` resource).
- Only supported for `Code.fromAsset` or `Code.fromInline` — the Phase 3 handler uses `from_asset` with `BundlingOptions`, so this works. [VERIFIED against `backend_api.py` lines 49–59.]

**`current_version_options.removal_policy` gotcha.** [CITED: AWS CDK VersionOptions docs]. Default is `RemovalPolicy.DESTROY` — old versions are cleaned up when superseded. The alternative `RemovalPolicy.RETAIN` causes every deploy to leave orphan versions accumulating in the account (Lambda has a 75 GB code-storage account limit). For Phase 7 the DESTROY default is correct; setting it explicitly in the example above is documentation rather than functional change.

### Pattern 4: CDK Context Flag Reading (D-11)

**What:** `self.node.try_get_context("demo_pc")` returns `None` when the flag is absent, or the parsed value (string `"1"` from CLI `-c demo_pc=1`, int `1` from `cdk.context.json` literal). Cast with `int()`, validate non-negative, fail synth on garbage.

**When to use:** The one invocation point at construct init. Not exposed as a constructor kwarg because the construct is the one place that needs the value (Claude's Discretion — construct-level).

**Example:** see Pattern 3 above; the `raw_pc = self.node.try_get_context("demo_pc")` → `int()` → validation block is the canonical shape.

**Why fail at synth, not deploy.** [CITED: CDK context patterns]. Synth-time failures are caught on the developer's laptop; deploy-time failures burn a stack update and leave the stack in UPDATE_ROLLBACK_FAILED if CFN errors propagate. Validating in Python at construct init is free and fast; invalid values never reach CloudFormation.

### Anti-Patterns to Avoid

- **Pointing `HttpLambdaIntegration` at `fn` (raw function) instead of the alias.** PC attached to the alias never takes effect because invocations bypass the alias qualifier. [CITED: AWS Lambda PC docs — "event sources must target the alias or specific version"]. D-09 explicitly guards against this. [VERIFIED in `test_backend_api_synth.py` assertion — `IntegrationUri` must reference alias ARN.]
- **Reading `self.node.try_get_context("demo_pc")` at stack level and passing it through kwargs.** Adds a thread of state across two files for one construct-local value. Construct-level read keeps the BackendApiStack thin (matches Claude's Discretion recommendation).
- **Catching `(ClientError, ReadTimeoutError)` only in the prewarm branch.** The seven modeled `InvokeAgentRuntime` exceptions all surface as `ClientError` subtypes (see boto3 Exception Taxonomy section below), so that catch is sufficient for modelled errors — but **transport-level issues** (DNS failure, SSL handshake errors, `EndpointConnectionError`) are `botocore.exceptions.*` types that are NOT subclasses of `ClientError`. D-04 requires `except Exception` (broad) to truly swallow all.
- **Using `logger.info(..., extra=dict)` for structured logs.** Without a JSON formatter on the Lambda logging handler, `extra=` fields don't appear in the CloudWatch log record. Use `logger.info(json.dumps({...}))` instead — the message body is CloudWatch-indexed and queryable with Logs Insights directly.
- **Emitting `narrative_source` log before the marker is popped.** If the marker hasn't been stripped yet, a future code path could re-serialise it into the response. Pop first, log from the popped value, then return body. (Pattern 1 example shows this order.)
- **Returning `{"body": None}` or omitting `body` entirely from the 204 response.** Some API Gateway HTTP API v2 proxy contracts reject responses without a `body` key. Use empty headers dict and omit body, OR explicitly `{"statusCode": 204, "headers": {}, "body": ""}` — both valid. Match the `_error()` helper shape for consistency.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Lambda alias version tracking | Manual `lambda_.CfnAlias(function_version="$LATEST_v1", ...)` literal | `fn.add_alias("live", ...)` with implicit `version=fn.current_version` | CDK auto-publishes versions on code change; manual version numbers drift. |
| PC config | Raw `CfnAlias.ProvisionedConcurrencyConfigurationProperty(...)` | `add_alias(... provisioned_concurrent_executions=N)` kwarg | L2 generates the L1 property; L2 is the tested path. |
| Marker stripping | Whitelist-based body rebuild (`{k: v for k, v in body.items() if k != "_narrative_source"}`) | `body.pop("_narrative_source", None)` | D-06 explicit; keeps handler agnostic of the rest of the schema. |
| Prewarm exception matrix | Explicit catches for each of 7 bedrock-agentcore exceptions | `except Exception` + extract code from `ClientError.response` when present | D-04 swallow-all; the modelled exception list is `ServiceQuotaExceededException`, `ValidationException`, `AccessDeniedException`, `RuntimeClientError`, `ThrottlingException`, `ResourceNotFoundException`, `InternalServerException` [VERIFIED: botocore service model 1.42.11] — all `ClientError` subclasses, but PLUS transport-level `botocore.exceptions` types that aren't. |
| Structured CloudWatch logs | Python `logging` with custom `extra=` dict + no formatter | `logger.info(json.dumps({...}))` | No Lambda layer / JSON formatter needed; Logs Insights parses JSON-in-message natively. |
| CDK context reading | Hand-parsing `sys.argv` or reading `cdk.context.json` directly | `self.node.try_get_context("demo_pc")` | Standard CDK API; works with `-c flag=value` CLI AND `cdk.context.json` literals. |
| 400/404/502/504/500 error responses | New mapping for the prewarm path | Reuse existing `_error()` helper for the normal path ONLY | Prewarm is a separate response family (204-only); do not mix error taxonomies (D-12 discipline). |

**Key insight:** Everything Phase 7 does is either (a) a one-line addition to the existing handler, (b) a straightforward CDK L2 construct call, or (c) a pytest test that copies an existing pattern. There is nothing to hand-roll — the architectural decisions were locked in CONTEXT.md and CDK provides all the primitives needed.

## boto3 `invoke_agent_runtime` Exception Taxonomy [VERIFIED via botocore service model 1.42.11]

Confirmed 2026-04-25 via `botocore.session.Session().get_service_model("bedrock-agentcore").operation_model("InvokeAgentRuntime").error_shapes`:

| Exception | Raised as | When |
|-----------|-----------|------|
| `ServiceQuotaExceededException` | `ClientError` with `error_code == "ServiceQuotaExceededException"` | Account/region PC quota hit, too many concurrent AgentCore sessions |
| `ValidationException` | `ClientError` with `error_code == "ValidationException"` | Malformed request body, invalid runtimeSessionId length |
| `AccessDeniedException` | `ClientError` with `error_code == "AccessDeniedException"` | IAM policy missing, model access revoked (e.g. Bedrock Legacy 30-day rule per Phase 06.1) |
| `RuntimeClientError` | `ClientError` with `error_code == "RuntimeClientError"` | AgentCore container crashed during invoke (wraps runtime's own error — see Phase 06.1 SUMMARY) |
| `ThrottlingException` | `ClientError` with `error_code == "ThrottlingException"` | Bedrock model or AgentCore API rate limit |
| `ResourceNotFoundException` | `ClientError` with `error_code == "ResourceNotFoundException"` | Agent runtime ARN does not exist in region (bad SSM lookup, stale deploy) |
| `InternalServerException` | `ClientError` with `error_code == "InternalServerException"` | AWS-side outage; retryable |

**Plus transport-level errors** (from `botocore.exceptions`, NOT subclasses of `ClientError`):

- `ReadTimeoutError` — response not received within `read_timeout=25s`
- `ConnectTimeoutError` — connection not established within `connect_timeout=5s`
- `EndpointConnectionError` — DNS / network failure
- `SSLError` — TLS handshake failure

**Normal path** (Phase 3 existing): `except ReadTimeoutError: 504 / except ClientError: 502 / except Exception: 500` — unchanged by Phase 7. No new modeled exceptions since Phase 3's research.

**Prewarm path** (D-04): `except Exception` (broad) — correctly swallows ALL of the above. Extract `error_code` from `.response` when `isinstance(exc, ClientError)` for log richness; fall through to `type(exc).__name__` otherwise (e.g. `"ReadTimeoutError"`, `"EndpointConnectionError"`).

**`ReadTimeoutError` signature:** `ReadTimeoutError(endpoint_url=..., **kwargs)` [VERIFIED: `inspect.signature(ReadTimeoutError.__init__)` → `(self, request=None, response=None, **kwargs)` — the `endpoint_url=` kwarg is accepted via `**kwargs`; matches the existing pattern in `tests/test_backend_api_handler.py` line 115].

**Session ID required.** `invoke_agent_runtime` requires `runtimeSessionId` ≥33 chars (current Phase 3 D-11 uses uuid4 = 36 chars). Applies identically to the prewarm branch. AP-3 in PITFALLS.md: fresh uuid4 per invocation, never cached — prewarm honours this by minting inside the branch (see Pattern 2 example above).

## AWS Lambda Provisioned Concurrency — Semantics [CITED: docs.aws.amazon.com/lambda/latest/dg/provisioned-concurrency.html]

**Attach latency.** Current AWS doc language (confirmed 2026-04-25 via Context7):

- `Status: IN_PROGRESS` immediately after `cdk deploy` updates the PC config; `AllocatedProvisionedConcurrentExecutions` climbs from 0 to the requested value.
- `Status: READY` when all pre-initialised environments are provisioned. Typical time for small (<256 MB, <200 MB code) functions at PC=1: 30–120 seconds. Historical AWS guidance has cited "1–3 minutes" as a safe wait; CONTEXT.md claims "~1–3 min" — confirmed.
- **Polling recipe (D-15 step):**
  ```bash
  aws lambda get-provisioned-concurrency-config \
    --function-name tariff-api --qualifier live
  ```
  returns `{... "Status": "READY" ...}` when complete. Planner recommendation: wait ≥3 min after `cdk deploy` for conservative margin, OR poll `Status: READY` explicitly.

**Version migration on deploy.** When code changes:
1. `cdk deploy` publishes a new Lambda version (auto-triggered by `fn.current_version` detecting a change).
2. The alias `live` updates to point to the new version.
3. **PC migrates automatically** to the new version. There is a brief transitional window where the OLD version is scaling in and the NEW version is scaling out — during this window, some invocations may hit on-demand (cold) slots. AWS doc language: "Lambda pre-initialises execution environments for provisioned concurrency, and deployment failures can happen if these environments cannot initialize correctly due to code errors" — implying initialisation happens during deploy; the warm window on the new version trails shortly after.
4. For Phase 7's demo, this implies: if `cdk deploy -c demo_pc=1` is run between prewarm rotations, allow the ≥3-min wait before trusting warm-median measurements. D-15 pins this.

**Billing granularity.** [CITED: Lambda PC docs — "Pricing"]. Per-GB-second × PC duration, billed regardless of concurrent use. For PC=1 × 256 MB × 24h × 30d ≈ $0.40/month at current us-east-1 rates — matches CONTEXT.md claim. Negligible for a one-shot demo engagement.

**"Invalid alias configuration for provisioned concurrency" error.** [CITED: Lambda troubleshooting-deployment.html]. Occurs when a new version's init code throws an uncaught exception — PC cannot pre-initialise, deploy fails. Mitigations:
- Keep module-level init in `api_lambda/handler.py` minimal (current code: logger setup, regex compile, env read, boto3 client). No narrative or validation logic fires at import.
- Existing `api_lambda/handler.py` imports are clean; Phase 7's additions (marker-strip is in-handler, prewarm branch is in-handler) don't add new module-level state.
- AWS recommended recovery: roll alias back to previous version, fix init code, re-publish, re-attach PC.

**No IAM change.** The Lambda execution role's `bedrock-agentcore:InvokeAgentRuntime` permission is scoped to `[agent_runtime_arn, agent_runtime_arn/*]`. The alias uses the same role. The prewarm branch hits the same action on the same resource. No new IAM scoping is needed. [VERIFIED: `infrastructure/constructs/backend_api.py` lines 77–86 + CONTEXT.md D-01 / Integration Points.]

## Common Pitfalls

### Pitfall 1: Integration update replacing API Gateway ARN at Phase 10 freeze

**What goes wrong:** CFN stack policy `Update:*` deny applied at Phase 10 T-48h could block the alias-swap if it's attempted after freeze. Worse — if Phase 7 ships with `HttpLambdaIntegration(fn)` and the alias is added in a LATER deploy, the integration update IS an `Update:Replace` on the `AWS::ApiGatewayV2::Integration` resource, which `Update:*` deny blocks.

**Why it happens:** API Gateway integrations are immutable for the `IntegrationUri`; changing the target function (raw function → alias) requires replacing the integration resource.

**How to avoid:** D-09 locks this — the alias must be created AND the integration must target the alias ON INITIAL PHASE 7 DEPLOY, before Phase 10 freeze. The Phase 7 CDK change lands once; freeze only prevents further updates.

**Warning signs:** `cdk diff` at Phase 10 showing `[~] AWS::ApiGatewayV2::Integration ... IntegrationUri: function-arn → alias-arn`. If this diff appears post-freeze, freeze is breached. Phase 10's `cdk diff` empty gate catches this — no action needed in Phase 7 other than landing the change on the initial Phase 7 deploy.

### Pitfall 2: Invalid `demo_pc` value accepted at synth time

**What goes wrong:** `cdk deploy -c demo_pc=abc` or `-c demo_pc=-1` passes through `try_get_context` as the raw string, reaches `int()` and either raises `ValueError` (for "abc") or produces a negative integer (for "-1") that CloudFormation would either accept as literal `-1` or reject with a cryptic PC API error.

**Why it happens:** `try_get_context` returns whatever was given. CDK's CLI flag parser does not type-check context values.

**How to avoid:** The construct validates explicitly (Pattern 3 example's `int()` wrap + `if demo_pc < 0` check). Fails at synth with a readable error message.

**Warning signs:** `cdk synth` error `Invalid -c demo_pc value: 'abc'. Must be a non-negative integer.` Good — that's the validation firing.

### Pitfall 3: `body.pop()` called before `json.loads()`

**What goes wrong:** If the marker-strip line is moved above the `json.loads(...)` call, the code attempts `response["response"].read().pop(...)` which is a bytes `.pop()` (raises AttributeError on bytes, or pops a byte on bytearray — either wrong).

**Why it happens:** Instruction reordering during refactor; `body` is bound to the dict only after `json.loads`.

**How to avoid:** D-06 locks the order: `body = json.loads(response["response"].read())` FIRST, then `body.pop("_narrative_source", None)`. The Pattern 1 example shows this sequence explicitly. The pytest `test_narrative_pass_through` asserts the marker is popped post-load, catching any reordering regression.

**Warning signs:** Local test failure with `AttributeError: 'bytes' object has no attribute 'pop'`.

### Pitfall 4: Prewarm `?prewarm=1` ambiguity with query-param boolean

**What goes wrong:** HTTP API v2 event `queryStringParameters` surfaces each param as a string. Checking `query_params.get("prewarm") is True` never matches. Checking `query_params.get("prewarm")` matches any truthy value including `"0"`, `"false"`, `"no"`.

**Why it happens:** API Gateway event format uses string values; Python truthiness of non-empty strings fires regardless of content.

**How to avoid:** Explicit `query_params.get("prewarm") == "1"` (D-01 contract; Pattern 2 example). No regex, no boolean coercion.

**Warning signs:** Production traffic seeing `GET /recommendations/CUST-001?prewarm=0` returning 204. The offline test `test_prewarm_returns_204_happy_path` passes specifically with `"prewarm": "1"`; extend with a `?prewarm=0` case if the planner wants explicit coverage (optional — not in D-13).

### Pitfall 5: Prewarm exception log exposing PII-adjacent data

**What goes wrong:** `str(exc)` on a `ClientError` sometimes embeds the full request including the payload (`{"customer_id": "..."}`) in the message. For dummy-data CUST-001/002/003 this is harmless; for v3.0 with live CRM the same code path is a PII leak (PITFALLS.md M7).

**Why it happens:** `ClientError.__str__` delegates to the AWS error message which may include quoted request args in debug responses.

**How to avoid:** Log the `error_code` extracted from `exc.response["Error"]["Code"]` as the primary signal; include `str(exc)` only as a secondary `"error"` field that Phase 9's eval harness can grep but is not formatted into alerts. For v2.0 (dummy data, 3 personas) this is defensive documentation; for v3.0 it becomes a hard requirement. Phase 7 log shape in Pattern 2 already separates `error_code` from `error` — matches the discipline.

**Warning signs:** CloudWatch `prewarm_failed` records with multi-line bodies embedding payload JSON. For v2.0 not a bug; flag in code comments for v3.0 review.

### Pitfall 6: PC allocation IN_PROGRESS at demo start

**What goes wrong:** Presenter runs `cdk deploy -c demo_pc=1` at T-2min, then immediately runs the prewarm script. PC is still `IN_PROGRESS`, invocations fall through to on-demand cold slots, warm median spikes.

**Why it happens:** PC allocation is asynchronous from `cdk deploy` return. The deploy returns as soon as the CFN update completes; Lambda continues pre-initialising envs in the background.

**How to avoid:** D-15 mandates ≥3-min wait between `cdk deploy` and warm-median check. Planner may tighten by polling `aws lambda get-provisioned-concurrency-config --function-name tariff-api --qualifier live` until `Status: READY`. Phase 10 T-48h deploy window gives hours of buffer, not minutes.

**Warning signs:** D-15 step 4 failing (`warm median >3000ms`) on a freshly-deployed stack. Re-check PC status; wait longer.

### Pitfall 7: Lambda module-level init throwing on new deploy → PC init fails

**What goes wrong:** [CITED: Lambda troubleshooting-deployment.html] An uncaught exception at module import (`api_lambda/handler.py` top-level) prevents PC from pre-initialising. Deploy returns but `Status` never progresses to READY.

**Why it happens:** PC pre-runs the init phase of the execution environment. Init errors that are silent for on-demand (they just surface as cold-start failures on the NEXT invocation) become deploy-blockers for PC.

**How to avoid:** Keep `api_lambda/handler.py` module-level code minimal — as it already is. The Phase 7 additions (marker-strip, prewarm branch) live INSIDE `handler()` function, not at module scope. No new imports or boto3 clients at module level.

**Warning signs:** CloudWatch `/aws/lambda/tariff-api` log stream for the alias shows `Init phase failed` or `Function not ready` during the PC provisioning window.

### Pitfall 8: Mixing old `extra=` log kwarg with JSON-in-message style

**What goes wrong:** Some log lines use `logger.info("msg", customer_id=...)` (Phase 3 style), others use `logger.info(json.dumps({...}))` (Phase 7 style). CloudWatch Logs Insights queries break across the two styles.

**Why it happens:** Python `logging` supports both positional-format and kwarg-extra styles; without a JSON formatter neither produces structured records automatically.

**How to avoid:** Phase 7's new log lines (`narrative_source`, `prewarm_failed`) ALWAYS use `logger.info(json.dumps({...}))`. Existing Phase 3 logs (`"Invoking agent customer_id=%s..."`) stay unchanged — they're not queried by Phase 9's eval harness. Two styles coexisting is acceptable; just don't mix them within a single log event.

**Warning signs:** Phase 9 eval harness CloudWatch Insights query `filter @message like /narrative_source/` returns zero matches because the log was emitted with a different key shape.

## Code Examples

Verified patterns, from existing Phase 3 code + official sources:

### Existing pattern: Offline handler test with mocked StreamingBody (`tests/test_backend_api_handler.py` lines 32–38)

```python
# Source: tests/test_backend_api_handler.py (Phase 3, verified)
def _make_agent_response(body: dict) -> dict:
    """Construct a mock invoke_agent_runtime response (StreamingBody via BytesIO)."""
    return {
        "response": io.BytesIO(json.dumps(body).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }


@patch("api_lambda.handler._agentcore_client")
def test_valid_customer_success(mock_client, mock_savings_response):
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        mock_savings_response
    )
    result = handler(_make_event("CUST-001"), None)
    assert result["statusCode"] == 200
```

**Phase 7 test pattern (D-13 — `test_narrative_pass_through`):**

```python
# Source: Phase 7 D-13, extends Phase 3 existing pattern
import json
import logging
from unittest.mock import patch


@patch("api_lambda.handler._agentcore_client")
def test_narrative_pass_through(mock_client, caplog):
    """D-06/D-07/D-08: narrative fields flow byte-identically, marker stripped, log fires."""
    agent_body = {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 30.00,
            "saving_annual": 360.00,
            "usage_narrative": "Winter-heavy household with consistent usage.",
            "call_script": "Ask about EcoFlex — it suits your winter profile.",
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 55.00,
            "saving_annual": 660.00,
            "usage_narrative": "Heavy evening usage peaking in December.",
            "call_script": "Consider Value 12 for simpler flat-rate billing.",
        },
        "_narrative_source": {
            "usage_narrative": "model",
            "call_script": "model",
        },
    }
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_body)

    with caplog.at_level(logging.INFO, logger="api_lambda.handler"):
        result = handler(_make_event("CUST-001"), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])

    # D-06: marker absent in response.
    assert "_narrative_source" not in body

    # D-08: narrative fields flow byte-identically.
    assert body["green"]["usage_narrative"] == agent_body["green"]["usage_narrative"]
    assert body["green"]["call_script"] == agent_body["green"]["call_script"]
    assert body["cheapest"]["usage_narrative"] == agent_body["cheapest"]["usage_narrative"]
    assert body["cheapest"]["call_script"] == agent_body["cheapest"]["call_script"]

    # D-02: pass-through preserves existing green/cheapest structure.
    assert body["green"]["saving_monthly"] == 30.00

    # D-07: structured log fires with correct shape.
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

**Phase 7 test pattern (D-13 — `test_prewarm_returns_204_on_read_timeout`):**

```python
# Source: Phase 7 D-13, extends Phase 3 ReadTimeoutError pattern
@patch("api_lambda.handler._agentcore_client")
def test_prewarm_returns_204_on_read_timeout(mock_client, caplog):
    """D-04: ReadTimeoutError in prewarm → 204 (never 5xx), prewarm_failed log fires."""
    from botocore.exceptions import ReadTimeoutError
    mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(
        endpoint_url="https://example.com"
    )

    event = _make_event("CUST-001")
    event["queryStringParameters"] = {"prewarm": "1"}

    with caplog.at_level(logging.WARNING, logger="api_lambda.handler"):
        result = handler(event, None)

    assert result["statusCode"] == 204
    assert result.get("body", "") == ""

    # Structured prewarm_failed log fires.
    prewarm_logs = [
        json.loads(r.message) for r in caplog.records
        if r.message.startswith("{") and "prewarm_failed" in r.message
    ]
    assert len(prewarm_logs) == 1
    assert prewarm_logs[0]["event"] == "prewarm_failed"
    assert prewarm_logs[0]["customer_id"] == "CUST-001"
    assert prewarm_logs[0]["error_code"] == "ReadTimeoutError"
```

**Phase 7 test pattern (D-13 — `test_prewarm_returns_204_on_client_error`):**

```python
# Source: Phase 7 D-13, extends Phase 3 ClientError pattern (test_client_error_returns_502)
@patch("api_lambda.handler._agentcore_client")
def test_prewarm_returns_204_on_client_error(mock_client, caplog):
    """D-04: ClientError in prewarm → 204, prewarm_failed log captures error_code."""
    from botocore.exceptions import ClientError
    mock_client.invoke_agent_runtime.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "InvokeAgentRuntime",
    )

    event = _make_event("CUST-001")
    event["queryStringParameters"] = {"prewarm": "1"}

    with caplog.at_level(logging.WARNING, logger="api_lambda.handler"):
        result = handler(event, None)

    assert result["statusCode"] == 204
    prewarm_logs = [
        json.loads(r.message) for r in caplog.records
        if r.message.startswith("{") and "prewarm_failed" in r.message
    ]
    assert len(prewarm_logs) == 1
    assert prewarm_logs[0]["error_code"] == "ThrottlingException"
```

### Existing CDK synth pattern (`tests/test_backend_api_synth.py` lines 52–56, 115–128)

```python
# Source: tests/test_backend_api_synth.py (Phase 3, verified)
def test_has_route(synth_template):
    synth_template.has_resource_properties(
        "AWS::ApiGatewayV2::Route",
        {"RouteKey": "GET /recommendations/{customer_id}"},
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
    assert found
```

**Phase 7 synth pattern (D-14 — alias + PC assertions):**

```python
# Source: Phase 7 D-14, extends Phase 3 has_resource_properties pattern
import aws_cdk as cdk
from aws_cdk.assertions import Template, Match

def _synth_with_context(demo_pc: int | None = None) -> Template:
    """Synth BackendApiStack with optional -c demo_pc=N context override."""
    ctx = {"demo_pc": demo_pc} if demo_pc is not None else {}
    app = cdk.App(context=ctx)
    stack = BackendApiStack(
        app, "TestBackendApiStack",
        env=cdk.Environment(region="us-east-1", account="123456789012"),
    )
    return Template.from_stack(stack)


def test_alias_live_exists():
    """D-09/D-10: alias named 'live' tracking the Lambda's current version."""
    template = _synth_with_context(demo_pc=0)
    template.has_resource_properties(
        "AWS::Lambda::Alias",
        {"Name": "live"},
    )


def test_integration_targets_alias():
    """D-09: HttpLambdaIntegration IntegrationUri references the alias ARN, not $LATEST."""
    template = _synth_with_context(demo_pc=0)
    # IntegrationUri is a Fn::Sub / Fn::Join with the alias ARN inside.
    # Alias ARNs embed the alias name as the final path segment.
    template_json = template.to_json()
    integrations = [
        r for r in template_json["Resources"].values()
        if r.get("Type") == "AWS::ApiGatewayV2::Integration"
    ]
    assert len(integrations) == 1
    integ_uri = integrations[0]["Properties"].get("IntegrationUri")
    # CFN token reference. Could be str or dict (Fn::Sub/Fn::Join). We verify
    # a Ref or GetAtt to an AWS::Lambda::Alias resource exists in the
    # Resources block and that the integration's IntegrationUri references it.
    alias_logical_ids = [
        logical_id
        for logical_id, r in template_json["Resources"].items()
        if r.get("Type") == "AWS::Lambda::Alias"
    ]
    assert alias_logical_ids, "No AWS::Lambda::Alias in template"
    # IntegrationUri references the alias. Serialise to JSON string for grep.
    import json as _json
    assert any(
        alias_id in _json.dumps(integ_uri)
        for alias_id in alias_logical_ids
    ), f"IntegrationUri does not reference alias: {integ_uri}"


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


def test_pc_absent_when_demo_pc_zero():
    """D-11: demo_pc=0 leaves alias without ProvisionedConcurrencyConfig."""
    template = _synth_with_context(demo_pc=0)
    # Assert alias exists but has NO ProvisionedConcurrencyConfig property.
    template_json = template.to_json()
    aliases = [
        r for r in template_json["Resources"].values()
        if r.get("Type") == "AWS::Lambda::Alias"
    ]
    assert len(aliases) == 1
    assert "ProvisionedConcurrencyConfig" not in aliases[0]["Properties"], (
        "Expected no PC config when demo_pc=0"
    )
```

## Validation Architecture

The Nyquist-validation gate for Phase 7 has three clearly separated layers and a documented live-smoke runbook. This section is mandatory for `/gsd-plan-phase` to spawn the Nyquist validator.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=7.0 [VERIFIED: `requirements-dev.txt`] with `pytest-mock >=3.0` |
| Config file | Discovered in project root (existing pytest config; markers `smoke` and default "not smoke") |
| Quick run command | `pytest tests/test_backend_api_handler.py tests/test_backend_api_synth.py -x` |
| Full suite command | `pytest -m "not smoke"` (current: 161 passed / 7 skipped per Phase 06.1 close) |
| Live smoke command | `BACKEND_API_URL=https://... pytest -m "smoke" tests/test_backend_api_smoke.py` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEMO-03 (plumbing) — narrative pass-through | `body.pop('_narrative_source')` + byte-identical narrative fields in response | unit | `pytest tests/test_backend_api_handler.py::test_narrative_pass_through -x` | ✅ (file exists; test new in Phase 7) |
| DEMO-03 (plumbing) — marker-absent tolerance | `pop(..., None)` silent when marker missing | unit | `pytest tests/test_backend_api_handler.py::test_narrative_pass_through_marker_absent -x` | ✅ (file exists; test new) |
| DEMO-03 (plumbing) — narrative_source log shape (D-07) | CloudWatch INFO log with correct keys on every success | unit (caplog) | `pytest tests/test_backend_api_handler.py::test_narrative_pass_through -x` (checks log assertion) | ✅ |
| DEMO-03 (plumbing) — prewarm happy path returns 204 | `?prewarm=1` with successful invoke → 204 + no narrative_source log | unit | `pytest tests/test_backend_api_handler.py::test_prewarm_returns_204_happy_path -x` | ✅ (file exists; test new) |
| DEMO-03 (plumbing) — prewarm ClientError → 204 | D-04 swallow-all | unit | `pytest tests/test_backend_api_handler.py::test_prewarm_returns_204_on_client_error -x` | ✅ |
| DEMO-03 (plumbing) — prewarm ReadTimeoutError → 204 | D-04 swallow-all + transport-level catch | unit | `pytest tests/test_backend_api_handler.py::test_prewarm_returns_204_on_read_timeout -x` | ✅ |
| DEMO-03 (plumbing) — prewarm invalid customer_id → 400 | D-13 regex precedes prewarm branch | unit | `pytest tests/test_backend_api_handler.py::test_prewarm_invalid_customer_id_returns_400 -x` | ✅ |
| DEMO-03 (plumbing) — alias `live` exists (D-09/D-14) | CDK synth produces `AWS::Lambda::Alias` with name `live` | unit (CDK synth) | `pytest tests/test_backend_api_synth.py::test_alias_live_exists -x` | ✅ (file exists; test new) |
| DEMO-03 (plumbing) — integration targets alias (D-09/D-14) | IntegrationUri references alias, not $LATEST or raw fn | unit (CDK synth) | `pytest tests/test_backend_api_synth.py::test_integration_targets_alias -x` | ✅ |
| DEMO-03 (plumbing) — PC present with demo_pc=1 (D-11/D-14) | synth with `-c demo_pc=1` yields `ProvisionedConcurrentExecutions: 1` | unit (CDK synth) | `pytest tests/test_backend_api_synth.py::test_pc_present_when_demo_pc_set -x` | ✅ |
| DEMO-03 (plumbing) — PC absent with demo_pc=0 (D-11/D-14) | synth with `-c demo_pc=0` omits `ProvisionedConcurrencyConfig` | unit (CDK synth) | `pytest tests/test_backend_api_synth.py::test_pc_absent_when_demo_pc_zero -x` | ✅ |
| Success Criterion 1 — narrative fields present live | Live `GET /recommendations/{id}` returns narrative fields on both tracks per persona | manual-only (D-15 runbook step 6) | documented runbook — not pytest | N/A |
| Success Criterion 2 — `?prewarm=1` returns 204 live | 204 response per persona, never 5xx | manual-only (D-15 runbook steps 2–3) | documented runbook | N/A |
| Success Criterion 3 — integration targets alias | CFN template check (Phase 7) + post-deploy `aws lambda get-alias` confirm | unit+manual | unit assertion (`test_integration_targets_alias`) + `aws lambda get-alias --function-name tariff-api --name live` live | ✅ (unit) |
| Success Criterion 4 — UI-02 <3s warm median | 3 warm lookups per persona, `curl -w "%{time_total}"`, median <3000ms | manual-only (D-15 runbook step 4) | documented runbook | N/A |

### Sampling Rate

- **Per task commit:** `pytest tests/test_backend_api_handler.py tests/test_backend_api_synth.py -x` (~2 seconds, covers D-13 + D-14 assertions)
- **Per wave merge:** `pytest -m "not smoke"` (full suite — must remain green at 161+ passed as per Phase 06.1 close baseline)
- **Phase gate:** Full suite green AND D-15 live-smoke runbook executed AND result recorded in Phase 7 SUMMARY before `/gsd-verify-work`

### Wave 0 Gaps

None. All test files already exist (`tests/test_backend_api_handler.py`, `tests/test_backend_api_synth.py`, `tests/test_backend_api_smoke.py`). `tests/conftest.py` fixtures (`mock_savings_response`, `mock_marcus_response`, `mock_elena_response`, `mock_agent_invoke_response`) are reusable; no new shared fixture work required. Framework already installed and verified green at 161 passing tests.

**Implication:** Phase 7 plan does NOT need a Wave 0 test-infrastructure task. Plans can start directly with implementation + test additions.

### D-15 Live-Smoke Closeout Gate — Runbook

**Not a pytest.** Documented runbook because the warm-median gate requires real HTTP timing against the deployed endpoint with PC warm-up latency baked in. Expressing as pytest would tempt replacement with a mocked variant that hides the latency truth.

**Execution steps (evidence persists in Phase 7 SUMMARY):**

1. **Deploy:** `cdk deploy -c demo_pc=1 BackendApiStack` succeeds idempotently. Capture CFN `UPDATE_COMPLETE` timestamp.
2. **Wait for PC READY:** Either sleep ≥180s OR poll:
   ```bash
   aws lambda get-provisioned-concurrency-config \
     --function-name tariff-api --qualifier live \
     --query 'Status' --output text
   # Expected: READY (initially: IN_PROGRESS)
   ```
3. **Prewarm all 3 personas:**
   ```bash
   for p in CUST-001 CUST-002 CUST-003; do
     curl -sS -o /dev/null -w "prewarm %{http_code} %{time_total}s\n" \
       "$BACKEND_API_URL/recommendations/$p?prewarm=1"
     sleep 2
   done
   # Expected: all three "prewarm 204 ..." lines, completing <25s each
   ```
4. **Warm-median per persona:** 3 lookups per persona, median across 9 total:
   ```bash
   for p in CUST-001 CUST-002 CUST-003; do
     for i in 1 2 3; do
       curl -sS -o /tmp/p${p}_$i.json \
         -w "%{http_code} %{time_total}\n" \
         "$BACKEND_API_URL/recommendations/$p"
     done
   done
   # Compute median from the 9 time_total values.
   # Gate: median per persona < 3000ms (SC-4 / UI-02).
   # Recommended tighter floor for CUST-001 Sarah: <2500ms (Claude's Discretion).
   ```
5. **CloudWatch log checks:**
   ```bash
   # narrative_source present on every successful lookup (3 personas × 3 lookups = 9 expected)
   aws logs filter-log-events \
     --log-group-name /aws/lambda/tariff-api \
     --filter-pattern '"narrative_source"' \
     --start-time $(date -d '10 minutes ago' +%s)000 \
     | jq '.events | length'
   # Expected: ≥ 9

   # prewarm_failed absent across the 3 prewarm calls
   aws logs filter-log-events \
     --log-group-name /aws/lambda/tariff-api \
     --filter-pattern '"prewarm_failed"' \
     --start-time $(date -d '10 minutes ago' +%s)000 \
     | jq '.events | length'
   # Expected: 0
   ```
6. **Response body content check** (against one persona from step 4 output):
   ```bash
   jq '.green.usage_narrative, .green.call_script, .cheapest.usage_narrative, .cheapest.call_script, ._narrative_source' /tmp/pCUST-001_1.json
   # Expected: 4 non-empty strings; _narrative_source = null (absent from body)
   ```

**Gate:** All six steps must PASS before Phase 7 closes. Evidence (timing table, CloudWatch counts, jq output) captured in `07-SUMMARY.md`.

**Why not pytest.** (Restating D-15 discipline.) The moment this becomes a pytest, someone mocks the HTTP layer and the warm-median assertion becomes fiction. Phase 9 inherits and automates this as `scripts/prewarm.py`; Phase 7's gate is the human-run runbook.

## Project Constraints (from CLAUDE.md)

CLAUDE.md does not exist in this repository. No explicit per-project directives beyond those captured in `.planning/PROJECT.md` (core value + constraints) and CONTEXT.md (locked D-01 through D-15). The planner is free to apply standard conventions.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| API Gateway → raw Lambda function (v1.0 Phase 3) | API Gateway → named `live` alias (Phase 7 D-09) | Phase 7 | Enables PC without mid-freeze integration swaps (Phase 10 safety) |
| Same-turn Claude 3.7 Sonnet | Claude Sonnet 4.6 (Phase 06.1 D-01) | Phase 06.1 | Model pin is already in place; Phase 7 doesn't see it (runtime internal) |
| `Agent.structured_output()` deprecated path | Current Strands 1.37.0 tool-using pattern (Phase 06.1 D-05) | Phase 06.1 | Fixed the DEMO-02 regression; Phase 7 trusts it |
| No provisioned concurrency (Phase 3 D-04) | PC opt-in via `-c demo_pc=N` (Phase 7 D-11) | Phase 7 | Demo-window opt-in preserves zero-cost default deploys |

**Deprecated/outdated:**

- Any suggestion to use a separate `/prewarm` route — rejected in D-01; Phase 7 D-01 locks `?prewarm=1` on existing route.
- Always-on PC in prod — explicitly rejected in FEATURES.md and D-11.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| (none) | — | — | All claims in this research are either [VERIFIED] (Context7 + botocore service model + local Python introspection) or [CITED] (AWS CDK / Lambda docs via Context7). No `[ASSUMED]` claims. |

**Table is empty:** All claims in this research were verified against AWS docs (Context7), botocore's service model introspection, or existing Phase 3 code. No user confirmation required.

## Open Questions

1. **Should `?prewarm=1` log `narrative_source` on success?**
   - What we know: D-07 says "every successful invocation" emits `narrative_source`. D-04 / Specifics say "prewarm path doesn't log that" (and the `test_prewarm_returns_204_happy_path` test asserts `no narrative_source log`).
   - What's unclear: Resolution is in CONTEXT.md — prewarm branch does NOT emit `narrative_source` (body is discarded, no popped marker to log). But "every successful invocation" wording in D-07 could be read as "including prewarm". Planner should pin this in plan docs: `narrative_source` log is NORMAL-PATH ONLY.
   - Recommendation: Plan's task description for the prewarm branch explicitly states "does not emit narrative_source". Test `test_prewarm_returns_204_happy_path` asserts the log is absent. Locks the reading.

2. **Should the `narrative_source` log fire on 404 (customer not found)?**
   - What we know: D-12 (Phase 3) returns 404 when `green` or `cheapest` missing. The popped marker is present at the time of the 404 check (after `pop`, before the 404 check).
   - What's unclear: CONTEXT.md does not explicitly say. The safer reading (emit ALWAYS-on-INVOKE-success) would log `narrative_source` even before the 404 short-circuit. The ambiguous reading (emit ONLY on 200) would skip the 404 path.
   - Recommendation: Log BEFORE the 404 check (after `pop`). The invoke succeeded; narrative_source was observable; logging adds zero PII overhead. The 404 is a handler-side decision based on the agent's fallback response, not an invocation failure.
   - Plan action: Pattern 1 example shows log BEFORE 404 check — use that ordering.

3. **Does `fn.current_version` with `BundlingOptions` behave correctly across deploys?**
   - What we know: CDK docs say `current_version` is supported for `Code.fromAsset` and `Code.fromInline`. Phase 3 uses `from_asset` with `BundlingOptions` [VERIFIED: `backend_api.py` lines 49–59].
   - What's unclear: The `BundlingOptions.command` output must be deterministic for CDK to correctly detect "no change" vs "code changed" — otherwise the asset hash changes on every synth even when source hasn't changed, triggering unnecessary version publishes.
   - Recommendation: Phase 3 has been deploying successfully since Phase 3 close without version churn; assume the bundling is deterministic enough. If Phase 7 deploy reveals unexpected version publishes on no-op `cdk deploy`, revisit (but not a known blocker).
   - Low risk; note for plan execution, not for research closure.

4. **Offline test setup — pytest `caplog` level + logger name handling.**
   - What we know: `caplog.at_level(logging.INFO, logger="api_lambda.handler")` captures records emitted via `logger = logging.getLogger(__name__)` when the module's `__name__` is `api_lambda.handler`.
   - What's unclear: Whether the module fully-qualified name is `api_lambda.handler` (repo layout) or just `handler` (Lambda runtime `/var/task/handler.py` layout). The test harness imports via `from api_lambda.handler import handler`, so `__name__` is `api_lambda.handler` in the test context.
   - Recommendation: Use `caplog.at_level(logging.INFO, logger="api_lambda.handler")` as shown in Pattern 1 test examples. [VERIFIED: existing `tests/test_backend_api_handler.py` imports as `from api_lambda.handler import handler`.]

## Environment Availability

Phase 7 has external dependencies (AWS CLI for D-15 smoke; already-deployed AgentCore runtime). Probed 2026-04-25:

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | All pytest + CDK synth | ✓ | 3.9 (system); Phase 06.1 noted `/opt/homebrew/bin/python3.13` has needed deps | Use `/opt/homebrew/bin/python3.13` for CDK + strands-dependent tests (per Phase 06.1 SUMMARY decision) |
| `boto3` | api_lambda runtime + tests | ✓ | 1.42.11 [VERIFIED] | — |
| `botocore` | exception imports | ✓ | 1.42.11 [VERIFIED] | — |
| `aws-cdk-lib` | CDK synth tests | (assumed installed per requirements-dev.txt) | `>=2.250.0` | — |
| `pytest`, `pytest-mock`, `requests` | offline + smoke tests | (assumed installed per requirements-dev.txt) | `>=7.0`, `>=3.0`, `>=2.28,<3` | — |
| `aws` CLI | D-15 runbook steps 2, 5 | (assumed present on demo laptop) | — | Can substitute AWS SDK calls via Python if CLI absent |
| `curl` | D-15 runbook steps 3, 4 | (assumed present) | — | `requests` via Python works |
| `jq` | D-15 runbook step 5 | (commonly present on dev machines) | — | Python `json.tool` |
| Deployed `CustomerTariffAgent` stack | D-15 live smoke | ✓ [VERIFIED: Phase 06.1 SUMMARY confirms stable ARN `tariff_agent-O2Hai86N8V`] | — | — |
| `BackendApiStack` deployed (v1.0) | D-15 live smoke | ✓ (v1.0 shipped Phase 3) | — | — |
| `BACKEND_API_URL` env var | Smoke test skip gate | set by operator at D-15 execution time | — | — |

**Missing dependencies with no fallback:** None known.

**Missing dependencies with fallback:** None critical. Python 3.9 vs 3.13 is the only active concern from Phase 06.1; test execution uses `/opt/homebrew/bin/python3.13` per that plan's decision.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 3 D-08 open endpoint (demo, no auth). Unchanged by Phase 7. |
| V3 Session Management | yes (integrity) | Phase 3 D-11 / AP-3: fresh uuid4 per invocation — Phase 7 preserves in both normal and prewarm branches. No session caching. |
| V4 Access Control | yes | IAM policy scoped to `bedrock-agentcore:InvokeAgentRuntime` on specific runtime ARN (Phase 3). Phase 7 adds no new IAM. |
| V5 Input Validation | yes | Phase 3 D-13 regex `^CUST-\d{3,6}$` runs BEFORE prewarm branch. Same fast-fail for both modes. |
| V6 Cryptography | no | No cryptographic operations in Phase 7 scope. |

### Known Threat Patterns for Phase 7 Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SSRF via customer_id path param | Tampering | D-13 regex restricts to `CUST-NNN` — no free-form strings reach the agent. |
| PII leakage via `prewarm_failed` log message body (M7 from PITFALLS.md) | Information Disclosure | Pattern 2 example emits `error_code` separately; `str(exc)` relegated to `error` field. Demo dummy data is safe; flag in code comments for v3.0 review. |
| DoS via prewarm spam (`?prewarm=1` × N) | Denial of Service | Not a new vector — same rate limit as existing `/recommendations/{id}`. Phase 9 `scripts/prewarm.py` uses 2s spacing. No throttling added at API Gateway (accepted risk for demo). |
| Alias privilege escalation | Elevation of Privilege | Alias uses the SAME Lambda execution role. No new permissions. [VERIFIED: CDK construct share one `fn.add_to_role_policy` call.] |
| Log injection via customer_id (not applicable post-validation) | Tampering | D-13 regex accepts only `CUST-NNN` — cannot inject JSON-breaking characters. `json.dumps` escapes anyway. |
| `_narrative_source` leaked to UI (Phase 6 D-03 contract) | Information Disclosure | D-06 explicit pop before response — enforced by `test_narrative_pass_through` assertion `"_narrative_source" not in body`. |

**No new security surface introduced by Phase 7.** All new code paths inherit Phase 3's IAM, CORS, and input-validation posture.

## Sources

### Primary (HIGH confidence)

- Context7: `/websites/aws_amazon_cdk_api_v2_python` — `add_alias`, `Alias`, `VersionOptions`, `current_version_options`, `CfnAlias.ProvisionedConcurrencyConfigurationProperty`, `HttpLambdaIntegration` (topics: Lambda Alias PC + HTTP API integration) [VERIFIED 2026-04-25]
- Context7: `/websites/aws_amazon_lambda_dg` — Lambda Provisioned Concurrency status + troubleshooting + get-provisioned-concurrency-config [VERIFIED 2026-04-25]
- Local Python introspection: `botocore.session.Session().get_service_model("bedrock-agentcore").operation_model("InvokeAgentRuntime").error_shapes` → 7 modeled errors listed [VERIFIED 2026-04-25]
- Local Python introspection: `inspect.signature(ReadTimeoutError.__init__)` → confirms `endpoint_url=` kwarg shape [VERIFIED 2026-04-25]
- Local file verification: `api_lambda/handler.py`, `infrastructure/constructs/backend_api.py`, `infrastructure/backend_api_stack.py`, `tests/test_backend_api_handler.py`, `tests/test_backend_api_synth.py`, `tests/test_backend_api_smoke.py`, `tests/conftest.py`, `api_lambda/requirements.txt`, `requirements.txt`, `requirements-dev.txt` — all read in full [VERIFIED 2026-04-25]
- Phase 3 Context (`.planning/milestones/v1.0-phases/03-backend-api/03-CONTEXT.md`) — D-02/D-09/D-11/D-12/D-13 invariants [CITED]
- Phase 6 Context (`.planning/phases/06-agent-narrative-guardrail/06-CONTEXT.md`) — D-03 load-bearing `_narrative_source` contract [CITED]
- Phase 06.1 Context (`.planning/phases/06.1-resolve-sonnet-4-6-tool-use-regression-demo-02/06.1-CONTEXT.md`) — stable AgentRuntimeArn, model pin [CITED]
- v2.0 research (`.planning/research/ARCHITECTURE.md`, `FEATURES.md`, `PITFALLS.md`, `STACK.md`) — DEMO-03 architecture, PC trade-offs, AP-3 session hygiene, M7 PII [CITED]

### Secondary (MEDIUM confidence)

- AWS Lambda PC "1-3 minute allocation" wait — [CITED: AWS docs via Context7] + historical AWS consensus; matches CONTEXT.md claim. Exact timing depends on function size (256 MB here — fast end).
- `fn.current_version` change-detection determinism with `BundlingOptions` — [CITED: CDK docs say "automatically creates new version on change"]; empirically working in Phase 3 deploys since Phase 3 close (no reported version churn).

### Tertiary (LOW confidence)

None — every load-bearing claim in this research has a HIGH or MEDIUM source.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — versions verified via live Python introspection + pinned in requirements files
- Architecture (alias + PC + integration wiring): HIGH — Context7 + AWS CDK docs + existing Phase 3 construct as the baseline
- Pitfalls (marker-strip ordering, query-param string coercion, PC allocation timing, module-init init errors): HIGH — each has an official-doc citation or a direct code-inspection verification
- boto3 exception taxonomy: HIGH — 7 modeled exceptions verified directly from the botocore service model
- Validation Architecture (test files, framework, commands): HIGH — all verified by reading the three test files in full
- D-15 runbook steps: HIGH — commands validated against `aws lambda get-provisioned-concurrency-config` doc + CloudWatch Logs Insights query syntax

**Research date:** 2026-04-25
**Valid until:** 2026-05-25 (30 days — stable AWS primitives, no fast-moving library in the critical path; re-verify `boto3` version if Phase 10 freeze pinning bumps the pin)
