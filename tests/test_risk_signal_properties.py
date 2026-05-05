"""Property-based tests for Risk Signal Computation.

Feature: agentic-actions-portfolio

Uses Hypothesis for property-based testing with minimum 100 iterations per
property. Each test is tagged with the feature and property reference from
the design document.

Properties tested:
  - Property 11: Risk Signal Range Invariant
  - Property 12: Hardship Caps Risk at Zero
  - Property 13: Risk Signal Sort Invariant
"""
from __future__ import annotations

import importlib

from hypothesis import given, settings, assume
from hypothesis import strategies as st

# `from lambda.handler import ...` is a SyntaxError (lambda = Python keyword).
_handler = importlib.import_module("lambda.handler")
compute_risk_signals = _handler.compute_risk_signals


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy: valid customer_id
_customer_id = st.from_regex(r"CUST-\d{3}", fullmatch=True)

# Strategy: valid billing record
_billing_record = st.fixed_dictionaries({
    "month": st.from_regex(r"2025-(0[1-9]|1[0-2])", fullmatch=True),
    "usage_kwh": st.floats(min_value=50, max_value=1500, allow_nan=False, allow_infinity=False),
    "customer_id": st.just("CUST-001"),
    "plan_id": st.just("STD"),
})

# Strategy: billing history (2-12 months, unique months)
_billing_history = st.lists(
    _billing_record,
    min_size=2,
    max_size=12,
    unique_by=lambda r: r["month"],
)

# Strategy: hardship flag
_hardship_flag = st.booleans()

# Strategy: usage trend
_usage_trend = st.sampled_from(["increasing", "decreasing", "stable"])


# ---------------------------------------------------------------------------
# Property 11: Risk Signal Range Invariant
# Feature: agentic-actions-portfolio, Property 11: Risk Signal Range Invariant
# **Validates: Requirements 9.3, 9.5**
# ---------------------------------------------------------------------------


class TestRiskSignalRangeInvariant:
    """Property 11: Risk Signal Range Invariant.

    *For any* valid combination of bill-shock magnitude, usage trend direction,
    and hardship flag status, the compute_risk_signals function SHALL produce a
    risk_score in the range [0, 100].

    **Validates: Requirements 9.3, 9.5**
    """

    @settings(max_examples=100)
    @given(
        billing_history=_billing_history,
        hardship_flag=_hardship_flag,
    )
    def test_risk_signal_range_invariant(self, billing_history, hardship_flag):
        # Feature: agentic-actions-portfolio, Property 11: Risk Signal Range Invariant
        # **Validates: Requirements 9.3, 9.5**
        customer_id = "CUST-001"

        # Set customer_id on all records
        for r in billing_history:
            r["customer_id"] = customer_id

        billing_records = {customer_id: billing_history}
        hardship_flags = {customer_id: hardship_flag}

        result = compute_risk_signals(
            [customer_id], billing_records, hardship_flags
        )

        assert len(result["queue"]) == 1
        signal = result["queue"][0]
        assert 0 <= signal["risk_score"] <= 100, (
            f"risk_score {signal['risk_score']} out of range [0, 100] "
            f"for hardship={hardship_flag}, billing_months={len(billing_history)}"
        )


# ---------------------------------------------------------------------------
# Property 12: Hardship Caps Risk at Zero
# Feature: agentic-actions-portfolio, Property 12: Hardship Caps Risk at Zero
# **Validates: Requirements 9.4**
# ---------------------------------------------------------------------------


class TestHardshipCapsRiskAtZero:
    """Property 12: Hardship Caps Risk at Zero.

    *For any* customer with hardship_flag=true, the compute_risk_signals
    function SHALL return a risk_score of 0.

    **Validates: Requirements 9.4**
    """

    @settings(max_examples=100)
    @given(billing_history=_billing_history)
    def test_hardship_caps_risk_at_zero(self, billing_history):
        # Feature: agentic-actions-portfolio, Property 12: Hardship Caps Risk at Zero
        # **Validates: Requirements 9.4**
        customer_id = "CUST-001"

        # Set customer_id on all records
        for r in billing_history:
            r["customer_id"] = customer_id

        billing_records = {customer_id: billing_history}
        # Hardship flag is ALWAYS true for this property
        hardship_flags = {customer_id: True}

        result = compute_risk_signals(
            [customer_id], billing_records, hardship_flags
        )

        assert len(result["queue"]) == 1
        signal = result["queue"][0]
        assert signal["risk_score"] == 0, (
            f"Hardship customer should have risk_score=0, "
            f"got {signal['risk_score']}"
        )
        assert signal["hardship_flag"] is True


# ---------------------------------------------------------------------------
# Property 13: Risk Signal Sort Invariant
# Feature: agentic-actions-portfolio, Property 13: Risk Signal Sort Invariant
# **Validates: Requirements 9.6**
# ---------------------------------------------------------------------------


class TestRiskSignalSortInvariant:
    """Property 13: Risk Signal Sort Invariant.

    *For any* list of customer_ids passed to compute_risk_signals, the output
    list SHALL be sorted in descending order by risk_score.

    **Validates: Requirements 9.6**
    """

    @settings(max_examples=100)
    @given(
        billing_histories=st.lists(
            _billing_history,
            min_size=2,
            max_size=6,
        ),
        hardship_flags_list=st.lists(
            _hardship_flag,
            min_size=2,
            max_size=6,
        ),
    )
    def test_risk_signal_sort_invariant(self, billing_histories, hardship_flags_list):
        # Feature: agentic-actions-portfolio, Property 13: Risk Signal Sort Invariant
        # **Validates: Requirements 9.6**

        # Ensure same length
        n = min(len(billing_histories), len(hardship_flags_list))
        assume(n >= 2)
        billing_histories = billing_histories[:n]
        hardship_flags_list = hardship_flags_list[:n]

        # Generate unique customer_ids
        customer_ids = [f"CUST-{i+1:03d}" for i in range(n)]

        billing_records = {}
        hardship_flags = {}
        for i, cid in enumerate(customer_ids):
            # Set customer_id on all records
            records = billing_histories[i]
            for r in records:
                r["customer_id"] = cid
            billing_records[cid] = records
            hardship_flags[cid] = hardship_flags_list[i]

        result = compute_risk_signals(
            customer_ids, billing_records, hardship_flags
        )

        queue = result["queue"]
        assert len(queue) == n

        # Verify descending sort by risk_score
        for i in range(len(queue) - 1):
            assert queue[i]["risk_score"] >= queue[i + 1]["risk_score"], (
                f"Sort invariant violated: queue[{i}].risk_score="
                f"{queue[i]['risk_score']} < queue[{i+1}].risk_score="
                f"{queue[i+1]['risk_score']}"
            )
