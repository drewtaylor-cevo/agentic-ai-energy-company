"""Property-based tests for Bill-Shock Decomposition v2 — Enriched Output.

Feature: agentic-actions-portfolio

Uses Hypothesis for property-based testing with minimum 100 iterations per
property. Each test is tagged with the feature and property reference from
the design document.

Properties tested:
  - Property 7: Decomposition Sum Invariant
  - Property 8: Decomposition Percentage Sum Invariant
  - Property 9: Zero-Rate Factor Omission
  - Property 10: Explanation Sentence Format
"""
from __future__ import annotations

import importlib
import re

from hypothesis import given, settings, assume
from hypothesis import strategies as st

# `from lambda.handler import ...` is a SyntaxError (lambda = Python keyword).
_handler = importlib.import_module("lambda.handler")
decompose_bill_shock_pure = _handler.decompose_bill_shock_pure


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


# ---------------------------------------------------------------------------
# Property 7: Decomposition Sum Invariant
# Feature: agentic-actions-portfolio, Property 7: Decomposition Sum Invariant
# **Validates: Requirements 5.2, 5.6**
# ---------------------------------------------------------------------------


class TestDecompositionSumInvariant:
    """Property 7: Decomposition Sum Invariant.

    *For any* valid billing history with at least 2 months, the sum of all
    Contributing_Factor dollar_amount values in the decomposition output SHALL
    equal total_delta_dollars within a tolerance of $0.01.

    **Validates: Requirements 5.2, 5.6**
    """

    @settings(max_examples=100)
    @given(billing_history=_billing_history)
    def test_decomposition_sum_invariant(self, billing_history):
        # Feature: agentic-actions-portfolio, Property 7: Decomposition Sum Invariant
        # **Validates: Requirements 5.2, 5.6**
        result = decompose_bill_shock_pure(billing_history)
        total = result["total_delta_dollars"]
        factors = result["contributing_factors"]

        factor_sum = sum(f["dollar_amount"] for f in factors)
        assert abs(total - factor_sum) <= 0.01, (
            f"Decomposition sum mismatch: total_delta_dollars={total}, "
            f"sum(contributing_factors.dollar_amount)={factor_sum}, "
            f"diff={abs(total - factor_sum)}"
        )


# ---------------------------------------------------------------------------
# Property 8: Decomposition Percentage Sum Invariant
# Feature: agentic-actions-portfolio, Property 8: Decomposition Percentage Sum Invariant
# **Validates: Requirements 5.3**
# ---------------------------------------------------------------------------


class TestDecompositionPercentageSumInvariant:
    """Property 8: Decomposition Percentage Sum Invariant.

    *For any* decomposition result with a non-zero total_delta_dollars, the sum
    of all Contributing_Factor percentage_of_total values SHALL equal 100 within
    a tolerance of 1 percentage point.

    **Validates: Requirements 5.3**
    """

    @settings(max_examples=100)
    @given(billing_history=_billing_history)
    def test_decomposition_percentage_sum_invariant(self, billing_history):
        # Feature: agentic-actions-portfolio, Property 8: Decomposition Percentage Sum Invariant
        # **Validates: Requirements 5.3**
        result = decompose_bill_shock_pure(billing_history)

        # Only check when total_delta_dollars is non-zero
        assume(result["total_delta_dollars"] != 0.0)

        factors = result["contributing_factors"]
        pct_sum = sum(f["percentage_of_total"] for f in factors)

        assert abs(100.0 - pct_sum) <= 1.0, (
            f"Percentage sum mismatch: sum(percentage_of_total)={pct_sum}, "
            f"expected ~100, diff={abs(100.0 - pct_sum)}"
        )


# ---------------------------------------------------------------------------
# Property 9: Zero-Rate Factor Omission
# Feature: agentic-actions-portfolio, Property 9: Zero-Rate Factor Omission
# **Validates: Requirements 5.5**
# ---------------------------------------------------------------------------


class TestZeroRateFactorOmission:
    """Property 9: Zero-Rate Factor Omission.

    *For any* billing history where no rate change has occurred, the rate_increase
    Contributing_Factor SHALL have a dollar_amount of $0.00 AND SHALL be omitted
    from the explanation_factors list.

    **Validates: Requirements 5.5**
    """

    @settings(max_examples=100)
    @given(billing_history=_billing_history)
    def test_zero_rate_factor_omission(self, billing_history):
        # Feature: agentic-actions-portfolio, Property 9: Zero-Rate Factor Omission
        # **Validates: Requirements 5.5**
        result = decompose_bill_shock_pure(billing_history)

        # In seed data, rate never changes — rate_increase is always $0.00
        factors = result["contributing_factors"]
        rate_factor = next(
            f for f in factors if f["factor_name"] == "rate_increase"
        )

        # rate_increase dollar_amount must be $0.00
        assert rate_factor["dollar_amount"] == 0.0, (
            f"rate_increase dollar_amount should be $0.00, "
            f"got ${rate_factor['dollar_amount']:.2f}"
        )

        # rate_increase must NOT appear in explanation_factors
        explanation_factors = result["explanation_factors"]
        for ef in explanation_factors:
            assert "rate" not in ef.lower() or "Rate change" not in ef, (
                f"rate_increase factor should be omitted from explanation_factors "
                f"when dollar_amount is $0.00, but found: {ef}"
            )

        # rate_increase must NOT appear in explanation_sentence
        explanation_sentence = result["explanation_sentence"]
        assert "rate increase" not in explanation_sentence, (
            f"rate_increase should be omitted from explanation_sentence "
            f"when dollar_amount is $0.00, but found in: {explanation_sentence}"
        )


# ---------------------------------------------------------------------------
# Property 10: Explanation Sentence Format
# Feature: agentic-actions-portfolio, Property 10: Explanation Sentence Format
# **Validates: Requirements 6.1**
# ---------------------------------------------------------------------------


class TestExplanationSentenceFormat:
    """Property 10: Explanation Sentence Format.

    *For any* decomposition result with Contributing_Factors, the
    explanation_sentence SHALL match the format
    "$X over baseline — Y% from [cause A], Z% from [cause B], ..."
    where X equals total_delta_dollars and the percentages correspond to the
    Contributing_Factor percentage_of_total values.

    **Validates: Requirements 6.1**
    """

    @settings(max_examples=100)
    @given(billing_history=_billing_history)
    def test_explanation_sentence_format(self, billing_history):
        # Feature: agentic-actions-portfolio, Property 10: Explanation Sentence Format
        # **Validates: Requirements 6.1**
        result = decompose_bill_shock_pure(billing_history)
        sentence = result["explanation_sentence"]
        total = result["total_delta_dollars"]

        # Must start with "$X over baseline"
        expected_prefix = f"${abs(total):.2f} over baseline"
        assert sentence.startswith(expected_prefix), (
            f"explanation_sentence should start with '{expected_prefix}', "
            f"got: '{sentence}'"
        )

        # Must contain " — " separator
        assert " — " in sentence, (
            f"explanation_sentence should contain ' — ' separator, "
            f"got: '{sentence}'"
        )

        # Each non-zero factor should appear as "N% from [cause]"
        non_zero_factors = [
            f for f in result["contributing_factors"]
            if f["dollar_amount"] != 0.0
        ]

        # The part after " — " should have comma-separated "N% from cause" entries
        after_dash = sentence.split(" — ", 1)[1]

        if non_zero_factors:
            # Each factor should produce a "N% from cause_label" segment
            parts = [p.strip() for p in after_dash.split(",")]
            assert len(parts) == len(non_zero_factors), (
                f"Expected {len(non_zero_factors)} factor parts in explanation, "
                f"got {len(parts)}: {parts}"
            )

            # Each part should match "N% from <cause>"
            for part in parts:
                assert re.match(r"\d+% from .+", part), (
                    f"Factor part '{part}' does not match 'N% from <cause>' format"
                )
        else:
            # When all factors are zero
            assert "no significant factors" in after_dash.lower(), (
                f"Expected 'no significant factors' when all factors are zero, "
                f"got: '{after_dash}'"
            )
