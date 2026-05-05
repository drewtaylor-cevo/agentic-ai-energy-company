"""Seed data re-export for Lambda runtime.

When the Lambda is packaged (Code.from_asset("lambda")), this module sits
alongside handler.py and provides the seed data constants. It re-exports
from the canonical source (infrastructure/seed_data/tool_seed_data.py) when
running in repo layout (tests), or contains a direct copy for Lambda runtime.

For simplicity and to avoid import-path gymnastics in the Lambda zip, this
file imports from the canonical module. The CDK bundling step should be
updated to include this file OR the infrastructure/seed_data/ directory.
As a fallback for Lambda runtime where infrastructure/ is not on sys.path,
we inline the data.
"""
import sys
import os

# Try canonical import first (works in repo layout / tests)
try:
    from infrastructure.seed_data.tool_seed_data import (
        OUTAGE_DATA,
        CONCESSION_DATA,
        BALANCE_DATA,
        SUBURB_MAP,
        SOLAR_CONSTANTS,
        SOLAR_CUSTOMERS,
    )
except ImportError:
    # Lambda runtime fallback — inline the seed data
    # This block mirrors infrastructure/seed_data/tool_seed_data.py
    from typing import Dict, Any, Set

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

    BALANCE_DATA: Dict[str, float] = {
        "CUST-001": 0.00,
        "CUST-002": 45.50,
        "CUST-003": 120.00,
        "CUST-006": 890.00,
    }

    SUBURB_MAP: Dict[str, str] = {
        "CUST-001": "Bondi",
        "CUST-002": "Parramatta",
        "CUST-003": "Marrickville",
    }

    SOLAR_CONSTANTS: Dict[str, float] = {
        "cost_per_kw": 1200.00,
        "daily_generation_per_kw": 4.2,
        "self_consumption_ratio": 0.70,
        "feed_in_tariff": 0.05,
        "retail_rate": 0.32,
    }

    SOLAR_CUSTOMERS: Set[str] = {"CUST-004"}
