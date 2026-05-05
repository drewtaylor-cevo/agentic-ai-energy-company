"""Property-based tests for the multi-agent supervisor.

Feature: multi-agent-supervisor

Uses hypothesis for property-based testing with minimum 100 iterations per
property. Each test is tagged with the feature and property reference from
the design document.

Properties tested:
  - Property 1: TariffSpecialist always returns both tracks (REC-03)
  - Property 2: No upsell-to-disadvantage (non-negative savings)
  - Property 3: Hardship responses contain no tariff data
  - Property 4: Reference-period disclosure grounding
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from hypothesis import given, settings, assume
from hypothesis import strategies as st
from pydantic import ValidationError
from strands.types.exceptions import StructuredOutputException

from agent.agent import RecommendationResponse, TrackInfo
from agent.specialists.compliance import ComplianceReviewer
from agent.specialists.tariff import TariffSpecialist


# ---------------------------------------------------------------------------
# Shared reviewer instance — deterministic, stateless, safe to reuse.
# ---------------------------------------------------------------------------
_reviewer = ComplianceReviewer()


# ---------------------------------------------------------------------------
# Property 1: TariffSpecialist always returns both tracks (REC-03)
# **Validates: Requirements 3.1**
# ---------------------------------------------------------------------------

# Known persona customer IDs from the FALLBACKS bank.
_KNOWN_CUSTOMER_IDS = ("CUST-001", "CUST-003", "CUST-006")

# The five agent result scenarios that TariffSpecialist.handle() must survive.
_AGENT_RESULT_SCENARIOS = (
    "happy_path",
    "structured_output_exception",
    "none_structured_output",
    "cancelled_stop_reason",
    "general_exception",
)


def _make_valid_recommendation_response() -> RecommendationResponse:
    """Build a valid RecommendationResponse for the happy path mock."""
    return RecommendationResponse(
        green=TrackInfo(
            plan_id="ECO",
            plan_name="EcoFlex",
            saving_monthly=30.0,
            saving_annual=360.0,
            usage_narrative="Strong cool-season usage with a family-sized load across the year.",
            call_script="Ask about EcoFlex — it suits a strong winter-heating profile like yours.",
        ),
        cheapest=TrackInfo(
            plan_id="VAL",
            plan_name="Value Twelve",
            saving_monthly=55.0,
            saving_annual=660.0,
            usage_narrative="Consistently high household consumption with cool-season peaks.",
            call_script="Bring up Value Twelve — a budget-first pick for a high-usage home.",
        ),
    )


def _make_deterministic_savings() -> dict:
    """Build a valid deterministic savings dict for the fallback path."""
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex",
            "saving_monthly": 30.0,
            "saving_annual": 360.0,
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value Twelve",
            "saving_monthly": 55.0,
            "saving_annual": 660.0,
        },
    }


def _configure_mock_agent(mock_agent: MagicMock, scenario: str) -> None:
    """Configure the mock agent callable to simulate a specific scenario."""
    if scenario == "happy_path":
        result = MagicMock()
        result.stop_reason = "end_turn"
        result.structured_output = _make_valid_recommendation_response()
        result.message = {"content": []}
        mock_agent.return_value = result

    elif scenario == "structured_output_exception":
        mock_agent.side_effect = StructuredOutputException(
            "structured output validation failed"
        )

    elif scenario == "none_structured_output":
        result = MagicMock()
        result.stop_reason = "end_turn"
        result.structured_output = None
        result.message = {"content": []}
        mock_agent.return_value = result

    elif scenario == "cancelled_stop_reason":
        result = MagicMock()
        result.stop_reason = "cancelled"
        result.structured_output = None
        result.message = {"content": []}
        mock_agent.return_value = result

    elif scenario == "general_exception":
        mock_agent.side_effect = RuntimeError("agent invocation failed")


class TestTariffSpecialistAlwaysReturnsBothTracks:
    """Property 1: TariffSpecialist always returns both tracks (REC-03).

    Feature: multi-agent-supervisor, Property 1

    *For any* valid customer_id from the known persona set, and *for any*
    combination of mocked LLM responses (successful structured output,
    StructuredOutputException, None structured_output, cancelled stop_reason,
    general exception), the TariffSpecialist's handle() method SHALL return
    a dict containing both "green" and "cheapest" keys, or a dict containing
    "errorMessage" (the D-04 fallback shape). No other response shape is valid.

    **Validates: Requirements 3.1**
    """

    @settings(max_examples=100)
    @given(
        customer_id=st.sampled_from(list(_KNOWN_CUSTOMER_IDS)),
        scenario=st.sampled_from(list(_AGENT_RESULT_SCENARIOS)),
    )
    def test_tariff_specialist_always_returns_both_tracks(
        self, customer_id: str, scenario: str
    ) -> None:
        """For any customer_id × scenario, response has green+cheapest or errorMessage.

        Feature: multi-agent-supervisor, Property 1
        **Validates: Requirements 3.1**
        """
        # Build a TariffSpecialist with a mock agent and mock hook.
        mock_agent = MagicMock()
        mock_agent.messages = []  # Empty message list for _messages_start
        mock_hook = MagicMock()
        mock_hook.reset = MagicMock()

        specialist = TariffSpecialist(mock_agent, mock_hook)

        # Configure the mock agent for this scenario.
        _configure_mock_agent(mock_agent, scenario)

        # Patch the helpers that TariffSpecialist.handle() calls internally.
        # _narrative_fallback_salvage is called on the StructuredOutputException path.
        # _fetch_deterministic_savings is called on the general Exception path.
        salvage_result = _make_valid_recommendation_response()
        salvage_narrative = {
            "green": {"usage_narrative": "fallback", "call_script": "fallback"},
            "cheapest": {"usage_narrative": "fallback", "call_script": "fallback"},
        }
        deterministic_savings = _make_deterministic_savings()

        with patch(
            "agent.specialists.tariff._narrative_fallback_salvage",
            return_value=(salvage_result, salvage_narrative),
        ), patch(
            "agent.specialists.tariff._fetch_deterministic_savings",
            return_value=deterministic_savings,
        ):
            response = specialist.handle({"customer_id": customer_id})

        # Property assertion: response MUST have (green AND cheapest) OR errorMessage.
        has_both_tracks = "green" in response and "cheapest" in response
        has_error = "errorMessage" in response
        assert has_both_tracks or has_error, (
            f"Invalid response shape for customer_id={customer_id}, "
            f"scenario={scenario}: keys={set(response.keys())}. "
            f"Expected (green + cheapest) or errorMessage."
        )

    @settings(max_examples=100)
    @given(
        customer_id=st.sampled_from(list(_KNOWN_CUSTOMER_IDS)),
        scenario=st.sampled_from(list(_AGENT_RESULT_SCENARIOS)),
    )
    def test_tariff_specialist_fallback_failure_returns_error_message(
        self, customer_id: str, scenario: str
    ) -> None:
        """When fallback helpers also fail, response still has errorMessage.

        Feature: multi-agent-supervisor, Property 1
        **Validates: Requirements 3.1**
        """
        # Skip happy path — fallback helpers are not called on success.
        assume(scenario != "happy_path")

        mock_agent = MagicMock()
        mock_agent.messages = []
        mock_hook = MagicMock()
        mock_hook.reset = MagicMock()

        specialist = TariffSpecialist(mock_agent, mock_hook)
        _configure_mock_agent(mock_agent, scenario)

        # Make BOTH fallback helpers raise — worst-case D-04 path.
        with patch(
            "agent.specialists.tariff._narrative_fallback_salvage",
            side_effect=RuntimeError("salvage failed"),
        ), patch(
            "agent.specialists.tariff._fetch_deterministic_savings",
            side_effect=RuntimeError("deterministic savings failed"),
        ):
            response = specialist.handle({"customer_id": customer_id})

        # Even when everything fails, the response must have errorMessage.
        has_both_tracks = "green" in response and "cheapest" in response
        has_error = "errorMessage" in response
        assert has_both_tracks or has_error, (
            f"Invalid response shape for customer_id={customer_id}, "
            f"scenario={scenario} (fallback failure): keys={set(response.keys())}. "
            f"Expected (green + cheapest) or errorMessage."
        )


# ---------------------------------------------------------------------------
# Strategies (shared by Properties 2-4)
# ---------------------------------------------------------------------------

# Finite floats only — avoid NaN/inf which are not meaningful savings values.
_finite_float = st.floats(allow_nan=False, allow_infinity=False)

# Tool names that count as grounding evidence for reference-period disclosure.
_GROUNDING_TOOLS = ("simulate_savings", "get_billing_history")

# Non-grounding tool names — tools that do NOT satisfy the reference-period check.
_non_grounding_tool = st.sampled_from([
    "detect_bill_shock",
    "get_hardship_flag",
    "some_other_tool",
    "lookup_customer",
])

# A grounding tool name.
_grounding_tool = st.sampled_from(list(_GROUNDING_TOOLS))

# Tariff field keys that must not appear in hardship responses.
_TARIFF_FIELDS = ("plan_id", "saving_monthly", "saving_annual")


# ---------------------------------------------------------------------------
# Property 2: No upsell-to-disadvantage (non-negative savings)
# **Validates: Requirements 4.2**
# ---------------------------------------------------------------------------


class TestNoUpsellToDisadvantage:
    """Property 2: No upsell-to-disadvantage (non-negative savings).

    Feature: multi-agent-supervisor, Property 2

    *For any* RecommendationResponse dict with arbitrary saving_monthly float
    values on the green and cheapest tracks, the ComplianceReviewer's
    upsell-to-disadvantage check SHALL return "pass" if and only if both
    saving_monthly values are >= 0. If either value is negative, the check
    SHALL return "fail" with a reason string identifying the offending track.

    **Validates: Requirements 4.2**
    """

    @settings(max_examples=100)
    @given(
        green_saving=_finite_float,
        cheapest_saving=_finite_float,
    )
    def test_pass_iff_both_non_negative(
        self, green_saving: float, cheapest_saving: float
    ) -> None:
        """Verdict is 'pass' iff both saving_monthly values are >= 0.

        **Validates: Requirements 4.2**
        """
        response = {
            "kind": "recommendation",
            "green": {"saving_monthly": green_saving},
            "cheapest": {"saving_monthly": cheapest_saving},
            # Provide a valid reasoning_trace so the reference-period check
            # passes — we're isolating the upsell check here.
            "reasoning_trace": [{"tool": "simulate_savings", "summary": "ok"}],
        }
        result = _reviewer._check_no_upsell_to_disadvantage(response)

        both_non_negative = green_saving >= 0 and cheapest_saving >= 0
        if both_non_negative:
            assert result.verdict == "pass", (
                f"Expected pass for green={green_saving}, cheapest={cheapest_saving}, "
                f"got verdict={result.verdict}, reason={result.reason}"
            )
        else:
            assert result.verdict == "fail", (
                f"Expected fail for green={green_saving}, cheapest={cheapest_saving}, "
                f"got verdict={result.verdict}, reason={result.reason}"
            )

    @settings(max_examples=100)
    @given(
        green_saving=st.floats(min_value=0, allow_nan=False, allow_infinity=False),
        cheapest_saving=st.floats(min_value=0, allow_nan=False, allow_infinity=False),
    )
    def test_non_negative_always_passes(
        self, green_saving: float, cheapest_saving: float
    ) -> None:
        """Any non-negative saving_monthly pair always passes.

        **Validates: Requirements 4.2**
        """
        response = {
            "kind": "recommendation",
            "green": {"saving_monthly": green_saving},
            "cheapest": {"saving_monthly": cheapest_saving},
            "reasoning_trace": [{"tool": "simulate_savings", "summary": "ok"}],
        }
        result = _reviewer._check_no_upsell_to_disadvantage(response)
        assert result.verdict == "pass"
        assert result.rule == "no_upsell_to_disadvantage"

    @settings(max_examples=100)
    @given(
        green_saving=_finite_float,
        cheapest_saving=_finite_float,
    )
    def test_negative_saving_identifies_offending_track(
        self, green_saving: float, cheapest_saving: float
    ) -> None:
        """When a track has negative saving, the reason identifies it.

        **Validates: Requirements 4.2**
        """
        assume(green_saving < 0 or cheapest_saving < 0)

        response = {
            "kind": "recommendation",
            "green": {"saving_monthly": green_saving},
            "cheapest": {"saving_monthly": cheapest_saving},
            "reasoning_trace": [{"tool": "simulate_savings", "summary": "ok"}],
        }
        result = _reviewer._check_no_upsell_to_disadvantage(response)
        assert result.verdict == "fail"

        if green_saving < 0:
            assert "green" in result.reason
        if cheapest_saving < 0:
            assert "cheapest" in result.reason


# ---------------------------------------------------------------------------
# Property 3: Hardship responses contain no tariff data
# **Validates: Requirements 4.3**
# ---------------------------------------------------------------------------

# Strategy: a clean hardship response with no tariff fields.
_clean_hardship = st.fixed_dictionaries({
    "kind": st.just("hardship"),
    "customer_id": st.text(min_size=1, max_size=20),
    "reason": st.text(min_size=1, max_size=100),
    "routing_target": st.just("hardship_team"),
    "call_script": st.text(min_size=1, max_size=100),
})


def _inject_tariff_field(base: dict, field: str, depth: int) -> dict:
    """Inject a tariff field at the specified nesting depth."""
    result = dict(base)
    if depth == 0:
        result[field] = "leaked_value"
    else:
        # Build nested dict chain
        inner: dict = {field: "leaked_value"}
        for _ in range(depth - 1):
            inner = {"nested": inner}
        result["leaked_data"] = inner
    return result


class TestHardshipNoTariffData:
    """Property 3: Hardship responses contain no tariff data.

    Feature: multi-agent-supervisor, Property 3

    *For any* dict with kind: "hardship", the ComplianceReviewer's
    hardship-flag cross-check SHALL return "pass" if and only if the dict
    contains none of the keys plan_id, saving_monthly, or saving_annual at
    the top level or nested within any sub-dict. If any of these keys are
    present, the check SHALL return "fail".

    **Validates: Requirements 4.3**
    """

    @settings(max_examples=100)
    @given(base=_clean_hardship)
    def test_clean_hardship_always_passes(self, base: dict) -> None:
        """A hardship response with no tariff fields always passes.

        **Validates: Requirements 4.3**
        """
        result = _reviewer._check_hardship_no_tariff_data(base)
        assert result.verdict == "pass"
        assert result.rule == "hardship_no_tariff_data"

    @settings(max_examples=100)
    @given(
        base=_clean_hardship,
        field=st.sampled_from(list(_TARIFF_FIELDS)),
    )
    def test_top_level_tariff_field_fails(self, base: dict, field: str) -> None:
        """A tariff field at the top level causes failure.

        **Validates: Requirements 4.3**
        """
        contaminated = _inject_tariff_field(base, field, depth=0)
        result = _reviewer._check_hardship_no_tariff_data(contaminated)
        assert result.verdict == "fail"
        assert field in result.reason

    @settings(max_examples=100)
    @given(
        base=_clean_hardship,
        field=st.sampled_from(list(_TARIFF_FIELDS)),
        depth=st.integers(min_value=1, max_value=5),
    )
    def test_nested_tariff_field_fails(
        self, base: dict, field: str, depth: int
    ) -> None:
        """A tariff field nested at any depth causes failure.

        **Validates: Requirements 4.3**
        """
        contaminated = _inject_tariff_field(base, field, depth=depth)
        result = _reviewer._check_hardship_no_tariff_data(contaminated)
        assert result.verdict == "fail"
        assert field in result.reason

    @settings(max_examples=100)
    @given(base=_clean_hardship)
    def test_full_review_clean_hardship_passes(self, base: dict) -> None:
        """Full review() on a clean hardship response passes.

        **Validates: Requirements 4.3**
        """
        review = _reviewer.review(base, {})
        assert review.verdict == "pass"
        assert "hardship_no_tariff_data" in review.rules_checked


# ---------------------------------------------------------------------------
# Property 4: Reference-period disclosure grounding
# **Validates: Requirements 4.1**
# ---------------------------------------------------------------------------

# Strategy: a reasoning_trace entry with a specific tool name.
_trace_entry = st.fixed_dictionaries({
    "tool": st.text(min_size=1, max_size=30),
    "summary": st.text(min_size=1, max_size=100),
})

# Strategy: a reasoning_trace with only non-grounding tools.
_non_grounding_trace = st.lists(
    st.fixed_dictionaries({
        "tool": _non_grounding_tool,
        "summary": st.text(min_size=1, max_size=50),
    }),
    min_size=0,
    max_size=5,
)


class TestReferencePeriodDisclosure:
    """Property 4: Reference-period disclosure grounding.

    Feature: multi-agent-supervisor, Property 4

    *For any* RecommendationResponse dict with an arbitrary reasoning_trace
    list, the ComplianceReviewer's reference-period disclosure check SHALL
    return "pass" if and only if the reasoning_trace contains at least one
    entry with tool equal to "simulate_savings" or "get_billing_history".
    An empty or missing reasoning_trace SHALL cause the check to return "fail".

    **Validates: Requirements 4.1**
    """

    @settings(max_examples=100)
    @given(
        grounding_tool=_grounding_tool,
        extra_entries=st.lists(_trace_entry, min_size=0, max_size=5),
        insert_pos=st.integers(min_value=0, max_value=10),
    )
    def test_grounding_tool_present_passes(
        self,
        grounding_tool: str,
        extra_entries: list[dict],
        insert_pos: int,
    ) -> None:
        """A trace with at least one grounding tool entry passes.

        **Validates: Requirements 4.1**
        """
        grounding_entry = {"tool": grounding_tool, "summary": "grounding evidence"}
        trace = list(extra_entries)
        # Insert the grounding entry at a bounded position.
        pos = min(insert_pos, len(trace))
        trace.insert(pos, grounding_entry)

        response = {"kind": "recommendation", "reasoning_trace": trace}
        result = _reviewer._check_reference_period(response)
        assert result.verdict == "pass"
        assert result.rule == "reference_period_disclosure"

    @settings(max_examples=100)
    @given(trace=_non_grounding_trace)
    def test_no_grounding_tool_fails(self, trace: list[dict]) -> None:
        """A trace with no grounding tool entries fails.

        **Validates: Requirements 4.1**
        """
        response = {"kind": "recommendation", "reasoning_trace": trace}
        result = _reviewer._check_reference_period(response)
        assert result.verdict == "fail"
        assert result.rule == "reference_period_disclosure"

    @settings(max_examples=100)
    @given(data=st.data())
    def test_empty_or_missing_trace_fails(self, data: st.DataObject) -> None:
        """An empty or missing reasoning_trace always fails.

        **Validates: Requirements 4.1**
        """
        variant = data.draw(st.sampled_from(["empty", "missing", "none"]))
        if variant == "empty":
            response = {"kind": "recommendation", "reasoning_trace": []}
        elif variant == "missing":
            response = {"kind": "recommendation"}
        else:
            response = {"kind": "recommendation", "reasoning_trace": None}

        result = _reviewer._check_reference_period(response)
        assert result.verdict == "fail"
        assert result.rule == "reference_period_disclosure"

    @settings(max_examples=100)
    @given(
        grounding_tool=_grounding_tool,
        non_grounding_entries=_non_grounding_trace,
    )
    def test_full_review_with_grounding_passes_reference_check(
        self,
        grounding_tool: str,
        non_grounding_entries: list[dict],
    ) -> None:
        """Full review() passes reference-period check when grounding tool present.

        **Validates: Requirements 4.1**
        """
        trace = non_grounding_entries + [
            {"tool": grounding_tool, "summary": "grounding"}
        ]
        response = {
            "kind": "recommendation",
            "reasoning_trace": trace,
            "green": {"saving_monthly": 10.0},
            "cheapest": {"saving_monthly": 5.0},
        }
        review = _reviewer.review(response, {})
        assert "reference_period_disclosure" in review.rules_checked
        # The reference-period check should pass (grounding tool present).
        # The overall verdict depends on all checks, but reference_period
        # should not be in failures.
        ref_failures = [f for f in review.failures if "reference" in f.lower() or "reasoning_trace" in f.lower()]
        assert len(ref_failures) == 0
