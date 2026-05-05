"""HardshipSpecialist — hardship routing specialist.

Extracted from the pre-LLM hardship guard in agent/agent.py::invoke().
Code-side only — no LLM turn, no Agent instance, no tariff tools.

The specialist calls _build_typed_hardship_response(customer_id, category, config)
to produce a typed HardshipResponse dict and attaches _narrative_source with
hardship reason/call_script fallback markers and category info.

Satisfies the AgentRole Protocol (handle(payload) -> dict).

Bi-mode import: try container /app/ layout first, fall back to repo layout.
"""
from __future__ import annotations

from typing import Any

# Bi-mode import: _build_typed_hardship_response and HARDSHIP_CATEGORIES
# live in agent.py and hardship_config.py respectively.
# In the container, agent.py is at /app/agent.py (top-level module `agent`).
# In the repo, it's `agent.agent`. Try container layout first.
try:
    from agent import _build_typed_hardship_response  # type: ignore[import-not-found]
except ImportError:
    from agent.agent import _build_typed_hardship_response

try:
    from specialists.hardship_config import HARDSHIP_CATEGORIES  # type: ignore[import-not-found]
except ImportError:
    from agent.specialists.hardship_config import HARDSHIP_CATEGORIES


class HardshipSpecialist:
    """Hardship routing specialist — no tariff tools, no LLM turn.

    Produces a typed HardshipResponse dict for hardship-flagged customers.
    The LLM never sees tariff context for these customers — code-side
    enforcement, not prompt-side.
    """

    def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Build a typed HardshipResponse for a hardship-flagged customer.

        Reads hardship_category from payload, defaults to "other" if missing,
        None, or unrecognised. D-04: wrapped in try/except — any failure in
        category extraction falls back to "other".

        Code-side only — the LLM never sees tariff context.
        """
        customer_id = payload["customer_id"]

        # D-04 preservation: wrap category extraction in try/except.
        # Any failure defaults to "other" — never raises.
        try:
            raw_category = payload.get("hardship_category")
            if raw_category and raw_category in HARDSHIP_CATEGORIES:
                category = raw_category
            else:
                category = "other"
        except Exception:  # noqa: BLE001 — D-04 never-500
            category = "other"

        config = HARDSHIP_CATEGORIES[category]
        body = _build_typed_hardship_response(customer_id, category, config)
        body["_narrative_source"] = {
            "hardship": {"reason": "fallback", "call_script": "fallback", "category": category},
        }
        return body
