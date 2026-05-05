"""Property-based tests for StreamingTraceHook.

Feature: streaming-reasoning-trace

Uses Hypothesis for property-based testing with minimum 100 iterations per
property. Each test is tagged with the feature and property reference from
the design document.

Properties tested:
  - Property 5: Summary integrity — deterministic formatters, no narrative filtering
  - Property 6: Unknown tools are silently skipped
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from agent.hooks.streaming_trace import StreamingTraceHook, _TRACE_TOOLS, _SUMMARY_DISPATCH
from agent.reasoning.summaries import (
    summary_detect_bill_shock,
    summary_get_billing_history,
    summary_get_hardship_flag,
    summary_simulate_savings,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Known tool names that the hook DOES handle — used to exclude from generation.
_KNOWN_TOOLS = frozenset(_TRACE_TOOLS)

# Strategy: random tool names that are NOT in the known set.
# Combines text generation with explicit near-miss examples.
_unknown_tool_name = st.one_of(
    # Random ASCII text (avoids empty strings which aren't realistic tool names)
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
        min_size=1,
        max_size=50,
    ).filter(lambda s: s not in _KNOWN_TOOLS),
    # Near-miss variants of known tools (prefix/suffix/case mutations)
    st.sampled_from([
        "detect_bill_shock_v2",
        "get_billing",
        "billing_history",
        "get_hardship",
        "simulate",
        "savings",
        "DETECT_BILL_SHOCK",
        "Get_Billing_History",
        "unknown_tool",
        "some_random_tool",
        "calculate_tariff",
        "fetch_customer_data",
        "run_model_inference",
    ]),
)


# ---------------------------------------------------------------------------
# Property 6: Unknown tools are silently skipped
# **Validates: Requirements 3.3**
# ---------------------------------------------------------------------------


class TestUnknownToolsSilentlySkipped:
    """Property 6: Unknown tools are silently skipped.

    Feature: streaming-reasoning-trace, Property 6: Unknown tools are silently skipped

    *For any* tool name that is NOT in the set {detect_bill_shock,
    get_billing_history, get_hardship_flag, simulate_savings}, the
    StreamingTraceHook SHALL NOT invoke the streaming callback and SHALL NOT
    raise an exception.

    **Validates: Requirements 3.3**
    """

    @settings(max_examples=100)
    @given(tool_name=_unknown_tool_name)
    def test_unknown_tool_does_not_invoke_callback(self, tool_name: str) -> None:
        """For any unknown tool name, the callback is never invoked.

        Feature: streaming-reasoning-trace, Property 6: Unknown tools are silently skipped
        **Validates: Requirements 3.3**
        """
        assume(tool_name not in _KNOWN_TOOLS)

        hook = StreamingTraceHook()
        callback = MagicMock()
        hook.set_callback(callback)

        # Build a mock AfterToolCallEvent with the unknown tool name.
        event = MagicMock()
        event.tool_name = tool_name
        event.tool_result = {"some": "data"}

        # Invoke the hook's internal handler — must not raise.
        hook._on_tool_complete(event)

        # The callback must NOT have been called.
        callback.assert_not_called()

    @settings(max_examples=100)
    @given(tool_name=_unknown_tool_name)
    def test_unknown_tool_does_not_raise(self, tool_name: str) -> None:
        """For any unknown tool name, no exception is raised.

        Feature: streaming-reasoning-trace, Property 6: Unknown tools are silently skipped
        **Validates: Requirements 3.3**
        """
        assume(tool_name not in _KNOWN_TOOLS)

        hook = StreamingTraceHook()
        callback = MagicMock()
        hook.set_callback(callback)

        event = MagicMock()
        event.tool_name = tool_name
        event.tool_result = {"arbitrary": "payload", "nested": [1, 2, 3]}

        # Must not raise any exception.
        try:
            hook._on_tool_complete(event)
        except Exception as exc:
            raise AssertionError(
                f"StreamingTraceHook raised {type(exc).__name__} for unknown "
                f"tool '{tool_name}': {exc}"
            )

    @settings(max_examples=100)
    @given(tool_name=_unknown_tool_name)
    def test_unknown_tool_without_callback_does_not_raise(self, tool_name: str) -> None:
        """For any unknown tool name with no callback set, no exception is raised.

        Feature: streaming-reasoning-trace, Property 6: Unknown tools are silently skipped
        **Validates: Requirements 3.3**
        """
        assume(tool_name not in _KNOWN_TOOLS)

        hook = StreamingTraceHook()
        # No callback set — _callback is None.

        event = MagicMock()
        event.tool_name = tool_name
        event.tool_result = None  # Edge case: None result

        # Must not raise any exception.
        try:
            hook._on_tool_complete(event)
        except Exception as exc:
            raise AssertionError(
                f"StreamingTraceHook raised {type(exc).__name__} for unknown "
                f"tool '{tool_name}' (no callback): {exc}"
            )

# ---------------------------------------------------------------------------
# Strategies for Property 5: Summary integrity
# ---------------------------------------------------------------------------

# Strategy: valid detect_bill_shock result payloads
_bill_shock_detected_result = st.fixed_dictionaries({
    "is_shock": st.just(True),
    "delta_dollars": st.floats(min_value=0.01, max_value=9999.99, allow_nan=False, allow_infinity=False),
    "shock_month": st.from_regex(r"20\d{2}-(?:0[1-9]|1[0-2])", fullmatch=True),
    "current_dollars": st.floats(min_value=0.01, max_value=9999.99, allow_nan=False, allow_infinity=False),
    "mean_dollars": st.floats(min_value=0.01, max_value=9999.99, allow_nan=False, allow_infinity=False),
})

_bill_shock_not_detected_result = st.fixed_dictionaries({
    "is_shock": st.just(False),
})

_detect_bill_shock_result = st.one_of(
    _bill_shock_detected_result,
    _bill_shock_not_detected_result,
)

# Strategy: valid get_billing_history result payloads (list or dict shapes)
_billing_history_list_result = st.lists(
    st.fixed_dictionaries({
        "month": st.from_regex(r"20\d{2}-(?:0[1-9]|1[0-2])", fullmatch=True),
        "amount": st.floats(min_value=0.0, max_value=9999.99, allow_nan=False, allow_infinity=False),
    }),
    min_size=0,
    max_size=24,
)

_billing_history_dict_result = st.one_of(
    st.fixed_dictionaries({"billing": st.lists(st.integers(), min_size=0, max_size=12)}),
    st.fixed_dictionaries({"billing_history": st.lists(st.integers(), min_size=0, max_size=12)}),
)

_get_billing_history_result = st.one_of(
    _billing_history_list_result,
    _billing_history_dict_result,
)

# Strategy: valid get_hardship_flag result payloads
_get_hardship_flag_result = st.one_of(
    st.fixed_dictionaries({
        "hardship": st.booleans(),
        "customer_id": st.from_regex(r"CUST-\d{3,6}", fullmatch=True),
    }),
    st.fixed_dictionaries({
        "hardship_flag": st.booleans(),
    }),
)

# Strategy: valid simulate_savings result payloads
_simulate_savings_result = st.fixed_dictionaries({
    "green": st.one_of(
        st.none(),
        st.fixed_dictionaries({
            "saving_monthly": st.floats(min_value=0.0, max_value=999.99, allow_nan=False, allow_infinity=False),
        }),
    ),
    "cheapest": st.one_of(
        st.none(),
        st.fixed_dictionaries({
            "saving_monthly": st.floats(min_value=0.0, max_value=999.99, allow_nan=False, allow_infinity=False),
        }),
    ),
})

# Combined strategy: a random (tool_name, result) pair
_tool_and_result = st.one_of(
    st.tuples(st.just("detect_bill_shock"), _detect_bill_shock_result),
    st.tuples(st.just("get_billing_history"), _get_billing_history_result),
    st.tuples(st.just("get_hardship_flag"), _get_hardship_flag_result),
    st.tuples(st.just("simulate_savings"), _simulate_savings_result),
)


# ---------------------------------------------------------------------------
# Property 5: Summary integrity — deterministic formatters, no narrative filtering
# **Validates: Requirements 2.6, 4.3**
# ---------------------------------------------------------------------------


class TestSummaryIntegrity:
    """Property 5: Summary integrity — deterministic formatters, no narrative filtering.

    Feature: streaming-reasoning-trace, Property 5: Summary integrity — deterministic formatters, no narrative filtering

    *For any* valid tool result payload for a tool in {detect_bill_shock,
    get_billing_history, get_hardship_flag, simulate_savings}, the summary
    field in the emitted trace_step event SHALL equal the output of the
    corresponding deterministic formatter in agent/reasoning/summaries.py,
    with no narrative filtering applied (digits, currency symbols, percentages,
    and dates preserved).

    **Validates: Requirements 2.6, 4.3**
    """

    @settings(max_examples=100)
    @given(tool_and_result=_tool_and_result)
    def test_hook_summary_matches_formatter_output(self, tool_and_result: tuple) -> None:
        """The summary passed to the callback equals the direct formatter output.

        Feature: streaming-reasoning-trace, Property 5: Summary integrity — deterministic formatters, no narrative filtering
        **Validates: Requirements 2.6, 4.3**
        """
        tool_name, tool_result = tool_and_result

        # Compute expected summary directly from the formatter.
        formatter = _SUMMARY_DISPATCH[tool_name]
        expected_summary = formatter(tool_result)

        # Run through the hook and capture what the callback receives.
        hook = StreamingTraceHook()
        captured = []
        hook.set_callback(lambda name, summary: captured.append((name, summary)))

        event = MagicMock()
        event.tool_name = tool_name
        event.tool_result = tool_result

        hook._on_tool_complete(event)

        # The callback must have been invoked exactly once.
        assert len(captured) == 1, (
            f"Expected exactly 1 callback invocation for '{tool_name}', got {len(captured)}"
        )
        actual_tool, actual_summary = captured[0]
        assert actual_tool == tool_name
        assert actual_summary == expected_summary, (
            f"Summary mismatch for '{tool_name}':\n"
            f"  Expected: {expected_summary!r}\n"
            f"  Actual:   {actual_summary!r}"
        )

    @settings(max_examples=100)
    @given(tool_and_result=_tool_and_result)
    def test_summary_preserves_digits_currency_percentages_dates(self, tool_and_result: tuple) -> None:
        """D-11 exemption: summaries preserve digits, $, %, and date patterns.

        Feature: streaming-reasoning-trace, Property 5: Summary integrity — deterministic formatters, no narrative filtering
        **Validates: Requirements 2.6, 4.3**
        """
        tool_name, tool_result = tool_and_result

        # Compute summary via the hook path.
        hook = StreamingTraceHook()
        captured = []
        hook.set_callback(lambda name, summary: captured.append((name, summary)))

        event = MagicMock()
        event.tool_name = tool_name
        event.tool_result = tool_result

        hook._on_tool_complete(event)

        assert len(captured) == 1
        _, actual_summary = captured[0]

        # Compute expected summary directly.
        formatter = _SUMMARY_DISPATCH[tool_name]
        expected_summary = formatter(tool_result)

        # Verify no narrative filtering was applied — the summary must be
        # byte-identical to the formatter output (which intentionally contains
        # digits, currency symbols, percentages, and dates).
        assert actual_summary == expected_summary

        # Additionally verify that if the formatter output contains these
        # D-11 exempt characters, they are preserved in the hook output.
        # (i.e., no stripping/filtering has been applied)
        if "$" in expected_summary:
            assert "$" in actual_summary, "Currency symbol '$' was stripped from summary"
        if "%" in expected_summary:
            assert "%" in actual_summary, "Percentage symbol '%' was stripped from summary"
        if re.search(r"\d", expected_summary):
            # Digits present in expected — must be present in actual
            assert re.search(r"\d", actual_summary), "Digits were stripped from summary"
        if re.search(r"\d{4}-\d{2}", expected_summary):
            # Date pattern present in expected — must be present in actual
            assert re.search(r"\d{4}-\d{2}", actual_summary), "Date pattern was stripped from summary"

    @settings(max_examples=100)
    @given(tool_and_result=_tool_and_result)
    def test_summary_is_non_empty_string(self, tool_and_result: tuple) -> None:
        """Every known tool produces a non-empty summary string.

        Feature: streaming-reasoning-trace, Property 5: Summary integrity — deterministic formatters, no narrative filtering
        **Validates: Requirements 2.6, 4.3**
        """
        tool_name, tool_result = tool_and_result

        hook = StreamingTraceHook()
        captured = []
        hook.set_callback(lambda name, summary: captured.append((name, summary)))

        event = MagicMock()
        event.tool_name = tool_name
        event.tool_result = tool_result

        hook._on_tool_complete(event)

        assert len(captured) == 1
        _, actual_summary = captured[0]
        assert isinstance(actual_summary, str), f"Summary is not a string: {type(actual_summary)}"
        assert len(actual_summary) > 0, f"Summary is empty for tool '{tool_name}'"
