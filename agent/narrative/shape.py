"""Shape-token builder — converts billing history + plan into qualitative descriptors.

Contract (frozen at DEMO-04): the LLM sees the output of this function —
NEVER raw kWh, NEVER dollar values. Every returned value is a lowercase
`[a-z_]+` enum string. Structural guarantee that numbers cannot leak
into the narrative prompt (CONTEXT.md D-07).

Vocabulary:
  usage_tier:         "low" | "mid" | "high"
  seasonality:        "winter_heavy" | "summer_peak" | "flat"
  plan_category:      "green_premium" | "value" | "time_of_use" | "standard"
  renewable_profile:  "eco_aligned" | "cost_aligned"
  tenure_band:        "established"    # placeholder — v2.0 has no tenure data
"""
from typing import Any, Dict, List

# --- Threshold constants (LLM-facing contract — documented, reviewable) ---

_USAGE_TIER_THRESHOLDS_KWH = (200, 400)  # low < 200 <= mid < 400 <= high

# Australian seasonal months (June–August winter; December–February summer).
_WINTER_MONTHS = {"2025-06", "2025-07", "2025-08", "2026-06", "2026-07", "2026-08"}
_SUMMER_MONTHS = {"2025-12", "2026-01", "2026-02", "2026-12", "2027-01", "2027-02"}


def _compute_usage_tier(avg_kwh: float) -> str:
    if avg_kwh < _USAGE_TIER_THRESHOLDS_KWH[0]:
        return "low"
    if avg_kwh < _USAGE_TIER_THRESHOLDS_KWH[1]:
        return "mid"
    return "high"


def _compute_seasonality(billing_history: List[Dict[str, Any]]) -> str:
    winter = [float(r["usage_kwh"]) for r in billing_history if r["month"] in _WINTER_MONTHS]
    summer = [float(r["usage_kwh"]) for r in billing_history if r["month"] in _SUMMER_MONTHS]
    if not winter or not summer:
        return "flat"
    winter_avg = sum(winter) / len(winter)
    summer_avg = sum(summer) / len(summer)
    if winter_avg > summer_avg * 1.2:
        return "winter_heavy"
    if summer_avg > winter_avg * 1.2:
        return "summer_peak"
    return "flat"


def build_shape_tokens(
    billing_history: List[Dict[str, Any]],
    plan: Dict[str, Any],
) -> Dict[str, str]:
    """Derive qualitative descriptors from billing history + plan.

    Algorithm:
      avg_kwh     = mean(record["usage_kwh"])
      usage_tier  = band(avg_kwh, _USAGE_TIER_THRESHOLDS_KWH)
      seasonality = compare(winter_avg, summer_avg)
      plan_category = plan["plan_type"]
      renewable_profile = "eco_aligned" if plan_type == "green_premium" else "cost_aligned"
      tenure_band = "established"   # v2.0 placeholder

    Raises:
      ValueError: billing_history must not be empty.
    """
    if not billing_history:
        raise ValueError("billing_history must not be empty")

    avg_kwh = sum(float(r["usage_kwh"]) for r in billing_history) / len(billing_history)
    plan_type = plan.get("plan_type", "standard")
    return {
        "usage_tier": _compute_usage_tier(avg_kwh),
        "seasonality": _compute_seasonality(billing_history),
        "plan_category": plan_type,
        "renewable_profile": "eco_aligned" if plan_type == "green_premium" else "cost_aligned",
        "tenure_band": "established",
    }
