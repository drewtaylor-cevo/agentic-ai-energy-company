"""Offline smoke for Agent wiring — catches broken construction locally in <1s.

Rationale: Phase 6 Plan 03 spent 5 deploy cycles chasing integration bugs.
The migration to Strands 1.37.0+ structured_output_model API is a wiring
change; a unit test here catches any future regression before cdk deploy.

D-05/D-06 compliance — asserts simulate_savings is in the tool registry
alongside the dynamically-registered RecommendationResponse schema-tool.
"""
import pytest
from pydantic import ValidationError

from agent.agent import (
    RecommendationResponse,
    SYSTEM_PROMPT,
    _agent,
    simulate_savings,
)


def test_agent_has_simulate_savings_tool():
    """simulate_savings remains a callable tool on the module-level Agent.

    Attribute path for tool-name enumeration is verified per RESEARCH
    assumption A4 — LOW risk. If it changes, the assertion message shows
    the observed shape so the executor can adjust.
    """
    registry = _agent.tool_registry
    tool_names = list(registry.registry.keys()) if hasattr(registry, "registry") else []
    assert "simulate_savings" in tool_names, (
        f"simulate_savings missing from Agent tool registry; have: {tool_names}"
    )


def test_structured_output_tool_registers_dynamically():
    """When invoked with structured_output_model, schema-tool joins the registry.

    This is what fixes DEMO-02: both tools visible in the same event-loop turn.
    Mocks nothing — inspects the StructuredOutputContext directly.
    """
    from strands.tools.structured_output._structured_output_context import (
        StructuredOutputContext,
    )
    ctx = StructuredOutputContext(structured_output_model=RecommendationResponse)
    assert ctx.is_enabled is True
    assert ctx.expected_tool_name == "RecommendationResponse", (
        "schema-tool name derives from Pydantic class name (upstream contract)"
    )
    assert ctx.structured_output_tool is not None

    # Validator preservation (D-06 b): round-tripping a poisoned input raises
    # ValidationError, identical to the deprecated path.
    with pytest.raises(ValidationError):
        RecommendationResponse(
            green={
                "plan_id": "ECO", "plan_name": "EcoFlex",
                "saving_monthly": 30.0, "saving_annual": 360.0,
                "usage_narrative": "Saves $30 a month",  # poisoned — has $ and digits
                "call_script": "clean script text here",
            },
            cheapest={
                "plan_id": "VAL", "plan_name": "Value",
                "saving_monthly": 55.0, "saving_annual": 660.0,
                "usage_narrative": "clean narrative",
                "call_script": "clean script",
            },
        )


def test_system_prompt_retains_rule_7():
    """D-07: TOOL-OUTPUT-AS-SOURCE-OF-TRUTH + Rule 7 preserved post-migration."""
    assert "TOOL OUTPUT IS THE SOURCE OF TRUTH" in SYSTEM_PROMPT
    assert "saving_monthly` and `saving_annual` values" in SYSTEM_PROMPT
    assert "equal the tool output exactly" in SYSTEM_PROMPT


# ----------------------------------------------------------------------
# Phase 13 Plan 03 Task 3.2 — _BASE_SYSTEM_PROMPT extension (D-23).
#
# Assertions lock:
# - Generalised SAV-03 "ALL arithmetic" clause
# - Preference-ordered 4-tool graph (names 4 tools)
# - REC-03 "ALWAYS finish with simulate_savings" clause
# - Rules 2-7 verbatim preserved (byte-exact snapshot of the D-15
#   narrative clauses + REC-03 + no-arithmetic + byte-exact-saving)
# - ?flow=bill_shock intent-rejection clause
# - SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT + "\n\n" + NARRATIVE_PROMPT
# ----------------------------------------------------------------------


def test_base_system_prompt_contains_generalised_sav_03():
    """D-23: SAV-03 language generalised from simulate_savings-only to all tools."""
    from agent.agent import _BASE_SYSTEM_PROMPT

    assert "ALL arithmetic" in _BASE_SYSTEM_PROMPT, (
        "D-23: generalised SAV-03 clause missing — must cover every arithmetic tool, "
        "not just simulate_savings."
    )
    assert "NEVER compute, estimate, round, or adjust numbers yourself" in _BASE_SYSTEM_PROMPT


def test_base_system_prompt_names_all_four_tools():
    """D-09: preference-ordered graph names all 4 tools."""
    from agent.agent import _BASE_SYSTEM_PROMPT

    for tool_name in ("get_hardship_flag", "detect_bill_shock", "get_billing_history", "simulate_savings"):
        assert tool_name in _BASE_SYSTEM_PROMPT, (
            f"D-09: tool '{tool_name}' missing from preference-ordered graph."
        )


def test_base_system_prompt_always_finishes_with_simulate_savings():
    """REC-03: prompt explicitly instructs the agent to finish with simulate_savings."""
    from agent.agent import _BASE_SYSTEM_PROMPT

    # Accept either of the two canonical phrasings from the plan.
    assert (
        "ALWAYS call LAST" in _BASE_SYSTEM_PROMPT
        or "always finish with `simulate_savings`" in _BASE_SYSTEM_PROMPT
        or "ALWAYS finish with `simulate_savings`" in _BASE_SYSTEM_PROMPT
    ), (
        "REC-03: prompt must explicitly require the agent to finish every turn "
        "with simulate_savings (otherwise single-track responses become possible)."
    )


def test_base_system_prompt_rejects_flow_intent():
    """Area-1 decision: ?flow=... URL intent is explicitly rejected in the prompt."""
    from agent.agent import _BASE_SYSTEM_PROMPT

    assert "?flow=" in _BASE_SYSTEM_PROMPT, (
        "Area-1: LLM-decides is load-bearing — prompt must explicitly reject "
        "?flow=... URL hints so any future UI contract does not silently change "
        "agent behaviour."
    )


def test_base_system_prompt_retains_verbatim_rules_2_through_7():
    """D-23 VERBATIM-copy discipline: rules 2-7 of the existing prompt preserved.

    Snapshot tests the key numeric-integrity invariants as fragments — the exact
    byte-for-byte wording of rules 2-7 MUST survive the Plan 03 edit (D-23).
    """
    from agent.agent import _BASE_SYSTEM_PROMPT

    # Rule 2: VERBATIM copy of plan_id / plan_name / saving_monthly / saving_annual
    assert "VERBATIM" in _BASE_SYSTEM_PROMPT
    assert "`plan_id`, `plan_name`, `saving_monthly`, and `saving_annual`" in _BASE_SYSTEM_PROMPT
    # Rule 3: BOTH tracks
    assert "BOTH the GREEN and CHEAPEST tracks" in _BASE_SYSTEM_PROMPT
    # Rule 4: never rank
    assert "Never say one track is" in _BASE_SYSTEM_PROMPT
    # Rule 5: never only one
    assert "Never return only one track." in _BASE_SYSTEM_PROMPT
    # Rule 6: never arithmetic yourself
    assert "Never perform arithmetic yourself" in _BASE_SYSTEM_PROMPT
    # Rule 7: byte-exact saving_monthly / saving_annual
    assert "equal the tool output exactly" in _BASE_SYSTEM_PROMPT


def test_base_system_prompt_mentions_sav_03():
    """SAV-03 labelling is retained for traceability in the prompt."""
    from agent.agent import _BASE_SYSTEM_PROMPT

    assert "SAV-03" in _BASE_SYSTEM_PROMPT


def test_system_prompt_composition_unchanged():
    """D-25: composition is SYSTEM_PROMPT = _BASE + '\\n\\n' + NARRATIVE_PROMPT."""
    from agent.agent import _BASE_SYSTEM_PROMPT, SYSTEM_PROMPT
    from agent.narrative.prompt_loader import NARRATIVE_PROMPT

    assert SYSTEM_PROMPT == _BASE_SYSTEM_PROMPT + "\n\n" + NARRATIVE_PROMPT
