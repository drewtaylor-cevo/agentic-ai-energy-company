"""Phase 16 AGENT-03 Task 6: HardshipSpecialist integration tests.

Tests the full flow through HardshipSpecialist.handle() with typed categories.

Categories:
  1. TestPaymentDifficultyRouting — CUST-007 (payment_difficulty) returns correct
     routing_target, permitted_actions, and category-specific call_script.
  2. TestBackwardCompatGeneric — CUST-006 (hardship_flag: true, no category)
     returns the generic "other" response (CP-4 backward compat).
"""
from unittest.mock import patch

import pytest

from agent.specialists.hardship import HardshipSpecialist
from agent.specialists.hardship_config import HARDSHIP_CATEGORIES


class TestPaymentDifficultyRouting:
    """6.5: invoke with payment_difficulty customer returns correct routing,
    permitted_actions, and category-specific call_script."""

    def test_payment_difficulty_routing_target(self):
        """CUST-007 (payment_difficulty) → routing_target: 'hardship_team'."""
        specialist = HardshipSpecialist()
        payload = {"customer_id": "CUST-007", "hardship_category": "payment_difficulty"}
        response = specialist.handle(payload)

        assert response["routing_target"] == "hardship_team"

    def test_payment_difficulty_permitted_actions(self):
        """CUST-007 (payment_difficulty) → permitted_actions include payment_plan, billing_history, schedule_callback."""
        specialist = HardshipSpecialist()
        payload = {"customer_id": "CUST-007", "hardship_category": "payment_difficulty"}
        response = specialist.handle(payload)

        assert response["permitted_actions"] == ["payment_plan", "billing_history", "schedule_callback"]

    def test_payment_difficulty_category_field(self):
        """CUST-007 (payment_difficulty) → category: 'payment_difficulty'."""
        specialist = HardshipSpecialist()
        payload = {"customer_id": "CUST-007", "hardship_category": "payment_difficulty"}
        response = specialist.handle(payload)

        assert response["category"] == "payment_difficulty"

    def test_payment_difficulty_call_script(self):
        """CUST-007 (payment_difficulty) → call_script matches the payment_difficulty script from FALLBACKS."""
        specialist = HardshipSpecialist()
        payload = {"customer_id": "CUST-007", "hardship_category": "payment_difficulty"}
        response = specialist.handle(payload)

        # The call_script should be the payment_difficulty-specific script
        assert "flexible options" in response["call_script"] or "support" in response["call_script"]
        # Must NOT be the generic "other" script
        assert response["call_script"] != "Let me connect you with our specialist support team who can best help with your account."

    def test_payment_difficulty_kind(self):
        """CUST-007 (payment_difficulty) → kind: 'hardship'."""
        specialist = HardshipSpecialist()
        payload = {"customer_id": "CUST-007", "hardship_category": "payment_difficulty"}
        response = specialist.handle(payload)

        assert response["kind"] == "hardship"

    def test_payment_difficulty_narrative_source(self):
        """CUST-007 (payment_difficulty) → _narrative_source includes category."""
        specialist = HardshipSpecialist()
        payload = {"customer_id": "CUST-007", "hardship_category": "payment_difficulty"}
        response = specialist.handle(payload)

        assert "_narrative_source" in response
        assert response["_narrative_source"]["hardship"]["category"] == "payment_difficulty"

    def test_payment_difficulty_full_invoke_flow(self):
        """Full invoke() flow with CUST-007 returns correct typed response."""
        from agent.agent import invoke

        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-007"})

        assert response["kind"] == "hardship"
        assert response["category"] == "payment_difficulty"
        assert response["routing_target"] == "hardship_team"
        assert response["permitted_actions"] == ["payment_plan", "billing_history", "schedule_callback"]


class TestBackwardCompatGeneric:
    """6.6: invoke with hardship_flag: true but no hardship_category returns
    the generic 'other' response (backward compat — CP-4)."""

    def test_no_category_defaults_to_other(self):
        """Payload with no hardship_category → category: 'other'."""
        specialist = HardshipSpecialist()
        payload = {"customer_id": "CUST-006"}
        response = specialist.handle(payload)

        assert response["category"] == "other"

    def test_no_category_routing_target(self):
        """No hardship_category → routing_target: 'hardship_team'."""
        specialist = HardshipSpecialist()
        payload = {"customer_id": "CUST-006"}
        response = specialist.handle(payload)

        assert response["routing_target"] == "hardship_team"

    def test_no_category_permitted_actions(self):
        """No hardship_category → permitted_actions: ['schedule_callback']."""
        specialist = HardshipSpecialist()
        payload = {"customer_id": "CUST-006"}
        response = specialist.handle(payload)

        assert response["permitted_actions"] == ["schedule_callback"]

    def test_no_category_narrative_source(self):
        """No hardship_category → _narrative_source category is 'other'."""
        specialist = HardshipSpecialist()
        payload = {"customer_id": "CUST-006"}
        response = specialist.handle(payload)

        assert response["_narrative_source"]["hardship"]["category"] == "other"

    def test_none_category_defaults_to_other(self):
        """Payload with hardship_category=None → category: 'other'."""
        specialist = HardshipSpecialist()
        payload = {"customer_id": "CUST-006", "hardship_category": None}
        response = specialist.handle(payload)

        assert response["category"] == "other"

    def test_unrecognised_category_defaults_to_other(self):
        """Payload with unrecognised hardship_category → category: 'other'."""
        specialist = HardshipSpecialist()
        payload = {"customer_id": "CUST-006", "hardship_category": "unknown_category"}
        response = specialist.handle(payload)

        assert response["category"] == "other"

    def test_full_invoke_flow_cust006_backward_compat(self):
        """Full invoke() flow with CUST-006 (no category) returns 'other' response."""
        from agent.agent import invoke

        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        assert response["kind"] == "hardship"
        assert response["category"] == "other"
        assert response["routing_target"] == "hardship_team"
        assert response["permitted_actions"] == ["schedule_callback"]

    def test_full_invoke_flow_cust006_has_reason_and_call_script(self):
        """Full invoke() flow with CUST-006 returns dignity-preserving reason and call_script."""
        from agent.agent import invoke

        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        assert "reason" in response
        assert "call_script" in response
        assert len(response["reason"]) > 0
        assert len(response["call_script"]) > 0
