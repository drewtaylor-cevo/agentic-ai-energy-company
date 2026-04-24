"""Phase 3 API Lambda — API Gateway HTTP API v2 -> AgentCore runtime proxy.

Handles GET /recommendations/{customer_id} (D-10). Validates customer_id
against ^CUST-\\d{3,6}$ (D-13, mirrors lambda/handler.py::_validate_customer_id),
generates a fresh runtimeSessionId per invocation (D-11), invokes the Phase 2
AgentCore runtime synchronously (D-01), and returns the agent body verbatim
(D-02, pass-through). Maps errors to HTTP codes per D-12.

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

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# D-13: identical regex to lambda/handler.py line 39 — defense in depth.
_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")

# Injected by CDK (BackendApiConstruct). Empty string fallback keeps import
# working during offline unit tests that patch _agentcore_client.
_AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
_REGION = os.environ.get("AWS_REGION", "us-east-1")

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


def _error(status_code: int, message: str) -> dict:
    """Consistent JSON error body (D-12)."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }


def handler(event: dict, context) -> dict:
    """API Lambda entry point — GET /recommendations/{customer_id}."""
    # Extract customer_id from HTTP API v2 payload format (pathParameters).
    path_params = event.get("pathParameters") or {}
    customer_id = path_params.get("customer_id", "")

    # D-13: fast-fail on bad format — avoids wasting a 3-5s agent invocation.
    if not _CUSTOMER_ID_PATTERN.match(customer_id):
        return _error(400, "Invalid customer ID format. Use CUST-NNN (3-6 digits).")

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
    if "green" not in body or "cheapest" not in body:
        logger.info("Customer not found customer_id=%s body=%s", customer_id, body)
        return _error(404, f"Customer {customer_id} not found.")

    # D-02: pass-through verbatim — no envelope, no meta. One contract
    # agent -> API -> UI.
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
