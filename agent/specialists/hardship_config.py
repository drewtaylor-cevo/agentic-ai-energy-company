"""Hardship category configuration registry.

Single source of truth for all category-specific behaviour: routing targets,
permitted tool sets, permitted actions, and compliance flags.

Bi-mode import: this module lives at agent/specialists/hardship_config.py.
In the container layout it's importable as `specialists.hardship_config`;
in the repo layout as `agent.specialists.hardship_config`. Since this module
has no internal cross-package imports, placement alone satisfies bi-mode —
consumers use the try/except pattern (see agent/specialists/hardship.py).
"""
from __future__ import annotations

from typing import Literal

# ---------------------------------------------------------------------------
# Category type
# ---------------------------------------------------------------------------

HardshipCategory = Literal[
    "payment_difficulty",
    "medical_equipment",
    "family_violence",
    "other",
]

# ---------------------------------------------------------------------------
# Category configuration registry
# ---------------------------------------------------------------------------

HARDSHIP_CATEGORIES: dict[HardshipCategory, dict] = {
    "payment_difficulty": {
        "routing_target": "hardship_team",
        "permitted_tools": frozenset({"propose_payment_plan", "get_billing_history", "schedule_callback"}),
        "permitted_actions": ["payment_plan", "billing_history", "schedule_callback"],
        "financial_terms_forbidden": False,
    },
    "medical_equipment": {
        "routing_target": "priority_services_team",
        "permitted_tools": frozenset({"schedule_callback", "lookup_concessions"}),
        "permitted_actions": ["concession_lookup", "schedule_callback"],
        "financial_terms_forbidden": False,
    },
    "family_violence": {
        "routing_target": "family_violence_team",
        "permitted_tools": frozenset({"schedule_callback"}),
        "permitted_actions": ["schedule_callback"],
        "financial_terms_forbidden": True,
    },
    "other": {
        "routing_target": "hardship_team",
        "permitted_tools": frozenset({"schedule_callback"}),
        "permitted_actions": ["schedule_callback"],
        "financial_terms_forbidden": False,
    },
}

# ---------------------------------------------------------------------------
# Financial terminology forbidden in family_violence responses (CP-3)
# ---------------------------------------------------------------------------

FINANCIAL_TERMS: frozenset[str] = frozenset({
    "dollar",
    "payment",
    "bill",
    "tariff",
    "plan",
    "cost",
    "price",
    "save",
    "switch",
    "account",
    "balance",
    "debt",
    "arrears",
    "overdue",
})
