"""Offline unit tests for api_lambda/handler.py — no AWS credentials needed.

Mocks the module-level _agentcore_client to test all handler paths:
validation, success pass-through, error taxonomy (400/404/502/504/500),
and fresh session ID per invocation (D-11).
"""
import io
import json
import logging
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


@patch("api_lambda.handler._agentcore_client")
def test_unknown_customer_sentinel_returns_404(mock_client):
    """D-13.1-13: synthetic UNKNOWN-track response body → HTTP 404.

    Defence-in-depth against Gap 2 regression. When the agent disobeys the
    EMPTY BILLING STOP rule (Phase 13.1 Plan 01, D-13.1-12) and synthesises
    a full RecommendationResponse with plan_id='UNKNOWN' on both tracks
    (the exact shape captured live in 13-08-CEREMONY-LOG.md §Post-freeze
    Live Sanity lines 112-121), the api_lambda sentinel branch catches it.

    Paired with test_unknown_customer_returns_404 in smoke (live coverage).
    """
    unknown_body = {
        "green": {
            "plan_id": "UNKNOWN",
            "plan_name": "UNKNOWN",
            "saving_monthly": 0.0,
            "saving_annual": 0.0,
            "usage_narrative": "Customer record not available.",
            "call_script": "Apologise; escalate to the customer-data team.",
        },
        "cheapest": {
            "plan_id": "UNKNOWN",
            "plan_name": "UNKNOWN",
            "saving_monthly": 0.0,
            "saving_annual": 0.0,
            "usage_narrative": "Customer record not available.",
            "call_script": "Apologise; escalate to the customer-data team.",
        },
        "reasoning_trace": [],
    }
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(unknown_body)

    result = handler(_make_event("CUST-999"), None)

    assert result["statusCode"] == 404, (
        f"D-13.1-13 sentinel did not fire for symmetric UNKNOWN body: "
        f"{result}"
    )
    body = json.loads(result["body"])
    assert "not found" in body["error"], (
        f"Error message did not match expected 'not found' string: "
        f"{body}"
    )


@patch("api_lambda.handler._agentcore_client")
def test_unknown_sentinel_fires_when_only_green_is_unknown(mock_client):
    """D-13.1-13 asymmetric variant — if ONLY green.plan_id == 'UNKNOWN',
    the sentinel still returns 404.

    Guards against a future Sonnet / Strands drift that emits placeholder
    on just one track. The CONTEXT.md D-13.1-13 rationale note
    ('symmetric across tracks because the LLM synthesises UNKNOWN on both
    simultaneously') reflects CURRENT observed behaviour; this test is
    the regression guard against that assumption changing.
    """
    half_unknown_body = {
        "green": {
            "plan_id": "UNKNOWN",
            "plan_name": "UNKNOWN",
            "saving_monthly": 0.0,
            "saving_annual": 0.0,
            "usage_narrative": "Customer record not available.",
            "call_script": "Apologise; escalate to the customer-data team.",
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 55.0,
            "saving_annual": 660.0,
            "usage_narrative": "Winter-heavy household with steady usage.",
            "call_script": "Ask about Value 12 — its flat pricing suits this profile.",
        },
        "reasoning_trace": [],
    }
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(half_unknown_body)

    result = handler(_make_event("CUST-999"), None)

    assert result["statusCode"] == 404, (
        f"D-13.1-13 sentinel did not fire for asymmetric UNKNOWN body "
        f"(green only): {result}"
    )


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


# --- Phase 7: Narrative pass-through + marker strip (D-06, D-07, D-08) ---


@patch("api_lambda.handler._agentcore_client")
def test_narrative_pass_through(mock_client, caplog):
    """D-06/D-07/D-08: narrative fields byte-identical, marker stripped, log fires."""
    agent_body = {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 30.00,
            "saving_annual": 360.00,
            "usage_narrative": "Winter-heavy household with consistent usage.",
            "call_script": "Ask about EcoFlex — it suits your winter profile.",
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 55.00,
            "saving_annual": 660.00,
            "usage_narrative": "Heavy evening usage peaking in December.",
            "call_script": "Consider Value 12 for simpler flat-rate billing.",
        },
        "_narrative_source": {
            "usage_narrative": "model",
            "call_script": "model",
        },
    }
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(agent_body)

    with caplog.at_level(logging.INFO, logger="api_lambda.handler"):
        result = handler(_make_event("CUST-001"), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])

    # D-06: marker stripped from response body.
    assert "_narrative_source" not in body

    # D-08: narrative fields flow byte-identically.
    assert body["green"]["usage_narrative"] == agent_body["green"]["usage_narrative"]
    assert body["green"]["call_script"] == agent_body["green"]["call_script"]
    assert body["cheapest"]["usage_narrative"] == agent_body["cheapest"]["usage_narrative"]
    assert body["cheapest"]["call_script"] == agent_body["cheapest"]["call_script"]

    # D-02 invariant: existing fields unchanged.
    assert body["green"]["saving_monthly"] == 30.00
    assert body["cheapest"]["saving_monthly"] == 55.00

    # D-07: structured narrative_source log fires exactly once with correct shape.
    narrative_source_logs = [
        json.loads(r.message) for r in caplog.records
        if r.message.startswith("{") and "narrative_source" in r.message
    ]
    assert len(narrative_source_logs) == 1
    assert narrative_source_logs[0] == {
        "event": "narrative_source",
        "customer_id": "CUST-001",
        "narrative_source": {"usage_narrative": "model", "call_script": "model"},
    }


@patch("api_lambda.handler._agentcore_client")
def test_narrative_pass_through_marker_absent(mock_client, caplog, mock_savings_response):
    """D-06/D-07: pop(..., None) is silent when marker absent; log fires with null."""
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        mock_savings_response
    )

    with caplog.at_level(logging.INFO, logger="api_lambda.handler"):
        result = handler(_make_event("CUST-001"), None)

    assert result["statusCode"] == 200
    # Pass-through unchanged when marker absent.
    assert json.loads(result["body"]) == mock_savings_response

    # D-07: log fires on every successful invoke; narrative_source is null here.
    narrative_source_logs = [
        json.loads(r.message) for r in caplog.records
        if r.message.startswith("{") and "narrative_source" in r.message
    ]
    assert len(narrative_source_logs) == 1
    assert narrative_source_logs[0]["event"] == "narrative_source"
    assert narrative_source_logs[0]["customer_id"] == "CUST-001"
    assert narrative_source_logs[0]["narrative_source"] is None


# --- Phase 7: Prewarm branch (D-01, D-02, D-04, D-05) ---


@patch("api_lambda.handler._agentcore_client")
def test_prewarm_returns_204_happy_path(mock_client, caplog, mock_savings_response):
    """D-02: ?prewarm=1 runs full invoke + returns 204 + NO narrative_source log."""
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        mock_savings_response
    )

    event = _make_event("CUST-001")
    event["queryStringParameters"] = {"prewarm": "1"}

    with caplog.at_level(logging.INFO, logger="api_lambda.handler"):
        result = handler(event, None)

    assert result["statusCode"] == 204
    assert result.get("body", "") == ""
    assert result.get("headers", {}) == {}

    # D-02: full real invoke fired exactly once.
    assert mock_client.invoke_agent_runtime.call_count == 1
    call = mock_client.invoke_agent_runtime.call_args
    assert "runtimeSessionId" in call.kwargs
    # D-11 / AP-3: fresh uuid4, 36-char.
    assert len(call.kwargs["runtimeSessionId"]) == 36
    payload = json.loads(call.kwargs["payload"].decode())
    assert payload == {"customer_id": "CUST-001"}

    # Prewarm path does NOT emit narrative_source (body discarded).
    narrative_source_logs = [
        r for r in caplog.records
        if r.message.startswith("{") and "narrative_source" in r.message
    ]
    assert len(narrative_source_logs) == 0


@patch("api_lambda.handler._agentcore_client")
def test_prewarm_returns_204_on_client_error(mock_client, caplog):
    """D-04: ClientError in prewarm → 204 + prewarm_failed log with error_code."""
    from botocore.exceptions import ClientError

    mock_client.invoke_agent_runtime.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "InvokeAgentRuntime",
    )

    event = _make_event("CUST-001")
    event["queryStringParameters"] = {"prewarm": "1"}

    with caplog.at_level(logging.WARNING, logger="api_lambda.handler"):
        result = handler(event, None)

    # SC-2: NEVER 5xx on prewarm.
    assert result["statusCode"] == 204

    prewarm_logs = [
        json.loads(r.message) for r in caplog.records
        if r.message.startswith("{") and "prewarm_failed" in r.message
    ]
    assert len(prewarm_logs) == 1
    assert prewarm_logs[0]["event"] == "prewarm_failed"
    assert prewarm_logs[0]["customer_id"] == "CUST-001"
    assert prewarm_logs[0]["error_code"] == "ThrottlingException"


@patch("api_lambda.handler._agentcore_client")
def test_prewarm_returns_204_on_read_timeout(mock_client, caplog):
    """D-04: ReadTimeoutError in prewarm → 204 + prewarm_failed log.

    Transport-level error (not a ClientError subclass) — error_code falls
    through to type(exc).__name__ per Pattern 2 swallow-all logic.
    """
    from botocore.exceptions import ReadTimeoutError

    mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(
        endpoint_url="https://example.com"
    )

    event = _make_event("CUST-001")
    event["queryStringParameters"] = {"prewarm": "1"}

    with caplog.at_level(logging.WARNING, logger="api_lambda.handler"):
        result = handler(event, None)

    assert result["statusCode"] == 204
    prewarm_logs = [
        json.loads(r.message) for r in caplog.records
        if r.message.startswith("{") and "prewarm_failed" in r.message
    ]
    assert len(prewarm_logs) == 1
    assert prewarm_logs[0]["error_code"] == "ReadTimeoutError"


@patch("api_lambda.handler._agentcore_client")
def test_prewarm_invalid_customer_id_returns_400(mock_client):
    """D-01/D-13: ?prewarm=1 + bad customer_id still returns 400 (regex runs first)."""
    event = _make_event("NOTVALID")
    event["queryStringParameters"] = {"prewarm": "1"}

    result = handler(event, None)

    # D-13 regex runs BEFORE prewarm dispatch — fast-fail on format.
    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "Invalid customer ID format" in body["error"]

    # Invoke was NEVER called — 400 returned before dispatch.
    assert mock_client.invoke_agent_runtime.call_count == 0


# ----------------------------------------------------------------------
# Phase 13 Plan 05 — D-12 reasoning_trace pass-through contract.
# api_lambda/handler.py MUST NOT strip or mutate `reasoning_trace`. It
# MUST still 404 when green/cheapest absent regardless of reasoning_trace.
# ----------------------------------------------------------------------


@patch("api_lambda.handler._agentcore_client")
def test_reasoning_trace_passes_through_unchanged(mock_client):
    """D-12: api_lambda/handler.py is dumb — reasoning_trace arrives byte-equal."""
    body_with_trace = {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 14.00,
            "saving_annual": 168.00,
            "usage_narrative": "Strong cool-season usage pattern.",
            "call_script": "Ask about EcoFlex for winter comfort.",
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 25.67,
            "saving_annual": 308.04,
            "usage_narrative": "Lowest-cost option for stable usage.",
            "call_script": "Frame Value 12 as the budget-safe choice.",
        },
        "reasoning_trace": [
            {"tool": "get_hardship_flag", "summary": "hardship_flag=False"},
            {
                "tool": "detect_bill_shock",
                "summary": "Bill shock detected: +$47.00 2025-10 vs 11-month avg ($135.00 vs $88.00)",
            },
            {"tool": "simulate_savings", "summary": "Green $14.00/mo; Cheapest $25.67/mo"},
        ],
    }
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(body_with_trace)

    result = handler(_make_event("CUST-003"), None)

    assert result["statusCode"] == 200
    parsed_body = json.loads(result["body"])
    # reasoning_trace arrives byte-identical — no mutation, no stripping.
    assert parsed_body["reasoning_trace"] == body_with_trace["reasoning_trace"]
    assert len(parsed_body["reasoning_trace"]) == 3
    # Currency + digits + dates survive (sanity — D-15 does not apply).
    assert "$" in parsed_body["reasoning_trace"][1]["summary"]


@patch("api_lambda.handler._agentcore_client")
def test_reasoning_trace_not_stripped_like_narrative_source(mock_client):
    """D-12: ensure api_lambda/handler.py does NOT body.pop('reasoning_trace').

    Parallels the _narrative_source strip (which IS applied at line 121) —
    reasoning_trace is PUBLIC and must survive to the client.
    """
    body = {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 30.00,
            "saving_annual": 360.00,
            "usage_narrative": "n",
            "call_script": "c",
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 55.00,
            "saving_annual": 660.00,
            "usage_narrative": "n",
            "call_script": "c",
        },
        "reasoning_trace": [],
        "_narrative_source": {"green": {}, "cheapest": {}},
    }
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

    result = handler(_make_event("CUST-001"), None)

    parsed = json.loads(result["body"])
    # _narrative_source IS stripped (existing behaviour, Plan 06 Phase 7 D-06).
    assert "_narrative_source" not in parsed
    # reasoning_trace is NOT stripped (Phase 13 D-12).
    assert "reasoning_trace" in parsed
    assert parsed["reasoning_trace"] == []


@patch("api_lambda.handler._agentcore_client")
def test_customer_not_found_detection_unchanged_with_reasoning_trace(mock_client):
    """Regression: api_lambda/handler.py:152 detection is Phase 14 territory.

    Phase 13 MUST NOT regress the current 404 behaviour — missing green/cheapest
    still returns 404, even if reasoning_trace is present. Phase 14 amends this
    to condition on body.get('kind') != 'hardship'.
    """
    # Simulated agent fallback when customer not found — trace may still be present
    # (e.g. agent got partway through tool calls before failing).
    body_without_tracks = {
        "errorMessage": "Customer CUST-999 not found",
        "reasoning_trace": [
            {"tool": "get_hardship_flag", "summary": "hardship_flag=False"},
        ],
    }
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(body_without_tracks)

    result = handler(_make_event("CUST-999"), None)

    # Current Phase 13 behaviour: 404 (neither green nor cheapest present).
    # Phase 14 will amend to condition on kind != hardship — but that's not this phase.
    assert result["statusCode"] == 404


# --- Phase 14 AGENT-02a: Hardship response routing ---


@patch("api_lambda.handler._agentcore_client")
def test_hardship_response_returns_200(mock_client):
    """AGENT-02a: kind: 'hardship' body without green/cheapest → HTTP 200, not 404."""
    hardship_body = {
        "kind": "hardship",
        "customer_id": "CUST-006",
        "reason": "This customer account is flagged for dedicated support.",
        "routing_target": "hardship_team",
        "call_script": "Let me connect you with our specialist support team.",
        "_narrative_source": {"hardship": {"reason": "fallback", "call_script": "fallback"}},
    }
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(hardship_body)

    result = handler(_make_event("CUST-006"), None)

    assert result["statusCode"] == 200, (
        f"Hardship response should be HTTP 200, got {result['statusCode']}"
    )
    body = json.loads(result["body"])
    assert body["kind"] == "hardship"
    assert body["customer_id"] == "CUST-006"
    assert body["routing_target"] == "hardship_team"


@patch("api_lambda.handler._agentcore_client")
def test_hardship_response_has_no_green_cheapest(mock_client):
    """AGENT-02a: hardship body passes through without green/cheapest keys."""
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
    body = json.loads(result["body"])

    assert "green" not in body, "Hardship response must not contain green track"
    assert "cheapest" not in body, "Hardship response must not contain cheapest track"


@patch("api_lambda.handler._agentcore_client")
def test_hardship_response_strips_narrative_source(mock_client):
    """Phase 7 contract: _narrative_source stripped from hardship responses too."""
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
    body = json.loads(result["body"])

    assert "_narrative_source" not in body, (
        "_narrative_source marker must be stripped from hardship responses"
    )


@patch("api_lambda.handler._agentcore_client")
def test_recommendation_still_returns_200_after_hardship_update(mock_client, mock_savings_response):
    """REC-03 regression: recommendation path unchanged after Phase 14 surgical update."""
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        mock_savings_response
    )
    result = handler(_make_event("CUST-001"), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert "green" in body
    assert "cheapest" in body


@patch("api_lambda.handler._agentcore_client")
def test_unknown_customer_still_returns_404_after_hardship_update(mock_client):
    """D-12 regression: missing tracks WITHOUT kind: 'hardship' still → 404."""
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        {"errorMessage": "No billing history for 'CUST-999'"}
    )
    result = handler(_make_event("CUST-999"), None)

    assert result["statusCode"] == 404, (
        f"Missing tracks without kind: hardship should still be 404, got {result['statusCode']}"
    )


@patch("api_lambda.handler._agentcore_client")
def test_unknown_sentinel_still_returns_404_after_hardship_update(mock_client):
    """D-13.1-13 regression: UNKNOWN sentinel still fires after Phase 14 update."""
    unknown_body = {
        "green": {"plan_id": "UNKNOWN", "plan_name": "UNKNOWN", "saving_monthly": 0.0, "saving_annual": 0.0},
        "cheapest": {"plan_id": "UNKNOWN", "plan_name": "UNKNOWN", "saving_monthly": 0.0, "saving_annual": 0.0},
    }
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(unknown_body)

    result = handler(_make_event("CUST-999"), None)

    assert result["statusCode"] == 404, (
        f"UNKNOWN sentinel should still fire after Phase 14 update, got {result['statusCode']}"
    )
