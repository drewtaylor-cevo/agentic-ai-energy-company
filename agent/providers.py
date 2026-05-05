"""CustomerDataProvider abstraction — PROD-01 strangler-fig seam.

Three concrete implementations satisfy the runtime-checkable Protocol:
  - ToolsLambdaProvider: production path; each method issues a boto3
    lambda.invoke with a {action, customer_id} payload to the Tools Lambda.
  - InMemoryProvider: offline test double; seeds from the same
    infrastructure/seed_data/billing_records.py that feeds the live seeder.
  - SalesforceCustomerDataProvider: presenter stub for DOC-03; every
    method raises NotImplementedError with a breadcrumb to
    .planning/docs/presenter/DEFERRED-ROADMAP.md.

SAV-03 invariant: simulate_savings arithmetic stays in Tools Lambda
(D-04). This module wraps the invoke; it does not re-implement the math
path for the production provider.

Bi-mode import (D-16): agent/agent.py imports this module via both
`from providers import ...` (container /app layout) and `from agent.providers
import ...` (repo layout) — see agent/agent.py bi-mode import block.
"""
from __future__ import annotations

import json
import os
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CustomerDataProvider(Protocol):
    """Minimum viable shape for customer-data access (LD-5: 3 methods only).

    Deliberately excludes simulate_savings — arithmetic lives in Tools Lambda
    by design (D-04, SAV-03). Excludes get_tariff_catalog — Tools Lambda owns
    TARIFF_PLANS. Excludes consent/audit/circuit-breaker — deferred to v3.1+
    (PROD-03/04/05).
    """

    def get_customer(self, customer_id: str) -> dict[str, Any]: ...

    def get_billing_history(self, customer_id: str) -> list[dict[str, Any]]: ...

    def get_hardship_flag(self, customer_id: str) -> dict[str, Any]: ...


class ToolsLambdaProvider:
    """Production provider — each method issues a boto3 lambda.invoke.

    Re-uses the caller-supplied lambda_client (agent/agent.py _lambda_client).
    Never instantiates boto3 directly — D-03 singleton discipline.
    """

    def __init__(self, lambda_client: Any, tools_lambda_arn: str) -> None:
        self._lambda_client = lambda_client
        self._tools_lambda_arn = tools_lambda_arn

    def _invoke(self, payload: dict) -> Any:
        """Consolidated invoke + json + FunctionError handling.

        Mirrors agent/agent.py:255-270 verbatim (SAV-03: no new math path,
        identical invoke shape).
        """
        if not self._tools_lambda_arn:
            raise RuntimeError(
                "TOOLS_LAMBDA_ARN not set — provider misconfigured"
            )
        resp = self._lambda_client.invoke(
            FunctionName=self._tools_lambda_arn,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode(),
        )
        body = json.loads(resp["Payload"].read())
        if "FunctionError" in resp:
            raise RuntimeError(f"ToolsLambda error: {body}")
        return body

    def get_customer(self, customer_id: str) -> dict[str, Any]:
        return self._invoke({"action": "get_customer", "customer_id": customer_id})

    def get_billing_history(self, customer_id: str) -> list[dict[str, Any]]:
        return self._invoke({"action": "get_billing_history", "customer_id": customer_id})

    def get_hardship_flag(self, customer_id: str) -> dict[str, Any]:
        return self._invoke({"action": "get_hardship_flag", "customer_id": customer_id})

    def simulate_savings(self, customer_id: str) -> dict[str, Any]:
        """D-04 concrete method — NOT on the Protocol. Math stays in Lambda."""
        return self._invoke({"action": "simulate_savings", "customer_id": customer_id})


class InMemoryProvider:
    """Offline test double — sources data from Phase 11 seed artefacts.

    Constructor defaults to the same records the live DynamoDB seeder writes,
    so byte-exact savings are preserved without AWS. Used by
    tests/test_providers.py and the autouse _provider_swap fixture in
    tests/conftest.py.

    NOTE: simulate_savings() on this class imports simulate_savings_pure
    directly from lambda.handler. This is the OFFLINE test double only —
    production runs via ToolsLambdaProvider.simulate_savings which invokes
    the Tools Lambda. D-04 arithmetic-stays-in-Lambda invariant held.
    """

    def __init__(
        self,
        billing_records: list[dict] | None = None,
        profile_items: list[dict] | None = None,
        tariff_plans: list[dict] | None = None,
    ) -> None:
        if billing_records is None:
            from infrastructure.seed_data.billing_records import ALL_RECORDS
            billing_records = ALL_RECORDS
        if profile_items is None:
            from infrastructure.seed_data.billing_records import PROFILE_ITEMS
            profile_items = PROFILE_ITEMS
        if tariff_plans is None:
            _here = os.path.dirname(os.path.abspath(__file__))
            _plans_path = os.path.join(_here, "..", "lambda", "tariff_plans.json")
            with open(_plans_path) as f:
                tariff_plans = json.load(f)
        # Group records by customer_id (EXCLUDES PROFILE rows because
        # PROFILE rows already have month="PROFILE" — filtered below).
        self._records_by_customer: dict[str, list[dict]] = {}
        for rec in billing_records:
            if rec.get("month") == "PROFILE":
                continue
            self._records_by_customer.setdefault(rec["customer_id"], []).append(rec)
        # Index profile rows by customer_id for get_hardship_flag lookups.
        self._profile_by_customer: dict[str, dict] = {
            p["customer_id"]: p for p in profile_items
        }
        self._tariff_plans = tariff_plans

    def get_customer(self, customer_id: str) -> dict[str, Any]:
        return {"customer_id": customer_id}

    def get_billing_history(self, customer_id: str) -> list[dict[str, Any]]:
        """Return month-sorted rows, PROFILE filter already applied in __init__."""
        rows = self._records_by_customer.get(customer_id, [])
        return sorted(rows, key=lambda r: r["month"])

    def get_hardship_flag(self, customer_id: str) -> dict[str, Any]:
        """Match lambda/handler.py:143-161 get_hardship_flag_pure contract."""
        profile = self._profile_by_customer.get(customer_id)
        if profile is None:
            return {"hardship": False, "hardship_category": None, "customer_id": customer_id}
        return {
            "hardship": bool(profile.get("hardship_flag", False)),
            "hardship_category": profile.get("hardship_category"),  # None if absent
            "customer_id": customer_id,
        }

    def simulate_savings(self, customer_id: str) -> dict[str, Any]:
        """D-04 OFFLINE test-double path: reuse simulate_savings_pure directly.

        NOT a Protocol method — concrete only, parallels
        ToolsLambdaProvider.simulate_savings.
        """
        import importlib
        _handler = importlib.import_module("lambda.handler")
        billing = self.get_billing_history(customer_id)
        if not billing:
            raise ValueError(f"No billing history for {customer_id!r}")
        return _handler.simulate_savings_pure(billing, self._tariff_plans)


class SalesforceCustomerDataProvider:
    """Salesforce Energy & Utilities Cloud adapter — presenter stub (DOC-03).

    Real SObject mapping (Phase 16 / DOC-03):
        Account → ServicePoint → BillingAccount → Usage

    No simple_salesforce import — frozen lockfile contract (Phase 15 owns
    the only permitted dep bump). All methods raise NotImplementedError
    with a breadcrumb to DOC-03.
    """

    _NOT_IMPLEMENTED_MESSAGE = (
        "Salesforce adapter not implemented — see DOC-03 at "
        ".planning/docs/presenter/DEFERRED-ROADMAP.md (Phase 16)"
    )

    def get_customer(self, customer_id: str) -> dict[str, Any]:
        """Salesforce `Account` SObject, matched by `External_Customer_Id__c`."""
        raise NotImplementedError(self._NOT_IMPLEMENTED_MESSAGE)

    def get_billing_history(self, customer_id: str) -> list[dict[str, Any]]:
        """Salesforce `ServicePoint` + `BillingAccount` + `Usage` SObjects,
        joined by ServicePoint.BillingAccountId."""
        raise NotImplementedError(self._NOT_IMPLEMENTED_MESSAGE)

    def get_hardship_flag(self, customer_id: str) -> dict[str, Any]:
        """Salesforce `Account.Hardship_Flag__c` custom boolean field."""
        raise NotImplementedError(self._NOT_IMPLEMENTED_MESSAGE)


# --- Module-level singleton (D-11) ---

_PROVIDER: "CustomerDataProvider | None" = None


def set_provider(impl: "CustomerDataProvider") -> None:
    """Swap the active provider. Greppable via `git grep set_provider`.

    Called at agent/agent.py module import (production singleton) and by
    the `_provider_swap` autouse fixture in tests/conftest.py (InMemory
    swap). Explicit seam — no constructor injection through @tool
    wrappers (Strands tools are stateless per-call by design).
    """
    global _PROVIDER
    _PROVIDER = impl


def get_provider() -> "CustomerDataProvider":
    """Return the active provider. Raises if set_provider() was never called."""
    if _PROVIDER is None:
        raise RuntimeError(
            "provider not initialised — call set_provider() first"
        )
    return _PROVIDER
