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


def summary_check_outage_status(result: dict) -> str:
    """Format the output of lambda.handler.check_outage_status_pure."""
    if result.get("has_outage"):
        outage_type = result.get("outage_type", "unknown").capitalize()
        suburb = result.get("suburb", "unknown")
        customers = result.get("customers_affected", 0)
        restoration = result.get("estimated_restoration")
        restoration_str = f", restoration {restoration}" if restoration else ""
        return (
            f"{outage_type} outage in {suburb}: "
            f"~{customers} customers{restoration_str}"
        )
    suburb = result.get("suburb", "unknown")
    return f"No outage in {suburb}"


def summary_decompose_bill_shock(result: dict) -> str:
    """Format the output of lambda.handler.decompose_bill_shock_pure."""
    if not result.get("is_shock"):
        return "No bill shock: monthly usage within envelope"

    # Prefer the code-composed explanation_sentence (v2 enriched output)
    explanation = result.get("explanation_sentence")
    if explanation:
        month = result.get("shock_month", "unknown")
        return f"Bill shock ({month}): {explanation}"

    # Fallback to legacy component fields for backward compat
    total = result.get("total_delta_dollars", 0.0)
    month = result.get("shock_month", "unknown")
    rate = result.get("rate_change_component", 0.0)
    usage = result.get("usage_change_component", 0.0)
    seasonal = result.get("seasonal_component", 0.0)
    return (
        f"Bill shock +${total:.2f} ({month}): "
        f"rate +${rate:.2f}, usage +${usage:.2f}, seasonal +${seasonal:.2f}"
    )


def summary_lookup_concessions(result: dict) -> str:
    """Format the output of lambda.handler.lookup_concessions_pure."""
    concessions = result.get("eligible_concessions", []) or []
    total_value = result.get("total_annual_value", 0.0)
    count = len(concessions)
    not_applied = sum(1 for c in concessions if not c.get("applied"))
    suffix = f" ({not_applied} not yet applied)" if not_applied else ""
    return f"{count} concessions eligible, ${total_value:.2f}/yr total{suffix}"


def summary_estimate_solar_payback(result: dict) -> str:
    """Format the output of lambda.handler.estimate_solar_payback_pure."""
    if not result.get("eligible"):
        reason = result.get("reason", "ineligible")
        return f"Solar: ineligible ({reason})"
    system_size = result.get("estimated_system_size_kw", 0.0)
    annual_savings = result.get("annual_savings_dollars", 0.0)
    payback = result.get("payback_years", 0.0)
    recommendation = result.get("recommendation", "unknown")
    return (
        f"Solar: {system_size}kW system, "
        f"${annual_savings:,.2f}/yr savings, "
        f"{payback}yr payback ({recommendation})"
    )


def summary_propose_payment_plan(result: dict) -> str:
    """Format the output of lambda.handler.propose_payment_plan_pure."""
    balance = result.get("outstanding_balance", 0.0)
    count = result.get("instalment_count", 0)
    amount = result.get("instalment_amount", 0.0)
    interest_free = result.get("interest_free", False)
    interest_str = "interest-free" if interest_free else "with interest"
    return (
        f"Payment plan: ${balance:.2f} over {count} instalments "
        f"(${amount:.2f}/mo), {interest_str}"
    )


def summary_schedule_callback(result: dict) -> str:
    """Format the output of lambda.handler.schedule_callback_pure."""
    scheduled_time = result.get("scheduled_time", "unknown")
    reason = result.get("reason", "general")
    return f"Callback confirmed: {scheduled_time} ({reason})"
