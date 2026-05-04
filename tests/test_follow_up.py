"""Phase 15 WF-01: Offline tests for follow-up email workflow.

Tests cover:
- FollowUpEmailResponse model validation (D-15 extended)
- draft_follow_up() happy path and fallback path (D-04)
- Memory config isolation (C4 prevention)
- Invariant guards (recommendation + hardship paths unchanged)
"""
import re
import pytest

from agent.agent import (
    FollowUpEmailResponse,
    draft_follow_up,
    _build_follow_up_response,
    _FOLLOW_UP_DEFAULTS,
    invoke,
)
from agent.memory.config import build_memory_config
from agent.narrative.fallbacks import FALLBACKS, FOLLOW_UP_FALLBACKS
from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX


# --- TestFollowUpModel: Pydantic model validation ---


class TestFollowUpModel:
    """FollowUpEmailResponse Pydantic model validates D-15 rules."""

    def test_valid_response(self):
        resp = FollowUpEmailResponse(
            customer_id="CUST-001",
            subject="Your tariff options from our recent conversation",
            body=(
                "Thank you for speaking with us about your energy plan options. "
                "Please review the options at your convenience."
            ),
            plan_reference="EcoFlex Green",
        )
        assert resp.kind == "follow_up"
        assert resp.customer_id == "CUST-001"

    def test_body_rejects_digits(self):
        with pytest.raises(Exception):
            FollowUpEmailResponse(
                customer_id="CUST-001",
                subject="Your tariff options",
                body="You could save $30 per month on your energy bill.",
                plan_reference="EcoFlex Green",
            )

    def test_body_rejects_currency(self):
        with pytest.raises(Exception):
            FollowUpEmailResponse(
                customer_id="CUST-001",
                subject="Your tariff options",
                body="The plan saves approximately £50 annually for your household.",
                plan_reference="EcoFlex Green",
            )

    def test_subject_rejects_digits(self):
        with pytest.raises(Exception):
            FollowUpEmailResponse(
                customer_id="CUST-001",
                subject="Save 30 dollars with our plan",
                body="Thank you for speaking with us about your energy plan options.",
                plan_reference="EcoFlex Green",
            )

    def test_body_rejects_switch_verbs(self):
        with pytest.raises(Exception):
            FollowUpEmailResponse(
                customer_id="CUST-001",
                subject="Your tariff options",
                body="We recommend you switch to the new plan as soon as possible.",
                plan_reference="EcoFlex Green",
            )

    def test_kind_defaults_to_follow_up(self):
        resp = FollowUpEmailResponse(
            customer_id="CUST-001",
            subject="Your tariff options from our recent conversation",
            body="Thank you for speaking with us about your energy plan options.",
            plan_reference="EcoFlex Green",
        )
        assert resp.kind == "follow_up"


# --- TestFollowUpFallback: fallback template validation ---


class TestFollowUpFallback:
    """Fallback templates pass D-15 validators and produce valid responses."""

    def test_build_follow_up_response_cust001(self):
        body = _build_follow_up_response("CUST-001")
        assert body["kind"] == "follow_up"
        assert body["customer_id"] == "CUST-001"
        assert "subject" in body
        assert "body" in body
        assert "plan_reference" in body

    def test_build_follow_up_response_unknown_customer(self):
        """Unknown customer falls back to _FOLLOW_UP_DEFAULTS."""
        body = _build_follow_up_response("CUST-999")
        assert body["kind"] == "follow_up"
        assert body["customer_id"] == "CUST-999"
        assert body["subject"] == _FOLLOW_UP_DEFAULTS["subject"]

    @pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
    def test_fallback_templates_pass_d15(self, customer_id):
        """All follow-up fallback templates pass D-15 validators."""
        fb = FOLLOW_UP_FALLBACKS[customer_id]
        # Subject: no digits, no currency, no banned terms
        assert not NUMERIC_REGEX.search(fb["subject"]), f"{customer_id} subject has digits/currency"
        assert not BANNED_REGEX.search(fb["subject"]), f"{customer_id} subject has banned term"
        # Body: no digits, no currency, no banned terms
        assert not NUMERIC_REGEX.search(fb["body"]), f"{customer_id} body has digits/currency"
        assert not BANNED_REGEX.search(fb["body"]), f"{customer_id} body has banned term"

    def test_fallback_plan_reference_is_name_not_id(self):
        """plan_reference is a plan name, not a plan ID."""
        for cust_id, fb in FOLLOW_UP_FALLBACKS.items():
            # Plan IDs are short uppercase codes like ECO, VAL, SOL, EV-TOU
            assert len(fb["plan_reference"]) > 5, (
                f"{cust_id}: plan_reference looks like a plan ID, not a name"
            )

    def test_draft_follow_up_fallback_on_no_memory(self):
        """draft_follow_up returns fallback when MEMORY_ID is empty."""
        import agent.agent as agent_mod
        original = agent_mod._MEMORY_ID
        try:
            agent_mod._MEMORY_ID = ""
            result = draft_follow_up({"customer_id": "CUST-001"})
            assert result["kind"] == "follow_up"
            assert result["customer_id"] == "CUST-001"
            assert result["_workflow_source"]["subject"] == "fallback"
            assert result["_workflow_source"]["body"] == "fallback"
        finally:
            agent_mod._MEMORY_ID = original

    def test_draft_follow_up_never_raises(self):
        """D-04: draft_follow_up never raises, even with bad customer_id."""
        import agent.agent as agent_mod
        original = agent_mod._MEMORY_ID
        try:
            agent_mod._MEMORY_ID = ""
            result = draft_follow_up({"customer_id": "CUST-999"})
            assert result["kind"] == "follow_up"
        finally:
            agent_mod._MEMORY_ID = original

    def test_draft_follow_up_missing_customer_id(self):
        """Missing customer_id returns error dict."""
        result = draft_follow_up({})
        assert "error" in result


# --- TestFollowUpIsolation: Memory config isolation (C4 prevention) ---


class TestFollowUpIsolation:
    """Memory config produces customer-scoped, deterministic session keys."""

    def test_actor_id_scoped_to_customer(self):
        config = build_memory_config("mem-123", "CUST-001", "2026-05-03")
        assert config.actor_id == "customer:CUST-001"

    def test_session_id_deterministic(self):
        c1 = build_memory_config("mem-123", "CUST-001", "2026-05-03")
        c2 = build_memory_config("mem-123", "CUST-001", "2026-05-03")
        assert c1.session_id == c2.session_id

    def test_different_customers_different_actor_ids(self):
        c1 = build_memory_config("mem-123", "CUST-001", "2026-05-03")
        c2 = build_memory_config("mem-123", "CUST-002", "2026-05-03")
        assert c1.actor_id != c2.actor_id

    def test_different_dates_different_session_ids(self):
        c1 = build_memory_config("mem-123", "CUST-001", "2026-05-03")
        c2 = build_memory_config("mem-123", "CUST-001", "2026-05-04")
        assert c1.session_id != c2.session_id

    def test_session_id_format(self):
        config = build_memory_config("mem-123", "CUST-001", "2026-05-03")
        assert config.session_id == "CUST-001-2026-05-03"


# --- TestFollowUpInvariantGuards: existing paths unchanged ---


class TestFollowUpInvariantGuards:
    """Phase 15 changes do not regress recommendation or hardship paths."""

    def test_recommendation_path_default_action(self):
        """invoke() with no action defaults to recommendation path."""
        # This test verifies the action dispatcher doesn't break the default.
        # The actual recommendation will fail (no real Lambda), but the
        # dispatch logic should route to the recommendation path, not follow_up.
        result = invoke({"customer_id": "CUST-001"})
        # InMemoryProvider is installed by autouse fixture — should get a
        # recommendation response (kind=recommendation) or a fallback.
        assert result.get("kind") in ("recommendation", None) or "green" in result

    def test_hardship_path_unchanged(self):
        """invoke() for CUST-006 still returns hardship response."""
        result = invoke({"customer_id": "CUST-006"})
        assert result.get("kind") == "hardship"

    def test_follow_up_action_dispatches(self):
        """invoke() with action=follow_up dispatches to draft_follow_up."""
        import agent.agent as agent_mod
        original = agent_mod._MEMORY_ID
        try:
            agent_mod._MEMORY_ID = ""
            result = invoke({"customer_id": "CUST-001", "action": "follow_up"})
            assert result["kind"] == "follow_up"
        finally:
            agent_mod._MEMORY_ID = original

    def test_follow_up_body_no_savings_arithmetic(self):
        """Follow-up body contains no dollar figures (SAV-03 extension)."""
        import agent.agent as agent_mod
        original = agent_mod._MEMORY_ID
        try:
            agent_mod._MEMORY_ID = ""
            result = invoke({"customer_id": "CUST-001", "action": "follow_up"})
            body_text = result.get("body", "")
            assert not re.search(r'\$\d', body_text), "Follow-up body contains dollar figures"
            assert not re.search(r'\d+\.\d+', body_text), "Follow-up body contains decimal numbers"
        finally:
            agent_mod._MEMORY_ID = original
