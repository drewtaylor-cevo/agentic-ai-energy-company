# Phase 12: CustomerDataProvider Abstraction - Pattern Map

**Mapped:** 2026-04-28
**Files analyzed:** 6 (3 new, 3 modified)
**Analogs found:** 6/6 (full coverage — no net-new pattern territory)
**Source of scope:** `.planning/phases/12-customerdataprovider-abstraction/12-CONTEXT.md` (no RESEARCH.md for this phase)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `agent/providers.py` | new module (Protocol + 3 adapters + singleton helpers) | agent → provider → Lambda → DynamoDB | `agent/narrative/validators.py` (module shape + bi-mode header) + `agent/agent.py:241-270` (invoke pattern) | role + data-flow exact |
| `agent/agent.py` (modify) | modified module (wires provider singleton, refactors `simulate_savings` @tool) | agent → provider → Lambda | self (`agent/agent.py:26-51` bi-mode; `:60` client singleton; `:258-270` invoke) | self-referential — replicate in-file |
| `lambda/handler.py` (modify) | modified module (new `handler` action dispatcher) | Lambda entrypoint dispatch | existing `simulate_savings` + `get_billing_history` handlers at `lambda/handler.py:166-190` | exact |
| `tests/test_providers.py` | new test (Protocol + byte-exact parametrize + NotImplementedError) | offline pytest | `tests/test_get_hardship_flag_pure.py` (MagicMock client + import pattern), `tests/test_agent_tools.py:80-97` (cheapest≥green parametrize precedent), `tests/test_get_billing_history.py` (handler_module fixture) | role-match |
| `tests/conftest.py` (modify) | modified fixtures (autouse `_provider_swap` + `inmemory_provider`) | pytest fixture scope | existing `mock_*_response` fixtures at `tests/conftest.py:65-188` | role-match — sibling fixture |
| `scripts/capture_live_recommendations.py` | new script (pre/post live-diff harness) | HTTP GET → JSON file → diff | `scripts/prewarm.py` (stdlib-only, 0/1/2 exit taxonomy), `scripts/capture_samples.py` (JSON-writing precedent, boto3 invoke_agent_runtime — secondary) | exact for style + exit code; partial for content (diff logic is net-new) |

---

## Pattern Assignments

### `agent/providers.py` (new module — Protocol + 3 adapters + singleton helpers)

**Primary analog:** `agent/narrative/validators.py` (top-of-file module docstring + bi-mode import header). **Secondary analog:** `agent/agent.py:241-270` (`_lambda_client.invoke` + `json.dumps` + `FunctionError` handling — the pattern `ToolsLambdaProvider._invoke(payload)` consolidates).

#### Module header (docstring + bi-mode import)

**Copy from** `agent/narrative/validators.py:1-18`:

```python
"""Narrative field validators — UI-05 hard code-level gate.

STRIDE: V5 Input Validation. Runs inside Pydantic's `output_model(**dict)` call
inside `BedrockModel.structured_output`; ValidationError propagates up to
`invoke()`, which owns the retry-once-then-per-field-fallback policy (D-01).

D-15 dual-gate: the banned-terms list is ALSO injected as a negative constraint
in the system prompt (agent/narrative/prompt.txt). The validator is the
non-negotiable backstop per REQUIREMENTS.md UI-05.
"""
from pydantic import ValidationInfo, field_validator

# Bi-mode import: container layout is `/app/narrative/`, repo layout is
# `agent/narrative/`. See agent/agent.py for the parent rationale.
try:
    from narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX
except ImportError:  # pragma: no cover - hit only in offline test repo layout
    from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX
```

**Note on applicability:** `providers.py` does not *itself* cross the bi-mode seam (it has no sibling it imports from `narrative/` or `providers/`). The bi-mode pattern lives in `agent/agent.py` where `agent.py` consumes `providers.py` — D-16. The module docstring + `# pragma: no cover - offline repo layout` comment style is what's copied here.

#### `_invoke` helper pattern (inside `ToolsLambdaProvider`)

**Copy from** `agent/agent.py:255-270` (`simulate_savings` @tool body):

```python
# agent/agent.py:255-270
if not _TOOLS_LAMBDA_ARN:
    raise RuntimeError("TOOLS_LAMBDA_ARN not set — agent misconfigured")

resp = _lambda_client.invoke(
    FunctionName=_TOOLS_LAMBDA_ARN,
    InvocationType="RequestResponse",
    Payload=json.dumps({"customer_id": customer_id}).encode(),
)

payload = json.loads(resp["Payload"].read())

# Check for Lambda errors
if "FunctionError" in resp:
    raise RuntimeError(f"ToolsLambda error: {payload}")

return payload
```

Consolidate into `ToolsLambdaProvider._invoke(self, payload: dict) -> Any`:
- Method body: same `invoke(FunctionName=…, InvocationType="RequestResponse", Payload=json.dumps(payload).encode())` shape.
- Same `json.loads(resp["Payload"].read())` parse.
- Same `FunctionError` → `RuntimeError(f"ToolsLambda error: {payload}")` raise.
- Same empty-ARN guard: `if not self._tools_lambda_arn: raise RuntimeError("TOOLS_LAMBDA_ARN not set — …")`.

Per-method payload shapes (D-01):
```python
# ToolsLambdaProvider.get_billing_history
return self._invoke({"action": "get_billing_history", "customer_id": customer_id})

# ToolsLambdaProvider.get_hardship_flag
return self._invoke({"action": "get_hardship_flag", "customer_id": customer_id})

# ToolsLambdaProvider.get_customer
return self._invoke({"action": "get_customer", "customer_id": customer_id})

# ToolsLambdaProvider.simulate_savings  (NOT on Protocol — concrete-only per D-04 planner note)
return self._invoke({"action": "simulate_savings", "customer_id": customer_id})
```

#### Protocol definition

Per D-12 the Protocol needs `@runtime_checkable` so `isinstance(impl, CustomerDataProvider)` works. No existing file in the codebase uses `typing.Protocol` today (confirmed by the search — narrative module uses Pydantic for its contract, not Protocol). This is the pattern to introduce:

```python
from typing import Protocol, runtime_checkable, Any

@runtime_checkable
class CustomerDataProvider(Protocol):
    def get_customer(self, customer_id: str) -> dict[str, Any]: ...
    def get_billing_history(self, customer_id: str) -> list[dict[str, Any]]: ...
    def get_hardship_flag(self, customer_id: str) -> dict[str, Any]: ...
```

Exactly three Protocol methods (CONTEXT.md §"Decisions" D-12 + §"Specifics"). `simulate_savings` lives as a concrete method on `ToolsLambdaProvider` + `InMemoryProvider` only (per D-04 planner note).

#### `InMemoryProvider` data-source pattern

**Copy data-source imports from** `infrastructure/seed_data/billing_records.py:81-148`:

```python
# Constructor signature (D-10):
def __init__(
    self,
    billing_records: list[dict] | None = None,
    profile_items: list[dict] | None = None,
    tariff_plans: list[dict] | None = None,
):
    # Default to single source of truth — the same records the DynamoDB seeder writes.
    if billing_records is None:
        from infrastructure.seed_data.billing_records import ALL_RECORDS
        billing_records = ALL_RECORDS
    if profile_items is None:
        from infrastructure.seed_data.billing_records import PROFILE_ITEMS  # D-10 planner note: confirm symbol name
        profile_items = PROFILE_ITEMS
    if tariff_plans is None:
        import json, os
        _HANDLER_DIR = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(_HANDLER_DIR, "..", "lambda", "tariff_plans.json")) as f:
            tariff_plans = json.load(f)
    self._records_by_customer = ...  # group-by customer_id
    self._profiles_by_customer = ...
    self._tariff_plans = tariff_plans
```

The symbol `PROFILE_ITEMS` is verified present at `infrastructure/seed_data/billing_records.py:135` (confirmed — the planner note in D-10 can be resolved: it IS `PROFILE_ITEMS`, not `PROFILE_RECORDS`).

`InMemoryProvider.get_billing_history` must replicate the PROFILE filter from `lambda/handler.py:181` — but per CONTEXT.md D-12 the PROFILE filter behaviour is already covered by `tests/test_get_billing_history.py`; InMemoryProvider should filter PROFILE rows in its own `get_billing_history` for consistency. Copy the filter line verbatim:

```python
# lambda/handler.py:181
items = [i for i in items if i["month"] != "PROFILE"]
```

`InMemoryProvider.simulate_savings` must call `simulate_savings_pure` from `lambda/handler.py` directly — but per D-04 arithmetic stays in Tools Lambda. **Resolution:** `InMemoryProvider.simulate_savings` is the OFFLINE test double — it imports `simulate_savings_pure` for offline byte-exact assertions. The production path is `ToolsLambdaProvider.simulate_savings` which dispatches to the Lambda. Document this in the InMemoryProvider docstring so future readers don't confuse the two call sites.

#### `SalesforceCustomerDataProvider` skeleton

Per D-13 every method raises `NotImplementedError` with the DOC-03 breadcrumb. Docstrings MUST name real Salesforce SObjects:

```python
class SalesforceCustomerDataProvider:
    """Salesforce Energy & Utilities Cloud adapter — presenter stub.

    Real mapping (Phase 16 / DOC-03):
      Account → ServicePoint → BillingAccount → Usage
    No simple_salesforce dependency this phase — frozen lockfiles.
    """

    def get_customer(self, customer_id: str) -> dict:
        """Salesforce `Account` SObject, matched by `External_Customer_Id__c`."""
        raise NotImplementedError(
            "Salesforce adapter not implemented — see DOC-03 at "
            ".planning/docs/presenter/DEFERRED-ROADMAP.md (Phase 16)"
        )

    def get_billing_history(self, customer_id: str) -> list[dict]:
        """Salesforce `ServicePoint` + `BillingAccount` + `Usage` SObjects,
        joined by ServicePoint.BillingAccountId."""
        raise NotImplementedError(...)  # same message

    def get_hardship_flag(self, customer_id: str) -> dict:
        """Salesforce `Account.Hardship_Flag__c` custom boolean field."""
        raise NotImplementedError(...)  # same message
```

No `__init__` args — stays constructible so `isinstance()` checks work without mocks (D-14).

#### `set_provider` / `get_provider` singleton helpers (D-11)

**Copy pattern from** `agent/agent.py:60` — module-level singleton:

```python
# agent/agent.py:60
_lambda_client = boto3.client("lambda", region_name=_REGION)
```

Replicate structure for `providers.py`:

```python
# Module-level singleton — set at agent.py import time, swapped in tests via set_provider().
_PROVIDER: "CustomerDataProvider | None" = None


def set_provider(impl: "CustomerDataProvider") -> None:
    """Swap the active provider. Used by conftest.py _provider_swap autouse fixture.

    Greppable via `git grep set_provider` — explicit swap seam, no constructor injection.
    """
    global _PROVIDER
    _PROVIDER = impl


def get_provider() -> "CustomerDataProvider":
    """Return the active provider. Raises if set_provider() has never been called."""
    if _PROVIDER is None:
        raise RuntimeError("provider not initialised — call set_provider() first")
    return _PROVIDER
```

---

### `agent/agent.py` (modify)

Three surgical edits. Preserve every invariant at `agent/agent.py:255-418` — especially the `except Exception` fallback at `:386-418` (D-04 never-500 contract).

#### Edit 1 — add bi-mode import block (D-16)

**Insert immediately after** `agent/agent.py:51` (end of existing narrative bi-mode block), following the exact same template:

```python
# agent/agent.py:26-51 — TEMPLATE
try:
    from narrative.fallbacks import FALLBACKS
    from narrative.prompt_loader import NARRATIVE_PROMPT
    # ...
except ImportError:  # pragma: no cover - hit only in offline test repo layout
    from agent.narrative.fallbacks import FALLBACKS
    # ...
```

New block for providers:

```python
try:
    from providers import (
        CustomerDataProvider,
        ToolsLambdaProvider,
        InMemoryProvider,
        SalesforceCustomerDataProvider,
        set_provider,
        get_provider,
    )
except ImportError:  # pragma: no cover - hit only in offline test repo layout
    from agent.providers import (
        CustomerDataProvider,
        ToolsLambdaProvider,
        InMemoryProvider,
        SalesforceCustomerDataProvider,
        set_provider,
        get_provider,
    )
```

#### Edit 2 — construct provider singleton at module scope (D-03)

**Copy pattern from** `agent/agent.py:60`:

```python
# agent/agent.py:60 — TEMPLATE
_lambda_client = boto3.client("lambda", region_name=_REGION)
```

**Insert immediately after** `_lambda_client = …` (line 60):

```python
# D-03: module-level provider singleton. Swapped in tests via set_provider(InMemoryProvider(...)).
_provider = ToolsLambdaProvider(_lambda_client, _TOOLS_LAMBDA_ARN)
set_provider(_provider)
```

Key constraint: re-use `_lambda_client`. Never call `boto3.client("lambda", …)` a second time — CONTEXT.md §"Reusable Assets" first bullet.

#### Edit 3 — refactor `simulate_savings` @tool through the provider (D-04)

**Replace** `agent/agent.py:241-270` body with the provider call:

```python
# BEFORE (agent/agent.py:241-270)
@tool
def simulate_savings(customer_id: str) -> dict:
    """Calculate Green and Cheapest tariff savings for a customer.

    Returns both recommendation tracks from the deterministic savings engine.
    The numbers returned are exact — do NOT recalculate, round, or estimate them.
    ...
    """
    if not _TOOLS_LAMBDA_ARN:
        raise RuntimeError("TOOLS_LAMBDA_ARN not set — agent misconfigured")

    resp = _lambda_client.invoke(
        FunctionName=_TOOLS_LAMBDA_ARN,
        InvocationType="RequestResponse",
        Payload=json.dumps({"customer_id": customer_id}).encode(),
    )

    payload = json.loads(resp["Payload"].read())

    if "FunctionError" in resp:
        raise RuntimeError(f"ToolsLambda error: {payload}")

    return payload
```

```python
# AFTER
@tool
def simulate_savings(customer_id: str) -> dict:
    """Calculate Green and Cheapest tariff savings for a customer.

    Returns both recommendation tracks from the deterministic savings engine.
    The numbers returned are exact — do NOT recalculate, round, or estimate them.
    ...
    """
    # D-04: provider wraps the Lambda invoke; arithmetic stays in Tools Lambda.
    return get_provider().simulate_savings(customer_id)
```

The @tool docstring stays verbatim — SAV-03 system prompt language at `agent/agent.py:275-301` references the numbers being "byte-for-byte from the tool". The docstring drives Strands' tool schema for the LLM.

#### Edit 4 — fallback path at `agent/agent.py:394-418` (planner decides)

CONTEXT.md §"Integration Points" leaves this open: "planner decides whether to route through provider (keeps D-04 safety) or leave raw". Two options:

**Option A (route through provider):** Replace the `_lambda_client.invoke(…)` at `:394-399` with `get_provider().simulate_savings(customer_id)`. Benefit: single invoke pathway. Risk: if `get_provider()` itself raises, the never-500 guarantee cracks.

**Option B (leave raw):** Retain the direct `_lambda_client.invoke` call. Benefit: orthogonal fallback path cannot be corrupted by provider changes. Cost: duplicated invoke shape.

Recommend Option B to preserve the D-04 fallback as a pure defensive rail. Cite: CONTEXT.md §"Reusable Assets" third bullet acknowledges the duplication is acceptable.

---

### `lambda/handler.py` (modify — add action dispatcher, D-02)

**Analog:** existing handlers `get_billing_history` at `lambda/handler.py:166-183` and `simulate_savings` at `:185-190`.

**Copy pattern from** `lambda/handler.py:166-183`:

```python
# lambda/handler.py:166-183 — existing pattern
def get_billing_history(event: Dict[str, Any], context) -> List[Dict[str, Any]]:
    """Return 12 months of billing for a customer, sorted by month ASC.

    Raises ValueError on malformed customer_id (V5 input validation).
    Raises RuntimeError if TABLE_NAME env var is not set (fail-fast).
    """
    customer_id = _validate_customer_id(event.get("customer_id"))
    if table is None:
        raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")
    response = table.query(
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": customer_id},
    )
    items = response.get("Items", [])
    # Phase 11 D-21: filter sentinel PROFILE row so simulate_savings_pure sees only month rows
    items = [i for i in items if i["month"] != "PROFILE"]
    return sorted(items, key=lambda x: x["month"])
```

**Copy pattern from** `lambda/handler.py:185-190`:

```python
def simulate_savings(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Lambda wrapper: fetch billing, compute savings, return tracks."""
    billing = get_billing_history(event, context)
    if not billing:
        raise ValueError(f"No billing history for {event.get('customer_id')!r}")
    return simulate_savings_pure(billing, TARIFF_PLANS)
```

**New top-level `handler` dispatcher** — append after `simulate_savings`:

```python
def handler(event: Dict[str, Any], context) -> Any:
    """Phase 12 action dispatcher — routes to existing handlers.

    D-02: routes on `event["action"]`. Missing action defaults to simulate_savings
    for back-compat with v2.0 callers (D-05).
    """
    action = event.get("action")
    if action == "get_billing_history":
        return get_billing_history(event, context)
    if action == "get_hardship_flag":
        customer_id = _validate_customer_id(event.get("customer_id"))
        if table is None:
            raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")
        return get_hardship_flag_pure(customer_id, table)
    if action == "get_customer":
        # Phase 12 stub — Phase 13/14 may extend (D-02, CONTEXT §Claude's Discretion).
        customer_id = _validate_customer_id(event.get("customer_id"))
        return {"customer_id": customer_id}
    if action == "simulate_savings":
        return simulate_savings(event, context)
    # D-05 back-compat: action-less event routes to simulate_savings.
    return simulate_savings(event, context)
```

Non-touch zones (Chesterton's Fence per CONTEXT.md §"Non-integration points"):
- `simulate_savings_pure` body (lines 60–140) — do NOT touch.
- `get_hardship_flag_pure` body (lines 143–161) — do NOT touch.
- `_validate_customer_id` (lines 42-52) — reuse before routing.

CDK wiring — the Lambda Construct handler string in `infrastructure/foundation_stack.py` may still point at `handler.simulate_savings`; check whether to change it to `handler.handler`. Per CONTEXT.md the dispatcher is added without removing entrypoints (D-05 back-compat), so the CDK handler string can either switch to `handler.handler` (recommended — new unified entrypoint) OR stay at `handler.simulate_savings` (works via the "no action" default branch). Planner decides — the container-rebuild ceremony re-executes cleanly either way (D-07).

---

### `tests/test_providers.py` (new test file)

**Primary analog:** `tests/test_get_hardship_flag_pure.py` (structure, MagicMock, importlib pattern). **Secondary:** `tests/test_agent_tools.py:80-97` (byte-exact fixture consumption per persona).

#### Import + module doc pattern

**Copy from** `tests/test_get_hardship_flag_pure.py:1-8`:

```python
# tests/test_get_hardship_flag_pure.py:1-8
# tests/test_get_hardship_flag_pure.py — NEW (DATA-06 unit coverage, Phase 11-04)
import importlib
from unittest.mock import MagicMock
import pytest

# importlib fallback — `from lambda.handler import` is a SyntaxError in Python
handler = importlib.import_module("lambda.handler")
get_hardship_flag_pure = handler.get_hardship_flag_pure
```

Adapted for providers:

```python
"""Tests for agent/providers.py — Protocol satisfaction + byte-exact savings + Salesforce stub."""
import importlib
from unittest.mock import MagicMock
import pytest

from agent.providers import (
    CustomerDataProvider,
    ToolsLambdaProvider,
    InMemoryProvider,
    SalesforceCustomerDataProvider,
)
```

#### Protocol isinstance() tests (D-12 category 1)

```python
def test_tools_lambda_provider_satisfies_protocol():
    client = MagicMock()
    assert isinstance(ToolsLambdaProvider(client, "arn:aws:lambda:..."), CustomerDataProvider)


def test_inmemory_provider_satisfies_protocol():
    assert isinstance(InMemoryProvider(), CustomerDataProvider)


def test_salesforce_provider_satisfies_protocol():
    assert isinstance(SalesforceCustomerDataProvider(), CustomerDataProvider)
```

#### Byte-exact savings parametrize (D-12 category 2)

**Copy parametrize pattern from** `tests/test_agent_tools.py:80-97` (existing per-persona fixture consumption). For six personas, use `@pytest.mark.parametrize` across the `mock_*_response` fixtures:

```python
@pytest.mark.parametrize("customer_id,fixture_name", [
    ("CUST-001", "mock_savings_response"),
    ("CUST-002", "mock_marcus_response"),
    ("CUST-003", "mock_elena_response"),
    ("CUST-004", "mock_cust004_response"),
    ("CUST-005", "mock_cust005_response"),
    ("CUST-006", "mock_cust006_response"),
])
def test_inmemory_provider_byte_exact_savings(customer_id, fixture_name, request):
    expected = request.getfixturevalue(fixture_name)
    provider = InMemoryProvider()
    result = provider.simulate_savings(customer_id)
    for track in ("green", "cheapest"):
        for field in ("plan_id", "plan_name", "saving_monthly", "saving_annual"):
            assert result[track][field] == expected[track][field], \
                f"{customer_id} {track}.{field}: {result[track][field]} != {expected[track][field]}"
```

This threads the existing fixture family (`mock_savings_response` at `tests/conftest.py:65-80`, `mock_marcus_response` at `:83-99`, etc.) into a single parametrized body. D-08 numeric-only comparison rule applies — narrative fields absent from these fixtures by design.

#### Salesforce NotImplementedError asserts (D-12 category 3)

**Copy shape from** `tests/test_get_hardship_flag_pure.py:35-41`:

```python
def test_malformed_customer_id_rejected():
    """V5 input validation — _validate_customer_id guards entry."""
    client = MagicMock()
    with pytest.raises(ValueError):
        get_hardship_flag_pure("not-a-customer-id", client)
    # Ensure DynamoDB was NEVER called — V5 gate fired first
    client.get_item.assert_not_called()
```

Adapted for Salesforce stub:

```python
def test_salesforce_get_customer_raises_not_implemented():
    provider = SalesforceCustomerDataProvider()
    with pytest.raises(NotImplementedError, match="DOC-03"):
        provider.get_customer("CUST-001")


def test_salesforce_get_billing_history_raises_not_implemented():
    provider = SalesforceCustomerDataProvider()
    with pytest.raises(NotImplementedError, match="DOC-03"):
        provider.get_billing_history("CUST-001")


def test_salesforce_get_hardship_flag_raises_not_implemented():
    provider = SalesforceCustomerDataProvider()
    with pytest.raises(NotImplementedError, match="DOC-03"):
        provider.get_hardship_flag("CUST-001")
```

The `match="DOC-03"` hook verifies the breadcrumb survives (D-13/D-15).

---

### `tests/conftest.py` (modify — add `_provider_swap` autouse + `inmemory_provider` fixture)

**Analog:** existing fixture structure at `tests/conftest.py:1-58` (`tariff_plans`, `sarah_billing`, etc.). No autouse fixtures exist in the current conftest — this is the first. The `monkeypatch`-style teardown pattern can be referenced at `tests/test_get_billing_history.py:8-16` (the `handler_module` fixture uses `monkeypatch.setenv` + module reload).

**New pattern to introduce** (D-11):

```python
# ADD to tests/conftest.py (after existing fixtures)


@pytest.fixture
def inmemory_provider():
    """An InMemoryProvider seeded with Phase 11 records — for explicit-dependency tests."""
    from agent.providers import InMemoryProvider
    return InMemoryProvider()


@pytest.fixture(autouse=True)
def _provider_swap():
    """D-11: every test runs with an InMemoryProvider installed.

    Save the module-level singleton, swap in an InMemory one, restore on teardown.
    Greppable via `git grep _provider_swap`.
    """
    from agent.providers import get_provider, set_provider, InMemoryProvider
    try:
        original = get_provider()
    except RuntimeError:
        original = None
    set_provider(InMemoryProvider())
    yield
    if original is not None:
        set_provider(original)
```

Fixture ordering: insert after the `all_billing` fixture at `tests/conftest.py:55-58` but before the `# --- Phase 2 agent fixtures ---` section header at `:61`. Keeps the fixture list chronologically coherent (Phase 11 data → Phase 12 swap → Phase 2+ legacy).

Autouse blast-radius check: `_provider_swap` runs for every test, including `test_agent_tools.py` and `test_simulate_savings.py`. Those tests already mock `_lambda_client.invoke` directly (e.g. `tests/test_agent_tools.py:101-118`) and do NOT go through the provider; the autouse fixture is harmless because those tests bypass `get_provider()`. But if planning introduces a test that routes through the @tool body + provider singleton, the autouse swap ensures it gets InMemory not a live boto3 client.

---

### `scripts/capture_live_recommendations.py` (new script — pre/post live-diff harness)

**Primary analog:** `scripts/prewarm.py` (stdlib-only, 0/1/2 exit taxonomy, BACKEND_API_URL env var). **Secondary analog:** `scripts/capture_samples.py` (JSON-writing to phase artefact directory, but uses boto3 — NOT stdlib).

Per CONTEXT.md §"Decisions" D-06: stdlib-only, hits `/recommendations/{id}` via HTTP (not `invoke_agent_runtime` via boto3). Matches `prewarm.py` not `capture_samples.py`.

#### Module docstring + exit taxonomy

**Copy from** `scripts/prewarm.py:1-36`:

```python
#!/usr/bin/env python3
"""Phase 9 pre-warm CLI — two-pass warm + measurement against the live API.

Warms all three demo personas via the Phase 7 pre-warm query branch, settles
for 30s, then fires 3 timed `GET /recommendations/{customer_id}` calls per
persona and asserts warm median < 3000ms per persona. Runs pre-demo to
eliminate AgentCore / Lambda cold-start latency before the presenter walks
on stage.

Usage:
    BACKEND_API_URL=https://... \\
    python3 scripts/prewarm.py

Exit taxonomy (D-06):
    0 — all three personas under gate
    1 — gate-fail OR non-204 on warm pass OR non-200 on measurement GET
    2 — setup error (missing BACKEND_API_URL, unreachable endpoint on first call)
"""
import os
import socket
import statistics
import sys
import time
import urllib.error
import urllib.request

PERSONAS = ["CUST-001", "CUST-002", "CUST-003"]
MEDIAN_GATE_MS = 3000          # D-03 — matches ROADMAP SC-2 verbatim; do NOT tighten to 2500
PREWARM_SPACING_S = 2          # D-02 step 1
SETTLE_WAIT_S = 30             # D-02 step 2 — load-bearing for microVM pool settling
MEASUREMENT_SAMPLES = 3        # D-02 step 3
HTTP_TIMEOUT_S = 30            # D-08
```

Adapt for capture script:

```python
#!/usr/bin/env python3
"""Phase 12 pre/post live-diff capture — SAV-03 byte-exact proof.

Hits /recommendations/{customer_id} for CUST-001..005 and stores JSON bodies
under .planning/phases/12-customerdataprovider-abstraction/baseline/{pre|post}/.
In --compare mode, diffs pre/ vs post/ on numeric fields only (D-08) and exits
non-zero on any drift — phase-close deploy gate (D-06).

Usage:
    BACKEND_API_URL=https://... \\
    python3 scripts/capture_live_recommendations.py --mode pre
    # refactor + redeploy
    BACKEND_API_URL=https://... \\
    python3 scripts/capture_live_recommendations.py --mode post
    python3 scripts/capture_live_recommendations.py --mode compare

Exit taxonomy (D-06, matches prewarm.py):
    0 — diff clean (or capture succeeded)
    1 — diff drift / HTTP non-200 / gate fail
    2 — setup error (missing BACKEND_API_URL, unreachable endpoint first call)
"""
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

PERSONAS = ["CUST-001", "CUST-002", "CUST-003", "CUST-004", "CUST-005"]
NUMERIC_FIELDS = ("plan_id", "plan_name", "saving_monthly", "saving_annual")  # D-08
HTTP_TIMEOUT_S = 30
```

Note `CUST-006` exclusion: CONTEXT.md D-06 explicitly says "CUST-001..005". CUST-006 is the hardship persona — Phase 14 short-circuits it pre-LLM, so pre/post diff would compare a valid recommendation against a hardship hand-off and fail spuriously. Stop at 005.

#### HTTP GET + JSON write pattern

**Copy from** `scripts/prewarm.py:46-71`:

```python
# scripts/prewarm.py:46-71
for idx, persona in enumerate(PERSONAS):
    warm_url = f"{api_url}/recommendations/{persona}?prewarm=1"
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(warm_url, timeout=HTTP_TIMEOUT_S) as resp:
            status = resp.status
            resp.read()
    except urllib.error.HTTPError as exc:
        # HTTPError carries a status code — runtime failure, not setup error.
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        print(f"prewarm {persona}: {exc.code} {elapsed_ms}ms FAIL (expected 204)")
        return 1
    except (urllib.error.URLError, ConnectionRefusedError, socket.gaierror, socket.timeout) as exc:
        # Connectivity failure on the FIRST persona is a setup error → exit 2.
        # Any later persona treats it as runtime failure → exit 1.
        if persona == PERSONAS[0]:
            print(f"cannot reach {api_url}: {exc}", file=sys.stderr)
            return 2
        print(f"prewarm {persona}: ERROR {exc}")
        return 1
```

Adapt: capture mode reads the full response body, writes to `baseline/<mode>/<customer_id>.json`:

```python
url = f"{api_url}/recommendations/{persona}"
try:
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as resp:
        if resp.status != 200:
            print(f"{persona}: HTTP {resp.status} FAIL")
            return 1
        body = json.loads(resp.read())
except urllib.error.HTTPError as exc:
    print(f"{persona}: HTTP {exc.code} FAIL")
    return 1
except (urllib.error.URLError, ConnectionRefusedError, socket.gaierror, socket.timeout) as exc:
    if persona == PERSONAS[0]:
        print(f"cannot reach {api_url}: {exc}", file=sys.stderr)
        return 2
    print(f"{persona}: ERROR {exc}")
    return 1

target = phase_dir / "baseline" / mode / f"{persona}.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(body, indent=2))
print(f"{persona}: captured to {target}")
```

#### Pathlib pattern for phase_dir discovery

**Copy from** `scripts/capture_samples.py:30-32`:

```python
# scripts/capture_samples.py:30-32
repo_root = Path(__file__).resolve().parent.parent
out = repo_root / ".planning" / "phases" / "06-agent-narrative-guardrail" / "06-SAMPLES.md"
out.parent.mkdir(parents=True, exist_ok=True)
```

Adapted:

```python
repo_root = Path(__file__).resolve().parent.parent
phase_dir = repo_root / ".planning" / "phases" / "12-customerdataprovider-abstraction"
```

#### Diff mode (numeric-only per D-08)

Net-new logic — no direct analog. Shape:

```python
def _compare(pre: dict, post: dict, customer_id: str) -> list[str]:
    drifts = []
    for track in ("green", "cheapest"):
        for field in NUMERIC_FIELDS:
            pre_val = pre.get(track, {}).get(field)
            post_val = post.get(track, {}).get(field)
            if pre_val != post_val:
                drifts.append(f"{customer_id}.{track}.{field}: {pre_val!r} → {post_val!r}")
    return drifts
```

Narrative fields (`usage_narrative`, `call_script`) and `_narrative_source` are explicitly excluded per D-08.

#### Script location

Planner choice per CONTEXT.md §"Claude's Discretion": `scripts/capture_live_recommendations.py` (permanent, demo-friendly, git-tracked with the other demo tooling) vs `.planning/phases/12-.../capture_live_recommendations.py` (one-shot). The existing `scripts/capture_samples.py` precedent for a committed capture tool favours `scripts/`.

---

## Shared Patterns

### Bi-mode import (container vs repo layout) — D-16

**Source:** `agent/agent.py:26-51`, replicated in `agent/narrative/validators.py:14-18`.
**Apply to:** any `agent/*.py` import of a sibling `agent/*.py` module. In Phase 12 this is exclusively the `agent/agent.py` → `agent/providers.py` edge.

```python
# agent/agent.py:26-51 — canonical template
try:
    from narrative.fallbacks import FALLBACKS
    # ... more container-path imports
except ImportError:  # pragma: no cover - hit only in offline test repo layout
    from agent.narrative.fallbacks import FALLBACKS
    # ... mirror repo-path imports
```

D-17 container-side verification: `docker run --entrypoint python tariff_agent:latest -c "from providers import CustomerDataProvider"` must succeed (may fold into smoke tier or new `pytest -m bimode` marker — planner choice).

### Module-level singleton with lazy init — D-03

**Source:** `agent/agent.py:60`, `lambda/handler.py:30-34`.
**Apply to:** `_lambda_client` (reused, never re-instantiated) + new `_provider` in `agent/agent.py`; `_PROVIDER` module-level in `agent/providers.py`.

```python
# agent/agent.py:60
_lambda_client = boto3.client("lambda", region_name=_REGION)

# lambda/handler.py:30-34 — lazy boto3 init for offline testability
table = None
if os.environ.get("TABLE_NAME"):
    import boto3  # imported lazily so pure-function tests do not require boto3
    _dynamodb = boto3.resource("dynamodb")
    table = _dynamodb.Table(os.environ["TABLE_NAME"])
```

### V5 input validation (validate before side-effects) — `_validate_customer_id`

**Source:** `lambda/handler.py:39-52`.
**Apply to:** Lambda action dispatcher (before routing); also `get_hardship_flag_pure` and `get_billing_history` already call it.

```python
# lambda/handler.py:39-52
_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")


def _validate_customer_id(customer_id: Any) -> str:
    """Raise ValueError on invalid customer_id; returns normalised string.

    STRIDE: V5 Input Validation — rejects injection attempts, empty strings,
    and non-string types before any DynamoDB query is issued.
    """
    if not isinstance(customer_id, str):
        raise ValueError(f"customer_id must be a string, got {type(customer_id).__name__}")
    if not _CUSTOMER_ID_PATTERN.match(customer_id):
        raise ValueError(f"customer_id must match CUST-<digits>; got {customer_id!r}")
    return customer_id
```

The new `handler(event, context)` dispatcher calls `_validate_customer_id(event.get("customer_id"))` inside the `get_hardship_flag` and `get_customer` branches. The `simulate_savings` and `get_billing_history` branches already delegate to handlers that call it internally.

### Importlib module loading in tests (lambda.handler pattern)

**Source:** `tests/test_get_hardship_flag_pure.py:1-8`, `tests/test_get_billing_history.py:8-16`.
**Apply to:** any test importing `lambda.handler` — Python reserves `lambda` so `from lambda.handler import …` is a SyntaxError.

```python
# tests/test_get_hardship_flag_pure.py:1-8
import importlib
handler = importlib.import_module("lambda.handler")
get_hardship_flag_pure = handler.get_hardship_flag_pure
```

If `tests/test_providers.py` never directly imports from `lambda.handler` (InMemoryProvider handles the indirection), this pattern is not needed. If it does (e.g. to verify dispatcher behaviour from the provider side), copy the `importlib.import_module("lambda.handler")` incantation verbatim.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| *(none)* | — | — | Every Phase 12 file has a concrete codebase analog. The Protocol class itself is novel to the codebase (no existing `typing.Protocol` users), but the module-shape + bi-mode + singleton patterns fully cover the structural concerns. |

The `typing.Protocol` + `@runtime_checkable` construct is introduced by this phase — not previously used in the codebase. Planner should treat the Protocol skeleton in CONTEXT.md D-12 + ARCHITECTURE.md lines 406-436 (research doc) as the source, not any existing file.

## Metadata

**Analog search scope:** `agent/`, `lambda/`, `tests/`, `scripts/`, `infrastructure/seed_data/`
**Files scanned (Read calls):** 9 — `agent/agent.py`, `lambda/handler.py`, `tests/conftest.py`, `scripts/prewarm.py`, `scripts/capture_samples.py`, `agent/narrative/validators.py`, `agent/narrative/banned_terms.py` (partial), `tests/test_get_billing_history.py`, `tests/test_get_hardship_flag_pure.py`, `tests/test_agent_tools.py`, `infrastructure/seed_data/billing_records.py` (partial)
**Pattern extraction date:** 2026-04-28
