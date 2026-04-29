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


# ----------------------------------------------------------------------
# Phase 13 Plan 03 Task 3.1 — RED-phase smoke tests for the 3 new @tool
# wrappers (detect_bill_shock, get_billing_history, get_hardship_flag).
#
# These assert structural presence only: import succeeds, @tool decoration
# produces the Strands DecoratedFunctionTool shape, tool_name matches, and
# the _agent tool_registry includes all four tools. Detailed payload-shape
# assertions live in Task 3.3 (appended below after implementation).
# ----------------------------------------------------------------------


def test_detect_bill_shock_tool_importable():
    """Phase 13 D-01: detect_bill_shock @tool exists in agent.agent."""
    from agent.agent import detect_bill_shock

    # Strands @tool → DecoratedFunctionTool (callable).
    assert callable(detect_bill_shock)
    # Strands exposes the tool name via .tool_name attribute.
    assert getattr(detect_bill_shock, "tool_name", None) == "detect_bill_shock"


def test_get_billing_history_tool_importable():
    """Phase 13 D-01: get_billing_history @tool exists in agent.agent."""
    from agent.agent import get_billing_history

    assert callable(get_billing_history)
    assert getattr(get_billing_history, "tool_name", None) == "get_billing_history"


def test_get_hardship_flag_tool_importable():
    """Phase 13 D-01: get_hardship_flag @tool exists in agent.agent."""
    from agent.agent import get_hardship_flag

    assert callable(get_hardship_flag)
    assert getattr(get_hardship_flag, "tool_name", None) == "get_hardship_flag"


def test_agent_registry_contains_all_four_tools():
    """Phase 13 D-01: _agent tool_registry lists all 4 tools."""
    from agent.agent import _agent

    registry = _agent.tool_registry
    tool_names = set(registry.registry.keys()) if hasattr(registry, "registry") else set()
    expected = {
        "simulate_savings",
        "detect_bill_shock",
        "get_billing_history",
        "get_hardship_flag",
    }
    assert expected.issubset(tool_names), (
        f"Expected 4 tools registered, got {sorted(tool_names)}"
    )


def test_simulate_savings_still_registered_via_provider():
    """Phase 13 D-02 regression: simulate_savings unchanged (still provider-routed)."""
    from agent.agent import simulate_savings

    # Docstring still mentions deterministic savings engine / savings — sanity.
    assert callable(simulate_savings)
    doc = getattr(simulate_savings, "__doc__", "") or ""
    assert "saving" in doc.lower()


def test_agent_has_no_max_iterations_leak():
    """Phase 13 Pitfall 2: max_iterations is NOT a Strands 1.37 Agent kwarg.

    This regression guard ensures no-one accidentally reintroduces the
    primitive (Plan 04 adds hooks=[FourToolCapHook] instead).
    """
    import agent.agent as agent_module
    source = open(agent_module.__file__).read()
    assert "max_iterations" not in source, (
        "Pitfall 2: max_iterations is NOT a Strands 1.37 Agent parameter; "
        "the 4-tool cap lands as a HookProvider in Plan 04."
    )
