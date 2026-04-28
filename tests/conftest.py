"""Shared pytest fixtures for Phases 1-3 test suites."""
import io
import json
import os
import pytest

# Load tariff plans from the Lambda-side JSON (source of truth).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(_REPO_ROOT, "lambda", "tariff_plans.json")) as f:
    _PLANS = json.load(f)


@pytest.fixture
def tariff_plans():
    """4-plan tariff catalog (STD/ECO/VAL/TOU) from lambda/tariff_plans.json."""
    return _PLANS


@pytest.fixture
def sarah_billing():
    from infrastructure.seed_data.billing_records import SARAH_CHEN_RECORDS
    return SARAH_CHEN_RECORDS


@pytest.fixture
def marcus_billing():
    from infrastructure.seed_data.billing_records import MARCUS_WEBB_RECORDS
    return MARCUS_WEBB_RECORDS


@pytest.fixture
def elena_billing():
    from infrastructure.seed_data.billing_records import ELENA_VASQUEZ_RECORDS
    return ELENA_VASQUEZ_RECORDS


@pytest.fixture
def cust004_billing():
    from infrastructure.seed_data.billing_records import CUST004_RECORDS
    return CUST004_RECORDS


@pytest.fixture
def cust005_billing():
    from infrastructure.seed_data.billing_records import CUST005_RECORDS
    return CUST005_RECORDS


@pytest.fixture
def cust006_billing():
    from infrastructure.seed_data.billing_records import CUST006_RECORDS
    return CUST006_RECORDS


@pytest.fixture
def all_billing():
    from infrastructure.seed_data.billing_records import ALL_RECORDS
    return ALL_RECORDS


# --- Phase 2 agent fixtures ---


@pytest.fixture
def mock_savings_response():
    """Canonical savings response matching simulate_savings_pure output for Sarah Chen."""
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 30.00,
            "saving_annual": 360.00,
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 55.00,
            "saving_annual": 660.00,
        },
    }


@pytest.fixture
def mock_marcus_response():
    """Savings response for Marcus Webb (CUST-002)."""
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 16.90,
            "saving_annual": 202.80,
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 30.98,
            "saving_annual": 371.76,
        },
    }


@pytest.fixture
def mock_elena_response():
    """Savings response for Elena Vasquez (CUST-003)."""
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 14.00,
            "saving_annual": 168.00,
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 25.67,
            "saving_annual": 308.04,
        },
    }


@pytest.fixture
def mock_cust004_response():
    """CUST-004 solar persona — Green (ECO) and Cheapest (SOL).

    Locked byte-exact per scratch/target_equation_solver_v2.py:
    net_avg=667, export_avg=200, sol_rate=0.23, fit_rate=0.08.
    """
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 40.02,
            "saving_annual": 480.24,
        },
        "cheapest": {
            "plan_id": "SOL",
            "plan_name": "Solar Feed-in",
            "saving_monthly": 76.03,
            "saving_annual": 912.36,
        },
    }


@pytest.fixture
def mock_cust005_response():
    """CUST-005 EV persona — Green (ECO) and Cheapest (EV-TOU).

    Locked byte-exact per scratch/target_equation_solver_v2.py:
    total_avg=583.33, 30/70 peak/offpeak, peak_rate=0.40, offpeak_rate=0.08.
    """
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 35.00,
            "saving_annual": 420.00,
        },
        "cheapest": {
            "plan_id": "EV-TOU",
            "plan_name": "EV Drive TOU",
            "saving_monthly": 84.00,
            "saving_annual": 1008.00,
        },
    }


@pytest.fixture
def mock_cust006_response():
    """CUST-006 hardship persona — valid flat-catalog recommendation.

    Phase 14 will short-circuit to hardship before the LLM sees this — but
    simulate_savings_pure still produces a valid recommendation per D-07.
    avg_kwh=200, Green ECO $12.00/mo, Cheapest VAL $22.00/mo.
    """
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 12.00,
            "saving_annual": 144.00,
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 22.00,
            "saving_annual": 264.00,
        },
    }


@pytest.fixture
def mock_cust006_hardship():
    """CUST-006 hardship-flag lookup — shape returned by get_hardship_flag_pure."""
    return {
        "hardship": True,
        "customer_id": "CUST-006",
    }


# --- Phase 3 API Lambda fixtures ---


@pytest.fixture
def mock_agent_invoke_response(mock_savings_response):
    """Mock invoke_agent_runtime response wrapping savings body in StreamingBody-like BytesIO."""
    return {
        "response": io.BytesIO(json.dumps(mock_savings_response).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }


@pytest.fixture
def mock_agent_invoke_not_found():
    """Mock invoke_agent_runtime response for an unknown customer (no green/cheapest keys)."""
    return {
        "response": io.BytesIO(
            json.dumps({"errorMessage": "No billing history for 'CUST-999'"}).encode()
        ),
        "contentType": "application/json",
        "statusCode": 200,
    }


# --- Phase 6 narrative fixtures ---


@pytest.fixture
def mock_trackinfo():
    """Baseline valid-narrative TrackInfo dict — tests override specific fields.

    Narrative strings chosen to pass the validator (no digits, no banned terms,
    within word + char caps).
    """
    return {
        "plan_id": "ECO",
        "plan_name": "EcoFlex",
        "saving_monthly": 30.00,
        "saving_annual": 360.00,
        "usage_narrative": "Winter-heavy household with consistent mid-range usage across the year.",
        "call_script": "Ask about EcoFlex — it suits a strong winter-heating profile like yours.",
    }


@pytest.fixture
def clean_narrative_sample():
    """A known-clean narrative string that passes every validator rule."""
    return "Winter-heavy household with consistent mid-range usage across the year"


@pytest.fixture
def poisoned_narrative_samples():
    """List of (sample, reason) tuples covering each banned category."""
    return [
        ("Saves about 30 dollars a month",        "digit"),
        ("Saves $30 monthly",                       "currency"),
        ("Saves about 15% extra",                  "percent"),
        ("Origin customers often enquire",         "competitor-origin"),
        ("Compared with AGL plans",                "competitor-agl"),
        ("Better than EnergyAustralia",            "competitor-ea"),
        ("Prefer Red Energy? Reconsider",          "competitor-red"),
        ("Households moving to Alinta",            "competitor-alinta-and-move"),
        ("Momentum customers often ask",           "competitor-momentum"),
        ("Switch to EcoFlex to save",              "switch-verb"),
        ("Moving the household to EcoFlex",        "move-verb"),
        ("Changing plans helps in winter",         "change-verb"),
        ("Transferring to a cheaper plan",         "transfer-verb"),
        ("Swapping plans reduces cost",            "swap-verb"),
        ("Shifting from the standard plan",        "shift-verb"),
        ("Converting over to EcoFlex",             "convert-verb"),
        ("The greenest option available",          "env-superlative-greenest"),
        ("The cleanest option on the market",      "env-superlative-cleanest"),
        ("A most sustainable household choice",    "env-superlative-sustainable"),
        ("A carbon-neutral recommendation",        "env-superlative-carbon-neutral"),
        ("A zero-emission tariff",                 "env-superlative-zero-emission"),
        ("A net-zero plan for the future",         "env-superlative-net-zero"),
        ("Best for the planet of the lot",         "env-superlative-planet"),
    ]
