# Feature: conversational-chat-layer, Property 6: SSE event type constraint
# Feature: conversational-chat-layer, Property 7: SSE done event is terminal
"""Property-based tests for SSE streaming constraints.

**Validates: Requirements 3.2, 3.6**

Property 6: For any SSE stream from the chat endpoint, every emitted event type
SHALL be one of exactly four values: `trace_step`, `chat_reply`, `error`, `done`.

Property 7: For any SSE stream from the chat endpoint (whether successful or
failed), the stream SHALL end with exactly one `done` event, and no events SHALL
be emitted after it.
"""

import json
import re
from unittest.mock import patch, MagicMock

from botocore.exceptions import ClientError, ReadTimeoutError
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from api_lambda.chat_handler import chat_stream_handler


# --- Helpers ---

# The four allowed SSE event types per Requirement 3.2.
_ALLOWED_EVENT_TYPES = {"trace_step", "chat_reply", "error", "done"}

# Regex to parse SSE frames: "event: <type>\ndata: <json>\n\n"
_SSE_EVENT_PATTERN = re.compile(r"event: ([^\n]+)\ndata: ([^\n]*)\n\n")


def _parse_sse_events(raw: str) -> list[dict]:
    """Parse raw SSE text into a list of {type, data} dicts."""
    events = []
    for match in _SSE_EVENT_PATTERN.finditer(raw):
        event_type = match.group(1)
        data_str = match.group(2)
        try:
            data = json.loads(data_str)
        except (json.JSONDecodeError, TypeError):
            data = data_str
        events.append({"type": event_type, "data": data})
    return events


class MockResponseStream:
    """Mock response_stream that captures all .write(bytes) calls."""

    def __init__(self):
        self._chunks: list[bytes] = []

    def write(self, data: bytes) -> None:
        self._chunks.append(data)

    def get_raw_output(self) -> str:
        """Return all written bytes decoded as UTF-8."""
        return b"".join(self._chunks).decode("utf-8")

    def get_sse_events(self) -> list[dict]:
        """Parse all written SSE events."""
        return _parse_sse_events(self.get_raw_output())


def _make_stream_event(customer_id: str, message: str) -> dict:
    """Build a valid Lambda proxy event for the SSE streaming chat handler."""
    return {
        "rawPath": f"/chat/{customer_id}",
        "pathParameters": {"customer_id": customer_id},
        "body": json.dumps({"message": message}),
        "headers": {
            "content-type": "application/json",
            "accept": "text/event-stream",
        },
    }


def _make_mock_session(customer_id: str = "CUST-001") -> MagicMock:
    """Create a mock session object for patching session_store."""
    mock_session = MagicMock()
    mock_session.session_id = "test-session-id"
    mock_session.customer_id = customer_id
    mock_session.messages = []
    return mock_session


def _make_mock_agentcore_response(reply: str, reasoning_trace: list[dict]) -> MagicMock:
    """Create a mock AgentCore response with the given reply and trace."""
    response_body = json.dumps({
        "reply": reply,
        "reasoning_trace": reasoning_trace,
    }).encode()

    mock_response_stream = MagicMock()
    mock_response_stream.read.return_value = response_body

    return {"response": mock_response_stream}


# --- Strategies ---

# Valid customer IDs.
_valid_customer_id_strategy = st.from_regex(r"CUST-\d{3,6}", fullmatch=True)

# Valid messages.
_valid_message_strategy = st.text(min_size=1, max_size=100).filter(
    lambda s: s.strip() and len(s) <= 2000
)

# Reply content from AgentCore.
_reply_strategy = st.text(min_size=1, max_size=300).filter(lambda s: s.strip())

# Tool names the agent can call.
_tool_name_strategy = st.sampled_from([
    "simulate_savings",
    "detect_bill_shock",
    "get_billing_history",
    "get_hardship_flag",
])

# Summary text for trace entries.
_summary_strategy = st.text(min_size=1, max_size=150).filter(lambda s: s.strip())

# Reasoning trace entries.
_reasoning_trace_entry_strategy = st.fixed_dictionaries({
    "tool": _tool_name_strategy,
    "summary": _summary_strategy,
})

# Reasoning trace (0-4 entries, matching the 4-tool cap).
_reasoning_trace_strategy = st.lists(
    _reasoning_trace_entry_strategy,
    min_size=0,
    max_size=4,
)

# Exception types that can occur during AgentCore invocation.
_runtime_exception_strategy = st.one_of(
    st.just(RuntimeError("unexpected runtime failure")),
    st.just(TypeError("'NoneType' object is not subscriptable")),
    st.just(ValueError("invalid literal")),
    st.just(OSError("network unreachable")),
    st.just(ConnectionError("connection refused")),
    st.just(Exception("generic unexpected error")),
)


# --- Property 6: SSE event type constraint ---


@settings(max_examples=100)
@given(
    customer_id=_valid_customer_id_strategy,
    message=_valid_message_strategy,
    reply=_reply_strategy,
    reasoning_trace=_reasoning_trace_strategy,
)
def test_sse_event_types_on_success(
    customer_id: str,
    message: str,
    reply: str,
    reasoning_trace: list[dict],
) -> None:
    """On successful chat stream, all emitted event types are in the allowed set.

    **Validates: Requirements 3.2**
    """
    event = _make_stream_event(customer_id, message)
    stream = MockResponseStream()

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        mock_store.get_or_create.return_value = _make_mock_session(customer_id)
        mock_store.check_rate_limit.return_value = False
        mock_client.invoke_agent_runtime.return_value = _make_mock_agentcore_response(
            reply, reasoning_trace
        )

        chat_stream_handler(event, stream, None)

    sse_events = stream.get_sse_events()
    # Must have at least one event (done).
    assert len(sse_events) >= 1, "Stream must emit at least one event"

    for i, evt in enumerate(sse_events):
        assert evt["type"] in _ALLOWED_EVENT_TYPES, (
            f"Event {i} has disallowed type '{evt['type']}'. "
            f"Allowed: {_ALLOWED_EVENT_TYPES}"
        )


@settings(max_examples=100)
@given(
    customer_id=_valid_customer_id_strategy,
    message=_valid_message_strategy,
)
def test_sse_event_types_on_timeout(customer_id: str, message: str) -> None:
    """On timeout, all emitted event types are in the allowed set.

    **Validates: Requirements 3.2**
    """
    event = _make_stream_event(customer_id, message)
    stream = MockResponseStream()

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        mock_store.get_or_create.return_value = _make_mock_session(customer_id)
        mock_store.check_rate_limit.return_value = False
        mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(
            endpoint_url="https://bedrock.us-east-1.amazonaws.com"
        )

        chat_stream_handler(event, stream, None)

    sse_events = stream.get_sse_events()
    assert len(sse_events) >= 1, "Stream must emit at least one event"

    for i, evt in enumerate(sse_events):
        assert evt["type"] in _ALLOWED_EVENT_TYPES, (
            f"Event {i} has disallowed type '{evt['type']}'. "
            f"Allowed: {_ALLOWED_EVENT_TYPES}"
        )


@settings(max_examples=100)
@given(
    customer_id=_valid_customer_id_strategy,
    message=_valid_message_strategy,
    exception=_runtime_exception_strategy,
)
def test_sse_event_types_on_exception(
    customer_id: str, message: str, exception: Exception
) -> None:
    """On any runtime exception, all emitted event types are in the allowed set.

    **Validates: Requirements 3.2**
    """
    event = _make_stream_event(customer_id, message)
    stream = MockResponseStream()

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        mock_store.get_or_create.return_value = _make_mock_session(customer_id)
        mock_store.check_rate_limit.return_value = False
        mock_client.invoke_agent_runtime.side_effect = exception

        chat_stream_handler(event, stream, None)

    sse_events = stream.get_sse_events()
    assert len(sse_events) >= 1, "Stream must emit at least one event"

    for i, evt in enumerate(sse_events):
        assert evt["type"] in _ALLOWED_EVENT_TYPES, (
            f"Event {i} has disallowed type '{evt['type']}'. "
            f"Allowed: {_ALLOWED_EVENT_TYPES}"
        )


@settings(max_examples=100)
@given(
    customer_id=_valid_customer_id_strategy,
    message=_valid_message_strategy,
)
def test_sse_event_types_on_client_error(customer_id: str, message: str) -> None:
    """On ClientError, all emitted event types are in the allowed set.

    **Validates: Requirements 3.2**
    """
    event = _make_stream_event(customer_id, message)
    stream = MockResponseStream()

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        mock_store.get_or_create.return_value = _make_mock_session(customer_id)
        mock_store.check_rate_limit.return_value = False
        mock_client.invoke_agent_runtime.side_effect = ClientError(
            error_response={
                "Error": {"Code": "ServiceUnavailableException", "Message": "Service unavailable"}
            },
            operation_name="InvokeAgentRuntime",
        )

        chat_stream_handler(event, stream, None)

    sse_events = stream.get_sse_events()
    assert len(sse_events) >= 1, "Stream must emit at least one event"

    for i, evt in enumerate(sse_events):
        assert evt["type"] in _ALLOWED_EVENT_TYPES, (
            f"Event {i} has disallowed type '{evt['type']}'. "
            f"Allowed: {_ALLOWED_EVENT_TYPES}"
        )


# --- Property 7: SSE done event is terminal ---


@settings(max_examples=100)
@given(
    customer_id=_valid_customer_id_strategy,
    message=_valid_message_strategy,
    reply=_reply_strategy,
    reasoning_trace=_reasoning_trace_strategy,
)
def test_sse_done_is_terminal_on_success(
    customer_id: str,
    message: str,
    reply: str,
    reasoning_trace: list[dict],
) -> None:
    """On successful chat stream, the last event is exactly one `done` and nothing follows.

    **Validates: Requirements 3.6**
    """
    event = _make_stream_event(customer_id, message)
    stream = MockResponseStream()

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        mock_store.get_or_create.return_value = _make_mock_session(customer_id)
        mock_store.check_rate_limit.return_value = False
        mock_client.invoke_agent_runtime.return_value = _make_mock_agentcore_response(
            reply, reasoning_trace
        )

        chat_stream_handler(event, stream, None)

    sse_events = stream.get_sse_events()
    assert len(sse_events) >= 1, "Stream must emit at least one event"

    # The last event must be `done`.
    assert sse_events[-1]["type"] == "done", (
        f"Last event must be 'done', got '{sse_events[-1]['type']}'"
    )

    # There must be exactly one `done` event.
    done_count = sum(1 for e in sse_events if e["type"] == "done")
    assert done_count == 1, (
        f"Expected exactly 1 'done' event, found {done_count}"
    )

    # No events after `done` (verified by it being last + count == 1).
    done_index = next(i for i, e in enumerate(sse_events) if e["type"] == "done")
    assert done_index == len(sse_events) - 1, (
        f"'done' event at index {done_index} but stream has {len(sse_events)} events — "
        f"events after 'done': {[e['type'] for e in sse_events[done_index+1:]]}"
    )


@settings(max_examples=100)
@given(
    customer_id=_valid_customer_id_strategy,
    message=_valid_message_strategy,
)
def test_sse_done_is_terminal_on_timeout(customer_id: str, message: str) -> None:
    """On timeout, the stream ends with exactly one `done` event.

    **Validates: Requirements 3.6**
    """
    event = _make_stream_event(customer_id, message)
    stream = MockResponseStream()

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        mock_store.get_or_create.return_value = _make_mock_session(customer_id)
        mock_store.check_rate_limit.return_value = False
        mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(
            endpoint_url="https://bedrock.us-east-1.amazonaws.com"
        )

        chat_stream_handler(event, stream, None)

    sse_events = stream.get_sse_events()
    assert len(sse_events) >= 1, "Stream must emit at least one event"

    # Last event must be `done`.
    assert sse_events[-1]["type"] == "done", (
        f"Last event must be 'done', got '{sse_events[-1]['type']}'"
    )

    # Exactly one `done`.
    done_count = sum(1 for e in sse_events if e["type"] == "done")
    assert done_count == 1, (
        f"Expected exactly 1 'done' event, found {done_count}"
    )


@settings(max_examples=100)
@given(
    customer_id=_valid_customer_id_strategy,
    message=_valid_message_strategy,
    exception=_runtime_exception_strategy,
)
def test_sse_done_is_terminal_on_exception(
    customer_id: str, message: str, exception: Exception
) -> None:
    """On any runtime exception, the stream ends with exactly one `done` event.

    **Validates: Requirements 3.6**
    """
    event = _make_stream_event(customer_id, message)
    stream = MockResponseStream()

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        mock_store.get_or_create.return_value = _make_mock_session(customer_id)
        mock_store.check_rate_limit.return_value = False
        mock_client.invoke_agent_runtime.side_effect = exception

        chat_stream_handler(event, stream, None)

    sse_events = stream.get_sse_events()
    assert len(sse_events) >= 1, "Stream must emit at least one event"

    # Last event must be `done`.
    assert sse_events[-1]["type"] == "done", (
        f"Last event must be 'done', got '{sse_events[-1]['type']}'"
    )

    # Exactly one `done`.
    done_count = sum(1 for e in sse_events if e["type"] == "done")
    assert done_count == 1, (
        f"Expected exactly 1 'done' event, found {done_count}"
    )


@settings(max_examples=100)
@given(
    customer_id=_valid_customer_id_strategy,
    message=_valid_message_strategy,
)
def test_sse_done_is_terminal_on_client_error(customer_id: str, message: str) -> None:
    """On ClientError, the stream ends with exactly one `done` event.

    **Validates: Requirements 3.6**
    """
    event = _make_stream_event(customer_id, message)
    stream = MockResponseStream()

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        mock_store.get_or_create.return_value = _make_mock_session(customer_id)
        mock_store.check_rate_limit.return_value = False
        mock_client.invoke_agent_runtime.side_effect = ClientError(
            error_response={
                "Error": {"Code": "ServiceUnavailableException", "Message": "Service unavailable"}
            },
            operation_name="InvokeAgentRuntime",
        )

        chat_stream_handler(event, stream, None)

    sse_events = stream.get_sse_events()
    assert len(sse_events) >= 1, "Stream must emit at least one event"

    # Last event must be `done`.
    assert sse_events[-1]["type"] == "done", (
        f"Last event must be 'done', got '{sse_events[-1]['type']}'"
    )

    # Exactly one `done`.
    done_count = sum(1 for e in sse_events if e["type"] == "done")
    assert done_count == 1, (
        f"Expected exactly 1 'done' event, found {done_count}"
    )
