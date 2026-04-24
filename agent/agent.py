"""Strands SDK agent for tariff recommendations.

Deployed to AWS Bedrock AgentCore managed runtime. Exposes /invocations and
/ping endpoints via BedrockAgentCoreApp. Uses a single @tool that invokes the
Phase 1 ToolsLambda to get deterministic Green + Cheapest savings figures.

The LLM (Claude 3.7 Sonnet) orchestrates tool calls and composes the response.
It NEVER performs arithmetic — all numbers come from the tool (SAV-03).
"""
import json
import os
import logging

import boto3
from pydantic import BaseModel, Field
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

logger = logging.getLogger(__name__)

# --- Environment (injected by CDK) ---
_TOOLS_LAMBDA_ARN = os.environ.get("TOOLS_LAMBDA_ARN", "")
_REGION = os.environ.get("AWS_REGION", "us-east-1")

# --- boto3 client (module-level, reused across invocations) ---
_lambda_client = boto3.client("lambda", region_name=_REGION)


# --- Pydantic response schema (REC-03: both tracks always present) ---

class TrackInfo(BaseModel):
    """A single recommendation track (Green or Cheapest)."""
    plan_id: str = Field(description="Tariff plan identifier (e.g. ECO, VAL)")
    plan_name: str = Field(description="Human-readable plan name")
    saving_monthly: float = Field(description="Projected monthly saving in dollars")
    saving_annual: float = Field(description="Projected annual saving in dollars")


class RecommendationResponse(BaseModel):
    """Dual-track tariff recommendation — both tracks always present."""
    green: TrackInfo = Field(description="Most energy-efficient (green) plan recommendation")
    cheapest: TrackInfo = Field(description="Lowest projected cost plan recommendation")


# --- Tool definition ---

@tool
def simulate_savings(customer_id: str) -> dict:
    """Calculate Green and Cheapest tariff savings for a customer.

    Returns both recommendation tracks from the deterministic savings engine.
    The numbers returned are exact — do NOT recalculate, round, or estimate them.

    Args:
        customer_id: Customer identifier in format CUST-NNN (e.g. CUST-001).

    Returns:
        Dict with 'green' and 'cheapest' keys, each containing plan_id,
        plan_name, saving_monthly ($/month), and saving_annual ($/year).
    """
    if not _TOOLS_LAMBDA_ARN:
        raise RuntimeError("TOOLS_LAMBDA_ARN not set — agent misconfigured")

    resp = _lambda_client.invoke(
        FunctionName=_TOOLS_LAMBDA_ARN,
        InvocationType="RequestResponse",
        Payload=json.dumps({"customer_id": customer_id}).encode(),
    )

    payload = json.loads(resp["Payload"].read())

    # Check for Lambda errors
    if "FunctionError" in resp:
        raise RuntimeError(f"ToolsLambda error: {payload}")

    return payload


# --- System prompt (REC-03: both tracks, never ranked) ---

SYSTEM_PROMPT = """\
You are a call centre tariff recommendation assistant for an energy provider.

Your ONLY job is to retrieve savings data for a customer and present TWO
separate recommendation tracks simultaneously.

RULES:
1. Call the simulate_savings tool ONCE with the customer_id provided.
2. Use ONLY the numbers returned by the tool. Do NOT recalculate, estimate,
   or round the savings figures yourself.
3. Return BOTH the GREEN and CHEAPEST tracks in your response.
4. Never say one track is "better" or "recommended more" than the other.
5. Never return only one track.
6. Never perform arithmetic yourself — all numbers come from the tool.
"""

# --- Agent ---

_model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    region_name=_REGION,
)

_agent = Agent(
    model=_model,
    system_prompt=SYSTEM_PROMPT,
    tools=[simulate_savings],
)


# --- AgentCore entrypoint ---

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Handle an incoming AgentCore invocation.

    Expects payload: {"customer_id": "CUST-001"}
    Returns: {"green": {...}, "cheapest": {...}}
    """
    customer_id = payload.get("customer_id", "")
    if not customer_id:
        return {"error": "customer_id is required in the payload"}

    logger.info("Processing recommendation for %s", customer_id)

    try:
        result = _agent.structured_output(
            RecommendationResponse,
            f"Get tariff savings recommendations for customer {customer_id}",
        )
        return result.model_dump()
    except Exception:
        # Fallback: if structured_output doesn't work with tool calls,
        # call the Lambda directly and return the raw result.
        logger.warning(
            "structured_output failed — falling back to direct Lambda call",
            exc_info=True,
        )
        resp = _lambda_client.invoke(
            FunctionName=_TOOLS_LAMBDA_ARN,
            InvocationType="RequestResponse",
            Payload=json.dumps({"customer_id": customer_id}).encode(),
        )
        return json.loads(resp["Payload"].read())


if __name__ == "__main__":
    app.run()
