# tests/test_get_hardship_flag_pure.py — NEW (DATA-06 unit coverage, Phase 11-04)
import importlib
from unittest.mock import MagicMock
import pytest

# importlib fallback — `from lambda.handler import` is a SyntaxError in Python
handler = importlib.import_module("lambda.handler")
get_hardship_flag_pure = handler.get_hardship_flag_pure


def _fake_table_with_item(item):
    client = MagicMock()
    client.get_item.return_value = {"Item": item} if item else {}
    return client


def test_hardship_persona_returns_true():
    """CUST-006 has PROFILE row with hardship_flag=True."""
    client = _fake_table_with_item({
        "customer_id": "CUST-006",
        "month": "PROFILE",
        "hardship_flag": True,
    })
    result = get_hardship_flag_pure("CUST-006", client)
    assert result == {"hardship": True, "customer_id": "CUST-006"}


def test_nonhardship_persona_returns_false_when_profile_missing():
    """CUST-001 has no PROFILE row — default hardship=False per m3 mitigation."""
    client = _fake_table_with_item(None)
    result = get_hardship_flag_pure("CUST-001", client)
    assert result == {"hardship": False, "customer_id": "CUST-001"}


def test_malformed_customer_id_rejected():
    """V5 input validation — _validate_customer_id guards entry."""
    client = MagicMock()
    with pytest.raises(ValueError):
        get_hardship_flag_pure("not-a-customer-id", client)
    # Ensure DynamoDB was NEVER called — V5 gate fired first
    client.get_item.assert_not_called()


def test_profile_item_with_hardship_false_returns_false():
    """Defensive: PROFILE row present but hardship_flag=False still returns False."""
    client = _fake_table_with_item({
        "customer_id": "CUST-001",
        "month": "PROFILE",
        "hardship_flag": False,
    })
    result = get_hardship_flag_pure("CUST-001", client)
    assert result == {"hardship": False, "customer_id": "CUST-001"}
