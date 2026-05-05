"""Task 8: End-to-End Integration & Backward Compatibility tests.

Tests the full invoke() flow for typed hardship categories, non-hardship
recommendation path, backward compatibility, and the narrative=off kill-switch.

Categories:
  1. TestFamilyViolenceE2E — CUST-009 (family_violence) full invoke() flow
  2. TestNonHardshipE2E — CUST-001 (non-hardship) recommendation path unchanged
  3. TestBackwardCompatE2E — CUST-006 (no category) returns "other" backward-compat
  4. TestNarrativeOffKillSwitch — ?narrative=off strips compliance_review and supervisor_trace
"""
import json
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

import pytest

import agent.agent as _agent_mod
from agent.agent import (
    invoke,
    _four_tool_cap,
    RecommendationResponse,
    TrackInfo,
)
from agent.specialists.hardship_config import FINANCIAL_TERMS


@contextmanager
def _patch_agent_callable(return_value):
    """Patch _agent at both module level AND inside the TariffSpecialist.

    Post-supervisor refactor: TariffSpecialist holds its own reference to
    _agent (self._agent), so patching agent.agent._agent alone doesn't
    affect the specialist's stored reference. We must patch both.
    """
    _agent_mod._init_specialists()
    with patch.object(_agent_mod, "_agent", return_value=return_value):
        with patch.object(_agent_mod._tariff_specialist, "_agent", return_value=return_value):
            yield


class TestFamilyViolenceE2E:
    """8.1: Full invoke() call with CUST-009 (family_violence) returns correct
    category, routing_target, compliance passes, and no financial terms."""

    def test_cust009_category_is_family_violence(self):
        """CUST-009 → category: 'family_violence'."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-009"})

        assert response["category"] == "family_violence"

    def test_cust009_routing_target(self):
        """CUST-009 → routing_target: 'family_violence_team'."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-009"})

        assert response["routing_target"] == "family_violence_team"

    def test_cust009_compliance_review_passes(self):
        """CUST-009 → compliance_review verdict is 'pass'."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-009"})

        assert "compliance_review" in response
        assert response["compliance_review"]["verdict"] == "pass"

    def test_cust009_compliance_rules_checked(self):
        """CUST-009 → compliance_review includes hardship-specific rules."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-009"})

        rules = response["compliance_review"]["rules_checked"]
        assert "hardship_no_tariff_data" in rules
        assert "hardship_category_tool_restriction" in rules
        assert "family_violence_no_financial_content" in rules

    def test_cust009_no_financial_terms_in_reason(self):
        """CUST-009 → reason contains no financial terminology."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-009"})

        reason_tokens = [
            word.strip(".,;:!?'\"()-").lower()
            for word in response["reason"].split()
        ]
        found = set(reason_tokens) & FINANCIAL_TERMS
        assert not found, f"Financial terms in reason: {found}"

    def test_cust009_no_financial_terms_in_call_script(self):
        """CUST-009 → call_script contains no financial terminology."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-009"})

        script_tokens = [
            word.strip(".,;:!?'\"()-").lower()
            for word in response["call_script"].split()
        ]
        found = set(script_tokens) & FINANCIAL_TERMS
        assert not found, f"Financial terms in call_script: {found}"

    def test_cust009_no_financial_terms_in_permitted_actions(self):
        """CUST-009 → permitted_actions contains no financial terminology."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-009"})

        actions_str = " ".join(response.get("permitted_actions", []))
        actions_tokens = [
            word.strip(".,;:!?'\"()-").lower()
            for word in actions_str.split()
        ]
        found = set(actions_tokens) & FINANCIAL_TERMS
        assert not found, f"Financial terms in permitted_actions: {found}"

    def test_cust009_kind_is_hardship(self):
        """CUST-009 → kind: 'hardship'."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-009"})

        assert response["kind"] == "hardship"

    def test_cust009_permitted_actions(self):
        """CUST-009 → permitted_actions: ['schedule_callback']."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-009"})

        assert response["permitted_actions"] == ["schedule_callback"]

    def test_cust009_has_supervisor_trace(self):
        """CUST-009 → supervisor_trace attached with routing info."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-009"})

        assert "supervisor_trace" in response
        assert response["supervisor_trace"]["routed_to"] == "HardshipSpecialist"

    def test_cust009_agent_not_called(self):
        """CUST-009 → LLM agent is never invoked (code-side only)."""
        with patch("agent.agent._agent") as mock_agent:
            invoke({"customer_id": "CUST-009"})

        mock_agent.assert_not_called()


class TestNonHardshipE2E:
    """8.2: Full invoke() call with CUST-001 (non-hardship) is completely
    unchanged — recommendation path unaffected."""

    def _mock_recommendation_result(self):
        """Build a mock agent result returning a valid recommendation."""
        mock_result = MagicMock()
        mock_result.stop_reason = "end_turn"
        mock_result.structured_output = RecommendationResponse(
            green=TrackInfo(
                plan_id="ECO", plan_name="EcoFlex 100",
                saving_monthly=30.0, saving_annual=360.0,
                usage_narrative="Strong cool-season usage with a family-sized load.",
                call_script="Ask about EcoFlex for your household.",
            ),
            cheapest=TrackInfo(
                plan_id="VAL", plan_name="Value 12",
                saving_monthly=55.0, saving_annual=660.0,
                usage_narrative="Consistently high household consumption pattern.",
                call_script="Bring up Value Twelve for your home.",
            ),
        )
        mock_result.message = {"content": []}
        return mock_result

    def test_cust001_returns_recommendation_kind(self):
        """CUST-001 → kind: 'recommendation'."""
        _four_tool_cap.reset()
        mock_result = self._mock_recommendation_result()

        with _patch_agent_callable(mock_result):
            response = invoke({"customer_id": "CUST-001"})

        assert response.get("kind") == "recommendation"

    def test_cust001_has_green_track(self):
        """CUST-001 → response has green track."""
        _four_tool_cap.reset()
        mock_result = self._mock_recommendation_result()

        with _patch_agent_callable(mock_result):
            response = invoke({"customer_id": "CUST-001"})

        assert "green" in response

    def test_cust001_has_cheapest_track(self):
        """CUST-001 → response has cheapest track."""
        _four_tool_cap.reset()
        mock_result = self._mock_recommendation_result()

        with _patch_agent_callable(mock_result):
            response = invoke({"customer_id": "CUST-001"})

        assert "cheapest" in response

    def test_cust001_no_hardship_fields(self):
        """CUST-001 → no hardship-related fields (category, routing_target, permitted_actions)."""
        _four_tool_cap.reset()
        mock_result = self._mock_recommendation_result()

        with _patch_agent_callable(mock_result):
            response = invoke({"customer_id": "CUST-001"})

        # Recommendation responses should NOT have hardship-specific fields
        assert "category" not in response or response.get("kind") != "hardship"
        assert response.get("kind") == "recommendation"

    def test_cust001_has_compliance_review(self):
        """CUST-001 → compliance_review attached."""
        _four_tool_cap.reset()
        mock_result = self._mock_recommendation_result()

        with _patch_agent_callable(mock_result):
            response = invoke({"customer_id": "CUST-001"})

        assert "compliance_review" in response

    def test_cust001_has_supervisor_trace(self):
        """CUST-001 → supervisor_trace attached with TariffSpecialist routing."""
        _four_tool_cap.reset()
        mock_result = self._mock_recommendation_result()

        with _patch_agent_callable(mock_result):
            response = invoke({"customer_id": "CUST-001"})

        assert "supervisor_trace" in response
        assert response["supervisor_trace"]["routed_to"] == "TariffSpecialist"


class TestBackwardCompatE2E:
    """8.3: Full invoke() call with CUST-006 (existing hardship persona, no category)
    returns category 'other' with backward-compatible response."""

    def test_cust006_category_is_other(self):
        """CUST-006 (no hardship_category) → category: 'other'."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        assert response["category"] == "other"

    def test_cust006_routing_target(self):
        """CUST-006 → routing_target: 'hardship_team'."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        assert response["routing_target"] == "hardship_team"

    def test_cust006_has_reason_and_call_script(self):
        """CUST-006 → response has reason and call_script (generic hardship)."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        assert "reason" in response
        assert "call_script" in response
        assert len(response["reason"]) > 0
        assert len(response["call_script"]) > 0

    def test_cust006_permitted_actions(self):
        """CUST-006 → permitted_actions: ['schedule_callback']."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        assert response["permitted_actions"] == ["schedule_callback"]

    def test_cust006_kind_is_hardship(self):
        """CUST-006 → kind: 'hardship'."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        assert response["kind"] == "hardship"

    def test_cust006_compliance_review_passes(self):
        """CUST-006 → compliance_review verdict is 'pass'."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        assert "compliance_review" in response
        assert response["compliance_review"]["verdict"] == "pass"


class TestNarrativeOffKillSwitch:
    """8.4: ?narrative=off kill-switch strips compliance_review and
    supervisor_trace from typed hardship responses."""

    def test_narrative_off_strips_compliance_review_hardship(self):
        """narrative=off → compliance_review stripped from hardship response."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-009", "narrative": "off"})

        assert "compliance_review" not in response

    def test_narrative_off_strips_supervisor_trace_hardship(self):
        """narrative=off → supervisor_trace stripped from hardship response."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-009", "narrative": "off"})

        assert "supervisor_trace" not in response

    def test_narrative_off_preserves_core_hardship_fields(self):
        """narrative=off → core hardship fields (kind, category, routing_target) preserved."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-009", "narrative": "off"})

        assert response["kind"] == "hardship"
        assert response["category"] == "family_violence"
        assert response["routing_target"] == "family_violence_team"
        assert "reason" in response
        assert "call_script" in response

    def test_narrative_off_strips_compliance_review_other_category(self):
        """narrative=off → compliance_review stripped from 'other' category too."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006", "narrative": "off"})

        assert "compliance_review" not in response
        assert "supervisor_trace" not in response

    def test_narrative_on_keeps_compliance_review(self):
        """Without narrative=off → compliance_review and supervisor_trace present."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-009"})

        assert "compliance_review" in response
        assert "supervisor_trace" in response
