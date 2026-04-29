"""Deterministic tool-result summary formatters — D-10 SAV-03 by construction.

These read the dict payload returned by each of the four tools and produce a
code-composed one-liner string for the `reasoning_trace` surface. NO LLM is
involved in composition; no arithmetic, no estimation, no rounding beyond
`f'{x:.2f}'` format-spec rounding.

D-11 exemption: these strings INTENTIONALLY contain digits, currency ($),
percentages (%), and dates. They are consumed by ReasoningTraceEntry.summary
which has NO narrative validators applied. Applying the Phase 6 narrative
banned-terms filter to ReasoningTraceEntry.summary is a silent regression —
see CLAUDE.md addendum.
"""
from typing import Any


def summary_detect_bill_shock(result: dict) -> str:
    """Format the output of lambda.handler.detect_bill_shock_pure."""
    if result.get("is_shock"):
        return (
            f"Bill shock detected: +${result['delta_dollars']:.2f} "
            f"{result['shock_month']} vs 11-month avg "
            f"(${result['current_dollars']:.2f} vs ${result['mean_dollars']:.2f})"
        )
    return "No bill shock: monthly usage within 11-month envelope"


def summary_get_billing_history(result: Any) -> str:
    """Format the output of lambda.handler.get_billing_history.

    Accepts either a bare list (Phase 11 shape) or a dict carrying a `billing`
    key (defensive — future-proof against dispatcher refactor).
    """
    if isinstance(result, list):
        return f"{len(result)} months retrieved"
    if isinstance(result, dict):
        billing = result.get("billing") or result.get("billing_history") or []
        if isinstance(billing, list):
            return f"{len(billing)} months retrieved"
    return "billing history retrieved"


def summary_get_hardship_flag(result: dict) -> str:
    """Format the output of lambda.handler.get_hardship_flag_pure.

    Phase 11 helper returns {"hardship": bool, "customer_id": str}.
    Phase 13 wrapper may also return {"hardship_flag": bool}; handle both.
    """
    flag = result.get("hardship_flag")
    if flag is None:
        flag = result.get("hardship", False)
    return f"hardship_flag={bool(flag)}"


def summary_simulate_savings(result: dict) -> str:
    """Format the output of lambda.handler.simulate_savings / simulate_savings_pure."""
    green = result.get("green", {}) or {}
    cheapest = result.get("cheapest", {}) or {}
    return (
        f"Green ${float(green.get('saving_monthly', 0)):.2f}/mo; "
        f"Cheapest ${float(cheapest.get('saving_monthly', 0)):.2f}/mo"
    )
