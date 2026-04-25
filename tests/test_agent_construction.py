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
