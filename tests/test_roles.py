"""Unit tests for agent/roles.py — AgentRole Protocol and Pydantic schemas.

Validates:
  - AgentRole is @runtime_checkable (isinstance works on conforming classes)
  - AgentRole has handle method
  - ComplianceCheckResult schema has required fields (rule, verdict, reason)
  - ComplianceReview schema has required fields (verdict, rules_checked, failures, reviewed_at)
  - SupervisorTrace schema has required fields (routed_to, routing_reason, hardship_checked, compliance_reviewed)
"""
from typing import Any

from agent.roles import (
    AgentRole,
    ComplianceCheckResult,
    ComplianceReview,
    SupervisorTrace,
)


# --- AgentRole Protocol tests (Req 5.1, 5.2) ---


class _ConformingAgent:
    """Minimal class that satisfies AgentRole Protocol."""

    def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}


class _NonConformingAgent:
    """Class that does NOT satisfy AgentRole Protocol (no handle method)."""

    def process(self, payload: dict) -> dict:
        return {}


def test_agent_role_is_runtime_checkable():
    """AgentRole is @runtime_checkable — isinstance works on conforming classes."""
    agent = _ConformingAgent()
    assert isinstance(agent, AgentRole)


def test_agent_role_rejects_non_conforming():
    """isinstance returns False for classes without handle()."""
    agent = _NonConformingAgent()
    assert not isinstance(agent, AgentRole)


def test_agent_role_has_handle_method():
    """AgentRole Protocol defines a handle method."""
    assert hasattr(AgentRole, "handle")


# --- ComplianceCheckResult schema tests (Req 4.4) ---


def test_compliance_check_result_required_fields():
    """ComplianceCheckResult has rule, verdict, reason fields."""
    result = ComplianceCheckResult(
        rule="reference_period_disclosure",
        verdict="pass",
        reason="reasoning_trace contains simulate_savings entry",
    )
    assert result.rule == "reference_period_disclosure"
    assert result.verdict == "pass"
    assert result.reason == "reasoning_trace contains simulate_savings entry"


def test_compliance_check_result_field_names():
    """ComplianceCheckResult model_fields contains exactly the expected keys."""
    expected_fields = {"rule", "verdict", "reason"}
    assert set(ComplianceCheckResult.model_fields.keys()) == expected_fields


# --- ComplianceReview schema tests (Req 8.4) ---


def test_compliance_review_required_fields():
    """ComplianceReview has verdict, rules_checked, failures, reviewed_at fields."""
    review = ComplianceReview(
        verdict="pass",
        rules_checked=["reference_period_disclosure", "no_upsell_to_disadvantage"],
        failures=[],
        reviewed_at="2025-01-15T10:30:00+00:00",
    )
    assert review.verdict == "pass"
    assert review.rules_checked == [
        "reference_period_disclosure",
        "no_upsell_to_disadvantage",
    ]
    assert review.failures == []
    assert review.reviewed_at == "2025-01-15T10:30:00+00:00"


def test_compliance_review_field_names():
    """ComplianceReview model_fields contains exactly the expected keys."""
    expected_fields = {"verdict", "rules_checked", "failures", "reviewed_at"}
    assert set(ComplianceReview.model_fields.keys()) == expected_fields


def test_compliance_review_with_failures():
    """ComplianceReview correctly stores failure reasons."""
    review = ComplianceReview(
        verdict="fail",
        rules_checked=["no_upsell_to_disadvantage"],
        failures=["green track saving_monthly is negative (-5.00)"],
        reviewed_at="2025-01-15T10:30:00+00:00",
    )
    assert review.verdict == "fail"
    assert len(review.failures) == 1


# --- SupervisorTrace schema tests (Req 9.2) ---


def test_supervisor_trace_required_fields():
    """SupervisorTrace has routed_to, routing_reason, hardship_checked, compliance_reviewed."""
    trace = SupervisorTrace(
        routed_to="TariffSpecialist",
        routing_reason="Standard recommendation request",
        hardship_checked=True,
        compliance_reviewed=True,
    )
    assert trace.routed_to == "TariffSpecialist"
    assert trace.routing_reason == "Standard recommendation request"
    assert trace.hardship_checked is True
    assert trace.compliance_reviewed is True


def test_supervisor_trace_field_names():
    """SupervisorTrace model_fields contains exactly the expected keys."""
    expected_fields = {
        "routed_to",
        "routing_reason",
        "hardship_checked",
        "compliance_reviewed",
    }
    assert set(SupervisorTrace.model_fields.keys()) == expected_fields
