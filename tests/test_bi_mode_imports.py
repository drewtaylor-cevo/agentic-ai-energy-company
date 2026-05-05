"""Smoke tests for bi-mode imports of roles and specialists modules.

Verifies that all new modules introduced by the multi-agent supervisor
refactor can be imported in the repo layout (agent.X) and that the
expected classes/protocols are available and are the correct types.
"""
from __future__ import annotations

import typing

from agent.roles import (
    AgentRole,
    ComplianceCheckResult,
    ComplianceReview,
    SupervisorTrace,
)
from agent.specialists.compliance import ComplianceReviewer
from agent.specialists.hardship import HardshipSpecialist
from agent.specialists.tariff import TariffSpecialist


# --- roles.py imports ---


class TestRolesImport:
    """Verify agent.roles exports are importable and well-typed."""

    def test_agent_role_is_protocol(self) -> None:
        assert typing.runtime_checkable  # guard — runtime_checkable exists
        assert isinstance(AgentRole, type)
        # Protocol classes have _is_protocol attribute
        assert getattr(AgentRole, "_is_protocol", False)

    def test_compliance_check_result_is_pydantic_model(self) -> None:
        assert hasattr(ComplianceCheckResult, "model_fields")

    def test_compliance_review_is_pydantic_model(self) -> None:
        assert hasattr(ComplianceReview, "model_fields")

    def test_supervisor_trace_is_pydantic_model(self) -> None:
        assert hasattr(SupervisorTrace, "model_fields")


# --- specialists imports ---


class TestSpecialistsImport:
    """Verify specialist classes are importable and are concrete classes."""

    def test_hardship_specialist_importable(self) -> None:
        assert isinstance(HardshipSpecialist, type)

    def test_tariff_specialist_importable(self) -> None:
        assert isinstance(TariffSpecialist, type)

    def test_compliance_reviewer_importable(self) -> None:
        assert isinstance(ComplianceReviewer, type)

    def test_specialists_satisfy_agent_role(self) -> None:
        """All three specialists have a handle() method (AgentRole Protocol)."""
        for cls in (HardshipSpecialist, TariffSpecialist, ComplianceReviewer):
            assert hasattr(cls, "handle"), f"{cls.__name__} missing handle()"


# --- specialists __init__.py re-exports ---


class TestSpecialistsPackageReExports:
    """Verify agent.specialists.__init__ re-exports all three classes."""

    def test_package_reexports(self) -> None:
        from agent.specialists import (
            ComplianceReviewer as CR,
            HardshipSpecialist as HS,
            TariffSpecialist as TS,
        )

        assert CR is ComplianceReviewer
        assert HS is HardshipSpecialist
        assert TS is TariffSpecialist
