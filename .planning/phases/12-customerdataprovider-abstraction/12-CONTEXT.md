# Phase 12: CustomerDataProvider Abstraction - Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Agent-side customer-data access flows through a production-shaped adapter interface (`agent/providers.py`) with three concrete implementations (`ToolsLambdaProvider` — DynamoDB via Tools Lambda, `InMemoryProvider` — offline test double, `SalesforceCustomerDataProvider` — DOC-03 in-flight stub), shipped via a strangler-fig around the existing agent tool path. SAV-03 byte-exact savings are preserved on the deployed runtime for CUST-001..005 through the new indirection layer, verified by a pre/post live-diff ceremony + offline InMemoryProvider gate.

**Out of scope (belongs elsewhere):**
- Bill-shock multi-tool flow (Phase 13 — AGENT-01) and its new `@tool` wrappers (`detect_bill_shock`, `get_customer_profile`). Phase 12 only creates the seam; Phase 13 extends it.
- Hardship short-circuit discriminated union + `api_lambda/handler.py:152` detection update (Phase 14 — AGENT-02). Phase 12 exposes `get_hardship_flag` as a Protocol method and action but does NOT wire a pre-LLM guard.
- AgentCore Memory resource + follow-up route (Phase 15 — WF-01).
- DOC-03 (`.planning/docs/presenter/DEFERRED-ROADMAP.md`) content — Phase 12 only leaves a breadcrumb; Phase 16 owns the presenter markdown.
- Dependency bumps — Phase 12 ships zero new packages. Phase 15 owns the single permitted `bedrock-agentcore` 1.6.3 → 1.6.4 bump.
- Amplify `CustomerTariffFrontend` redeploy. No UI work this phase.

</domain>

<decisions>
## Implementation Decisions

### Provider Seam — Where It Plugs In

- **D-01: `ToolsLambdaProvider` methods each issue their own `_lambda_client.invoke` with per-method payload shape.** `get_billing_history(customer_id)` → `{action: "get_billing_history", customer_id}`; `get_hardship_flag(customer_id)` → `{action: "get_hardship_flag", customer_id}`; `get_customer(customer_id)` → `{action: "get_customer", customer_id}`. Each method returns the decoded JSON body. Matches ARCHITECTURE.md §4 option (a) and the ToolsLambdaProvider code example at lines 406–426.
- **D-02: `lambda/handler.py` grows a top-level `handler(event, context)` action dispatcher in Phase 12.** Routes on `event.get("action")`: `"get_billing_history"` → existing `get_billing_history(event, context)`; `"get_hardship_flag"` → new wrapper calling `get_hardship_flag_pure(customer_id, table)`; `"simulate_savings"` → existing `simulate_savings(event, context)`; `"get_customer"` → stub returning `{customer_id}` for now (placeholder — Phase 13/14 may extend). Missing `action` field defaults to `simulate_savings` behaviour for back-compat (D-05). Phase 13 no longer needs to add the dispatcher — only new helpers.
- **D-03: Module-level singleton `_provider = ToolsLambdaProvider(_lambda_client, _TOOLS_LAMBDA_ARN)` in `agent/agent.py`.** Mirrors the existing `_lambda_client` pattern at `agent/agent.py:60`. All `@tool` wrappers call `_provider.method(...)`. Test swap via module-level setter (D-11), not constructor injection.
- **D-04: `simulate_savings` @tool stays single-round-trip via the provider.** The @tool becomes `@tool def simulate_savings(customer_id): return _provider.simulate_savings(customer_id)` (provider method routes to `action: "simulate_savings"`). Tools Lambda still runs `get_billing_history` + `simulate_savings_pure` server-side and returns `{green, cheapest}`. **Arithmetic stays in Tools Lambda** — provider is a wrapper, never a new math path. SAV-03 byte-exact held by construction (ARCHITECTURE.md §4 "Invariants Preserved" line: "arithmetic still in Tools Lambda, provider is just a wrapper").
  - **Planner note:** `simulate_savings` is NOT a Protocol method — the Protocol has exactly three methods per ROADMAP SC #2 (`get_customer`, `get_billing_history`, `get_hardship_flag`). `simulate_savings` lives as a concrete method on `ToolsLambdaProvider` + `InMemoryProvider` only, invoked by the @tool wrapper. Alternatively, if keeping `simulate_savings` outside the Protocol offends the shape, the @tool can call `provider.get_billing_history(id)` + a locally-imported `simulate_savings_pure` — **but that moves arithmetic into the agent container** and breaks D-04. **Stay with provider.simulate_savings as a concrete method outside the Protocol.** Confirm during planning.
- **D-05: Lambda handler keeps back-compat for action-less events.** `if "action" in event: dispatch else: return simulate_savings(event, context)`. Existing callers (chiefly the agent's current `_lambda_client.invoke(...{customer_id})` at `agent/agent.py:258` and the API Lambda's fallback path at `agent/agent.py:394`) keep working through Phase 12 even if provider swap-in is staged across commits.

### SAV-03 Byte-Exact Proof

- **D-06: Pre/post live-diff is the phase-close deploy gate.** New script `scripts/capture_live_recommendations.py` (stdlib-only, mirroring `scripts/prewarm.py` style) hits `/recommendations/{id}` for CUST-001..005, stores the 5 JSON bodies at `.planning/phases/12-customerdataprovider-abstraction/baseline/pre/{customer_id}.json` before the refactor. Post-deploy: re-hit, store under `baseline/post/`, and a diff assertion passes if numeric fields are byte-equal. Exit taxonomy matches `prewarm.py` (0 = diff clean, 1 = diff drift / gate fail, 2 = setup error).
- **D-07: Phase 12 owns a full lift → deploy → byte-equality re-apply ceremony on BOTH `CustomerTariffAgent` (container rebuild for provider seam) AND `CustomerTariff` (Tools Lambda asset for action dispatcher).** Ceremony re-executes cleanly per phase per v2.0 Phase 10 precedent. `CustomerTariffApi` is NOT lifted this phase (no API Lambda changes). Termination protection re-enabled after re-apply. `cdk diff == 0` gate passes on the re-apply commit.
- **D-08: Diff compares numeric fields only: `plan_id`, `plan_name`, `saving_monthly`, `saving_annual` on both `green` and `cheapest` tracks.** Narrative fields (`usage_narrative`, `call_script`) and the `_narrative_source` marker are excluded — D-15 validators already cover narrative correctness; narrative text is stochastic per LLM invocation and would produce false positives on every deploy.
- **D-09: `tests/test_providers.py` is a hard pre-deploy gate.** InMemoryProvider is seeded with the exact Phase 11 records (ALL_RECORDS + PROFILE_ITEMS + TARIFF_PLANS), drives all six `mock_*_response` fixtures (CUST-001..006), and asserts byte-exact savings on every persona. Green offline = green to lift stack. Command: `pytest tests/test_providers.py -v` must pass before `aws cloudformation set-stack-policy` for the lift.

### InMemoryProvider Scope + Test Wiring

- **D-10: InMemoryProvider sources data from `infrastructure/seed_data/billing_records.py` + `lambda/tariff_plans.json` by re-import.** Constructor: `InMemoryProvider(billing_records=ALL_RECORDS, profile_items=PROFILE_ITEMS, tariff_plans=TARIFF_PLANS)`. Single source of truth — the same records the live seeder writes to DynamoDB. Zero drift risk between live and offline by construction. Preserves Phase 11's byte-exact invariant automatically.
  - **Planner note:** `PROFILE_ITEMS` is the Phase 11 D-09 structure (list of dicts of shape `{customer_id, month: "PROFILE", hardship_flag}`); confirm the exact symbol name during planning — may be `PROFILE_RECORDS` or similar.
- **D-11: `agent/providers.py` exposes `set_provider(impl: CustomerDataProvider) -> None` module-level setter + `get_provider() -> CustomerDataProvider` accessor.** `tests/conftest.py` adds an autouse fixture `_provider_swap` that saves the current provider, calls `set_provider(InMemoryProvider(...))` at test start, restores the original on teardown. Tests write `def test_foo(inmemory_provider): ...` and the fixture yields the swapped InMemoryProvider. Explicit swap seam, greppable via `git grep set_provider`. Matches v1.0 module-level-singleton pattern.
- **D-12: `tests/test_providers.py` asserts exactly three categories of behaviour:**
  1. **Protocol `isinstance()` satisfaction.** `isinstance(ToolsLambdaProvider(mock_lambda_client, "arn"), CustomerDataProvider) is True`; same for `InMemoryProvider(...)` and `SalesforceCustomerDataProvider()`. `@runtime_checkable` required on the Protocol definition.
  2. **Byte-exact savings for CUST-001..006 via InMemoryProvider.** Parametrized `@pytest.mark.parametrize("customer_id,expected", [...])` using `mock_savings_response` / `mock_marcus_response` / `mock_elena_response` / `mock_cust004_response` / `mock_cust005_response` / `mock_cust006_response` fixtures. Calls `provider.simulate_savings(customer_id)` under the hood and compares on numeric fields.
  3. **SalesforceCustomerDataProvider raises NotImplementedError on all three methods.** Three `with pytest.raises(NotImplementedError):` asserts — `get_customer`, `get_billing_history`, `get_hardship_flag`.
  PROFILE-row filter behaviour already covered by `tests/test_get_billing_history.py` from Phase 11 D-21 — not re-tested here.

### Salesforce Stub Shape

- **D-13: `SalesforceCustomerDataProvider` is a skeleton with SObject docstrings.** Each method raises `NotImplementedError("Salesforce adapter not implemented — see DOC-03 at .planning/docs/presenter/DEFERRED-ROADMAP.md (Phase 16)")`. Each method carries a real docstring naming the Salesforce Energy & Utilities Cloud SObjects it would query:
  - `get_customer(customer_id)` — "Salesforce `Account` SObject, matched by `External_Customer_Id__c`."
  - `get_billing_history(customer_id)` — "Salesforce `ServicePoint` + `BillingAccount` + `Usage` SObjects, joined by ServicePoint.BillingAccountId."
  - `get_hardship_flag(customer_id)` — "Salesforce `Account.Hardship_Flag__c` custom boolean field."
  NO `simple_salesforce` imports — Phase 12 bumps zero deps. No `__init__` args — stays constructible so isinstance() works.
- **D-14: All four symbols live in `agent/providers.py`: `CustomerDataProvider` (Protocol), `ToolsLambdaProvider`, `InMemoryProvider`, `SalesforceCustomerDataProvider`.** Single file, strangler-fig visible in one glance. `__init__` on all three impls succeeds (needed for `isinstance()` tests); only method calls raise on the Salesforce impl.
- **D-15: Phase 12 leaves DOC-03 as a breadcrumb only.** No `.planning/docs/presenter/` file created this phase. Stub docstring includes the future path; Phase 16 owns the content. Prevents scope creep across the phase boundary.

### Bi-Mode Import Pattern (inherited invariant)

- **D-16: `agent/providers.py` follows the existing bi-mode import convention** from `agent/agent.py:26-51`. Inside `agent.py`:
  ```python
  try:
      from providers import (
          CustomerDataProvider, ToolsLambdaProvider,
          InMemoryProvider, SalesforceCustomerDataProvider,
          set_provider, get_provider,
      )
  except ImportError:  # pragma: no cover - offline repo layout
      from agent.providers import (...)
  ```
  Dockerfile `COPY . /app` already picks up `providers.py`; container `import providers` resolves; repo pytest `import agent.providers` resolves. Matches `narrative/` precedent. ROADMAP SC #5 verifies both imports succeed.
- **D-17: Bi-mode import verification is part of the Phase 12 test suite.** Offline: `python -c "from agent.providers import CustomerDataProvider"` must succeed. Container: `docker run --entrypoint python tariff_agent:latest -c "from providers import CustomerDataProvider"` must succeed. Second form likely added to the smoke-tier tests or a one-shot verification during deploy ceremony — planner decides exact placement.

### Claude's Discretion

- Exact payload marshalling helper shape inside `ToolsLambdaProvider._invoke(payload)` — private method consolidating the `_lambda_client.invoke` + `json.dumps` + `FunctionError` handling pattern currently duplicated at `agent/agent.py:258-270` and `agent/agent.py:394-399`. Consolidation is welcome; leaving them separate and living with the duplication is also acceptable (provider code is the consolidation seam anyway).
- Whether `get_customer` stub returns `{customer_id}` only or also `{customer_id, display_name: None, hardship_flag: bool}` this phase. Phase 14 may need richer shape; Phase 12 can ship minimal.
- Test file organisation: single `tests/test_providers.py` OR split into `test_providers_protocol.py` + `test_providers_inmemory.py` + `test_providers_salesforce.py`. Single file keeps the strangler-fig story visible; split files scale for Phase 13+.
- Exact symbol name for hardship PROFILE records list in `billing_records.py` (may be `PROFILE_ITEMS`, `PROFILE_RECORDS`, `ALL_PROFILE_ROWS` — confirm during plan).
- Whether the `capture_live_recommendations.py` script is committed to `scripts/` (permanent artefact, demo-friendly) or lives under `.planning/phases/12-.../` (one-shot phase-close tool). Planner picks.
- Whether to add a **`pytest -m bimode` tag** for the container-side bi-mode import check, or fold it into the standard smoke tier.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap

- `.planning/ROADMAP.md` §"Phase 12: CustomerDataProvider Abstraction" — phase goal, 5 success criteria, invariant ownership statement (SAV-03 preservation through indirection, bi-mode import pattern, Chesterton's Fence risk on `simulate_savings_pure`).
- `.planning/REQUIREMENTS.md` §"Production Shape (PROD)" — PROD-01, PROD-01a, PROD-01b, PROD-01c requirement IDs with exact acceptance language.
- `.planning/REQUIREMENTS.md` §"Locked Decisions" — **LD-5 PROD-01 scope** (Protocol + DynamoDB + InMemory + NotImplementedError Salesforce stub; 3 methods only — no consent/audit/circuit-breaker in v3.0) is the load-bearing constraint for this phase; **LD-1 build order** places PROD-01 immediately after DATA-04 so new tools land through the abstraction from day 1.
- `.planning/PROJECT.md` §"Current Milestone: v3.0" — target features: `CustomerDataProvider` abstraction scoped with Salesforce `NotImplementedError` stub as a committed presenter artefact.
- `.planning/STATE.md` §"Invariants the v3.0 roadmap must preserve" — bi-mode imports rule specific to this phase; SAV-03 byte-exact on the recommendation branch; stack-policy lift ceremony.

### Research (v3.0)

- `.planning/research/ARCHITECTURE.md` §"4. PROD-01 — CustomerDataProvider Abstraction" (lines 366–464) — three-option comparison table; decision matrix for option (a); Protocol code example; `ToolsLambdaProvider` + `InMemoryProvider` skeleton at lines 406–436; integration points table at lines 453–459.
- `.planning/research/ARCHITECTURE.md` §"Pattern 4: Protocol-Based Provider Abstraction (PROD-01 enabler)" (lines 804–813) — `@runtime_checkable` rationale; size discipline (3–4 methods max).
- `.planning/research/ARCHITECTURE.md` §"AP-3: Shared `common/` package for provider abstraction" (lines 835–841) — what to avoid; bi-mode preservation rationale.
- `.planning/research/ARCHITECTURE.md` §"Phase 2: PROD-01 — CustomerDataProvider abstraction" (lines 912–924) — sequenced build plan with deliverables, unblocks, invariants-at-risk.
- `.planning/research/FEATURES.md` §"Category 5 — CustomerDataProvider Adapter (PROD-01)" (lines 276+) — Salesforce Energy & Utilities Cloud SObject inventory informing D-13 docstrings (Account, ServicePoint, Billing Account, Premise, Usage Point).
- `.planning/research/PITFALLS.md` — C7 (Chesterton's Fence on `simulate_savings_pure`: wrap AROUND, never through), bi-mode import regression (broken container entry if `providers.py` not COPYed), C6 stack-policy lift+reapply ceremony.
- `.planning/research/STACK.md` — confirms Phase 12 touches `CustomerTariff` (Tools Lambda asset for action dispatcher) + `CustomerTariffAgent` (container rebuild); `CustomerTariffApi` untouched.

### Prior phase context (carry-forward)

- `.planning/phases/11-new-personas-tariff-archetypes/11-CONTEXT.md` §"Hardship Flag Placement" — D-08 (PROFILE row shape `{customer_id, month: "PROFILE", hardship_flag: true}` on `tariff-billing` table), D-10 (`get_hardship_flag_pure` pure helper signature), D-21 (PROFILE filter inside `get_billing_history` — Phase 12 relies on this; do NOT duplicate the filter in provider methods).
- `.planning/phases/11-new-personas-tariff-archetypes/11-CONTEXT.md` §"TOU Dispatcher Refactor" — D-13 byte-exact gate: existing `mock_savings_response` / `mock_marcus_response` / `mock_elena_response` + new `mock_cust004_response` / `mock_cust005_response` / `mock_cust006_response` fixtures. Phase 12 re-uses these byte-for-byte in `tests/test_providers.py`.

### Load-bearing project-level docs

- `CLAUDE.md` §"Critical invariants — break these and the demo dies" — **SAV-03 (LLM never does arithmetic)** constrains D-04; **Bi-mode imports in `agent/agent.py`** establishes the pattern D-16 follows; **D-04 never-500 contract** applies to `invoke()` fallback path which retains its direct Lambda call at `agent/agent.py:394-417`.
- `CLAUDE.md` §"Common commands" — `pytest` and `cdk deploy` sequences that Phase 12 extends (new `pytest tests/test_providers.py` line; `cdk deploy CustomerTariff CustomerTariffAgent`).
- `CLAUDE.md` §"Things to know before changing things" — `demo-v2.0` frozen stacks require deny-Update:* lift via `aws cloudformation set-stack-policy`; stack-policy files under `infrastructure/stack-policies/`.
- `DEMO-RUNBOOK.md` §freeze section + stack-policy lift ceremony — scratch-stack test pattern Phase 11 preserved and Phase 12 must re-execute for the Tools Lambda asset change.

### Source code to read before touching

- `agent/agent.py:26-51` — bi-mode import pattern (template for D-16).
- `agent/agent.py:60` — `_lambda_client = boto3.client("lambda", region_name=_REGION)` — module-level singleton (template for D-03).
- `agent/agent.py:241-270` — `simulate_savings` @tool + `_lambda_client.invoke` pattern (template for `ToolsLambdaProvider._invoke`).
- `agent/agent.py:394-418` — v1.0 tool-failure fallback `except Exception` path with direct `_lambda_client.invoke`. Phase 12 may route this through the provider OR leave it as raw (D-04 allows either; planner decides based on D-04 preservation safety).
- `lambda/handler.py:60-140` — `simulate_savings_pure` dispatcher with `plan_type` branches (Chesterton's Fence — do NOT touch).
- `lambda/handler.py:143-161` — `get_hardship_flag_pure` helper (Phase 11 D-10) — Phase 12 wraps this in the `"get_hardship_flag"` action branch.
- `lambda/handler.py:166-183` — `get_billing_history` Lambda handler with PROFILE filter.
- `lambda/handler.py:185-190` — existing `simulate_savings` Lambda handler — retained as back-compat path per D-05.
- `tests/conftest.py` — `mock_savings_response` / `mock_marcus_response` / `mock_elena_response` / `mock_cust004_response` / `mock_cust005_response` / `mock_cust006_response` fixtures (test targets for D-09/D-12).
- `infrastructure/seed_data/billing_records.py` — `ALL_RECORDS` + PROFILE items source of truth (D-10 InMemoryProvider data source).
- `scripts/prewarm.py` — style template for new `scripts/capture_live_recommendations.py` (D-06) — stdlib-only, 0/1/2 exit taxonomy.
- `infrastructure/stack-policies/` — freeze lift + deny-Update policy files.

### Stacks touched

- `CustomerTariff` — **LIFT required**. Tools Lambda asset rebuild for action dispatcher (D-02).
- `CustomerTariffAgent` — **LIFT required**. Container rebuild for `agent/providers.py` + `agent/agent.py` provider wiring (D-01, D-03, D-04, D-16).
- `CustomerTariffApi` — **NO LIFT**. API Lambda unchanged this phase.
- `CustomerTariffFrontend` — **NO CHANGE**. Amplify untouched.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`_lambda_client` module-level singleton at `agent/agent.py:60`** — template and wire target for `ToolsLambdaProvider(__init__).lambda_client` injection. Provider takes the existing client, never creates a new one. No boto3 client duplication.
- **Bi-mode import pattern at `agent/agent.py:26-51`** — template for `providers.py` imports from `agent.py`. Same try/except, same `pragma: no cover - offline repo layout` annotation.
- **`_lambda_client.invoke` + `json.dumps` + `FunctionError` handling at `agent/agent.py:258-270`** — pattern to consolidate into `ToolsLambdaProvider._invoke(payload)`. Also appears at `agent/agent.py:394-399` in the fallback path.
- **`simulate_savings_pure` + `simulate_savings` Lambda handler pattern at `lambda/handler.py:60-140` + `lambda/handler.py:185-190`** — the Tools Lambda side. Action dispatcher wraps these without rewriting.
- **`get_hardship_flag_pure` helper at `lambda/handler.py:143-161`** (Phase 11 D-10) — already offline-testable with injectable `table_client`. Dispatcher just calls it with the module-level `table`.
- **`_CUSTOMER_ID_PATTERN` + `_validate_customer_id` at `lambda/handler.py:39-52`** — input validation; action dispatcher reuses before routing.
- **Existing `tests/conftest.py` `mock_*_response` fixture family** — targets for `tests/test_providers.py` parametrized byte-exact assertions.
- **`infrastructure/seed_data/billing_records.py::ALL_RECORDS` + PROFILE items** — InMemoryProvider constructor payload by re-import. Same data the DynamoDB seeder writes.
- **`scripts/prewarm.py` stdlib-only style + 0/1/2 exit taxonomy** — template for `scripts/capture_live_recommendations.py`.
- **Stack-policy lift ceremony scripts at `infrastructure/stack-policies/`** — v2.0 Phase 10 precedent; re-executed here for Tools Lambda asset + agent container deploy.

### Established Patterns

- **Module-level singletons** (`_lambda_client`, `_agent`) with lazy init — provider follows the same pattern (D-03).
- **Pure-helper-plus-handler** (`simulate_savings_pure` + `simulate_savings`, `get_hardship_flag_pure` + thin dispatcher branch) — Lambda dispatcher adds new handler branches without touching the pure helpers.
- **Bi-mode imports with container vs repo layout** — inherited invariant, verified by both pytest and container smoke (D-16/D-17).
- **Single-commit duplicated-file discipline** — `lambda/tariff_plans.json` ↔ `infrastructure/seed_data/tariff_plans.json`. Phase 12 does not touch these but inherits the discipline.
- **SSM parameter cross-stack wiring, not CloudFormation exports** — stacks redeploy independently. Phase 12's Tools Lambda asset diff + agent container diff deploy independently via this pattern.
- **pytest fixture autouse for test-environment setup** — new `_provider_swap` autouse fixture (D-11) joins existing fixtures in `tests/conftest.py`.

### Integration Points

- `agent/providers.py` — **NEW FILE** (all four symbols: Protocol + 3 impls + set_provider/get_provider helpers).
- `agent/agent.py` — **MODIFY**: bi-mode `from providers import ...` block (D-16), module-level `_provider = ToolsLambdaProvider(_lambda_client, _TOOLS_LAMBDA_ARN)` (D-03), `simulate_savings` @tool refactored to `return _provider.simulate_savings(customer_id)` (D-04). Fallback path at line 394 — planner decides whether to route through provider (keeps D-04 safety) or leave raw.
- `lambda/handler.py` — **MODIFY**: add top-level `handler(event, context)` action dispatcher (D-02). Existing entrypoints retained for back-compat (D-05).
- `tests/test_providers.py` — **NEW FILE**: Protocol satisfaction + byte-exact savings on 6 personas + Salesforce NotImplementedError asserts (D-12).
- `tests/conftest.py` — **MODIFY**: add `_provider_swap` autouse fixture + `inmemory_provider` fixture (D-11).
- `scripts/capture_live_recommendations.py` — **NEW FILE** (or `.planning/phases/12-.../capture_live_recommendations.py` per planner discretion): pre/post live-diff harness (D-06/D-08).
- `.planning/phases/12-customerdataprovider-abstraction/baseline/{pre,post}/` — **NEW**: captured JSON bodies for the 5 personas.
- `infrastructure/agentcore_stack.py` — **NO CODE CHANGE** but triggers a container rebuild because `agent/providers.py` is a new source file — the Dockerfile `COPY . /app` picks it up automatically. Stack-policy lift required (D-07).
- `infrastructure/foundation_stack.py` / Tools Lambda asset construct — **NO CODE CHANGE** but redeploy triggered by `lambda/handler.py` asset diff (D-02). Stack-policy lift required (D-07).

### Non-integration points (do NOT touch this phase)

- `agent/narrative/*` — no narrative changes; D-15 validators untouched.
- `agent/agent.py::RecommendationResponse` / `TrackInfo` Pydantic schemas — no discriminated union until Phase 14.
- `api_lambda/handler.py` — no change; `api_lambda/handler.py:152` customer-not-found detection is Phase 14's surgical update.
- `ui/*` — no UI changes.
- `requirements.txt` / `requirements-dev.txt` / `ui/package-lock.json` — frozen lockfiles untouched. Phase 15 owns the single permitted dep bump.
- `lambda/simulate_savings_pure` body (lines 60–140) — Chesterton's Fence. Wrap around via dispatcher, never through.
- `lambda/get_hardship_flag_pure` body (lines 143–161) — Phase 11-shipped, stable.
- `infrastructure/seed_data/billing_records.py` record data — Phase 12 reads it, never mutates it.

</code_context>

<specifics>
## Specific Ideas

- **Three Protocol methods, nothing more.** The Protocol is minimum viable: `get_customer(customer_id) -> dict`, `get_billing_history(customer_id) -> list[dict]`, `get_hardship_flag(customer_id) -> dict`. Resist the urge to add `get_tariff_catalog` or `simulate_savings` to the Protocol — tariff catalog is Lambda-local config, simulate_savings is a ToolsLambdaProvider-only method (the math lives in Tools Lambda by design, D-04). The Salesforce stub stays 3-method clean; a real CRM mapping is 3 SObject joins, not 5.
- **Strangler-fig, not rewrite.** Phase 12 adds the seam; Phase 13 is the first phase to consume new Protocol methods. The existing recommend path keeps working unchanged at the user-visible level — the only observable change is the internal `_provider.simulate_savings(id)` indirection.
- **Pre/post-diff ceremony is the story.** For the presenter narrative, the `baseline/pre/*.json` → refactor → `baseline/post/*.json` → byte-equal assertion is concrete evidence of SAV-03 discipline. Git-trackable, reviewable, reproducible. "Here's the proof we didn't change the numbers" lands harder than "tests pass."
- **DOC-03 breadcrumb pattern.** Stub docstring references `DOC-03 at .planning/docs/presenter/DEFERRED-ROADMAP.md (Phase 16)`. When Phase 16 actually writes DEFERRED-ROADMAP.md, it just cites `agent/providers.py::SalesforceCustomerDataProvider` back — the link closes itself without any retroactive edit to Phase 12's code.
- **Salesforce SObject docstrings are marketing copy for the demo.** "Salesforce Energy & Utilities Cloud: `Account` → `ServicePoint` → `BillingAccount` → `Usage`" tells the presenter story inline with zero cost. Don't fake implementation — real fields (`Hardship_Flag__c`, `External_Customer_Id__c`) signal domain awareness.

</specifics>

<deferred>
## Deferred Ideas

- **Consent flags (`consent_marketing`, `consent_data_share`) on `get_customer`** — PROD-03 per REQUIREMENTS.md §Deferred to v3.1+. Not in the 3-method Protocol (LD-5).
- **Audit trail on provider calls (`who accessed what when`)** — PROD-04. Not in v3.0.
- **Circuit breaker for downstream CRM failures** — PROD-05. Phase 12 has no retry/backoff; failures propagate up to the `except Exception` fallback at `agent/agent.py:394`.
- **`get_tariff_catalog` as a Protocol method** — Tools Lambda owns `TARIFF_PLANS` via bundled JSON asset; agent never asks for the catalog. A real Salesforce adapter would pull rates from a different system (product2 + pricebook2 or a utilities-billing SoR). Defer to when a real CRM integration motivates it.
- **Shared `common/` package for cross-layer abstraction** — AP-3 anti-pattern per ARCHITECTURE.md §"AP-3: Shared `common/` package for provider abstraction". Breaks bi-mode imports. Not doing this.
- **Per-tool Lambda functions for "clean IAM isolation"** — AP-1 anti-pattern. Phase 12 adds the dispatcher to the existing Tools Lambda; Phase 13/14 extend via helpers, not new Lambdas.
- **Constructor injection of provider into @tool wrappers** — breaks Strands `@tool` conventions (tools are stateless per-call by design). Module-level-setter pattern (D-11) chosen instead.
- **Presenter DOC-03 content** — breadcrumb only in Phase 12. Phase 16 owns `.planning/docs/presenter/DEFERRED-ROADMAP.md`.
- **Fully-scaffolded Salesforce stub with `simple_salesforce` import** — would require `requirements.txt` regen; Phase 15 owns the only permitted dep bump.
- **Container-side bi-mode import as a smoke-tier pytest marker** — may or may not be added; planner decides between `pytest -m bimode` vs folding into existing smoke.
- **Reviewed Todos (not folded):** None — no pending todos matched phase 12 scope at discussion time.

</deferred>

---

*Phase: 12-customerdataprovider-abstraction*
*Context gathered: 2026-04-28*
