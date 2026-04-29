---
phase: 12-customerdataprovider-abstraction
reviewed: 2026-04-29T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - agent/agent.py
  - agent/Dockerfile
  - agent/providers.py
  - infrastructure/constructs/tools_lambda.py
  - lambda/handler.py
  - scripts/capture_live_recommendations.py
  - tests/conftest.py
  - tests/test_cdk_synth.py
  - tests/test_providers.py
findings:
  critical: 0
  warning: 5
  info: 7
  total: 12
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-04-29
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 12 introduces a `CustomerDataProvider` Protocol seam with three implementations (ToolsLambdaProvider, InMemoryProvider, SalesforceCustomerDataProvider) plus an action dispatcher on `lambda/handler.py`. The SAV-03 byte-exact invariant is preserved on both the production path (unchanged `simulate_savings_pure` arithmetic in the Tools Lambda) and the offline path (InMemoryProvider delegates to `simulate_savings_pure`). D-04 never-500 (`except Exception` at `agent/agent.py:396`), D-15 dual-gate, D-16 bi-mode imports, `runtimeSessionId` scope, `?prewarm=1`, and `?narrative=off` are all untouched. No critical defects.

However, five warnings are worth addressing before shipping downstream changes on this seam:

- The D-04 fallback path in `agent/agent.py` now depends on an implicit route (`handler()` fallthrough when `action` is missing) — documented but fragile.
- `handler.handler` silently falls through to `simulate_savings` for **unknown** action values, masking caller bugs (e.g. typos or malicious action strings).
- `InMemoryProvider.__init__` has two lazy failure modes (tariff-plans path + seed-data import) that only surface at first-call in the container if the class is ever instantiated there — Phase 13+ should harden before anyone wires InMemoryProvider into a live path.
- `ToolsLambdaProvider._invoke` leaks the full Lambda error body (including stack trace) into the `RuntimeError` message it raises.
- Unknown `customer_id` in the tool-failure fallback still returns a `green`/`cheapest`-less body, which the API Lambda misreads as 404 (pre-existing, but widened by the new action dispatcher).

The test suite additions (`tests/test_providers.py`, conftest `_provider_swap` autouse) are clean: Protocol isinstance, 6-persona byte-exact replay, and DOC-03 stub breadcrumbs are all directly asserted. Info findings below are mostly about fragility and documentation clarity, not correctness.

## Warnings

### WR-01: handler.handler silently falls through to simulate_savings on unknown action

**File:** `lambda/handler.py:210-230`
**Issue:** The dispatcher matches four known actions with `if`/`if`/`if`/`if` (not `elif`), then unconditionally falls through to `simulate_savings(event, context)` at line 230. An event with `{"action": "get_customre", "customer_id": "CUST-001"}` (typo) or `{"action": "delete_all_data", "customer_id": "CUST-001"}` (hostile) silently runs `simulate_savings` instead of rejecting. The D-05 back-compat contract is "missing action ⇒ simulate_savings", but the code also covers "unknown action ⇒ simulate_savings", which is broader than documented and masks client bugs.
**Fix:** Distinguish "no action key" from "unknown action value" — reject the latter:
```python
action = event.get("action")
if action is None:
    return simulate_savings(event, context)  # D-05 back-compat only
if action == "get_billing_history":
    return get_billing_history(event, context)
if action == "get_hardship_flag":
    customer_id = _validate_customer_id(event.get("customer_id"))
    if table is None:
        raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")
    return get_hardship_flag_pure(customer_id, table)
if action == "get_customer":
    customer_id = _validate_customer_id(event.get("customer_id"))
    return {"customer_id": customer_id}
if action == "simulate_savings":
    return simulate_savings(event, context)
raise ValueError(f"Unknown action: {action!r}")
```

### WR-02: agent.py D-04 fallback path relies on D-05 implicit-route behaviour

**File:** `agent/agent.py:404-407`
**Issue:** The tool-failure fallback still calls `_lambda_client.invoke(...Payload=json.dumps({"customer_id": customer_id}).encode())` — with no `action` key. Under Phase 12's new dispatcher, this hits the "no action ⇒ simulate_savings" fallthrough at `lambda/handler.py:230`. That works today (D-05), but the coupling is not expressed in code: a future refactor that tightens the dispatcher (e.g. WR-01 style explicit-reject for unknown payloads, or dropping D-05 entirely) would silently break the D-04 never-500 fallback.
**Fix:** Make the dependency explicit at the call site:
```python
resp = _lambda_client.invoke(
    FunctionName=_TOOLS_LAMBDA_ARN,
    InvocationType="RequestResponse",
    Payload=json.dumps(
        {"action": "simulate_savings", "customer_id": customer_id}
    ).encode(),
)
```
This also makes the fallback shape parallel to `ToolsLambdaProvider.simulate_savings` (`providers.py:84-86`), which is easier to reason about in grep.

### WR-03: InMemoryProvider tariff_plans path fails if module not located under agent/

**File:** `agent/providers.py:115-119`
**Issue:** `_plans_path = os.path.join(_here, "..", "lambda", "tariff_plans.json")` assumes `agent/providers.py` is always at `<repo>/agent/providers.py`. In the AgentCore container, `providers.py` is at `/app/providers.py` (Dockerfile line 9) — not under any `agent/` directory — so `os.path.join("/app", "..", "lambda", "tariff_plans.json")` resolves to `/lambda/tariff_plans.json`, which does not exist. `lambda/` is also not copied into the container. This only manifests if `InMemoryProvider()` is ever instantiated inside the container (not today, but the class is imported unconditionally at `agent.py:55-71`). Any future "swap in InMemoryProvider for canary" path silently breaks.
**Fix:** Fail loudly on first-touch and document the constraint, or pass tariff_plans via constructor in every container-facing path:
```python
if tariff_plans is None:
    _here = os.path.dirname(os.path.abspath(__file__))
    _plans_path = os.path.join(_here, "..", "lambda", "tariff_plans.json")
    if not os.path.exists(_plans_path):
        raise RuntimeError(
            f"InMemoryProvider tariff_plans lookup failed ({_plans_path}) — "
            "pass tariff_plans=... explicitly when running outside the repo layout"
        )
    with open(_plans_path) as f:
        tariff_plans = json.load(f)
```
Same applies to `from infrastructure.seed_data.billing_records import ...` at `providers.py:110-114` — the `infrastructure/` directory is not inside the container image.

### WR-04: ToolsLambdaProvider._invoke leaks Lambda stack trace into RuntimeError message

**File:** `agent/providers.py:65-73`
**Issue:** When Lambda returns `FunctionError`, the payload body typically includes `errorMessage`, `errorType`, **and** `stackTrace` (a list of stack frames). `raise RuntimeError(f"ToolsLambda error: {body}")` embeds the full dict — including the stack trace — into the exception string. That exception string propagates up through the agent's `except Exception` at `agent.py:396` into CloudWatch logs (via `exc_info=True` at `agent.py:403`), and into the fallback code path. This is CloudWatch-visible (acceptable) but also becomes part of any error response the agent might return in future branches. STRIDE V3 (Information Disclosure) applies: internal module paths in stack frames expose Lambda internals. Also, `body` may not always be a dict (e.g. `"Internal Server Error"` string on some 5xx paths) — `f"{body}"` silently swallows the distinction.
**Fix:** Extract only the error-shape fields you care about:
```python
if "FunctionError" in resp:
    err_type = body.get("errorType", "Unknown") if isinstance(body, dict) else "Unknown"
    err_msg = body.get("errorMessage", str(body)) if isinstance(body, dict) else str(body)
    raise RuntimeError(f"ToolsLambda {err_type}: {err_msg}")
```

### WR-05: InMemoryProvider.simulate_savings fails opaquely when lambda/ not on sys.path

**File:** `agent/providers.py:156-162`
**Issue:** `importlib.import_module("lambda.handler")` succeeds only when:
(a) `lambda/__init__.py` exists (it does — confirmed at `lambda/__init__.py`), AND
(b) the repo root is on `sys.path`.
Under pytest this holds because pytest's rootdir discovery adds the repo root. Under ad-hoc usage (`python3 -c "from agent.providers import InMemoryProvider; p = InMemoryProvider(); p.simulate_savings('CUST-001')"` from any other cwd), or inside the container (lambda/ not copied), `import_module` raises `ModuleNotFoundError: No module named 'lambda'`. The error message does not point the user at the root cause (cwd / sys.path / missing `__init__.py`). This is the reserved-word `lambda` import dance — it's inherently fragile and should announce itself.
**Fix:** Wrap with a diagnostic:
```python
import importlib
try:
    _handler = importlib.import_module("lambda.handler")
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "InMemoryProvider.simulate_savings: could not import lambda.handler — "
        "ensure repo root is on sys.path and lambda/__init__.py exists "
        "(this path is offline-only; production uses ToolsLambdaProvider)"
    ) from exc
```

## Info

### IN-01: conftest._provider_swap leaks InMemoryProvider globally when original is None

**File:** `tests/conftest.py:78-98`
**Issue:** On teardown, `if original is not None: set_provider(original)` — if the very first test runs before any `agent.agent` import (so `get_provider()` raised at setup), the autouse fixture installs InMemoryProvider and never clears it. Subsequent non-test process state (e.g. if pytest is embedded) sees a stale InMemoryProvider. Low impact because every test re-runs `_provider_swap` and reinstalls a fresh InMemoryProvider.
**Fix:** On teardown when `original` is None, explicitly unset:
```python
if original is not None:
    set_provider(original)
else:
    # Restore pre-test global state so tests don't leak a stale singleton
    import agent.providers as _pm
    _pm._PROVIDER = None
```

### IN-02: Tool-failure fallback body lacks green/cheapest on customer-not-found

**File:** `agent/agent.py:404-428`
**Issue:** If Lambda fails entirely (ClientError, timeout) OR returns an errorMessage for an unknown customer_id, the raw payload at line 409 is `{"errorMessage": "No billing history for 'CUST-999'"}` (no `green`/`cheapest` keys). The subsequent `for track in ("green", "cheapest"): ... raw[track] = raw_track` block only adds `usage_narrative`/`call_script` fields to an empty dict — it does NOT backfill `plan_id`/`plan_name`/`saving_monthly`/`saving_annual`. The returned body has `{"errorMessage": ..., "green": {"usage_narrative": ..., "call_script": ...}, "cheapest": {...}, "_narrative_source": ...}` — malformed against `RecommendationResponse` but shipped as-is. The api_lambda's "no `green` or `cheapest` keys in body" customer-not-found check then misses this shape because `green` IS present (just incomplete) — so what should be 404 is returned as 200. Pre-existing behaviour (not introduced by Phase 12) but the action-dispatcher change makes it easier to reproduce.
**Fix:** Either short-circuit on error bodies before attaching fallback narratives, or populate a minimum-viable numeric shape:
```python
if "errorMessage" in raw and "green" not in raw and "cheapest" not in raw:
    return raw  # surface to api_lambda's not-found branch
```

### IN-03: ToolsLambdaProvider._invoke missing ARN check is a RuntimeError, not a constructor-time guard

**File:** `agent/providers.py:61-64`
**Issue:** The empty-ARN guard is inside `_invoke`, so construction is permissive — `ToolsLambdaProvider(client, "")` succeeds silently and only errors on first method call. During offline test import `agent/agent.py:83` instantiates `ToolsLambdaProvider(_lambda_client, "")` (since `TOOLS_LAMBDA_ARN` is unset in pytest). The swap-in of InMemoryProvider (via `_provider_swap`) hides this immediately, but a future test that forgets the fixture would see a cryptic `RuntimeError("TOOLS_LAMBDA_ARN not set — provider misconfigured")` far from the actual misconfiguration.
**Fix:** Keep the runtime check (defence-in-depth) but also log a warning at construction when ARN is empty.

### IN-04: capture_live_recommendations.py persona list hardcoded, diverges from PHASE-11 seed data

**File:** `scripts/capture_live_recommendations.py:40`
**Issue:** `PERSONAS = ("CUST-001", "CUST-002", "CUST-003", "CUST-004", "CUST-005")` excludes CUST-006 (the Phase 11 hardship persona). If Phase 14 hardship short-circuiting ships, the pre/post drift capture misses it entirely. The script is the official D-06 deploy gate — if the byte-exact guarantee is supposed to apply to all personas in `ALL_RECORDS`, this is an incomplete gate.
**Fix:** Import the canonical persona list:
```python
from infrastructure.seed_data.billing_records import ALL_RECORDS
PERSONAS = tuple(sorted({r["customer_id"] for r in ALL_RECORDS}))
```
Or at minimum add CUST-006 explicitly and document the decision in the script header.

### IN-05: NUMERIC_FIELDS includes plan_id and plan_name — misnamed tuple

**File:** `scripts/capture_live_recommendations.py:41`
**Issue:** `NUMERIC_FIELDS = ("plan_id", "plan_name", "saving_monthly", "saving_annual")` — but `plan_id` and `plan_name` are strings, not numerics. The diff works correctly (`!=` is polymorphic), but the constant name misleads anyone reading the script as auditor. Rename to `LOCKED_FIELDS` or `IDENTITY_FIELDS` to match D-08 intent (identity + math both locked).
**Fix:** `LOCKED_FIELDS = ("plan_id", "plan_name", "saving_monthly", "saving_annual")` and update call sites.

### IN-06: Script AWS_PROFILE in docstring is misleading — script doesn't use boto3

**File:** `scripts/capture_live_recommendations.py:13,18`
**Issue:** The usage block shows `AWS_PROFILE=cevo-dev25` but the script uses `urllib.request.urlopen` against the public API Gateway URL, which is unauthenticated. Setting `AWS_PROFILE` has no effect. Presenters may waste time debugging "wrong profile" errors that don't exist here.
**Fix:** Remove `AWS_PROFILE=cevo-dev25 \` from the usage block, or document that only `BACKEND_API_URL` matters for this script.

### IN-07: InMemoryProvider groups by customer_id but never validates customer_id format

**File:** `agent/providers.py:122-132`
**Issue:** Unlike the production path (`lambda/handler.py:42-52` `_validate_customer_id` CUST-NNN regex), the InMemory path accepts any string for `customer_id` on `get_customer`, `get_billing_history`, `get_hardship_flag`. STRIDE V5 parity with production is lost — tests that rely on the provider interface won't catch malformed-ID regressions. Also `get_billing_history` returns `[]` for an unknown ID (silent), vs the Lambda which returns `[]` for a valid-format-but-unknown ID (also silent but at least validated). Not a bug today but a divergence.
**Fix:** Add `_validate_customer_id` calls at each method entry in `InMemoryProvider`, importing `_validate_customer_id` lazily at method call to avoid the reserved-word `lambda` import pain at module scope:
```python
def get_billing_history(self, customer_id: str) -> list[dict[str, Any]]:
    import importlib
    importlib.import_module("lambda.handler")._validate_customer_id(customer_id)
    rows = self._records_by_customer.get(customer_id, [])
    return sorted(rows, key=lambda r: r["month"])
```
Or factor `_validate_customer_id` into a shared `agent/validators.py` that both Lambda and providers can import.

---

_Reviewed: 2026-04-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
