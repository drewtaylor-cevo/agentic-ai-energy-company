"""Specialist agents for the multi-agent supervisor pattern.

Bi-mode import support: in the AgentCore container, /app/specialists/ is a
top-level package (Dockerfile COPYs it there). In the repo / offline tests,
`agent/specialists/` is a subpackage of the `agent` namespace package.

Usage (bi-mode):
    try:
        from specialists.hardship import HardshipSpecialist
        from specialists.tariff import TariffSpecialist
    except ImportError:
        from agent.specialists.hardship import HardshipSpecialist
        from agent.specialists.tariff import TariffSpecialist
"""

# Re-export specialist classes for convenience.
# Bi-mode: try container layout first, fall back to repo layout.
try:
    from specialists.hardship import HardshipSpecialist  # type: ignore[import-not-found]
except ImportError:
    from agent.specialists.hardship import HardshipSpecialist

try:
    from specialists.tariff import TariffSpecialist  # type: ignore[import-not-found]
except ImportError:
    from agent.specialists.tariff import TariffSpecialist

try:
    from specialists.compliance import ComplianceReviewer  # type: ignore[import-not-found]
except ImportError:
    from agent.specialists.compliance import ComplianceReviewer

__all__ = [
    "ComplianceReviewer",
    "HardshipSpecialist",
    "TariffSpecialist",
]
