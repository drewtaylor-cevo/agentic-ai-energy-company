# Phase 2: AgentCore Agent - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 02-agentcore-agent
**Areas discussed:** Agent framework

---

## Agent Framework

### Strands SDK availability

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, Strands confirmed | pip install strands-agents works in the target account. Proceed with Strands SDK. | ✓ |
| Not confirmed yet | Haven't verified — add verification step to the plan. | |
| No — fall back to classic Bedrock Agents | Use classic Bedrock Agents action groups (more IAM wiring). | |

**User's choice:** Yes, Strands confirmed
**Notes:** Strands SDK is available and stable in the target account. Proceed with it as the agent framework.

---

### Runtime / deployment model

| Option | Description | Selected |
|--------|-------------|----------|
| BedrockAgentCoreApp managed runtime | Deploy to AgentCore managed runtime, invoked via invoke_agent_runtime. Matches Phase 2 success criteria. | ✓ |
| Lambda-hosted Strands agent | Package Strands as a Lambda function. No AgentCore Registry needed. | |

**User's choice:** BedrockAgentCoreApp managed runtime
**Notes:** Explicit requirement from Phase 2 success criteria — "A direct invoke_agent_runtime call".

---

### Claude model selection

| Option | Description | Selected |
|--------|-------------|----------|
| Claude Sonnet 3.7 | Latest capable Claude in Bedrock, good tool-calling reliability. | ✓ |
| Claude Haiku 3.5 | Fastest and cheapest — suits simple tool orchestration. | |
| Claude Sonnet 3.5 v2 | Proven reliable, slightly older fallback. | |

**User's choice:** Claude Sonnet 3.7
**Notes:** Widest capability, best tool-use reliability for the demo.

---

### Tool invocation source

| Option | Description | Selected |
|--------|-------------|----------|
| Call existing Lambda via boto3 invoke | Agent wraps ToolsLambda ARN as @tool functions. Reuses Phase 1 deployment. | ✓ |
| Import pure Python functions directly | Co-locate handler.py with agent code. No Lambda hop. | |

**User's choice:** Call existing Lambda via boto3 invoke
**Notes:** Keeps Phase 1 as the single source of truth. Avoids code duplication.

---

## Claude's Discretion

- CDK structure (new AgentCoreStack vs extending FoundationStack)
- Agent system prompt wording (must enforce "both tracks, never rank" per REC-03)
- Response format JSON schema
- IAM policy details
- Test structure and mocking strategy

## Deferred Ideas

- Tool wiring error handling specifics
- Exact response JSON schema (Phase 3 will define its own parsing contract)
- CDK cross-stack wiring approach (SSM Parameter Store vs CfnOutput import)
