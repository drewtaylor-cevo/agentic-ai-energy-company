"""Observability tests for api_lambda/handler.py — field stripping contracts.

Verifies:
  - compliance_review is NOT stripped (Req 8.3 — public field)
  - supervisor_trace is NOT stripped (Req 9.3 — public field)
  - _narrative_source IS still stripped (Req 7.5 — existing contract preserved)

These tests exercise the handler's response processing logic to confirm that
the multi-agent supervisor's new public fields survive to the API response,
while the internal _narrative_source marker continues to be removed.
"""
import io
import json
from unittest.mock import patch

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


# --- Recommendation response with all supervisor fields ---


def _recommendation_body_with_supervisor_fields() -> dict:
    """A full recommendation response body including compliance_review and supervisor_trace."""
    return {
        "kind": "recommendation",
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 30.00,
            "saving_annual": 360.00,
            "usage_narrative": "Winter-heavy household with consistent usage.",
            "call_script": "Ask about EcoFlex for your winter profile.",
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 55.00,
            "saving_annual": 660.00,
            "usage_narrative": "Heavy evening usage peaking in December.",
            "call_script": "Consider Value 12 for simpler flat-rate billing.",
        },
        "reasoning_trace": [
            {"tool": "simulate_savings", "summary": "Green $30.00/mo; Cheapest $55.00/mo"},
        ],
        "_narrative_source": {
            "green": {"usage_narrative": "model", "call_script": "model"},
            "cheapest": {"usage_narrative": "model", "call_script": "model"},
        },
        "compliance_review": {
            "verdict": "pass",
            "rules_checked": ["reference_period_disclosure", "no_upsell_to_disadvantage"],
            "failures": [],
            "reviewed_at": "2025-01-15T10:30:00+00:00",
        },
        "supervisor_trace": {
            "routed_to": "TariffSpecialist",
            "routing_reason": "Standard recommendation request",
            "hardship_checked": True,
            "compliance_reviewed": True,
        },
    }


# --- 8.2: compliance_review NOT stripped by api_lambda/handler.py (Req 8.3) ---


@patch("api_lambda.handler._agentcore_client")
def test_compliance_review_not_stripped_by_api_lambda(mock_client):
    """Req 8.3: compliance_review is a public field — handler must NOT strip it.

    The handler strips _narrative_source (body.pop) but compliance_review
    is part of the demo trust story and must survive to the API response.
    """
    body = _recommendation_body_with_supervisor_fields()
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

    result = handler(_make_event("CUST-001"), None)

    assert result["statusCode"] == 200
    parsed = json.loads(result["body"])
    assert "compliance_review" in parsed, (
        "compliance_review must NOT be stripped by api_lambda/handler.py"
    )
    assert parsed["compliance_review"]["verdict"] == "pass"
    assert parsed["compliance_review"]["rules_checked"] == [
        "reference_period_disclosure",
        "no_upsell_to_disadvantage",
    ]


@patch("api_lambda.handler._agentcore_client")
def test_compliance_review_with_fail_verdict_not_stripped(mock_client):
    """Req 8.2: compliance_review with fail verdict also survives to the API response."""
    body = _recommendation_body_with_supervisor_fields()
    body["compliance_review"] = {
        "verdict": "fail",
        "rules_checked": ["reference_period_disclosure", "no_upsell_to_disadvantage"],
        "failures": ["reasoning_trace is missing or empty — no billing-period grounding evidence"],
        "reviewed_at": "2025-01-15T10:30:00+00:00",
    }
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

    result = handler(_make_event("CUST-001"), None)

    assert result["statusCode"] == 200
    parsed = json.loads(result["body"])
    assert "compliance_review" in parsed
    assert parsed["compliance_review"]["verdict"] == "fail"
    assert len(parsed["compliance_review"]["failures"]) == 1


# --- 8.2: supervisor_trace NOT stripped by api_lambda/handler.py (Req 9.3) ---


@patch("api_lambda.handler._agentcore_client")
def test_supervisor_trace_not_stripped_by_api_lambda(mock_client):
    """Req 9.3: supervisor_trace is a public field — handler must NOT strip it.

    The handler strips _narrative_source but supervisor_trace is part of
    the multi-agent orchestration demo story and must survive.
    """
    body = _recommendation_body_with_supervisor_fields()
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

    result = handler(_make_event("CUST-001"), None)

    assert result["statusCode"] == 200
    parsed = json.loads(result["body"])
    assert "supervisor_trace" in parsed, (
        "supervisor_trace must NOT be stripped by api_lambda/handler.py"
    )
    assert parsed["supervisor_trace"]["routed_to"] == "TariffSpecialist"
    assert parsed["supervisor_trace"]["hardship_checked"] is True
    assert parsed["supervisor_trace"]["compliance_reviewed"] is True


# --- 8.2: Both fields survive together on hardship responses ---


@patch("api_lambda.handler._agentcore_client")
def test_compliance_review_and_supervisor_trace_survive_on_hardship(mock_client):
    """Both public fields survive on hardship responses (kind: hardship → 200 path)."""
    hardship_body = {
        "kind": "hardship",
        "customer_id": "CUST-006",
        "reason": "Account flagged for specialist support.",
        "routing_target": "hardship_team",
        "call_script": "Let me connect you with our specialist team.",
        "_narrative_source": {"hardship": {"reason": "fallback", "call_script": "fallback"}},
        "compliance_review": {
            "verdict": "pass",
            "rules_checked": ["hardship_no_tariff_data"],
            "failures": [],
            "reviewed_at": "2025-01-15T10:30:00+00:00",
        },
        "supervisor_trace": {
            "routed_to": "HardshipSpecialist",
            "routing_reason": "Customer hardship flag is true",
            "hardship_checked": True,
            "compliance_reviewed": True,
        },
    }
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(hardship_body)

    result = handler(_make_event("CUST-006"), None)

    assert result["statusCode"] == 200
    parsed = json.loads(result["body"])
    # Both public fields survive
    assert "compliance_review" in parsed
    assert "supervisor_trace" in parsed
    # _narrative_source is still stripped
    assert "_narrative_source" not in parsed


# --- 8.3: _narrative_source IS still stripped (Req 7.5 — existing contract) ---


@patch("api_lambda.handler._agentcore_client")
def test_narrative_source_still_stripped_on_recommendation(mock_client):
    """Req 7.5: _narrative_source is an internal marker — handler MUST strip it.

    This is the existing contract from Phase 7 (D-06). The multi-agent
    refactor must not regress this behaviour.
    """
    body = _recommendation_body_with_supervisor_fields()
    # Confirm _narrative_source is present in the agent response
    assert "_narrative_source" in body

    mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

    result = handler(_make_event("CUST-001"), None)

    assert result["statusCode"] == 200
    parsed = json.loads(result["body"])
    assert "_narrative_source" not in parsed, (
        "_narrative_source must be stripped by api_lambda/handler.py (existing contract)"
    )


@patch("api_lambda.handler._agentcore_client")
def test_narrative_source_still_stripped_on_hardship(mock_client):
    """_narrative_source stripped from hardship responses too (Phase 14 contract)."""
    hardship_body = {
        "kind": "hardship",
        "customer_id": "CUST-006",
        "reason": "Account flagged for specialist support.",
        "routing_target": "hardship_team",
        "call_script": "Let me connect you with our specialist team.",
        "_narrative_source": {"hardship": {"reason": "fallback", "call_script": "fallback"}},
    }
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(hardship_body)

    result = handler(_make_event("CUST-006"), None)

    assert result["statusCode"] == 200
    parsed = json.loads(result["body"])
    assert "_narrative_source" not in parsed, (
        "_narrative_source must be stripped from hardship responses too"
    )


@patch("api_lambda.handler._agentcore_client")
def test_all_three_fields_correct_stripping_behaviour(mock_client):
    """Combined test: _narrative_source stripped, compliance_review + supervisor_trace preserved.

    This is the definitive contract test — all three fields in one response,
    verifying the handler's selective stripping logic.
    """
    body = _recommendation_body_with_supervisor_fields()
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

    result = handler(_make_event("CUST-001"), None)

    assert result["statusCode"] == 200
    parsed = json.loads(result["body"])

    # Internal marker stripped
    assert "_narrative_source" not in parsed

    # Public fields preserved
    assert "compliance_review" in parsed
    assert "supervisor_trace" in parsed

    # Content integrity
    assert parsed["compliance_review"]["verdict"] == "pass"
    assert parsed["supervisor_trace"]["routed_to"] == "TariffSpecialist"
