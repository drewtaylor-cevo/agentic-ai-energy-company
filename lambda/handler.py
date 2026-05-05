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
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

# --- Seed data imports (bi-mode: Lambda runtime vs repo layout for tests) ---
try:
    from tool_seed_data import (
        OUTAGE_DATA, CONCESSION_DATA, BALANCE_DATA,
        SUBURB_MAP, SOLAR_CONSTANTS, SOLAR_CUSTOMERS,
    )
except ImportError:
    from infrastructure.seed_data.tool_seed_data import (
        OUTAGE_DATA, CONCESSION_DATA, BALANCE_DATA,
        SUBURB_MAP, SOLAR_CONSTANTS, SOLAR_CUSTOMERS,
    )


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


def detect_bill_shock_pure(
    billing_history: List[Dict[str, Any]],
    *,
    threshold: float = 0.30,  # D-03 symmetric gate on 11-month mean
    rate_per_kwh: float = 0.32,   # STD plan rate (matches seed_data STD_RATE)
    daily_supply: float = 1.10,   # STD plan daily supply
) -> Dict[str, Any]:
    """Detect bill-shock anomaly on projected STD cost (SAV-03 compliant — pure Python).

    Algorithm (D-03 symmetric, per-month scan per RESEARCH §6):
      1. Sort billing_history ASC by month (defensive — dispatcher already sorts).
      2. For EACH month, compute the self-excluded 11-month reference mean of
         projected STD costs = usage_kwh * rate + supply_month.
      3. Identify the month with the MAX abs-delta ratio vs its reference mean
         (the "peak shock candidate"). `shock_month` is that month's key.
      4. 'is_shock' = peak ratio > threshold (bool).

    This per-month scan is the semantics pinned by RESEARCH §6 (Elena's peak
    shock is 2025-10 at 0.6344; Marcus's peak is 2025-10 at 0.167 — neither
    month is the chronologically-last record). The CONTEXT.md A-01 amendment
    + Plan 01 TestDetectBillShockPure.test_elena_trips_shock_gate assert
    shock_month == "2025-10", requiring this peak-scan semantics rather than
    a "most-recent-month only" check.

    Per D-11: summary strings consuming this output intentionally contain digits,
    currency, and dates — do NOT apply narrative validators downstream.

    Raises:
        ValueError: if billing_history has < 2 months (can't compute reference mean).
    """
    if len(billing_history) < 2:
        raise ValueError("billing_history must have >= 2 months for anomaly detection")

    SUPPLY_MONTH = daily_supply * DAYS_PER_MONTH
    ordered = sorted(billing_history, key=lambda r: r["month"])
    costs = [float(r["usage_kwh"]) * rate_per_kwh + SUPPLY_MONTH for r in ordered]
    total_cost = sum(costs)
    n = len(costs)

    # Per-month scan: for each index i, reference_mean_i is the mean of the
    # OTHER (n-1) months' projected costs (self-excluded). Find the month with
    # the maximum |delta_i| / reference_mean_i ratio — that is the shock candidate.
    best_idx = 0
    best_ratio = -1.0
    best_delta = 0.0
    best_mean = 0.0
    for i, cost_i in enumerate(costs):
        reference_mean_i = (total_cost - cost_i) / (n - 1)
        delta_i = cost_i - reference_mean_i
        ratio_i = abs(delta_i) / reference_mean_i
        if ratio_i > best_ratio:
            best_ratio = ratio_i
            best_idx = i
            best_delta = delta_i
            best_mean = reference_mean_i

    peak_cost = costs[best_idx]
    is_shock = best_ratio > threshold

    return {
        "is_shock": is_shock,
        "delta_dollars": round(best_delta, 2),
        "shock_month": ordered[best_idx]["month"],
        "mean_dollars": round(best_mean, 2),
        "current_dollars": round(peak_cost, 2),
    }


def get_hardship_flag_pure(customer_id: str, table_client) -> Dict[str, Any]:
    """D-10 pure helper — injectable table_client (mirror of simulate_savings_pure shape).

    Returns {hardship: bool, hardship_category: str | None, customer_id: str}.
    Missing PROFILE row returns hardship=False, hardship_category=None
    (m3 mitigation — hardship default False for existing personas).

    STRIDE: V5 Input Validation — _validate_customer_id gates entry before any DynamoDB call.
    """
    _validate_customer_id(customer_id)
    response = table_client.get_item(
        Key={"customer_id": customer_id, "month": "PROFILE"}
    )
    item = response.get("Item")
    if item is None:
        return {"hardship": False, "hardship_category": None, "customer_id": customer_id}
    return {
        "hardship": bool(item.get("hardship_flag", False)),
        "hardship_category": item.get("hardship_category"),  # None if absent
        "customer_id": customer_id,
    }


# --- Expanded Tool Gallery: Pure Functions (Task 2) ---


def check_outage_status_pure(suburb: str) -> Dict[str, Any]:
    """Check current outage status for a suburb (deterministic, seed-data-backed).

    Validates suburb is a non-empty string. Looks up suburb in OUTAGE_DATA
    (case-sensitive). Returns no-outage default if suburb not found.

    Raises:
        ValueError: if suburb is not a non-empty string.
    """
    if not isinstance(suburb, str) or not suburb.strip():
        raise ValueError("suburb must be a non-empty string")

    if suburb in OUTAGE_DATA:
        data = OUTAGE_DATA[suburb]
        return {
            "suburb": suburb,
            "has_outage": data["has_outage"],
            "outage_type": data["outage_type"],
            "affected_postcodes": data["affected_postcodes"],
            "estimated_restoration": data["estimated_restoration"],
            "customers_affected": data["customers_affected"],
        }

    # Suburb not in seed data — return no-outage default
    return {
        "suburb": suburb,
        "has_outage": False,
        "outage_type": "none",
        "affected_postcodes": [],
        "estimated_restoration": None,
        "customers_affected": 0,
    }


def decompose_bill_shock_pure(
    billing_history: List[Dict[str, Any]],
    *,
    threshold: float = 0.30,
    rate_per_kwh: float = 0.32,
    daily_supply: float = 1.10,
) -> Dict[str, Any]:
    """Decompose bill-shock into rate/usage/seasonal/billing-day components (SAV-03 compliant).

    Extends detect_bill_shock_pure with component attribution. Uses the same
    threshold logic to identify the shock month, then decomposes the total delta
    into four named Contributing_Factors:
      - rate_increase: 0.0 (no rate change in seed data — structure supports it)
      - usage_spike: difference in usage * rate_per_kwh
      - seasonal_variation: residual (total_delta - rate - usage - billing_day)
      - billing_day_difference: 0.0 (no billing-day variance in seed data)

    Each Contributing_Factor has {factor_name, dollar_amount, percentage_of_total}.

    The sum of all Contributing_Factor dollar_amounts MUST equal total_delta_dollars
    within $0.01.

    Also produces:
      - explanation_sentence: code-composed string (SAV-03 — never touches LLM)
      - explanation_factors: backward-compat list of non-zero factor descriptions

    Raises:
        ValueError: if billing_history has < 2 months.
    """
    if len(billing_history) < 2:
        raise ValueError("billing_history must have >= 2 months for anomaly detection")

    SUPPLY_MONTH = daily_supply * DAYS_PER_MONTH
    ordered = sorted(billing_history, key=lambda r: r["month"])
    costs = [float(r["usage_kwh"]) * rate_per_kwh + SUPPLY_MONTH for r in ordered]
    usages = [float(r["usage_kwh"]) for r in ordered]
    total_cost = sum(costs)
    n = len(costs)

    # Per-month scan (same as detect_bill_shock_pure): find the month with
    # the maximum |delta_i| / reference_mean_i ratio.
    best_idx = 0
    best_ratio = -1.0
    best_delta = 0.0
    best_mean = 0.0
    for i, cost_i in enumerate(costs):
        reference_mean_i = (total_cost - cost_i) / (n - 1)
        delta_i = cost_i - reference_mean_i
        ratio_i = abs(delta_i) / reference_mean_i
        if ratio_i > best_ratio:
            best_ratio = ratio_i
            best_idx = i
            best_delta = delta_i
            best_mean = reference_mean_i

    is_shock = best_ratio > threshold
    shock_month = ordered[best_idx]["month"]
    total_delta_dollars = round(best_delta, 2)

    # Decomposition: attribute the delta to four named components
    # Rate increase component: 0.0 (no rate change in seed data — structure supports it)
    rate_increase_amount = 0.0

    # Usage spike component: difference in usage * rate_per_kwh
    shock_usage = usages[best_idx]
    total_usage = sum(usages)
    reference_usage_mean = (total_usage - shock_usage) / (n - 1)
    usage_delta = shock_usage - reference_usage_mean
    usage_spike_amount = round(usage_delta * rate_per_kwh, 2)

    # Billing day difference component: 0.0 (no billing-day variance in seed data)
    billing_day_amount = 0.0

    # Seasonal variation component: residual to ensure sum == total_delta_dollars
    seasonal_amount = round(
        total_delta_dollars - rate_increase_amount - usage_spike_amount - billing_day_amount, 2
    )

    # Backward-compat fields (kept for existing consumers)
    rate_change_component = rate_increase_amount
    usage_change_component = usage_spike_amount
    seasonal_component = seasonal_amount

    # Build Contributing_Factors list with percentages
    abs_total = abs(total_delta_dollars) if total_delta_dollars != 0.0 else 1.0
    contributing_factors = [
        {
            "factor_name": "rate_increase",
            "dollar_amount": rate_increase_amount,
            "percentage_of_total": round((rate_increase_amount / abs_total) * 100, 1) if total_delta_dollars != 0.0 else 0.0,
        },
        {
            "factor_name": "usage_spike",
            "dollar_amount": usage_spike_amount,
            "percentage_of_total": round((usage_spike_amount / abs_total) * 100, 1) if total_delta_dollars != 0.0 else 0.0,
        },
        {
            "factor_name": "seasonal_variation",
            "dollar_amount": seasonal_amount,
            "percentage_of_total": round((seasonal_amount / abs_total) * 100, 1) if total_delta_dollars != 0.0 else 0.0,
        },
        {
            "factor_name": "billing_day_difference",
            "dollar_amount": billing_day_amount,
            "percentage_of_total": round((billing_day_amount / abs_total) * 100, 1) if total_delta_dollars != 0.0 else 0.0,
        },
    ]

    # Adjust percentages so they sum to exactly 100 when total_delta != 0
    # Assign any rounding residual to the largest non-zero factor
    if total_delta_dollars != 0.0:
        pct_sum = sum(f["percentage_of_total"] for f in contributing_factors)
        residual = round(100.0 - pct_sum, 1)
        if residual != 0.0:
            # Find the factor with the largest absolute percentage to absorb residual
            non_zero = [f for f in contributing_factors if f["dollar_amount"] != 0.0]
            if non_zero:
                largest = max(non_zero, key=lambda f: abs(f["percentage_of_total"]))
                largest["percentage_of_total"] = round(largest["percentage_of_total"] + residual, 1)

    # Build explanation_factors (backward compat — only non-zero factors)
    _FACTOR_LABELS = {
        "rate_increase": "Rate change",
        "usage_spike": "Usage change",
        "seasonal_variation": "Seasonal variation",
        "billing_day_difference": "Billing day difference",
    }
    explanation_factors = []
    for f in contributing_factors:
        if f["dollar_amount"] != 0.0:
            label = _FACTOR_LABELS[f["factor_name"]]
            explanation_factors.append(f"{label} contributed ${f['dollar_amount']:.2f}")
    if not explanation_factors:
        explanation_factors.append("No significant contributing factors identified")

    # Build explanation_sentence (SAV-03: code-composed, never touches LLM)
    _FACTOR_CAUSE_LABELS = {
        "rate_increase": "rate increase",
        "usage_spike": "usage spike",
        "seasonal_variation": "seasonal variation",
        "billing_day_difference": "billing day difference",
    }
    non_zero_factors = [f for f in contributing_factors if f["dollar_amount"] != 0.0]
    if non_zero_factors:
        parts = [
            f"{abs(f['percentage_of_total']):.0f}% from {_FACTOR_CAUSE_LABELS[f['factor_name']]}"
            for f in non_zero_factors
        ]
        explanation_sentence = f"${abs(total_delta_dollars):.2f} over baseline — {', '.join(parts)}"
    else:
        explanation_sentence = f"${abs(total_delta_dollars):.2f} over baseline — no significant factors"

    # Extract customer_id from billing history if available
    customer_id = ordered[0].get("customer_id", "unknown")

    return {
        "customer_id": customer_id,
        "is_shock": is_shock,
        "shock_month": shock_month,
        "total_delta_dollars": total_delta_dollars,
        "rate_change_component": rate_change_component,
        "usage_change_component": usage_change_component,
        "seasonal_component": seasonal_component,
        "contributing_factors": contributing_factors,
        "explanation_sentence": explanation_sentence,
        "explanation_factors": explanation_factors,
    }


def lookup_concessions_pure(customer_id: str) -> Dict[str, Any]:
    """Look up AU-specific energy concessions for a customer (deterministic).

    Validates customer_id matches ^CUST-\\d{3,6}$ pattern. Returns concession
    list and total_annual_value from seed data.

    Raises:
        ValueError: if customer_id doesn't match the expected pattern.
    """
    _validate_customer_id(customer_id)

    if customer_id in CONCESSION_DATA:
        concessions = CONCESSION_DATA[customer_id]["eligible_concessions"]
    else:
        concessions = []

    total_annual_value = sum(c["annual_value"] for c in concessions)

    return {
        "customer_id": customer_id,
        "eligible_concessions": concessions,
        "total_annual_value": total_annual_value,
    }


def estimate_solar_payback_pure(
    customer_id: str,
    billing_history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Estimate solar PV payback period for a customer (SAV-03 compliant).

    Checks solar eligibility:
      - If customer_id is in SOLAR_CUSTOMERS set → ineligible (already has solar)
      - If any billing record has export_kwh > 0 → ineligible

    For eligible customers, computes system size, generation, savings, payback,
    and recommendation based on threshold rules.

    Raises:
        ValueError: if customer_id is invalid or billing_history is empty.
    """
    _validate_customer_id(customer_id)

    if not billing_history:
        raise ValueError("billing_history must not be empty")

    # Check if customer already has solar (in SOLAR_CUSTOMERS set)
    if customer_id in SOLAR_CUSTOMERS:
        return {
            "customer_id": customer_id,
            "eligible": False,
            "reason": "Customer already has solar installed",
        }

    # Check if any record has export_kwh > 0 (indicates existing solar)
    if any(float(r.get("export_kwh", 0)) > 0 for r in billing_history):
        return {
            "customer_id": customer_id,
            "eligible": False,
            "reason": "Customer already has solar installed",
        }

    # Calculate average monthly usage
    avg_monthly_usage_kwh = sum(float(r["usage_kwh"]) for r in billing_history) / len(billing_history)

    # System sizing
    daily_gen_per_kw = SOLAR_CONSTANTS["daily_generation_per_kw"]
    estimated_system_size_kw = avg_monthly_usage_kwh / (daily_gen_per_kw * 30)

    # Daily generation
    estimated_daily_generation_kwh = estimated_system_size_kw * daily_gen_per_kw

    # Annual savings calculation
    self_consumption_ratio = SOLAR_CONSTANTS["self_consumption_ratio"]
    retail_rate = SOLAR_CONSTANTS["retail_rate"]
    feed_in_tariff = SOLAR_CONSTANTS["feed_in_tariff"]

    self_consumed = estimated_daily_generation_kwh * self_consumption_ratio * 365 * retail_rate
    exported = estimated_daily_generation_kwh * (1 - self_consumption_ratio) * 365 * feed_in_tariff
    annual_savings = self_consumed + exported

    # System cost
    cost_per_kw = SOLAR_CONSTANTS["cost_per_kw"]
    system_cost = estimated_system_size_kw * cost_per_kw

    # Payback period
    payback_years = round(system_cost / annual_savings, 1)

    # Recommendation based on payback threshold
    if payback_years <= 5.0:
        recommendation = "strong_candidate"
    elif payback_years <= 8.0:
        recommendation = "moderate_candidate"
    else:
        recommendation = "not_recommended"

    return {
        "customer_id": customer_id,
        "eligible": True,
        "avg_monthly_usage_kwh": round(avg_monthly_usage_kwh, 2),
        "estimated_system_size_kw": round(estimated_system_size_kw, 2),
        "estimated_daily_generation_kwh": round(estimated_daily_generation_kwh, 2),
        "annual_savings_dollars": round(annual_savings, 2),
        "system_cost_dollars": round(system_cost, 2),
        "payback_years": payback_years,
        "recommendation": recommendation,
    }


def propose_payment_plan_pure(
    customer_id: str,
    instalments: int,
    outstanding_balance: float,
) -> Dict[str, Any]:
    """Propose a payment plan with instalment schedule (SAV-03 compliant).

    Validates instalments is int in range 2-12 and outstanding_balance > 0.
    Computes instalment amounts with rounding remainder on final instalment.
    Schedule uses monthly spacing from hardcoded "today" = "2025-07-01".

    Conservation invariant: sum(schedule[].amount) == outstanding_balance exactly.

    Raises:
        ValueError: if instalments not in 2-12 or outstanding_balance <= 0.
    """
    _validate_customer_id(customer_id)

    if not isinstance(instalments, int) or instalments < 2 or instalments > 12:
        raise ValueError("instalments must be an integer between 2 and 12")

    if outstanding_balance <= 0:
        raise ValueError("outstanding_balance must be greater than 0")

    # Compute instalment amount (rounded to 2 decimal places)
    instalment_amount = round(outstanding_balance / instalments, 2)

    # Final instalment gets the rounding remainder to ensure exact conservation.
    # Use round() to avoid floating-point drift in the subtraction.
    final_instalment = round(outstanding_balance - instalment_amount * (instalments - 1), 2)

    # Generate schedule with monthly spacing from hardcoded "today"
    start_date = datetime(2025, 7, 1)
    schedule = []
    for i in range(instalments):
        # Calculate due date: add i months to start_date
        month = start_date.month + i
        year = start_date.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        day = start_date.day
        due_date = datetime(year, month, day)

        amount = final_instalment if i == instalments - 1 else instalment_amount
        schedule.append({
            "due_date": due_date.strftime("%Y-%m-%d"),
            "amount": amount,
        })

    return {
        "customer_id": customer_id,
        "outstanding_balance": outstanding_balance,
        "instalment_count": instalments,
        "instalment_amount": instalment_amount,
        "total_payable": outstanding_balance,
        "interest_free": True,
        "schedule": schedule,
    }


def compute_risk_signals(
    customer_ids: List[str],
    billing_records: Dict[str, List[Dict[str, Any]]],
    hardship_flags: Dict[str, bool],
) -> Dict[str, Any]:
    """Compute and rank risk signals for a list of customers (SAV-03 compliant).

    For each customer, computes a risk_score (0-100) from:
      - Bill-shock magnitude (delta_dollars normalized to 0-60 range)
      - Usage trend direction (increasing/decreasing/stable over last 3 months)
      - Bill shock detected bonus (+20 if is_shock=true)
      - Hardship override: if hardship_flag=true, score=0 regardless

    Returns a dict with:
      - customers_at_risk: count of customers with non-zero risk_score
      - queue: list of RiskSignal objects sorted descending by risk_score

    Each RiskSignal contains:
      - customer_id, risk_score, risk_summary, bill_shock_detected,
        usage_trend, hardship_flag

    Args:
        customer_ids: list of customer_id strings to evaluate
        billing_records: dict mapping customer_id → list of billing records
        hardship_flags: dict mapping customer_id → bool (True if hardship)

    Returns:
        dict with customers_at_risk count and ranked queue list
    """
    signals = []

    for cid in customer_ids:
        _validate_customer_id(cid)
        records = billing_records.get(cid, [])
        is_hardship = hardship_flags.get(cid, False)

        # Compute bill-shock using existing pure function
        bill_shock_detected = False
        delta_dollars = 0.0
        if len(records) >= 2:
            shock_result = detect_bill_shock_pure(records)
            bill_shock_detected = shock_result["is_shock"]
            delta_dollars = shock_result["delta_dollars"]

        # Compute usage trend from last 3 months of billing history
        usage_trend = _compute_usage_trend(records)

        # Compute risk score
        risk_score = _compute_risk_score(
            delta_dollars=delta_dollars,
            bill_shock_detected=bill_shock_detected,
            usage_trend=usage_trend,
            is_hardship=is_hardship,
        )

        # Compose risk summary (SAV-03: code-composed, never touches LLM)
        risk_summary = _compose_risk_summary(
            bill_shock_detected=bill_shock_detected,
            delta_dollars=delta_dollars,
            usage_trend=usage_trend,
        )

        signals.append({
            "customer_id": cid,
            "risk_score": risk_score,
            "risk_summary": risk_summary,
            "bill_shock_detected": bill_shock_detected,
            "usage_trend": usage_trend,
            "hardship_flag": is_hardship,
        })

    # Sort descending by risk_score
    signals.sort(key=lambda s: s["risk_score"], reverse=True)

    customers_at_risk = sum(1 for s in signals if s["risk_score"] > 0)

    return {
        "customers_at_risk": customers_at_risk,
        "queue": signals,
    }


def _compute_usage_trend(records: List[Dict[str, Any]]) -> str:
    """Compute usage trend from last 3 months of billing history.

    Returns "increasing", "decreasing", or "stable" based on whether
    the last 3 months show a consistent upward/downward pattern.
    """
    if len(records) < 3:
        return "stable"

    # Sort by month ascending and take last 3
    sorted_records = sorted(records, key=lambda r: r["month"])
    last_3 = sorted_records[-3:]
    usages = [float(r["usage_kwh"]) for r in last_3]

    # Check if consistently increasing or decreasing
    if usages[2] > usages[1] > usages[0]:
        return "increasing"
    elif usages[2] < usages[1] < usages[0]:
        return "decreasing"
    else:
        return "stable"


def _compute_risk_score(
    *,
    delta_dollars: float,
    bill_shock_detected: bool,
    usage_trend: str,
    is_hardship: bool,
) -> int:
    """Compute risk score (0-100) from components.

    Formula:
      - Base: bill-shock delta_dollars normalized to 0-60 range (delta/100 * 60, capped at 60)
      - Usage trend bonus: +20 for increasing, +10 for stable, +0 for decreasing
      - Bill shock detected bonus: +20 if is_shock=true
      - Hardship override: if hardship_flag=true, score=0 regardless
      - Final score clamped to [0, 100]
    """
    # Hardship override
    if is_hardship:
        return 0

    # Base from bill-shock magnitude (only positive deltas contribute)
    base = max(0.0, delta_dollars) / 100.0 * 60.0
    base = min(base, 60.0)

    # Usage trend bonus
    trend_bonus = {"increasing": 20, "stable": 10, "decreasing": 0}.get(usage_trend, 0)

    # Bill shock bonus
    shock_bonus = 20 if bill_shock_detected else 0

    # Final score clamped to [0, 100]
    raw_score = base + trend_bonus + shock_bonus
    return max(0, min(100, int(round(raw_score))))


def _compose_risk_summary(
    *,
    bill_shock_detected: bool,
    delta_dollars: float,
    usage_trend: str,
) -> str:
    """Compose a human-readable risk summary (SAV-03: code-composed).

    Format:
      - If bill shock detected: "Bill shock: +$X over baseline"
      - If no shock but usage increasing: "Usage trending up, no shock detected"
      - If no shock and stable/decreasing: "Low risk: stable usage pattern"
    """
    if bill_shock_detected:
        return f"Bill shock: +${abs(delta_dollars):.0f} over baseline"
    elif usage_trend == "increasing":
        return "Usage trending up, no shock detected"
    else:
        return "Low risk: stable usage pattern"


def schedule_callback_pure(
    customer_id: str,
    when: str,
    reason: str,
) -> Dict[str, Any]:
    """Schedule a callback — demo-safe, no persistence (SAV-03 compliant).

    Validates `when` is a valid ISO datetime and `reason` is non-empty.
    Generates a deterministic callback_id using UUID5 from inputs.

    Raises:
        ValueError: if `when` is not valid ISO datetime or `reason` is empty.
    """
    _validate_customer_id(customer_id)

    # Validate ISO datetime
    try:
        datetime.fromisoformat(when)
    except (ValueError, TypeError):
        raise ValueError(f"'when' must be a valid ISO datetime string, got {when!r}")

    # Validate reason is non-empty
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("'reason' must be a non-empty string")

    # Generate deterministic callback_id using UUID5
    callback_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{customer_id}:{when}:{reason}"))

    return {
        "customer_id": customer_id,
        "callback_id": callback_id,
        "scheduled_time": when,
        "reason": reason,
        "status": "confirmed",
    }


# --- Agentic Actions Portfolio: Action Queue Pure Functions ---

_VALID_ACTION_TYPES = {"tariff_switch", "send_sms", "payment_plan_offer"}


def queue_action(action: Dict[str, Any], table_client=None) -> Dict[str, Any]:
    """Validate and store a Confirmable_Action with status=pending.

    Validates:
      - action_type is one of tariff_switch, send_sms, payment_plan_offer
      - customer_id matches CUST-NNN pattern
      - payload is a non-empty dict

    Stores in DynamoDB with sort key ACTION#{action_id}, status=pending,
    created_at (ISO 8601), and expires_at (Unix epoch, 24h TTL).

    Args:
        action: dict with keys action_type, customer_id, payload
        table_client: DynamoDB table resource (injectable for testing)

    Returns:
        dict with action_id, action_type, customer_id, payload, status,
        created_at, expires_at

    Raises:
        ValueError: if payload validation fails
    """
    # Validate action_type
    action_type = action.get("action_type")
    if action_type not in _VALID_ACTION_TYPES:
        raise ValueError(
            f"action_type must be one of {sorted(_VALID_ACTION_TYPES)}, got {action_type!r}"
        )

    # Validate customer_id
    customer_id = _validate_customer_id(action.get("customer_id"))

    # Validate payload
    payload = action.get("payload")
    if not isinstance(payload, dict) or not payload:
        raise ValueError("payload must be a non-empty dict")

    # Generate action metadata
    action_id = str(uuid.uuid4())
    now = datetime.utcnow()
    created_at = now.isoformat() + "Z"
    expires_at = int((now + timedelta(hours=24)).timestamp())

    item = {
        "action_id": action_id,
        "action_type": action_type,
        "customer_id": customer_id,
        "payload": payload,
        "status": "pending",
        "created_at": created_at,
        "expires_at": expires_at,
    }

    # Store in DynamoDB if table_client provided
    tbl = table_client or table
    if tbl is not None:
        tbl.put_item(Item={
            "customer_id": customer_id,
            "month": f"ACTION#{action_id}",
            **item,
        })

    return item


def confirm_action(action_id: str, table_client=None) -> Dict[str, Any]:
    """Transition a pending action to confirmed status.

    Reads the action by action_id, validates it is pending and not expired,
    then updates status to confirmed.

    Args:
        action_id: UUID string identifying the action
        table_client: DynamoDB table resource (injectable for testing)

    Returns:
        dict with updated action (status=confirmed)

    Raises:
        ValueError: if action_id is invalid, action not found, already
                    processed, or expired
    """
    return _transition_action(action_id, "confirmed", table_client)


def dismiss_action(action_id: str, table_client=None) -> Dict[str, Any]:
    """Transition a pending action to rejected status.

    Reads the action by action_id, validates it is pending and not expired,
    then updates status to rejected.

    Args:
        action_id: UUID string identifying the action
        table_client: DynamoDB table resource (injectable for testing)

    Returns:
        dict with updated action (status=rejected)

    Raises:
        ValueError: if action_id is invalid, action not found, already
                    processed, or expired
    """
    return _transition_action(action_id, "rejected", table_client)


def _transition_action(action_id: str, target_status: str, table_client=None) -> Dict[str, Any]:
    """Internal helper: transition an action to target_status.

    Validates:
      - action_id is a valid UUID
      - action exists in the store
      - action is currently pending
      - action has not expired

    Args:
        action_id: UUID string
        target_status: "confirmed" or "rejected"
        table_client: DynamoDB table resource (injectable for testing)

    Returns:
        dict with updated action

    Raises:
        ValueError: on validation failure
    """
    # Validate action_id format (UUID)
    try:
        uuid.UUID(action_id)
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f"action_id must be a valid UUID, got {action_id!r}")

    tbl = table_client or table
    if tbl is None:
        raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")

    # Scan for the action item by sort key pattern ACTION#{action_id}
    # Since we don't know the customer_id, we query using a scan with filter.
    # For the demo scale (6 personas), this is acceptable.
    sort_key = f"ACTION#{action_id}"
    response = tbl.scan(
        FilterExpression="month = :sk",
        ExpressionAttributeValues={":sk": sort_key},
    )
    items = response.get("Items", [])
    if not items:
        raise ValueError(f"Action not found: {action_id}")

    item = items[0]

    # Validate status is pending
    if item.get("status") != "pending":
        raise ValueError(
            f"Action already processed: status={item.get('status')!r}"
        )

    # Validate not expired
    expires_at = int(item.get("expires_at", 0))
    now_epoch = int(datetime.utcnow().timestamp())
    if now_epoch >= expires_at:
        raise ValueError("Action has expired")

    # Transition status
    tbl.update_item(
        Key={"customer_id": item["customer_id"], "month": sort_key},
        UpdateExpression="SET #s = :status",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":status": target_status},
    )

    # Return updated action
    return {
        "action_id": item["action_id"],
        "action_type": item["action_type"],
        "customer_id": item["customer_id"],
        "payload": item["payload"],
        "status": target_status,
        "created_at": item["created_at"],
        "expires_at": item["expires_at"],
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


# --- Phase 12 action dispatcher (D-02) ---

def handler(event: Dict[str, Any], context) -> Any:
    """Phase 12 action dispatcher — routes to existing handlers.

    Per D-02: routes on `event["action"]`. Per D-05: missing action defaults
    to `simulate_savings` for back-compat with v2.0 callers (the agent's
    pre-provider `_lambda_client.invoke(...{customer_id})` and the fallback
    path at agent/agent.py:394-418 still work).

    Routed actions (matches agent/providers.py::ToolsLambdaProvider payload shapes):
      - "get_billing_history" → get_billing_history(event, context)
      - "get_hardship_flag"   → get_hardship_flag_pure(customer_id, table)
      - "get_customer"        → {"customer_id": customer_id}  (Phase 12 stub)
      - "simulate_savings"    → simulate_savings(event, context)
      - "check_outage_status" → check_outage_status_pure(suburb)
      - "decompose_bill_shock" → decompose_bill_shock_pure(billing_history)
      - "detect_bill_shock"   → decompose_bill_shock_pure(billing_history) (backward compat alias)
      - "lookup_concessions"  → lookup_concessions_pure(customer_id)
      - "estimate_solar_payback" → estimate_solar_payback_pure(customer_id, billing_history)
      - "propose_payment_plan" → propose_payment_plan_pure(customer_id, instalments, balance)
      - "schedule_callback"   → schedule_callback_pure(customer_id, when, reason)
      - (none)                → simulate_savings(event, context)  (D-05 back-compat)
    """
    try:
        action = event.get("action")

        if action == "get_billing_history":
            return get_billing_history(event, context)

        if action == "get_hardship_flag":
            customer_id = _validate_customer_id(event.get("customer_id"))
            if table is None:
                raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")
            return get_hardship_flag_pure(customer_id, table)

        if action == "detect_bill_shock":
            # Backward-compat alias: routes to decompose_bill_shock_pure for richer
            # decomposition while preserving the existing action name for callers.
            customer_id = _validate_customer_id(event.get("customer_id"))
            if table is None:
                raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")
            billing = get_billing_history({"customer_id": customer_id}, context)
            return decompose_bill_shock_pure(billing)

        if action == "decompose_bill_shock":
            customer_id = _validate_customer_id(event.get("customer_id"))
            if table is None:
                raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")
            billing = get_billing_history({"customer_id": customer_id}, context)
            return decompose_bill_shock_pure(billing)

        if action == "check_outage_status":
            return check_outage_status_pure(event["suburb"])

        if action == "lookup_concessions":
            return lookup_concessions_pure(event["customer_id"])

        if action == "estimate_solar_payback":
            customer_id = _validate_customer_id(event.get("customer_id"))
            if table is None:
                raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")
            billing = get_billing_history({"customer_id": customer_id}, context)
            return estimate_solar_payback_pure(customer_id, billing)

        if action == "propose_payment_plan":
            customer_id = _validate_customer_id(event.get("customer_id"))
            outstanding_balance = BALANCE_DATA.get(customer_id, 0.0)
            return propose_payment_plan_pure(
                customer_id, event["instalments"], outstanding_balance
            )

        if action == "schedule_callback":
            return schedule_callback_pure(
                event["customer_id"], event["when"], event["reason"]
            )

        if action == "compute_risk_signals":
            customer_ids = event.get("customer_ids", [])
            # Build billing records and hardship flags for each customer
            if table is None:
                raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")
            billing_records = {}
            hardship_flags = {}
            for cid in customer_ids:
                _validate_customer_id(cid)
                billing = get_billing_history({"customer_id": cid}, context)
                billing_records[cid] = billing
                hardship_result = get_hardship_flag_pure(cid, table)
                hardship_flags[cid] = hardship_result["hardship"]
            return compute_risk_signals(customer_ids, billing_records, hardship_flags)

        if action == "queue_action":
            return queue_action(event.get("action_payload", {}))

        if action == "confirm_action":
            return confirm_action(event.get("action_id", ""))

        if action == "dismiss_action":
            return dismiss_action(event.get("action_id", ""))

        if action == "get_customer":
            # Phase 12 stub — Phase 13/14 may extend the shape (CONTEXT §Claude's Discretion).
            customer_id = _validate_customer_id(event.get("customer_id"))
            return {"customer_id": customer_id}

        if action == "simulate_savings":
            return simulate_savings(event, context)

        # D-05 back-compat: action-less event → simulate_savings (v2.0 shape).
        return simulate_savings(event, context)

    except ValueError as e:
        return {"error": True, "message": str(e)}
