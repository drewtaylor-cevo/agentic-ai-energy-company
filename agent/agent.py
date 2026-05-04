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
from datetime import datetime, timezone
from typing import Any, Literal

import boto3
from pydantic import BaseModel, Field, ValidationError, field_validator
from strands import Agent, tool
from strands.models import BedrockModel
from strands.types.exceptions import StructuredOutputException
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

# Bi-mode import (D-16): same container /app vs repo layout rationale as above.
try:
    from providers import (
        CustomerDataProvider,
        ToolsLambdaProvider,
        InMemoryProvider,
        SalesforceCustomerDataProvider,
        set_provider,
        get_provider,
    )
except ImportError:  # pragma: no cover - hit only in offline test repo layout
    from agent.providers import (
        CustomerDataProvider,
        ToolsLambdaProvider,
        InMemoryProvider,
        SalesforceCustomerDataProvider,
        set_provider,
        get_provider,
    )

# Phase 13 D-10: deterministic tool-result summary formatters for reasoning_trace.
# Bi-mode import: in the AgentCore container `/app/reasoning/` is a top-level
# package (agent/Dockerfile COPYs it there); in the repo layout it is
# `agent/reasoning/`. Matches the narrative/ + providers.py precedent.
try:
    from reasoning.summaries import (
        summary_detect_bill_shock,
        summary_get_billing_history,
        summary_get_hardship_flag,
        summary_simulate_savings,
    )
except ImportError:  # pragma: no cover - hit only in offline test repo layout
    from agent.reasoning.summaries import (
        summary_detect_bill_shock,
        summary_get_billing_history,
        summary_get_hardship_flag,
        summary_simulate_savings,
    )

# Phase 13 AGENT-01b: Strands HookProvider-based 4-tool cap (A-02 amendment).
# Bi-mode import: agent/hooks/ is COPYed to /app/hooks/ by agent/Dockerfile;
# in the repo layout the module is agent/hooks/four_tool_cap.py. Same
# precedent as narrative/, reasoning/, providers.py.
try:
    from hooks.four_tool_cap import FourToolCapHook
except ImportError:  # pragma: no cover - hit only in offline test repo layout
    from agent.hooks.four_tool_cap import FourToolCapHook

# Phase 15 WF-01: Memory configuration helpers.
# Bi-mode import: agent/memory/ is COPYed to /app/memory/ by agent/Dockerfile;
# in the repo layout the module is agent/memory/config.py. Same precedent as
# narrative/, reasoning/, hooks/, providers.py.
try:
    from memory.config import build_memory_config, build_session_manager
except ImportError:  # pragma: no cover - hit only in offline test repo layout
    from agent.memory.config import build_memory_config, build_session_manager

logger = logging.getLogger(__name__)

# --- Environment (injected by CDK) ---
_TOOLS_LAMBDA_ARN = os.environ.get("TOOLS_LAMBDA_ARN", "")
_REGION = os.environ.get("AWS_REGION", "us-east-1")
# Phase 15 WF-01: Memory resource ID (empty string = Memory not provisioned).
_MEMORY_ID = os.environ.get("MEMORY_ID", "")

# --- boto3 client (module-level, reused across invocations) ---
_lambda_client = boto3.client("lambda", region_name=_REGION)

# D-03: module-level provider singleton — swapped in tests via set_provider(InMemoryProvider(...)).
_provider = ToolsLambdaProvider(_lambda_client, _TOOLS_LAMBDA_ARN)
set_provider(_provider)


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


class ReasoningTraceEntry(BaseModel):
    """Phase 13 D-07: one entry in the reasoning_trace surface.

    D-11 EXEMPTION: `summary` intentionally contains digits, currency ($),
    dates, and percentages — it is code-composed by agent/reasoning/summaries.py
    from deterministic tool outputs. DO NOT apply `_reject_forbidden`,
    `validate_usage_narrative`, `validate_call_script`, or any D-15-family
    narrative validator to `summary`. Counter-pytest in tests/test_schema.py
    locks this exemption — delete that test only if removing the field.
    """
    tool: str = Field(description="Tool name (e.g. 'detect_bill_shock')")
    summary: str = Field(description="Code-composed summary of the tool result")
    # No field validators on summary — D-11 exemption locked.


class RecommendationResponse(BaseModel):
    """Dual-track tariff recommendation — both tracks always present."""
    kind: str = Field(default="recommendation", description="Response type discriminator")
    green: TrackInfo = Field(description="Most energy-efficient (green) plan recommendation")
    cheapest: TrackInfo = Field(description="Lowest projected cost plan recommendation")
    # Phase 13 D-07 — PUBLIC field; NOT stripped by api_lambda/handler.py.
    # Default empty list: single-tool turns (CUST-001/004/005) return [];
    # multi-tool turns (CUST-003) return 2-3 entries.
    reasoning_trace: list[ReasoningTraceEntry] = Field(default_factory=list)


class HardshipResponse(BaseModel):
    """Phase 14 AGENT-02: dignity-preserving hardship routing response.

    Returned when `hardship_flag: true` — the pre-LLM guard in invoke()
    fires BEFORE the agent sees any tariff context. No green/cheapest tracks,
    no plan IDs, no savings figures. D-15 validators apply to `reason` and
    `call_script` (no digits, no currency, no banned terms).
    """
    kind: str = Field(default="hardship", description="Response type discriminator")
    customer_id: str = Field(description="Customer identifier")
    reason: str = Field(
        max_length=USAGE_NARRATIVE_MAX_CHARS,
        description=(
            "Dignity-preserving explanation of why recommendations are unavailable. "
            "Maximum 20 words. NEVER contains digits, $/£/€/%, competitor names, "
            "switch verbs, or environmental superlatives."
        ),
    )
    routing_target: str = Field(
        default="hardship_team",
        description="Internal routing destination for the call",
    )
    call_script: str = Field(
        max_length=CALL_SCRIPT_MAX_CHARS,
        description=(
            "Second-person one-liner the call-centre agent reads verbatim. "
            "Maximum 22 words. Same forbidden-content rules as usage_narrative."
        ),
    )

    # D-15 validators for hardship narrative surfaces. Cannot reuse
    # validate_usage_narrative directly (it's @field_validator("usage_narrative")).
    # Call _reject_forbidden with the same caps instead.
    @field_validator("reason", mode="after")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        return _reject_forbidden(value, max_words=USAGE_NARRATIVE_MAX_WORDS, field_label="reason")

    @field_validator("call_script", mode="after")
    @classmethod
    def validate_hardship_call_script(cls, value: str) -> str:
        return _reject_forbidden(value, max_words=CALL_SCRIPT_MAX_WORDS, field_label="call_script")


# Hardship fallback strings — used when the pre-LLM guard fires.
# Loaded from FALLBACKS if available; otherwise inline defaults.
_HARDSHIP_DEFAULTS = {
    "reason": "This customer account is flagged for dedicated support from our specialist team.",
    "call_script": "Let me connect you with our specialist support team who can best help with your account.",
}


# --- Phase 15 WF-01: Follow-up email response schema ---

# D-15 extended: email body allows up to 100 words (longer form than
# usage_narrative's 20), but the same banned-terms gauntlet applies.
FOLLOW_UP_BODY_MAX_WORDS = 100
FOLLOW_UP_BODY_MAX_CHARS = 600
FOLLOW_UP_SUBJECT_MAX_WORDS = 20
FOLLOW_UP_SUBJECT_MAX_CHARS = 120


class FollowUpEmailResponse(BaseModel):
    """Phase 15 WF-01: draft follow-up email response.

    Returned when the rep clicks "Draft follow-up email" after a recommendation.
    The agent uses AgentCore Memory to recall the prior turn's recommendation
    and drafts an email body the rep can edit and send.

    D-15 extended: subject and body pass the banned-terms gauntlet (no digits,
    no currency, no switch verbs, no competitor names, no environmental
    superlatives). Body allows up to 100 words (longer form).
    """
    kind: Literal["follow_up"] = "follow_up"
    customer_id: str = Field(description="Customer identifier")
    subject: str = Field(
        max_length=FOLLOW_UP_SUBJECT_MAX_CHARS,
        description=(
            "Email subject line. Maximum 20 words. NEVER contains digits, "
            "$/£/€/%, competitor names, switch verbs, or environmental superlatives."
        ),
    )
    body: str = Field(
        max_length=FOLLOW_UP_BODY_MAX_CHARS,
        description=(
            "Email body text the rep can edit before sending. Maximum 100 words. "
            "References the plan by NAME (not ID). Same forbidden-content rules."
        ),
    )
    plan_reference: str = Field(
        description="Plan name from the prior recommendation (e.g. 'EcoFlex Green')",
    )

    @field_validator("subject", mode="after")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        return _reject_forbidden(value, max_words=FOLLOW_UP_SUBJECT_MAX_WORDS, field_label="subject")

    @field_validator("body", mode="after")
    @classmethod
    def validate_body(cls, value: str) -> str:
        return _reject_forbidden(value, max_words=FOLLOW_UP_BODY_MAX_WORDS, field_label="body")


# --- Follow-up fallback defaults (used when FALLBACKS[customer_id]["follow_up"] is missing) ---
_FOLLOW_UP_DEFAULTS = {
    "subject": "Your tariff options from our recent conversation",
    "body": (
        "Thank you for speaking with us about your energy plan options. "
        "As discussed, we identified plans that could better suit your household "
        "usage pattern. Please review the options at your convenience and contact "
        "us if you would like to proceed."
    ),
    "plan_reference": "EcoFlex Green",
}


def _build_hardship_response(customer_id: str) -> dict:
    """Build a HardshipResponse dict for a hardship-flagged customer.

    Code-side only — the LLM never sees tariff context for this customer.
    Uses FALLBACKS[customer_id]["hardship"] if available, else _HARDSHIP_DEFAULTS.
    Validates through HardshipResponse Pydantic model to enforce D-15.
    """
    fb = FALLBACKS.get(customer_id, {}).get("hardship", {})
    reason = fb.get("reason", _HARDSHIP_DEFAULTS["reason"])
    call_script = fb.get("call_script", _HARDSHIP_DEFAULTS["call_script"])

    response = HardshipResponse(
        customer_id=customer_id,
        reason=reason,
        call_script=call_script,
    )
    return response.model_dump()


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


_SAVINGS_TRACK_FIELDS = ("plan_id", "plan_name", "saving_monthly", "saving_annual")


def _fetch_deterministic_savings(customer_id: str) -> dict[str, dict[str, Any]]:
    """Fetch and validate savings from the deterministic Tools Lambda path.

    Fallback paths may salvage model-generated narrative, but tariff identity
    and savings figures must still come from the pricing engine (SAV-03).
    """
    raw = get_provider().simulate_savings(customer_id)
    if not isinstance(raw, dict):
        raise RuntimeError("simulate_savings returned non-object payload")

    validated: dict[str, dict[str, Any]] = {}
    for track in ("green", "cheapest"):
        raw_track = raw.get(track)
        if not isinstance(raw_track, dict):
            raise RuntimeError(f"simulate_savings missing {track} track")

        missing = [field for field in _SAVINGS_TRACK_FIELDS if field not in raw_track]
        if missing:
            raise RuntimeError(
                f"simulate_savings {track} track missing fields: {', '.join(missing)}"
            )

        for field in ("plan_id", "plan_name"):
            if not isinstance(raw_track[field], str) or not raw_track[field].strip():
                raise RuntimeError(f"simulate_savings {track}.{field} must be a non-empty string")

        for field in ("saving_monthly", "saving_annual"):
            value = raw_track[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RuntimeError(f"simulate_savings {track}.{field} must be numeric")

        validated[track] = {
            field: raw_track[field] for field in _SAVINGS_TRACK_FIELDS
        }

    return validated


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
    deterministic_savings = _fetch_deterministic_savings(customer_id)
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
        savings_track = deterministic_savings[track]
        return TrackInfo(
            plan_id=savings_track["plan_id"],
            plan_name=savings_track["plan_name"],
            saving_monthly=savings_track["saving_monthly"],
            saving_annual=savings_track["saving_annual"],
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


def _extract_lenient_from_agent_result(
    agent_result: "AgentResult | None",
) -> "_RecommendationResponseLenient | None":
    """Pull the model's last attempt at RecommendationResponse input from message history.

    Zero-network alternative to issuing a third structured_output() call for
    per-field salvage. Reads the last assistant message's toolUse block whose
    name is "RecommendationResponse" and parses its `input` via the lenient
    schema. Returns None on any failure (caller falls back to FALLBACKS bank).
    """
    if agent_result is None or agent_result.message is None:
        return None
    content_blocks = agent_result.message.get("content", []) or []
    for block in reversed(content_blocks):
        if not isinstance(block, dict):
            continue
        tool_use = block.get("toolUse") or block.get("tool_use")
        if tool_use and tool_use.get("name") == "RecommendationResponse":
            try:
                return _RecommendationResponseLenient(**tool_use.get("input", {}))
            except Exception:  # noqa: BLE001 — best-effort salvage
                return None
    return None


# --- Reasoning-trace extractor (Phase 13 D-08) ---
#
# Mirrors _extract_lenient_from_agent_result structurally, but iterates
# content[] forward (order-preserving) and pairs toolUse with toolResult by
# toolUseId. Returns [] on ANY failure (missing content, missing pair,
# malformed JSON, agent_result is None). Never raises — the @app.entrypoint
# invoke() depends on this discipline.
_TRACE_TOOLS = {
    "detect_bill_shock",
    "get_billing_history",
    "get_hardship_flag",
    "simulate_savings",
}


def _summarise_tool_result(tool_name: str, payload: Any) -> str:
    """Dispatch to the deterministic per-tool formatter (D-10, SAV-03)."""
    if tool_name == "detect_bill_shock":
        return summary_detect_bill_shock(payload)
    if tool_name == "get_billing_history":
        return summary_get_billing_history(payload)
    if tool_name == "get_hardship_flag":
        return summary_get_hardship_flag(payload)
    if tool_name == "simulate_savings":
        return summary_simulate_savings(payload)
    # Unknown tool: produce a generic one-liner rather than raising.
    return f"{tool_name} called"


def _extract_reasoning_trace(
    agent_result: "AgentResult | None",
    messages: "list | None" = None,
) -> list[ReasoningTraceEntry]:
    """Collect ordered (tool, summary) entries for the reasoning_trace surface (D-08).

    Iterates content blocks collecting every toolUse whose name is in
    _TRACE_TOOLS. For each toolUse, finds the matching toolResult (same
    toolUseId) and composes a deterministic summary via the per-tool formatter
    (D-10).

    Source selection:
    - When `messages` is provided (Strands 1.37 live path, post-fix), iterate
      all content blocks across `messages` — this captures intermediate
      tool-use/tool-result turns that `agent_result.message` (LAST message
      only) drops when `structured_output_model=` is set.
    - When `messages` is None (offline unit tests with a synthetic
      agent_result), fall back to `agent_result.message['content']` — the
      pre-fix behaviour keeps the offline test contract intact.

    Returns [] on ANY failure (missing content, missing pair, malformed JSON,
    agent_result is None AND messages is None). NEVER raises — invoke() relies
    on it.
    """
    # Collect content blocks across the relevant message slice.
    content_blocks: list = []
    if messages:
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            for block in msg.get("content", []) or []:
                content_blocks.append(block)
    elif agent_result is not None and agent_result.message is not None:
        content_blocks = list(agent_result.message.get("content", []) or [])
    else:
        return []

    # Build O(1) index of toolResult by toolUseId.
    tool_results_by_id: dict[str, dict] = {}
    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        tool_result = block.get("toolResult")
        if tool_result and isinstance(tool_result, dict):
            tool_use_id = tool_result.get("toolUseId")
            if isinstance(tool_use_id, str):
                tool_results_by_id[tool_use_id] = tool_result

    entries: list[ReasoningTraceEntry] = []
    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        tool_use = block.get("toolUse") or block.get("tool_use")
        if not tool_use:
            continue
        name = tool_use.get("name")
        if name not in _TRACE_TOOLS:
            continue
        tool_use_id = tool_use.get("toolUseId")
        result_block = tool_results_by_id.get(tool_use_id)
        if result_block is None:
            continue
        try:
            # Prefer structured json content; fall back to json.loads(text).
            result_payload = None
            for rc in result_block.get("content", []) or []:
                if "json" in rc:
                    result_payload = rc["json"]
                    break
                if "text" in rc:
                    try:
                        result_payload = json.loads(rc["text"])
                        break
                    except (TypeError, ValueError):
                        continue
            if result_payload is None:
                continue
            summary = _summarise_tool_result(name, result_payload)
            entries.append(ReasoningTraceEntry(tool=name, summary=summary))
        except Exception:  # noqa: BLE001 — best-effort extraction
            continue

    return entries


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
    # D-04: provider wraps the Lambda invoke; arithmetic stays in Tools Lambda (SAV-03).
    return get_provider().simulate_savings(customer_id)


# Phase 13 D-01: three new @tool wrappers that go DIRECT to _lambda_client.invoke
# (NOT through get_provider()) — preserves LD-5 3-method Protocol in
# agent/providers.py. Each wrapper posts {"action": "<name>", "customer_id": ...}
# to the Phase 12 action dispatcher at lambda/handler.py::handler.
# Matches the pre-Phase-12 simulate_savings Lambda wrapper style; sync callable
# (Strands' @tool handles threading via ConcurrentToolExecutor internally).


@tool
def detect_bill_shock(customer_id: str) -> dict:
    """Detect bill-shock anomaly on the most recent month's projected STD cost.

    Numeric content (delta, mean, current-month cost) is computed by a pure
    Python helper in the Tools Lambda — SAV-03. Do NOT estimate or round any
    value yourself; copy the tool's return dict verbatim.

    Args:
        customer_id: Customer identifier in format CUST-NNN (e.g. CUST-003).

    Returns:
        Dict with keys: is_shock (bool), delta_dollars (float), shock_month
        (str, YYYY-MM), mean_dollars (float), current_dollars (float).
    """
    resp = _lambda_client.invoke(
        FunctionName=_TOOLS_LAMBDA_ARN,
        InvocationType="RequestResponse",
        Payload=json.dumps(
            {"action": "detect_bill_shock", "customer_id": customer_id}
        ).encode(),
    )
    return json.loads(resp["Payload"].read())


@tool
def get_billing_history(customer_id: str) -> dict:
    """Return the 12-month billing history for a customer.

    PROFILE row is filtered server-side per Phase 11 D-21 — the result is a
    list of 12 monthly billing records, ASC by month.

    Args:
        customer_id: Customer identifier in format CUST-NNN.

    Returns:
        Response payload containing the 12-month billing-record list.
    """
    resp = _lambda_client.invoke(
        FunctionName=_TOOLS_LAMBDA_ARN,
        InvocationType="RequestResponse",
        Payload=json.dumps(
            {"action": "get_billing_history", "customer_id": customer_id}
        ).encode(),
    )
    return json.loads(resp["Payload"].read())


@tool
def get_hardship_flag(customer_id: str) -> dict:
    """Return the hardship_flag boolean for a customer (Phase 14 co-land).

    Phase 13 exposes the tool but does NOT enforce short-circuit — Phase 14
    wires the pre-LLM guard + discriminated union. For now the agent can call
    it as an evidence-gathering step; the result enters the reasoning_trace
    observability surface.

    Args:
        customer_id: Customer identifier in format CUST-NNN.

    Returns:
        Dict with `hardship_flag: bool` (keyed to match Phase 11 pure helper).
    """
    resp = _lambda_client.invoke(
        FunctionName=_TOOLS_LAMBDA_ARN,
        InvocationType="RequestResponse",
        Payload=json.dumps(
            {"action": "get_hardship_flag", "customer_id": customer_id}
        ).encode(),
    )
    return json.loads(resp["Payload"].read())


# --- System prompt (REC-03: both tracks, never ranked) ---

_BASE_SYSTEM_PROMPT = """\
You are a call centre tariff recommendation assistant for an energy provider.

Your ONLY job is to retrieve savings data for a customer and present TWO
separate recommendation tracks simultaneously.

You have access to FOUR tools. Decide which to call based on the customer and
the request — do NOT follow a fixed script, and IGNORE any `?flow=...`
query-string hint if present (the assistant chooses the tool graph, not the
URL).

AVAILABLE TOOLS (preference-ordered — call in this order when relevant):
  1. `get_hardship_flag(customer_id)` — check first if the customer is flagged
     for hardship support. If so, still proceed to recommendation in this
     phase; the trace records the check as evidence. (A future phase
     short-circuits hardship entirely.)
  2. `detect_bill_shock(customer_id)` — optional evidence tool: confirm
     whether the most recent month's projected cost deviates sharply from
     the 11-month mean (symmetric > 30% threshold). See the SHORT-CIRCUIT
     RULE below before deciding whether to call this tool.
  3. `get_billing_history(customer_id)` — optional: retrieve the full
     12-month billing record list when the narrative requires supporting
     evidence of usage trend. See the EMPTY BILLING STOP RULE below for
     what to do when this returns an empty list.
  4. `simulate_savings(customer_id)` — ALWAYS call LAST. Returns both GREEN
     and CHEAPEST recommendation tracks with deterministic savings figures.
     Without this tool call the response is incomplete (REC-03).

Do not call unnecessary tools — each extra tool call costs latency.

SHORT-CIRCUIT RULE (Phase 13.1 D-13.1-14):
`get_hardship_flag` is the universal first tool call. After that, branch by
persona:
- NON-SHOCK customers (the common case): call `simulate_savings` directly
  after `get_hardship_flag`. Do NOT call `detect_bill_shock` or
  `get_billing_history`. The 2-tool path `get_hardship_flag → simulate_savings`
  is correct and complete for non-shock customers.
- SHOCK customers (bill-shock evident from the user's turn or prior context):
  call `detect_bill_shock` second, then `simulate_savings`. Only call
  `get_billing_history` if the narrative specifically requires enumerating
  the monthly usage trend.
Every extra tool call costs ~400-700ms of warm latency; choose the
shortest path that answers the request.

EMPTY BILLING STOP RULE (Phase 13.1 D-13.1-12):
If `get_billing_history` returns an empty list, STOP. Do NOT call
`simulate_savings`. Do NOT synthesise track data. Do NOT emit placeholder
`plan_id` values like "UNKNOWN" on either track. Return only an
`errorMessage` body indicating the customer was not found — the existing
D-04 fallback shape `{"errorMessage": "customer not found"}` is correct.
An empty `get_billing_history` result means the customer record does not
exist; synthesising recommendations for a non-existent customer is the
most serious correctness error you can make after fabricating savings
figures.

ARITHMETIC INTEGRITY (SAV-03, extended):
ALL arithmetic — savings, bill-shock deltas, averages, dates — comes from
tools. NEVER compute, estimate, round, or adjust numbers yourself. Tool
output is the single source of truth for every numeric and date value in
your response.

TOOL OUTPUT IS THE SOURCE OF TRUTH. Each tool returns deterministic,
authoritative numbers from the pricing engine or the anomaly detector. You
MUST copy these numbers byte-for-byte into your response. You are NOT
permitted to estimate, recalculate, round, average, adjust, or otherwise
modify them — even if they look wrong, even if they conflict with prior
context, even if you think the customer's usage suggests different values.
If a tool says saving_monthly is 30.0, your response MUST contain exactly
30.0 (not 18.5, not 30, not "about 30"). Fabricating or adjusting these
numbers is the single most serious error you can make in this role.

RULES:
1. Call tools in the preference order above; always finish with
   `simulate_savings`. NEVER return a response that omits either the GREEN
   or CHEAPEST track.
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

# Phase 13 D-14 (amended A-02): module-level FourToolCapHook instance.
# `used` counter is reset by invoke() at the top of every invocation to
# avoid session bleed (SC-3 mirror — module-level counters leak across
# invocations). The cap mechanism is a Strands HookProvider — NOT an
# Agent constructor iteration-cap kwarg (Strands 1.37.0 has no such
# kwarg; Pitfall 2 prevention).
_four_tool_cap = FourToolCapHook(budget=4)

_agent = Agent(
    model=_model,
    system_prompt=SYSTEM_PROMPT,
    tools=[
        simulate_savings,
        detect_bill_shock,
        get_billing_history,
        get_hardship_flag,
    ],
    hooks=[_four_tool_cap],
)


# --- AgentCore entrypoint ---

app = BedrockAgentCoreApp()


# --- Phase 15 WF-01: Follow-up email system prompt ---

_FOLLOW_UP_SYSTEM_PROMPT = """\
You are a call centre follow-up email assistant for an energy provider.

Your ONLY job is to draft a short, professional follow-up email that the
call-centre agent can review, edit, and send to the customer after a
tariff recommendation conversation.

CONTEXT: The customer was recently shown tariff recommendation options
during a call. You have access to the conversation history from that call
via Memory. Use it to personalise the email.

RULES:
1. Reference the recommended plan by NAME only (e.g. "EcoFlex Green").
   NEVER include plan IDs (e.g. "ECO", "VAL", "SOL", "TOU").
2. NEVER include any numbers, dollar amounts, percentages, or dates in
   the email subject or body. The savings figures were discussed on the
   call — the email is a qualitative follow-up, not a quote.
3. NEVER perform arithmetic. You have no tools in this turn.
4. Keep the tone warm, professional, and brief.
5. The subject line should be under 20 words.
6. The body should be under 100 words.
7. Do NOT use switch verbs (switch, change, move, transfer, cancel).
8. Do NOT mention competitor names or environmental superlatives.
9. Set plan_reference to the GREEN plan name from the prior recommendation.
"""


def _build_follow_up_response(customer_id: str) -> dict:
    """Build a FollowUpEmailResponse dict from fallback templates.

    Code-side only — used when Memory is unavailable or the agent turn fails.
    Uses FALLBACKS[customer_id]["follow_up"] if available, else _FOLLOW_UP_DEFAULTS.
    Validates through FollowUpEmailResponse Pydantic model to enforce D-15.
    """
    fb = FALLBACKS.get(customer_id, {}).get("follow_up", {})
    subject = fb.get("subject", _FOLLOW_UP_DEFAULTS["subject"])
    body = fb.get("body", _FOLLOW_UP_DEFAULTS["body"])
    plan_reference = fb.get("plan_reference", _FOLLOW_UP_DEFAULTS["plan_reference"])

    response = FollowUpEmailResponse(
        customer_id=customer_id,
        subject=subject,
        body=body,
        plan_reference=plan_reference,
    )
    return response.model_dump()


def draft_follow_up(payload: dict) -> dict:
    """Handle a follow-up email draft request (Phase 15 WF-01).

    Expects payload: {"customer_id": "CUST-001", "action": "follow_up"}
    Returns: {"kind": "follow_up", "customer_id": "...", "subject": "...",
              "body": "...", "plan_reference": "...", "_workflow_source": {...}}

    Uses AgentCore Memory to recall the prior turn's recommendation context.
    If Memory is unavailable or the agent turn fails, falls back to a
    deterministic template from FALLBACKS (D-04 never-500).

    CRITICAL: `runtimeSessionId` is NOT used here — that's the AgentCore
    runtime session (SC-3). Memory uses its own `session_id` derived from
    customer_id + UTC date (AP-2 distinction).
    """
    customer_id = payload.get("customer_id", "")
    if not customer_id:
        return {"error": "customer_id is required in the payload"}

    logger.info("Drafting follow-up email for %s", customer_id)

    workflow_source = {"subject": "model", "body": "model"}

    # Attempt Memory-backed agent turn.
    try:
        if not _MEMORY_ID:
            raise RuntimeError("MEMORY_ID not configured — Memory not provisioned")

        # Build deterministic Memory session key (AP-2: NOT runtimeSessionId).
        session_date = datetime.now(timezone.utc).date().isoformat()
        memory_config = build_memory_config(_MEMORY_ID, customer_id, session_date)
        session_manager = build_session_manager(memory_config, _REGION)

        # Create a dedicated agent for the follow-up turn with Memory wired in.
        follow_up_agent = Agent(
            model=_model,
            system_prompt=_FOLLOW_UP_SYSTEM_PROMPT,
            tools=[],  # No tools in follow-up turn — narrative only
            session_manager=session_manager,
        )

        agent_result = follow_up_agent(
            f"Draft a follow-up email for customer {customer_id} referencing "
            f"the tariff recommendations from our recent conversation.",
            structured_output_model=FollowUpEmailResponse,
        )

        result = agent_result.structured_output
        if result is None:
            raise StructuredOutputException(
                "structured_output is None for follow-up email"
            )

        body = result.model_dump()
        body["_workflow_source"] = workflow_source
        return body

    except Exception as err:  # noqa: BLE001 — D-04 never-500
        logger.warning(
            "Follow-up agent turn failed for %s — using fallback template: %s",
            customer_id, err,
        )
        workflow_source = {"subject": "fallback", "body": "fallback"}
        try:
            body = _build_follow_up_response(customer_id)
            body["_workflow_source"] = workflow_source
            return body
        except Exception as fallback_err:  # noqa: BLE001 — D-04 absolute last resort
            logger.error(
                "Follow-up fallback also failed for %s: %s",
                customer_id, fallback_err,
            )
            # Absolute last resort — hand-craft a minimal valid response.
            return {
                "kind": "follow_up",
                "customer_id": customer_id,
                "subject": "Your tariff options from our recent conversation",
                "body": (
                    "Thank you for speaking with us about your energy plan options. "
                    "Please contact us if you would like to proceed."
                ),
                "plan_reference": "EcoFlex Green",
                "_workflow_source": {"subject": "fallback", "body": "fallback"},
            }


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

    # Phase 15 WF-01: action dispatcher. Default is "recommend" (existing path).
    action = payload.get("action", "recommend")
    if action == "follow_up":
        return draft_follow_up(payload)

    logger.info("Processing recommendation for %s", customer_id)

    # Phase 14 AGENT-02: pre-LLM hardship guard. Fires BEFORE the agent
    # sees any tariff context — code-side enforcement, not prompt-side.
    # get_provider().get_hardship_flag() goes direct to the data layer
    # (InMemoryProvider offline, ToolsLambdaProvider in production).
    try:
        hardship_result = get_provider().get_hardship_flag(customer_id)
        if hardship_result.get("hardship") is True:
            logger.info("Hardship flag detected for %s — short-circuiting", customer_id)
            hardship_body = _build_hardship_response(customer_id)
            # Attach _narrative_source marker for observability (Phase 7 contract).
            # API Lambda strips this before returning to the client.
            hardship_body["_narrative_source"] = {
                "hardship": {"reason": "fallback", "call_script": "fallback"},
            }
            return hardship_body
    except Exception as hardship_err:  # noqa: BLE001 — D-04 never-500
        # If the hardship check itself fails, log and continue to the normal
        # recommendation path. The customer gets a recommendation rather than
        # a 500. This preserves D-04.
        logger.warning(
            "Hardship flag check failed for %s — proceeding to recommendation: %s",
            customer_id, hardship_err,
        )

    narrative_source = {
        "green":    {"usage_narrative": "model", "call_script": "model"},
        "cheapest": {"usage_narrative": "model", "call_script": "model"},
    }

    # A-02 (Phase 13 D-14 amended): reset per-invocation cap counter. The
    # module-level _four_tool_cap accumulates state across invocations
    # otherwise and silently denies tool calls to later requests (SC-3 mirror
    # — module-level counters leak).
    _four_tool_cap.reset()

    # D-08 (Phase 13 live-regression fix): Strands 1.37's AgentResult.message
    # is the LAST turn only; with structured_output_model= set, intermediate
    # tool-use/tool-result turns live in the Agent's conversation history
    # (_agent.messages), not on agent_result. Snapshot the pre-invocation
    # length so _extract_reasoning_trace reads only THIS invocation's new
    # messages — SC-3 mirror (cross-invocation bleed would leak prior tool
    # uses into later reasoning traces).
    _messages_start = len(_agent.messages)

    # D-01: retry-once-then-per-field-fallback owned HERE (not Strands).
    # Under Strands 1.37.0+ the retry is INLINE within one _agent() call
    # (StructuredOutputTool.stream() catches ValidationError + yields tool-error
    # back to LLM for self-correction; force-tool-use round is Strands' second
    # attempt). Terminal failure surfaces as StructuredOutputException OR
    # agent_result.structured_output is None — we catch both. (RESEARCH §D-06 (c))
    agent_result = None
    try:
        agent_result = _agent(
            _build_narrative_prompt(customer_id),
            structured_output_model=RecommendationResponse,
        )
        # Phase 13 D-14 + D-15 (A-02 amendment): if the 4-tool cap hook
        # cancelled the loop, route through the D-04 fallback by raising
        # into the existing except Exception below. The partial tool-call
        # evidence (whatever fired before the cap) is still stitched into
        # the response via _extract_reasoning_trace in the fallback branch.
        if agent_result.stop_reason == "cancelled":
            raise RuntimeError("tool budget exhausted")
        result = agent_result.structured_output
        if result is None:
            # End-of-turn without structured output — force round must have failed.
            # Pitfall 4: treat identically to StructuredOutputException.
            raise StructuredOutputException(
                "structured_output is None after successful stop_reason"
            )
    except StructuredOutputException as terminal_err:
        logger.warning(
            "structured output exhausted — applying per-field fallback",
            extra={"customer_id": customer_id, "reason": str(terminal_err)},
        )
        # D-02: per-field fallback. Under the new API, salvage reads the LAST
        # assistant message's toolUse block (zero network cost) rather than
        # issuing a third _agent(..., structured_output_model=_RecommendationResponseLenient) call.
        lenient_response = _extract_lenient_from_agent_result(agent_result)
        if lenient_response is None:
            logger.warning(
                "lenient salvage parse failed — using full fallback bank",
                exc_info=False,
            )
        try:
            result, narrative_source = _narrative_fallback_salvage(
                customer_id, lenient_response, terminal_err,
            )
        except Exception as fallback_err:  # noqa: BLE001 - preserve D-04 contract
            logger.warning(
                "deterministic savings fallback failed during narrative salvage",
                extra={"customer_id": customer_id, "reason": str(fallback_err)},
                exc_info=True,
            )
            return {
                "errorMessage": str(fallback_err),
                "_narrative_source": narrative_source,
                "reasoning_trace": [
                    entry.model_dump() for entry in _extract_reasoning_trace(agent_result, _agent.messages[_messages_start:])
                ],
            }
        body = result.model_dump()
        body["_narrative_source"] = narrative_source
        return body
    except Exception:
        # v1.0 tool-failure fallback: deterministic savings fetch. Narrative
        # fields are attached from FALLBACKS so the extended-schema contract holds.
        # D-04 never-500 guarantee — UNCHANGED from pre-migration shape.
        logger.warning(
            "agent invocation failed — falling back to deterministic savings helper",
            exc_info=True,
        )
        try:
            raw = _fetch_deterministic_savings(customer_id)
        except Exception as fallback_err:  # noqa: BLE001 - preserve D-04 contract
            logger.warning(
                "deterministic savings fallback failed",
                extra={"customer_id": customer_id, "reason": str(fallback_err)},
                exc_info=True,
            )
            return {
                "errorMessage": str(fallback_err),
                "_narrative_source": narrative_source,
                "reasoning_trace": [
                    entry.model_dump() for entry in _extract_reasoning_trace(agent_result, _agent.messages[_messages_start:])
                ],
            }
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
        # Phase 14: add kind discriminator for API Lambda routing.
        raw["kind"] = "recommendation"
        # Phase 13 D-15 (amended A-02): stitch whatever partial trace we
        # captured before the cap fired (or empty list if the agent never
        # started, or the cap cancelled before any tool completed).
        # agent_result may be None or bound to the cancelled result — the
        # extractor tolerates both (returns [] on any failure).
        raw["reasoning_trace"] = [
            entry.model_dump() for entry in _extract_reasoning_trace(agent_result, _agent.messages[_messages_start:])
        ]
        return raw

    # Happy path — validator passed (possibly after Strands' inline self-correction).
    body = result.model_dump()
    body["_narrative_source"] = narrative_source
    # Phase 13 D-07 + D-08: attach reasoning_trace to the response body.
    # Extractor is best-effort (returns [] on any failure — never raises).
    body["reasoning_trace"] = [
        entry.model_dump() for entry in _extract_reasoning_trace(agent_result, _agent.messages[_messages_start:])
    ]
    return body


if __name__ == "__main__":
    app.run()
