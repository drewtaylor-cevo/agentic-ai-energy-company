"""Offline unit tests for api_lambda/handler.py — no AWS credentials needed.

Mocks the module-level _agentcore_client to test all handler paths:
validation, success pass-through, error taxonomy (400/404/502/504/500),
and fresh session ID per invocation (D-11).
"""
import io
import json
from unittest.mock import MagicMock, patch

import pytest

try:
    from api_lambda.handler import handler
    _CAN_IMPORT = True
    _IMPORT_ERROR = ""
except ImportError as e:
    _CAN_IMPORT = False
    _IMPORT_ERROR = str(e)

pytestmark = pytest.mark.skipif(
    not _CAN_IMPORT,
    reason="api_lambda.handler import failed: {}".format(_IMPORT_ERROR),
)


def _make_event(customer_id: str) -> dict:
    """Build a minimal HTTP API v2 event with pathParameters."""
    return {"pathParameters": {"customer_id": customer_id}}


def _make_agent_response(body: dict) -> dict:
    """Construct a mock invoke_agent_runtime response (StreamingBody via BytesIO)."""
    return {
        "response": io.BytesIO(json.dumps(body).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }


# --- Success path ---


@patch("api_lambda.handler._agentcore_client")
def test_valid_customer_success(mock_client, mock_savings_response):
    """SC-1: valid CUST-001 returns 200 with green + cheapest."""
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        mock_savings_response
    )
    result = handler(_make_event("CUST-001"), None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert "green" in body
    assert "cheapest" in body


@patch("api_lambda.handler._agentcore_client")
def test_response_passthrough_shape(mock_client, mock_savings_response):
    """D-02: response body is verbatim pass-through — no envelope, no meta."""
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        mock_savings_response
    )
    result = handler(_make_event("CUST-001"), None)
    assert json.loads(result["body"]) == mock_savings_response


# --- Validation (400) ---


@pytest.mark.parametrize(
    "bad_id",
    ["NOTVALID", "cust-001", "CUST-1", "CUST-1234567", ""],
)
def test_invalid_customer_id_returns_400(bad_id):
    """D-13: malformed customer_id returns 400 without calling agent."""
    result = handler(_make_event(bad_id), None)
    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "error" in body
    assert "Invalid customer ID format" in body["error"]


# --- Customer not found (404) ---


@patch("api_lambda.handler._agentcore_client")
def test_missing_green_returns_404(mock_client):
    """D-12: response without green key -> 404."""
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        {"cheapest": {"plan_id": "VAL"}}
    )
    result = handler(_make_event("CUST-001"), None)
    assert result["statusCode"] == 404
    assert "not found" in json.loads(result["body"])["error"]


@patch("api_lambda.handler._agentcore_client")
def test_missing_cheapest_returns_404(mock_client):
    """D-12: response without cheapest key -> 404."""
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        {"green": {"plan_id": "ECO"}}
    )
    result = handler(_make_event("CUST-001"), None)
    assert result["statusCode"] == 404


# --- Timeout (504) ---


@patch("api_lambda.handler._agentcore_client")
def test_timeout_returns_504(mock_client):
    """D-03/D-12: ReadTimeoutError -> 504."""
    from botocore.exceptions import ReadTimeoutError

    mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(
        endpoint_url="https://example.com"
    )
    result = handler(_make_event("CUST-001"), None)
    assert result["statusCode"] == 504
    assert "timed out" in json.loads(result["body"])["error"]


# --- ClientError (502) ---


@patch("api_lambda.handler._agentcore_client")
def test_client_error_returns_502(mock_client):
    """D-12: ClientError -> 502."""
    from botocore.exceptions import ClientError

    mock_client.invoke_agent_runtime.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "InvokeAgentRuntime",
    )
    result = handler(_make_event("CUST-001"), None)
    assert result["statusCode"] == 502
    assert "service error" in json.loads(result["body"])["error"]


# --- Unexpected error (500) ---


@patch("api_lambda.handler._agentcore_client")
def test_unexpected_error_returns_500(mock_client):
    """D-12: unknown Exception -> 500."""
    mock_client.invoke_agent_runtime.side_effect = Exception("boom")
    result = handler(_make_event("CUST-001"), None)
    assert result["statusCode"] == 500
    assert "Internal server error" in json.loads(result["body"])["error"]


# --- Fresh session ID per invocation (D-11) ---


@patch("api_lambda.handler._agentcore_client")
def test_fresh_session_id_per_call(mock_client, mock_savings_response):
    """D-11/SC-3: two consecutive calls produce different runtimeSessionId values."""
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        mock_savings_response
    )
    handler(_make_event("CUST-001"), None)

    # Reset BytesIO for second call
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        mock_savings_response
    )
    handler(_make_event("CUST-001"), None)

    calls = mock_client.invoke_agent_runtime.call_args_list
    assert len(calls) == 2
    session_1 = calls[0].kwargs.get("runtimeSessionId") or calls[0][1].get(
        "runtimeSessionId"
    )
    session_2 = calls[1].kwargs.get("runtimeSessionId") or calls[1][1].get(
        "runtimeSessionId"
    )
    assert session_1 != session_2, "Session IDs must differ between invocations"
