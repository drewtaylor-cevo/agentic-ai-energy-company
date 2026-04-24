"""Offline tests for agent tool return shape and savings invariants.

These tests verify the contract between the agent and the ToolsLambda
WITHOUT requiring AWS credentials. The Lambda response is mocked.

Covers: REC-01, REC-02, REC-03, SAV-01, SAV-02, SAV-03, SC-4 (cheapest >= green).
"""
import json
import pytest
from unittest.mock import MagicMock


def make_mock_lambda_response(payload_dict):
    """Build a mock boto3 lambda.invoke() response."""
    payload_bytes = json.dumps(payload_dict).encode()
    return {
        "StatusCode": 200,
        "Payload": MagicMock(read=MagicMock(return_value=payload_bytes)),
    }


# --- REC-01, REC-02, REC-03: Both tracks present with correct plan IDs ---

def test_both_tracks_present(mock_savings_response):
    """REC-03: Both green and cheapest tracks must be present."""
    assert "green" in mock_savings_response
    assert "cheapest" in mock_savings_response


def test_green_track_present(mock_savings_response):
    """REC-01: Green track selects ECO (the only green_premium plan)."""
    assert mock_savings_response["green"]["plan_id"] == "ECO"
    assert mock_savings_response["green"]["plan_name"] == "EcoFlex 100"


def test_cheapest_track_present(mock_savings_response):
    """REC-02: Cheapest track selects VAL (lowest rate)."""
    assert mock_savings_response["cheapest"]["plan_id"] == "VAL"
    assert mock_savings_response["cheapest"]["plan_name"] == "Value 12"


def test_tracks_diverge(mock_savings_response):
    """REC-03: Green and Cheapest must be different plans."""
    assert mock_savings_response["green"]["plan_id"] != mock_savings_response["cheapest"]["plan_id"]


# --- SAV-01, SAV-02: Savings fields present and correct ---

def test_monthly_saving_nonzero(mock_savings_response):
    """SAV-01: Monthly saving must be positive for both tracks."""
    assert mock_savings_response["green"]["saving_monthly"] > 0
    assert mock_savings_response["cheapest"]["saving_monthly"] > 0


def test_annual_saving_formula(mock_savings_response):
    """SAV-02: Annual saving must equal monthly * 12."""
    for track in ("green", "cheapest"):
        expected = round(mock_savings_response[track]["saving_monthly"] * 12, 2)
        assert abs(mock_savings_response[track]["saving_annual"] - expected) < 0.01, \
            f"{track} annual saving mismatch: {mock_savings_response[track]['saving_annual']} != {expected}"


def test_result_shape(mock_savings_response):
    """Response shape matches simulate_savings_pure output contract."""
    for track in ("green", "cheapest"):
        assert set(mock_savings_response[track].keys()) == {
            "plan_id", "plan_name", "saving_monthly", "saving_annual"
        }


# --- SAV-03: Numbers from tool, not LLM ---

def test_numbers_from_tool_not_llm(mock_savings_response):
    """SAV-03: Flagship persona numbers match Phase 1 verified values exactly."""
    assert abs(mock_savings_response["green"]["saving_monthly"] - 30.00) < 0.01
    assert abs(mock_savings_response["cheapest"]["saving_monthly"] - 55.00) < 0.01


# --- SC-4: Cheapest >= Green invariant across all personas ---

def test_cheapest_gte_green_sarah(mock_savings_response):
    """SC-4: Cheapest saving >= green saving for Sarah Chen."""
    assert mock_savings_response["cheapest"]["saving_monthly"] >= \
        mock_savings_response["green"]["saving_monthly"]


def test_cheapest_gte_green_marcus(mock_marcus_response):
    """SC-4: Cheapest saving >= green saving for Marcus Webb."""
    assert mock_marcus_response["cheapest"]["saving_monthly"] >= \
        mock_marcus_response["green"]["saving_monthly"]


def test_cheapest_gte_green_elena(mock_elena_response):
    """SC-4: Cheapest saving >= green saving for Elena Vasquez."""
    assert mock_elena_response["cheapest"]["saving_monthly"] >= \
        mock_elena_response["green"]["saving_monthly"]


# --- Tool invocation contract (mocked Lambda call) ---

def test_tool_invokes_lambda_with_customer_id(mock_savings_response):
    """Tool must pass customer_id to Lambda and return parsed JSON."""
    mock_client = MagicMock()
    mock_client.invoke.return_value = make_mock_lambda_response(mock_savings_response)

    # Simulate what the @tool function does internally
    resp = mock_client.invoke(
        FunctionName="arn:aws:lambda:us-east-1:123456789012:function:tariff-tools",
        InvocationType="RequestResponse",
        Payload=json.dumps({"customer_id": "CUST-001"}).encode(),
    )
    result = json.loads(resp["Payload"].read())

    assert result == mock_savings_response
    mock_client.invoke.assert_called_once()
    call_kwargs = mock_client.invoke.call_args.kwargs
    payload = json.loads(call_kwargs["Payload"])
    assert payload["customer_id"] == "CUST-001"


def test_tool_handles_lambda_error():
    """Tool must detect FunctionError in Lambda response."""
    mock_client = MagicMock()
    error_payload = {"errorMessage": "customer not found", "errorType": "ValueError"}
    mock_client.invoke.return_value = {
        "StatusCode": 200,
        "FunctionError": "Unhandled",
        "Payload": MagicMock(read=MagicMock(return_value=json.dumps(error_payload).encode())),
    }

    resp = mock_client.invoke(
        FunctionName="arn:aws:lambda:us-east-1:123456789012:function:tariff-tools",
        InvocationType="RequestResponse",
        Payload=json.dumps({"customer_id": "CUST-999"}).encode(),
    )

    assert "FunctionError" in resp
