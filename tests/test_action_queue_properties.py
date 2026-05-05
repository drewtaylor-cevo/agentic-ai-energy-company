"""Property-based tests for the Action Queue (Agentic Actions Portfolio).

Feature: agentic-actions-portfolio

Uses Hypothesis for property-based testing with minimum 100 iterations per
property. Each test is tagged with the feature and property reference from
the design document.

Properties tested:
  - Property 1: Action State Machine — Confirm
  - Property 2: Action State Machine — Dismiss
  - Property 3: Expired Actions Rejected
  - Property 14: Queue Action Validation
"""
from __future__ import annotations

import importlib
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from hypothesis import given, settings, assume
from hypothesis import strategies as st

# `from lambda.handler import ...` is a SyntaxError (lambda = Python keyword).
_handler = importlib.import_module("lambda.handler")
queue_action = _handler.queue_action
confirm_action = _handler.confirm_action
dismiss_action = _handler.dismiss_action


# ---------------------------------------------------------------------------
# In-memory DynamoDB table mock for pure-function testing
# ---------------------------------------------------------------------------


class InMemoryTable:
    """Minimal DynamoDB table mock supporting put_item, scan, update_item, get_item."""

    def __init__(self):
        self._items: Dict[str, Dict[str, Any]] = {}

    def _key(self, customer_id: str, month: str) -> str:
        return f"{customer_id}##{month}"

    def put_item(self, Item: Dict[str, Any]) -> None:
        key = self._key(Item["customer_id"], Item["month"])
        self._items[key] = dict(Item)

    def scan(self, FilterExpression: str = "", ExpressionAttributeValues: dict = None, **kwargs) -> dict:
        # Simple filter: match month = :sk
        sk_value = ExpressionAttributeValues.get(":sk", "") if ExpressionAttributeValues else ""
        matched = [item for item in self._items.values() if item.get("month") == sk_value]
        return {"Items": matched}

    def update_item(self, Key: dict, UpdateExpression: str = "", ExpressionAttributeNames: dict = None, ExpressionAttributeValues: dict = None, **kwargs) -> None:
        k = self._key(Key["customer_id"], Key["month"])
        if k in self._items:
            # Parse simple SET #s = :status
            if ExpressionAttributeValues and ":status" in ExpressionAttributeValues:
                self._items[k]["status"] = ExpressionAttributeValues[":status"]

    def get_item(self, Key: dict) -> dict:
        k = self._key(Key["customer_id"], Key["month"])
        if k in self._items:
            return {"Item": self._items[k]}
        return {}


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid action types
_action_types = st.sampled_from(["tariff_switch", "send_sms", "payment_plan_offer"])

# Valid customer IDs
_valid_customer_id = st.from_regex(r"CUST-\d{3,6}", fullmatch=True)

# Valid payload dicts (non-empty)
_valid_payload = st.fixed_dictionaries({
    "plan_id": st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),
}).map(lambda d: d)  # ensure it's a plain dict

# Strategy for a complete valid action payload
_valid_action = st.fixed_dictionaries({
    "action_type": _action_types,
    "customer_id": _valid_customer_id,
    "payload": _valid_payload,
})


# ---------------------------------------------------------------------------
# Property 1: Action State Machine — Confirm
# Feature: agentic-actions-portfolio, Property 1: Action State Machine — Confirm
# **Validates: Requirements 1.3, 2.3, 3.3**
# ---------------------------------------------------------------------------


class TestActionStateMachineConfirm:
    """Property 1: Action State Machine — Confirm.

    *For any* Confirmable_Action in pending status, calling confirm_action
    with its action_id SHALL transition the status to confirmed.

    **Validates: Requirements 1.3, 2.3, 3.3**
    """

    @settings(max_examples=100)
    @given(action_payload=_valid_action)
    def test_confirm_transitions_to_confirmed(self, action_payload):
        # Feature: agentic-actions-portfolio, Property 1: Action State Machine — Confirm
        # **Validates: Requirements 1.3, 2.3, 3.3**
        tbl = InMemoryTable()

        # Queue the action
        queued = queue_action(action_payload, table_client=tbl)
        assert queued["status"] == "pending"

        # Confirm it
        confirmed = confirm_action(queued["action_id"], table_client=tbl)
        assert confirmed["status"] == "confirmed", (
            f"Expected status='confirmed', got {confirmed['status']!r}"
        )
        assert confirmed["action_id"] == queued["action_id"]
        assert confirmed["action_type"] == action_payload["action_type"]
        assert confirmed["customer_id"] == action_payload["customer_id"]


# ---------------------------------------------------------------------------
# Property 2: Action State Machine — Dismiss
# Feature: agentic-actions-portfolio, Property 2: Action State Machine — Dismiss
# **Validates: Requirements 1.4**
# ---------------------------------------------------------------------------


class TestActionStateMachineDismiss:
    """Property 2: Action State Machine — Dismiss.

    *For any* Confirmable_Action in pending status, calling dismiss_action
    with its action_id SHALL transition the status to rejected.

    **Validates: Requirements 1.4**
    """

    @settings(max_examples=100)
    @given(action_payload=_valid_action)
    def test_dismiss_transitions_to_rejected(self, action_payload):
        # Feature: agentic-actions-portfolio, Property 2: Action State Machine — Dismiss
        # **Validates: Requirements 1.4**
        tbl = InMemoryTable()

        # Queue the action
        queued = queue_action(action_payload, table_client=tbl)
        assert queued["status"] == "pending"

        # Dismiss it
        dismissed = dismiss_action(queued["action_id"], table_client=tbl)
        assert dismissed["status"] == "rejected", (
            f"Expected status='rejected', got {dismissed['status']!r}"
        )
        assert dismissed["action_id"] == queued["action_id"]
        assert dismissed["action_type"] == action_payload["action_type"]
        assert dismissed["customer_id"] == action_payload["customer_id"]


# ---------------------------------------------------------------------------
# Property 3: Expired Actions Rejected
# Feature: agentic-actions-portfolio, Property 3: Expired Actions Rejected
# **Validates: Requirements 1.5**
# ---------------------------------------------------------------------------


class TestExpiredActionsRejected:
    """Property 3: Expired Actions Rejected.

    *For any* Confirmable_Action whose expires_at timestamp is in the past,
    calling confirm_action or dismiss_action SHALL return an expiry error.

    **Validates: Requirements 1.5**
    """

    @settings(max_examples=100)
    @given(action_payload=_valid_action)
    def test_expired_action_confirm_raises(self, action_payload):
        # Feature: agentic-actions-portfolio, Property 3: Expired Actions Rejected
        # **Validates: Requirements 1.5**
        tbl = InMemoryTable()

        # Queue the action
        queued = queue_action(action_payload, table_client=tbl)

        # Manually expire it by setting expires_at to the past
        sort_key = f"ACTION#{queued['action_id']}"
        key = tbl._key(action_payload["customer_id"], sort_key)
        tbl._items[key]["expires_at"] = int((datetime.utcnow() - timedelta(hours=1)).timestamp())

        # Confirm should raise expiry error
        import pytest
        with pytest.raises(ValueError, match="expired"):
            confirm_action(queued["action_id"], table_client=tbl)

    @settings(max_examples=100)
    @given(action_payload=_valid_action)
    def test_expired_action_dismiss_raises(self, action_payload):
        # Feature: agentic-actions-portfolio, Property 3: Expired Actions Rejected
        # **Validates: Requirements 1.5**
        tbl = InMemoryTable()

        # Queue the action
        queued = queue_action(action_payload, table_client=tbl)

        # Manually expire it
        sort_key = f"ACTION#{queued['action_id']}"
        key = tbl._key(action_payload["customer_id"], sort_key)
        tbl._items[key]["expires_at"] = int((datetime.utcnow() - timedelta(hours=1)).timestamp())

        # Dismiss should raise expiry error
        import pytest
        with pytest.raises(ValueError, match="expired"):
            dismiss_action(queued["action_id"], table_client=tbl)


# ---------------------------------------------------------------------------
# Property 14: Queue Action Validation
# Feature: agentic-actions-portfolio, Property 14: Queue Action Validation
# **Validates: Requirements 1.2**
# ---------------------------------------------------------------------------


class TestQueueActionValidation:
    """Property 14: Queue Action Validation.

    *For any* valid Confirmable_Action payload, queue_action SHALL store it
    with status pending and expires_at 24h in future. For invalid payload,
    SHALL reject with validation error.

    **Validates: Requirements 1.2**
    """

    @settings(max_examples=100)
    @given(action_payload=_valid_action)
    def test_valid_action_queued_with_pending_and_ttl(self, action_payload):
        # Feature: agentic-actions-portfolio, Property 14: Queue Action Validation
        # **Validates: Requirements 1.2**
        tbl = InMemoryTable()
        now_before = datetime.utcnow()

        result = queue_action(action_payload, table_client=tbl)

        now_after = datetime.utcnow()

        # Status must be pending
        assert result["status"] == "pending", (
            f"Expected status='pending', got {result['status']!r}"
        )

        # action_id must be a valid UUID4
        parsed_uuid = uuid.UUID(result["action_id"])
        assert parsed_uuid.version == 4

        # action_type, customer_id, payload preserved
        assert result["action_type"] == action_payload["action_type"]
        assert result["customer_id"] == action_payload["customer_id"]
        assert result["payload"] == action_payload["payload"]

        # created_at must be a valid ISO timestamp
        assert result["created_at"].endswith("Z")

        # expires_at must be ~24h in the future (within 5 seconds tolerance)
        expected_min = int((now_before + timedelta(hours=24)).timestamp()) - 5
        expected_max = int((now_after + timedelta(hours=24)).timestamp()) + 5
        assert expected_min <= result["expires_at"] <= expected_max, (
            f"expires_at={result['expires_at']} not within 24h window "
            f"[{expected_min}, {expected_max}]"
        )

    @settings(max_examples=100)
    @given(
        invalid_type=st.text(min_size=1, max_size=20).filter(
            lambda s: s not in {"tariff_switch", "send_sms", "payment_plan_offer"}
        )
    )
    def test_invalid_action_type_rejected(self, invalid_type):
        # Feature: agentic-actions-portfolio, Property 14: Queue Action Validation
        # **Validates: Requirements 1.2**
        import pytest
        with pytest.raises(ValueError, match="action_type"):
            queue_action({
                "action_type": invalid_type,
                "customer_id": "CUST-001",
                "payload": {"plan_id": "ECO"},
            })

    @settings(max_examples=100)
    @given(
        invalid_customer=st.one_of(
            st.just(""),
            st.just("INVALID"),
            st.just("CUST-"),
            st.just("CUST-1"),
            st.just("CUST-1234567"),
            st.text(min_size=1, max_size=20).filter(
                lambda s: not s.startswith("CUST-") or not s[5:].isdigit() or len(s[5:]) < 3 or len(s[5:]) > 6
            ),
        )
    )
    def test_invalid_customer_id_rejected(self, invalid_customer):
        # Feature: agentic-actions-portfolio, Property 14: Queue Action Validation
        # **Validates: Requirements 1.2**
        import pytest
        with pytest.raises(ValueError):
            queue_action({
                "action_type": "tariff_switch",
                "customer_id": invalid_customer,
                "payload": {"plan_id": "ECO"},
            })

    @settings(max_examples=100)
    @given(
        invalid_payload=st.one_of(
            st.just(None),
            st.just({}),
            st.just("not a dict"),
            st.just(42),
            st.just([]),
        )
    )
    def test_invalid_payload_rejected(self, invalid_payload):
        # Feature: agentic-actions-portfolio, Property 14: Queue Action Validation
        # **Validates: Requirements 1.2**
        import pytest
        with pytest.raises(ValueError, match="payload"):
            queue_action({
                "action_type": "tariff_switch",
                "customer_id": "CUST-001",
                "payload": invalid_payload,
            })
