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
