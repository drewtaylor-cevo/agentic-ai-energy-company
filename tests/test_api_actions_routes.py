"""Unit tests for API Lambda agentic-actions-portfolio routes.

Tests cover:
  - GET /retention-queue (happy path + upstream failure)
  - POST /actions/{action_id}/confirm (happy path + error cases)
  - POST /actions/{action_id}/dismiss (happy path + error cases)
  - Error mapping: 400, 404, 409, 410, 502
  - pending_actions pass-through in recommendation response
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


# --- Helpers ---


def _make_retention_queue_event() -> dict:
    """Build a minimal HTTP API v2 event for GET /retention-queue."""
    return {"rawPath": "/retention-queue", "pathParameters": {}}


def _make_action_event(action_id: str, verb: str) -> dict:
    """Build a minimal HTTP API v2 event for POST /actions/{action_id}/{verb}."""
    return {
        "rawPath": f"/actions/{action_id}/{verb}",
        "pathParameters": {"action_id": action_id},
    }


def _make_recommendation_event(customer_id: str) -> dict:
    """Build a minimal HTTP API v2 event for GET /recommendations/{customer_id}."""
    return {"rawPath": f"/recommendations/{customer_id}", "pathParameters": {"customer_id": customer_id}}


def _make_agent_response(body: dict) -> dict:
    """Construct a mock invoke_agent_runtime response."""
    return {
        "response": io.BytesIO(json.dumps(body).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }


def _make_tools_lambda_response(body: dict) -> dict:
    """Construct a mock Lambda invoke response (Tools Lambda)."""
    return {
        "Payload": io.BytesIO(json.dumps(body).encode()),
        "StatusCode": 200,
    }


# --- GET /retention-queue ---


@patch("api_lambda.handler._tools_lambda_client")
def test_retention_queue_happy_path(mock_tools_client):
    """GET /retention-queue returns 200 with ranked risk signals."""
    expected_result = {
        "customers_at_risk": 4,
        "queue": [
            {
                "customer_id": "CUST-003",
                "risk_score": 82,
                "risk_summary": "Bill shock: +$45 over baseline",
                "bill_shock_detected": True,
                "usage_trend": "increasing",
                "hardship_flag": False,
            },
            {
                "customer_id": "CUST-001",
                "risk_score": 50,
                "risk_summary": "Usage trending up, no shock detected",
                "bill_shock_detected": False,
                "usage_trend": "increasing",
                "hardship_flag": False,
            },
        ],
    }
    mock_tools_client.invoke.return_value = _make_tools_lambda_response(expected_result)

    result = handler(_make_retention_queue_event(), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["customers_at_risk"] == 4
    assert len(body["queue"]) == 2
    assert body["queue"][0]["customer_id"] == "CUST-003"


@patch("api_lambda.handler._tools_lambda_client")
def test_retention_queue_invokes_with_all_customer_ids(mock_tools_client):
    """GET /retention-queue invokes Tools Lambda with all 6 known customer_ids."""
    mock_tools_client.invoke.return_value = _make_tools_lambda_response(
        {"customers_at_risk": 0, "queue": []}
    )

    handler(_make_retention_queue_event(), None)

    mock_tools_client.invoke.assert_called_once()
    call_kwargs = mock_tools_client.invoke.call_args.kwargs
    payload = json.loads(call_kwargs["Payload"].decode())
    assert payload["action"] == "compute_risk_signals"
    assert payload["customer_ids"] == [
        "CUST-001", "CUST-002", "CUST-003",
        "CUST-004", "CUST-005", "CUST-006",
    ]


@patch("api_lambda.handler._tools_lambda_client")
def test_retention_queue_upstream_failure_returns_502(mock_tools_client):
    """GET /retention-queue returns 502 when Tools Lambda invocation fails (D-04)."""
    mock_tools_client.invoke.side_effect = Exception("Connection refused")

    result = handler(_make_retention_queue_event(), None)

    assert result["statusCode"] == 502
    body = json.loads(result["body"])
    assert body["error"] == "Upstream service error"


@patch("api_lambda.handler._tools_lambda_client")
def test_retention_queue_tools_error_returns_502(mock_tools_client):
    """GET /retention-queue returns 502 when Tools Lambda returns an error response."""
    mock_tools_client.invoke.return_value = _make_tools_lambda_response(
        {"error": True, "message": "TABLE_NAME env var not set"}
    )

    result = handler(_make_retention_queue_event(), None)

    assert result["statusCode"] == 502
    body = json.loads(result["body"])
    assert body["error"] == "Upstream service error"


# --- POST /actions/{action_id}/confirm ---


VALID_ACTION_ID = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"


@patch("api_lambda.handler._tools_lambda_client")
def test_action_confirm_happy_path(mock_tools_client):
    """POST /actions/{id}/confirm returns 200 with updated action."""
    confirmed_action = {
        "action_id": VALID_ACTION_ID,
        "action_type": "tariff_switch",
        "customer_id": "CUST-001",
        "payload": {"plan_id": "ECO"},
        "status": "confirmed",
        "created_at": "2025-01-01T00:00:00Z",
        "expires_at": 1735776000,
    }
    mock_tools_client.invoke.return_value = _make_tools_lambda_response(confirmed_action)

    result = handler(_make_action_event(VALID_ACTION_ID, "confirm"), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["status"] == "confirmed"
    assert body["action_id"] == VALID_ACTION_ID


@patch("api_lambda.handler._tools_lambda_client")
def test_action_confirm_invokes_tools_lambda(mock_tools_client):
    """POST /actions/{id}/confirm invokes Tools Lambda with confirm_action."""
    mock_tools_client.invoke.return_value = _make_tools_lambda_response(
        {"action_id": VALID_ACTION_ID, "status": "confirmed"}
    )

    handler(_make_action_event(VALID_ACTION_ID, "confirm"), None)

    call_kwargs = mock_tools_client.invoke.call_args.kwargs
    payload = json.loads(call_kwargs["Payload"].decode())
    assert payload["action"] == "confirm_action"
    assert payload["action_id"] == VALID_ACTION_ID


# --- POST /actions/{action_id}/dismiss ---


@patch("api_lambda.handler._tools_lambda_client")
def test_action_dismiss_happy_path(mock_tools_client):
    """POST /actions/{id}/dismiss returns 200 with updated action."""
    dismissed_action = {
        "action_id": VALID_ACTION_ID,
        "action_type": "send_sms",
        "customer_id": "CUST-002",
        "payload": {"message_body": "Thanks for calling"},
        "status": "rejected",
        "created_at": "2025-01-01T00:00:00Z",
        "expires_at": 1735776000,
    }
    mock_tools_client.invoke.return_value = _make_tools_lambda_response(dismissed_action)

    result = handler(_make_action_event(VALID_ACTION_ID, "dismiss"), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["status"] == "rejected"


@patch("api_lambda.handler._tools_lambda_client")
def test_action_dismiss_invokes_tools_lambda(mock_tools_client):
    """POST /actions/{id}/dismiss invokes Tools Lambda with dismiss_action."""
    mock_tools_client.invoke.return_value = _make_tools_lambda_response(
        {"action_id": VALID_ACTION_ID, "status": "rejected"}
    )

    handler(_make_action_event(VALID_ACTION_ID, "dismiss"), None)

    call_kwargs = mock_tools_client.invoke.call_args.kwargs
    payload = json.loads(call_kwargs["Payload"].decode())
    assert payload["action"] == "dismiss_action"
    assert payload["action_id"] == VALID_ACTION_ID


# --- Error mapping: 400 (invalid action_id) ---


def test_action_confirm_invalid_action_id_returns_400():
    """POST /actions/{bad_id}/confirm returns 400 for non-UUID action_id."""
    result = handler(_make_action_event("not-a-uuid", "confirm"), None)

    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert body["error"] == "Invalid action_id"


def test_action_dismiss_invalid_action_id_returns_400():
    """POST /actions/{bad_id}/dismiss returns 400 for non-UUID action_id."""
    result = handler(_make_action_event("INVALID", "dismiss"), None)

    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert body["error"] == "Invalid action_id"


@pytest.mark.parametrize("bad_id", [
    "not-a-uuid",
    "12345",
    "",
    "abc",
    "a1b2c3d4-e5f6-XXXX-8c9d-0e1f2a3b4c5d",  # invalid hex
])
def test_action_various_invalid_ids_return_400(bad_id):
    """Various invalid action_id formats all return 400."""
    result = handler(_make_action_event(bad_id, "confirm"), None)
    assert result["statusCode"] == 400


# --- Error mapping: 404 (action not found) ---


@patch("api_lambda.handler._tools_lambda_client")
def test_action_confirm_not_found_returns_404(mock_tools_client):
    """POST /actions/{id}/confirm returns 404 when action doesn't exist."""
    mock_tools_client.invoke.return_value = _make_tools_lambda_response(
        {"error": True, "message": f"Action not found: {VALID_ACTION_ID}"}
    )

    result = handler(_make_action_event(VALID_ACTION_ID, "confirm"), None)

    assert result["statusCode"] == 404
    body = json.loads(result["body"])
    assert body["error"] == "Action not found"


# --- Error mapping: 410 (action expired) ---


@patch("api_lambda.handler._tools_lambda_client")
def test_action_confirm_expired_returns_410(mock_tools_client):
    """POST /actions/{id}/confirm returns 410 when action has expired."""
    mock_tools_client.invoke.return_value = _make_tools_lambda_response(
        {"error": True, "message": "Action has expired"}
    )

    result = handler(_make_action_event(VALID_ACTION_ID, "confirm"), None)

    assert result["statusCode"] == 410
    body = json.loads(result["body"])
    assert body["error"] == "Action has expired"


# --- Error mapping: 409 (already processed) ---


@patch("api_lambda.handler._tools_lambda_client")
def test_action_confirm_already_processed_returns_409(mock_tools_client):
    """POST /actions/{id}/confirm returns 409 when action already confirmed/rejected."""
    mock_tools_client.invoke.return_value = _make_tools_lambda_response(
        {"error": True, "message": "Action already processed: status='confirmed'"}
    )

    result = handler(_make_action_event(VALID_ACTION_ID, "confirm"), None)

    assert result["statusCode"] == 409
    body = json.loads(result["body"])
    assert body["error"] == "Action already processed"


# --- Error mapping: 502 (upstream failure) ---


@patch("api_lambda.handler._tools_lambda_client")
def test_action_confirm_upstream_failure_returns_502(mock_tools_client):
    """POST /actions/{id}/confirm returns 502 on unexpected upstream error."""
    mock_tools_client.invoke.side_effect = Exception("Network error")

    result = handler(_make_action_event(VALID_ACTION_ID, "confirm"), None)

    assert result["statusCode"] == 502
    body = json.loads(result["body"])
    assert body["error"] == "Upstream service error"


@patch("api_lambda.handler._tools_lambda_client")
def test_action_dismiss_upstream_failure_returns_502(mock_tools_client):
    """POST /actions/{id}/dismiss returns 502 on unexpected upstream error."""
    mock_tools_client.invoke.side_effect = Exception("Network error")

    result = handler(_make_action_event(VALID_ACTION_ID, "dismiss"), None)

    assert result["statusCode"] == 502
    body = json.loads(result["body"])
    assert body["error"] == "Upstream service error"


# --- pending_actions pass-through (Task 5.5) ---


@patch("api_lambda.handler._agentcore_client")
def test_pending_actions_passes_through_in_recommendation(mock_client):
    """pending_actions field passes through recommendation response without modification."""
    recommendation_with_actions = {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 30.00,
            "saving_annual": 360.00,
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 55.00,
            "saving_annual": 660.00,
        },
        "pending_actions": [
            {
                "action_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                "action_type": "tariff_switch",
                "customer_id": "CUST-001",
                "payload": {"plan_id": "ECO", "plan_name": "EcoFlex 100"},
                "status": "pending",
            },
            {
                "action_id": "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
                "action_type": "send_sms",
                "customer_id": "CUST-001",
                "payload": {"message_body": "Thanks for calling us today"},
                "status": "pending",
            },
        ],
    }
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        recommendation_with_actions
    )

    result = handler(_make_recommendation_event("CUST-001"), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert "pending_actions" in body
    assert len(body["pending_actions"]) == 2
    assert body["pending_actions"][0]["action_type"] == "tariff_switch"
    assert body["pending_actions"][1]["action_type"] == "send_sms"
    # Verify pass-through is byte-identical
    assert body["pending_actions"] == recommendation_with_actions["pending_actions"]


@patch("api_lambda.handler._agentcore_client")
def test_recommendation_without_pending_actions_still_works(mock_client, mock_savings_response):
    """Existing recommendation response without pending_actions still returns 200."""
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        mock_savings_response
    )

    result = handler(_make_recommendation_event("CUST-001"), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert "green" in body
    assert "cheapest" in body


# --- Routing: existing routes unchanged ---


@patch("api_lambda.handler._agentcore_client")
def test_existing_recommendation_route_unchanged(mock_client, mock_savings_response):
    """Existing GET /recommendations/{customer_id} route still works after new routes added."""
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        mock_savings_response
    )

    result = handler(_make_recommendation_event("CUST-001"), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert "green" in body
    assert "cheapest" in body
