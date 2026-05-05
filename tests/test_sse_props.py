"""Property-based tests for SSE formatting functions.

Feature: streaming-reasoning-trace

Uses Hypothesis for property-based testing with minimum 100 iterations per
property. Each test is tagged with the feature and property reference from
the design document.

Properties tested:
  - Property 8: SSE framing format
  - Property 9: ReasoningTraceEntry round-trip serialisation
"""
from __future__ import annotations

import json
import re

from hypothesis import given, settings
from hypothesis import strategies as st

from api_lambda.sse import format_sse_event, format_done_event


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# The four valid SSE event types defined by the wire protocol.
_EVENT_TYPES = st.sampled_from(["trace_step", "result", "error", "done"])

# Strategy: JSON-serialisable data objects (dicts with various value types).
# Covers nested structures, strings, numbers, booleans, nulls, and lists.
_json_serialisable_data = st.recursive(
    base=st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-1_000_000, max_value=1_000_000),
        st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),  # Exclude surrogates
            ),
            min_size=0,
            max_size=50,
        ),
    ),
    extend=lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=5),
        st.dictionaries(
            keys=st.text(
                alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
                min_size=1,
                max_size=20,
            ),
            values=children,
            min_size=0,
            max_size=5,
        ),
    ),
    max_leaves=15,
)


# ---------------------------------------------------------------------------
# Property 8: SSE framing format
# **Validates: Requirements 8.1**
# ---------------------------------------------------------------------------


class TestSSEFramingFormat:
    """Property 8: SSE framing format.

    Feature: streaming-reasoning-trace, Property 8: SSE framing format

    *For any* event type in {trace_step, result, error, done} and *for any*
    valid JSON-serialisable data object, the formatted SSE event SHALL match
    the pattern `event: <type>\\ndata: <json>\\n\\n` where `<json>` is a
    single-line JSON string with no embedded newlines.

    **Validates: Requirements 8.1**
    """

    @settings(max_examples=100)
    @given(event_type=_EVENT_TYPES, data=_json_serialisable_data)
    def test_sse_event_matches_framing_pattern(self, event_type: str, data) -> None:
        """The formatted SSE event matches `event: <type>\\ndata: <json>\\n\\n`.

        Feature: streaming-reasoning-trace, Property 8: SSE framing format
        **Validates: Requirements 8.1**
        """
        result = format_sse_event(event_type, data)

        # Must match the exact SSE framing pattern.
        # Pattern: "event: " + type + "\n" + "data: " + json + "\n\n"
        pattern = re.compile(
            r"^event: (?P<type>[a-z_]+)\ndata: (?P<json>.+)\n\n$",
            re.DOTALL,
        )
        match = pattern.match(result)
        assert match is not None, (
            f"SSE event does not match framing pattern.\n"
            f"  Event type: {event_type!r}\n"
            f"  Data: {data!r}\n"
            f"  Formatted: {result!r}"
        )

        # Verify the event type in the frame matches the input.
        assert match.group("type") == event_type

    @settings(max_examples=100)
    @given(event_type=_EVENT_TYPES, data=_json_serialisable_data)
    def test_data_line_is_single_line_json(self, event_type: str, data) -> None:
        """The data field is a single-line JSON string with no embedded newlines.

        Feature: streaming-reasoning-trace, Property 8: SSE framing format
        **Validates: Requirements 8.1**
        """
        result = format_sse_event(event_type, data)

        # Split into lines — the frame has exactly 3 lines:
        # line 0: "event: <type>"
        # line 1: "data: <json>"
        # line 2: "" (empty, from first trailing \n)
        # The final \n produces the second trailing newline.
        # So the full string ends with \n\n.
        assert result.endswith("\n\n"), (
            f"SSE event does not end with two newlines: {result!r}"
        )

        # Strip the trailing double-newline and split on \n.
        lines = result[:-2].split("\n")
        assert len(lines) == 2, (
            f"Expected exactly 2 lines (event + data), got {len(lines)}.\n"
            f"  Lines: {lines!r}\n"
            f"  Full result: {result!r}"
        )

        event_line, data_line = lines

        # Verify event line format.
        assert event_line == f"event: {event_type}"

        # Verify data line starts with "data: ".
        assert data_line.startswith("data: "), (
            f"Data line does not start with 'data: ': {data_line!r}"
        )

        # Extract the JSON portion and verify it has no embedded newlines.
        json_str = data_line[len("data: "):]
        assert "\n" not in json_str, (
            f"JSON string contains embedded newline: {json_str!r}"
        )
        assert "\r" not in json_str, (
            f"JSON string contains embedded carriage return: {json_str!r}"
        )

        # Verify the JSON is valid and round-trips correctly.
        parsed = json.loads(json_str)
        # Re-serialise and compare to ensure compact format.
        re_serialised = json.dumps(parsed, separators=(",", ":"))
        assert json_str == re_serialised, (
            f"JSON is not in compact format.\n"
            f"  Got:      {json_str!r}\n"
            f"  Expected: {re_serialised!r}"
        )

    @settings(max_examples=100)
    @given(event_type=_EVENT_TYPES, data=_json_serialisable_data)
    def test_sse_event_ends_with_double_newline(self, event_type: str, data) -> None:
        """Every SSE event ends with exactly two newlines (frame terminator).

        Feature: streaming-reasoning-trace, Property 8: SSE framing format
        **Validates: Requirements 8.1**
        """
        result = format_sse_event(event_type, data)

        # Must end with \n\n (SSE frame terminator).
        assert result.endswith("\n\n"), (
            f"SSE event does not end with '\\n\\n': {result!r}"
        )

        # Must NOT end with \n\n\n (no extra trailing newline).
        assert not result.endswith("\n\n\n"), (
            f"SSE event has extra trailing newline: {result!r}"
        )

    def test_format_done_event_matches_framing_pattern(self) -> None:
        """format_done_event() produces the exact expected SSE frame.

        Feature: streaming-reasoning-trace, Property 8: SSE framing format
        **Validates: Requirements 8.1**
        """
        result = format_done_event()

        # Must be exactly: "event: done\ndata: {}\n\n"
        expected = "event: done\ndata: {}\n\n"
        assert result == expected, (
            f"format_done_event() output mismatch.\n"
            f"  Expected: {expected!r}\n"
            f"  Got:      {result!r}"
        )

    @settings(max_examples=100)
    @given(data=_json_serialisable_data)
    def test_format_done_event_equivalent_to_format_sse_event(self, data) -> None:
        """format_done_event() is equivalent to format_sse_event('done', {}).

        Feature: streaming-reasoning-trace, Property 8: SSE framing format
        **Validates: Requirements 8.1**
        """
        done_result = format_done_event()
        sse_result = format_sse_event("done", {})

        assert done_result == sse_result, (
            f"format_done_event() != format_sse_event('done', {{}}).\n"
            f"  done_result: {done_result!r}\n"
            f"  sse_result:  {sse_result!r}"
        )


# ---------------------------------------------------------------------------
# Strategies for Property 9
# ---------------------------------------------------------------------------

# Strategy: arbitrary strings suitable for ReasoningTraceEntry fields.
# Excludes surrogate characters (which cannot round-trip through JSON).
_arbitrary_strings = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=0,
    max_size=100,
)


# ---------------------------------------------------------------------------
# Property 9: ReasoningTraceEntry round-trip serialisation
# **Validates: Requirements 8.4**
# ---------------------------------------------------------------------------


class TestReasoningTraceEntryRoundTrip:
    """Property 9: ReasoningTraceEntry round-trip serialisation.

    Feature: streaming-reasoning-trace, Property 9: ReasoningTraceEntry round-trip serialisation

    *For any* valid ReasoningTraceEntry object (with arbitrary tool string and
    summary string), serialising it to a trace_step SSE event and then parsing
    the SSE event back SHALL produce an equivalent ReasoningTraceEntry object.

    **Validates: Requirements 8.4**
    """

    @settings(max_examples=100)
    @given(tool=_arbitrary_strings, summary=_arbitrary_strings)
    def test_round_trip_produces_equivalent_entry(self, tool: str, summary: str) -> None:
        """Serialising a ReasoningTraceEntry to SSE and parsing back yields the original.

        Feature: streaming-reasoning-trace, Property 9: ReasoningTraceEntry round-trip serialisation
        **Validates: Requirements 8.4**
        """
        # 1. Create a ReasoningTraceEntry-like dict
        original = {"tool": tool, "summary": summary}

        # 2. Format as a trace_step SSE event
        sse_frame = format_sse_event("trace_step", original)

        # 3. Parse the SSE event back
        lines = sse_frame.split("\n")
        # Frame structure: "event: trace_step", "data: <json>", "", ""
        data_line = lines[1]
        assert data_line.startswith("data: "), (
            f"Expected data line to start with 'data: ', got: {data_line!r}"
        )
        json_str = data_line[len("data: "):]
        parsed = json.loads(json_str)

        # 4. Verify the parsed data matches the original
        assert parsed == original, (
            f"Round-trip mismatch.\n"
            f"  Original: {original!r}\n"
            f"  Parsed:   {parsed!r}"
        )

    @settings(max_examples=100)
    @given(tool=_arbitrary_strings, summary=_arbitrary_strings)
    def test_round_trip_preserves_both_fields(self, tool: str, summary: str) -> None:
        """The parsed entry has exactly the 'tool' and 'summary' fields.

        Feature: streaming-reasoning-trace, Property 9: ReasoningTraceEntry round-trip serialisation
        **Validates: Requirements 8.4**
        """
        original = {"tool": tool, "summary": summary}
        sse_frame = format_sse_event("trace_step", original)

        # Parse back
        lines = sse_frame.split("\n")
        json_str = lines[1][len("data: "):]
        parsed = json.loads(json_str)

        # Verify both fields are present and correct
        assert "tool" in parsed, f"Missing 'tool' field in parsed: {parsed!r}"
        assert "summary" in parsed, f"Missing 'summary' field in parsed: {parsed!r}"
        assert parsed["tool"] == tool
        assert parsed["summary"] == summary
        # No extra fields introduced
        assert set(parsed.keys()) == {"tool", "summary"}, (
            f"Unexpected keys in parsed entry: {set(parsed.keys())}"
        )

    @settings(max_examples=100)
    @given(tool=_arbitrary_strings, summary=_arbitrary_strings)
    def test_round_trip_event_type_is_trace_step(self, tool: str, summary: str) -> None:
        """The SSE event type line is always 'event: trace_step'.

        Feature: streaming-reasoning-trace, Property 9: ReasoningTraceEntry round-trip serialisation
        **Validates: Requirements 8.4**
        """
        original = {"tool": tool, "summary": summary}
        sse_frame = format_sse_event("trace_step", original)

        # Parse the event type line
        lines = sse_frame.split("\n")
        event_line = lines[0]
        assert event_line == "event: trace_step", (
            f"Expected 'event: trace_step', got: {event_line!r}"
        )
