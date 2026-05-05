"""Phase 3 API Lambda — API Gateway HTTP API v2 -> AgentCore runtime proxy.

Handles GET /recommendations/{customer_id} (D-10). Validates customer_id
against ^CUST-\\d{3,6}$ (D-13, mirrors lambda/handler.py::_validate_customer_id),
generates a fresh runtimeSessionId per invocation (D-11), invokes the Phase 2
AgentCore runtime synchronously (D-01), and returns the agent body verbatim
(D-02, pass-through). Maps errors to HTTP codes per D-12.

Also provides a streaming code path via `stream_handler()` for Lambda Function
URL with Response Streaming. When the client sends `Accept: text/event-stream`,
the handler emits SSE frames (trace_step, result, done) as the agent executes.
The batch path (`handler()`) remains completely unchanged (Requirement 7.1).

CRITICAL: Config(read_timeout=25) must be set on the boto3 client. The default
botocore read timeout is 60s, which outlasts the 30s Lambda timeout — without
this override the 504 branch is unreachable (RESEARCH.md Pitfall 1).
"""
import json
import logging
import os
import re
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError

from api_lambda.sse import format_done_event, format_sse_event

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# D-13: identical regex to lambda/handler.py line 39 — defense in depth.
_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")

# UUID v4 pattern for action_id validation.
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Injected by CDK (BackendApiConstruct). Empty string fallback keeps import
# working during offline unit tests that patch _agentcore_client.
_AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
_TOOLS_LAMBDA_ARN = os.environ.get("TOOLS_LAMBDA_ARN", "")
_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Known seed personas for the retention queue.
_KNOWN_CUSTOMER_IDS = [
    "CUST-001", "CUST-002", "CUST-003",
    "CUST-004", "CUST-005", "CUST-006",
]

# Module-level client — reused across warm invocations.
# Config(read_timeout=25, connect_timeout=5): fire ReadTimeoutError at 25s,
# leaving a 5s buffer before Lambda's 30s timeout kills the process (D-03).
# Without this override, botocore's 60s default outlasts the Lambda execution
# environment and 504 is never surfaced (Pitfall 1).
_agentcore_client = boto3.client(
    "bedrock-agentcore",
    region_name=_REGION,
    config=Config(read_timeout=25, connect_timeout=5),
)

# Tools Lambda client — used for retention-queue and action confirm/dismiss.
# Same timeout config as agentcore client (D-04: never-500 contract).
_tools_lambda_client = boto3.client(
    "lambda",
    region_name=_REGION,
    config=Config(read_timeout=25, connect_timeout=5),
)


def _error(status_code: int, message: str) -> dict:
    """Consistent JSON error body (D-12)."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }


def _follow_up(customer_id: str, event: dict, context) -> dict:
    """Handle GET /recommendations/{customer_id}/follow-up (Phase 15 WF-01).

    Invokes the AgentCore runtime with action="follow_up" to draft a follow-up
    email referencing the prior recommendation via Memory.

    D-11: fresh uuid4 per invocation (SC-3 preserved — runtimeSessionId is
    NOT the Memory session_id; see agent/memory/config.py AP-2 distinction).
    """
    # D-11: fresh uuid4 per invocation, generated INSIDE this function.
    session_id = str(uuid.uuid4())
    logger.info("Follow-up invoke customer_id=%s session_id=%s", customer_id, session_id)

    try:
        response = _agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=_AGENT_RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=json.dumps({
                "customer_id": customer_id,
                "action": "follow_up",
            }).encode(),
        )
        body = json.loads(response["response"].read())
        # D-15-07: strip internal workflow marker (parallel to _narrative_source).
        body.pop("_workflow_source", None)
        body.pop("_narrative_source", None)

        # Log workflow source for observability (same pattern as narrative_source).
        logger.info(json.dumps({
            "event": "follow_up_complete",
            "customer_id": customer_id,
        }))
    except ReadTimeoutError:
        logger.warning("Follow-up timeout customer_id=%s", customer_id)
        return _error(504, "Follow-up service timed out. Please try again.")
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "Unknown")
        error_msg = exc.response.get("Error", {}).get("Message", str(exc))
        logger.error(
            "Follow-up ClientError customer_id=%s code=%s: %s",
            customer_id, error_code, error_msg,
        )
        return _error(502, "Follow-up service error. Please try again.")
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Follow-up unexpected error customer_id=%s: %s", customer_id, exc, exc_info=True)
        return _error(500, "Internal server error.")

    # Validate response shape — must be a follow_up response.
    if body.get("kind") != "follow_up":
        logger.warning("Follow-up unexpected shape customer_id=%s body=%s", customer_id, body)
        return _error(502, "Follow-up service returned unexpected response.")

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _invoke_tools_lambda(payload: dict) -> dict:
    """Invoke the Tools Lambda with the given payload and return parsed response.

    Raises:
        RuntimeError: if the Tools Lambda invocation fails or returns an error.
    """
    resp = _tools_lambda_client.invoke(
        FunctionName=_TOOLS_LAMBDA_ARN,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode(),
    )
    body = json.loads(resp["Payload"].read())
    if isinstance(body, dict) and body.get("error"):
        raise RuntimeError(body.get("message", "Tools Lambda error"))
    return body


def _retention_queue(event: dict, context) -> dict:
    """Handle GET /retention-queue — compute risk signals for all known personas.

    Invokes Tools Lambda `compute_risk_signals` with all known customer_ids.
    Returns ranked list with HTTP 200. On upstream failure, returns 502 (D-04).
    """
    try:
        result = _invoke_tools_lambda({
            "action": "compute_risk_signals",
            "customer_ids": _KNOWN_CUSTOMER_IDS,
        })
    except Exception as exc:
        logger.error("Retention queue upstream failure: %s", exc, exc_info=True)
        return _error(502, "Upstream service error")

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result),
    }


def _action_confirm(action_id: str, event: dict, context) -> dict:
    """Handle POST /actions/{action_id}/confirm — transition action to confirmed.

    Validates action_id format, invokes Tools Lambda `confirm_action`,
    and maps errors to appropriate HTTP status codes.
    """
    # Validate action_id format
    if not _UUID_PATTERN.match(action_id):
        return _error(400, "Invalid action_id")

    try:
        result = _invoke_tools_lambda({
            "action": "confirm_action",
            "action_id": action_id,
        })
    except RuntimeError as exc:
        return _map_action_error(str(exc))
    except Exception as exc:
        logger.error("Action confirm upstream failure: %s", exc, exc_info=True)
        return _error(502, "Upstream service error")

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result),
    }


def _action_dismiss(action_id: str, event: dict, context) -> dict:
    """Handle POST /actions/{action_id}/dismiss — transition action to rejected.

    Validates action_id format, invokes Tools Lambda `dismiss_action`,
    and maps errors to appropriate HTTP status codes.
    """
    # Validate action_id format
    if not _UUID_PATTERN.match(action_id):
        return _error(400, "Invalid action_id")

    try:
        result = _invoke_tools_lambda({
            "action": "dismiss_action",
            "action_id": action_id,
        })
    except RuntimeError as exc:
        return _map_action_error(str(exc))
    except Exception as exc:
        logger.error("Action dismiss upstream failure: %s", exc, exc_info=True)
        return _error(502, "Upstream service error")

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result),
    }


def _map_action_error(message: str) -> dict:
    """Map Tools Lambda action error messages to HTTP status codes.

    Error mapping (from design):
      - "Action not found" → 404
      - "Action has expired" → 410
      - "Action already processed" → 409
      - Other → 502 (upstream failure)
    """
    msg_lower = message.lower()
    if "not found" in msg_lower:
        return _error(404, "Action not found")
    if "expired" in msg_lower:
        return _error(410, "Action has expired")
    if "already processed" in msg_lower:
        return _error(409, "Action already processed")
    return _error(502, "Upstream service error")


def handler(event: dict, context) -> dict:
    """API Lambda entry point — GET /recommendations/{customer_id}, /follow-up, and /chat/."""
    # Route /chat/ requests to the chat handler (lazy import to avoid overhead
    # when chat is not used). Must check BEFORE customer_id extraction since
    # chat uses its own validation internally.
    raw_path = event.get("rawPath", "")
    if "/chat/" in raw_path:
        from api_lambda.chat_handler import chat_handler
        return chat_handler(event, context)

    # Route retention-queue requests.
    if raw_path == "/retention-queue" or raw_path.endswith("/retention-queue"):
        return _retention_queue(event, context)

    # Route action confirm/dismiss requests.
    # Pattern: /actions/{action_id}/confirm or /actions/{action_id}/dismiss
    action_match = re.match(r"^/actions/([^/]+)/(confirm|dismiss)$", raw_path)
    if action_match:
        action_id = action_match.group(1)
        action_verb = action_match.group(2)
        if action_verb == "confirm":
            return _action_confirm(action_id, event, context)
        else:
            return _action_dismiss(action_id, event, context)

    # Also check pathParameters for action_id (API Gateway route pattern).
    path_params = event.get("pathParameters") or {}
    if path_params.get("action_id"):
        action_id = path_params["action_id"]
        if raw_path.endswith("/confirm"):
            return _action_confirm(action_id, event, context)
        elif raw_path.endswith("/dismiss"):
            return _action_dismiss(action_id, event, context)

    # Extract customer_id from HTTP API v2 payload format (pathParameters).
    path_params = event.get("pathParameters") or {}
    customer_id = path_params.get("customer_id", "")

    # D-13: fast-fail on bad format — avoids wasting a 3-5s agent invocation.
    if not _CUSTOMER_ID_PATTERN.match(customer_id):
        return _error(400, "Invalid customer ID format. Use CUST-NNN (3-6 digits).")

    # Phase 15 WF-01: route follow-up requests to dedicated handler.
    # rawPath ends with "/follow-up" for the follow-up route.
    if raw_path.endswith("/follow-up"):
        return _follow_up(customer_id, event, context)

    # D-01/D-02: Prewarm branch — warm the full hot path and return 204
    # without touching the normal-path response taxonomy. D-04: NEVER 5xx.
    # Runs AFTER the D-13 regex check so stray ?prewarm=1 + bad customer_id
    # still returns 400 (Pitfall 4 locks the literal string "1" compare).
    query_params = event.get("queryStringParameters") or {}
    if query_params.get("prewarm") == "1":
        # D-11 (Phase 3) / AP-3: fresh uuid4 per invocation — never cache.
        prewarm_session_id = str(uuid.uuid4())
        logger.info(
            "Prewarm invoke customer_id=%s session_id=%s",
            customer_id, prewarm_session_id,
        )
        try:
            # D-02: full real agent turn; D-05: shared _agentcore_client.
            prewarm_response = _agentcore_client.invoke_agent_runtime(
                agentRuntimeArn=_AGENT_RUNTIME_ARN,
                runtimeSessionId=prewarm_session_id,
                payload=json.dumps({"customer_id": customer_id}).encode(),
            )
            # Drain StreamingBody to release the connection; body discarded.
            prewarm_response["response"].read()
        except Exception as exc:  # pylint: disable=broad-except
            # D-04: swallow EVERYTHING. ClientError + ReadTimeoutError +
            # transport-level (EndpointConnectionError, SSLError) all land here.
            error_code = type(exc).__name__
            if isinstance(exc, ClientError):
                error_code = exc.response.get("Error", {}).get(
                    "Code", "Unknown"
                )
            logger.warning(
                json.dumps({
                    "event": "prewarm_failed",
                    "customer_id": customer_id,
                    "error_code": error_code,
                    "error": str(exc),
                })
            )
        # D-04: 204 on success AND failure. Empty body + empty headers
        # matches API Gateway HTTP API v2 proxy contract.
        return {"statusCode": 204, "headers": {}, "body": ""}

    # D-11: fresh uuid4 per invocation, generated INSIDE handler() — never at
    # module scope. Module-level cache would cause session bleed between
    # consecutive persona lookups, violating SC-3 (Pitfall 2).
    session_id = str(uuid.uuid4())  # 36 chars, satisfies AgentCore's 33-char minimum
    logger.info("Invoking agent customer_id=%s session_id=%s", customer_id, session_id)

    try:
        response = _agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=_AGENT_RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=json.dumps({"customer_id": customer_id}).encode(),
        )
        body = json.loads(response["response"].read())
        # D-06: strip internal marker (idempotent; None default means
        # pre-6.1 agent deployments do not break the handler).
        narrative_source = body.pop("_narrative_source", None)
        # D-07: structured CloudWatch INFO log (zero-PII by construction —
        # narrative_source is {"usage_narrative": "model"|"fallback",
        # "call_script": "model"|"fallback"} OR None). Logged on every
        # successful invoke, BEFORE the 404 check (Open Question 2 in
        # RESEARCH.md resolves to log-before-404: invoke succeeded, the
        # marker is observable, 404 is a handler-side decision not an
        # invocation failure).
        logger.info(json.dumps({
            "event": "narrative_source",
            "customer_id": customer_id,
            "narrative_source": narrative_source,
        }))
    except ReadTimeoutError:
        logger.warning("Agent timeout customer_id=%s", customer_id)
        return _error(504, "Recommendation service timed out. Please try again.")
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "Unknown")
        error_msg = exc.response.get("Error", {}).get("Message", str(exc))
        logger.error(
            "AgentCore ClientError customer_id=%s code=%s: %s",
            customer_id, error_code, error_msg,
        )
        return _error(502, "Recommendation service error. Please try again.")
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Unexpected error customer_id=%s: %s", customer_id, exc, exc_info=True)
        return _error(500, "Internal server error.")

    # D-12: customer-not-found detection — agent fallback path returns
    # {"errorMessage": "..."} with no green/cheapest keys (RESEARCH.md Pitfall 5).
    # Checking for absent tracks is the most robust detection signal.
    # Phase 14 AGENT-02a: hardship responses legitimately lack green/cheapest
    # (kind: "hardship"). Only trigger 404 when the response is NOT hardship.
    if "green" not in body or "cheapest" not in body:
        if body.get("kind") == "hardship":
            # Hardship is a valid 200 response — pass through verbatim.
            # No _narrative_source stripping needed (hardship marker is
            # already structured differently from recommendation markers).
            body.pop("_narrative_source", None)
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(body),
            }
        logger.info("Customer not found customer_id=%s body=%s", customer_id, body)
        return _error(404, f"Customer {customer_id} not found.")

    # D-13.1-13 (Phase 13.1): defence-in-depth sentinel against LLM
    # synthesising UNKNOWN placeholder tracks when the prompt STOP rule
    # (D-13.1-12, _BASE_SYSTEM_PROMPT) drifts. The "UNKNOWN" string was
    # empirically observed from Sonnet 4.6 live emission in
    # 13-08-CEREMONY-LOG.md §Post-freeze Live Sanity (lines 112-121).
    # Symmetric across tracks — the LLM emits UNKNOWN on both at once,
    # but we check either-track to guard against a future model drift
    # that only emits placeholder on one side. This branch SHOULD never
    # fire in production after Phase 13.1 ships; it exists to fail
    # loudly (404) rather than silently (200 with UNKNOWN tracks) if
    # the prompt-side contract regresses.
    if (body.get("green", {}).get("plan_id") == "UNKNOWN"
            or body.get("cheapest", {}).get("plan_id") == "UNKNOWN"):
        logger.info(
            "Customer not found (UNKNOWN-plan_id sentinel) customer_id=%s",
            customer_id,
        )
        return _error(404, f"Customer {customer_id} not found.")

    # D-02: pass-through verbatim — no envelope, no meta. One contract
    # agent -> API -> UI.
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }

# ---------------------------------------------------------------------------
# Streaming handler — Lambda Function URL with Response Streaming
# ---------------------------------------------------------------------------
# This is a SEPARATE entry point from handler(). Lambda Function URL invokes
# stream_handler(event, response_stream, context) directly. The existing
# handler() is invoked by API Gateway and remains completely unchanged
# (Requirement 7.1, 7.2).
# ---------------------------------------------------------------------------

# Lazy import of StreamingTraceHook — avoids circular import at module load.
_streaming_trace_hook = None


def _get_streaming_trace_hook():
    """Lazy-load StreamingTraceHook to avoid import-time failures in test."""
    global _streaming_trace_hook  # noqa: PLW0603
    if _streaming_trace_hook is None:
        try:
            from agent.hooks.streaming_trace import StreamingTraceHook
        except ImportError:  # pragma: no cover
            from hooks.streaming_trace import StreamingTraceHook
        _streaming_trace_hook = StreamingTraceHook()
    return _streaming_trace_hook


def _is_sse_requested(event: dict) -> bool:
    """Check if the client requested SSE via Accept header (content negotiation)."""
    headers = event.get("headers") or {}
    # Lambda Function URL lowercases all header names.
    accept = headers.get("accept", "")
    return "text/event-stream" in accept


def stream_handler(event: dict, response_stream, context) -> None:
    """Lambda Function URL streaming entry point.

    Content negotiation:
    - Accept: text/event-stream → SSE streaming path (_stream_handler)
    - Otherwise → delegate to batch handler() and write JSON to stream

    The response_stream object supports .write(bytes) for Lambda Response
    Streaming (awslambdaric pattern).
    """
    # Route /chat/ requests to the chat stream handler (lazy import to avoid
    # overhead when chat is not used).
    raw_path = event.get("rawPath", "")
    if "/chat/" in raw_path:
        from api_lambda.chat_handler import chat_stream_handler
        return chat_stream_handler(event, response_stream, context)

    if _is_sse_requested(event):
        _stream_handler(event, response_stream, context)
    else:
        # Batch fallback: invoke existing handler, write result as JSON.
        result = handler(event, context)
        response_stream.write(json.dumps(result).encode())


def _stream_handler(event: dict, response_stream, context) -> None:
    """SSE streaming path — emits trace_step, result, and done events.

    Implements Requirements 1.1-1.4, 2.1-2.6, 4.1, 4.4-4.7, 7.3, 8.2.
    D-04 never-500: wraps AgentCore invocation in try/except and emits
    fallback as result event on any exception.
    """
    # Extract customer_id from Function URL event format.
    # Function URL uses the same payload format as HTTP API v2.
    path_params = event.get("pathParameters") or {}
    customer_id = path_params.get("customer_id", "")

    # Also try extracting from rawPath if pathParameters not populated
    # (Function URL may not have route patterns configured).
    if not customer_id:
        raw_path = event.get("rawPath", "")
        # Pattern: /recommendations/{customer_id}
        match = re.match(r"^/recommendations/([^/]+)$", raw_path)
        if match:
            customer_id = match.group(1)

    # D-13: validate customer_id BEFORE opening stream (return JSON 400).
    if not _CUSTOMER_ID_PATTERN.match(customer_id):
        # Return JSON error — no SSE stream opened.
        error_body = json.dumps({"error": "Invalid customer ID format. Use CUST-NNN (3-6 digits)."})
        response_stream.write(json.dumps({
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": error_body,
        }).encode())
        return

    # Requirement 4.6: ?prewarm=1 returns 204 with empty body, no streaming.
    query_params = event.get("queryStringParameters") or {}
    if query_params.get("prewarm") == "1":
        response_stream.write(json.dumps({
            "statusCode": 204,
            "headers": {},
            "body": "",
        }).encode())
        return

    # Requirement 4.7: ?narrative=off suppresses trace_step events and strips
    # reasoning_trace, compliance_review, supervisor_trace from result.
    narrative_off = query_params.get("narrative") == "off"

    # D-11 / SC-3: fresh uuid4 per invocation, generated INSIDE handler.
    session_id = str(uuid.uuid4())
    logger.info("Streaming invoke customer_id=%s session_id=%s", customer_id, session_id)

    # Wire StreamingTraceHook callback to emit SSE trace_step events.
    hook = _get_streaming_trace_hook()
    hook.reset()

    # Streaming callback: writes SSE trace_step frames to response_stream.
    # When narrative=off, the callback is a no-op (suppress trace_step events).
    def _streaming_callback(tool_name: str, summary: str) -> None:
        if narrative_off:
            return
        frame = format_sse_event("trace_step", {"tool": tool_name, "summary": summary})
        response_stream.write(frame.encode())

    hook.set_callback(_streaming_callback)

    # D-04 never-500: wrap entire AgentCore invocation in try/except.
    try:
        response = _agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=_AGENT_RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=json.dumps({"customer_id": customer_id}).encode(),
        )
        body = json.loads(response["response"].read())

        # D-06: strip internal marker before emitting to client.
        body.pop("_narrative_source", None)

        # Customer-not-found detection (same logic as batch path).
        if "green" not in body or "cheapest" not in body:
            if body.get("kind") == "hardship":
                # Hardship is valid — emit as result.
                body.pop("_narrative_source", None)
                if narrative_off:
                    body.pop("reasoning_trace", None)
                    body.pop("compliance_review", None)
                    body.pop("supervisor_trace", None)
                response_stream.write(format_sse_event("result", body).encode())
                response_stream.write(format_done_event().encode())
                return
            # Customer not found — emit error event + done.
            logger.info("Customer not found (streaming) customer_id=%s", customer_id)
            response_stream.write(
                format_sse_event("error", {
                    "status": 404,
                    "message": f"Customer {customer_id} not found.",
                }).encode()
            )
            response_stream.write(format_done_event().encode())
            return

        # D-13.1-13: UNKNOWN sentinel check (same as batch path).
        if (body.get("green", {}).get("plan_id") == "UNKNOWN"
                or body.get("cheapest", {}).get("plan_id") == "UNKNOWN"):
            logger.info(
                "Customer not found (UNKNOWN sentinel, streaming) customer_id=%s",
                customer_id,
            )
            response_stream.write(
                format_sse_event("error", {
                    "status": 404,
                    "message": f"Customer {customer_id} not found.",
                }).encode()
            )
            response_stream.write(format_done_event().encode())
            return

        # Requirement 4.7: strip narrative fields when narrative=off.
        if narrative_off:
            body.pop("reasoning_trace", None)
            body.pop("compliance_review", None)
            body.pop("supervisor_trace", None)

        # Success: emit result event + done event.
        response_stream.write(format_sse_event("result", body).encode())
        response_stream.write(format_done_event().encode())

    except ReadTimeoutError:
        # D-04 fallback: emit timeout as error event (Requirement 7.3: 504).
        logger.warning("Agent timeout (streaming) customer_id=%s", customer_id)
        response_stream.write(
            format_sse_event("error", {
                "status": 504,
                "message": "Recommendation service timed out. Please try again.",
            }).encode()
        )
        response_stream.write(format_done_event().encode())

    except ClientError as exc:
        # D-04 fallback: emit service error (Requirement 7.3: 502).
        error_code = exc.response.get("Error", {}).get("Code", "Unknown")
        error_msg = exc.response.get("Error", {}).get("Message", str(exc))
        logger.error(
            "AgentCore ClientError (streaming) customer_id=%s code=%s: %s",
            customer_id, error_code, error_msg,
        )
        response_stream.write(
            format_sse_event("error", {
                "status": 502,
                "message": "Recommendation service error. Please try again.",
            }).encode()
        )
        response_stream.write(format_done_event().encode())

    except Exception as exc:  # pylint: disable=broad-except
        # D-04 never-500: catch everything, emit fallback result + done.
        logger.error(
            "Unexpected error (streaming) customer_id=%s: %s",
            customer_id, exc, exc_info=True,
        )
        response_stream.write(
            format_sse_event("error", {
                "status": 500,
                "message": "Internal server error.",
            }).encode()
        )
        response_stream.write(format_done_event().encode())

    finally:
        # Clean up hook state after invocation.
        hook.reset()
