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
from pydantic import BaseModel, Field, ValidationError
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Bi-mode imports: in the AgentCore container, /app/agent.py is a script and
# /app/narrative/ is a top-level package (Dockerfile COPYs it there). In the
# repo / offline tests, `agent/narrative/` is a subpackage of the `agent`
# namespace package. Try the container layout first so runtime startup is
# fast; fall back to the repo layout for pytest -m "not smoke".
try:
    from narrative.fallbacks import FALLBACKS
    from narrative.prompt_loader import NARRATIVE_PROMPT
    from narrative.shape import build_shape_tokens
    from narrative.validators import (
        CALL_SCRIPT_MAX_CHARS,
        CALL_SCRIPT_MAX_WORDS,
        USAGE_NARRATIVE_MAX_CHARS,
        USAGE_NARRATIVE_MAX_WORDS,
        _reject_forbidden,
        validate_call_script,
        validate_usage_narrative,
    )
except ImportError:  # pragma: no cover - hit only in offline test repo layout
    from agent.narrative.fallbacks import FALLBACKS
    from agent.narrative.prompt_loader import NARRATIVE_PROMPT
    from agent.narrative.shape import build_shape_tokens
    from agent.narrative.validators import (
        CALL_SCRIPT_MAX_CHARS,
        CALL_SCRIPT_MAX_WORDS,
        USAGE_NARRATIVE_MAX_CHARS,
        USAGE_NARRATIVE_MAX_WORDS,
        _reject_forbidden,
        validate_call_script,
        validate_usage_narrative,
    )

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
    usage_narrative: str = Field(
        max_length=USAGE_NARRATIVE_MAX_CHARS,
        description=(
            "Third-person description of the customer's usage profile. "
            "Maximum 20 words. NEVER contains digits, $/£/€/%, competitor names, "
            "switch verbs, or environmental superlatives."
        ),
    )
    call_script: str = Field(
        max_length=CALL_SCRIPT_MAX_CHARS,
        description=(
            "Second-person one-liner the call-centre agent reads verbatim. "
            "Maximum 22 words. Same forbidden-content rules as usage_narrative."
        ),
    )

    # D-15 dual-gate: these run after Pydantic's max_length + type checks.
    _validate_usage_narrative = validate_usage_narrative
    _validate_call_script = validate_call_script


class RecommendationResponse(BaseModel):
    """Dual-track tariff recommendation — both tracks always present."""
    green: TrackInfo = Field(description="Most energy-efficient (green) plan recommendation")
    cheapest: TrackInfo = Field(description="Lowest projected cost plan recommendation")


# --- Lenient salvage schema (retry path only — per-field fallback per D-02) ---


class _TrackInfoLenient(BaseModel):
    """TrackInfo without narrative validators — used on retry to reach per-field salvage."""
    plan_id: str
    plan_name: str
    saving_monthly: float
    saving_annual: float
    usage_narrative: str
    call_script: str


class _RecommendationResponseLenient(BaseModel):
    green: _TrackInfoLenient
    cheapest: _TrackInfoLenient


# --- Narrative prompt + salvage helpers (D-01/D-02/D-03) ---


def _build_narrative_prompt(customer_id: str, shape_tokens: dict | None = None) -> str:
    """Compose the per-invocation user prompt.

    SYSTEM_PROMPT holds the narrative rules + exemplars (D-10, D-15).
    This function adds the customer_id hint + qualitative shape-tokens line (D-07).
    """
    if shape_tokens:
        tokens_line = ", ".join(f"{k}={v}" for k, v in shape_tokens.items())
        return (
            f"Get tariff savings recommendations for customer {customer_id}. "
            f"Shape tokens: {tokens_line}."
        )
    return f"Get tariff savings recommendations for customer {customer_id}"


def _narrative_fallback_salvage(
    customer_id: str,
    lenient_response: "_RecommendationResponseLenient | None",
    raw_err: ValidationError,
) -> "tuple[RecommendationResponse, dict]":
    """Rebuild a valid RecommendationResponse by per-field fallback (D-02).

    Strategy: take the lenient-parsed output when available; per-field run
    `_reject_forbidden` standalone. Fields that pass keep the LLM text; fields
    that fail swap to FALLBACKS[customer_id][track][field].

    Returns (response, narrative_source_marker).
    """
    fallback_bank = FALLBACKS.get(customer_id)
    narrative_source = {
        "green":    {"usage_narrative": "model", "call_script": "model"},
        "cheapest": {"usage_narrative": "model", "call_script": "model"},
    }

    def _resolve(track: str, field: str, model_value, max_words: int) -> str:
        """Return validated model output if clean; else fallback; log on swap."""
        if model_value is not None:
            try:
                return _reject_forbidden(model_value, max_words=max_words, field_label=field)
            except ValueError as rejection:
                logger.info(
                    "narrative fallback fired",
                    extra={
                        "narrative_fallback_fired": True,
                        "customer_id": customer_id,
                        "track": track,
                        "field": field,
                        "failure_reason": str(rejection),  # reason only — never raw model_value
                    },
                )
        else:
            logger.info(
                "narrative fallback fired (model output unavailable)",
                extra={
                    "narrative_fallback_fired": True,
                    "customer_id": customer_id,
                    "track": track,
                    "field": field,
                    "failure_reason": "lenient parse unavailable",
                },
            )
        narrative_source[track][field] = "fallback"
        # D-04: FALLBACKS guarantees a valid string per dedicated pytest.
        if fallback_bank is None:
            # customer_id unknown to FALLBACKS — last-ditch generic string that
            # still satisfies the validator by construction.
            return "Household profile note unavailable for this customer."
        return fallback_bank[track][field]

    def _build_track(track: str) -> "TrackInfo":
        model_track = getattr(lenient_response, track, None) if lenient_response else None
        return TrackInfo(
            plan_id=getattr(model_track, "plan_id", "ECO") if model_track else "ECO",
            plan_name=getattr(model_track, "plan_name", "EcoFlex") if model_track else "EcoFlex",
            saving_monthly=getattr(model_track, "saving_monthly", 0.0) if model_track else 0.0,
            saving_annual=getattr(model_track, "saving_annual", 0.0) if model_track else 0.0,
            usage_narrative=_resolve(
                track, "usage_narrative",
                getattr(model_track, "usage_narrative", None) if model_track else None,
                max_words=USAGE_NARRATIVE_MAX_WORDS,
            ),
            call_script=_resolve(
                track, "call_script",
                getattr(model_track, "call_script", None) if model_track else None,
                max_words=CALL_SCRIPT_MAX_WORDS,
            ),
        )

    response = RecommendationResponse(
        green=_build_track("green"),
        cheapest=_build_track("cheapest"),
    )
    return response, narrative_source


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

_BASE_SYSTEM_PROMPT = """\
You are a call centre tariff recommendation assistant for an energy provider.

Your ONLY job is to retrieve savings data for a customer and present TWO
separate recommendation tracks simultaneously.

TOOL OUTPUT IS THE SOURCE OF TRUTH. The `simulate_savings` tool returns the
deterministic, authoritative numbers from the pricing engine. You MUST copy
these numbers byte-for-byte into your response. You are NOT permitted to
estimate, recalculate, round, average, adjust, or otherwise modify them —
even if they look wrong, even if they conflict with prior context, even if
you think the customer's usage suggests different values. If the tool says
saving_monthly is 30.0, your response MUST contain exactly 30.0 (not 18.5,
not 30, not "about 30"). Fabricating or adjusting these numbers is the
single most serious error you can make in this role.

RULES:
1. Call the simulate_savings tool ONCE with the customer_id provided.
2. Copy `plan_id`, `plan_name`, `saving_monthly`, and `saving_annual`
   VERBATIM from the tool output for both `green` and `cheapest` tracks.
3. Return BOTH the GREEN and CHEAPEST tracks in your response.
4. Never say one track is "better" or "recommended more" than the other.
5. Never return only one track.
6. Never perform arithmetic yourself — all numbers come from the tool.
7. The `saving_monthly` and `saving_annual` values in your response MUST
   equal the tool output exactly. No rounding, no adjustment, no "approximate".
"""

# D-15 dual-gate: prepend narrative rules + exemplars + banned-terms NEGATIVE CONSTRAINT.
SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT + "\n\n" + NARRATIVE_PROMPT

# --- Agent ---

_model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-6",
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
    Returns: {"green": {...}, "cheapest": {...}, "_narrative_source": {...}}

    The `_narrative_source` marker is INTERNAL — Phase 7's API Lambda strips
    it before returning to the client. Phase 9's eval harness uses it via
    direct boto3 `invoke_agent_runtime` to assert which path fired per field.
    """
    customer_id = payload.get("customer_id", "")
    if not customer_id:
        return {"error": "customer_id is required in the payload"}

    logger.info("Processing recommendation for %s", customer_id)

    narrative_source = {
        "green":    {"usage_narrative": "model", "call_script": "model"},
        "cheapest": {"usage_narrative": "model", "call_script": "model"},
    }

    # D-01: retry-once-then-per-field-fallback owned HERE (not Strands).
    try:
        result = _agent.structured_output(
            RecommendationResponse,
            _build_narrative_prompt(customer_id),
        )
    except ValidationError:
        logger.warning(
            "narrative validator failed on first call — retrying once",
            exc_info=False,
        )
        try:
            result = _agent.structured_output(
                RecommendationResponse,
                _build_narrative_prompt(customer_id),
            )
        except ValidationError as second_err:
            # D-02: per-field fallback. Try lenient parse so we can keep
            # whichever field DID pass; swap only the offender(s).
            lenient_response = None
            try:
                lenient_response = _agent.structured_output(
                    _RecommendationResponseLenient,
                    _build_narrative_prompt(customer_id),
                )
            except Exception:  # noqa: BLE001 — best-effort; fallback bank guarantees completeness
                logger.warning(
                    "lenient salvage parse failed — using full fallback bank",
                    exc_info=False,
                )
            result, narrative_source = _narrative_fallback_salvage(
                customer_id, lenient_response, second_err,
            )
        body = result.model_dump()
        body["_narrative_source"] = narrative_source
        return body
    except Exception:
        # v1.0 tool-failure fallback: direct Lambda call. Narrative fields are
        # absent in this path — it exists for a catastrophic structured_output
        # failure (network, schema conversion, etc.) and should be exceptionally
        # rare. The response shape is the raw tool output (v1.0 contract).
        logger.warning(
            "structured_output failed — falling back to direct Lambda call",
            exc_info=True,
        )
        resp = _lambda_client.invoke(
            FunctionName=_TOOLS_LAMBDA_ARN,
            InvocationType="RequestResponse",
            Payload=json.dumps({"customer_id": customer_id}).encode(),
        )
        raw = json.loads(resp["Payload"].read())
        # Attach fallback narrative + marker so the extended-schema contract holds.
        fb = FALLBACKS.get(customer_id, {})
        for track in ("green", "cheapest"):
            track_fb = fb.get(track, {})
            raw_track = raw.get(track, {})
            if "usage_narrative" not in raw_track:
                raw_track["usage_narrative"] = track_fb.get(
                    "usage_narrative",
                    "Household profile note unavailable for this customer.",
                )
                narrative_source[track]["usage_narrative"] = "fallback"
            if "call_script" not in raw_track:
                raw_track["call_script"] = track_fb.get(
                    "call_script",
                    "Ask about the recommended plan for this household.",
                )
                narrative_source[track]["call_script"] = "fallback"
            raw[track] = raw_track
        raw["_narrative_source"] = narrative_source
        return raw

    # Happy path — validator passed on first call.
    body = result.model_dump()
    body["_narrative_source"] = narrative_source
    return body


if __name__ == "__main__":
    app.run()
