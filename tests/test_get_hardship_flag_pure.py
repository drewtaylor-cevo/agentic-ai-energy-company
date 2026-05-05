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
    assert result == {"hardship": True, "hardship_category": None, "customer_id": "CUST-006"}


def test_nonhardship_persona_returns_false_when_profile_missing():
    """CUST-001 has no PROFILE row — default hardship=False per m3 mitigation."""
    client = _fake_table_with_item(None)
    result = get_hardship_flag_pure("CUST-001", client)
    assert result == {"hardship": False, "hardship_category": None, "customer_id": "CUST-001"}


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
    assert result == {"hardship": False, "hardship_category": None, "customer_id": "CUST-001"}


def test_hardship_persona_with_category_returns_category():
    """CUST-007 has PROFILE row with hardship_flag=True and hardship_category set."""
    client = _fake_table_with_item({
        "customer_id": "CUST-007",
        "month": "PROFILE",
        "hardship_flag": True,
        "hardship_category": "payment_difficulty",
    })
    result = get_hardship_flag_pure("CUST-007", client)
    assert result == {
        "hardship": True,
        "hardship_category": "payment_difficulty",
        "customer_id": "CUST-007",
    }


# --- Property-based test (CP-4 partial): hardship_flag=True + no hardship_category → None ---

from hypothesis import given, settings
from hypothesis import strategies as st


# Strategy: generate valid CUST-NNN customer IDs (3-6 digits)
_customer_id_st = st.integers(min_value=100, max_value=999999).map(lambda n: f"CUST-{n:03d}")


class TestHardshipCategoryNoneWhenAbsent:
    """CP-4 partial: for any customer with hardship_flag=True and no hardship_category
    attribute, the response has hardship_category=None.

    **Validates: Requirements 1.2**
    """

    @settings(max_examples=100)
    @given(customer_id=_customer_id_st)
    def test_hardship_true_no_category_returns_none(self, customer_id):
        """Property: hardship_flag=True + absent hardship_category → hardship_category is None."""
        # Feature: typed-hardship-categories, Property CP-4 partial
        # **Validates: Requirements 1.2**
        client = _fake_table_with_item({
            "customer_id": customer_id,
            "month": "PROFILE",
            "hardship_flag": True,
            # hardship_category intentionally absent
        })
        result = get_hardship_flag_pure(customer_id, client)
        assert result["hardship"] is True
        assert result["hardship_category"] is None
        assert result["customer_id"] == customer_id
