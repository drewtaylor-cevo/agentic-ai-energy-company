"""Unit tests for the Supervisor dispatcher (refactored invoke()).

Tests the routing logic in agent/agent.py::invoke() after the multi-agent
supervisor refactor. All specialists and providers are mocked — these tests
verify the Supervisor's dispatch, compliance review integration, supervisor
trace attachment, and DEMO-07 kill-switch behaviour.

Task 5.6 test matrix:
  - recommend action → TariffSpecialist.handle() called
  - follow_up action → draft_follow_up() called
  - hardship flag true → HardshipSpecialist.handle() called
  - missing customer_id → error dict returned
  - compliance review pass → compliance_review attached
  - compliance review fail → compliance_review with fail verdict attached (not blocked)
  - compliance reviewer exception → response returned unchanged
  - narrative=off → compliance_review and supervisor_trace stripped
  - hardship check failure → falls back to TariffSpecialist
"""
from unittest.mock import MagicMock, patch

import pytest

import agent.agent as agent_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _skip_specialist_init(mocker):
    """Prevent _init_specialists() from overwriting mocked specialists.

    Sets the _specialists_initialized flag to True so the lazy-init
    function is a no-op. Each test that needs specialists patches them
    explicitly via mocker.patch.object.
    """
    mocker.patch.object(agent_mod, "_specialists_initialized", True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tariff_response():
    """Minimal TariffSpecialist response dict for testing."""
    return {
        "kind": "recommendation",
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 30.00,
            "saving_annual": 360.00,
            "usage_narrative": "Winter-heavy household with consistent usage.",
            "call_script": "Ask about EcoFlex for your winter-heating profile.",
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 55.00,
            "saving_annual": 660.00,
            "usage_narrative": "Consistently high household consumption.",
            "call_script": "Bring up Value Twelve for a budget-first pick.",
        },
        "reasoning_trace": [
            {"tool": "simulate_savings", "summary": "Green ECO $30/mo, Cheapest VAL $55/mo"},
        ],
        "_narrative_source": {
            "green": {"usage_narrative": "model", "call_script": "model"},
            "cheapest": {"usage_narrative": "model", "call_script": "model"},
        },
    }


def _make_hardship_response():
    """Minimal HardshipSpecialist response dict for testing."""
    return {
        "kind": "hardship",
        "customer_id": "CUST-006",
        "reason": "This customer account is flagged for dedicated support from our specialist team.",
        "routing_target": "hardship_team",
        "call_script": "Let me connect you with our specialist support team who can best help with your account.",
        "_narrative_source": {
            "hardship": {"reason": "fallback", "call_script": "fallback"},
        },
    }


def _make_compliance_review_mock(verdict="pass", failures=None, rules=None):
    """Create a mock ComplianceReview object."""
    mock_review = MagicMock()
    mock_review.verdict = verdict
    mock_review.failures = failures or []
    mock_review.model_dump.return_value = {
        "verdict": verdict,
        "rules_checked": rules or [],
        "failures": failures or [],
        "reviewed_at": "2025-01-15T10:30:00+00:00",
    }
    return mock_review


# ---------------------------------------------------------------------------
# Req 1.5: Missing customer_id returns error
# ---------------------------------------------------------------------------


class TestMissingCustomerId:
    """Supervisor returns error dict when customer_id is missing."""

    def test_empty_customer_id_returns_error(self):
        """Empty string customer_id → error dict."""
        result = agent_mod.invoke({"customer_id": ""})
        assert "error" in result
        assert "customer_id" in result["error"]

    def test_missing_customer_id_key_returns_error(self):
        """No customer_id key at all → error dict."""
        result = agent_mod.invoke({})
        assert "error" in result
        assert "customer_id" in result["error"]


# ---------------------------------------------------------------------------
# Req 1.1: recommend action → TariffSpecialist
# ---------------------------------------------------------------------------


class TestRecommendRouting:
    """Supervisor dispatches recommend action to TariffSpecialist."""

    def test_recommend_dispatches_to_tariff_specialist(self, mocker):
        """Default action dispatches to TariffSpecialist.handle()."""
        mock_provider = MagicMock()
        mock_provider.get_hardship_flag.return_value = {"hardship": False}
        mocker.patch.object(agent_mod, "get_provider", return_value=mock_provider)

        mock_tariff = MagicMock()
        mock_tariff.handle.return_value = _make_tariff_response()
        mocker.patch.object(agent_mod, "_tariff_specialist", mock_tariff)

        mock_compliance = MagicMock()
        mock_compliance.review.return_value = _make_compliance_review_mock()
        mocker.patch.object(agent_mod, "_compliance_reviewer", mock_compliance)

        result = agent_mod.invoke({"customer_id": "CUST-001"})

        mock_tariff.handle.assert_called_once_with({"customer_id": "CUST-001"})
        assert result["supervisor_trace"]["routed_to"] == "TariffSpecialist"

    def test_explicit_recommend_action(self, mocker):
        """Explicit action='recommend' dispatches to TariffSpecialist."""
        mock_provider = MagicMock()
        mock_provider.get_hardship_flag.return_value = {"hardship": False}
        mocker.patch.object(agent_mod, "get_provider", return_value=mock_provider)

        mock_tariff = MagicMock()
        mock_tariff.handle.return_value = _make_tariff_response()
        mocker.patch.object(agent_mod, "_tariff_specialist", mock_tariff)

        mock_compliance = MagicMock()
        mock_compliance.review.return_value = _make_compliance_review_mock()
        mocker.patch.object(agent_mod, "_compliance_reviewer", mock_compliance)

        result = agent_mod.invoke({"customer_id": "CUST-001", "action": "recommend"})

        mock_tariff.handle.assert_called_once()
        assert "supervisor_trace" in result


# ---------------------------------------------------------------------------
# Req 1.2: follow_up action → draft_follow_up
# ---------------------------------------------------------------------------


class TestFollowUpRouting:
    """Supervisor dispatches follow_up action to draft_follow_up."""

    def test_follow_up_dispatches_to_draft_follow_up(self, mocker):
        """action='follow_up' dispatches to draft_follow_up()."""
        mock_draft = mocker.patch.object(agent_mod, "draft_follow_up", return_value={
            "kind": "follow_up",
            "customer_id": "CUST-001",
            "subject": "Your tariff options",
            "body": "Thank you for speaking with us.",
            "plan_reference": "EcoFlex Green",
        })

        result = agent_mod.invoke({"customer_id": "CUST-001", "action": "follow_up"})

        mock_draft.assert_called_once_with({"customer_id": "CUST-001", "action": "follow_up"})
        assert result["kind"] == "follow_up"
        # follow_up path does NOT go through supervisor routing
        assert "supervisor_trace" not in result


# ---------------------------------------------------------------------------
# Req 2.2: hardship flag true → HardshipSpecialist
# ---------------------------------------------------------------------------


class TestHardshipRouting:
    """Supervisor routes hardship-flagged customers to HardshipSpecialist."""

    def test_hardship_true_routes_to_hardship_specialist(self, mocker):
        """Hardship flag true → HardshipSpecialist.handle() called."""
        mock_provider = MagicMock()
        mock_provider.get_hardship_flag.return_value = {"hardship": True}
        mocker.patch.object(agent_mod, "get_provider", return_value=mock_provider)

        mock_hardship = MagicMock()
        mock_hardship.handle.return_value = _make_hardship_response()
        mocker.patch.object(agent_mod, "_hardship_specialist", mock_hardship)

        mock_compliance = MagicMock()
        mock_compliance.review.return_value = _make_compliance_review_mock(
            rules=["hardship_no_tariff_data"]
        )
        mocker.patch.object(agent_mod, "_compliance_reviewer", mock_compliance)

        result = agent_mod.invoke({"customer_id": "CUST-006"})

        mock_hardship.handle.assert_called_once_with({"customer_id": "CUST-006", "hardship_category": None})
        assert result["supervisor_trace"]["routed_to"] == "HardshipSpecialist"
        assert result["supervisor_trace"]["hardship_checked"] is True


# ---------------------------------------------------------------------------
# Req 2.5: hardship check failure → falls back to TariffSpecialist
# ---------------------------------------------------------------------------


class TestHardshipCheckFailure:
    """Supervisor falls back to TariffSpecialist when hardship check fails."""

    def test_hardship_check_exception_falls_back_to_tariff(self, mocker):
        """Hardship check exception → TariffSpecialist (D-04 never-500)."""
        mock_provider = MagicMock()
        mock_provider.get_hardship_flag.side_effect = RuntimeError("provider down")
        mocker.patch.object(agent_mod, "get_provider", return_value=mock_provider)

        mock_tariff = MagicMock()
        mock_tariff.handle.return_value = _make_tariff_response()
        mocker.patch.object(agent_mod, "_tariff_specialist", mock_tariff)

        mock_compliance = MagicMock()
        mock_compliance.review.return_value = _make_compliance_review_mock()
        mocker.patch.object(agent_mod, "_compliance_reviewer", mock_compliance)

        result = agent_mod.invoke({"customer_id": "CUST-001"})

        mock_tariff.handle.assert_called_once()
        assert result["supervisor_trace"]["routed_to"] == "TariffSpecialist"
        assert result["supervisor_trace"]["hardship_checked"] is False


# ---------------------------------------------------------------------------
# Req 1.3, 8.1: compliance review pass → compliance_review attached
# ---------------------------------------------------------------------------


class TestComplianceReviewPass:
    """Supervisor attaches compliance_review on pass verdict."""

    def test_compliance_pass_attached(self, mocker):
        """Compliance pass → compliance_review field present with pass verdict."""
        mock_provider = MagicMock()
        mock_provider.get_hardship_flag.return_value = {"hardship": False}
        mocker.patch.object(agent_mod, "get_provider", return_value=mock_provider)

        mock_tariff = MagicMock()
        mock_tariff.handle.return_value = _make_tariff_response()
        mocker.patch.object(agent_mod, "_tariff_specialist", mock_tariff)

        mock_compliance = MagicMock()
        mock_compliance.review.return_value = _make_compliance_review_mock(
            verdict="pass",
            rules=["reference_period_disclosure", "no_upsell_to_disadvantage"],
        )
        mocker.patch.object(agent_mod, "_compliance_reviewer", mock_compliance)

        result = agent_mod.invoke({"customer_id": "CUST-001"})

        assert "compliance_review" in result
        assert result["compliance_review"]["verdict"] == "pass"
        assert result["supervisor_trace"]["compliance_reviewed"] is True


# ---------------------------------------------------------------------------
# Req 4.5: compliance review fail → warning attached, not blocked
# ---------------------------------------------------------------------------


class TestComplianceReviewFail:
    """Supervisor attaches compliance_review on fail verdict (not blocked)."""

    def test_compliance_fail_attaches_warning_not_blocks(self, mocker):
        """Compliance fail → response still returned with fail verdict attached."""
        mock_provider = MagicMock()
        mock_provider.get_hardship_flag.return_value = {"hardship": False}
        mocker.patch.object(agent_mod, "get_provider", return_value=mock_provider)

        mock_tariff = MagicMock()
        mock_tariff.handle.return_value = _make_tariff_response()
        mocker.patch.object(agent_mod, "_tariff_specialist", mock_tariff)

        mock_compliance = MagicMock()
        mock_compliance.review.return_value = _make_compliance_review_mock(
            verdict="fail",
            failures=["negative saving_monthly on green track(s)"],
            rules=["no_upsell_to_disadvantage"],
        )
        mocker.patch.object(agent_mod, "_compliance_reviewer", mock_compliance)

        result = agent_mod.invoke({"customer_id": "CUST-001"})

        # Response is NOT blocked — still has green/cheapest
        assert "green" in result
        assert "cheapest" in result
        # Compliance fail verdict is attached
        assert result["compliance_review"]["verdict"] == "fail"
        assert len(result["compliance_review"]["failures"]) > 0
        assert result["supervisor_trace"]["compliance_reviewed"] is True


# ---------------------------------------------------------------------------
# Req 4.6: compliance reviewer exception → response returned unchanged
# ---------------------------------------------------------------------------


class TestComplianceReviewerException:
    """Supervisor returns response unchanged when ComplianceReviewer raises."""

    def test_compliance_exception_returns_response_unchanged(self, mocker):
        """ComplianceReviewer exception → response returned without compliance_review."""
        mock_provider = MagicMock()
        mock_provider.get_hardship_flag.return_value = {"hardship": False}
        mocker.patch.object(agent_mod, "get_provider", return_value=mock_provider)

        mock_tariff = MagicMock()
        mock_tariff.handle.return_value = _make_tariff_response()
        mocker.patch.object(agent_mod, "_tariff_specialist", mock_tariff)

        mock_compliance = MagicMock()
        mock_compliance.review.side_effect = RuntimeError("reviewer crashed")
        mocker.patch.object(agent_mod, "_compliance_reviewer", mock_compliance)

        result = agent_mod.invoke({"customer_id": "CUST-001"})

        # Response is returned — D-04 never-500
        assert "green" in result
        assert "cheapest" in result
        # compliance_review NOT attached (reviewer raised)
        assert "compliance_review" not in result
        # supervisor_trace still attached but compliance_reviewed is False
        assert result["supervisor_trace"]["compliance_reviewed"] is False


# ---------------------------------------------------------------------------
# Req 9.4: narrative=off strips compliance_review and supervisor_trace
# ---------------------------------------------------------------------------


class TestNarrativeOffKillSwitch:
    """DEMO-07 kill-switch strips post-v2.0 surfaces."""

    def test_narrative_off_strips_new_fields(self, mocker):
        """narrative=off → compliance_review and supervisor_trace stripped."""
        mock_provider = MagicMock()
        mock_provider.get_hardship_flag.return_value = {"hardship": False}
        mocker.patch.object(agent_mod, "get_provider", return_value=mock_provider)

        mock_tariff = MagicMock()
        mock_tariff.handle.return_value = _make_tariff_response()
        mocker.patch.object(agent_mod, "_tariff_specialist", mock_tariff)

        mock_compliance = MagicMock()
        mock_compliance.review.return_value = _make_compliance_review_mock()
        mocker.patch.object(agent_mod, "_compliance_reviewer", mock_compliance)

        result = agent_mod.invoke({"customer_id": "CUST-001", "narrative": "off"})

        # Both fields stripped
        assert "compliance_review" not in result
        assert "supervisor_trace" not in result
        # Core response still present
        assert "green" in result
        assert "cheapest" in result


# ---------------------------------------------------------------------------
# Req 1.4: hardship response goes through compliance review
# ---------------------------------------------------------------------------


class TestHardshipComplianceIntegration:
    """Supervisor submits hardship responses to ComplianceReviewer."""

    def test_hardship_response_goes_through_compliance(self, mocker):
        """Hardship response is submitted to ComplianceReviewer.review()."""
        mock_provider = MagicMock()
        mock_provider.get_hardship_flag.return_value = {"hardship": True}
        mocker.patch.object(agent_mod, "get_provider", return_value=mock_provider)

        hardship_resp = _make_hardship_response()
        mock_hardship = MagicMock()
        mock_hardship.handle.return_value = hardship_resp
        mocker.patch.object(agent_mod, "_hardship_specialist", mock_hardship)

        mock_compliance = MagicMock()
        mock_compliance.review.return_value = _make_compliance_review_mock(
            rules=["hardship_no_tariff_data"]
        )
        mocker.patch.object(agent_mod, "_compliance_reviewer", mock_compliance)

        result = agent_mod.invoke({"customer_id": "CUST-006"})

        # ComplianceReviewer.review() was called with the hardship response
        mock_compliance.review.assert_called_once()
        call_args = mock_compliance.review.call_args
        assert call_args[0][0] is hardship_resp  # first positional arg is the response
        assert "compliance_review" in result
        assert result["supervisor_trace"]["compliance_reviewed"] is True
