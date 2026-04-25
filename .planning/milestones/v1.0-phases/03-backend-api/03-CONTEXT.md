# Phase 3: Backend API - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a Lambda + API Gateway HTTP API that accepts a customer ID over HTTP, invokes the Phase 2 AgentCore runtime via `invoke_agent_runtime`, and returns both Green and Cheapest recommendations as a single synchronous JSON response. The deliverable is a deployed HTTP endpoint that passes curl/Postman verification for all 3 demo personas (DEMO-01) and is ready for the Phase 4 React UI to consume.

New capabilities (authentication systems, live CRM integration, additional endpoints, pre-warm scripts, frozen environment locks) belong in later phases or remain deferred to v2.

</domain>

<decisions>
## Implementation Decisions

### Response Delivery
- **D-01:** **Synchronous JSON response** — no HTTP streaming. The API Lambda calls `invoke_agent_runtime`, waits for the agent's single `structured_output` result, and returns it as a JSON body. The roadmap's "streaming recommendations" phrasing refers to dynamic/live recommendations, not token-by-token HTTP streaming. The existing agent has nothing to stream mid-call.
- **D-02:** **Pass-through response shape** — the API returns the agent response verbatim: `{"green": {plan_id, plan_name, saving_monthly, saving_annual}, "cheapest": {...}}`. No envelope, no meta block. One contract across agent → API → UI.
- **D-03:** **Lambda timeout 30s, surface 504 on agent timeout** — aligns with the API Gateway HTTP API hard maximum. If `invoke_agent_runtime` exceeds ~25s, return HTTP 504 Gateway Timeout with a user-friendly error body (success criterion 2).
- **D-04:** **Accept cold-start latency for the demo** — no provisioned concurrency, no scheduled warmer. DEMO-03 (pre-warm script) is explicitly deferred to v2 in PROJECT.md. First invocation may be slower; subsequent calls benefit from Lambda warm reuse.

### API Gateway & Infrastructure
- **D-05:** **API Gateway HTTP API** — cheaper, faster cold start, built-in CORS config, simpler CDK wiring than REST API. 30s native timeout aligns with D-03. REST API features (WAF, usage plans, API keys) are unnecessary for a dummy-data demo. Lambda Function URL rejected because we want a proper routable endpoint.
- **D-06:** **New `BackendApiStack`** — continues the stack-per-phase pattern: `FoundationStack` (Phase 1) + `AgentCoreStack` (Phase 2) + `BackendApiStack` (Phase 3). Independent deploy cadence, clean separation of concerns.
- **D-07:** **SSM Parameter for cross-stack ARN wiring** — `AgentCoreStack` writes `/customer-tariff/agent-runtime-arn` to SSM; `BackendApiStack` reads via `ssm.StringParameter.value_for_string_parameter`. Mirrors the Phase 1 → Phase 2 ToolsLambda ARN pattern. CfnOutput import rejected (Pitfall 5: CloudFormation export lock prevents independent redeploys).

### Authentication & CORS
- **D-08:** **No authentication — open endpoint.** PROJECT.md Out of Scope lists OAuth/authentication. Dummy-data demo with no sensitive content; endpoint lives under an AWS-generated HTTPS URL (not indexed or discoverable).
- **D-09:** **CORS allow-all** — `Access-Control-Allow-Origin: *`, allowed methods `GET, POST, OPTIONS`, allowed headers `Content-Type`. Phase 4 UI will run from `localhost` during dev and an unknown production origin at demo time; origin-pinning would force premature hostname decisions.

### Request/Response Contract
- **D-10:** **`GET /recommendations/{customer_id}`** — clean REST, identifier in the path. Idempotent, curl-friendly (success criterion 1), matches the "customer lookup → instant savings plan" demo hook. Customer ID in access logs is acceptable for dummy data.
- **D-11:** **API Lambda generates fresh `runtimeSessionId = str(uuid.uuid4())` per invocation** — guarantees no session bleed between persona lookups (success criterion 3). UUID4 is 36 characters, satisfying AgentCore's 33-character minimum. Client-supplied session IDs and API Gateway request IDs rejected.
- **D-12:** **Standard HTTP error mapping** with a consistent JSON error body (`{"error": "<friendly message>"}`):
  - Invalid customer_id format (not `CUST-NNN`) → **400 Bad Request**
  - Customer not found (no billing history) → **404 Not Found**
  - Agent/runtime timeout → **504 Gateway Timeout**
  - Unknown agent/runtime failure → **502 Bad Gateway**
  - Unexpected server error → **500 Internal Server Error**
- **D-13:** **API Lambda validates customer_id against `^CUST-\d{3,6}$` before calling the agent** — fail fast with 400 on bad input; avoid wasting a 3-5s agent invocation. Same regex as `lambda/handler.py::_validate_customer_id`. Defense-in-depth: the tool Lambda still validates too.

### Claude's Discretion
- **CloudWatch log groups, log retention, structured logging format** — Claude picks conventions consistent with Phase 1/2 Lambdas.
- **X-Ray tracing on the API Lambda** — enable or skip based on planner judgment; not a success criterion.
- **Lambda memory and Python runtime version** — match the existing Phase 1 ToolsLambda defaults unless there's a reason to differ.
- **Exact CDK construct layout** — e.g., `BackendApiConstruct` wrapping the Lambda + HTTP API, or inline in the stack. Claude determines based on existing construct patterns (`infrastructure/constructs/*`).
- **Test structure** — offline unit tests with mocked `bedrock-agentcore` client, plus live smoke test via curl/requests against the deployed endpoint for all 3 personas. Exact pytest marker names and fixture design at planner's discretion, but must mirror the Phase 2 `@pytest.mark.smoke` pattern.
- **Phase 2 modification to write AgentRuntimeArn to SSM** — small prep step required since `AgentCoreStack` currently exposes the ARN only via `CfnOutput`. Claude decides whether to fold this into `BackendApiStack`'s deploy prerequisites or amend `AgentCoreStack` directly.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — Phase 3 maps to **DEMO-01** (fully self-contained demo, no live CRM). Read §Demo in full.

### Project Context
- `.planning/PROJECT.md` — Core value, Out of Scope (OAuth/auth excluded, real CRM excluded), demo hook "customer lookup → instant personalised savings plan". The call-centre-agent UX context informs latency and error-message expectations.

### Roadmap
- `.planning/ROADMAP.md` — Phase 3 success criteria (3 items): curl/Postman returns recommendations for every persona; error cases handled gracefully (customer not found, agent timeout); fresh session ID per lookup with no bleed. All 3 must be TRUE before Phase 4 begins.

### Phase 2 Decisions and Agent Contract
- `.planning/phases/02-agentcore-agent/02-CONTEXT.md` — Phase 2 decisions: Strands SDK agent, `BedrockAgentCoreApp` managed runtime, `invoke_agent_runtime` invocation, pass-through JSON response shape. The agent contract Phase 3 consumes.
- `agent/agent.py` — Phase 2 agent source. Read `RecommendationResponse` Pydantic model and the `@app.entrypoint invoke` signature. The API Lambda's payload shape (`{"customer_id": "CUST-NNN"}`) and response shape (`{"green": {...}, "cheapest": {...}}`) must match these exactly.

### Phase 1 Tool Contract
- `lambda/handler.py` — `_validate_customer_id` regex (`^CUST-\d{3,6}$`) must be mirrored in the API Lambda (D-13). `simulate_savings_pure` error cases (empty billing → `ValueError("No billing history for ...")`) inform the 404 mapping (D-12).

### Phase 2 Infrastructure
- `infrastructure/agentcore_stack.py` — Currently exports `AgentRuntimeArn` via `CfnOutput` only. Phase 3 requires adding an SSM Parameter write for the new cross-stack contract (D-07).
- `infrastructure/foundation_stack.py` — Reference implementation of the SSM parameter write pattern (writes `/customer-tariff/tools-lambda-arn`). Phase 3's `AgentCoreStack` amendment follows the same template.
- `infrastructure/constructs/agent_runtime.py` — Phase 2 CDK construct pattern. Phase 3 `BackendApiStack` construct layout should mirror this style.

### CDK Entry
- `app.py` — Current stack registration. `BackendApiStack` must be added here, all three stacks scoped to `us-east-1`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `lambda/handler.py::_validate_customer_id` — regex and error shape to mirror in the API Lambda's 400 fast-fail (D-13).
- `infrastructure/foundation_stack.py` SSM pattern — template for `AgentCoreStack` amendment that writes `AgentRuntimeArn` to SSM (D-07).
- `agent/agent.py` `RecommendationResponse` — authoritative response schema that the API Lambda returns verbatim (D-02).
- `tests/conftest.py` and `tests/test_agent_smoke.py` — fixture + smoke-test patterns to reuse for Phase 3 HTTP smoke tests.

### Established Patterns
- **Stack-per-phase** — FoundationStack → AgentCoreStack → BackendApiStack.
- **SSM cross-stack ARN wiring** — avoid CfnOutput imports to prevent CloudFormation export locks (Pitfall 5, established Phase 2).
- **Construct modules** — `infrastructure/constructs/<name>.py` with a single `Construct` subclass; stacks compose constructs only.
- **Python CDK + Python Lambda** — one language across the stack.
- **pytest offline + `@pytest.mark.smoke` live tests** — offline tests mock boto3; smoke tests require env vars and real AWS credentials.
- **us-east-1 only** — hardcoded in `app.py` because AgentCore Registry is not available in `ap-southeast-2`.

### Integration Points
- **Upstream:** Phase 3 Lambda calls `boto3.client("bedrock-agentcore").invoke_agent_runtime(agentRuntimeArn, runtimeSessionId, payload)`. Agent runtime ARN read from SSM (D-07).
- **Downstream:** Phase 4 React UI will fetch `GET /recommendations/{customer_id}` and render the returned `{green, cheapest}` object as two cards (UI-01, UI-02). The CORS-open stance (D-09) means the UI can run from anywhere during dev.
- **Prep step:** `AgentCoreStack` needs a small amendment to write `AgentRuntimeArn` to SSM before `BackendApiStack` can read it. This is an explicit Phase 3 work item, not a Phase 2 regression.

</code_context>

<specifics>
## Specific Ideas

- **Success criterion 1 is literal:** a plain `curl` or Postman call must return recommendations. No auth tokens, no custom headers beyond `Content-Type` — any developer can invoke it from the terminal.
- **Success criterion 3 is a data-isolation invariant:** fresh `runtimeSessionId` per invocation. Any hint of a reused session ID (e.g., a module-level default) must be caught in review — it would break the "no bleed between persona lookups" guarantee.
- **The error messages must be call-centre-friendly:** the UI will surface them directly during a live customer call. "Customer CUST-999 not found" is acceptable; a raw AWS exception or stack trace is not (success criterion 2).
- **The Phase 4 UI contract is fixed here:** `GET /recommendations/{customer_id}` returning `{green, cheapest}` is the entire interface Phase 4 consumes. Any UI experiments (loading states, retry buttons) work against this contract.

</specifics>

<deferred>
## Deferred Ideas

- **DEMO-03 pre-warm script** — already v2-deferred in PROJECT.md; remains deferred. Cold-start latency accepted for this phase.
- **DEMO-04 frozen environment lock** — v2, handled in Phase 5 (Demo Hardening).
- **API key / WAF / usage plans** — not needed for a dummy-data demo. Would require swapping to REST API. Revisit only if the demo is exposed publicly long-term.
- **Observability polish (X-Ray, structured JSON logs, metrics dashboards)** — left to Claude's discretion during planning, but not a success criterion.
- **Multiple deploy stages (dev/staging/prod)** — single stage is sufficient for the demo.
- **Custom domain / CloudFront fronting** — may surface in Phase 4 if the UI is deployed under a specific brand URL; out of scope for Phase 3.

</deferred>

---

*Phase: 03-backend-api*
*Context gathered: 2026-04-24*
