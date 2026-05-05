"""PROD-01 test suite — Protocol satisfaction + byte-exact savings + Salesforce stub.

D-09 hard pre-deploy gate: this suite MUST pass before Plan 06 lifts the
CustomerTariff + CustomerTariffAgent stack policies.

D-12 three categories:
  1. Protocol isinstance() — proves @runtime_checkable works for all 3 impls.
  2. InMemoryProvider byte-exact savings — proves the offline test double
     reproduces the Phase 11 locked values for all 6 personas via
     simulate_savings_pure reuse.
  3. SalesforceCustomerDataProvider NotImplementedError — proves the stub
     is constructible (for isinstance) but raises the DOC-03 breadcrumb
     message on every method call.
"""
from unittest.mock import MagicMock

import pytest

from agent.providers import (
    CustomerDataProvider,
    InMemoryProvider,
    SalesforceCustomerDataProvider,
    ToolsLambdaProvider,
)


# --- Category 1: Protocol isinstance (D-12 category 1) ---


def test_tools_lambda_provider_satisfies_protocol():
    client = MagicMock()
    provider = ToolsLambdaProvider(client, "arn:aws:lambda:us-east-1:000000000000:function:tariff-tools")
    assert isinstance(provider, CustomerDataProvider)


def test_inmemory_provider_satisfies_protocol():
    assert isinstance(InMemoryProvider(), CustomerDataProvider)


def test_salesforce_provider_satisfies_protocol():
    assert isinstance(SalesforceCustomerDataProvider(), CustomerDataProvider)


# --- Category 2: InMemoryProvider byte-exact savings (D-12 category 2, D-09 gate) ---


@pytest.mark.parametrize(
    "customer_id,fixture_name",
    [
        ("CUST-001", "mock_savings_response"),
        ("CUST-002", "mock_marcus_response"),
        ("CUST-003", "mock_elena_response"),
        ("CUST-004", "mock_cust004_response"),
        ("CUST-005", "mock_cust005_response"),
        ("CUST-006", "mock_cust006_response"),
    ],
    ids=["CUST-001", "CUST-002", "CUST-003", "CUST-004", "CUST-005", "CUST-006"],
)
def test_inmemory_provider_byte_exact_savings(customer_id, fixture_name, request, inmemory_provider):
    """D-08 numeric fields only: plan_id, plan_name, saving_monthly, saving_annual."""
    expected = request.getfixturevalue(fixture_name)
    result = inmemory_provider.simulate_savings(customer_id)
    for track in ("green", "cheapest"):
        for field in ("plan_id", "plan_name", "saving_monthly", "saving_annual"):
            assert result[track][field] == expected[track][field], (
                f"{customer_id} {track}.{field}: "
                f"{result[track][field]!r} != {expected[track][field]!r}"
            )


def test_inmemory_provider_hardship_flag_cust006_is_true(inmemory_provider):
    """DATA-06 hardship row round-trips through the provider shape."""
    result = inmemory_provider.get_hardship_flag("CUST-006")
    assert result == {"hardship": True, "hardship_category": None, "customer_id": "CUST-006"}


def test_inmemory_provider_hardship_flag_cust001_is_false(inmemory_provider):
    """Non-hardship persona → {hardship: False, …} (no PROFILE row for CUST-001)."""
    result = inmemory_provider.get_hardship_flag("CUST-001")
    assert result == {"hardship": False, "hardship_category": None, "customer_id": "CUST-001"}


# --- Category 3: SalesforceCustomerDataProvider NotImplementedError (D-12 category 3) ---


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
