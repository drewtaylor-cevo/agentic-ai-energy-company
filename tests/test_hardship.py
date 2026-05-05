"""Phase 14 AGENT-02: Hardship short-circuit offline tests.

Tests the pre-LLM guard in invoke() that fires when hardship_flag is true.
The guard calls get_provider().get_hardship_flag() directly — no LLM involved.
InMemoryProvider is installed by the autouse _provider_swap fixture (conftest.py).

Categories:
  1. TestHardshipGuard — invoke() returns kind: "hardship" for CUST-006
  2. TestHardshipNarrative — D-15 validators on hardship response fields
  3. TestHardshipCodeSide — guard fires without prompt help (code-side enforcement)
  4. TestRecommendationBranchPreserved — REC-03 regression guard
"""
import json
import io
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

import pytest

from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX
# Import agent.agent at MODULE level so the module-level set_provider()
# runs BEFORE the _provider_swap autouse fixture swaps to InMemoryProvider.
# If imported inside test functions, the module-level set_provider() would
# overwrite the fixture's swap.
import agent.agent as _agent_mod
from agent.agent import (
    invoke,
    _four_tool_cap,
    RecommendationResponse,
    TrackInfo,
    HardshipResponse,
)
from agent.providers import get_provider, set_provider


@contextmanager
def _patch_agent_callable(return_value):
    """Patch _agent at both module level AND inside the TariffSpecialist.

    Post-supervisor refactor: TariffSpecialist holds its own reference to
    _agent (self._agent), so patching agent.agent._agent alone doesn't
    affect the specialist's stored reference. We must patch both.
    """
    # Ensure specialists are initialized so we can patch the instance.
    _agent_mod._init_specialists()
    with patch.object(_agent_mod, "_agent", return_value=return_value):
        with patch.object(_agent_mod._tariff_specialist, "_agent", return_value=return_value):
            yield
# All known plan IDs in the tariff catalog — hardship response must contain NONE.
_PLAN_IDS = {"STD", "ECO", "VAL", "TOU", "SOL", "EV-TOU"}

# Verbs that imply recommendation — forbidden in hardship response.
_RECOMMEND_VERBS = {
    "recommend", "recommends", "recommended", "recommending",
    "suggest", "suggests", "suggested", "suggesting",
    "ideal", "optimal", "perfect",
}
def _assert_no_plan_ids(body: dict, context: str = "") -> None:
    """Assert no plan IDs appear anywhere in the serialized body."""
    body_str = json.dumps(body)
    for plan_id in _PLAN_IDS:
        assert plan_id not in body_str, (
            f"Plan ID {plan_id!r} found in hardship response body {context}: {body_str[:200]}"
        )
def _assert_no_recommend_verbs(text: str, field: str) -> None:
    """Assert no recommendation verbs in a text field."""
    words = set(text.lower().split())
    found = words & _RECOMMEND_VERBS
    assert not found, f"Recommend verb(s) {found} found in {field}: {text!r}"
class TestHardshipGuard:
    """Category 1: invoke() returns kind: 'hardship' for hardship-flagged customers."""

    def test_cust006_returns_hardship_kind(self):
        """CUST-006 (hardship_flag: true) → kind: 'hardship', no green/cheapest."""
        # InMemoryProvider is already installed by _provider_swap autouse fixture.
        # CUST-006 has hardship_flag: true in PROFILE_ITEMS.
        # The pre-LLM guard should fire before _agent() is called.
        with patch("agent.agent._agent") as mock_agent:
            response = invoke({"customer_id": "CUST-006"})

        assert response["kind"] == "hardship"
        assert response["customer_id"] == "CUST-006"
        assert "green" not in response
        assert "cheapest" not in response
        assert response["routing_target"] == "hardship_team"
        # The agent should NOT have been called — pre-LLM guard short-circuits.
        mock_agent.assert_not_called()

    def test_cust006_has_narrative_source_marker(self):
        """Hardship response carries _narrative_source for observability."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        assert "_narrative_source" in response
        assert "hardship" in response["_narrative_source"]

    def test_cust001_still_returns_recommendation(self):
        """Non-hardship persona (CUST-001) → kind: 'recommendation' with both tracks."""
        _four_tool_cap.reset()

        # Mock the agent to return a valid recommendation.
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

        with _patch_agent_callable(mock_result):
            response = invoke({"customer_id": "CUST-001"})

        assert response.get("kind") == "recommendation"
        assert "green" in response
        assert "cheapest" in response

    def test_hardship_guard_failure_falls_through_to_recommendation(self):
        """D-04: if get_hardship_flag raises, invoke() falls through to normal path."""
        _four_tool_cap.reset()

        # Create a provider that raises on get_hardship_flag.
        broken_provider = MagicMock()
        broken_provider.get_hardship_flag.side_effect = RuntimeError("provider broken")

        # Mock the agent to return a valid recommendation.
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

        original = get_provider()
        set_provider(broken_provider)
        try:
            with _patch_agent_callable(mock_result):
                response = invoke({"customer_id": "CUST-006"})
        finally:
            set_provider(original)

        # Should have fallen through to recommendation path, not raised.
        assert isinstance(response, dict)
        assert "green" in response or "errorMessage" in response  # either path is D-04 compliant
class TestHardshipNarrative:
    """Category 2: D-15 validators on hardship response fields."""

    def test_reason_has_no_digits(self):
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        assert not NUMERIC_REGEX.search(response["reason"]), \
            f"Digits/currency in reason: {response['reason']!r}"

    def test_call_script_has_no_digits(self):
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        assert not NUMERIC_REGEX.search(response["call_script"]), \
            f"Digits/currency in call_script: {response['call_script']!r}"

    def test_reason_has_no_banned_terms(self):
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        m = BANNED_REGEX.search(response["reason"])
        assert m is None, f"Banned term in reason: {m.group()!r}"

    def test_call_script_has_no_banned_terms(self):
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        m = BANNED_REGEX.search(response["call_script"])
        assert m is None, f"Banned term in call_script: {m.group()!r}"

    def test_no_plan_ids_in_hardship_body(self):
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        _assert_no_plan_ids(response, "CUST-006")

    def test_no_recommend_verbs_in_reason(self):
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        _assert_no_recommend_verbs(response["reason"], "reason")

    def test_no_recommend_verbs_in_call_script(self):
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        _assert_no_recommend_verbs(response["call_script"], "call_script")

    def test_reason_within_word_cap(self):
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        words = response["reason"].split()
        assert len(words) <= 20, f"reason has {len(words)} words (cap 20)"

    def test_call_script_within_word_cap(self):
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        words = response["call_script"].split()
        assert len(words) <= 22, f"call_script has {len(words)} words (cap 22)"
class TestHardshipCodeSide:
    """Category 3: guard fires without prompt help (code-side enforcement).

    The pre-LLM guard in invoke() calls get_provider().get_hardship_flag()
    BEFORE _agent() — the LLM never sees tariff context. This test proves
    the guard is code-side by verifying _agent is never called.
    """

    def test_agent_never_called_for_hardship_customer(self):
        """The LLM is never invoked for a hardship-flagged customer."""
        with patch("agent.agent._agent") as mock_agent:
            response = invoke({"customer_id": "CUST-006"})

        mock_agent.assert_not_called()
        assert response["kind"] == "hardship"

    def test_hardship_response_has_no_tariff_context(self):
        """Hardship body contains no tariff plan references whatsoever."""
        with patch("agent.agent._agent"):
            response = invoke({"customer_id": "CUST-006"})

        body_str = json.dumps(response)
        # No plan names
        for name in ["EcoFlex", "Value 12", "Solar Feed-in", "EV Drive", "Standard"]:
            assert name not in body_str, f"Plan name {name!r} leaked into hardship body"
        # No plan IDs
        _assert_no_plan_ids(response, "code-side check")
class TestRecommendationBranchPreserved:
    """Category 4: REC-03 regression guard — recommendation responses always
    carry both green and cheapest tracks."""

    @pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
    def test_non_hardship_personas_have_both_tracks(self, customer_id):
        """REC-03: kind: 'recommendation' responses always have green + cheapest."""
        _four_tool_cap.reset()

        mock_result = MagicMock()
        mock_result.stop_reason = "end_turn"
        mock_result.structured_output = RecommendationResponse(
            green=TrackInfo(
                plan_id="ECO", plan_name="EcoFlex 100",
                saving_monthly=30.0, saving_annual=360.0,
                usage_narrative="Household profile with consistent usage across the year.",
                call_script="Ask about EcoFlex for your household.",
            ),
            cheapest=TrackInfo(
                plan_id="VAL", plan_name="Value 12",
                saving_monthly=55.0, saving_annual=660.0,
                usage_narrative="High consumption household with seasonal variation.",
                call_script="Bring up Value Twelve for your home.",
            ),
        )
        mock_result.message = {"content": []}

        with _patch_agent_callable(mock_result):
            response = invoke({"customer_id": customer_id})

        assert response.get("kind") == "recommendation", \
            f"{customer_id} should return kind: recommendation"
        assert "green" in response, f"{customer_id} missing green track"
        assert "cheapest" in response, f"{customer_id} missing cheapest track"
