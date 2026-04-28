---
phase: 12-customerdataprovider-abstraction
plan: 01
subsystem: agent-provider-abstraction
tags: [providers, protocol, strangler-fig, PROD-01, D-01, D-03, D-04, D-10, D-11, D-13, D-16]
requirements_completed: [PROD-01, PROD-01a, PROD-01b, PROD-01c]
dependency_graph:
  requires:
    - "lambda/handler.py::simulate_savings_pure (InMemoryProvider.simulate_savings imports this offline; D-04)"
    - "infrastructure/seed_data/billing_records.py (ALL_RECORDS + PROFILE_ITEMS feed InMemoryProvider; D-10)"
    - "lambda/tariff_plans.json (InMemoryProvider loads plans from here; tests/conftest.py treats this as source of truth)"
  provides:
    - "agent/providers.py::CustomerDataProvider Protocol (@runtime_checkable, 3 methods)"
    - "agent/providers.py::ToolsLambdaProvider (production boto3 invoke path)"
    - "agent/providers.py::InMemoryProvider (offline test double, byte-exact savings)"
    - "agent/providers.py::SalesforceCustomerDataProvider (DOC-03 presenter stub)"
    - "agent/providers.py::set_provider / get_provider (module-level swap helpers; D-11)"
  affects:
    - "Plan 12-02: ToolsLambdaProvider's {action, customer_id} payload shape is what the new Lambda dispatcher will route"
    - "Plan 12-04: tests/test_providers.py will exercise InMemoryProvider + Salesforce stub + Protocol isinstance"
    - "Plan 12-05: agent/agent.py module-init will call set_provider(ToolsLambdaProvider(...))"
tech_stack:
  added: []
  patterns:
    - "Protocol + @runtime_checkable (PEP 544) — duck-typed interface, isinstance-checkable"
    - "Strangler-fig seam — abstraction introduced before callers re-point to it (Plan 12-05 completes the swap)"
    - "Constructor injection for boto3 client (D-03) — no module-scope boto3 in providers.py"
    - "Module-level singleton with explicit swap (D-11) — greppable set_provider / get_provider"
    - "Offline test double reuses production pure helper (simulate_savings_pure) — D-04 invariant: math stays in Lambda"
key_files:
  created:
    - "agent/providers.py: 218 lines — Protocol + 3 concrete impls + singleton helpers"
  modified: []
decisions:
  - "InMemoryProvider filters PROFILE rows in __init__ (mirrors lambda/handler.py:181 contract) to prevent PROFILE bleed into billing history."
  - "ToolsLambdaProvider.simulate_savings is a concrete method NOT on the Protocol (D-04) — production savings math stays in Tools Lambda, but the provider still exposes a single invoke path for agent/agent.py to call."
  - "InMemoryProvider.simulate_savings uses `importlib.import_module('lambda.handler')` rather than top-level `from lambda.handler import ...` because `lambda` is a Python reserved keyword and breaks static imports. Offline-only code path."
  - "SalesforceCustomerDataProvider raises NotImplementedError with the exact DOC-03 breadcrumb string '.planning/docs/presenter/DEFERRED-ROADMAP.md (Phase 16)' — greppable from presenter deck."
metrics:
  duration_minutes: 14
  completed_at: "2026-04-28T21:45:59Z"
  tasks_completed: 2
  files_modified: 1
---

# Phase 12 Plan 01: CustomerDataProvider Abstraction Summary

Created `agent/providers.py` as the strangler-fig seam for PROD-01. Exposes a `@runtime_checkable` `CustomerDataProvider` Protocol with three methods (`get_customer`, `get_billing_history`, `get_hardship_flag`) and three concrete implementations: `ToolsLambdaProvider` (production boto3 invoke with `{action, customer_id}` payloads), `InMemoryProvider` (offline test double seeded from Phase 11 `ALL_RECORDS` + `PROFILE_ITEMS` + `lambda/tariff_plans.json`), and `SalesforceCustomerDataProvider` (DOC-03 presenter stub). Plus module-level `set_provider` / `get_provider` helpers for explicit-swap discipline (D-11).

## What Shipped

### Task 1: Protocol + ToolsLambdaProvider + singleton helpers (commit `80f5e59`)

- `@runtime_checkable class CustomerDataProvider(Protocol)` — 3 methods only (LD-5).
- `class ToolsLambdaProvider` — consolidates boto3 `invoke` + `json.dumps`/`loads` + `FunctionError` handling through a single `_invoke` helper that mirrors `agent/agent.py:255-270` verbatim (SAV-03: no new invoke path).
- Per-method `{action, customer_id}` payload shape (D-01).
- Concrete `simulate_savings` on `ToolsLambdaProvider` (NOT on the Protocol) — D-04 math stays in Lambda.
- `set_provider` / `get_provider` module-level singleton helpers (D-11). `get_provider()` raises `RuntimeError("provider not initialised — call set_provider() first")` when called before any swap.
- No boto3 import at module scope — client injected via constructor (D-03).

### Task 2: InMemoryProvider + SalesforceCustomerDataProvider (commit `b203c07`)

- `class InMemoryProvider` — seeds from `ALL_RECORDS` + `PROFILE_ITEMS` + `lambda/tariff_plans.json` (D-10). Groups records by `customer_id` (filtering `month == "PROFILE"` rows to match `lambda/handler.py:181`). Indexes profile rows separately for `get_hardship_flag` lookups.
- `InMemoryProvider.simulate_savings` reuses `simulate_savings_pure` offline (via `importlib.import_module('lambda.handler')` — `lambda` is a reserved word). Byte-exact Sarah $30/$55, Marcus $16.90/$30.98, Elena $14.00/$25.67.
- `class SalesforceCustomerDataProvider` — parameterless constructor; every method raises `NotImplementedError` with the DOC-03 breadcrumb string. SObject chain (Account → ServicePoint → BillingAccount → Usage) named in class docstring.
- All three concrete providers satisfy `isinstance(CustomerDataProvider)` via `@runtime_checkable`.

## Verification Results

All from the plan's `<verify><automated>` blocks, run on Python 3.13:

- `from agent.providers import CustomerDataProvider, ToolsLambdaProvider, InMemoryProvider, SalesforceCustomerDataProvider, set_provider, get_provider` — clean import.
- `isinstance(ToolsLambdaProvider(MagicMock(), 'arn'), CustomerDataProvider)` → True.
- `isinstance(InMemoryProvider(), CustomerDataProvider)` → True.
- `isinstance(SalesforceCustomerDataProvider(), CustomerDataProvider)` → True.
- `SalesforceCustomerDataProvider().get_customer('CUST-001')` raises `NotImplementedError` containing `"DOC-03"`.
- `InMemoryProvider().simulate_savings('CUST-001')` returns `green.saving_monthly == 30.00`, `cheapest.saving_monthly == 55.00`.
- `InMemoryProvider().simulate_savings('CUST-002')` returns `green.saving_monthly == 16.90`, `cheapest.saving_monthly == 30.98`.
- `InMemoryProvider().simulate_savings('CUST-003')` returns `green.saving_monthly == 14.00`, `cheapest.saving_monthly == 25.67`.
- `set_provider` / `get_provider` round-trip verified.
- `get_provider()` raises `RuntimeError("provider not initialised")` before any `set_provider()` call.

Structural greps all pass: `class CustomerDataProvider`, `@runtime_checkable`, `class ToolsLambdaProvider`, `class InMemoryProvider`, `class SalesforceCustomerDataProvider`, `def set_provider`, `def get_provider`, `DOC-03`, `.planning/docs/presenter/DEFERRED-ROADMAP.md`, `ALL_RECORDS`, `PROFILE_ITEMS`, `simulate_savings_pure`, `FunctionError`, `"TOOLS_LAMBDA_ARN not set"`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — plan-spec slip] `grep -c "def get_customer\|def get_billing_history\|def get_hardship_flag"` assertion**

- **Found during:** Task 2 automated verify
- **Issue:** Plan asserted the grep would return exactly 10. Actual count is 12: `Protocol` contributes 3 stub declarations + 3 concrete classes × 3 methods = 9 concrete + 3 Protocol = 12.
- **Fix:** No code change needed — the semantic intent (all three methods exist on all three providers + Protocol) is satisfied. Noting here for the planner's reference.
- **Files modified:** None.

## Self-Check: PASSED

- [x] `agent/providers.py` created (218 lines)
- [x] Task 1 commit `80f5e59` present in `git log`
- [x] Task 2 commit `b203c07` present in `git log`
- [x] Protocol + 3 concrete impls + 2 module helpers all importable
- [x] isinstance checks pass for all 3 providers against Protocol
- [x] InMemoryProvider reproduces Phase 11 byte-exact savings for Sarah / Marcus / Elena
- [x] SalesforceCustomerDataProvider emits DOC-03 breadcrumb on all 3 methods
- [x] set_provider / get_provider round-trip works; get_provider pre-init raises RuntimeError
- [x] No boto3 at module scope (D-03)
- [x] No simulate_savings on the Protocol itself (D-04)
