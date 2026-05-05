"""Property-based tests for streaming handler in api_lambda/handler.py.

Feature: streaming-reasoning-trace

Uses Hypothesis for property-based testing with minimum 100 iterations per
property. Each test is tagged with the feature and property reference from
the design document.

Properties tested:
  - Property 1: Customer ID validation rejects all non-matching inputs
  - Property 2: Session ID uniqueness across invocations
  - Property 3: _narrative_source is never exposed to the client
  - Property 4: Every stream terminates with exactly one done event
"""
from __future__ import annotations

import json
import uuid
from io import BytesIO
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError, ReadTimeoutError

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from api_lambda.handler import _stream_handler, _CUSTOMER_ID_PATTERN


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy: random strings that do NOT match ^CUST-\d{3,6}$
# Combines multiple approaches to generate invalid customer IDs:
# 1. Random ASCII text
# 2. Random unicode text
# 3. Partial matches (close but not valid)
# 4. Empty strings
# 5. Near-miss variants

_partial_matches = st.sampled_from([
    "",                        # empty
    "CUST-",                   # prefix only, no digits
    "CUST-12",                 # too few digits (2)
    "CUST-1234567",            # too many digits (7)
    "CUST-12345678",           # too many digits (8)
    "cust-123",                # wrong case
    "CUST123",                 # missing hyphen
    "CUST_123",                # underscore instead of hyphen
    "CUST-abc",                # letters instead of digits
    "CUST-12a",                # mixed letters and digits
    "CUST-123 ",               # trailing space
    " CUST-123",               # leading space
    "CUST-123\n",              # trailing newline
    "CUSTOMER-123",            # wrong prefix
    "CUS-123",                 # truncated prefix
    "CUST-0",                  # single digit
    "CUST-00",                 # two digits
    "CUST--123",               # double hyphen
    "PREFIX-CUST-123",         # extra prefix
    "CUST-123-SUFFIX",         # extra suffix
    "CUST-123456EXTRA",        # valid digits + trailing chars
    "xCUST-123",               # leading char
    "CUST-1234567890",         # way too many digits
])

_random_ascii = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
    min_size=0,
    max_size=50,
)

_random_unicode = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),  # Exclude surrogates
    min_size=0,
    max_size=50,
)

# Combined strategy for invalid customer IDs
_invalid_customer_id = st.one_of(
    _partial_matches,
    _random_ascii,
    _random_unicode,
).filter(lambda s: not _CUSTOMER_ID_PATTERN.match(s))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_streaming_event(customer_id: str) -> dict:
    """Build a Lambda Function URL event with the given customer_id."""
    return {
        "pathParameters": {"customer_id": customer_id},
        "rawPath": f"/recommendations/{customer_id}",
        "headers": {"accept": "text/event-stream"},
        "queryStringParameters": {},
    }


class _MockResponseStream:
    """Mock response_stream that captures .write(bytes) calls."""

    def __init__(self):
        self.chunks: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.chunks.append(data)

    @property
    def written(self) -> bytes:
        return b"".join(self.chunks)

    @property
    def written_str(self) -> str:
        return self.written.decode("utf-8")


# ---------------------------------------------------------------------------
# Property 1: Customer ID validation rejects all non-matching inputs
# **Validates: Requirements 1.3**
# ---------------------------------------------------------------------------


class TestCustomerIDValidationStreaming:
    """Property 1: Customer ID validation rejects all non-matching inputs.

    Feature: streaming-reasoning-trace, Property 1: Customer ID validation rejects all non-matching inputs

    *For any* string that does not match the pattern ^CUST-\\d{3,6}$, the
    streaming handler SHALL return an error (HTTP 400) and SHALL NOT initiate
    an AgentCore invocation.

    **Validates: Requirements 1.3**
    """

    @settings(max_examples=100)
    @given(customer_id=_invalid_customer_id)
    @patch("api_lambda.handler._agentcore_client")
    @patch("api_lambda.handler._get_streaming_trace_hook")
    def test_invalid_customer_id_returns_400(
        self, mock_hook, mock_client, customer_id: str
    ) -> None:
        """For any invalid customer_id, the streaming handler returns HTTP 400.

        Feature: streaming-reasoning-trace, Property 1: Customer ID validation rejects all non-matching inputs
        **Validates: Requirements 1.3**
        """
        assume(not _CUSTOMER_ID_PATTERN.match(customer_id))

        event = _make_streaming_event(customer_id)
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        # Parse the response written to the stream.
        response = json.loads(response_stream.written_str)

        # Must be HTTP 400.
        assert response["statusCode"] == 400, (
            f"Expected statusCode 400 for invalid customer_id {customer_id!r}, "
            f"got {response['statusCode']}"
        )

    @settings(max_examples=100)
    @given(customer_id=_invalid_customer_id)
    @patch("api_lambda.handler._agentcore_client")
    @patch("api_lambda.handler._get_streaming_trace_hook")
    def test_invalid_customer_id_does_not_invoke_agentcore(
        self, mock_hook, mock_client, customer_id: str
    ) -> None:
        """For any invalid customer_id, AgentCore is NOT invoked.

        Feature: streaming-reasoning-trace, Property 1: Customer ID validation rejects all non-matching inputs
        **Validates: Requirements 1.3**
        """
        assume(not _CUSTOMER_ID_PATTERN.match(customer_id))

        event = _make_streaming_event(customer_id)
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        # AgentCore client must NOT have been called.
        mock_client.invoke_agent_runtime.assert_not_called()

    @settings(max_examples=100)
    @given(customer_id=_invalid_customer_id)
    @patch("api_lambda.handler._agentcore_client")
    @patch("api_lambda.handler._get_streaming_trace_hook")
    def test_invalid_customer_id_error_body_contains_message(
        self, mock_hook, mock_client, customer_id: str
    ) -> None:
        """For any invalid customer_id, the error body contains a descriptive message.

        Feature: streaming-reasoning-trace, Property 1: Customer ID validation rejects all non-matching inputs
        **Validates: Requirements 1.3**
        """
        assume(not _CUSTOMER_ID_PATTERN.match(customer_id))

        event = _make_streaming_event(customer_id)
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        # Parse the response.
        response = json.loads(response_stream.written_str)

        # The body should contain a JSON error message.
        body = json.loads(response["body"])
        assert "error" in body, (
            f"Expected 'error' key in response body for invalid customer_id "
            f"{customer_id!r}, got: {body}"
        )
        assert isinstance(body["error"], str) and len(body["error"]) > 0, (
            f"Expected non-empty error message string, got: {body['error']!r}"
        )


# ---------------------------------------------------------------------------
# Property 2: Session ID uniqueness across invocations
# **Validates: Requirements 1.4**
# ---------------------------------------------------------------------------


class TestSessionIDUniqueness:
    """Property 2: Session ID uniqueness across invocations.

    Feature: streaming-reasoning-trace, Property 2: Session ID uniqueness across invocations

    *For any* N sequential streaming invocations, all N generated
    runtimeSessionId values SHALL be distinct valid uuid4 strings.

    **Validates: Requirements 1.4**
    """

    @settings(max_examples=100)
    @given(n=st.integers(min_value=2, max_value=20))
    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_all_session_ids_are_distinct(
        self, mock_client, mock_hook_fn, n: int
    ) -> None:
        """For any N invocations, all N runtimeSessionId values are distinct.

        Feature: streaming-reasoning-trace, Property 2: Session ID uniqueness across invocations
        **Validates: Requirements 1.4**
        """
        # Set up mock hook
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        # Set up mock AgentCore client to return a valid recommendation response
        mock_response_body = json.dumps({
            "kind": "recommendation",
            "green": {"plan_id": "ECO", "plan_name": "EcoFlex", "saving_monthly": 30.0},
            "cheapest": {"plan_id": "VAL", "plan_name": "Value", "saving_monthly": 55.0},
        }).encode()

        # Capture all runtimeSessionId values passed to invoke_agent_runtime
        captured_session_ids: list[str] = []

        def _capture_invoke(**kwargs):
            captured_session_ids.append(kwargs["runtimeSessionId"])
            return {"response": BytesIO(mock_response_body)}

        mock_client.invoke_agent_runtime.side_effect = _capture_invoke

        # Use a valid customer ID for all invocations
        customer_id = "CUST-001"
        event = _make_streaming_event(customer_id)
        context = MagicMock()

        # Invoke _stream_handler N times sequentially
        for _ in range(n):
            response_stream = _MockResponseStream()
            _stream_handler(event, response_stream, context)

        # All N session IDs must be captured
        assert len(captured_session_ids) == n, (
            f"Expected {n} invocations, got {len(captured_session_ids)}"
        )

        # All session IDs must be distinct
        unique_ids = set(captured_session_ids)
        assert len(unique_ids) == n, (
            f"Expected {n} distinct session IDs, got {len(unique_ids)}. "
            f"Duplicates found: {[sid for sid in captured_session_ids if captured_session_ids.count(sid) > 1]}"
        )

    @settings(max_examples=100)
    @given(n=st.integers(min_value=2, max_value=20))
    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_all_session_ids_are_valid_uuid4(
        self, mock_client, mock_hook_fn, n: int
    ) -> None:
        """For any N invocations, all runtimeSessionId values are valid uuid4 strings.

        Feature: streaming-reasoning-trace, Property 2: Session ID uniqueness across invocations
        **Validates: Requirements 1.4**
        """
        # Set up mock hook
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        # Set up mock AgentCore client to return a valid recommendation response
        mock_response_body = json.dumps({
            "kind": "recommendation",
            "green": {"plan_id": "ECO", "plan_name": "EcoFlex", "saving_monthly": 30.0},
            "cheapest": {"plan_id": "VAL", "plan_name": "Value", "saving_monthly": 55.0},
        }).encode()

        # Capture all runtimeSessionId values passed to invoke_agent_runtime
        captured_session_ids: list[str] = []

        def _capture_invoke(**kwargs):
            captured_session_ids.append(kwargs["runtimeSessionId"])
            return {"response": BytesIO(mock_response_body)}

        mock_client.invoke_agent_runtime.side_effect = _capture_invoke

        # Use a valid customer ID for all invocations
        customer_id = "CUST-001"
        event = _make_streaming_event(customer_id)
        context = MagicMock()

        # Invoke _stream_handler N times sequentially
        for _ in range(n):
            response_stream = _MockResponseStream()
            _stream_handler(event, response_stream, context)

        # All session IDs must be valid uuid4 strings
        for session_id in captured_session_ids:
            # Must be a string
            assert isinstance(session_id, str), (
                f"Expected session_id to be a string, got {type(session_id)}"
            )
            # Must parse as a valid UUID
            try:
                parsed = uuid.UUID(session_id)
            except ValueError:
                raise AssertionError(
                    f"Session ID {session_id!r} is not a valid UUID string"
                )
            # Must be version 4
            assert parsed.version == 4, (
                f"Session ID {session_id!r} is UUID version {parsed.version}, expected 4"
            )


# ---------------------------------------------------------------------------
# Property 3: _narrative_source is never exposed to the client
# **Validates: Requirements 2.3, 4.1**
# ---------------------------------------------------------------------------

# Strategy: random dicts that simulate agent response payloads.
# Always include `green` and `cheapest` keys (to avoid triggering the 404 path).
# Randomly include or exclude `_narrative_source` with arbitrary values.

_narrative_source_values = st.one_of(
    st.none(),
    st.text(min_size=0, max_size=50),
    st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.text(min_size=0, max_size=30),
        min_size=0,
        max_size=5,
    ),
    st.booleans(),
    st.integers(),
    st.lists(st.text(min_size=0, max_size=10), max_size=3),
)

# Strategy for a valid recommendation body that includes green + cheapest.
# plan_id must NOT be "UNKNOWN" (handler's D-13.1-13 sentinel triggers 404).
_safe_plan_id = st.text(min_size=1, max_size=10).filter(lambda s: s != "UNKNOWN")

_valid_recommendation_body = st.fixed_dictionaries({
    "kind": st.just("recommendation"),
    "green": st.fixed_dictionaries({
        "plan_id": _safe_plan_id,
        "plan_name": st.text(min_size=1, max_size=30),
        "saving_monthly": st.floats(min_value=0.01, max_value=999.99, allow_nan=False, allow_infinity=False),
    }),
    "cheapest": st.fixed_dictionaries({
        "plan_id": _safe_plan_id,
        "plan_name": st.text(min_size=1, max_size=30),
        "saving_monthly": st.floats(min_value=0.01, max_value=999.99, allow_nan=False, allow_infinity=False),
    }),
})


def _parse_sse_events(raw: str) -> list[tuple[str, dict]]:
    """Parse SSE frames from raw response stream output.

    Returns a list of (event_type, data_dict) tuples.
    """
    events = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_type = None
        data_str = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: "):]
            elif line.startswith("data: "):
                data_str = line[len("data: "):]
        if event_type and data_str is not None:
            events.append((event_type, json.loads(data_str)))
    return events


class TestNarrativeSourceStripping:
    """Property 3: _narrative_source is never exposed to the client.

    Feature: streaming-reasoning-trace, Property 3: _narrative_source is never exposed to the client

    *For any* agent response payload that contains a `_narrative_source` key,
    the `result` SSE event emitted to the client SHALL NOT contain that key.

    **Validates: Requirements 2.3, 4.1**
    """

    @settings(max_examples=100)
    @given(
        body=_valid_recommendation_body,
        narrative_source=_narrative_source_values,
    )
    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_narrative_source_stripped_from_result_event(
        self, mock_client, mock_hook_fn, body: dict, narrative_source
    ) -> None:
        """For any agent response with _narrative_source, the result SSE event omits it.

        Feature: streaming-reasoning-trace, Property 3: _narrative_source is never exposed to the client
        **Validates: Requirements 2.3, 4.1**
        """
        # Set up mock hook
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        # Build the agent response body with _narrative_source injected
        agent_body = dict(body)
        agent_body["_narrative_source"] = narrative_source

        mock_response_bytes = json.dumps(agent_body).encode()

        def _mock_invoke(**kwargs):
            return {"response": BytesIO(mock_response_bytes)}

        mock_client.invoke_agent_runtime.side_effect = _mock_invoke

        # Use a valid customer ID
        event = _make_streaming_event("CUST-001")
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        # Parse SSE events from the response stream
        sse_events = _parse_sse_events(response_stream.written_str)

        # Find the result event
        result_events = [(etype, data) for etype, data in sse_events if etype == "result"]
        assert len(result_events) == 1, (
            f"Expected exactly 1 result event, got {len(result_events)}"
        )

        _, result_data = result_events[0]

        # The _narrative_source key MUST NOT be present in the result event
        assert "_narrative_source" not in result_data, (
            f"_narrative_source was exposed to the client in the result event. "
            f"Value: {result_data.get('_narrative_source')!r}"
        )

    @settings(max_examples=100)
    @given(body=_valid_recommendation_body)
    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_narrative_source_stripped_even_when_absent(
        self, mock_client, mock_hook_fn, body: dict
    ) -> None:
        """For any agent response WITHOUT _narrative_source, the result event still works.

        Feature: streaming-reasoning-trace, Property 3: _narrative_source is never exposed to the client
        **Validates: Requirements 2.3, 4.1**
        """
        # Set up mock hook
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        # Build the agent response body WITHOUT _narrative_source
        agent_body = dict(body)
        # Ensure _narrative_source is NOT present
        agent_body.pop("_narrative_source", None)

        mock_response_bytes = json.dumps(agent_body).encode()

        def _mock_invoke(**kwargs):
            return {"response": BytesIO(mock_response_bytes)}

        mock_client.invoke_agent_runtime.side_effect = _mock_invoke

        # Use a valid customer ID
        event = _make_streaming_event("CUST-001")
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        # Parse SSE events from the response stream
        sse_events = _parse_sse_events(response_stream.written_str)

        # Find the result event
        result_events = [(etype, data) for etype, data in sse_events if etype == "result"]
        assert len(result_events) == 1, (
            f"Expected exactly 1 result event, got {len(result_events)}"
        )

        _, result_data = result_events[0]

        # The _narrative_source key MUST NOT be present in the result event
        assert "_narrative_source" not in result_data, (
            f"_narrative_source was unexpectedly present in the result event "
            f"even though it was not in the agent response."
        )


# ---------------------------------------------------------------------------
# Property 4: Every stream terminates with exactly one done event
# **Validates: Requirements 2.5, 4.4**
# ---------------------------------------------------------------------------

# Strategy: randomly select between different streaming scenarios.
# Each scenario simulates a different outcome from the AgentCore invocation:
# - "success": valid recommendation response
# - "customer_not_found": response missing green/cheapest (triggers 404 error event)
# - "read_timeout": ReadTimeoutError from AgentCore (triggers 504 error event)
# - "client_error": ClientError from AgentCore (triggers 502 error event)
# - "generic_exception": unexpected Exception (triggers 500 error event)

_streaming_scenario = st.sampled_from([
    "success",
    "customer_not_found",
    "read_timeout",
    "client_error",
    "generic_exception",
])


class TestDoneEventTermination:
    """Property 4: Every stream terminates with exactly one done event.

    Feature: streaming-reasoning-trace, Property 4: Every stream terminates with exactly one done event

    *For any* streaming invocation (whether the agent succeeds, fails, times out,
    or hits the D-04 fallback), the event sequence SHALL end with exactly one
    `done` event and no events SHALL follow it.

    **Validates: Requirements 2.5, 4.4**
    """

    def _configure_mock_for_scenario(self, mock_client, scenario: str) -> None:
        """Configure the mock AgentCore client for the given scenario."""
        if scenario == "success":
            # Valid recommendation response with both tracks
            body = json.dumps({
                "kind": "recommendation",
                "green": {"plan_id": "ECO", "plan_name": "EcoFlex 100", "saving_monthly": 30.0},
                "cheapest": {"plan_id": "VAL", "plan_name": "Value 12", "saving_monthly": 55.0},
                "reasoning_trace": [{"tool": "detect_bill_shock", "summary": "Bill shock detected"}],
            }).encode()
            mock_client.invoke_agent_runtime.side_effect = (
                lambda **kwargs: {"response": BytesIO(body)}
            )

        elif scenario == "customer_not_found":
            # Response missing green/cheapest — triggers customer-not-found 404
            body = json.dumps({
                "errorMessage": "No billing data found for customer",
            }).encode()
            mock_client.invoke_agent_runtime.side_effect = (
                lambda **kwargs: {"response": BytesIO(body)}
            )

        elif scenario == "read_timeout":
            # ReadTimeoutError — triggers 504 error event
            mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(
                endpoint_url="https://bedrock-agentcore.us-east-1.amazonaws.com"
            )

        elif scenario == "client_error":
            # ClientError — triggers 502 error event
            mock_client.invoke_agent_runtime.side_effect = ClientError(
                error_response={"Error": {"Code": "ServiceException", "Message": "Service unavailable"}},
                operation_name="InvokeAgentRuntime",
            )

        elif scenario == "generic_exception":
            # Generic Exception — triggers 500 error event (D-04 fallback)
            mock_client.invoke_agent_runtime.side_effect = RuntimeError(
                "Unexpected internal failure"
            )

    @settings(max_examples=100)
    @given(scenario=_streaming_scenario)
    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_stream_ends_with_exactly_one_done_event(
        self, mock_client, mock_hook_fn, scenario: str
    ) -> None:
        """For any scenario, the stream ends with exactly one done event.

        Feature: streaming-reasoning-trace, Property 4: Every stream terminates with exactly one done event
        **Validates: Requirements 2.5, 4.4**
        """
        # Set up mock hook
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        # Configure mock for the randomly selected scenario
        self._configure_mock_for_scenario(mock_client, scenario)

        # Use a valid customer ID
        event = _make_streaming_event("CUST-001")
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        # Parse SSE events from the response stream
        sse_events = _parse_sse_events(response_stream.written_str)

        # There must be at least one event (the done event)
        assert len(sse_events) >= 1, (
            f"Expected at least 1 SSE event (done), got {len(sse_events)} "
            f"for scenario {scenario!r}"
        )

        # Count done events
        done_events = [(etype, data) for etype, data in sse_events if etype == "done"]
        assert len(done_events) == 1, (
            f"Expected exactly 1 done event, got {len(done_events)} "
            f"for scenario {scenario!r}. All events: {[e[0] for e in sse_events]}"
        )

    @settings(max_examples=100)
    @given(scenario=_streaming_scenario)
    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_done_event_is_last_in_stream(
        self, mock_client, mock_hook_fn, scenario: str
    ) -> None:
        """For any scenario, the done event is the last event — nothing follows it.

        Feature: streaming-reasoning-trace, Property 4: Every stream terminates with exactly one done event
        **Validates: Requirements 2.5, 4.4**
        """
        # Set up mock hook
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        # Configure mock for the randomly selected scenario
        self._configure_mock_for_scenario(mock_client, scenario)

        # Use a valid customer ID
        event = _make_streaming_event("CUST-001")
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        # Parse SSE events from the response stream
        sse_events = _parse_sse_events(response_stream.written_str)

        # The last event must be a done event
        last_event_type, last_event_data = sse_events[-1]
        assert last_event_type == "done", (
            f"Expected last event to be 'done', got '{last_event_type}' "
            f"for scenario {scenario!r}. All events: {[e[0] for e in sse_events]}"
        )

        # No events after the done event (verified by checking done is at the end)
        done_index = next(
            i for i, (etype, _) in enumerate(sse_events) if etype == "done"
        )
        assert done_index == len(sse_events) - 1, (
            f"Done event at index {done_index} but there are {len(sse_events)} events. "
            f"Events after done: {[e[0] for e in sse_events[done_index + 1:]]} "
            f"for scenario {scenario!r}"
        )

    @settings(max_examples=100)
    @given(scenario=_streaming_scenario)
    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_done_event_has_empty_data(
        self, mock_client, mock_hook_fn, scenario: str
    ) -> None:
        """For any scenario, the done event data is an empty object {}.

        Feature: streaming-reasoning-trace, Property 4: Every stream terminates with exactly one done event
        **Validates: Requirements 2.5, 4.4**
        """
        # Set up mock hook
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        # Configure mock for the randomly selected scenario
        self._configure_mock_for_scenario(mock_client, scenario)

        # Use a valid customer ID
        event = _make_streaming_event("CUST-001")
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        # Parse SSE events from the response stream
        sse_events = _parse_sse_events(response_stream.written_str)

        # Find the done event and verify its data is {}
        done_events = [(etype, data) for etype, data in sse_events if etype == "done"]
        assert len(done_events) == 1, (
            f"Expected exactly 1 done event, got {len(done_events)} "
            f"for scenario {scenario!r}"
        )

        _, done_data = done_events[0]
        assert done_data == {}, (
            f"Expected done event data to be {{}}, got {done_data!r} "
            f"for scenario {scenario!r}"
        )


# ---------------------------------------------------------------------------
# Property 7: REC-03 preserved in streaming result events
# **Validates: Requirements 4.2**
# ---------------------------------------------------------------------------

# Strategy: Random RecommendationResponse payloads with varying track data.
# Both green and cheapest tracks are always present in the agent response
# (the handler must preserve them in the result event).

_rec03_plan_name = st.text(min_size=1, max_size=40)
_rec03_saving = st.floats(min_value=0.01, max_value=9999.99, allow_nan=False, allow_infinity=False)

# Additional optional fields that may appear on track objects
_rec03_extra_fields = st.fixed_dictionaries(
    {},
    optional={
        "annual_saving": st.floats(min_value=0.01, max_value=99999.99, allow_nan=False, allow_infinity=False),
        "rate_type": st.sampled_from(["flat", "tou", "demand", "solar_feed_in"]),
        "contract_months": st.integers(min_value=1, max_value=36),
        "provider": st.text(min_size=1, max_size=30),
    },
)

_rec03_track = st.builds(
    lambda plan_id, plan_name, saving, extras: {
        "plan_id": plan_id,
        "plan_name": plan_name,
        "saving_monthly": saving,
        **extras,
    },
    plan_id=_safe_plan_id,
    plan_name=_rec03_plan_name,
    saving=_rec03_saving,
    extras=_rec03_extra_fields,
)

# Full recommendation body with random tracks + optional extra top-level fields
_rec03_recommendation_body = st.builds(
    lambda green, cheapest, extras: {
        "kind": "recommendation",
        "green": green,
        "cheapest": cheapest,
        **extras,
    },
    green=_rec03_track,
    cheapest=_rec03_track,
    extras=st.fixed_dictionaries(
        {},
        optional={
            "reasoning_trace": st.lists(
                st.fixed_dictionaries({
                    "tool": st.sampled_from(["detect_bill_shock", "get_billing_history", "simulate_savings"]),
                    "summary": st.text(min_size=5, max_size=100),
                }),
                min_size=0,
                max_size=4,
            ),
            "compliance_review": st.text(min_size=0, max_size=50),
            "supervisor_trace": st.text(min_size=0, max_size=50),
        },
    ),
)


class TestREC03PreservedInStreamingResult:
    """Property 7: REC-03 preserved in streaming result events.

    Feature: streaming-reasoning-trace, Property 7: REC-03 preserved in streaming result events

    *For any* streaming result event where the response kind is "recommendation",
    the payload SHALL contain both `green` and `cheapest` track objects.

    **Validates: Requirements 4.2**
    """

    @settings(max_examples=100)
    @given(body=_rec03_recommendation_body)
    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_result_event_contains_green_track(
        self, mock_client, mock_hook_fn, body: dict
    ) -> None:
        """For any recommendation response, the result event contains a `green` track.

        Feature: streaming-reasoning-trace, Property 7: REC-03 preserved in streaming result events
        **Validates: Requirements 4.2**
        """
        # Set up mock hook
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        mock_response_bytes = json.dumps(body).encode()

        def _mock_invoke(**kwargs):
            return {"response": BytesIO(mock_response_bytes)}

        mock_client.invoke_agent_runtime.side_effect = _mock_invoke

        # Use a valid customer ID
        event = _make_streaming_event("CUST-001")
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        # Parse SSE events from the response stream
        sse_events = _parse_sse_events(response_stream.written_str)

        # Find the result event
        result_events = [(etype, data) for etype, data in sse_events if etype == "result"]
        assert len(result_events) == 1, (
            f"Expected exactly 1 result event, got {len(result_events)}. "
            f"All events: {[e[0] for e in sse_events]}"
        )

        _, result_data = result_events[0]

        # REC-03: green track MUST be present
        assert "green" in result_data, (
            f"REC-03 violated: 'green' track missing from result event. "
            f"Result keys: {list(result_data.keys())}"
        )
        # green must be a dict (track object)
        assert isinstance(result_data["green"], dict), (
            f"REC-03 violated: 'green' is not a dict, got {type(result_data['green'])}"
        )

    @settings(max_examples=100)
    @given(body=_rec03_recommendation_body)
    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_result_event_contains_cheapest_track(
        self, mock_client, mock_hook_fn, body: dict
    ) -> None:
        """For any recommendation response, the result event contains a `cheapest` track.

        Feature: streaming-reasoning-trace, Property 7: REC-03 preserved in streaming result events
        **Validates: Requirements 4.2**
        """
        # Set up mock hook
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        mock_response_bytes = json.dumps(body).encode()

        def _mock_invoke(**kwargs):
            return {"response": BytesIO(mock_response_bytes)}

        mock_client.invoke_agent_runtime.side_effect = _mock_invoke

        # Use a valid customer ID
        event = _make_streaming_event("CUST-001")
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        # Parse SSE events from the response stream
        sse_events = _parse_sse_events(response_stream.written_str)

        # Find the result event
        result_events = [(etype, data) for etype, data in sse_events if etype == "result"]
        assert len(result_events) == 1, (
            f"Expected exactly 1 result event, got {len(result_events)}. "
            f"All events: {[e[0] for e in sse_events]}"
        )

        _, result_data = result_events[0]

        # REC-03: cheapest track MUST be present
        assert "cheapest" in result_data, (
            f"REC-03 violated: 'cheapest' track missing from result event. "
            f"Result keys: {list(result_data.keys())}"
        )
        # cheapest must be a dict (track object)
        assert isinstance(result_data["cheapest"], dict), (
            f"REC-03 violated: 'cheapest' is not a dict, got {type(result_data['cheapest'])}"
        )

    @settings(max_examples=100)
    @given(body=_rec03_recommendation_body)
    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_result_event_contains_both_tracks_simultaneously(
        self, mock_client, mock_hook_fn, body: dict
    ) -> None:
        """For any recommendation response, both green AND cheapest are present together.

        Feature: streaming-reasoning-trace, Property 7: REC-03 preserved in streaming result events
        **Validates: Requirements 4.2**
        """
        # Set up mock hook
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        mock_response_bytes = json.dumps(body).encode()

        def _mock_invoke(**kwargs):
            return {"response": BytesIO(mock_response_bytes)}

        mock_client.invoke_agent_runtime.side_effect = _mock_invoke

        # Use a valid customer ID
        event = _make_streaming_event("CUST-001")
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        # Parse SSE events from the response stream
        sse_events = _parse_sse_events(response_stream.written_str)

        # Find the result event
        result_events = [(etype, data) for etype, data in sse_events if etype == "result"]
        assert len(result_events) == 1, (
            f"Expected exactly 1 result event, got {len(result_events)}. "
            f"All events: {[e[0] for e in sse_events]}"
        )

        _, result_data = result_events[0]

        # REC-03: BOTH tracks must be present simultaneously
        assert "green" in result_data and "cheapest" in result_data, (
            f"REC-03 violated: both 'green' and 'cheapest' must be present. "
            f"Has green: {'green' in result_data}, has cheapest: {'cheapest' in result_data}. "
            f"Result keys: {list(result_data.keys())}"
        )

        # Both must be dict objects (track objects, not None or other types)
        assert isinstance(result_data["green"], dict) and isinstance(result_data["cheapest"], dict), (
            f"REC-03 violated: tracks must be objects. "
            f"green type: {type(result_data.get('green'))}, "
            f"cheapest type: {type(result_data.get('cheapest'))}"
        )

        # Verify the response kind is "recommendation"
        assert result_data.get("kind") == "recommendation", (
            f"Expected kind='recommendation', got kind={result_data.get('kind')!r}"
        )
