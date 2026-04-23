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
