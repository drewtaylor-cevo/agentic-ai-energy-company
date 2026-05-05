"""TariffSpecialist — tariff recommendation specialist.

Extracted from the recommendation path in agent/agent.py::invoke().
Owns the Strands Agent call, FourToolCapHook budget enforcement,
structured output via RecommendationResponse, D-01 retry-once-then-
per-field-fallback chain, and _narrative_source + reasoning_trace
attachment.

The specialist receives the EXISTING module-level _agent and _four_tool_cap
instances via its constructor — no new Agent construction per invocation
(Req 6.4). The handle() method is the recommendation portion of today's
invoke(), extracted without modification to the logic.

Satisfies the AgentRole Protocol (handle(payload) -> dict).

Bi-mode import: try container /app/ layout first, fall back to repo layout.
"""
from __future__ import annotations

import logging
from typing import Any

# Bi-mode import: Agent lives in strands (always available).
from strands import Agent
from strands.types.exceptions import StructuredOutputException

# Bi-mode import: FourToolCapHook
try:
    from hooks.four_tool_cap import FourToolCapHook  # type: ignore[import-not-found]
except ImportError:
    from agent.hooks.four_tool_cap import FourToolCapHook

# Bi-mode import: agent.py helpers and models.
# In the container, agent.py is at /app/agent.py (top-level module `agent`).
# In the repo, it's `agent.agent`. Try container layout first.
try:
    from agent import (  # type: ignore[import-not-found]
        RecommendationResponse,
        ConfirmableAction,
        _RecommendationResponseLenient,
        _build_narrative_prompt,
        _extract_lenient_from_agent_result,
        _extract_reasoning_trace,
        _fetch_deterministic_savings,
        _narrative_fallback_salvage,
        queue_prepared_actions,
    )
except ImportError:
    from agent.agent import (
        RecommendationResponse,
        ConfirmableAction,
        _RecommendationResponseLenient,
        _build_narrative_prompt,
        _extract_lenient_from_agent_result,
        _extract_reasoning_trace,
        _fetch_deterministic_savings,
        _narrative_fallback_salvage,
        queue_prepared_actions,
    )

# Bi-mode import: FALLBACKS bank for the general Exception fallback path.
try:
    from narrative.fallbacks import FALLBACKS  # type: ignore[import-not-found]
except ImportError:
    from agent.narrative.fallbacks import FALLBACKS

logger = logging.getLogger(__name__)


class TariffSpecialist:
    """Tariff recommendation specialist — extracted from invoke().

    Owns:
    - The Strands Agent instance (_agent), received via constructor
    - FourToolCapHook budget enforcement, received via constructor
    - Structured output via RecommendationResponse
    - D-01 retry-once-then-per-field-fallback chain
    - _narrative_source and reasoning_trace attachment
    - Shape tokens and narrative prompt composition
    """

    def __init__(self, agent: Agent, four_tool_cap: FourToolCapHook) -> None:
        self._agent = agent
        self._four_tool_cap = four_tool_cap

    def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run the recommendation flow for a customer.

        Returns a RecommendationResponse dict with _narrative_source
        and reasoning_trace attached.

        This is the recommendation portion of invoke(), extracted verbatim.
        Three paths:
          1. Happy path — structured output succeeds
          2. StructuredOutputException — per-field fallback salvage (D-01/D-02)
          3. General Exception — deterministic savings + FALLBACKS narrative (D-04)
        """
        customer_id = payload["customer_id"]

        narrative_source = {
            "green":    {"usage_narrative": "model", "call_script": "model"},
            "cheapest": {"usage_narrative": "model", "call_script": "model"},
        }

        # A-02 (Phase 13 D-14 amended): reset per-invocation cap counter.
        self._four_tool_cap.reset()

        # D-08: snapshot pre-invocation message length for reasoning_trace
        # extraction — SC-3 mirror (cross-invocation bleed prevention).
        _messages_start = len(self._agent.messages)

        # D-01: retry-once-then-per-field-fallback owned HERE (not Strands).
        agent_result = None
        try:
            agent_result = self._agent(
                _build_narrative_prompt(customer_id),
                structured_output_model=RecommendationResponse,
            )
            # Phase 13 D-14 + D-15 (A-02 amendment): if the 4-tool cap hook
            # cancelled the loop, route through the D-04 fallback.
            if agent_result.stop_reason == "cancelled":
                raise RuntimeError("tool budget exhausted")
            result = agent_result.structured_output
            if result is None:
                raise StructuredOutputException(
                    "structured_output is None after successful stop_reason"
                )
        except StructuredOutputException as terminal_err:
            logger.warning(
                "structured output exhausted — applying per-field fallback",
                extra={"customer_id": customer_id, "reason": str(terminal_err)},
            )
            # D-02: per-field fallback via lenient salvage.
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
                        entry.model_dump()
                        for entry in _extract_reasoning_trace(
                            agent_result,
                            self._agent.messages[_messages_start:],
                        )
                    ],
                }
            body = result.model_dump()
            body["_narrative_source"] = narrative_source
            return body
        except Exception:
            # v1.0 tool-failure fallback: deterministic savings fetch.
            # D-04 never-500 guarantee.
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
                        entry.model_dump()
                        for entry in _extract_reasoning_trace(
                            agent_result,
                            self._agent.messages[_messages_start:],
                        )
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
            raw["kind"] = "recommendation"
            raw["reasoning_trace"] = [
                entry.model_dump()
                for entry in _extract_reasoning_trace(
                    agent_result,
                    self._agent.messages[_messages_start:],
                )
            ]
            return raw

        # Happy path — validator passed.
        body = result.model_dump()
        body["_narrative_source"] = narrative_source
        body["reasoning_trace"] = [
            entry.model_dump()
            for entry in _extract_reasoning_trace(
                agent_result,
                self._agent.messages[_messages_start:],
            )
        ]

        # Agentic Actions Portfolio: prepare confirmable actions (D-04 guarded).
        # Extract savings from the validated result for action preparation.
        savings_for_actions = {
            "green": {
                "plan_id": result.green.plan_id,
                "plan_name": result.green.plan_name,
                "saving_monthly": result.green.saving_monthly,
                "saving_annual": result.green.saving_annual,
            },
            "cheapest": {
                "plan_id": result.cheapest.plan_id,
                "plan_name": result.cheapest.plan_name,
                "saving_monthly": result.cheapest.saving_monthly,
                "saving_annual": result.cheapest.saving_annual,
            },
        }
        pending_actions = queue_prepared_actions(
            customer_id, savings_for_actions
        )
        body["pending_actions"] = [a.model_dump() for a in pending_actions]

        return body
