"""Phase 13 Plan 02 Task 2.3 — tests for ReasoningTraceEntry schema + extractor.

Covers the 7-case behavior block in 13-02-PLAN.md Task 2.3:

- Test 1: ReasoningTraceEntry with digits/$/dates validates cleanly (D-11 counter).
- Test 2: RecommendationResponse default reasoning_trace == [].
- Test 3: RecommendationResponse preserves a supplied reasoning_trace list.
- Test 4: _extract_reasoning_trace(None) -> [].
- Test 5: _extract_reasoning_trace on agent_result with message=None -> [].
- Test 6: 3-pair synthesised AgentResult -> 3 ordered entries preserving iteration order.
- Test 7: Unknown tool names (not in _TRACE_TOOLS) are skipped.

Note: a dedicated D-11 exemption class is added by Task 2.4 to
tests/test_schema.py; this file covers the extractor contract + the minimum
schema-level assertions needed to drive the Task 2.3 RED/GREEN cycle.
"""
import json
from types import SimpleNamespace

import pytest


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

_TRACK_GREEN_INPUT = dict(
    plan_id="ECO",
    plan_name="EcoFlex 100",
    saving_monthly=14.00,
    saving_annual=168.00,
    usage_narrative="Cool-season usage with stable monthly pattern.",
    call_script="Ask about EcoFlex for winter comfort and savings.",
)

_TRACK_CHEAPEST_INPUT = dict(
    plan_id="VAL",
    plan_name="Value 12",
    saving_monthly=25.67,
    saving_annual=308.04,
    usage_narrative="Lowest-cost option for households on a tight budget.",
    call_script="Frame Value 12 as the budget-safe choice today.",
)


def _fake_agent_result(content_blocks: list) -> SimpleNamespace:
    """Build a minimal agent_result with a .message attribute matching Strands shape.

    The real `strands.agent.agent_result.AgentResult` has `message` typed as a
    `Message` TypedDict with `role` + `content` keys. The extractor only reads
    .message.get("content", []) so we supply that via a plain dict.
    """
    return SimpleNamespace(message={"role": "assistant", "content": content_blocks})


# ----------------------------------------------------------------------------
# Schema contract tests
# ----------------------------------------------------------------------------


class TestReasoningTraceEntrySchema:
    """Task 2.3 Tests 1-3: schema shape + REC-03 preservation."""

    def test_1_entry_with_dollars_digits_and_dates_validates(self):
        # Phase 13 D-11 — this string would FAIL D-15 narrative validators.
        # On ReasoningTraceEntry.summary it must pass unchanged.
        from agent.agent import ReasoningTraceEntry

        entry = ReasoningTraceEntry(
            tool="detect_bill_shock",
            summary="Bill shock detected: +$47.00 2025-10 vs 11-month avg ($135.00 vs $88.00)",
        )
        assert entry.tool == "detect_bill_shock"
        assert "$47.00" in entry.summary
        assert "2025-10" in entry.summary

    def test_2_default_reasoning_trace_is_empty_list(self):
        from agent.agent import RecommendationResponse

        resp = RecommendationResponse(
            green=_TRACK_GREEN_INPUT,
            cheapest=_TRACK_CHEAPEST_INPUT,
        )
        assert resp.reasoning_trace == []

    def test_3_supplied_reasoning_trace_is_preserved(self):
        from agent.agent import ReasoningTraceEntry, RecommendationResponse

        trace = [
            ReasoningTraceEntry(tool="detect_bill_shock", summary="x"),
            ReasoningTraceEntry(tool="simulate_savings", summary="y"),
        ]
        resp = RecommendationResponse(
            green=_TRACK_GREEN_INPUT,
            cheapest=_TRACK_CHEAPEST_INPUT,
            reasoning_trace=trace,
        )
        assert len(resp.reasoning_trace) == 2
        assert resp.reasoning_trace[0].tool == "detect_bill_shock"
        assert resp.reasoning_trace[1].tool == "simulate_savings"


# ----------------------------------------------------------------------------
# Extractor contract tests (D-08)
# ----------------------------------------------------------------------------


class TestExtractReasoningTrace:
    """Task 2.3 Tests 4-7: _extract_reasoning_trace contract.

    D-08: the extractor never raises. Returns [] on any failure.
    """

    def test_4_none_agent_result_returns_empty_list(self):
        from agent.agent import _extract_reasoning_trace

        assert _extract_reasoning_trace(None) == []

    def test_5_agent_result_with_message_none_returns_empty_list(self):
        from agent.agent import _extract_reasoning_trace

        ar = SimpleNamespace(message=None)
        assert _extract_reasoning_trace(ar) == []

    def test_6_three_paired_tool_calls_return_three_ordered_entries(self):
        from agent.agent import _extract_reasoning_trace

        # Three toolUse blocks followed by three toolResult blocks,
        # matched by toolUseId. Trace tools: get_hardship_flag,
        # detect_bill_shock, simulate_savings (iteration-order preserved).
        content = [
            {"toolUse": {
                "name": "get_hardship_flag",
                "toolUseId": "tu-1",
                "input": {"customer_id": "CUST-003"},
            }},
            {"toolUse": {
                "name": "detect_bill_shock",
                "toolUseId": "tu-2",
                "input": {"customer_id": "CUST-003"},
            }},
            {"toolUse": {
                "name": "simulate_savings",
                "toolUseId": "tu-3",
                "input": {"customer_id": "CUST-003"},
            }},
            {"toolResult": {
                "toolUseId": "tu-1",
                "status": "success",
                "content": [{"json": {"hardship_flag": False, "customer_id": "CUST-003"}}],
            }},
            {"toolResult": {
                "toolUseId": "tu-2",
                "status": "success",
                "content": [{"json": {
                    "is_shock": True,
                    "delta_dollars": 65.16,
                    "shock_month": "2025-10",
                    "mean_dollars": 102.72,
                    "current_dollars": 167.88,
                }}],
            }},
            {"toolResult": {
                "toolUseId": "tu-3",
                "status": "success",
                "content": [{"json": {
                    "green": {"saving_monthly": 14.0, "saving_annual": 168.0,
                              "plan_id": "ECO", "plan_name": "EcoFlex 100"},
                    "cheapest": {"saving_monthly": 25.67, "saving_annual": 308.04,
                                 "plan_id": "VAL", "plan_name": "Value 12"},
                }}],
            }},
        ]
        entries = _extract_reasoning_trace(_fake_agent_result(content))
        assert len(entries) == 3
        assert [e.tool for e in entries] == [
            "get_hardship_flag",
            "detect_bill_shock",
            "simulate_savings",
        ]
        # Spot-check summaries are non-empty + code-composed.
        assert "hardship_flag=False" in entries[0].summary
        assert "Bill shock detected" in entries[1].summary
        assert "+$65.16" in entries[1].summary
        assert "2025-10" in entries[1].summary
        assert "Green $14.00/mo" in entries[2].summary
        assert "Cheapest $25.67/mo" in entries[2].summary

    def test_7_unknown_tool_names_are_skipped(self):
        from agent.agent import _extract_reasoning_trace

        content = [
            {"toolUse": {"name": "unknown_tool", "toolUseId": "tu-x", "input": {}}},
            {"toolUse": {"name": "simulate_savings", "toolUseId": "tu-y", "input": {}}},
            {"toolResult": {
                "toolUseId": "tu-x",
                "status": "success",
                "content": [{"json": {"foo": "bar"}}],
            }},
            {"toolResult": {
                "toolUseId": "tu-y",
                "status": "success",
                "content": [{"json": {
                    "green": {"saving_monthly": 30.0},
                    "cheapest": {"saving_monthly": 55.0},
                }}],
            }},
        ]
        entries = _extract_reasoning_trace(_fake_agent_result(content))
        assert len(entries) == 1
        assert entries[0].tool == "simulate_savings"

    def test_malformed_content_does_not_raise(self):
        # D-08 safety: the extractor must never raise. Throw garbage at it.
        from agent.agent import _extract_reasoning_trace

        ar = SimpleNamespace(message={"role": "assistant", "content": [
            None,
            "string-not-a-dict",
            {"toolUse": None},
            {"toolUse": {"name": "simulate_savings", "toolUseId": None}},  # missing match
            {"toolResult": {"toolUseId": "x"}},  # missing content
        ]})
        assert _extract_reasoning_trace(ar) == []

    def test_text_content_json_loads_fallback(self):
        # Strands 1.37 may emit `text` blocks instead of `json`.
        # The extractor falls back to json.loads(text).
        from agent.agent import _extract_reasoning_trace

        content = [
            {"toolUse": {"name": "simulate_savings", "toolUseId": "tu-1", "input": {}}},
            {"toolResult": {
                "toolUseId": "tu-1",
                "status": "success",
                "content": [{"text": json.dumps({
                    "green": {"saving_monthly": 30.0},
                    "cheapest": {"saving_monthly": 55.0},
                })}],
            }},
        ]
        entries = _extract_reasoning_trace(_fake_agent_result(content))
        assert len(entries) == 1
        assert entries[0].tool == "simulate_savings"
        assert "Green $30.00/mo" in entries[0].summary
        assert "Cheapest $55.00/mo" in entries[0].summary
