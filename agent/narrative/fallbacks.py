"""Per-persona × per-card fallback narrative strings.

D-05, D-06: demo-ready copy, frozen at DEMO-04. Every string MUST pass
`_reject_forbidden` (enforced by tests/test_fallbacks_pass_validator.py).
References the plan name; NEVER references numbers, currency, or banned terms.

STRIDE: Integrity — double-fail recovery path (D-02) lands here, so these
strings are the last line of defence. If they fail validation, the response
is corrupted.
"""
from typing import Dict

# --- FALLBACKS constant ---

FALLBACKS: Dict[str, Dict[str, Dict[str, str]]] = {
    # Sarah Chen (CUST-001) — high-usage family household, winter-heavy.
    "CUST-001": {
        "green": {
            "usage_narrative": "Strong cool-season usage with a family-sized load across the year.",
            "call_script": "Ask about EcoFlex — it suits a strong winter-heating profile like yours.",
        },
        "cheapest": {
            "usage_narrative": "Consistently high household consumption with cool-season peaks.",
            "call_script": "Bring up Value Twelve — a budget-first pick for a high-usage home.",
        },
    },
    # Marcus Webb (CUST-002) — mid-usage apartment dweller, modest seasonality.
    "CUST-002": {
        "green": {
            "usage_narrative": "Mid-range apartment usage with gentle seasonal variation across the year.",
            "call_script": "Ask about EcoFlex — a steady, eco-aligned option for a mid-range home.",
        },
        "cheapest": {
            "usage_narrative": "Moderate apartment consumption with only mild cool-season lifts.",
            "call_script": "Bring up Value Twelve — a cost-led pick for a mid-range apartment.",
        },
    },
    # Elena Vasquez (CUST-003) — seasonal, summer-peak, cooling-heavy.
    "CUST-003": {
        "green": {
            "usage_narrative": "Summer-peak household profile with cooling-driven demand in warm months.",
            "call_script": "Ask about EcoFlex — an eco-aligned fit for a summer-peak cooling load.",
        },
        "cheapest": {
            "usage_narrative": "Warm-season heavy with light winter usage and a cooling-led pattern.",
            "call_script": "Bring up Value Twelve — a cost-led option for a warm-season household.",
        },
    },
}

# --- Import-time sanity assertions (billing_records.py pattern) ---

assert len(FALLBACKS) == 3, "FALLBACKS must contain 3 personas"
for _cust, _tracks in FALLBACKS.items():
    assert set(_tracks.keys()) == {"green", "cheapest"}, f"{_cust}: must have green and cheapest"
    for _track, _fields in _tracks.items():
        assert set(_fields.keys()) == {"usage_narrative", "call_script"}, (
            f"{_cust}/{_track}: must have usage_narrative and call_script"
        )
