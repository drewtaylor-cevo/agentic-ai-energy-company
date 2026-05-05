"""Property-based tests for the Expanded Tool Gallery.

Feature: expanded-tool-gallery

Uses Hypothesis for property-based testing with minimum 100 iterations per
property. Each test is tagged with the feature and property reference from
the design document.

Properties tested:
  - Property 1: Bill Shock Decomposition Sum Invariant
  - Property 2: Bill Shock Backward Compatibility
  - Property 3: Solar Payback Arithmetic
  - Property 4: Solar Recommendation Threshold Classification
  - Property 5: Payment Plan Conservation of Money
  - Property 6: Payment Plan Schedule Structure
  - Property 7: Callback Deterministic ID
  - Property 8: Tool Cap Budget Enforcement
  - Property 9: Invalid Input Error Handling
"""
from __future__ import annotations

import importlib
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from hypothesis import given, settings, assume
from hypothesis import strategies as st

# `from lambda.handler import ...` is a SyntaxError (lambda = Python keyword).
# Use importlib fallback as documented in project conventions.
_handler = importlib.import_module("lambda.handler")
check_outage_status_pure = _handler.check_outage_status_pure
decompose_bill_shock_pure = _handler.decompose_bill_shock_pure
detect_bill_shock_pure = _handler.detect_bill_shock_pure
estimate_solar_payback_pure = _handler.estimate_solar_payback_pure
lookup_concessions_pure = _handler.lookup_concessions_pure
propose_payment_plan_pure = _handler.propose_payment_plan_pure
schedule_callback_pure = _handler.schedule_callback_pure

from agent.hooks.four_tool_cap import FourToolCapHook


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy: valid billing history records (2-12 months, usage 50-1000 kWh)
_billing_record = st.fixed_dictionaries({
    "month": st.from_regex(r"2025-(0[1-9]|1[0-2])", fullmatch=True),
    "usage_kwh": st.floats(min_value=50, max_value=1000, allow_nan=False, allow_infinity=False),
    "customer_id": st.just("CUST-001"),
    "plan_id": st.just("STD"),
})

_billing_history = st.lists(
    _billing_record,
    min_size=2,
    max_size=12,
    unique_by=lambda r: r["month"],
)

# Strategy: billing history for solar-eligible customers (no export_kwh)
_solar_eligible_billing = st.lists(
    st.fixed_dictionaries({
        "month": st.from_regex(r"2025-(0[1-9]|1[0-2])", fullmatch=True),
        "usage_kwh": st.floats(min_value=100, max_value=1000, allow_nan=False, allow_infinity=False),
        "customer_id": st.just("CUST-001"),
        "plan_id": st.just("STD"),
    }),
    min_size=2,
    max_size=12,
    unique_by=lambda r: r["month"],
)

# Strategy: valid customer IDs that are NOT in SOLAR_CUSTOMERS and NOT CUST-004
_solar_eligible_customer_id = st.sampled_from(["CUST-001", "CUST-002", "CUST-003", "CUST-005", "CUST-006"])

# Strategy: valid ISO datetime strings (using builds to avoid Unicode digit issues)
_valid_iso_datetime = st.builds(
    lambda y, mo, d, h, mi, s: f"2025-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}",
    y=st.just(2025),
    mo=st.integers(min_value=1, max_value=12),
    d=st.integers(min_value=1, max_value=28),
    h=st.integers(min_value=0, max_value=23),
    mi=st.integers(min_value=0, max_value=59),
    s=st.integers(min_value=0, max_value=59),
)

# Strategy: non-empty reason strings
_valid_reason = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip() != "")

# Strategy: valid customer IDs
_valid_customer_id = st.from_regex(r"CUST-\d{3,6}", fullmatch=True)


# ---------------------------------------------------------------------------
# Property 1: Bill Shock Decomposition Sum Invariant
# Feature: expanded-tool-gallery, Property 1: Bill Shock Decomposition Sum Invariant
# **Validates: Requirements 2.2, 2.6**
# ---------------------------------------------------------------------------


class TestBillShockDecompositionSum:
    """Property 1: Bill Shock Decomposition Sum Invariant.

    *For any* valid billing history with at least 2 months, when
    decompose_bill_shock_pure is invoked, the sum
    rate_change_component + usage_change_component + seasonal_component
    SHALL equal total_delta_dollars within a tolerance of $0.01.

    **Validates: Requirements 2.2, 2.6**
    """

    @settings(max_examples=100)
    @given(billing_history=_billing_history)
    def test_bill_shock_decomposition_sum(self, billing_history):
        # Feature: expanded-tool-gallery, Property 1: Bill Shock Decomposition Sum Invariant
        # **Validates: Requirements 2.2, 2.6**
        result = decompose_bill_shock_pure(billing_history)
        total = result["total_delta_dollars"]
        component_sum = (
            result["rate_change_component"]
            + result["usage_change_component"]
            + result["seasonal_component"]
        )
        assert abs(total - component_sum) <= 0.01, (
            f"Decomposition sum mismatch: total={total}, "
            f"components={result['rate_change_component']} + "
            f"{result['usage_change_component']} + "
            f"{result['seasonal_component']} = {component_sum}"
        )


# ---------------------------------------------------------------------------
# Property 2: Bill Shock Backward Compatibility
# Feature: expanded-tool-gallery, Property 2: Bill Shock Backward Compatibility
# **Validates: Requirements 2.5**
# ---------------------------------------------------------------------------


class TestBillShockBackwardCompat:
    """Property 2: Bill Shock Backward Compatibility.

    *For any* valid billing history, the is_shock and shock_month fields
    returned by decompose_bill_shock_pure SHALL match the corresponding
    fields returned by the existing detect_bill_shock_pure function.

    **Validates: Requirements 2.5**
    """

    @settings(max_examples=100)
    @given(billing_history=_billing_history)
    def test_bill_shock_backward_compat(self, billing_history):
        # Feature: expanded-tool-gallery, Property 2: Bill Shock Backward Compatibility
        # **Validates: Requirements 2.5**
        decomposed = decompose_bill_shock_pure(billing_history)
        legacy = detect_bill_shock_pure(billing_history)

        assert decomposed["is_shock"] == legacy["is_shock"], (
            f"is_shock mismatch: decomposed={decomposed['is_shock']}, "
            f"legacy={legacy['is_shock']}"
        )
        assert decomposed["shock_month"] == legacy["shock_month"], (
            f"shock_month mismatch: decomposed={decomposed['shock_month']}, "
            f"legacy={legacy['shock_month']}"
        )


# ---------------------------------------------------------------------------
# Property 3: Solar Payback Arithmetic
# Feature: expanded-tool-gallery, Property 3: Solar Payback Arithmetic
# **Validates: Requirements 4.3, 4.6**
# ---------------------------------------------------------------------------


class TestSolarPaybackArithmetic:
    """Property 3: Solar Payback Arithmetic.

    *For any* customer where estimate_solar_payback_pure returns eligible: true,
    the payback_years field SHALL equal round(system_cost_dollars / annual_savings_dollars, 1).

    **Validates: Requirements 4.3, 4.6**
    """

    @settings(max_examples=100)
    @given(
        customer_id=_solar_eligible_customer_id,
        billing_history=_solar_eligible_billing,
    )
    def test_solar_payback_arithmetic(self, customer_id, billing_history):
        # Feature: expanded-tool-gallery, Property 3: Solar Payback Arithmetic
        # **Validates: Requirements 4.3, 4.6**
        result = estimate_solar_payback_pure(customer_id, billing_history)

        # Only check eligible customers
        assume(result.get("eligible") is True)

        expected_payback = round(
            result["system_cost_dollars"] / result["annual_savings_dollars"], 1
        )
        assert result["payback_years"] == expected_payback, (
            f"Payback mismatch: got {result['payback_years']}, "
            f"expected round({result['system_cost_dollars']} / "
            f"{result['annual_savings_dollars']}, 1) = {expected_payback}"
        )


# ---------------------------------------------------------------------------
# Property 4: Solar Recommendation Threshold Classification
# Feature: expanded-tool-gallery, Property 4: Solar Recommendation Threshold Classification
# **Validates: Requirements 4.4**
# ---------------------------------------------------------------------------


class TestSolarRecommendationThreshold:
    """Property 4: Solar Recommendation Threshold Classification.

    *For any* customer where estimate_solar_payback_pure returns eligible: true,
    the recommendation field SHALL be:
      - "strong_candidate" when payback_years <= 5.0
      - "moderate_candidate" when 5.0 < payback_years <= 8.0
      - "not_recommended" when payback_years > 8.0

    **Validates: Requirements 4.4**
    """

    @settings(max_examples=100)
    @given(
        customer_id=_solar_eligible_customer_id,
        billing_history=_solar_eligible_billing,
    )
    def test_solar_recommendation_threshold(self, customer_id, billing_history):
        # Feature: expanded-tool-gallery, Property 4: Solar Recommendation Threshold Classification
        # **Validates: Requirements 4.4**
        result = estimate_solar_payback_pure(customer_id, billing_history)

        # Only check eligible customers
        assume(result.get("eligible") is True)

        payback = result["payback_years"]
        recommendation = result["recommendation"]

        if payback <= 5.0:
            expected = "strong_candidate"
        elif payback <= 8.0:
            expected = "moderate_candidate"
        else:
            expected = "not_recommended"

        assert recommendation == expected, (
            f"Recommendation mismatch for payback_years={payback}: "
            f"got '{recommendation}', expected '{expected}'"
        )


# ---------------------------------------------------------------------------
# Property 5: Payment Plan Conservation of Money
# Feature: expanded-tool-gallery, Property 5: Payment Plan Conservation of Money
# **Validates: Requirements 5.6**
# ---------------------------------------------------------------------------


class TestPaymentPlanConservation:
    """Property 5: Payment Plan Conservation of Money.

    *For any* valid payment plan (balance 1-10000, instalments 2-12),
    the sum of all schedule[].amount values SHALL equal outstanding_balance
    exactly (zero tolerance — no money created or destroyed).

    **Validates: Requirements 5.6**
    """

    @settings(max_examples=100)
    @given(
        balance=st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        instalments=st.integers(min_value=2, max_value=12),
    )
    def test_payment_plan_conservation(self, balance, instalments):
        # Feature: expanded-tool-gallery, Property 5: Payment Plan Conservation of Money
        # **Validates: Requirements 5.6**
        balance = round(balance, 2)  # Ensure 2 decimal places
        result = propose_payment_plan_pure("CUST-006", instalments, balance)
        schedule_sum = round(sum(entry["amount"] for entry in result["schedule"]), 2)
        assert schedule_sum == balance, (
            f"Conservation violated: sum(schedule)={schedule_sum}, "
            f"balance={balance}, diff={schedule_sum - balance}"
        )


# ---------------------------------------------------------------------------
# Property 6: Payment Plan Schedule Structure
# Feature: expanded-tool-gallery, Property 6: Payment Plan Schedule Structure
# **Validates: Requirements 5.1, 5.3, 5.4**
# ---------------------------------------------------------------------------


class TestPaymentPlanStructure:
    """Property 6: Payment Plan Schedule Structure.

    *For any* valid payment plan request with instalment_count N, the response
    SHALL contain exactly N schedule entries, interest_free SHALL be true,
    and schedule dates SHALL be spaced exactly one month apart.

    **Validates: Requirements 5.1, 5.3, 5.4**
    """

    @settings(max_examples=100)
    @given(
        balance=st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        instalments=st.integers(min_value=2, max_value=12),
    )
    def test_payment_plan_structure(self, balance, instalments):
        # Feature: expanded-tool-gallery, Property 6: Payment Plan Schedule Structure
        # **Validates: Requirements 5.1, 5.3, 5.4**
        balance = round(balance, 2)
        result = propose_payment_plan_pure("CUST-006", instalments, balance)

        # Schedule length == instalment_count
        assert len(result["schedule"]) == instalments, (
            f"Schedule length mismatch: got {len(result['schedule'])}, "
            f"expected {instalments}"
        )

        # interest_free == True
        assert result["interest_free"] is True, (
            f"interest_free should be True, got {result['interest_free']}"
        )

        # Dates are monthly-spaced
        dates = [
            datetime.strptime(entry["due_date"], "%Y-%m-%d")
            for entry in result["schedule"]
        ]
        for i in range(1, len(dates)):
            prev = dates[i - 1]
            curr = dates[i]
            # Month should increment by 1 (handling year rollover)
            expected_month = prev.month + 1
            expected_year = prev.year
            if expected_month > 12:
                expected_month = 1
                expected_year += 1
            assert curr.month == expected_month and curr.year == expected_year, (
                f"Date spacing violation at index {i}: "
                f"prev={prev.strftime('%Y-%m-%d')}, curr={curr.strftime('%Y-%m-%d')}, "
                f"expected month={expected_month}, year={expected_year}"
            )


# ---------------------------------------------------------------------------
# Property 7: Callback Deterministic ID
# Feature: expanded-tool-gallery, Property 7: Callback Deterministic ID
# **Validates: Requirements 6.3**
# ---------------------------------------------------------------------------


class TestCallbackDeterministicId:
    """Property 7: Callback Deterministic ID.

    *For any* set of valid inputs (customer_id, when, reason), calling
    schedule_callback_pure twice with identical inputs SHALL produce identical
    callback_id values. Furthermore, changing any single input SHALL produce
    a different callback_id.

    **Validates: Requirements 6.3**
    """

    @settings(max_examples=100)
    @given(
        customer_id=_valid_customer_id,
        when=_valid_iso_datetime,
        reason=_valid_reason,
    )
    def test_callback_deterministic_id(self, customer_id, when, reason):
        # Feature: expanded-tool-gallery, Property 7: Callback Deterministic ID
        # **Validates: Requirements 6.3**

        # Same inputs → same callback_id
        result1 = schedule_callback_pure(customer_id, when, reason)
        result2 = schedule_callback_pure(customer_id, when, reason)
        assert result1["callback_id"] == result2["callback_id"], (
            f"Determinism violated: same inputs produced different IDs: "
            f"{result1['callback_id']} vs {result2['callback_id']}"
        )

        # Different customer_id → different callback_id
        alt_customer = "CUST-999" if customer_id != "CUST-999" else "CUST-998"
        result_alt = schedule_callback_pure(alt_customer, when, reason)
        assert result1["callback_id"] != result_alt["callback_id"], (
            f"Uniqueness violated: different customer_id produced same ID"
        )

        # Different reason → different callback_id
        alt_reason = reason + "_alt"
        result_alt_reason = schedule_callback_pure(customer_id, when, alt_reason)
        assert result1["callback_id"] != result_alt_reason["callback_id"], (
            f"Uniqueness violated: different reason produced same ID"
        )


# ---------------------------------------------------------------------------
# Property 8: Tool Cap Budget Enforcement
# Feature: expanded-tool-gallery, Property 8: Tool Cap Budget Enforcement
# **Validates: Requirements 7.1, 7.2**
# ---------------------------------------------------------------------------


class TestToolCapBudgetEnforcement:
    """Property 8: Tool Cap Budget Enforcement.

    *For any* sequence of tool calls on an agent with FourToolCapHook(budget=8),
    the hook SHALL allow exactly 8 calls before cancelling the agent. After
    reset(), the budget SHALL be fully restored.

    **Validates: Requirements 7.1, 7.2**
    """

    @settings(max_examples=100)
    @given(n_calls=st.integers(min_value=1, max_value=20))
    def test_tool_cap_budget_enforcement(self, n_calls):
        # Feature: expanded-tool-gallery, Property 8: Tool Cap Budget Enforcement
        # **Validates: Requirements 7.1, 7.2**
        hook = FourToolCapHook(budget=8)

        mock_agent = MagicMock()
        cancelled_at = None

        for i in range(n_calls):
            event = MagicMock()
            event.agent = mock_agent
            hook.on_tool_complete(event)

            if mock_agent.cancel.called and cancelled_at is None:
                cancelled_at = i + 1  # 1-indexed call count

        if n_calls >= 8:
            # Hook should have cancelled at exactly call 8
            assert cancelled_at == 8, (
                f"Expected cancellation at call 8, got {cancelled_at} "
                f"(n_calls={n_calls})"
            )
        else:
            # Hook should NOT have cancelled
            assert cancelled_at is None, (
                f"Unexpected cancellation at call {cancelled_at} "
                f"(n_calls={n_calls}, budget=8)"
            )

        # After reset(), budget is fully restored
        hook.reset()
        mock_agent.reset_mock()

        # Should be able to make 7 calls without cancellation
        for i in range(7):
            event = MagicMock()
            event.agent = mock_agent
            hook.on_tool_complete(event)

        assert not mock_agent.cancel.called, (
            "Agent was cancelled before budget=8 after reset()"
        )

        # 8th call should trigger cancellation
        event = MagicMock()
        event.agent = mock_agent
        hook.on_tool_complete(event)
        assert mock_agent.cancel.called, (
            "Agent was NOT cancelled at call 8 after reset()"
        )


# ---------------------------------------------------------------------------
# Property 9: Invalid Input Error Handling
# Feature: expanded-tool-gallery, Property 9: Invalid Input Error Handling
# **Validates: Requirements 1.5, 3.5, 5.5, 6.4**
# ---------------------------------------------------------------------------


class TestInvalidInputErrors:
    """Property 9: Invalid Input Error Handling.

    *For any* invalid input to each tool, the function SHALL raise ValueError
    or return an error response rather than a success payload.

    **Validates: Requirements 1.5, 3.5, 5.5, 6.4**
    """

    @settings(max_examples=100)
    @given(
        suburb=st.one_of(
            st.just(""),
            st.just("   "),
            st.just("\t"),
            st.just("\n"),
        )
    )
    def test_check_outage_status_empty_suburb(self, suburb):
        # Feature: expanded-tool-gallery, Property 9: Invalid Input Error Handling
        # **Validates: Requirements 1.5**
        import pytest
        with pytest.raises(ValueError):
            check_outage_status_pure(suburb)

    @settings(max_examples=100)
    @given(
        customer_id=st.one_of(
            st.just(""),
            st.just("INVALID"),
            st.just("CUST"),
            st.just("CUST-"),
            st.just("CUST-1"),  # too few digits
            st.just("CUST-1234567"),  # too many digits
            st.text(min_size=1, max_size=20).filter(
                lambda s: not s.startswith("CUST-") or not s[5:].isdigit() or len(s[5:]) < 3
            ),
        )
    )
    def test_lookup_concessions_invalid_customer_id(self, customer_id):
        # Feature: expanded-tool-gallery, Property 9: Invalid Input Error Handling
        # **Validates: Requirements 3.5**
        import pytest
        with pytest.raises(ValueError):
            lookup_concessions_pure(customer_id)

    @settings(max_examples=100)
    @given(
        instalments=st.one_of(
            st.integers(max_value=1),
            st.integers(min_value=13),
        )
    )
    def test_propose_payment_plan_invalid_instalments(self, instalments):
        # Feature: expanded-tool-gallery, Property 9: Invalid Input Error Handling
        # **Validates: Requirements 5.5**
        import pytest
        with pytest.raises(ValueError):
            propose_payment_plan_pure("CUST-006", instalments, 100.0)

    @settings(max_examples=100)
    @given(
        balance=st.one_of(
            st.just(0.0),
            st.just(-1.0),
            st.floats(max_value=0.0, allow_nan=False, allow_infinity=False),
        )
    )
    def test_propose_payment_plan_invalid_balance(self, balance):
        # Feature: expanded-tool-gallery, Property 9: Invalid Input Error Handling
        # **Validates: Requirements 5.5**
        import pytest
        with pytest.raises(ValueError):
            propose_payment_plan_pure("CUST-006", 3, balance)

    @settings(max_examples=100)
    @given(
        when=st.one_of(
            st.just(""),
            st.just("not-a-date"),
            st.just("2025-13-01T00:00:00"),
            st.just("yesterday"),
            st.text(min_size=1, max_size=30).filter(
                lambda s: not _is_valid_iso(s)
            ),
        )
    )
    def test_schedule_callback_invalid_datetime(self, when):
        # Feature: expanded-tool-gallery, Property 9: Invalid Input Error Handling
        # **Validates: Requirements 6.4**
        import pytest
        with pytest.raises(ValueError):
            schedule_callback_pure("CUST-001", when, "billing query")

    @settings(max_examples=100)
    @given(
        reason=st.one_of(
            st.just(""),
            st.just("   "),
            st.just("\t"),
            st.just("\n"),
        )
    )
    def test_schedule_callback_empty_reason(self, reason):
        # Feature: expanded-tool-gallery, Property 9: Invalid Input Error Handling
        # **Validates: Requirements 6.4**
        import pytest
        with pytest.raises(ValueError):
            schedule_callback_pure("CUST-001", "2025-07-15T10:00:00", reason)


def _is_valid_iso(s: str) -> bool:
    """Helper to check if a string is a valid ISO datetime."""
    try:
        datetime.fromisoformat(s)
        return True
    except (ValueError, TypeError):
        return False
