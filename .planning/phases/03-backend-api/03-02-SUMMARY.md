---
phase: 03-backend-api
plan: 02
subsystem: cdk-infrastructure
status: complete
tags:
  - cdk
  - api-gateway
  - http-api-v2
  - ssm
  - iam
dependency_graph:
  requires:
    - 03-01 (api_lambda/ asset)
  provides:
    - infrastructure/backend_api_stack.py
    - infrastructure/constructs/backend_api.py (Lambda + HttpApi + CORS + IAM + route)
    - tests/test_backend_api_synth.py (11 synth assertions)
    - /customer-tariff/agent-runtime-arn SSM parameter (written by amended AgentCoreStack)
  affects:
    - "Plan 03-03 (deploy + smoke): both stacks deployable via cdk deploy"
key_files:
  created:
    - infrastructure/constructs/backend_api.py
    - infrastructure/backend_api_stack.py
    - tests/test_backend_api_synth.py
  modified:
    - infrastructure/agentcore_stack.py (SSM write for AgentRuntimeArn)
    - app.py (register BackendApiStack)
metrics:
  completed: "2026-04-24"
  tasks_completed: 4
  files_created: 3
  files_modified: 2
  tests_added: 11
---

# Phase 3 Plan 2: CDK Infrastructure + Synth Tests Summary

**One-liner:** BackendApiConstruct (Lambda + HTTP API v2 + CORS + IAM), BackendApiStack, AgentCoreStack SSM amendment, app.py registration, and 11 synth tests.

## What Was Built

### Task 2.1: AgentCoreStack SSM Amendment

**`infrastructure/agentcore_stack.py`** — appended one `ssm.StringParameter` block writing the runtime ARN to `/customer-tariff/agent-runtime-arn` (D-07). Existing CfnOutputs preserved. No new imports needed.

### Task 2.2: BackendApiConstruct

**`infrastructure/constructs/backend_api.py`** — new construct combining:
- **Lambda** — `api_lambda/` asset, `python3.12`, `handler.handler`, 30s timeout (D-03), 256MB, env vars (`AGENT_RUNTIME_ARN`, `AWS_REGION`, `LOG_LEVEL`)
- **IAM** — `PolicyStatement(actions=["bedrock-agentcore:InvokeAgentRuntime"], resources=[agent_runtime_arn])` — no wildcards, scoped to specific runtime ARN (T-03-06, Research Q6)
- **HTTP API v2** — `apigwv2.HttpApi` with `CorsPreflightOptions(allow_origins=["*"], allow_methods=[GET, OPTIONS], allow_headers=["Content-Type"])` (D-09, T-03-05)
- **Route** — `GET /recommendations/{customer_id}` via `HttpLambdaIntegration` (D-10)
- Exposes `.api_endpoint` property

### Task 2.3: BackendApiStack + app.py

**`infrastructure/backend_api_stack.py`** — new stack reading the runtime ARN via `ssm.StringParameter.value_for_string_parameter` (Pattern 5 — CloudFormation dynamic reference, no AWS creds at synth; avoids `Fn.import_value` export lock per Pitfall 3). Emits `ApiEndpoint` CfnOutput.

**`app.py`** — added import and registration block. All 3 stacks now register in `us-east-1` (AgentCore Registry constraint).

### Task 2.4: CDK Synth Tests

**`tests/test_backend_api_synth.py`** — 11 assertions, all passing:

| Test | What it verifies |
|------|------------------|
| test_stack_synthesises | Non-empty Resources block |
| test_has_http_api | Exactly 1 `AWS::ApiGatewayV2::Api` |
| test_has_lambda | Exactly 1 `AWS::Lambda::Function` |
| test_has_route | Route key `GET /recommendations/{customer_id}` present |
| test_lambda_runtime_and_handler | Runtime=python3.12, Handler=handler.handler, FunctionName=tariff-api, MemorySize=256 |
| test_lambda_timeout | Timeout=30 (D-03) |
| test_cors_allow_all | CorsConfiguration.AllowOrigins==["*"] |
| test_cors_methods | AllowMethods contains GET + OPTIONS |
| test_cors_headers | AllowHeaders contains Content-Type |
| test_has_iam_policy_with_invoke_agent_runtime | IAM policy walk finds `bedrock-agentcore:InvokeAgentRuntime`, no wildcard |
| test_agentcore_stack_has_ssm_parameter | AgentCoreStack synth contains SSM parameter at `/customer-tariff/agent-runtime-arn` |

## Test Results

```
tests/test_backend_api_synth.py: 11 passed
Full offline suite: 81 passed, 6 skipped, 23 deselected
```

`python3 app.py` synthesises all 3 stacks cleanly offline (no AWS creds).

## Deviations

- Split CORS assertion into 3 tests (origins / methods / headers) instead of one compound test. More granular failure signal; no contract change.
- Lambda timeout broken out as its own test for the same reason.

## Self-Check: PASSED

- `cdk synth` produces `cdk.out/CustomerTariffApi.template.json` and `cdk.out/CustomerTariffAgent.template.json`
- AgentCoreStack template contains `AWS::SSM::Parameter` at the right name
- BackendApiStack template has 1 HttpApi, 1 Lambda (tariff-api), 1 route, 1 IAM policy scoped to the runtime ARN, CORS allow-all
- All 11 synth tests pass
- Full offline suite green (no regressions)
