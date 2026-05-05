"""Property-based tests for typed hardship categories (Phase 16 AGENT-03).

CP-1: For any valid HardshipCategory, _build_typed_hardship_response produces
      a response that passes Pydantic validation and D-15 content rules.

CP-5: routing_target is a pure function of category — same category always
      produces same routing_target regardless of customer_id.
"""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agent.agent import (
    HardshipResponse,
    _build_typed_hardship_response,
    HARDSHIP_CATEGORIES,
)
from agent.narrative.validators import _reject_forbidden, USAGE_NARRATIVE_MAX_WORDS, CALL_SCRIPT_MAX_WORDS
from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX


# --- Strategies ---

# All valid hardship categories
_CATEGORIES = st.sampled_from(["payment_difficulty", "medical_equipment", "family_violence", "other"])

# Customer IDs that have hardship fallback entries (typed + legacy)
_HARDSHIP_CUSTOMER_IDS = st.sampled_from(["CUST-006", "CUST-007", "CUST-008", "CUST-009", "CUST-010"])


class TestCP1CategoryCompleteness:
    """CP-1: For any valid HardshipCategory, _build_typed_hardship_response
    produces a valid HardshipResponse that passes Pydantic validation and
    D-15 content rules.

    **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
    """

    @given(category=_CATEGORIES, customer_id=_HARDSHIP_CUSTOMER_IDS)
    @settings(max_examples=50)
    def test_response_passes_pydantic_validation(self, category, customer_id):
        """Every category × customer_id combination produces a valid HardshipResponse."""
        config = HARDSHIP_CATEGORIES[category]
        result = _build_typed_hardship_response(customer_id, category, config)

        # Must be a dict (model_dump output)
        assert isinstance(result, dict)

        # Must pass full Pydantic validation (including D-15 field validators)
        response = HardshipResponse(**result)
        assert response.kind == "hardship"
        assert response.customer_id == customer_id
        assert response.category == category

    @given(category=_CATEGORIES, customer_id=_HARDSHIP_CUSTOMER_IDS)
    @settings(max_examples=50)
    def test_response_reason_passes_d15(self, category, customer_id):
        """reason field passes D-15 content rules (no digits, currency, banned terms)."""
        config = HARDSHIP_CATEGORIES[category]
        result = _build_typed_hardship_response(customer_id, category, config)

        reason = result["reason"]
        # No digits or currency symbols
        assert not NUMERIC_REGEX.search(reason), f"Digits/currency in reason: {reason!r}"
        # No banned terms
        assert not BANNED_REGEX.search(reason), f"Banned term in reason: {reason!r}"
        # Within word cap
        assert len(reason.split()) <= USAGE_NARRATIVE_MAX_WORDS

    @given(category=_CATEGORIES, customer_id=_HARDSHIP_CUSTOMER_IDS)
    @settings(max_examples=50)
    def test_response_call_script_passes_d15(self, category, customer_id):
        """call_script field passes D-15 content rules."""
        config = HARDSHIP_CATEGORIES[category]
        result = _build_typed_hardship_response(customer_id, category, config)

        call_script = result["call_script"]
        # No digits or currency symbols
        assert not NUMERIC_REGEX.search(call_script), f"Digits/currency in call_script: {call_script!r}"
        # No banned terms
        assert not BANNED_REGEX.search(call_script), f"Banned term in call_script: {call_script!r}"
        # Within word cap
        assert len(call_script.split()) <= CALL_SCRIPT_MAX_WORDS

    @given(category=_CATEGORIES, customer_id=_HARDSHIP_CUSTOMER_IDS)
    @settings(max_examples=50)
    def test_response_has_required_fields(self, category, customer_id):
        """Response dict contains all required HardshipResponse fields."""
        config = HARDSHIP_CATEGORIES[category]
        result = _build_typed_hardship_response(customer_id, category, config)

        required_fields = {"kind", "customer_id", "category", "reason", "routing_target", "call_script", "permitted_actions"}
        assert required_fields.issubset(result.keys())
        assert isinstance(result["permitted_actions"], list)


class TestCP5RoutingTargetDeterminism:
    """CP-5: routing_target is a pure function of category — same category
    always produces same routing_target regardless of customer_id.

    **Validates: Requirements 4.2**
    """

    @given(
        category=_CATEGORIES,
        customer_id_a=_HARDSHIP_CUSTOMER_IDS,
        customer_id_b=_HARDSHIP_CUSTOMER_IDS,
    )
    @settings(max_examples=100)
    def test_same_category_same_routing_target(self, category, customer_id_a, customer_id_b):
        """Same category always produces same routing_target regardless of customer_id."""
        config = HARDSHIP_CATEGORIES[category]
        result_a = _build_typed_hardship_response(customer_id_a, category, config)
        result_b = _build_typed_hardship_response(customer_id_b, category, config)

        assert result_a["routing_target"] == result_b["routing_target"], (
            f"routing_target differs for category={category!r}: "
            f"{customer_id_a}→{result_a['routing_target']}, "
            f"{customer_id_b}→{result_b['routing_target']}"
        )

    @given(category=_CATEGORIES, customer_id=_HARDSHIP_CUSTOMER_IDS)
    @settings(max_examples=50)
    def test_routing_target_matches_config(self, category, customer_id):
        """routing_target always matches the value from HARDSHIP_CATEGORIES config."""
        config = HARDSHIP_CATEGORIES[category]
        result = _build_typed_hardship_response(customer_id, category, config)

        expected_target = config["routing_target"]
        assert result["routing_target"] == expected_target, (
            f"routing_target={result['routing_target']!r} != config={expected_target!r} "
            f"for category={category!r}, customer_id={customer_id!r}"
        )
