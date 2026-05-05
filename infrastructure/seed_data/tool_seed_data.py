"""Seed data for the expanded tool gallery (Phase: expanded-tool-gallery).

Provides hardcoded, deterministic data for the 6 new tools:
  - check_outage_status → OUTAGE_DATA (keyed by suburb)
  - lookup_concessions → CONCESSION_DATA (keyed by customer_id)
  - propose_payment_plan → BALANCE_DATA (keyed by customer_id)
  - check_outage_status (customer lookup) → SUBURB_MAP (customer_id → suburb)
  - estimate_solar_payback → SOLAR_CONSTANTS + SOLAR_CUSTOMERS

All data is embedded (no DynamoDB reads) for demo-safety and determinism.
Persona mappings:
  - CUST-001 (Sarah Chen) → Bondi (no outage), 1 active concession, $0 balance
  - CUST-002 (Marcus Webb) → Parramatta (unplanned outage), no concessions, $45.50 balance
  - CUST-003 (Elena Vasquez) → Marrickville (planned outage), eligible-not-applied, $120 balance
  - CUST-004 → already has solar (ineligible for solar payback)
  - CUST-006 → hardship persona, $890 balance
"""
from typing import Dict, Any, List, Set


# ---------------------------------------------------------------------------
# 1. Outage Data — keyed by suburb name
# ---------------------------------------------------------------------------

OUTAGE_DATA: Dict[str, Dict[str, Any]] = {
    "Marrickville": {
        "has_outage": True,
        "outage_type": "planned",
        "affected_postcodes": ["2204", "2205"],
        "estimated_restoration": "2025-07-15T14:00:00+10:00",
        "customers_affected": 450,
    },
    "Parramatta": {
        "has_outage": True,
        "outage_type": "unplanned",
        "affected_postcodes": ["2150", "2151", "2152"],
        "estimated_restoration": "2025-07-12T18:00:00+10:00",
        "customers_affected": 1200,
    },
    "Bondi": {
        "has_outage": False,
        "outage_type": "none",
        "affected_postcodes": [],
        "estimated_restoration": None,
        "customers_affected": 0,
    },
}


# ---------------------------------------------------------------------------
# 2. Concession Data — keyed by customer_id
# ---------------------------------------------------------------------------

CONCESSION_DATA: Dict[str, Dict[str, Any]] = {
    "CUST-001": {
        "eligible_concessions": [
            {
                "name": "NSW Energy Rebate",
                "type": "energy_concession",
                "annual_value": 285.00,
                "applied": True,
                "description": "Annual rebate for eligible NSW households",
            }
        ],
    },
    "CUST-002": {"eligible_concessions": []},
    "CUST-003": {
        "eligible_concessions": [
            {
                "name": "Low Income Household Rebate",
                "type": "low_income",
                "annual_value": 315.00,
                "applied": False,
                "description": "Rebate for Health Care Card holders",
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# 3. Outstanding Balance Data — keyed by customer_id
# ---------------------------------------------------------------------------

BALANCE_DATA: Dict[str, float] = {
    "CUST-001": 0.00,
    "CUST-002": 45.50,
    "CUST-003": 120.00,
    "CUST-006": 890.00,
}


# ---------------------------------------------------------------------------
# 4. Suburb-to-Customer Mapping — for outage lookups
# ---------------------------------------------------------------------------

SUBURB_MAP: Dict[str, str] = {
    "CUST-001": "Bondi",
    "CUST-002": "Parramatta",
    "CUST-003": "Marrickville",
}


# ---------------------------------------------------------------------------
# 5. Solar Constants — AU-average irradiance and system economics
# ---------------------------------------------------------------------------

SOLAR_CONSTANTS: Dict[str, float] = {
    "cost_per_kw": 1200.00,           # AUD per kW installed
    "daily_generation_per_kw": 4.2,   # kWh/kW/day (AU average irradiance)
    "self_consumption_ratio": 0.70,   # 70% self-consumed, 30% exported
    "feed_in_tariff": 0.05,           # $/kWh export credit
    "retail_rate": 0.32,              # $/kWh avoided grid purchase (matches STD_RATE)
}

# Customers who already have solar installed (ineligible for solar payback estimation)
SOLAR_CUSTOMERS: Set[str] = {"CUST-004"}


# ---------------------------------------------------------------------------
# Import-time assertions — fail fast on data invariant violations
# ---------------------------------------------------------------------------

# At least 3 suburbs in outage data
assert len(OUTAGE_DATA) >= 3, (
    f"OUTAGE_DATA must contain at least 3 suburbs, got {len(OUTAGE_DATA)}"
)

# Outage type diversity: at least one planned and one unplanned
_outage_types = {v["outage_type"] for v in OUTAGE_DATA.values()}
assert "planned" in _outage_types, "OUTAGE_DATA must contain at least one planned outage"
assert "unplanned" in _outage_types, "OUTAGE_DATA must contain at least one unplanned outage"
assert "none" in _outage_types, "OUTAGE_DATA must contain at least one no-outage suburb"

# Persona differentiation in concession data
assert len(CONCESSION_DATA["CUST-001"]["eligible_concessions"]) > 0, (
    "CUST-001 must have at least one concession"
)
assert any(
    c["applied"] for c in CONCESSION_DATA["CUST-001"]["eligible_concessions"]
), "CUST-001 must have at least one applied concession"

assert len(CONCESSION_DATA["CUST-002"]["eligible_concessions"]) == 0, (
    "CUST-002 must have no eligible concessions"
)

assert len(CONCESSION_DATA["CUST-003"]["eligible_concessions"]) > 0, (
    "CUST-003 must have eligible concessions"
)
assert all(
    not c["applied"] for c in CONCESSION_DATA["CUST-003"]["eligible_concessions"]
), "CUST-003 concessions must all be unapplied (eligible but not applied)"

# CUST-004 has solar
assert "CUST-004" in SOLAR_CUSTOMERS, (
    "CUST-004 must be in SOLAR_CUSTOMERS (already has solar installed)"
)

# Balance data persona differentiation
assert BALANCE_DATA["CUST-006"] == 890.00, "CUST-006 (hardship) must have $890 balance"
assert BALANCE_DATA["CUST-001"] == 0.00, "CUST-001 must have $0 balance"

# Solar constants completeness
_required_solar_keys = {"cost_per_kw", "daily_generation_per_kw", "self_consumption_ratio",
                        "feed_in_tariff", "retail_rate"}
assert _required_solar_keys.issubset(SOLAR_CONSTANTS.keys()), (
    f"SOLAR_CONSTANTS missing keys: {_required_solar_keys - set(SOLAR_CONSTANTS.keys())}"
)

# Suburb map consistency: all mapped suburbs must exist in OUTAGE_DATA
assert all(suburb in OUTAGE_DATA for suburb in SUBURB_MAP.values()), (
    "All suburbs in SUBURB_MAP must exist in OUTAGE_DATA"
)
