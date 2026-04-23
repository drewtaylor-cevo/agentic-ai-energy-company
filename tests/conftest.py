"""Shared pytest fixtures for Phase 1 test suite."""
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
