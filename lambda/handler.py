"""Tariff tools Lambda — get_billing_history and simulate_savings.

Two entry points exposed to Phase 2 agent tools:
  - get_billing_history(event, context): DynamoDB read for a customer_id
  - simulate_savings(event, context):   deterministic savings arithmetic

Both wrap pure helpers (`_query_billing`, `simulate_savings_pure`) so unit
tests can exercise logic without AWS credentials.
"""
import json
import os
import re
from typing import Any, Dict, List

# --- Module-level init (cold start) ---

# Load tariff catalog from the bundled JSON. In Lambda runtime /var/task is the
# cwd and tariff_plans.json sits at the root of the asset zip. For local tests,
# cwd varies, so use a path relative to this file as a fallback.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    with open("tariff_plans.json") as _f:
        TARIFF_PLANS: List[Dict[str, Any]] = json.load(_f)
except FileNotFoundError:
    with open(os.path.join(_THIS_DIR, "tariff_plans.json")) as _f:
        TARIFF_PLANS = json.load(_f)

# DynamoDB table handle — only initialised when TABLE_NAME is present so the
# module can be imported by unit tests running without AWS creds.
table = None
if os.environ.get("TABLE_NAME"):
    import boto3  # imported lazily so pure-function tests do not require boto3
    _dynamodb = boto3.resource("dynamodb")
    table = _dynamodb.Table(os.environ["TABLE_NAME"])


# --- Input validation ---

_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")


def _validate_customer_id(customer_id: Any) -> str:
    """Raise ValueError on invalid customer_id; returns normalised string.

    STRIDE: V5 Input Validation — rejects injection attempts, empty strings,
    and non-string types before any DynamoDB query is issued.
    """
    if not isinstance(customer_id, str):
        raise ValueError(f"customer_id must be a string, got {type(customer_id).__name__}")
    if not _CUSTOMER_ID_PATTERN.match(customer_id):
        raise ValueError(f"customer_id must match CUST-<digits>; got {customer_id!r}")
    return customer_id


# --- Pure savings arithmetic (testable offline) ---

DAYS_PER_MONTH = 30.44  # 365.25/12; used to annualise daily supply charges


def simulate_savings_pure(
    billing_history: List[Dict[str, Any]],
    plans: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Deterministic savings calculator — SAV-03 compliant (no LLM arithmetic).

    Algorithm:
      avg_kwh = mean(record["usage_kwh"])
      current_plan = plan where plan_id == billing_history[0]["plan_id"]
      projected_cost(plan) = avg_kwh * plan.rate_per_kwh + plan.daily_supply_charge * 30.44
      saving(plan) = projected_cost(current_plan) - projected_cost(plan)
      green_plan   = argmax(green_score) over plans where plan_type == "green_premium"
                                                        and plan_id != current_plan_id
      cheapest_plan = argmin(projected_cost) over all plans with plan_id != current_plan_id
    """
    if not billing_history:
        raise ValueError("billing_history must not be empty")
    if not plans:
        raise ValueError("plans must not be empty")

    avg_kwh = sum(float(r["usage_kwh"]) for r in billing_history) / len(billing_history)
    current_plan_id = billing_history[0]["plan_id"]
    current_plan = next((p for p in plans if p["plan_id"] == current_plan_id), None)
    if current_plan is None:
        raise ValueError(f"current plan {current_plan_id!r} not in catalog")

    def projected_monthly_cost(plan: Dict[str, Any]) -> float:
        plan_type = plan.get("plan_type", "flat_rate")
        supply = float(plan["daily_supply_charge"]) * DAYS_PER_MONTH

        if plan_type == "time_of_use":
            # D-05/D-12: EV-TOU math. Default 100% peak if records lack peak/offpeak fields.
            peak_kwh_avg = sum(float(r.get("peak_kwh", r.get("usage_kwh", 0))) for r in billing_history) / len(billing_history)
            offpeak_kwh_avg = sum(float(r.get("offpeak_kwh", 0)) for r in billing_history) / len(billing_history)
            peak_rate = float(plan.get("peak_rate", plan["rate_per_kwh"]))
            offpeak_rate = float(plan.get("offpeak_rate", plan["rate_per_kwh"]))
            return peak_kwh_avg * peak_rate + offpeak_kwh_avg * offpeak_rate + supply

        if plan_type == "solar_fit":
            # D-04/D-12: SOL math. The SOL tariff bills gross consumption at rate_per_kwh
            # and separately credits exported kWh at fit_rate. This matches the solver's
            # convention (scratch/target_equation_solver_v2.py projected_sol where the
            # first argument is gross usage). The `net_kwh` field on records is informational
            # (grid-import after export offset) and is NOT used here. Default export=0 if
            # records lack export_kwh (v2.0 persona fallback).
            gross_kwh_avg = avg_kwh  # already computed above from usage_kwh
            export_kwh_avg = sum(float(r.get("export_kwh", 0)) for r in billing_history) / len(billing_history)
            sol_rate = float(plan["rate_per_kwh"])
            fit_rate = float(plan.get("fit_rate", 0))
            return gross_kwh_avg * sol_rate - export_kwh_avg * fit_rate + supply

        # Default: flat_rate / green_premium — BYTE-EXACT preservation of v2.0 formula
        return avg_kwh * float(plan["rate_per_kwh"]) + supply

    current_cost = projected_monthly_cost(current_plan)
    candidates = [p for p in plans if p["plan_id"] != current_plan_id]

    green_candidates = [p for p in candidates if p.get("plan_type") == "green_premium"]
    if not green_candidates:
        raise ValueError("No green_premium plan in catalog — demo cannot surface Green track")
    green_plan = max(green_candidates, key=lambda p: p["green_score"])

    cheapest_plan = min(candidates, key=projected_monthly_cost)

    green_saving = round(current_cost - projected_monthly_cost(green_plan), 2)
    cheapest_saving = round(current_cost - projected_monthly_cost(cheapest_plan), 2)

    return {
        "green": {
            "plan_id": green_plan["plan_id"],
            "plan_name": green_plan["plan_name"],
            "saving_monthly": green_saving,
            "saving_annual": round(green_saving * 12, 2),
        },
        "cheapest": {
            "plan_id": cheapest_plan["plan_id"],
            "plan_name": cheapest_plan["plan_name"],
            "saving_monthly": cheapest_saving,
            "saving_annual": round(cheapest_saving * 12, 2),
        },
    }


def get_hardship_flag_pure(customer_id: str, table_client) -> Dict[str, Any]:
    """D-10 pure helper — injectable table_client (mirror of simulate_savings_pure shape).

    Returns {hardship: bool, customer_id: str}. Missing PROFILE row returns hardship=False
    (m3 mitigation — hardship default False for existing personas).

    STRIDE: V5 Input Validation — _validate_customer_id gates entry before any DynamoDB call.
    """
    _validate_customer_id(customer_id)
    response = table_client.get_item(
        Key={"customer_id": customer_id, "month": "PROFILE"}
    )
    item = response.get("Item")
    if item is None:
        return {"hardship": False, "customer_id": customer_id}
    return {
        "hardship": bool(item.get("hardship_flag", False)),
        "customer_id": customer_id,
    }


# --- Lambda handler entry points ---

def get_billing_history(event: Dict[str, Any], context) -> List[Dict[str, Any]]:
    """Return 12 months of billing for a customer, sorted by month ASC.

    Raises ValueError on malformed customer_id (V5 input validation).
    Raises RuntimeError if TABLE_NAME env var is not set (fail-fast).
    """
    customer_id = _validate_customer_id(event.get("customer_id"))
    if table is None:
        raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")
    response = table.query(
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": customer_id},
    )
    items = response.get("Items", [])
    # Phase 11 D-21: filter sentinel PROFILE row so simulate_savings_pure sees only month rows
    items = [i for i in items if i["month"] != "PROFILE"]
    return sorted(items, key=lambda x: x["month"])


def simulate_savings(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Lambda wrapper: fetch billing, compute savings, return tracks."""
    billing = get_billing_history(event, context)
    if not billing:
        raise ValueError(f"No billing history for {event.get('customer_id')!r}")
    return simulate_savings_pure(billing, TARIFF_PLANS)
