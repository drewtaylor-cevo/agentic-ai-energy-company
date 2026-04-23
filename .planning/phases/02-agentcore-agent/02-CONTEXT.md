# Phase 2: AgentCore Agent - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the Strands SDK AgentCore agent that orchestrates `get_billing_history` and `simulate_savings` tool calls via the Phase 1 ToolsLambda, and returns accurate, simultaneous Green + Cheapest recommendations for all 3 demo personas. No UI, no API layer — the deliverable is a deployed agent runtime that passes `invoke_agent_runtime` verification for every persona.

New capabilities (API layer, UI, CRM integration) belong in later phases.

</domain>

<decisions>
## Implementation Decisions

### Agent Framework
- **D-01:** **Strands SDK** is the agent framework — confirmed available in the target AWS account. Use `strands-agents` PyPI package with `@tool` decorators.
- **D-02:** Deploy to **BedrockAgentCoreApp managed runtime** (AgentCore managed runtime, not Lambda-hosted). Invoked via `invoke_agent_runtime` — this matches the Phase 2 success criteria exactly.
- **D-03:** Agent LLM: **Claude Sonnet 3.7** via Amazon Bedrock (us-east-1). Use the `anthropic.claude-3-7-sonnet-20250219-v1:0` model ID (or equivalent Bedrock ARN).

### Tool Invocation
- **D-04:** The Strands agent tools call the **Phase 1 ToolsLambda via boto3 invoke** — the agent wraps `get_billing_history` and `simulate_savings` as Strands `@tool` functions that invoke the deployed Lambda ARN. No code duplication — Phase 1 remains the single source of truth for data access and savings arithmetic.

### Claude's Discretion
- **CDK structure:** New `AgentCoreStack` (separate from `FoundationStack`) is preferred for clean separation. Stack should import the ToolsLambda ARN from FoundationStack via SSM Parameter Store or CfnOutput. Claude determines exact cross-stack wiring.
- **Agent system prompt:** Must enforce REC-03 — both Green and Cheapest tracks always surfaced simultaneously, neither ranked above the other. Claude writes the system prompt; it must prevent any single-track or ranked response.
- **Response format:** Structured JSON output with Green and Cheapest track objects (each with `plan_id`, `plan_name`, `saving_monthly`, `saving_annual`) is preferred for downstream Phase 3 API parsing. Claude determines exact schema — but it must align with `simulate_savings_pure` output shape from `lambda/handler.py`.
- **IAM permissions:** Agent execution role needs `lambda:InvokeFunction` on ToolsLambda ARN and `bedrock:InvokeModel` for the Claude model. Claude determines full IAM policy.
- **Test/verification strategy:** Both offline unit tests (mocked tools) and a live `invoke_agent_runtime` smoke test per persona. Claude determines test structure, but all 4 Phase 2 success criteria must be verified.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — Phase 2 maps to REC-01, REC-02, REC-03, SAV-01, SAV-02, SAV-03. Read §Recommendations and §Savings Simulation sections in full.

### Project Context
- `.planning/PROJECT.md` — Core value, constraints, demo approach, and "Recommendation design" section. The "neither track is ranked above the other" invariant is defined here.

### Roadmap
- `.planning/ROADMAP.md` — Phase 2 success criteria (4 items). All 4 must be TRUE before Phase 3 begins. Phase 3 depends on this phase completing cleanly.

### Phase 1 Decisions and Tool Contracts
- `.planning/phases/01-foundation-dummy-data/01-CONTEXT.md` — Phase 1 data schema decisions (DynamoDB record shape, tariff_plans.json structure, seeder approach). The data contract the agent tools must honour.

### Tool Implementation
- `lambda/handler.py` — Phase 1 tool entry points: `get_billing_history(event, context)` and `simulate_savings(event, context)`. Also contains `simulate_savings_pure` — the offline-testable savings calculator. Read this before writing any `@tool` wrappers — the input/output shapes are defined here.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `lambda/handler.py` → `get_billing_history` and `simulate_savings` — these are the two tool entry points the agent wraps. Input: `{"customer_id": "CUST-XXX"}`. Output shapes defined in the file.
- `lambda/handler.py` → `simulate_savings_pure(billing_history, plans)` — deterministic savings calculator. Can be used directly in offline unit tests without AWS credentials.
- `infrastructure/constructs/tools_lambda.py` — ToolsLambda construct; its `function.function_arn` is the ARN the agent tools must invoke.
- `infrastructure/foundation_stack.py` → `CfnOutput("ToolsLambdaArn", ...)` — ARN exported after `cdk deploy` and available for cross-stack reference.

### Established Patterns
- Python throughout — CDK, Lambda, tests all Python. Agent code must be Python.
- `boto3` for AWS SDK calls — already a project dependency.
- `pytest` for testing — test suite in `tests/` with conftest fixtures. New agent tests follow the same pattern.

### Integration Points
- Phase 2 agent calls ToolsLambda ARN (from FoundationStack CfnOutput) via `boto3.client("lambda").invoke(...)`.
- Phase 3 will call the Phase 2 agent via `invoke_agent_runtime` — the agent response format established here becomes Phase 3's input contract.
- AgentCore requires us-east-1 (AgentCore Registry not available in ap-southeast-2/Sydney).

</code_context>

<specifics>
## Specific Ideas

- SAV-03 is non-negotiable: savings arithmetic must be done by `simulate_savings_pure` in code, not by the LLM. The agent's role is orchestration and narration — numbers come from the tool.
- The agent's success criteria explicitly require `invoke_agent_runtime` as the invocation method — not direct Lambda, not a local Strands run. The BedrockAgentCoreApp runtime must be deployed and the agent registered.
- Success criterion 4 ("cheapest savings always >= green savings") is a data invariant that must hold for all 3+ personas. Phase 1 engineered this into the dummy data, but Phase 2 verification must confirm it end-to-end through the agent.

</specifics>

<deferred>
## Deferred Ideas

- Tool wiring detail (exact boto3 invoke payload shape, error handling for Lambda errors) — Claude's discretion during planning
- Response format schema (exact JSON field names) — Claude's discretion, but must be compatible with `simulate_savings_pure` output
- CDK cross-stack wiring approach (SSM vs CfnOutput import) — Claude's discretion
- Phase 3 API contract — determined when Phase 3 is discussed

</deferred>

---

*Phase: 02-agentcore-agent*
*Context gathered: 2026-04-23*
