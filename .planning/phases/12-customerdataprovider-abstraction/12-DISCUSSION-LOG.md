# Phase 12: CustomerDataProvider Abstraction - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-28
**Phase:** 12-customerdataprovider-abstraction
**Areas discussed:** Provider seam — where it plugs in, SAV-03 byte-exact proof, InMemoryProvider scope + test wiring, Salesforce stub — what it looks like

---

## Provider seam — where it plugs in

### Q1. What sits behind the CustomerDataProvider Protocol methods on ToolsLambdaProvider?

| Option | Description | Selected |
|--------|-------------|----------|
| Raw Lambda-invoke pass-through | Provider methods issue their own _lambda_client.invoke with per-method `{action, customer_id, ...}` payloads. Tools Lambda grows an `action` dispatcher. Closest to Phase 13 future shape. | ✓ |
| Provider wraps only what's needed today | Three Protocol methods minimal; simulate_savings stays raw. Smallest blast radius but kicks the dispatcher work to Phase 13. | |
| Full strangler — simulate_savings routes through provider too | Agent does arithmetic locally. Biggest SAV-03 risk. Wrong choice. | |

**User's choice:** Raw Lambda-invoke pass-through
**Notes:** Aligns with ARCHITECTURE.md §4 option (a) and pre-empts Phase 13's dispatcher work.

### Q2. How does Tools Lambda respond to the new Protocol calls?

| Option | Description | Selected |
|--------|-------------|----------|
| Add an `action` dispatcher now | `handler(event, context)` dispatches on `event['action']`. Existing entrypoints stay back-compat. CustomerTariff lift required. | ✓ |
| Leave Lambda unchanged; provider marshals to existing entrypoints | No `action` field. Problem: get_hardship_flag_pure has no Lambda entrypoint today. | |
| You decide | — | |

**User's choice:** Add an `action` dispatcher now
**Notes:** Phase 13 only adds new helpers afterward; dispatcher is phased-13-future-proofing.

### Q3. Where does the provider instance live on the agent side?

| Option | Description | Selected |
|--------|-------------|----------|
| Module-level singleton `_provider = ToolsLambdaProvider(...)` | Mirrors `_lambda_client` pattern at agent.py:60. Tests swap via module-level setter. Greppable. | ✓ |
| Per-invocation instance inside invoke() | Fresh provider per call. Over-engineered. | |
| Factory pattern (get_provider() accessor) | Slightly more ceremony. | |

**User's choice:** Module-level singleton
**Notes:** Matches existing v1.0 pattern; test swap is explicit and greppable.

### Q4. Does simulate_savings @tool refactor or stay single-round-trip?

| Option | Description | Selected |
|--------|-------------|----------|
| Stay single-round-trip | simulate_savings @tool calls provider.simulate_savings(id); Lambda runs math server-side. SAV-03 byte-exact by construction. | ✓ |
| Split into two provider calls in the agent | Arithmetic in two places. Wrong choice. | |

**User's choice:** Stay single-round-trip
**Notes:** ARCHITECTURE.md §4 "Invariants Preserved" — arithmetic stays in Tools Lambda.

### Q5. Back-compat for existing Lambda entrypoints?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep both — action dispatcher routes to existing functions | `if "action" in event: dispatch else: default to simulate_savings`. Safest rollback room. | ✓ |
| Break compat — only action-shaped events work | Atomic but no rollback room mid-phase. | |
| You decide | — | |

**User's choice:** Keep both
**Notes:** Atomic-commit discipline preserved; staged swap-in possible.

---

## SAV-03 byte-exact proof

### Q6. How is SAV-03 byte-exact proven on the live runtime for all 5 personas?

| Option | Description | Selected |
|--------|-------------|----------|
| Capture pre-refactor responses, diff against post-refactor | New `scripts/capture_live_recommendations.py`; baseline stored under .planning/phases/12-.../baseline/. | ✓ |
| Extend tests/test_narrative_eval_live.py smoke suite | Live smoke with constant expected values. Leverages Phase 9 harness. | |
| Both — pre/post-diff AND smoke extension | Pre/post-diff is one-shot gate; smoke is permanent regression gate. | |
| Offline pytest only; trust live deploy | Lean but thin on deploy evidence. | |

**User's choice:** Capture pre-refactor live responses, diff against post-refactor responses
**Notes:** Presenter-friendly evidence; "here's the proof we didn't change the numbers" is the story.

### Q7. CustomerTariffAgent stack-policy lift timing?

| Option | Description | Selected |
|--------|-------------|----------|
| Lift + redeploy now, re-apply at Phase 12 close | Phase 12 owns one full ceremony on CustomerTariffAgent + CustomerTariff. Phase 13/14/15 each own their own. | ✓ |
| Lift once at Phase 12, keep lifted through Phase 15, re-apply once at Phase 17 | Less ceremony, less auditability. | |
| You decide | — | |

**User's choice:** Lift + redeploy now, re-apply at Phase 12 close
**Notes:** Mirrors v2.0 Phase 10 ceremony per-phase discipline.

### Q8. Narrative fields in the byte-exact proof?

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude narrative + _narrative_source | Diff on plan_id / plan_name / saving_monthly / saving_annual only. | ✓ |
| Include narrative, re-run D-15 validators | Catches narrative regression but stochastic drift risk. | |
| Full byte-equal including narrative | Stochastic — false positives every deploy. Wrong. | |

**User's choice:** Exclude narrative + _narrative_source
**Notes:** D-15 validators already cover narrative correctness via Phase 9 harness.

### Q9. Offline pre-deploy gate?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — `pytest tests/test_providers.py` with InMemoryProvider driving all 6 mock_* fixtures | Hard pre-deploy gate. Matches ROADMAP SC #3 directly. | ✓ |
| No — rely on existing simulate_savings pytests | Misses SC #3. | |

**User's choice:** Yes — hard pre-deploy gate
**Notes:** Green offline = green to lift stack.

---

## InMemoryProvider scope + test wiring

### Q10. Where does InMemoryProvider source persona data?

| Option | Description | Selected |
|--------|-------------|----------|
| Re-import from infrastructure/seed_data/billing_records.py | ALL_RECORDS + PROFILE_ITEMS + TARIFF_PLANS. Zero drift. | ✓ |
| New fixture-style in tests/conftest.py | Drift risk vs seed_data. | |
| InMemoryProvider data-agnostic; tests build dicts | Verbose for happy path. | |

**User's choice:** Re-import from infrastructure/seed_data/billing_records.py
**Notes:** Preserves Phase 11 byte-exact invariant automatically.

### Q11. How do tests inject InMemoryProvider?

| Option | Description | Selected |
|--------|-------------|----------|
| Module-level setter + autouse conftest fixture | providers.py exposes set_provider(impl); conftest swaps/restores. Explicit seam. | ✓ |
| monkeypatch.setattr(agent.agent, '_provider', ...) | Idiomatic pytest but less discoverable. | |
| Dependency injection via @tool args | Breaks Strands @tool conventions. | |

**User's choice:** Module-level setter + autouse conftest fixture
**Notes:** Explicit, greppable, matches v1.0 pattern.

### Q12. What does tests/test_providers.py assert?

| Option | Description | Selected |
|--------|-------------|----------|
| isinstance() Protocol satisfaction | ROADMAP SC #2 requires this. @runtime_checkable runtime check. | ✓ |
| Byte-exact savings for CUST-001..006 via InMemoryProvider | Core SC #3 gate. 6 persona parametrization. | ✓ |
| SalesforceCustomerDataProvider raises NotImplementedError on all three methods | ROADMAP SC #4 explicit test. | ✓ |
| PROFILE filter behaviour via InMemoryProvider | Already covered by Phase 11 test_get_billing_history. | |

**User's choice:** isinstance() + byte-exact savings CUST-001..006 + Salesforce NotImplementedError (3 of 4)
**Notes:** PROFILE filter not re-tested; Phase 11 D-21 already covers.

---

## Salesforce stub — what it looks like

### Q13. How 'real' does the Salesforce stub look?

| Option | Description | Selected |
|--------|-------------|----------|
| Skeleton with SObject docstrings | Each method raises NotImplementedError with real docstring naming SObjects (Account, ServicePoint, BillingAccount, Hardship_Flag__c). No SDK imports. | ✓ |
| Bare stub — just `raise NotImplementedError` | Minimum; weakens DOC-03 presenter story. | |
| Fully-scaffolded with simple_salesforce import | Violates 'no new dependencies' constraint. | |

**User's choice:** Skeleton with SObject docstrings
**Notes:** Real field names signal domain awareness for DOC-03; zero dep cost.

### Q14. Where does the stub live and when does it raise?

| Option | Description | Selected |
|--------|-------------|----------|
| Same file as Protocol (agent/providers.py), NotImplementedError at method-call time | All 4 symbols in one file. isinstance() works because __init__ succeeds. | ✓ |
| Separate file agent/providers_salesforce.py | Breaks one-glance abstraction story. | |
| Raises at __init__ time | Fails isinstance() test because you can't instantiate. | |

**User's choice:** Same file as Protocol, NotImplementedError at method-call time
**Notes:** Strangler-fig visible in one glance.

### Q15. DOC-03 reference now, or breadcrumb?

| Option | Description | Selected |
|--------|-------------|----------|
| Leave breadcrumb only — Phase 16 owns DOC-03 | Stub docstring references .planning/docs/presenter/DEFERRED-ROADMAP.md (Phase 16). | ✓ |
| Phase 12 writes a placeholder DOC-03 skeleton | Scope creep across phase boundary. | |

**User's choice:** Leave breadcrumb only
**Notes:** Respects Phase 16 requirement ownership per ROADMAP.md.

---

## Claude's Discretion

- Exact payload marshalling helper shape inside `ToolsLambdaProvider._invoke(payload)` — consolidate duplicated `_lambda_client.invoke` pattern or leave raw at two sites.
- Whether `get_customer` stub returns `{customer_id}` only or richer shape this phase.
- Test file organisation: single `tests/test_providers.py` or split.
- Exact symbol name for PROFILE records list in `billing_records.py`.
- Whether `capture_live_recommendations.py` lives under `scripts/` or `.planning/phases/12-.../`.
- Whether to add `pytest -m bimode` tag for container-side import verification.

## Deferred Ideas

- Consent flags on `get_customer` (PROD-03, v3.1+).
- Audit trail on provider calls (PROD-04, v3.1+).
- Circuit breaker for downstream CRM failures (PROD-05, v3.1+).
- `get_tariff_catalog` as a Protocol method — defer until a real CRM integration motivates it.
- Shared `common/` package (AP-3 anti-pattern — not doing this).
- Per-tool Lambda functions (AP-1 anti-pattern).
- Constructor injection of provider into @tool wrappers (breaks Strands conventions).
- Presenter DOC-03 content (Phase 16 ownership).
- Fully-scaffolded Salesforce stub with `simple_salesforce` import (Phase 15 owns deps).
- Container-side bi-mode import as a smoke-tier pytest marker (planner decides).
