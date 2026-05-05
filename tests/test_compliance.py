"""Tests for ComplianceReviewer hardship category extensions (Phase 16 AGENT-03).

CP-2: For any family_violence response with reasoning_trace, no tool outside
      {"schedule_callback"} passes the tool restriction check.

CP-3: For any family_violence response, concatenation of reason + call_script +
      str(permitted_actions) contains zero tokens from FINANCIAL_TERMS.

Unit tests: payment_difficulty tool restriction pass/fail scenarios.
"""
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from agent.specialists.compliance import ComplianceReviewer
from agent.specialists.hardship_config import HARDSHIP_CATEGORIES, FINANCIAL_TERMS


# --- Strategies ---

# Tools that are NOT in family_violence permitted set
_FAMILY_VIOLENCE_PERMITTED = HARDSHIP_CATEGORIES["family_violence"]["permitted_tools"]
_ALL_KNOWN_TOOLS = [
    "simulate_savings", "propose_payment_plan", "get_billing_history",
    "detect_bill_shock", "decompose_bill_shock", "lookup_concessions",
    "estimate_solar_payback", "schedule_callback",
]
_FORBIDDEN_TOOLS_FV = [t for t in _ALL_KNOWN_TOOLS if t not in _FAMILY_VIOLENCE_PERMITTED]

# Strategy for generating reasoning_trace entries
_tool_name_st = st.sampled_from(_ALL_KNOWN_TOOLS)
_trace_entry_st = st.fixed_dictionaries({"tool": _tool_name_st, "summary": st.text(min_size=1, max_size=50)})
_reasoning_trace_st = st.lists(_trace_entry_st, min_size=1, max_size=5)

# Strategy for safe (non-financial) text
_safe_words = st.sampled_from([
    "support", "safety", "care", "help", "team", "specialist",
    "connect", "priority", "immediate", "dedicated", "wellbeing",
    "confidential", "secure", "transfer", "callback",
])
_safe_text_st = st.lists(_safe_words, min_size=1, max_size=10).map(lambda words: " ".join(words))


class TestCP2ToolRestrictionEnforcement:
    """CP-2: For any family_violence response with reasoning_trace, no tool
    outside {"schedule_callback"} passes the tool restriction check.

    **Validates: Requirements 5.1**
    """

    @given(trace=_reasoning_trace_st)
    @settings(max_examples=100)
    def test_forbidden_tools_fail_family_violence(self, trace):
        """Any reasoning_trace with a tool outside {"schedule_callback"} fails."""
        # Ensure at least one forbidden tool is present
        tools_in_trace = {entry["tool"] for entry in trace}
        assume(not tools_in_trace.issubset(_FAMILY_VIOLENCE_PERMITTED))

        response = {
            "kind": "hardship",
            "category": "family_violence",
            "reasoning_trace": trace,
        }

        result = ComplianceReviewer._check_hardship_tool_restriction(response)
        assert result.verdict == "fail", (
            f"Expected fail for family_violence with tools {tools_in_trace}, "
            f"but got {result.verdict}: {result.reason}"
        )
        assert result.rule == "hardship_category_tool_restriction"

    @given(trace_size=st.integers(min_value=1, max_value=5))
    @settings(max_examples=50)
    def test_only_schedule_callback_passes_family_violence(self, trace_size):
        """reasoning_trace with ONLY schedule_callback passes for family_violence."""
        trace = [{"tool": "schedule_callback", "summary": "scheduled"} for _ in range(trace_size)]

        response = {
            "kind": "hardship",
            "category": "family_violence",
            "reasoning_trace": trace,
        }

        result = ComplianceReviewer._check_hardship_tool_restriction(response)
        assert result.verdict == "pass", (
            f"Expected pass for family_violence with only schedule_callback, "
            f"but got {result.verdict}: {result.reason}"
        )

    @given(trace=_reasoning_trace_st)
    @settings(max_examples=50)
    def test_empty_trace_passes(self, trace):
        """Empty reasoning_trace always passes (no violations possible)."""
        response = {
            "kind": "hardship",
            "category": "family_violence",
            "reasoning_trace": [],
        }

        result = ComplianceReviewer._check_hardship_tool_restriction(response)
        assert result.verdict == "pass"


class TestCP3FamilyViolenceFinancialIsolation:
    """CP-3: For any family_violence response, concatenation of reason +
    call_script + str(permitted_actions) contains zero tokens from FINANCIAL_TERMS.

    **Validates: Requirements 5.2**
    """

    @given(reason=_safe_text_st, call_script=_safe_text_st)
    @settings(max_examples=100)
    def test_safe_text_passes(self, reason, call_script):
        """Responses with no financial terms pass the check."""
        response = {
            "kind": "hardship",
            "category": "family_violence",
            "reason": reason,
            "call_script": call_script,
            "permitted_actions": ["schedule_callback"],
        }

        result = ComplianceReviewer._check_family_violence_no_financial(response)
        assert result.verdict == "pass", (
            f"Expected pass for safe text, but got {result.verdict}: {result.reason}"
        )

    @given(financial_term=st.sampled_from(sorted(FINANCIAL_TERMS)))
    @settings(max_examples=50)
    def test_financial_term_in_reason_fails(self, financial_term):
        """Any financial term in reason causes failure."""
        response = {
            "kind": "hardship",
            "category": "family_violence",
            "reason": f"We will discuss your {financial_term} situation",
            "call_script": "Safety is our priority",
            "permitted_actions": ["schedule_callback"],
        }

        result = ComplianceReviewer._check_family_violence_no_financial(response)
        assert result.verdict == "fail", (
            f"Expected fail for financial term '{financial_term}' in reason, "
            f"but got {result.verdict}"
        )
        assert financial_term in result.reason

    @given(financial_term=st.sampled_from(sorted(FINANCIAL_TERMS)))
    @settings(max_examples=50)
    def test_financial_term_in_call_script_fails(self, financial_term):
        """Any financial term in call_script causes failure."""
        response = {
            "kind": "hardship",
            "category": "family_violence",
            "reason": "Safety is our priority",
            "call_script": f"Let me check your {financial_term} details",
            "permitted_actions": ["schedule_callback"],
        }

        result = ComplianceReviewer._check_family_violence_no_financial(response)
        assert result.verdict == "fail", (
            f"Expected fail for financial term '{financial_term}' in call_script, "
            f"but got {result.verdict}"
        )

    @given(financial_term=st.sampled_from(sorted(FINANCIAL_TERMS)))
    @settings(max_examples=50)
    def test_financial_term_in_permitted_actions_fails(self, financial_term):
        """Any financial term in permitted_actions causes failure."""
        response = {
            "kind": "hardship",
            "category": "family_violence",
            "reason": "Safety is our priority",
            "call_script": "Connecting you to support",
            "permitted_actions": [financial_term],
        }

        result = ComplianceReviewer._check_family_violence_no_financial(response)
        assert result.verdict == "fail", (
            f"Expected fail for financial term '{financial_term}' in permitted_actions, "
            f"but got {result.verdict}"
        )


class TestPaymentDifficultyToolRestriction:
    """Unit tests: payment_difficulty tool restriction pass/fail scenarios.

    **Validates: Requirements 5.1**
    """

    def test_propose_payment_plan_passes(self):
        """payment_difficulty response with propose_payment_plan in reasoning_trace passes."""
        response = {
            "kind": "hardship",
            "category": "payment_difficulty",
            "reasoning_trace": [
                {"tool": "propose_payment_plan", "summary": "proposed a plan"},
            ],
        }

        result = ComplianceReviewer._check_hardship_tool_restriction(response)
        assert result.verdict == "pass", (
            f"Expected pass for payment_difficulty with propose_payment_plan, "
            f"but got {result.verdict}: {result.reason}"
        )
        assert result.rule == "hardship_category_tool_restriction"

    def test_simulate_savings_fails(self):
        """payment_difficulty response with simulate_savings in reasoning_trace fails."""
        response = {
            "kind": "hardship",
            "category": "payment_difficulty",
            "reasoning_trace": [
                {"tool": "simulate_savings", "summary": "simulated savings"},
            ],
        }

        result = ComplianceReviewer._check_hardship_tool_restriction(response)
        assert result.verdict == "fail", (
            f"Expected fail for payment_difficulty with simulate_savings, "
            f"but got {result.verdict}: {result.reason}"
        )
        assert result.rule == "hardship_category_tool_restriction"
        assert "simulate_savings" in result.reason


class TestReviewMethodIntegration:
    """Integration tests for the review() method with new hardship checks."""

    def test_hardship_review_includes_new_rules(self):
        """review() includes tool restriction rule for hardship responses."""
        reviewer = ComplianceReviewer()
        response = {
            "kind": "hardship",
            "category": "payment_difficulty",
            "reasoning_trace": [
                {"tool": "propose_payment_plan", "summary": "proposed"},
            ],
        }

        review = reviewer.review(response, {})
        assert "hardship_no_tariff_data" in review.rules_checked
        assert "hardship_category_tool_restriction" in review.rules_checked

    def test_family_violence_review_includes_financial_check(self):
        """review() includes financial content check for family_violence."""
        reviewer = ComplianceReviewer()
        response = {
            "kind": "hardship",
            "category": "family_violence",
            "reason": "Safety is our priority",
            "call_script": "Connecting you to support",
            "permitted_actions": ["schedule_callback"],
            "reasoning_trace": [
                {"tool": "schedule_callback", "summary": "scheduled"},
            ],
        }

        review = reviewer.review(response, {})
        assert "hardship_no_tariff_data" in review.rules_checked
        assert "hardship_category_tool_restriction" in review.rules_checked
        assert "family_violence_no_financial_content" in review.rules_checked
        assert review.verdict == "pass"

    def test_family_violence_with_violations_fails(self):
        """review() fails when family_violence has tool violations."""
        reviewer = ComplianceReviewer()
        response = {
            "kind": "hardship",
            "category": "family_violence",
            "reason": "Safety is our priority",
            "call_script": "Connecting you to support",
            "permitted_actions": ["schedule_callback"],
            "reasoning_trace": [
                {"tool": "get_billing_history", "summary": "checked billing"},
            ],
        }

        review = reviewer.review(response, {})
        assert review.verdict == "fail"
        assert any("get_billing_history" in f for f in review.failures)
