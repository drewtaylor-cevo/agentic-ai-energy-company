"""Offline unit tests for api_lambda/chat_handler.py — no AWS credentials needed.

Mocks the module-level _chat_agentcore_client and session_store to test all
chat handler paths: routing, validation, content negotiation, error taxonomy
(400/429/502/504), HTML sanitisation, and regression for existing endpoints.

Requirements: 1.1, 1.2, 1.3, 1.6, 1.7, 1.8, 3.7, 8.4, 8.5, 10.1, 10.2, 10.4, 10.5
"""
import io
import json
from unittest.mock import MagicMock, patch

import pytest

try:
    from api_lambda.chat_handler import chat_handler, chat_stream_handler
    from api_lambda.handler import handler, stream_handler
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_chat_response():
    """Canonical successful chat agent response body."""
    return {
        "reply": "Based on the billing records, usage increased in February.",
        "reasoning_trace": [
            {"tool": "get_billing_history", "summary": "12 months retrieved"},
        ],
    }


@pytest.fixture
def mock_agentcore_success(mock_chat_response):
    """Mock invoke_agent_runtime returning a successful chat response."""
    return {
        "response": io.BytesIO(json.dumps(mock_chat_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }


def _make_chat_event(
    customer_id: str,
    message: str = "Why did her bill jump?",
    session_id: str | None = None,
    accept: str = "application/json",
) -> dict:
    """Build a minimal HTTP API v2 event for POST /chat/{customer_id}."""
    body = {"message": message}
    if session_id:
        body["session_id"] = session_id
    event = {
        "pathParameters": {"customer_id": customer_id},
        "rawPath": f"/chat/{customer_id}",
        "headers": {"accept": accept},
        "body": json.dumps(body),
    }
    return event


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


# ---------------------------------------------------------------------------
# Test: Routing — POST /chat/{customer_id} dispatches correctly
# ---------------------------------------------------------------------------


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
def test_chat_route_dispatches_via_handler(mock_session_store, mock_client, mock_chat_response):
    """Req 1.1: POST /chat/{customer_id} routes through handler() to chat_handler."""
    # Setup session store mock
    mock_session = MagicMock()
    mock_session.session_id = "test-session-id"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    # Setup agentcore mock
    mock_client.invoke_agent_runtime.return_value = {
        "response": io.BytesIO(json.dumps(mock_chat_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }

    event = _make_chat_event("CUST-001")
    result = handler(event, None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert "reply" in body
    assert body["session_id"] == "test-session-id"


# ---------------------------------------------------------------------------
# Test: Content negotiation (Accept header → SSE vs JSON)
# ---------------------------------------------------------------------------


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
def test_content_negotiation_json_batch(mock_session_store, mock_client, mock_chat_response):
    """Req 3.7: Without Accept: text/event-stream, returns JSON batch response."""
    mock_session = MagicMock()
    mock_session.session_id = "sess-123"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    mock_client.invoke_agent_runtime.return_value = {
        "response": io.BytesIO(json.dumps(mock_chat_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }

    event = _make_chat_event("CUST-001", accept="application/json")
    result = chat_handler(event, None)

    assert result["statusCode"] == 200
    assert result["headers"]["Content-Type"] == "application/json"
    body = json.loads(result["body"])
    assert "reply" in body


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
def test_content_negotiation_sse_stream(mock_session_store, mock_client, mock_chat_response):
    """Req 3.7: Accept: text/event-stream routes to SSE streaming via stream_handler."""
    mock_session = MagicMock()
    mock_session.session_id = "sess-456"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    mock_client.invoke_agent_runtime.return_value = {
        "response": io.BytesIO(json.dumps(mock_chat_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }

    event = _make_chat_event("CUST-001", accept="text/event-stream")
    response_stream = MagicMock()
    chat_stream_handler(event, response_stream, None)

    # Verify SSE events were written
    written = b"".join(call.args[0] for call in response_stream.write.call_args_list)
    written_str = written.decode()
    assert "event: chat_reply" in written_str
    assert "event: done" in written_str


# ---------------------------------------------------------------------------
# Test: Invalid customer_id returns 400
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_id",
    ["NOTVALID", "cust-001", "CUST-1", "CUST-1234567", "", "CUST-ABC"],
)
def test_invalid_customer_id_returns_400(bad_id):
    """Req 1.2, 10.1: Malformed customer_id returns 400 without calling agent."""
    event = _make_chat_event(bad_id)
    result = chat_handler(event, None)
    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "error" in body
    assert "Invalid customer ID format" in body["error"]


# ---------------------------------------------------------------------------
# Test: Missing/empty/whitespace message returns 400
# ---------------------------------------------------------------------------


def test_missing_message_returns_400():
    """Req 1.3, 10.2: Missing message field returns 400."""
    event = {
        "pathParameters": {"customer_id": "CUST-001"},
        "rawPath": "/chat/CUST-001",
        "headers": {"accept": "application/json"},
        "body": json.dumps({}),
    }
    result = chat_handler(event, None)
    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "error" in body


def test_empty_message_returns_400():
    """Req 1.3, 10.2: Empty string message returns 400."""
    event = _make_chat_event("CUST-001", message="")
    result = chat_handler(event, None)
    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "error" in body


def test_whitespace_only_message_returns_400():
    """Req 10.2: Whitespace-only message returns 400."""
    event = _make_chat_event("CUST-001", message="   \t\n  ")
    result = chat_handler(event, None)
    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "error" in body
    assert "empty" in body["error"].lower() or "whitespace" in body["error"].lower()


def test_no_body_returns_400():
    """Req 1.3: No request body returns 400."""
    event = {
        "pathParameters": {"customer_id": "CUST-001"},
        "rawPath": "/chat/CUST-001",
        "headers": {"accept": "application/json"},
        "body": "",
    }
    result = chat_handler(event, None)
    assert result["statusCode"] == 400


# ---------------------------------------------------------------------------
# Test: Message exceeding 2000 chars returns 400
# ---------------------------------------------------------------------------


def test_message_exceeding_2000_chars_returns_400():
    """Req 10.1: Message over 2000 characters returns 400."""
    long_message = "x" * 2001
    event = _make_chat_event("CUST-001", message=long_message)
    result = chat_handler(event, None)
    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "2000" in body["error"]


def test_message_at_2000_chars_is_accepted():
    """Boundary: message at exactly 2000 characters is valid (not rejected)."""
    exact_message = "x" * 2000
    event = _make_chat_event("CUST-001", message=exact_message)
    # This should pass validation — will fail at session/agent level without mocks,
    # but should NOT return 400 for length.
    with patch("api_lambda.chat_handler.session_store") as mock_ss, \
         patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client:
        mock_session = MagicMock()
        mock_session.session_id = "sess-ok"
        mock_session.customer_id = "CUST-001"
        mock_session.messages = []
        mock_ss.get_or_create.return_value = mock_session
        mock_ss.check_rate_limit.return_value = False
        mock_client.invoke_agent_runtime.return_value = {
            "response": io.BytesIO(json.dumps({"reply": "ok", "reasoning_trace": []}).encode()),
            "contentType": "application/json",
            "statusCode": 200,
        }
        result = chat_handler(event, None)
    assert result["statusCode"] == 200


# ---------------------------------------------------------------------------
# Test: Cross-customer session returns 400
# ---------------------------------------------------------------------------


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
def test_cross_customer_session_returns_400(mock_session_store, mock_client):
    """Req 10.4, SC-3: Session belonging to different customer returns 400."""
    mock_session_store.get_or_create.side_effect = ValueError(
        "Session belongs to a different customer."
    )

    event = _make_chat_event("CUST-002", session_id="stolen-session-id")
    result = chat_handler(event, None)

    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "different customer" in body["error"]


# ---------------------------------------------------------------------------
# Test: Rate limit exceeded returns 429
# ---------------------------------------------------------------------------


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
def test_rate_limit_exceeded_returns_429(mock_session_store, mock_client):
    """Req 10.4: Rate limit exceeded returns 429."""
    mock_session = MagicMock()
    mock_session.session_id = "sess-rate"
    mock_session.customer_id = "CUST-001"
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = True

    event = _make_chat_event("CUST-001")
    result = chat_handler(event, None)

    assert result["statusCode"] == 429
    body = json.loads(result["body"])
    assert "Rate limit" in body["error"]


# ---------------------------------------------------------------------------
# Test: Timeout returns 504
# ---------------------------------------------------------------------------


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
def test_timeout_returns_504(mock_session_store, mock_client):
    """Req 1.6: ReadTimeoutError → 504."""
    from botocore.exceptions import ReadTimeoutError

    mock_session = MagicMock()
    mock_session.session_id = "sess-timeout"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(
        endpoint_url="https://example.com"
    )

    event = _make_chat_event("CUST-001")
    result = chat_handler(event, None)

    assert result["statusCode"] == 504
    body = json.loads(result["body"])
    assert "timed out" in body["error"]


# ---------------------------------------------------------------------------
# Test: ClientError returns 502
# ---------------------------------------------------------------------------


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
def test_client_error_returns_502(mock_session_store, mock_client):
    """Req 1.7: ClientError → 502."""
    from botocore.exceptions import ClientError

    mock_session = MagicMock()
    mock_session.session_id = "sess-ce"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    mock_client.invoke_agent_runtime.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "InvokeAgentRuntime",
    )

    event = _make_chat_event("CUST-001")
    result = chat_handler(event, None)

    assert result["statusCode"] == 502
    body = json.loads(result["body"])
    assert "service error" in body["error"]


# ---------------------------------------------------------------------------
# Test: Unexpected exception returns 502 (never 500)
# ---------------------------------------------------------------------------


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
def test_unexpected_exception_returns_502_never_500(mock_session_store, mock_client):
    """Req 1.8, D-04: Unexpected exception → 502, never 500."""
    mock_session = MagicMock()
    mock_session.session_id = "sess-boom"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    mock_client.invoke_agent_runtime.side_effect = RuntimeError("unexpected kaboom")

    event = _make_chat_event("CUST-001")
    result = chat_handler(event, None)

    assert result["statusCode"] == 502, "D-04: must never return 500"
    body = json.loads(result["body"])
    assert "service error" in body["error"]


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
def test_type_error_returns_502_never_500(mock_session_store, mock_client):
    """D-04: TypeError also maps to 502, not 500."""
    mock_session = MagicMock()
    mock_session.session_id = "sess-type"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    mock_client.invoke_agent_runtime.side_effect = TypeError("NoneType has no attribute")

    event = _make_chat_event("CUST-001")
    result = chat_handler(event, None)

    assert result["statusCode"] == 502


# ---------------------------------------------------------------------------
# Test: HTML tags stripped from message
# ---------------------------------------------------------------------------


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
def test_html_tags_stripped_from_message(mock_session_store, mock_client, mock_chat_response):
    """Req 10.5: HTML tags are stripped before passing to agent."""
    mock_session = MagicMock()
    mock_session.session_id = "sess-html"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    mock_client.invoke_agent_runtime.return_value = {
        "response": io.BytesIO(json.dumps(mock_chat_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }

    # Message with HTML tags
    event = _make_chat_event("CUST-001", message="<script>alert('xss')</script>Why did the bill jump?")
    result = chat_handler(event, None)

    assert result["statusCode"] == 200

    # Verify the payload sent to AgentCore has HTML stripped
    call_kwargs = mock_client.invoke_agent_runtime.call_args.kwargs
    payload = json.loads(call_kwargs["payload"].decode())
    assert "<script>" not in payload["message"]
    assert "</" not in payload["message"]
    assert "alert('xss')" in payload["message"]  # text content preserved
    assert "Why did the bill jump?" in payload["message"]


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
def test_html_img_tag_stripped(mock_session_store, mock_client, mock_chat_response):
    """Req 10.5: <img> tags are stripped from message."""
    mock_session = MagicMock()
    mock_session.session_id = "sess-img"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    mock_client.invoke_agent_runtime.return_value = {
        "response": io.BytesIO(json.dumps(mock_chat_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }

    event = _make_chat_event("CUST-001", message='<img src="x" onerror="alert(1)">Hello')
    result = chat_handler(event, None)

    assert result["statusCode"] == 200
    call_kwargs = mock_client.invoke_agent_runtime.call_args.kwargs
    payload = json.loads(call_kwargs["payload"].decode())
    assert "<img" not in payload["message"]
    assert "Hello" in payload["message"]


# ---------------------------------------------------------------------------
# Test: Batch fallback (no Accept: text/event-stream → JSON response)
# ---------------------------------------------------------------------------


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
def test_batch_fallback_returns_json(mock_session_store, mock_client, mock_chat_response):
    """Req 3.7: Without Accept: text/event-stream, handler() returns JSON batch.

    The batch fallback path is: handler() detects /chat/ in rawPath and
    delegates to chat_handler() which returns a JSON dict response.
    """
    mock_session = MagicMock()
    mock_session.session_id = "sess-batch"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    mock_client.invoke_agent_runtime.return_value = {
        "response": io.BytesIO(json.dumps(mock_chat_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }

    # handler() with no SSE accept header routes to chat_handler (batch JSON)
    event = _make_chat_event("CUST-001", accept="application/json")
    result = handler(event, None)

    # Batch path returns a standard JSON response dict
    assert result["statusCode"] == 200
    assert result["headers"]["Content-Type"] == "application/json"
    body = json.loads(result["body"])
    assert "reply" in body
    assert body["session_id"] == "sess-batch"
    # Verify it's NOT SSE format
    assert "event:" not in result["body"]


# ---------------------------------------------------------------------------
# Test: Existing recommendation endpoint unchanged (regression)
# ---------------------------------------------------------------------------


@patch("api_lambda.handler._agentcore_client")
def test_recommendation_endpoint_unchanged(mock_client, mock_savings_response):
    """Req 8.4: Existing GET /recommendations/{customer_id} still works."""
    mock_client.invoke_agent_runtime.return_value = {
        "response": io.BytesIO(json.dumps(mock_savings_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }

    event = _make_recommendation_event("CUST-001")
    result = handler(event, None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert "green" in body
    assert "cheapest" in body
    # Chat fields should NOT be present
    assert "reply" not in body
    assert "session_id" not in body


# ---------------------------------------------------------------------------
# Test: Existing follow-up endpoint unchanged (regression)
# ---------------------------------------------------------------------------


@patch("api_lambda.handler._agentcore_client")
def test_follow_up_endpoint_unchanged(mock_client, mock_follow_up_response):
    """Req 8.5: Existing GET /recommendations/{customer_id}/follow-up still works."""
    mock_client.invoke_agent_runtime.return_value = {
        "response": io.BytesIO(json.dumps(mock_follow_up_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }

    event = _make_follow_up_event("CUST-001")
    result = handler(event, None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["kind"] == "follow_up"
    assert body["customer_id"] == "CUST-001"
    assert "subject" in body
    assert "body" in body


# ---------------------------------------------------------------------------
# Test: SC-3 StreamingTraceHook wiring in chat_stream_handler
# ---------------------------------------------------------------------------


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
@patch("api_lambda.chat_handler._get_chat_streaming_trace_hook")
def test_chat_stream_handler_resets_hook_before_invocation(
    mock_hook_fn, mock_session_store, mock_client, mock_chat_response
):
    """Req 3.3, SC-3: Hook is reset before AgentCore invocation to clear stale state."""
    mock_hook = MagicMock()
    mock_hook_fn.return_value = mock_hook

    mock_session = MagicMock()
    mock_session.session_id = "test-session-id"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    mock_client.invoke_agent_runtime.return_value = {
        "response": io.BytesIO(json.dumps(mock_chat_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }

    event = _make_chat_event("CUST-001", accept="text/event-stream")
    response_stream = MagicMock()
    chat_stream_handler(event, response_stream, None)

    # Hook must be reset at least twice: once before invocation, once in finally.
    assert mock_hook.reset.call_count >= 2, (
        f"Expected hook.reset() called at least 2 times (before + finally), "
        f"got {mock_hook.reset.call_count}"
    )


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
@patch("api_lambda.chat_handler._get_chat_streaming_trace_hook")
def test_chat_stream_handler_sets_callback_on_hook(
    mock_hook_fn, mock_session_store, mock_client, mock_chat_response
):
    """Req 3.3: Hook callback is wired to emit SSE trace_step frames."""
    mock_hook = MagicMock()
    mock_hook_fn.return_value = mock_hook

    mock_session = MagicMock()
    mock_session.session_id = "test-session-id"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    mock_client.invoke_agent_runtime.return_value = {
        "response": io.BytesIO(json.dumps(mock_chat_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }

    event = _make_chat_event("CUST-001", accept="text/event-stream")
    response_stream = MagicMock()
    chat_stream_handler(event, response_stream, None)

    # Hook must have set_callback called with a callable.
    mock_hook.set_callback.assert_called_once()
    callback = mock_hook.set_callback.call_args[0][0]
    assert callable(callback)


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
@patch("api_lambda.chat_handler._get_chat_streaming_trace_hook")
def test_chat_stream_handler_resets_hook_on_exception(
    mock_hook_fn, mock_session_store, mock_client
):
    """SC-3: Hook is reset in finally block even when AgentCore raises."""
    mock_hook = MagicMock()
    mock_hook_fn.return_value = mock_hook

    mock_session = MagicMock()
    mock_session.session_id = "test-session-id"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    # Simulate an unexpected exception during invocation.
    mock_client.invoke_agent_runtime.side_effect = RuntimeError("boom")

    event = _make_chat_event("CUST-001", accept="text/event-stream")
    response_stream = MagicMock()
    chat_stream_handler(event, response_stream, None)

    # Hook must still be reset in finally block (SC-3 cleanup).
    assert mock_hook.reset.call_count >= 2, (
        f"Expected hook.reset() called at least 2 times even on exception, "
        f"got {mock_hook.reset.call_count}"
    )


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
@patch("api_lambda.chat_handler._get_chat_streaming_trace_hook")
def test_chat_stream_handler_callback_emits_trace_step_sse(
    mock_hook_fn, mock_session_store, mock_client, mock_chat_response
):
    """Req 3.4: The hook callback emits SSE trace_step frames with tool and summary."""
    mock_hook = MagicMock()
    mock_hook_fn.return_value = mock_hook

    mock_session = MagicMock()
    mock_session.session_id = "test-session-id"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    mock_client.invoke_agent_runtime.return_value = {
        "response": io.BytesIO(json.dumps(mock_chat_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }

    event = _make_chat_event("CUST-001", accept="text/event-stream")
    response_stream = MagicMock()
    chat_stream_handler(event, response_stream, None)

    # Extract the callback that was set on the hook.
    callback = mock_hook.set_callback.call_args[0][0]

    # Invoke the callback with a tool name and summary.
    callback("get_billing_history", "12 months retrieved")

    # Verify it wrote an SSE trace_step frame to response_stream.
    written = b"".join(call.args[0] for call in response_stream.write.call_args_list)
    written_str = written.decode()

    # The callback should produce the same SSE format as the recommendation path.
    assert 'event: trace_step\ndata: {"tool":"get_billing_history","summary":"12 months retrieved"}\n\n' in written_str


@patch("api_lambda.chat_handler._chat_agentcore_client")
@patch("api_lambda.chat_handler.session_store")
def test_chat_stream_handler_trace_step_events_from_response_body(
    mock_session_store, mock_client
):
    """Req 2.5, 3.3: trace_step events emitted from response body use same format as recommendation path."""
    mock_session = MagicMock()
    mock_session.session_id = "test-session-id"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    mock_session_store.get_or_create.return_value = mock_session
    mock_session_store.check_rate_limit.return_value = False

    # Response with multiple reasoning trace entries.
    chat_response = {
        "reply": "The bill increased due to higher usage.",
        "reasoning_trace": [
            {"tool": "get_billing_history", "summary": "12 months retrieved"},
            {"tool": "detect_bill_shock", "summary": "Bill shock detected: +$45.60 2025-02 vs 11-month avg ($187.60 vs $142.00)"},
        ],
    }
    mock_client.invoke_agent_runtime.return_value = {
        "response": io.BytesIO(json.dumps(chat_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }

    event = _make_chat_event("CUST-001", accept="text/event-stream")
    response_stream = MagicMock()
    chat_stream_handler(event, response_stream, None)

    # Collect all written SSE frames.
    written = b"".join(call.args[0] for call in response_stream.write.call_args_list)
    written_str = written.decode()

    # Verify trace_step events are emitted with correct format.
    assert 'event: trace_step\ndata: {"tool":"get_billing_history","summary":"12 months retrieved"}\n\n' in written_str
    assert 'event: trace_step\ndata: {"tool":"detect_bill_shock","summary":"Bill shock detected: +$45.60 2025-02 vs 11-month avg ($187.60 vs $142.00)"}\n\n' in written_str

    # Verify ordering: trace_step events come before chat_reply.
    trace_step_pos = written_str.find("event: trace_step")
    chat_reply_pos = written_str.find("event: chat_reply")
    done_pos = written_str.find("event: done")
    assert trace_step_pos < chat_reply_pos < done_pos
