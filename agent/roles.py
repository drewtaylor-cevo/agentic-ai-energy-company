"""AgentRole Protocol and compliance/supervisor Pydantic schemas.

Follows the Phase 12 CustomerDataProvider pattern from agent/providers.py:
  - @runtime_checkable Protocol with a single entry-point method
  - Pydantic models for public response fields
  - Bi-mode import support (container /app/ vs repo agent/)

New models:
  - ComplianceCheckResult: single rule check (rule, verdict, reason)
  - ComplianceReview: full compliance verdict (public response field)
  - SupervisorTrace: routing decision (public response field)
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


# --- AgentRole Protocol (Req 5.1, 5.2) ---


@runtime_checkable
class AgentRole(Protocol):
    """Minimum interface for specialist agents — Phase 12 CustomerDataProvider pattern.

    Each specialist (TariffSpecialist, HardshipSpecialist, ComplianceReviewer)
    implements handle() as its single entry point. The Supervisor dispatches
    to handle() and collects the response dict.
    """

    def handle(self, payload: dict[str, Any]) -> dict[str, Any]: ...


# --- Compliance Schemas (Req 4.4, 8.4) ---


class ComplianceCheckResult(BaseModel):
    """Single rule check result — used internally by ComplianceReviewer."""

    rule: str = Field(description="Rule name (e.g. 'reference_period_disclosure')")
    verdict: str = Field(description="'pass' or 'fail'")
    reason: str = Field(description="Explanation of the verdict")


class ComplianceReview(BaseModel):
    """Public response field — the ComplianceReviewer's full verdict.

    Attached to every outbound response as ``compliance_review``.
    NOT stripped by api_lambda/handler.py — part of the demo trust story.
    """

    verdict: str = Field(description="Overall 'pass' or 'fail'")
    rules_checked: list[str] = Field(description="List of rule names checked")
    failures: list[str] = Field(
        description="List of failure reasons (empty on pass)"
    )
    reviewed_at: str = Field(description="ISO 8601 timestamp")


# --- Supervisor Trace Schema (Req 9.2) ---


class SupervisorTrace(BaseModel):
    """Public response field — the Supervisor's routing decision.

    Attached to every outbound response as ``supervisor_trace``.
    Collapses (omitted) when ``?narrative=off`` is active (DEMO-07).
    """

    routed_to: str = Field(
        description="Specialist name (e.g. 'TariffSpecialist')"
    )
    routing_reason: str = Field(
        description="Brief explanation of routing decision"
    )
    hardship_checked: bool = Field(
        description="Whether hardship flag was checked"
    )
    compliance_reviewed: bool = Field(
        description="Whether ComplianceReviewer ran"
    )
