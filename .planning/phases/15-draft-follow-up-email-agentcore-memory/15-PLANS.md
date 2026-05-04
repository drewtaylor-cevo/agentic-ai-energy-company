# Phase 15 Plan Decomposition — Draft Follow-Up Email via AgentCore Memory (WF-01)

## Plan overview

| Plan | Name | Wave | Depends on | Files |
|------|------|------|------------|-------|
| 15-01 | Dependency bump + Memory CDK construct + agent memory module | 1 | — | `requirements.in`, `requirements.txt`, `agent/requirements.txt`, `agent/Dockerfile`, `agent/memory/`, `infrastructure/agentcore_stack.py`, `infrastructure/constructs/agent_runtime.py` |
| 15-02 | FollowUpEmailResponse model + agent draft_follow_up() + fallback templates | 1 | — | `agent/agent.py`, `agent/narrative/fallbacks.py`, `agent/narrative/validators.py` |
| 15-03 | API Lambda follow-up route + handler tests | 1 | — | `api_lambda/handler.py`, `infrastructure/constructs/backend_api.py`, `tests/test_backend_api_handler.py` |
| 15-04 | Offline agent tests (follow-up + Memory isolation + invariant guards) | 2 | 15-01, 15-02 | `tests/test_follow_up.py`, `tests/conftest.py` |
| 15-05 | UI FollowUpDrawer + useFollowUp hook + mock fixtures + `?narrative=off` | 2 | 15-02, 15-03 | `ui/src/components/FollowUpDrawer.tsx`, `ui/src/hooks/useFollowUp.ts`, `ui/src/App.tsx`, `ui/src/lib/types.ts`, `ui/src/lib/mock/` |
| 15-06 | Stack-policy lift ceremony + close-gates + re-freeze | 3 | 15-01..05 | ceremony artifacts, `autonomous: false` |

## Plan details

### 15-01: Dependency bump + Memory CDK construct + agent memory module

**Goal:** The `bedrock-agentcore` dependency is bumped to 1.6.4, the AgentCore Memory resource is provisioned via CDK, and the agent container has the memory module available for import.

**Changes:**

1. **Dependency bump:**
   - Update `requirements.in`: `bedrock-agentcore==1.6.3` → `bedrock-agentcore==1.6.4`
   - Regenerate `requirements.txt` via `pip-compile --generate-hashes requirements.in`
   - Fresh-venv gate: `pip install --require-hashes -r requirements.txt` must succeed
   - Full `pytest` suite must pass with the new dependency (no regression)
   - Update `agent/requirements.txt` for container build (if separate from root)

2. **CDK Memory construct in `infrastructure/agentcore_stack.py`:**
   ```python
   from aws_cdk import Duration
   from aws_cdk import aws_bedrock_agentcore_alpha as agentcore

   # Short-term only Memory (LD-3: no long-term strategies)
   memory = agentcore.Memory(
       self, "TariffAgentMemory",
       memory_name="tariff_agent_memory",
       description="Short-term session memory for follow-up email workflow",
       expiration_duration=Duration.hours(12),
       # No memory_strategies — short-term only per LD-3
   )
   ```
   - Write Memory ID to SSM: `/customer-tariff/memory-id`
   - Pass `memory_id` to `AgentRuntimeConstruct` as new kwarg

3. **Update `infrastructure/constructs/agent_runtime.py`:**
   - Accept `memory_id: str` kwarg
   - Add `MEMORY_ID` to `environment_variables` dict
   - Add IAM policy for Memory operations:
     ```python
     iam.PolicyStatement(
         effect=iam.Effect.ALLOW,
         actions=[
             "bedrock-agentcore:CreateEvent",
             "bedrock-agentcore:ListEvents",
             "bedrock-agentcore:RetrieveMemoryRecords",
         ],
         resources=["*"],  # Memory ARN not available as CDK token; scope at deploy
     )
     ```

4. **Create `agent/memory/` module:**
   - `agent/memory/__init__.py` — empty
   - `agent/memory/config.py`:
     ```python
     def build_memory_config(memory_id: str, customer_id: str, session_date: str) -> "AgentCoreMemoryConfig":
         """Build Memory config with deterministic session_id and customer-scoped actorId."""
         from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
         return AgentCoreMemoryConfig(
             memory_id=memory_id,
             session_id=f"{customer_id}-{session_date}",
             actor_id=f"customer:{customer_id}",
         )

     def build_session_manager(config: "AgentCoreMemoryConfig", region: str) -> "AgentCoreMemorySessionManager":
         """Build Strands-compatible session manager."""
         from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
         return AgentCoreMemorySessionManager(
             agentcore_memory_config=config,
             region_name=region,
         )
     ```

5. **Update `agent/Dockerfile`:**
   - Add `COPY memory/ ./memory/` after existing COPY lines

6. **Bi-mode imports in `agent/agent.py`:**
   ```python
   try:
       from memory.config import build_memory_config, build_session_manager
   except ImportError:
       from agent.memory.config import build_memory_config, build_session_manager
   ```

**Success criteria:**
- `pip install --require-hashes -r requirements.txt` succeeds in fresh venv with `bedrock-agentcore==1.6.4`
- `pytest` full suite passes (no regression from dep bump)
- `cdk synth CustomerTariffAgent` succeeds with Memory resource in template
- `docker build agent/` succeeds and `python -c "from memory.config import build_memory_config"` works inside container
- Bi-mode import works in both container and repo layout

**Pitfall prevention:** C4 (actorId structural isolation baked into `build_memory_config`), AP-2 (session_id vs runtimeSessionId documented in config.py docstrings)

---

### 15-02: FollowUpEmailResponse model + agent draft_follow_up() + fallback templates

**Goal:** The agent can produce a follow-up email draft for a customer whose recommendation was stored in Memory, with D-15-extended validators and D-04 fallback path.

**Changes:**

1. **Add `FollowUpEmailResponse` Pydantic model to `agent/agent.py`:**
   ```python
   class FollowUpEmailResponse(BaseModel):
       kind: Literal["follow_up"] = "follow_up"
       customer_id: str
       subject: str = Field(max_length=120)
       body: str = Field(max_length=500)
       plan_reference: str

       @field_validator("body", mode="after")
       @classmethod
       def validate_body(cls, value: str) -> str:
           return _reject_forbidden(value, max_words=100, field_label="body")

       @field_validator("subject", mode="after")
       @classmethod
       def validate_subject(cls, value: str) -> str:
           return _reject_forbidden(value, max_words=20, field_label="subject")
   ```

2. **Add `_FOLLOW_UP_SYSTEM_PROMPT` to `agent/agent.py`:**
   - Instructs the agent to draft a follow-up email referencing the prior recommendation
   - Includes the same numeric-integrity rules as `_BASE_SYSTEM_PROMPT` (SAV-03)
   - Specifies the email must reference the plan name (not plan ID) and avoid all banned terms
   - Instructs the agent NOT to recalculate savings — reference the prior turn's figures by citing the plan name only

3. **Add `draft_follow_up()` function to `agent/agent.py`:**
   ```python
   def draft_follow_up(payload: dict) -> dict:
       """Handle a follow-up email draft request.

       Expects payload: {"customer_id": "CUST-001", "action": "follow_up"}
       Returns: {"kind": "follow_up", "customer_id": "...", "subject": "...", "body": "...", "plan_reference": "..."}
       """
   ```
   - Build Memory config with deterministic session_id
   - Create session manager and Agent with `session_manager=...`
   - Call agent with `_FOLLOW_UP_SYSTEM_PROMPT`
   - Use `structured_output_model=FollowUpEmailResponse`
   - On success: return model_dump() with `_workflow_source` marker
   - On failure: D-04 fallback to deterministic template from FALLBACKS

4. **Wire `draft_follow_up` into the `@app.entrypoint` `invoke()` dispatcher:**
   ```python
   action = payload.get("action", "recommend")
   if action == "follow_up":
       return draft_follow_up(payload)
   # ... existing recommendation path
   ```

5. **Add follow-up fallback templates to `agent/narrative/fallbacks.py`:**
   ```python
   # Per-persona follow-up email templates
   "CUST-001": {
       ...,
       "follow_up": {
           "subject": "Your tariff options from our recent conversation",
           "body": "Thank you for speaking with us about your energy plan options. As discussed, we identified plans that could better suit your household usage pattern. Please review the options at your convenience and contact us if you would like to proceed.",
           "plan_reference": "EcoFlex Green",
       },
   },
   ```
   - Add follow-up templates for all 5 recommendation personas (CUST-001 through CUST-005)
   - All templates must pass D-15 validators (no digits, no currency, no banned terms)

6. **Extend `_reject_forbidden` usage for follow-up body:**
   - The existing `_reject_forbidden` function already accepts `max_words` parameter
   - Follow-up body uses `max_words=100` (longer form than usage_narrative's 20)
   - Same banned-terms gauntlet applies

**Success criteria:**
- `FollowUpEmailResponse` model validates with D-15 rules
- `draft_follow_up({"customer_id": "CUST-001", "action": "follow_up"})` returns `kind: "follow_up"` shape
- Fallback templates for all 5 personas pass `_reject_forbidden` (import-time assertion)
- D-04: any exception in `draft_follow_up` returns a fallback template, never raises
- `_workflow_source` marker attached to response

**Pitfall prevention:** D-04 (never-500 via except Exception fallback), D-15 (banned-terms on email body/subject), SAV-03 (no arithmetic in follow-up path — plan_reference is name only)

---

### 15-03: API Lambda follow-up route + handler tests

**Goal:** `GET /recommendations/{customer_id}/follow-up` returns a follow-up email draft via the same API Lambda, with proper routing, error handling, and `_workflow_source` stripping.

**Changes:**

1. **Add route to `infrastructure/constructs/backend_api.py`:**
   ```python
   api.add_routes(
       path="/recommendations/{customer_id}/follow-up",
       methods=[apigwv2.HttpMethod.GET],
       integration=integ.HttpLambdaIntegration("FollowUpIntegration", live_alias),
   )
   ```

2. **Add `follow_up()` function to `api_lambda/handler.py`:**
   ```python
   def follow_up(customer_id: str, event: dict, context) -> dict:
       """Handle GET /recommendations/{customer_id}/follow-up."""
       # D-11: fresh uuid4 per invocation (SC-3 preserved)
       session_id = str(uuid.uuid4())
       logger.info("Follow-up invoke customer_id=%s session_id=%s", customer_id, session_id)

       try:
           response = _agentcore_client.invoke_agent_runtime(
               agentRuntimeArn=_AGENT_RUNTIME_ARN,
               runtimeSessionId=session_id,
               payload=json.dumps({
                   "customer_id": customer_id,
                   "action": "follow_up",
               }).encode(),
           )
           body = json.loads(response["response"].read())
           # Strip internal markers
           body.pop("_workflow_source", None)
           body.pop("_narrative_source", None)
       except ReadTimeoutError:
           logger.warning("Follow-up timeout customer_id=%s", customer_id)
           return _error(504, "Follow-up service timed out. Please try again.")
       except ClientError as exc:
           error_code = exc.response.get("Error", {}).get("Code", "Unknown")
           logger.error("Follow-up ClientError customer_id=%s code=%s", customer_id, error_code)
           return _error(502, "Follow-up service error. Please try again.")
       except Exception as exc:
           logger.error("Follow-up unexpected error customer_id=%s: %s", customer_id, exc, exc_info=True)
           return _error(500, "Internal server error.")

       # Validate response shape
       if body.get("kind") != "follow_up":
           logger.warning("Follow-up unexpected shape customer_id=%s body=%s", customer_id, body)
           return _error(502, "Follow-up service returned unexpected response.")

       return {
           "statusCode": 200,
           "headers": {"Content-Type": "application/json"},
           "body": json.dumps(body),
       }
   ```

3. **Add route detection in `handler()`:**
   ```python
   # At the top of handler(), after customer_id extraction and D-13 regex check:
   raw_path = event.get("rawPath", "")
   if raw_path.endswith("/follow-up"):
       return follow_up(customer_id, event, context)
   ```

4. **Add handler tests to `tests/test_backend_api_handler.py`:**
   - `test_follow_up_returns_200`: mock agent returns follow-up body → HTTP 200
   - `test_follow_up_strips_workflow_source`: `_workflow_source` not in response body
   - `test_follow_up_bad_customer_id_returns_400`: invalid format → 400
   - `test_follow_up_timeout_returns_504`: ReadTimeoutError → 504
   - `test_follow_up_client_error_returns_502`: ClientError → 502
   - `test_follow_up_unexpected_shape_returns_502`: missing `kind: "follow_up"` → 502
   - `test_existing_recommendation_route_unchanged`: existing path still works

**Success criteria:**
- `GET /recommendations/CUST-001/follow-up` routes to `follow_up()` function
- `GET /recommendations/CUST-001` still routes to existing recommendation path (no regression)
- `_workflow_source` stripped from response
- D-13 regex check applies to follow-up route (bad customer_id → 400)
- Error taxonomy matches existing recommendation route (504/502/500)
- All existing handler tests pass unchanged

**Pitfall prevention:** SC-3 (fresh uuid4 per invocation in follow_up()), D-04 (error taxonomy mirrors recommendation route), `_workflow_source` strip (parallel to `_narrative_source`)

---

### 15-04: Offline agent tests (follow-up + Memory isolation + invariant guards)

**Goal:** Follow-up email generation is locked by offline tests, including cross-customer isolation canary and D-15 validator coverage.

**Changes:**

1. **Add `tests/test_follow_up.py`:**
   - `TestFollowUpResponse`:
     - `test_follow_up_returns_kind_follow_up`: mock provider + mock Memory → `kind: "follow_up"`
     - `test_follow_up_has_required_fields`: subject, body, plan_reference all present
     - `test_follow_up_body_passes_d15`: body contains no digits, no currency, no banned terms
     - `test_follow_up_subject_passes_d15`: subject contains no digits, no currency, no banned terms
     - `test_follow_up_plan_reference_is_name_not_id`: plan_reference is a plan name (e.g. "EcoFlex Green"), not a plan ID (e.g. "ECO")
   - `TestFollowUpFallback`:
     - `test_follow_up_memory_failure_returns_fallback`: mock Memory raises → fallback template returned
     - `test_follow_up_agent_failure_returns_fallback`: mock agent raises → fallback template returned
     - `test_follow_up_fallback_passes_d15`: all fallback templates pass validators
   - `TestFollowUpIsolation`:
     - `test_memory_config_actor_id_scoped_to_customer`: assert `actorId == f"customer:{customer_id}"`
     - `test_memory_config_session_id_deterministic`: same customer + same date → same session_id
     - `test_memory_config_different_customers_different_actor_ids`: CUST-001 vs CUST-002 → different actorIds
   - `TestFollowUpInvariantGuards`:
     - `test_recommendation_path_unchanged`: `invoke({"customer_id": "CUST-001"})` still returns `kind: "recommendation"` (REC-03)
     - `test_hardship_path_unchanged`: `invoke({"customer_id": "CUST-006"})` still returns `kind: "hardship"` (AGENT-02)
     - `test_follow_up_no_savings_arithmetic`: body contains no dollar figures (SAV-03 extension)

2. **Add fixtures to `tests/conftest.py`:**
   - `mock_follow_up_response`: fixture with expected follow-up shape for CUST-001
   - `mock_follow_up_cust002_response`: fixture for CUST-002 (cross-customer canary pair)

3. **Extend `tests/test_bill_shock_flow.py::TestCrossPersonaCanary`:**
   - Add follow-up shape assertion for recommendation personas

**Success criteria:**
- All follow-up tests pass offline (no AWS required)
- D-15 validators enforced on follow-up body and subject
- Memory isolation tests prove structural actorId scoping
- Existing recommendation and hardship paths unchanged
- Fallback path tested and D-04 preserved

**Pitfall prevention:** C4 (structural isolation verified in test), D-15 (validator coverage on new surface), D-04 (fallback path tested)

---

### 15-05: UI FollowUpDrawer + useFollowUp hook + mock fixtures + `?narrative=off`

**Goal:** The UI renders a "Draft follow-up email" button after a successful recommendation, opens a drawer with the editable draft, and `?narrative=off` collapses it.

**Changes:**

1. **Add `FollowUpEmailResponse` type to `ui/src/lib/types.ts`:**
   ```typescript
   export interface FollowUpEmailResponse {
     kind: 'follow_up';
     customer_id: string;
     subject: string;
     body: string;
     plan_reference: string;
   }
   ```

2. **Create `ui/src/hooks/useFollowUp.ts`:**
   - State machine: `idle | loading | success | error`
   - `fetchFollowUp(customerId: string)` — calls `GET /recommendations/{customerId}/follow-up`
   - Mock fallback when `VITE_API_URL` unset (same pattern as `useRecommendations`)
   - AbortController for cancellation

3. **Create `ui/src/components/FollowUpDrawer.tsx`:**
   - Renders below the recommendation cards when triggered
   - "Draft follow-up email" button (primary action)
   - On click: calls `fetchFollowUp`, shows loading skeleton
   - On success: renders subject (read-only) + body (editable textarea) + "Copy to clipboard" button
   - Uses shadcn `Card`, `Button`, `Textarea`, `Skeleton` primitives
   - Accessible: proper ARIA labels, keyboard navigation
   - `?narrative=off` → component renders null (collapsed)

4. **Update `ui/src/App.tsx`:**
   - Import `FollowUpDrawer` and `useFollowUp`
   - Render `FollowUpDrawer` below the card grid in the `success` state
   - Pass `customerId` and follow-up hook state/actions as props
   - Reset follow-up state when a new lookup is triggered

5. **Add follow-up mock responses to `ui/src/lib/mock/recommendations.ts`:**
   - `MOCK_FOLLOW_UP_RESPONSES` keyed by customer_id
   - Byte-sync with Python fallback strings in `agent/narrative/fallbacks.py`

6. **Add CUST-004/005 to persona chips if not already present.**

7. **Vitest tests:**
   - `FollowUpDrawer.test.tsx`: renders button, shows drawer on click, displays subject/body, copy button works
   - `useFollowUp.test.ts`: state transitions, mock mode, error handling
   - `?narrative=off` collapse test: drawer not rendered when flag is set
   - Snapshot test at 1280×800: both cards + collapsed drawer above fold (UI-01)

**Success criteria:**
- "Draft follow-up email" button appears after successful recommendation lookup
- Clicking button fetches follow-up and renders editable draft
- `?narrative=off` collapses the drawer (not rendered)
- Mock mode serves follow-up responses for all recommendation personas
- All existing UI tests pass (no regression)
- UI-01: both recommendation cards remain above fold at 1280×800 with drawer collapsed

**Pitfall prevention:** LD-7 (`?narrative=off` single-flag contract), UI-01 (drawer below fold, collapsed by default)

---

### 15-06: Stack-policy lift ceremony + close-gates + re-freeze (autonomous: false)

**Goal:** Deploy Phase 15 changes to the live stack and verify end-to-end, including cross-customer Memory isolation.

**Changes:**

1. **Pre-capture baseline:**
   - Capture recommendation responses for CUST-001/002/003/004/005 (SAV-03 byte-equivalence)
   - Capture CUST-006 hardship response (AGENT-02 preserved)

2. **Lift deny-Update:* on target stacks:**
   - `CustomerTariffAgent` (container rebuild + Memory resource + MEMORY_ID env var + IAM)
   - `CustomerTariffApi` (new follow-up route)
   - `CustomerTariff` only if Memory resource lands there (verify via `cdk diff`)

3. **`cdk deploy` target stacks**

4. **Close-gates:**
   - SAV-03 byte-equivalence on CUST-001/002/003/004/005 (existing personas unchanged)
   - CUST-006 returns HTTP 200 with `kind: "hardship"` (AGENT-02 preserved)
   - CUST-001 follow-up returns HTTP 200 with `kind: "follow_up"` body
   - Follow-up body contains no digits, no currency, no banned terms (D-15)
   - Follow-up `plan_reference` matches a known plan name
   - **Cross-customer isolation canary (MANDATORY):**
     - Lookup CUST-001 recommendation
     - Lookup CUST-002 recommendation
     - Follow-up CUST-002 → body contains zero CUST-001 tokens (no plan names, no customer name, no dollar figures from CUST-001)
   - CUST-999 still returns HTTP 404 (customer-not-found preserved)
   - `?prewarm=1` still returns 204 (prewarm contract preserved)
   - `pytest -m smoke -x` green
   - `pip install --require-hashes -r requirements.txt` in fresh venv (lockfile contract)

5. **Re-apply freeze + termination protection**

6. **Post-ceremony:**
   - Run `scripts/prewarm.py` with follow-up route added to rotation
   - Commit ceremony log
   - Document FREEZE-MANIFEST lockfile-hash placeholder for Phase 17

**Success criteria:**
- All close-gates pass
- Cross-customer isolation canary PASSES (mandatory — phase blocker if it fails)
- Stacks re-frozen with byte-equal policies
- Ceremony log committed
- FREEZE-MANIFEST placeholder documented

**Pitfall prevention:** C4 (live cross-customer isolation canary — most critical gate), C6 (scripted lift+reapply), D-04 (follow-up never 500 on live stack)
