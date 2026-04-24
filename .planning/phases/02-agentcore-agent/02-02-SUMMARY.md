---
phase: 02-agentcore-agent
plan: 02
subsystem: infrastructure/cdk
status: complete
tags:
  - cdk
  - agentcore
  - infrastructure
  - iam
dependency_graph:
  requires:
    - 02-01 (agent/ directory with Dockerfile, agent.py, requirements.txt)
  provides:
    - infrastructure/constructs/agent_runtime.py (AgentRuntimeConstruct)
    - infrastructure/agentcore_stack.py (AgentCoreStack)
    - infrastructure/foundation_stack.py (updated with SSM parameter)
    - app.py (updated with AgentCoreStack)
    - tests/test_agentcore_synth.py (7 offline synth tests)
  affects:
    - Plan 02-03 (deploy + smoke): CDK stacks ready for cdk deploy --all
key_files:
  created:
    - infrastructure/constructs/agent_runtime.py
    - infrastructure/agentcore_stack.py
    - tests/test_agentcore_synth.py
  modified:
    - infrastructure/foundation_stack.py (added SSM StringParameter)
    - app.py (added AgentCoreStack instantiation)
    - requirements.txt (added aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0)
decisions:
  - "runtime_name uses underscores (tariff_agent) not hyphens — L2 construct validates: letters, numbers, underscores only"
  - "environment_variables (not environment) — correct L2 parameter name confirmed via inspect"
  - "platform=ecr_assets.Platform.LINUX_ARM64 on from_asset — explicit arm64 build"
  - "SSM cross-stack wiring (not CfnOutput import) — avoids CloudFormation export lock (Pitfall 5)"
metrics:
  completed: "2026-04-23"
  tasks_completed: 3
  files_created: 3
  files_modified: 3
---

# Phase 2 Plan 2: CDK Infrastructure Summary

**One-liner:** AgentCoreStack with L2 Runtime construct, SSM cross-stack wiring, scoped IAM (lambda:InvokeFunction + bedrock:InvokeModel), and 7 offline synth tests — all passing.

## What Was Built

### Task 1: SSM Parameter + CDK Alpha Package

**`infrastructure/foundation_stack.py`** (modified):
- Added `aws_ssm as ssm` import
- Added `ssm.StringParameter` writing ToolsLambda ARN to `/customer-tariff/tools-lambda-arn`
- Decouples FoundationStack from AgentCoreStack at CloudFormation level (Pitfall 5)

**`requirements.txt`** (modified):
- Added `aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0`

### Task 2: AgentRuntimeConstruct + AgentCoreStack + app.py

**`infrastructure/constructs/agent_runtime.py`** — `AgentRuntimeConstruct`:
- `AgentRuntimeArtifact.from_asset("agent", platform=Platform.LINUX_ARM64)` — builds Docker image from agent/ directory
- `environment_variables={"TOOLS_LAMBDA_ARN": ..., "AWS_REGION": ...}` — injected into container
- IAM: `bedrock:InvokeModel` + `bedrock:InvokeModelWithResponseStream` on foundation-model ARN pattern
- IAM: `lambda:InvokeFunction` scoped to exact ToolsLambda ARN
- Properties: `agent_runtime_arn`, `agent_runtime_id`

**`infrastructure/agentcore_stack.py`** — `AgentCoreStack`:
- Reads ToolsLambda ARN from SSM via `value_for_string_parameter`
- Wires `AgentRuntimeConstruct`
- CfnOutputs: AgentRuntimeArn, AgentRuntimeId

**`app.py`** (modified):
- Added `AgentCoreStack` import and instantiation with `region="us-east-1"`

### Task 3: Offline CDK Synth Tests

**`tests/test_agentcore_synth.py`** — 7 tests, all passing:

| Test | What it asserts |
|------|----------------|
| test_stack_synthesises | Non-empty template produced |
| test_has_agentcore_runtime | 1x AWS::BedrockAgentCore::Runtime |
| test_has_iam_role | 1x AWS::IAM::Role |
| test_has_iam_policy_with_lambda_invoke | lambda:InvokeFunction in policy |
| test_has_iam_policy_with_bedrock_invoke | bedrock:InvokeModel in policy |
| test_no_wildcard_lambda_actions | No * in Lambda actions |
| test_runtime_has_environment_variables | TOOLS_LAMBDA_ARN in env vars |

## Deviations from Plan

1. **runtime_name changed from `tariff-agent` to `tariff_agent`**: The L2 construct validates that runtime names contain only letters, numbers, and underscores. Hyphens are rejected with `InvalidRuntimeName`. Fixed during execution.

2. **Parameter name `environment_variables` (not `environment`)**: Confirmed via `inspect.signature()` before writing the construct. The plan noted this as a possibility.

3. **Added `platform=ecr_assets.Platform.LINUX_ARM64`** to `from_asset()`: The L2 construct supports an explicit platform parameter, which is cleaner than relying on the Dockerfile's `--platform` flag alone.

## Test Results

```
tests/test_agentcore_synth.py: 7 passed
Full offline suite: 57 passed, 6 skipped
```

## Self-Check: PASSED

- SSM parameter present in foundation_stack.py: `/customer-tariff/tools-lambda-arn`
- AgentCoreStack in app.py: import + instantiation confirmed
- lambda:InvokeFunction in agent_runtime.py: confirmed
- bedrock:InvokeModel in agent_runtime.py: confirmed
- from_asset in agent_runtime.py: confirmed with LINUX_ARM64 platform
- Phase 1 synth tests: 8/8 still passing
- Phase 2 synth tests: 7/7 passing
- Full offline suite: 57 passed, 6 skipped
