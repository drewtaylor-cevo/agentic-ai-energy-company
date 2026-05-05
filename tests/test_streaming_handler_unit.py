"""Unit tests for streaming handler in api_lambda/handler.py.

Feature: streaming-reasoning-trace

Tests content negotiation routing, prewarm bypass, narrative=off suppression,
D-04 fallback behavior, error event shapes, and follow-up endpoint isolation.

Requirements: 1.1, 1.2, 4.5, 4.6, 4.7, 7.2, 7.3
"""
from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError

from api_lambda.handler import stream_handler, handler, _stream_handler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _make_event(
    customer_id: str = "CUST-001",
    accept: str | None = None,
    prewarm: bool = False,
    narrative_off: bool = False,
    raw_path: str | None = None,
) -> dict:
    """Build a Lambda Function URL / HTTP API v2 event."""
    headers = {}
    if accept:
        headers["accept"] = accept

    query_params = {}
    if prewarm:
        query_params["prewarm"] = "1"
    if narrative_off:
        query_params["narrative"] = "off"

    if raw_path is None:
        raw_path = f"/recommendations/{customer_id}"

    return {
        "pathParameters": {"customer_id": customer_id},
        "rawPath": raw_path,
        "headers": headers,
        "queryStringParameters": query_params or None,
    }


def _valid_recommendation_body() -> bytes:
    """Return a valid recommendation response body as bytes."""
    return json.dumps({
        "kind": "recommendation",
        "green": {"plan_id": "ECO", "plan_name": "EcoFlex 100", "saving_monthly": 30.0},
        "cheapest": {"plan_id": "VAL", "plan_name": "Value 12", "saving_monthly": 55.0},
        "reasoning_trace": [
            {"tool": "get_billing_history", "summary": "Retrieved 12 months of billing data"},
            {"tool": "detect_bill_shock", "summary": "Bill shock detected: +$65.16"},
        ],
        "compliance_review": "All checks passed",
        "supervisor_trace": "Supervisor approved",
    }).encode()


# ---------------------------------------------------------------------------
# Test: Content Negotiation Routing
# Requirements: 1.1, 1.2
# ---------------------------------------------------------------------------


class TestContentNegotiation:
    """Test that Accept header routes to streaming vs batch path."""

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_accept_sse_routes_to_streaming_path(self, mock_client, mock_hook_fn):
        """Accept: text/event-stream → SSE streaming path emits SSE events.

        **Validates: Requirements 1.1**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        mock_client.invoke_agent_runtime.return_value = {
            "response": BytesIO(_valid_recommendation_body())
        }

        event = _make_event(accept="text/event-stream")
        response_stream = _MockResponseStream()
        context = MagicMock()

        stream_handler(event, response_stream, context)

        # Should produce SSE events (not a JSON envelope)
        sse_events = _parse_sse_events(response_stream.written_str)
        event_types = [e[0] for e in sse_events]
        assert "result" in event_types
        assert "done" in event_types

    @patch("api_lambda.handler._agentcore_client")
    def test_no_accept_header_routes_to_batch_path(self, mock_client):
        """No Accept header → batch path returns JSON envelope.

        **Validates: Requirements 1.2**
        """
        mock_client.invoke_agent_runtime.return_value = {
            "response": BytesIO(_valid_recommendation_body())
        }

        event = _make_event(accept=None)
        response_stream = _MockResponseStream()
        context = MagicMock()

        stream_handler(event, response_stream, context)

        # Should produce a JSON envelope (batch handler result)
        result = json.loads(response_stream.written_str)
        assert "statusCode" in result
        assert result["statusCode"] == 200

    @patch("api_lambda.handler._agentcore_client")
    def test_accept_json_routes_to_batch_path(self, mock_client):
        """Accept: application/json → batch path (not streaming).

        **Validates: Requirements 1.2**
        """
        mock_client.invoke_agent_runtime.return_value = {
            "response": BytesIO(_valid_recommendation_body())
        }

        event = _make_event(accept="application/json")
        response_stream = _MockResponseStream()
        context = MagicMock()

        stream_handler(event, response_stream, context)

        # Should produce a JSON envelope (batch handler result)
        result = json.loads(response_stream.written_str)
        assert "statusCode" in result
        assert result["statusCode"] == 200


# ---------------------------------------------------------------------------
# Test: Prewarm Bypass
# Requirements: 4.6
# ---------------------------------------------------------------------------


class TestPrewarmBypass:
    """Test ?prewarm=1 returns 204 regardless of Accept header."""

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_prewarm_with_sse_accept_returns_204(self, mock_client, mock_hook_fn):
        """?prewarm=1 with Accept: text/event-stream → 204 empty body.

        **Validates: Requirements 4.6**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        event = _make_event(accept="text/event-stream", prewarm=True)
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        result = json.loads(response_stream.written_str)
        assert result["statusCode"] == 204
        assert result["body"] == ""

    @patch("api_lambda.handler._agentcore_client")
    def test_prewarm_without_sse_accept_returns_204(self, mock_client):
        """?prewarm=1 without Accept: text/event-stream → 204 via batch path.

        **Validates: Requirements 4.6**
        """
        mock_response_body = _valid_recommendation_body()
        mock_client.invoke_agent_runtime.return_value = {
            "response": BytesIO(mock_response_body)
        }

        event = _make_event(accept=None, prewarm=True)
        context = MagicMock()

        # Batch path via handler()
        result = handler(event, context)
        assert result["statusCode"] == 204
        assert result["body"] == ""

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_prewarm_does_not_emit_sse_events(self, mock_client, mock_hook_fn):
        """?prewarm=1 does not emit any SSE events.

        **Validates: Requirements 4.6**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        event = _make_event(accept="text/event-stream", prewarm=True)
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        # Should NOT contain SSE event framing
        raw = response_stream.written_str
        assert "event: trace_step" not in raw
        assert "event: result" not in raw
        assert "event: done" not in raw


# ---------------------------------------------------------------------------
# Test: ?narrative=off Suppresses trace_step Events
# Requirements: 4.7
# ---------------------------------------------------------------------------


class TestNarrativeOff:
    """Test ?narrative=off suppresses trace_step events and strips fields."""

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_narrative_off_suppresses_trace_step_events(self, mock_client, mock_hook_fn):
        """?narrative=off → no trace_step events emitted.

        **Validates: Requirements 4.7**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        mock_client.invoke_agent_runtime.return_value = {
            "response": BytesIO(_valid_recommendation_body())
        }

        event = _make_event(accept="text/event-stream", narrative_off=True)
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        sse_events = _parse_sse_events(response_stream.written_str)
        event_types = [e[0] for e in sse_events]

        # No trace_step events
        assert "trace_step" not in event_types
        # Still has result + done
        assert "result" in event_types
        assert "done" in event_types

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_narrative_off_strips_reasoning_fields_from_result(self, mock_client, mock_hook_fn):
        """?narrative=off → result event omits reasoning_trace, compliance_review, supervisor_trace.

        **Validates: Requirements 4.7**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        mock_client.invoke_agent_runtime.return_value = {
            "response": BytesIO(_valid_recommendation_body())
        }

        event = _make_event(accept="text/event-stream", narrative_off=True)
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        sse_events = _parse_sse_events(response_stream.written_str)
        result_events = [(t, d) for t, d in sse_events if t == "result"]
        assert len(result_events) == 1

        _, result_data = result_events[0]
        assert "reasoning_trace" not in result_data
        assert "compliance_review" not in result_data
        assert "supervisor_trace" not in result_data
        # Core recommendation data preserved
        assert "green" in result_data
        assert "cheapest" in result_data

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_narrative_off_callback_is_noop(self, mock_client, mock_hook_fn):
        """?narrative=off → streaming callback does not write trace_step frames.

        **Validates: Requirements 4.7**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        # Capture the callback set on the hook
        captured_callbacks = []
        mock_hook.set_callback.side_effect = lambda cb: captured_callbacks.append(cb)

        mock_client.invoke_agent_runtime.return_value = {
            "response": BytesIO(_valid_recommendation_body())
        }

        event = _make_event(accept="text/event-stream", narrative_off=True)
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        # The callback was set
        assert len(captured_callbacks) == 1
        callback = captured_callbacks[0]

        # Calling the callback should NOT write anything (it's a no-op when narrative=off)
        chunks_before = len(response_stream.chunks)
        callback("detect_bill_shock", "Bill shock detected")
        chunks_after = len(response_stream.chunks)
        assert chunks_after == chunks_before


# ---------------------------------------------------------------------------
# Test: D-04 Fallback Emits Error + Done (Not Result)
# Requirements: 4.5, 7.3
# ---------------------------------------------------------------------------


class TestD04Fallback:
    """Test D-04 fallback emits error event + done (clean stream termination).

    Per the design doc's error handling table, exceptions map to error events
    with appropriate status codes, followed by done. The stream always
    terminates cleanly.
    """

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_read_timeout_emits_error_504_then_done(self, mock_client, mock_hook_fn):
        """ReadTimeoutError → error event (504) + done event.

        **Validates: Requirements 4.5, 7.3**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(
            endpoint_url="https://bedrock-agentcore.us-east-1.amazonaws.com"
        )

        event = _make_event(accept="text/event-stream")
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        sse_events = _parse_sse_events(response_stream.written_str)
        event_types = [e[0] for e in sse_events]

        assert event_types == ["error", "done"]
        error_data = sse_events[0][1]
        assert error_data["status"] == 504

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_client_error_emits_error_502_then_done(self, mock_client, mock_hook_fn):
        """ClientError → error event (502) + done event.

        **Validates: Requirements 4.5, 7.3**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        mock_client.invoke_agent_runtime.side_effect = ClientError(
            error_response={"Error": {"Code": "ServiceException", "Message": "Service unavailable"}},
            operation_name="InvokeAgentRuntime",
        )

        event = _make_event(accept="text/event-stream")
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        sse_events = _parse_sse_events(response_stream.written_str)
        event_types = [e[0] for e in sse_events]

        assert event_types == ["error", "done"]
        error_data = sse_events[0][1]
        assert error_data["status"] == 502

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_generic_exception_emits_error_500_then_done(self, mock_client, mock_hook_fn):
        """Generic Exception → error event (500) + done event.

        **Validates: Requirements 4.5, 7.3**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        mock_client.invoke_agent_runtime.side_effect = RuntimeError("Unexpected failure")

        event = _make_event(accept="text/event-stream")
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        sse_events = _parse_sse_events(response_stream.written_str)
        event_types = [e[0] for e in sse_events]

        assert event_types == ["error", "done"]
        error_data = sse_events[0][1]
        assert error_data["status"] == 500

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_all_fallback_paths_end_with_done(self, mock_client, mock_hook_fn):
        """All exception paths terminate with done event (never leaves stream open).

        **Validates: Requirements 4.5**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        exceptions = [
            ReadTimeoutError(endpoint_url="https://example.com"),
            ClientError(
                error_response={"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
                operation_name="InvokeAgentRuntime",
            ),
            ValueError("Something went wrong"),
            OSError("Connection reset"),
        ]

        for exc in exceptions:
            mock_client.invoke_agent_runtime.side_effect = exc

            event = _make_event(accept="text/event-stream")
            response_stream = _MockResponseStream()
            context = MagicMock()

            _stream_handler(event, response_stream, context)

            sse_events = _parse_sse_events(response_stream.written_str)
            assert len(sse_events) >= 1, f"No events for {type(exc).__name__}"
            assert sse_events[-1][0] == "done", (
                f"Last event should be 'done' for {type(exc).__name__}, "
                f"got '{sse_events[-1][0]}'"
            )


# ---------------------------------------------------------------------------
# Test: Error Event Shape
# Requirements: 7.3
# ---------------------------------------------------------------------------


class TestErrorEventShape:
    """Test error event shape for each error scenario (400, 404, 502, 504)."""

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_400_error_shape_invalid_customer_id(self, mock_client, mock_hook_fn):
        """Invalid customer_id → JSON 400 error (pre-stream, not SSE).

        **Validates: Requirements 7.3**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        event = _make_event(customer_id="INVALID")
        event["headers"]["accept"] = "text/event-stream"
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        # 400 is returned as JSON envelope (not SSE) since stream hasn't opened
        result = json.loads(response_stream.written_str)
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "error" in body
        assert isinstance(body["error"], str)
        assert len(body["error"]) > 0

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_404_error_event_shape_customer_not_found(self, mock_client, mock_hook_fn):
        """Customer not found → error SSE event with status 404.

        **Validates: Requirements 7.3**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        # Response without green/cheapest triggers customer-not-found
        not_found_body = json.dumps({"errorMessage": "No data found"}).encode()
        mock_client.invoke_agent_runtime.return_value = {
            "response": BytesIO(not_found_body)
        }

        event = _make_event(accept="text/event-stream")
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        sse_events = _parse_sse_events(response_stream.written_str)
        error_events = [(t, d) for t, d in sse_events if t == "error"]
        assert len(error_events) == 1

        _, error_data = error_events[0]
        assert error_data["status"] == 404
        assert "message" in error_data
        assert isinstance(error_data["message"], str)
        assert "CUST-001" in error_data["message"]

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_502_error_event_shape(self, mock_client, mock_hook_fn):
        """ClientError → error SSE event with status 502 and message.

        **Validates: Requirements 7.3**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        mock_client.invoke_agent_runtime.side_effect = ClientError(
            error_response={"Error": {"Code": "ServiceException", "Message": "Unavailable"}},
            operation_name="InvokeAgentRuntime",
        )

        event = _make_event(accept="text/event-stream")
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        sse_events = _parse_sse_events(response_stream.written_str)
        error_events = [(t, d) for t, d in sse_events if t == "error"]
        assert len(error_events) == 1

        _, error_data = error_events[0]
        assert error_data["status"] == 502
        assert "message" in error_data
        assert isinstance(error_data["message"], str)
        assert len(error_data["message"]) > 0

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_504_error_event_shape(self, mock_client, mock_hook_fn):
        """ReadTimeoutError → error SSE event with status 504 and message.

        **Validates: Requirements 7.3**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(
            endpoint_url="https://bedrock-agentcore.us-east-1.amazonaws.com"
        )

        event = _make_event(accept="text/event-stream")
        response_stream = _MockResponseStream()
        context = MagicMock()

        _stream_handler(event, response_stream, context)

        sse_events = _parse_sse_events(response_stream.written_str)
        error_events = [(t, d) for t, d in sse_events if t == "error"]
        assert len(error_events) == 1

        _, error_data = error_events[0]
        assert error_data["status"] == 504
        assert "message" in error_data
        assert isinstance(error_data["message"], str)
        assert "timed out" in error_data["message"].lower()

    @patch("api_lambda.handler._get_streaming_trace_hook")
    @patch("api_lambda.handler._agentcore_client")
    def test_error_events_always_have_status_and_message(self, mock_client, mock_hook_fn):
        """All error events have integer 'status' and string 'message' fields.

        **Validates: Requirements 7.3**
        """
        mock_hook = MagicMock()
        mock_hook_fn.return_value = mock_hook

        scenarios = [
            ReadTimeoutError(endpoint_url="https://example.com"),
            ClientError(
                error_response={"Error": {"Code": "X", "Message": "Y"}},
                operation_name="InvokeAgentRuntime",
            ),
            RuntimeError("boom"),
        ]

        for exc in scenarios:
            mock_client.invoke_agent_runtime.side_effect = exc

            event = _make_event(accept="text/event-stream")
            response_stream = _MockResponseStream()
            context = MagicMock()

            _stream_handler(event, response_stream, context)

            sse_events = _parse_sse_events(response_stream.written_str)
            error_events = [(t, d) for t, d in sse_events if t == "error"]
            assert len(error_events) == 1, f"Expected 1 error event for {type(exc).__name__}"

            _, error_data = error_events[0]
            assert "status" in error_data, f"Missing 'status' for {type(exc).__name__}"
            assert "message" in error_data, f"Missing 'message' for {type(exc).__name__}"
            assert isinstance(error_data["status"], int), (
                f"'status' should be int for {type(exc).__name__}"
            )
            assert isinstance(error_data["message"], str), (
                f"'message' should be str for {type(exc).__name__}"
            )


# ---------------------------------------------------------------------------
# Test: Follow-up Endpoint Ignores Accept Header
# Requirements: 7.2
# ---------------------------------------------------------------------------


class TestFollowUpEndpoint:
    """Test follow-up endpoint always returns JSON regardless of Accept header."""

    @patch("api_lambda.handler._agentcore_client")
    def test_follow_up_with_sse_accept_returns_json(self, mock_client):
        """Follow-up endpoint with Accept: text/event-stream → still returns JSON.

        **Validates: Requirements 7.2**
        """
        follow_up_body = json.dumps({
            "kind": "follow_up",
            "subject": "Your energy plan options",
            "body": "Dear customer, following our conversation...",
        }).encode()

        mock_client.invoke_agent_runtime.return_value = {
            "response": BytesIO(follow_up_body)
        }

        event = _make_event(
            customer_id="CUST-001",
            accept="text/event-stream",
            raw_path="/recommendations/CUST-001/follow-up",
        )
        context = MagicMock()

        # The batch handler() handles follow-up — it does NOT check Accept header
        result = handler(event, context)

        assert result["statusCode"] == 200
        assert result["headers"]["Content-Type"] == "application/json"
        body = json.loads(result["body"])
        assert body["kind"] == "follow_up"

    @patch("api_lambda.handler._agentcore_client")
    def test_follow_up_without_accept_returns_json(self, mock_client):
        """Follow-up endpoint without Accept header → returns JSON.

        **Validates: Requirements 7.2**
        """
        follow_up_body = json.dumps({
            "kind": "follow_up",
            "subject": "Your energy plan options",
            "body": "Dear customer, following our conversation...",
        }).encode()

        mock_client.invoke_agent_runtime.return_value = {
            "response": BytesIO(follow_up_body)
        }

        event = _make_event(
            customer_id="CUST-001",
            accept=None,
            raw_path="/recommendations/CUST-001/follow-up",
        )
        context = MagicMock()

        result = handler(event, context)

        assert result["statusCode"] == 200
        assert result["headers"]["Content-Type"] == "application/json"
        body = json.loads(result["body"])
        assert body["kind"] == "follow_up"

    @patch("api_lambda.handler._agentcore_client")
    def test_follow_up_never_streams_sse(self, mock_client):
        """Follow-up endpoint never produces SSE events even with Accept header.

        **Validates: Requirements 7.2**
        """
        follow_up_body = json.dumps({
            "kind": "follow_up",
            "subject": "Your energy plan options",
            "body": "Dear customer...",
        }).encode()

        mock_client.invoke_agent_runtime.return_value = {
            "response": BytesIO(follow_up_body)
        }

        event = _make_event(
            customer_id="CUST-001",
            accept="text/event-stream",
            raw_path="/recommendations/CUST-001/follow-up",
        )
        context = MagicMock()

        result = handler(event, context)

        # Result is a dict (JSON response), not SSE frames
        assert isinstance(result, dict)
        assert "statusCode" in result
        # Body does not contain SSE framing
        assert "event: " not in result.get("body", "")
