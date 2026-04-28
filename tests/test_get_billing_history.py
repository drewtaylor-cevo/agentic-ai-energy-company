"""Tests for get_billing_history — DATA-01 proof + V5 input validation."""
import importlib
import os
import sys
import pytest


@pytest.fixture
def handler_module(monkeypatch):
    """Re-import handler with TABLE_NAME set so `table` attribute is bound."""
    monkeypatch.setenv("TABLE_NAME", "tariff-billing-test")
    # Force reload so module-level `table` reflects the new env var.
    if "lambda.handler" in sys.modules:
        del sys.modules["lambda.handler"]
    mod = importlib.import_module("lambda.handler")
    return mod


def test_returns_12_months(handler_module, mocker, sarah_billing):
    mock_table = mocker.patch.object(handler_module, "table")
    mock_table.query.return_value = {"Items": sarah_billing}
    result = handler_module.get_billing_history({"customer_id": "CUST-001"}, None)
    assert len(result) == 12


def test_sorted_by_month(handler_module, mocker, sarah_billing):
    mock_table = mocker.patch.object(handler_module, "table")
    mock_table.query.return_value = {"Items": list(reversed(sarah_billing))}
    result = handler_module.get_billing_history({"customer_id": "CUST-001"}, None)
    months = [r["month"] for r in result]
    assert months == sorted(months)


def test_empty_result_returns_empty_list(handler_module, mocker):
    mock_table = mocker.patch.object(handler_module, "table")
    mock_table.query.return_value = {"Items": []}
    result = handler_module.get_billing_history({"customer_id": "CUST-999"}, None)
    assert result == []


def test_rejects_missing_customer_id(handler_module):
    with pytest.raises(ValueError):
        handler_module.get_billing_history({}, None)


def test_rejects_non_string_customer_id(handler_module):
    with pytest.raises(ValueError):
        handler_module.get_billing_history({"customer_id": 123}, None)


def test_rejects_malformed_customer_id(handler_module):
    with pytest.raises(ValueError):
        handler_module.get_billing_history({"customer_id": "'; DROP TABLE customers--"}, None)


def test_rejects_empty_string_customer_id(handler_module):
    with pytest.raises(ValueError):
        handler_module.get_billing_history({"customer_id": ""}, None)


def test_raises_when_table_not_configured(monkeypatch, mocker):
    monkeypatch.delenv("TABLE_NAME", raising=False)
    if "lambda.handler" in sys.modules:
        del sys.modules["lambda.handler"]
    mod = importlib.import_module("lambda.handler")
    assert mod.table is None
    with pytest.raises(RuntimeError, match="TABLE_NAME"):
        mod.get_billing_history({"customer_id": "CUST-001"}, None)


def test_passes_customer_id_to_query(handler_module, mocker):
    mock_table = mocker.patch.object(handler_module, "table")
    mock_table.query.return_value = {"Items": []}
    handler_module.get_billing_history({"customer_id": "CUST-001"}, None)
    call_kwargs = mock_table.query.call_args.kwargs
    assert call_kwargs["ExpressionAttributeValues"][":cid"] == "CUST-001"
    assert "customer_id = :cid" in call_kwargs["KeyConditionExpression"]


# Phase 11-04 D-21 PROFILE filter tests


def _fake_query_with_profile():
    """CUST-006 shape: 12 month rows + 1 PROFILE sentinel row."""
    months = [
        "2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09",
        "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
    ]
    items = [
        {"customer_id": "CUST-006", "month": m, "usage_kwh": 200,
         "cost_usd": 97.49, "plan_id": "STD"}
        for m in months
    ]
    items.append({
        "customer_id": "CUST-006",
        "month": "PROFILE",
        "hardship_flag": True,
    })
    return {"Items": items}


def _fake_query_without_profile():
    """v2.0 shape: 12 month rows only (no PROFILE row)."""
    months = [
        "2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09",
        "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
    ]
    items = [
        {"customer_id": "CUST-001", "month": m, "usage_kwh": 500,
         "cost_usd": 193.48, "plan_id": "STD"}
        for m in months
    ]
    return {"Items": items}


def test_profile_row_filtered_for_hardship_persona(handler_module, mocker):
    """D-21: get_billing_history must strip PROFILE sentinel row before returning.

    Pitfall 4 mitigation: without this filter, simulate_savings_pure would raise KeyError
    on float(r["usage_kwh"]) when it hits the PROFILE row (which has no usage_kwh field).
    """
    mock_table = mocker.patch.object(handler_module, "table")
    mock_table.query.return_value = _fake_query_with_profile()

    result = handler_module.get_billing_history({"customer_id": "CUST-006"}, None)

    assert len(result) == 12, f"expected 12 month rows, got {len(result)}"
    assert all(item["month"] != "PROFILE" for item in result)
    # sorted by month ASC
    assert result[0]["month"] == "2025-04"
    assert result[-1]["month"] == "2026-03"


def test_no_profile_row_for_v2_persona(handler_module, mocker):
    """v2.0 personas have no PROFILE row — filter is a no-op."""
    mock_table = mocker.patch.object(handler_module, "table")
    mock_table.query.return_value = _fake_query_without_profile()

    result = handler_module.get_billing_history({"customer_id": "CUST-001"}, None)

    assert len(result) == 12
    assert result[0]["month"] == "2025-04"
    assert result[-1]["month"] == "2026-03"
