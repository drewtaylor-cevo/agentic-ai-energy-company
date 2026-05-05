"""Chat endpoint handler — POST /chat/{customer_id}.

Provides both batch JSON and SSE streaming paths for the conversational
chat layer. Reuses the same AgentCore runtime as the recommendation endpoint,
invoking with action="chat" payload.

Design decisions:
- Validation errors (400, 429) are returned BEFORE opening the SSE stream.
- D-04 never-500: all runtime exceptions map to 502 (service error) or 504
  (timeout). HTTP 500 is never surfaced.
- Content negotiation: Accept: text/event-stream → SSE, otherwise → JSON batch.
- HTML tags stripped from message before passing to agent (input sanitisation).
- Fresh runtimeSessionId (uuid4) per invocation (SC-3 pattern).
- Config(read_timeout=25, connect_timeout=5) on boto3 client — same as
  recommendation path (Pitfall 1: default 60s outlasts Lambda 30s timeout).

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.1, 2.2, 2.3, 2.4,
3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 5.1, 5.2, 8.2, 8.3, 10.1, 10.2, 10.4, 10.5
"""

import json
import logging
import os
import re
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError

from api_lambda.chat_session import session_store
from api_lambda.sse import format_done_event, format_sse_event

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# D-13: identical regex to api_lambda/handler.py — defense in depth.
_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")

# HTML tag stripping pattern (simple tag removal).
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

# Message constraints.
_MESSAGE_MAX_LENGTH = 2000

# Injected by CDK. Empty string fallback keeps import working during tests.
_AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")

# Module-level client — reused across warm invocations.
# Config(read_timeout=25, connect_timeout=5): fire ReadTimeoutError at 25s,
# leaving a 5s buffer before Lambda's 30s timeout (Pitfall 1).
_chat_agentcore_client = boto3.client(
    "bedrock-agentcore",
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
    config=Config(read_timeout=25, connect_timeout=5),
)

# Lazy-loaded StreamingTraceHook instance for the chat path (SC-3 pattern).
# Mirrors _get_streaming_trace_hook() in api_lambda/handler.py — separate
# instance avoids cross-path state leakage between recommendation and chat
# streaming handlers sharing the same Lambda warm instance.
_chat_streaming_trace_hook = None


def _get_chat_streaming_trace_hook():
    """Lazy-load StreamingTraceHook to avoid import-time failures in test."""
    global _chat_streaming_trace_hook  # noqa: PLW0603
    if _chat_streaming_trace_hook is None:
        try:
            from agent.hooks.streaming_trace import StreamingTraceHook
        except ImportError:  # pragma: no cover
            from hooks.streaming_trace import StreamingTraceHook
        _chat_streaming_trace_hook = StreamingTraceHook()
    return _chat_streaming_trace_hook


def _error(status_code: int, message: str) -> dict:
    """Consistent JSON error body."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }


def _validate_request(event: dict) -> tuple[str, str, str | None, dict | None]:
    """Validate customer_id and message from the event.

    Returns:
        (customer_id, message, session_id, error_response)
        If error_response is not None, return it immediately.
    """
    # Extract customer_id from path parameters.
    path_params = event.get("pathParameters") or {}
    customer_id = path_params.get("customer_id", "")

    # Also try extracting from rawPath if pathParameters not populated
    # (Function URL may not have route patterns configured).
    if not customer_id:
        raw_path = event.get("rawPath", "")
        match = re.match(r"^/chat/([^/]+)$", raw_path)
        if match:
            customer_id = match.group(1)

    # Validate customer_id format.
    if not _CUSTOMER_ID_PATTERN.match(customer_id):
        return "", "", None, _error(400, "Invalid customer ID format. Use CUST-NNN (3-6 digits).")

    # Parse request body.
    body_str = event.get("body", "")
    if not body_str:
        return customer_id, "", None, _error(400, "Message is required (1-2000 characters).")

    try:
        body = json.loads(body_str)
    except (json.JSONDecodeError, TypeError):
        return customer_id, "", None, _error(400, "Message is required (1-2000 characters).")

    message = body.get("message", "")
    session_id = body.get("session_id")

    # Validate message: must be a string.
    if not isinstance(message, str):
        return customer_id, "", session_id, _error(400, "Message is required (1-2000 characters).")

    # Validate message: not empty or whitespace-only.
    if not message or not message.strip():
        return customer_id, "", session_id, _error(400, "Message cannot be empty or whitespace-only.")

    # Validate message: length constraint.
    if len(message) > _MESSAGE_MAX_LENGTH:
        return customer_id, message, session_id, _error(400, "Message exceeds maximum length of 2000 characters.")

    return customer_id, message, session_id, None


def _sanitize_message(message: str) -> str:
    """Strip HTML tags from message (input sanitisation)."""
    return _HTML_TAG_PATTERN.sub("", message)


def _is_sse_requested(event: dict) -> bool:
    """Check if the client requested SSE via Accept header."""
    headers = event.get("headers") or {}
    accept = headers.get("accept", "")
    return "text/event-stream" in accept


def chat_handler(event: dict, context) -> dict:
    """Batch chat handler — returns Chat_Response as JSON.

    Content negotiation: if Accept: text/event-stream is present, this
    function should NOT be called — the stream_handler routing in
    api_lambda/handler.py should delegate to chat_stream_handler instead.
    """
    # Validate inputs.
    customer_id, message, session_id_input, error_resp = _validate_request(event)
    if error_resp is not None:
        return error_resp

    # Sanitize message — strip HTML tags.
    sanitized_message = _sanitize_message(message)

    # Resolve/create session.
    try:
        session = session_store.get_or_create(session_id_input, customer_id)
    except ValueError as exc:
        # Cross-customer rejection (SC-3).
        return _error(400, str(exc))

    # Check rate limit.
    if session_store.check_rate_limit(session.session_id):
        return _error(429, "Rate limit exceeded. Maximum 10 messages per minute.")

    # Generate fresh runtimeSessionId (uuid4) per invocation (D-11 / SC-3).
    runtime_session_id = str(uuid.uuid4())
    logger.info(
        "Chat invoke customer_id=%s session_id=%s runtime_session_id=%s",
        customer_id, session.session_id, runtime_session_id,
    )

    # Build payload for AgentCore.
    payload = {
        "customer_id": customer_id,
        "action": "chat",
        "message": sanitized_message,
        "session_history": session.messages,
    }

    # D-04 never-500: wrap AgentCore invocation in try/except.
    try:
        response = _chat_agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=_AGENT_RUNTIME_ARN,
            runtimeSessionId=runtime_session_id,
            payload=json.dumps(payload).encode(),
        )
        body = json.loads(response["response"].read())

        # Build Chat_Response.
        chat_response = {
            "reply": body.get("reply", ""),
            "reasoning_trace": body.get("reasoning_trace", []),
            "session_id": session.session_id,
            "customer_id": customer_id,
        }

        # Record turn in session store after successful response.
        session_store.record_turn(
            session.session_id,
            sanitized_message,
            chat_response["reply"],
        )

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(chat_response),
        }

    except ReadTimeoutError:
        logger.warning("Chat timeout customer_id=%s", customer_id)
        return _error(504, "Chat service timed out. Please try again.")

    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "Unknown")
        error_msg = exc.response.get("Error", {}).get("Message", str(exc))
        logger.error(
            "Chat ClientError customer_id=%s code=%s: %s",
            customer_id, error_code, error_msg,
        )
        return _error(502, "Chat service error. Please try again.")

    except Exception as exc:  # pylint: disable=broad-except
        # D-04: catch everything — never return 500.
        logger.error(
            "Chat unexpected error customer_id=%s: %s", customer_id, exc, exc_info=True
        )
        return _error(502, "Chat service error. Please try again.")


def chat_stream_handler(event: dict, response_stream, context) -> None:
    """SSE streaming chat handler — emits trace_step, chat_reply, error, done.

    Validation errors (400, 429) are returned as JSON BEFORE opening the
    SSE stream. Only runtime errors during agent execution are emitted as
    SSE error events.

    SC-3 pattern: the StreamingTraceHook is reset before and after each
    invocation to prevent state leakage between warm Lambda invocations.
    The hook callback is wired to emit SSE trace_step frames using the same
    deterministic summary formatters as the recommendation path (Req 2.5, 3.3).
    """
    # Validate inputs — return JSON error before stream opens.
    customer_id, message, session_id_input, error_resp = _validate_request(event)
    if error_resp is not None:
        response_stream.write(json.dumps(error_resp).encode())
        return

    # Sanitize message — strip HTML tags.
    sanitized_message = _sanitize_message(message)

    # Resolve/create session.
    try:
        session = session_store.get_or_create(session_id_input, customer_id)
    except ValueError as exc:
        # Cross-customer rejection — return JSON error before stream.
        error_resp = _error(400, str(exc))
        response_stream.write(json.dumps(error_resp).encode())
        return

    # Check rate limit — return JSON error before stream.
    if session_store.check_rate_limit(session.session_id):
        error_resp = _error(429, "Rate limit exceeded. Maximum 10 messages per minute.")
        response_stream.write(json.dumps(error_resp).encode())
        return

    # Generate fresh runtimeSessionId (uuid4) per invocation (D-11 / SC-3).
    runtime_session_id = str(uuid.uuid4())
    logger.info(
        "Chat stream invoke customer_id=%s session_id=%s runtime_session_id=%s",
        customer_id, session.session_id, runtime_session_id,
    )

    # Build payload for AgentCore.
    payload = {
        "customer_id": customer_id,
        "action": "chat",
        "message": sanitized_message,
        "session_history": session.messages,
    }

    # SC-3 pattern: wire StreamingTraceHook callback to emit SSE trace_step
    # frames. Reset before invocation to clear any stale state from a prior
    # warm-Lambda invocation. The hook uses the same deterministic summary
    # formatters (agent/reasoning/summaries.py) as the recommendation path.
    # NOTE: Since the API Lambda invokes AgentCore via invoke_agent_runtime
    # (a remote call returning a complete response), the hook callback at
    # this layer is not fired during execution. Trace events are emitted
    # from the response body's reasoning_trace field below. The hook wiring
    # ensures the SC-3 reset contract is honoured and the pattern is
    # consistent with _stream_handler in handler.py.
    hook = _get_chat_streaming_trace_hook()
    hook.reset()

    # Streaming callback: writes SSE trace_step frames to response_stream.
    # Uses the same format_sse_event("trace_step", ...) as the recommendation
    # streaming path, ensuring wire-format consistency (Req 3.3, 3.4).
    def _streaming_callback(tool_name: str, summary: str) -> None:
        frame = format_sse_event("trace_step", {"tool": tool_name, "summary": summary})
        response_stream.write(frame.encode())

    hook.set_callback(_streaming_callback)

    # D-04 never-500: wrap AgentCore invocation in try/except.
    try:
        response = _chat_agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=_AGENT_RUNTIME_ARN,
            runtimeSessionId=runtime_session_id,
            payload=json.dumps(payload).encode(),
        )
        body = json.loads(response["response"].read())

        # Emit trace_step events for each tool in reasoning_trace.
        # The reasoning_trace summaries are produced by the same deterministic
        # formatters in agent/reasoning/summaries.py that the recommendation
        # path uses (Req 2.5 — SAV-03 compliance by construction).
        reasoning_trace = body.get("reasoning_trace", [])
        for trace_entry in reasoning_trace:
            response_stream.write(
                format_sse_event("trace_step", {
                    "tool": trace_entry.get("tool", ""),
                    "summary": trace_entry.get("summary", ""),
                }).encode()
            )

        # Build Chat_Response.
        chat_response = {
            "reply": body.get("reply", ""),
            "reasoning_trace": reasoning_trace,
            "session_id": session.session_id,
            "customer_id": customer_id,
        }

        # Emit chat_reply event.
        response_stream.write(format_sse_event("chat_reply", chat_response).encode())

        # Emit done event.
        response_stream.write(format_done_event().encode())

        # Record turn in session store after successful response.
        session_store.record_turn(
            session.session_id,
            sanitized_message,
            chat_response["reply"],
        )

    except ReadTimeoutError:
        # D-04: emit timeout as error event (504).
        logger.warning("Chat stream timeout customer_id=%s", customer_id)
        response_stream.write(
            format_sse_event("error", {
                "status": 504,
                "message": "Chat service timed out. Please try again.",
            }).encode()
        )
        response_stream.write(format_done_event().encode())

    except ClientError as exc:
        # D-04: emit service error (502).
        error_code = exc.response.get("Error", {}).get("Code", "Unknown")
        error_msg = exc.response.get("Error", {}).get("Message", str(exc))
        logger.error(
            "Chat stream ClientError customer_id=%s code=%s: %s",
            customer_id, error_code, error_msg,
        )
        response_stream.write(
            format_sse_event("error", {
                "status": 502,
                "message": "Chat service error. Please try again.",
            }).encode()
        )
        response_stream.write(format_done_event().encode())

    except Exception as exc:  # pylint: disable=broad-except
        # D-04 never-500: catch everything, emit error + done.
        logger.error(
            "Chat stream unexpected error customer_id=%s: %s",
            customer_id, exc, exc_info=True,
        )
        response_stream.write(
            format_sse_event("error", {
                "status": 502,
                "message": "Chat service error. Please try again.",
            }).encode()
        )
        response_stream.write(format_done_event().encode())

    finally:
        # SC-3: reset hook state after each invocation to prevent state
        # leakage between warm Lambda invocations (mirrors _stream_handler
        # in handler.py).
        hook.reset()
