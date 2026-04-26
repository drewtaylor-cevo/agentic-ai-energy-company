# Phase 7: API Pass-Through + Pre-Warm Route - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Forward narrative fields verbatim through API Gateway → Lambda → client (stripping the `_narrative_source` internal marker introduced by Phase 6), add a `?prewarm=1` branch on the existing `/recommendations/{customer_id}` route that exercises the hot path and returns 204, and re-wire the API Gateway integration to a named Lambda alias (`live`) with Provisioned Concurrency togglable via `cdk deploy -c demo_pc=N`. Closes the DEMO-03 plumbing half (REQUIREMENTS.md Traceability). Operator tooling (`scripts/prewarm.py`, `demo-keepalive.sh`) and the end-to-end eval harness belong in Phase 9.

**In scope (Phase 7 only):**
- `api_lambda/handler.py` extension: pop `_narrative_source` from agent response, log marker values, return body verbatim otherwise
- `api_lambda/handler.py` prewarm branch: when `?prewarm=1`, run full real agent turn against the seed persona (path `customer_id` param), discard body, return 204, swallow all downstream exceptions to structured CloudWatch log
- `infrastructure/constructs/backend_api.py` changes: create Lambda alias `live` tracking `fn.current_version`, wire `HttpLambdaIntegration` to alias ARN, attach conditional `ProvisionedConcurrencyConfiguration` when `-c demo_pc=N` (N≥1) is passed
- Offline pytest: `test_narrative_pass_through` (fields flow + marker stripped + structured log), `test_prewarm_returns_204` (success + downstream failure + ReadTimeoutError all return 204)
- CDK synth test extension: asserts alias exists, API Gateway integration targets alias, PC config presence follows `demo_pc` context
- Live smoke (after `cdk deploy`): curl `?prewarm=1` per persona → 204; then 3 warm lookups per persona with `curl -w "%{time_total}"` → median <3000ms (UI-02 gate)

**Out of scope (Phase 7 does NOT do):**
- `scripts/prewarm.py` operator script — Phase 9 (DEMO-03 tooling half)
- `scripts/demo-keepalive.sh` — Phase 9 (DEMO-05)
- End-to-end narrative eval harness across 10 × 3 × 2 invocations — Phase 9
- UI rendering of narrative rows, `?narrative=off` feature flag, version indicator — Phase 8
- Freeze artefacts, stack policies, `demo-v2.0` tag, rollback drill — Phase 10
- Any changes to `agent/`, `agent/narrative/`, or the AgentCore runtime (Phase 6 and Phase 06.1 locked)
- Changes to the `_narrative_source` marker contract (Phase 6 D-03 is load-bearing for Phase 9's eval harness, which reaches AgentCore directly via boto3 and bypasses this API Lambda)

**Success criteria (from ROADMAP.md):**
1. Live `GET /recommendations/{customer_id}` per persona returns JSON with `usage_narrative` + `call_script` on both tracks, byte-identical to what the agent produced (minus `_narrative_source`).
2. `GET /recommendations/{customer_id}?prewarm=1` returns HTTP 204 within the handler budget after exercising one full agent turn; never returns 5xx even when the downstream warm-up fails.
3. API Gateway integration targets the `live` alias (not `$LATEST`); Provisioned Concurrency configurable via `cdk deploy -c demo_pc=N`.
4. UI-01 (both cards above fold at 1280px) and UI-02 (<3s lookup-to-rendered) hold on live smoke with narratives included.

</domain>

<decisions>
## Implementation Decisions

### Pre-Warm Route Shape

- **D-01:** Pre-warm uses the existing `/recommendations/{customer_id}` route with a `?prewarm=1` query flag — NOT a new `/prewarm` route, NOT a separate Lambda, NOT a bodyless `GET /` route. Matches ARCHITECTURE.md §DEMO-03 Option (b) — "warms exactly what the demo will hit." Same IAM policy (already scoped to `bedrock-agentcore:InvokeAgentRuntime` on the runtime ARN and sub-resource), same route pattern, same integration. The customer_id path param remains mandatory and is validated by the D-13 regex even when prewarm=1 (a stray `?prewarm=1` with an invalid customer_id returns 400 — same fast-fail for both modes; acceptable and consistent).

- **D-02:** When `?prewarm=1` is set, the handler runs a **full real agent turn** via `_agentcore_client.invoke_agent_runtime(...)` against the seed customer_id path param — identical to the normal lookup path. Response body is discarded; handler returns HTTP 204. Warms Lambda + microVM + Bedrock + `simulate_savings` tool Lambda + Strands + Pydantic validator in one call. No stripped-down "hello" path and no chained-minimal-keepalive variant. Matches ARCHITECTURE.md Open Question 1 recommended answer.

- **D-03:** **Persona rotation is owned by the operator script**, not the Lambda handler. The Phase 9 `scripts/prewarm.py` script curls `?prewarm=1` three times (CUST-001, CUST-002, CUST-003) with 2s spacing. The Lambda handler is stateless — accepts whatever customer_id path param it receives, warms that one persona per invocation. Warming 3 personas requires 3 operator-initiated calls, which also warms the AgentCore microVM pool to a depth sufficient for back-to-back demo lookups (ARCHITECTURE.md §DEMO-03 data flow).

### Pre-Warm Failure Semantics

- **D-04:** When any exception fires inside the prewarm branch (ClientError, ReadTimeoutError, generic Exception), the handler **always returns 204** and emits a structured CloudWatch log: `{"prewarm_failed": true, "customer_id": "...", "error_code": "...", "error": "..."}`. SC-2 is emphatic that `?prewarm=1` NEVER returns 5xx — this is non-negotiable. `scripts/prewarm.py`'s `curl -f` (Phase 9) always sees success; failures surface via CloudWatch tail, not script exit codes. Keeps demo-day loud failures out of the terminal the presenter is watching.

- **D-05:** The prewarm branch uses the **same `_agentcore_client`** as the normal lookup path — same `Config(read_timeout=25, connect_timeout=5)` budget. No dedicated client, no `signal.alarm` handler-side timer. On read_timeout, the existing `ReadTimeoutError` catch swallows → 204 + log (D-04). Minimal new configuration surface; no split client instances to freeze.

### Marker Strip + Pass-Through

- **D-06:** The `_narrative_source` marker is stripped via explicit `body.pop('_narrative_source', None)` immediately after `body = json.loads(response["response"].read())` and before any validation or JSON dump. Idempotent (pops nothing if absent), greppable, one line. The `None` default means pre-6.1 agent deployments or any future agent revision that drops the marker do not break the handler. NOT a whitelist-based rebuild (would require the handler to know the UI contract), NOT a deep-copy walk (Phase 6 D-03 pins the marker to a single top-level location).

- **D-07:** Before stripping, the handler emits a structured CloudWatch log at INFO: `{"customer_id": "...", "narrative_source": {"usage_narrative": "model"|"fallback", "call_script": "model"|"fallback"}}`. Logged on every successful invocation (not only on fallback). Gives Phase 9's eval harness a CloudWatch-queryable record of end-to-end model-vs-fallback hit rate across the full API path (Phase 6's AgentCore-layer log only captures the agent-direct path). Zero PII — source marker is always `"model"` or `"fallback"`, never the narrative text. When `_narrative_source` is absent (shouldn't happen post-6.1 but defensive), the log field is `null` — not an error.

- **D-08:** Narrative fields (`usage_narrative`, `call_script` on both `green` and `cheapest` tracks) flow through the handler **byte-identically** via the existing `json.dumps(body)` path. The handler does NOT validate, reshape, or field-check these fields — they are Phase 6's contract, enforced by Phase 6's Pydantic validator before they ever reach the API Lambda. Phase 7's only responsibility for new fields is "don't break what's already there." Matches Phase 3 D-02 pass-through invariant.

### Alias + Provisioned Concurrency

- **D-09:** A named Lambda alias `live` is **always created** in the CDK stack (whether or not PC is configured). API Gateway's `HttpLambdaIntegration` always targets the alias ARN — never `$LATEST`, never a raw function ARN. The integration target never changes between deploys, which keeps the freeze surface minimal: CFN stack policies applied at Phase 10 freeze can deny `Update:*` without blocking PC toggling (PC config attaches to the alias, not the integration). Name `live` follows AWS convention and is future-proof for v3.0 production use (vs. `demo`, which would need renaming).

- **D-10:** The alias tracks `fn.current_version` via `fn.add_alias("live", version=fn.current_version)`. CDK auto-publishes a new immutable Lambda version on every code change; the alias rolls forward to point at the new version on each `cdk deploy`. Provisioned Concurrency attaches to the alias — PC auto-warms the new version on deploy (no manual re-attach step). Simplest wiring, idempotent, matches AWS Lambda alias best practice.

- **D-11:** Provisioned Concurrency is controlled by an integer CDK context flag `-c demo_pc=N`:
  - `cdk deploy -c demo_pc=0` (or omitted — the default): no `ProvisionedConcurrencyConfiguration` on the alias. Alias exists; PC does not. Zero PC billing.
  - `cdk deploy -c demo_pc=1`: attaches `ProvisionedConcurrencyConfiguration(provisioned_concurrent_executions=1)` to the alias. Typical demo-day value.
  - `cdk deploy -c demo_pc=N` (N>1): presenter escape hatch for back-to-back depth if 3-persona rotation ever needs more warm slots.
  - Flag is read from CDK context via `self.node.try_get_context("demo_pc")` in `BackendApiConstruct`; cast to int, default 0. Invalid values (negative, non-numeric) fail at synth.
- **D-12:** DEMO-04 freeze workflow (Phase 10): T-48h, presenter runs `cdk deploy -c demo_pc=1` to pin PC at 1. CFN stack policy is then applied denying `Update:*` on BackendApiStack. PC configuration is frozen from that point through demo-day, billing continuously at the PC rate (~$0.40/month at PC=1, negligible for a single-demo engagement per FEATURES.md assessment).

### Testing + Live Verification

- **D-13:** Offline pytest additions (all in `tests/test_backend_api_handler.py` existing file):
  - `test_narrative_pass_through`: mocks `invoke_agent_runtime` to return a body containing both narrative fields + `_narrative_source` marker; asserts response body has narrative fields byte-identical to input, marker absent, and the structured `narrative_source` log line fires.
  - `test_narrative_pass_through_marker_absent`: same shape without the marker; asserts `.pop(..., None)` is silent and response is unchanged shape-wise.
  - `test_prewarm_returns_204_happy_path`: mocks successful `invoke_agent_runtime`; asserts 204, empty body, no `narrative_source` log (prewarm path doesn't log that).
  - `test_prewarm_returns_204_on_client_error`: mocks `ClientError`; asserts 204 + `prewarm_failed=true` log.
  - `test_prewarm_returns_204_on_read_timeout`: mocks `ReadTimeoutError`; asserts 204 + `prewarm_failed=true` log.
  - `test_prewarm_invalid_customer_id_returns_400`: confirms D-13 customer_id validation still fires before the prewarm branch (stray `?prewarm=1` with bad customer_id → 400, not 204).

- **D-14:** CDK synth test extension in `tests/test_backend_api_synth.py`:
  - Alias resource exists (`AWS::Lambda::Alias` with name `live`).
  - `AWS::ApiGatewayV2::Integration` `IntegrationUri` references the alias ARN (not `$LATEST`).
  - With `-c demo_pc=1` context: `AWS::Lambda::Alias` has `ProvisionedConcurrencyConfiguration` with `ProvisionedConcurrentExecutions: 1`.
  - With `-c demo_pc=0` (default): no `ProvisionedConcurrencyConfiguration` property present.

- **D-15:** Phase 7 live-smoke closeout gate (NOT shipped as pytest — documented in plan SUMMARY and runbook):
  1. `cdk deploy -c demo_pc=1 BackendApiStack` succeeds idempotently.
  2. Curl `?prewarm=1` for CUST-001, CUST-002, CUST-003 → all three return 204.
  3. For each persona, curl 3 subsequent warm lookups with `curl -w "%{time_total}"` within 5 minutes of prewarm.
  4. Assert median warm time <3000ms per persona (UI-02 gate, SC-4).
  5. CloudWatch tail shows `narrative_source` structured log on each warm lookup and `prewarm_failed` absent across the 3 prewarm calls.
  6. Response body per persona contains `usage_narrative` + `call_script` on both `green` and `cheapest` tracks; `_narrative_source` absent from the body.
  Phase 7 does NOT close until D-15 passes end-to-end. Phase 9 then wraps this into `scripts/prewarm.py` + eval harness.

### Claude's Discretion

- **Structured log format.** JSON vs key=value. Default to JSON (matches existing AgentCore fallback log format from Phase 6 D-03). Planner confirms consistency.
- **How `demo_pc` context is read.** `self.node.try_get_context("demo_pc")` in `BackendApiConstruct.__init__` vs. passed-in kwarg from `BackendApiStack`. Planner decides; recommend construct-level (keeps the stack thin).
- **Whether to export `demo_pc` value as a `CfnOutput`.** Nice-to-have for operator confirmation but adds an output surface. Planner decides; recommend no (checkable via `aws lambda get-provisioned-concurrency-config` when needed).
- **Whether prewarm uses a distinct uuid4 session prefix** (e.g. `prewarm-<uuid4>`) for CloudWatch filtering. Marginal observability value; recommend keeping vanilla uuid4 (D-11 Phase 3) to avoid introducing a new session shape on the AgentCore side.
- **Whether PC warm-up is asserted post-deploy in Phase 7.** AWS takes ~1–3 min to provision the PC instances after the alias is updated. Live smoke D-15 should wait ≥3 min between `cdk deploy` and the warm-median check; planner pins the wait.
- **Exact floats for UI-02 gate per persona.** D-15 uses <3000ms median across 3 samples per persona. Planner may tighten to <2500ms on the flagship (CUST-001 Sarah) if the warm-path budget holds consistently, matching ARCHITECTURE.md §"Latency Budget" 1470–3150ms envelope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v2.0 Requirements + Roadmap

- `.planning/REQUIREMENTS.md` — §"Demo Hardening — Pre-warm (DEMO)" for DEMO-03 + DEMO-05 (DEMO-03 plumbing half is Phase 7's scope; tooling half is Phase 9). §"Key Decisions Locked at Requirements Stage" for rollback mechanism (feature flag + `demo-v1.0` tag + `build:mock` dist).
- `.planning/ROADMAP.md` §"Phase 7: API Pass-Through + Pre-Warm Route" — 4 success criteria; all must be TRUE before Phase 8 (UI integration) starts.
- `.planning/PROJECT.md` — Core value, constraints, "Recommendation design" invariant (Green + Cheapest surfaced together, neither ranked).
- `.planning/STATE.md` — Phase 7 precondition evidence: deployed runtime ARN stable (`tariff_agent-O2Hai86N8V`), extended TrackInfo schema serving byte-exact values, `_narrative_source` marker expected to be stripped by Phase 7 per pass-through contract.

### Phase 6 + Phase 06.1 Artefacts (downstream contracts this phase honours)

- `.planning/phases/06-agent-narrative-guardrail/06-CONTEXT.md` — **D-03 is load-bearing**: the `_narrative_source` internal marker must be stripped by the Phase 7 API Lambda and never reach the UI. Phase 9's eval harness reads the marker by calling AgentCore directly via boto3 (bypassing this Lambda). D-01, D-02, D-04 describe the retry-once-then-per-field-fallback behaviour that produces the marker — reference only, Phase 7 does not modify.
- `.planning/phases/06-agent-narrative-guardrail/06-03-SUMMARY.md` — Integration points for the new `narrative/` package and the extended `TrackInfo` schema that Phase 7 receives on the wire.
- `.planning/phases/06.1-resolve-sonnet-4-6-tool-use-regression-demo-02/06.1-CONTEXT.md` — Confirms strategic model pin (Claude Sonnet 4.6) and the stable AgentRuntimeArn that Phase 7's IAM policy is already scoped to. No IAM changes required in Phase 7.

### v2.0 Research (the source for DEMO-03 architecture)

- `.planning/research/ARCHITECTURE.md` §"DEMO-03 — Pre-Warm Architecture" — the 5-surface cold-start grid, trade-off grid for prewarm entry mechanism (Option (b) recommended = reuse `/recommendations` with `?prewarm=1`), pre-warm data flow diagram, AP-3 (no cached session IDs), AP-5 (skipping pre-warm at T-24h rehearsal).
- `.planning/research/ARCHITECTURE.md` §"Latency Budget — Does UI-02 Survive v2.0?" — 1470–3150ms warm envelope; UI-02 (<3s) remains the gate for Phase 7 D-15.
- `.planning/research/ARCHITECTURE.md` §"Phase 2.2 — API Pass-Through" + §"Phase 2.4 — Pre-Warm Tooling" — phase-level task breakdown (Phase 2.2 = this phase; Phase 2.4 = Phase 9).
- `.planning/research/FEATURES.md` §"Pre-warm script" + §"Provisioned Concurrency on the production Lambda" (explicit NO — always-on PC rejected; on-demand via `-c demo_pc=N` honours this while still satisfying SC-3).
- `.planning/research/FEATURES.md` §"DEMO-03 (Pre-Warm) — Playbook" — operator-facing behaviour Phase 9 will implement; Phase 7 delivers the Lambda-side target.
- `.planning/research/PITFALLS.md` — AP-1 (free-form prose instead of structured fields, Phase 6 concern but validator path still active), AP-3 (cached session IDs — prewarm must mint fresh uuid4), M7 (PII in logs — `narrative_source` log is zero-PII by construction).
- `.planning/research/STACK.md` — boto3>=1.42.0 already bundled via BundlingOptions (unchanged from Phase 3); Python 3.12 Lambda runtime.

### v1.0 Carry-Forward (the stack Phase 7 extends)

- `api_lambda/handler.py` — **primary file modified**. Existing `handler()` function (lines 55–106) is where the marker-strip + structured log additions land (right after `body = json.loads(...)` on line 77) and where the prewarm branch is added (after the customer_id regex check on line 63, before the main `invoke_agent_runtime` call). Existing `_error()` helper (line 46) is unchanged. Existing `_agentcore_client` with `Config(read_timeout=25, connect_timeout=5)` (line 39) is reused by both paths.
- `infrastructure/constructs/backend_api.py` — **primary file modified**. `fn` Lambda function definition (lines 43–67) gains `current_version_options` if needed; new code adds `fn.add_alias("live", ...)` with `ProvisionedConcurrencyConfiguration` when `demo_pc>0`. `api.add_routes(...)` (lines 104–108) integration target changes from `fn` to the alias.
- `infrastructure/backend_api_stack.py` — reads `demo_pc` from `self.node.try_get_context("demo_pc")` or passes through (planner decides exact layering).
- `tests/test_backend_api_handler.py` — offline pytest pattern. Phase 7 adds 5+ new test functions here (see D-13).
- `tests/test_backend_api_smoke.py` — live HTTP smoke pattern. Phase 7 may extend with a prewarm smoke test (optional; D-15 is primarily documented gates).
- `tests/test_backend_api_synth.py` — CDK synth assertion pattern. Phase 7 adds alias + PC assertions (see D-14).
- `lambda/handler.py` — the tariff-tools Lambda (unchanged). Referenced here because the prewarm full turn (D-02) exercises this Lambda via `simulate_savings` — it's part of what gets warmed.

### v1.0 Phase Context (for convention carry-forward)

- `.planning/milestones/v1.0-phases/03-backend-api/03-CONTEXT.md` — Phase 3 decisions: D-02 (pass-through verbatim, no envelope), D-09 (allow-all CORS — unchanged in v2.0), D-11 (fresh uuid4 per invocation), D-12 (error taxonomy), D-13 (customer_id regex), D-07 (SSM param for agent ARN — no CfnOutput export lock). Phase 7 preserves all of these.
- `.planning/milestones/v1.0-research/ARCHITECTURE.md` — v1.0 Layer 3 reference architecture. Phase 7 is a pure additive delta over this.

### External / upstream docs (researcher to fetch current as of 2026-04-25)

- AWS CDK Python `aws_lambda` docs — `Function.current_version`, `Function.add_alias`, `Alias.add_auto_scaling` (not needed), `ProvisionedConcurrencyConfiguration`. Researcher verifies the correct attribute name and type signature for the Alias construct's PC argument.
- AWS CDK `aws_apigatewayv2_integrations` — `HttpLambdaIntegration` constructor signature when target is an `Alias` rather than a `Function`. The integration should accept an alias IFunction directly but verify with current docs.
- AWS Lambda Provisioned Concurrency docs — PC attach latency (~1–3 min), billing semantics (per-hour of reservation), behaviour when alias version is updated (PC migrates to new version automatically).
- AWS API Gateway v2 HTTP API docs — integration target update semantics under stack policy (should PC toggle trigger a stack update that's blocked by `Update:*` deny? Planner confirms via CFN changeset inspection during planning).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `api_lambda/handler.py::handler()` — the existing entry point. Phase 7 extends this function; no new handler file. The prewarm branch is a 5–10 line addition near the top of the function (after customer_id validation, before the main invoke). The marker-strip + log is 2–4 lines after `body = json.loads(...)`.
- `api_lambda/handler.py::_error()` — unchanged; still the source of 400/404/502/504/500 responses per D-12. Prewarm branch does NOT use `_error` (never returns 5xx), so a dedicated `_prewarm_success()` helper or inline `return {"statusCode": 204, ...}` is fine.
- `api_lambda/handler.py::_agentcore_client` module-level client — reused by both paths (D-05). No second client instance.
- `api_lambda/handler.py::_CUSTOMER_ID_PATTERN` — D-13 regex. Runs before prewarm branch dispatch so a malformed customer_id always returns 400, regardless of `?prewarm` flag.
- `infrastructure/constructs/backend_api.py` BundlingOptions boto3>=1.42.0 — already bundled. No new runtime deps.
- `tests/test_backend_api_handler.py` — existing offline test conventions (MagicMock `_agentcore_client`, fixture-based event payloads, `caplog` for log assertions). Phase 7 tests follow exactly.
- `tests/test_backend_api_synth.py` — existing CDK assertions.Template pattern. Phase 7 adds 3–4 new assertions.

### Established Patterns

- **Pass-through pattern (Phase 3 D-02).** API Lambda never enriches, wraps, or reshapes the agent response — it forwards verbatim. Phase 7's marker-strip is the only deviation and is justified by Phase 6 D-03 as explicitly-designed-to-be-stripped internal metadata. Narrative fields flow through under the existing verbatim contract — no new enrichment surface.
- **Fresh uuid4 per invocation (Phase 3 D-11).** Both the normal lookup and the prewarm branch mint a new uuid4 per call. AP-3 in ARCHITECTURE.md: NEVER cache session IDs for pre-warm keep-alive purposes.
- **Error taxonomy via `_error()` (Phase 3 D-12).** Only the normal lookup path uses `_error` for 400/404/502/504/500 mapping. Prewarm is a separate response family (204 only, logged failures) and intentionally does not participate in the error taxonomy.
- **Structured logging via `logger.info("...", customer_id=..., ...)`.** Phase 3 established `logging.getLogger(__name__)` with the `LOG_LEVEL` env var override. Phase 7's `narrative_source` and `prewarm_failed` logs follow the same pattern (JSON-ish structured values passed as kwargs or serialised into the message).
- **Module-level init for reused clients + regex.** Phase 7 adds no new module-level state.
- **CDK context flags via `self.node.try_get_context("...")`.** v1.0 used this for `demo_pc=0` default patterns in the milestones research; Phase 7 makes it a real toggle.

### Integration Points

- **Upstream (Phase 6):** The agent response body (parsed JSON) contains `green.usage_narrative`, `green.call_script`, `cheapest.usage_narrative`, `cheapest.call_script`, plus a top-level `_narrative_source` dict `{"usage_narrative": "model"|"fallback", "call_script": "model"|"fallback"}`. Phase 7 pops that top-level key and passes the rest through.
- **Downstream (Phase 8):** The UI receives the exact agent response body minus `_narrative_source`. UI's extended `TrackInfo` TS type (Phase 8 scope) has optional `usage_narrative?` and `call_script?` fields — backward-compatible if the Lambda ever returns them missing.
- **Downstream (Phase 9):** `scripts/prewarm.py` consumes the `?prewarm=1` → 204 contract established here. The `narrative_source` CloudWatch log (D-07) is queryable by the end-to-end eval harness. The stable alias ARN + deterministic PC behaviour (D-09 through D-12) gives Phase 9's `demo-keepalive.sh` a stable target.
- **Downstream (Phase 10):** DEMO-04 freeze applies CFN stack policy `Update:*` deny on BackendApiStack at T-48h. At that time, `-c demo_pc=1` should already be set and PC pinned at 1. The `live` alias + conditional PC design (D-09, D-11) was specifically chosen so the alias ARN never changes across PC-on/PC-off deploys, minimising freeze-surface risk.
- **No IAM change** — the existing Lambda execution role has `bedrock-agentcore:InvokeAgentRuntime` scoped to `[agent_runtime_arn, {agent_runtime_arn}/*]` (covers the runtime-endpoint sub-resource). Prewarm calls hit the same action on the same resource. No new permissions.
- **No new stack** — changes live entirely inside `BackendApiStack` / `BackendApiConstruct`. `FoundationStack` and `AgentCoreStack` are untouched.

</code_context>

<specifics>
## Specific Ideas

- **The `?prewarm=1` branch is additive-only to the existing handler**, not a replacement. The normal lookup path (lines 55–106 of `api_lambda/handler.py`) remains structurally unchanged except for the 2–4 line marker-strip + log insertion. The prewarm branch is a ~15-line block that can be read top-to-bottom in isolation: check flag → invoke → 204 or log+204. No shared state between the two paths beyond the module-level client.
- **The `narrative_source` structured log is the only new observability surface Phase 7 adds to the demo-day runtime.** It is zero-PII (enum `"model"|"fallback"` per field), CloudWatch-queryable, and bridges the gap between Phase 6's AgentCore-layer log and Phase 9's eval harness. This is an intentional investment — it makes the "did the fallback path fire end-to-end?" question answerable from a single CloudWatch query during demo-day debugging.
- **PC=1 is sufficient for a 3-persona rotation with 2s spacing.** Each warm turn is ~1500–2500ms (ARCHITECTURE.md latency budget). With PC=1 and microVM pool depth of 1, consecutive calls reuse the warm slot. `demo_pc=2` is available if a presenter later wants belt-and-braces depth; Phase 7 does not pin the default at 2 because it doubles PC billing for no meaningful demo benefit.
- **Alias-always-exists is the freeze-surface-critical decision.** Under D-09, the API Gateway integration ARN never changes across deploys, regardless of whether PC is configured. This means DEMO-04's CFN stack policy (Phase 10) can deny `Update:*` on BackendApiStack without blocking legitimate PC toggle scenarios (the toggle mutates the alias's PC config, not the integration).
- **D-15 live smoke is a closeout gate, not a pytest.** The warm-median check requires multiple `curl` invocations with `curl -w "%{time_total}"` post-`cdk deploy`, plus a ≥3-minute wait for PC to warm up. Expressing this as pytest would tempt the implementation into replacing it with a mocked variant; the plan keeps it as a documented runbook step so it can't be accidentally weakened. The successor (`scripts/prewarm.py` in Phase 9) inherits and automates this.
- **Do not regress v1.0 tests.** `pytest -m "not smoke"` must stay green (81 passed / 6 skipped at v1.0 close, confirmed green after Phase 6 + 06.1). Phase 7 adds offline tests only; no existing test file is deleted or modified beyond additions.

</specifics>

<deferred>
## Deferred Ideas

- **`scripts/prewarm.py` operator tooling + `scripts/demo-keepalive.sh`** — Phase 9 scope (DEMO-03 tooling half + DEMO-05). Phase 7 delivers only the Lambda-side target.
- **End-to-end narrative eval harness across 10 × 3 × 2 invocations via live API** — Phase 9 scope. The `narrative_source` CloudWatch log (D-07) is the groundwork.
- **`X-Prewarm-Status` warning response header** (considered under D-04) — rejected: adds a contract surface no operator script currently consumes; CloudWatch tail is the canonical observability channel per D-04.
- **Prewarm body with `{"prewarm_failed": true, ...}` on failure** (considered under D-04) — rejected: SC-2 is HTTP-status-based; body-content variance would bind `scripts/prewarm.py` to a non-trivial response schema for a never-reaches-the-UI path.
- **Presenter tooltip (alt-click reveals raw LLM + verdict)** — Phase 8 UI work. Requires the `_narrative_source` marker to survive the API Lambda; Phase 7 D-06 explicitly strips it. If this feature is revived, Phase 8 would need a debug-only endpoint or environment toggle that preserves the marker.
- **Hard in-Lambda timeout budget on narrative generation (<1500ms else fallback)** — considered in Phase 6 CONTEXT.md deferred; belongs more naturally in Phase 9's keep-alive infra (or, strictly, in the agent Lambda's invoke() wrapping). Phase 7's 25s read_timeout is the outer bound; tighter budgets are not a Phase 7 concern.
- **CloudWatch alarm on `prewarm_failed > N/min`** — v3.0 production hardening. Demo is single-shot; alarms add surface without saving presenter actions.
- **Explicit `/prewarm` route or `/prewarm/{customer_id}` dedicated route** — rejected in D-01. Revisit only if Phase 9 reveals operational friction with `?prewarm=1` query flag (unlikely; `scripts/prewarm.py` hides the URL shape from the operator entirely).
- **Dedicated `_agentcore_client` with shorter read_timeout for prewarm** — rejected in D-05. Revisit only if observed prewarm p99 exceeds the normal lookup p99 materially.
- **Provisioned Concurrency always-on** — explicitly rejected in FEATURES.md and D-11. PC attaches only when `-c demo_pc=N` (N≥1) is passed; default deploys remain zero-cost.
- **`cdk deploy -c demo_pc=N` as `CfnOutput`** — considered in Claude's Discretion; recommend no. `aws lambda get-provisioned-concurrency-config` is the authoritative check.
- **Phase 7 UAT beyond D-15 live smoke** — Phase 9 eval harness is the deeper validation layer. Phase 7's gate is "plumbing works + UI-02 holds."

</deferred>

---

*Phase: 07-api-pass-through-pre-warm-route*
*Context gathered: 2026-04-25*
