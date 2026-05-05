"""Integration tests for end-to-end chat flow.

Tests the full request/response cycle through the handler routing layer,
verifying that the chat endpoint, SSE streaming, multi-turn sessions, and
existing endpoints all work correctly together.

Requirements: 1.1, 3.2, 3.6, 8.4, 8.5
"""
import io
import json
from unittest.mock import MagicMock, patch

import pytest

try:
    from api_lambda.handler import handler, stream_handler
    from api_lambda.chat_handler import chat_handler, chat_stream_handler
    import api_lambda.chat_session as chat_session_module
    _CAN_IMPORT = True
    _IMPORT_ERROR = ""
except ImportError as e:
    _CAN_IMPORT = False
    _IMPORT_ERROR = str(e)

pytestmark = pytest.mark.skipif(
    not _CAN_IMPORT,
    reason="api_lambda imports failed: {}".format(_IMPORT_ERROR),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chat_event(
    customer_id: str,
    message: str = "Why did her bill jump in February?",
    session_id: str | None = None,
    accept: str = "application/json",
) -> dict:
    """Build a minimal HTTP API v2 event for POST /chat/{customer_id}."""
    body = {"message": message}
    if session_id:
        body["session_id"] = session_id
    return {
        "pathParameters": {"customer_id": customer_id},
        "rawPath": f"/chat/{customer_id}",
        "headers": {"accept": accept},
        "body": json.dumps(body),
    }


def _make_recommendation_event(customer_id: str) -> dict:
    """Build a minimal HTTP API v2 event for GET /recommendations/{customer_id}."""
    return {
        "pathParameters": {"customer_id": customer_id},
        "rawPath": f"/recommendations/{customer_id}",
    }


def _make_follow_up_event(customer_id: str) -> dict:
    """Build a minimal HTTP API v2 event for GET /recommendations/{customer_id}/follow-up."""
    return {
        "pathParameters": {"customer_id": customer_id},
        "rawPath": f"/recommendations/{customer_id}/follow-up",
    }


def _make_agent_response(body: dict) -> dict:
    """Construct a mock invoke_agent_runtime response."""
    return {
        "response": io.BytesIO(json.dumps(body).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }


def _parse_sse_events(raw_bytes: bytes) -> list[dict]:
    """Parse SSE frames from raw bytes into a list of {event, data} dicts."""
    text = raw_bytes.decode()
    events = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_type = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: "):]
            elif line.startswith("data: "):
                data = line[len("data: "):]
        if event_type is not None:
            parsed_data = json.loads(data) if data else {}
            events.append({"event": event_type, "data": parsed_data})
    return events


class MockResponseStream:
    """Mock response_stream that captures writes for SSE testing."""

    def __init__(self):
        self.chunks: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.chunks.append(data)

    def get_all_bytes(self) -> bytes:
        return b"".join(self.chunks)

    def get_sse_events(self) -> list[dict]:
        return _parse_sse_events(self.get_all_bytes())


@pytest.fixture(autouse=True)
def _clear_sessions():
    """Clear the module-level session store between tests."""
    chat_session_module._sessions.clear()
    yield
    chat_session_module._sessions.clear()


# ---------------------------------------------------------------------------
# Test: Full request/response cycle with mocked AgentCore (POST /chat/CUST-001)
# ---------------------------------------------------------------------------


class TestFullChatCycle:
    """Integration tests for the full chat request/response cycle (Req 1.1)."""

    @patch("api_lambda.chat_handler._chat_agentcore_client")
    def test_full_chat_cycle_through_handler_routing(self, mock_client):
        """Req 1.1: POST /chat/CUST-001 routes through handler() → chat_handler() and returns Chat_Response."""
        agent_response = {
            "reply": "The February bill was higher because usage increased from 380 kWh to 520 kWh.",
            "reasoning_trace": [
                {"tool": "get_billing_history", "summary": "12 months retrieved — peak 520 kWh in 2025-02"},
                {"tool": "detect_bill_shock", "summary": "Bill shock detected: +$45.60 vs 11-month mean $142.30"},
            ],
        }
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response)

        event = _make_chat_event("CUST-001")
        result = handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])

        # Verify Chat_Response schema completeness
        assert "reply" in body
        assert "reasoning_trace" in body
        assert "session_id" in body
        assert "customer_id" in body

        # Verify content
        assert body["reply"] == agent_response["reply"]
        assert body["reasoning_trace"] == agent_response["reasoning_trace"]
        assert body["customer_id"] == "CUST-001"
        assert len(body["session_id"]) == 36  # uuid4 format

    @patch("api_lambda.chat_handler._chat_agentcore_client")
    def test_chat_invokes_agentcore_with_correct_payload(self, mock_client):
        """Req 1.1: AgentCore is invoked with action=chat, message, and session_history."""
        agent_response = {"reply": "Answer", "reasoning_trace": []}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response)

        event = _make_chat_event("CUST-001", message="What is her current plan?")
        handler(event, None)

        # Verify AgentCore was called with correct payload shape
        call_kwargs = mock_client.invoke_agent_runtime.call_args.kwargs
        payload = json.loads(call_kwargs["payload"].decode())
        assert payload["customer_id"] == "CUST-001"
        assert payload["action"] == "chat"
        assert payload["message"] == "What is her current plan?"
        assert "session_history" in payload
        assert isinstance(payload["session_history"], list)

        # Verify fresh runtimeSessionId (uuid4)
        assert len(call_kwargs["runtimeSessionId"]) == 36

    @patch("api_lambda.chat_handler._chat_agentcore_client")
    def test_chat_records_turn_in_session(self, mock_client):
        """After successful response, the turn is recorded in the session store."""
        agent_response = {"reply": "The bill was $142.", "reasoning_trace": []}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response)

        event = _make_chat_event("CUST-001", message="What was last month's bill?")
        result = handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        session_id = body["session_id"]

        # Verify session was created and turn recorded
        session = chat_session_module._sessions[session_id]
        assert session.turn_count == 1
        assert len(session.messages) == 2  # user + assistant
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"
        assert session.messages[1]["content"] == "The bill was $142."


# ---------------------------------------------------------------------------
# Test: SSE streaming delivers trace_step + chat_reply + done in correct order
# ---------------------------------------------------------------------------


class TestSSEStreaming:
    """Integration tests for SSE streaming event ordering (Req 3.2, 3.6)."""

    @patch("api_lambda.chat_handler._chat_agentcore_client")
    def test_sse_stream_event_order_trace_chat_done(self, mock_client):
        """Req 3.2, 3.6: SSE stream delivers trace_step → chat_reply → done in correct order."""
        agent_response = {
            "reply": "Usage increased in February.",
            "reasoning_trace": [
                {"tool": "get_billing_history", "summary": "12 months retrieved"},
                {"tool": "detect_bill_shock", "summary": "Bill shock detected: +$45.60"},
            ],
        }
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response)

        event = _make_chat_event("CUST-001", accept="text/event-stream")
        stream = MockResponseStream()
        stream_handler(event, stream, None)

        events = stream.get_sse_events()

        # Verify event types in order: trace_step(s) → chat_reply → done
        event_types = [e["event"] for e in events]
        assert event_types == ["trace_step", "trace_step", "chat_reply", "done"]

    @patch("api_lambda.chat_handler._chat_agentcore_client")
    def test_sse_stream_trace_step_content(self, mock_client):
        """Req 3.2: trace_step events contain tool and summary fields."""
        agent_response = {
            "reply": "Answer",
            "reasoning_trace": [
                {"tool": "get_billing_history", "summary": "12 months retrieved — peak 520 kWh"},
            ],
        }
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response)

        event = _make_chat_event("CUST-001", accept="text/event-stream")
        stream = MockResponseStream()
        stream_handler(event, stream, None)

        events = stream.get_sse_events()
        trace_events = [e for e in events if e["event"] == "trace_step"]

        assert len(trace_events) == 1
        assert trace_events[0]["data"]["tool"] == "get_billing_history"
        assert trace_events[0]["data"]["summary"] == "12 months retrieved — peak 520 kWh"

    @patch("api_lambda.chat_handler._chat_agentcore_client")
    def test_sse_stream_chat_reply_contains_full_response(self, mock_client):
        """Req 3.2: chat_reply event contains the full Chat_Response payload."""
        agent_response = {
            "reply": "The bill was higher due to increased usage.",
            "reasoning_trace": [
                {"tool": "get_billing_history", "summary": "12 months retrieved"},
            ],
        }
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response)

        event = _make_chat_event("CUST-001", accept="text/event-stream")
        stream = MockResponseStream()
        stream_handler(event, stream, None)

        events = stream.get_sse_events()
        chat_reply_events = [e for e in events if e["event"] == "chat_reply"]

        assert len(chat_reply_events) == 1
        data = chat_reply_events[0]["data"]
        assert data["reply"] == "The bill was higher due to increased usage."
        assert data["reasoning_trace"] == [{"tool": "get_billing_history", "summary": "12 months retrieved"}]
        assert data["customer_id"] == "CUST-001"
        assert "session_id" in data

    @patch("api_lambda.chat_handler._chat_agentcore_client")
    def test_sse_stream_done_is_terminal(self, mock_client):
        """Req 3.6: done event is always the last event in the stream."""
        agent_response = {"reply": "Answer", "reasoning_trace": []}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response)

        event = _make_chat_event("CUST-001", accept="text/event-stream")
        stream = MockResponseStream()
        stream_handler(event, stream, None)

        events = stream.get_sse_events()
        assert len(events) >= 2  # at least chat_reply + done
        assert events[-1]["event"] == "done"
        assert events[-1]["data"] == {}

    @patch("api_lambda.chat_handler._chat_agentcore_client")
    def test_sse_stream_no_trace_steps_when_empty_reasoning(self, mock_client):
        """When reasoning_trace is empty, only chat_reply + done are emitted."""
        agent_response = {"reply": "I don't have enough information.", "reasoning_trace": []}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response)

        event = _make_chat_event("CUST-001", accept="text/event-stream")
        stream = MockResponseStream()
        stream_handler(event, stream, None)

        events = stream.get_sse_events()
        event_types = [e["event"] for e in events]
        assert event_types == ["chat_reply", "done"]

    @patch("api_lambda.chat_handler._chat_agentcore_client")
    def test_sse_stream_error_followed_by_done(self, mock_client):
        """Req 3.6: On error, stream emits error + done (done is always terminal)."""
        from botocore.exceptions import ReadTimeoutError

        mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(
            endpoint_url="https://example.com"
        )

        event = _make_chat_event("CUST-001", accept="text/event-stream")
        stream = MockResponseStream()
        stream_handler(event, stream, None)

        events = stream.get_sse_events()
        event_types = [e["event"] for e in events]
        assert event_types == ["error", "done"]
        assert events[0]["data"]["status"] == 504

    @patch("api_lambda.chat_handler._chat_agentcore_client")
    def test_sse_stream_only_valid_event_types(self, mock_client):
        """Req 3.2: All emitted event types are one of trace_step, chat_reply, error, done."""
        agent_response = {
            "reply": "Answer",
            "reasoning_trace": [
                {"tool": "get_billing_history", "summary": "data retrieved"},
                {"tool": "simulate_savings", "summary": "savings calculated"},
            ],
        }
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response)

        event = _make_chat_event("CUST-001", accept="text/event-stream")
        stream = MockResponseStream()
        stream_handler(event, stream, None)

        events = stream.get_sse_events()
        valid_types = {"trace_step", "chat_reply", "error", "done"}
        for e in events:
            assert e["event"] in valid_types, f"Unexpected event type: {e['event']}"


# ---------------------------------------------------------------------------
# Test: Multi-turn conversation with session reuse
# ---------------------------------------------------------------------------


class TestMultiTurnConversation:
    """Integration tests for multi-turn conversation with session reuse."""

    @patch("api_lambda.chat_handler._chat_agentcore_client")
    def test_multi_turn_session_reuse(self, mock_client):
        """Multi-turn: second request with session_id reuses the same session."""
        # First turn
        agent_response_1 = {"reply": "Usage was 380 kWh in January.", "reasoning_trace": []}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response_1)

        event_1 = _make_chat_event("CUST-001", message="What was January usage?")
        result_1 = handler(event_1, None)
        assert result_1["statusCode"] == 200
        body_1 = json.loads(result_1["body"])
        session_id = body_1["session_id"]

        # Second turn — reuse session_id
        agent_response_2 = {"reply": "February was 520 kWh, an increase of 140 kWh.", "reasoning_trace": []}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response_2)

        event_2 = _make_chat_event("CUST-001", message="And February?", session_id=session_id)
        result_2 = handler(event_2, None)
        assert result_2["statusCode"] == 200
        body_2 = json.loads(result_2["body"])

        # Same session_id returned
        assert body_2["session_id"] == session_id

    @patch("api_lambda.chat_handler._chat_agentcore_client")
    def test_multi_turn_session_history_grows(self, mock_client):
        """Multi-turn: session history accumulates across turns."""
        # First turn
        agent_response_1 = {"reply": "First answer.", "reasoning_trace": []}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response_1)

        event_1 = _make_chat_event("CUST-001", message="First question")
        result_1 = handler(event_1, None)
        body_1 = json.loads(result_1["body"])
        session_id = body_1["session_id"]

        # Verify session has 1 turn (2 messages)
        session = chat_session_module._sessions[session_id]
        assert session.turn_count == 1
        assert len(session.messages) == 2

        # Second turn
        agent_response_2 = {"reply": "Second answer.", "reasoning_trace": []}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response_2)

        event_2 = _make_chat_event("CUST-001", message="Second question", session_id=session_id)
        result_2 = handler(event_2, None)
        body_2 = json.loads(result_2["body"])

        # Verify session has 2 turns (4 messages)
        assert session.turn_count == 2
        assert len(session.messages) == 4
        assert session.messages[2]["role"] == "user"
        assert session.messages[2]["content"] == "Second question"
        assert session.messages[3]["role"] == "assistant"
        assert session.messages[3]["content"] == "Second answer."

    @patch("api_lambda.chat_handler._chat_agentcore_client")
    def test_multi_turn_session_history_sent_to_agent(self, mock_client):
        """Multi-turn: session history is included in the AgentCore payload."""
        # First turn
        agent_response_1 = {"reply": "First answer.", "reasoning_trace": []}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response_1)

        event_1 = _make_chat_event("CUST-001", message="First question")
        result_1 = handler(event_1, None)
        body_1 = json.loads(result_1["body"])
        session_id = body_1["session_id"]

        # Second turn
        agent_response_2 = {"reply": "Second answer.", "reasoning_trace": []}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response_2)

        event_2 = _make_chat_event("CUST-001", message="Follow-up question", session_id=session_id)
        handler(event_2, None)

        # Verify the second call includes session history
        second_call_kwargs = mock_client.invoke_agent_runtime.call_args.kwargs
        payload = json.loads(second_call_kwargs["payload"].decode())
        assert len(payload["session_history"]) == 2  # user + assistant from turn 1
        assert payload["session_history"][0]["role"] == "user"
        assert payload["session_history"][0]["content"] == "First question"
        assert payload["session_history"][1]["role"] == "assistant"
        assert payload["session_history"][1]["content"] == "First answer."

    @patch("api_lambda.chat_handler._chat_agentcore_client")
    def test_multi_turn_cross_customer_rejected(self, mock_client):
        """SC-3: Session created for CUST-001 cannot be reused by CUST-002."""
        # Create session for CUST-001
        agent_response = {"reply": "Answer for CUST-001.", "reasoning_trace": []}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_response)

        event_1 = _make_chat_event("CUST-001", message="Hello")
        result_1 = handler(event_1, None)
        body_1 = json.loads(result_1["body"])
        session_id = body_1["session_id"]

        # Try to reuse session with CUST-002
        event_2 = _make_chat_event("CUST-002", message="Steal session", session_id=session_id)
        result_2 = handler(event_2, None)

        assert result_2["statusCode"] == 400
        body_2 = json.loads(result_2["body"])
        assert "different customer" in body_2["error"]


# ---------------------------------------------------------------------------
# Test: Existing recommendation endpoint regression (unchanged behavior)
# ---------------------------------------------------------------------------


class TestRecommendationRegression:
    """Regression tests: existing recommendation endpoint unchanged (Req 8.4)."""

    @patch("api_lambda.handler._agentcore_client")
    def test_recommendation_endpoint_returns_200(self, mock_client, mock_savings_response):
        """Req 8.4: GET /recommendations/{customer_id} still returns 200 with green + cheapest."""
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(mock_savings_response)

        event = _make_recommendation_event("CUST-001")
        result = handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "green" in body
        assert "cheapest" in body
        # Chat fields must NOT be present
        assert "reply" not in body
        assert "session_id" not in body

    @patch("api_lambda.handler._agentcore_client")
    def test_recommendation_endpoint_validation_unchanged(self, mock_client):
        """Req 8.4: Invalid customer_id still returns 400 on recommendation endpoint."""
        event = _make_recommendation_event("INVALID")
        result = handler(event, None)
        assert result["statusCode"] == 400

    @patch("api_lambda.handler._agentcore_client")
    def test_recommendation_endpoint_not_found_unchanged(self, mock_client):
        """Req 8.4: Missing customer still returns 404 on recommendation endpoint."""
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(
            {"errorMessage": "No billing history for 'CUST-999'"}
        )
        event = _make_recommendation_event("CUST-999")
        result = handler(event, None)
        assert result["statusCode"] == 404

    @patch("api_lambda.handler._agentcore_client")
    def test_recommendation_endpoint_timeout_unchanged(self, mock_client):
        """Req 8.4: Timeout still returns 504 on recommendation endpoint."""
        from botocore.exceptions import ReadTimeoutError

        mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(
            endpoint_url="https://example.com"
        )
        event = _make_recommendation_event("CUST-001")
        result = handler(event, None)
        assert result["statusCode"] == 504

    @patch("api_lambda.handler._agentcore_client")
    def test_recommendation_streaming_still_works(self, mock_client, mock_savings_response):
        """Req 8.4: Streaming recommendation path still works through stream_handler."""
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(mock_savings_response)

        event = _make_recommendation_event("CUST-001")
        event["headers"] = {"accept": "text/event-stream"}
        stream = MockResponseStream()
        stream_handler(event, stream, None)

        events = stream.get_sse_events()
        event_types = [e["event"] for e in events]
        # Recommendation streaming emits result + done
        assert "result" in event_types
        assert "done" in event_types


# ---------------------------------------------------------------------------
# Test: Existing follow-up endpoint regression (unchanged behavior)
# ---------------------------------------------------------------------------


class TestFollowUpRegression:
    """Regression tests: existing follow-up endpoint unchanged (Req 8.5)."""

    @patch("api_lambda.handler._agentcore_client")
    def test_follow_up_endpoint_returns_200(self, mock_client, mock_follow_up_response):
        """Req 8.5: GET /recommendations/{customer_id}/follow-up still returns 200."""
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(mock_follow_up_response)

        event = _make_follow_up_event("CUST-001")
        result = handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["kind"] == "follow_up"
        assert body["customer_id"] == "CUST-001"
        assert "subject" in body
        assert "body" in body
        assert "plan_reference" in body

    @patch("api_lambda.handler._agentcore_client")
    def test_follow_up_endpoint_validation_unchanged(self, mock_client):
        """Req 8.5: Invalid customer_id still returns 400 on follow-up endpoint."""
        event = _make_follow_up_event("INVALID")
        result = handler(event, None)
        assert result["statusCode"] == 400

    @patch("api_lambda.handler._agentcore_client")
    def test_follow_up_endpoint_timeout_unchanged(self, mock_client):
        """Req 8.5: Timeout still returns 504 on follow-up endpoint."""
        from botocore.exceptions import ReadTimeoutError

        mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(
            endpoint_url="https://example.com"
        )
        event = _make_follow_up_event("CUST-001")
        result = handler(event, None)
        assert result["statusCode"] == 504

    @patch("api_lambda.handler._agentcore_client")
    def test_follow_up_endpoint_strips_workflow_source(self, mock_client, mock_follow_up_response):
        """Req 8.5: _workflow_source marker is still stripped from follow-up response."""
        response_with_marker = {**mock_follow_up_response, "_workflow_source": {"subject": "model"}}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(response_with_marker)

        event = _make_follow_up_event("CUST-001")
        result = handler(event, None)

        body = json.loads(result["body"])
        assert "_workflow_source" not in body

    @patch("api_lambda.handler._agentcore_client")
    def test_follow_up_client_error_returns_502(self, mock_client):
        """Req 8.5: ClientError still returns 502 on follow-up endpoint."""
        from botocore.exceptions import ClientError

        mock_client.invoke_agent_runtime.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeAgentRuntime",
        )
        event = _make_follow_up_event("CUST-001")
        result = handler(event, None)
        assert result["statusCode"] == 502
