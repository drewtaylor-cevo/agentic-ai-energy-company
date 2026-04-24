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
