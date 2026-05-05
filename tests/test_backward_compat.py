"""Backward Compatibility Verification Tests — Task 8 (agentic-actions-portfolio).

Confirms that all existing API contracts and behaviors are preserved after
the agentic-actions-portfolio feature was added. These tests verify:

  8.1 — GET /recommendations/{customer_id} returns valid responses without
        requiring pending_actions (field is optional, default empty list).
  8.2 — SSE streaming contract unchanged — pending_actions included in
        result event payload when present.
  8.3 — GET /recommendations/{customer_id}/follow-up endpoint unchanged.
  8.4 — ?prewarm=1 still returns HTTP 204 with empty body.
  8.6 — Integration tests for all 6 personas (CUST-001 through CUST-006)
        still produce valid responses.

Requirements validated: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6
"""
import io
import json
from unittest.mock import patch

import pytest

try:
    from api_lambda.handler import handler, stream_handler
    _CAN_IMPORT = True
    _IMPORT_ERROR = ""
except ImportError as e:
    _CAN_IMPORT = False
    _IMPORT_ERROR = str(e)

pytestmark = pytest.mark.skipif(
    not _CAN_IMPORT,
    reason="api_lambda.handler import failed: {}".format(_IMPORT_ERROR),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(customer_id: str, query_params: dict | None = None, raw_path: str | None = None) -> dict:
    """Build a minimal HTTP API v2 event."""
    event = {
        "pathParameters": {"customer_id": customer_id},
        "rawPath": raw_path or f"/recommendations/{customer_id}",
    }
    if query_params:
        event["queryStringParameters"] = query_params
    return event


def _make_agent_response(body: dict) -> dict:
    """Construct a mock invoke_agent_runtime response."""
    return {
        "response": io.BytesIO(json.dumps(body).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }


class _MockResponseStream:
    """Mock response_stream that captures .write(bytes) calls."""

    def __init__(self):
        self.chunks: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.chunks.append(data)

    @property
    def written_str(self) -> str:
        return b"".join(self.chunks).decode("utf-8")


def _parse_sse_events(raw: str) -> list[tuple[str, dict]]:
    """Parse SSE frames from raw response stream output."""
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


# ---------------------------------------------------------------------------
# Persona response fixtures (all 6 personas)
# ---------------------------------------------------------------------------


def _recommendation_body(customer_id: str, green: dict, cheapest: dict, **extra) -> dict:
    """Build a valid recommendation response body."""
    body = {
        "green": green,
        "cheapest": cheapest,
    }
    body.update(extra)
    return body


# Canonical savings for each persona (matches conftest.py fixtures).
_PERSONA_RESPONSES = {
    "CUST-001": {
        "green": {"plan_id": "ECO", "plan_name": "EcoFlex 100", "saving_monthly": 30.00, "saving_annual": 360.00},
        "cheapest": {"plan_id": "VAL", "plan_name": "Value 12", "saving_monthly": 55.00, "saving_annual": 660.00},
    },
    "CUST-002": {
        "green": {"plan_id": "ECO", "plan_name": "EcoFlex 100", "saving_monthly": 16.90, "saving_annual": 202.80},
        "cheapest": {"plan_id": "VAL", "plan_name": "Value 12", "saving_monthly": 30.98, "saving_annual": 371.76},
    },
    "CUST-003": {
        "green": {"plan_id": "ECO", "plan_name": "EcoFlex 100", "saving_monthly": 14.00, "saving_annual": 168.00},
        "cheapest": {"plan_id": "VAL", "plan_name": "Value 12", "saving_monthly": 25.67, "saving_annual": 308.04},
    },
    "CUST-004": {
        "green": {"plan_id": "ECO", "plan_name": "EcoFlex 100", "saving_monthly": 40.02, "saving_annual": 480.24},
        "cheapest": {"plan_id": "SOL", "plan_name": "Solar Feed-in", "saving_monthly": 76.03, "saving_annual": 912.36},
    },
    "CUST-005": {
        "green": {"plan_id": "ECO", "plan_name": "EcoFlex 100", "saving_monthly": 35.00, "saving_annual": 420.00},
        "cheapest": {"plan_id": "EV-TOU", "plan_name": "EV Drive TOU", "saving_monthly": 84.00, "saving_annual": 1008.00},
    },
    "CUST-006": {
        "kind": "hardship",
        "customer_id": "CUST-006",
        "reason": "This customer account is flagged for dedicated support from our specialist team.",
        "routing_target": "hardship_team",
        "call_script": "Let me connect you with our specialist support team who can best help with your account.",
    },
}


# ---------------------------------------------------------------------------
# 8.1 — GET /recommendations/{customer_id} without pending_actions
# ---------------------------------------------------------------------------


class TestRecommendationWithoutPendingActions:
    """Verify existing endpoint works without requiring pending_actions field."""

    @patch("api_lambda.handler._agentcore_client")
    def test_response_without_pending_actions_returns_200(self, mock_client):
        """Recommendation response without pending_actions field returns 200."""
        body = _PERSONA_RESPONSES["CUST-001"]
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        result = handler(_make_event("CUST-001"), None)

        assert result["statusCode"] == 200
        parsed = json.loads(result["body"])
        assert "green" in parsed
        assert "cheapest" in parsed
        # pending_actions is NOT required — absence is valid
        assert parsed.get("pending_actions") is None or isinstance(parsed.get("pending_actions"), list)

    @patch("api_lambda.handler._agentcore_client")
    def test_response_with_empty_pending_actions_returns_200(self, mock_client):
        """Recommendation response with empty pending_actions returns 200."""
        body = {**_PERSONA_RESPONSES["CUST-001"], "pending_actions": []}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        result = handler(_make_event("CUST-001"), None)

        assert result["statusCode"] == 200
        parsed = json.loads(result["body"])
        assert parsed["pending_actions"] == []

    @patch("api_lambda.handler._agentcore_client")
    def test_response_with_pending_actions_passes_through(self, mock_client):
        """Recommendation response with pending_actions passes through unchanged."""
        actions = [
            {
                "action_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                "action_type": "tariff_switch",
                "customer_id": "CUST-001",
                "payload": {"plan_id": "ECO", "plan_name": "EcoFlex 100"},
                "status": "pending",
            }
        ]
        body = {**_PERSONA_RESPONSES["CUST-001"], "pending_actions": actions}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        result = handler(_make_event("CUST-001"), None)

        assert result["statusCode"] == 200
        parsed = json.loads(result["body"])
        assert parsed["pending_actions"] == actions

    @patch("api_lambda.handler._agentcore_client")
    def test_green_cheapest_fields_unchanged(self, mock_client):
        """Green and cheapest track fields are byte-identical in response."""
        body = _PERSONA_RESPONSES["CUST-001"]
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        result = handler(_make_event("CUST-001"), None)

        parsed = json.loads(result["body"])
        assert parsed["green"] == body["green"]
        assert parsed["cheapest"] == body["cheapest"]


# ---------------------------------------------------------------------------
# 8.2 — SSE streaming contract unchanged
# ---------------------------------------------------------------------------


class TestSSEStreamingContract:
    """Verify SSE streaming includes pending_actions in result event payload."""

    @patch("api_lambda.handler._agentcore_client")
    def test_sse_result_event_includes_pending_actions(self, mock_client):
        """SSE result event payload includes pending_actions when present."""
        actions = [
            {
                "action_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                "action_type": "tariff_switch",
                "customer_id": "CUST-001",
                "payload": {"plan_id": "ECO"},
                "status": "pending",
            }
        ]
        body = {**_PERSONA_RESPONSES["CUST-001"], "pending_actions": actions}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        stream = _MockResponseStream()
        event = {
            "pathParameters": {"customer_id": "CUST-001"},
            "rawPath": "/recommendations/CUST-001",
            "headers": {"accept": "text/event-stream"},
            "queryStringParameters": None,
        }
        stream_handler(event, stream, None)

        events = _parse_sse_events(stream.written_str)
        # Should have result + done events
        result_events = [(t, d) for t, d in events if t == "result"]
        assert len(result_events) == 1
        result_data = result_events[0][1]
        assert "pending_actions" in result_data
        assert result_data["pending_actions"] == actions

    @patch("api_lambda.handler._agentcore_client")
    def test_sse_result_event_without_pending_actions(self, mock_client):
        """SSE result event works when pending_actions is absent."""
        body = _PERSONA_RESPONSES["CUST-001"]
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        stream = _MockResponseStream()
        event = {
            "pathParameters": {"customer_id": "CUST-001"},
            "rawPath": "/recommendations/CUST-001",
            "headers": {"accept": "text/event-stream"},
            "queryStringParameters": None,
        }
        stream_handler(event, stream, None)

        events = _parse_sse_events(stream.written_str)
        result_events = [(t, d) for t, d in events if t == "result"]
        assert len(result_events) == 1
        result_data = result_events[0][1]
        assert "green" in result_data
        assert "cheapest" in result_data

    @patch("api_lambda.handler._agentcore_client")
    def test_sse_done_event_still_emitted(self, mock_client):
        """SSE done event is still emitted after result event."""
        body = _PERSONA_RESPONSES["CUST-001"]
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        stream = _MockResponseStream()
        event = {
            "pathParameters": {"customer_id": "CUST-001"},
            "rawPath": "/recommendations/CUST-001",
            "headers": {"accept": "text/event-stream"},
            "queryStringParameters": None,
        }
        stream_handler(event, stream, None)

        events = _parse_sse_events(stream.written_str)
        event_types = [t for t, _ in events]
        assert "done" in event_types
        # done is always last
        assert event_types[-1] == "done"

    @patch("api_lambda.handler._agentcore_client")
    def test_sse_error_event_format_unchanged(self, mock_client):
        """SSE error event format unchanged (status + message fields)."""
        from botocore.exceptions import ReadTimeoutError
        mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(
            endpoint_url="https://example.com"
        )

        stream = _MockResponseStream()
        event = {
            "pathParameters": {"customer_id": "CUST-001"},
            "rawPath": "/recommendations/CUST-001",
            "headers": {"accept": "text/event-stream"},
            "queryStringParameters": None,
        }
        stream_handler(event, stream, None)

        events = _parse_sse_events(stream.written_str)
        error_events = [(t, d) for t, d in events if t == "error"]
        assert len(error_events) == 1
        error_data = error_events[0][1]
        assert "status" in error_data
        assert "message" in error_data
        assert error_data["status"] == 504


# ---------------------------------------------------------------------------
# 8.3 — GET /recommendations/{customer_id}/follow-up unchanged
# ---------------------------------------------------------------------------


class TestFollowUpEndpointUnchanged:
    """Verify follow-up endpoint still works after agentic-actions-portfolio."""

    @patch("api_lambda.handler._agentcore_client")
    def test_follow_up_returns_200_with_valid_shape(self, mock_client):
        """Follow-up endpoint returns 200 with kind=follow_up response."""
        follow_up_body = {
            "kind": "follow_up",
            "customer_id": "CUST-001",
            "subject": "Your tariff options from our recent conversation",
            "body": (
                "Thank you for speaking with us about your energy plan options. "
                "As discussed, we identified plans that could better suit your household "
                "usage pattern. Please review the options at your convenience."
            ),
            "plan_reference": "EcoFlex Green",
        }
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(follow_up_body)

        event = _make_event(
            "CUST-001",
            raw_path="/recommendations/CUST-001/follow-up",
        )
        result = handler(event, None)

        assert result["statusCode"] == 200
        parsed = json.loads(result["body"])
        assert parsed["kind"] == "follow_up"
        assert parsed["customer_id"] == "CUST-001"
        assert "subject" in parsed
        assert "body" in parsed
        assert "plan_reference" in parsed

    @patch("api_lambda.handler._agentcore_client")
    def test_follow_up_strips_internal_markers(self, mock_client):
        """Follow-up endpoint strips _workflow_source and _narrative_source."""
        follow_up_body = {
            "kind": "follow_up",
            "customer_id": "CUST-001",
            "subject": "Your tariff options from our recent conversation",
            "body": "Thank you for speaking with us about your energy plan options.",
            "plan_reference": "EcoFlex Green",
            "_workflow_source": {"subject": "model"},
            "_narrative_source": {"body": "model"},
        }
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(follow_up_body)

        event = _make_event(
            "CUST-001",
            raw_path="/recommendations/CUST-001/follow-up",
        )
        result = handler(event, None)

        parsed = json.loads(result["body"])
        assert "_workflow_source" not in parsed
        assert "_narrative_source" not in parsed

    @patch("api_lambda.handler._agentcore_client")
    def test_follow_up_invalid_customer_returns_400(self, mock_client):
        """Follow-up endpoint with invalid customer_id returns 400."""
        event = _make_event(
            "INVALID",
            raw_path="/recommendations/INVALID/follow-up",
        )
        result = handler(event, None)
        assert result["statusCode"] == 400


# ---------------------------------------------------------------------------
# 8.4 — ?prewarm=1 still returns HTTP 204
# ---------------------------------------------------------------------------


class TestPrewarmUnchanged:
    """Verify ?prewarm=1 still returns HTTP 204 with empty body."""

    @patch("api_lambda.handler._agentcore_client")
    def test_prewarm_returns_204_on_success(self, mock_client):
        """?prewarm=1 returns 204 with empty body on success."""
        body = _PERSONA_RESPONSES["CUST-001"]
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        event = _make_event("CUST-001", query_params={"prewarm": "1"})
        result = handler(event, None)

        assert result["statusCode"] == 204
        assert result.get("body", "") == ""
        assert result.get("headers", {}) == {}

    @patch("api_lambda.handler._agentcore_client")
    def test_prewarm_returns_204_on_failure(self, mock_client):
        """?prewarm=1 returns 204 even when agent invocation fails (D-04)."""
        mock_client.invoke_agent_runtime.side_effect = Exception("Connection refused")

        event = _make_event("CUST-001", query_params={"prewarm": "1"})
        result = handler(event, None)

        assert result["statusCode"] == 204
        assert result.get("body", "") == ""

    @patch("api_lambda.handler._agentcore_client")
    def test_prewarm_with_invalid_customer_returns_400(self, mock_client):
        """?prewarm=1 with invalid customer_id still returns 400 (regex first)."""
        event = _make_event("BAD", query_params={"prewarm": "1"})
        result = handler(event, None)

        assert result["statusCode"] == 400
        assert mock_client.invoke_agent_runtime.call_count == 0


# ---------------------------------------------------------------------------
# 8.6 — Integration tests for all 6 personas
# ---------------------------------------------------------------------------


class TestAllPersonaFlows:
    """Integration tests confirming all existing persona flows produce valid responses."""

    @patch("api_lambda.handler._agentcore_client")
    def test_cust001_returns_valid_recommendation(self, mock_client):
        """CUST-001 (Sarah Chen) returns valid recommendation with green + cheapest."""
        body = _PERSONA_RESPONSES["CUST-001"]
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        result = handler(_make_event("CUST-001"), None)

        assert result["statusCode"] == 200
        parsed = json.loads(result["body"])
        assert parsed["green"]["plan_id"] == "ECO"
        assert parsed["cheapest"]["plan_id"] == "VAL"
        assert parsed["green"]["saving_monthly"] == 30.00
        assert parsed["cheapest"]["saving_monthly"] == 55.00

    @patch("api_lambda.handler._agentcore_client")
    def test_cust002_returns_valid_recommendation(self, mock_client):
        """CUST-002 (Marcus Webb) returns valid recommendation."""
        body = _PERSONA_RESPONSES["CUST-002"]
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        result = handler(_make_event("CUST-002"), None)

        assert result["statusCode"] == 200
        parsed = json.loads(result["body"])
        assert parsed["green"]["plan_id"] == "ECO"
        assert parsed["cheapest"]["plan_id"] == "VAL"
        assert parsed["green"]["saving_monthly"] == 16.90
        assert parsed["cheapest"]["saving_monthly"] == 30.98

    @patch("api_lambda.handler._agentcore_client")
    def test_cust003_returns_valid_recommendation(self, mock_client):
        """CUST-003 (Elena Vasquez) returns valid recommendation."""
        body = _PERSONA_RESPONSES["CUST-003"]
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        result = handler(_make_event("CUST-003"), None)

        assert result["statusCode"] == 200
        parsed = json.loads(result["body"])
        assert parsed["green"]["plan_id"] == "ECO"
        assert parsed["cheapest"]["plan_id"] == "VAL"
        assert parsed["green"]["saving_monthly"] == 14.00
        assert parsed["cheapest"]["saving_monthly"] == 25.67

    @patch("api_lambda.handler._agentcore_client")
    def test_cust004_returns_valid_recommendation(self, mock_client):
        """CUST-004 (solar persona) returns valid recommendation."""
        body = _PERSONA_RESPONSES["CUST-004"]
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        result = handler(_make_event("CUST-004"), None)

        assert result["statusCode"] == 200
        parsed = json.loads(result["body"])
        assert parsed["green"]["plan_id"] == "ECO"
        assert parsed["cheapest"]["plan_id"] == "SOL"
        assert parsed["green"]["saving_monthly"] == 40.02
        assert parsed["cheapest"]["saving_monthly"] == 76.03

    @patch("api_lambda.handler._agentcore_client")
    def test_cust005_returns_valid_recommendation(self, mock_client):
        """CUST-005 (EV persona) returns valid recommendation."""
        body = _PERSONA_RESPONSES["CUST-005"]
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        result = handler(_make_event("CUST-005"), None)

        assert result["statusCode"] == 200
        parsed = json.loads(result["body"])
        assert parsed["green"]["plan_id"] == "ECO"
        assert parsed["cheapest"]["plan_id"] == "EV-TOU"
        assert parsed["green"]["saving_monthly"] == 35.00
        assert parsed["cheapest"]["saving_monthly"] == 84.00

    @patch("api_lambda.handler._agentcore_client")
    def test_cust006_returns_hardship_response(self, mock_client):
        """CUST-006 (hardship persona) returns valid hardship response."""
        body = _PERSONA_RESPONSES["CUST-006"]
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        result = handler(_make_event("CUST-006"), None)

        assert result["statusCode"] == 200
        parsed = json.loads(result["body"])
        assert parsed["kind"] == "hardship"
        assert parsed["customer_id"] == "CUST-006"
        assert parsed["routing_target"] == "hardship_team"
        assert "green" not in parsed
        assert "cheapest" not in parsed

    @patch("api_lambda.handler._agentcore_client")
    def test_cust001_with_reasoning_trace_passes_through(self, mock_client):
        """CUST-001 with reasoning_trace passes through unchanged."""
        body = {
            **_PERSONA_RESPONSES["CUST-001"],
            "reasoning_trace": [
                {"tool": "simulate_savings", "summary": "Green $30.00/mo; Cheapest $55.00/mo"},
            ],
        }
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        result = handler(_make_event("CUST-001"), None)

        parsed = json.loads(result["body"])
        assert "reasoning_trace" in parsed
        assert len(parsed["reasoning_trace"]) == 1

    @patch("api_lambda.handler._agentcore_client")
    def test_cust003_with_pending_actions_passes_through(self, mock_client):
        """CUST-003 with pending_actions passes through unchanged."""
        actions = [
            {
                "action_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                "action_type": "tariff_switch",
                "customer_id": "CUST-003",
                "payload": {"plan_id": "ECO", "plan_name": "EcoFlex 100"},
                "status": "pending",
            },
            {
                "action_id": "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
                "action_type": "payment_plan_offer",
                "customer_id": "CUST-003",
                "payload": {"proposed_installments": 3, "installment_amount": 15.67, "total_owed": 47.00},
                "status": "pending",
            },
        ]
        body = {**_PERSONA_RESPONSES["CUST-003"], "pending_actions": actions}
        mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

        result = handler(_make_event("CUST-003"), None)

        parsed = json.loads(result["body"])
        assert parsed["pending_actions"] == actions

    @patch("api_lambda.handler._agentcore_client")
    def test_all_personas_strip_narrative_source(self, mock_client):
        """All persona responses strip _narrative_source marker."""
        for cust_id in ["CUST-001", "CUST-002", "CUST-003", "CUST-004", "CUST-005"]:
            body = {
                **_PERSONA_RESPONSES[cust_id],
                "_narrative_source": {"usage_narrative": "model", "call_script": "model"},
            }
            mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

            result = handler(_make_event(cust_id), None)

            parsed = json.loads(result["body"])
            assert "_narrative_source" not in parsed, f"{cust_id} leaked _narrative_source"

    @patch("api_lambda.handler._agentcore_client")
    def test_all_recommendation_personas_have_both_tracks(self, mock_client):
        """All recommendation personas (CUST-001 through CUST-005) have both tracks."""
        for cust_id in ["CUST-001", "CUST-002", "CUST-003", "CUST-004", "CUST-005"]:
            body = _PERSONA_RESPONSES[cust_id]
            mock_client.invoke_agent_runtime.return_value = _make_agent_response(body)

            result = handler(_make_event(cust_id), None)

            assert result["statusCode"] == 200, f"{cust_id} did not return 200"
            parsed = json.loads(result["body"])
            assert "green" in parsed, f"{cust_id} missing green track"
            assert "cheapest" in parsed, f"{cust_id} missing cheapest track"
