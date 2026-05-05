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
    # CUST-006 — hardship persona (Phase 14 AGENT-02).
    # D-15 validated: no digits, no currency, no banned terms, no plan IDs.
    # The "hardship" key is a third track alongside green/cheapest — used by
    # _build_hardship_response when the pre-LLM guard fires.
    "CUST-006": {
        "green": {
            "usage_narrative": "Low-usage household with a steady, modest consumption pattern.",
            "call_script": "Ask about EcoFlex — a gentle, eco-aligned option for a modest home.",
        },
        "cheapest": {
            "usage_narrative": "Modest household consumption with a flat, low-demand profile.",
            "call_script": "Bring up Value Twelve — a budget-friendly pick for a low-usage home.",
        },
        "hardship": {
            "reason": "This customer account is flagged for dedicated support from our specialist team.",
            "call_script": "Let me connect you with our specialist support team who can best help with your account.",
        },
    },
    # --- Phase 16 AGENT-03: Typed hardship personas (category-keyed) ---
    # CUST-007 — payment_difficulty persona.
    # The "hardship" key is a dict keyed by category with reason + call_script sub-keys.
    "CUST-007": {
        "green": {
            "usage_narrative": "Low-usage household receiving dedicated support for energy needs.",
            "call_script": "Ask about EcoFlex — a gentle, eco-aligned option for a modest home.",
        },
        "cheapest": {
            "usage_narrative": "Modest household consumption with a flat, low-demand profile.",
            "call_script": "Bring up Value Twelve — a budget-friendly pick for a low-usage home.",
        },
        "hardship": {
            "payment_difficulty": {
                "reason": "This customer is receiving dedicated support for managing their energy needs.",
                "call_script": "I can see you have support in place — let me discuss flexible options that work for you.",
            },
        },
    },
    # CUST-008 — medical_equipment persona.
    "CUST-008": {
        "green": {
            "usage_narrative": "Low-usage household with priority service needs and steady demand.",
            "call_script": "Ask about EcoFlex — a gentle, eco-aligned option for a modest home.",
        },
        "cheapest": {
            "usage_narrative": "Modest household consumption with priority service requirements.",
            "call_script": "Bring up Value Twelve — a budget-friendly pick for a low-usage home.",
        },
        "hardship": {
            "medical_equipment": {
                "reason": "This customer has priority service guarantees for essential equipment at home.",
                "call_script": "Your priority service guarantee is noted — let me ensure your supply continuity is protected.",
            },
        },
    },
    # CUST-009 — family_violence persona.
    # CRITICAL: zero financial terms in reason or call_script.
    "CUST-009": {
        "green": {
            "usage_narrative": "Low-usage household requiring immediate specialist team support.",
            "call_script": "Ask about EcoFlex — a gentle, eco-aligned option for a modest home.",
        },
        "cheapest": {
            "usage_narrative": "Modest household consumption requiring specialist team routing.",
            "call_script": "Bring up Value Twelve — a budget-friendly pick for a low-usage home.",
        },
        "hardship": {
            "family_violence": {
                "reason": "This customer requires immediate, confidential connection to our specialist safety team.",
                "call_script": "Your safety is our priority — I am connecting you directly to our specialist support team now.",
            },
        },
    },
    # CUST-010 — other (generic) hardship persona.
    "CUST-010": {
        "green": {
            "usage_narrative": "Low-usage household with a steady, modest consumption pattern.",
            "call_script": "Ask about EcoFlex — a gentle, eco-aligned option for a modest home.",
        },
        "cheapest": {
            "usage_narrative": "Modest household consumption with a flat, low-demand profile.",
            "call_script": "Bring up Value Twelve — a budget-friendly pick for a low-usage home.",
        },
        "hardship": {
            "other": {
                "reason": "This customer is flagged for dedicated support from our specialist team.",
                "call_script": "Let me connect you with our specialist support team who can best help you.",
            },
        },
    },
}
for _cust, _tracks in FALLBACKS.items():
    # Recommendation personas have green + cheapest; CUST-006 also has hardship.
    assert "green" in _tracks and "cheapest" in _tracks, f"{_cust}: must have green and cheapest"
    for _track_name, _fields in _tracks.items():
        if _track_name == "hardship":
            if isinstance(_fields, dict) and "reason" in _fields and "call_script" in _fields:
                # Legacy flat hardship format (CUST-006)
                assert set(_fields.keys()) == {"reason", "call_script"}, (
                    f"{_cust}/hardship: must have reason and call_script"
                )
            elif isinstance(_fields, dict):
                # New category-keyed hardship format (CUST-007 through CUST-010)
                for _cat, _cat_fields in _fields.items():
                    assert isinstance(_cat_fields, dict), (
                        f"{_cust}/hardship/{_cat}: must be a dict"
                    )
                    assert set(_cat_fields.keys()) == {"reason", "call_script"}, (
                        f"{_cust}/hardship/{_cat}: must have reason and call_script"
                    )
            else:
                raise AssertionError(f"{_cust}/hardship: unexpected format")
        else:
            assert set(_fields.keys()) == {"usage_narrative", "call_script"}, (
                f"{_cust}/{_track_name}: must have usage_narrative and call_script"
            )


# --- Phase 15 WF-01: Follow-up email fallback templates ---
# Per-persona follow-up email templates used when Memory is unavailable or
# the agent turn fails. All templates MUST pass D-15 validators (no digits,
# no currency, no banned terms). plan_reference is the GREEN plan name.

FOLLOW_UP_FALLBACKS: Dict[str, Dict[str, str]] = {
    # Sarah Chen (CUST-001) — high-usage family household.
    "CUST-001": {
        "subject": "Your tariff options from our recent conversation",
        "body": (
            "Thank you for speaking with us about your energy plan options. "
            "As discussed, we identified plans that could better suit your household "
            "usage pattern. Please review the options at your convenience and contact "
            "us if you would like to proceed with the plan that works for your family."
        ),
        "plan_reference": "EcoFlex Green",
    },
    # Marcus Webb (CUST-002) — mid-usage apartment dweller.
    "CUST-002": {
        "subject": "Your tariff options from our recent conversation",
        "body": (
            "Thank you for speaking with us about your energy plan options. "
            "We discussed plans that align well with your apartment usage profile. "
            "Please review the options at your convenience and reach out if you "
            "would like to proceed with the plan that suits your home."
        ),
        "plan_reference": "EcoFlex Green",
    },
    # Elena Vasquez (CUST-003) — seasonal, summer-peak.
    "CUST-003": {
        "subject": "Your tariff options from our recent conversation",
        "body": (
            "Thank you for speaking with us about your energy plan options. "
            "We identified plans that could complement your seasonal usage pattern. "
            "Please review the options at your convenience and let us know if you "
            "would like to proceed with the plan that fits your household."
        ),
        "plan_reference": "EcoFlex Green",
    },
    # CUST-004 — Solar PV persona.
    "CUST-004": {
        "subject": "Your tariff options from our recent conversation",
        "body": (
            "Thank you for speaking with us about your energy plan options. "
            "We discussed plans that work well with your solar generation profile. "
            "Please review the options at your convenience and contact us if you "
            "would like to proceed with the plan that complements your setup."
        ),
        "plan_reference": "Solar Feed-in",
    },
    # CUST-005 — EV persona.
    "CUST-005": {
        "subject": "Your tariff options from our recent conversation",
        "body": (
            "Thank you for speaking with us about your energy plan options. "
            "We identified plans that align with your household charging pattern. "
            "Please review the options at your convenience and reach out if you "
            "would like to proceed with the plan that suits your needs."
        ),
        "plan_reference": "EV Time-of-Use",
    },
}

# Wire follow-up templates into the main FALLBACKS dict so they're accessible
# via FALLBACKS[customer_id]["follow_up"] — same pattern as "hardship" key.
for _cust_id, _follow_up in FOLLOW_UP_FALLBACKS.items():
    if _cust_id in FALLBACKS:
        FALLBACKS[_cust_id]["follow_up"] = _follow_up

# --- Import-time sanity assertions (billing_records.py pattern) ---

assert len(FALLBACKS) == 8, f"FALLBACKS must contain 8 personas, got {len(FALLBACKS)}"
for _cust, _tracks in FALLBACKS.items():
    # All personas have green + cheapest.
    assert "green" in _tracks and "cheapest" in _tracks, f"{_cust}: must have green and cheapest"
    for _track_name, _fields in _tracks.items():
        if _track_name == "hardship":
            if isinstance(_fields, dict) and "reason" in _fields and "call_script" in _fields:
                # Legacy flat hardship format (CUST-006)
                assert set(_fields.keys()) == {"reason", "call_script"}, (
                    f"{_cust}/hardship: must have reason and call_script"
                )
            elif isinstance(_fields, dict):
                # New category-keyed hardship format (CUST-007 through CUST-010)
                assert len(_fields) > 0, f"{_cust}/hardship: must have at least one category"
                for _cat, _cat_fields in _fields.items():
                    assert isinstance(_cat_fields, dict), (
                        f"{_cust}/hardship/{_cat}: must be a dict"
                    )
                    assert set(_cat_fields.keys()) == {"reason", "call_script"}, (
                        f"{_cust}/hardship/{_cat}: must have reason and call_script"
                    )
            else:
                raise AssertionError(f"{_cust}/hardship: unexpected format")
        elif _track_name == "follow_up":
            assert set(_fields.keys()) == {"subject", "body", "plan_reference"}, (
                f"{_cust}/follow_up: must have subject, body, and plan_reference"
            )
        else:
            assert set(_fields.keys()) == {"usage_narrative", "call_script"}, (
                f"{_cust}/{_track_name}: must have usage_narrative and call_script"
            )

# Verify follow-up templates exist for all recommendation personas.
for _cust_id in ("CUST-001", "CUST-002", "CUST-003"):
    assert "follow_up" in FALLBACKS[_cust_id], (
        f"{_cust_id}: must have follow_up fallback template"
    )

# Verify typed hardship personas have category-keyed hardship dicts.
_TYPED_HARDSHIP_PERSONAS = ("CUST-007", "CUST-008", "CUST-009", "CUST-010")
for _cust_id in _TYPED_HARDSHIP_PERSONAS:
    assert _cust_id in FALLBACKS, f"{_cust_id}: must be in FALLBACKS"
    assert "hardship" in FALLBACKS[_cust_id], f"{_cust_id}: must have hardship key"
    _h = FALLBACKS[_cust_id]["hardship"]
    # Must NOT be the legacy flat format (no top-level "reason" key)
    assert "reason" not in _h, (
        f"{_cust_id}/hardship: typed persona must use category-keyed format, not flat"
    )
    for _cat, _cat_fields in _h.items():
        assert "reason" in _cat_fields and "call_script" in _cat_fields, (
            f"{_cust_id}/hardship/{_cat}: must have reason and call_script"
        )
